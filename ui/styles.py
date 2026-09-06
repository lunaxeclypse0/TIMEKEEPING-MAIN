APP_CSS = """
<style>

/* ═══════════════════════════════════════════════
   DESIGN TOKENS
═══════════════════════════════════════════════ */
:root {
    --bg-app: #f1f5f9;
    --bg-card: #ffffff;
    --bg-soft: #f8fafc;
    --bg-soft-2: #eff6ff;

    --text-main: #1e293b;
    --text-soft: #475569;
    --text-muted: #64748b;
    --text-faint: #94a3b8;

    --border: #e2e8f0;
    --border-soft: #dde3ed;

    --primary: #2563eb;
    --primary-hover: #1d4ed8;
    --primary-soft: rgba(37, 99, 235, 0.10);
    --primary-soft-2: rgba(37, 99, 235, 0.12);

    --success-bg: #dcfce7;
    --success-text: #15803d;
    --success-border: #bbf7d0;

    --warn-bg: #fef9c3;
    --warn-text: #713f12;
    --warn-border: #eab308;

    --info-bg: #eff6ff;
    --info-text: #1e40af;
    --info-border: #3b82f6;

    --radius-sm: 8px;
    --radius-md: 10px;
    --radius-lg: 12px;
    --radius-xl: 14px;
    --radius-2xl: 16px;
    --radius-full: 999px;

    --shadow-sm: 0 1px 4px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.04);
    --shadow-blue-sm: 0 2px 8px rgba(37,99,235,0.25);
    --shadow-blue-md: 0 4px 14px rgba(37,99,235,0.35);
    --shadow-blue-lg: 0 4px 20px rgba(37,99,235,0.10), 0 1px 4px rgba(0,0,0,0.06);

    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-7: 28px;

    --pad-page-x: clamp(0.75rem, 2vw, 2rem);
    --pad-card-x: clamp(14px, 2.4vw, 28px);
    --pad-card-y: clamp(14px, 2vw, 24px);

    --fs-xs: clamp(11px, 0.25vw + 10px, 12px);
    --fs-sm: clamp(12px, 0.35vw + 11px, 13px);
    --fs-base: clamp(13px, 0.35vw + 12px, 14px);
    --fs-md: clamp(14px, 0.45vw + 13px, 16px);
    --fs-lg: clamp(16px, 0.7vw + 14px, 18px);
    --fs-xl: clamp(18px, 1vw + 15px, 22px);
}


/* ═══════════════════════════════════════════════
   GLOBAL APP BACKGROUND
═══════════════════════════════════════════════ */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: var(--bg-app) !important;
    color: var(--text-main) !important;
}

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
    padding-left: var(--pad-page-x) !important;
    padding-right: var(--pad-page-x) !important;
    max-width: 100% !important;
}

/* Prevent cramped content overflow */
html, body, .main, .block-container {
    overflow-x: hidden !important;
}


/* ═══════════════════════════════════════════════
   SIDEBAR — Clean White Light Theme
═══════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1.5px solid var(--border) !important;
    box-shadow: 2px 0 12px rgba(37, 99, 235, 0.06) !important;
}

[data-testid="stSidebar"] * {
    color: var(--text-main) !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label {
    color: var(--text-main) !important;
}

/* Sidebar section title */
[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: var(--fs-sm) !important;
    font-weight: 800 !important;
    color: var(--text-main) !important;
    letter-spacing: 0.5px !important;
    margin-bottom: 4px !important;
}

/* Sidebar divider */
[data-testid="stSidebar"] hr {
    border-color: var(--border) !important;
    margin: 12px 0 !important;
}

/* Sidebar file uploader */
[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    background: var(--bg-soft) !important;
    border: 1.5px dashed #cbd5e1 !important;
    border-radius: var(--radius-md) !important;
    padding: 4px !important;
}

[data-testid="stSidebar"] [data-testid="stFileUploader"]:hover {
    border-color: var(--primary) !important;
    background: var(--bg-soft-2) !important;
}

/* Sidebar inputs */
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-baseweb="base-input"] {
    background: var(--bg-soft) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
}

[data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
[data-testid="stSidebar"] [data-baseweb="base-input"]:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-soft) !important;
}

[data-testid="stSidebar"] [data-baseweb="input"] input,
[data-testid="stSidebar"] [data-baseweb="base-input"] input {
    color: var(--text-main) !important;
    background: transparent !important;
}

/* Sidebar button */
[data-testid="stSidebar"] .stButton > button {
    background: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 700 !important;
    font-size: var(--fs-base) !important;
    padding: 10px 12px !important;
    min-height: 44px !important;
    width: 100% !important;
    box-shadow: var(--shadow-blue-sm) !important;
    transition: all 0.15s ease !important;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--primary-hover) !important;
    box-shadow: var(--shadow-blue-md) !important;
}

/* Sidebar label text */
[data-testid="stSidebar"] [data-testid="stTextInput"] label,
[data-testid="stSidebar"] [data-testid="stFileUploader"] label,
[data-testid="stSidebar"] [data-testid="stNumberInput"] label,
[data-testid="stSidebar"] [data-testid="stSelectbox"] label {
    font-size: var(--fs-xs) !important;
    font-weight: 600 !important;
    color: var(--text-muted) !important;
    letter-spacing: 0.2px !important;
}


/* ═══════════════════════════════════════════════
   INPUTS — Force Light Mode
═══════════════════════════════════════════════ */
[data-baseweb="input"],
[data-baseweb="base-input"] {
    background-color: #ffffff !important;
    border: 1.5px solid var(--border-soft) !important;
    border-radius: var(--radius-sm) !important;
    transition: border-color 0.15s ease !important;
}

[data-baseweb="input"]:focus-within,
[data-baseweb="base-input"]:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-soft-2) !important;
}

[data-baseweb="input"] input,
[data-baseweb="base-input"] input {
    background-color: #ffffff !important;
    color: var(--text-main) !important;
    font-size: 16px !important; /* better on mobile, prevents iOS zoom */
}

input::placeholder {
    color: #b0b8c8 !important;
    font-style: italic;
}


/* SELECT / DROPDOWN */
[data-baseweb="select"] > div:first-child {
    background-color: #ffffff !important;
    border: 1.5px solid var(--border-soft) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-main) !important;
    min-height: 44px !important;
}

[data-baseweb="select"] > div:first-child:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-soft-2) !important;
}

[data-baseweb="select"] [data-baseweb="icon"] {
    color: var(--text-muted) !important;
}

[data-baseweb="popover"],
[data-baseweb="menu"] {
    background-color: #ffffff !important;
    border-radius: var(--radius-md) !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.12) !important;
}

[data-baseweb="option"] {
    background-color: #ffffff !important;
    color: var(--text-main) !important;
    font-size: var(--fs-base) !important;
}

[data-baseweb="option"]:hover {
    background-color: var(--bg-soft-2) !important;
}


/* Number input spinners */
[data-testid="stNumberInput"] button {
    background: var(--bg-app) !important;
    color: var(--text-main) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    min-width: 34px !important;
    min-height: 34px !important;
}


/* Form container */
[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

.stForm {
    background: transparent !important;
    border: none !important;
}


/* Input labels */
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stSelectbox"] label {
    color: #374151 !important;
    font-size: var(--fs-base) !important;
    font-weight: 600 !important;
    margin-bottom: 2px !important;
}


/* ═══════════════════════════════════════════════
   FORM CARD — Modal Style
═══════════════════════════════════════════════ */
.emp-form-card {
    background: #ffffff;
    border: 1.5px solid var(--border);
    border-radius: var(--radius-xl);
    overflow: hidden;
    box-shadow: var(--shadow-blue-lg);
    margin: 12px 0 18px 0;
}

.emp-form-header {
    background: linear-gradient(120deg, #1d4ed8 0%, #2563eb 60%, #3b82f6 100%);
    padding: clamp(14px, 2vw, 16px) clamp(16px, 2.5vw, 22px) clamp(12px, 2vw, 14px) clamp(16px, 2.5vw, 22px);
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.emp-form-title {
    font-size: clamp(15px, 0.5vw + 14px, 16px);
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.2px;
    line-height: 1.3;
    word-break: break-word;
}

.emp-form-subtitle {
    font-size: var(--fs-xs);
    color: rgba(255,255,255,0.72);
    font-weight: 400;
    line-height: 1.4;
}

.emp-form-body {
    padding: clamp(16px, 2.2vw, 20px) clamp(16px, 2.5vw, 22px) clamp(14px, 2vw, 16px) clamp(16px, 2.5vw, 22px);
}

/* Form primary button */
.emp-form-card [data-testid="column"]:first-child [data-testid="stFormSubmitButton"] button {
    background: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 700 !important;
    font-size: var(--fs-md) !important;
    padding: 10px 12px !important;
    min-height: 44px !important;
    width: 100% !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.30) !important;
    transition: all 0.15s ease !important;
}

.emp-form-card [data-testid="column"]:first-child [data-testid="stFormSubmitButton"] button:hover {
    background: var(--primary-hover) !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.40) !important;
}

/* Form cancel button */
.emp-form-card [data-testid="column"]:last-child [data-testid="stFormSubmitButton"] button {
    background: var(--bg-app) !important;
    color: var(--text-muted) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    font-size: var(--fs-md) !important;
    padding: 10px 12px !important;
    min-height: 44px !important;
    width: 100% !important;
}

.emp-form-card [data-testid="column"]:last-child [data-testid="stFormSubmitButton"] button:hover {
    background: var(--border) !important;
    color: #374151 !important;
}


/* ═══════════════════════════════════════════════
   CARDS
═══════════════════════════════════════════════ */
.clean-card {
    background: #ffffff;
    border-radius: var(--radius-2xl);
    padding: var(--pad-card-y) var(--pad-card-x);
    box-shadow: var(--shadow-sm), var(--shadow-md);
    margin-bottom: 20px;
    overflow: hidden;
}

.card-title {
    font-size: clamp(1rem, 0.6vw + 0.95rem, 1.08rem);
    font-weight: 700;
    color: var(--text-main);
    margin-bottom: 16px;
    letter-spacing: -0.2px;
    line-height: 1.35;
    word-break: break-word;
}


/* ═══════════════════════════════════════════════
   EMPLOYEE TABLE / LIST
═══════════════════════════════════════════════ */
.table-responsive {
    width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    border-radius: var(--radius-md);
}

.table-responsive table,
.table-responsive [role="table"] {
    min-width: 720px;
}

.th-cell {
    font-size: var(--fs-xs);
    font-weight: 700;
    color: var(--text-faint);
    letter-spacing: 0.9px;
    text-transform: uppercase;
    padding: 6px 4px 10px 4px;
    white-space: nowrap;
}

.table-divider {
    height: 2px;
    background: linear-gradient(90deg, #e2e8f0, #f8fafc);
    border-radius: 2px;
    margin-bottom: 4px;
}

.table-row-divider {
    height: 1px;
    background: var(--bg-app);
    margin: 2px 0 4px 0;
}


/* ═══════════════════════════════════════════════
   AVATAR
═══════════════════════════════════════════════ */
.avatar-circle {
    width: clamp(34px, 3.6vw, 40px);
    height: clamp(34px, 3.6vw, 40px);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-weight: 800;
    font-size: clamp(13px, 0.7vw + 12px, 15px);
    margin-top: 4px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    flex-shrink: 0;
}


/* ═══════════════════════════════════════════════
   EMPLOYEE INFO
═══════════════════════════════════════════════ */
.emp-name-main {
    font-weight: 700;
    font-size: var(--fs-base);
    color: var(--text-main);
    margin-top: 5px;
    line-height: 1.35;
    word-break: break-word;
}

.emp-id-sub {
    font-size: var(--fs-xs);
    color: var(--text-faint);
    margin-top: 2px;
    font-weight: 500;
    word-break: break-word;
}

.emp-full-name {
    font-size: var(--fs-base);
    color: var(--text-soft);
    margin-top: 8px;
    line-height: 1.45;
    word-break: break-word;
}


/* ═══════════════════════════════════════════════
   BADGES
═══════════════════════════════════════════════ */
.sched-badge {
    display: inline-flex;
    align-items: center;
    border: 1.5px solid #cbd5e1;
    border-radius: var(--radius-full);
    padding: 4px 11px;
    font-size: var(--fs-base);
    color: #334155;
    font-weight: 500;
    margin-top: 8px;
    white-space: nowrap;
    background: var(--bg-soft);
    max-width: 100%;
}

.status-active-badge {
    display: inline-flex;
    align-items: center;
    background: var(--success-bg);
    color: var(--success-text);
    border: 1.5px solid var(--success-border);
    border-radius: var(--radius-full);
    padding: 4px 11px;
    font-size: var(--fs-base);
    font-weight: 700;
    margin-top: 8px;
    white-space: nowrap;
    max-width: 100%;
}


/* ═══════════════════════════════════════════════
   ALERT BOXES
═══════════════════════════════════════════════ */
.warn-box {
    background: var(--warn-bg);
    border-left: 4px solid var(--warn-border);
    border-radius: var(--radius-sm);
    padding: 12px 16px;
    margin-bottom: 12px;
    color: var(--warn-text);
    font-size: 0.9rem;
    line-height: 1.45;
}

.info-box {
    background: var(--info-bg);
    border-left: 4px solid var(--info-border);
    border-radius: var(--radius-sm);
    padding: 10px 16px;
    margin-bottom: 10px;
    color: var(--info-text);
    font-size: 0.875rem;
    line-height: 1.45;
}

.success-box {
    background: #f0fdf4;
    border-left: 4px solid #22c55e;
    border-radius: var(--radius-sm);
    padding: 10px 16px;
    margin-bottom: 10px;
    color: #14532d;
    font-size: 0.875rem;
    line-height: 1.45;
}


/* ═══════════════════════════════════════════════
   METRIC CARDS
═══════════════════════════════════════════════ */
.metric-box {
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: clamp(12px, 2vw, 16px) clamp(14px, 2.4vw, 20px);
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    height: 100%;
}

.metric-label {
    font-size: var(--fs-xs);
    font-weight: 700;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 6px;
}

.metric-value {
    font-size: clamp(1.35rem, 2.2vw, 1.9rem);
    font-weight: 800;
    color: var(--text-main);
    line-height: 1.05;
    word-break: break-word;
}


/* ═══════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════ */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    flex-wrap: wrap !important;
    gap: 6px !important;
}

div[data-testid="stTabs"] [data-baseweb="tab"] {
    font-weight: 600;
    font-size: clamp(12px, 0.5vw + 11px, 14px);
    padding: 10px 16px;
    color: var(--text-soft) !important;
    border-radius: var(--radius-sm) !important;
    min-height: 44px !important;
}

div[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--primary) !important;
}


/* ═══════════════════════════════════════════════
   GENERAL BUTTONS
═══════════════════════════════════════════════ */
.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] button {
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    font-size: var(--fs-base) !important;
    transition: all 0.15s ease !important;
    background: var(--bg-app) !important;
    color: var(--text-main) !important;
    border: 1px solid var(--border) !important;
    min-height: 44px !important;
    width: 100% !important;
    white-space: normal !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] button:hover {
    background: var(--border) !important;
    border-color: #cbd5e1 !important;
}

.stButton > button:focus,
.stDownloadButton > button:focus,
[data-testid="stFormSubmitButton"] button:focus {
    box-shadow: 0 0 0 3px var(--primary-soft) !important;
}


/* ═══════════════════════════════════════════════
   FOOTER
═══════════════════════════════════════════════ */
.footer {
    text-align: center;
    font-size: var(--fs-xs);
    font-weight: 700;
    color: var(--text-faint);
    letter-spacing: 2.5px;
    text-transform: uppercase;
    padding: 24px 0 12px 0;
    line-height: 1.4;
}


/* ═══════════════════════════════════════════════
   STREAMLIT LAYOUT FIXES
═══════════════════════════════════════════════ */

/* Better spacing for columns */
[data-testid="column"] {
    min-width: 0 !important;
}

/* Prevent markdown/text overflow inside cards */
.clean-card *,
.emp-form-card *,
.metric-box * {
    max-width: 100%;
}

/* Dataframe / table wrappers */
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    width: 100% !important;
    overflow-x: auto !important;
}

/* Help long content wrap */
p, span, div, label {
    word-wrap: break-word;
    overflow-wrap: break-word;
}

/* Make images/media safe */
img, svg, canvas {
    max-width: 100% !important;
    height: auto !important;
}


/* ═══════════════════════════════════════════════
   TABLET
═══════════════════════════════════════════════ */
@media (max-width: 1024px) {
    [data-testid="stSidebar"] {
        min-width: 260px !important;
        max-width: 320px !important;
    }

    .clean-card {
        margin-bottom: 16px !important;
    }

    .metric-value {
        font-size: clamp(1.3rem, 2vw, 1.7rem) !important;
    }
}


/* ═══════════════════════════════════════════════
   MOBILE / SMALL TABLET
═══════════════════════════════════════════════ */
@media (max-width: 768px) {

    .block-container {
        padding-top: 0.75rem !important;
        padding-bottom: 0.75rem !important;
    }

    /* Stack streamlit columns */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: column !important;
        gap: 12px !important;
    }

    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
    }

    .clean-card {
        border-radius: var(--radius-xl) !important;
        padding: 16px !important;
    }

    .emp-form-card {
        border-radius: 12px !important;
        margin: 10px 0 16px 0 !important;
    }

    .emp-form-header,
    .emp-form-body {
        padding-left: 14px !important;
        padding-right: 14px !important;
    }

    .card-title {
        margin-bottom: 12px !important;
    }

    .sched-badge,
    .status-active-badge {
        padding: 4px 10px !important;
    }

    .footer {
        letter-spacing: 1.5px !important;
        padding: 18px 0 8px 0 !important;
    }

    div[data-testid="stTabs"] [data-baseweb="tab"] {
        padding: 8px 12px !important;
    }
}


/* ═══════════════════════════════════════════════
   PHONES
═══════════════════════════════════════════════ */
@media (max-width: 640px) {

    [data-testid="stSidebar"] {
        min-width: 250px !important;
        max-width: 82vw !important;
    }

    .avatar-circle {
        margin-top: 2px !important;
    }

    .emp-name-main {
        font-size: 13px !important;
    }

    .emp-full-name {
        font-size: 12px !important;
        margin-top: 6px !important;
    }

    .sched-badge,
    .status-active-badge {
        font-size: 11px !important;
    }

    .metric-box {
        border-radius: 10px !important;
    }

    .metric-label {
        letter-spacing: 0.5px !important;
    }

    .table-responsive table,
    .table-responsive [role="table"] {
        min-width: 640px;
    }
}


/* ═══════════════════════════════════════════════
   EXTRA SMALL PHONES
═══════════════════════════════════════════════ */
@media (max-width: 480px) {

    .block-container {
        padding-left: 0.65rem !important;
        padding-right: 0.65rem !important;
    }

    .clean-card {
        padding: 14px !important;
        border-radius: 12px !important;
    }

    .emp-form-header {
        padding: 14px 14px 12px 14px !important;
    }

    .emp-form-body {
        padding: 14px !important;
    }

    .metric-value {
        font-size: 1.28rem !important;
    }

    .emp-form-title {
        font-size: 14px !important;
    }

    .emp-form-subtitle {
        font-size: 11px !important;
    }

    .footer {
        font-size: 10px !important;
    }
}


/* ═══════════════════════════════════════════════
   TOUCH + ACCESSIBILITY ENHANCEMENTS
═══════════════════════════════════════════════ */
@media (hover: none) and (pointer: coarse) {
    .stButton > button,
    .stDownloadButton > button,
    [data-testid="stFormSubmitButton"] button,
    [data-baseweb="select"] > div:first-child,
    [data-testid="stNumberInput"] button {
        min-height: 44px !important;
    }
}


/* ═══════════════════════════════════════════════
   OPTIONAL HELPER CLASSES
═══════════════════════════════════════════════ */
.hide-mobile {
    display: block;
}

.show-mobile {
    display: none;
}

@media (max-width: 768px) {
    .hide-mobile {
        display: none !important;
    }

    .show-mobile {
        display: block !important;
    }
}

</style>
"""