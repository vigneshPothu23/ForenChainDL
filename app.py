
import hashlib
import sqlite3
import uuid
from pathlib import Path

import streamlit as st
import numpy as np
from PIL import Image

from forenchain.auth import (
    ROLES,
    authenticate_user,
    change_password,
    create_initial_admin,
    create_user,
    has_permission,
    initial_admin_required,
    initialize_auth_database,
)
from forenchain.custody import (
    get_custody_history,
    record_custody_event,
    verify_custody_chain,
)
from forenchain.evidence_store import (
    DATABASE_PATH,
    find_duplicate_evidence,
    initialize_database,
    register_evidence,
)
from forenchain.forensics import MVSSForensics
from forenchain.integrity import verify_evidence
from forenchain.analysis_history import save_analysis, save_examiner_finding
from forenchain.forensic_report import build_forensic_report_pdf


st.set_page_config(
    page_title="ForenChain-DL",
    page_icon="F",
    layout="wide",
)


st.markdown("""
<style>
/* FORENCHAIN_CUSTOM_THEME */
:root {
    --fc-ink: #182b43;
    --fc-navy: #203b5c;
    --fc-muted: #68788c;
    --fc-border: #dce3eb;
    --fc-surface: #ffffff;
    --fc-page: #f5f7fa;
    --fc-accent: #315d83;
}
.stApp {
    background: var(--fc-page);
    color: var(--fc-ink);
    font-family: "Segoe UI", Arial, sans-serif;
}
[data-testid="stHeader"] {
    background: rgba(245,247,250,.96);
}
.block-container {
    max-width: 1500px;
    padding: 2rem 2.4rem 3rem;
}
h1, h2, h3 {
    color: var(--fc-ink);
    letter-spacing: -.025em;
    font-weight: 650;
}
h1 { font-size: 2rem; }
h2 { font-size: 1.45rem; }
h3 { font-size: 1.12rem; }
p, label, .stCaption {
    color: var(--fc-muted);
}
[data-testid="stMetric"] {
    background: var(--fc-surface);
    border: 1px solid var(--fc-border);
    border-radius: 10px;
    padding: 19px 21px;
    box-shadow: 0 2px 5px rgba(24,43,67,.035);
}
[data-testid="stMetricLabel"] {
    color: var(--fc-muted);
    font-size: .85rem;
    font-weight: 600;
}
[data-testid="stMetricValue"] {
    color: var(--fc-navy);
    font-size: 1.8rem;
    font-weight: 700;
}
[data-testid="stSidebar"] {
    background: #edf1f6;
    border-right: 1px solid var(--fc-border);
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: var(--fc-ink);
}
div.stButton > button,
div[data-testid="stFormSubmitButton"] > button {
    border-radius: 7px;
    min-height: 2.55rem;
    font-weight: 600;
    border: 1px solid #cbd5e1;
    transition: border-color .15s ease, background .15s ease;
}
div.stButton > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
    background: var(--fc-navy);
    color: #ffffff;
    border-color: var(--fc-navy);
}
div.stButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    border-color: var(--fc-accent);
}
div[data-testid="stTabs"] button {
    color: #53657a;
    font-weight: 600;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--fc-navy);
}
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border: 1px solid var(--fc-border);
    border-radius: 8px;
    overflow: hidden;
}
[data-testid="stForm"],
[data-testid="stExpander"] {
    background: var(--fc-surface);
    border: 1px solid var(--fc-border);
    border-radius: 9px;
    padding: .4rem;
}
input, textarea {
    border-radius: 6px !important;
}
hr {
    border-color: var(--fc-border);
}
[data-testid="stAlert"] {
    border-radius: 8px;
}
@media (max-width: 768px) {
    .block-container {
        padding: 1rem 1rem 2rem;
    }
    h1 { font-size: 1.65rem; }
}

/* FORENCHAIN_DASHBOARD_POLISH */
.fc-dashboard-heading {
    margin: 0 0 1.25rem 0;
    padding: 1.15rem 1.35rem;
    background: linear-gradient(110deg, #ffffff, #edf3f8);
    border: 1px solid var(--fc-border);
    border-left: 4px solid var(--fc-navy);
    border-radius: 10px;
}

.fc-dashboard-heading .fc-eyebrow {
    color: var(--fc-accent);
    font-size: 0.72rem;
    font-weight: 750;
    letter-spacing: 0.12em;
    margin-bottom: 0.35rem;
}

.fc-dashboard-heading h2 {
    margin: 0;
    font-size: 1.5rem;
}

.fc-dashboard-heading p {
    margin: 0.4rem 0 0 0;
    font-size: 0.9rem;
}

[data-testid="stMetric"] {
    min-height: 112px;
    transition: border-color 0.18s ease,
                box-shadow 0.18s ease,
                transform 0.18s ease;
}

[data-testid="stMetric"]:hover {
    border-color: #aabbd0;
    box-shadow: 0 5px 16px rgba(24, 43, 67, 0.07);
    transform: translateY(-2px);
}


/* FORENCHAIN_DASHBOARD_V2 */
.fc-v2-hero {
    padding: 1.8rem 2rem;
    margin: .2rem 0 1.8rem;
    border-radius: 17px;
    color: #fff;
    background: linear-gradient(118deg, #122940 0%, #234e70 58%, #36758a 100%);
    box-shadow: 0 12px 30px rgba(22,48,76,.16);
}
.fc-v2-top {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}
.fc-v2-logo {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 11px;
    border: 1px solid rgba(255,255,255,.24);
    background: rgba(255,255,255,.13);
    color: white;
    font-weight: 800;
}
.fc-v2-kicker {
    color: #dbeaf6;
    font-size: .7rem;
    letter-spacing: .14em;
    font-weight: 800;
}
.fc-v2-status {
    margin-left: auto;
    padding: 6px 10px;
    border-radius: 20px;
    background: rgba(10,125,88,.25);
    border: 1px solid rgba(190,255,224,.25);
    color: #d1fae5;
    font-size: .68rem;
    font-weight: 750;
}
.fc-v2-hero h1 {
    margin: 1.3rem 0 .5rem;
    color: #fff !important;
    font-size: clamp(1.9rem,3vw,2.65rem) !important;
    letter-spacing: -.04em;
}
.fc-v2-hero p {
    color: #e0eaf3 !important;
    margin: 0;
    line-height: 1.6;
    max-width: 650px;
}
.fc-v2-footer {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 1.4rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(255,255,255,.19);
    color: #edf4fa;
    font-size: .85rem;
}
.fc-v2-role {
    padding: 5px 10px;
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,.24);
    background: rgba(255,255,255,.09);
}
.fc-v2-section {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 1rem;
}
.fc-v2-eyebrow {
    color: #557b9c;
    font-size: .68rem;
    letter-spacing: .15em;
    font-weight: 850;
    margin-bottom: 4px;
}
.fc-v2-section h3 {
    margin: 0;
    font-size: 1.4rem;
}
.fc-v2-local {
    padding: 7px 10px;
    border: 1px solid #d5e0eb;
    border-radius: 7px;
    background: #edf3f9;
    color: #425d78;
    font-size: .66rem;
    font-weight: 800;
    letter-spacing: .05em;
}
[data-testid="stMetric"] {
    min-height: 118px;
    padding: 1.1rem 1.15rem;
    border-radius: 13px;
    border: 1px solid #dbe5ef;
    background: linear-gradient(145deg,#fff,#f5f9fd);
    box-shadow: 0 4px 14px rgba(24,43,67,.05);
    transition: transform .18s ease, box-shadow .18s ease,
                border-color .18s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    border-color: #9db5cd;
    box-shadow: 0 10px 24px rgba(24,43,67,.09);
}
[data-testid="stMetricLabel"] {
    color: #60748b;
    font-size: .83rem;
    font-weight: 700;
}
[data-testid="stMetricValue"] {
    color: #1c3c5c;
    font-size: 2rem;
    font-weight: 800;
}
.fc-v2-note {
    display: flex;
    gap: 13px;
    align-items: flex-start;
    margin: 1.3rem 0 .6rem;
    padding: 1.05rem 1.15rem;
    border: 1px solid #d7e5e6;
    border-radius: 12px;
    background: linear-gradient(100deg,#f0f8f7,#f8fbfc);
}
.fc-v2-note-icon {
    display: flex;
    flex: 0 0 26px;
    height: 26px;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    color: #08775f;
    background: #d7f3e8;
    font-weight: 900;
}
.fc-v2-note strong { color: #234c56; font-size: .92rem; }
.fc-v2-note p {
    color: #5d727c !important;
    margin: 4px 0 0;
    font-size: .85rem;
    line-height: 1.55;
}
@media (max-width: 768px) {
    .fc-v2-hero { padding: 1.25rem; border-radius: 13px; }
    .fc-v2-status { margin-left: 0; }
    .fc-v2-section { align-items: flex-start; flex-direction: column; }
}



/* FORENCHAIN_AI_RESULTS_POLISH */
.fc-ai-results-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    margin: 1.2rem 0 1rem;
    padding: 1.15rem 1.35rem;
    border: 1px solid #d8e3ed;
    border-left: 4px solid #315d83;
    border-radius: 12px;
    background: linear-gradient(110deg, #ffffff, #eff5fa);
}
.fc-ai-eyebrow {
    display: block;
    margin-bottom: 5px;
    color: #557b9c;
    font-size: .68rem;
    font-weight: 800;
    letter-spacing: .14em;
}
.fc-ai-results-heading h3 {
    margin: 0;
    color: #182b43;
    font-size: 1.35rem;
}
.fc-ai-results-heading p {
    margin: 5px 0 0;
    font-size: .86rem;
}
.fc-ai-result-tag {
    padding: 7px 10px;
    border: 1px solid #b8e2d1;
    border-radius: 7px;
    background: #e9f8f0;
    color: #176447;
    font-size: .67rem;
    font-weight: 800;
    letter-spacing: .04em;
}
[data-testid="stMetric"] {
    border-radius: 12px;
    border-color: #d9e4ee;
    box-shadow: 0 3px 12px rgba(24,43,67,.045);
}



/* FC_AI_SCORE_CARD_V4 */
.fc-score-feature, .fc-device-feature {
    min-height: 142px;
    padding: 22px;
    border: 1px solid #d7e3ee;
    border-radius: 15px;
    background: linear-gradient(135deg, #ffffff, #edf4fa);
    box-shadow: 0 6px 18px rgba(24,43,67,.055);
}
.fc-score-feature {
    border-top: 4px solid #315d83;
}
.fc-device-feature {
    border-top: 4px solid #7593aa;
    background: linear-gradient(135deg, #ffffff, #f4f7fa);
}
.fc-score-label {
    color: #60778d;
    font-size: .69rem;
    font-weight: 850;
    letter-spacing: .12em;
}
.fc-score-value {
    margin: 13px 0 7px;
    color: #183b5c;
    font-size: clamp(2rem, 4vw, 2.8rem);
    line-height: 1;
    font-weight: 850;
    letter-spacing: -.05em;
    overflow-wrap: anywhere;
}
.fc-device-value {
    margin: 17px 0 10px;
    color: #234762;
    font-size: 1.7rem;
    line-height: 1.1;
    font-weight: 800;
}
.fc-score-caption {
    color: #718397;
    font-size: .78rem;
    line-height: 1.5;
}



/* FORENCHAIN_EVIDENCE_REGISTER_V2 */
.fc-register-hero {
    padding: 1.5rem 1.7rem;
    margin: .2rem 0 1.3rem;
    border: 1px solid #d6e2ed;
    border-left: 5px solid #315d83;
    border-radius: 15px;
    background: linear-gradient(115deg,#fff,#edf4fa);
    box-shadow: 0 6px 20px rgba(24,43,67,.045);
}
.fc-register-kicker {
    color: #527697;
    font-size: .68rem;
    font-weight: 850;
    letter-spacing: .15em;
}
.fc-register-hero h2 {
    margin: .55rem 0 .35rem;
    color: #18344f;
    font-size: 1.7rem;
}
.fc-register-hero p {
    margin: 0;
    color: #667b90 !important;
    font-size: .9rem;
    line-height: 1.6;
}


    /* FORENCHAIN_CUSTODY_UI_V2 */
    .fc-custody-hero {
        padding: 28px 32px;
        margin: 8px 0 24px 0;
        border: 1px solid #d5e3f1;
        border-left: 6px solid #315f85;
        border-radius: 20px;
        background: linear-gradient(120deg, #ffffff 0%, #edf5fc 100%);
    }
    .fc-custody-eyebrow {
        color: #426b91;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 2px;
        margin-bottom: 12px;
    }
    .fc-custody-hero h1 {
        color: #153452;
        font-size: 30px;
        margin: 0 0 10px 0;
    }
    .fc-custody-hero p {
        color: #5a7188;
        font-size: 16px;
        margin: 0;
    }


/* FORENCHAIN_BATCH4_DARK_TEAL */
:root {
  --fc-ink: #E8EEF4;
  --fc-navy: #DCE7F0;
  --fc-muted: #A6B4C2;
  --fc-border: #2A3A49;
  --fc-surface: #121E2A;
  --fc-page: #0B1118;
  --fc-accent: #18B8A6;
}
.stApp, [data-testid="stAppViewContainer"] {
  background: #0B1118 !important;
  color: #E8EEF4 !important;
}
[data-testid="stHeader"] {
  background: #0B1118 !important;
}
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {
  background: #0E1822 !important;
}
h1, h2, h3, h4, h5, h6, p, label,
[data-testid="stMarkdownContainer"] {
  color: #E8EEF4;
}
[data-testid="stCaptionContainer"] {
  color: #A6B4C2 !important;
}
hr { border-color: #2A3A49 !important; }
[data-testid="stMetric"] {
  background: #121E2A !important;
  border: 1px solid #2A3A49 !important;
  border-radius: 12px !important;
  padding: 16px !important;
}
[data-testid="stMetricLabel"],
[data-testid="stMetricDelta"] { color: #A6B4C2 !important; }
[data-testid="stMetricValue"] { color: #E8EEF4 !important; }
[data-testid="stExpander"],
[data-testid="stForm"] {
  border-color: #2A3A49 !important;
}
[data-testid="stTabs"] button { color: #A6B4C2 !important; }
[data-testid="stTabs"] button[aria-selected="true"] {
  color: #18B8A6 !important;
  border-bottom-color: #18B8A6 !important;
}
.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {
  background: #18B8A6 !important;
  color: #061714 !important;
  border: 1px solid #18B8A6 !important;
  border-radius: 8px !important;
  font-weight: 650 !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
  background: #2DD4BF !important;
  color: #061714 !important;
}
input, textarea, [data-baseweb="input"] input,
[data-baseweb="select"] > div, [data-baseweb="textarea"] {
  background: #0D1721 !important;
  color: #E8EEF4 !important;
  border-color: #2A3A49 !important;
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
  border: 1px solid #2A3A49 !important;
  border-radius: 8px !important;
  overflow: hidden !important;
}
.fc-v2-hero, .fc-v2-note, .fc-ai-results-heading,
.fc-score-feature, .fc-device-feature,
.fc-register-hero, .fc-custody-hero {
  background: #121E2A !important;
  color: #E8EEF4 !important;
  border-color: #2A3A49 !important;
  box-shadow: none !important;
}
.fc-v2-hero, .fc-register-hero,
.fc-custody-hero, .fc-ai-results-heading {
  border-left: 3px solid #18B8A6 !important;
}

</style>
""", unsafe_allow_html=True)


ROLE_LABELS = {
    "System Administrator": "Platform Administrator",
    "Investigator": "Evidence Registrar",
    "Forensic Examiner": "Forensic Examiner",
    "Evidence Custodian": "Chain-of-Custody Officer",
    "Judicial Authority": "Judicial Reviewer",
}

initialize_auth_database()


def query_all(sql, params=()):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def get_evidence(evidence_id):
    rows = query_all(
        """
        SELECT evidence_id, case_id, original_filename, stored_path,
               sha256, size_bytes, image_width, image_height, registered_at
        FROM evidence
        WHERE evidence_id = ?
        """,
        (evidence_id.strip(),),
    )
    return rows[0] if rows else None


def logout():
    st.session_state.pop("user", None)
    st.rerun()


def show_header(user):
    """Batch 4 top bar: active case chip, environment chip, user chip, log out."""
    import html as _html

    role_label = ROLE_LABELS.get(user["role"], user["role"])
    username = str(user.get("username", "User"))
    initials = "".join(p[0] for p in username.replace("_", " ").split()[:2]).upper() or username[:2].upper()

    case_chip = ""
    if has_permission(user["role"], "view_evidence"):
        latest = query_all(
            """SELECT evidence_id, case_id, sha256 FROM evidence
               ORDER BY registered_at DESC LIMIT 1"""
        )
        if latest:
            row = latest[0]
            case_chip = (
                '<div class="fcd-case">'
                f'<div class="fcd-case-glyph">{_fcd_glyph(row["sha256"], 30, 1)}</div>'
                f'<div><b>{_html.escape(str(row["case_id"]))}</b>'
                f'<span>{_html.escape(_fcd_short(row["evidence_id"]))}</span></div></div>'
            )

    _fcd_css()
    left, right = st.columns([6, 1], vertical_alignment="center")
    with left:
        st.markdown(
            '<div class="fcd-top">'
            f'{case_chip}'
            '<span class="fcd-chip"><i></i>LOCAL DATABASE</span>'
            '<div class="fcd-user">'
            f'<span class="fcd-avatar">{_html.escape(initials)}</span>'
            f'<div><b>{_html.escape(username)}</b><span>{_html.escape(str(role_label))}</span></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.button("Log out", on_click=logout, width="stretch", key="fcd_logout")


def _fcd_short(value, head=4, tail=8):
    text = str(value or "")
    prefix, sep, rest = text.partition("-")
    if sep and len(rest) > head + tail + 1:
        return f"{prefix}-{rest[:head]}…{rest[-tail:]}"
    return text


def _fcd_glyph(sha256, size, gap):
    ramp = ["#0F2A26", "#17584B", "#2FB592", "#7CF2D6"]
    hexs = str(sha256 or "")[:64].ljust(64, "0")
    cells = "".join(
        f'<b style="background:{ramp[int(c, 16) // 4] if c in "0123456789abcdefABCDEF" else ramp[0]}"></b>'
        for c in hexs
    )
    return f'<div class="fcd-glyph" style="width:{size}px;gap:{gap}px">{cells}</div>'


def _fcd_time(value):
    from datetime import datetime, timezone
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%d %b")


def _fcd_table_exists(name):
    return bool(query_all(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ))


@st.cache_data(ttl=60, show_spinner=False)
def _fcd_integrity(evidence_id):
    """Read-only integrity check for the dashboard, cached for 60 seconds."""
    try:
        return verify_evidence(evidence_id).get("status", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


@st.cache_data(ttl=60, show_spinner=False)
def _fcd_chain():
    """Read-only global custody-chain check for the dashboard, cached for 60 seconds."""
    try:
        return verify_custody_chain()
    except Exception as exc:
        return {"valid": False, "message": str(exc), "event_count": 0}


_FCD_ICONS = {
    "folder": "M4 6h6l2 2h8v11H4z",
    "shield": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.5 2.5 4.5-5",
    "link": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    "scan": "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M8 12h8",
    "file": "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
    "seal": "M12 2l2.4 2.2 3.2-.4.9 3.1 2.9 1.5-1 3.1 1 3.1-2.9 1.5-.9 3.1-3.2-.4L12 22l-2.4-2.2-3.2.4-.9-3.1-2.9-1.5 1-3.1-1-3.1 2.9-1.5.9-3.1 3.2.4z",
    "lock": "M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3",
    "x": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9 9l6 6M15 9l-6 6",
}


def _fcd_icon(name, size=20):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'<path d="{_FCD_ICONS[name]}"/></svg>'
    )


def _fcd_ring(pct, size, stroke, inner):
    import math
    r = (size - stroke) / 2
    c = 2 * math.pi * r
    d = c * max(0.0, min(100.0, pct)) / 100
    return (
        f'<div class="fcd-ring" style="width:{size}px;height:{size}px">'
        f'<svg width="{size}" height="{size}" style="transform:rotate(-90deg)">'
        '<defs><linearGradient id="fcdRing" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#5FE0C3"/><stop offset="1" stop-color="#8B7CFF"/></linearGradient></defs>'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="rgba(255,255,255,.07)" stroke-width="{stroke}"/>'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="url(#fcdRing)" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-dasharray="{d} {c}" style="filter:drop-shadow(0 0 8px rgba(95,224,195,.55))"/>'
        f'</svg><div class="fcd-ring-inner">{inner}</div></div>'
    )


def _fcd_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Tinos:ital@0;1&display=swap');
        .stApp:has(.fcd-marker), .stApp:has(.fcd-marker) [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(900px 520px at 12% -8%, rgba(95,224,195,.13), transparent 60%),
                radial-gradient(800px 520px at 100% 0%, rgba(139,124,255,.12), transparent 60%),
                #05080E !important;
        }
        .stApp:has(.fcd-marker) [data-testid="stHeader"] { background: transparent !important; }
        [data-testid="stElementContainer"]:has(.fcd-marker), .element-container:has(.fcd-marker) { display:none; }
        .fcd-top { display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
        .fcd-case { display:flex; align-items:center; gap:12px; padding:8px 14px 8px 8px; border-radius:14px;
                    background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); }
        .fcd-case-glyph { padding:4px; border-radius:9px; background:rgba(95,224,195,.06); border:1px solid rgba(95,224,195,.2); }
        .fcd-case b { display:block; font:600 14px "IBM Plex Sans","Segoe UI",sans-serif; color:#E8EDF5; line-height:1.25; }
        .fcd-case span { display:block; font:400 11.5px "IBM Plex Mono",Consolas,monospace; color:#7C889C; }
        .fcd-chip { margin-left:auto; display:inline-flex; align-items:center; gap:7px; height:30px; padding:0 12px;
                    border-radius:999px; font:500 12px "IBM Plex Mono",Consolas,monospace; color:#AEB8C8;
                    border:1px solid rgba(255,255,255,.1); background:rgba(255,255,255,.03); }
        .fcd-chip i { width:7px; height:7px; border-radius:50%; background:#5FE0C3; box-shadow:0 0 10px #5FE0C3; }
        .fcd-user { display:flex; align-items:center; gap:10px; padding:6px 14px 6px 6px; border-radius:14px;
                    background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); }
        .fcd-avatar { width:32px; height:32px; border-radius:10px; display:flex; align-items:center; justify-content:center;
                      background:linear-gradient(135deg,#2FB592,#3B5BA9); font:600 12px "IBM Plex Sans",sans-serif; color:#fff; }
        .fcd-user > div > b { display:block; font:600 12.5px "IBM Plex Sans","Segoe UI",sans-serif; color:#E8EDF5; line-height:1.2; }
        .fcd-user > div > span { display:block; font:400 11.5px "IBM Plex Sans","Segoe UI",sans-serif; color:#9AA5B6; }
        .st-key-fcd_logout button {
            background:rgba(255,255,255,.04) !important; color:#E8EDF5 !important;
            border:1px solid rgba(255,255,255,.12) !important; border-radius:12px !important; min-height:44px;
        }
        .st-key-fcd_logout button p { color:#E8EDF5 !important; }
        .st-key-fcd_logout button:hover { border-color:#5FE0C3 !important; background:rgba(95,224,195,.08) !important; }
        .fcd-glyph { display:grid; grid-template-columns:repeat(8,1fr); }
        .fcd-glyph b { aspect-ratio:1; border-radius:2px; }

        .fcd-ov { font:500 11px "IBM Plex Mono",Consolas,monospace; letter-spacing:.16em; text-transform:uppercase; color:#7CF2D6; }
        .fcd-k { font:500 10.5px "IBM Plex Mono",Consolas,monospace; letter-spacing:.12em; text-transform:uppercase; color:#7C889C; }
        .fcd-h1 { font-family:"Times New Roman",Tinos,Times,serif !important; font-weight:400; font-size:clamp(34px,3.6vw,52px);
                  line-height:1.05; letter-spacing:-.015em; color:#E8EDF5; margin:8px 0 6px; }
        .fcd-mut { color:#9AA5B6; font:400 15px "IBM Plex Sans","Segoe UI",sans-serif; }
        .fcd-pn { background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.018));
                  border:1px solid rgba(255,255,255,.085); border-radius:20px; color:#E8EDF5;
                  box-shadow:0 40px 80px -40px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.06);
                  font-family:"IBM Plex Sans","Segoe UI",sans-serif; height:100%; box-sizing:border-box; }
        .fcd-pill { display:inline-flex; align-items:center; gap:6px; height:22px; padding:0 9px; border-radius:999px;
                    font:500 11px "IBM Plex Sans","Segoe UI",sans-serif; white-space:nowrap; }
        .fcd-pill i { width:6px; height:6px; border-radius:50%; background:currentColor; box-shadow:0 0 8px currentColor; }
        .fcd-ok { background:rgba(95,224,195,.12); color:#7CF2D6; }
        .fcd-vio { background:rgba(139,124,255,.14); color:#B3A9FF; }
        .fcd-neu { background:rgba(255,255,255,.06); color:#B8C2D2; }
        .fcd-info { background:rgba(122,167,255,.13); color:#9DBDFF; }
        .fcd-bad { background:rgba(255,122,107,.12); color:#FF8C7E; }
        .fcd-warn { background:rgba(242,184,75,.12); color:#F5C66A; }

        .fcd-trail { display:flex; align-items:flex-start; }
        .fcd-step { display:flex; flex-direction:column; align-items:center; gap:10px; text-align:center; flex:1 1 0; min-width:0; }
        .fcd-node { width:56px; height:56px; border-radius:16px; display:flex; align-items:center; justify-content:center; }
        .fcd-node.done { background:linear-gradient(180deg,rgba(95,224,195,.25),rgba(95,224,195,.08)); border:1px solid rgba(95,224,195,.45);
                         color:#7CF2D6; box-shadow:0 0 28px -8px rgba(95,224,195,.8); }
        .fcd-node.now { background:linear-gradient(180deg,rgba(139,124,255,.35),rgba(139,124,255,.1)); border:1.5px solid #8B7CFF;
                        color:#D4CEFF; box-shadow:0 0 0 6px rgba(139,124,255,.12), 0 0 36px -4px rgba(139,124,255,.9); }
        .fcd-node.lock { background:rgba(255,255,255,.03); border:1px dashed rgba(255,255,255,.18); color:#59647A; }
        .fcd-node.fail { background:rgba(255,122,107,.12); border:1px solid rgba(255,122,107,.5); color:#FF8C7E; }
        .fcd-step b { font:600 13.5px "IBM Plex Sans","Segoe UI",sans-serif; color:#E8EDF5; }
        .fcd-step b.dim { color:#7C889C; }
        .fcd-step small { font:400 11.5px "IBM Plex Sans","Segoe UI",sans-serif; color:#7C889C; min-height:34px; display:block; overflow-wrap:anywhere; }
        .fcd-link { flex:0 0 22px; height:2px; margin-top:28px; }

        .fcd-ring { position:relative; flex:none; }
        .fcd-ring-inner { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
        .fcd-serif { font-family:"Times New Roman",Tinos,Times,serif !important; font-weight:400; line-height:1; }
        .fcd-bars { display:flex; gap:6px; margin-top:6px; }
        .fcd-bars span { flex:1; height:10px; border-radius:4px; }

        .fcd-row { display:flex; gap:14px; align-items:center; padding:13px 0; border-bottom:1px solid rgba(255,255,255,.06); }
        .fcd-row:last-child { border-bottom:none; }
        .fcd-sq { width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center; flex:none; }
        .fcd-mono { font-family:"IBM Plex Mono",Consolas,monospace; }
        .fcd-stats { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:12px 0 8px; }
        .fcd-tbl { width:100%; border-collapse:collapse; font:400 13px "IBM Plex Sans","Segoe UI",sans-serif; color:#E8EDF5; }
        .fcd-tbl th { text-align:left; font:500 10.5px "IBM Plex Mono",Consolas,monospace; letter-spacing:.12em; text-transform:uppercase;
                      color:#7C889C; padding:10px 14px; border-bottom:1px solid rgba(255,255,255,.08); }
        .fcd-tbl td { padding:11px 14px; border-bottom:1px solid rgba(255,255,255,.05); white-space:nowrap; }
        .fcd-tbl tr:last-child td { border-bottom:none; }
        @media (max-width: 1100px) {
            .fcd-trail { flex-wrap:wrap; row-gap:18px; }
            .fcd-link { display:none; }
            .fcd-chip { margin-left:0; }
        }
        </style>
        <span class="fcd-marker"></span>
        """,
        unsafe_allow_html=True,
    )


def _fcd_case_steps(evidence, can_analyze):
    """Six recorded steps for one evidence item, built from existing records only."""
    eid = evidence["evidence_id"]
    custody = query_all(
        "SELECT actor, action, event_time FROM custody_events WHERE evidence_id = ? ORDER BY event_id",
        (eid,),
    ) if _fcd_table_exists("custody_events") else []
    registered_by = next((e["actor"] for e in custody if e["action"] == "REGISTERED"), None)

    integrity = _fcd_integrity(eid)

    analyses = []
    if can_analyze and _fcd_table_exists("analysis_records"):
        analyses = query_all(
            "SELECT analysis_id FROM analysis_records WHERE evidence_id = ? ORDER BY analyzed_at DESC",
            (eid,),
        )
    findings = []
    if can_analyze and _fcd_table_exists("examiner_findings"):
        findings = query_all(
            "SELECT conclusion FROM examiner_findings WHERE evidence_id = ? ORDER BY recorded_at DESC",
            (eid,),
        )

    steps = [
        ("folder", "Registered", f"{registered_by or 'Recorded'} · {_fcd_time(evidence['registered_at'])}", True, False),
        ("shield", "Integrity verified",
         {"INTEGRITY_OK": "SHA-256 match · 64/64",
          "HASH_MISMATCH": "Hash mismatch",
          "MISSING_FILE": "Evidence file missing",
          "NOT_FOUND": "Record not found"}.get(integrity, f"Status: {integrity}"),
         integrity == "INTEGRITY_OK", integrity in ("HASH_MISMATCH", "MISSING_FILE", "NOT_FOUND", "INVALID_PATH")),
        ("link", "Custody logged",
         f"{len(custody)} event{'s' if len(custody) != 1 else ''}" if custody else "No custody events",
         bool(custody), False),
    ]
    if can_analyze:
        steps += [
            ("scan", "AI screened",
             f"MVSS-Net · {_fcd_short(analyses[0]['analysis_id'], 4, 4)}" if analyses else "Run in AI Screening",
             bool(analyses), False),
            ("file", "Findings recorded",
             findings[0]["conclusion"] if findings else "Record in AI Screening",
             bool(findings), False),
            ("seal", "Report available",
             "Download from AI Screening" if (analyses and findings) else "Needs analysis and findings",
             bool(analyses and findings), False),
        ]
    return steps


def show_dashboard_metrics(user):
    """Batch 4 command center. Same data sources and permissions as before; display only."""
    import html as _html

    role = user.get("role", "")
    can_view_evidence = has_permission(role, "view_evidence")
    can_view_audit = has_permission(role, "view_audit")
    can_analyze = has_permission(role, "analyze_image")
    role_label = ROLE_LABELS.get(role, role)

    latest = query_all(
        """SELECT evidence_id, case_id, original_filename, sha256, registered_at
           FROM evidence ORDER BY registered_at DESC LIMIT 1"""
    ) if can_view_evidence else []

    steps = _fcd_case_steps(latest[0], can_analyze) if latest else []
    done = sum(1 for s in steps if s[3])
    remaining = len(steps) - done

    if latest:
        case_id = _html.escape(str(latest[0]["case_id"]))
        subtitle = (f"{case_id} has {remaining} step{'s' if remaining != 1 else ''} left to complete its record."
                    if remaining else f"Every recorded step for {case_id} is complete.")
    else:
        subtitle = f"{_html.escape(str(role_label))} workspace."

    st.markdown(
        '<div style="margin:22px 0 22px">'
        '<div class="fcd-ov">Command center</div>'
        f'<div class="fcd-mut" style="margin-top:6px">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )

    if not can_view_evidence and not can_analyze:
        if can_view_audit:
            st.markdown(
                '<div class="fcd-pn" style="padding:22px 26px"><div class="fcd-k">Audit access</div>'
                '<div style="font-size:18px;font-weight:600;margin-top:6px">Enabled</div>'
                '<div class="fcd-mut" style="font-size:13px">Role permission</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Your role-specific workspace is ready.")
        return

    # ---- row 1: evidence trail + progress ring
    if latest and steps:
        parts = []
        first_open = next((i for i, s in enumerate(steps) if not s[3]), None)
        for i, (icon, title, sub, is_done, failed) in enumerate(steps):
            if failed:
                state, tag = "fail", '<span class="fcd-pill fcd-bad">Check</span>'
            elif is_done:
                state, tag = "done", '<span class="fcd-pill fcd-ok">Done</span>'
            elif i == first_open:
                state, tag = "now", '<span class="fcd-pill fcd-vio"><i></i>Next</span>'
            else:
                state, tag = "lock", '<span class="fcd-pill fcd-neu">Open</span>'
            node_icon = _fcd_icon("x" if failed else ("lock" if state == "lock" else icon), 24)
            parts.append(
                f'<div class="fcd-step"><div class="fcd-node {state}">{node_icon}</div>'
                f'<b class="{"dim" if state == "lock" else ""}">{_html.escape(title)}</b>'
                f'<small>{_html.escape(str(sub))}</small>{tag}</div>'
            )
            if i < len(steps) - 1:
                nxt = steps[i + 1]
                if nxt[3]:
                    line = "background:#5FE0C3;box-shadow:0 0 10px rgba(95,224,195,.6)"
                elif i + 1 == first_open:
                    line = "background:linear-gradient(90deg,#5FE0C3,#8B7CFF);box-shadow:0 0 10px rgba(139,124,255,.5)"
                else:
                    line = "background:repeating-linear-gradient(90deg,rgba(255,255,255,.18) 0 6px,transparent 6px 12px)"
                parts.append(f'<div class="fcd-link" style="{line}"></div>')

        pct = round(100 * done / len(steps))
        next_step = steps[first_open][1] if first_open is not None else None
        next_hint = steps[first_open][2] if first_open is not None else ""

        chain = _fcd_chain()
        events = int(chain.get("event_count") or 0)
        bars = min(events, 12) or 1
        bar_color = "#5FE0C3;box-shadow:0 0 10px rgba(95,224,195,.6)" if chain.get("valid") else "#FF8C7E"
        bar_html = "".join('<span style="background:' + bar_color + '"></span>' for _ in range(bars))
        chain_text = (f"{events} / {events} links intact" if chain.get("valid")
                      else _html.escape(str(chain.get("message", "Chain check failed"))))

        c1, c2 = st.columns([1.55, 1], gap="medium")
        with c1:
            st.markdown(
                '<div class="fcd-pn" style="padding:26px 28px">'
                '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:22px">'
                f'<div><div class="fcd-k">Active case</div><div style="font-size:20px;font-weight:600;margin-top:4px">'
                f'{_html.escape(str(latest[0]["case_id"]))} · evidence trail</div></div>'
                f'<span class="fcd-pill fcd-vio" style="height:28px;padding:0 12px"><i></i>{done} of {len(steps)} steps</span></div>'
                f'<div class="fcd-trail">{"".join(parts)}</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            ring = _fcd_ring(pct, 128, 10,
                             f'<span class="fcd-serif" style="font-size:40px">{pct}%</span><span class="fcd-k">progress</span>')
            next_block = (
                f'<div><div class="fcd-k">Next step</div><div style="font-weight:600;font-size:15px;margin-top:3px">'
                f'{_html.escape(next_step)}</div><div style="font-size:12.5px;color:#7C889C">{_html.escape(str(next_hint))}</div></div>'
                if next_step else
                '<div><div class="fcd-k">Next step</div><div style="font-weight:600;font-size:15px;margin-top:3px">'
                'All steps recorded</div></div>'
            )
            st.markdown(
                '<div class="fcd-pn" style="padding:26px;display:flex;flex-wrap:wrap;gap:22px;align-items:center">'
                f'{ring}<div style="display:flex;flex-direction:column;gap:14px;flex:1;min-width:min(170px,100%)">'
                f'{next_block}'
                '<div><div class="fcd-k">Chain health</div>'
                f'<div class="fcd-bars">{bar_html}</div>'
                f'<div style="font-size:12px;color:{"#7CF2D6" if chain.get("valid") else "#FF8C7E"};margin-top:6px">{chain_text}</div>'
                '</div></div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)

    # ---- row 2: next steps, recent AI analyses, workspace
    panels = []

    if steps:
        open_steps = [s for s in steps if not s[3]]
        tab_for = {"Integrity verified": "Verify Integrity", "Custody logged": "Chain of Custody",
                   "AI screened": "AI Screening", "Findings recorded": "AI Screening",
                   "Report available": "AI Screening"}
        tone = {"shield": "fcd-ok", "link": "fcd-info", "scan": "fcd-vio", "file": "fcd-vio", "seal": "fcd-warn"}
        rows = "".join(
            f'<div class="fcd-row"><span class="fcd-sq fcd-pill {tone.get(s[0], "fcd-neu")}" style="padding:0">{_fcd_icon(s[0], 18)}</span>'
            f'<div style="flex:1"><div style="font-weight:500">{_html.escape(s[1])}</div>'
            f'<div style="font-size:12px;color:#7C889C">{_html.escape(str(s[2]))}</div></div>'
            f'<span class="fcd-pill fcd-neu">{_html.escape(tab_for.get(s[1], ""))}</span></div>'
            for s in open_steps
        ) or '<div class="fcd-row"><div style="color:#7CF2D6">Nothing pending for this case.</div></div>'
        panels.append(
            '<div class="fcd-pn" style="padding:22px 26px">'
            '<div style="display:flex;justify-content:space-between;align-items:center">'
            '<span class="fcd-k">Pending actions</span>'
            f'<span class="fcd-pill fcd-vio"><i></i>{len(open_steps)} open</span></div>{rows}</div>'
        )

    if can_analyze:
        recent_analyses = query_all(
            """SELECT analysis_id, evidence_id, model_name, model_response_score, analyzed_at
               FROM analysis_records ORDER BY analyzed_at DESC LIMIT 5"""
        ) if _fcd_table_exists("analysis_records") else []
        rows = "".join(
            f'<div class="fcd-row" style="padding:11px 0"><span class="fcd-sq fcd-pill fcd-vio" style="width:30px;height:30px;border-radius:9px;padding:0">{_fcd_icon("scan", 15)}</span>'
            f'<span class="fcd-mono" style="font-size:12.5px;flex:1" title="{_html.escape(str(r["analysis_id"]))}">{_html.escape(_fcd_short(r["analysis_id"], 4, 6))}</span>'
            f'<span class="fcd-mono" style="font-size:11.5px;color:#9AA5B6">{float(r["model_response_score"]):.4f}</span>'
            f'<span class="fcd-mono" style="font-size:11.5px;color:#7C889C" title="{_html.escape(str(r["evidence_id"]))}">{_html.escape(_fcd_short(r["evidence_id"], 4, 4))}</span></div>'
            for r in recent_analyses
        ) or '<div class="fcd-row"><div style="color:#7C889C">No AI analyses have been recorded yet.</div></div>'
        panels.append(
            '<div class="fcd-pn" style="padding:22px 26px">'
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
            '<span class="fcd-k">Recent AI analyses</span><span class="fcd-mono" style="font-size:11px;color:#7C889C">MVSS-Net</span></div>'
            f'{rows}</div>'
        )

    stats = []
    if can_view_evidence:
        stats.append(("Evidence", query_all("SELECT COUNT(*) AS n FROM evidence")[0]["n"], "#E8EDF5"))
        stats.append(("Custody", query_all("SELECT COUNT(*) AS n FROM custody_events")[0]["n"], "#7CF2D6"))
    if can_analyze:
        stats.append(("Analyses", query_all("SELECT COUNT(*) AS n FROM analysis_records")[0]["n"], "#B3A9FF"))
    feed = ""
    if can_view_evidence:
        recent_custody = query_all(
            """SELECT event_id, evidence_id, actor, action, event_time
               FROM custody_events ORDER BY event_time DESC LIMIT 4"""
        )
        kind = {"REGISTERED": "fcd-neu", "TRANSFERRED": "fcd-warn", "ACCEPTED": "fcd-ok"}
        feed = "".join(
            '<div class="fcd-row" style="padding:11px 0">'
            f'<span class="fcd-mono" style="width:30px;height:30px;border-radius:9px;background:rgba(255,255,255,.05);display:flex;align-items:center;justify-content:center;font-size:11px;color:#9AA5B6;flex:none">#{e["event_id"]}</span>'
            '<div style="flex:1;min-width:0"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
            f'<span class="fcd-pill {kind.get(e["action"], "fcd-info")}"><i></i>{_html.escape(str(e["action"]).replace("_", " ").capitalize())}</span>'
            f'<span class="fcd-mono" style="font-size:12px" title="{_html.escape(str(e["evidence_id"]))}">{_html.escape(_fcd_short(e["evidence_id"], 4, 4))}</span></div>'
            f'<div style="font-size:12px;color:#7C889C">{_html.escape(str(e["actor"]))}</div></div>'
            f'<span class="fcd-mono" style="font-size:11.5px;color:#7C889C">{_fcd_time(e["event_time"])}</span></div>'
            for e in recent_custody
        )
    stat_html = "".join(
        f'<div><div class="fcd-serif" style="font-size:44px;color:{c}">{v}</div><div class="fcd-k">{label}</div></div>'
        for label, v, c in stats
    )
    panels.append(
        '<div class="fcd-pn" style="padding:22px 26px"><span class="fcd-k">Workspace</span>'
        f'<div class="fcd-stats">{stat_html}</div>{feed}</div>'
    )

    columns = st.columns(len(panels), gap="medium")
    for column, panel in zip(columns, panels):
        with column:
            st.markdown(panel, unsafe_allow_html=True)


def show_recent_evidence(user):
    """Recent evidence activity, kept from the previous dashboard (same query and permission)."""
    import html as _html

    if not has_permission(user["role"], "view_evidence"):
        return
    recent = query_all(
        """SELECT evidence_id, case_id, original_filename, registered_at
           FROM evidence ORDER BY registered_at DESC LIMIT 5"""
    )
    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    if not recent:
        st.info("No evidence has been registered yet.")
        return
    rows = "".join(
        f'<tr><td class="fcd-mono" style="font-size:12px">{_html.escape(str(r["evidence_id"]))}</td>'
        f'<td>{_html.escape(str(r["case_id"]))}</td>'
        f'<td style="color:#9AA5B6">{_html.escape(str(r["original_filename"]))}</td>'
        f'<td class="fcd-mono" style="font-size:12px;color:#9AA5B6">{_html.escape(str(r["registered_at"])[:16].replace("T", " "))}</td></tr>'
        for r in recent
    )
    st.markdown(
        '<div class="fcd-pn" style="padding:14px 12px;overflow-x:auto"><div class="fcd-k" style="padding:6px 14px 4px">Recent evidence activity</div>'
        '<table class="fcd-tbl"><thead><tr><th>Evidence ID</th><th>Case ID</th><th>Filename</th><th>Registered</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
        '<div style="height:22px"></div>',
        unsafe_allow_html=True,
    )


def first_admin_setup():
    st.title("ForenChain-DL - Initial Setup")
    st.info("Create the first Platform Administrator account.")

    with st.form("initial_admin_form"):
        username = st.text_input("Administrator username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button(
            "Create Administrator",
            width="stretch",
        )

    if submitted:
        if password != confirm:
            st.error("Passwords do not match.")
        else:
            try:
                create_initial_admin(username, password)
                st.success("Administrator created. Please sign in.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))



def login_screen():
    """Batch 4 sign-in page. Same authentication flow; presentation only."""
    import hashlib as _hashlib

    # Decorative fingerprint derived from the product name (not from any evidence).
    deco_hash = _hashlib.sha256(b"ForenChain-DL").hexdigest()
    deco_chunks = " ".join(deco_hash[i:i + 8] for i in range(0, 64, 8))
    ramp = ["#0F2A26", "#17584B", "#2FB592", "#7CF2D6"]
    glyph_cells = "".join(
        f'<b style="background:{ramp[int(c, 16) // 4]}"></b>' for c in deco_hash
    )

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Tinos:ital@0;1&display=swap');

        div[data-testid="stForm"]:has(input[aria-label="Username"]) [data-testid="InputInstructions"] {
            display: none !important;
        }

        /* page */
        .stApp:has(.fc-login2-marker), .stApp:has(.fc-login2-marker) [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(900px 520px at 12% -8%, rgba(95,224,195,.13), transparent 60%),
                radial-gradient(800px 520px at 100% 0%, rgba(139,124,255,.12), transparent 60%),
                radial-gradient(700px 500px at 60% 120%, rgba(95,224,195,.06), transparent 60%),
                #05080E !important;
        }
        .stApp:has(.fc-login2-marker) [data-testid="stHeader"] { background: transparent !important; }
        .stApp:has(.fc-login2-marker) [data-testid="stToolbar"],
        .stApp:has(.fc-login2-marker) [data-testid="stDecoration"] { display:none !important; }
        .stApp:has(.fc-login2-marker) .block-container {
            max-width: 1280px !important;
            padding: 4vh 4.5rem 2rem !important;
        }
        .stApp:has(.fc-login2-marker) [data-testid="stHorizontalBlock"]:has(.fc2-glyph-anchor) {
            min-height: 82vh; align-items: center !important;
        }
        [data-testid="stElementContainer"]:has(.fc-login2-marker),
        .element-container:has(.fc-login2-marker) { display: none; }

        /* left hero */
        .fc2-brand { display:flex; align-items:center; gap:10px; margin-bottom:26px; }
        .fc2-brand b { font: 600 18px "IBM Plex Sans", "Segoe UI", sans-serif; color:#E8EDF5; }
        .fc2-tag { font: 500 10.5px "IBM Plex Mono", Consolas, monospace; color:#7C889C;
                   border:1px solid rgba(255,255,255,.15); border-radius:5px; padding:1px 6px; }
        .fc2-eyebrow { font: 500 11.5px "IBM Plex Mono", Consolas, monospace; letter-spacing:.14em;
                       text-transform:uppercase; color:#7CF2D6; margin-bottom:22px; }
        .fc2-headline { font-family:"Times New Roman", Tinos, Times, serif !important; font-weight:400 !important;
                        font-size: clamp(36px, 4vw, 58px); line-height:1.05; letter-spacing:-.01em; max-width:560px;
                        color:#E8EDF5; margin:0 0 30px 0; }
        .fc2-headline em { font-style:italic;
                           background:linear-gradient(90deg,#7CF2D6,#B3A9FF);
                           -webkit-background-clip:text; background-clip:text; color:transparent; }
        .fc2-pills { display:flex; flex-wrap:wrap; gap:12px; }
        .fc2-pill { display:inline-flex; align-items:center; gap:7px; height:30px; padding:0 14px;
                    border-radius:999px; font: 500 12.5px "IBM Plex Sans", "Segoe UI", sans-serif; }
        .fc2-pill i { width:6px; height:6px; border-radius:50%; background:currentColor; box-shadow:0 0 8px currentColor; }
        .fc2-ok { background:rgba(95,224,195,.12); color:#7CF2D6; }
        .fc2-vio { background:rgba(139,124,255,.14); color:#B3A9FF; }
        .fc2-info { background:rgba(122,167,255,.13); color:#9DBDFF; }

        /* decorative fingerprint behind the card + hash footer */
        .fc2-glyph-anchor { position:relative; height:0; max-width:420px; margin:0 auto; z-index:0; }
        .fc2-glyph { position:absolute; top:-38px; right:-46px; width:250px; opacity:.2;
                     display:grid; grid-template-columns:repeat(8,1fr); gap:6px; pointer-events:none; }
        [data-testid="stColumn"]:has(.fc2-glyph-anchor), [data-testid="column"]:has(.fc2-glyph-anchor),
        [data-testid="stColumn"]:has(.fc2-glyph-anchor) *, [data-testid="column"]:has(.fc2-glyph-anchor) * { overflow:visible !important; }
        [data-testid="stElementContainer"]:has(.fc2-glyph-anchor), .element-container:has(.fc2-glyph-anchor) { height:0; margin:0; }
        .fc2-glyph b { aspect-ratio:1; border-radius:3px; }
        .fc2-hash { margin-top:6px; pointer-events:none; overflow-wrap:anywhere;
                    font: 400 11px "IBM Plex Mono", Consolas, monospace; color:#3A475C; word-spacing:8px; }

        /* sign-in card (the real Streamlit form) */
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] {
            position:relative; z-index:1;
            max-width:420px; margin-left:auto; margin-right:auto;
            background:linear-gradient(180deg, rgba(18,24,36,.92), rgba(10,14,22,.95)) !important;
            border:1px solid rgba(255,255,255,.085) !important;
            border-radius:20px !important;
            padding:30px 34px 24px !important;
            box-shadow:0 40px 80px -40px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.06);
            backdrop-filter:blur(18px);
        }
        .fc2-card-k { font: 500 10.5px "IBM Plex Mono", Consolas, monospace; letter-spacing:.12em;
                      text-transform:uppercase; color:#7C889C; }
        .fc2-card-title { font-family:"Times New Roman", Tinos, Times, serif !important; font-size:42px; line-height:1;
                          color:#E8EDF5; margin:8px 0 4px; }
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] [data-testid="stWidgetLabel"] p {
            font: 500 10.5px "IBM Plex Mono", Consolas, monospace !important;
            letter-spacing:.12em; text-transform:uppercase; color:#7C889C !important;
        }
        /* inputs: React Aria (newer Streamlit) and BaseWeb (older Streamlit) */
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] [data-testid="stTextInputRootElement"],
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] [data-baseweb="input"] {
            background:rgba(255,255,255,.04) !important;
            border:1px solid rgba(255,255,255,.12) !important;
            border-radius:12px !important;
            min-height:48px;
        }
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] [data-baseweb="base-input"],
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] input {
            background:transparent !important; border:none !important;
            color:#E8EDF5 !important; font: 400 15px "IBM Plex Sans", "Segoe UI", sans-serif !important;
        }
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] [data-testid="stTextInputRootElement"]:focus-within,
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] [data-baseweb="input"]:focus-within {
            border-color:#5FE0C3 !important;
            box-shadow:0 0 0 4px rgba(95,224,195,.12) !important;
        }
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] button[kind^="primary"],
        .stApp:has(.fc-login2-marker) [data-testid="stForm"] [data-testid^="stBaseButton-primary"],
        .stApp:has(.fc-login2-marker) [data-testid="stFormSubmitButton"] > button {
            min-height:50px; margin-top:6px;
            background:linear-gradient(180deg,#7CF2D6,#3CCFAE) !important;
            color:#04241D !important; border:none !important; border-radius:12px !important;
            box-shadow:0 10px 30px -10px rgba(95,224,195,.7), inset 0 1px 0 rgba(255,255,255,.5) !important;
        }
        .stApp:has(.fc-login2-marker) [data-testid="stFormSubmitButton"] button p,
        .stApp:has(.fc-login2-marker) [data-testid="stFormSubmitButton"] button span {
            color:#04241D !important; font: 600 15px "IBM Plex Sans", "Segoe UI", sans-serif !important;
        }
        .stApp:has(.fc-login2-marker) [data-testid="stFormSubmitButton"] button p::before {
            content:""; display:inline-block; width:15px; height:15px; margin-right:9px; vertical-align:-2px;
            background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2304241D' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3'/></svg>") no-repeat center / contain;
        }
        .fc2-card-foot { display:flex; justify-content:space-between; margin:4px 0 6px;
                         font: 400 12px "IBM Plex Sans", "Segoe UI", sans-serif; color:#7C889C; }
        .fc2-card-foot span:last-child { font-family:"IBM Plex Mono", Consolas, monospace; letter-spacing:.06em; }

        @media (max-width: 1200px) {
            .fc2-glyph { width:210px; right:-30px; top:-30px; gap:5px; }
        }
        @media (max-width: 900px) {
            .stApp:has(.fc-login2-marker) .block-container { padding: 6vh 1.2rem 2rem !important; }
            .fc2-glyph-anchor { display:none; }
            .stApp:has(.fc-login2-marker) [data-testid="stHorizontalBlock"]:has(.fc2-glyph-anchor) { min-height: 0; }
            .fc2-headline { font-size:44px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<span class="fc-login2-marker"></span>', unsafe_allow_html=True)

    logo = (
        '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#5FE0C3" '
        'stroke-width="1.8" aria-hidden="true"><rect x="3" y="3" width="11" height="11" rx="2.5"/>'
        '<rect x="10" y="10" width="11" height="11" rx="2.5"/></svg>'
    )

    left, right = st.columns([1.15, 1], gap="large", vertical_alignment="center")

    with left:
        st.markdown(
            f"""
            <div class="fc2-brand">{logo}<b>ForenChain</b><span class="fc2-tag">DL</span></div>
            <div class="fc2-eyebrow">Digital evidence integrity · AI image forensics</div>
            <div class="fc2-headline" role="heading" aria-level="1">Every file<br>fingerprinted.<br><em>Every hand-off on record.</em></div>
            <div class="fc2-pills">
                <span class="fc2-pill fc2-ok"><i></i>SHA-256 integrity</span>
                <span class="fc2-pill fc2-vio"><i></i>Chain of custody</span>
                <span class="fc2-pill fc2-info"><i></i>MVSS-Net screening</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            f'<div class="fc2-glyph-anchor" aria-hidden="true"><div class="fc2-glyph">{glyph_cells}</div></div>',
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            st.markdown(
                '<div class="fc2-card-k">Secure sign in</div>'
                '<div class="fc2-card-title">Welcome back</div>',
                unsafe_allow_html=True,
            )
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "Sign in",
                type="primary",
                width="stretch",
            )
            st.markdown(
                '<div class="fc2-card-foot"><span>Authorized personnel only</span>'
                '<span>LOCAL DB</span></div>',
                unsafe_allow_html=True,
            )

        if submitted:
            user = authenticate_user(username, password)
            if user is None:
                st.error("Invalid username or password, or account inactive.")
            else:
                st.session_state["user"] = user
                st.rerun()

    st.markdown(
        f'<div class="fc2-hash" aria-hidden="true">{deco_chunks}</div>',
        unsafe_allow_html=True,
    )


def password_change_screen(user):
    st.title("Change Your Password")
    st.info("You must change your initial password before continuing.")

    with st.form("forced_password_change"):
        current = st.text_input("Initial password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Change Password")

    if submitted:
        if new != confirm:
            st.error("New passwords do not match.")
        else:
            try:
                change_password(user["user_id"], current, new)
                st.session_state["user"] = authenticate_user(
                    user["username"], new
                )
                st.success("Password changed successfully.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def user_management(user):
    st.header("User and Role Management")

    if not has_permission(user["role"], "manage_users"):
        st.error("You do not have permission to manage users.")
        return

    with st.form("create_user_form"):
        username = st.text_input("New username")
        password = st.text_input("Initial password", type="password")
        confirm = st.text_input("Confirm initial password", type="password")
        role = st.selectbox(
            "Assign role",
            options=sorted(ROLES),
            format_func=lambda item: ROLE_LABELS.get(item, item),
        )
        submitted = st.form_submit_button("Create Account")

    if submitted:
        if password != confirm:
            st.error("Passwords do not match.")
        else:
            try:
                create_user(user["user_id"], username, password, role)
                st.success(
                    f"Created {username} as "
                    f"{ROLE_LABELS.get(role, role)}. "
                    "They must change the initial password at first login."
                )
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))


    st.divider()
    st.subheader("Existing Accounts")

    accounts = query_all(
        """
        SELECT user_id, username, role, active,
               must_change_password, created_at
        FROM users
        ORDER BY user_id
        """
    )

    # Hide the RBAC test account from this display only.
    accounts = [
        account for account in accounts
        if account["username"].strip().casefold() != "rbac_test_user"
    ]

    if accounts:
        st.dataframe(
            [
                {
                    "Username": account["username"],
                    "Role": ROLE_LABELS.get(account["role"], account["role"]),
                    "Status": "Active" if account["active"] else "Inactive",
                    "Password Change Required": (
                        "Yes" if account["must_change_password"] else "No"
                    ),
                    "Created": account["created_at"],
                }
                for account in accounts
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No accounts to display.")

def register_evidence_screen(user):
    st.header("Register Evidence")

    if not has_permission(user["role"], "register_evidence"):
        st.warning("Your role cannot register evidence.")
        return

    uploaded = st.file_uploader(
        "Upload evidence image (maximum 25 MB)",
        max_upload_size=25,
        type=["jpg", "jpeg", "png", "bmp", "tif", "tiff", "webp"],
        key="register_upload",
    )
    case_id = st.text_input("Case ID")

    if uploaded:
        try:
            if uploaded.size > 25 * 1024 * 1024:
                st.error("File exceeds the 2 MB upload limit.")
                return
            image = Image.open(uploaded)
            image.verify()
            uploaded.seek(0)
            image = Image.open(uploaded)
            image.load()
            st.image(image, caption=uploaded.name, width="stretch")
            st.caption(f"Image dimensions: {image.width} x {image.height}")
        except Exception:
            st.error("The uploaded file is not a valid supported image.")
            return

        file_bytes = uploaded.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        duplicates = find_duplicate_evidence(file_hash)

        if duplicates:
            st.warning(
                f"This file matches {len(duplicates)} existing evidence "
                "record(s) by SHA-256."
            )
            for duplicate in duplicates:
                st.write(
                    f"{duplicate['evidence_id']} | "
                    f"Case: {duplicate['case_id']}"
                )
            confirm_duplicate = st.checkbox(
                "I confirm that registering this identical file again is intentional."
            )
        else:
            confirm_duplicate = False

        if st.button("Register Evidence", type="primary"):
            try:
                result = register_evidence(
                    file_bytes=file_bytes,
                    filename=uploaded.name,
                    case_id=case_id,
                    image_width=image.width,
                    image_height=image.height,
                    confirm_duplicate=confirm_duplicate,
                )
                if result["status"] == "DUPLICATE_FOUND":
                    st.warning(
                        "Duplicate found. Confirm the checkbox and register again."
                    )
                else:
                    record_custody_event(
                        evidence_id=result["evidence_id"],
                        actor_user_id=user["user_id"],
                        action="REGISTERED",
                        details="Evidence registered",
                    )
                    st.success("Evidence registered successfully.")
                    st.code(result["evidence_id"])
                    st.write("SHA-256")
                    st.code(result["sha256"])
            except (ValueError, OSError) as exc:
                st.error(str(exc))


_FCI_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Tinos:ital@0;1&display=swap');
.fci-ov { font:500 11px "IBM Plex Mono",Consolas,monospace; letter-spacing:.16em; text-transform:uppercase; color:#7CF2D6; }
.fci-h1 { font-family:"Times New Roman",Tinos,Times,serif !important; font-weight:400; font-size:clamp(34px,3.6vw,52px);
          line-height:1.05; letter-spacing:-.015em; color:#E8EDF5; margin:8px 0 6px; }
.fci-sub { color:#9AA5B6; font:400 15px "IBM Plex Sans","Segoe UI",sans-serif; margin-bottom:14px; }
.fci-k { font:500 10.5px "IBM Plex Mono",Consolas,monospace; letter-spacing:.12em; text-transform:uppercase; color:#7C889C; }
.fci-pn { background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.018));
          border:1px solid rgba(255,255,255,.085); border-radius:20px; color:#E8EDF5;
          box-shadow:0 40px 80px -40px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.06);
          font-family:"IBM Plex Sans","Segoe UI",sans-serif; box-sizing:border-box; }
.fci-stage { position:relative; overflow:hidden; padding:36px 32px; margin-top:6px; }
.fci-glow { position:absolute; inset:0; pointer-events:none; }
.fci-grid3 { position:relative; display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:28px; }
.fci-side { display:flex; flex-direction:column; align-items:center; gap:14px; min-width:0; }
.fci-gwrap { padding:14px; border-radius:20px; background:rgba(95,224,195,.05); border:1px solid rgba(95,224,195,.25); }
.fci-gwrap.bad { background:rgba(255,122,107,.05); border-color:rgba(255,122,107,.3); }
.fci-glyph { display:grid; grid-template-columns:repeat(8,1fr); }
.fci-glyph b { aspect-ratio:1; border-radius:3px; }
.fci-hash { font:400 12px/1.75 "IBM Plex Mono",Consolas,monospace; color:#9AA5B6; text-align:center; max-width:260px; word-spacing:6px; }
.fci-hash .x { color:#FF8C7E; }
.fci-mid { display:flex; flex-direction:column; align-items:center; gap:14px; }
.fci-ring { position:relative; }
.fci-ring-in { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.fci-num { font-family:"Times New Roman",Tinos,Times,serif !important; font-size:58px; line-height:1; }
.fci-pill { display:inline-flex; align-items:center; gap:8px; height:34px; padding:0 18px; border-radius:999px;
            font:500 13px "IBM Plex Sans","Segoe UI",sans-serif; }
.fci-ok { background:rgba(95,224,195,.12); color:#7CF2D6; }
.fci-bad { background:rgba(255,122,107,.12); color:#FF8C7E; }
.fci-warn { background:rgba(242,184,75,.12); color:#F5C66A; }
.fci-info { background:rgba(122,167,255,.13); color:#9DBDFF; }
.fci-cards { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; margin:18px 0 14px; }
.fci-card { padding:18px 22px; display:flex; gap:14px; align-items:center; }
.fci-sq { width:44px; height:44px; border-radius:14px; display:flex; align-items:center; justify-content:center; flex:none; }
.fci-card b { display:block; font-weight:600; font-size:14.5px; color:#E8EDF5; }
.fci-card span.s { display:block; font-size:12.5px; color:#7C889C; overflow-wrap:anywhere; }
.fci-status { padding:22px 26px; display:flex; gap:16px; align-items:center; margin-top:6px; }
.fci-form-note { font:400 12px "IBM Plex Sans","Segoe UI",sans-serif; color:#7C889C; margin-top:-4px; }
.st-key-fci_inputs { background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.015));
                     border:1px solid rgba(255,255,255,.085); border-radius:18px; padding:18px 20px 8px; }
@media (max-width: 1000px) {
  .fci-grid3 { grid-template-columns:1fr; }
  .fci-cards { grid-template-columns:1fr; }
}
</style>
"""

_FCI_ICONS = {
    "shield": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.5 2.5 4.5-5",
    "check": "M5 12.5l4.5 4.5L19 7.5",
    "lock": "M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3",
    "scan": "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M8 12h8",
    "x": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9 9l6 6M15 9l-6 6",
    "alert": "M12 3l10 18H2zM12 10v5M12 18h.01",
    "file": "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
}


def _fci_icon(name, size=20, stroke=1.8):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'<path d="{_FCI_ICONS[name]}"/></svg>'
    )


def _fci_glyph(sha256, size, other=None):
    """8x8 fingerprint of a SHA-256 value (display only). Cells that differ from `other` are red."""
    ramp = ["#0F2A26", "#17584B", "#2FB592", "#7CF2D6"]
    bad = ["#2A1210", "#5A231C", "#B8473A", "#FF8C7E"]
    value = str(sha256 or "").lower()[:64].ljust(64, "0")
    ref = str(other or "").lower()[:64].ljust(64, "0") if other else None
    cells = []
    for i, ch in enumerate(value):
        level = int(ch, 16) // 4 if ch in "0123456789abcdef" else 0
        differs = ref is not None and ref[i] != ch
        color = (bad if differs else ramp)[level]
        glow = ";box-shadow:0 0 10px rgba(124,242,214,.55)" if level == 3 and not differs else ""
        cells.append(f'<b style="background:{color}{glow}"></b>')
    return f'<div class="fci-glyph" style="width:{size}px;gap:{max(2, size // 55)}px">{"".join(cells)}</div>'


def _fci_hash_html(value, other):
    import html as _html
    value = str(value or "")
    other = str(other or "")
    groups = []
    for i in range(0, len(value), 8):
        part = value[i:i + 8]
        cls = "" if part == other[i:i + 8] else ' class="x"'
        groups.append(f"<span{cls}>{_html.escape(part)}</span>")
    return " ".join(groups) or "—"


def _fci_ring(pct, size, stroke, colors, inner):
    import math
    r = (size - stroke) / 2
    c = 2 * math.pi * r
    d = c * max(0.0, min(100.0, pct)) / 100
    return (
        f'<div class="fci-ring" style="width:{size}px;height:{size}px">'
        f'<svg width="{size}" height="{size}" style="transform:rotate(-90deg)">'
        f'<defs><linearGradient id="fciRing" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{colors[0]}"/><stop offset="1" stop-color="{colors[1]}"/></linearGradient></defs>'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="rgba(255,255,255,.07)" stroke-width="{stroke}"/>'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="url(#fciRing)" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-dasharray="{d} {c}" style="filter:drop-shadow(0 0 10px {colors[0]}88)"/>'
        f'</svg><div class="fci-ring-in">{inner}</div></div>'
    )


def _fci_head(placeholder, title, subtitle):
    import html as _html
    placeholder.markdown(
        _FCI_CSS
        + '<div class="fci-ov">Evidence workspace · Verify integrity</div>'
        + f'<div class="fci-h1">{_html.escape(title)}</div>'
        + f'<div class="fci-sub">{_html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def _fci_render_result(result, compared_label, can_analyze):
    """Presentation of a verify_evidence() result. Reads the result only."""
    import html as _html

    status = result.get("status", "UNKNOWN")
    registered = str(result.get("registered_hash") or "")
    current = str(result.get("current_hash") or "")

    if status in ("INTEGRITY_OK", "HASH_MISMATCH") and registered:
        ok = status == "INTEGRITY_OK"
        same = sum(1 for a, b in zip(registered.lower(), current.lower()) if a == b)
        total = max(len(registered), 1)
        colors = ("#5FE0C3", "#8B7CFF") if ok else ("#FF8C7E", "#F5C66A")
        glow = ("radial-gradient(500px 260px at 50% 50%, rgba(95,224,195,.16), transparent 70%)" if ok
                else "radial-gradient(500px 260px at 50% 50%, rgba(255,122,107,.14), transparent 70%)")
        num_color = "#7CF2D6" if ok else "#FF8C7E"
        ring = _fci_ring(
            100 * same / total, 220, 14, colors,
            f'<span class="fci-num" style="color:{num_color};text-shadow:0 0 30px {num_color}99">{same}/{total}</span>'
            '<span class="fci-k" style="margin-top:6px">characters match</span>',
        )
        pill = (f'<span class="fci-pill fci-ok">{_fci_icon("check", 15, 2.4)}Integrity verified</span>' if ok
                else f'<span class="fci-pill fci-bad">{_fci_icon("x", 15, 2)}Hash mismatch</span>')
        bad_cls = "" if ok else " bad"
        st.markdown(
            '<div class="fci-pn fci-stage">'
            f'<div class="fci-glow" style="background:{glow}"></div>'
            '<div class="fci-grid3">'
            '<div class="fci-side"><span class="fci-k">Registered</span>'
            f'<div class="fci-gwrap">{_fci_glyph(registered, 220)}</div>'
            f'<div class="fci-hash">{_fci_hash_html(registered, registered)}</div></div>'
            f'<div class="fci-mid">{ring}{pill}</div>'
            f'<div class="fci-side"><span class="fci-k">Recomputed</span>'
            f'<div class="fci-gwrap{bad_cls}">{_fci_glyph(current, 220, registered)}</div>'
            f'<div class="fci-hash">{_fci_hash_html(current, registered)}</div></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

        first = (
            f'<div class="fci-pn fci-card"><span class="fci-sq fci-ok">{_fci_icon("check", 20, 2.4)}</span>'
            f'<div><b>Integrity verified</b><span class="s">{_html.escape(compared_label)}</span></div></div>'
            if ok else
            f'<div class="fci-pn fci-card"><span class="fci-sq fci-bad">{_fci_icon("x", 20)}</span>'
            f'<div><b>File differs at byte level</b><span class="s">{total - same} of {total} characters differ · '
            f'{_html.escape(compared_label)}</span></div></div>'
        )
        second = (
            f'<div class="fci-pn fci-card"><span class="fci-sq fci-info">{_fci_icon("lock", 20)}</span>'
            '<div><b>SHA-256 · 256-bit</b><span class="s">Registered value is never modified</span></div></div>'
        )
        if ok and can_analyze:
            third = (
                f'<div class="fci-pn fci-card"><span class="fci-sq" style="background:rgba(139,124,255,.14);color:#B3A9FF">'
                f'{_fci_icon("scan", 20)}</span><div><b>Next: run AI screening</b>'
                '<span class="s">MVSS-Net · mvssnet_casia.pt · AI Screening tab</span></div></div>'
            )
        else:
            third = (
                f'<div class="fci-pn fci-card"><span class="fci-sq fci-warn">{_fci_icon("file", 20)}</span>'
                f'<div><b>Case {_html.escape(str(result.get("case_id", "—")))}</b>'
                f'<span class="s">{_html.escape(str(result.get("evidence_id", "")))}</span></div></div>'
            )
        st.markdown(f'<div class="fci-cards">{first}{second}{third}</div>', unsafe_allow_html=True)
    else:
        messages = {
            "NOT_FOUND": ("fci-warn", "alert", "Evidence not found", "No evidence record matches this ID."),
            "MISSING_FILE": ("fci-warn", "alert", "Evidence file missing",
                             "The record exists, but the stored evidence file could not be found."),
            "INVALID_PATH": ("fci-bad", "x", "Invalid evidence path",
                             "The stored path is outside the evidence directory, so verification was refused."),
        }
        cls, icon, title, body = messages.get(
            status, ("fci-warn", "alert", f"Verification result: {status}", "")
        )
        st.markdown(
            f'<div class="fci-pn fci-status"><span class="fci-sq {cls}">{_fci_icon(icon, 22)}</span>'
            f'<div><b style="font-size:16px">{_html.escape(title)}</b>'
            f'<div style="color:#9AA5B6;font-size:13.5px">{_html.escape(body)}</div></div></div>',
            unsafe_allow_html=True,
        )

    with st.expander("Raw verification result"):
        st.json(result)


def integrity_screen(user):
    head = st.empty()
    _fci_head(head, "Verify integrity.",
              "Recompute the SHA-256 fingerprint and compare it with the value sealed at registration.")

    if not has_permission(user["role"], "verify_integrity"):
        st.warning("Your role cannot verify integrity.")
        return

    with st.container(key="fci_inputs"):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        with c1:
            evidence_id = st.text_input("Registered Evidence ID", placeholder="EV-…")
        with c2:
            clicked = st.button("Verify Integrity", type="primary", width="stretch")
        alternate = st.checkbox(
            "Compare an external file against the registered hash"
        )
        uploaded = None
        if alternate:
            uploaded = st.file_uploader(
                "Upload file to compare",
                type=["jpg", "jpeg", "png", "bmp", "tif", "tiff", "webp"],
                key="integrity_upload",
            )

    if clicked:
        if not evidence_id.strip():
            st.error("Enter an Evidence ID.")
            return

        try:
            if alternate:
                if uploaded is None:
                    st.error("Upload a comparison file first.")
                    return

                temp_path = None
                import tempfile

                suffix = Path(uploaded.name).suffix
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=suffix, delete=False
                ) as temp:
                    temp.write(uploaded.getvalue())
                    temp_path = temp.name

                try:
                    result = verify_evidence(evidence_id, temp_path)
                finally:
                    Path(temp_path).unlink(missing_ok=True)
                compared = f"External file: {uploaded.name}"
            else:
                result = verify_evidence(evidence_id)
                compared = "Registered evidence file"

            status = result.get("status", "UNKNOWN")
            if status == "INTEGRITY_OK":
                _fci_head(head, "Fingerprint match.",
                          "Recomputed SHA-256 compared against the value sealed at registration.")
            elif status == "HASH_MISMATCH":
                _fci_head(head, "Fingerprint mismatch.",
                          "The recomputed SHA-256 differs from the value sealed at registration.")
            _fci_render_result(result, compared, has_permission(user["role"], "analyze_image"))
        except (ValueError, OSError, sqlite3.Error) as exc:
            st.error(str(exc))


def evidence_records_screen(user):
    st.markdown(
        """
        <div class="fc-register-hero">
            <div class="fc-register-kicker">EVIDENCE MANAGEMENT</div>
            <h2>Evidence Register</h2>
            <p>Search, filter, and review registered digital evidence and integrity metadata.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not has_permission(user["role"], "view_evidence"):
        st.warning("Your role cannot view evidence.")
        return

    rows = query_all(
        """
        SELECT evidence_id, case_id, original_filename, sha256,
               size_bytes, image_width, image_height, registered_at
        FROM evidence
        ORDER BY registered_at DESC
        """
    )

    if not rows:
        st.info("No evidence has been registered.")
        return

    total_bytes = sum(int(row.get("size_bytes") or 0) for row in rows)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total evidence", len(rows))
    m2.metric("Cases represented", len({str(r.get("case_id") or "") for r in rows}))
    m3.metric("Combined file size", f"{total_bytes / (1024 * 1024):.2f} MB")

    st.markdown("#### Find evidence")
    c1, c2 = st.columns([2, 1], gap="medium")
    with c1:
        search = st.text_input(
            "Search by ID, case, or filename",
            placeholder="Start typing to filter records...",
            key="evidence_register_search_v2",
        )
    with c2:
        cases = ["All cases"] + sorted({
            str(r.get("case_id") or "") for r in rows if r.get("case_id")
        })
        case_filter = st.selectbox(
            "Case filter", cases, key="evidence_register_case_v2"
        )

    query = search.strip().casefold()
    filtered = [
        r for r in rows
        if (case_filter == "All cases" or str(r.get("case_id") or "") == case_filter)
        and (
            not query
            or any(query in str(r.get(k) or "").casefold()
                   for k in ("evidence_id", "case_id", "original_filename"))
        )
    ]

    st.caption(f"Showing {len(filtered)} of {len(rows)} registered records.")

    if not filtered:
        st.info("No records match your search and filters.")
        return

    table_rows = [{
        "Evidence ID": r["evidence_id"],
        "Case ID": r["case_id"],
        "Filename": r["original_filename"],
        "Size (KB)": round(int(r.get("size_bytes") or 0) / 1024, 2),
        "Dimensions": f"{r.get('image_width')} × {r.get('image_height')}",
        "Registered": r["registered_at"],
    } for r in filtered]

    st.dataframe(table_rows, hide_index=True, width="stretch")

    st.markdown("#### Evidence details")
    selected_id = st.selectbox(
        "Select a record to inspect",
        options=[r["evidence_id"] for r in filtered],
        format_func=lambda eid: next(
            f"{r['evidence_id']} · {r['original_filename']}"
            for r in filtered if r["evidence_id"] == eid
        ),
        key="evidence_register_selected_v2",
    )

    record = get_evidence(selected_id)
    if record:
        a, b = st.columns(2, gap="medium")
        with a:
            st.markdown("**Record information**")
            st.write("Evidence ID:", record["evidence_id"])
            st.write("Case ID:", record["case_id"])
            st.write("Filename:", record["original_filename"])
            st.write("Registered:", record["registered_at"])
        with b:
            st.markdown("**File properties**")
            st.write("Size:", f"{record['size_bytes']} bytes")
            st.write(
                "Dimensions",
                f"{record['image_width']} × {record['image_height']}",
            )
        with st.expander("View SHA-256 fingerprint"):
            st.code(record["sha256"], language=None)



def custody_screen(user):
    st.markdown("""
    <div class="fc-custody-hero">
      <div class="fc-custody-eyebrow">EVIDENCE GOVERNANCE</div>
      <h1>Chain of Custody</h1>
      <p>Track evidence transfers, acceptance events, and custody-chain integrity.</p>
    </div>
    """, unsafe_allow_html=True)

    if not has_permission(user["role"], "view_evidence"):
        st.warning("Your role cannot view evidence.")
        return

    evidence_rows = query_all(
        """
        SELECT evidence_id, case_id, original_filename
        FROM evidence ORDER BY registered_at DESC
        """
    )
    if not evidence_rows:
        st.info("Register evidence before recording custody events.")
        return

    labels = {
        row["evidence_id"]:
        f"{row['evidence_id']} | {row['case_id']} | {row['original_filename']}"
        for row in evidence_rows
    }

    st.markdown("### Select evidence")
    evidence_id = st.selectbox(
        "Evidence record",
        options=list(labels),
        format_func=lambda item: labels[item],
        key="custody_evidence",
    )
    selected = next(row for row in evidence_rows if row["evidence_id"] == evidence_id)
    history = get_custody_history(evidence_id)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Registered evidence", len(evidence_rows))
    with c2:
        st.metric("Events for selected item", len(history))
    with c3:
        st.metric("Selected case", str(selected["case_id"]))

    with st.container(border=True):
        st.markdown("#### Selected evidence")
        st.write("**Filename:**", selected["original_filename"])
        st.write("**Evidence ID:**")
        st.code(evidence_id, language=None)
        st.write("**Case ID:**", selected["case_id"])

    can_transfer = has_permission(user["role"], "transfer_custody")
    can_accept = has_permission(user["role"], "accept_custody")

    if can_transfer or can_accept:
        st.markdown("### Record a custody event")
        st.caption("Record each transfer or acceptance against the selected evidence.")

        with st.container(border=True):
            with st.form("custody_event_form"):
                action_options = []
                if can_transfer:
                    action_options.append("TRANSFERRED")
                if can_accept:
                    action_options.append("ACCEPTED")

                action = st.selectbox(
                    "Event type",
                    options=action_options,
                    format_func=lambda item: {
                        "TRANSFERRED": "Transfer evidence",
                        "ACCEPTED": "Accept custody",
                    }.get(item, item),
                )

                if action == "TRANSFERRED":
                    recipient = st.text_input(
                        "Recipient username",
                        help="Must match an existing username exactly, ignoring case.",
                    )
                    notes = st.text_area("Transfer notes")
                    details = f"recipient={recipient.strip()}; notes={notes.strip()}"
                else:
                    notes = st.text_area("Acceptance notes")
                    details = notes.strip()

                submitted = st.form_submit_button(
                    "Record Custody Event", type="primary", use_container_width=True
                )

        if submitted:
            try:
                if action == "TRANSFERRED":
                    if not recipient.strip():
                        raise ValueError("Recipient username is required.")

                    users = query_all(
                        """
                        SELECT username, active
                        FROM users WHERE username = ? COLLATE NOCASE
                        """,
                        (recipient.strip(),),
                    )
                    if not users or users[0]["active"] != 1:
                        raise ValueError(
                            "Recipient must be an existing active account."
                        )

                    details = (
                        f"recipient={users[0]['username']}; "
                        f"notes={notes.strip()}"
                    )

                event = record_custody_event(
                    evidence_id=evidence_id,
                    actor_user_id=user["user_id"],
                    action=action,
                    details=details,
                )
                st.success("Custody event recorded.")
                st.json(event)
            except (ValueError, PermissionError, sqlite3.Error) as exc:
                st.error(str(exc))

    st.markdown("### Custody history")
    if history:
        for index, event in enumerate(history, start=1):
            action_value = str(event.get("action", "CUSTODY EVENT")).replace("_", " ")
            with st.container(border=True):
                left, right = st.columns([3, 1])
                with left:
                    st.markdown(f"**Event {index} · {action_value}**")
                with right:
                    st.caption("Recorded event")
                for key, value in event.items():
                    st.write(f"**{key.replace('_', ' ').title()}:** {value}")
    else:
        st.info("No custody events recorded for this evidence yet.")

    if has_permission(user["role"], "view_audit"):
        st.markdown("### Global custody-chain verification")
        st.caption("Validate the complete custody chain, not only the selected evidence.")
        if st.button("Verify Complete Global Custody Chain", type="primary"):
            result = verify_custody_chain()
            if result["valid"]:
                st.success(result["message"])
            else:
                st.error(result["message"])
            st.json(result)


@st.cache_resource
def load_forensics():
    return MVSSForensics()



def make_response_heatmap(response):
    """Create a display-only, percentile-normalized color visualization."""
    from PIL import Image

    values = np.asarray(response, dtype=np.float32)
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)

    low, high = np.percentile(values, [2, 99])
    if high <= low:
        normalized = np.zeros_like(values, dtype=np.float32)
    else:
        normalized = np.clip((values - low) / (high - low), 0.0, 1.0)

    stops = np.array([
        [15, 23, 42],
        [37, 99, 235],
        [139, 92, 246],
        [249, 115, 22],
        [253, 224, 71],
    ], dtype=np.float32)

    positions = normalized * (len(stops) - 1)
    lower = np.floor(positions).astype(np.int32)
    upper = np.minimum(lower + 1, len(stops) - 1)
    fraction = (positions - lower)[..., None]

    rgb = stops[lower] * (1 - fraction) + stops[upper] * fraction
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


_FCS_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Tinos:ital@0;1&display=swap');
.fcs-ov { font:500 11px "IBM Plex Mono",Consolas,monospace; letter-spacing:.16em; text-transform:uppercase; color:#7CF2D6; }
.fcs-h1 { font-family:"Times New Roman",Tinos,Times,serif !important; font-weight:400; font-size:clamp(34px,3.6vw,52px);
          line-height:1.05; letter-spacing:-.015em; color:#E8EDF5; margin:8px 0 6px; }
.fcs-sub { color:#9AA5B6; font:400 15px "IBM Plex Sans","Segoe UI",sans-serif; }
.fcs-k { font:500 10.5px "IBM Plex Mono",Consolas,monospace; letter-spacing:.12em; text-transform:uppercase; color:#7C889C; }
.fcs-mono { font-family:"IBM Plex Mono",Consolas,monospace; }
.fcs-pill { display:inline-flex; align-items:center; gap:6px; height:26px; padding:0 11px; border-radius:999px;
            font:500 12px "IBM Plex Sans","Segoe UI",sans-serif; white-space:nowrap; }
.fcs-pill i { width:6px; height:6px; border-radius:50%; background:currentColor; box-shadow:0 0 8px currentColor; }
.fcs-ok { background:rgba(95,224,195,.12); color:#7CF2D6; }
.fcs-bad { background:rgba(255,122,107,.12); color:#FF8C7E; }
.fcs-neu { background:rgba(255,255,255,.06); color:#B8C2D2; }
.fcs-info { background:rgba(122,167,255,.08); border:1px solid rgba(122,167,255,.2); color:#B5CBFF; }

/* cards built from Streamlit containers (keys) */
.st-key-fcs_viewer_panel, .st-key-fcs_score_card, .st-key-fcs_run_card,
.st-key-fcs_findings_card, .st-key-fcs_report_card {
  background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.018)) !important;
  border:1px solid rgba(255,255,255,.085) !important; border-radius:20px !important;
  box-shadow:0 40px 80px -40px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.06);
  padding:20px 22px !important;
}

/* segmented mode control */
.st-key-forensics_comparison_view [role="radiogroup"] {
  display:inline-flex; flex-wrap:wrap; gap:4px; padding:4px; border-radius:12px;
  background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08);
}
.st-key-forensics_comparison_view [role="radiogroup"] label,
.st-key-forensics_comparison_view [data-testid="stRadioOption"] {
  margin:0 !important; padding:6px 14px; border-radius:9px; cursor:pointer;
}
.st-key-forensics_comparison_view [role="radiogroup"] label > div:first-child,
.st-key-forensics_comparison_view [data-testid="stRadioOption"] > div > div:first-child { display:none; }
.st-key-forensics_comparison_view [role="radiogroup"] label p { color:#9AA5B6; font-weight:500; font-size:13.5px; }
.st-key-forensics_comparison_view [role="radiogroup"] label:has(input:checked) {
  background:rgba(95,224,195,.14); box-shadow:inset 0 0 0 1px rgba(95,224,195,.35);
}
.st-key-forensics_comparison_view [role="radiogroup"] label:has(input:checked) p { color:#7CF2D6; }
.st-key-forensics_comparison_view [data-testid="stWidgetLabel"] { display:none; }

/* buttons inside the run card */
.st-key-fcs_run_card button[kind^="primary"], .st-key-fcs_run_card [data-testid^="stBaseButton-primary"] {
  min-height:50px; margin-top:6px; background:linear-gradient(180deg,#7CF2D6,#3CCFAE) !important; color:#04241D !important;
  border:none !important; border-radius:12px !important;
  box-shadow:0 10px 30px -10px rgba(95,224,195,.7), inset 0 1px 0 rgba(255,255,255,.5) !important;
}
.st-key-fcs_run_card button[kind^="primary"] p { color:#04241D !important; font-weight:600 !important; font-size:15px !important; }
.st-key-fcs_run_card button[kind^="primary"] p::before {
  content:""; display:inline-block; width:16px; height:16px; margin-right:9px; vertical-align:-3px;
  background:currentColor;
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M8 12h8'/%3E%3C/svg%3E") center/contain no-repeat;
          mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M8 12h8'/%3E%3C/svg%3E") center/contain no-repeat;
}
.st-key-fcs_run_card button[kind^="secondary"], .st-key-fcs_run_card [data-testid^="stBaseButton-secondary"] {
  min-height:30px !important; padding:2px 6px !important; background:transparent !important;
  border:none !important; box-shadow:none !important; justify-content:flex-end !important;
}
.st-key-fcs_run_card button[kind^="secondary"] p { color:#7CF2D6 !important; font-size:13px !important; font-weight:500 !important; }
.st-key-fcs_run_card button[kind^="secondary"]:hover p { text-decoration:underline; }
.st-key-fcs_run_card button[kind^="secondary"] > div { justify-content:flex-end !important; width:100%; }
.st-key-fcs_run_card button[kind^="secondary"] { padding-right:0 !important; transform:translateY(7px); }
.st-key-fcs_run_card [data-testid="stHorizontalBlock"]:has(.fcs-foot) { align-items:center !important; margin-top:2px; }
.st-key-fcs_run_card [data-testid="stHorizontalBlock"]:has(.fcs-foot) [data-testid="stElementContainer"],
.st-key-fcs_run_card [data-testid="stHorizontalBlock"]:has(.fcs-foot) [data-testid="stMarkdownContainer"] p { margin:0 !important; }
.fcs-foot { font:400 13.5px/30px "IBM Plex Sans","Segoe UI",sans-serif; color:#7C889C; white-space:nowrap; }
.st-key-fcs_run_card [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.st-key-fcs_run_card [data-testid="stSelectbox"] > div > div {
  background:rgba(255,255,255,.03) !important; border-radius:10px !important;
}

.fcs-ring { position:relative; margin:4px auto 0; }
.fcs-ring-in { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.fcs-score { font-family:"Times New Roman",Tinos,Times,serif !important; font-size:46px; line-height:1; color:#E8EDF5; }
.fcs-kv { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:9px 0;
          font:400 15px "IBM Plex Sans","Segoe UI",sans-serif; color:#9AA5B6; }
.fcs-kv span:last-child { font-family:"IBM Plex Mono",Consolas,monospace; font-size:13px; color:#E8EDF5; }
.fcs-legend { display:flex; align-items:center; gap:14px; margin:4px 0 12px; }
.fcs-legend .bar { flex:1; height:9px; border-radius:99px;
  background:linear-gradient(90deg,#0F172A,#2563EB,#8B5CF6,#F97316,#FDE047); }
.fcs-note { display:flex; gap:10px; align-items:center; padding:12px 14px; border-radius:12px; font-size:13.5px; }
.fcs-empty { min-height:300px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:10px;
             border:1px dashed rgba(255,255,255,.14); border-radius:14px; background:#070C11; color:#7C889C;
             font:400 14px "IBM Plex Sans","Segoe UI",sans-serif; text-align:center; padding:24px; }
.fcs-check { display:flex; gap:10px; align-items:center; padding:5px 0; color:#E8EDF5; font-size:13.5px; }
</style>
"""

_FCS_ICONS = {
    "scan": "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M8 12h8",
    "info": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8h.01",
    "check": "M5 12.5l4.5 4.5L19 7.5",
}


def _fcs_icon(name, size=16, stroke=1.8):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'<path d="{_FCS_ICONS[name]}"/></svg>'
    )


def _fcs_ring(pct, size, stroke, inner):
    import math
    r = (size - stroke) / 2
    c = 2 * math.pi * r
    d = c * max(0.0, min(100.0, pct)) / 100
    dot = ""
    if pct is not None and pct > 0:
        angle = 2 * math.pi * pct / 100 - math.pi / 2
        cx = size / 2 + r * math.cos(angle)
        cy = size / 2 + r * math.sin(angle)
        dot = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{stroke * 0.75:.1f}" fill="#F7A440" style="filter:drop-shadow(0 0 6px #F7A440)"/>'
    return (
        f'<div class="fcs-ring" style="width:{size}px;height:{size}px">'
        f'<svg width="{size}" height="{size}">'
        '<defs><linearGradient id="fcsRing" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#F2B84B"/><stop offset="1" stop-color="#F08A3C"/></linearGradient></defs>'
        f'<g transform="rotate(-90 {size/2} {size/2})">'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="rgba(255,255,255,.07)" stroke-width="{stroke}"/>'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="url(#fcsRing)" stroke-width="{stroke}" '
        + (f'stroke-linecap="round" stroke-dasharray="{d} {c}"/>' if d > 0 else 'stroke-opacity="0"/>') + f'</g>{dot}'
        f'</svg><div class="fcs-ring-in">{inner}</div></div>'
    )


def _fcs_short(value, head=4, tail=8):
    text = str(value or "")
    prefix, sep, rest = text.partition("-")
    if sep and len(rest) > head + tail + 1:
        return f"{prefix}-{rest[:head]}…{rest[-tail:]}"
    return text


def _fcs_viewer(view_mode, original, heatmap):
    """Fixed-height viewer for all four comparison modes (display only)."""
    import base64 as _b64
    import io as _io
    import streamlit.components.v1 as _components

    heatmap_display = heatmap.resize(original.size)
    overlay = Image.blend(
        original.convert("RGBA"),
        heatmap_display.convert("RGBA"),
        alpha=0.42,
    ).convert("RGB")

    def src(image, max_side=1400):
        view = image.convert("RGB")
        if max(view.size) > max_side:
            view = view.copy()
            view.thumbnail((max_side, max_side))
        buf = _io.BytesIO()
        view.save(buf, format="JPEG", quality=90)
        return "data:image/jpeg;base64," + _b64.b64encode(buf.getvalue()).decode("ascii")

    aspect = original.width / max(1, original.height)
    frame_h = 420
    content_w = 1000  # widest left-column width, used only to size the iframe

    css = """
    <style>
      body { margin:0; background:transparent; font-family:'IBM Plex Sans','Segoe UI',Arial,sans-serif; }
      .vw { display:flex; gap:22px; justify-content:center; align-items:flex-start; }
      .cell { display:flex; flex-direction:column; gap:10px; min-width:0; }
      .frame { position:relative; overflow:hidden; border-radius:12px; line-height:0; max-height:FRAMEHpx;
               aspect-ratio:ASPECT; background:#0B1118; box-shadow:0 0 0 1px rgba(255,255,255,.06); }
      .frame img { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; display:block; user-select:none; }
      .cap { display:flex; flex-wrap:wrap; justify-content:space-between; gap:4px 14px; font:400 12px 'IBM Plex Mono',Consolas,monospace;
             letter-spacing:.04em; color:#7C889C; }
      .tag { position:absolute; top:10px; padding:5px 8px; border-radius:6px; background:#0B1118d9; color:#E8EEF4;
             font-size:11px; letter-spacing:.06em; line-height:1.2; pointer-events:none; z-index:3; }
      @media (max-width: 480px) {
        .vw { flex-direction:column; align-items:center; }
        .vw .cell { width:100% !important; max-width:MAXWpx; }
      }
    </style>
    <script>
    (function () {
      function fit() {
        try {
          var f = window.frameElement;
          if (!f) return;
          var h = Math.ceil(document.body.scrollHeight) + 2;
          if (h > 40) {
            f.style.height = h + "px"; f.setAttribute("height", h);
            var p = f.parentElement;
            if (p && p.getAttribute("data-testid") === "stElementContainer") {
              p.style.setProperty("height", h + "px", "important");
              p.style.setProperty("min-height", "0", "important");
              p.style.setProperty("flex", "0 0 auto", "important");
            }
          }
        } catch (e) {}
      }
      window.addEventListener("load", fit);
      window.addEventListener("resize", fit);
      setTimeout(fit, 60); setTimeout(fit, 400);
    })();
    </script>
    """.replace("FRAMEH", str(frame_h)).replace("ASPECT", f"{aspect:.6f}").replace("MAXW", f"{frame_h * aspect:.1f}")

    def width(n):
        return f"min(calc((100% - {22 * (n - 1)}px) / {n}), {frame_h * aspect:.1f}px)"

    def iframe_h(n, extra=34):
        avail = (content_w - 22 * (n - 1)) / n
        return int(min(frame_h, avail / aspect) + extra)

    def cell(image_src, alt, left, right, n):
        return (f'<div class="cell" style="width:{width(n)}"><div class="frame" style="width:100%">'
                f'<img src="{image_src}" alt="{alt}"></div>'
                f'<div class="cap"><span>{left}</span><span>{right}</span></div></div>')

    if view_mode == "Reveal Comparison":
        html = f"""{css}
        <div class="vw"><div class="cell" style="width:{width(1)}">
          <div class="frame" style="width:100%">
            <img src="{src(original)}" alt="Original registered evidence">
            <img id="response" src="{src(overlay)}" alt="Model response overlay" style="clip-path:inset(0 50% 0 0)">
            <div id="divider" style="position:absolute;top:0;bottom:0;left:50%;width:2px;background:#18B8A6;transform:translateX(-1px);pointer-events:none;z-index:2">
              <div style="position:absolute;top:50%;left:50%;width:24px;height:24px;border-radius:50%;background:#18B8A6;border:2px solid #0B1118;box-shadow:0 0 0 2px #18B8A6;transform:translate(-50%,-50%)"></div>
            </div>
            <input id="drag" type="range" min="0" max="100" value="50" aria-label="Reveal model response"
              style="position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:ew-resize;z-index:4">
            <span class="tag" style="left:10px">MODEL RESPONSE</span>
            <span class="tag" style="right:10px">ORIGINAL</span>
          </div>
          <div class="cap"><span>MODEL OUTPUT · REVEAL</span><span id="percent">50% revealed</span></div>
        </div></div>
        <script>
        (function () {{
          const drag = document.getElementById("drag");
          const response = document.getElementById("response");
          const divider = document.getElementById("divider");
          const percent = document.getElementById("percent");
          function updateReveal() {{
            const value = Number(drag.value);
            response.style.clipPath = "inset(0 " + (100 - value) + "% 0 0)";
            divider.style.left = value + "%";
            percent.textContent = value + "% revealed";
          }}
          drag.addEventListener("input", updateReveal);
          updateReveal();
        }})();
        </script>"""
        _components.html(html, height=iframe_h(1), scrolling=False)
    elif view_mode == "Side-by-Side":
        html = (css + '<div class="vw">'
                + cell(src(original), "Original registered evidence", "EVIDENCE · INPUT", "native ratio", 2)
                + cell(src(heatmap_display), "Normalized localization response", "MODEL OUTPUT · SIDE-BY-SIDE", "same ratio", 2)
                + "</div>")
        _components.html(html, height=iframe_h(2), scrolling=False)
    elif view_mode == "Heatmap Overlay":
        html = (css + '<div class="vw">'
                + cell(src(overlay), "Model response overlay", "MODEL OUTPUT · HEATMAP OVERLAY", "native ratio", 1)
                + "</div>")
        _components.html(html, height=iframe_h(1), scrolling=False)
    else:
        html = (css + '<div class="vw">'
                + cell(src(heatmap_display), "Normalized localization response", "MODEL OUTPUT · HEATMAP ONLY", "native ratio", 1)
                + "</div>")
        _components.html(html, height=iframe_h(1), scrolling=False)


_FCF_CSS = """
<style>
.fcf-head { display:flex; justify-content:space-between; align-items:flex-end; gap:20px; margin:30px 0 18px; }
.fcf-step { display:inline-flex; align-items:center; gap:8px; height:34px; padding:0 16px; border-radius:999px;
            background:rgba(139,124,255,.14); color:#B3A9FF; font:500 13.5px "IBM Plex Sans","Segoe UI",sans-serif; white-space:nowrap; }
.fcf-step i { width:7px; height:7px; border-radius:50%; background:currentColor; box-shadow:0 0 8px currentColor; }
.fcf-card { background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.018));
            border:1px solid rgba(255,255,255,.085); border-radius:20px; color:#E8EDF5;
            box-shadow:0 40px 80px -40px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.06);
            font-family:"IBM Plex Sans","Segoe UI",sans-serif; box-sizing:border-box; }
.fcf-trail { display:flex; align-items:flex-start; padding:26px 24px 22px; margin-bottom:20px; }
.fcf-s { flex:1 1 0; min-width:0; display:flex; flex-direction:column; align-items:center; text-align:center; gap:7px; }
.fcf-ic { width:56px; height:56px; border-radius:16px; display:flex; align-items:center; justify-content:center; }
.fcf-ic.done { background:rgba(95,224,195,.10); border:1px solid rgba(95,224,195,.45); color:#7CF2D6;
               box-shadow:0 0 22px -6px rgba(95,224,195,.6); }
.fcf-ic.next { background:rgba(139,124,255,.16); border:1px solid rgba(139,124,255,.7); color:#C9C1FF;
               box-shadow:0 0 0 5px rgba(139,124,255,.12), 0 0 26px -4px rgba(139,124,255,.75); }
.fcf-ic.todo { background:rgba(255,255,255,.02); border:1px dashed rgba(255,255,255,.18); color:#59647A; }
.fcf-ic.bad { background:rgba(255,122,107,.10); border:1px solid rgba(255,122,107,.5); color:#FF8C7E; }
.fcf-s b { font-weight:600; font-size:14.5px; color:#E8EDF5; margin-top:6px; }
.fcf-s.todo b { color:#7C889C; }
.fcf-s span.d { font-size:12.5px; color:#7C889C; line-height:1.45; max-width:170px; overflow-wrap:anywhere; }
.fcf-tag { margin-top:4px; padding:3px 10px; border-radius:999px; font:500 11.5px "IBM Plex Sans","Segoe UI",sans-serif; }
.fcf-tag.done { background:rgba(95,224,195,.12); color:#7CF2D6; }
.fcf-tag.next { background:rgba(139,124,255,.16); color:#C9C1FF; }
.fcf-tag.next::before { content:"●"; font-size:8px; margin-right:6px; vertical-align:2px; }
.fcf-tag.todo { background:rgba(255,255,255,.06); color:#B8C2D2; }
.fcf-tag.bad { background:rgba(255,122,107,.12); color:#FF8C7E; }
.fcf-line { flex:0 0 7%; height:2px; margin-top:28px; border-radius:2px; }
.fcf-line.done { background:#4FD1B5; box-shadow:0 0 8px rgba(95,224,195,.5); }
.fcf-line.next { background:linear-gradient(90deg,#4FD1B5,#8B7CFF); }
.fcf-line.todo { background:repeating-linear-gradient(90deg,rgba(255,255,255,.22) 0 6px,transparent 6px 12px); }

/* conclusion radio as option cards (works for React Aria and BaseWeb radio markup) */
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] {
  display:grid !important; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; width:100% !important; max-width:none !important;
}
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] > div { display:flex; min-width:0; }
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label {
  position:relative; display:flex !important; flex-direction:column; align-items:flex-start; gap:12px;
  width:100%; margin:0 !important; padding:16px 18px 18px !important; min-height:118px; border-radius:16px; cursor:pointer;
  background:rgba(255,255,255,.02); border:1px solid rgba(255,255,255,.09); box-sizing:border-box;
  transition:border-color .15s, background .15s;
}
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label:hover { border-color:rgba(255,255,255,.18); }
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label::before {
  content:"Option"; padding:4px 11px; border-radius:999px; background:rgba(255,255,255,.06); color:#B8C2D2;
  font:500 12.5px "IBM Plex Sans","Segoe UI",sans-serif;
}
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
  background:rgba(242,184,75,.07); border-color:#E9A93E; box-shadow:0 0 26px -10px rgba(242,184,75,.7);
}
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked)::before {
  content:"● Selected"; background:rgba(242,184,75,.14); color:#F5C66A;
}
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label > div:first-child,
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label > span + div > div:first-child { display:none !important; }
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p {
  font:500 16px/1.4 "IBM Plex Sans","Segoe UI",sans-serif !important; color:#9AA5B6 !important; margin:0 !important;
}
.st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) [data-testid="stMarkdownContainer"] p {
  color:#F3F6FA !important; font-weight:600 !important;
}
.st-key-fcf_form_card [data-testid="stRadio"] > div:has([role="radiogroup"]) { width:100% !important; }
.st-key-fcf_form_card [data-testid="stForm"] { background:transparent !important; border:none !important; padding:0 !important; }
.st-key-fcf_form_card [data-testid="stWidgetLabel"] p {
  font:500 11px "IBM Plex Mono",Consolas,monospace !important; letter-spacing:.14em; text-transform:uppercase; color:#7C889C !important;
}
.st-key-fcf_form_card textarea { min-height:170px; }
.st-key-fcf_form_card, .st-key-fcf_report_card {
  background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.018)) !important;
  border:1px solid rgba(255,255,255,.085) !important; border-radius:20px !important;
  box-shadow:0 40px 80px -40px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.06);
  padding:24px 26px !important;
}
.st-key-fcf_form_card [data-testid="stFormSubmitButton"] button {
  min-height:50px; padding:0 26px !important; background:linear-gradient(180deg,#7CF2D6,#3CCFAE) !important;
  border:none !important; border-radius:12px !important;
  box-shadow:0 10px 30px -10px rgba(95,224,195,.7), inset 0 1px 0 rgba(255,255,255,.5) !important;
}
.st-key-fcf_form_card [data-testid="stFormSubmitButton"] button p { color:#04241D !important; font-weight:600 !important; font-size:15.5px !important; }
.fcf-note { font:400 13.5px/1.4 "IBM Plex Sans","Segoe UI",sans-serif; color:#7C889C; }

/* locked report preview */
.fcf-locked { position:relative; min-height:300px; overflow:hidden; border-radius:14px; }
.fcf-locked .ghost { filter:blur(1.4px); opacity:.22; pointer-events:none; user-select:none; }
.fcf-lockmid { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:10px; }
.fcf-lockic { width:84px; height:84px; border-radius:22px; display:flex; align-items:center; justify-content:center; color:#E8EDF5;
              background:rgba(139,124,255,.12); border:1px solid rgba(139,124,255,.55);
              box-shadow:0 0 50px -6px rgba(139,124,255,.7); }
.fcf-lockmid b { font:600 21px "IBM Plex Sans","Segoe UI",sans-serif; color:#F3F6FA; }
.fcf-lockmid span { font-size:15px; color:#B8C2D2; }
.fcf-dots { position:absolute; right:22px; top:20px; display:grid; grid-template-columns:repeat(6,9px); gap:5px; opacity:.5; }
.fcf-dots b { width:9px; height:9px; border-radius:50%; background:#2A3646; }
.st-key-fcf_report_card [data-testid="stDownloadButton"] button[kind^="secondary"] {
  background:transparent !important; border:1px solid rgba(255,255,255,.12) !important; border-radius:12px !important; box-shadow:none !important;
}
.st-key-fcf_report_card [data-testid="stDownloadButton"] button[kind^="secondary"] p { color:#B8C2D2 !important; font-size:13.5px !important; }
.st-key-fcf_report_card [data-testid="stDownloadButton"] button[kind^="primary"] {
  min-height:50px; background:linear-gradient(180deg,#7CF2D6,#3CCFAE) !important; border:none !important; border-radius:12px !important;
  box-shadow:0 10px 30px -10px rgba(95,224,195,.7), inset 0 1px 0 rgba(255,255,255,.5) !important;
}
.st-key-fcf_report_card [data-testid="stDownloadButton"] button[kind^="primary"] p { color:#04241D !important; font-weight:600 !important; font-size:15px !important; }

/* sealed */
.st-key-fcf_sealed {
  position:relative; overflow:hidden; text-align:center; margin-top:28px;
  background:radial-gradient(700px 360px at 50% 30%, rgba(95,224,195,.10), transparent 70%),
             radial-gradient(500px 300px at 85% 80%, rgba(139,124,255,.12), transparent 70%),
             linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.012)) !important;
  border:1px solid rgba(255,255,255,.085) !important; border-radius:24px !important;
  box-shadow:0 40px 80px -40px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.06);
  padding:48px 32px 44px !important;
}
.st-key-fcf_sealed [data-testid="stMarkdownContainer"], .st-key-fcf_sealed [data-testid="stMarkdownContainer"] > div { text-align:center !important; }
.fcf-seal { position:relative; width:230px; height:230px; margin:0 auto 18px; }
.fcf-seal svg { position:absolute; inset:0; filter:drop-shadow(0 0 26px rgba(124,242,214,.35)); }
.fcf-seal .g { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
               display:grid; grid-template-columns:repeat(8,1fr); gap:3px; width:104px; }
.fcf-seal .g b { aspect-ratio:1; border-radius:2px; }
.fcf-sealh { font-family:"Times New Roman",Tinos,Times,serif !important; font-weight:400; font-size:clamp(46px,5vw,76px);
             line-height:1.05; color:#E8EDF5; margin:10px 0 14px; }
.fcf-sealh em { font-style:italic; background:linear-gradient(90deg,#7CF2D6,#A99BFF); -webkit-background-clip:text;
                background-clip:text; color:transparent; }
.fcf-sealsub { max-width:560px; margin:0 auto 26px; color:#9AA5B6; font:400 16px/1.6 "IBM Plex Sans","Segoe UI",sans-serif; }
.st-key-fcf_sealed [data-testid="stDownloadButton"] button {
  min-height:52px; background:linear-gradient(180deg,#7CF2D6,#3CCFAE) !important; border:none !important; border-radius:12px !important;
  box-shadow:0 12px 34px -10px rgba(95,224,195,.75), inset 0 1px 0 rgba(255,255,255,.5) !important;
}
.st-key-fcf_sealed [data-testid="stDownloadButton"] button p { color:#04241D !important; font-weight:600 !important; font-size:15.5px !important; }
.st-key-fcf_sealed [data-testid="stDownloadButton"] button p::before {
  content:"↓"; margin-right:9px; font-weight:700;
}
.st-key-fcf_sealed [data-testid="stButton"] button {
  min-height:52px; background:rgba(255,255,255,.04) !important; border:1px solid rgba(255,255,255,.14) !important;
  border-radius:12px !important; box-shadow:none !important;
}
.st-key-fcf_sealed [data-testid="stButton"] button p { color:#E8EDF5 !important; font-weight:500 !important; font-size:15px !important; }
.fcf-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:18px; margin:20px 0 18px; }
.fcf-stat { padding:22px 22px; display:flex; gap:16px; align-items:center; text-align:left; }
.fcf-sq { width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center; flex:none; }
.fcf-stat .k { font:500 10.5px "IBM Plex Mono",Consolas,monospace; letter-spacing:.14em; text-transform:uppercase; color:#7C889C; }
.fcf-stat b { display:block; margin-top:4px; font-weight:600; font-size:15px; color:#E8EDF5; overflow-wrap:anywhere; }
@media (max-width: 1100px) { .fcf-stats { grid-template-columns:repeat(2,minmax(0,1fr)); } }
.fcf-stat .s { display:block; margin-top:3px; font-size:12px; color:#7C889C; }
.fcf-qual { display:inline-flex; align-items:center; gap:8px; margin:0 auto 22px; padding:7px 14px; border-radius:999px;
            background:rgba(242,184,75,.12); color:#F5C66A; font:500 13.5px "IBM Plex Sans","Segoe UI",sans-serif; }
.fcf-meta { text-align:center; font:400 11.5px/1.7 "IBM Plex Mono",Consolas,monospace; color:#7C889C; margin:6px 0 4px; overflow-wrap:anywhere; }
.fcr-checks { margin:14px 0 10px; padding:12px 14px; border-radius:12px; background:rgba(255,255,255,.025);
              border:1px solid rgba(255,255,255,.07); }
.fcr-checks .r { display:flex; justify-content:space-between; gap:10px; padding:4px 0; font-size:13px; color:#B8C2D2; }
.fcr-checks .ok { color:#7CF2D6; } .fcr-checks .no { color:#FF8C7E; }
.st-key-fcr_finalize_box [data-testid="stButton"] button[kind^="primary"] {
  min-height:50px; background:linear-gradient(180deg,#7CF2D6,#3CCFAE) !important; border:none !important; border-radius:12px !important;
  box-shadow:0 10px 30px -10px rgba(95,224,195,.7), inset 0 1px 0 rgba(255,255,255,.5) !important;
}
.st-key-fcr_finalize_box [data-testid="stButton"] button[kind^="primary"] p { color:#04241D !important; font-weight:600 !important; font-size:15px !important; }
.st-key-fcr_finalize_box [data-testid="stCheckbox"] p { font-size:13px !important; color:#E8EDF5 !important; }
</style>
"""

_FCF_ICONS = {
    "folder": "M4 6h6l2 2h8v11H4z",
    "shield": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.5 2.5 4.5-5",
    "link": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    "scan": "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M8 12h8",
    "file": "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
    "lock": "M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3",
    "check": "M5 12.5l4.5 4.5L19 7.5",
    "x": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9 9l6 6M15 9l-6 6",
}


def _fcf_icon(name, size=22, stroke=1.8):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'<path d="{_FCF_ICONS[name]}"/></svg>'
    )


def _fcf_trail(steps):
    """steps: list of (icon, title, detail, state) with state in done/next/todo/bad."""
    import html as _html
    labels = {"done": "Done", "next": "Next", "todo": "Locked", "bad": "Check"}
    parts = []
    for i, (icon, title, detail, state) in enumerate(steps):
        if i:
            prev = steps[i - 1][3]
            line = "done" if prev == "done" and state == "done" else ("next" if prev == "done" else "todo")
            parts.append(f'<div class="fcf-line {line}"></div>')
        parts.append(
            f'<div class="fcf-s {state}"><div class="fcf-ic {state}">{_fcf_icon(icon, 22)}</div>'
            f'<b>{_html.escape(title)}</b><span class="d">{_html.escape(detail)}</span>'
            f'<span class="fcf-tag {state}">{labels[state]}</span></div>'
        )
    return f'<div class="fcf-card fcf-trail">{"".join(parts)}</div>'


def _fcf_seal(sha256):
    import math
    ramp = ["#0F2A26", "#17584B", "#2FB592", "#7CF2D6"]
    value = str(sha256 or "").lower()[:64].ljust(64, "0")
    cells = "".join(
        f'<b style="background:{ramp[int(ch, 16) // 4] if ch in "0123456789abcdef" else ramp[0]}'
        f'{";box-shadow:0 0 8px rgba(124,242,214,.6)" if ch in "cdef" else ""}"></b>'
        for ch in value
    )
    pts = []
    n = 12
    for k in range(n * 2):
        r = 108 if k % 2 == 0 else 90
        a = math.pi * k / n - math.pi / 2
        pts.append(f"{115 + r * math.cos(a):.1f},{115 + r * math.sin(a):.1f}")
    poly = " ".join(pts)
    return (
        '<div class="fcf-seal"><svg width="230" height="230" viewBox="0 0 230 230">'
        '<defs><linearGradient id="fcfSeal" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#7CF2D6"/><stop offset="1" stop-color="#A99BFF"/></linearGradient></defs>'
        f'<polygon points="{poly}" fill="#0B1620" stroke="url(#fcfSeal)" stroke-width="3" stroke-linejoin="round"/>'
        f'</svg><div class="g">{cells}</div></div>'
    )


def _fcf_scroll_top():
    import streamlit.components.v1 as _components
    _components.html(
        """<script>
        try {
          const doc = window.parent.document;
          const main = doc.querySelector('[data-testid="stMain"]') || doc.querySelector('section.main');
          if (main) main.scrollTo({top: 0, behavior: "smooth"});
          window.parent.scrollTo({top: 0, behavior: "smooth"});
        } catch (e) {}
        </script>""",
        height=0,
    )



def _fcr_when(value):
    try:
        parsed = __import__("datetime").datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y %H:%M UTC")
    except (TypeError, ValueError):
        return str(value or "—")


def _fcr_finalized_panel(user, record):
    """Page 6: shown only for a finalization record read back from the database."""
    import html as _html
    from forenchain.report_finalization import (
        FinalizationError, get_finalized_report_pdf, get_report_audit_log, record_report_download,
    )

    st.markdown(_FCF_CSS, unsafe_allow_html=True)
    qualified = bool(record["qualified_conclusion"])
    version = int(record["version"])
    with st.container(key="fcf_sealed"):
        st.markdown(
            _fcf_seal(record["registered_sha256"])
            + f'<div class="fcs-ov">Case {_html.escape(str(record["case_id"]))} · Report v{version} · Finalized</div>'
            '<div class="fcf-sealh">Report <em>finalized.</em></div>'
            '<div class="fcf-sealsub">Integrity verified, custody chain valid, AI screening and examiner findings '
            f'recorded. Version {version} of this report is now locked. Finalizing does not close the legal case '
            'and does not establish that the image is authentic or manipulated.</div>'
            + (f'<div class="fcf-qual">● Conclusion: {_html.escape(record["conclusion"])} — follow-up needed</div>'
               if qualified else ''),
            unsafe_allow_html=True,
        )
        _, download_col, back_col, _ = st.columns([1, 1.3, 0.95, 1], vertical_alignment="center")
        with download_col:
            if has_permission(user["role"], "view_reports"):
                try:
                    pdf_bytes, _stored = get_finalized_report_pdf(user["user_id"], record["finalization_id"])
                    st.download_button(
                        "Download finalized report (PDF)",
                        data=pdf_bytes,
                        file_name=f"ForenChain_Report_{record['evidence_id']}_v{version}.pdf",
                        mime="application/pdf",
                        key="download_finalized_report",
                        type="primary",
                        width="stretch",
                        on_click=record_report_download,
                        args=(user["user_id"], record["finalization_id"]),
                    )
                except (FinalizationError, PermissionError) as exc:
                    st.error(str(exc))
            else:
                st.info("Your role cannot download finalized reports.")
        with back_col:
            back = st.button("Back to command center", key="fcr_back_cc", width="stretch")
        if back:
            _fcf_scroll_top()

    stat = (
        '<div class="fcf-card fcf-stat"><span class="fcf-sq" style="{bg}">{icon}</span>'
        '<div><span class="k">{k}</span><b>{v}</b><span class="s">{sub}</span></div></div>'
    )
    teal = "background:rgba(95,224,195,.12);color:#7CF2D6"
    amber = "background:rgba(242,184,75,.13);color:#F5C66A"
    events = int(record["custody_event_count"])
    st.markdown(
        '<div class="fcf-stats">'
        + stat.format(bg=teal, icon=_fcf_icon("shield", 21), k="Integrity",
                      v="Verified · 64/64", sub=_html.escape("checked " + _fcr_when(record["integrity_checked_at"])))
        + stat.format(bg=teal, icon=_fcf_icon("link", 21), k="Custody chain",
                      v=_html.escape(f"Valid · {events} event{'s' if events != 1 else ''}"),
                      sub="hash-linked chain verified")
        + stat.format(bg="background:rgba(139,124,255,.14);color:#B3A9FF", icon=_fcf_icon("scan", 21),
                      k="AI screening", v=_html.escape(_fcs_short(record["analysis_id"], 4, 8)),
                      sub="MVSS-Net · decision support only")
        + stat.format(bg=amber if qualified else teal, icon=_fcf_icon("file", 21), k="Conclusion",
                      v=_html.escape(record["conclusion"]),
                      sub="qualified · acknowledged" if qualified else "examiner conclusion")
        + '</div>',
        unsafe_allow_html=True,
    )
    amends = (f' · amends v{version - 1}: {_html.escape(str(record["amendment_reason"] or ""))}'
              if record.get("supersedes_id") else "")
    st.markdown(
        f'<div class="fcf-meta">Finalized by {_html.escape(record["examiner_username"])} · '
        f'{_html.escape(_fcr_when(record["finalized_at"]))} · {_html.escape(record["finalization_id"])}<br>'
        f'PDF SHA-256 {_html.escape(record["report_sha256"])} · peer review: not recorded{amends}</div>',
        unsafe_allow_html=True,
    )
    if has_permission(user["role"], "view_audit"):
        with st.expander("Report audit trail"):
            rows = get_report_audit_log(record["evidence_id"])
            st.dataframe(
                [{"Time (UTC)": r["event_time"], "User": r["actor_username"], "Action": r["action"],
                  "Outcome": r["outcome"], "Report": r["finalization_id"] or "—"} for r in rows],
                hide_index=True, width="stretch",
            )


def ai_screening_screen(user):
    import html as _html

    st.markdown(_FCS_CSS, unsafe_allow_html=True)

    head_left, head_right = st.columns([1.6, 1], vertical_alignment="bottom")
    with head_left:
        st.markdown(
            '<div class="fcs-ov">Evidence workspace · AI screening</div>'
            '<div class="fcs-h1">AI-assisted image forensics.</div>'
            '<div class="fcs-sub">Decision-support visualization for authorized forensic examiners.</div>',
            unsafe_allow_html=True,
        )

    if not has_permission(user["role"], "analyze_image"):
        st.info("Your role cannot run AI screening.")
        return

    records = query_all(
        """
        SELECT evidence_id, case_id, original_filename, registered_at
        FROM evidence
        ORDER BY registered_at DESC
        """
    )

    if not records:
        st.info("No registered evidence is available for AI screening.")
        return

    with head_right:
        view_mode = st.radio(
            "Comparison view",
            ["Reveal Comparison", "Side-by-Side", "Heatmap Overlay", "Heatmap Only"],
            key="forensics_comparison_view",
            horizontal=True,
        )

    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    left, right = st.columns([2.05, 1], gap="medium")

    # ---- right column first: actions run before the viewer reads the result
    with right:
        score_slot = st.container(key="fcs_score_card")
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        with st.container(key="fcs_run_card"):
            st.markdown('<div class="fcs-k" style="margin-bottom:8px">Run</div>', unsafe_allow_html=True)
            evidence_ids = [row["evidence_id"] for row in records]
            selected_id = st.selectbox(
                "Select registered evidence",
                evidence_ids,
                format_func=lambda eid: next(
                    (
                        f"{row['case_id']} · {row['original_filename']} · "
                        f"{_fcs_short(row['evidence_id'], 4, 8)}"
                        for row in records if row["evidence_id"] == eid
                    ),
                    eid,
                ),
                key="registered_ai_evidence",
                label_visibility="collapsed",
            )

            if st.session_state.get("ai_screening_evidence_id") != selected_id:
                st.session_state.pop("ai_screening_result", None)
                st.session_state["ai_screening_evidence_id"] = selected_id

            record = get_evidence(selected_id)
            if record is None:
                st.error("The selected evidence record could not be found.")
                return

            analysis_slot = st.empty()
            run_clicked = st.button("Run AI screening", type="primary", width="stretch")
            foot_l, foot_r = st.columns([1.25, 1], vertical_alignment="center")
            with foot_l:
                st.markdown('<div class="fcs-foot">Completes trail step 4 of 6</div>', unsafe_allow_html=True)
            with foot_r:
                verify_clicked = st.button("Verify integrity", key="verify_ai_evidence", width="stretch")
            message_slot = st.container()

    with message_slot:
        if verify_clicked:
            verification = verify_evidence(selected_id)
            if verification["status"] == "INTEGRITY_OK":
                st.success("Integrity verified: SHA-256 matches the registered hash.")
            else:
                st.error(
                    f"Integrity verification failed: {verification['status']}. "
                    "AI screening is blocked."
                )

        if run_clicked:
            try:
                verification = verify_evidence(selected_id)
                if verification["status"] != "INTEGRITY_OK":
                    st.error(
                        f"Screening blocked. Integrity status: "
                        f"{verification['status']}."
                    )
                    st.session_state.pop("ai_screening_result", None)
                    return

                evidence_path = (
                    Path(__file__).resolve().parent / record["stored_path"]
                ).resolve()

                if not evidence_path.is_file():
                    st.error("Registered evidence file is missing. Screening blocked.")
                    return

                file_bytes = evidence_path.read_bytes()
                analyzed_hash = hashlib.sha256(file_bytes).hexdigest()

                if (
                    analyzed_hash != record["sha256"]
                    or analyzed_hash != verification["current_hash"]
                ):
                    st.error("Evidence changed during verification. Screening blocked.")
                    return

                from io import BytesIO
                image = Image.open(BytesIO(file_bytes)).convert("RGB")

                with st.spinner("Verifying evidence and running MVSS-Net on CPU..."):
                    result = load_forensics().analyze(image)

                score = float(result["screening_score"])
                device = str(result.get("device", "cpu"))

                latest_analysis_id = "AN-" + uuid.uuid4().hex.upper()
                save_analysis(
                    analysis_id=latest_analysis_id,
                    evidence_id=selected_id,
                    examiner_user_id=int(user["user_id"]),
                    model_name="MVSS-Net / mvssnet_casia.pt",
                    score=score,
                    device=device,
                    registered_sha256=record["sha256"],
                    analyzed_sha256=analyzed_hash,
                )

                st.session_state["ai_screening_result"] = {
                    "evidence_id": selected_id,
                    "image": image.copy(),
                    "screening_score": score,
                    "localization_map": np.asarray(
                        result["localization_map"], dtype=np.float32
                    ).copy(),
                    "device": device,
                    "sha256": analyzed_hash,
                    "analysis_id": latest_analysis_id,
                }
                st.success("Analysis completed and its metadata was recorded.")

            except Exception as exc:
                st.error(f"AI screening failed: {exc}")
                return

    saved = st.session_state.get("ai_screening_result")
    has_result = saved is not None and saved["evidence_id"] == selected_id

    integrity_status = None
    if has_result:
        integrity_check = verify_evidence(selected_id)
        integrity_status = integrity_check.get("status", "UNKNOWN")

    # ---- score card
    with score_slot:
        if has_result:
            score = saved["screening_score"]
            ring = _fcs_ring(100 * max(0.0, min(1.0, score)), 200, 12,
                             f'<span class="fcs-score">{score:.4f}</span>'
                             '<span class="fcs-k" style="margin-top:6px">response score</span>')
            pill = ('<span class="fcs-pill fcs-ok"><i></i>Integrity verified</span>'
                    if integrity_status == "INTEGRITY_OK" else
                    f'<span class="fcs-pill fcs-bad"><i></i>{_html.escape(str(integrity_status))}</span>')
            device_pill = f'<span class="fcs-pill fcs-neu">{_html.escape(saved["device"].upper())}</span>'
        else:
            ring = _fcs_ring(0, 200, 12,
                             '<span class="fcs-score" style="color:#59647A">—</span>'
                             '<span class="fcs-k" style="margin-top:6px">response score</span>')
            pill = '<span class="fcs-pill fcs-neu"><i></i>Not run</span>'
            device_pill = ""
        st.markdown(
            f'{ring}<div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin:14px 0 4px">'
            f'{pill}{device_pill}</div>',
            unsafe_allow_html=True,
        )

    analysis_id = saved.get("analysis_id", "") if has_result else ""
    analysis_slot.markdown(
        '<div class="fcs-kv"><span>Model</span><span>mvssnet_casia.pt</span></div>'
        f'<div class="fcs-kv" style="margin-bottom:6px"><span>Analysis</span>'
        f'<span title="{_html.escape(analysis_id)}">{_html.escape(_fcs_short(analysis_id, 4, 8)) if analysis_id else "—"}</span></div>',
        unsafe_allow_html=True,
    )

    # ---- viewer panel
    with left:
        with st.container(key="fcs_viewer_panel"):
            if has_result:
                original = saved["image"]
                heatmap = make_response_heatmap(saved["localization_map"])
                _fcs_viewer(view_mode, original, heatmap)
                st.markdown(
                    '<div class="fcs-legend"><span class="fcs-k">Response</span><span class="bar"></span>'
                    '<span class="fcs-mono" style="font-size:12px;color:#7C889C">low → high</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="fcs-empty">'
                    f'<span style="color:#7CF2D6">{_fcs_icon("scan", 30)}</span>'
                    f'<b style="color:#E8EDF5;font-weight:600">{_html.escape(record["original_filename"])}</b>'
                    f'<span class="fcs-mono" style="font-size:12px">{_html.escape(record["evidence_id"])} · '
                    f'{record["image_width"]} × {record["image_height"]}</span>'
                    '<span>Run AI screening to view the model response.</span></div>',
                    unsafe_allow_html=True,
                )

    if not has_result:
        from forenchain.report_finalization import latest_finalization as _fcr_latest
        _existing = _fcr_latest(selected_id, user["user_id"])
        if _existing is not None:
            _fcr_finalized_panel(user, _existing)
        return

    score = saved["screening_score"]
    original = saved["image"]
    heatmap = make_response_heatmap(saved["localization_map"])

    with st.expander("Evidence fingerprint · SHA-256"):
        st.code(saved["sha256"], language=None)

    report_history = query_all(
        """
        SELECT analysis_id, analyzed_at
        FROM analysis_records
        WHERE evidence_id = ? AND examiner_user_id = ?
        ORDER BY analyzed_at DESC
        LIMIT 1
        """,
        (selected_id, int(user["user_id"])),
    )
    latest = report_history[0] if report_history else {}

    findings_rows = query_all(
        """
        SELECT conclusion, notes, recorded_at
        FROM examiner_findings
        WHERE evidence_id = ? AND examiner_user_id = ?
        ORDER BY recorded_at DESC
        LIMIT 1
        """,
        (selected_id, int(user["user_id"])),
    )
    latest_finding = findings_rows[0] if findings_rows else {}

    integrity_checked_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()

    report_metadata = {
        "case_id": record["case_id"],
        "evidence_id": selected_id,
        "original_filename": record["original_filename"],
        "registered_sha256": record["sha256"],
        "analyzed_sha256": saved["sha256"],
        "integrity_status": integrity_status,
        "integrity_checked_at": integrity_checked_at,
        "examiner_username": user["username"],
        "examiner_user_id": user["user_id"],
        "model_name": "MVSS-Net / mvssnet_casia.pt",
        "model_response_score": f"{score:.6f}",
        "inference_device": saved["device"],
        "analysis_id": saved.get("analysis_id", latest.get("analysis_id", "Not available")),
        "analyzed_at": latest.get("analyzed_at", "Not available"),
        "examiner_conclusion": latest_finding.get("conclusion", "Not recorded"),
        "examiner_notes": latest_finding.get("notes", "No findings recorded."),
    }

    # ---- Batch 4 findings / sealed presentation (display only) ----
    st.markdown(_FCF_CSS, unsafe_allow_html=True)
    case_id = str(record["case_id"])
    can_record = has_permission(user["role"], "record_findings")
    integrity_ok = integrity_status == "INTEGRITY_OK"

    try:
        custody_rows = query_all(
            "SELECT event_id, actor, action, event_time FROM custody_events "
            "WHERE evidence_id = ? ORDER BY event_id",
            (selected_id,),
        )
    except sqlite3.Error:
        custody_rows = []
    try:
        chain_ok = bool(verify_custody_chain().get("valid"))
    except Exception:
        chain_ok = False
    registered_by = next((r["actor"] for r in custody_rows if r["action"] == "REGISTERED"), "Registered")
    try:
        registered_on = __import__("datetime").datetime.fromisoformat(
            str(record["registered_at"]).replace("Z", "+00:00")
        ).strftime("%d %b")
    except (TypeError, ValueError):
        registered_on = str(record["registered_at"] or "")
    analysis_short = _fcs_short(report_metadata["analysis_id"], 4, 8)
    custody_detail = (
        f"Event #{custody_rows[-1]['event_id']} · {'chain intact' if chain_ok else 'chain check failed'}"
        if custody_rows else "No custody events"
    )

    flash = st.session_state.pop("fcf_flash", None)
    if flash:
        st.success(flash)

    from forenchain.report_finalization import (
        FinalizationError, finalization_readiness, finalize_report, latest_finalization,
    )
    can_finalize = has_permission(user["role"], "finalize_report")
    finalized = latest_finalization(selected_id, user["user_id"])
    latest_ids = query_all(
        """
        SELECT finding_id, analysis_id
        FROM examiner_findings
        WHERE evidence_id = ? AND examiner_user_id = ?
        ORDER BY recorded_at DESC
        LIMIT 1
        """,
        (selected_id, int(user["user_id"])),
    )
    latest_finding_id = latest_ids[0]["finding_id"] if latest_ids else None
    finalized_current = finalized is not None and finalized["finding_id"] == latest_finding_id

    def _fcf_download(metadata, label, primary):
        try:
            pdf_bytes = build_forensic_report_pdf(metadata, original, heatmap)
            st.download_button(
                label,
                data=pdf_bytes,
                file_name=f"ForenChain_Report_{selected_id}_DRAFT.pdf",
                mime="application/pdf",
                key="download_forensic_report",
                type="primary" if primary else "secondary",
                width="stretch",
            )
        except Exception as exc:
            st.error(f"Unable to generate forensic report: {exc}")

    # FC_EXAMINER_FINDINGS_FORM_V1
    def _fcf_form():
        with st.form("examiner_findings_form", border=False):
            conclusion = st.radio(
                "Examiner conclusion",
                [
                    "Requires further examination",
                    "No conclusion reached",
                    "Potential signs of manipulation",
                    "No obvious signs of manipulation detected",
                ],
            )
            notes = st.text_area(
                "Findings and observations",
                placeholder="Describe observations, limitations, and any corroborating checks.",
                height=170,
            )
            note_col, button_col = st.columns([1.25, 1], vertical_alignment="center")
            with note_col:
                st.markdown(
                    '<div class="fcf-note">Saved findings are included in the forensic report</div>',
                    unsafe_allow_html=True,
                )
            with button_col:
                save_finding = st.form_submit_button(
                    "Save findings · unlock report",
                    type="primary",
                    width="stretch",
                )

        if save_finding:
            try:
                finding_id = "FN-" + uuid.uuid4().hex[:16].upper()
                analysis_id = saved.get("analysis_id", latest.get("analysis_id"))
                save_examiner_finding(
                    finding_id=finding_id,
                    evidence_id=selected_id,
                    examiner_user_id=int(user["user_id"]),
                    analysis_id=analysis_id,
                    conclusion=conclusion,
                    notes=notes,
                )
                st.session_state["fcf_flash"] = "Examiner findings saved. Download a new PDF to include them."
                st.rerun()
            except (ValueError, PermissionError, sqlite3.Error) as exc:
                st.error(str(exc))

    if finalized_current:
        _fcr_finalized_panel(user, finalized)
        if can_record:
            with st.expander("Record amended findings (creates a new report version)"):
                with st.container(key="fcf_form_card"):
                    _fcf_form()
    else:
        st.markdown(
            '<div class="fcf-head"><div>'
            f'<div class="fcs-ov">Case {_html.escape(case_id)} · Step 5 of 6</div>'
            '<div class="fcs-h1">Record your findings.</div>'
            '<div class="fcs-sub">Your conclusion is the last step before the report can be finalized.</div>'
            '</div><span class="fcf-step"><i></i>'
            + ("Findings recorded" if latest_finding else "Step 5 of 6")
            + '</span></div>',
            unsafe_allow_html=True,
        )
        steps = [
            ("folder", "Registered", f"{registered_by} · {registered_on}", "done"),
            ("shield", "Integrity verified",
             "SHA-256 match · 64/64" if integrity_ok else f"Status: {integrity_status}",
             "done" if integrity_ok else "bad"),
            ("link", "Custody logged", custody_detail, "done" if custody_rows else "todo"),
            ("scan", "AI screened", f"MVSS-Net · {_fcs_short(report_metadata['analysis_id'], 4, 4)}", "done"),
            ("file", "Findings recorded",
             latest_finding.get("conclusion", "Awaiting conclusion"),
             "done" if latest_finding else "next"),
            ("lock", "Report finalized",
             (f"v{finalized['version']} finalized · amendment pending" if finalized is not None
              else ("Ready to finalize" if latest_finding else "After findings")),
             "next" if latest_finding else "todo"),
        ]
        st.markdown(_fcf_trail(steps), unsafe_allow_html=True)

        form_col, report_col = st.columns([1.5, 1], gap="medium")
        with form_col:
            with st.container(key="fcf_form_card"):
                if can_record:
                    _fcf_form()
                else:
                    st.info("Your role cannot record examiner findings.")

        with report_col:
            with st.container(key="fcf_report_card"):
                checks = "".join(
                    f'<div class="fcs-check"><span style="color:#18B8A6">{_fcs_icon("check", 15, 2.2)}</span>{item}</div>'
                    for item in [
                        "Evidence identity and SHA-256 fingerprints",
                        "Integrity verification status",
                        "Model response score and inference device",
                        "Examiner conclusion and notes",
                    ]
                )
                preview = (
                    '<div class="fcs-k">Forensic report · PDF</div>'
                    f'<div class="fcs-h1" style="font-size:40px;margin:10px 0 2px">{_html.escape(case_id)}</div>'
                    f'<div class="fcs-mono" style="font-size:11.5px;color:#7C889C;margin-bottom:14px">{_html.escape(selected_id)}</div>'
                    f'{checks}'
                )
                if not integrity_ok:
                    if integrity_status == "HASH_MISMATCH":
                        st.error("Evidence integrity: hash mismatch")
                    else:
                        st.warning(f"Evidence integrity status: {integrity_status}")
                if can_record and not latest_finding:
                    dots = "".join("<b></b>" for _ in range(36))
                    st.markdown(
                        f'<div class="fcf-locked"><div class="fcf-dots">{dots}</div>'
                        f'<div class="ghost">{preview}</div>'
                        f'<div class="fcf-lockmid"><div class="fcf-lockic">{_fcf_icon("lock", 34, 1.9)}</div>'
                        '<b>Report locked</b><span>Save findings to unlock</span></div></div>',
                        unsafe_allow_html=True,
                    )
                    _fcf_download(report_metadata, "Download draft report (PDF)", False)
                else:
                    st.markdown(preview, unsafe_allow_html=True)
                    if latest_finding and can_finalize:
                        readiness = finalization_readiness(
                            user["user_id"], selected_id, saved.get("analysis_id")
                        )
                        rc = readiness.get("checks", {})

                        def _row(label, ok, text):
                            mark = '<span class="ok">✓ ' if ok else '<span class="no">✕ '
                            return f'<div class="r"><span>{label}</span>{mark}{_html.escape(text)}</span></div>'

                        st.markdown(
                            '<div class="fcr-checks">'
                            + _row("Integrity", rc.get("integrity") == "INTEGRITY_OK",
                                   "SHA-256 match" if rc.get("integrity") == "INTEGRITY_OK"
                                   else str(rc.get("integrity", "not checked")))
                            + _row("Custody chain", bool(rc.get("custody_chain_valid")) and rc.get("custody_event_count", 0) > 0,
                                   f"valid · {rc.get('custody_event_count', 0)} event{'' if rc.get('custody_event_count', 0) == 1 else 's'}" if rc.get("custody_chain_valid")
                                   else "not valid")
                            + _row("AI analysis", bool(rc.get("analysis")) and bool(rc.get("analysis_hash_match")),
                                   "linked · hashes match" if rc.get("analysis_hash_match") else "not linked")
                            + _row("Findings", bool(rc.get("findings")),
                                   "recorded for this analysis" if rc.get("findings") else "missing or for another analysis")
                            + '</div>',
                            unsafe_allow_html=True,
                        )
                        with st.container(key="fcr_finalize_box"):
                            if not readiness["ready"]:
                                st.warning(readiness["reason"])
                            else:
                                acknowledged = False
                                if readiness.get("qualified"):
                                    acknowledged = st.checkbox(
                                        f"Finalize with the qualified conclusion “{readiness['conclusion']}”. "
                                        "The report will not state a definitive finding.",
                                        key="fcr_ack",
                                    )
                                reason = ""
                                if finalized is not None:
                                    reason = st.text_input(
                                        f"Reason for amending v{finalized['version']}",
                                        key="fcr_reason",
                                        placeholder="Why does this report replace the finalized version?",
                                    )
                                if st.button("Finalize report", type="primary", key="fcr_finalize", width="stretch"):
                                    try:
                                        new_record, created = finalize_report(
                                            user["user_id"], selected_id, saved.get("analysis_id"), heatmap,
                                            acknowledge_qualified=acknowledged, amendment_reason=reason,
                                        )
                                        st.session_state["fcf_flash"] = (
                                            f"Report finalized as version {new_record['version']}."
                                            if created else
                                            "This report was already finalized. No new version was created."
                                        )
                                        st.rerun()
                                    except (FinalizationError, PermissionError) as exc:
                                        st.error(str(exc))
                    st.markdown(
                        '<div class="fcf-note" style="margin:10px 0 6px">Draft PDFs are regenerated on each '
                        'download and are not a finalized record.</div>',
                        unsafe_allow_html=True,
                    )
                    _fcf_download(report_metadata, "Download draft report (PDF)", False)

    with st.expander("Analysis history for this evidence"):
        history = query_all(
            """
            SELECT analysis_id, examiner_user_id, model_name,
                   model_response_score, inference_device, analyzed_at
            FROM analysis_records
            WHERE evidence_id = ?
            ORDER BY analyzed_at DESC
            """,
            (selected_id,),
        )
        if history:
            st.dataframe(history, hide_index=True, width="stretch")
        else:
            st.info("No saved analysis records for this evidence.")


# FC_RESPONSIVE_BEGIN
def _fc_responsive_css():
    """Responsive layer for phones and tablets. Desktop (> 768px) is unchanged."""
    st.markdown(
        """
<style>
/* FORENCHAIN_RESPONSIVE_V1 */
/* Long identifiers, file names and hashes wrap inside their own box at every width. */
.fcs-empty b, .fcs-empty span, .fcd-step small, .fcf-s span.d, .fcf-meta,
.fci-card span.s, .fcs-kv span:last-child, .fcd-case b, .fcd-case span {
  overflow-wrap: anywhere;
}
.fcs-empty { max-width: 100%; box-sizing: border-box; }

@media (max-width: 900px) {
  /* Tablets: these card rows stack full-width (Streamlit only stacks columns below 640px). */
  .stApp [data-testid="stHorizontalBlock"]:has(.fcd-pn),
  .stApp [data-testid="stHorizontalBlock"]:has(.st-key-fcs_viewer_panel),
  .stApp [data-testid="stHorizontalBlock"]:has(.st-key-fcf_form_card),
  .stApp .st-key-fcf_sealed [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap;
  }
  .stApp [data-testid="stHorizontalBlock"]:has(.fcd-pn) > [data-testid="stColumn"],
  .stApp [data-testid="stHorizontalBlock"]:has(.st-key-fcs_viewer_panel) > [data-testid="stColumn"],
  .stApp [data-testid="stHorizontalBlock"]:has(.st-key-fcf_form_card) > [data-testid="stColumn"],
  .stApp .st-key-fcf_sealed [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 100% !important;
  }
  /* Finalized-report buttons: full labels, centred, not over-wide. */
  .stApp .st-key-fcf_sealed [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    max-width: 440px;
    margin: 0 auto;
  }
  .stApp .st-key-fcf_sealed button p { white-space: normal; }
}

@media (max-width: 768px) {
  /* Comfortable touch targets (about 44px). */
  .stApp [data-testid="stButton"] button,
  .stApp [data-testid="stDownloadButton"] button,
  .stApp [data-testid="stFormSubmitButton"] button,
  .stApp [data-baseweb="tab"],
  .stApp [data-testid="stExpander"] summary,
  .stApp [data-baseweb="select"] > div,
  .stApp [data-testid="stTextInputRootElement"] {
    min-height: 44px;
  }
  .stApp [data-testid="stCheckbox"] label { min-height: 44px; align-items: center; }
  /* 16px text in fields stops iPhones from zooming in on focus. */
  .stApp [data-testid="stTextInputRootElement"] input, .stApp [data-testid="stTextArea"] textarea,
  .stApp [data-baseweb="select"] input { font-size: 16px; }
  .stApp [data-testid="stTextInputRootElement"] input { min-height: 42px; }
  .stApp .st-key-forensics_comparison_view [role="radiogroup"] label { min-height: 40px; display: flex; align-items: center; }
  /* The small "Verify integrity" text link in the Run card. */
  .stApp .st-key-fcs_run_card button[kind^="secondary"] { min-height: 44px !important; transform: none; }

  /* Findings header: title above the step pill. */
  .stApp .fcf-head { flex-direction: column; align-items: flex-start; gap: 12px; }
}

@media (max-width: 640px) {
  /* Six-step evidence trails: three steps per row instead of six squeezed columns. */
  .stApp .fcd-trail, .stApp .fcf-trail { flex-wrap: wrap; row-gap: 18px; }
  .stApp .fcd-link, .stApp .fcf-line { display: none; }
  .stApp .fcd-step, .stApp .fcf-s { flex: 0 0 33.333%; padding: 0 4px; box-sizing: border-box; }
  .stApp .fcf-trail { padding: 20px 10px 18px; }

  /* Single-column cards. */
  .stApp .st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] { grid-template-columns: 1fr; }
  .stApp .st-key-fcf_form_card [data-testid="stRadio"] [role="radiogroup"] label { min-height: 0; }
  .stApp .fcf-stats { grid-template-columns: 1fr; }

  /* Tighter card padding so content keeps its width. */
  .stApp .st-key-fcs_viewer_panel, .stApp .st-key-fcs_score_card, .stApp .st-key-fcs_run_card,
  .stApp .st-key-fcf_form_card, .stApp .st-key-fcf_report_card {
    padding: 16px 14px !important;
  }
  .stApp .st-key-fcf_sealed { padding: 30px 16px 26px !important; }
  .stApp .fcf-seal { width: 190px; height: 190px; }
  .stApp .fcf-seal svg { width: 190px; height: 190px; }
  .stApp .fcf-seal .g { width: 86px; }
  .stApp .fcf-locked { min-height: 240px; }
}
</style>
""",
        unsafe_allow_html=True,
    )
# FC_RESPONSIVE_END


def main():
    _fc_responsive_css()
    if initial_admin_required():
        first_admin_setup()
        return

    user = st.session_state.get("user")
    if user is None:
        login_screen()
        return

    if user.get("must_change_password"):
        password_change_screen(user)
        return

    show_header(user)
    show_dashboard_metrics(user)


    show_recent_evidence(user)

    tabs = []

    if has_permission(user["role"], "manage_users"):
        tabs.append(("User Management", lambda: user_management(user)))

    if has_permission(user["role"], "register_evidence"):
        tabs.append(("Register Evidence", lambda: register_evidence_screen(user)))

    if has_permission(user["role"], "verify_integrity"):
        tabs.append(("Verify Integrity", lambda: integrity_screen(user)))

    if has_permission(user["role"], "view_evidence"):
        tabs.append(("Evidence Records", lambda: evidence_records_screen(user)))
        tabs.append(("Chain of Custody", lambda: custody_screen(user)))

    if has_permission(user["role"], "analyze_image"):
        tabs.append(("AI Screening", lambda: ai_screening_screen(user)))

    if has_permission(user["role"], "view_audit") and not has_permission(
        user["role"], "view_evidence"
    ):
        tabs.append(("Chain of Custody", lambda: custody_screen(user)))

    if not tabs:
        st.warning("No features are assigned to this account.")
        return

    rendered_tabs = st.tabs([item[0] for item in tabs])
    for tab, (_, render_function) in zip(rendered_tabs, tabs):
        with tab:
            render_function()

    st.divider()


if __name__ == "__main__":
    main()




