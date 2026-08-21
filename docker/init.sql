-- Inicialização automática do PostGIS e datasets de padronização de endereços do Brasil
-- (Executado automaticamente pelo docker-entrypoint-initdb.d apenas na criação de um novo cluster)
--
-- NOTA PARA CLUSTERS EXISTENTES:
-- Se o diretório .pgdata já existir, o Docker não reexecuta este arquivo. Para aplicar as tabelas
-- e regras em um banco já existente, execute manualmente via container:
--   docker exec -i postgis_br psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-address_db}" -f /docker-entrypoint-initdb.d/init.sql
-- Ou redefina o volume de dados (ATENÇÃO: apaga dados existentes):
--   docker compose down && rm -rf -- "${POSTGRES_DATA_DIR:-./.pgdata}" && docker compose up -d
--
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS address_standardizer;

-- Carregamento dos datasets do Brasil (Léxico, Gazetteer dos 5.571 municípios/UFs e Regras PAGC)
\i /sql/23_br_lex.sql
\i /sql/24_br_gaz.sql
\i /sql/25_br_rules.sql
\i /sql/26_br_data_extension.sql

