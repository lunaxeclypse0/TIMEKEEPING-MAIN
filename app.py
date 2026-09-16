from __future__ import annotations

import html
import hashlib
import hmac
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core import (
    accounting_review_rows,
    apply_accounting_review,
    build_daily_records,
    build_output_workbook,
    normalize_punches,
    parse_adjustments_table,
    read_raw_rows,
    save_workbook_to_bytes,
)
from services.storage_backend import (
    add_employee,
    add_employees_if_missing,
    delete_employee,
    init_storage_with_retry,
    is_transient_storage_error,
    list_recent_employee_changes,
    load_adjustments_df,
    load_employee_df,
    merge_employee_directories,
    resolve_database_path,
    find_logo_base64,
    storage_mode,
    update_employee,
)
from services.validators import (
    build_unknown_employee_records,
    detect_unknown_adjustment_employee_ids,
    detect_unknown_employee_ids,
    is_blank_row,
    safe_int,
    validate_adjustment_df,
    validate_employee_df,
)
from ui.banner import render_top_banner
from ui.styles import APP_CSS


st.set_page_config(
    page_title="Timekeeping System",
    page_icon="🕒",
    layout="wide",
    initial_sidebar_state="expanded",
)


def require_access() -> None:
    """Enable a deployment-level password without breaking existing local use."""
    expected_password = os.environ.get("TIMEKEEPING_APP_PASSWORD", "")
    if not expected_password or st.session_state.get("access_granted"):
        return

    st.title("🔒 Timekeeping System")
    with st.form("access_form"):
        supplied_password = st.text_input("Access Password", type="password")
        submitted = st.form_submit_button("Sign In", width="stretch")
    if submitted:
        if hmac.compare_digest(supplied_password, expected_password):
            st.session_state.access_granted = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


require_access()


# ── Paths & Storage ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = resolve_database_path(BASE_DIR)

database_status = st.empty()


def _show_database_retry(failed_attempt: int, max_attempts: int, delay_seconds: float) -> None:
    database_status.warning(
        "The database is waking up. Retrying automatically in "
        f"{delay_seconds:g} seconds ({failed_attempt}/{max_attempts})…"
    )


try:
    init_storage_with_retry(DB_PATH, on_retry=_show_database_retry)
except Exception as exc:
    database_status.empty()
    if is_transient_storage_error(exc):
        st.error("The database is still waking up after several automatic retries.")
        st.caption("No data was changed. Wait a moment, then retry the connection.")
        if st.button("Retry database connection", type="primary"):
            st.rerun()
    else:
        st.error(
            "Database configuration failed. Verify TIMEKEEPING_DATABASE_URL "
            "in the Streamlit deployment secrets."
        )
        st.caption("The app did not modify any database records.")
    st.stop()
else:
    database_status.empty()


# ── Session State Init ────────────────────────────────────────────────────────
if "employee_editor_df"   not in st.session_state:
    st.session_state.employee_editor_df   = load_employee_df(DB_PATH)
else:
    # Refresh on every Streamlit rerun so other accounting sessions become visible.
    st.session_state.employee_editor_df = load_employee_df(DB_PATH)
if "adjustment_editor_df" not in st.session_state:
    st.session_state.adjustment_editor_df = load_adjustments_df(DB_PATH)
if "unknown_ids"          not in st.session_state:
    st.session_state.unknown_ids          = []
if "last_processed_info"  not in st.session_state:
    st.session_state.last_processed_info  = {}
if "editing_employee_id"  not in st.session_state:
    st.session_state.editing_employee_id  = None
if "adding_employee"      not in st.session_state:
    st.session_state.adding_employee      = False
if "pending_delete_employee_id" not in st.session_state:
    st.session_state.pending_delete_employee_id = None
if "employee_flash" not in st.session_state:
    st.session_state.employee_flash = None


# ── Logo ─────────────────────────────────────────────────────────────────────
_logo_result = find_logo_base64(BASE_DIR)
if isinstance(_logo_result, tuple):
    logo_b64, logo_mime = _logo_result
else:
    logo_b64  = _logo_result
    logo_mime = "image/png"

st.markdown(APP_CSS, unsafe_allow_html=True)


# ── Schedule Presets ──────────────────────────────────────────────────────────
# ✅ UPDATED: Added 7AM-4PM and 6AM-6PM (full shift)
SCHEDULE_PRESETS = {
    "6:00 AM – 3:00 PM":  ("06:00", "15:00"),
    "7:00 AM – 4:00 PM":  ("07:00", "16:00"),
    "8:00 AM – 5:00 PM":  ("08:00", "17:00"),
    "9:00 AM – 6:00 PM":  ("09:00", "18:00"),
    "6:00 AM – 6:00 PM":  ("06:00", "18:00"),  # Full shift
}

AVATAR_COLORS = [
    "#2563eb", "#7c3aed", "#db2777", "#dc2626", "#d97706",
    "#059669", "#0891b2", "#4f46e5", "#9333ea", "#c026d3",
]

def get_avatar_color(emp_id: int) -> str:
    return AVATAR_COLORS[int(emp_id) % len(AVATAR_COLORS)]


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ System Control")

    if storage_mode() == "supabase-postgresql":
        st.success("☁️ Permanent Supabase database connected")
    else:
        st.info("💻 Local SQLite mode")

    if os.environ.get("TIMEKEEPING_APP_PASSWORD"):
        if st.button("🔒 Sign Out", width="stretch", key="sign_out_btn"):
            st.session_state.access_granted = False
            st.rerun()

    raw_file    = st.file_uploader("1. Attendance File (.xls / .xlsx)", type=["xls", "xlsx"])
    config_file = st.file_uploader("2. Employee Directory Updates (CSV, optional)", type=["csv"])
    st.caption("CSV rows update matching IDs; saved employees not listed in the CSV are retained.")
    adjust_file = st.file_uploader("3. Accounting Corrections (CSV, optional)", type=["csv"])


# ── Banner ────────────────────────────────────────────────────────────────────
render_top_banner(logo_b64, logo_mime)

tab1, tab2 = st.tabs(["👥 Employee Directory", "🚀 Processing Data"])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Employee Directory
# ═════════════════════════════════════════════════════════════════════════════
with tab1:

    flash = st.session_state.pop("employee_flash", None)
    if flash:
        level, message = flash
        getattr(st, level, st.info)(message)

    # ── Header Row ────────────────────────────────────────────────────────────
    hdr_l, hdr_r = st.columns([4, 1])
    with hdr_l:
        st.markdown('<div class="card-title">👥 Employee Directory</div>', unsafe_allow_html=True)
        st.caption(f"{len(st.session_state.employee_editor_df)} saved employees")
        st.caption("Employee changes are saved directly to the database and verified after every update.")
    with hdr_r:
        if st.button("➕ Add Employee", width="stretch", key="toggle_add_emp_btn"):
            st.session_state.adding_employee     = not st.session_state.adding_employee
            st.session_state.editing_employee_id = None
            st.rerun()

    # ── Add Employee Form ─────────────────────────────────────────────────────
    if st.session_state.adding_employee:
        st.markdown('<div class="emp-form-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="emp-form-header">'
            '<span class="emp-form-title">➕ New Employee</span>'
            '<span class="emp-form-subtitle">Fill in the employee details below</span>'
            '</div>'
            '<div class="emp-form-body">',
            unsafe_allow_html=True,
        )
        with st.form("add_employee_form", clear_on_submit=True):
            ef1, ef2 = st.columns(2)
            ef3, ef4 = st.columns(2)
            existing_ids = [
                safe_int(value)
                for value in st.session_state.employee_editor_df.get("employee_id", []).tolist()
            ]
            next_emp_id = max((value for value in existing_ids if value is not None), default=0) + 1
            new_emp_id     = ef1.number_input("Employee ID *", value=next_emp_id, min_value=1, step=1)
            new_short_name = ef2.text_input("Short Name / Username *", placeholder="e.g. Kazz")
            new_full_name  = ef3.text_input("Full Name *",             placeholder="e.g. Pavia, Kazzela Aira C.")
            sched_label    = ef4.selectbox("Schedule Preset",          list(SCHEDULE_PRESETS.keys()), index=2)
            preset_in, preset_out = SCHEDULE_PRESETS[sched_label]
            ef5, ef6 = st.columns(2)
            new_sched_in   = ef5.text_input("Schedule In *",  value=preset_in)
            new_sched_out  = ef6.text_input("Schedule Out *", value=preset_out)
            fa1, fa2 = st.columns(2)
            submitted = fa1.form_submit_button("✅  Add Employee", width="stretch")
            cancelled = fa2.form_submit_button("✖  Cancel",        width="stretch")

            if submitted:
                new_employee = {
                    "employee_id":  int(new_emp_id),
                    "short_name":   new_short_name.strip(),
                    "full_name":    new_full_name.strip(),
                    "schedule_in":  new_sched_in.strip(),
                    "schedule_out": new_sched_out.strip(),
                }
                new_row = pd.DataFrame([new_employee])
                candidate = pd.concat(
                    [st.session_state.employee_editor_df, new_row],
                    ignore_index=True,
                )
                issues = validate_employee_df(candidate)
                if issues:
                    st.error(issues[0])
                else:
                    try:
                        add_employee(DB_PATH, new_employee)
                    except sqlite3.IntegrityError:
                        st.error(f"Employee ID {int(new_emp_id)} already exists. Use a different ID.")
                    except (sqlite3.Error, OSError, ValueError) as exc:
                        st.error(f"Employee was not saved: {exc}")
                    else:
                        st.session_state.employee_editor_df = load_employee_df(DB_PATH)
                        st.session_state.adding_employee = False
                        st.session_state.employee_flash = (
                            "success",
                            f"Employee {new_short_name.strip()} was saved and verified in the database.",
                        )
                        st.rerun()

            if cancelled:
                st.session_state.adding_employee = False
                st.rerun()

        st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Table Header ──────────────────────────────────────────────────────────
    th1, th2, th3, th4, th5, th6 = st.columns([0.6, 2, 3, 2, 1, 1.5])
    th1.markdown('<div class="th-cell">ID</div>',        unsafe_allow_html=True)
    th2.markdown('<div class="th-cell">USERNAME</div>',  unsafe_allow_html=True)
    th3.markdown('<div class="th-cell">FULL NAME</div>', unsafe_allow_html=True)
    th4.markdown('<div class="th-cell">SCHEDULE</div>',  unsafe_allow_html=True)
    th5.markdown('<div class="th-cell">DATABASE</div>',  unsafe_allow_html=True)
    th6.markdown('<div class="th-cell">ACTIONS</div>',   unsafe_allow_html=True)
    st.markdown('<div class="table-divider"></div>', unsafe_allow_html=True)

    # ── Employee Rows ─────────────────────────────────────────────────────────
    df_display = st.session_state.employee_editor_df.copy().reset_index(drop=True)

    if df_display.empty:
        st.info("No employees found. Add one using the button above.")
    else:
        for idx, row in df_display.iterrows():
            emp_id     = safe_int(row.get("employee_id")) or 0
            short_name = str(row.get("short_name", "") or "")
            full_name  = str(row.get("full_name",  "") or "")
            sched_in   = str(row.get("schedule_in",  "") or "")
            sched_out  = str(row.get("schedule_out", "") or "")
            initial    = (short_name[0] if short_name else str(emp_id)[0]).upper()
            color      = get_avatar_color(emp_id)
            is_editing = (st.session_state.editing_employee_id == emp_id)
            safe_short_name = html.escape(short_name)
            safe_full_name = html.escape(full_name)

            c1, c2, c3, c4, c5, c6 = st.columns([0.6, 2, 3, 2, 1, 1.5])

            with c1:
                st.markdown(
                    f'<div class="avatar-circle" style="background:{color}">{initial}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div class="emp-name-main">{safe_short_name}</div>'
                    f'<div class="emp-id-sub">ID: {emp_id}</div>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f'<div class="emp-full-name">{safe_full_name}</div>',
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    f'<div class="sched-badge">🕐 {sched_in} – {sched_out}</div>',
                    unsafe_allow_html=True,
                )
            with c5:
                st.markdown(
                    '<div class="status-active-badge">● Saved</div>',
                    unsafe_allow_html=True,
                )
            with c6:
                btn_edit, btn_del = st.columns(2)
                with btn_edit:
                    edit_label = "✖️" if is_editing else "✏️"
                    if st.button(edit_label, key=f"edit_emp_{emp_id}_{idx}", help="Edit employee"):
                        if is_editing:
                            st.session_state.editing_employee_id = None
                        else:
                            st.session_state.editing_employee_id = emp_id
                            st.session_state.adding_employee     = False
                        st.rerun()
                with btn_del:
                    if st.button("🗑️", key=f"del_emp_{emp_id}_{idx}", help="Delete employee"):
                        st.session_state.pending_delete_employee_id = emp_id
                        st.rerun()

            if st.session_state.pending_delete_employee_id == emp_id:
                st.warning(f"Delete {short_name} (Employee ID {emp_id})? A database backup will be created first.")
                confirm_col, cancel_col = st.columns(2)
                if confirm_col.button("Confirm Delete", key=f"confirm_delete_{emp_id}", width="stretch"):
                    try:
                        delete_employee(DB_PATH, emp_id)
                    except (sqlite3.Error, LookupError, OSError) as exc:
                        st.error(f"Employee was not deleted: {exc}")
                    else:
                        st.session_state.employee_editor_df = load_employee_df(DB_PATH)
                        st.session_state.editing_employee_id = None
                        st.session_state.pending_delete_employee_id = None
                        st.session_state.employee_flash = ("success", f"Deleted {short_name} safely.")
                        st.rerun()
                if cancel_col.button("Keep Employee", key=f"cancel_delete_{emp_id}", width="stretch"):
                    st.session_state.pending_delete_employee_id = None
                    st.rerun()

            # ── Inline Edit Form ──────────────────────────────────────────────
            if is_editing:
                st.markdown('<div class="emp-form-card">', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="emp-form-header">'
                    f'<span class="emp-form-title">✏️ Edit Employee</span>'
                    f'<span class="emp-form-subtitle">{safe_full_name or safe_short_name}</span>'
                    f'</div>'
                    f'<div class="emp-form-body">',
                    unsafe_allow_html=True,
                )
                with st.form(f"edit_form_{emp_id}_{idx}", clear_on_submit=False):
                    fe1, fe2 = st.columns(2)
                    fe3, fe4 = st.columns(2)
                    upd_id    = fe1.number_input("Employee ID",  value=int(emp_id), min_value=1, step=1)
                    upd_short = fe2.text_input("Short Name",     value=short_name)
                    upd_full  = fe3.text_input("Full Name",      value=full_name)

                    current_pair   = (sched_in, sched_out)
                    preset_options = list(SCHEDULE_PRESETS.keys()) + ["— Custom —"]
                    matched        = next(
                        (k for k, v in SCHEDULE_PRESETS.items() if v == current_pair),
                        "— Custom —",
                    )
                    sel_preset = fe4.selectbox(
                        "Schedule Preset", preset_options,
                        index=preset_options.index(matched),
                    )

                    if sel_preset != "— Custom —":
                        default_in, default_out = SCHEDULE_PRESETS[sel_preset]
                    else:
                        default_in, default_out = sched_in, sched_out

                    fe5, fe6  = st.columns(2)
                    upd_in    = fe5.text_input("Schedule In",  value=default_in)
                    upd_out   = fe6.text_input("Schedule Out", value=default_out)
                    fs1, fs2  = st.columns(2)
                    save_ok   = fs1.form_submit_button("💾  Save Changes", width="stretch")
                    cancel_ok = fs2.form_submit_button("✖  Cancel",        width="stretch")

                    if save_ok:
                        updated_df = st.session_state.employee_editor_df.copy()
                        match_rows = updated_df.index[
                            updated_df["employee_id"].apply(safe_int) == emp_id
                        ].tolist()
                        if match_rows:
                            r = match_rows[0]
                            updated_df.at[r, "employee_id"]  = int(upd_id)
                            updated_df.at[r, "short_name"]   = upd_short.strip()
                            updated_df.at[r, "full_name"]    = upd_full.strip()
                            updated_df.at[r, "schedule_in"]  = upd_in.strip()
                            updated_df.at[r, "schedule_out"] = upd_out.strip()
                        issues = validate_employee_df(updated_df)
                        if issues:
                            st.error(issues[0])
                        else:
                            updated_employee = {
                                "employee_id": int(upd_id),
                                "short_name": upd_short.strip(),
                                "full_name": upd_full.strip(),
                                "schedule_in": upd_in.strip(),
                                "schedule_out": upd_out.strip(),
                            }
                            try:
                                update_employee(DB_PATH, emp_id, updated_employee)
                            except sqlite3.IntegrityError:
                                st.error(f"Employee ID {int(upd_id)} already exists.")
                            except (sqlite3.Error, LookupError, OSError, ValueError) as exc:
                                st.error(f"Changes were not saved: {exc}")
                            else:
                                st.session_state.employee_editor_df = load_employee_df(DB_PATH)
                                st.session_state.editing_employee_id = None
                                st.session_state.employee_flash = (
                                    "success",
                                    f"Changes for {upd_short.strip()} were saved and verified.",
                                )
                                st.rerun()

                    if cancel_ok:
                        st.session_state.editing_employee_id = None
                        st.rerun()

                st.markdown('</div></div>', unsafe_allow_html=True)

            st.markdown('<div class="table-row-divider"></div>', unsafe_allow_html=True)

    # ── Footer Buttons ────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    foot1, foot2 = st.columns(2)
    with foot1:
        st.download_button(
            "📤 Export CSV",
            data=st.session_state.employee_editor_df.to_csv(index=False).encode(),
            file_name="employees.csv",
            width="stretch",
            key="employee_export_csv_btn",
        )
    with foot2:
        if st.button("🔄 Reload from Database", width="stretch", key="employee_reload_btn"):
            st.session_state.employee_editor_df  = load_employee_df(DB_PATH)
            st.session_state.editing_employee_id = None
            st.session_state.employee_flash = ("success", "Employee directory reloaded from the database.")
            st.rerun()

    recent_changes = list_recent_employee_changes(DB_PATH, limit=10)
    with st.expander("🛡️ Recent Employee Changes", expanded=False):
        if not recent_changes:
            st.caption("No employee changes recorded yet.")
        else:
            change_df = pd.DataFrame([
                {
                    "When (UTC)": item["changed_at"].replace("T", " "),
                    "Employee ID": item["employee_id"],
                    "Action": item["action"].title(),
                }
                for item in recent_changes
            ])
            st.dataframe(change_df, width="stretch", hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Processing Data
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    if raw_file is None:
        st.info("Upload the raw biometric Excel file from the sidebar to begin processing.")
    else:
        try:
            raw_rows = read_raw_rows(raw_file)
            punches  = normalize_punches(raw_rows)
            if not raw_rows:
                raise ValueError("The attendance file has no data rows.")
            if not punches:
                raise ValueError(
                    "No valid punch records were found. Check the Employee ID and Date/Time columns."
                )
            skipped_rows = len(raw_rows) - len(punches)
            if skipped_rows > 0:
                st.warning(
                    f"{skipped_rows} uploaded row(s) were not used because the Employee ID "
                    "or Date/Time was missing/invalid, or the punch was an exact duplicate."
                )

            # Build employee config
            csv_df = None
            if config_file is not None:
                csv_df = pd.read_csv(config_file)
                cfg_df = merge_employee_directories(
                    st.session_state.employee_editor_df.copy(), csv_df,
                )
            else:
                cfg_df = st.session_state.employee_editor_df.copy()

            employee_config_issues = validate_employee_df(cfg_df)
            if employee_config_issues:
                st.error(employee_config_issues[0])
                st.stop()

            # Any valid attendance ID missing from the saved database is added
            # automatically. Existing rows are never overwritten by this path.
            saved_before_auto_add = st.session_state.employee_editor_df.copy()
            unknown_saved_ids = detect_unknown_employee_ids(punches, saved_before_auto_add)
            auto_added_ids: list[int] = []
            default_schedule_ids: list[int] = []
            if unknown_saved_ids:
                suggestions = build_unknown_employee_records(raw_rows, unknown_saved_ids, cfg_df)
                configured_csv_ids = {
                    safe_int(value)
                    for value in (
                        csv_df.get("employee_id", pd.Series(dtype=object)).tolist()
                        if csv_df is not None else []
                    )
                    if safe_int(value) is not None
                }
                auto_added_ids = add_employees_if_missing(DB_PATH, suggestions)
                default_schedule_ids = sorted(set(auto_added_ids) - configured_csv_ids)
                st.session_state.employee_editor_df = load_employee_df(DB_PATH)
                cfg_df = (
                    merge_employee_directories(st.session_state.employee_editor_df.copy(), csv_df)
                    if csv_df is not None
                    else st.session_state.employee_editor_df.copy()
                )
                employee_config_issues = validate_employee_df(cfg_df)
                if employee_config_issues:
                    st.error(employee_config_issues[0])
                    st.stop()

            unknown_ids = detect_unknown_employee_ids(punches, cfg_df)
            st.session_state.unknown_ids = unknown_ids
            if unknown_ids:
                raise RuntimeError(
                    "These valid attendance IDs could not be saved automatically: "
                    + ", ".join(map(str, unknown_ids))
                )
            if auto_added_ids:
                st.success(
                    "Automatically saved new attendance employee ID(s): "
                    + ", ".join(map(str, auto_added_ids))
                    + ". They are already included in this processing run."
                )
            if default_schedule_ids:
                st.warning(
                    "New ID(s) " + ", ".join(map(str, default_schedule_ids))
                    + " used the safe default 08:00–17:00 schedule. The raw attendance name was saved "
                    "when available; review the exact name and schedule in Employee Directory."
                )

            employee_config: dict = {}
            for _, r in cfg_df.iterrows():
                if is_blank_row(r, ["employee_id", "short_name", "full_name", "schedule_in", "schedule_out"]):
                    continue
                eid = safe_int(r.get("employee_id"))
                if eid is None:
                    continue
                employee_config[eid] = {
                    "short_name":   str(r.get("short_name",  "") or "").strip(),
                    "full_name":    str(r.get("full_name",   "") or "").strip(),
                    "schedule_in":  str(r.get("schedule_in",  "08:00") or "08:00").strip(),
                    "schedule_out": str(r.get("schedule_out", "17:00") or "17:00").strip(),
                }

            # Build adjustments
            if adjust_file is not None:
                adj_source = pd.read_csv(adjust_file).fillna("")
            else:
                adj_source = st.session_state.adjustment_editor_df.fillna("")

            adjustment_issues = validate_adjustment_df(adj_source)
            if adjustment_issues:
                st.error(adjustment_issues[0])
                st.stop()
            unknown_adjustment_ids = detect_unknown_adjustment_employee_ids(adj_source, cfg_df)
            if unknown_adjustment_ids:
                st.error(
                    "Adjustment file contains employee IDs not found in the Employee Directory: "
                    + ", ".join(map(str, unknown_adjustment_ids))
                )
                st.stop()
            adjustments = parse_adjustments_table(adj_source.to_dict(orient="records"))

            # Process records
            records, employee_meta, _ = build_daily_records(
                punches, employee_config, adjustments,
            )

            st.session_state.last_processed_info = {
                "raw_logs":      len(punches),
                "daily_records": len(records),
                "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # ✅ Simple clean success message lang — walang info boxes or metric cards
            st.markdown(
                f'<div class="success-box">✅ Processing complete. '
                f'<b>{len(records)}</b> daily records generated from '
                f'<b>{len(punches)}</b> raw punch logs. '
                f'Ready to export.</div>',
                unsafe_allow_html=True,
            )

            st.markdown("<br>", unsafe_allow_html=True)

            sub_tab1, sub_tab2, sub_tab3 = st.tabs([
                "✍️ Accounting Review",
                "🆕 Unknown Employees",
                "💾 Finalize & Export",
            ])

            preview_df = pd.DataFrame(accounting_review_rows(records))
            upload_fingerprint = hashlib.sha256(raw_file.getvalue()).hexdigest()[:12]

            with sub_tab1:
                st.caption(
                    "Review and correct the same fields used by Accounting. "
                    "ID and Name stay locked; all timekeeping results remain editable before export."
                )
                edited_df = st.data_editor(
                    preview_df,
                    width="stretch",
                    height=560,
                    hide_index=True,
                    num_rows="fixed",
                    disabled=["ID", "Name"],
                    column_config={
                        "ID": st.column_config.NumberColumn("ID", format="%d"),
                        "Date/Time (IN)": st.column_config.TextColumn("Date/Time (IN)"),
                        "Date/Time (OUT)": st.column_config.TextColumn("Date/Time (OUT)"),
                        "Late": st.column_config.NumberColumn("Late", min_value=0, step=1, format="%d"),
                        "Undertime": st.column_config.NumberColumn("Undertime", min_value=0, step=1, format="%d"),
                        "Overtime": st.column_config.NumberColumn("Overtime", min_value=0, step=1, format="%d"),
                        "Half Day": st.column_config.NumberColumn("Half Day", min_value=0.0, max_value=1.0, step=0.5),
                        "Remarks": st.column_config.TextColumn("Remarks"),
                    },
                    key=f"accounting_review_{upload_fingerprint}",
                )

            review_error = None
            reviewed_records = records
            try:
                reviewed_records = apply_accounting_review(
                    records,
                    edited_df.fillna("").to_dict(orient="records"),
                )
            except ValueError as exc:
                review_error = str(exc)

            with sub_tab2:
                if auto_added_ids:
                    added_df = st.session_state.employee_editor_df[
                        st.session_state.employee_editor_df["employee_id"].apply(safe_int).isin(auto_added_ids)
                    ][["employee_id", "short_name", "full_name", "schedule_in", "schedule_out"]]
                    st.success("✅ New attendance employees were automatically saved.")
                    st.dataframe(added_df, width="stretch", hide_index=True)
                    st.caption("Review the exact employee name and schedule in Employee Directory when needed.")
                elif st.session_state.unknown_ids:
                    unknown_df = pd.DataFrame({
                        "Unknown Employee ID": st.session_state.unknown_ids,
                        "Action Needed": ["Set schedule in Employee Directory"] * len(st.session_state.unknown_ids),
                    })
                    st.dataframe(unknown_df, width="stretch", height=300, hide_index=True)
                else:
                    st.success("✅ No unknown employees found.")

            with sub_tab3:
                if review_error:
                    st.error(review_error)
                    st.info("Correct the highlighted Accounting Review value before exporting.")
                else:
                    st.success("Detailed workbook is ready. No Summary sheet will be included.")
                    wb = build_output_workbook(reviewed_records, employee_meta)
                    st.download_button(
                        label="📥 Download Excel Report",
                        data=save_workbook_to_bytes(wb),
                        file_name="Attendance_Report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                        key="download_professional_excel_report_btn",
                    )

        except Exception as e:
            st.error(f"System Error: {str(e)}")


st.markdown('<div class="footer">POWERED BY GOCLINIC</div>', unsafe_allow_html=True)
