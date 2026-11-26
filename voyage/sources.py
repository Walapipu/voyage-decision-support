"""Where the tables come from: the data-pack CSV files, or a SQL database.

Both sources implement the same small interface (the repository pattern): `read()` returns
{table name: [{column: text value}]} following the contract in voyage/schema.py, and nothing
else in the app knows which one is in use. voyage/data.py validates whatever a source returns
and decides when to read it again.

Choosing a source (environment variables win over .streamlit/secrets.toml):

    VOYAGE_DATA_SOURCE   / [data] source           "csv" (default) or "sql"
    VOYAGE_DATABASE_URL  / [connections.voyage_db] url
                                                   SQLAlchemy URL, e.g. postgresql+psycopg://...
                           [data] connection       name of the [connections.*] block (voyage_db)
                           [data] schema           database schema holding the tables, if not the default
                           [data] refresh_seconds  how often to re-read the database (600)

The [connections.*] block uses Streamlit's st.connection layout, so the same secret also works
with st.connection("voyage_db", type="sql") for ad-hoc queries. The database driver for the
chosen URL (for example psycopg for PostgreSQL) must be installed alongside SQLAlchemy.
"""
import csv
import os
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
DEFAULT_REFRESH_SECONDS = 600


class CsvSource:
    """The frozen data-pack files: every .csv under the folder, named by file stem."""

    refresh_seconds = None  # files only change with a deploy, so they are read once per run

    def __init__(self, root=RAW):
        self.root = Path(root)
        self.key = ("csv", str(self.root))

    def read(self):
        tables = {}
        for path in sorted(self.root.rglob("*.csv")):
            with path.open(encoding="utf-8-sig", newline="") as handle:
                tables[path.stem] = list(csv.DictReader(handle))
        return tables


class SqlSource:
    """A SQL database holding the contract tables. Values come back as text, NULL as an empty
    string, so the engine sees exactly what the CSV source would give it."""

    def __init__(self, url, schema=None, refresh_seconds=DEFAULT_REFRESH_SECONDS):
        self.url, self.schema, self.refresh_seconds = url, schema, refresh_seconds
        self.key = ("sql", url, schema)
        self._engine = None

    def engine(self):
        if self._engine is None:
            from sqlalchemy import create_engine
            # pool_pre_ping replaces connections the server has dropped between refreshes.
            self._engine = create_engine(self.url, pool_pre_ping=True)
        return self._engine

    def read(self):
        from sqlalchemy import inspect, select
        from voyage.schema import metadata
        tables = {}
        with self.engine().connect() as conn:
            present = set(inspect(conn).get_table_names(schema=self.schema)) | \
                set(inspect(conn).get_view_names(schema=self.schema))
            for name, table in metadata.tables.items():
                if name not in present:
                    continue  # data.validate reports any required table that is missing
                bound = table.to_metadata(_bare(), schema=self.schema) if self.schema else table
                rows = conn.execute(select(bound)).mappings()
                tables[name] = [{k: "" if v is None else str(v) for k, v in row.items()} for row in rows]
        return tables


def _bare():
    from sqlalchemy import MetaData
    return MetaData()


def _secrets():
    """The secrets file as a plain dict, or {} outside Streamlit or when there is none."""
    try:
        import streamlit as st
        return st.secrets.to_dict()
    except Exception:
        return {}


_sources = {}


def configured_source():
    """The source the settings ask for. Built once per setting, so a SQL engine and its
    connection pool are reused across reads."""
    secrets = _secrets()
    data = secrets.get("data", {})
    kind = (os.environ.get("VOYAGE_DATA_SOURCE") or data.get("source") or "csv").lower()
    if kind == "csv":
        key = ("csv",)
        if key not in _sources:
            _sources[key] = CsvSource()
        return _sources[key]
    if kind != "sql":
        raise ValueError(f'Unknown data source "{kind}". Use "csv" or "sql".')
    name = data.get("connection", "voyage_db")
    url = os.environ.get("VOYAGE_DATABASE_URL") or secrets.get("connections", {}).get(name, {}).get("url")
    if not url:
        raise ValueError(f"The data source is sql but no database URL is set. Add [connections.{name}] url "
                         "to .streamlit/secrets.toml or set VOYAGE_DATABASE_URL.")
    schema = data.get("schema") or None
    refresh = int(data.get("refresh_seconds", DEFAULT_REFRESH_SECONDS))
    key = ("sql", url, schema, refresh)
    if key not in _sources:
        _sources[key] = SqlSource(url, schema, refresh)
    return _sources[key]
