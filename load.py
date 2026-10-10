"""Load every export in data/raw/ (and anything already processed from inbox/) into
data/warehouse.sqlite. Safe to run again: it rebuilds the database from the files.
All or nothing: if any file is wrong, it stops, says which file and why, and keeps the
previous database unchanged.

    python3 load.py          (Mac)
    python load.py           (Windows)

Standard library only. The raw files are never changed.
"""
import csv, json, os, sqlite3, sys
from pathlib import Path

import pg

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "warehouse.sqlite"
TMP = ROOT / "data" / "warehouse.sqlite.tmp"
PROCESSED = ROOT / "inbox" / "processed"

SCHEMA = """
CREATE TABLE locations (location_id TEXT PRIMARY KEY, name TEXT, type TEXT, city TEXT, currency TEXT);
CREATE TABLE suppliers (supplier_id TEXT PRIMARY KEY, name TEXT, country TEXT, lead_time_weeks INTEGER);
CREATE TABLE products (style_code TEXT PRIMARY KEY, name TEXT, shopify_handle TEXT, category TEXT,
  collection TEXT, supplier_id TEXT, fabric TEXT, unit_cost_eur REAL, price_eur REAL, price_usd REAL,
  price_gbp REAL, launch_date TEXT, status TEXT);
CREATE TABLE variants (sku TEXT PRIMARY KEY, style_code TEXT, shopify_name TEXT, size TEXT, color TEXT,
  category TEXT);
CREATE TABLE store_sales (sale_date TEXT, location_id TEXT, sku TEXT, qty INTEGER, net_amount REAL,
  currency TEXT, source_file TEXT);
CREATE TABLE online_orders (order_name TEXT, ordered_at TEXT, sale_date TEXT, currency TEXT, sku TEXT,
  shopify_name TEXT, qty INTEGER, unit_price REAL, country TEXT);
CREATE TABLE online_returns (return_id TEXT, order_name TEXT, return_date TEXT, sku TEXT, qty INTEGER,
  status TEXT);
CREATE TABLE stock_sage (snapshot_date TEXT, location_id TEXT, sku TEXT, qty INTEGER, source_file TEXT);
CREATE TABLE shopify_stock (pulled_at TEXT, shopify_handle TEXT, shopify_variant_id TEXT, sku TEXT, shopify_name TEXT,
  qty INTEGER);
CREATE TABLE purchase_orders (po_id TEXT, supplier_id TEXT, order_date TEXT, expected_date TEXT, sku TEXT,
  qty INTEGER, unit_cost_eur REAL, status TEXT);
CREATE TABLE production_plan (season TEXT, style_code TEXT, style TEXT, supplier_id TEXT, planned_units INTEGER,
  produced_to_date INTEGER, first_delivery TEXT);
CREATE TABLE fx_rates (currency TEXT PRIMARY KEY, per_eur REAL);
CREATE TABLE load_log (loaded_at TEXT DEFAULT CURRENT_TIMESTAMP, file TEXT, table_name TEXT, rows INTEGER);
"""


class LoadError(Exception):
    """A problem in one of the files, explained in plain words."""


def read_csv(path, delimiter, required):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise LoadError(f"{path.name}: column {', '.join(missing)} is missing. "
                            f"Columns found: {', '.join(reader.fieldnames or [])}.")
        return list(reader)


def rows(name, delimiter=",", required=()):
    return read_csv(RAW / name, delimiter, required)


def check_known_skus(con, path, skus):
    known = {s for (s,) in con.execute("SELECT sku FROM variants")}
    unknown = sorted(set(skus) - known)
    if unknown:
        raise LoadError(f"{path.name}: {len(unknown)} article code(s) not in sage_artigos.csv, "
                        f"e.g. {', '.join(unknown[:5])}.")


def check_new_dates(con, path, table, column, dates):
    seen = sorted({d for (d,) in con.execute(f"SELECT DISTINCT {column} FROM {table}")} & set(dates))
    if seen:
        raise LoadError(f"{path.name}: data for {', '.join(seen[:3])} is already loaded. "
                        "Not loaded twice.")


def num(s):  # accepts "28,46" (Sage) and "28.46" (Shopify)
    return float(str(s).replace(",", ".")) if s not in (None, "") else None


def log(con, file, table, n):
    con.execute("INSERT INTO load_log(file, table_name, rows) VALUES (?,?,?)", (file, table, n))


def load_sage_sales(con, path):
    rs = read_csv(path, ";", ("Data", "Loja", "Artigo", "Quantidade", "Valor liquido", "Moeda"))
    check_known_skus(con, path, [r["Artigo"] for r in rs])
    check_new_dates(con, path, "store_sales", "sale_date", [r["Data"] for r in rs])
    data = [(r["Data"], r["Loja"], r["Artigo"], int(r["Quantidade"]), num(r["Valor liquido"]), r["Moeda"],
             path.name) for r in rs]
    con.executemany("INSERT INTO store_sales VALUES (?,?,?,?,?,?,?)", data)
    log(con, path.name, "store_sales", len(data))
    return len(data)


def load_sage_stock(con, path):
    rs = read_csv(path, ";", ("Data", "Armazem", "Artigo", "Quantidade"))
    check_known_skus(con, path, [r["Artigo"] for r in rs])
    check_new_dates(con, path, "stock_sage", "snapshot_date", [r["Data"] for r in rs])
    data = [(r["Data"], r["Armazem"], r["Artigo"], int(r["Quantidade"]), path.name) for r in rs]
    con.executemany("INSERT INTO stock_sage VALUES (?,?,?,?,?)", data)
    log(con, path.name, "stock_sage", len(data))
    return len(data)


def load_inbox_file(con, path):
    """Files from the 'nightly Sage export' (see mock_systems/store_day.py)."""
    if path.name.startswith("sage_vendas_"):
        return load_sage_sales(con, path)
    if path.name.startswith("sage_stock_"):
        return load_sage_stock(con, path)
    return 0


def build():
    """Build into a temporary file; replace the real database only if everything loaded."""
    DB.parent.mkdir(exist_ok=True)
    if TMP.exists():
        TMP.unlink()
    con = sqlite3.connect(TMP)
    try:
        fill(con)
        con.commit()
        summary(con)
    except BaseException:
        con.close()
        TMP.unlink()
        raise
    con.close()
    os.replace(TMP, DB)
    print(f"\nDatabase ready: {DB.relative_to(ROOT)}")
    if pg.database_url():  # instructor only: also publish the shared copy (see pg.py)
        try:
            pg.publish(DB)
        except Exception as e:  # e.g. wrong password, no internet: the local build is still fine
            sys.exit(f"\nThe local database is ready, but the shared copy was NOT updated ({e}).\n"
                     "Check DATABASE_URL in .env and the internet connection, then run load.py again.")


def fill(con):
    con.executescript(SCHEMA)

    con.executemany("INSERT INTO locations VALUES (?,?,?,?,?)",
                    [tuple(r.values()) for r in rows("locations.csv")])
    con.executemany("INSERT INTO suppliers VALUES (?,?,?,?)",
                    [(r["Supplier"], r["Name"], r["Country"], int(r["Lead time (weeks)"])) for r in rows("suppliers.csv", required=("Supplier", "Name", "Country", "Lead time (weeks)"))])
    prod = rows("notion_products.csv", required=("Style code", "Name", "Handle", "Category", "Collection",
                "Supplier", "Fabric", "Unit cost (EUR)", "Price EUR", "Price USD", "Price GBP", "Launch date", "Status"))
    con.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(r["Style code"], r["Name"], r["Handle"], r["Category"], r["Collection"], r["Supplier"],
                      r["Fabric"], num(r["Unit cost (EUR)"]), num(r["Price EUR"]), num(r["Price USD"]),
                      num(r["Price GBP"]), r["Launch date"], r["Status"]) for r in prod])
    arts = rows("sage_artigos.csv", ";", ("Artigo", "Descricao", "Tamanho", "Cor", "Familia"))
    con.executemany("INSERT INTO variants VALUES (?,?,?,?,?,?)",
                    [(r["Artigo"], r["Artigo"].split("-")[0], r["Descricao"], r["Tamanho"], r["Cor"], r["Familia"])
                     for r in arts])
    name_to_sku = {r["Descricao"]: r["Artigo"] for r in arts}

    load_sage_sales(con, RAW / "sage_store_sales.csv")
    load_sage_stock(con, RAW / "sage_stock_by_location.csv")

    orders = rows("shopify_orders.csv", required=("Name", "Created at", "Currency", "Lineitem sku",
                  "Lineitem name", "Lineitem quantity", "Lineitem price", "Shipping Country"))
    con.executemany("INSERT INTO online_orders VALUES (?,?,?,?,?,?,?,?,?)",
                    [(r["Name"], r["Created at"], r["Created at"][:10], r["Currency"],
                      r["Lineitem sku"] or name_to_sku.get(r["Lineitem name"]), r["Lineitem name"],
                      int(r["Lineitem quantity"]), num(r["Lineitem price"]), r["Shipping Country"]) for r in orders])
    log(con, "shopify_orders.csv", "online_orders", len(orders))
    rets = rows("shopify_returns.csv", required=("Return", "Order", "Returned at", "Lineitem name", "Quantity", "Status"))
    con.executemany("INSERT INTO online_returns VALUES (?,?,?,?,?,?)",
                    [(r["Return"], r["Order"], r["Returned at"], name_to_sku.get(r["Lineitem name"]),
                      int(r["Quantity"]), r["Status"]) for r in rets])
    log(con, "shopify_returns.csv", "online_returns", len(rets))

    con.executemany("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?,?)",
                    [(r["Encomenda"], r["Fornecedor"], r["Data encomenda"], r["Data prevista"], r["Artigo"],
                      int(r["Quantidade"]), num(r["Custo unitario"]), r["Estado"])
                     for r in rows("sage_purchase_orders.csv", ";", ("Encomenda", "Fornecedor", "Data encomenda",
                                     "Data prevista", "Artigo", "Quantidade", "Custo unitario", "Estado"))])
    con.executemany("INSERT INTO production_plan VALUES (?,?,?,?,?,?,?)",
                    [(r["Season"], r["Style code"], r["Style"], r["Supplier"], int(r["Planned units"]),
                      int(r["Produced to date"]), r["First delivery"])
                     for r in rows("production_plan.csv", required=("Season", "Style code", "Style", "Supplier",
                                   "Planned units", "Produced to date", "First delivery"))])
    con.executemany("INSERT INTO fx_rates VALUES (?,?)", [("EUR", 1.0), ("USD", 1.15), ("GBP", 0.86)])

    # Shopify stock: the most recent pull (live pull if present, else the snapshot taken 2026-09-30)
    live = RAW / "shopify_stock_live.json"
    src = live if live.exists() else RAW / "mockshop_snapshot.json"
    pulled_at = json.load(open(live))["pulled_at"] if live.exists() else "2026-09-30"
    products = json.load(open(live))["products"] if live.exists() else json.load(open(src))
    id_to_sku = shopify_ids_to_sku(arts, products)
    stock = []
    for p in products:
        for e in p["variants"]["edges"]:
            v = e["node"]
            stock.append((pulled_at, p["handle"], v["id"], id_to_sku.get((p["handle"], v["id"])), None,
                          v.get("quantityAvailable") or 0))
    con.executemany("INSERT INTO shopify_stock VALUES (?,?,?,?,?,?)", stock)
    con.execute("UPDATE shopify_stock SET shopify_name = (SELECT shopify_name FROM variants v WHERE v.sku = shopify_stock.sku)")
    log(con, src.name, "shopify_stock", len(stock))

    if PROCESSED.exists():
        for path in sorted(PROCESSED.glob("*.csv")):
            load_inbox_file(con, path)

    check_matched(con)


def check_matched(con):
    """Shopify has no SKUs, so its lines are matched to Sage articles by name. A renamed
    product would silently drop out of every total, so stop instead."""
    for table, label, file in (("online_orders", "shopify_name", "shopify_orders.csv"),
                               ("online_returns", "return_id", "shopify_returns.csv")):
        names = [n for (n,) in con.execute(f"SELECT DISTINCT {label} FROM {table} WHERE sku IS NULL")]
        if names:
            raise LoadError(f"{file}: {len(names)} line(s) match no product in sage_artigos.csv, "
                            f"e.g. {', '.join(map(str, names[:5]))}. A product was probably renamed.")
    check_known_skus(con, RAW / "sage_purchase_orders.csv",
                     [s for (s,) in con.execute("SELECT DISTINCT sku FROM purchase_orders")])
    n = con.execute("SELECT COUNT(*) FROM shopify_stock WHERE sku IS NULL").fetchone()[0]
    if n:  # mock.shop is a shared demo store: new products there are expected, so warn only
        print(f"Note: {n} Shopify stock line(s) match no Sage article and are left out of the comparison.\n")


def summary(con):
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        print(f"{t:18} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>7} rows")
    sale, order, stock, pull = con.execute(
        "SELECT (SELECT MAX(sale_date) FROM store_sales), (SELECT MAX(sale_date) FROM online_orders),"
        " (SELECT MAX(snapshot_date) FROM stock_sage), (SELECT MAX(pulled_at) FROM shopify_stock)").fetchone()
    print(f"\nData as of: store sales {sale} · online orders {order} · Sage stock {stock} · Shopify stock {pull}")


def run():
    """Build, and on a problem print one plain sentence instead of a Python error."""
    try:
        build()
    except LoadError as e:
        sys.exit(f"\nNOT LOADED. {e}\nThe previous database is unchanged. Fix the file (or put back the "
                 "original export) and run load.py again.")
    except (ValueError, KeyError) as e:
        sys.exit(f"\nNOT LOADED. A value in one of the files could not be read ({e}).\n"
                 "The previous database is unchanged.")


def shopify_ids_to_sku(arts, products):
    """Shopify has no SKUs here, so match Shopify variants to Sage articles by name.
    Keyed by (product handle, variant id): mock.shop reuses the same variant ids in two products."""
    name_to_sku = {r["Descricao"]: r["Artigo"] for r in arts}
    out = {}
    for p in products:
        for e in p["variants"]["edges"]:
            v = e["node"]
            title = v["title"]
            opts = v.get("selectedOptions") or []
            color = next((o["value"] for o in opts if o["name"] == "Color"), None)
            if color and color not in title:
                title = " / ".join(o["value"] for o in opts)
            out[(p["handle"], v["id"])] = name_to_sku.get(f'{p["title"]} - {title}')
    return out


if __name__ == "__main__":
    run()
