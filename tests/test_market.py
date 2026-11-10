import unittest

from voyage.data import load_tables
from voyage.engine import calculate
from voyage.market import market_rates, offer_table, quote_table


class MarketRateTests(unittest.TestCase):
    def test_index_route_cargoes_reproduce_the_pack_ffa(self):
        quotes = market_rates()["quotes"]
        self.assertEqual(quotes["MC-01"]["rate_usd_per_tonne"], 9.05)   # C5, March 2026
        self.assertEqual(quotes["MC-02"]["rate_usd_per_tonne"], 21.9)   # C3, Q2 2026
        self.assertEqual(quotes["MC-07"]["tce_source"], "C5_USD_PER_TONNE")

    def test_every_market_cargo_has_a_positive_quote_near_published_spreads(self):
        quotes = market_rates()["quotes"]
        self.assertEqual(set(quotes), {f"MC-0{i}" for i in range(1, 9)})
        ratio = lambda cid, index: quotes[cid]["rate_usd_per_tonne"] / quotes[cid][index]
        self.assertTrue(0.75 <= ratio("MC-03", "c3_usd_per_tonne") <= 0.90)   # Saldanha
        self.assertTrue(0.70 <= ratio("MC-06", "c3_usd_per_tonne") <= 0.80)   # Kamsar to India
        self.assertTrue(0.85 <= ratio("MC-04", "c5_usd_per_tonne") <= 1.10)   # Indonesia to India

    def test_hire_offers_sit_around_the_delivery_month_5tc(self):
        offers = market_rates()["offers"]
        self.assertEqual(len(offers), 11)
        for offer in offers.values():
            self.assertEqual(offer["index_usd_per_day"], 18900)
            self.assertLess(abs(offer["hire_usd_per_day"] - 18900), 1500)
            self.assertEqual(offer["hire_usd_per_day"] % 50, 0)

    def test_engine_prices_market_pairs_with_the_assumptions(self):
        row = calculate("MV-09", "MC-07", 166000)
        offer = market_rates()["offers"]["MV-09"]["hire_usd_per_day"]
        quote = market_rates()["quotes"]["MC-07"]["rate_usd_per_tonne"]
        self.assertAlmostEqual(float(row["freight_revenue_usd"]), 166000 * quote, places=2)
        self.assertAlmostEqual(float(row["hire_cost_usd"]), float(row["voyage_days"]) * offer, places=2)

    def test_source_tables_are_not_rewritten(self):
        tables = load_tables()
        self.assertTrue(all(c["contract_freight_rate_usd_per_tonne"] == "0" for c in tables["market_cargoes"]))
        self.assertNotIn("hire_rate_usd_per_day", tables["market_vessels"][0])

    def test_display_tables_cover_every_row(self):
        self.assertEqual(len(offer_table()), 11)
        self.assertEqual(len(quote_table()), 8)


if __name__ == "__main__":
    unittest.main()
