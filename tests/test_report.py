import copy
from html.parser import HTMLParser
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from voyage.dashboard_data import dashboard_case
from voyage.report import analytics_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.case = dashboard_case('CC-02', 164000, '2026-03', 'MF-01')

    def test_report_preserves_results_and_bundles_charts_offline(self):
        report = analytics_report(self.case)
        self.assertIn('CC-02', report)
        self.assertIn('164,000 tonnes', report)
        self.assertIn('2026-03', report)
        for row in self.case['comparison']['rows']:
            self.assertIn(row['vessel_id'], report)
            self.assertIn(f"{row['voyage_contribution_usd']:,.2f}", report)
        self.assertIn('Methodology and assumptions', report)
        self.assertIn('Full calculation evidence', report)
        self.assertIn('Fuel replenishment assumed', report)
        self.assertIn('Plotly.newPlot', report)
        scripts = []
        class Scripts(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == 'script':
                    scripts.append(dict(attrs))
        Scripts().feed(report)
        self.assertTrue(scripts)
        self.assertFalse(any('src' in attrs for attrs in scripts))

    def test_all_excluded_options_are_not_recommended(self):
        case = copy.deepcopy(self.case)
        for row in case['comparison']['rows']:
            row['feasible'] = False
            row['failed_checks'] = ['laycan']
        report = analytics_report(case)
        self.assertIn('No feasible options; cost figures below are hypothetical', report)
        self.assertIn('Excluded: laycan', report)
        self.assertNotIn('<h2>Earnings comparison</h2>', report)

    def test_text_is_escaped_in_export(self):
        self.case['comparison']['scope'] = '<script>alert("scope")</script>'
        self.case['comparison']['rows'][0]['warnings'].append('<img src=x onerror=alert(1)>')
        report = analytics_report(self.case)
        self.assertNotIn('<script>alert("scope")</script>', report)
        self.assertIn('&lt;script&gt;', report)
        self.assertNotIn('<img src=x onerror=alert(1)>', report)

    def test_analytics_download_requires_selection_and_exports_current_case(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
        next(r for r in app.radio if r.label == 'Navigation').set_value('Analytics').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.get('download_button')[0].proto.disabled)
        app.selectbox(key='selected_vessel').set_value('MF-01').run()
        app.selectbox(key='selected_cargo').set_value('CC-02').run()
        app.number_input(key='selected_lift').set_value(164000)
        with patch('streamlit.download_button') as download:
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(download.call_args.args[0], 'Download report')
        self.assertIn('164,000 tonnes', download.call_args.args[1])
        self.assertEqual(download.call_args.kwargs['file_name'], 'oceanflow_CC-02_2026-03_report.html')
        self.assertEqual(download.call_args.kwargs['on_click'], 'ignore')


if __name__ == '__main__':
    unittest.main()
