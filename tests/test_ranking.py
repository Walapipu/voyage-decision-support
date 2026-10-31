import unittest
from voyage.data import load_tables
from voyage.engine import calculate
from voyage.ranking import quantity_options, rank_cargo


class RankingTests(unittest.TestCase):
    def test_selected_lift_ranks_exact_quantity(self):
        result = rank_cargo('CC-02', lift_tonnes=160500)
        self.assertTrue(result['all_options'])
        self.assertEqual(result['assumptions']['quantity_mode'], 'selected')
        for row in result['all_options']:
            self.assertEqual(row['recommended_tonnes'], 160500)
            expected = calculate(row['vessel_id'], 'CC-02', 160500)
            self.assertAlmostEqual(row['profit_usd'], float(expected['voyage_contribution_usd']))
        self.assertEqual(len(result['all_options']) + len(result['excluded']), 4)

    def test_out_of_range_quantity_never_recommended(self):
        cargo = next(c for c in load_tables()['committed_cargoes'] if c['cargo_id'] == 'CC-02')
        for quantity in (int(cargo['minimum_quantity_tonnes']) - 1,
                         int(cargo['maximum_quantity_tonnes']) + 1):
            result = rank_cargo('CC-02', lift_tonnes=quantity)
            self.assertIsNone(result['recommendation'])
            self.assertEqual(result['all_options'], [])
            self.assertEqual(len(result['excluded']), 4)
            self.assertTrue(all('quantity' in r['reason'] for r in result['excluded']))

    def test_quantity_boundaries_and_threshold(self):
        cargo = dict(minimum_quantity_tonnes='100', nominal_quantity_tonnes='155',
                     maximum_quantity_tonnes='230', special_freight_threshold_tonnes='175')
        self.assertEqual([float(q) for q in quantity_options(cargo, 60)], [100, 155, 160, 175, 220, 230])

    def test_rankings_feasible_and_reconciled(self):
        for cargo in load_tables()['committed_cargoes']:
            result = rank_cargo(cargo['cargo_id'])
            rows = result['all_options']
            self.assertEqual(rows, sorted(rows, key=lambda r: (-r['profit_usd'], -r['tce_usd_per_day'], r['vessel_id'])))
            for row in rows:
                self.assertTrue(row['feasible'])
                self.assertAlmostEqual(row['profit_usd'], float(calculate(row['vessel_id'], cargo['cargo_id'], row['lift_tonnes'])['voyage_contribution_usd']))
                self.assertLessEqual(row['stress_profit_usd'], row['profit_usd'])
            for row in result['best_per_vessel']:
                self.assertEqual(row['profit_usd'], max(r['profit_usd'] for r in rows if r['vessel_id'] == row['vessel_id']))
            if rows:
                self.assertEqual(result['recommendation']['expected_profit_usd'], rows[0]['profit_usd'])

    def test_zero_stress_and_validation(self):
        result = rank_cargo('cc-02', bunker_increase=0, port_delay_days=0, port_cost_increase=0)
        for row in result['all_options']:
            self.assertEqual(row['profit_usd'], row['stress_profit_usd'])
        for kwargs in ({'risk_weight': 2}, {'quantity_step': 0}, {'bunker_increase': float('nan')}):
            with self.assertRaises(ValueError):
                rank_cargo('CC-02', **kwargs)

    def test_extra_ballast_changes_arrival(self):
        base = calculate('MF-02', 'CC-02', 164000)
        stress = calculate('MF-02', 'CC-02', 164000, additional_ballast_nm=10000)
        self.assertGreater(stress['ballast_days'], base['ballast_days'])
        self.assertFalse(stress['laycan_pass'])
