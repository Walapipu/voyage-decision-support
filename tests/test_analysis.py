import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
from voyage.analysis import analyst_facts, profit_tone
from voyage.charts import earnings_chart, cost_chart, duration_chart
from voyage.tools import execute_tool
from voyage.decision import compare_vessels
from voyage.chat import chat_reply
from voyage.briefing import calculated_briefing, parse_commentary
from voyage.data import load_tables


def fuel_sufficient_comparison():
    """Hypothetical inventory fixture to retain positive ranking/chart coverage."""
    tables = deepcopy(load_tables())
    for vessel in tables["managed_vessels"]:
        vessel["vlsfo_rob_tonnes"] = "5000"
        vessel["mgo_rob_tonnes"] = "500"
    with patch("voyage.engine.load_tables", return_value=tables):
        return execute_tool("compare_vessels", '{"cargo_id":"CC-02","lift_tonnes":164000}')


class AnalysisTests(unittest.TestCase):
    def test_report_and_charts_reconcile_to_executed_result(self):
        output = fuel_sufficient_comparison()
        facts, rows = output["analysis"], output["rows"]
        best = rows[0]
        self.assertEqual(facts["highest_contribution_feasible_vessel"], "MF-02")
        self.assertEqual(facts["feasible_count"], 2)
        self.assertAlmostEqual(facts["focus_margin_pct"], best["voyage_contribution_usd"] / best["freight_revenue_usd"] * 100)
        self.assertAlmostEqual(facts["contribution_advantage_usd"], rows[0]["voyage_contribution_usd"] - rows[1]["voyage_contribution_usd"])
        self.assertAlmostEqual(sum(facts["cost_breakdown_usd"].values()) + best["voyage_contribution_usd"], best["freight_revenue_usd"])
        chart = earnings_chart(rows)
        self.assertEqual(list(chart.data[1].x), ["MF-02", "MF-01"])
        self.assertEqual(list(chart.data[1].y), [r["voyage_contribution_usd"] for r in rows if r["feasible"]])
        self.assertAlmostEqual(sum(cost_chart(best).data[0].y), best["voyage_contribution_usd"])
        self.assertAlmostEqual(sum(trace.x[0] for trace in duration_chart(rows).data), best["voyage_days"])

    def test_infeasible_and_zero_revenue_do_not_become_recommendations(self):
        rows = compare_vessels("CC-01", 178000)["rows"]
        facts = analyst_facts(rows)
        self.assertEqual(facts["feasible_count"], 0)
        self.assertIsNone(facts["highest_contribution_feasible_vessel"])
        self.assertEqual(len(earnings_chart(rows).data[0].x), 0)
        row = dict(rows[0], freight_revenue_usd=0)
        facts = analyst_facts([row])
        self.assertIsNone(facts["focus_margin_pct"])
        json.dumps(facts, allow_nan=False)
        for dark in (False, True):
            self.assertNotEqual(profit_tone(-12, dark)[0], profit_tone(12, dark)[0])
            self.assertLess(profit_tone(2, dark)[1], profit_tone(20, dark)[1])
            self.assertEqual(profit_tone(100, dark)[1], 1)

    @patch("voyage.chat.load_settings", return_value=("test-secret", "openrouter/free"))
    def test_analyst_receives_calculated_facts(self, settings):
        first = {"choices":[{"message":{"role":"assistant", "tool_calls":[{"id":"one", "function":{"name":"compare_vessels", "arguments":'{"cargo_id":"CC-02","lift_tonnes":164000}'}}]}}]}
        second = {"choices":[{"message":{"content":"MF-02 offers the highest feasible contribution."}}]}
        with patch("voyage.chat.api_request", side_effect=[first, second]) as api:
            answer = chat_reply([{"role":"user", "content":"Analyse CC-02"}], force_comparison=True)
        self.assertEqual(api.call_args_list[0].args[2]["tool_choice"]["function"]["name"], "compare_vessels")
        actual_tool_data = json.loads(next(m["content"] for m in api.call_args_list[1].args[2]["messages"] if m["role"] == "tool"))
        self.assertEqual(actual_tool_data["analysis"], answer["evidence"][0]["result"]["analysis"])
        with patch("voyage.chat.api_request", return_value=second), self.assertRaises(ValueError):
            chat_reply([], force_comparison=True)

    def test_unsupported_numeric_commentary_is_replaced(self):
        output = fuel_sufficient_comparison()
        invalid = json.dumps({"assessment":"Best option", "drivers":"Saves 9.6M in costs", "risk":"Delay", "next_action":"Review"})
        self.assertIsNone(parse_commentary(invalid))
        report = calculated_briefing([{"result":output}])
        self.assertNotIn("9.6M", report)
        self.assertIn("44,987", report)
        self.assertIn("profit margin **12.1%**", report)
        valid = json.dumps({"assessment":"The leading feasible vessel provides a stronger commercial result.", "drivers":"Positioning reduces unproductive sailing time.", "risk":"Confirm the arrival window before commitment.", "next_action":"Review readiness with operations."})
        self.assertIsNotNone(parse_commentary(valid))

    def test_repeated_analyst_replies_render_unique_dashboards(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        output = execute_tool("compare_vessels", '{"cargo_id":"CC-02","lift_tonnes":164000}')
        answer = {"content":"MF-02 offers the highest feasible contribution.", "model":"test", "truncated":False,
                  "evidence":[{"tool":"compare_vessels", "result":output}]}
        with patch("voyage.chat.chat_reply", return_value=answer) as chat:
            app.chat_input[0].set_value("Compare CC-02 at 164000 tonnes").run()
            self.assertFalse(chat.call_args.kwargs["force_comparison"])
            self.assertFalse(app.exception)
            app.chat_input[0].set_value("Compare it again").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("plotly_chart")), 6)
        self.assertEqual(len(app.chat_message), 4)
