"""
app.py — PII Detection Pipeline v3
Professional Next.js/React aesthetic
Run with: streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.chdir(os.path.abspath(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd

from pipeline import Pipeline

st.set_page_config(
    page_title="PII Detection Pipeline",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/*
  ── Design tokens (dark canvas) ──────────────────────────────────
  Frame + Canvas are now one continuous dark instrument panel.

  Ink Navy     #0B1120  frame + canvas background
  Panel        #131C2E  card surfaces
  Panel Hover  #18223A  card hover / inset surfaces
  Hairline     #1B2436  borders
  Text Bright  #F8FAFC  primary text
  Text Mid     #C7D2E0  secondary text
  Text Dim     #6B7793  tertiary / meta text
  Signal       #818CF8  brand / primary action (brighter for dark bg)

  Category colours (data classification, not risk):
  PII          #F87171  red
  PHI          #991B1B  dark red
  Financial    #C084FC  purple
  Other        #FACC15  yellow
*/

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"], .stApp {
    background: #0B1120 !important;
    color: #F8FAFC !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-size: 16px !important;
    line-height: 1.6 !important;
}

/* faint blueprint-grid texture so the canvas reads as instrumented, not blank */
.stApp {
    background-image: radial-gradient(circle, rgba(129,140,248,0.10) 1px, transparent 1px) !important;
    background-size: 22px 22px !important;
}

/* ── Sidebar (dark frame) ── */
[data-testid="stSidebar"] {
    background: #0B1120 !important;
    border-right: 1px solid #1B2436 !important;
    padding-top: 0 !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

.sidebar-logo {
    padding: 20px 16px 16px;
    border-bottom: 1px solid #1B2436;
    margin-bottom: 16px;
}
.sidebar-logo-text {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 17px;
    font-weight: 700;
    color: #F8FAFC;
    letter-spacing: -0.01em;
}
.sidebar-logo-text span { color: #818CF8; }
.sidebar-logo-sub {
    font-size: 13px;
    color: #8B95AC;
    margin-top: 3px;
    font-family: 'JetBrains Mono', monospace;
}

[data-testid="stSidebar"] label {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #A5B4FC !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #131C2E !important;
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
    font-size: 15px !important;
}
[data-testid="stSidebar"] p {
    color: #8B95AC !important;
    font-size: 14px !important;
}
[data-testid="stSidebar"] hr {
    border-color: #1B2436 !important;
    margin: 12px 0 !important;
}

/* ── Main ── */
.main .block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* ── Top nav (dark frame) ── */
.topnav {
    height: 54px;
    background: #0B1120;
    border-bottom: 1px solid #1B2436;
    display: flex;
    align-items: center;
    padding: 0 28px;
    gap: 32px;
    position: sticky;
    top: 0;
    z-index: 100;
}
.topnav-brand {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: #F8FAFC;
    letter-spacing: -0.01em;
    display: flex;
    align-items: center;
    gap: 8px;
}
.topnav-brand span { color: #818CF8; }
.topnav-badge {
    font-size: 13px;
    padding: 2px 8px;
    background: #1B2350;
    color: #A5B4FC;
    border-radius: 99px;
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid #2D3A6E;
}
.topnav-links {
    display: flex;
    gap: 4px;
    margin-left: auto;
}
.topnav-link {
    font-size: 14px;
    padding: 5px 12px;
    border-radius: 6px;
    color: #6B7793;
    cursor: pointer;
    transition: all 0.15s;
}
.topnav-link:hover { background: #131C2E; color: #E2E8F0; }
.topnav-link.active { background: #1B2350; color: #A5B4FC; }
.topnav-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #6B7793;
    font-family: 'JetBrains Mono', monospace;
}
.status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #34D399;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* ── Page body (dark canvas) ── */
.page-body {
    padding: 28px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    min-height: calc(100vh - 54px);
}

/* ── Cards (panel surfaces) ── */
.card {
    background: #131C2E;
    border: 1px solid #1B2436;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.2);
    position: relative;
}
.card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #4338CA, #818CF8);
}
.card-header {
    padding: 14px 20px;
    border-bottom: 1px solid #1B2436;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.card-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #F8FAFC;
    display: flex;
    align-items: center;
    gap: 8px;
}
.card-title-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #818CF8;
}
.card-body { padding: 20px; }
.card-meta {
    font-size: 13px;
    color: #6B7793;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Metric grid ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}
.metric-card {
    background: #131C2E;
    border: 1px solid #1B2436;
    border-radius: 10px;
    padding: 16px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.3);
    transition: border-color 0.2s, box-shadow 0.2s;
}
.metric-card:hover { border-color: #2D3A6E; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }
.metric-card::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 3px;
}
/* category-driven accents: PII red · PHI dark red · Financial purple · Other yellow */
.mc-pii::after   { background: #F87171; }
.mc-phi::after   { background: #991B1B; }
.mc-fin::after   { background: #C084FC; }
.mc-other::after { background: #FACC15; }
.mc-risk-high::after   { background: #F87171; }
.mc-risk-medium::after { background: #FACC15; }
.mc-risk-low::after    { background: #34D399; }
.mc-risk-none::after   { background: #3D4A6B; }

.metric-label {
    font-size: 13px;
    font-weight: 700;
    color: #8B95AC;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
}
.metric-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 42px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    font-feature-settings: "tnum";
}
.mv-pii   { color: #F87171; }
.mv-phi   { color: #EF4444; }
.mv-fin   { color: #C084FC; }
.mv-other { color: #FACC15; }
.mv-high  { color: #F87171; font-size: 29px; padding-top: 4px; }
.mv-medium{ color: #FACC15; font-size: 29px; padding-top: 4px; }
.mv-low   { color: #34D399; font-size: 29px; padding-top: 4px; }
.mv-none  { color: #6B7793; font-size: 29px; padding-top: 4px; }

.metric-sub {
    font-size: 13px;
    color: #6B7793;
    margin-top: 4px;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Textarea ── */
.stTextArea textarea {
    background: #0F1626 !important;
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 15px !important;
    line-height: 1.7 !important;
    caret-color: #818CF8 !important;
    transition: border-color 0.2s !important;
}
.stTextArea textarea:focus {
    border-color: #818CF8 !important;
    box-shadow: 0 0 0 3px rgba(129,140,248,0.18) !important;
    outline: none !important;
}
.stTextArea textarea::placeholder { color: #4B5775 !important; }

/* ── Selectbox (main canvas) ── */
[data-baseweb="select"] > div {
    background: #0F1626 !important;
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
    font-size: 15px !important;
    transition: border-color 0.2s !important;
}
[data-baseweb="select"] > div:focus-within {
    border-color: #818CF8 !important;
    box-shadow: 0 0 0 3px rgba(129,140,248,0.18) !important;
}
[data-baseweb="popover"] {
    background: #131C2E !important;
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    box-shadow: 0 8px 20px rgba(0,0,0,0.5) !important;
}
[data-baseweb="menu"] { background: #131C2E !important; }
[role="option"] { color: #E2E8F0 !important; font-size: 15px !important; }
[role="option"]:hover { background: #18223A !important; }

/* ── Radio ── */
[data-testid="stRadio"] label {
    font-size: 15px !important;
    color: #C7D2E0 !important;
    font-weight: 400 !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
}

/* ── Button ── */
.stButton > button {
    background: #4338CA !important;
    border: none !important;
    border-radius: 8px !important;
    color: #fff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    padding: 0.65rem 1.4rem !important;
    width: 100% !important;
    transition: all 0.15s !important;
    cursor: pointer !important;
}
.stButton > button:hover {
    background: #4F46E5 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(67,56,202,0.4) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
    box-shadow: none !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #1B2436 !important;
    gap: 0 !important;
    padding: 0 4px !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    color: #6B7793 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 15px !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 8px 14px !important;
    border-radius: 0 !important;
    transition: all 0.15s !important;
    text-transform: none !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover { color: #C7D2E0 !important; }
[data-testid="stTabs"] [aria-selected="true"] {
    color: #A5B4FC !important;
    border-bottom-color: #818CF8 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
    padding: 16px 0 0 !important;
    background: transparent !important;
}

/* ── Highlighted text ──
   Category-driven, not risk-driven:
   PII = red · PHI = dark red · Financial = purple · Other = yellow
*/
.hl-wrap {
    background: #0F1626;
    border: 1px solid #1B2436;
    border-radius: 8px;
    padding: 18px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    line-height: 1.9;
    color: #C7D2E0;
    white-space: pre-wrap;
    word-break: break-word;
}
.hl-pii {
    background: rgba(248,113,113,0.18);
    color: #FCA5A5;
    border: 1px solid rgba(248,113,113,0.45);
    border-radius: 4px;
    padding: 1px 5px;
    font-weight: 700;
    cursor: default;
    transition: background 0.15s;
}
.hl-pii:hover { background: rgba(248,113,113,0.3); }
.hl-phi {
    background: rgba(153,27,27,0.32);
    color: #FCA5A5;
    border: 1px solid rgba(153,27,27,0.65);
    border-radius: 4px;
    padding: 1px 5px;
    font-weight: 700;
    cursor: default;
}
.hl-phi:hover { background: rgba(153,27,27,0.45); }
.hl-fin {
    background: rgba(192,132,252,0.18);
    color: #D8B4FE;
    border: 1px solid rgba(192,132,252,0.45);
    border-radius: 4px;
    padding: 1px 5px;
    font-weight: 700;
    cursor: default;
}
.hl-fin:hover { background: rgba(192,132,252,0.3); }
.hl-other {
    background: rgba(250,204,21,0.16);
    color: #FDE047;
    border: 1px solid rgba(250,204,21,0.4);
    border-radius: 4px;
    padding: 1px 5px;
    font-weight: 700;
    cursor: default;
}
.hl-other:hover { background: rgba(250,204,21,0.28); }

/* ── Legend pills ── */
.legend {
    display: flex;
    gap: 8px;
    margin-top: 14px;
    flex-wrap: wrap;
}
.legend-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 99px;
    font-size: 13px;
    font-weight: 700;
    border: 1px solid;
}
.lp-pii   { background: rgba(248,113,113,0.15); color: #FCA5A5; border-color: rgba(248,113,113,0.4); }
.lp-phi   { background: rgba(153,27,27,0.28);   color: #FCA5A5; border-color: rgba(153,27,27,0.55); }
.lp-fin   { background: rgba(192,132,252,0.15); color: #D8B4FE; border-color: rgba(192,132,252,0.4); }
.lp-other { background: rgba(250,204,21,0.14);  color: #FDE047; border-color: rgba(250,204,21,0.35); }

/* ── Code block ── */
.stCode, pre, code {
    background: #0F1626 !important;
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 14px !important;
    color: #C7D2E0 !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}
[data-testid="stDataFrame"] table {
    background: #131C2E !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 15px !important;
}
[data-testid="stDataFrame"] th {
    background: #0F1626 !important;
    color: #8B95AC !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid #1B2436 !important;
    padding: 8px 12px !important;
}
[data-testid="stDataFrame"] td {
    color: #E2E8F0 !important;
    border-bottom: 1px solid #18223A !important;
    padding: 10px 12px !important;
}
[data-testid="stDataFrame"] tr:hover td { background: #18223A !important; }

/* ── Compliance bars ── */
.comp-card {
    background: #0F1626;
    border: 1px solid #1B2436;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
}
.comp-card:hover { border-color: #2D3A6E; }
.comp-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.comp-name {
    font-size: 15px;
    font-weight: 700;
    color: #E2E8F0;
    font-family: 'JetBrains Mono', monospace;
}
.comp-badge {
    font-size: 13px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 99px;
}
.cb-high   { background: rgba(248,113,113,0.18); color: #FCA5A5; }
.cb-medium { background: rgba(250,204,21,0.16);  color: #FDE047; }
.cb-low    { background: rgba(52,211,153,0.16);  color: #6EE7B7; }
.comp-bar-bg {
    height: 5px;
    background: #1B2436;
    border-radius: 99px;
    overflow: hidden;
}
.comp-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.8s cubic-bezier(0.4,0,0.2,1);
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #0F1626 !important;
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    margin-bottom: 6px !important;
}
[data-testid="stExpander"] summary {
    font-size: 15px !important;
    color: #C7D2E0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    padding: 10px 14px !important;
}
[data-testid="stExpander"] summary:hover { color: #F8FAFC !important; }
[data-testid="stExpander"] p {
    font-size: 15px !important;
    color: #C7D2E0 !important;
    line-height: 1.6 !important;
}

/* ── Explanation ── */
.explain-card {
    background: #0F1626;
    border: 1px solid #1B2436;
    border-radius: 8px;
    padding: 20px;
    position: relative;
    overflow: hidden;
}
.explain-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, #4338CA, #818CF8);
    border-radius: 3px 0 0 3px;
}
.explain-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}
.explain-icon {
    width: 28px;
    height: 28px;
    background: #1B2350;
    border: 1px solid #2D3A6E;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
}
.explain-title {
    font-size: 16px;
    font-weight: 700;
    color: #A5B4FC;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
}
.explain-model {
    font-size: 13px;
    color: #6B7793;
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
}
.explain-body {
    font-size: 15px;
    line-height: 1.8;
    color: #E2E8F0;
    font-family: 'Inter', sans-serif;
}

/* ── Empty state ── */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    text-align: center;
    gap: 8px;
}
.empty-icon {
    width: 48px;
    height: 48px;
    background: #0F1626;
    border: 1px solid #1B2436;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    margin-bottom: 8px;
    color: #3D4A6B;
}
.empty-title {
    font-size: 15px;
    font-weight: 700;
    color: #E2E8F0;
}
.empty-sub {
    font-size: 13px;
    color: #6B7793;
    font-family: 'JetBrains Mono', monospace;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #0F1626 !important;
    border: 1px dashed #2D3A6E !important;
    border-radius: 8px !important;
    padding: 8px !important;
}
[data-testid="stFileUploader"] * { color: #8B95AC !important; font-size: 15px !important; }
[data-testid="stFileUploader"] button {
    background: #1B2350 !important;
    border: 1px solid #2D3A6E !important;
    border-radius: 6px !important;
    color: #A5B4FC !important;
    font-size: 15px !important;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    background: transparent !important;
    border: 1px solid #1B2436 !important;
    border-radius: 6px !important;
    color: #C7D2E0 !important;
    font-size: 15px !important;
    font-family: 'JetBrains Mono', monospace !important;
    transition: all 0.15s !important;
}
[data-testid="stDownloadButton"] button:hover {
    border-color: #818CF8 !important;
    color: #A5B4FC !important;
    background: #1B2350 !important;
}

/* ── Toggle ── */
[data-testid="stToggle"] { accent-color: #818CF8 !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] * { color: #A5B4FC !important; }

/* ── Alert ── */
[data-testid="stAlert"] {
    background: #0F1626 !important;
    border: 1px solid #1B2436 !important;
    border-radius: 8px !important;
    font-size: 15px !important;
    color: #E2E8F0 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0B1120; }
::-webkit-scrollbar-thumb { background: #2D3A6E; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #4B5775; }

/* ── Caption ── */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 14px !important;
    color: #8B95AC !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Hide Streamlit chrome */
footer, #MainMenu, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }
header { background: transparent !important; }

/* ── Prevent sidebar collapse ── */
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] {
    display: flex !important;
    visibility: visible !important;
    min-width: 240px !important;
    width: 240px !important;
    transform: none !important;
    left: 0 !important;
    position: relative !important;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Initialising PII Detection Pipeline...")
def get_pipeline():
    p = Pipeline(load_reasoner=True)
    p._detector.load()
    p._rag.load()
    p._reasoner.load()
    return p


# Category-driven highlight classes: PII = red, PHI = dark red,
# Financial = purple, anything else = yellow.
CATEGORY_CLS = {
    "PII": "hl-pii",
    "PHI": "hl-phi",
    "Financial": "hl-fin",
}

def highlight_html(text, findings):
    if not findings:
        return f'<div class="hl-wrap">{_esc(text)}</div>'
    sorted_f = sorted(findings, key=lambda f: f.start, reverse=True)
    chars = list(text)
    for f in sorted_f:
        cls = CATEGORY_CLS.get(f.category, "hl-other")
        val = text[f.start:f.end]
        span = f'<span class="{cls}" title="{f.entity_type} · {f.category} · {f.risk} risk · {f.source}">{_esc(val)}</span>'
        chars[f.start:f.end] = list(span)
    return f'<div class="hl-wrap">{"".join(chars)}</div>'

def _esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <div class="sidebar-logo-text">PII Detection <span>Pipeline</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Redaction**")
    redaction_mode = st.selectbox(
        "mode",
        ["redact", "mask", "replace"],
        format_func=lambda x: {
            "redact":  "Redact — [ENTITY_TYPE]",
            "mask":    "Mask — *** partial reveal",
            "replace": "Replace — synthetic values",
        }[x],
        label_visibility="collapsed",
    )

    st.markdown("**Reasoning**")
    use_reasoner = st.toggle("AI explanation (Gemini API)", value=True)

    st.markdown("---")
    st.markdown("""
    <div style="font-size:14px;color:#8B95AC;font-family:'JetBrains Mono',monospace;line-height:2.1;">
    OCR &nbsp;&nbsp;&nbsp; EasyOCR · PyMuPDF<br>
    NER &nbsp;&nbsp;&nbsp; Presidio · GLiNER<br>
    REGEX &nbsp; SSN · PAN · Aadhaar<br>
    RAG &nbsp;&nbsp;&nbsp; ChromaDB · MiniLM<br>
    LLM &nbsp;&nbsp;&nbsp; Gemini 2.5 Flash (API)
    </div>
    """, unsafe_allow_html=True)

# ── Top nav ───────────────────────────────────────────────────────────────────

st.markdown("""
<div class="topnav">
    <div class="topnav-brand">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M9 1L16 5V13L9 17L2 13V5L9 1Z" stroke="#818CF8" stroke-width="1.5" fill="rgba(129,140,248,0.18)"/>
            <path d="M9 6L12 8V12L9 14L6 12V8L9 6Z" fill="#818CF8"/>
        </svg>
        PII Detection <span>Pipeline</span>
    </div>
    <span class="topnav-badge">v3.0</span>
    <div class="topnav-links">
        <span class="topnav-link active">Scanner</span>
        <span class="topnav-link">Reports</span>
        <span class="topnav-link">Settings</span>
    </div>
    <div class="topnav-status">
        <div class="status-dot"></div>
        engine online
    </div>
</div>
""", unsafe_allow_html=True)


# ── Two column layout ─────────────────────────────────────────────────────────

SAMPLES = {
    "Medical record": """Patient: Sarah Mitchell
DOB: 03/14/1978 | SSN: 482-67-3901
MRN: MRN-20248819
Admitted: 2024-11-02 | Physician: Dr. James Okafor
Diagnosis: Type 2 Diabetes Mellitus (ICD-10: E11.9)
Medications: Metformin 500mg twice daily
Insurance ID: BCBS-TX-00291847
Contact: s.mitchell@email.com | (512) 445-9901""",

    "HR document": """Employee Record — Confidential
Name: Marcus T. Fernandez | Employee ID: EMP-44821
SSN: 319-55-7284 | DOB: September 8, 1985
Email: marcus.fernandez@acmecorp.com
Phone: +1 (404) 882-3310
Address: 2204 Peachtree Rd NW, Atlanta, GA 30309
Salary: $124,500/year
Bank Account: 7291048832 (Routing: 063100277)""",

    "Financial data": """Customer: Priya Nair | Account: 4521-XXXX-XXXX-8834
Credit Card: 4539 1488 0343 6467 (Exp: 09/26, CVV: 847)
IBAN: GB29NWBK60161331926819
Routing: 021000021
Wire Amount: $87,500.00
Email: p.nair@globaltrade.io
Passport No: P12983741""",
}

col_in, col_out = st.columns([1, 1], gap="medium")

with col_in:
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <div class="card-title">
                <div class="card-title-dot"></div>
                Input
            </div>
            <div class="card-meta">txt · pdf · png · jpg</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    input_mode = st.radio("type", ["Text", "File upload"], horizontal=True, label_visibility="collapsed")
    source = None
    filename = ""

    if input_mode == "Text":
        sample = st.selectbox(
            "sample",
            ["— select sample —"] + list(SAMPLES.keys()),
            label_visibility="collapsed"
        )
        default_text = SAMPLES.get(sample, "")
        text_input = st.text_area(
            "input",
            value=default_text,
            height=260,
            placeholder="// paste any text, JSON, CSV, or document content...",
            label_visibility="collapsed",
        )
        if text_input.strip():
            source = text_input
            filename = "input.txt"
    else:
        uploaded = st.file_uploader(
            "upload",
            type=["txt","pdf","png","jpg","jpeg","bmp","tiff"],
            label_visibility="collapsed",
        )
        if uploaded:
            source = uploaded.read()
            filename = uploaded.name
            st.markdown(f'<div style="font-size:15px;color:#6EE7B7;font-family:\'JetBrains Mono\',monospace;padding:4px 0;">✓ {filename} · {len(source):,} bytes</div>', unsafe_allow_html=True)

    scan = st.button("Run scan →", type="primary", use_container_width=True)


with col_out:
    st.markdown("""
    <div class="card" style="margin-bottom:0">
        <div class="card-header">
            <div class="card-title">
                <div class="card-title-dot" style="background:#34D399"></div>
                Results
            </div>
            <div class="card-meta" id="result-meta">awaiting input</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if scan and source:
        pipeline = get_pipeline()

        with st.spinner("scanning..."):
            result = pipeline.run(
                source=source,
                filename=filename,
                redaction_mode=redaction_mode,
                use_reasoner=use_reasoner,
            )

        s = result.summary
        risk = s["overall_risk"]
        risk_cls = {"High":"mc-risk-high","Medium":"mc-risk-medium","Low":"mc-risk-low"}.get(risk,"mc-risk-none")
        risk_val_cls = {"High":"mv-high","Medium":"mv-medium","Low":"mv-low"}.get(risk,"mv-none")

        total = s["categories"].get("PII",0) + s["categories"].get("PHI",0) + s["categories"].get("Financial",0)

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card mc-pii">
                <div class="metric-label">PII</div>
                <div class="metric-value mv-pii">{s['categories'].get('PII',0)}</div>
                <div class="metric-sub">identifiers</div>
            </div>
            <div class="metric-card mc-phi">
                <div class="metric-label">PHI</div>
                <div class="metric-value mv-phi">{s['categories'].get('PHI',0)}</div>
                <div class="metric-sub">health data</div>
            </div>
            <div class="metric-card mc-fin">
                <div class="metric-label">Financial</div>
                <div class="metric-value mv-fin">{s['categories'].get('Financial',0)}</div>
                <div class="metric-sub">records</div>
            </div>
            <div class="metric-card {risk_cls}">
                <div class="metric-label">Risk</div>
                <div class="metric-value {risk_val_cls}">{risk}</div>
                <div class="metric-sub">{total} total</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        tab_hl, tab_red, tab_find, tab_comp, tab_exp = st.tabs([
            "Highlighted", "Redacted", "Findings", "Compliance", "Explain"
        ])

        with tab_hl:
            st.markdown(highlight_html(result.original_text, result.findings), unsafe_allow_html=True)
            st.markdown("""
            <div class="legend">
                <span class="legend-pill lp-pii">PII</span>
                <span class="legend-pill lp-phi">PHI</span>
                <span class="legend-pill lp-fin">Financial</span>
                <span class="legend-pill lp-other">Other</span>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Colour reflects data category. Hover over any highlighted value to see entity type, risk level, and detection source.")

        with tab_red:
            st.code(result.redacted_text, language=None)
            fname = filename.rsplit('.', 1)[0] if '.' in filename else filename
            st.download_button(
                f"↓ Download {redaction_mode}ed output",
                data=result.redacted_text,
                file_name=f"{fname}_{redaction_mode}d.txt",
                mime="text/plain",
            )

        with tab_find:
            if result.findings:
                rows = [{
                    "Entity":    f.entity_type,
                    "Category":  f.category,
                    "Value":     f.value[:50] + ("…" if len(f.value) > 50 else ""),
                    "Risk":      f.risk,
                    "Conf":      f"{f.score:.0%}",
                    "Source":    f.source,
                } for f in result.findings]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-icon">✓</div>
                    <div class="empty-title">No findings</div>
                    <div class="empty-sub">// document appears clean</div>
                </div>""", unsafe_allow_html=True)

        with tab_comp:
            if result.compliance_exposure:
                for fw, score in sorted(result.compliance_exposure.items(), key=lambda x: -x[1]):
                    if score > 70:
                        badge_cls, badge_txt = "cb-high", "High exposure"
                    elif score > 40:
                        badge_cls, badge_txt = "cb-medium", "Moderate"
                    else:
                        badge_cls, badge_txt = "cb-low", "Low"
                    colour = "#F87171" if score > 70 else "#FACC15" if score > 40 else "#34D399"
                    st.markdown(f"""
                    <div class="comp-card">
                        <div class="comp-header">
                            <span class="comp-name">{fw}</span>
                            <span class="comp-badge {badge_cls}">{badge_txt} · {score:.0f}%</span>
                        </div>
                        <div class="comp-bar-bg">
                            <div class="comp-bar-fill" style="width:{score}%;background:{colour}"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown('<div style="margin-top:16px;margin-bottom:8px;font-size:12px;font-weight:700;color:#8B95AC;text-transform:uppercase;letter-spacing:0.1em;font-family:\'JetBrains Mono\',monospace;">Retrieved rules</div>', unsafe_allow_html=True)
                for rule in result.compliance_rules:
                    with st.expander(f"[{rule['framework']}] {rule['rule']}"):
                        st.markdown(f"**Description:** {rule['description']}")
                        st.markdown(f"**Entity types:** `{', '.join(rule['entity_types'])}`")
                        st.markdown(f"**Risk:** {rule['risk']} · **Relevance:** {rule['relevance']:.2f}")
            else:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-title">No matches</div>
                    <div class="empty-sub">// no compliance rules triggered</div>
                </div>""", unsafe_allow_html=True)

        with tab_exp:
            if result.explanation:
                st.markdown(f"""
                <div class="explain-card">
                    <div class="explain-header">
                        <div class="explain-icon">⬡</div>
                        <span class="explain-title">AI Risk Analysis</span>
                        <span class="explain-model">gemini-2.5-flash</span>
                    </div>
                    <div class="explain-body">{result.explanation}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-icon">⬡</div>
                    <div class="empty-title">AI explanation disabled</div>
                    <div class="empty-sub">// toggle on in sidebar to enable</div>
                </div>""", unsafe_allow_html=True)

        if result.warnings:
            with st.expander("⚠ warnings"):
                for w in result.warnings:
                    st.warning(w)

    elif scan and not source:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-title">No input</div>
            <div class="empty-sub">// paste text or upload a file first</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state" style="padding-top:80px">
            <div class="empty-icon" style="width:64px;height:64px;font-size:28px;">🛡</div>
            <div class="empty-title">Ready to scan</div>
            <div class="empty-sub">// paste text or upload a file · then run scan</div>
        </div>""", unsafe_allow_html=True)
