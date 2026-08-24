#!/usr/bin/env python3
"""
Unit tests for CNEFE import tooling.
"""

import io
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from unittest.mock import MagicMock, patch

# Ensure tools directory is in Python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import import_cnefe


class TestImportCnefe(unittest.TestCase):
    """Tests for import_cnefe.py logic and validation."""

    @staticmethod
    def cnefe_zip_bytes() -> bytes:
        """Returns a small valid CNEFE-shaped ZIP archive for download tests."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("cnefe.csv", "COD_MUNICIPIO;NOM_SEGLOGR\n")
        return buffer.getvalue()

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
            self.assertEqual(cmd, ["psql", "-h", "localhost", "-p", "5433", "-U", "testuser", "-d", "testdb", "-w"])

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
                    import_cnefe.import_cnefe_to_postgres(zip_path, "PA", muni_map={})
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
        """Verify that records with empty street name, unmapped municipality, or missing IBGE code are skipped."""
        csv_data = (
            "COD_MUNICIPIO;NOM_TIPO_SEGLOGR;NOM_TITULO_SEGLOGR;NOM_SEGLOGR;NUM_ENDERECO;DSC_MODIFICADOR;DSC_LOCALIDADE;CEP;LATITUDE;LONGITUDE;NUM_LATITUDE;NUM_LONGITUDE\n"
            "3550308;RUA;;AUGUSTA;100;APTO 12;CENTRO;01304-000;-23.5532;-46.6521;99;99\n"
            "3550308;RUA;;;100;;;;;;;;\n"  # Missing NOM_SEGLOGR -> must be skipped
            ";RUA;;PAULISTA;100;;;;;;;;\n"  # Missing COD_MUNICIPIO -> must be skipped
            "9999999;RUA;;ORFANATO;100;;;;;;;;\n"  # Unmapped COD_MUNICIPIO -> must be skipped
            "3304557;RUA;;COPACABANA;200;;;;;;;;\n"  # Municipality belongs to RJ -> must be skipped
            "3550308;AVENIDA;PRESIDENTE;VARGAS;500;;PACAEMBU;01246-000;-23.5550;-46.6660;88;88\n"
            "3500000;RUA;;SEM UF;300;;;;;;;;\n"  # Missing mapped UF is accepted
        )
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test_cnefe.CSV", "\ufeff" + csv_data)

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
                 patch("import_cnefe.get_municipality_map", return_value={
                     3550308: ("SAO PAULO", "SP"),
                     3304557: ("RIO DE JANEIRO", "RJ"),
                     3500000: ("SEM UF", ""),
                 }):

                mock_run.return_value = MagicMock(stdout="0\n")
                import_cnefe.import_cnefe_to_postgres(zip_path, "SP")

            # Check lines sent via STDIN
            all_text = "".join(captured_output)
            written_lines = [line.strip().split("\t") for line in all_text.strip().split("\n") if line.strip()]
            self.assertEqual(len(written_lines), 3)
            self.assertEqual(written_lines[0][5], "AUGUSTA")
            self.assertEqual(written_lines[0][10:12], ["-23.5532", "-46.6521"])
            self.assertEqual(written_lines[1][4:6], ["PRESIDENTE", "VARGAS"])
            self.assertEqual(written_lines[1][10:12], ["-23.5550", "-46.6660"])
            self.assertEqual(written_lines[2][5], "SEM UF")
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
                # Verify the unique temporary file was cleaned up and final file not created
                dest_file = os.path.join(temp_dir, "15_PA.zip")
                self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(temp_dir)))
                self.assertFalse(os.path.exists(dest_file))

    def test_download_cnefe_success_and_absent_content_length(self):
        """Verify successful download promotion when Content-Length matches or is absent."""
        mock_resp = MagicMock()
        data = self.cnefe_zip_bytes()
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

    def test_download_cnefe_rejects_invalid_zip_without_content_length(self):
        """Verify a corrupt chunked response is not promoted into the cache."""
        mock_resp = MagicMock()
        mock_resp.headers = {}
        mock_resp.read.side_effect = [b"not a ZIP archive", b""]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("urllib.request.urlopen", return_value=mock_resp):
                with self.assertRaises(IOError) as ctx:
                    import_cnefe.download_cnefe("PA", temp_dir)
            self.assertIn("não foi salvo em cache", str(ctx.exception))
            self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(temp_dir)))
            self.assertFalse(os.path.exists(os.path.join(temp_dir, "15_PA.zip")))

    def test_download_cnefe_replaces_invalid_cached_zip(self):
        """Verify an invalid large cache entry is discarded and recovered automatically."""
        data = self.cnefe_zip_bytes()
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(data))}
        mock_resp.read.side_effect = [data, b""]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "15_PA.zip")
            with open(cache_path, "wb") as cache:
                cache.write(b"not a ZIP archive" * 70_000)

            with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                dest = import_cnefe.download_cnefe("PA", temp_dir)

            mock_urlopen.assert_called_once()
            with open(dest, "rb") as cache:
                self.assertEqual(cache.read(), data)

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

    def test_cached_zip_skips_full_crc_validation(self):
        """Large cache hits avoid decompressing the whole archive again."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "15_PA.zip")
            with zipfile.ZipFile(cache_path, "w", zipfile.ZIP_STORED) as archive:
                archive.writestr("cnefe.csv", b"x" * 1_000_001)

            with patch.object(zipfile.ZipFile, "testzip", side_effect=AssertionError("deep validation")), \
                 patch("urllib.request.urlopen") as mock_urlopen:
                self.assertEqual(import_cnefe.download_cnefe("PA", temp_dir), cache_path)

            mock_urlopen.assert_not_called()

    def test_fresh_zip_keeps_full_crc_validation(self):
        """Freshly downloaded archives retain the full CRC check."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("cnefe.csv", "COD_MUNICIPIO;NOM_SEGLOGR\n")

            with patch.object(zipfile.ZipFile, "testzip", return_value=None) as mock_testzip:
                self.assertTrue(import_cnefe.validate_cnefe_zip(zip_path))
                mock_testzip.assert_called_once_with()
                mock_testzip.reset_mock()
                self.assertTrue(import_cnefe.validate_cnefe_zip(zip_path, deep=False))
                mock_testzip.assert_not_called()
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_download_cnefe_tolerates_concurrent_cache_removal(self):
        """Another downloader may remove an invalid cache entry first."""
        data = self.cnefe_zip_bytes()
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(data))}
        mock_resp.read.side_effect = [data, b""]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "15_PA.zip")
            with open(cache_path, "wb") as cache:
                cache.write(b"not a ZIP archive" * 70_000)

            with patch("urllib.request.urlopen", return_value=mock_resp), \
                 patch("import_cnefe.os.remove", side_effect=FileNotFoundError):
                dest = import_cnefe.download_cnefe("PA", temp_dir)

            with open(dest, "rb") as cache:
                self.assertEqual(cache.read(), data)

    def test_download_cnefe_tolerates_cache_removal_before_stat(self):
        """A cache entry may disappear between discovery and the initial stat."""
        data = self.cnefe_zip_bytes()
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(data))}
        mock_resp.read.side_effect = [data, b""]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("urllib.request.urlopen", return_value=mock_resp), \
                 patch("import_cnefe.os.path.getsize", side_effect=[FileNotFoundError, len(data)]):
                dest = import_cnefe.download_cnefe("PA", temp_dir)

            with open(dest, "rb") as cache:
                self.assertEqual(cache.read(), data)

    def test_uppercase_csv_member_is_valid(self):
        """Validation and import agree that .CSV members are CSV files."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("CNEFE.CSV", "COD_MUNICIPIO;NOM_SEGLOGR\n")
            self.assertTrue(import_cnefe.validate_cnefe_zip(zip_path))
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_download_cnefe_uses_unique_temp_paths(self):
        """Concurrent downloads cannot share a temporary archive path."""
        data = self.cnefe_zip_bytes()
        responses = []
        for _ in range(2):
            response = MagicMock()
            response.headers = {"Content-Length": str(len(data))}
            response.read.side_effect = [data, b""]
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            responses.append(response)

        real_mkstemp = tempfile.mkstemp
        created_paths = []

        def capture_mkstemp(*args, **kwargs):
            fd, path = real_mkstemp(*args, **kwargs)
            created_paths.append(path)
            return fd, path

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("urllib.request.urlopen", side_effect=responses), \
                 patch("import_cnefe.tempfile.mkstemp", side_effect=capture_mkstemp):
                import_cnefe.download_cnefe("PA", temp_dir)
                import_cnefe.download_cnefe("RJ", temp_dir)

            self.assertEqual(len(created_paths), 2)
            self.assertNotEqual(*created_paths)
            self.assertTrue(all(not os.path.exists(path) for path in created_paths))

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

    @patch("subprocess.run")
    def test_schema_initialization_is_serialized(self, mock_run):
        """Shared first-run DDL must finish under one database-wide transaction lock."""
        import_cnefe.ensure_tables_exist()

        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        sql = command[command.index("-c") + 1]
        self.assertTrue(mock_run.call_args.kwargs["check"])
        self.assertLess(sql.index("BEGIN;"), sql.index("pg_advisory_xact_lock"))
        self.assertLess(sql.index("pg_advisory_xact_lock"), sql.index("CREATE EXTENSION"))
        self.assertLess(sql.index("pg_advisory_xact_lock"), sql.index("CREATE TABLE"))
        self.assertLess(sql.index("CREATE TABLE"), sql.index("COMMIT;"))
        self.assertIn("address_standardizer:cnefe_schema", sql)
        self.assertNotIn("cnefe_enderecos:SP", sql)

    def test_reverse_geocoding_geography_knn(self):
        """Verify that reverse geocoding index and query use geography KNN and ST_DWithin for metric search."""
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

        # Docs query 3 must order by geography KNN (<->) and use ST_DWithin radius filter
        self.assertIn("ST_Distance(c.geom::geography", docs_content)
        self.assertIn("c.geom::geography <->", docs_content)
        self.assertIn("ST_DWithin(c.geom::geography", docs_content)

        # Both exact and fuzzy geocoding must disambiguate streets that share a name and number.
        self.assertEqual(docs_content.count("AND c.tipo = p.pretype"), 2)
        self.assertIn("NOM_SEGLOGR canonical key", docs_content)
        self.assertIn("CONCAT_WS(' ', c.tipo, c.titulo, c.logradouro)", docs_content)

    def test_psql_base_cmd_host_mode_w_flag(self):
        """Verify that psql_base_cmd includes -w flag in direct host mode and sets PGPASSWORD."""
        with patch.dict(os.environ, {"POSTGRES_HOST": "localhost", "POSTGRES_PORT": "5433", "POSTGRES_PASSWORD": "secret_password"}, clear=True):
            cmd = import_cnefe.psql_base_cmd()
            self.assertIn("-w", cmd)
            self.assertIn("localhost", cmd)
            self.assertEqual(os.environ.get("PGPASSWORD"), "secret_password")

    def test_psql_base_cmd_pgpassword_empty_fallback(self):
        """Verify that empty PGPASSWORD falls back to non-empty POSTGRES_PASSWORD and non-empty PGPASSWORD is preserved."""
        with patch.dict(os.environ, {"POSTGRES_HOST": "localhost", "POSTGRES_PASSWORD": "fallback_pass", "PGPASSWORD": ""}, clear=True):
            cmd = import_cnefe.psql_base_cmd()
            self.assertIn("-w", cmd)
            self.assertEqual(os.environ.get("PGPASSWORD"), "fallback_pass")

        with patch.dict(os.environ, {"POSTGRES_HOST": "localhost", "POSTGRES_PASSWORD": "fallback_pass", "PGPASSWORD": "custom_pass"}, clear=True):
            cmd = import_cnefe.psql_base_cmd()
            self.assertIn("-w", cmd)
            self.assertEqual(os.environ.get("PGPASSWORD"), "custom_pass")

    def test_docker_compose_security_and_healthcheck(self):
        """Verify that docker-compose.yml enforces loopback binding, password requirement, and healthcheck."""
        compose_path = os.path.join(REPO_ROOT, "docker-compose.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_content = f.read()

        self.assertIn("127.0.0.1:", compose_content)
        self.assertIn("POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Please set POSTGRES_PASSWORD in .env}", compose_content)
        self.assertIn("healthcheck:", compose_content)
        self.assertIn("pg_isready", compose_content)

    def test_ci_runs_cnefe_tooling_tests(self):
        """The CNEFE importer tests must run in every GitHub Actions matrix job."""
        workflow_path = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")
        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_content = f.read()

        self.assertIn("name: 'Test CNEFE tooling'", workflow_content)
        self.assertIn("run: python3 test/test_tools.py -q", workflow_content)
        self.assertIn("permissions:\n  contents: read", workflow_content)

    def test_existing_cluster_upgrade_guidance(self):
        """Verify that docker/init.sql and tools/README.md document the upgrade procedure and POSTGRES_DATA_DIR reset."""
        init_sql_path = os.path.join(REPO_ROOT, "docker", "init.sql")
        with open(init_sql_path, "r", encoding="utf-8") as f:
            init_content = f.read()

        tools_readme_path = os.path.join(REPO_ROOT, "tools", "README.md")
        with open(tools_readme_path, "r", encoding="utf-8") as f:
            tools_readme_content = f.read()

        self.assertIn("-f /docker-entrypoint-initdb.d/init.sql", init_content)
        self.assertIn("-f /docker-entrypoint-initdb.d/init.sql", tools_readme_content)
        self.assertIn("sh -c 'psql -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\"", init_content)
        self.assertIn("sh -c 'psql -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\"", tools_readme_content)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pg_trgm;", init_content)
        self.assertIn('set -a; . ./.env; set +a', init_content)
        self.assertIn('set -a\n. ./.env\nset +a', tools_readme_content)
        self.assertIn('rm -rf -- "${POSTGRES_DATA_DIR:-./.pgdata}"', init_content)
        self.assertIn('rm -rf -- "${POSTGRES_DATA_DIR:-./.pgdata}"', tools_readme_content)

    def test_docker_init_omits_extension_only_metadata_script(self):
        """Raw Docker initialization must not call pg_extension_config_dump."""
        init_sql_path = os.path.join(REPO_ROOT, "docker", "init.sql")
        with open(init_sql_path, "r", encoding="utf-8") as f:
            init_content = f.read()

        self.assertIn("\\i /sql/23_br_lex.sql", init_content)
        self.assertIn("\\i /sql/24_br_gaz.sql", init_content)
        self.assertIn("\\i /sql/25_br_rules.sql", init_content)
        self.assertNotIn("26_br_data_extension.sql", init_content)

    def test_generate_uuid7(self):
        """Verify that generate_uuid7 produces valid RFC 9562 UUIDv7 strings."""
        u_str = import_cnefe.generate_uuid7()
        u = uuid.UUID(u_str)
        self.assertEqual(u.version, 7)

    def test_stage_table_name_keeps_uuid_random_bits(self):
        """Imports in one UUIDv7 millisecond must not share a staging table."""
        with patch("import_cnefe.generate_uuid7", side_effect=[
            "018f0f00-0000-7000-8000-000000000001",
            "018f0f00-0000-7000-8000-000000000002",
        ]):
            first = import_cnefe.stage_table_name("SP")
            second = import_cnefe.stage_table_name("SP")

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith("8000000000000001"))
        self.assertTrue(second.endswith("8000000000000002"))

    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_isolated_per_uf_staging_table(self, mock_run, mock_popen):
        """A failed import must clean up the same unique staging table it created."""
        stage_table = "cnefe_stage_sp_unique_run"
        mock_proc = MagicMock()
        mock_proc.stdin = io.StringIO()
        mock_proc.wait.return_value = 1
        mock_popen.return_value = mock_proc

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "test.csv",
                    "COD_MUNICIPIO;NOM_SEGLOGR\n3550308;AUGUSTA\n",
                )

            with patch("import_cnefe.ensure_tables_exist"), \
                 patch("import_cnefe.stage_table_name", return_value=stage_table) as mock_name:
                with self.assertRaises(subprocess.CalledProcessError):
                    import_cnefe.import_cnefe_to_postgres(
                        zip_path,
                        "SP",
                        muni_map={3550308: ("SAO PAULO", "SP")},
                    )

            mock_name.assert_called_once_with("SP")
            sql_commands = [" ".join(call.args[0]) for call in mock_run.call_args_list]
            self.assertTrue(any(f"CREATE UNLOGGED TABLE IF NOT EXISTS {stage_table}" in sql for sql in sql_commands))
            self.assertIn(f"COPY {stage_table}", " ".join(mock_popen.call_args.args[0]))
            self.assertTrue(any(f"DROP TABLE IF EXISTS {stage_table}" in sql for sql in sql_commands))
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_import_cnefe_zero_count_aborts_safely(self, mock_run, mock_popen):
        """Verify that when 0 valid rows exist, import_cnefe_to_postgres aborts without wiping data."""
        mock_proc = MagicMock()
        mock_proc.stdin = io.StringIO()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        # Create a mock zip with a CSV containing no valid street rows
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as z:
                # CSV with empty street name (NOM_SEGLOGR is empty)
                csv_data = "COD_MUNICIPIO;NOM_SEGLOGR;NOM_TIPO_SEGLOGR;NOM_TITULO_SEGLOGR;NUM_ENDERECO;DSC_MODIFICADOR;DSC_LOCALIDADE;CEP;LATITUDE;LONGITUDE\n3550308;;RUA;;100;;CENTRO;01001000;-23.55;-46.63\n"
                z.writestr("test.csv", csv_data)

            with patch("import_cnefe.ensure_tables_exist"):
                with patch("import_cnefe.get_municipality_map", return_value={3550308: ("SAO PAULO", "SP")}):
                    res = import_cnefe.import_cnefe_to_postgres(zip_path, "SP")
                    self.assertEqual(res, 0)

            # Check that atomic swap SQL (DELETE FROM cnefe_enderecos) was NOT called
            executed_sqls = [call.args[0] for call in mock_run.call_args_list if call.args]
            for cmd in executed_sqls:
                cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
                self.assertNotIn("DELETE FROM cnefe_enderecos WHERE uf = 'SP'", cmd_str)

        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_atomic_swap_guards_partial_import_after_lock(self):
        """The same-UF lock must cover the final partial-import check and swap."""
        csv_data = (
            "COD_MUNICIPIO;NOM_SEGLOGR;LATITUDE;LONGITUDE\n"
            "3550308;AUGUSTA;-23.5532;-46.6521\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("test.csv", csv_data)

            mock_proc = MagicMock()
            mock_proc.stdin = io.StringIO()
            mock_proc.wait.return_value = 0
            with patch("subprocess.run") as mock_run, \
                 patch("subprocess.Popen", return_value=mock_proc):
                mock_run.return_value = MagicMock(stdout="0\n")
                import_cnefe.import_cnefe_to_postgres(
                    zip_path, "SP", limit=1, muni_map={3550308: ("SAO PAULO", "SP")}
                )

            sql_commands = [" ".join(call.args[0]) for call in mock_run.call_args_list if call.args]
            swap_sql = next(sql for sql in sql_commands if "DELETE FROM cnefe_enderecos WHERE uf = 'SP'" in sql)
            self.assertIn("latitude, longitude, geom", swap_sql)
            self.assertIn("ST_SetSRID(ST_Point(longitude, latitude), 4326)", swap_sql)
            self.assertIn("pg_advisory_xact_lock", swap_sql)
            self.assertIn("cnefe_enderecos:SP", swap_sql)
            self.assertNotIn("address_standardizer:cnefe_schema", swap_sql)
            self.assertIn("Substituição parcial com --limit foi rejeitada", swap_sql)
            self.assertLess(swap_sql.index("pg_advisory_xact_lock"), swap_sql.index("DO $$"))
            self.assertLess(swap_sql.index("DO $$"), swap_sql.index("DELETE FROM cnefe_enderecos"))
            self.assertIn("COMMIT", swap_sql)
            self.assertFalse(any("UPDATE cnefe_enderecos" in sql for sql in sql_commands))
            post_import_sql = next(sql for sql in sql_commands if "idx_cnefe_lookup" in sql)
            self.assertLess(post_import_sql.index("BEGIN;"), post_import_sql.index("pg_advisory_xact_lock"))
            self.assertLess(post_import_sql.index("address_standardizer:cnefe_schema"), post_import_sql.index("CREATE INDEX"))
            self.assertLess(post_import_sql.index("idx_cnefe_logr_trgm"), post_import_sql.index("ANALYZE cnefe_enderecos"))
            self.assertLess(post_import_sql.index("ANALYZE cnefe_enderecos"), post_import_sql.index("COMMIT;"))
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_positive_limit_validation(self):
        """The CLI parser and library reject zero or negative row limits."""
        for value in ("0", "-1"):
            with self.assertRaises(SystemExit):
                with patch.object(sys, "argv", ["import_cnefe.py", "--limit", value]):
                    import_cnefe.main()

        for value in (0, -1):
            with self.assertRaises(ValueError):
                import_cnefe.import_cnefe_to_postgres("/tmp/fake.zip", "SP", limit=value)

    def test_batch_import_continues_after_a_uf_failure(self):
        """A failed UF is reported after the remaining selected UFs run."""
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(sys, "argv", ["import_cnefe.py", "--uf", "SP,RJ,MG", "--dest", temp_dir]), \
             patch("import_cnefe.get_municipality_map", return_value={}), \
             patch("import_cnefe.download_cnefe", side_effect=["SP.zip", RuntimeError("network down"), "MG.zip"]) as mock_download, \
             patch("import_cnefe.import_cnefe_to_postgres", side_effect=[10, 20]) as mock_import, \
             patch("import_cnefe.sys.stderr", new_callable=io.StringIO) as stderr, \
             patch("import_cnefe.sys.stdout", new_callable=io.StringIO) as stdout:
            with self.assertRaises(SystemExit) as raised:
                import_cnefe.main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual([call.args[0] for call in mock_download.call_args_list], ["SP", "RJ", "MG"])
        self.assertEqual([call.args[1] for call in mock_import.call_args_list], ["SP", "MG"])
        self.assertIn("Falha na UF RJ: network down", stderr.getvalue())
        self.assertIn("Total de UFs processadas: 2", stdout.getvalue())
        self.assertIn("Total de UFs com falha: 1", stdout.getvalue())
        self.assertIn("- RJ: network down", stdout.getvalue())

    def test_copy_process_is_reaped_when_streaming_fails(self):
        """A CSV read failure must close psql's stdin and wait for the child."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("test.csv", "COD_MUNICIPIO;NOM_SEGLOGR\n3550308;AUGUSTA\n")

            mock_proc = MagicMock()
            mock_proc.wait.return_value = 0
            with patch("subprocess.run") as mock_run, \
                 patch("subprocess.Popen", return_value=mock_proc), \
                 patch("csv.DictReader", side_effect=RuntimeError("CSV read failed")):
                mock_run.return_value = MagicMock(stdout="0\n")
                with self.assertRaisesRegex(RuntimeError, "CSV read failed"):
                    import_cnefe.import_cnefe_to_postgres(
                        zip_path, "SP", muni_map={3550308: ("SAO PAULO", "SP")}
                    )

            mock_proc.stdin.close.assert_called()
            mock_proc.wait.assert_called()
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)


if __name__ == "__main__":
    unittest.main()
