"""Create the contract tables in a database and load them from CSV files.

    python -m voyage.db_load                  # the database in the settings, from data/raw
    python -m voyage.db_load --source DIR     # load another folder of CSV files
    python -m voyage.db_load --create-only    # create empty tables, load nothing

The URL comes from VOYAGE_DATABASE_URL or [connections.voyage_db] url in .streamlit/secrets.toml
(see voyage/sources.py), never from the command line, so credentials stay out of shell history.

The files are validated first, then each table is replaced in one transaction: either every
table is loaded or the database is left as it was. Running it again with the same files gives
the same database. Creating tables is safe on a database that already has them.

This creates tables straight from voyage/schema.py, which suits a first setup. Once a shared
database holds real data, schema changes should go through a migration tool such as Alembic.
"""
import argparse
import os
import sys
from pathlib import Path

from voyage.data import validate
from voyage.sources import RAW, CsvSource, _secrets


def database_url():
    secrets = _secrets()
    name = secrets.get("data", {}).get("connection", "voyage_db")
    url = os.environ.get("VOYAGE_DATABASE_URL") or secrets.get("connections", {}).get(name, {}).get("url")
    if not url:
        raise SystemExit(f"No database URL. Set VOYAGE_DATABASE_URL or [connections.{name}] url in .streamlit/secrets.toml.")
    return url


def create_tables(engine, schema=None):
    from voyage.schema import metadata
    target = metadata
    if schema:
        from sqlalchemy import MetaData
        target = MetaData()
        for table in metadata.tables.values():
            table.to_metadata(target, schema=schema)
    target.create_all(engine)
    return target


def load(engine, root=RAW, schema=None):
    """Replace every contract table with the rows from the CSV files under root."""
    from sqlalchemy import delete, insert
    tables = validate(CsvSource(root).read())
    target = create_tables(engine, schema)
    with engine.begin() as conn:  # one transaction: all tables or none
        for table in target.sorted_tables:
            name = table.name
            if name not in tables:
                continue
            columns = {c.name for c in table.columns}
            extra = set(tables[name][0]) - columns if tables[name] else set()
            if extra:
                raise ValueError(f"{name} has columns the schema does not: {', '.join(sorted(extra))}")
            conn.execute(delete(table))
            if tables[name]:
                conn.execute(insert(table), tables[name])
    return {name: len(rows) for name, rows in tables.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, default=RAW, help="folder of CSV files (default data/raw)")
    parser.add_argument("--schema", default=None, help="database schema for the tables")
    parser.add_argument("--create-only", action="store_true", help="create the tables without loading rows")
    args = parser.parse_args(argv)
    from sqlalchemy import create_engine
    engine = create_engine(database_url())
    schema = args.schema or _secrets().get("data", {}).get("schema")
    if args.create_only:
        create_tables(engine, schema)
        print("Tables created.")
        return 0
    counts = load(engine, args.source, schema)
    print("Loaded " + ", ".join(f"{name} {count}" for name, count in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
