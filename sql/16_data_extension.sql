
-- needed so entries added by users will default to custom
ALTER TABLE us_rules ALTER COLUMN is_custom SET DEFAULT true;
SELECT pg_catalog.pg_extension_config_dump('us_lex', 'WHERE is_custom');
SELECT pg_catalog.pg_extension_config_dump('us_rules', 'WHERE is_custom');
SELECT pg_catalog.pg_extension_config_dump('us_gaz', 'WHERE is_custom');
