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
import subprocess
import sys
import time
import unicodedata
import urllib.request
import zipfile

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

def download_cnefe(uf: str, dest_dir: str) -> str:
    """Downloads official CNEFE zip file from IBGE with atomic file writing."""
    uf_upper = uf.upper()
    code = UF_CODE_MAP.get(uf_upper)
    if not code:
        raise ValueError(f"UF inválida: {uf}")

    filename = f"{code}_{uf_upper}.zip"
    dest_path = os.path.join(dest_dir, filename)
    tmp_path = dest_path + ".tmp"

    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000000:
        print(f"Arquivo já existe em cache: {dest_path} ({os.path.getsize(dest_path)/(1024*1024):.2f} MB)")
        return dest_path

    url = f"https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/{filename}"
    print(f"Baixando CNEFE oficial do IBGE para {uf_upper}: {url}")
    print(f"Destino local: {dest_path}")

    start_time = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': 'PostGIS-CNEFE-Importer/1.0'})
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

    os.replace(tmp_path, dest_path)
    elapsed = time.time() - start_time
    print(f"\n✅ Download concluído em {elapsed:.1f}s ({os.path.getsize(dest_path)/(1024*1024):.2f} MB).")
    return dest_path

def ensure_tables_exist() -> None:
    """Ensures that the cnefe_enderecos table and required extensions exist in PostgreSQL."""
    sql = """
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    CREATE TABLE IF NOT EXISTS cnefe_enderecos (
        id bigserial PRIMARY KEY,
        cod_municipio_ibge integer NOT NULL,
        municipio text,
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
    """
    subprocess.run([
        "docker", "exec", "-i", "postgis_br", "psql", "-U", os.getenv("POSTGRES_USER", "postgres"),
        "-d", os.getenv("POSTGRES_DB", "address_db"), "-c", sql
    ], check=True)

def import_cnefe_to_postgres(zip_path: str, uf: str, limit: int = None) -> None:
    """Streams CSV data from zip file into PostgreSQL with COPY and builds spatial indexes."""
    ensure_tables_exist()
    muni_map = get_municipality_map()
    uf_upper = uf.upper()

    print(f"Preparando importação para UF: {uf_upper}...")
    # Idempotent replacement for this UF
    subprocess.run([
        "docker", "exec", "-i", "postgis_br", "psql", "-U", os.getenv("POSTGRES_USER", "postgres"),
        "-d", os.getenv("POSTGRES_DB", "address_db"),
        "-c", f"DELETE FROM cnefe_enderecos WHERE uf = '{uf_upper}';"
    ], check=True)

    print(f"Lendo e transmitindo dados de {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        csv_filename = [name for name in z.namelist() if name.endswith('.csv')][0]
        print(f"Arquivo CSV interno: {csv_filename}")
        
        psql_cmd = [
            "docker", "exec", "-i", "postgis_br", "psql", "-U", os.getenv("POSTGRES_USER", "postgres"),
            "-d", os.getenv("POSTGRES_DB", "address_db"),
            "-c", "COPY cnefe_enderecos (cod_municipio_ibge, municipio, uf, tipo, titulo, logradouro, numero, modificador, bairro, cep, latitude, longitude) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '');"
        ]

        proc = subprocess.Popen(psql_cmd, stdin=subprocess.PIPE, text=True, bufsize=65536)
        
        start_time = time.time()
        count = 0
        
        with z.open(csv_filename, 'r') as raw_file:
            text_stream = io.TextIOWrapper(raw_file, encoding='utf-8', errors='ignore')
            reader = csv.DictReader(text_stream, delimiter=';')
            
            for row in reader:
                try:
                    cod_muni = int(row.get("COD_MUNICIPIO", 0))
                except ValueError:
                    continue
                
                muni_info = muni_map.get(cod_muni, ("", uf_upper))
                municipio = muni_info[0]
                
                tipo = remove_accents(row.get("NOM_TIPO_SEGLOGR", ""))
                titulo = remove_accents(row.get("NOM_TITULO_SEGLOGR", ""))
                logr_base = remove_accents(row.get("NOM_SEGLOGR", ""))
                
                if titulo:
                    logradouro = f"{titulo} {logr_base}".strip()
                else:
                    logradouro = logr_base
                
                numero = row.get("NUM_ENDERECO", "").strip()
                modificador = row.get("DSC_MODIFICADOR", "").strip()
                bairro = remove_accents(row.get("DSC_LOCALIDADE", ""))
                cep = row.get("CEP", "").strip()
                
                lat_str = row.get("LATITUDE", "").replace(",", ".").strip()
                lon_str = row.get("LONGITUDE", "").replace(",", ".").strip()
                
                tsv_line = f"{cod_muni}\t{municipio}\t{uf_upper}\t{tipo}\t{titulo}\t{logradouro}\t{numero}\t{modificador}\t{bairro}\t{cep}\t{lat_str}\t{lon_str}\n"
                proc.stdin.write(tsv_line)
                count += 1
                
                if count % 100000 == 0:
                    elapsed = time.time() - start_time
                    speed = count / elapsed if elapsed > 0 else 0
                    print(f"\rProcessando e inserindo: {count:,} linhas ({speed:.0f} linhas/s)...", end="", flush=True)
                
                if limit and count >= limit:
                    break
        
        proc.stdin.close()
        return_code = proc.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, psql_cmd)
        
        elapsed = time.time() - start_time
        print(f"\n✅ Total inserido no banco: {count:,} registros em {elapsed:.1f}s.")

    print("\nAtualizando geometrias espaciais PostGIS e criando índices...")
    post_import_sql = f"""
    UPDATE cnefe_enderecos 
    SET geom = ST_SetSRID(ST_Point(longitude, latitude), 4326) 
    WHERE uf = '{uf_upper}' AND geom IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL;
    
    CREATE INDEX IF NOT EXISTS idx_cnefe_lookup ON cnefe_enderecos (uf, municipio, logradouro, numero);
    CREATE INDEX IF NOT EXISTS idx_cnefe_cep ON cnefe_enderecos (cep);
    CREATE INDEX IF NOT EXISTS idx_cnefe_geom ON cnefe_enderecos USING GIST (geom);
    CREATE INDEX IF NOT EXISTS idx_cnefe_logr_trgm ON cnefe_enderecos USING GIN (logradouro gin_trgm_ops);
    """
    subprocess.run([
        "docker", "exec", "-i", "postgis_br", "psql", "-U", os.getenv("POSTGRES_USER", "postgres"),
        "-d", os.getenv("POSTGRES_DB", "address_db"), "-c", post_import_sql
    ], check=True)
    print("✅ Geometrias PostGIS e índices otimizados com sucesso!")

def main() -> None:
    """Main CLI entrypoint for CNEFE address importer."""
    default_dest = os.getenv("CNEFE_DOWNLOAD_DIR")
    if not default_dest:
        pg_data = os.getenv("POSTGRES_DATA_DIR", "./.pgdata")
        if "/Volumes/" in pg_data:
            default_dest = os.path.join(os.path.dirname(pg_data), "downloads_cnefe")
        else:
            default_dest = "./downloads_cnefe"

    parser = argparse.ArgumentParser(description="Import CNEFE data for a Brazilian state into PostGIS.")
    parser.add_argument("--uf", type=str, default="PA", help="Sigla da UF (ex: PA, SP, RJ, MG, SC).")
    parser.add_argument("--dest", type=str, default=default_dest, help="Diretório de download para os arquivos ZIP do IBGE.")
    parser.add_argument("--limit", type=int, default=None, help="Limite de linhas para teste.")
    args = parser.parse_args()

    os.makedirs(args.dest, exist_ok=True)
    zip_path = download_cnefe(args.uf, args.dest)
    import_cnefe_to_postgres(zip_path, args.uf, args.limit)

if __name__ == "__main__":
    main()
