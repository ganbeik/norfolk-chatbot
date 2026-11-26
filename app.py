"""Norfolk County prosecution data chatbot (prototype).

Run:  streamlit run app.py
Needs an OpenRouter API key for written answers: OPENROUTER_API_KEY in a .env file next to
this script (never committed: .env is in .gitignore), in .streamlit/secrets.toml, or pasted in the sidebar. Without a key the app runs in offline mode and shows the
closest chart for each question.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import core
from widget import chart_html

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"

EXAMPLES = [
    "How did dismissals of domestic violence charges change from 2017 to 2025?",
    "Which district court has the highest share of cases with a dismissal?",
    "What are the most common crime types countywide?",
    "How have DV and sexual assault case numbers changed since 2017?",
    "What kinds of crimes most often end in a nolle prosequi in Superior Court?",
    "What is the race breakdown of victims?",
]

st.set_page_config(page_title="Norfolk prosecution data chatbot", page_icon="⚖️", layout="wide")


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


def render_message(msg: dict, n: int, store: core.Store):
    with st.chat_message(msg["role"], avatar="⚖️" if msg["role"] == "assistant" else None):
        st.markdown(msg["content"])
        for j, c in enumerate(msg.get("charts", [])):
            try:
                args = (store, c["chart_id"], c.get("from_year"), c.get("to_year"), c.get("series"))
                if st.session_state.get("chart_style", "Dashboard") == "Dashboard":
                    html, height = chart_html(*args)
                    components.html(html, height=height, scrolling=True)
                else:
                    from charts import make_figure   # Plotly alternative (needs plotly)
                    st.caption(store.spec(c["chart_id"])["title"])
                    show_figure(make_figure(*args), key=f"fig_{n}_{j}")
            except KeyError:
                st.warning(f"Chart {c['chart_id']} is not in the data file.")
        if msg.get("tool_log"):
            with st.expander("How this answer was found"):
                for t in msg["tool_log"]:
                    st.markdown(f"- `{t['tool']}` {t['input']}")
                st.caption("The assistant only reads the summary numbers behind the dashboard charts.")


store = load_store()
st.session_state.setdefault("messages", [])

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Norfolk prosecution data")
    st.caption("Prototype chatbot. Answers come only from the six-question analysis of the "
               "Norfolk DA public-records extract (charges received 2017–2025).")
    st.subheader("Try a question")
    for q in EXAMPLES:
        if wide_button(q, key=f"ex_{q}"):
            st.session_state.pending = q

    st.subheader("Browse charts")
    titles = {f"Q{s['q']} · {s['title']}": s["id"] for s in store.data["specs"]}
    pick = st.selectbox("Chart", ["—"] + list(titles), label_visibility="collapsed")
    if pick != "—" and wide_button("Show this chart"):
        sid = titles[pick]
        st.session_state.messages.append({"role": "assistant", "content": f"**{store.spec(sid)['title']}.** "
                                          f"{store.spec(sid).get('meta', '')}",
                                          "charts": [{"chart_id": sid}], "browse": True})

    st.subheader("Settings")
    key = get_api_key()
    if not key:
        entered = st.text_input("OpenRouter API key", type="password",
                                help="Kept only for this browser session. Or put OPENROUTER_API_KEY in .env.")
        if entered:
            st.session_state.api_key = entered.strip()
            st.rerun()
        st.info("No API key: offline mode shows the closest chart instead of a written answer.")
    else:
        st.success("Written answers are on (OpenRouter).")
    model = st.selectbox("Model", core.MODELS, index=0, help="Low-cost models only during development.")
    st.radio("Chart style", ["Dashboard", "Plotly"], key="chart_style", horizontal=True,
             help="Dashboard: same interactive charts as norfolk_dashboard.html. Plotly: standard Plotly charts.")
    if wide_button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

    with st.expander("What this data can't answer"):
        for s in store.data["sections"]:
            if s.get("status", "").lower().startswith(("unavailable", "partially", "county")):
                st.markdown(f"**Q{s['q']} · {s['short']}** ({s['status']}): {s['summary']}")
        st.markdown("Also not covered yet: bail (withheld from the extract), sentencing, defendant race "
                    "and sex, per-capita rates.")

# ----------------------------------------------------------------------------- main
st.title("Ask about Norfolk County prosecutions")
st.caption(store.data.get("subtitle", ""))
kpis = store.data.get("kpis", [])[:4]
if kpis:
    cols = st.columns(len(kpis))
    for c, k in zip(cols, kpis):
        c.metric(k["label"], k["value"])

for n, m in enumerate(st.session_state.messages):
    render_message(m, n, store)

prompt = st.chat_input("Ask a question about the Norfolk data…")
prompt = prompt or st.session_state.pop("pending", None)

if prompt:
    history = [m for m in st.session_state.messages if not m.get("browse")]
    user_msg = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_msg)
    render_message(user_msg, len(st.session_state.messages) - 1, store)

    key = get_api_key()
    with st.spinner("Looking up the numbers…"):
        if key:
            try:
                ans = core.ask_openrouter(key, store, history, prompt, model=model)
            except Exception as e:  # auth, rate limit, network
                name = type(e).__name__
                msg = str(e)
                hint = ("Check the API key." if " 401" in msg or " 403" in msg
                        else "Out of credits: add credits on openrouter.ai." if " 402" in msg
                        else "Try again in a moment." if " 429" in msg or " 5" in msg[:16]
                        else "")
                ans = core.Answer(f"Couldn't reach the model ({name}). {hint} Showing the closest chart instead.",
                                  core.offline_answer(store, prompt).charts, [], True)
        else:
            ans = core.offline_answer(store, prompt)

    bot = {"role": "assistant", "content": ans.text, "charts": ans.charts, "tool_log": ans.tool_log}
    st.session_state.messages.append(bot)
    render_message(bot, len(st.session_state.messages) - 1, store)
