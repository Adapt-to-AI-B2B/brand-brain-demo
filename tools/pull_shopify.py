"""Pull the catalog and live stock from Shopify (Shopify's public demo store, mock.shop)
and reload the database.

    python3 tools/pull_shopify.py      (Mac)
    python tools/pull_shopify.py       (Windows)

Writes data/raw/shopify_stock_live.json, then rebuilds data/warehouse.sqlite.
Note: mock.shop is a shared demo store, so its stock can move a little over time.
Standard library only; no key needed.
"""
import json, sys, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import load  # noqa: E402

QUERY = """query($c:String){ products(first:100, after:$c){ pageInfo{hasNextPage endCursor}
 edges{ node{ id title handle variants(first:50){ edges{ node{ id title quantityAvailable
 price{amount currencyCode} selectedOptions{name value} } } } } } } }"""


def pull():
    products, cursor = [], None
    while True:
        req = urllib.request.Request("https://mock.shop/api",
                                     data=json.dumps({"query": QUERY, "variables": {"c": cursor}}).encode(),
                                     headers={"Content-Type": "application/json"})
        data = json.load(urllib.request.urlopen(req, timeout=30))["data"]["products"]
        products += [e["node"] for e in data["edges"]]
        if not data["pageInfo"]["hasNextPage"]:
            return products
        cursor = data["pageInfo"]["endCursor"]


if __name__ == "__main__":
    try:
        products = pull()
    except Exception as e:  # network down in class: keep the snapshot
        print(f"Could not reach mock.shop ({e}). The database keeps the 2026-09-30 snapshot.")
        sys.exit(1)
    out = {"pulled_at": datetime.now().isoformat(timespec="seconds"), "products": products}
    (ROOT / "data" / "raw" / "shopify_stock_live.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    n = sum(len(p["variants"]["edges"]) for p in products)
    print(f"Pulled {len(products)} products, {n} variants from Shopify at {out['pulled_at']}.\n")
    load.run()
