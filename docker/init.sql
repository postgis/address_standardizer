-- Inicialização automática do PostGIS e datasets de padronização de endereços do Brasil
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS address_standardizer;

-- Carregamento dos datasets do Brasil (Léxico, Gazetteer dos 5.571 municípios/UFs e Regras PAGC)
\i /sql/23_br_lex.sql
\i /sql/24_br_gaz.sql
\i /sql/25_br_rules.sql
\i /sql/26_br_data_extension.sql
