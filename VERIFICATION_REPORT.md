# Verification Report — 2026-09-06

## Accounting workbook reference

- Reference inspected: `January 26, 2026 - February 10, 2026(20260906-094608).xlsx`
- Detail worksheet reviewed: 116 attendance rows, 13 employees
- Reference fields checked: Date/Time In, Date/Time Out, Late, Undertime, Overtime, Half Day, Remarks
- Full Accounting Review reconciliation: **116/116 rows passed**
- Generated workbook worksheet count: **1**
- Generated worksheet name: **TIME IN & TIME OUT**
- Formula/error scan: **0 spreadsheet errors found**
- Rendered layout inspection: **PASS**
- Excel per-cell gridlines visible: **PASS**
- Summary worksheet excluded: **PASS**

## Automated regression suite

- Tests run: **42**
- Passed: **42**
- Failed: **0**

Coverage includes:

- Approved sample-derived shift selection and tie behavior
- Late, rounded-up short Undertime, completed-hour Overtime, and Half Day
- Missing Time In/Out handling without false Undertime/Overtime
- Adjustment-only dates excluded from detail rows
- Exact export headings and single-sheet workbook structure
- Accounting Review validation and special-roster correction
- Employee add/update/delete durability and audit history
- SQLite migration, backups, duplicate IDs, stale/concurrent writes, and CSV merge safety
- Invalid IDs, names, clock values, correction values, and unsupported overnight schedules
- Automatic attendance-ID discovery using raw names and optional directory priority
- Insert-only auto-add behavior, invalid-batch atomicity, restart durability, and same-ID concurrency safety
- Full raw-upload → automatic employee insert → same-run daily-record processing → single-sheet export pipeline

## Supabase conversion verification

- Cloud/local storage dispatcher: **IMPLEMENTED**
- Private `timekeeping` schema with revoked Data API roles and RLS: **IMPLEMENTED**
- Transactional employee writes and PostgreSQL advisory locking: **IMPLEMENTED**
- Rolling pre-change employee snapshots: **IMPLEMENTED**
- SQLite-to-Supabase migration with post-copy row verification: **IMPLEMENTED**
- Pinned PostgreSQL driver (`psycopg[binary]==3.3.5`): **IMPLEMENTED**

Live Supabase connection and schema execution remain pending until a dedicated target project is selected. The release does not claim a live cloud test without a chosen project and connection secret.

## Interactive UI smoke test

The release container did not include Streamlit, and dependency installation was blocked by its runtime approval limit. Therefore an interactive AppTest run is **not claimed** for this release. The source-level processing path was inspected for the complete automatic-discovery flow: raw upload parsing, unknown-ID detection against the saved database, transactional insert, database reload, revalidation, current-run processing, and export preparation. The Python modules compile cleanly and all 42 deterministic tests pass.

The prior UI baseline remains covered by the existing source structure: Employee Directory, Add/Edit/Delete, Processing Data, Accounting Review, Finalize & Export, and the removed Summary UI are all retained in this build.

## Data-preservation release check

The packaged database is restored from the original uploaded ZIP immediately before packaging. Its SHA-256 is compared with the original archive to ensure the release does not ship test or migration writes.
