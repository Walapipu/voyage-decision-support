# Data sources

The app reads its data either from the data-pack CSV files in `data/raw/` (the default) or from a SQL database. The rest of the app does not know which one is in use. Calculations, pages and the chat behave identically with either source.

## How it fits together

```mermaid
flowchart LR
    CSV["CSV files (data/raw)"] --> Csv[CsvSource]
    DB[(SQL database)] --> Sql[SqlSource]
    Csv --> Load["data.py: validate, cache, refresh"]
    Sql --> Load
    Load --> App["Engine, pages, chat tool lists"]
    CSV -. "python -m voyage.db_load" .-> DB
```

| Piece | File | Job |
|---|---|---|
| Data contract | `voyage/schema.py` | One table per data-pack file, same column names. Column meanings are in `data/raw/DATA_DICTIONARY.md` |
| Sources | `voyage/sources.py` | `CsvSource` and `SqlSource` both return `{table: [row]}`; `configured_source()` picks one from settings |
| Loader | `voyage/data.py` | Validates every read, hands out copies, re-reads the database on a timer, clears computed results when the data changes |
| Database setup | `voyage/db_load.py` | Creates the tables and loads them from CSV files in one transaction |

## Connecting a database

1. Install the driver for your database next to SQLAlchemy, for example `psycopg[binary]` for PostgreSQL. SQLite needs no driver.
2. Create the tables and load the current data:
   ```
   set VOYAGE_DATABASE_URL=postgresql+psycopg://user:password@host:5432/voyage
   python -m voyage.db_load
   ```
3. Point the app at the database, in `.streamlit/secrets.toml` locally or in the hosting service's secrets:
   ```toml
   [data]
   source = "sql"
   refresh_seconds = 600

   [connections.voyage_db]
   url = "postgresql+psycopg://user:password@host:5432/voyage"
   ```
   `VOYAGE_DATA_SOURCE` and `VOYAGE_DATABASE_URL` environment variables override these. The URL contains credentials, so it belongs only in secrets or the environment, never in tracked files.

The `[connections.voyage_db]` block follows Streamlit's `st.connection` layout, so the same secret also serves `st.connection("voyage_db", type="sql")` for ad-hoc queries.

## What the database must hold

The tables and columns in `voyage/schema.py`, with values in the same form as the CSV files: numbers as plain decimals and timestamps as ISO 8601 UTC. If the company's own tables use different names or types, expose these as views over them. The app reads views the same way as tables, and casting to text in the view keeps the values in the expected form.

Every read is checked before the app uses it, so incomplete data fails with a message naming the problem:

- every required table is present and its key is unique
- every vessel and cargo port exists in `ports`
- every vessel has a ballast distance to every cargo's load port
- every cargo has a laden route
- every cargo has VLSFO and MGO prices for its laycan month at its load port's pricing location

When a new record goes in, these checks decide what else it needs. A new vessel needs ballast distances to every load port. A new cargo needs a laden route, ballast distances from every vessel's port and prices for its month. A new port also needs coordinates in `data/map_locations.json` to appear on the map.

## Refreshing

The database is read again every `refresh_seconds` (600 by default). The check runs on each page load, so new rows appear without restarting the app. When the data has changed, cached plans, rankings, market rates and the chat's vessel, cargo and month lists are cleared and rebuilt from the new data. If a re-read fails, for example because the database is briefly unreachable, the app keeps the last good data and tries again after the next interval. Errors never include the connection URL.

## Later steps

- **Schema changes.** `db_load` creates tables straight from `voyage/schema.py`, which suits a first setup. Once a shared database holds real data, manage schema changes with Alembic migrations.
- **Typed columns.** The contract uses text columns so both sources give the engine identical values. A typed warehouse schema can sit behind views that cast to text.
- **Write access.** The app only reads. The account it connects with should have read-only rights on these tables.
