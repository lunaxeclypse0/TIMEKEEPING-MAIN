from __future__ import annotations

import json
import os
import sqlite3
import threading
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

import pandas as pd

from services.storage import (
    DEFAULT_ADJUSTMENT_COLUMNS,
    DEFAULT_EMPLOYEE_COLUMNS,
    MAX_AUTOMATIC_BACKUPS,
    _default_employee_records,
    _normalize_employee,
    default_adjustments_df,
)


SCHEMA = "timekeeping"
EMPLOYEE_WRITE_LOCK = 711_202_609_060_001
_INITIALIZED_TARGETS: set[str] = set()
_INIT_LOCK = threading.Lock()
_TRANSIENT_SQLSTATES = {
    "53300",  # too_many_connections
    "57P01",  # admin_shutdown
    "57P02",  # crash_shutdown
    "57P03",  # cannot_connect_now
}


def _driver():
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise RuntimeError(
            "Supabase mode requires psycopg 3. Install the pinned project requirements."
        ) from exc
    return psycopg, dict_row, Jsonb


def resolve_database_path(base_dir: Path) -> str:
    del base_dir
    dsn = os.environ.get("TIMEKEEPING_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("TIMEKEEPING_DATABASE_URL is required for Supabase mode.")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("TIMEKEEPING_DATABASE_URL must be a PostgreSQL connection string.")
    ssl_mode = parse_qs(urlsplit(dsn).query).get("sslmode", [""])[0].lower()
    if ssl_mode not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError(
            "TIMEKEEPING_DATABASE_URL must require SSL; append ?sslmode=require "
            "or &sslmode=require to the Supabase connection URI."
        )
    return dsn


def _connect(target: str):
    psycopg, dict_row, _ = _driver()
    try:
        return psycopg.connect(
            str(target),
            row_factory=dict_row,
            connect_timeout=15,
            prepare_threshold=None,
            application_name="goclinic-timekeeping",
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not connect to the permanent Supabase database. Check the secret connection string."
        ) from exc


def is_transient_storage_error(exc: BaseException) -> bool:
    """Return True for connection failures that can recover without configuration changes."""
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        sqlstate = getattr(current, "sqlstate", None)
        if isinstance(sqlstate, str):
            if sqlstate.startswith("08") or sqlstate in _TRANSIENT_SQLSTATES:
                return True

        error_type = type(current)
        if error_type.__module__.startswith("psycopg") and error_type.__name__ in {
            "InterfaceError",
            "OperationalError",
        }:
            return True
        if isinstance(current, (ConnectionError, TimeoutError, OSError)):
            return True

        current = current.__cause__ or current.__context__
    return False


def _employee_rows(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT employee_id, short_name, full_name,
               to_char(schedule_in, 'HH24:MI') AS schedule_in,
               to_char(schedule_out, 'HH24:MI') AS schedule_out
        FROM {SCHEMA}.employees
        ORDER BY employee_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _write_audit(
    conn,
    employee_id: int,
    action: str,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> None:
    _, _, Jsonb = _driver()
    conn.execute(
        f"""
        INSERT INTO {SCHEMA}.employee_audit_log (
            employee_id, action, before_json, after_json
        ) VALUES (%s, %s, %s, %s)
        """,
        (
            employee_id,
            action,
            Jsonb(dict(before)) if before else None,
            Jsonb(dict(after)) if after else None,
        ),
    )


def _sync_legacy_employee_state(conn) -> None:
    _, _, Jsonb = _driver()
    conn.execute(
        f"""
        INSERT INTO {SCHEMA}.app_state (key, json_value)
        VALUES ('employee_directory', %s)
        ON CONFLICT (key) DO UPDATE SET
            json_value = EXCLUDED.json_value,
            updated_at = now()
        """,
        (Jsonb(_employee_rows(conn)),),
    )


def _snapshot_employees(conn, reason: str) -> None:
    _, _, Jsonb = _driver()
    conn.execute(
        f"""
        INSERT INTO {SCHEMA}.employee_snapshots (reason, employees_json)
        VALUES (%s, %s)
        """,
        (reason[:100], Jsonb(_employee_rows(conn))),
    )
    conn.execute(
        f"""
        DELETE FROM {SCHEMA}.employee_snapshots
        WHERE snapshot_id NOT IN (
            SELECT snapshot_id
            FROM {SCHEMA}.employee_snapshots
            ORDER BY snapshot_id DESC
            LIMIT %s
        )
        """,
        (MAX_AUTOMATIC_BACKUPS,),
    )


def _lock_employee_writes(conn) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (EMPLOYEE_WRITE_LOCK,))


def init_storage(target: str) -> None:
    target_key = sha256(str(target).encode("utf-8")).hexdigest()
    if target_key in _INITIALIZED_TARGETS:
        return
    with _INIT_LOCK:
        if target_key in _INITIALIZED_TARGETS:
            return
        _initialize_storage_once(target)
        _INITIALIZED_TARGETS.add(target_key)


def _initialize_storage_once(target: str) -> None:
    with _connect(target) as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.app_state (
                key text PRIMARY KEY,
                json_value jsonb NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.employees (
                employee_id integer PRIMARY KEY CHECK (employee_id > 0),
                short_name text NOT NULL CHECK (length(btrim(short_name)) > 0),
                full_name text NOT NULL CHECK (length(btrim(full_name)) > 0),
                schedule_in time NOT NULL,
                schedule_out time NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT employees_schedule_order CHECK (schedule_out > schedule_in)
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.employee_audit_log (
                audit_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                employee_id integer,
                action text NOT NULL CHECK (action IN ('create', 'update', 'delete', 'import')),
                before_json jsonb,
                after_json jsonb,
                changed_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_employee_audit_changed_at
            ON {SCHEMA}.employee_audit_log (changed_at DESC)
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.employee_snapshots (
                snapshot_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                reason text NOT NULL,
                employees_json jsonb NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )

        # The app uses a server-side PostgreSQL connection. These tables remain
        # outside Supabase's default exposed public schema and have no Data API access.
        conn.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM anon, authenticated")
        conn.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {SCHEMA} FROM anon, authenticated")
        conn.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {SCHEMA} FROM anon, authenticated")
        for table in ("app_state", "employees", "employee_audit_log", "employee_snapshots"):
            conn.execute(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")

        count = conn.execute(f"SELECT count(*) AS count FROM {SCHEMA}.employees").fetchone()["count"]
        if count == 0:
            for record in _default_employee_records():
                conn.execute(
                    f"""
                    INSERT INTO {SCHEMA}.employees (
                        employee_id, short_name, full_name, schedule_in, schedule_out
                    ) VALUES (%s, %s, %s, %s::time, %s::time)
                    ON CONFLICT (employee_id) DO NOTHING
                    """,
                    (
                        record["employee_id"], record["short_name"], record["full_name"],
                        record["schedule_in"], record["schedule_out"],
                    ),
                )
            _sync_legacy_employee_state(conn)


def check_storage_connection(target: str) -> None:
    init_storage(target)
    with _connect(target) as conn:
        result = conn.execute(
            f"SELECT count(*) AS count FROM {SCHEMA}.employees"
        ).fetchone()
        if result is None or result["count"] < 0:
            raise RuntimeError("Supabase employee table health check failed.")


def load_employee_df(target: str) -> pd.DataFrame:
    init_storage(target)
    with _connect(target) as conn:
        rows = _employee_rows(conn)
    return pd.DataFrame(rows, columns=DEFAULT_EMPLOYEE_COLUMNS).fillna("")


def add_employee(target: str, employee: Mapping[str, Any]) -> None:
    record = _normalize_employee(employee)
    init_storage(target)
    try:
        with _connect(target) as conn:
            _lock_employee_writes(conn)
            _snapshot_employees(conn, "before-add-employee")
            conn.execute(
                f"""
                INSERT INTO {SCHEMA}.employees (
                    employee_id, short_name, full_name, schedule_in, schedule_out
                ) VALUES (%s, %s, %s, %s::time, %s::time)
                """,
                (
                    record["employee_id"], record["short_name"], record["full_name"],
                    record["schedule_in"], record["schedule_out"],
                ),
            )
            _write_audit(conn, record["employee_id"], "create", None, record)
            _sync_legacy_employee_state(conn)
    except Exception as exc:
        if getattr(exc, "sqlstate", None) == "23505":
            raise sqlite3.IntegrityError("Employee ID already exists.") from exc
        raise


def add_employees_if_missing(
    target: str,
    employees: list[Mapping[str, Any]],
) -> list[int]:
    normalized_by_id: dict[int, dict[str, Any]] = {}
    for employee in employees:
        record = _normalize_employee(employee)
        normalized_by_id.setdefault(record["employee_id"], record)
    if not normalized_by_id:
        return []

    init_storage(target)
    requested_ids = sorted(normalized_by_id)
    added_ids: list[int] = []
    with _connect(target) as conn:
        _lock_employee_writes(conn)
        existing_rows = conn.execute(
            f"SELECT employee_id FROM {SCHEMA}.employees WHERE employee_id = ANY(%s)",
            (requested_ids,),
        ).fetchall()
        existing_ids = {int(row["employee_id"]) for row in existing_rows}
        if existing_ids == set(requested_ids):
            return []
        _snapshot_employees(conn, "before-auto-add-employees")
        for employee_id in requested_ids:
            record = normalized_by_id[employee_id]
            inserted = conn.execute(
                f"""
                INSERT INTO {SCHEMA}.employees (
                    employee_id, short_name, full_name, schedule_in, schedule_out
                ) VALUES (%s, %s, %s, %s::time, %s::time)
                ON CONFLICT (employee_id) DO NOTHING
                RETURNING employee_id
                """,
                (
                    record["employee_id"], record["short_name"], record["full_name"],
                    record["schedule_in"], record["schedule_out"],
                ),
            ).fetchone()
            if inserted:
                added_ids.append(employee_id)
                _write_audit(conn, employee_id, "create", None, record)
        if added_ids:
            _sync_legacy_employee_state(conn)
    return added_ids


def update_employee(
    target: str,
    original_employee_id: int,
    employee: Mapping[str, Any],
) -> None:
    record = _normalize_employee(employee)
    init_storage(target)
    try:
        with _connect(target) as conn:
            _lock_employee_writes(conn)
            old = conn.execute(
                f"""
                SELECT employee_id, short_name, full_name,
                       to_char(schedule_in, 'HH24:MI') AS schedule_in,
                       to_char(schedule_out, 'HH24:MI') AS schedule_out
                FROM {SCHEMA}.employees
                WHERE employee_id = %s
                FOR UPDATE
                """,
                (int(original_employee_id),),
            ).fetchone()
            if old is None:
                raise LookupError("Employee no longer exists. Reload the directory and try again.")
            _snapshot_employees(conn, "before-update-employee")
            conn.execute(
                f"""
                UPDATE {SCHEMA}.employees
                SET employee_id = %s, short_name = %s, full_name = %s,
                    schedule_in = %s::time, schedule_out = %s::time, updated_at = now()
                WHERE employee_id = %s
                """,
                (
                    record["employee_id"], record["short_name"], record["full_name"],
                    record["schedule_in"], record["schedule_out"], int(original_employee_id),
                ),
            )
            _write_audit(conn, record["employee_id"], "update", dict(old), record)
            _sync_legacy_employee_state(conn)
    except Exception as exc:
        if getattr(exc, "sqlstate", None) == "23505":
            raise sqlite3.IntegrityError("Employee ID already exists.") from exc
        raise


def delete_employee(target: str, employee_id: int) -> None:
    init_storage(target)
    with _connect(target) as conn:
        _lock_employee_writes(conn)
        old = conn.execute(
            f"""
            SELECT employee_id, short_name, full_name,
                   to_char(schedule_in, 'HH24:MI') AS schedule_in,
                   to_char(schedule_out, 'HH24:MI') AS schedule_out
            FROM {SCHEMA}.employees
            WHERE employee_id = %s
            FOR UPDATE
            """,
            (int(employee_id),),
        ).fetchone()
        if old is None:
            raise LookupError("Employee no longer exists. Reload the directory and try again.")
        _snapshot_employees(conn, "before-delete-employee")
        conn.execute(f"DELETE FROM {SCHEMA}.employees WHERE employee_id = %s", (int(employee_id),))
        _write_audit(conn, int(employee_id), "delete", dict(old), None)
        _sync_legacy_employee_state(conn)


def save_employee_df(target: str, df: pd.DataFrame) -> None:
    records: list[dict[str, Any]] = []
    for raw in df.fillna("").to_dict(orient="records"):
        if not any(str(raw.get(col, "")).strip() for col in DEFAULT_EMPLOYEE_COLUMNS):
            continue
        records.append(_normalize_employee(raw))
    init_storage(target)
    with _connect(target) as conn:
        _lock_employee_writes(conn)
        existing = {row["employee_id"]: row for row in _employee_rows(conn)}
        changed = [record for record in records if existing.get(record["employee_id"]) != record]
        if not changed:
            return
        _snapshot_employees(conn, "before-employee-import")
        for record in changed:
            before = existing.get(record["employee_id"])
            conn.execute(
                f"""
                INSERT INTO {SCHEMA}.employees (
                    employee_id, short_name, full_name, schedule_in, schedule_out
                ) VALUES (%s, %s, %s, %s::time, %s::time)
                ON CONFLICT (employee_id) DO UPDATE SET
                    short_name = EXCLUDED.short_name,
                    full_name = EXCLUDED.full_name,
                    schedule_in = EXCLUDED.schedule_in,
                    schedule_out = EXCLUDED.schedule_out,
                    updated_at = now()
                """,
                (
                    record["employee_id"], record["short_name"], record["full_name"],
                    record["schedule_in"], record["schedule_out"],
                ),
            )
            _write_audit(conn, record["employee_id"], "import", before, record)
        _sync_legacy_employee_state(conn)


def list_recent_employee_changes(target: str, limit: int = 10) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    init_storage(target)
    with _connect(target) as conn:
        rows = conn.execute(
            f"""
            SELECT audit_id, employee_id, action, before_json, after_json,
                   to_char(changed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') AS changed_at
            FROM {SCHEMA}.employee_audit_log
            ORDER BY audit_id DESC
            LIMIT %s
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _load_state(target: str, key: str):
    init_storage(target)
    with _connect(target) as conn:
        row = conn.execute(
            f"SELECT json_value FROM {SCHEMA}.app_state WHERE key = %s",
            (key,),
        ).fetchone()
    if not row:
        return None
    value = row["json_value"]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _save_state(target: str, key: str, value) -> None:
    _, _, Jsonb = _driver()
    init_storage(target)
    with _connect(target) as conn:
        conn.execute(
            f"""
            INSERT INTO {SCHEMA}.app_state (key, json_value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET
                json_value = EXCLUDED.json_value,
                updated_at = now()
            """,
            (key, Jsonb(value)),
        )


def load_adjustments_df(target: str) -> pd.DataFrame:
    data = _load_state(target, "adjustments")
    if not data:
        return default_adjustments_df()
    frame = pd.DataFrame(data)
    for column in DEFAULT_ADJUSTMENT_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    return frame[DEFAULT_ADJUSTMENT_COLUMNS].fillna("")


def save_adjustments_df(target: str, df: pd.DataFrame) -> None:
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
    _save_state(target, "adjustments", cleaned[DEFAULT_ADJUSTMENT_COLUMNS].to_dict(orient="records"))


def load_settings(target: str) -> dict:
    data = _load_state(target, "settings")
    return data if isinstance(data, dict) else {}


def save_settings(target: str, data: dict) -> None:
    _save_state(target, "settings", data)
