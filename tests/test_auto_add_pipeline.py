from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core import build_daily_records, build_output_workbook, normalize_punches
from services.storage import add_employees_if_missing, init_storage, load_employee_df
from services.validators import (
    build_unknown_employee_records,
    detect_unknown_employee_ids,
    safe_int,
)


class AutomaticAttendanceEmployeePipelineTests(unittest.TestCase):
    def test_unknown_attendance_id_is_saved_and_processed_in_same_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "pipeline.db"
            init_storage(db_path)
            raw_rows = [
                {"ID Number": 99, "Name": " New   Employee ", "Date/Time": "12/01/2026 8:05:00 am"},
                {"ID Number": 99, "Name": "New Employee", "Date/Time": "12/01/2026 5:05:00 pm"},
            ]

            punches = normalize_punches(raw_rows)
            saved_before = load_employee_df(db_path)
            unknown_ids = detect_unknown_employee_ids(punches, saved_before)
            self.assertEqual(unknown_ids, [99])

            suggestions = build_unknown_employee_records(raw_rows, unknown_ids)
            self.assertEqual(add_employees_if_missing(db_path, suggestions), [99])
            saved_after = load_employee_df(db_path)
            self.assertNotIn(99, detect_unknown_employee_ids(punches, saved_after))

            employee_config = {
                safe_int(row.employee_id): {
                    "short_name": row.short_name,
                    "full_name": row.full_name,
                    "schedule_in": row.schedule_in,
                    "schedule_out": row.schedule_out,
                }
                for row in saved_after.itertuples(index=False)
            }
            records, employee_meta, _ = build_daily_records(punches, employee_config, [])
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].employee_id, 99)
            self.assertEqual(records[0].display_name, "New Employee")
            self.assertEqual(records[0].time_in.strftime("%H:%M"), "08:05")
            self.assertEqual(records[0].time_out.strftime("%H:%M"), "17:05")
            self.assertEqual(build_output_workbook(records, employee_meta).sheetnames, ["TIME IN & TIME OUT"])


if __name__ == "__main__":
    unittest.main()
