"""Publish the practice database to Postgres (Supabase): the shared, always-on copy everyone
queries in class through the Supabase connector, read-only.

Instructor only. Participants never run this.
    1. pip install -r requirements-instructor.txt
    2. Put the project's Session pooler connection string in .env (never committed). Supabase
       dashboard → Connect → Session pooler; the direct connection needs IPv6:
         DATABASE_URL=postgresql://postgres.<ref>:<password>@<host>:5432/postgres
    3. python3 load.py   (builds data/warehouse.sqlite, checks it, then publishes it here)

The local SQLite build is the checked master: load.py validates every file there first, and
only a build that passed is copied. The copy is one transaction, so people querying during a
publish see the old data until the new data is complete. Tables live in the schema `este`,
which Supabase's web API does not expose.
"""
import os, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA = "este"

# Same tables as load.py, with real Postgres types (dates are dates, so date maths works).
TABLES = {
    "locations": "location_id TEXT PRIMARY KEY, name TEXT, type TEXT, city TEXT, currency TEXT",
    "suppliers": "supplier_id TEXT PRIMARY KEY, name TEXT, country TEXT, lead_time_weeks INTEGER",
    "products": "style_code TEXT PRIMARY KEY, name TEXT, shopify_handle TEXT, category TEXT, collection TEXT, "
                "supplier_id TEXT, fabric TEXT, unit_cost_eur NUMERIC, price_eur NUMERIC, price_usd NUMERIC, "
                "price_gbp NUMERIC, launch_date DATE, status TEXT",
    "variants": "sku TEXT PRIMARY KEY, style_code TEXT, shopify_name TEXT, size TEXT, color TEXT, category TEXT",
    "store_sales": "sale_date DATE, location_id TEXT, sku TEXT, qty INTEGER, net_amount NUMERIC, currency TEXT, "
                   "source_file TEXT",
    "online_orders": "order_name TEXT, ordered_at TIMESTAMP, sale_date DATE, currency TEXT, sku TEXT, "
                     "shopify_name TEXT, qty INTEGER, unit_price NUMERIC, country TEXT",
    "online_returns": "return_id TEXT, order_name TEXT, return_date DATE, sku TEXT, qty INTEGER, status TEXT",
    "stock_sage": "snapshot_date DATE, location_id TEXT, sku TEXT, qty INTEGER, source_file TEXT",
    "shopify_stock": "pulled_at TIMESTAMP, shopify_handle TEXT, shopify_variant_id TEXT, sku TEXT, "
                     "shopify_name TEXT, qty INTEGER",
    "purchase_orders": "po_id TEXT, supplier_id TEXT, order_date DATE, expected_date DATE, sku TEXT, qty INTEGER, "
                       "unit_cost_eur NUMERIC, status TEXT",
    "production_plan": "season TEXT, style_code TEXT, style TEXT, supplier_id TEXT, planned_units INTEGER, "
                       "produced_to_date INTEGER, first_delivery DATE",
    "fx_rates": "currency TEXT PRIMARY KEY, per_eur NUMERIC",
    "load_log": "loaded_at TIMESTAMP, file TEXT, table_name TEXT, rows INTEGER",
}


def database_url():
    """DATABASE_URL from the environment, else from .env. None = local only."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "DATABASE_URL" and value.strip():
                return value.strip().strip('"').strip("'")
    return None


def connect():
    try:
        import psycopg2
    except ImportError:
        raise SystemExit("DATABASE_URL is set but psycopg2 is not installed: "
                         "pip install -r requirements-instructor.txt")
    return psycopg2.connect(database_url(), connect_timeout=15)


def _insert(cur, table, rows):
    from psycopg2.extras import execute_values
    if rows:
        execute_values(cur, f"INSERT INTO {SCHEMA}.{table} VALUES %s", rows, page_size=1000)


def publish(sqlite_path):
    """Replace the whole schema with the SQLite build, in one transaction."""
    src = sqlite3.connect(sqlite_path)
    con = connect()
    try:
        with con, con.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            cur.execute(f"CREATE SCHEMA {SCHEMA}")
            for table, cols in TABLES.items():
                cur.execute(f"CREATE TABLE {SCHEMA}.{table} ({cols})")
                _insert(cur, table, src.execute(f"SELECT * FROM {table}").fetchall())
            # The connector's read-only mode queries as supabase_read_only_user. Nobody else
            # (and not the web API roles anon/authenticated) gets access to this schema.
            cur.execute("""DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_read_only_user') THEN
                  EXECUTE 'GRANT USAGE ON SCHEMA este TO supabase_read_only_user';
                  EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA este TO supabase_read_only_user';
                END IF; END $$""")
            total = 0
            for table in TABLES:  # still inside the transaction: a mismatch publishes nothing
                cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
                remote = cur.fetchone()[0]
                local = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if remote != local:
                    raise SystemExit(f"Postgres got {remote} rows in {table}, the local build has {local}. "
                                     "Nothing was published.")
                total += remote
        print(f"Published to Postgres (schema {SCHEMA}): {total} rows in {len(TABLES)} tables.")
    finally:
        con.close()
        src.close()


def append(sqlite_path, file_name):
    """Copy the rows one nightly file added locally (watch_inbox.py) to Postgres."""
    src = sqlite3.connect(sqlite_path)
    con = connect()
    try:
        with con, con.cursor() as cur:
            for table in ("store_sales", "stock_sage"):
                _insert(cur, table, src.execute(f"SELECT * FROM {table} WHERE source_file = ?", (file_name,)).fetchall())
            _insert(cur, "load_log", src.execute("SELECT * FROM load_log WHERE file = ?", (file_name,)).fetchall())
    finally:
        con.close()
        src.close()
