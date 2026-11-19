"""Interactive Plotly charts built from dashboard_data.json specs.

Hover any bar segment, dot or point to see its value, count and denominator,
plus the change since the first year shown on year-based charts.
"""
from __future__ import annotations

import plotly.graph_objects as go

from core import NEUTRAL_RE, Store, colors_for, year_index

FONT = "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"


def _fmt_int(v):
    return "–" if v is None else f"{int(round(v)):,}"


def _fmt_val(v, pct):
    if v is None:
        return "–"
    return f"{v:.1f}%" if pct else f"{int(round(v)):,}"


def _code_note(store, code):
    """Plain-language hint for a crime or agency code, taken from the data-derived glossary."""
    g = store.glossary or {}
    if code in g.get("agencies", {}):
        return g["agencies"][code]
    cc = g.get("crime_codes", {}).get(code)
    if cc and cc.get("top_charges"):
        return "mostly " + cc["top_charges"][0].rsplit(" (", 1)[0]
    return None


def _hover_lines(store, spec, s, i, idx, pct, sden):
    """Text block for one mark: value, count of denominator, change since first shown year."""
    cats = spec["categories"]
    v = s["value"][i]
    sname, cat = s["name"], cats[i]
    sn, cn = _code_note(store, sname), _code_note(store, cat)
    lines = [f"<b>{sname}</b>" + (f" <span style='color:#7a7974'>{sn}</span>" if sn else ""),
             f"{spec.get('catLabel') or ''} {cat}".strip() + (f" ({cn})" if cn else ""),
             f"<span style='font-size:15px'><b>{_fmt_val(v, pct)}</b></span>"]
    cnt = s["count"][i] if s.get("count") else None
    den = sden if sden is not None else (spec["denom"][i] if spec.get("denom") else None)
    unit = spec.get("denomLabel") or ""
    if pct and cnt is not None:
        lines.append(f"{_fmt_int(cnt)} of {_fmt_int(den)} {unit}".strip() if den is not None else f"{_fmt_int(cnt)} records")
    elif not pct and den is not None:
        lines.append(f"Total {_fmt_int(den)} {unit}".strip())
    if spec.get("isYear") and idx and i != idx[0] and v is not None:
        base = s["value"][idx[0]]
        if base is not None:
            if pct:
                lines.append(f"{'▲ +' if v - base >= 0 else '▼ '}{v - base:.1f} pts since {cats[idx[0]]}")
            elif base:
                ch = (v / base - 1) * 100
                lines.append(f"{'▲ +' if ch >= 0 else '▼ '}{ch:.1f}% since {cats[idx[0]]}")
    return "<br>".join(lines)


def make_figure(store: Store, chart_id: str, from_year=None, to_year=None, series=None,
                dark: bool = False) -> go.Figure:
    spec = store.spec(chart_id)
    idx = year_index(spec, from_year, to_year)
    cats = [spec["categories"][i] for i in idx]
    pct = spec["unit"] == "pct"
    colors = colors_for(store, spec)
    keep = set(series) if series else None
    sdenom = spec.get("sdenom") or {}
    focus = spec.get("focus")
    kind = spec["kind"]
    fig = go.Figure()

    for s in spec["series"]:
        if keep and s["name"] not in keep:
            continue
        vals = [s["value"][i] for i in idx]
        hover = [_hover_lines(store, spec, s, i, idx, pct, sdenom.get(s["name"])) for i in idx]
        col = colors[s["name"]]
        faded = focus is not None and s["name"] != focus and not NEUTRAL_RE.match(s["name"]) and kind == "stacked"
        common = dict(name=s["name"], hovertext=hover, hoverinfo="text",
                      hoverlabel=dict(bgcolor="white", bordercolor=col, font=dict(color="#0b0b0b")))
        if kind in ("stacked", "grouped"):
            text = [f"{v:.0f}%" if (pct and v is not None and v >= 6 and kind == "stacked") else "" for v in vals]
            fig.add_trace(go.Bar(x=cats, y=vals, marker=dict(color=col, opacity=0.55 if faded else 1,
                                                             line=dict(color="white", width=1)),
                                 text=text, textposition="inside", insidetextanchor="middle",
                                 textfont=dict(size=11, color="white" if not faded else "#0b0b0b"), **common))
        elif kind == "barh":
            text = [_fmt_val(v, pct) if len(spec["series"]) == 1 else "" for v in vals]
            fig.add_trace(go.Bar(x=vals, y=cats, orientation="h", marker=dict(color=col),
                                 text=text, textposition="outside", cliponaxis=False, **common))
        elif kind == "dot":
            fig.add_trace(go.Scatter(x=vals, y=cats, mode="markers",
                                     marker=dict(color=col, size=13, line=dict(color="white", width=2)), **common))
        else:  # line
            fig.add_trace(go.Scatter(x=cats, y=vals, mode="lines+markers",
                                     line=dict(color=col, width=2.5), marker=dict(size=7, color=col,
                                     line=dict(color="white", width=1.5)), **common))

    if kind == "dot":   # grey range line from lowest to highest court per outcome
        for i, c in zip(idx, cats):
            xs = [s["value"][i] for s in spec["series"] if s["value"][i] is not None and (not keep or s["name"] in keep)]
            if len(xs) > 1:
                fig.add_shape(type="line", x0=min(xs), x1=max(xs), y0=c, y1=c, layer="below",
                              line=dict(color="#a9a7a0", width=4))

    ink, grid, paper = ("#f0efec", "#2c2c29", "#1a1a19") if dark else ("#0b0b0b", "#e6e4df", "#ffffff")
    n_rows = len(cats)
    height = max(360, 70 + n_rows * (34 if kind == "dot" else 26)) if kind in ("barh", "dot") else 430
    value_axis = dict(title=spec["ylabel"], gridcolor=grid, zeroline=False,
                      ticksuffix="%" if pct else "", rangemode="tozero")
    if pct and kind == "stacked":
        value_axis["range"] = [0, 100]
    cat_axis = dict(type="category", showgrid=False, title=None)
    fig.update_layout(
        barmode="stack" if kind == "stacked" else "group",
        bargap=0.3, height=height, font=dict(family=FONT, size=13, color=ink),
        paper_bgcolor=paper, plot_bgcolor=paper,
        margin=dict(l=10, r=20, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None, font=dict(size=12),
                    itemclick="toggle", itemdoubleclick="toggleothers"),
        hoverlabel=dict(font=dict(family=FONT, size=12)),
        showlegend=len(spec["series"]) > 1,
    )
    if kind in ("barh", "dot"):
        fig.update_xaxes(**value_axis)
        fig.update_yaxes(**cat_axis, categoryorder="array", categoryarray=cats,
                         autorange="reversed")   # first category (largest bar / first outcome) on top
    else:
        fig.update_yaxes(**value_axis)
        fig.update_xaxes(**cat_axis)
    return fig
