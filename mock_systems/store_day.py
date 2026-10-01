"""Pretend to be Sage: drop "the nightly export" of one day of store sales into inbox/.

    python3 mock_systems/store_day.py              one new day
    python3 mock_systems/store_day.py --every 20   a new day every 20 seconds (Ctrl+C to stop)

Each file is named sage_vendas_<date>.csv, in the same format as data/raw/sage_store_sales.csv.
Days continue after the latest date already in the data. Standard library only.
"""
import csv, random, sqlite3, sys, time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
DB = ROOT / "data" / "warehouse.sqlite"


def next_day():
    days = [date.fromisoformat(p.stem.split("_")[-1]) for p in INBOX.rglob("sage_vendas_*.csv")]
    if DB.exists():
        con = sqlite3.connect(DB)
        last = con.execute("SELECT MAX(sale_date) FROM store_sales").fetchone()[0]
        con.close()
        if last:
            days.append(date.fromisoformat(last))
    return (max(days) if days else date(2026, 9, 30)) + timedelta(1)


def make_day():
    con = sqlite3.connect(DB)
    skus = [r for r in con.execute(
        "SELECT v.sku, p.price_eur FROM variants v JOIN products p ON p.style_code = v.style_code "
        "WHERE p.status = 'Active'")]
    stores = [r[0] for r in con.execute("SELECT location_id FROM locations WHERE type = 'store'")]
    con.close()
    d = next_day()
    rnd = random.Random(d.toordinal())
    rows = []
    for store in stores:
        for sku, price in rnd.sample(skus, rnd.randint(25, 45)):
            q = rnd.choice([1, 1, 1, 2])
            cur = "GBP" if store == "LON1" else "EUR"
            net = q * price * (0.86 if cur == "GBP" else 1) / (1.2 if cur == "GBP" else 1.23)
            rows.append([d.isoformat(), store, sku, q, f"{net:.2f}".replace(".", ","), cur])
    INBOX.mkdir(exist_ok=True)
    path = INBOX / f"sage_vendas_{d.isoformat()}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Data", "Loja", "Artigo", "Quantidade", "Valor liquido", "Moeda"])
        w.writerows(rows)
    print(f"Sage export written: inbox/{path.name} ({sum(r[3] for r in rows)} units, {len(rows)} lines)")


if __name__ == "__main__":
    if "--every" in sys.argv:
        secs = int(sys.argv[sys.argv.index("--every") + 1])
        try:
            while True:
                make_day()
                time.sleep(secs)
        except KeyboardInterrupt:
            print("Stopped.")
    else:
        make_day()
