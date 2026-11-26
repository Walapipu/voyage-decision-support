import csv
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, text

from voyage import data, sources
from voyage.data import load_tables
from voyage.db_load import load
from voyage.schema import metadata
from voyage.sources import RAW, CsvSource, SqlSource


class DataSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # Windows may hold the SQLite file
        self.url = f"sqlite:///{Path(self.tmp.name) / 'voyage.db'}"
        self.engine = create_engine(self.url)
        load(self.engine)

    def tearDown(self):
        self.engine.dispose()
        for source in sources._sources.values():
            if isinstance(source, SqlSource) and source._engine is not None:
                source._engine.dispose()
        sources._sources.clear()
        data.reset()
        self.tmp.cleanup()

    def use_sql(self, refresh=None):
        env = {"VOYAGE_DATA_SOURCE": "sql", "VOYAGE_DATABASE_URL": self.url}
        patch = mock.patch.dict(os.environ, env)
        patch.start(); self.addCleanup(patch.stop)
        if refresh is not None:
            secrets = mock.patch("voyage.sources._secrets", return_value={"data": {"refresh_seconds": refresh}})
            secrets.start(); self.addCleanup(secrets.stop)
        sources._sources.clear(); data.reset()

    def test_schema_matches_every_csv_header(self):
        files = {p.stem: p for p in RAW.rglob("*.csv")}
        self.assertEqual(set(files), set(metadata.tables))
        for name, path in files.items():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                header = next(csv.reader(handle))
            self.assertEqual(header, [c.name for c in metadata.tables[name].columns], name)

    def test_database_returns_exactly_what_the_files_hold(self):
        source = SqlSource(self.url)
        self.assertEqual(source.read(), CsvSource().read())
        source.engine().dispose()

    def test_loading_twice_gives_the_same_database(self):
        load(self.engine)
        with self.engine.connect() as conn:
            count = conn.execute(text("select count(*) from managed_vessels")).scalar()
        self.assertEqual(count, len(CsvSource().read()["managed_vessels"]))

    def test_app_reads_the_database_when_configured(self):
        csv_tables = load_tables()
        self.use_sql()
        self.assertEqual(load_tables(), csv_tables)
        from voyage.plan import build_plan
        self.assertTrue(build_plan()["voyages"])

    def test_refresh_picks_up_changes_and_clears_computed_results(self):
        self.use_sql(refresh=0)
        from voyage.tools import tool_definitions
        before = tool_definitions()
        with self.engine.begin() as conn:
            conn.execute(text("update managed_vessels set vessel_id = 'MF-99' where vessel_id = 'MF-04'"))
        time.sleep(0.01)
        load_tables()
        vessels = next(t for t in tool_definitions() if t["function"]["name"] == "calculate_voyage")[
            "function"]["parameters"]["properties"]["vessel_id"]["enum"]
        self.assertIsNot(tool_definitions(), before)
        self.assertIn("MF-99", vessels)
        self.assertNotIn("MF-04", vessels)

    def test_bad_data_in_the_database_is_rejected(self):
        with self.engine.begin() as conn:
            conn.execute(text("delete from laden_routes where cargo_id = 'CC-01'"))
        self.use_sql()
        with self.assertRaisesRegex(ValueError, "Missing laden route for cargo CC-01"):
            load_tables()

    def test_unreachable_database_error_hides_the_url(self):
        secret_url = "sqlite:///" + str(Path(self.tmp.name) / "missing" / "nope.db")
        with mock.patch.dict(os.environ, {"VOYAGE_DATA_SOURCE": "sql", "VOYAGE_DATABASE_URL": secret_url}):
            sources._sources.clear(); data.reset()
            with self.assertRaises(RuntimeError) as caught:
                load_tables()
        self.assertNotIn("nope.db", str(caught.exception))

    def test_failed_refresh_keeps_the_last_good_tables(self):
        self.use_sql(refresh=0)
        good = load_tables()
        with mock.patch.object(SqlSource, "read", side_effect=OSError("down")):
            self.assertEqual(load_tables(), good)

    def test_sql_without_a_url_explains_what_to_set(self):
        with mock.patch.dict(os.environ, {"VOYAGE_DATA_SOURCE": "sql"}, clear=False), \
             mock.patch("voyage.sources._secrets", return_value={}):
            os.environ.pop("VOYAGE_DATABASE_URL", None)
            with self.assertRaisesRegex(ValueError, "VOYAGE_DATABASE_URL"):
                sources.configured_source()


class ToolListTests(unittest.TestCase):
    def test_chat_tool_choices_come_from_the_data(self):
        from voyage.tools import tool_definitions
        tables = load_tables()
        props = next(t for t in tool_definitions() if t["function"]["name"] == "calculate_voyage")["function"]["parameters"]["properties"]
        self.assertEqual(props["vessel_id"]["enum"],
                         [r["vessel_id"] for r in tables["managed_vessels"] + tables["market_vessels"]])
        self.assertEqual(props["cargo_id"]["enum"],
                         [r["cargo_id"] for r in tables["committed_cargoes"] + tables["market_cargoes"]])
        self.assertEqual(props["period"]["enum"], sorted({r["period"] for r in tables["bunker_forward_curve"]}))


if __name__ == "__main__":
    unittest.main()
