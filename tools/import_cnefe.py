#!/usr/bin/env python3
"""
IBGE CNEFE 2022 Address & Geocode Importer for PostgreSQL/PostGIS.

Downloads official CNEFE (Censo Demográfico 2022) open datasets from IBGE,
processes addresses and GPS coordinates, and loads them directly into PostGIS.
"""

import argparse
import csv
import gzip
import io
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Optional
import unicodedata
import urllib.request
import uuid
import zipfile


def generate_uuid7() -> str:
    """Generates an RFC 9562 UUIDv7 string."""
    try:
        import uuid6
        return str(uuid6.uuid7())
    except ImportError:
        pass
    try:
        import uuid_extensions
        return str(uuid_extensions.uuid7())
    except ImportError:
        pass
    # Standard RFC 9562 UUIDv7 implementation
    ns = time.time_ns()
    ms = ns // 1_000_000
    rand_bytes = secrets.token_bytes(10)
    time_bytes = ms.to_bytes(6, byteorder="big")
    ver_and_rand_a = (0x7000 | (int.from_bytes(rand_bytes[:2], "big") & 0x0FFF)).to_bytes(2, "big")
    var_and_rand_b = (0x80 | (rand_bytes[2] & 0x3F)).to_bytes(1, "big") + rand_bytes[3:10]
    raw = time_bytes + ver_and_rand_a + var_and_rand_b
    return str(uuid.UUID(bytes=raw))


def load_env() -> None:
    """Loads environment variables from .env in the repository root if present."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'").strip('"')
                    if k not in os.environ:
                        os.environ[k] = v

load_env()

UF_CODE_MAP = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
    "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
    "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53"
}

def remove_accents(input_str: str) -> str:
    """Normalizes characters removing diacritics and converting to uppercase."""
    if not input_str:
        return ""
    nfkd = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper().strip()

def psql_base_cmd() -> list:
    """Returns the base command list for executing psql commands via Docker or directly."""
    user = os.getenv("POSTGRES_USER", "postgres")
    db = os.getenv("POSTGRES_DB", "address_db")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    password = os.getenv("POSTGRES_PASSWORD")
    if host:
        if password and not os.environ.get("PGPASSWORD"):
            os.environ["PGPASSWORD"] = password
        return ["psql", "-h", host, "-p", port, "-U", user, "-d", db, "-w"]
    container = os.getenv("POSTGRES_CONTAINER", "postgis_br")
    return ["docker", "exec", "-i", container, "psql", "-U", user, "-d", db]

def get_target_ufs(uf_arg: str, all_flag: bool = False) -> list[str]:
    """Resolves target UF list from CLI arguments (supports BR / ALL / comma-separated list)."""
    if all_flag or (uf_arg and uf_arg.strip().upper() in ("BR", "ALL", "BRASIL")):
        return sorted(list(UF_CODE_MAP.keys()))

    ufs = [u.strip().upper() for u in uf_arg.split(",") if u.strip()]
    if not ufs:
        raise ValueError("Nenhuma UF informada. Forneça uma sigla (ex: SP, PA), uma lista (ex: SP,RJ) ou 'BR' para todos os estados.")

    for u in ufs:
        if u not in UF_CODE_MAP:
            raise ValueError(f"UF inválida: '{u}'. Use uma sigla válida (ex: SP, RJ, MG) ou 'BR' / --all para o Brasil inteiro.")
    return ufs

def get_municipality_map() -> dict:
    """Fetches official IBGE code -> (Municipality Name, UF) mapping from IBGE API."""
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    print("Obtendo lista oficial de municípios do IBGE...")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode('utf-8'))
            muni_map = {}
            for item in data:
                muni_id = item["id"]
                name = remove_accents(item["nome"])
                uf = ""
                if item.get("microrregiao"):
                    uf = item["microrregiao"]["mesorregiao"]["UF"]["sigla"]
                elif item.get("regiao-imediata"):
                    uf = item["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
                muni_map[muni_id] = (name, uf)
            print(f"✅ {len(muni_map):,} municípios mapeados com sucesso.")
            return muni_map
    except Exception as e:
        raise RuntimeError(f"Não foi possível obter o mapeamento de municípios do IBGE: {e}") from e


def validate_cnefe_zip(zip_path: str, deep: bool = True) -> bool:
    """Returns whether a downloaded CNEFE archive is readable and contains a CSV."""
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            if find_csv_filename(archive.namelist()) is None:
                return False
            return archive.testzip() is None if deep else True
    except (OSError, zipfile.BadZipFile):
        return False


def find_csv_filename(names: list[str]) -> Optional[str]:
    """Returns the first CSV member name, case-insensitively."""
    return next((name for name in names if name.lower().endswith(".csv")), None)


def download_cnefe(uf: str, dest_dir: str) -> str:
    """Downloads official CNEFE zip file from IBGE with atomic file writing."""
    uf_upper = uf.upper()
    code = UF_CODE_MAP.get(uf_upper)
    if not code:
        if uf_upper in ("BR", "ALL", "BRASIL"):
            raise ValueError(f"O IBGE divide o CNEFE por estados. Use o importador com '--uf BR' ou '--all' para iterar por todas as 27 UFs.")
        raise ValueError(f"UF inválida: {uf}")

    filename = f"{code}_{uf_upper}.zip"
    dest_path = os.path.join(dest_dir, filename)
    try:
        cached_size = os.path.getsize(dest_path)
    except FileNotFoundError:
        cached_size = 0
    if cached_size > 1000000:
        if validate_cnefe_zip(dest_path, deep=False):
            print(f"Arquivo já existe em cache: {dest_path} ({cached_size/(1024*1024):.2f} MB)")
            return dest_path
        print(f"Arquivo em cache inválido; baixando novamente: {dest_path}")
        try:
            os.remove(dest_path)
        except FileNotFoundError:
            pass

    url = f"https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/{filename}"
    print(f"Baixando CNEFE oficial do IBGE para {uf_upper}: {url}")
    print(f"Destino local: {dest_path}")

    start_time = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': 'PostGIS-CNEFE-Importer/1.0'})
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=f".{filename}.", suffix=".tmp", dir=dest_dir)
    os.close(tmp_fd)
    try:
        with urllib.request.urlopen(req, timeout=120) as response, open(tmp_path, "wb") as out_file:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 1024 * 1024

            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    mb_down = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"\rProgresso do Download: {percent:.1f}% ({mb_down:.1f}/{mb_total:.1f} MB)", end="", flush=True)

        if total_size > 0 and downloaded != total_size:
            raise IOError(f"Download truncado para {uf_upper}: recebidos {downloaded} bytes de {total_size} bytes esperados.")

        if not validate_cnefe_zip(tmp_path):
            raise IOError(f"Download inválido ou corrompido para {uf_upper}; arquivo ZIP não foi salvo em cache.")

        os.replace(tmp_path, dest_path)
        elapsed = time.time() - start_time
        print(f"\n✅ Download concluído em {elapsed:.1f}s ({os.path.getsize(dest_path)/(1024*1024):.2f} MB).")
        return dest_path
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def ensure_tables_exist() -> None:
    """Ensures that the target table and required extensions exist in PostgreSQL."""
    sql = """
    BEGIN;
    SELECT pg_advisory_xact_lock(hashtext('address_standardizer:cnefe_schema'));

    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    CREATE TABLE IF NOT EXISTS cnefe_enderecos (
        id bigserial PRIMARY KEY,
        cod_municipio_ibge integer NOT NULL,
        municipio text NOT NULL,
        uf varchar(2) NOT NULL,
        tipo text,
        titulo text,
        logradouro text NOT NULL,
        numero text,
        modificador text,
        bairro text,
        cep varchar(9),
        latitude double precision,
        longitude double precision,
        geom geometry(Point, 4326)
    );
    COMMIT;
    """
    subprocess.run(psql_base_cmd() + ["-c", sql], check=True)


def stage_table_name(uf: str) -> str:
    """Returns a PostgreSQL-safe, collision-resistant staging-table name."""
    run_id = generate_uuid7().replace("-", "")
    return f"cnefe_stage_{uf.lower()}_{run_id}"


def import_cnefe_to_postgres(
    zip_path: str,
    uf: str,
    limit: Optional[int] = None,
    muni_map: Optional[dict] = None
) -> int:
    """Streams CSV data from zip file into PostgreSQL via staging table with COPY and builds spatial indexes."""
    uf_upper = uf.upper()
    if uf_upper not in UF_CODE_MAP:
        raise ValueError(f"UF inválida: {uf}")
    if limit is not None and limit <= 0:
        raise ValueError("--limit deve ser um número inteiro positivo.")

    ensure_tables_exist()

    # Reject partial --limit if the target UF already contains complete data
    if limit is not None:
        count_cmd = psql_base_cmd() + ["-t", "-A", "-c", f"SELECT count(*) FROM cnefe_enderecos WHERE uf = '{uf_upper}';"]
        res = subprocess.run(count_cmd, capture_output=True, text=True, check=True)
        existing_count = int(res.stdout.strip() or 0)
        if existing_count > 0:
            raise ValueError(
                f"A UF '{uf_upper}' já possui {existing_count:,} registros no banco. "
                "Substituição parcial com --limit foi rejeitada para evitar perda de dados existentes. "
                "Execute sem --limit para atualizar o estado completo."
            )

    if muni_map is None:
        muni_map = get_municipality_map()

    stage_table = stage_table_name(uf_upper)
    print(f"Preparando importação para UF: {uf_upper} (tabela temporária: {stage_table})...")
    create_stage_sql = f"""
    CREATE UNLOGGED TABLE IF NOT EXISTS {stage_table} (
        cod_municipio_ibge integer NOT NULL,
        municipio text NOT NULL,
        uf varchar(2) NOT NULL,
        tipo text,
        titulo text,
        logradouro text NOT NULL,
        numero text,
        modificador text,
        bairro text,
        cep varchar(9),
        latitude double precision,
        longitude double precision
    );
    TRUNCATE {stage_table};
    """
    subprocess.run(psql_base_cmd() + ["-c", create_stage_sql], check=True)

    try:
        print(f"Lendo e transmitindo dados de {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            csv_filename = find_csv_filename(z.namelist())
            if not csv_filename:
                raise FileNotFoundError(f"Nenhum arquivo CSV encontrado dentro do arquivo ZIP: {zip_path}")
            print(f"Arquivo CSV interno: {csv_filename}")

            copy_sql = (
                f"COPY {stage_table} (cod_municipio_ibge, municipio, uf, tipo, titulo, logradouro, "
                "numero, modificador, bairro, cep, latitude, longitude) FROM STDIN "
                "WITH (FORMAT csv, DELIMITER E'\\t', QUOTE '\"', ESCAPE '\"', NULL '');"
            )
            psql_cmd = psql_base_cmd() + ["-c", copy_sql]

            proc = subprocess.Popen(psql_cmd, stdin=subprocess.PIPE, text=True, bufsize=65536)
            try:
                tsv_writer = csv.writer(proc.stdin, delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)

                start_time = time.time()
                count = 0

                with z.open(csv_filename, 'r') as raw_file:
                    text_stream = io.TextIOWrapper(raw_file, encoding='utf-8-sig', errors='ignore')
                    reader = csv.DictReader(text_stream, delimiter=';')

                    for row in reader:
                        cod_muni_str = row.get("COD_MUNICIPIO", "").strip()
                        if not cod_muni_str:
                            continue
                        try:
                            cod_muni = int(cod_muni_str)
                        except ValueError:
                            continue
                        if not cod_muni:
                            continue

                        logr_base = remove_accents(row.get("NOM_SEGLOGR", ""))
                        if not logr_base:
                            continue  # Filter out records without a street name

                        muni_info = muni_map.get(cod_muni, ("", uf_upper))
                        municipio = muni_info[0]
                        if not municipio:
                            continue  # Filter out records without a mapped municipality name
                        muni_uf = muni_info[1]
                        if muni_uf and muni_uf != uf_upper:
                            continue  # Reject records whose municipality belongs to another UF

                        tipo = remove_accents(row.get("NOM_TIPO_SEGLOGR", ""))
                        titulo = remove_accents(row.get("NOM_TITULO_SEGLOGR", ""))
                        # NOM_SEGLOGR is the canonical key emitted as p.name by the standardizer.
                        logradouro = logr_base

                        numero = row.get("NUM_ENDERECO", "").strip()
                        modificador = row.get("DSC_MODIFICADOR", "").strip()
                        bairro = remove_accents(row.get("DSC_LOCALIDADE", ""))
                        cep = row.get("CEP", "").strip()
                        # CNEFE 2022's published CSV dictionary names these columns exactly.
                        lat_str = row.get("LATITUDE", "").replace(",", ".").strip()
                        lon_str = row.get("LONGITUDE", "").replace(",", ".").strip()

                        tsv_writer.writerow([
                            cod_muni, municipio, uf_upper, tipo, titulo, logradouro,
                            numero, modificador, bairro, cep, lat_str, lon_str
                        ])
                        count += 1

                        if count % 100000 == 0:
                            elapsed = time.time() - start_time
                            speed = count / elapsed if elapsed > 0 else 0
                            print(f"\rProcessando e inserindo: {count:,} linhas ({speed:.0f} linhas/s)...", end="", flush=True)

                        if limit is not None and count >= limit:
                            break

                proc.stdin.close()
                return_code = proc.wait()
                if return_code != 0:
                    raise subprocess.CalledProcessError(return_code, psql_cmd)
            except BaseException:
                try:
                    proc.stdin.close()
                except (OSError, ValueError):
                    pass
                try:
                    proc.wait()
                except OSError:
                    pass
                raise

            elapsed = time.time() - start_time
            print(f"\n✅ Total inserido em staging ({stage_table}): {count:,} registros em {elapsed:.1f}s.")

        if count == 0:
            print(f"⚠️ Nenhum registro válido encontrado em {zip_path} para a UF {uf_upper}. Importação abortada e dados existentes preservados.")
            return 0

        print(f"\nAplicando transação atômica para substituir dados da UF: {uf_upper}...")
        partial_limit_guard_sql = ""
        if limit is not None:
            partial_limit_guard_sql = f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM cnefe_enderecos WHERE uf = '{uf_upper}') THEN
                    RAISE EXCEPTION 'Substituição parcial com --limit foi rejeitada para a UF {uf_upper}';
                END IF;
            END
            $$;
            """
        atomic_swap_sql = f"""
        BEGIN;
        SELECT pg_advisory_xact_lock(hashtext('cnefe_enderecos:{uf_upper}'));
        {partial_limit_guard_sql}
        DELETE FROM cnefe_enderecos WHERE uf = '{uf_upper}';
        INSERT INTO cnefe_enderecos (
            cod_municipio_ibge, municipio, uf, tipo, titulo, logradouro,
            numero, modificador, bairro, cep, latitude, longitude, geom
        )
        SELECT
            cod_municipio_ibge, municipio, uf, tipo, titulo, logradouro,
            numero, modificador, bairro, cep, latitude, longitude,
            CASE
                WHEN latitude IS NOT NULL AND longitude IS NOT NULL
                THEN ST_SetSRID(ST_Point(longitude, latitude), 4326)
            END
        FROM {stage_table};
        DROP TABLE IF EXISTS {stage_table};
        COMMIT;
        """
        subprocess.run(psql_base_cmd() + ["-c", atomic_swap_sql], check=True)

        print("Criando índices espaciais PostGIS...")
        post_import_sql = f"""
        BEGIN;
        SELECT pg_advisory_xact_lock(hashtext('address_standardizer:cnefe_schema'));
        CREATE INDEX IF NOT EXISTS idx_cnefe_lookup ON cnefe_enderecos (uf, municipio, logradouro, numero);
        CREATE INDEX IF NOT EXISTS idx_cnefe_cep ON cnefe_enderecos (cep);
        CREATE INDEX IF NOT EXISTS idx_cnefe_geom ON cnefe_enderecos USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_cnefe_geog ON cnefe_enderecos USING GIST ((geom::geography));
        CREATE INDEX IF NOT EXISTS idx_cnefe_logr_trgm ON cnefe_enderecos USING GIN (logradouro gin_trgm_ops);
        ANALYZE cnefe_enderecos;
        COMMIT;
        """
        subprocess.run(psql_base_cmd() + ["-c", post_import_sql], check=True)
        print(f"✅ Geometrias PostGIS e índices otimizados para {uf_upper} com sucesso!")
        return count
    finally:
        cleanup_sql = f"DROP TABLE IF EXISTS {stage_table};"
        subprocess.run(psql_base_cmd() + ["-c", cleanup_sql], capture_output=True)

def positive_int(value: str) -> int:
    """argparse converter for a positive row limit."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("deve ser um número inteiro positivo")
    return parsed


def main() -> None:
    """Main CLI entrypoint for CNEFE address importer."""
    default_dest = os.getenv("CNEFE_DOWNLOAD_DIR")
    if not default_dest:
        pg_data = os.getenv("POSTGRES_DATA_DIR", "./.pgdata")
        if "/Volumes/" in pg_data:
            default_dest = os.path.join(os.path.dirname(pg_data), "downloads_cnefe")
        else:
            default_dest = "./downloads_cnefe"

    parser = argparse.ArgumentParser(description="Import CNEFE 2022 address and geocode datasets into PostGIS.")
    parser.add_argument(
        "--uf",
        type=str,
        default="PA",
        help="Sigla da UF (ex: PA, SP, RJ), lista separada por vírgula (ex: SP,RJ,MG) ou 'BR' para o Brasil completo."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Importa todos os 27 estados do Brasil sequencialmente."
    )
    parser.add_argument(
        "--dest",
        type=str,
        default=default_dest,
        help="Diretório de download para os arquivos ZIP do IBGE."
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="Limite de linhas para teste por UF."
    )
    args = parser.parse_args()

    os.makedirs(args.dest, exist_ok=True)
    target_ufs = get_target_ufs(args.uf, args.all)

    print("\n=================================================================")
    print("🗺️  Importador IBGE CNEFE 2022 -> PostgreSQL/PostGIS")
    print(f"📌  UFs selecionadas ({len(target_ufs)}): {', '.join(target_ufs)}")
    print(f"📂  Pasta de download: {args.dest}")
    if args.limit is not None:
        print(f"⚠️  Limite de teste: {args.limit:,} linhas por UF")
    print("=================================================================\n")

    # Fetch municipality map once for all UFs
    muni_map = get_municipality_map()
    total_start = time.time()
    total_imported = 0
    failures = []

    for idx, uf in enumerate(target_ufs, start=1):
        print(f"\n[{idx}/{len(target_ufs)}] >>> Iniciando UF: {uf} <<<")
        try:
            zip_path = download_cnefe(uf, args.dest)
            count = import_cnefe_to_postgres(zip_path, uf, args.limit, muni_map=muni_map)
            total_imported += count
        except Exception as exc:
            print(f"❌ Falha na UF {uf}: {exc}", file=sys.stderr)
            failures.append((uf, str(exc)))

    total_elapsed = time.time() - total_start
    print("\n=================================================================")
    if failures:
        print("⚠️  Importação CNEFE concluída com falhas.")
    else:
        print("🎉 Importação CNEFE Concluída com Sucesso!")
    print(f"📊 Total de UFs processadas: {len(target_ufs) - len(failures)}")
    print(f"❌ Total de UFs com falha: {len(failures)}")
    for uf, error in failures:
        print(f"   - {uf}: {error}")
    print(f"📍 Total de registros inseridos no PostGIS: {total_imported:,}")
    print(f"⏱️  Tempo total: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print("=================================================================\n")

    if failures:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
