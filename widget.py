"""Dashboard-style interactive chart for Streamlit.

Uses the same chart code as norfolk_dashboard.html: pointing at a colour fades the others
and shows that piece's value, count of total, change since the first year and code meaning.
Click legend items to hide them (double-click to isolate); switch Percent/Count; show the table.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from core import Store, colors_for

TEMPLATE = (Path(__file__).parent / "chart_widget.html").read_text(encoding="utf-8")


def _code_notes(store: Store, spec: dict) -> dict:
    g = store.glossary or {}
    agencies, crimes = g.get("agencies", {}), g.get("crime_codes", {})
    notes = {}
    for code in list(spec["categories"]) + [s["name"] for s in spec["series"]]:
        if code in agencies:
            notes[code] = agencies[code]
        elif code in crimes and crimes[code].get("top_charges"):
            notes[code] = "mostly " + crimes[code]["top_charges"][0].rsplit(" (", 1)[0]
    return notes


def _height(spec: dict, n_cats: int, n_series_shown: int) -> int:
    names = [s["name"] for s in spec["series"]]
    legend_rows = 0 if len(names) < 2 else math.ceil(sum(len(n) * 7 + 34 for n in names) / 640)
    head = 64 + (18 if len(spec.get("meta", "")) > 70 else 0)
    if spec["kind"] == "dot":
        chart = 40 + n_cats * 36
    elif spec["kind"] == "barh":
        chart = 50 + n_cats * max(18, 10 + 9 * max(1, n_series_shown))
    else:
        chart = 300
    return head + legend_rows * 28 + chart + 94


def chart_html(store: Store, chart_id: str, from_year=None, to_year=None, series=None) -> tuple[str, int]:
    spec = dict(store.spec(chart_id))
    spec["colors"] = colors_for(store, spec)
    spec["codeNotes"] = _code_notes(store, spec)
    names = [s["name"] for s in spec["series"]]
    hidden = [n for n in names if series and n not in series]
    cats = spec["categories"]
    if spec.get("isYear"):
        years = [int(c) for c in cats]
        y_from = int(from_year) if from_year else years[0]
        y_to = int(to_year) if to_year else years[-1]
        n_cats = sum(y_from <= y <= y_to for y in years)
    else:
        y_from = y_to = None
        n_cats = len(cats)
    payload = {"spec": spec, "yFrom": y_from, "yTo": y_to, "hidden": hidden}
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/null", data)
    return html, _height(spec, n_cats, len(names) - len(hidden))
