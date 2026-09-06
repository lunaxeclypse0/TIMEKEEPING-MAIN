# Final Fixes — 2026-09-06

## Accounting-reference reconciliation

- Reconciled the computation and export layout against the supplied 116-row Accounting workbook.
- Restored the approved nearest-standard-shift behavior instead of forcing one saved shift onto every date.
- Added the correct tie rule for employees configured on 06:00–18:00.
- Late uses completed minutes; Undertime rounds up and appears only for 1–60 minutes; Overtime uses completed whole hours.
- Incomplete punches no longer generate false Undertime or Overtime.
- Adjustment-only holiday/leave dates no longer create detail rows.
- Exact headings and per-employee total formulas match the Accounting detail sheet.
- Restored Excel's light per-cell gridlines to match the Accounting reference view.
- Removed the Summary worksheet and all Summary UI.

## Accounting Review

- Added an editable review grid before export with the exact fields used by Accounting.
- Employee ID and Name remain locked.
- Date/Time In, Date/Time Out, Late, Undertime, Overtime, Half Day, and Remarks can be corrected for approved roster changes, official business, or manual exceptions.
- Review values are validated before the download button is enabled.
- Half Day automatically clears Late, Undertime, and Overtime on the same row.

## Employee persistence

- Migrated employee storage from a single JSON blob to a row-based SQLite table.
- Added transactional add, update, import, and delete operations.
- Added pre-change backups, an employee audit log, unique-ID enforcement, and concurrent-write protection.
- Employee CSV imports merge by ID and retain saved employees absent from the CSV.
- Hosted deployments can point `TIMEKEEPING_DB_PATH` to persistent storage.

## Permanent Supabase deployment

- Added automatic storage selection: Supabase PostgreSQL when `TIMEKEEPING_DATABASE_URL` is configured, with SQLite retained for local/offline use.
- Added a private `timekeeping` schema for employees, audit history, application state, and rolling employee snapshots.
- Revoked `anon` and `authenticated` access and enabled RLS on every cloud table; the connection string remains a server-only Streamlit secret.
- Added transaction-level advisory locking for employee writes, insert-only automatic discovery, and atomic update/delete/import behavior.
- Added up to 20 pre-change employee snapshots for recovery on the free database plan.
- Added a verified SQLite-to-Supabase data migration script and complete Streamlit Community Cloud deployment guide.

## Automatic attendance employee discovery

- A valid Employee ID found in an uploaded attendance file is automatically inserted into the row-based employee database during the same processing run.
- The raw attendance name is normalized and used for the new employee when no complete directory row is supplied.
- A complete matching row in the optional Employee Directory CSV takes priority for the new employee's name and schedule.
- Missing schedule data uses a visible, safe `08:00–17:00` default and the processing screen asks Accounting to review it.
- Existing IDs are insert-only in this path: an attendance upload cannot overwrite an existing employee's name, ID, or schedule.
- Concurrent uploads for the same new ID result in one durable employee row and one audit event.

## Input and operational hardening

- Rejects fractional/non-positive IDs and invalid/overnight schedules.
- Handles Excel dates, 12-hour and 24-hour timestamps, and exact duplicate punches safely.
- Rejects empty or invalid uploads with clear user-facing messages.
- Optional access protection is available through `TIMEKEEPING_APP_PASSWORD`.
