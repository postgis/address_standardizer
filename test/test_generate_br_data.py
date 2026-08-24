#!/usr/bin/env python3
"""Unit tests for the Brazilian address dataset generator."""

import os
import re
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import generate_br_data


class TestGenerateBrData(unittest.TestCase):
    """Tests for generate_br_data.py functions and data structures."""

    def test_normalize_text(self):
        self.assertEqual(generate_br_data.normalize_text("São Paulo"), "SAO PAULO")
        self.assertEqual(generate_br_data.normalize_text("Amapá"), "AMAPA")
        self.assertEqual(generate_br_data.normalize_text("Pará"), "PARA")
        self.assertEqual(generate_br_data.normalize_text("Espírito Santo"), "ESPIRITO SANTO")

    def test_brazil_states_accent_coverage(self):
        """Verify that BRAZIL_STATES contains official accented names."""
        states_dict = dict(generate_br_data.BRAZIL_STATES)
        self.assertEqual(len(states_dict), 27)
        self.assertEqual(states_dict["SP"], "SÃO PAULO")
        self.assertEqual(states_dict["PA"], "PARÁ")
        self.assertEqual(states_dict["AP"], "AMAPÁ")
        self.assertEqual(states_dict["CE"], "CEARÁ")
        self.assertEqual(states_dict["GO"], "GOIÁS")
        self.assertEqual(states_dict["MA"], "MARANHÃO")

    def test_generate_br_gaz_structure(self):
        """Verify gazetteer generation generates sequential IDs per word and handles accents."""
        mock_ibge = [
            {"id": 3550308, "nome": "São Paulo"},
            {"id": 1501402, "nome": "Belém"},
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".sql", delete=False) as tf:
            temp_path = tf.name

        try:
            generate_br_data.generate_br_gaz_sql(temp_path, mock_ibge)
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("CREATE TABLE IF NOT EXISTS br_gaz", content)
            self.assertIn("SAO PAULO", content)
            self.assertIn("SÃO PAULO", content)
            self.assertIn("BELEM", content)
            self.assertIn("BELÉM", content)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_hyphenated_municipalities_get_scanner_compatible_aliases(self):
        """Hyphenated IBGE names also match the scanner's joined spelling."""
        mock_ibge = [
            {"id": 2404309, "nome": "Governador Dix-Sept Rosado"},
            {"id": 3550308, "nome": "São Paulo"},
        ]
        with tempfile.NamedTemporaryFile(suffix=".sql") as tf:
            generate_br_data.generate_br_gaz_sql(tf.name, mock_ibge)
            with open(tf.name, "r", encoding="utf-8") as f:
                content = f.read()

        self.assertIn(
            "'GOVERNADOR DIX SEPT ROSADO', 'GOVERNADOR DIX-SEPT ROSADO', 10",
            content,
        )
        self.assertIn("'GOVERNADOR DIX-SEPT ROSADO', 'GOVERNADOR DIX-SEPT ROSADO', 10", content)
        self.assertEqual(generate_br_data.scanner_compatible_aliases("SAO PAULO"), {"SAO PAULO"})

    def test_provenance_and_licensing(self):
        """Verify that the README and generated SQL carry source and license provenance."""
        readme_path = os.path.join(REPO_ROOT, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()

        self.assertIn("public open sources", readme_content)
        self.assertIn("OpenStreetMap contributors", readme_content)
        self.assertIn("Open Database License (ODbL)", readme_content)
        self.assertIn("https://opendatacommons.org/licenses/odbl/", readme_content)
        self.assertIn("Public API for Localidades", readme_content)
        self.assertNotIn("CNEFE", readme_content)
        self.assertNotIn("5,571", readme_content)

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".sql", delete=False) as tf:
            temp_lex_path = tf.name

        try:
            generate_br_data.generate_br_lex_sql(temp_lex_path)
            with open(temp_lex_path, "r", encoding="utf-8") as f:
                lex_content = f.read()

            self.assertIn("public open sources (IBGE official open data and OpenStreetMap)", lex_content)
            self.assertIn("ODbL", lex_content)
            self.assertIn("https://opendatacommons.org/licenses/odbl/", lex_content)
        finally:
            if os.path.exists(temp_lex_path):
                os.remove(temp_lex_path)

    def test_ibge_fetch_advertises_only_supported_compression(self):
        """The request must not advertise encodings that the reader does not decode."""
        response = mock.MagicMock()
        response.read.return_value = b"[]"
        response.headers.get.return_value = None
        response.__enter__.return_value = response
        response.__exit__.return_value = None

        with mock.patch.object(generate_br_data.urllib.request, "urlopen", return_value=response) as urlopen:
            self.assertEqual(generate_br_data.fetch_ibge_municipalities(), [])

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Accept-encoding"), "gzip")

    def test_generate_br_data_extension_sql_dumps_custom_rows_and_sequences(self):
        """Extension upgrades preserve custom rows and the IDs allocated by serial sequences."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".sql", delete=False) as tf:
            temp_path = tf.name

        try:
            generate_br_data.generate_br_data_extension_sql(temp_path)
            with open(temp_path, "r", encoding="utf-8") as f:
                self.assertEqual(
                    f.read().splitlines(),
                    [
                        "SELECT pg_catalog.pg_extension_config_dump('br_lex', 'WHERE is_custom');",
                        "SELECT pg_catalog.pg_extension_config_dump('br_rules', 'WHERE is_custom');",
                        "SELECT pg_catalog.pg_extension_config_dump('br_gaz', 'WHERE is_custom');",
                        "SELECT pg_catalog.pg_extension_config_dump('br_lex_id_seq', '');",
                        "SELECT pg_catalog.pg_extension_config_dump('br_rules_id_seq', '');",
                        "SELECT pg_catalog.pg_extension_config_dump('br_gaz_id_seq', '');",
                    ],
                )
        finally:
            os.remove(temp_path)

    def test_is_custom_default_restoration(self):
        """Verify that generated SQL datasets reset is_custom default back to true."""
        mock_ibge = [{"id": 3550308, "nome": "São Paulo"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            gaz_path = os.path.join(tmpdir, "test_gaz.sql")
            lex_path = os.path.join(tmpdir, "test_lex.sql")
            rules_path = os.path.join(tmpdir, "test_rules.sql")

            generate_br_data.generate_br_gaz_sql(gaz_path, mock_ibge)
            generate_br_data.generate_br_lex_sql(lex_path)
            generate_br_data.generate_br_rules_sql(rules_path)

            with open(gaz_path, "r", encoding="utf-8") as f:
                self.assertIn("ALTER TABLE br_gaz ALTER COLUMN is_custom SET DEFAULT true;", f.read())
            with open(lex_path, "r", encoding="utf-8") as f:
                self.assertIn("ALTER TABLE br_lex ALTER COLUMN is_custom SET DEFAULT true;", f.read())
            with open(rules_path, "r", encoding="utf-8") as f:
                self.assertIn("ALTER TABLE br_rules ALTER COLUMN is_custom SET DEFAULT true;", f.read())

    def test_generate_br_gaz_empty_ibge_error(self):
        """Verify that generate_br_gaz_sql rejects empty IBGE data."""
        with tempfile.NamedTemporaryFile(suffix=".sql") as tf:
            with self.assertRaises(RuntimeError) as ctx:
                generate_br_data.generate_br_gaz_sql(tf.name, [])
            self.assertIn("empty or missing", str(ctx.exception))

    def test_accented_variants_token_1_generated(self):
        """Verify that accented states and municipalities generate WORD entries."""
        with tempfile.NamedTemporaryFile(suffix=".sql") as tf:
            mock_mun = [
                {
                    "id": 3550308,
                    "nome": "São Paulo",
                    "microrregiao": {
                        "mesorregiao": {"UF": {"sigla": "SP", "nome": "São Paulo"}}
                    },
                }
            ]
            generate_br_data.generate_br_gaz_sql(tf.name, mock_mun)
            with open(tf.name, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("'SÃO PAULO', 'SAO PAULO', 10", content)
            self.assertIn("'SÃO PAULO', 'SAO PAULO', 1", content)

    def test_house_number_headers_are_consumed_without_output_text(self):
        """House-number headers match BUILDH rules without becoming address fields."""
        with tempfile.NamedTemporaryFile(suffix=".sql") as tf:
            generate_br_data.generate_br_lex_sql(tf.name)
            with open(tf.name, "r", encoding="utf-8") as f:
                content = f.read()

        self.assertIn("'NUMERO', '', 19", content)
        self.assertIn("'NÚMERO', '', 19", content)

    def test_rules_cover_reviewed_brazilian_address_forms(self):
        """The generated rules cover direction names, long highways, and number headers."""
        with tempfile.NamedTemporaryFile(suffix=".sql") as tf:
            generate_br_data.generate_br_rules_sql(tf.name)
            with open(tf.name, "r", encoding="utf-8") as f:
                content = f.read()

        self.assertIn("2 22 0 -1 4 5 1 -1 1 16", content)
        self.assertIn("6 1 1 1 20 0 -1 4 5 5 5 8 1 -1 1 16", content)
        self.assertIn("2 7 1 20 0 -1 4 5 5 8 1 -1 1 16", content)
        self.assertIn("2 1 19 0 -1 4 5 16 1 -1 1 16", content)
        self.assertIn("2 1 0 -1 4 5 1 -1 1 16", content)

    def test_numeric_street_prefixes_are_context_specific_phrases(self):
        """Reviewed date-name prefixes become words without changing bare numbers."""
        with tempfile.NamedTemporaryFile(suffix=".sql") as tf:
            generate_br_data.generate_br_lex_sql(tf.name)
            with open(tf.name, "r", encoding="utf-8") as f:
                content = f.read()

        self.assertIn("'9 DE', '9 DE', 1", content)
        self.assertIn("'25 DE', '25 DE', 1", content)
        self.assertNotIn("'9', '9', 1", content)
        self.assertNotIn("'25', '25', 1", content)

    def test_control_file_version_synchronization(self):
        """Verify that all extension control files have synchronized versions."""
        control_files = [
            "address_standardizer.control",
            "address_standardizer_data_us.control",
            "address_standardizer_data_br.control",
        ]
        versions = {}
        for filename in control_files:
            path = os.path.join(REPO_ROOT, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r"default_version\s*=\s*'([^']+)'", content)
            self.assertIsNotNone(match, f"Could not find default_version in {filename}")
            versions[filename] = match.group(1)

        first_version = next(iter(versions.values()))
        for filename, version in versions.items():
            self.assertEqual(
                version,
                first_version,
                f"Version mismatch in {filename}: expected {first_version}, got {version}",
            )


if __name__ == "__main__":
    unittest.main()
