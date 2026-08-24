select * from parse_address('123 Main Street, Kansas City, MO 45678');
select * from standardize_address('us_lex'::text, 'us_gaz'::text, 'us_rules'::text, '123 Main Street'::text, 'Kansas City, MO 45678'::text);
SELECT '#2981' As ticket, * FROM standardize_address('us_lex','us_gaz','us_rules', '1566 NEW STATE HWY, RAYNHAM, MA');
SELECT '#2978a' As ticket, * FROM standardize_address('us_lex','us_gaz','us_rules', '10-20 DORRANCE ST PROVIDENCE RI' );
SELECT '#2978b' As ticket, * FROM standardize_address('us_lex','us_gaz','us_rules', '10 20 DORRANCE ST PROVIDENCE RI' );
SELECT '#2978c' As ticket, * FROM standardize_address('us_lex','us_gaz','us_rules', '10-20 DORRANCE ST, PROVIDENCE, RI');
SELECT '#state_only_macro' AS ticket, * FROM standardize_address('us_lex','us_gaz','us_rules', '25 Prince Street, NC 09985');
SELECT '#5299a' AS ticket, * FROM standardize_address('us_lex',  'us_gaz', 'us_rules','1 Timepiece Point','Boston, MA, 02220');
SELECT '#5299b' AS ticket, * FROM standardize_address('us_lex',  'us_gaz', 'us_rules','50 Gold Piece Drive','Boston, MA, 02020');
SELECT '#5695a' AS ticket, * FROM standardize_address('us_lex', 'us_gaz', 'us_rules', 'ONE E PIMA ST STE 999, TUCSON, AZ');
SELECT '#2459a' AS ticket, * FROM standardize_address('us_lex', 'us_gaz', 'us_rules', '26 Court Street, Boston, Massachusetts 02109, France');
SELECT '#2459b' AS ticket, * FROM standardize_address('us_lex', 'us_gaz', 'us_rules', '212 3rd Ave N, MINNEAPOLIS, MN 553404');
SET statement_timeout = '2s';
SELECT '#hash_unit' AS ticket, house_num, name, suftype, unit FROM standardize_address(
    'us_lex', 'us_gaz', 'us_rules', '123 Main St #4', 'Boston, MA');
SELECT '#hash_unit_attached' AS ticket, house_num, name, suftype, unit FROM standardize_address(
    'us_lex', 'us_gaz', 'us_rules', '123 Main St#4', 'Boston, MA');
SELECT '#unit_order' AS ticket, house_num, name, suftype, unit FROM standardize_address(
    'us_lex', 'us_gaz', 'us_rules', '123 Main St Rear Apt 2', 'Boston, MA');
SELECT '#ca_postal' AS ticket, postcode FROM standardize_address(
    'us_lex', 'us_gaz', 'us_rules', '123 King St', 'Toronto, ON M5V 2T6');
RESET statement_timeout;
DO $$
BEGIN
	PERFORM standardize_address('us_lex', 'us_gaz', 'us_rules', '   ');
EXCEPTION WHEN OTHERS THEN
	RAISE NOTICE 'blank-input: %', SQLERRM;
END
$$;
-- CVE: rule with >128 terms must be rejected gracefully, not crash (stack OOB write)
CREATE TEMP TABLE t_overlong_rule(id serial, rule text);
INSERT INTO t_overlong_rule(rule) SELECT string_agg('1', ' ') FROM generate_series(1, 130);
DO $$
BEGIN
	PERFORM standardize_address('us_lex', 'us_gaz', 't_overlong_rule', '1 Main St', 'Boston, MA');
EXCEPTION WHEN OTHERS THEN
	RAISE NOTICE 'overlong-rule: %', SQLERRM;
END
$$;
-- OOB read: rule missing type/weight tokens must be rejected, not read past array end
CREATE TEMP TABLE t_short_rule(id serial, rule text);
INSERT INTO t_short_rule(rule) VALUES ('1 -1 5 -1');
DO $$
BEGIN
	PERFORM standardize_address('us_lex', 'us_gaz', 't_short_rule', '1 Main St', 'Boston, MA');
EXCEPTION WHEN OTHERS THEN
	RAISE NOTICE 'short-rule: %', SQLERRM;
END
$$;
