# Permanent Online Deployment — Supabase + Streamlit

This build automatically selects its storage backend:

- `TIMEKEEPING_DATABASE_URL` present: permanent Supabase PostgreSQL storage.
- Secret absent: local SQLite storage for offline/local use.

The Excel calculation and export logic is identical in both modes.

## 1. Create a dedicated Supabase project

Use a project dedicated to this timekeeping system, preferably in Singapore (`ap-southeast-1`) for Philippine users. Do not reuse an unrelated production project.

## 2. Create the private database schema

Open **Supabase Dashboard → SQL Editor**, paste the complete contents of `supabase/schema.sql`, and run it once.

The tables live in the private `timekeeping` schema. `anon` and `authenticated` have no schema, table, or sequence privileges. The Streamlit server connects through a secret PostgreSQL connection string; no database credential is shipped to the browser.

## 3. Copy the pooled PostgreSQL connection string

Open **Connect** in Supabase and copy the **Transaction pooler** URI. Use the URI supplied by the dashboard and ensure SSL is required. It normally follows this shape:

```text
postgresql://postgres.PROJECT_REF:PASSWORD@POOLER_HOST:6543/postgres?sslmode=require
```

Do not commit this value to GitHub or place it in `.streamlit/config.toml`.

## 4. Upload the code to a private GitHub repository

Extract the ZIP. Upload the contents inside `TIMEKEEPING-main/` to the root of a private repository. The repository root must contain `app.py`, `requirements.txt`, `core.py`, `services/`, `ui/`, and `supabase/`.

Do not commit `.streamlit/secrets.toml`, `.env`, database WAL files, or `data/backups/`; `.gitignore` already excludes them.

### Optional: migrate the current local database

If Accounting has already added or edited employees in the local system, migrate that exact SQLite database before going live. From the extracted project directory, set `TIMEKEEPING_DATABASE_URL` in the terminal environment and run:

```bash
python scripts/migrate_sqlite_to_supabase.py --source data/goclinic_timekeeping.db
```

The migration is non-destructive: it copies employees, corrections, and settings, then reloads the cloud rows and verifies them against the source. Keep an untouched copy of the original SQLite database until the online acceptance check passes.

## 5. Deploy on Streamlit Community Cloud

1. Open `https://share.streamlit.io/`.
2. Select **Create app**.
3. Choose the private repository, `main` branch, and `app.py`.
4. Open **Advanced settings → Secrets** and add root-level secrets:

```toml
TIMEKEEPING_DATABASE_URL = "postgresql://postgres.PROJECT_REF:PASSWORD@POOLER_HOST:6543/postgres?sslmode=require"
TIMEKEEPING_APP_PASSWORD = "REPLACE_WITH_A_LONG_UNIQUE_PASSWORD"
```

5. Deploy. The app should display **Permanent Supabase database connected** in the sidebar.

Root-level Streamlit secrets are exposed to the Python server as environment variables. They are not committed to GitHub and are not sent to users' browsers.

## 6. Required acceptance check

Before giving the link to Accounting:

1. Sign in with the deployment password.
2. Add a temporary employee ID in Employee Directory.
3. Reload the browser and reboot the Streamlit app.
4. Confirm the employee still exists.
5. Upload an attendance file containing a second new ID.
6. Confirm the ID is automatically saved and included in that same processing run.
7. Download the workbook and confirm there is only `TIME IN & TIME OUT`, visible Excel gridlines, and no Summary sheet.
8. Delete the temporary test employees.

## Operational notes

- Employee writes are serialized with a PostgreSQL advisory transaction lock.
- Existing employee rows cannot be overwritten by automatic attendance discovery.
- Employee changes have an audit record.
- The database stores up to 20 rolling pre-change employee snapshots.
- The free Supabase plan can pause projects with low activity and does not provide downloadable automatic backups. Daily use usually provides activity, but Accounting should still export the employee CSV periodically.
