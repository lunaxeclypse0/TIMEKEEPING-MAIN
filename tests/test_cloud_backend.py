from __future__ import annotations

import os
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import postgres_storage, storage_backend
from scripts.migrate_sqlite_to_supabase import load_sqlite_source_without_mutation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CloudStorageConfigurationTests(unittest.TestCase):
    def test_dispatcher_keeps_sqlite_for_local_use(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"TIMEKEEPING_DATABASE_URL": ""}, clear=False):
                target = storage_backend.resolve_database_path(Path(temp_dir))
                self.assertEqual(storage_backend.storage_mode(), "sqlite-local")
                storage_backend.init_storage(target)
                self.assertTrue(Path(target).is_file())

    def test_dispatcher_selects_cloud_without_exposing_or_connecting_dsn(self) -> None:
        dsn = "postgresql://postgres.example:secret@pooler.example.com:6543/postgres?sslmode=require"
        with patch.dict(os.environ, {"TIMEKEEPING_DATABASE_URL": dsn}, clear=False):
            self.assertEqual(storage_backend.storage_mode(), "supabase-postgresql")
            self.assertEqual(storage_backend.resolve_database_path(PROJECT_ROOT), dsn)

    def test_cloud_dsn_validation_rejects_non_postgresql_values(self) -> None:
        with patch.dict(os.environ, {"TIMEKEEPING_DATABASE_URL": "https://example.invalid"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "PostgreSQL connection string"):
                postgres_storage.resolve_database_path(PROJECT_ROOT)

        with patch.dict(
            os.environ,
            {"TIMEKEEPING_DATABASE_URL": "postgresql://postgres:secret@example.invalid/postgres"},
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "require SSL"):
                postgres_storage.resolve_database_path(PROJECT_ROOT)

    def test_cloud_employee_validation_happens_before_database_connection(self) -> None:
        invalid = {
            "employee_id": 90,
            "short_name": "Invalid",
            "full_name": "Invalid Schedule",
            "schedule_in": "22:00",
            "schedule_out": "06:00",
        }
        with self.assertRaisesRegex(ValueError, "overnight shifts are not supported"):
            postgres_storage.add_employee("postgresql://unused", invalid)

    def test_schema_is_private_and_cloud_driver_is_pinned(self) -> None:
        schema = (PROJECT_ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create schema if not exists timekeeping", schema)
        self.assertIn("revoke all on schema timekeeping from anon, authenticated", schema)
        self.assertEqual(schema.count("enable row level security"), 4)
        requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("psycopg[binary]==3.3.5", requirements)

        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("from services.storage_backend import", app_source)
        self.assertIn("Permanent Supabase database connected", app_source)

    def test_deployment_secrets_are_excluded_from_git(self) -> None:
        ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".streamlit/secrets.toml", ignored)
        self.assertIn(".env", ignored)

    def test_sqlite_migration_reader_does_not_modify_source_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.db"
            shutil.copy2(PROJECT_ROOT / "data" / "goclinic_timekeeping.db", source)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            employees, adjustments, settings = load_sqlite_source_without_mutation(source)
            after = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(after, before)
            self.assertFalse(employees.empty)
            self.assertFalse(adjustments.empty)
            self.assertIsInstance(settings, dict)


if __name__ == "__main__":
    unittest.main()
