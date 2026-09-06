from __future__ import annotations

import unittest

import pandas as pd

from services.validators import (
    build_unknown_employee_records,
    detect_unknown_adjustment_employee_ids,
    safe_int,
    validate_adjustment_df,
    validate_employee_df,
)


class EmployeeValidatorTests(unittest.TestCase):
    def test_fractional_employee_id_is_not_silently_truncated(self) -> None:
        self.assertIsNone(safe_int("10.5"))
        self.assertEqual(safe_int("10.0"), 10)

    def test_names_are_required(self) -> None:
        frame = pd.DataFrame([{
            "employee_id": 90,
            "short_name": "",
            "full_name": "",
            "schedule_in": "08:00",
            "schedule_out": "17:00",
        }])
        issues = validate_employee_df(frame)
        self.assertTrue(any("required" in issue.lower() for issue in issues))

    def test_invalid_clock_time_is_rejected(self) -> None:
        frame = pd.DataFrame([{
            "employee_id": 90,
            "short_name": "Test",
            "full_name": "Test Employee",
            "schedule_in": "25:00",
            "schedule_out": "17:00",
        }])
        issues = validate_employee_df(frame)
        self.assertTrue(any("invalid schedule" in issue.lower() for issue in issues))

    def test_unsupported_overnight_schedule_is_rejected(self) -> None:
        frame = pd.DataFrame([{
            "employee_id": 90,
            "short_name": "Test",
            "full_name": "Test Employee",
            "schedule_in": "22:00",
            "schedule_out": "06:00",
        }])
        issues = validate_employee_df(frame)
        self.assertTrue(any("overnight" in issue.lower() for issue in issues))

    def test_adjustment_value_and_employee_id_are_validated(self) -> None:
        frame = pd.DataFrame([{
            "date": "2026-09-01",
            "employee_id": "not-an-id",
            "type": "paid_leave",
            "value": "not-a-number",
            "label": "Approved leave",
            "remarks": "",
        }])
        issues = validate_adjustment_df(frame)
        self.assertTrue(any("employee id" in issue.lower() for issue in issues))
        self.assertTrue(any("numeric value" in issue.lower() for issue in issues))

    def test_duplicate_and_unknown_employee_adjustments_are_detected(self) -> None:
        adjustments = pd.DataFrame([
            {"date": "2026-09-01", "employee_id": 91, "type": "paid_leave", "value": 1, "label": "", "remarks": ""},
            {"date": "2026-09-01", "employee_id": 91, "type": "paid_leave", "value": 1, "label": "", "remarks": ""},
        ])
        issues = validate_adjustment_df(adjustments)
        self.assertTrue(any("duplicates" in issue.lower() for issue in issues))
        employees = pd.DataFrame([{"employee_id": 90}])
        self.assertEqual(detect_unknown_adjustment_employee_ids(adjustments, employees), [91])

    def test_unknown_employee_uses_most_frequent_raw_name(self) -> None:
        rows = [
            {"ID Number": 99, "Name": " New   Employee ", "Date/Time": "2026-09-01 08:00"},
            {"ID Number": 99, "Name": "New Employee", "Date/Time": "2026-09-01 17:00"},
            {"ID Number": 99, "Name": "99", "Date/Time": "2026-09-02 08:00"},
        ]
        records = build_unknown_employee_records(rows, [99])
        self.assertEqual(records, [{
            "employee_id": 99,
            "short_name": "New Employee",
            "full_name": "New Employee",
            "schedule_in": "08:00",
            "schedule_out": "17:00",
        }])

    def test_uploaded_directory_has_priority_for_unknown_employee(self) -> None:
        directory = pd.DataFrame([{
            "employee_id": 99,
            "short_name": "Nina",
            "full_name": "Nina New Hire",
            "schedule_in": "09:00",
            "schedule_out": "18:00",
        }])
        records = build_unknown_employee_records(
            [{"ID Number": 99, "Name": "Biometric Name"}],
            [99],
            directory,
        )
        self.assertEqual(records[0]["full_name"], "Nina New Hire")
        self.assertEqual((records[0]["schedule_in"], records[0]["schedule_out"]), ("09:00", "18:00"))

    def test_unknown_employee_without_name_gets_clear_placeholder(self) -> None:
        records = build_unknown_employee_records(
            [{"ID Number": 101, "Name": "101"}],
            [101],
        )
        self.assertEqual(records[0]["short_name"], "EMP101")
        self.assertEqual(records[0]["full_name"], "New Employee 101")


if __name__ == "__main__":
    unittest.main()
