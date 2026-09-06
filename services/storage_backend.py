from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from services import storage as sqlite_storage


def _cloud_configured() -> bool:
    return bool(os.environ.get("TIMEKEEPING_DATABASE_URL", "").strip())


def _backend():
    if _cloud_configured():
        from services import postgres_storage

        return postgres_storage
    return sqlite_storage


def storage_mode() -> str:
    return "supabase-postgresql" if _cloud_configured() else "sqlite-local"


def resolve_database_path(base_dir: Path):
    return _backend().resolve_database_path(base_dir)


def init_storage(target) -> None:
    _backend().init_storage(target)


def load_employee_df(target):
    return _backend().load_employee_df(target)


def add_employee(target, employee) -> None:
    _backend().add_employee(target, employee)


def add_employees_if_missing(target, employees):
    return _backend().add_employees_if_missing(target, employees)


def update_employee(target, original_employee_id, employee) -> None:
    _backend().update_employee(target, original_employee_id, employee)


def delete_employee(target, employee_id) -> None:
    _backend().delete_employee(target, employee_id)


def save_employee_df(target, df) -> None:
    _backend().save_employee_df(target, df)


def list_recent_employee_changes(target, limit: int = 10):
    return _backend().list_recent_employee_changes(target, limit)


def load_adjustments_df(target):
    return _backend().load_adjustments_df(target)


def save_adjustments_df(target, df) -> None:
    _backend().save_adjustments_df(target, df)


def load_settings(target) -> dict[str, Any]:
    return _backend().load_settings(target)


def save_settings(target, data: dict[str, Any]) -> None:
    _backend().save_settings(target, data)


def check_storage_connection(target) -> None:
    checker = getattr(_backend(), "check_storage_connection", None)
    if checker is not None:
        checker(target)
        return
    sqlite_storage.load_employee_df(target)


# These helpers do not access the database and are shared by both backends.
merge_employee_directories = sqlite_storage.merge_employee_directories
find_logo_base64 = sqlite_storage.find_logo_base64
default_employee_df = sqlite_storage.default_employee_df
default_adjustments_df = sqlite_storage.default_adjustments_df
