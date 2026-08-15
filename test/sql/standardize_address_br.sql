-- Brazilian address standardizer regression tests
SELECT '#br1' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta, 100', 'Sao Paulo, SP');
SELECT '#br2' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Avenida Paulista, 1000 Apto 101', 'Sao Paulo, SP, 01310 100');
SELECT '#br3' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rodovia dos Imigrantes, Km 50', 'Sao Paulo, SP');
SELECT '#br4' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'SQS 308 Bloco B Apto 101', 'Brasilia, DF');
SELECT '#br5' AS ticket, * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Quadra 10 Lote 5', 'Goiania, GO');
