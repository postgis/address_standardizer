#!/usr/bin/env python3
"""
Unit tests for Brazilian address data generation and CNEFE import tools.
"""

import io
import os
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock, patch

# Ensure tools directory is in Python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import generate_br_data
import import_cnefe


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
            {"id": 1501402, "nome": "Belém"}
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

    def test_provenance_and_licensing(self):
        """Verify that README and generated SQL headers contain public open sources, IBGE and OSM ODbL attribution."""
        readme_path = os.path.join(REPO_ROOT, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()

        self.assertIn("public open sources", readme_content)
        self.assertIn("OpenStreetMap contributors", readme_content)
        self.assertIn("Open Database License (ODbL)", readme_content)
        self.assertIn("https://opendatacommons.org/licenses/odbl/", readme_content)

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


class TestImportCnefe(unittest.TestCase):
    """Tests for import_cnefe.py logic and validation."""

    def test_remove_accents(self):
        self.assertEqual(import_cnefe.remove_accents("Belém"), "BELEM")
        self.assertEqual(import_cnefe.remove_accents("São João d'Aliança"), "SAO JOAO D'ALIANCA")
        self.assertEqual(import_cnefe.remove_accents(""), "")

    def test_psql_base_cmd(self):
        with patch.dict(os.environ, {"POSTGRES_USER": "testuser", "POSTGRES_DB": "testdb", "POSTGRES_CONTAINER": "custom_container"}, clear=True):
            cmd = import_cnefe.psql_base_cmd()
            self.assertEqual(cmd, ["docker", "exec", "-i", "custom_container", "psql", "-U", "testuser", "-d", "testdb"])

        with patch.dict(os.environ, {"POSTGRES_USER": "testuser", "POSTGRES_DB": "testdb", "POSTGRES_HOST": "localhost", "POSTGRES_PORT": "5433"}, clear=True):
            cmd = import_cnefe.psql_base_cmd()
            self.assertEqual(cmd, ["psql", "-h", "localhost", "-p", "5433", "-U", "testuser", "-d", "testdb"])

    def test_invalid_uf_rejection(self):
        with self.assertRaises(ValueError):
            import_cnefe.download_cnefe("XX", "/tmp")

        with self.assertRaises(ValueError):
            import_cnefe.import_cnefe_to_postgres("/tmp/fake.zip", "INVALID_UF")

    def test_missing_csv_in_zip(self):
        """Verify that zip archive with no CSV raises FileNotFoundError."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("readme.txt", "No csv here")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="0\n")
                with self.assertRaises(FileNotFoundError):
                    import_cnefe.import_cnefe_to_postgres(zip_path, "PA")
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_prevent_destructive_limit(self):
        """Verify that --limit is rejected if database already has records for the UF."""
        mock_result = MagicMock()
        mock_result.stdout = "500000\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            with self.assertRaises(ValueError) as ctx:
                import_cnefe.import_cnefe_to_postgres("/tmp/fake.zip", "SP", limit=100)
            self.assertIn("Substituição parcial com --limit foi rejeitada", str(ctx.exception))

    def test_row_filtering_and_parsing(self):
        """Verify that records with empty street name or missing IBGE code are skipped."""
        csv_data = (
            "COD_MUNICIPIO;NOM_TIPO_SEGLOGR;NOM_TITULO_SEGLOGR;NOM_SEGLOGR;NUM_ENDERECO;DSC_MODIFICADOR;DSC_LOCALIDADE;CEP;LATITUDE;LONGITUDE\n"
            "3550308;RUA;;AUGUSTA;100;APTO 12;CENTRO;01304-000;-23.5532;-46.6521\n"
            "3550308;RUA;;;100;;;;;\n"  # Missing NOM_SEGLOGR -> must be skipped
            ";RUA;;PAULISTA;100;;;;;\n"  # Missing COD_MUNICIPIO -> must be skipped
            "3550308;AVENIDA;DOUTOR;ARNALDO;500;;PACAEMBU;01246-000;-23.5550;-46.6660\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test_cnefe.csv", csv_data)

            captured_output = []

            class CaptureStream:
                def write(self, s):
                    captured_output.append(s)
                def close(self):
                    pass

            mock_proc = MagicMock()
            mock_proc.stdin = CaptureStream()
            mock_proc.wait.return_value = 0

            with patch("subprocess.run") as mock_run, \
                 patch("subprocess.Popen", return_value=mock_proc), \
                 patch("import_cnefe.get_municipality_map", return_value={3550308: ("SAO PAULO", "SP")}):
                
                mock_run.return_value = MagicMock(stdout="0\n")
                import_cnefe.import_cnefe_to_postgres(zip_path, "SP")

            # Check lines sent via STDIN
            all_text = "".join(captured_output)
            written_lines = [line.strip().split("\t") for line in all_text.strip().split("\n") if line.strip()]
            self.assertEqual(len(written_lines), 2)
            self.assertEqual(written_lines[0][5], "AUGUSTA")
            self.assertEqual(written_lines[1][5], "DOUTOR ARNALDO")
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_download_cnefe_truncated(self):
        """Verify that truncated downloads raise IOError and clean up temp file."""
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "1000"}
        mock_resp.read.side_effect = [b"short_bytes", b""]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("urllib.request.urlopen", return_value=mock_resp):
                with self.assertRaises(IOError) as ctx:
                    import_cnefe.download_cnefe("PA", temp_dir)
                self.assertIn("Download truncado", str(ctx.exception))
                # Verify tmp file was cleaned up and final file not created
                tmp_file = os.path.join(temp_dir, "15_PA.zip.tmp")
                dest_file = os.path.join(temp_dir, "15_PA.zip")
                self.assertFalse(os.path.exists(tmp_file))
                self.assertFalse(os.path.exists(dest_file))

    def test_download_cnefe_success_and_absent_content_length(self):
        """Verify successful download promotion when Content-Length matches or is absent."""
        mock_resp = MagicMock()
        data = b"full_cnefe_file_content"
        mock_resp.headers = {"Content-Length": str(len(data))}
        mock_resp.read.side_effect = [data, b""]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("urllib.request.urlopen", return_value=mock_resp):
                dest = import_cnefe.download_cnefe("PA", temp_dir)
                self.assertTrue(os.path.exists(dest))
                with open(dest, "rb") as f:
                    self.assertEqual(f.read(), data)

        # Test absent Content-Length
        mock_resp_no_len = MagicMock()
        mock_resp_no_len.headers = {}
        mock_resp_no_len.read.side_effect = [data, b""]
        mock_resp_no_len.__enter__.return_value = mock_resp_no_len
        mock_resp_no_len.__exit__.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("urllib.request.urlopen", return_value=mock_resp_no_len):
                dest = import_cnefe.download_cnefe("PA", temp_dir)
                self.assertTrue(os.path.exists(dest))
                with open(dest, "rb") as f:
                    self.assertEqual(f.read(), data)

    def test_get_target_ufs(self):
        """Verify parsing of single UF, multiple comma-separated UFs, and BR/ALL."""
        self.assertEqual(import_cnefe.get_target_ufs("SP"), ["SP"])
        self.assertEqual(import_cnefe.get_target_ufs("sp, rj, mg"), ["SP", "RJ", "MG"])
        
        all_ufs = import_cnefe.get_target_ufs("BR")
        self.assertEqual(len(all_ufs), 27)
        self.assertIn("SP", all_ufs)
        self.assertIn("AP", all_ufs)
        self.assertIn("DF", all_ufs)

        all_ufs_flag = import_cnefe.get_target_ufs("SP", all_flag=True)
        self.assertEqual(len(all_ufs_flag), 27)

    def test_schema_definition_consistency(self):
        """Verify that cnefe_enderecos table schema in docs and importer match columns and types."""
        docs_path = os.path.join(REPO_ROOT, "docs", "geocodificador_cnefe_brasil.md")
        with open(docs_path, "r", encoding="utf-8") as f:
            docs_content = f.read()

        import_cnefe_path = os.path.join(REPO_ROOT, "tools", "import_cnefe.py")
        with open(import_cnefe_path, "r", encoding="utf-8") as f:
            importer_content = f.read()

        expected_columns = [
            "id bigserial PRIMARY KEY",
            "cod_municipio_ibge integer NOT NULL",
            "municipio text NOT NULL",
            "uf varchar(2) NOT NULL",
            "tipo text",
            "titulo text",
            "logradouro text NOT NULL",
            "numero text",
            "modificador text",
            "bairro text",
            "cep varchar(9)",
            "latitude double precision",
            "longitude double precision",
            "geom geometry(Point, 4326)"
        ]

        for col in expected_columns:
            self.assertIn(col, docs_content, f"Missing column in docs: {col}")
            self.assertIn(col, importer_content, f"Missing column in importer: {col}")

        # Ensure obsolete column 'complemento' is not present in either schema definition
        self.assertNotIn("complemento text", docs_content)
        self.assertNotIn("complemento text", importer_content)

    def test_reverse_geocoding_geography_knn(self):
        """Verify that reverse geocoding index and query use geography KNN for metric distance."""
        docs_path = os.path.join(REPO_ROOT, "docs", "geocodificador_cnefe_brasil.md")
        with open(docs_path, "r", encoding="utf-8") as f:
            docs_content = f.read()

        import_cnefe_path = os.path.join(REPO_ROOT, "tools", "import_cnefe.py")
        with open(import_cnefe_path, "r", encoding="utf-8") as f:
            importer_content = f.read()

        # Both docs and importer must create GiST index on geography
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_cnefe_geog", docs_content)
        self.assertIn("ON cnefe_enderecos USING GIST ((geom::geography))", docs_content)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_cnefe_geog ON cnefe_enderecos USING GIST ((geom::geography))", importer_content)

        # Docs query 3 must order by geography KNN (<->) matching ST_Distance in meters
        self.assertIn("ST_Distance(c.geom::geography", docs_content)
        self.assertIn("c.geom::geography <->", docs_content)

    def test_control_file_version_synchronization(self):
        """Verify that all extension control files have synchronized default_version values."""
        import re
        control_files = [
            "address_standardizer.control",
            "address_standardizer_data_us.control",
            "address_standardizer_data_br.control"
        ]
        versions = {}
        for fname in control_files:
            fpath = os.path.join(REPO_ROOT, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r"default_version\s*=\s*'([^']+)'", content)
            self.assertIsNotNone(match, f"Could not find default_version in {fname}")
            versions[fname] = match.group(1)

        first_v = next(iter(versions.values()))
        for fname, ver in versions.items():
            self.assertEqual(ver, first_v, f"Version mismatch in {fname}: expected {first_v}, got {ver}")

    def test_docker_compose_security_and_healthcheck(self):
        """Verify that docker-compose.yml enforces loopback binding, password requirement, and healthcheck."""
        compose_path = os.path.join(REPO_ROOT, "docker-compose.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_content = f.read()

        self.assertIn("127.0.0.1:", compose_content)
        self.assertIn("POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Please set POSTGRES_PASSWORD in .env}", compose_content)
        self.assertIn("healthcheck:", compose_content)
        self.assertIn("pg_isready", compose_content)

    def test_existing_cluster_upgrade_guidance(self):
        """Verify that docker/init.sql and tools/README.md document the upgrade procedure for existing clusters."""
        init_sql_path = os.path.join(REPO_ROOT, "docker", "init.sql")
        with open(init_sql_path, "r", encoding="utf-8") as f:
            init_content = f.read()

        tools_readme_path = os.path.join(REPO_ROOT, "tools", "README.md")
        with open(tools_readme_path, "r", encoding="utf-8") as f:
            tools_readme_content = f.read()

        self.assertIn("-f /docker-entrypoint-initdb.d/init.sql", init_content)
        self.assertIn("-f /docker-entrypoint-initdb.d/init.sql", tools_readme_content)


if __name__ == "__main__":
    unittest.main()
