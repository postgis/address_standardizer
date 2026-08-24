# Exemplo de geocodificador brasileiro com o CNEFE

[English](README.md) | Português (Brasil)

Este exemplo opcional combina o `address_standardizer`, o PostGIS e os dados
brasileiros de endereços do CNEFE 2022 publicados pelo IBGE.

CNEFE significa *Cadastro Nacional de Endereços para Fins Estatísticos*. Ele
fornece registros de referência de endereços e, quando publicadas pelo IBGE,
coordenadas geográficas.

Este exemplo é deliberadamente separado da extensão:

- o `address_standardizer` analisa texto livre e o separa em componentes de
  endereço;
- o `address_standardizer_data_br` fornece as tabelas brasileiras de léxico,
  gazetteer e regras gramaticais;
- o importador do exemplo baixa o CNEFE e mantém uma tabela de referência
  pesquisável no PostGIS;
- o SQL do exemplo relaciona os componentes padronizados com essa tabela de
  referência.

O exemplo não faz parte do geocodificador TIGER do Censo dos Estados Unidos e
não adiciona APIs de geocodificação ao `address_standardizer`.

## Iniciar o banco de dados do exemplo

A imagem do exemplo compila a extensão a partir do checkout atual. Em seguida,
o script de inicialização instala as extensões empacotadas; ele não carrega
arquivos SQL brutos do repositório.

```bash
cd examples/brazilian_cnefe_geocoder
cp .env.example .env
# Defina uma POSTGRES_PASSWORD forte no arquivo .env.
docker compose up --build -d
```

Por padrão, o banco de dados é exposto apenas em `127.0.0.1`. O PostgreSQL
executa os arquivos em `initdb/` somente quando cria um novo diretório de dados.

Para instalar as extensões em um banco de dados existente sem apagar dados:

```bash
docker compose exec -T database sh -eu -c \
  'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -f /docker-entrypoint-initdb.d/10_extensions.sql'
```

## Importar dados brasileiros do CNEFE

O importador baixa os arquivos oficiais por unidade da federação, transmite
as linhas CSV para o PostgreSQL e, depois da validação, substitui atomicamente
os dados da unidade selecionada. Uma importação vazia ou com falha preserva os
registros existentes, aparece no resumo final e faz o comando terminar com
código diferente de zero.

```bash
# Uma unidade da federação
python3 import_brazilian_cnefe.py --uf SP

# Várias unidades da federação
python3 import_brazilian_cnefe.py --uf SP,RJ,MG

# Todas as 27 unidades da federação
python3 import_brazilian_cnefe.py --all

# Importação pequena para desenvolvimento inicial; nunca substitui dados existentes
python3 import_brazilian_cnefe.py --uf SP --limit 5000
```

O importador lê o arquivo `.env` deste diretório de exemplo. Defina
`POSTGRES_HOST` para usar um servidor PostgreSQL acessível diretamente em vez
do contêiner do exemplo.

Downloads novos passam por uma verificação CRC completa do ZIP antes de serem
promovidos ao cache. Em usos posteriores do cache, o importador valida o
diretório do ZIP e o membro CSV obrigatório sem descompactar novamente todo o
arquivo da unidade da federação.

## Modelo de dados

O importador gerencia a tabela `cnefe_enderecos`, exclusiva deste exemplo:

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

`logradouro` armazena `NOM_SEGLOGR`, enquanto `titulo` armazena
`NOM_TITULO_SEGLOGR`. A coluna gerada `street_name` combina os dois campos na
forma ASCII em maiúsculas usada pelo importador. As consultas abaixo normalizam
o nome de logradouro produzido pelo padronizador para a mesma chave com
`upper(unaccent(...))`; assim, entradas com e sem acentos correspondem ao mesmo
registro do CNEFE. Da mesma maneira, `house_number` combina `NUM_ENDERECO` e
`DSC_MODIFICADOR`, portanto um registro do CNEFE com `100` + `A` corresponde ao
valor padronizado `100 A`. Apartamento, unidade e outros campos de complemento
não são armazenados nem diferenciados; a correspondência termina no nível do
edifício e do número do endereço.

## Geocodificação exata

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

## Geocodificação aproximada

O tipo de logradouro continua fazendo parte da chave para que logradouros de
tipos diferentes, mas com nomes semelhantes, não concorram entre si.

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

## Consulta reversa

O índice geográfico e o filtro por raio mantêm as distâncias em metros e
limitam a busca KNN.

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

## Fonte e escopo

- [Portal do CNEFE no IBGE](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/estrutura-territorial/27533-cadastro-nacional-de-enderecos-para-fins-estatisticos.html)
- [Arquivos estaduais do CNEFE 2022 no IBGE](https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/)

O CNEFE é um cadastro estatístico de endereços, não uma garantia de entrega
postal nem de coordenadas completas. Cada aplicação precisa definir os seus
próprios limiares de correspondência, tratamento de ambiguidades e política de
atualização.
