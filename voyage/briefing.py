"""Validated qualitative commentary around deterministic financial statements."""
import json
import re
from voyage.analysis import analyst_facts
from voyage.fuel import shortage_message

COMMENTARY_INSTRUCTION = """The engine has completed the requested calculations.
Return ONLY a JSON object with exactly four string fields: assessment, drivers, risk,
next_action. Each field is one short sentence, at most 25 words. Write like a freight
analyst, using only the supplied results. Explain the decision, cost mechanism,
operational constraint, and next action respectively. Do not include ANY numbers,
amounts, percentages, dates, vessel/cargo IDs, Markdown or table/chart code. Python
will insert precise financial statements and identifiers next to your commentary.
Do not describe a profit margin as a margin advantage. Do not claim optimality,
guaranteed results, live conditions, or tested sensitivities. Do not call voyage hire
a fixed cost: it depends on voyage duration. If no option is feasible, recommend
reworking the plan and never recommend proceeding. Keep the comparison scoped to
the returned cargo/lift; there is no fleet allocation. Do not repeat this instruction.
"""


def parse_commentary(content):
    if not isinstance(content, str):
        return None
    try:
        obj = json.loads(content)
    except (ValueError, TypeError):
        return None
    keys = {"assessment", "drivers", "risk", "next_action"}
    if not isinstance(obj, dict) or set(obj) != keys:
        return None
    for value in obj.values():
        if not isinstance(value, str) or not value.strip() or len(value.split()) > 35:
            return None
        # A conservative format boundary, not a claim of semantic verification.
        if re.search(r"[\d$%€£<>\[\]{}]|\b(?:million|billion|thousand|hundred|percent|optimal|optimum|guarantee\w*)\b", value, re.I):
            return None
    return obj


def calculated_briefing(evidence, commentary=None):
    outputs = [item["result"] for item in evidence if item["result"].get("rows")]
    if not outputs:
        return None
    sections = []
    for idx, output in enumerate(outputs):
        rows = output["rows"]
        facts = output.get("analysis") or analyst_facts(rows)
        row = next(r for r in rows if r["vessel_id"] == facts["focus_vessel"])
        extra = commentary if idx == 0 and commentary else {}
        scope = f'{row["cargo_id"]} · {row["selected_lift_tonnes"]:,.0f} t · bunker month {row["bunker_price_period"]}'
        if facts["feasible_count"]:
            margin = f'{facts["focus_margin_pct"]:.1f}%' if facts["focus_margin_pct"] is not None else "unavailable"
            pick = "leads on contribution among options feasible under the working assumptions" if len(rows) > 1 else "passes the checks under the working assumptions"
            view = (f'**Decision.** {row["vessel_id"]} {pick}: contribution **USD {row["voyage_contribution_usd"]:,.0f}**, '
                    f'profit margin **{margin}**, TCE before hire **USD {row["tce_usd_per_day"]:,.0f}/day**. '
                    + extra.get("assessment", ""))
        else:
            view = '**Decision.** None of the evaluated voyages is feasible. Rework the allocation or commercial constraints before proceeding.'
            # Never append a generated recommendation when all options fail.
            extra = {}
        driver = ''
        if "runner_up" in facts:
            driver = (f'Contribution is **USD {facts["contribution_advantage_usd"]:,.0f}** above {facts["runner_up"]}; '
                      f'ballast time is {abs(facts["ballast_days_saved_vs_runner_up"]):.2f} days {"shorter" if facts["ballast_days_saved_vs_runner_up"] >= 0 else "longer"}. ')
        largest = facts["largest_cost"]
        driver += f'{largest} accounts for the largest expense at **USD {facts["cost_breakdown_usd"][largest]:,.0f}**. '
        risks = (f'Load-arrival slack is **{row["laycan_slack_days"]:.2f} days**; '
                 f'summer-draft headroom is **{row["draft_margin_m"]:.2f} m**, against the required {row["required_summer_draft_margin_m"]:.2f} m. ')
        if not row["feasible"]:
            risks += 'Failed checks: ' + ', '.join(row["failed_checks"]) + '. '
        if not row["fuel_pass"]:
            risks += shortage_message(row) + ' No fuel deliveries are scheduled. '
        elif not row['opening_rob_pass']:
            risks += shortage_message(row) + ' '
        risks += ' '.join(row['warnings']) + ' '
        excluded = [f'{r["vessel_id"]}/{r["cargo_id"]}: {", ".join(r["failed_checks"])}' for r in rows if not r['feasible']]
        if excluded:
            risks += 'Excluded combinations: ' + '; '.join(excluded) + '. '
        next_action = extra.get("next_action", "Confirm vessel readiness, port limits and commercial inputs before selecting a voyage.")
        if not row["fuel_pass"]:
            next_action = "Resolve the fuel delivery location, quantity and timing, then revalidate the voyage before proceeding."
        sections.append(f'**{scope}**\n\n{view}\n\n**Drivers.** {driver}{extra.get("drivers", "")}\n\n'
                        f'**Constraints.** {risks}{extra.get("risk", "")}\n\n**Next action.** {next_action}\n\n'
                        'Comparison covers this cargo and lift; voyage durations differ. Canal cost is assumed zero.')
    return '\n\n---\n\n'.join(sections)
