-- Brazilian address standardizer regression tests
SELECT '#br1' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta, 100', 'Sao Paulo, SP');
SELECT '#br2' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Avenida Paulista, 1000 Apto 101', 'Sao Paulo, SP, 01310 100');
SELECT '#br3' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rodovia dos Imigrantes, Km 50', 'Sao Paulo, SP');
SELECT '#br4' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'SQS 308 Bloco B Apto 101', 'Brasilia, DF');
SELECT '#br5' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Quadra 10 Lote 5', 'Goiania, GO');
SELECT '#br6' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Açucena, 100', 'São Paulo, SP');
SELECT '#br7' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta, 100A', 'Sao Paulo, SP');
SELECT '#br8' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Avenida Paulista, 1000 Bloco B', 'Sao Paulo, SP');
SELECT '#br9' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta, 100', 'Sao Paulo, SP, Brazil');
SELECT '#br10' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta, 100', 'Sao Paulo, SP, 01310-100, Brasil');
SELECT '#br11' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Norte, 100', 'Sao Paulo, SP');
SELECT '#br12' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rodovia Presidente Castelo Branco Km 30', 'Sao Paulo, SP');
SELECT '#br13' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta Numero 100', 'Sao Paulo, SP');
SELECT '#br14' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Estrada dos Romeiros Km 30', 'Sao Paulo, SP');
SELECT '#br15' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta No 100', 'Sao Paulo, SP');
SELECT '#br16' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Noroeste 100', 'Sao Paulo, SP');
\pset format unaligned
SELECT '#br17' AS ticket, house_num, pretype, name FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Açucena – 100', 'São Paulo, SP');
SELECT '#br18' AS ticket, house_num, pretype, name FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Açucena 100', 'São Paulo, SP');
SELECT '#br19' AS ticket, house_num, pretype, name FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Acucena 100', 'Sao Paulo, SP');
SELECT '#br20' AS ticket, house_num, pretype, name FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Açucena 100', 'São Paulo, SP');
SELECT '#br21' AS ticket, house_num, pretype, name, city FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules',
    U&'Rua Ac\0327ucena 100', U&'Sa\0303o Paulo, SP');
SELECT '#br22' AS ticket, house_num, pretype, name FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua 25 de Março 100', 'Sao Paulo, SP');
SELECT '#br23' AS ticket, house_num, pretype, name FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Avenida 9 de Julho 200', 'Sao Paulo, SP');
SELECT '#br24' AS ticket, city, state FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100', 'Governador Dix-Sept Rosado, RN');
\pset format aligned
-- End Brazilian address standardizer regression tests
