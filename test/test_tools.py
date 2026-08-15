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
                # Verify tmp file was cleaned up
                tmp_file = os.path.join(temp_dir, "15_PA.zip.tmp")
                self.assertFalse(os.path.exists(tmp_file))

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

        with self.assertRaises(ValueError):
            import_cnefe.get_target_ufs("INVALID_UF")


if __name__ == "__main__":
    unittest.main()
