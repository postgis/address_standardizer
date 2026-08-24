SET client_encoding = 'UTF8';

CREATE EXTENSION address_standardizer;
CREATE EXTENSION address_standardizer_data_br;

DO $latin1_c_locale$
DECLARE
	standardized stdaddr;
BEGIN
	IF current_setting('server_encoding') <> 'LATIN1' THEN
		RAISE EXCEPTION 'LATIN1 scanner test is running in the wrong database';
	END IF;

	standardized := standardize_address(
		'br_lex', 'br_gaz', 'br_rules',
		'Rua Açucena, 100', 'São Paulo, SP');
	IF standardized IS NULL
	   OR standardized.house_num IS DISTINCT FROM '100'
	   OR standardized.pretype IS DISTINCT FROM 'RUA'
	   OR standardized.name IS DISTINCT FROM 'AÇUCENA'
	   OR standardized.city IS DISTINCT FROM 'SÃO PAULO' THEN
		RAISE EXCEPTION 'LATIN1 C-locale Portuguese address was not standardized';
	END IF;

	-- ASCII remains on the same portable path.
	standardized := standardize_address(
		'br_lex', 'br_gaz', 'br_rules',
		'Rua Acucena, 100', 'Sao Paulo, SP');
	IF standardized IS NULL
	   OR standardized.name IS DISTINCT FROM 'ACUCENA'
	   OR standardized.city IS DISTINCT FROM 'SAO PAULO' THEN
		RAISE EXCEPTION 'LATIN1 scanner changed ASCII input';
	END IF;
END
$latin1_c_locale$;
