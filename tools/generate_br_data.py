#!/usr/bin/env python3
"""
Generator for PostGIS address_standardizer Brazilian Dataset (address_standardizer_data_br)
Data Sources:
  - IBGE (Instituto Brasileiro de Geografia e Estatística) - API de Localidades & CNEFE 2022 (Open Data / Public Domain)
  - OpenStreetMap (ODbL) terminology for Brazilian street types and qualifiers
Note:
  This dataset is strictly constructed from official public open data sources (IBGE/Gov.br).
  No proprietary postal database (such as Correios DNE) is used.
"""

import json
import urllib.request
import unicodedata
import os
import re

def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def normalize_text(text: str) -> str:
    return remove_accents(text).upper().strip()

def escape_sql(text: str) -> str:
    return text.replace("'", "''")

# -------------------------------------------------------------
# 1. BRAZILIAN LEXICON DEFINITION (br_lex)
# Token definitions from pagc_api.h:
# NUMBER = 0, WORD = 1, TYPE = 2, ROAD = 6, STOPWORD = 7, DASH = 9,
# AMPERS = 13, ORD = 15, SINGLE = 18, BUILDH = 19, DIRECT = 22,
# FRACT = 25
# -------------------------------------------------------------

# Brazilian Street Types (pretype / TYPE = 2)
# (variations, canonical standard word, token)
STREET_TYPES = [
    # (word, stdword, token)
    ("RUA", "RUA", 2),
    ("R", "RUA", 2),
    ("R.", "RUA", 2),
    ("AVENIDA", "AVENIDA", 2),
    ("AV", "AVENIDA", 2),
    ("AV.", "AVENIDA", 2),
    ("ALAMEDA", "ALAMEDA", 2),
    ("AL", "ALAMEDA", 2),
    ("AL.", "ALAMEDA", 2),
    ("TRAVESSA", "TRAVESSA", 2),
    ("TRAV", "TRAVESSA", 2),
    ("TV", "TRAVESSA", 2),
    ("TV.", "TRAVESSA", 2),
    ("RODOVIA", "RODOVIA", 6),
    ("ROD", "RODOVIA", 6),
    ("ROD.", "RODOVIA", 6),
    ("ESTRADA", "ESTRADA", 2),
    ("ESTR", "ESTRADA", 2),
    ("ESTR.", "ESTRADA", 2),
    ("PRACA", "PRACA", 2),
    ("PRAÇA", "PRACA", 2),
    ("PC", "PRACA", 2),
    ("PC.", "PRACA", 2),
    ("PÇA", "PRACA", 2),
    ("PÇA.", "PRACA", 2),
    ("LARGO", "LARGO", 2),
    ("LG", "LARGO", 2),
    ("LG.", "LARGO", 2),
    ("VIELA", "VIELA", 2),
    ("BECO", "BECO", 2),
    ("BC", "BECO", 2),
    ("BC.", "BECO", 2),
    ("PASSARELA", "PASSARELA", 2),
    ("PASSAGEM", "PASSAGEM", 2),
    ("PSG", "PASSAGEM", 2),
    ("VIADUTO", "VIADUTO", 2),
    ("VD", "VIADUTO", 2),
    ("PONTE", "PONTE", 2),
    ("PTE", "PONTE", 2),
    ("SERVIDAO", "SERVIDAO", 2),
    ("SERVIDÃO", "SERVIDAO", 2),
    ("SRV", "SERVIDAO", 2),
    ("CALCADA", "CALCADA", 2),
    ("CALÇADA", "CALCADA", 2),
    ("LADEIRA", "LADEIRA", 2),
    ("LAD", "LADEIRA", 2),
    ("LAD.", "LADEIRA", 2),
    ("RAMPA", "RAMPA", 2),
    ("TRECHO", "TRECHO", 2),
    ("TR", "TRECHO", 2),
    ("TREVO", "TREVO", 2),
    ("TRV", "TREVO", 2),
    ("PARQUE", "PARQUE", 2),
    ("PQ", "PARQUE", 2),
    ("PQ.", "PARQUE", 2),
    ("JARDIM", "JARDIM", 2),
    ("JD", "JARDIM", 2),
    ("JD.", "JARDIM", 2),
    ("VILA", "VILA", 2),
    ("VL", "VILA", 2),
    ("VL.", "VILA", 2),
    ("CONDOMINIO", "CONDOMINIO", 2),
    ("CONDOMÍNIO", "CONDOMINIO", 2),
    ("COND", "CONDOMINIO", 2),
    ("COND.", "CONDOMINIO", 2),
    ("RESIDENCIAL", "RESIDENCIAL", 2),
    ("RES", "RESIDENCIAL", 2),
    ("RES.", "RESIDENCIAL", 2),
    ("LOTEAMENTO", "LOTEAMENTO", 2),
    ("LOT", "LOTEAMENTO", 2),
    ("CHACARA", "CHACARA", 2),
    ("CHÁCARA", "CHACARA", 2),
    ("CH", "CHACARA", 2),
    ("CH.", "CHACARA", 2),
    ("FAZENDA", "FAZENDA", 2),
    ("FAZ", "FAZENDA", 2),
    ("FAZ.", "FAZENDA", 2),
    ("SITIO", "SITIO", 2),
    ("SÍTIO", "SITIO", 2),
    ("COLONIA", "COLONIA", 2),
    ("COLÔNIA", "COLONIA", 2),
    ("MORRO", "MORRO", 2),
    ("ALTO", "ALTO", 2),
    ("BALNEARIO", "BALNEARIO", 2),
    ("BALNEÁRIO", "BALNEARIO", 2),
    ("SETOR", "SETOR", 2),
    ("ST", "SETOR", 2),
    ("ST.", "SETOR", 2),
    ("QUADRA", "QUADRA", 2),
    ("QD", "QUADRA", 2),
    ("QD.", "QUADRA", 2),
    ("Q.", "QUADRA", 2),
    ("SUPERQUADRA", "SUPERQUADRA", 2),
    ("SQS", "SUPERQUADRA SUL", 2),
    ("SQN", "SUPERQUADRA NORTE", 2),
    ("EQS", "ENTRE QUADRA SUL", 2),
    ("EQN", "ENTRE QUADRA NORTE", 2),
    ("SHIS", "SETOR DE HABITACOES INDIVIDUAIS SUL", 2),
    ("SHIN", "SETOR DE HABITACOES INDIVIDUAIS NORTE", 2),
    ("CLN", "COMERCIO LOCAL NORTE", 2),
    ("CLS", "COMERCIO LOCAL SUL", 2),
    ("CRN", "COMERCIO RESIDENCIAL NORTE", 2),
    ("CRS", "COMERCIO RESIDENCIAL SUL", 2),
    ("VIA", "VIA", 2),
    ("MARGINAL", "MARGINAL", 2),
    ("ANEL", "ANEL VIARIO", 2),
    ("CONTORNO", "CONTORNO", 2),
    # Highway identifiers (BR-101, SP-330, RJ-116, etc.)
    ("BR", "BR", 1),
    ("SP", "SP", 1),
    ("RJ", "RJ", 1),
    ("MG", "MG", 1),
    ("PR", "PR", 1),
    ("SC", "SC", 1),
    ("RS", "RS", 1),
    ("BA", "BA", 1),
    ("GO", "GO", 1),
    ("DF", "DF", 1),
    ("ES", "ES", 1),
    ("PE", "PE", 1),
    ("CE", "CE", 1),
    ("MT", "MT", 1),
    ("MS", "MS", 1),
    ("PA", "PA", 1),
    ("MA", "MA", 1),
    ("AM", "AM", 1),
    ("RN", "RN", 1),
    ("PB", "PB", 1),
    ("PI", "PI", 1),
    ("AL", "AL", 1),
    ("SE", "SE", 1),
    ("RO", "RO", 1),
    ("TO", "TO", 1),
    ("AC", "AC", 1),
    ("AP", "AP", 1),
    ("RR", "RR", 1),
]

# Complement / Unit words (BUILDH = 19, SINGLE = 18, etc.)
UNIT_WORDS = [
    ("APARTAMENTO", "APTO", 19),
    ("APTO", "APTO", 19),
    ("APT", "APTO", 19),
    ("AP", "APTO", 19),
    ("AP.", "APTO", 19),
    ("BLOCO", "BLOCO", 19),
    ("BL", "BLOCO", 19),
    ("BL.", "BLOCO", 19),
    ("SALA", "SALA", 19),
    ("SL", "SALA", 19),
    ("SL.", "SALA", 19),
    ("CONJUNTO", "CJTO", 19),
    ("CONJ", "CJTO", 19),
    ("CJ", "CJTO", 19),
    ("CJ.", "CJTO", 19),
    ("ANDAR", "ANDAR", 19),
    ("AND", "ANDAR", 19),
    ("PAVIMENTO", "PAVIMENTO", 19),
    ("PAV", "PAVIMENTO", 19),
    ("LOTE", "LOTE", 19),
    ("LT", "LOTE", 19),
    ("LT.", "LOTE", 19),
    ("CASA", "CASA", 19),
    ("CS", "CASA", 19),
    ("FUNDOS", "FUNDOS", 19),
    ("FDS", "FUNDOS", 19),
    ("FRENTE", "FRENTE", 19),
    ("FRT", "FRENTE", 19),
    ("SOBRADO", "SOBRADO", 19),
    ("SOB", "SOBRADO", 19),
    ("COBERTURA", "COBERTURA", 19),
    ("COB", "COBERTURA", 19),
    ("GALPAO", "GALPAO", 19),
    ("GALPÃO", "GALPAO", 19),
    ("GALP", "GALPAO", 19),
    ("GARAGEM", "GARAGEM", 19),
    ("GAR", "GARAGEM", 19),
    ("SUBSOLO", "SUBSOLO", 19),
    ("SS", "SUBSOLO", 19),
    ("LOJA", "LOJA", 19),
    ("LJ", "LOJA", 19),
    ("LJ.", "LOJA", 19),
    ("SOBRELOJA", "SOBRELOJA", 19),
    ("SLJ", "SOBRELOJA", 19),
    ("QUIOSQUE", "QUIOSQUE", 19),
    ("KM", "KM", 20),
    ("QUILOMETRO", "KM", 20),
    ("QUILÔMETRO", "KM", 20),
    ("NUMERO", "NUMERO", 19),
    ("NÚMERO", "NUMERO", 19),
    ("NUM", "NUMERO", 19),
    ("Nº", "NUMERO", 19),
    ("N.", "NUMERO", 19),
    ("NO", "NUMERO", 19),
    ("S/N", "S/N", 0),
    ("SN", "S/N", 0),
    ("SEM NUMERO", "S/N", 0),
    ("SEM NÚMERO", "S/N", 0),
]

# Cardinal Directions (DIRECT = 22)
DIRECTIONS = [
    ("NORTE", "NORTE", 22),
    ("SUL", "SUL", 22),
    ("LESTE", "LESTE", 22),
    ("OESTE", "OESTE", 22),
    ("CENTRO", "CENTRO", 22),
    ("NORDESTE", "NORDESTE", 22),
    ("NOROESTE", "NOROESTE", 22),
    ("SUDESTE", "SUDESTE", 22),
    ("SUDOESTE", "SUDOESTE", 22),
    ("N", "NORTE", 22),
    ("S", "SUL", 22),
    ("L", "LESTE", 22),
    ("O", "OESTE", 22),
    ("NE", "NORDESTE", 22),
    ("NO", "NOROESTE", 22),
    ("NW", "NOROESTE", 22),
    ("SE", "SUDESTE", 22),
    ("SO", "SUDOESTE", 22),
    ("SW", "SUDOESTE", 22),
]

# Stopwords & Connectors (STOPWORD = 7, AMPERS = 13, DASH = 9)
CONNECTORS = [
    ("DE", "DE", 7),
    ("DA", "DA", 7),
    ("DO", "DO", 7),
    ("DAS", "DAS", 7),
    ("DOS", "DOS", 7),
    ("E", "E", 7),
    ("D'", "D", 7),
    ("D", "D", 7),
    ("-", "-", 9),
    ("&", "E", 13),
    ("/", "/", 9),
    (",", ",", 9),
]

# -------------------------------------------------------------
# 2. BRAZILIAN STATES (UFs) AND NATION
# -------------------------------------------------------------
BRAZIL_STATES = [
    ("AC", "ACRE"),
    ("AL", "ALAGOAS"),
    ("AP", "AMAPA"),
    ("AM", "AMAZONAS"),
    ("BA", "BAHIA"),
    ("CE", "CEARA"),
    ("DF", "DISTRITO FEDERAL"),
    ("ES", "ESPIRITO SANTO"),
    ("GO", "GOIAS"),
    ("MA", "MARANHAO"),
    ("MT", "MATO GROSSO"),
    ("MS", "MATO GROSSO DO SUL"),
    ("MG", "MINAS GERAIS"),
    ("PA", "PARA"),
    ("PB", "PARAIBA"),
    ("PR", "PARANA"),
    ("PE", "PERNAMBUCO"),
    ("PI", "PIAUI"),
    ("RJ", "RIO DE JANEIRO"),
    ("RN", "RIO GRANDE DO NORTE"),
    ("RS", "RIO GRANDE DO SUL"),
    ("RO", "RONDONIA"),
    ("RR", "RORAIMA"),
    ("SC", "SANTA CATARINA"),
    ("SP", "SAO PAULO"),
    ("SE", "SERGIPE"),
    ("TO", "TOCANTINS")
]

import json
import urllib.request
import unicodedata
import os
import re
import gzip

def fetch_ibge_municipalities():
    """Fetches all 5,570 Brazilian municipalities from the official IBGE Open Data API."""
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    print(f"Fetching IBGE municipalities from {url}...")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'PostGIS-Address-Standardizer-BR-Generator/1.0',
            'Accept-Encoding': 'gzip, deflate'
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            raw_data = response.read()
            # Check if gzip compressed (magic bytes 0x1f, 0x8b)
            if raw_data[:2] == b'\x1f\x8b' or response.headers.get('Content-Encoding') == 'gzip':
                raw_data = gzip.decompress(raw_data)
            data = json.loads(raw_data.decode('utf-8'))
            print(f"Successfully fetched {len(data)} municipalities from IBGE API.")
            return data
    except Exception as e:
        raise RuntimeError(f"Erro crítico: Não foi possível obter a lista de municípios do IBGE ({e}).") from e

def generate_br_lex_sql(output_path: str):
    """Generates sql/23_br_lex.sql with Brazilian thoroughfares, units, and connectors."""
    entries = []
    
    # Add Street Types
    for word, stdword, tok in STREET_TYPES:
        entries.append((1, word, stdword, tok))
        norm = normalize_text(word)
        if norm != word:
            entries.append((1, norm, normalize_text(stdword), tok))

    # Add Unit Words
    for word, stdword, tok in UNIT_WORDS:
        entries.append((1, word, stdword, tok))
        norm = normalize_text(word)
        if norm != word:
            entries.append((1, norm, normalize_text(stdword), tok))

    # Add Directions
    for word, stdword, tok in DIRECTIONS:
        entries.append((1, word, stdword, tok))
        norm = normalize_text(word)
        if norm != word:
            entries.append((1, norm, normalize_text(stdword), tok))

    # Add Connectors
    for word, stdword, tok in CONNECTORS:
        entries.append((1, word, stdword, tok))

    # Deduplicate entries by (word, stdword, token)
    seen = set()
    unique_entries = []
    for seq, word, stdword, tok in entries:
        key = (word.upper(), stdword.upper(), tok)
        if key not in seen:
            seen.add(key)
            unique_entries.append((seq, word.upper(), stdword.upper(), tok))

    # Sort
    unique_entries.sort(key=lambda x: (x[1], x[2], x[3]))

    # Calculate monotonic seq for identical words
    word_counters = {}
    final_entries = []
    for _, word, stdword, tok in unique_entries:
        seq = word_counters.get(word, 0) + 1
        word_counters[word] = seq
        final_entries.append((seq, word, stdword, tok))
    unique_entries = final_entries


    with open(output_path, "w", encoding="utf-8") as f:
        f.write("-- ==========================================================================\n")
        f.write("-- PostGIS address_standardizer: Brazilian Lexicon Dataset (br_lex)\n")
        f.write("-- Data Provenance: Derived from official Brazilian public open data (IBGE / OpenStreetMap)\n")
        f.write("-- License: Public Domain / Open Source (BSD/PostGIS License)\n")
        f.write("-- ==========================================================================\n\n")
        f.write("CREATE TABLE IF NOT EXISTS br_lex (\n")
        f.write("    id serial,\n")
        f.write("    seq integer,\n")
        f.write("    word text,\n")
        f.write("    stdword text,\n")
        f.write("    token integer, is_custom boolean NOT NULL DEFAULT true, CONSTRAINT pk_br_lex PRIMARY KEY(id)\n")
        f.write(");\n\n")
        f.write("-- Upgrade protection for custom entries\n")
        f.write("DELETE FROM br_lex WHERE is_custom = false;\n\n")
        f.write("-- Default is_custom to false for shipped entries\n")
        f.write("ALTER TABLE br_lex ALTER COLUMN is_custom SET DEFAULT false;\n\n")
        
        f.write("INSERT INTO br_lex (seq, word, stdword, token)\nWITH t(seq,word,stdword,token) AS ( VALUES \n")
        lines = []
        for seq, word, stdword, tok in unique_entries:
            lines.append(f"({seq}, '{escape_sql(word)}', '{escape_sql(stdword)}', {tok})")
        f.write(",\n".join(lines))
        f.write("\n)\nSELECT seq, word, stdword, token FROM t;\n")

    print(f"Generated {output_path} with {len(unique_entries)} lexicon entries.")

def generate_br_gaz_sql(output_path: str, ibge_data: list):
    """Generates sql/24_br_gaz.sql with all Brazilian Municipalities, States, and Country."""
    # Token 10 = CITY, Token 11 = PROV (State), Token 12 = NATION, Token 1 = WORD
    gaz_entries = []

    # 1. Country & Highway Acronyms
    gaz_entries.append((1, "BRASIL", "BRASIL", 12))
    gaz_entries.append((2, "BRASIL", "BRASIL", 1))
    gaz_entries.append((1, "BRAZIL", "BRASIL", 12))
    gaz_entries.append((1, "BR", "BRASIL", 12))
    gaz_entries.append((2, "BR", "BR", 1))
    gaz_entries.append((3, "BR", "BR", 6))


    # 2. States (Siglas and Full Names)
    for sigla, name in BRAZIL_STATES:
        norm_name = normalize_text(name)
        # Sigla as State (Token 11 = PROV) and Word (Token 1)
        gaz_entries.append((1, sigla, sigla, 11))
        gaz_entries.append((2, sigla, sigla, 1))

        # Full state name as State (Token 11)
        gaz_entries.append((1, norm_name, sigla, 11))
        gaz_entries.append((2, norm_name, norm_name, 1))

        if norm_name != name.upper():
            gaz_entries.append((1, name.upper(), sigla, 11))

    # 3. Municipalities (From IBGE)
    if ibge_data:
        for mun in ibge_data:
            nome = mun.get('nome', '').strip()
            if nome:
                norm_nome = normalize_text(nome)
                # City entry (Token 10 = CITY)
                gaz_entries.append((1, norm_nome, norm_nome, 10))
                gaz_entries.append((2, norm_nome, norm_nome, 1))
                if nome.upper() != norm_nome:
                    gaz_entries.append((1, nome.upper(), norm_nome, 10))
    else:
        # Fallback major capitals
        capitals = [
            "SAO PAULO", "RIO DE JANEIRO", "BRASILIA", "SALVADOR", "FORTALEZA",
            "BELO HORIZONTE", "MANAUS", "CURITIBA", "RECIFE", "GOIANIA",
            "BELEM", "PORTO ALEGRE", "GUARULHOS", "CAMPINAS", "SAO LUIS",
            "SAO GONCALO", "MACEIO", "DUQUE DE CAXIAS", "NATAL", "TERESINA",
            "SAO BERNARDO DO CAMPO", "CAMPO GRANDE", "OSASCO", "SANTO ANDRE",
            "JOAO PESSOA", "JABOATAO DOS GUARARAPES", "CONTAGEM", "SAO JOSE DOS CAMPOS",
            "UBERLANDIA", "FLORIANOPOLIS", "CUIABA", "ARACAJU", "VITORIA"
        ]
        for cap in capitals:
            gaz_entries.append((1, cap, cap, 10))
            gaz_entries.append((2, cap, cap, 1))

    # Clean sequence numbers per word
    word_groups = {}
    for seq, word, stdword, tok in gaz_entries:
        if word not in word_groups:
            word_groups[word] = []
        if (stdword, tok) not in [(sw, t) for _, sw, t in word_groups[word]]:
            s = len(word_groups[word]) + 1
            word_groups[word].append((s, stdword, tok))

    unique_gaz = []
    for word in sorted(word_groups.keys()):
        for seq, stdword, tok in word_groups[word]:
            unique_gaz.append((seq, word, stdword, tok))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("-- ==========================================================================\n")
        f.write("-- PostGIS address_standardizer: Brazilian Gazetteer Dataset (br_gaz)\n")
        f.write("-- Data Provenance: Official IBGE Localidades (Municipalities and States of Brazil)\n")
        f.write("-- License: Public Domain / Open Government Data\n")
        f.write("-- ==========================================================================\n\n")
        f.write("CREATE TABLE IF NOT EXISTS br_gaz (\n")
        f.write("    id serial,\n")
        f.write("    seq integer,\n")
        f.write("    word text,\n")
        f.write("    stdword text,\n")
        f.write("    token integer, is_custom boolean NOT NULL DEFAULT true, CONSTRAINT pk_br_gaz PRIMARY KEY(id)\n")
        f.write(");\n\n")
        f.write("-- Upgrade protection for custom entries\n")
        f.write("DELETE FROM br_gaz WHERE is_custom = false;\n\n")
        f.write("-- Default is_custom to false for shipped entries\n")
        f.write("ALTER TABLE br_gaz ALTER COLUMN is_custom SET DEFAULT false;\n\n")
        
        f.write("INSERT INTO br_gaz (seq, word, stdword, token)\nWITH t(seq,word,stdword,token) AS ( VALUES \n")
        lines = []
        for seq, word, stdword, tok in unique_gaz:
            lines.append(f"({seq}, '{escape_sql(word)}', '{escape_sql(stdword)}', {tok})")
        f.write(",\n".join(lines))
        f.write("\n)\nSELECT seq, word, stdword, token FROM t;\n")

    print(f"Generated {output_path} with {len(unique_gaz)} gazetteer entries.")

def generate_br_rules_sql(output_path: str):
    """
    Generates sql/25_br_rules.sql with PAGC grammar rules tuned for Brazilian addresses.
    
    Rule Types (from analyze.c / PAGC):
      0: MACRO_C (Macro address components: City, State, Country, Postal)
      1: MICRO_C (Micro address components: Street, Number, Unit, etc.)
      2: ARC_C
      3: CIVIC_C
      4: EXTRA_C (Unit / Occupancy details)
      
    Tokens:
    Input:
      0: NUMBER, 1: WORD, 2: TYPE, 6: ROAD, 7: STOPWORD, 9: DASH,
      11: STATE/PROV (in gaz), 12: COUNTRY/NATION (in gaz), 13: AMPERS,
      15: ORD, 16: UNITH, 18: SINGLE, 19: BUILDH, 20: MILE, 22: DIRECT,
      27, 28, 29: POSTAL
    Output:
      0: BLDNG, 1: HOUSE, 2: PREDIR, 3: QUALIF, 4: PRETYP, 5: STREET, 6: SUFTYP,
      7: SUFDIR, 8: RR, 9: UNKNWN, 10: CITY, 11: PROV, 12: NATION, 13: POSTAL,
      14: BOXH, 15: BOXT, 16: UNITH, 17: UNITT
    """
    rules = []

    # -------------------------------------------------------------
    # A. MICRO RULES (Rule Type 1 = MICRO_C)
    # -------------------------------------------------------------

    # 1. [TYPE] [STREET...] [NUMBER] (Canonical Brazilian Address)
    # Ex: Rua Augusta 100
    rules.append(([2, 1, 0], [4, 5, 1], 1, 16))
    rules.append(([2, 1, 1, 0], [4, 5, 5, 1], 1, 16))
    rules.append(([2, 1, 1, 1, 0], [4, 5, 5, 5, 1], 1, 16))
    rules.append(([2, 1, 1, 1, 1, 0], [4, 5, 5, 5, 5, 1], 1, 16))
    rules.append(([2, 1, 1, 1, 1, 1, 0], [4, 5, 5, 5, 5, 5, 1], 1, 16))
    
    # Ex: Rua da Consolacao 100 / Rua do Ouvidor 50
    rules.append(([2, 7, 1, 0], [4, 5, 5, 1], 1, 16))
    rules.append(([2, 7, 1, 1, 0], [4, 5, 5, 5, 1], 1, 16))
    rules.append(([2, 7, 1, 1, 1, 0], [4, 5, 5, 5, 5, 1], 1, 16))
    
    # Ex: Rua Barao de Itapetininga 100 / Avenida Duque de Caxias 500
    rules.append(([2, 1, 7, 1, 0], [4, 5, 5, 5, 1], 1, 16))
    rules.append(([2, 1, 7, 1, 1, 0], [4, 5, 5, 5, 5, 1], 1, 16))
    rules.append(([2, 1, 1, 7, 1, 0], [4, 5, 5, 5, 5, 1], 1, 16))
    rules.append(([2, 1, 1, 7, 1, 1, 0], [4, 5, 5, 5, 5, 5, 1], 1, 16))

    # With Cardinal direction: Ex: Rua Augusta Norte 100
    rules.append(([2, 1, 22, 0], [4, 5, 7, 1], 1, 16))
    rules.append(([2, 1, 1, 22, 0], [4, 5, 5, 7, 1], 1, 16))

    # 2. [TYPE] [STREET...] [NUMBER] [UNITH] [NUMBER/WORD]
    # Ex: Rua Augusta 100 Apto 101 / Av Paulista 1000 Bloco B
    rules.append(([2, 1, 0, 19, 0], [4, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 1, 1, 0, 19, 0], [4, 5, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 1, 1, 1, 0, 19, 0], [4, 5, 5, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 1, 7, 1, 0, 19, 0], [4, 5, 5, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 7, 1, 0, 19, 0], [4, 5, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 1, 0, 19, 1], [4, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 1, 1, 0, 19, 1], [4, 5, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 1, 7, 1, 0, 19, 1], [4, 5, 5, 5, 1, 16, 17], 1, 16))
    rules.append(([2, 7, 1, 0, 19, 1], [4, 5, 5, 1, 16, 17], 1, 16))

    # 3. [TYPE] [STREET...] [NUMBER] [UNITH] [WORD/NUMBER] [UNITH] [NUMBER]
    # Ex: Rua Augusta 100 Bloco B Apto 101
    rules.append(([2, 1, 0, 19, 1, 19, 0], [4, 5, 1, 16, 17, 16, 17], 1, 17))
    rules.append(([2, 1, 1, 0, 19, 1, 19, 0], [4, 5, 5, 1, 16, 17, 16, 17], 1, 17))
    rules.append(([2, 1, 0, 19, 0, 19, 0], [4, 5, 1, 16, 17, 16, 17], 1, 17))
    rules.append(([2, 1, 1, 0, 19, 0, 19, 0], [4, 5, 5, 1, 16, 17, 16, 17], 1, 17))

    # 4. [TYPE] [STREET...] (Sem número)
    rules.append(([2, 1], [4, 5], 1, 10))
    rules.append(([2, 1, 1], [4, 5, 5], 1, 10))
    rules.append(([2, 1, 1, 1], [4, 5, 5, 5], 1, 10))
    rules.append(([2, 1, 1, 1, 1], [4, 5, 5, 5, 5], 1, 10))
    rules.append(([2, 7, 1], [4, 5, 5], 1, 10))
    rules.append(([2, 7, 1, 1], [4, 5, 5, 5], 1, 10))
    rules.append(([2, 1, 7, 1], [4, 5, 5, 5], 1, 10))
    rules.append(([2, 1, 7, 1, 1], [4, 5, 5, 5, 5], 1, 10))

    # 5. [STREET...] [NUMBER] (Sem tipo explícito: Ex: Paulista 1000)
    rules.append(([1, 0], [5, 1], 1, 12))
    rules.append(([1, 1, 0], [5, 5, 1], 1, 12))
    rules.append(([1, 1, 1, 0], [5, 5, 5, 1], 1, 12))
    rules.append(([1, 7, 1, 0], [5, 5, 5, 1], 1, 12))

    # 6. Rodovias: [ROAD] [WORD...] [MILE] [NUMBER]
    # Ex: Rodovia dos Imigrantes Km 50 / Rodovia BR-101 Km 100 / Rodovia Anhanguera Km 15
    rules.append(([6, 1, 20, 0], [4, 5, 8, 1], 1, 16))
    rules.append(([6, 1, 1, 20, 0], [4, 5, 5, 8, 1], 1, 16))
    rules.append(([6, 7, 1, 20, 0], [4, 5, 5, 8, 1], 1, 16))
    rules.append(([6, 7, 1, 1, 20, 0], [4, 5, 5, 5, 8, 1], 1, 16))
    rules.append(([6, 0, 20, 0], [4, 5, 8, 1], 1, 16))
    rules.append(([6, 1, 0, 20, 0], [4, 5, 5, 8, 1], 1, 16))      # Ex: Rodovia BR 101 Km 150
    rules.append(([6, 1, 9, 0, 20, 0], [4, 5, 5, 5, 8, 1], 1, 16)) # Ex: Rodovia BR-101 Km 150
    rules.append(([6, 1, 0], [4, 5, 5], 1, 12))                    # Ex: Rodovia BR 101
    rules.append(([6, 1, 9, 0], [4, 5, 5, 5], 1, 12))              # Ex: Rodovia BR-101

    # 7. Padrão Brasília: [TYPE] [NUMBER] [BUILDH] [WORD/SINGLE/NUMBER]
    # Ex: SQS 308 Bloco B / SQS 308 Bloco B Apto 101
    rules.append(([2, 0, 19, 18], [4, 5, 16, 17], 1, 16))
    rules.append(([2, 0, 19, 1], [4, 5, 16, 17], 1, 16))
    rules.append(([2, 0, 19, 0], [4, 5, 16, 17], 1, 16))
    rules.append(([2, 0, 19, 18, 19, 0], [4, 5, 16, 17, 16, 17], 1, 17))
    rules.append(([2, 0, 19, 1, 19, 0], [4, 5, 16, 17, 16, 17], 1, 17))
    rules.append(([2, 0, 19, 0, 19, 0], [4, 5, 16, 17, 16, 17], 1, 17))

    # 8. Padrão Loteamento: [TYPE/UNITH] [NUMBER] [UNITH] [NUMBER]
    # Ex: Quadra 10 Lote 5
    rules.append(([19, 0, 19, 0], [16, 17, 16, 17], 1, 15))

    # 9. Standalone words
    rules.append(([1], [5], 1, 5))
    rules.append(([1, 1], [5, 5], 1, 5))
    rules.append(([1, 1, 1], [5, 5, 5], 1, 5))


    # -------------------------------------------------------------
    # B. MACRO RULES (Rule Type 0 = MACRO_C)
    # Outputs: 10 = CITY, 11 = PROV (State), 12 = NATION, 13 = POSTAL
    # -------------------------------------------------------------
    
    # 1. Gazetteer Recognized City (Token 10) + State (Token 11)
    rules.append(([10, 11], [10, 11], 0, 17))
    rules.append(([10, 11, 0], [10, 11, 13], 0, 17))
    rules.append(([10, 11, 0, 0], [10, 11, 13, 13], 0, 17))
    rules.append(([10, 11, 12], [10, 11, 12], 0, 17))
    rules.append(([10, 0], [10, 13], 0, 16))
    rules.append(([10, 12], [10, 12], 0, 16))
    rules.append(([10], [10], 0, 14))

    # 2. Word-based City (Token 1 / 7) + State (Token 11)
    # Ex: São Paulo SP / Campinas SP / Rio de Janeiro RJ / Belo Horizonte MG
    rules.append(([1, 11], [10, 11], 0, 16))
    rules.append(([1, 1, 11], [10, 10, 11], 0, 16))
    rules.append(([1, 1, 1, 11], [10, 10, 10, 11], 0, 16))
    rules.append(([1, 7, 1, 11], [10, 10, 10, 11], 0, 16))
    rules.append(([1, 7, 1, 1, 11], [10, 10, 10, 10, 11], 0, 16))
    rules.append(([1, 7, 1, 7, 1, 11], [10, 10, 10, 10, 10, 11], 0, 16))

    # 3. Word-based City + State + Postal
    # Ex: São Paulo SP 01310-000
    rules.append(([1, 11, 0], [10, 11, 13], 0, 17))
    rules.append(([1, 1, 11, 0], [10, 10, 11, 13], 0, 17))
    rules.append(([1, 1, 1, 11, 0], [10, 10, 10, 11, 13], 0, 17))
    rules.append(([1, 7, 1, 11, 0], [10, 10, 10, 11, 13], 0, 17))
    rules.append(([1, 7, 1, 1, 11, 0], [10, 10, 10, 10, 11, 13], 0, 17))
    
    # With two-part postal (e.g. 01310 - 000 / 0 0)
    rules.append(([1, 11, 0, 0], [10, 11, 13, 13], 0, 17))
    rules.append(([1, 1, 11, 0, 0], [10, 10, 11, 13, 13], 0, 17))
    rules.append(([1, 7, 1, 11, 0, 0], [10, 10, 10, 11, 13, 13], 0, 17))

    # 4. Word-based City + State + Country
    # Ex: São Paulo SP Brasil
    rules.append(([1, 11, 12], [10, 11, 12], 0, 17))
    rules.append(([1, 1, 11, 12], [10, 10, 11, 12], 0, 17))
    rules.append(([1, 7, 1, 11, 12], [10, 10, 10, 11, 12], 0, 17))

    # 5. [CITY] only
    rules.append(([1], [10], 0, 8))
    rules.append(([1, 1], [10, 10], 0, 8))
    rules.append(([1, 1, 1], [10, 10, 10], 0, 8))
    rules.append(([1, 7, 1], [10, 10, 10], 0, 8))
    rules.append(([1, 7, 1, 1], [10, 10, 10, 10], 0, 8))

    # 6. [STATE] only
    rules.append(([11], [11], 0, 10))
    rules.append(([11, 12], [11, 12], 0, 12))

    # 7. [POSTAL] only
    rules.append(([0], [13], 0, 14))
    rules.append(([0, 0], [13, 13], 0, 14))

    # -------------------------------------------------------------
    # C. Write SQL Output (with automatic deduplication)
    # -------------------------------------------------------------
    unique_rules = []
    seen = set()
    for inp, outp, rtype, weight in rules:
        key = (tuple(inp), tuple(outp), rtype)
        if key not in seen:
            seen.add(key)
            unique_rules.append((inp, outp, rtype, weight))
    rules = unique_rules

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("-- ==========================================================================\n")
        f.write("-- PostGIS address_standardizer: Brazilian Grammar Rules Dataset (br_rules)\n")
        f.write("-- PAGC syntax: <input_tokens> -1 <output_tokens> -1 <type> <weight>\n")
        f.write("-- License: Public Domain / Open Source (BSD/PostGIS License)\n")
        f.write("-- ==========================================================================\n\n")
        f.write("CREATE TABLE IF NOT EXISTS br_rules (\n")
        f.write("    id serial, rule text, is_custom boolean NOT NULL DEFAULT true, CONSTRAINT pk_br_rules PRIMARY KEY(id)\n")
        f.write(");\n\n")
        f.write("-- Upgrade protection for custom entries\n")
        f.write("DELETE FROM br_rules WHERE is_custom = false;\n\n")
        f.write("-- Default is_custom to false for shipped entries\n")
        f.write("ALTER TABLE br_rules ALTER COLUMN is_custom SET DEFAULT false;\n\n")
        
        for inp, outp, rtype, weight in rules:
            inp_str = " ".join(map(str, inp))
            outp_str = " ".join(map(str, outp))
            rule_str = f"{inp_str} -1 {outp_str} -1 {rtype} {weight}"
            f.write(f"INSERT INTO br_rules (rule) VALUES ('{rule_str}');\n")

    print(f"Generated {output_path} with {len(rules)} rules.")


def generate_br_data_extension_sql(output_path: str):
    """Generates sql/26_br_data_extension.sql"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("SELECT pg_catalog.pg_extension_config_dump('br_lex', 'WHERE is_custom');\n")
        f.write("SELECT pg_catalog.pg_extension_config_dump('br_rules', 'WHERE is_custom');\n")
        f.write("SELECT pg_catalog.pg_extension_config_dump('br_gaz', 'WHERE is_custom');\n")
    print(f"Generated {output_path}.")

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_dir = os.path.join(base_dir, "sql")
    os.makedirs(sql_dir, exist_ok=True)
    
    ibge_data = fetch_ibge_municipalities()
    
    generate_br_lex_sql(os.path.join(sql_dir, "23_br_lex.sql"))
    generate_br_gaz_sql(os.path.join(sql_dir, "24_br_gaz.sql"), ibge_data)
    generate_br_rules_sql(os.path.join(sql_dir, "25_br_rules.sql"))
    generate_br_data_extension_sql(os.path.join(sql_dir, "26_br_data_extension.sql"))
    print("All Brazilian dataset SQL files generated successfully!")

if __name__ == "__main__":
    main()
