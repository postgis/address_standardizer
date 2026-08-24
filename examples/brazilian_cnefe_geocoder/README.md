# Brazilian CNEFE geocoder example

This optional example combines `address_standardizer` with PostGIS and the
Brazilian 2022 CNEFE address dataset published by IBGE.

CNEFE means *Cadastro Nacional de Endereços para Fins Estatísticos* (National
Address Register for Statistical Purposes). It provides address reference rows
and, where IBGE publishes them, geographic coordinates.

This example is deliberately separate from the extension itself:

- `address_standardizer` parses free-form text into address components.
- `address_standardizer_data_br` supplies Brazilian lexicon, gazetteer, and
  grammar tables.
- the example importer downloads CNEFE and maintains a searchable PostGIS
  reference table.
- the example SQL joins standardized components to that reference table.

It is not part of the US Census TIGER geocoder and it does not add geocoding
APIs to `address_standardizer`.

## Start the example database

The example image builds the extension from the current checkout. The init
script then installs the packaged extensions; it does not load raw repository
SQL files.

```bash
cd examples/brazilian_cnefe_geocoder
cp .env.example .env
# Set a strong POSTGRES_PASSWORD in .env.
docker compose up --build -d
```

The database is exposed only on `127.0.0.1` by default. PostgreSQL runs the
files in `initdb/` only when it creates a new data directory.

To install the extensions in an existing database without deleting data:

```bash
docker compose exec -T database sh -eu -c \
  'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -f /docker-entrypoint-initdb.d/10_extensions.sql'
```

## Import Brazilian CNEFE data

The importer downloads the official state archives, streams their CSV rows to
PostgreSQL, and atomically replaces the selected state after validation. A
failed or empty state import preserves existing rows, is reported in the final
summary, and makes the command exit non-zero.

```bash
# One state
python3 import_brazilian_cnefe.py --uf SP

# Several states
python3 import_brazilian_cnefe.py --uf SP,RJ,MG

# All 27 federative units
python3 import_brazilian_cnefe.py --all

# Small first-time development import; never replaces existing state data
python3 import_brazilian_cnefe.py --uf SP --limit 5000
```

The importer reads `.env` from this example directory. Set `POSTGRES_HOST` to
use a directly reachable PostgreSQL server instead of the example container.

Fresh downloads receive a full ZIP CRC check before cache promotion. Later
cache hits validate the ZIP directory and required CSV member without
decompressing the complete state archive again.

## Data model

The importer owns the example-only `cnefe_enderecos` table:

```sql
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
    geom geometry(Point, 4326),
    street_name text GENERATED ALWAYS AS (
        CASE
            WHEN titulo IS NULL OR titulo = '' THEN logradouro
            ELSE titulo || ' ' || logradouro
        END
    ) STORED,
    house_number text GENERATED ALWAYS AS (
        CASE
            WHEN modificador IS NULL OR modificador = '' THEN numero
            ELSE numero || ' ' || modificador
        END
    ) STORED
);
```

`logradouro` stores `NOM_SEGLOGR`, while `titulo` stores
`NOM_TITULO_SEGLOGR`. The generated `street_name` combines both fields in the
ASCII-uppercase form used by the importer. The queries below normalize the
standardizer's street name to that same key with `upper(unaccent(...))`, so
accented and unaccented input match the same CNEFE row. Likewise,
`house_number` combines `NUM_ENDERECO` and `DSC_MODIFICADOR`, so a CNEFE row
such as `100` + `A` matches standardized `100 A`. Apartment, unit, and other
complement fields are not stored or distinguished; matching stops at the
building and house-number level.

## Exact geocoding

```sql
WITH parsed AS (
    SELECT * FROM standardize_address(
        'br_lex', 'br_gaz', 'br_rules',
        'Rua Açucena, 100',
        'Sao Paulo, SP'
    )
), normalized AS (
    SELECT p.*, upper(unaccent('unaccent', p.name)) AS street_key
    FROM parsed AS p
)
SELECT c.*
FROM cnefe_enderecos AS c, normalized AS p
WHERE c.uf = p.state
  AND c.municipio = p.city
  AND c.tipo = p.pretype
  AND c.street_name = p.street_key
  AND c.house_number = p.house_num
LIMIT 1;
```

## Fuzzy geocoding

The street type remains part of the key so similarly named streets of
different types do not compete.

```sql
WITH parsed AS (
    SELECT * FROM standardize_address(
        'br_lex', 'br_gaz', 'br_rules',
        'Rua Agusta, 100',
        'Sao Paulo, SP'
    )
), normalized AS (
    SELECT p.*, upper(unaccent('unaccent', p.name)) AS street_key
    FROM parsed AS p
)
SELECT c.*, similarity(c.street_name, p.street_key) AS similarity_score
FROM cnefe_enderecos AS c, normalized AS p
WHERE c.uf = p.state
  AND c.municipio = p.city
  AND c.tipo = p.pretype
  AND c.house_number = p.house_num
  AND c.street_name % p.street_key
ORDER BY similarity_score DESC
LIMIT 5;
```

## Reverse lookup

The geography index and radius filter keep distances in metres and bound the
KNN search.

```sql
SELECT
    CONCAT_WS(' ', c.tipo, c.street_name) AS street,
    c.house_number,
    c.municipio,
    c.uf,
    c.cep,
    ST_Distance(
        c.geom::geography,
        ST_SetSRID(ST_Point(-46.6521, -23.5532), 4326)::geography
    ) AS distance_metres
FROM cnefe_enderecos AS c
WHERE ST_DWithin(
    c.geom::geography,
    ST_SetSRID(ST_Point(-46.6521, -23.5532), 4326)::geography,
    500
)
ORDER BY c.geom::geography <->
    ST_SetSRID(ST_Point(-46.6521, -23.5532), 4326)::geography
LIMIT 1;
```

## Source and scope

- [IBGE CNEFE portal](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/estrutura-territorial/27533-cadastro-nacional-de-enderecos-para-fins-estatisticos.html)
- [IBGE CNEFE 2022 state archives](https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/)

CNEFE is a statistical address register, not a guarantee of postal
deliverability or complete coordinates. Applications must define their own
matching thresholds, ambiguity handling, and freshness policy.
