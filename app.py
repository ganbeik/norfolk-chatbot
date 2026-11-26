"""Norfolk County prosecution data chatbot (prototype).

Run:  streamlit run app.py
Needs an OpenRouter API key for written answers: OPENROUTER_API_KEY in a .env file next to
this script (never committed: .env is in .gitignore), in .streamlit/secrets.toml, or pasted
under Developer options. Without a key the app runs in offline mode and shows the closest
chart for each question.

Tabs: Ask (chatbot) · Explore charts (all charts by question) · About the data.
"""
from __future__ import annotations

import csv
import html as _html
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import core
from widget import chart_html

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
FEEDBACK_FILE = HERE / "feedback.csv"     # local only (gitignored); on Streamlit Cloud see the app logs

EXAMPLES = [
    "How did dismissals of domestic violence charges change from 2017 to 2025?",
    "Which district court has the highest share of cases with a dismissal?",
    "What are the most common crime types countywide?",
    "How have DV and sexual assault case numbers changed since 2017?",
    "What kinds of crimes most often end in a nolle prosequi in Superior Court?",
    "What is the race breakdown of victims?",
]

# Plain-language labels for the headline numbers (hover shows the exact definition).
KPI_LABELS = {
    "Charge rows, receipt cohort 2017–2025": "Charges received",
    "Distinct cases received": "Cases received",
    "Dated outcome rows in window": "Charges with an outcome",
    "Cases with any nolle prosequi": "Cases with a nolle prosequi",
}
DATA_RANGE = "2017–2025"
INTRO = ("Ask about case volume, outcomes, dismissals, nolle prosequi and courts in Norfolk County, "
         "for charges received 2017–2025. Answers use only the summary numbers from the DA's data, "
         "and each one comes with its chart.")
NOTICE = ("Prototype: answers are written by an AI model from the data's summary tables. "
          "Check important numbers against the chart shown with each answer.")

st.set_page_config(page_title="Norfolk County Prosecution Data Explorer", page_icon="⚖️", layout="wide")

# Styling on top of the theme in .streamlit/config.toml (same colors as the dashboard charts).
# Hides Streamlit's own menu, toolbar, top stripe and footer so the page reads as one product.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {--navy: #1b365d; --accent: #1f4e8c; --ink: #1f2937; --muted: #5b6472;
       --line: #e2e6ec; --card: #ffffff; --page: #f5f7fa;}
.stApp {background: var(--page);}
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
.stApp button, .stApp input, .stApp textarea, .app-header {font-family: 'Inter', system-ui, sans-serif;}
.stApp p, .stApp li {font-size: 1rem; line-height: 1.6; color: var(--ink);}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
#MainMenu, footer {visibility: hidden; height: 0;}
header[data-testid="stHeader"] {background: transparent;}
[data-testid="stMain"] .block-container, [data-testid="stMainBlockContainer"] {max-width: 1120px; padding-top: 1.25rem;}
[data-testid="stSidebar"] {background: #eef1f5; border-right: 1px solid var(--line);}
.app-header {display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
             padding: 20px 28px; margin-bottom: 0.5rem; background: var(--navy); border-radius: 14px;}
.app-header .name {font-size: 1.6rem; font-weight: 700; color: #ffffff; letter-spacing: -0.015em;}
.app-header .sub {font-size: 0.95rem; color: #c9d6ea; margin-top: 4px;}
.app-header .badge {display: inline-block; margin-left: 12px; padding: 3px 10px; border-radius: 999px;
                    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
                    vertical-align: middle; color: var(--navy); background: #dbe6f5;}
.app-header .range {text-align: right; font-size: 0.85rem; color: #c9d6ea; line-height: 1.4;}
.app-header .range b {display: block; font-size: 1.35rem; font-weight: 700; color: #ffffff;}
.stTabs [role="tablist"] {gap: 6px !important; border-bottom: 1px solid #e2e6ec;}
.stTabs [role="tab"] {padding: 10px 18px !important; margin: 0 !important; border-radius: 10px 10px 0 0; transition: background .15s;}
.stTabs [role="tab"] p {font-size: 1.02rem !important; font-weight: 500 !important; color: #6b7480 !important;}
.stTabs [role="tab"]:hover {background: #eef2f8;}
.stTabs [role="tab"]:hover p {color: #1f4e8c !important;}
.stTabs [role="tab"][aria-selected="true"] {background: #ffffff;}
.stTabs [role="tab"][aria-selected="true"] p {color: #1b365d !important; font-weight: 700 !important;}
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"] {background: #1b365d !important; height: 3px !important;}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {font-size: 0.9rem; color: var(--muted) !important; opacity: 1 !important;}
[data-testid="stMetric"] {background: var(--card); border: 1px solid var(--line); border-radius: 12px;
                          padding: 14px 18px; min-height: 118px; display: flex; flex-direction: column;
                          justify-content: space-between;}
[data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] div {font-size: 0.85rem; font-weight: 600; color: var(--muted);
                                 white-space: normal !important; overflow: visible !important; text-overflow: clip !important;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {font-size: 1.9rem !important; font-weight: 700 !important;
                                 color: var(--navy) !important; line-height: 1.2 !important;}
.stButton button {width: 100%; min-height: 4.4rem; align-items: center; padding: 10px 16px; border-radius: 10px;
                  justify-content: flex-start; text-align: left;
                  border: 1px solid var(--line); background: var(--card); color: var(--ink);}
.stButton button > div, .stButton button [data-testid="stMarkdownContainer"] {width: 100%; justify-content: flex-start;}
.stButton button p {text-align: left; width: 100%; white-space: normal; font-size: 0.95rem; font-weight: 500;}
.stButton button:hover {border-color: var(--accent); background: #f3f7fc;}
.stButton button:hover p {color: var(--accent);}
[data-testid="stChatInput"] {border-radius: 12px;}
[data-testid="stChatInput"] textarea {font-size: 1rem;}
[data-testid="stVerticalBlockBorderWrapper"], [class*="st-key-answer_card"] {background: var(--card);
    border-color: var(--line) !important; border-radius: 12px;}
[class*="st-key-answer_card"] {padding: 20px 24px;}
[data-testid="stChatMessage"] {background: transparent;}
.stApp [data-testid="stChatInput"], .stApp [data-testid="stChatInput"] > div {background: var(--card); border-color: var(--line);}
.section-title {font-size: 1.25rem; font-weight: 700; color: var(--navy); margin: 0.5rem 0 0.25rem;}
.section-label {font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: uppercase;
                letter-spacing: 0.04em; margin: 1.25rem 0 0.5rem;}
.user-row {display: flex; justify-content: flex-end; margin: 10px 0 2px;}
.user-bubble {max-width: 75%; background: #1b365d; color: #ffffff; padding: 10px 16px; line-height: 1.5;
              border-radius: 16px 16px 4px 16px; font-weight: 500; font-family: 'Inter', system-ui, sans-serif;}
[data-testid="stButtonGroup"] {gap: 8px !important; flex-wrap: wrap;}
[data-testid="stButtonGroup"] button {border-radius: 999px !important; border: 1px solid #d5dbe3 !important;
  background: #ffffff !important; padding: 6px 16px !important; min-height: 2.3rem !important; margin: 0 !important;
  box-shadow: none !important; transition: all .15s;}
[data-testid="stButtonGroup"] button p {font-size: 0.9rem !important; font-weight: 500 !important; color: #3c4654 !important; white-space: nowrap;}
[data-testid="stButtonGroup"] button:hover {border-color: #1f4e8c !important; background: #f3f7fc !important;}
[data-testid="stButtonGroup"] button:hover p {color: #1f4e8c !important;}
[data-testid="stButtonGroup"] button[aria-checked="true"] {background: #1b365d !important; border-color: #1b365d !important;}
[data-testid="stButtonGroup"] button[aria-checked="true"] p {color: #ffffff !important; font-weight: 600 !important;}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_store() -> core.Store:
    return core.Store.load(DATA_DIR)


def load_dotenv(path: Path = HERE / ".env") -> None:
    """Read KEY=value lines from .env into the environment (no extra package needed)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()


def get_api_key() -> str | None:
    if st.session_state.get("api_key"):
        return st.session_state.api_key
    try:
        if "OPENROUTER_API_KEY" in st.secrets:   # Streamlit Cloud: app settings -> Secrets
            return st.secrets["OPENROUTER_API_KEY"]
    except Exception:  # no secrets file
        pass
    return os.environ.get("OPENROUTER_API_KEY")


def wide_button(label, **kw):
    """Full-width button on any Streamlit version (width= is newer, use_container_width= older)."""
    try:
        return st.button(label, width="stretch", **kw)
    except TypeError:
        return st.button(label, use_container_width=True, **kw)


def show_figure(fig, key):
    try:
        st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})
    except TypeError:  # older Streamlit
        st.plotly_chart(fig, use_container_width=True, key=key, config={"displaylogo": False})


def card(key: str | None = None):
    """Bordered container on any Streamlit version (key gives it a CSS class: st-key-<key>)."""
    try:
        return st.container(border=True, key=key)
    except TypeError:
        try:
            return st.container(border=True)
        except TypeError:
            return st.container()


# ----------------------------------------------------------------------------- answer helpers
FOLLOWUP_RE = re.compile(r"^\s*\**follow-?ups?:?\**\s*:?\s*(.+)$", re.IGNORECASE)


def split_followups(text: str) -> tuple[str, list[str]]:
    """Take the model's last 'Follow-ups: a | b | c' line off the answer text."""
    lines = (text or "").rstrip().splitlines()
    for i in range(len(lines) - 1, max(-1, len(lines) - 4), -1):
        m = FOLLOWUP_RE.match(lines[i])
        if m:
            qs = [q.strip(" -•*\"'") for q in m.group(1).split("|")]
            body = "\n".join(lines[:i] + lines[i + 1:]).rstrip()
            return body, [q for q in qs if len(q) > 3][:3]
    return text, []


def source_line(store: core.Store, chart_id: str) -> str:
    """'Based on <total> <unit> · <years>' for the chart (the chart itself already shows its title)."""
    try:
        sp = store.spec(chart_id)
    except KeyError:
        return ""
    total, unit = None, sp.get("denomLabel") or "records"
    denom, sdenom = sp.get("denom"), sp.get("sdenom")
    nums = [x for x in denom if isinstance(x, (int, float))] if isinstance(denom, list) else []
    if nums:
        # one shared denominator repeated per bar -> that number; otherwise separate groups -> their sum
        total = nums[0] if len(set(nums)) == 1 else sum(nums)
    elif isinstance(sdenom, dict) and sdenom:
        total = sum(v for v in sdenom.values() if isinstance(v, (int, float)))
    parts = []
    if total:
        parts.append(f"Based on {int(total):,} {unit}")
    cats = sp.get("categories") or []
    if sp.get("isYear") in (True, "True") and cats:
        parts.append(f"{cats[0]}–{cats[-1]}")
    parts.append("Norfolk DA public-records extract")
    return " · ".join(parts)


def source_html(text: str) -> str:
    return (f'<p style="font-size:0.8rem;color:#52514e;margin:-4px 0 6px 4px;">{text}</p>' if text else "")


def log_feedback(n: int):
    """Save a thumbs up/down for answer n (session, local CSV, and the app log)."""
    value = st.session_state.get(f"fb_{n}")
    if value is None:
        return
    msgs = st.session_state.messages
    question = next((m["content"] for m in reversed(msgs[:n]) if m["role"] == "user"), "")
    row = [datetime.now(timezone.utc).isoformat(timespec="seconds"), "up" if value == 1 else "down",
           question, msgs[n].get("content", "")[:300]]
    print("FEEDBACK", row, flush=True)                 # visible under Manage app -> logs
    try:
        new = not FEEDBACK_FILE.exists()
        with FEEDBACK_FILE.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time_utc", "rating", "question", "answer_start"])
            w.writerow(row)
    except OSError:
        pass


def draw_chart(store: core.Store, c: dict, key: str):
    args = (store, c["chart_id"], c.get("from_year"), c.get("to_year"), c.get("series"))
    if st.session_state.get("chart_style", "Dashboard") == "Dashboard":
        html, height = chart_html(*args)
        components.html(html, height=max(260, height - 60), scrolling=True)   # trims empty space under the chart
    else:
        from charts import make_figure   # Plotly alternative (needs plotly)
        st.caption(store.spec(c["chart_id"])["title"])
        show_figure(make_figure(*args), key=key)


def user_bubble(text: str):
    """The question, right-aligned in a navy bubble (like a messaging app)."""
    st.markdown(f'<div class="user-row"><div class="user-bubble">{_html.escape(text)}</div></div>',
                unsafe_allow_html=True)


def render_message(msg: dict, n: int, store: core.Store, last: bool):
    if msg["role"] == "user":
        user_bubble(msg["content"])
        return
    with st.chat_message("assistant", avatar=":material/balance:"):
        with card(key=f"answer_card_{n}"):
            st.markdown(msg["content"])
            for j, c in enumerate(msg.get("charts", [])):
                try:
                    draw_chart(store, c, key=f"fig_{n}_{j}")
                    st.markdown(source_html(source_line(store, c["chart_id"])), unsafe_allow_html=True)
                except KeyError:
                    st.warning(f"Chart {c['chart_id']} is not in the data file.")

            if msg.get("followups") and last:
                st.markdown('<p class="section-label">Ask next</p>', unsafe_allow_html=True)
                cols = st.columns(len(msg["followups"]))
                for k, (col, q) in enumerate(zip(cols, msg["followups"])):
                    with col:
                        if wide_button(q, key=f"fu_{n}_{k}"):
                            st.session_state.pending = q

            left, right = st.columns([4, 1])
            with left:
                if msg.get("tool_log"):
                    with st.expander("How this answer was found"):
                        for t in msg["tool_log"]:
                            st.markdown(f"- `{t['tool']}` {t['input']}")
                        st.caption("The assistant only reads the summary numbers behind the dashboard charts.")
            with right:
                if not msg.get("browse") and hasattr(st, "feedback"):
                    st.feedback("thumbs", key=f"fb_{n}", on_change=log_feedback, args=(n,))


def answer(prompt: str, store: core.Store, model: str) -> dict:
    history = [{"role": m["role"], "content": m["content"]}
               for m in st.session_state.messages[:-1] if not m.get("browse")]
    key = get_api_key()
    if key:
        try:
            ans = core.ask_openrouter(key, store, history, prompt, model=model)
        except Exception as e:  # auth, rate limit, network
            msg = str(e)
            hint = ("Check the API key." if " 401" in msg or " 403" in msg
                    else "Out of credits: add credits on openrouter.ai." if " 402" in msg
                    else "Try again in a moment.")
            ans = core.Answer(f"Couldn't reach the model ({type(e).__name__}). {hint} "
                              "Showing the closest chart instead.",
                              core.offline_answer(store, prompt).charts, [], True)
    else:
        ans = core.offline_answer(store, prompt)
    body, followups = split_followups(ans.text)
    return {"role": "assistant", "content": body, "charts": ans.charts,
            "tool_log": ans.tool_log, "followups": followups}


# ----------------------------------------------------------------------------- page
store = load_store()
st.session_state.setdefault("messages", [])

with st.sidebar:
    st.markdown("**Norfolk County Prosecution Data Explorer**")
    st.caption("Norfolk DA public-records extract, charges received 2017–2025.")
    if wide_button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    key = get_api_key()
    if not key:
        st.info("Written answers are off: showing the closest chart for each question.")
    with st.expander("Developer options"):
        if key:
            st.success("Written answers are on (OpenRouter).")
        else:
            entered = st.text_input("OpenRouter API key", type="password",
                                    help="Kept only for this browser session. Or put OPENROUTER_API_KEY in .env.")
            if entered:
                st.session_state.api_key = entered.strip()
                st.rerun()
        model = st.selectbox("Model", core.MODELS, index=0, help="Low-cost models only during development.")
        st.radio("Chart style", ["Dashboard", "Plotly"], key="chart_style", horizontal=True,
                 help="Dashboard: same interactive charts as norfolk_dashboard.html. Plotly: standard Plotly charts.")

st.markdown(f"""
<div class="app-header">
  <div>
        <div class="name">Norfolk County Prosecution Data Explorer</div>
  </div>
  <div class="range"><b>{DATA_RANGE}</b>charges received</div>
</div>
""", unsafe_allow_html=True)

tab_ask, tab_explore, tab_about = st.tabs(["Ask", "Explore charts", "About the data"])

# ----------------------------------------------------------------------------- Ask
with tab_ask:
    msgs = st.session_state.messages
    if not msgs:
        st.markdown(INTRO)
        st.caption(NOTICE)
        kpis = [k for k in store.data.get("kpis", []) if k["label"] in KPI_LABELS][:4]
        if kpis:
            cols = st.columns(len(kpis))
            for c, k in zip(cols, kpis):
                c.metric(KPI_LABELS[k["label"]], k["value"], help=k["label"])
        st.markdown('<p class="section-label">Try one of these</p>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, q in enumerate(EXAMPLES):
            with cols[i % 2]:
                if wide_button(q, key=f"start_{i}"):
                    st.session_state.pending = q
    else:
        last_bot = max((i for i, m in enumerate(msgs) if m["role"] == "assistant"), default=-1)
        for n, m in enumerate(msgs):
            render_message(m, n, store, last=(n == last_bot))

    try:   # inside the tab on current Streamlit; older versions only allow it at the page bottom
        typed = st.chat_input("Ask a question about the Norfolk data…")
        input_in_tab = True
    except Exception:
        typed, input_in_tab = None, False
    prompt = typed or st.session_state.pop("pending", None)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        user_bubble(prompt)
        with st.spinner("Looking up the numbers…"):
            bot = answer(prompt, store, model)
        st.session_state.messages.append(bot)
        st.rerun()

# ----------------------------------------------------------------------------- Explore charts
with tab_explore:
    st.markdown("Every chart behind the chatbot, grouped by question. Point at a color for details; "
                "click the legend to hide a series; switch Percent / Count at the top right of each chart.")
    sections = {s["q"]: s for s in store.data["sections"]}
    qs = sorted({sp["q"] for sp in store.data["specs"]}, key=lambda q: int(q) if str(q).isdigit() else 99)
    labels = {q: (f"Q{q} · {sections[q]['short']}" if q in sections else f"Q{q}") for q in qs}
    if hasattr(st, "segmented_control"):      # pill buttons on current Streamlit
        pick = st.segmented_control("Question", qs, format_func=lambda q: labels[q], default=qs[0],
                                    label_visibility="collapsed") or qs[0]
    else:
        pick = st.radio("Question", qs, format_func=lambda q: labels[q], horizontal=True,
                        label_visibility="collapsed")
    if pick in sections:
        s = sections[pick]
        st.markdown(f'<p class="section-title">{s["title"]}</p>', unsafe_allow_html=True)
        st.caption(f"{s.get('status', '')} · {s.get('summary', '')}")
    specs = [sp for sp in store.data["specs"] if sp["q"] == pick]
    for sp in specs:
        draw_chart(store, {"chart_id": sp["id"]}, key=f"explore_{sp['id']}")
        st.markdown(source_html(source_line(store, sp["id"])), unsafe_allow_html=True)

# ----------------------------------------------------------------------------- About
with tab_about:
    st.markdown('<p class="section-label">Source</p>', unsafe_allow_html=True)
    st.markdown("Norfolk County District Attorney's Office public-records extract of charges received "
                f"{DATA_RANGE} (file `NFK-Data-final-2017-2025_redacted.csv`). The chatbot and charts use "
                "only summary tables built from this file; no individual records are shown.")

    st.markdown('<p class="section-label">Headline numbers</p>', unsafe_allow_html=True)
    for k in store.data.get("kpis", []):
        if k["label"] in KPI_LABELS:
            st.markdown(f"- **{KPI_LABELS[k['label']]}: {k['value']}**: {k['label']}.")

    st.markdown('<p class="section-label">What each question covers</p>', unsafe_allow_html=True)
    for s in store.data["sections"]:
        st.markdown(f"**Q{s['q']} · {s['short']}** ({s.get('status', '')})  \n{s.get('summary', '')}")

    st.markdown('<p class="section-label">What the data can’t answer</p>', unsafe_allow_html=True)
    st.markdown(
        "- Victim characteristics (the extract has no victim records)\n"
        "- Results by town (police agencies can't be mapped to the town where an incident happened)\n"
        "- Bail and pretrial detention (withheld from this extract)\n"
        "- Sentencing, defendant race or sex, and per-capita rates (not part of these questions yet)\n"
        "- Anything about a specific person, case or docket")

    st.markdown('<p class="section-label">Method</p>', unsafe_allow_html=True)
    st.markdown(
        "- Counts are charge rows or cases as labeled on each chart; every percentage shows its denominator.\n"
        "- Missing values are kept separate from explicit \"unknown\" codes.\n"
        "- Groups (for example DV and sexual assault cases) can overlap, so they must not be added together.\n"
        "- The chatbot reads the numbers behind these charts through a lookup tool and is instructed "
        "never to state a number it didn't look up. It's an AI prototype: check key numbers against the chart.")
    if store.data.get("footer"):
        st.caption(store.data["footer"])

if not input_in_tab:
    late = st.chat_input("Ask a question about the Norfolk data…")
    if late:
        st.session_state.pending = late
        st.rerun()
