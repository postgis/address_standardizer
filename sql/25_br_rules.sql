-- ==========================================================================
-- PostGIS address_standardizer: Brazilian Grammar Rules Dataset (br_rules)
-- PAGC syntax: <input_tokens> -1 <output_tokens> -1 <type> <weight>
-- License: Public Domain / Open Source (BSD/PostGIS License)
-- ==========================================================================

CREATE TABLE IF NOT EXISTS br_rules (
    id serial, rule text, is_custom boolean NOT NULL DEFAULT true, CONSTRAINT pk_br_rules PRIMARY KEY(id)
);

-- Upgrade protection for custom entries
DELETE FROM br_rules WHERE is_custom = false;

-- Default is_custom to false for shipped entries
ALTER TABLE br_rules ALTER COLUMN is_custom SET DEFAULT false;

INSERT INTO br_rules (rule) VALUES ('2 1 0 -1 4 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 0 -1 4 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 1 0 -1 4 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 1 1 0 -1 4 5 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 1 1 1 0 -1 4 5 5 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 7 1 0 -1 4 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 7 1 1 0 -1 4 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 7 1 1 1 0 -1 4 5 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 7 1 0 -1 4 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 7 1 1 0 -1 4 5 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 7 1 0 -1 4 5 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 7 1 1 0 -1 4 5 5 5 5 5 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 22 0 -1 4 5 7 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 22 0 -1 4 5 5 7 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 0 19 0 -1 4 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 0 19 0 -1 4 5 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 1 0 19 0 -1 4 5 5 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 7 1 0 19 0 -1 4 5 5 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 7 1 0 19 0 -1 4 5 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 0 19 1 -1 4 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 1 0 19 1 -1 4 5 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 7 1 0 19 1 -1 4 5 5 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 7 1 0 19 1 -1 4 5 5 1 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 1 0 19 1 19 0 -1 4 5 1 16 17 16 17 -1 1 17');
INSERT INTO br_rules (rule) VALUES ('2 1 1 0 19 1 19 0 -1 4 5 5 1 16 17 16 17 -1 1 17');
INSERT INTO br_rules (rule) VALUES ('2 1 0 19 0 19 0 -1 4 5 1 16 17 16 17 -1 1 17');
INSERT INTO br_rules (rule) VALUES ('2 1 1 0 19 0 19 0 -1 4 5 5 1 16 17 16 17 -1 1 17');
INSERT INTO br_rules (rule) VALUES ('2 1 -1 4 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('2 1 1 -1 4 5 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('2 1 1 1 -1 4 5 5 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('2 1 1 1 1 -1 4 5 5 5 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('2 7 1 -1 4 5 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('2 7 1 1 -1 4 5 5 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('2 1 7 1 -1 4 5 5 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('2 1 7 1 1 -1 4 5 5 5 5 -1 1 10');
INSERT INTO br_rules (rule) VALUES ('1 0 -1 5 1 -1 1 12');
INSERT INTO br_rules (rule) VALUES ('1 1 0 -1 5 5 1 -1 1 12');
INSERT INTO br_rules (rule) VALUES ('1 1 1 0 -1 5 5 5 1 -1 1 12');
INSERT INTO br_rules (rule) VALUES ('1 7 1 0 -1 5 5 5 1 -1 1 12');
INSERT INTO br_rules (rule) VALUES ('6 1 20 0 -1 4 5 8 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('6 1 1 20 0 -1 4 5 5 8 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('6 7 1 20 0 -1 4 5 5 8 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('6 7 1 1 20 0 -1 4 5 5 5 8 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('6 0 20 0 -1 4 5 8 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('6 1 0 20 0 -1 4 5 5 8 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('6 1 9 0 20 0 -1 4 5 5 5 8 1 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('6 1 0 -1 4 5 5 -1 1 12');
INSERT INTO br_rules (rule) VALUES ('6 1 9 0 -1 4 5 5 5 -1 1 12');
INSERT INTO br_rules (rule) VALUES ('2 0 19 18 -1 4 5 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 0 19 1 -1 4 5 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 0 19 0 -1 4 5 16 17 -1 1 16');
INSERT INTO br_rules (rule) VALUES ('2 0 19 18 19 0 -1 4 5 16 17 16 17 -1 1 17');
INSERT INTO br_rules (rule) VALUES ('2 0 19 1 19 0 -1 4 5 16 17 16 17 -1 1 17');
INSERT INTO br_rules (rule) VALUES ('2 0 19 0 19 0 -1 4 5 16 17 16 17 -1 1 17');
INSERT INTO br_rules (rule) VALUES ('19 0 19 0 -1 16 17 16 17 -1 1 15');
INSERT INTO br_rules (rule) VALUES ('1 -1 5 -1 1 5');
INSERT INTO br_rules (rule) VALUES ('1 1 -1 5 5 -1 1 5');
INSERT INTO br_rules (rule) VALUES ('1 1 1 -1 5 5 5 -1 1 5');
INSERT INTO br_rules (rule) VALUES ('10 11 -1 10 11 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('10 11 0 -1 10 11 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('10 11 0 0 -1 10 11 13 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('10 11 12 -1 10 11 12 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('10 0 -1 10 13 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('10 12 -1 10 12 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('10 -1 10 -1 0 14');
INSERT INTO br_rules (rule) VALUES ('1 11 -1 10 11 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('1 1 11 -1 10 10 11 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('1 1 1 11 -1 10 10 10 11 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('1 7 1 11 -1 10 10 10 11 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('1 7 1 1 11 -1 10 10 10 10 11 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('1 7 1 7 1 11 -1 10 10 10 10 10 11 -1 0 16');
INSERT INTO br_rules (rule) VALUES ('1 11 0 -1 10 11 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 1 11 0 -1 10 10 11 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 1 1 11 0 -1 10 10 10 11 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 7 1 11 0 -1 10 10 10 11 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 7 1 1 11 0 -1 10 10 10 10 11 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 11 0 0 -1 10 11 13 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 1 11 0 0 -1 10 10 11 13 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 7 1 11 0 0 -1 10 10 10 11 13 13 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 11 12 -1 10 11 12 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 1 11 12 -1 10 10 11 12 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 7 1 11 12 -1 10 10 10 11 12 -1 0 17');
INSERT INTO br_rules (rule) VALUES ('1 -1 10 -1 0 8');
INSERT INTO br_rules (rule) VALUES ('1 1 -1 10 10 -1 0 8');
INSERT INTO br_rules (rule) VALUES ('1 1 1 -1 10 10 10 -1 0 8');
INSERT INTO br_rules (rule) VALUES ('1 7 1 -1 10 10 10 -1 0 8');
INSERT INTO br_rules (rule) VALUES ('1 7 1 1 -1 10 10 10 10 -1 0 8');
INSERT INTO br_rules (rule) VALUES ('11 -1 11 -1 0 10');
INSERT INTO br_rules (rule) VALUES ('11 12 -1 11 12 -1 0 12');
INSERT INTO br_rules (rule) VALUES ('0 -1 13 -1 0 14');
INSERT INTO br_rules (rule) VALUES ('0 0 -1 13 13 -1 0 14');
