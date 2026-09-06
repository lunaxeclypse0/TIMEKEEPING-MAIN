from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any, Iterable, Mapping

import pandas as pd


VALID_ADJUSTMENT_TYPES = {
    "regular_holiday",
    "special_holiday",
    "paid_leave",
    "unpaid_leave",
    "rest_day",
    "absent",
    "manual_adjustment",
    "half_day",
    "adjustment_days",
    "force_no_time_in",
    "force_no_time_out",
    "",
}

# FIX: Was r"^\\\\d{2}:\\\\d{2}$" — never matched any real time string.
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def safe_int(value):
    try:
        # FIX: Guard against list/array which causes pd.isna() to raise ValueError.
        if isinstance(value, (list, dict)):
            return None
        if pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None
        number = float(text)
        if not math.isfinite(number) or not number.is_integer():
            return None
        return int(number)
    except Exception:
        return None


def is_blank_row(row, fields: list[str]) -> bool:
    for field in fields:
        value = row.get(field, "")
        if pd.isna(value):
            value = ""
        if str(value).strip() != "":
            return False
    return True


def _is_valid_time(text: str) -> bool:
    text = str(text).strip()
    if text == "":
        return False
    if not TIME_PATTERN.match(text):
        return False
    try:
        datetime.strptime(text, "%H:%M")
        return True
    except ValueError:
        return False


def _is_valid_date_or_blank(text: str) -> bool:
    text = str(text).strip()
    if text == "":
        return True
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def validate_employee_df(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    if df.empty:
        issues.append("Employee directory is empty.")
        return issues

    required = {"employee_id", "short_name", "full_name", "schedule_in", "schedule_out"}
    missing = required - set(df.columns)
    if missing:
        issues.append(f"Employee directory missing columns: {', '.join(sorted(missing))}")
        return issues

    cleaned_ids = []
    schedule_issue_rows = []
    missing_name_rows = []

    for idx, row in df.reset_index(drop=True).iterrows():
        row_no = idx + 1

        if is_blank_row(row, ["employee_id", "short_name", "full_name", "schedule_in", "schedule_out"]):
            continue

        emp_id = safe_int(row.get("employee_id"))
        if emp_id is None:
            issues.append(f"Row {row_no}: invalid employee ID.")
        else:
            cleaned_ids.append(emp_id)

        short_name = str(row.get("short_name", "") or "").strip()
        full_name = str(row.get("full_name", "") or "").strip()
        if not short_name or not full_name:
            missing_name_rows.append(row_no)

        schedule_in  = str(row.get("schedule_in",  "") or "").strip()
        schedule_out = str(row.get("schedule_out", "") or "").strip()

        schedule_in_valid = _is_valid_time(schedule_in)
        schedule_out_valid = _is_valid_time(schedule_out)
        if not schedule_in_valid:
            schedule_issue_rows.append(row_no)
        if not schedule_out_valid:
            schedule_issue_rows.append(row_no)
        if schedule_in_valid and schedule_out_valid:
            in_time = datetime.strptime(schedule_in, "%H:%M")
            out_time = datetime.strptime(schedule_out, "%H:%M")
            if out_time <= in_time:
                issues.append(
                    f"Row {row_no}: Schedule Out must be later than Schedule In; overnight shifts are not supported."
                )

    if len(cleaned_ids) != len(set(cleaned_ids)):
        issues.append("Duplicate employee IDs found in employee directory.")

    if missing_name_rows:
        joined = ", ".join(map(str, missing_name_rows[:10]))
        extra = f" and {len(missing_name_rows) - 10} more" if len(missing_name_rows) > 10 else ""
        issues.append(f"Short Name and Full Name are required in employee rows: {joined}{extra}.")

    if schedule_issue_rows:
        unique_rows = sorted(set(schedule_issue_rows))
        joined = ", ".join(map(str, unique_rows[:10]))
        extra = f" and {len(unique_rows) - 10} more" if len(unique_rows) > 10 else ""
        issues.append(
            f"Invalid schedule format in employee rows: {joined}{extra}. "
            f"Use HH:MM format, e.g. 08:00 or 17:00."
        )

    return issues


def validate_adjustment_df(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    if df.empty:
        return issues

    required = {"date", "employee_id", "type", "value", "label", "remarks"}
    missing = required - set(df.columns)
    if missing:
        issues.append(f"Adjustment table missing columns: {', '.join(sorted(missing))}")
        return issues

    seen_adjustments = set()
    for idx, row in df.reset_index(drop=True).iterrows():
        row_no = idx + 1

        if is_blank_row(row, ["date", "employee_id", "type", "value", "label", "remarks"]):
            continue

        date_text = str(row.get("date", "") or "").strip()
        if not date_text or not _is_valid_date_or_blank(date_text):
            issues.append(f"Adjustment row {row_no} has invalid date format.")

        employee_text = str(row.get("employee_id", "") or "").strip()
        if employee_text and employee_text.upper() != "ALL" and safe_int(employee_text) is None:
            issues.append(f"Adjustment row {row_no} has an invalid employee ID.")

        adj_type = str(row.get("type", "") or "").strip().lower()
        if not adj_type:
            issues.append(f"Adjustment row {row_no} requires a type.")
        elif adj_type not in VALID_ADJUSTMENT_TYPES:
            issues.append(f"Adjustment row {row_no} has invalid type: {adj_type}")

        value_text = str(row.get("value", "") or "").strip()
        if value_text:
            try:
                numeric_value = float(value_text)
            except (TypeError, ValueError):
                issues.append(f"Adjustment row {row_no} requires a numeric value.")
            else:
                if adj_type == "half_day" and not 0 < numeric_value <= 1:
                    issues.append(f"Adjustment row {row_no} half-day value must be above 0 and at most 1.")
                if adj_type in {"regular_holiday", "special_holiday", "paid_leave"} and numeric_value < 0:
                    issues.append(f"Adjustment row {row_no} cannot use a negative credited-day value.")

        normalized_employee = employee_text.upper() if employee_text else "ALL"
        if normalized_employee != "ALL":
            normalized_employee = safe_int(normalized_employee)
        adjustment_key = (date_text, normalized_employee, adj_type)
        if adjustment_key in seen_adjustments:
            issues.append(
                f"Adjustment row {row_no} duplicates an earlier date, employee, and type."
            )
        seen_adjustments.add(adjustment_key)

    return issues


def detect_unknown_adjustment_employee_ids(
    adjustment_df: pd.DataFrame,
    employee_df: pd.DataFrame,
) -> list[int]:
    known_ids = {
        safe_int(value)
        for value in employee_df.get("employee_id", pd.Series(dtype=object)).tolist()
        if safe_int(value) is not None
    }
    unknown_ids = set()
    for value in adjustment_df.get("employee_id", pd.Series(dtype=object)).tolist():
        text = str(value or "").strip()
        if not text or text.upper() == "ALL":
            continue
        employee_id = safe_int(text)
        if employee_id is not None and employee_id not in known_ids:
            unknown_ids.add(employee_id)
    return sorted(unknown_ids)


def get_punch_employee_id(punch):
    if isinstance(punch, dict):
        for key in ["employee_id", "emp_id", "id", "userid", "user_id"]:
            if key in punch:
                return safe_int(punch.get(key))
        return None
    for attr in ["employee_id", "emp_id", "id", "userid", "user_id"]:
        if hasattr(punch, attr):
            return safe_int(getattr(punch, attr))
    return None


def detect_unknown_employee_ids(punches, employee_df: pd.DataFrame) -> list[int]:
    known_ids = {
        safe_int(x)
        for x in (
            employee_df["employee_id"].tolist()
            if "employee_id" in employee_df.columns
            else []
        )
        if safe_int(x) is not None
    }
    found_ids = set()
    for punch in punches:
        emp_id = get_punch_employee_id(punch)
        if emp_id is not None:
            found_ids.add(emp_id)
    return sorted(found_ids - known_ids)


RAW_EMPLOYEE_ID_FIELDS = (
    "ID Number", "ID number", "ID", "ID No.", "No.", "No",
    "Employee ID", "employee_id",
)
RAW_EMPLOYEE_NAME_FIELDS = (
    "Employee Name", "Full Name", "Name", "employee_name",
)


def build_unknown_employee_records(
    raw_rows: Iterable[Mapping[str, Any]],
    unknown_ids: Iterable[int],
    processing_directory: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Build safe employee records from a raw attendance upload.

    A valid uploaded directory row has priority. Otherwise, the most frequent
    non-numeric name found beside the ID is used with a conservative default
    schedule that Accounting can review after automatic creation.
    """
    wanted_ids = {safe_int(value) for value in unknown_ids}
    wanted_ids.discard(None)
    if not wanted_ids:
        return []

    configured: dict[int, dict[str, Any]] = {}
    if processing_directory is not None and not processing_directory.empty:
        for row in processing_directory.fillna("").to_dict(orient="records"):
            employee_id = safe_int(row.get("employee_id"))
            if employee_id in wanted_ids:
                configured[employee_id] = {
                    "employee_id": employee_id,
                    "short_name": str(row.get("short_name", "") or "").strip(),
                    "full_name": str(row.get("full_name", "") or "").strip(),
                    "schedule_in": str(row.get("schedule_in", "") or "").strip(),
                    "schedule_out": str(row.get("schedule_out", "") or "").strip(),
                }

    names_by_id: dict[int, Counter[str]] = {employee_id: Counter() for employee_id in wanted_ids}
    for row in raw_rows:
        employee_id = None
        for field in RAW_EMPLOYEE_ID_FIELDS:
            employee_id = safe_int(row.get(field))
            if employee_id is not None:
                break
        if employee_id not in wanted_ids:
            continue

        for field in RAW_EMPLOYEE_NAME_FIELDS:
            raw_name = row.get(field)
            if raw_name is None:
                continue
            name = re.sub(r"\s+", " ", str(raw_name)).strip()
            if not name or safe_int(name) == employee_id:
                continue
            names_by_id[employee_id][name] += 1
            break

    records: list[dict[str, Any]] = []
    for employee_id in sorted(wanted_ids):
        configured_record = configured.get(employee_id)
        if configured_record and all(
            str(configured_record.get(field, "")).strip()
            for field in ("short_name", "full_name", "schedule_in", "schedule_out")
        ):
            records.append(configured_record)
            continue

        raw_name = names_by_id[employee_id].most_common(1)[0][0] if names_by_id[employee_id] else ""
        records.append({
            "employee_id": employee_id,
            "short_name": raw_name or f"EMP{employee_id}",
            "full_name": raw_name or f"New Employee {employee_id}",
            "schedule_in": "08:00",
            "schedule_out": "17:00",
        })
    return records


def append_unknown_employees(employee_df: pd.DataFrame, unknown_ids: list[int]) -> pd.DataFrame:
    df = employee_df.copy()
    existing = {
        safe_int(x)
        for x in (
            df["employee_id"].tolist()
            if "employee_id" in df.columns
            else []
        )
        if safe_int(x) is not None
    }
    new_rows = []
    for emp_id in unknown_ids:
        if emp_id not in existing:
            new_rows.append({
                "employee_id":  emp_id,
                "short_name":   f"EMP{emp_id}",
                "full_name":    f"New Employee {emp_id}",
                "schedule_in":  "08:00",
                "schedule_out": "17:00",
            })
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    return df
