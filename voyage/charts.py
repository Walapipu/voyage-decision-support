"""Plotly figures built from executed engine rows, never from generated code."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from voyage.analysis import COSTS, STAGES, result_frame, profit_tone


def style_chart(fig, dark, height=280):
    text, line = ("#c4d5e4", "#2a4056") if dark else ("#30475e", "#e0e7ef")
    fig.update_layout(height=height, template="plotly_dark" if dark else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial, sans-serif", size=11, color=text),
        margin=dict(l=14, r=14, t=38, b=35), showlegend=False,
        hoverlabel=dict(font_size=12), modebar=dict(orientation="v"))
    fig.update_xaxes(gridcolor=line, zerolinecolor=line, automargin=True)
    fig.update_yaxes(gridcolor=line, zerolinecolor=line, automargin=True)
    return fig


def earnings_chart(rows, dark=True):
    frame = result_frame(rows)
    frame = frame[frame["feasible"]].sort_values("voyage_contribution_usd", ascending=False)
    fig = make_subplots(rows=1, cols=2, subplot_titles=["TCE before hire · USD/day", "Contribution after hire · USD"], horizontal_spacing=.18)
    for col, metric in enumerate(["tce_usd_per_day", "voyage_contribution_usd"], 1):
        colours = [profit_tone(v if col == 2 else (1 if v > 0 else -1 if v < 0 else 0), dark)[0]
                   for v in (frame["profit_margin_pct"] if col == 2 else frame[metric])]
        fig.add_trace(go.Bar(x=frame["vessel_id"].tolist(), y=frame[metric].tolist(),
            marker_color=colours, hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>"), row=1, col=col)
    fig.update_annotations(font_size=11)
    fig.update_yaxes(tickprefix="$", tickformat="~s")
    return style_chart(fig, dark)


def cost_chart(row, dark=True):
    labels = ["Revenue", *COSTS, "Contribution"]
    costs = [float(row[key]) for key in COSTS.values()]
    margin = 100 * row["voyage_contribution_usd"] / row["freight_revenue_usd"] if row["freight_revenue_usd"] else None
    fig = go.Figure(go.Waterfall(x=labels,
        measure=["absolute"] + ["relative"] * len(costs) + ["total"],
        y=[row["freight_revenue_usd"], *[-cost for cost in costs], 0],
        increasing=dict(marker_color="#38bdf8"), decreasing=dict(marker_color="#ef7182"),
        totals=dict(marker_color=profit_tone(margin, dark)[0]),
        connector=dict(line=dict(color="#6a8296", width=1)),
        hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>"))
    fig.update_yaxes(tickprefix="$", tickformat="~s")
    fig.update_layout(title=dict(text=f"{row['vessel_id']} · revenue to contribution", font_size=13))
    return style_chart(fig, dark)


def duration_chart(rows, dark=True):
    fig = go.Figure()
    for (name, key), colour in zip(STAGES.items(), ["#6099c8", "#f5bd66", "#7486e8", "#21b8c5", "#ad82db"]):
        fig.add_trace(go.Bar(name=name, y=[r["vessel_id"] for r in rows],
            x=[r[key] for r in rows], orientation="h", marker_color=colour,
            hovertemplate=name + ": %{x:.2f} days<extra>%{y}</extra>"))
    style_chart(fig, dark, height=210 if len(rows) == 1 else 270)
    fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", y=1.3, x=0))
    fig.update_xaxes(title_text="Voyage days, including ballast")
    return fig
