from __future__ import annotations

import unittest
from datetime import date, datetime

from core import (
    Adjustment,
    RawPunch,
    accounting_review_rows,
    apply_accounting_review,
    build_daily_records,
    build_output_workbook,
    normalize_punches,
    parse_datetime_value,
)


class AccountingReferenceTests(unittest.TestCase):
    CONFIG = {
        4: {"short_name": "Cris", "full_name": "Baliton, Maria Cristina E.", "schedule_in": "09:00", "schedule_out": "17:00"},
        7: {"short_name": "Kazz", "full_name": "Pavia, Kazzela Aira C.", "schedule_in": "09:00", "schedule_out": "18:00"},
        8: {"short_name": "Janneth", "full_name": "Duran, Janneth B.", "schedule_in": "06:00", "schedule_out": "15:00"},
        14: {"short_name": "Crystal", "full_name": "De Guzman, Crystal Joy A.", "schedule_in": "06:00", "schedule_out": "15:00"},
        19: {"short_name": "Wela", "full_name": "Coloma, Louela", "schedule_in": "06:00", "schedule_out": "18:00"},
        26: {"short_name": "Kath", "full_name": "Mamalayan, Katherine Nicole", "schedule_in": "09:00", "schedule_out": "15:00"},
    }

    @staticmethod
    def punches(employee_id: int, time_in: str, time_out: str | None = None) -> list[RawPunch]:
        values = [RawPunch(employee_id, parse_datetime_value(time_in))]
        if time_out:
            values.append(RawPunch(employee_id, parse_datetime_value(time_out)))
        return values

    def build(self, punches, adjustments=None):
        records, meta, dates = build_daily_records(punches, self.CONFIG, adjustments or [])
        self.assertTrue(records)
        return records, meta, dates

    def test_invalid_fractional_ids_are_skipped_and_duplicates_removed(self) -> None:
        rows = [
            {"Employee ID": "10.5", "Date/Time": "2026-09-01 08:00"},
            {"Employee ID": "abc", "Date/Time": "2026-09-01 08:00"},
            {"Employee ID": "10.0", "Date/Time": "2026-09-01 08:00"},
            {"Employee ID": "10", "Date/Time": "2026-09-01 08:00"},
        ]
        punches = normalize_punches(rows)
        self.assertEqual([(p.employee_id, p.punch_at) for p in punches], [(10, datetime(2026, 9, 1, 8, 0))])

    def test_24_hour_slash_datetime_is_supported(self) -> None:
        self.assertEqual(parse_datetime_value("01/09/2026 17:30:45"), datetime(2026, 9, 1, 17, 30, 45))

    def test_reference_cris_late_and_long_undertime_exception(self) -> None:
        records, _, _ = self.build(self.punches(4, "06/01/2026 8:10:32 am", "06/01/2026 1:12:23 pm"))
        self.assertEqual(records[0].late_minutes, 10)
        self.assertIsNone(records[0].undertime_minutes)

    def test_reference_janneth_dynamic_shift_and_completed_overtime(self) -> None:
        records, _, _ = self.build(self.punches(8, "06/01/2026 8:05:24 am", "06/01/2026 6:03:35 pm"))
        self.assertEqual(records[0].late_minutes, 5)
        self.assertEqual(records[0].overtime_hours, 1)

    def test_reference_wela_undertime_rounds_up(self) -> None:
        records, _, _ = self.build(self.punches(19, "09/01/2026 8:57:52 am", "09/01/2026 5:14:11 pm"))
        self.assertIsNone(records[0].late_minutes)
        self.assertEqual(records[0].undertime_minutes, 46)

    def test_reference_configured_pair_wins_same_start_time_tie(self) -> None:
        records, _, _ = self.build(self.punches(19, "08/01/2026 5:59:44 am", "08/01/2026 4:07:07 pm"))
        self.assertIsNone(records[0].overtime_hours)

    def test_reference_kath_three_completed_overtime_hours(self) -> None:
        records, _, _ = self.build(self.punches(26, "06/01/2026 5:58:03 am", "06/01/2026 6:03:18 pm"))
        self.assertEqual(records[0].overtime_hours, 3)

    def test_incomplete_punch_retains_late_but_no_out_metric(self) -> None:
        records, _, _ = self.build(self.punches(8, "09/01/2026 8:23:05 am"))
        self.assertEqual(records[0].late_minutes, 23)
        self.assertIsNone(records[0].undertime_minutes)
        self.assertIsNone(records[0].overtime_hours)
        self.assertEqual(records[0].remarks, "no time out")

    def test_force_no_time_in_has_no_false_undertime(self) -> None:
        punches = self.punches(7, "03/01/2026 5:18:19 pm")
        adjustments = [Adjustment(date(2026, 1, 3), 7, "force_no_time_in", 0)]
        records, _, _ = self.build(punches, adjustments)
        self.assertIsNone(records[0].time_in)
        self.assertEqual(records[0].time_out, datetime(2026, 1, 3, 17, 18, 19))
        self.assertIsNone(records[0].undertime_minutes)
        self.assertEqual(records[0].remarks, "no time in")

    def test_half_day_adjustment_matches_reference_without_forced_remark(self) -> None:
        punches = self.punches(14, "08/01/2026 8:55:23 am", "08/01/2026 2:06:53 pm")
        adjustments = [Adjustment(date(2026, 1, 8), 14, "half_day", 0.5)]
        records, _, _ = self.build(punches, adjustments)
        self.assertEqual(records[0].half_day, 0.5)
        self.assertIsNone(records[0].remarks)
        self.assertIsNone(records[0].undertime_minutes)

    def test_no_punch_adjustment_does_not_create_detail_row(self) -> None:
        punches = self.punches(4, "02/01/2026 7:58:16 am", "02/01/2026 5:07:22 pm")
        adjustments = [Adjustment(date(2026, 1, 1), 4, "paid_leave", 1, "New Year", "")]
        records, _, dates = self.build(punches, adjustments)
        self.assertEqual(len(records), 1)
        self.assertEqual(dates, [date(2026, 1, 2)])

    def test_accounting_review_can_apply_special_roster_correction(self) -> None:
        punches = self.punches(8, "03/01/2026 8:07:30 am", "03/01/2026 6:04:33 pm")
        records, _, _ = self.build(punches)
        self.assertEqual(records[0].late_minutes, 7)
        self.assertEqual(records[0].overtime_hours, 1)

        rows = accounting_review_rows(records)
        rows[0]["Late"] = None
        rows[0]["Overtime"] = None
        reviewed = apply_accounting_review(records, rows)
        self.assertIsNone(reviewed[0].late_minutes)
        self.assertIsNone(reviewed[0].overtime_hours)

    def test_accounting_review_validates_dates_and_half_day_exclusivity(self) -> None:
        records, _, _ = self.build(self.punches(4, "03/01/2026 8:07:18 am", "03/01/2026 5:01:31 pm"))
        rows = accounting_review_rows(records)
        rows[0]["Half Day"] = 0.5
        reviewed = apply_accounting_review(records, rows)
        self.assertEqual(reviewed[0].half_day, 0.5)
        self.assertIsNone(reviewed[0].late_minutes)

        rows[0]["Date/Time (OUT)"] = "04/01/2026 5:01:31 pm"
        with self.assertRaisesRegex(ValueError, "same date"):
            apply_accounting_review(records, rows)

    def test_export_has_only_approved_detail_sheet_and_exact_headers(self) -> None:
        records, meta, _ = self.build(self.punches(8, "06/01/2026 8:05:24 am", "06/01/2026 6:03:35 pm"))
        workbook = build_output_workbook(records, meta)
        self.assertEqual(workbook.sheetnames, ["TIME IN & TIME OUT"])
        sheet = workbook.active
        self.assertEqual(
            [sheet.cell(1, column).value for column in range(1, 10)],
            [None, "Name", "Date/Time (IN)", "Date/Time (OUT)", "Late", "Undertime", "Overtime", "Half Day", "Remarks"],
        )
        self.assertEqual(sheet["D4"].value, "=COUNTA(B3:B3)-SUM(H3:H3)")
        self.assertEqual(sheet["E4"].value, "=SUM(E3:E3)")
        self.assertTrue(sheet.sheet_view.showGridLines)
        all_values = [cell.value for row in sheet.iter_rows() for cell in row]
        self.assertNotIn("Credited Days", all_values)


if __name__ == "__main__":
    unittest.main()
