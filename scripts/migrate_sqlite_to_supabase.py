from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services import postgres_storage
from services.storage import (
    load_adjustments_df,
    load_employee_df,
    load_settings,
)


def load_sqlite_source_without_mutation(source: Path):
    with tempfile.TemporaryDirectory() as temp_dir:
        working_copy = Path(temp_dir) / source.name
        shutil.copy2(source, working_copy)
        return (
            load_employee_df(working_copy),
            load_adjustments_df(working_copy),
            load_settings(working_copy),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy the existing local timekeeping data into Supabase PostgreSQL."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "data" / "goclinic_timekeeping.db",
        help="Path to the existing SQLite database.",
    )
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"SQLite source was not found: {source}")

    target = os.environ.get("TIMEKEEPING_DATABASE_URL", "").strip()
    if not target:
        raise SystemExit("Set TIMEKEEPING_DATABASE_URL before running the migration.")

    # The SQLite initializer may add newer compatibility tables. Work from a
    # disposable copy so the Accounting source database remains byte-for-byte untouched.
    employees, adjustments, settings = load_sqlite_source_without_mutation(source)

    postgres_storage.init_storage(target)
    postgres_storage.save_employee_df(target, employees)
    postgres_storage.save_adjustments_df(target, adjustments)
    postgres_storage.save_settings(target, settings)

    cloud_employees = postgres_storage.load_employee_df(target)
    local_records = employees.sort_values("employee_id").reset_index(drop=True).to_dict(orient="records")
    cloud_records = cloud_employees[
        cloud_employees["employee_id"].isin(employees["employee_id"])
    ].sort_values("employee_id").reset_index(drop=True).to_dict(orient="records")
    if cloud_records != local_records:
        raise SystemExit("Migration verification failed: employee rows differ after upload.")

    cloud_adjustments = postgres_storage.load_adjustments_df(target)
    adjustment_columns = ["date", "employee_id", "type", "value", "label", "remarks"]
    local_adjustment_records = adjustments[adjustment_columns].fillna("").astype(str).to_dict(orient="records")
    cloud_adjustment_records = cloud_adjustments[adjustment_columns].fillna("").astype(str).to_dict(orient="records")
    if cloud_adjustment_records != local_adjustment_records:
        raise SystemExit("Migration verification failed: correction rows differ after upload.")
    if postgres_storage.load_settings(target) != settings:
        raise SystemExit("Migration verification failed: settings differ after upload.")

    print(
        f"Migration verified: {len(local_records)} employee rows and "
        f"{len(local_adjustment_records)} correction rows copied to Supabase."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
