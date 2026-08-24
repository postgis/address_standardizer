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
SELECT '#br25' AS ticket, house_num, pretype, name, sufdir, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta Nº 100', 'Sao Paulo, SP');
SELECT '#br26' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100 Apto 101A', 'Sao Paulo, SP');
SELECT '#br27' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100 Apto 101 A', 'Sao Paulo, SP');
SELECT '#br28' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100 Fundos', 'Sao Paulo, SP');
SELECT '#br29' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100 Frente', 'Sao Paulo, SP');
SELECT '#br30' AS ticket, state, postcode FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100', 'SP, 01310');
SELECT '#br31' AS ticket, state, postcode FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100', 'SP, 01310-100');
SELECT '#br32' AS ticket, house_num, pretype, name, city FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua João & Maria 100', 'Sao Paulo, SP');
SELECT '#br33' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100 Bloco 2 A Apto 101B', 'Sao Paulo, SP');
SELECT '#br34' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100 Bloco B2 Apto 101 A', 'Sao Paulo, SP');
SELECT '#br35' AS ticket, house_num, pretype, name, ruralroute FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rodovia BR-101 Km 150', 'Sao Paulo, SP');
SELECT '#br36' AS ticket, house_num, pretype, name, ruralroute FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rodovia BR-101', 'Sao Paulo, SP');
SELECT '#br37' AS ticket, house_num, pretype, name, ruralroute FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rodovia Anhanguera 100', 'Sao Paulo, SP');
SELECT '#br38' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Casa do Ator 100', 'Sao Paulo, SP');
SELECT '#br39' AS ticket, house_num, pretype, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua Augusta 100 Casa 2', 'Sao Paulo, SP');
SELECT '#br40' AS ticket, house_num, pretype, name, ruralroute FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rodovia BR 101 Km 150', 'Sao Paulo, SP');
SELECT '#br41' AS ticket, house_num, pretype, name, ruralroute FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rodovia BR 101', 'Sao Paulo, SP');
SELECT '#br42' AS ticket, house_num, pretype, name, ruralroute FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rodovia SP-330 Km 100', 'Sao Paulo, SP');
SELECT '#br43' AS ticket, house_num, pretype, name, ruralroute FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rodovia SP 330', 'Sao Paulo, SP');
SELECT '#br44' AS ticket, house_num, pretype, name FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua A 100', 'Sao Paulo, SP');
SELECT '#br45' AS ticket, house_num, pretype, name FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Rua XV de Novembro 100', 'Sao Paulo, SP');
SELECT '#br46' AS ticket, house_num, name, unit FROM standardize_address(
    'br_lex', 'br_gaz', 'br_rules', 'Paulista 1000 Apto 101', 'Sao Paulo, SP');
\pset format aligned
-- End Brazilian address standardizer regression tests
