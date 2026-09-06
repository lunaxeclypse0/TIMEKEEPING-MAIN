from __future__ import annotations

import base64
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


DEFAULT_EMPLOYEE_COLUMNS = [
    "employee_id",
    "short_name",
    "full_name",
    "schedule_in",
    "schedule_out",
]

DEFAULT_ADJUSTMENT_COLUMNS = [
    "date",
    "employee_id",
    "type",
    "value",
    "label",
    "remarks",
]

MAX_AUTOMATIC_BACKUPS = 20


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_database_path(base_dir: Path) -> Path:
    """Allow deployments to place SQLite on a persistent mounted directory."""
    configured = os.environ.get("TIMEKEEPING_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (base_dir / "data" / "goclinic_timekeeping.db").resolve()


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def _default_employee_records() -> list[dict[str, Any]]:
    from core import DEFAULT_EMPLOYEE_CONFIG

    return [
        {
            "employee_id": int(emp_id),
            "short_name": str(cfg.get("short_name", "")).strip(),
            "full_name": str(cfg.get("full_name", "")).strip(),
            "schedule_in": str(cfg.get("schedule_in", "08:00")).strip(),
            "schedule_out": str(cfg.get("schedule_out", "17:00")).strip(),
        }
        for emp_id, cfg in sorted(DEFAULT_EMPLOYEE_CONFIG.items())
    ]


def _normalize_employee(employee: Mapping[str, Any]) -> dict[str, Any]:
    try:
        employee_number = float(str(employee.get("employee_id", "")).strip())
    except (TypeError, ValueError):
        raise ValueError("Employee ID must be a positive whole number.") from None
    if not math.isfinite(employee_number) or not employee_number.is_integer():
        raise ValueError("Employee ID must be a positive whole number.")
    employee_id = int(employee_number)
    if employee_id < 1:
        raise ValueError("Employee ID must be a positive whole number.")

    record = {
        "employee_id": employee_id,
        "short_name": str(employee.get("short_name", "") or "").strip(),
        "full_name": str(employee.get("full_name", "") or "").strip(),
        "schedule_in": str(employee.get("schedule_in", "") or "").strip(),
        "schedule_out": str(employee.get("schedule_out", "") or "").strip(),
    }
    if not record["short_name"]:
        raise ValueError("Short Name / Username is required.")
    if not record["full_name"]:
        raise ValueError("Full Name is required.")
    if not re.fullmatch(r"\d{2}:\d{2}", record["schedule_in"]):
        raise ValueError("Schedule In must use HH:MM format.")
    if not re.fullmatch(r"\d{2}:\d{2}", record["schedule_out"]):
        raise ValueError("Schedule Out must use HH:MM format.")
    parsed_times = {}
    for label, value in (("Schedule In", record["schedule_in"]), ("Schedule Out", record["schedule_out"])):
        try:
            parsed_times[label] = datetime.strptime(value, "%H:%M")
        except ValueError:
            raise ValueError(f"{label} is not a valid 24-hour time.") from None
    if parsed_times["Schedule Out"] <= parsed_times["Schedule In"]:
        raise ValueError("Schedule Out must be later than Schedule In; overnight shifts are not supported.")
    return record


def _employee_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT employee_id, short_name, full_name, schedule_in, schedule_out
        FROM employees
        ORDER BY employee_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _sync_legacy_employee_state(conn: sqlite3.Connection) -> None:
    """Keep the former JSON value current so rollback to the old app stays safe."""
    payload = _employee_rows(conn)
    conn.execute(
        """
        INSERT INTO app_state (key, json_value)
        VALUES ('employee_directory', ?)
        ON CONFLICT(key) DO UPDATE SET json_value = excluded.json_value
        """,
        (json.dumps(payload, ensure_ascii=False),),
    )


def init_storage(db_path: Path) -> None:
    needs_migration_backup = False
    if db_path.exists() and db_path.stat().st_size > 0:
        with sqlite3.connect(db_path) as existing_conn:
            has_employees_table = existing_conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'employees'"
            ).fetchone()
            needs_migration_backup = has_employees_table is None
    if needs_migration_backup:
        backup_database(db_path, "before-storage-migration")

    with _connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                json_value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                employee_id INTEGER PRIMARY KEY CHECK (employee_id > 0),
                short_name TEXT NOT NULL CHECK (length(trim(short_name)) > 0),
                full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
                schedule_in TEXT NOT NULL,
                schedule_out TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                action TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete', 'import')),
                before_json TEXT,
                after_json TEXT,
                changed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_employee_audit_changed_at
            ON employee_audit_log(changed_at DESC)
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        if count == 0:
            legacy = conn.execute(
                "SELECT json_value FROM app_state WHERE key = 'employee_directory'"
            ).fetchone()
            records: list[Mapping[str, Any]] = []
            if legacy:
                try:
                    decoded = json.loads(legacy[0])
                    if isinstance(decoded, list):
                        records = decoded
                except (TypeError, json.JSONDecodeError):
                    records = []
            if not records:
                records = _default_employee_records()

            timestamp = _utc_now()
            for raw in records:
                try:
                    record = _normalize_employee(raw)
                except ValueError:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO employees (
                        employee_id, short_name, full_name, schedule_in, schedule_out,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["employee_id"], record["short_name"], record["full_name"],
                        record["schedule_in"], record["schedule_out"], timestamp, timestamp,
                    ),
                )
            _sync_legacy_employee_state(conn)


def _load_state(db_path: Path, key: str):
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT json_value FROM app_state WHERE key = ?", (key,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None


def _save_state(db_path: Path, key: str, value) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO app_state (key, json_value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET json_value = excluded.json_value
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )


def backup_database(db_path: Path, reason: str = "change") -> Path | None:
    if not db_path.exists():
        return None
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    safe_reason = re.sub(r"[^a-z0-9_-]+", "-", reason.lower()).strip("-") or "change"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = backup_dir / f"{db_path.stem}-{stamp}-{safe_reason}.db"
    with _connect(db_path) as source, sqlite3.connect(destination) as target:
        source.backup(target)

    backups = sorted(backup_dir.glob(f"{db_path.stem}-*.db"), key=lambda p: p.stat().st_mtime)
    for old_backup in backups[:-MAX_AUTOMATIC_BACKUPS]:
        old_backup.unlink(missing_ok=True)
    return destination


def default_employee_df() -> pd.DataFrame:
    return pd.DataFrame(_default_employee_records(), columns=DEFAULT_EMPLOYEE_COLUMNS)


def default_adjustments_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "date": "2025-12-30",
            "employee_id": "ALL",
            "type": "regular_holiday",
            "value": 1,
            "label": "Rizal Day",
            "remarks": "",
        },
        {
            "date": "2026-01-01",
            "employee_id": "ALL",
            "type": "regular_holiday",
            "value": 1,
            "label": "New Year's Day",
            "remarks": "",
        },
    ])


def load_employee_df(db_path: Path) -> pd.DataFrame:
    init_storage(db_path)
    with _connect(db_path) as conn:
        rows = _employee_rows(conn)
    return pd.DataFrame(rows, columns=DEFAULT_EMPLOYEE_COLUMNS).fillna("")


def _write_audit(
    conn: sqlite3.Connection,
    employee_id: int,
    action: str,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO employee_audit_log (
            employee_id, action, before_json, after_json, changed_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            employee_id,
            action,
            json.dumps(dict(before), ensure_ascii=False) if before else None,
            json.dumps(dict(after), ensure_ascii=False) if after else None,
            _utc_now(),
        ),
    )


def add_employee(db_path: Path, employee: Mapping[str, Any]) -> None:
    record = _normalize_employee(employee)
    init_storage(db_path)
    backup_database(db_path, "before-add-employee")
    timestamp = _utc_now()
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO employees (
                employee_id, short_name, full_name, schedule_in, schedule_out,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["employee_id"], record["short_name"], record["full_name"],
                record["schedule_in"], record["schedule_out"], timestamp, timestamp,
            ),
        )
        _write_audit(conn, record["employee_id"], "create", None, record)
        _sync_legacy_employee_state(conn)


def add_employees_if_missing(
    db_path: Path,
    employees: list[Mapping[str, Any]],
) -> list[int]:
    """Atomically add attendance IDs without changing existing employees."""
    normalized_by_id: dict[int, dict[str, Any]] = {}
    for employee in employees:
        record = _normalize_employee(employee)
        normalized_by_id.setdefault(record["employee_id"], record)
    if not normalized_by_id:
        return []

    init_storage(db_path)
    requested_ids = sorted(normalized_by_id)
    placeholders = ",".join("?" for _ in requested_ids)
    with _connect(db_path) as conn:
        existing_ids = {
            int(row[0])
            for row in conn.execute(
                f"SELECT employee_id FROM employees WHERE employee_id IN ({placeholders})",
                requested_ids,
            ).fetchall()
        }
    if existing_ids == set(requested_ids):
        return []

    backup_database(db_path, "before-auto-add-employees")
    timestamp = _utc_now()
    added_ids: list[int] = []
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for employee_id in requested_ids:
            record = normalized_by_id[employee_id]
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO employees (
                    employee_id, short_name, full_name, schedule_in, schedule_out,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["employee_id"], record["short_name"], record["full_name"],
                    record["schedule_in"], record["schedule_out"], timestamp, timestamp,
                ),
            )
            if cursor.rowcount == 1:
                added_ids.append(employee_id)
                _write_audit(conn, employee_id, "create", None, record)
        if added_ids:
            _sync_legacy_employee_state(conn)
    return added_ids


def update_employee(
    db_path: Path,
    original_employee_id: int,
    employee: Mapping[str, Any],
) -> None:
    record = _normalize_employee(employee)
    init_storage(db_path)
    backup_database(db_path, "before-update-employee")
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        old_row = conn.execute(
            """
            SELECT employee_id, short_name, full_name, schedule_in, schedule_out
            FROM employees WHERE employee_id = ?
            """,
            (int(original_employee_id),),
        ).fetchone()
        if old_row is None:
            raise LookupError("Employee no longer exists. Reload the directory and try again.")
        conn.execute(
            """
            UPDATE employees
            SET employee_id = ?, short_name = ?, full_name = ?, schedule_in = ?,
                schedule_out = ?, updated_at = ?
            WHERE employee_id = ?
            """,
            (
                record["employee_id"], record["short_name"], record["full_name"],
                record["schedule_in"], record["schedule_out"], _utc_now(),
                int(original_employee_id),
            ),
        )
        _write_audit(conn, record["employee_id"], "update", dict(old_row), record)
        _sync_legacy_employee_state(conn)


def delete_employee(db_path: Path, employee_id: int) -> None:
    init_storage(db_path)
    backup_database(db_path, "before-delete-employee")
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        old_row = conn.execute(
            """
            SELECT employee_id, short_name, full_name, schedule_in, schedule_out
            FROM employees WHERE employee_id = ?
            """,
            (int(employee_id),),
        ).fetchone()
        if old_row is None:
            raise LookupError("Employee no longer exists. Reload the directory and try again.")
        conn.execute("DELETE FROM employees WHERE employee_id = ?", (int(employee_id),))
        _write_audit(conn, int(employee_id), "delete", dict(old_row), None)
        _sync_legacy_employee_state(conn)


def save_employee_df(db_path: Path, df: pd.DataFrame) -> None:
    """Atomically upsert rows without deleting employees added by another session."""
    records: list[dict[str, Any]] = []
    for raw in df.fillna("").to_dict(orient="records"):
        if not any(str(raw.get(col, "")).strip() for col in DEFAULT_EMPLOYEE_COLUMNS):
            continue
        records.append(_normalize_employee(raw))

    init_storage(db_path)
    backup_database(db_path, "before-employee-import")
    timestamp = _utc_now()
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for record in records:
            old = conn.execute(
                """
                SELECT employee_id, short_name, full_name, schedule_in, schedule_out
                FROM employees WHERE employee_id = ?
                """,
                (record["employee_id"],),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO employees (
                    employee_id, short_name, full_name, schedule_in, schedule_out,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(employee_id) DO UPDATE SET
                    short_name = excluded.short_name,
                    full_name = excluded.full_name,
                    schedule_in = excluded.schedule_in,
                    schedule_out = excluded.schedule_out,
                    updated_at = excluded.updated_at
                """,
                (
                    record["employee_id"], record["short_name"], record["full_name"],
                    record["schedule_in"], record["schedule_out"], timestamp, timestamp,
                ),
            )
            before = dict(old) if old else None
            if before != record:
                _write_audit(conn, record["employee_id"], "import", before, record)
        _sync_legacy_employee_state(conn)


def merge_employee_directories(base_df: pd.DataFrame, override_df: pd.DataFrame) -> pd.DataFrame:
    """Merge CSV updates by employee ID while retaining saved employees not in the CSV."""
    combined: dict[int, dict[str, Any]] = {}
    for source in (base_df, override_df):
        for raw in source.fillna("").to_dict(orient="records"):
            try:
                record = _normalize_employee(raw)
            except ValueError:
                record = {col: raw.get(col, "") for col in DEFAULT_EMPLOYEE_COLUMNS}
                try:
                    key = int(float(str(record["employee_id"]).strip()))
                except (TypeError, ValueError):
                    key = -(len(combined) + 1)
                combined[key] = record
                continue
            combined[record["employee_id"]] = record
    return pd.DataFrame(list(combined.values()), columns=DEFAULT_EMPLOYEE_COLUMNS).reset_index(drop=True)


def list_recent_employee_changes(db_path: Path, limit: int = 10) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT audit_id, employee_id, action, before_json, after_json, changed_at
            FROM employee_audit_log
            ORDER BY audit_id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def load_adjustments_df(db_path: Path) -> pd.DataFrame:
    data = _load_state(db_path, "adjustments")
    if not data:
        return default_adjustments_df()
    df = pd.DataFrame(data)
    for col in DEFAULT_ADJUSTMENT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[DEFAULT_ADJUSTMENT_COLUMNS].fillna("")


def save_adjustments_df(db_path: Path, df: pd.DataFrame) -> None:
    cleaned = df.fillna("").copy()
    cleaned = cleaned[
        ~(
            (cleaned["date"].astype(str).str.strip() == "")
            & (cleaned["employee_id"].astype(str).str.strip() == "")
            & (cleaned["type"].astype(str).str.strip() == "")
            & (cleaned["value"].astype(str).str.strip() == "")
            & (cleaned["label"].astype(str).str.strip() == "")
            & (cleaned["remarks"].astype(str).str.strip() == "")
        )
    ]
    payload = cleaned[DEFAULT_ADJUSTMENT_COLUMNS].to_dict(orient="records")
    _save_state(db_path, "adjustments", payload)


def load_settings(db_path: Path) -> dict:
    data = _load_state(db_path, "settings")
    return data if isinstance(data, dict) else {}


def save_settings(db_path: Path, data: dict) -> None:
    _save_state(db_path, "settings", data)


def find_logo_base64(base_dir: Path) -> str | None:
    possible_files = [
        "assets/1.png", "assets/1.jpg", "assets/1.jpeg",
        "assets/goclinic_logo.png", "assets/goclinic_logo.jpg", "assets/goclinic_logo.jpeg",
        "1.png", "1.jpg", "1.jpeg",
        "goclinic_logo.png", "goclinic_logo.jpg", "goclinic_logo.jpeg",
    ]
    for rel_path in possible_files:
        path = base_dir / rel_path
        if path.exists():
            return base64.b64encode(path.read_bytes()).decode("utf-8")
    return None
