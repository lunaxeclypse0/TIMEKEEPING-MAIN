from __future__ import annotations

import os
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import postgres_storage, storage as sqlite_storage, storage_backend
from scripts.migrate_sqlite_to_supabase import load_sqlite_source_without_mutation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CloudStorageConfigurationTests(unittest.TestCase):
    def test_transient_connection_errors_are_classified_through_wrappers(self) -> None:
        transient = RuntimeError("database is starting")
        transient.sqlstate = "57P03"
        wrapped = RuntimeError("connection failed")
        wrapped.__cause__ = transient
        self.assertTrue(postgres_storage.is_transient_storage_error(wrapped))

        bad_password = RuntimeError("password authentication failed")
        bad_password.sqlstate = "28P01"
        self.assertFalse(postgres_storage.is_transient_storage_error(bad_password))

    def test_storage_initialization_retries_only_transient_failures(self) -> None:
        transient = RuntimeError("temporary connection failure")
        sleeps: list[float] = []
        retry_events: list[tuple[int, int, float]] = []
        with (
            patch.object(
                storage_backend,
                "init_storage",
                side_effect=[transient, transient, None],
            ) as initializer,
            patch.object(storage_backend, "is_transient_storage_error", return_value=True),
        ):
            completed_attempt = storage_backend.init_storage_with_retry(
                "postgresql://unused",
                attempts=4,
                initial_delay_seconds=1,
                max_delay_seconds=4,
                sleep_fn=sleeps.append,
                on_retry=lambda attempt, maximum, delay: retry_events.append(
                    (attempt, maximum, delay)
                ),
            )

        self.assertEqual(completed_attempt, 3)
        self.assertEqual(initializer.call_count, 3)
        self.assertEqual(sleeps, [1, 2])
        self.assertEqual(retry_events, [(1, 4, 1), (2, 4, 2)])

    def test_storage_initialization_does_not_retry_permanent_failures(self) -> None:
        sleeps: list[float] = []
        with (
            patch.object(storage_backend, "init_storage", side_effect=ValueError("bad DSN")),
            patch.object(storage_backend, "is_transient_storage_error", return_value=False),
        ):
            with self.assertRaisesRegex(ValueError, "bad DSN"):
                storage_backend.init_storage_with_retry(
                    "invalid",
                    sleep_fn=sleeps.append,
                )
        self.assertEqual(sleeps, [])

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
            fixture = PROJECT_ROOT / "data" / "goclinic_timekeeping.db"
            if fixture.is_file():
                shutil.copy2(fixture, source)
            else:
                # The real local database is intentionally gitignored. Build a
                # representative fixture so a clean clone can run this test.
                sqlite_storage.init_storage(source)
                sqlite_storage.save_adjustments_df(
                    source,
                    sqlite_storage.default_adjustments_df(),
                )
                sqlite_storage.save_settings(source, {"source": "generated-test-fixture"})
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            employees, adjustments, settings = load_sqlite_source_without_mutation(source)
            after = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(after, before)
            self.assertFalse(employees.empty)
            self.assertFalse(adjustments.empty)
            self.assertIsInstance(settings, dict)


if __name__ == "__main__":
    unittest.main()
