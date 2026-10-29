"""Self-contained Analytics export built only from executed engine evidence."""
from datetime import datetime, timezone
from html import escape
import json

from voyage.analysis import analyst_facts, result_frame
from voyage.charts import earnings_chart, cost_chart, duration_chart
from voyage.fuel import shortage_message


def analytics_report(case):
    comparison = case["comparison"]
    rows = comparison["rows"]
    facts = analyst_facts(rows)
    focus = next(row for row in rows if row["vessel_id"] == facts["focus_vessel"])
    cargo = case["cargo"]
    e = lambda value: escape(str(value))
    frame = result_frame(rows)
    frame["Status"] = ["Feasible" if row["feasible"] else "Excluded: " + ", ".join(row["failed_checks"]) for row in rows]
    frame = frame.rename(columns={"vessel_id": "Vessel", "voyage_days": "Days", "tce_usd_per_day": "TCE (USD/day)",
        "voyage_contribution_usd": "Contribution (USD)", "profit_margin_pct": "Margin (%)"})
    table = frame[["Vessel", "Status", "Days", "TCE (USD/day)", "Contribution (USD)", "Margin (%)"]].to_html(
        index=False, escape=True, border=0, float_format=lambda value: f"{value:,.2f}")
    warnings = []
    for row in rows:
        notes = list(row["warnings"])
        if not row["feasible"]:
            notes.insert(0, "Excluded: " + ", ".join(row["failed_checks"]) + ". Financial figures are hypothetical.")
        if not row["fuel_pass"]:
            notes.append(shortage_message(row))
        warnings.extend(f"<li><b>{e(row['vessel_id'])}</b>: {e(note)}</li>" for note in notes)
    figures = []
    if facts["feasible_count"]:
        figures.append(("Earnings comparison", earnings_chart(rows, dark=False)))
    figures.extend([(f"Cost drivers: {focus['vessel_id']}", cost_chart(focus, dark=False)),
                    ("Voyage time: all evaluated options", duration_chart(rows, dark=False))])
    charts = "".join(f"<section><h2>{e(title)}</h2>" + figure.to_html(full_html=False,
        include_plotlyjs=(idx == 0), config={"displaylogo": False, "responsive": True}) + "</section>"
        for idx, (title, figure) in enumerate(figures))
    conventions = "".join(f"<tr><th>{e(key.replace('_', ' ').title())}</th><td>{e(value)}</td></tr>"
        for key, value in comparison["conventions"].items())
    focus_label = "Highest contribution among feasible options" if facts["feasible_count"] else "No feasible options; cost figures below are hypothetical"
    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OceanFlow Analytics - {e(focus['cargo_id'])}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f0f4f8;color:#14243b;font:15px/1.6 Arial,sans-serif}}
main{{max-width:1100px;margin:32px auto;padding:28px;background:white;border-radius:12px}}
h1{{margin:0;font-size:30px}}h2{{font-size:20px;margin:24px 0 12px}}p{{margin:8px 0}}.muted{{color:#62768e}}
.summary{{background:#edf6ff;border-left:4px solid #087bf5;padding:16px;margin:20px 0}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #e0e7ef;vertical-align:top}}th{{background:#f3f6fa}}
li{{margin:8px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}section{{break-inside:avoid}}
@media(max-width:600px){{main{{margin:0;padding:16px;border-radius:0}}}}@media print{{body{{background:white}}main{{margin:0;padding:0;max-width:none}}.modebar{{display:none!important}}}}
</style></head><body><main>
<header><p class="muted">OceanFlow · Voyage Decision Support</p><h1>Analytics report</h1><p class="muted">Generated {generated}</p></header>
<p><b>{e(focus['cargo_id'])}</b> · {e(cargo['load_port'])} → {e(cargo['discharge_port'])} · {focus['selected_lift_tonnes']:,.0f} tonnes · Bunker price month {e(focus['bunker_price_period'])}</p>
<p>Selected vessel: {e(case['row']['vessel_id'])}. {e(comparison['scope'])}</p>
<div class="summary"><b>{e(focus_label)}</b><p>{e(focus['vessel_id'])} · Contribution USD {focus['voyage_contribution_usd']:,.2f} · TCE USD {focus['tce_usd_per_day']:,.2f}/day · {facts['feasible_count']} / {facts['evaluated_count']} feasible options</p></div>
<p>TCE is before hire; contribution is after hire for the whole voyage. Voyage durations differ, so contribution ranking is not a fleet allocation plan.</p>
<h2>Vessel comparison</h2><div class="table-wrap">{table}</div>
<h2>Feasibility and planning notes</h2><ul>{''.join(warnings) or '<li>No additional engine warnings.</li>'}</ul>
{charts}
<h2>Methodology and assumptions</h2><div class="table-wrap"><table>{conventions}</table></div>
<p>Fuel is valued at the loading port's regional price proxy for the selected month. A price proxy does not establish a bunkering location. Canal cost is provisionally zero.</p>
<p>Scenario analysis and recommendation-switch thresholds are not available. Market quotes and fleet-wide allocation are outside this comparison.</p>
<details><summary>Full calculation evidence</summary><pre>{e(json.dumps(comparison, indent=2))}</pre></details>
</main></body></html>'''
