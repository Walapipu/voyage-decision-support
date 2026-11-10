"""Analytics figures. Colour roles follow the dataviz method:

* the heat map is one sequential hue (blue), light to dark by contribution;
* charts where every vessel can sit beside every other (scatter, lines) use emphasis: the focused
  pairing in blue, the rest in labelled grey (four categorical hues fail the all-pairs CVD check);
* cost shares use the first four validated categorical slots (adjacent pairs only);
* voyage stages keep the app-wide stage colours so they match the Voyages page.
"""
import math

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from voyage.analysis import STAGES, STAGE_COLOURS
from voyage.analytics_data import margin

CHECKS = {"quantity": "lift", "laycan": "laycan", "deadweight": "deadweight", "draft": "draft",
          "fuel": "fuel", "port_draft": "port draft"}
# Validated categorical slots 1-4 (light on #ffffff, dark on #13161b): adjacent CVD ΔE ≥ 8.4.
COST_SLOTS = {True: ["#3987e5", "#d95926", "#199e70", "#c98500"], False: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]}
COSTS = [("Hire", "hire_cost_usd"), ("Bunkers", "bunker_cost_usd"), ("Ports", "port_cost_usd"), ("Commission", "commission_usd")]
SEQ = {False: ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
       True: ["#104281", "#184f95", "#256abf", "#2a78d6", "#5598e7", "#86b6ef", "#b7d3f6"]}
DIVERGING = {False: ["#c62828", "#f0efec", "#256abf"], True: ["#e66767", "#383835", "#5598e7"]}


def ink(dark):
    return ({"text": "#e8ebf0", "text2": "#a3a9b5", "muted": "#858c98", "grid": "rgba(232,236,242,.08)", "axis": "rgba(232,236,242,.18)",
             "surface": "#13161b", "field": "#1b1f25", "accent": "#5aa9f0", "other": "#5c6370", "band": "rgba(224,178,99,.07)",
             "bad": "rgba(229,72,77,.07)"}
            if dark else
            {"text": "#111827", "text2": "#4b5565", "muted": "#6b7487", "grid": "rgba(17,24,39,.07)", "axis": "rgba(17,24,39,.2)",
             "surface": "#ffffff", "field": "#f1f3f6", "accent": "#0a6fd6", "other": "#a3abb8", "band": "rgba(154,100,16,.06)",
             "bad": "rgba(198,40,40,.05)"})


def label(row):
    return f'{row["vessel_id"]} → {row["cargo_id"]}'


def short(value):
    sign = "−" if value < 0 else ""
    value = abs(value)
    return f"{sign}${value / 1e6:.2f}M" if value >= 1e6 else f"{sign}${value / 1e3:.0f}k" if value >= 1e3 else f"{sign}${value:,.0f}"


def failed(row):
    return ", ".join(CHECKS.get(c, c) for c in row["failed_checks"])


def style(fig, dark, height):
    c = ink(dark)
    fig.update_layout(height=height, template="plotly_dark" if dark else "plotly_white",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Source Sans 3, Source Sans Pro, system-ui, sans-serif", size=11, color=c["text2"]),
                      margin=dict(l=8, r=12, t=8, b=8), showlegend=False,
                      hoverlabel=dict(bgcolor=c["surface"], bordercolor=c["axis"], font=dict(color=c["text"], size=12)))
    fig.update_xaxes(gridcolor=c["grid"], zerolinecolor=c["axis"], linecolor=c["axis"], tickcolor=c["axis"], automargin=True,
                     title_font=dict(size=11, color=c["muted"]))
    fig.update_yaxes(gridcolor=c["grid"], zerolinecolor=c["axis"], linecolor=c["axis"], tickcolor=c["axis"], automargin=True,
                     title_font=dict(size=11, color=c["muted"]))
    return fig


def _hover(row):
    status = "Feasible" if row["feasible"] else "Fails: " + failed(row)
    m = margin(row)
    return (f"<b>{label(row)}</b> · {row['selected_lift_tonnes']:,.0f} t<br>{status}<br>"
            f"Contribution ${row['voyage_contribution_usd']:,.0f}" + (f" ({m:.1f}%)" if m is not None else "") +
            f"<br>TCE ${row['tce_usd_per_day']:,.0f}/day · {row['voyage_days']:.1f} days"
            f"<br>Laycan slack {row['laycan_slack_days']:+.1f} days · draft headroom {row['limiting_draft_margin_m']:.3f} m")


def _mix(a, b, t):
    a, b = (tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in (a, b))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _ramp_rgb(ramp, t):
    t = min(max(t, 0), 1) * (len(ramp) - 1)
    i = min(int(t), len(ramp) - 2)
    return _mix(ramp[i], ramp[i + 1], t - i)


def _luma(rgb):
    lin = [((v / 255 + .055) / 1.055) ** 2.4 if v / 255 > .04045 else v / 255 / 12.92 for v in rgb]
    return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]


def spread(values, gap):
    """Positions for end-of-line labels: the same order as `values`, at least `gap` apart."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    placed = list(values)
    for prev, i in zip(order, order[1:]):
        placed[i] = max(placed[i], placed[prev] + gap)
    return placed


def _end_labels(fig, ends, c, axis_span, row=None, col=None, height_px=220):
    """ends: [(x, y, text, hot)]. Labels sit right of the last point, at least one text line apart."""
    if not ends:
        return
    ys = [y for _, y, _, _ in ends]
    gap = (axis_span or 1) * 13 / height_px  # 13px of axis, in data units
    for (x, y, text, hot), at in zip(ends, spread(ys, gap)):
        fig.add_annotation(x=x, y=at, text=text, xanchor="left", xshift=6, showarrow=False, row=row, col=col,
                           font=dict(size=10, color=c["text"] if hot else c["muted"], family="Source Code Pro, monospace"))


def _place_labels(xs, ys, width_px=420, height_px=230):
    """Direct-label positions that avoid each other: try above, below, right, left; None when all collide."""
    if not xs:
        return []
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx, sy = width_px / ((x1 - x0) or 1), height_px / ((y1 - y0) or 1)
    boxes, out = [], []
    offsets = {"top center": (0, 16), "bottom center": (0, -16), "middle right": (56, 0), "middle left": (-56, 0)}
    for x, y in zip(xs, ys):
        px, py = (x - x0) * sx, (y - y0) * sy
        chosen = None
        for pos, (dx, dy) in offsets.items():
            box = (px + dx - 42, py + dy - 7, px + dx + 42, py + dy + 7)
            if all(box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3] for b in boxes):
                chosen = pos
                boxes.append(box)
                break
        out.append(chosen)
    return out


def heatmap(rows, vessels, cargoes, focus, dark):
    """Contribution by vessel (rows) and cargo (columns). Infeasible cells stay empty and name the failed check."""
    c = ink(dark)
    cell = {(r["vessel_id"], r["cargo_id"]): r for r in rows}
    values = [r["voyage_contribution_usd"] for r in rows if r["feasible"]]
    low, high = (min(values), max(values)) if values else (0, 1)
    diverging = low < 0 < high
    scale = DIVERGING[dark] if diverging else SEQ[dark]
    span = max(abs(low), abs(high)) if diverging else None
    z, text, hover = [], [], []
    # Beyond three cargo columns a cell is too narrow for two lines: show the contribution
    # alone and mark a failed cell with a cross; the hover still names every figure and check.
    compact = len(cargoes) > 3
    fig = go.Figure()
    for v in vessels:
        z.append([]), text.append([]), hover.append([])
        for cg in cargoes:
            r = cell.get((v, cg))
            ok = r is not None and r["feasible"]
            z[-1].append(r["voyage_contribution_usd"] if ok else None)
            hover[-1].append(_hover(r) if r else "Not evaluated")
            if r is None:
                continue
            if ok:
                t = (r["voyage_contribution_usd"] + span) / (2 * span) if diverging else (
                    (r["voyage_contribution_usd"] - low) / (high - low) if high > low else .6)
                rgb = _ramp_rgb(scale, t)
                colour = "#0b0b0b" if _luma(rgb) > .32 else "#ffffff"
                note = (f'<b>{short(r["voyage_contribution_usd"])}</b>' if compact else
                        f'<b>{short(r["voyage_contribution_usd"])}</b><br>{short(r["tce_usd_per_day"])}/day · {r["selected_lift_tonnes"] / 1e3:,.1f}k t')
            else:
                colour = c["muted"]
                # Two checks per line, so long failure lists stay inside their own cell.
                names = [CHECKS.get(k, k) for k in r["failed_checks"]]
                note = "✕" if compact else "✕ " + "<br>".join(", ".join(names[i:i + 2]) for i in range(0, len(names), 2))
            fig.add_annotation(x=cg, y=v, text=note, showarrow=False, font=dict(size=10 if compact else 11, color=colour))
    fig.add_trace(go.Heatmap(z=z, x=cargoes, y=vessels, customdata=hover, hovertemplate="%{customdata}<extra></extra>",
                             colorscale=[[i / (len(scale) - 1), h] for i, h in enumerate(scale)],
                             zmid=0 if diverging else None, zmin=None if diverging else low, zmax=None if diverging else high,
                             xgap=3, ygap=3, hoverongaps=False,
                             colorbar=dict(thickness=8, len=.9, outlinewidth=0, tickprefix="$", tickformat="~s",
                                           tickfont=dict(size=10, color=c["muted"]), title=dict(text="", side="right"))))
    # Infeasible cells: a neutral tile under the empty heat cell, so "no value" reads as a surface, not a colour.
    for v in vessels:
        for cg in cargoes:
            r = cell.get((v, cg))
            if r is not None and not r["feasible"]:
                fig.add_shape(type="rect", xref="x", yref="y", x0=cargoes.index(cg) - .49, x1=cargoes.index(cg) + .49,
                              y0=vessels.index(v) - .49, y1=vessels.index(v) + .49, fillcolor=c["field"], line_width=0, layer="below")
    focused = bool(focus) and focus in cell
    if focused:
        # Same accent as the focused bubble in the TCE chart, so the two read as one selection.
        # A thin surface-coloured ring inside separates the accent from the cell's own colour.
        x, y = cargoes.index(focus[1]), vessels.index(focus[0])
        fig.add_shape(type="rect", xref="x", yref="y", x0=x - .5, x1=x + .5, y0=y - .5, y1=y + .5,
                      line=dict(color=c["accent"], width=3))
        fig.add_shape(type="rect", xref="x", yref="y", x0=x - .45, x1=x + .45, y0=y - .45, y1=y + .45,
                      line=dict(color=c["surface"], width=1.5))

    def ticks(ids, hot):
        return dict(tickmode="array", tickvals=ids,
                    ticktext=[f'<span style="color:{c["accent"]}"><b>{i}</b></span>' if focused and i == hot else i for i in ids])

    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(family="Source Code Pro, monospace", size=11, color=c["text"]),
                     **ticks(vessels, focus[0] if focused else None))
    fig.update_xaxes(side="top", showgrid=False, tickfont=dict(family="Source Code Pro, monospace", size=11, color=c["text"]),
                     **ticks(cargoes, focus[1] if focused else None))
    return style(fig, dark, 300)


def scatter(rows, focus, dark):
    """TCE against laycan slack; bubble area is contribution. Click a bubble to focus it."""
    c = ink(dark)
    fig = go.Figure()
    xs = [r["laycan_slack_days"] for r in rows] or [0]
    fig.add_vrect(x0=min(min(xs), 0) - 1.5, x1=0, fillcolor=c["bad"], line_width=0, layer="below")
    fig.add_vrect(x0=0, x1=3, fillcolor=c["band"], line_width=0, layer="below")
    fig.add_annotation(x=0, y=0, yref="paper", text="misses laycan ←", xanchor="right", yanchor="bottom", showarrow=False, font=dict(size=10, color=c["muted"]))
    fig.add_annotation(x=1.5, y=0, yref="paper", text="tight", yanchor="bottom", showarrow=False, font=dict(size=10, color=c["muted"]))
    top = max([abs(r["voyage_contribution_usd"]) for r in rows] or [1]) or 1
    radius = lambda r: max(10, 34 * math.sqrt(abs(r["voyage_contribution_usd"]) / top))
    for group in (False, True):
        part = [r for r in rows if r["feasible"] is group]
        if not part:
            continue
        is_focus = [(r["vessel_id"], r["cargo_id"]) == focus for r in part]
        fig.add_trace(go.Scatter(
            x=[r["laycan_slack_days"] for r in part], y=[r["tce_usd_per_day"] for r in part],
            mode="markers", customdata=[f'{r["vessel_id"]}|{r["cargo_id"]}' for r in part],
            hovertext=[_hover(r) for r in part], hovertemplate="%{hovertext}<extra></extra>",
            marker=dict(size=[radius(r) for r in part],
                        color=[c["accent"] if f else (c["other"] if group else "rgba(0,0,0,0)") for f in is_focus],
                        symbol="circle" if group else "circle-open",
                        line=dict(width=[3 if f else (2 if not group else 1.5) for f in is_focus],
                                  color=[c["text"] if f else (c["surface"] if group else c["other"]) for f in is_focus]),
                        opacity=1),
            name="Feasible" if group else "Fails a check"))
    # Label the focus first, then feasible pairings by contribution, then the rest, wherever there is room.
    # Every bubble is still named on hover and in the table.
    order = sorted(rows, key=lambda r: ((r["vessel_id"], r["cargo_id"]) != focus, not r["feasible"], -r["voyage_contribution_usd"]))
    for r, pos in zip(order, _place_labels([r["laycan_slack_days"] for r in order], [r["tce_usd_per_day"] for r in order])):
        if not pos:
            continue
        hot = (r["vessel_id"], r["cargo_id"]) == focus
        half = radius(r) / 2
        dx, dy = {"top center": (0, half + 7), "bottom center": (0, -half - 7),
                  "middle right": (half + 4, 0), "middle left": (-half - 4, 0)}[pos]
        fig.add_annotation(x=r["laycan_slack_days"], y=r["tce_usd_per_day"], text=label(r), showarrow=False, xshift=dx, yshift=dy,
                           xanchor={"middle right": "left", "middle left": "right"}.get(pos, "center"),
                           font=dict(size=10, color=c["text"] if hot else c["muted"]))
    fig.update_xaxes(title_text="Laycan slack, days (arrival before laycan closes)", zeroline=True, zerolinewidth=1)
    fig.update_yaxes(title_text="TCE before hire, USD/day", tickprefix="$", tickformat="~s")
    fig.update_layout(clickmode="event+select", dragmode=False)
    return style(fig, dark, 300)


def cost_share(rows, dark):
    """Each pairing's revenue split into costs and contribution, as a share of freight revenue."""
    c = ink(dark)
    rows = sorted(rows, key=lambda r: margin(r) if margin(r) is not None else -1e9)
    y = [label(r) for r in rows]
    fig = go.Figure()
    for (name, key), colour in zip(COSTS, COST_SLOTS[dark]):
        share = [100 * r[key] / r["freight_revenue_usd"] if r["freight_revenue_usd"] else 0 for r in rows]
        fig.add_trace(go.Bar(y=y, x=share, name=name, orientation="h", marker=dict(color=colour, line=dict(color=c["surface"], width=2)),
                             customdata=[r[key] for r in rows], hovertemplate=name + " %{x:.1f}% · $%{customdata:,.0f}<extra>%{y}</extra>"))
    share = [margin(r) or 0 for r in rows]
    fig.add_trace(go.Bar(y=y, x=[max(s, 0) for s in share], name="Contribution", orientation="h",
                         marker=dict(color=c["field"], line=dict(color=c["axis"], width=1)),
                         text=[f"{s:.1f}%" for s in share], textposition="inside", insidetextanchor="end",
                         textfont=dict(color=c["text"], size=11), customdata=[r["voyage_contribution_usd"] for r in rows],
                         hovertemplate="Contribution %{text} · $%{customdata:,.0f}<extra>%{y}</extra>"))
    style(fig, dark, max(220, 40 * len(rows) + 90))
    fig.update_layout(barmode="stack", showlegend=True, bargap=.35, margin=dict(l=8, r=12, t=30, b=8),
                      legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, font=dict(size=11, color=c["text2"]), traceorder="normal"))
    fig.update_xaxes(ticksuffix="%", range=[0, max(100, max((100 - s for s in share), default=100) + 5)], title_text="Share of freight revenue")
    fig.update_yaxes(tickfont=dict(family="Source Code Pro, monospace", size=11, color=c["text"]), showgrid=False)
    return fig


def stages(rows, dark):
    c = ink(dark)
    rows = sorted(rows, key=lambda r: r["voyage_days"])
    y = [label(r) for r in rows]
    fig = go.Figure()
    for (name, key) in STAGES.items():
        fig.add_trace(go.Bar(y=y, x=[r[key] for r in rows], name=name, orientation="h",
                             marker=dict(color=STAGE_COLOURS[name], line=dict(color=c["surface"], width=2)),
                             hovertemplate=name + " %{x:.1f} days<extra>%{y}</extra>"))
    fig.add_trace(go.Scatter(y=y, x=[r["voyage_days"] for r in rows], mode="text", text=[f'{r["voyage_days"]:.1f} days' for r in rows],
                             textposition="middle right", textfont=dict(size=11, color=c["text2"]), hoverinfo="skip", showlegend=False, name=""))
    style(fig, dark, max(220, 40 * len(rows) + 90))
    fig.update_layout(barmode="stack", showlegend=True, bargap=.35, margin=dict(l=8, r=12, t=30, b=8),
                      legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, font=dict(size=11, color=c["text2"]), traceorder="normal"))
    fig.update_xaxes(title_text="Days from open position to discharge complete", range=[0, max((r["voyage_days"] for r in rows), default=1) * 1.12])
    fig.update_yaxes(tickfont=dict(family="Source Code Pro, monospace", size=11, color=c["text"]), showgrid=False)
    return fig


def months(series, cargoes, vessels, focus, dark):
    """Contribution by bunker month, one panel per cargo; filled markers are feasible, open ones fail a check."""
    c = ink(dark)
    fig = make_subplots(rows=1, cols=len(cargoes), shared_yaxes=True, subplot_titles=cargoes, horizontal_spacing=.04)
    periods = list(series)
    ticks = [f'{["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(p[5:]) - 1]}' for p in periods]
    values = [r["voyage_contribution_usd"] for rows in series.values() for r in rows]
    span = (max(values) - min(min(values), 0)) * 1.1 if values else 1
    for col, cargo in enumerate(cargoes, 1):
        order = sorted(vessels, key=lambda v: (v, cargo) == focus)  # focus drawn last, on top
        ends = []
        for v in order:
            pts = [next((r for r in series[p] if r["vessel_id"] == v and r["cargo_id"] == cargo), None) for p in periods]
            if not any(pts):
                continue
            hot = (v, cargo) == focus
            colour = c["accent"] if hot else c["other"]
            fig.add_trace(go.Scatter(
                x=ticks, y=[r["voyage_contribution_usd"] if r else None for r in pts], mode="lines+markers",
                line=dict(color=colour, width=2.5 if hot else 1.5),
                marker=dict(size=8, color=[colour if r and r["feasible"] else c["surface"] for r in pts],
                            line=dict(color=colour, width=1.5), symbol="circle"),
                hovertext=[_hover(r) if r else "" for r in pts], hovertemplate="%{hovertext}<extra></extra>"), row=1, col=col)
            last = next(r for r in reversed(pts) if r)
            ends.append((ticks[len(pts) - 1 - pts[::-1].index(last)], last["voyage_contribution_usd"], v, hot))
        _end_labels(fig, ends, c, span, row=1, col=col)
        fig.update_xaxes(range=[-.3, len(periods) - .2], row=1, col=col)
    fig.update_yaxes(tickprefix="$", tickformat="~s", row=1, col=1, title_text="Contribution after hire")
    for a in fig.layout.annotations:
        if a.text in cargoes:
            a.font = dict(size=11, color=c["text"], family="Source Code Pro, monospace")
    style(fig, dark, 280)
    fig.update_layout(margin=dict(l=8, r=40, t=26, b=8))
    return fig


def lift_sensitivity(curves, cargo, focus, dark):
    """Contribution across the contract range per vessel: solid where feasible, dotted where a check fails."""
    c = ink(dark)
    fig = go.Figure()
    nominal = cargo["nominal_quantity_tonnes"]
    for at, name in ((float(cargo["minimum_quantity_tonnes"]), "min"), (float(nominal), "contract"), (float(cargo["maximum_quantity_tonnes"]), "max")):
        fig.add_vline(x=at, line=dict(color=c["axis"], width=1, dash="dot"))
        fig.add_annotation(x=at, y=1, yref="paper", text=name, showarrow=False, yanchor="bottom", font=dict(size=10, color=c["muted"]))
    ends = []
    for v, rows in sorted(curves.items(), key=lambda kv: kv[0] == (focus[0] if focus else None)):
        hot = focus is not None and v == focus[0]
        colour = c["accent"] if hot else c["other"]
        for feasible in (True, False):
            # Keep the line continuous: include the neighbour on each side of a run.
            y = [r["voyage_contribution_usd"] if r["feasible"] is feasible or
                 (i and rows[i - 1]["feasible"] is feasible) or (i + 1 < len(rows) and rows[i + 1]["feasible"] is feasible)
                 else None for i, r in enumerate(rows)]
            if not any(v_ is not None for v_ in y):
                continue
            fig.add_trace(go.Scatter(x=[r["selected_lift_tonnes"] for r in rows], y=y, mode="lines", connectgaps=False,
                                     line=dict(color=colour, width=2.5 if hot else 1.5, dash="solid" if feasible else "dot"),
                                     hovertext=[_hover(r) for r in rows], hovertemplate="%{hovertext}<extra></extra>"))
        ends.append((rows[-1]["selected_lift_tonnes"], rows[-1]["voyage_contribution_usd"], v, hot))
        if hot and focus:
            pick = next((r for r in rows if r["selected_lift_tonnes"] == focus[2]), None)
            if pick:
                fig.add_trace(go.Scatter(x=[pick["selected_lift_tonnes"]], y=[pick["voyage_contribution_usd"]], mode="markers",
                                         marker=dict(size=11, color=colour, line=dict(color=c["surface"], width=2)),
                                         hovertext=[_hover(pick)], hovertemplate="%{hovertext}<extra></extra>"))
    values = [r["voyage_contribution_usd"] for rows in curves.values() for r in rows]
    _end_labels(fig, ends, c, (max(values) - min(values)) * 1.1 if values else 1)
    fig.update_xaxes(title_text="Lift, tonnes", tickformat="~s", ticksuffix="t")
    fig.update_yaxes(title_text="Contribution after hire", tickprefix="$", tickformat="~s")
    style(fig, dark, 280)
    fig.update_layout(margin=dict(l=8, r=44, t=22, b=8))
    return fig
