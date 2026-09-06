# Timekeeping Detail Builder

This system converts a raw biometric `.xls` or `.xlsx` export into Accounting's approved detail workbook.

The downloaded workbook contains exactly one worksheet: **TIME IN & TIME OUT**. Its columns are:

1. Employee ID
2. Name
3. Date/Time (IN)
4. Date/Time (OUT)
5. Late
6. Undertime
7. Overtime
8. Half Day
9. Remarks

No Summary worksheet is generated.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Without cloud secrets the app uses local SQLite. When the root-level secret `TIMEKEEPING_DATABASE_URL` contains a Supabase PostgreSQL URI, the app automatically uses permanent cloud storage instead. See `SUPABASE_SETUP.md` for the production deployment procedure.

## Normal workflow

1. Upload the raw biometric attendance file.
2. Any valid Employee ID that is not yet saved is automatically added to the database during that same upload. The name beside the ID in the raw file is used when available. If an optional Employee Directory CSV contains the ID, its complete name and schedule take priority. A new ID with no supplied schedule receives the safe `08:00–17:00` default and is clearly flagged for review.
3. Review the computed rows in **Accounting Review**. ID and Name are locked; the time fields, Late, Undertime, Overtime, Half Day, and Remarks may be corrected before export.
4. Download `Attendance_Report.xlsx` from **Finalize & Export**.

Existing saved employees are never overwritten by automatic attendance discovery. The insert is transactional, concurrency-safe, durable across restart, and included immediately in the current processing run.

The review step is intentional: biometric punches alone cannot identify a temporary roster change, official business, or an approved manual exception. Accounting can enter those authorized corrections without editing the generated workbook afterward.

## Approved calculation behavior

- The earliest punch per employee/date is Time In; the latest punch is Time Out.
- Exact duplicate punches are removed.
- The daily shift is selected from 06:00–15:00, 07:00–16:00, 08:00–17:00, 09:00–18:00, and 06:00–18:00 using the standard shift start nearest to Time In. If two shifts share the same start, the employee's saved schedule wins.
- Late is the completed number of minutes after shift start.
- Undertime is rounded up to the next minute and is shown only when it is 1–60 minutes. Longer gaps are left for Accounting review as a roster/half-day exception.
- Overtime is the number of completed whole hours after shift end.
- Arrival at least 120 minutes after shift start is marked as `0.5` Half Day and clears Late, Undertime, and Overtime.
- A one-punch row remains visible. It is marked `no time in` or `no time out`, and no false Undertime/Overtime is calculated.
- Half Day clears Late, Undertime, and Overtime for the same row.
- Holidays, leave, or adjustments without any biometric punch do not create detail rows.
- Each employee block ends with formulas for worked days, Late, Undertime, Overtime, and Half Day totals, matching the approved Accounting layout.
- Excel's light gridlines remain visible across every cell, with stronger separator lines for the header and employee totals.

## Optional files

### Employee directory CSV

Required columns:

- `employee_id`
- `short_name`
- `full_name`
- `schedule_in`
- `schedule_out`

Uploaded rows are used as authoritative processing-time overrides for matching IDs. Existing saved employees omitted from the CSV are retained. If a CSV row supplies a previously unknown attendance ID, that complete row is automatically persisted as the employee record.

### Accounting corrections CSV

Supported columns:

- `date`
- `employee_id`
- `type`
- `value`
- `label`
- `remarks`

The most useful row-level types are `half_day`, `force_no_time_in`, `force_no_time_out`, and `manual_adjustment`. A correction only affects an existing biometric detail date. The on-screen Accounting Review remains available for final authorized edits.

## Employee data safety

- Online deployments use a private Supabase PostgreSQL schema when `TIMEKEEPING_DATABASE_URL` is configured; local use retains the row-based SQLite backend.
- Add, edit, import, and delete operations use transactions and are verified after writing.
- SQLite creates file backups before employee changes. Supabase keeps the latest 20 pre-change employee snapshots in the database.
- Changes are recorded in **Recent Employee Changes**.
- Concurrent accounting sessions cannot silently overwrite newly added employees.
- Supabase tables are outside the exposed `public` schema, have RLS enabled, and revoke access from `anon` and `authenticated`; only the server-side secret PostgreSQL connection is used.

For Streamlit Community Cloud, configure `TIMEKEEPING_DATABASE_URL` and `TIMEKEEPING_APP_PASSWORD` as root-level Streamlit secrets. Never put database credentials or the app password in source code. A traditional hosted server with a persistent disk may continue using `TIMEKEEPING_DB_PATH` for SQLite.
