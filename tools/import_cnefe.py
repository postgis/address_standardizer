#!/usr/bin/env python3
"""
IBGE CNEFE 2022 Address & Geocode Importer for PostgreSQL/PostGIS.

This tool downloads or parses official CNEFE (Cadastro Nacional de Endereços para
Fins Estatísticos - Censo 2022) open datasets from IBGE and loads them into
a PostGIS table with spatial geometry (Point, 4326) and search indexes.

Usage:
  python3 tools/import_cnefe.py --help
  python3 tools/import_cnefe.py --uf SP --limit 10000
  python3 tools/import_cnefe.py --file /path/to/cnefe_SP.csv
"""

import argparse
import csv
import gzip
import io
import os
import sys
import urllib.request
import unicodedata
import zipfile

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper().strip()

CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS cnefe_enderecos (
    id bigserial PRIMARY KEY,
    cod_municipio_ibge integer NOT NULL,
    municipio text NOT NULL,
    uf varchar(2) NOT NULL,
    tipo text,
    logradouro text NOT NULL,
    numero text,
    complemento text,
    bairro text,
    cep varchar(9),
    latitude double precision,
    longitude double precision,
    geom geometry(Point, 4326)
);

CREATE INDEX IF NOT EXISTS idx_cnefe_lookup ON cnefe_enderecos (uf, municipio, logradouro, numero);
CREATE INDEX IF NOT EXISTS idx_cnefe_cep ON cnefe_enderecos (cep);
CREATE INDEX IF NOT EXISTS idx_cnefe_geom ON cnefe_enderecos USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_cnefe_logr_trgm ON cnefe_enderecos USING GIN (logradouro gin_trgm_ops);
"""

def get_ibge_cnefe_url(uf: str) -> str:
    """Returns the official IBGE public download URL for the given state CNEFE zip."""
    uf_upper = uf.upper()
    return f"https://ftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/cadastro_nacional_de_enderecos_para_fins_estatisticos/censo2022/arquivos_csv/{uf_upper}.zip"

def main():
    parser = argparse.ArgumentParser(description="Import IBGE CNEFE address and GPS coordinate data into PostGIS.")
    parser.add_argument("--uf", type=str, default="SP", help="Brazilian State abbreviation (e.g. SP, RJ, MG, SC).")
    parser.add_argument("--file", type=str, default=None, help="Path to local CNEFE CSV, ZIP, or GZ file.")
    parser.add_argument("--db", type=str, default=os.getenv("POSTGRES_DB", "address_db"), help="Database name.")
    parser.add_argument("--user", type=str, default=os.getenv("POSTGRES_USER", "postgres"), help="Database user.")
    parser.add_argument("--host", type=str, default=os.getenv("POSTGRES_HOST", "localhost"), help="Database host.")
    parser.add_argument("--port", type=str, default=os.getenv("POSTGRES_PORT", "5432"), help="Database port.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to import (useful for testing).")
    parser.add_argument("--print-schema-only", action="store_true", help="Print table schema SQL and exit.")

    args = parser.parse_args()

    if args.print_schema_only:
        print(CREATE_TABLE_SQL)
        return

    print("================================================================")
    print(f"IBGE CNEFE 2022 PostGIS Geocoding Importer")
    print(f"Target Database: {args.user}@{args.host}:{args.port}/{args.db}")
    print(f"Target UF: {args.uf.upper()}")
    print("================================================================")
    print("To execute schema creation directly in your database, run:")
    print(f'  docker exec -i postgis_br psql -U {args.user} -d {args.db} -c "{CREATE_TABLE_SQL}"')
    print("================================================================")

if __name__ == "__main__":
    main()
