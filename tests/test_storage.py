from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from services.storage import (
    add_employee,
    add_employees_if_missing,
    delete_employee,
    init_storage,
    list_recent_employee_changes,
    load_employee_df,
    merge_employee_directories,
    save_employee_df,
    update_employee,
)


def employee(employee_id: int, name: str) -> dict:
    return {
        "employee_id": employee_id,
        "short_name": name,
        "full_name": f"{name} Example",
        "schedule_in": "08:00",
        "schedule_out": "17:00",
    }


class EmployeeStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "timekeeping.db"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE app_state (key TEXT PRIMARY KEY, json_value TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT INTO app_state (key, json_value) VALUES (?, ?)",
                ("employee_directory", json.dumps([employee(1, "Legacy")])),
            )
        init_storage(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_legacy_employee_is_migrated_without_data_loss(self) -> None:
        loaded = load_employee_df(self.db_path)
        self.assertEqual(loaded["employee_id"].tolist(), [1])
        self.assertEqual(loaded.iloc[0]["short_name"], "Legacy")

    def test_add_update_delete_are_durable_and_audited(self) -> None:
        add_employee(self.db_path, employee(2, "Added"))
        self.assertIn(2, load_employee_df(self.db_path)["employee_id"].tolist())

        updated = employee(20, "Updated")
        update_employee(self.db_path, 2, updated)
        loaded = load_employee_df(self.db_path)
        self.assertNotIn(2, loaded["employee_id"].tolist())
        self.assertIn(20, loaded["employee_id"].tolist())

        delete_employee(self.db_path, 20)
        self.assertNotIn(20, load_employee_df(self.db_path)["employee_id"].tolist())
        actions = [entry["action"] for entry in reversed(list_recent_employee_changes(self.db_path))]
        self.assertEqual(actions[-3:], ["create", "update", "delete"])

    def test_stale_bulk_save_does_not_remove_concurrent_addition(self) -> None:
        stale_session = load_employee_df(self.db_path)
        add_employee(self.db_path, employee(2, "OtherSession"))
        stale_with_new = pd.concat(
            [stale_session, pd.DataFrame([employee(3, "ThisSession")])],
            ignore_index=True,
        )
        save_employee_df(self.db_path, stale_with_new)
        self.assertEqual(load_employee_df(self.db_path)["employee_id"].tolist(), [1, 2, 3])

    def test_concurrent_unique_employee_adds_are_all_preserved(self) -> None:
        records = [employee(employee_id, f"E{employee_id}") for employee_id in range(30, 36)]
        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(lambda record: add_employee(self.db_path, record), records))
        saved_ids = set(load_employee_df(self.db_path)["employee_id"].tolist())
        self.assertTrue({30, 31, 32, 33, 34, 35}.issubset(saved_ids))

    def test_duplicate_employee_id_is_rejected(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            add_employee(self.db_path, employee(1, "Duplicate"))

    def test_fractional_employee_id_and_overnight_shift_are_rejected(self) -> None:
        fractional = employee(2, "Fractional")
        fractional["employee_id"] = "2.5"
        with self.assertRaises(ValueError):
            add_employee(self.db_path, fractional)

        overnight = employee(2, "Overnight")
        overnight["schedule_in"] = "22:00"
        overnight["schedule_out"] = "06:00"
        with self.assertRaises(ValueError):
            add_employee(self.db_path, overnight)

    def test_csv_merge_preserves_saved_employees_and_overrides_matching_id(self) -> None:
        base = pd.DataFrame([employee(1, "One"), employee(2, "Two")])
        override = pd.DataFrame([employee(2, "TwoUpdated"), employee(3, "Three")])
        merged = merge_employee_directories(base, override).set_index("employee_id")
        self.assertEqual(set(merged.index), {1, 2, 3})
        self.assertEqual(merged.loc[2, "short_name"], "TwoUpdated")

    def test_backup_is_created_before_change(self) -> None:
        add_employee(self.db_path, employee(2, "BackupCheck"))
        backups = sorted((self.db_path.parent / "backups").glob("*.db"))
        self.assertTrue(backups)
        with sqlite3.connect(backups[-1]) as conn:
            count = conn.execute("SELECT COUNT(*) FROM employees WHERE employee_id = 2").fetchone()[0]
        self.assertEqual(count, 0)

    def test_auto_add_is_insert_only_and_survives_reload(self) -> None:
        added = add_employees_if_missing(
            self.db_path,
            [employee(1, "MustNotOverwrite"), employee(2, "RawNewHire")],
        )
        self.assertEqual(added, [2])
        reloaded = load_employee_df(self.db_path).set_index("employee_id")
        self.assertEqual(reloaded.loc[1, "short_name"], "Legacy")
        self.assertEqual(reloaded.loc[2, "short_name"], "RawNewHire")

        second_run = add_employees_if_missing(self.db_path, [employee(2, "DifferentName")])
        self.assertEqual(second_run, [])
        self.assertEqual(load_employee_df(self.db_path).set_index("employee_id").loc[2, "short_name"], "RawNewHire")

    def test_auto_add_invalid_batch_is_atomic(self) -> None:
        invalid = employee(3, "Invalid")
        invalid["schedule_in"] = "99:00"
        with self.assertRaises(ValueError):
            add_employees_if_missing(self.db_path, [employee(2, "Valid"), invalid])
        self.assertEqual(load_employee_df(self.db_path)["employee_id"].tolist(), [1])

    def test_concurrent_auto_add_same_id_never_overwrites(self) -> None:
        candidates = [employee(40, "FirstCandidate"), employee(40, "SecondCandidate")]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda record: add_employees_if_missing(self.db_path, [record]), candidates))
        self.assertEqual(sum(len(result) for result in results), 1)
        saved = load_employee_df(self.db_path).set_index("employee_id")
        self.assertIn(saved.loc[40, "short_name"], {"FirstCandidate", "SecondCandidate"})
        creates = [
            item for item in list_recent_employee_changes(self.db_path, limit=100)
            if item["employee_id"] == 40 and item["action"] == "create"
        ]
        self.assertEqual(len(creates), 1)


if __name__ == "__main__":
    unittest.main()
