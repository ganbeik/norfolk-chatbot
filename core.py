"""Core logic for the Norfolk prosecution-data chatbot.

Plain Python (no Streamlit or Plotly imports), so it can be tested on its own.
Claude answers only from dashboard_data.json, which the analysis notebook writes:
it reads chart numbers with the get_chart_data tool and picks the chart to display
with show_chart. Nothing here touches case-level records.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# OpenRouter model ids. Development: low-cost models only.
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
MODELS = ["anthropic/claude-haiku-5.5", "anthropic/claude-haiku-4.5"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOOL_STEPS = 6
HISTORY_TURNS = 8   # earlier user/assistant turns sent back to Claude for follow-up questions

# Same validated palette as the HTML dashboard (light mode).
PALETTE = ["#2b67b0", "#e07b3c", "#14a38b", "#8b6cc9", "#d4a017", "#d0566e", "#6f9a2e"]
NEUTRAL_COLOR = "#c2c0b9"
NEUTRAL_RE = re.compile(r"^(other recorded|other|missing|unknown|other / unmapped)$", re.I)


# ----------------------------------------------------------------------------- data
@dataclass
class Store:
    data: dict
    glossary: dict
    specs: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)

    @classmethod
    def load(cls, folder: str | Path) -> "Store":
        folder = Path(folder)
        data = json.loads((folder / "dashboard_data.json").read_text(encoding="utf-8"))
        gpath = folder / "glossary.json"
        glossary = json.loads(gpath.read_text(encoding="utf-8")) if gpath.exists() else {}
        st = cls(data=data, glossary=glossary)
        st.specs = {s["id"]: s for s in data["specs"]}
        st.sections = {s["q"]: s for s in data["sections"]}
        return st

    def spec(self, chart_id: str) -> dict:
        if chart_id not in self.specs:
            raise KeyError(f"Unknown chart_id {chart_id!r}. Valid ids: {', '.join(self.specs)}")
        return self.specs[chart_id]


def year_index(spec: dict, from_year=None, to_year=None) -> list[int]:
    """Positions of the categories to keep, applying a year range to year-based charts."""
    idx = list(range(len(spec["categories"])))
    if spec.get("isYear") and (from_year or to_year):
        lo = int(from_year or 0)
        hi = int(to_year or 9999)
        idx = [i for i in idx if lo <= int(spec["categories"][i]) <= hi]
    return idx


def _round(v, nd=1):
    return None if v is None else (round(v, nd) if isinstance(v, float) else v)


# ----------------------------------------------------------------------------- colours
def colors_for(store: Store, spec: dict) -> dict:
    """Series name -> hex colour. Mirrors the dashboard: a series keeps one colour across
    every chart in its colour group, neutral grey for Other/Missing, and names beyond the
    seven palette slots borrow a slot that no fixed series in this chart uses."""
    names_here = [s["name"] for s in spec["series"]]
    if len(names_here) == 1:
        return {names_here[0]: PALETTE[0]}
    grp = spec.get("colorGroup") or spec["q"]
    group_names: list[str] = []
    for s in store.data["specs"]:
        if (s.get("colorGroup") or s["q"]) == grp and len(s["series"]) > 1:
            for x in s["series"]:
                if not NEUTRAL_RE.match(x["name"]) and x["name"] not in group_names:
                    group_names.append(x["name"])

    def fixed(n):
        i = group_names.index(n) if n in group_names else -1
        return i if 0 <= i < len(PALETTE) else -1

    own = [n for n in names_here if not NEUTRAL_RE.match(n)]
    used = {fixed(n) for n in own if fixed(n) >= 0}
    free = [i for i in range(len(PALETTE)) if i not in used]
    extras = [n for n in own if fixed(n) < 0]
    out = {}
    for n in names_here:
        if NEUTRAL_RE.match(n):
            out[n] = NEUTRAL_COLOR
        elif fixed(n) >= 0:
            out[n] = PALETTE[fixed(n)]
        elif free:
            out[n] = PALETTE[free[extras.index(n) % len(free)]]
        else:
            out[n] = NEUTRAL_COLOR
    return out


# ----------------------------------------------------------------------------- tools
TOOLS = [
    {
        "name": "get_chart_data",
        "description": (
            "Return the exact numbers behind one chart: each category (year, court, crime code...) with "
            "every series' value, its count and the denominator. Call this before stating any number."),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "string", "description": "Chart id from the catalog, e.g. chart_01."},
                "from_year": {"type": "integer", "description": "Optional first year (year-based charts only)."},
                "to_year": {"type": "integer", "description": "Optional last year (year-based charts only)."},
            },
            "required": ["chart_id"],
        },
    },
    {
        "name": "show_chart",
        "description": (
            "Display one interactive chart under your answer. Call once for the chart that best supports "
            "the answer (twice at most). Optionally limit years or list the series to show."),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "string"},
                "from_year": {"type": "integer"},
                "to_year": {"type": "integer"},
                "series": {"type": "array", "items": {"type": "string"},
                           "description": "Optional subset of series names to show; omit to show all."},
            },
            "required": ["chart_id"],
        },
    },
]


def get_chart_data(store: Store, chart_id: str, from_year=None, to_year=None) -> dict:
    spec = store.spec(chart_id)
    idx = year_index(spec, from_year, to_year)
    pct = spec["unit"] == "pct"
    sec = store.sections.get(spec["q"], {})
    rows = []
    for i in idx:
        vals = {}
        for s in spec["series"]:
            v = s["value"][i]
            c = s["count"][i] if s.get("count") else None
            if pct:
                vals[s["name"]] = {"percent": _round(v), "count": c}
            else:
                vals[s["name"]] = {"count": v}
        row = {"category": spec["categories"][i], "values": vals}
        if spec.get("denom"):
            row["denominator"] = spec["denom"][i]
        rows.append(row)
    out = {
        "chart_id": chart_id,
        "question": f"Q{spec['q']}. {sec.get('title', '')}",
        "question_status": sec.get("status"),
        "title": spec["title"],
        "what_it_measures": spec.get("meta", ""),
        "unit": "percent" if pct else "count",
        "category_label": spec.get("catLabel") or "Category",
        "denominator_label": spec.get("denomLabel") or None,
        "rows": rows,
    }
    if spec.get("sdenom"):
        out["denominator_per_series"] = spec["sdenom"]
        out["note"] = "Each series has its own denominator (denominator_per_series); percentages sum to 100% within a series."
    if spec.get("finding"):
        out["finding"] = spec["finding"]
    if sec.get("summary"):
        out["caveats"] = sec["summary"]
    return out


def show_chart(store: Store, chart_id: str, from_year=None, to_year=None, series=None) -> dict:
    spec = store.spec(chart_id)
    names = [s["name"] for s in spec["series"]]
    keep = [n for n in (series or []) if n in names] or None
    bad = [n for n in (series or []) if n not in names]
    req = {"chart_id": chart_id, "from_year": from_year, "to_year": to_year, "series": keep}
    msg = {"shown": chart_id, "title": spec["title"]}
    if bad:
        msg["ignored_series"] = bad
        msg["valid_series"] = names
    return {"request": req, "result": msg}


def run_tool(store: Store, name: str, args: dict, charts: list) -> str:
    try:
        if name == "get_chart_data":
            return json.dumps(get_chart_data(store, **args), ensure_ascii=False)
        if name == "show_chart":
            if len(charts) >= 2:
                return json.dumps({"error": "Two charts are already shown; do not add more."})
            r = show_chart(store, **args)
            charts.append(r["request"])
            return json.dumps(r["result"], ensure_ascii=False)
        return json.dumps({"error": f"Unknown tool {name}"})
    except (KeyError, TypeError, ValueError) as e:
        return json.dumps({"error": str(e)})


# ----------------------------------------------------------------------------- prompt
RULES = """You are a prototype assistant that answers questions about Norfolk County (Massachusetts) District Attorney prosecution records: charges received 2017-2025, from a public-records extract. You answer ONLY from the charts in the catalog below, which you read with the get_chart_data tool.

Rules:
1. Before stating any number, call get_chart_data for the chart and use its values exactly. Never invent numbers or use outside knowledge about Norfolk or crime statistics. Simple arithmetic on returned values (a difference, which is larger) is fine; a difference between two percentages is in "percentage points".
2. Call show_chart for the chart that best supports your answer (at most two). Use from_year/to_year when the question is about particular years.
3. Every answer that gives numbers names its denominator (for example "of 3,723 DV outcome rows in 2025") and one caveat that matters for it, taken from the chart's caveats or what_it_measures.
4. If these charts cannot answer the question, say so plainly in one sentence, say what the data lacks, and offer the closest question they can answer. This covers: victim characteristics, results by town or municipality, bail or pretrial detention, sentences, defendant race or sex, per-capita rates, why something changed, and anything about a specific person, case or docket. Never guess.
5. If a denominator is under 30, warn that the percentage rests on very few records.
6. Explain crime-type and agency codes with the glossary. It lists the most common charges recorded under each code in this data; the official codebook meaning of CHAB, ELAB and HACR is unconfirmed, so say "appears to cover".
7. Describe what the data shows. Do not speculate about causes, judge courts or people, or recommend policy.
8. Style: plain English, 2-5 short sentences or a short bullet list. Bold the key number with **...**. No headings or tables. Do not mention chart ids, tools or JSON."""


def catalog_text(store: Store) -> str:
    lines = ["QUESTIONS COVERED (with how far the data answers each):"]
    for s in store.data["sections"]:
        lines.append(f"- Q{s['q']} [{s.get('status','')}] {s['title']} :: {s.get('summary','')}"
                     + (f" Unavailable: {s['unavailable']}" if s.get("unavailable") else ""))
    lines.append("\nCHARTS:")
    for sp in store.data["specs"]:
        cats = sp["categories"]
        cat_txt = f"{cats[0]}-{cats[-1]}" if sp.get("isYear") else ", ".join(cats[:15])
        lines.append(
            f"- {sp['id']} (Q{sp['q']}, {sp['kind']}, {'percent' if sp['unit']=='pct' else 'count'}): {sp['title']}. "
            f"{sp.get('meta','')} Categories ({sp.get('catLabel') or 'category'}): {cat_txt}. "
            f"Series: {', '.join(s['name'] for s in sp['series'])}.")
    k = store.data.get("kpis") or []
    if k:
        lines.append("\nHEADLINE TOTALS: " + "; ".join(f"{x['label']}: {x['value']}" for x in k))
    g = store.glossary
    if g.get("crime_codes"):
        lines.append("\nGLOSSARY - crime-type codes (most common recorded charges under each code, share of the code's rows):")
        for code, v in g["crime_codes"].items():
            lines.append(f"- {code} ({v['rows']:,} rows): {'; '.join(v['top_charges'])}")
    if g.get("agencies"):
        lines.append("\nGLOSSARY - agency codes: " + "; ".join(f"{c} = {n}" for c, n in g["agencies"].items()))
    return "\n".join(lines)


def system_prompt(store: Store) -> str:
    return RULES + "\n\n" + catalog_text(store)


# ----------------------------------------------------------------------------- Claude loop
@dataclass
class Answer:
    text: str
    charts: list
    tool_log: list
    offline: bool = False


def _block_dicts(content) -> list[dict]:
    out = []
    for b in content:
        t = getattr(b, "type", None) or b.get("type")
        get = (lambda k: getattr(b, k)) if not isinstance(b, dict) else b.get
        if t == "text":
            out.append({"type": "text", "text": get("text")})
        elif t == "tool_use":
            out.append({"type": "tool_use", "id": get("id"), "name": get("name"), "input": get("input")})
    return out


def build_messages(history: list[dict], user_text: str) -> list[dict]:
    msgs = [{"role": m["role"], "content": m["content"]}
            for m in history[-2 * HISTORY_TURNS:] if m.get("content") and m["role"] in ("user", "assistant")]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    msgs.append({"role": "user", "content": user_text})
    return msgs


def ask_claude(client, store: Store, history: list[dict], user_text: str,
               model: str = DEFAULT_MODEL, max_tokens: int = 1200) -> Answer:
    """Run one chat turn: Claude may call tools several times, then answers in text."""
    system = [{"type": "text", "text": system_prompt(store), "cache_control": {"type": "ephemeral"}}]
    messages = build_messages(history, user_text)
    charts, log = [], []
    for _ in range(MAX_TOOL_STEPS):
        resp = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                      tools=TOOLS, messages=messages)
        blocks = _block_dicts(resp.content)
        uses = [b for b in blocks if b["type"] == "tool_use"]
        if not uses:
            text = "\n\n".join(b["text"] for b in blocks if b["type"] == "text").strip()
            return Answer(text or "(No answer returned.)", charts, log)
        messages.append({"role": "assistant", "content": blocks})
        results = []
        for u in uses:
            out = run_tool(store, u["name"], u["input"] or {}, charts)
            log.append({"tool": u["name"], "input": u["input"], "output": out[:400]})
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": out})
        messages.append({"role": "user", "content": results})
    return Answer("I couldn't finish looking that up. Please try a narrower question.", charts, log)


def _openai_tools() -> list[dict]:
    """TOOLS in the OpenAI / OpenRouter function format."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in TOOLS]


def ask_openrouter(api_key: str, store: Store, history: list[dict], user_text: str,
                   model: str = DEFAULT_MODEL, max_tokens: int = 1200, post=None) -> Answer:
    """Same tool loop as ask_claude, through OpenRouter's OpenAI-compatible API."""
    import json as _json
    import requests
    post = post or requests.post
    messages = [{"role": "system", "content": system_prompt(store)}] + build_messages(history, user_text)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
               "X-Title": "Norfolk prosecution chatbot"}
    charts, log = [], []
    for _ in range(MAX_TOOL_STEPS):
        r = post(OPENROUTER_URL, headers=headers, timeout=90,
                 json={"model": model, "max_tokens": max_tokens, "messages": messages, "tools": _openai_tools()})
        if r.status_code != 200:
            raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:300]}")
        msg = r.json()["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            return Answer((msg.get("content") or "").strip() or "(No answer returned.)", charts, log)
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            try:
                args = _json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            out = run_tool(store, name, args, charts)
            log.append({"tool": name, "input": args, "output": out[:400]})
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": out})
    return Answer("I couldn't finish looking that up. Please try a narrower question.", charts, log)


# ----------------------------------------------------------------------------- offline mode
OUT_OF_SCOPE = [
    (r"\bvictim", "victim characteristics: the extract has no victim records or victim race/ethnicity"),
    (r"\b(town|city|municipal|neighbo)", "results by town: police agencies can't be mapped to incident municipalities"),
    (r"\bbail|pretrial|detain|detention", "bail or pretrial detention: bail data was withheld from this extract"),
    (r"\bsentenc|incarcerat|jail|prison|probation", "sentences: these six questions don't analyse sentencing yet"),
    (r"\b(race|racial|black|white|hispanic|latino|ethnic|gender|sex\b|male|female)", "defendant race or sex: not part of these six questions yet"),
    (r"per capita|per 10,?000|population", "per-capita rates: these need population figures that aren't in the data"),
    (r"\bdocket|\bdefendant named|\bperson named", "individual cases or people: the chatbot only uses summary numbers"),
    (r"how long|time to (disposition|resolve)|\bdays\b|duration", "time-to-disposition chart: case length isn't charted in these six questions yet"),
]
# Offline routing: first matching pattern wins (checked before word overlap).
_NOPR = r"(nolle|nol\.? ?pros|nopr)"
_DV = r"(\bdv\b|domestic)"
_SA = r"(\bsa\b|sexual)"
INTENTS = [
    (_NOPR + r".*(crime|type|kind|charge|offen)|(crime|type|kind|charge|offen).*" + _NOPR, "chart_12"),
    (_NOPR, "chart_11"),
    (r"(court).*(dismiss)|(dismiss).*(court)", "chart_06"),
    (r"\b(court|quincy|brookline|dedham|stoughton|wrentham)\b", "chart_05"),
    (r"(agency|agencies|police)", "chart_08"),
    (r"(elder|hate|hacr|elab|civil.rights)", "chart_10"),
    (r"(crime type|common crime|crime mix|countywide|most common)", "chart_07"),
    (r"(how many|number of|\bcounts?\b|filed|charging|caseload|volume)", "chart_09"),
    (_DV + r".*(dismiss|outcome|disposition|plea|result)|(dismiss|outcome|disposition|plea|result).*" + _DV, "chart_01"),
    (_SA + r".*(dismiss|outcome|disposition|plea|result)|(dismiss|outcome|disposition|plea|result).*" + _SA, "chart_02"),
    (r"(child|chab).*(dismiss|outcome|disposition)|(dismiss|outcome|disposition).*(child|chab)", "chart_04"),
    (_DV + "|" + _SA, "chart_09"),
    (r"(dismiss|outcome|disposition)", "chart_01"),
]
SYNONYMS = {
    "domestic": "dv", "dv": "dv", "sexual": "sa", "sa": "sa", "assault": "sa", "dismiss": "dismissed",
    "dismissal": "dismissed", "dismissals": "dismissed", "dismisses": "dismissed", "nolle": "nopr", "nol": "nopr", "pros": "nopr",
    "prosequi": "nopr", "child": "chab", "children": "chab", "elder": "elab", "elderly": "elab",
    "hate": "hacr", "court": "court", "courts": "court", "police": "agency", "agencies": "agency",
    "agency": "agency", "crime": "crime", "crimes": "crime", "plea": "plea", "cwof": "cwof",
    "superior": "superior", "district": "district", "charging": "charging", "charges": "charging",
}


def _words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z]+", text.lower()):
        if len(w) > 2 or w in ("dv", "sa"):
            out.add(SYNONYMS.get(w, w))
    return out


def offline_answer(store: Store, text: str) -> Answer:
    """No API key: decline out-of-scope topics, otherwise show the closest chart."""
    low = text.lower()
    for pat, why in OUT_OF_SCOPE:
        if re.search(pat, low):
            return Answer(f"This data can't answer that: it has no {why}. Try asking about dispositions, "
                          "court outcomes, crime mix, charging trends or nolle prosequi.", [], [], True)
    for pattern, chart_id in INTENTS:
        if re.search(pattern, low) and chart_id in store.specs:
            best = store.spec(chart_id)
            return Answer(f"Offline mode (no API key), so this is the closest chart rather than a written answer: "
                          f"**{best['title']}.** {best.get('meta', '')}",
                          [{"chart_id": chart_id, "from_year": None, "to_year": None, "series": None}], [], True)
    q = _words(text)
    best, best_score = None, 0
    for sp in store.data["specs"]:
        sec = store.sections.get(sp["q"], {})
        hay = " ".join([sp["title"], sp.get("meta", ""), sec.get("title", ""), sec.get("short", ""),
                        " ".join(s["name"] for s in sp["series"]), " ".join(sp["categories"])])
        score = len(q & _words(hay))
        if score >= 2 and score > best_score:
            best, best_score = sp, score
    if not best:
        return Answer("Offline mode (no API key): I couldn't match that to a chart. Pick one under "
                      "**Browse charts** in the sidebar.", [], [], True)
    return Answer(f"Offline mode (no API key), so this is the closest chart rather than a written answer: "
                  f"**{best['title']}.** {best.get('meta', '')}",
                  [{"chart_id": best["id"], "from_year": None, "to_year": None, "series": None}], [], True)
