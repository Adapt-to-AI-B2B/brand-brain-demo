"""Generate the Este mock data (reproducible, seed 42).

Este is a FICTIONAL apparel brand used for teaching. Every number here is invented.
The online catalog is Shopify's public demo store (mock.shop): its products and live stock
are read from data/raw/mockshop_snapshot.json (taken from https://mock.shop/api).

Run from the repo root:  python3 tools/generate.py
Writes the "exports" in data/raw/ and the answer-key facts in answers/facts.json.
Standard library only.
"""
import csv, json, math, random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
R = random.Random(42)

START, END = date(2025, 10, 1), date(2026, 9, 30)
DAYS = [(START + timedelta(d)) for d in range((END - START).days + 1)]
SNAPSHOT_DATE = END

FX = {"EUR": 1.0, "USD": 1.15, "GBP": 0.86}  # 1 EUR = x currency (fixed teaching rates)

LOCATIONS = [  # id, name, type, city, currency, weight of store sales
    ("LIS1", "Lisboa Chiado", "store", "Lisboa", "EUR", 1.4),
    ("LIS2", "Lisboa Principe Real", "store", "Lisboa", "EUR", 1.0),
    ("OPO1", "Porto Baixa", "store", "Porto", "EUR", 1.2),
    ("OPO2", "Porto Foz", "store", "Porto", "EUR", 0.7),
    ("MAD1", "Madrid Salamanca", "store", "Madrid", "EUR", 0.9),
    ("LON1", "London Shoreditch", "store", "London", "GBP", 0.8),
    ("WH-OPO", "Warehouse Porto (stores)", "warehouse", "Porto", "EUR", 0),
    ("WH-WEB", "Warehouse Online", "warehouse", "Maia", "EUR", 0),
]
STORES = [l for l in LOCATIONS if l[2] == "store"]

SUPPLIERS = [  # id, name, country, lead_time_weeks
    ("SUP01", "Fiação do Ave", "PT", 8), ("SUP02", "Malhas Barcelos", "PT", 8),
    ("SUP03", "Confeções Guimarães", "PT", 7), ("SUP04", "Têxteis Famalicão", "PT", 8),
    ("SUP05", "Tricot Felgueiras", "PT", 9), ("SUP06", "Calçado São João", "PT", 10),
    ("SUP07", "Algodão Vizela", "PT", 8), ("SUP08", "Atelier Covilhã", "PT", 9),
    ("SUP09", "Manufacturas Elche", "ES", 10), ("SUP10", "Punto Mataró", "ES", 8),
    ("SUP11", "Tessitura Biella", "IT", 9), ("SUP12", "Maglificio Carpi", "IT", 8),
    ("SUP13", "Izmir Cotton", "TR", 7), ("SUP14", "Bursa Knit", "TR", 6),
    ("SUP15", "Porto Packaging", "PT", 4), ("SUP16", "Lã Serra da Estrela", "PT", 10),
    ("SUP17", "Óculos Braga", "PT", 9), ("SUP18", "Mochilas Ovar", "PT", 8),
    ("SUP19", "Down Works Valencia", "ES", 10), ("SUP20", "Estampados Trofa", "PT", 6),
]

COLOR_CODE = {"Green": "GRN", "Olive": "OLV", "Ocean": "OCN", "Purple": "PRP", "Red": "RED",
              "Clay": "CLY", "Black": "BLK", "White": "WHT", "Gray": "GRY", "Grey": "GRY",
              "Navy": "NVY", "Blue": "BLU"}
SIZE_CODE = {"Small": "S", "Medium": "M", "Large": "L", "X-Large": "XL", "XX-Large": "XXL"}

# style rules by keyword: (category, price_eur, cost_ratio, fabric, demand weight, season curve)
RULES = [
    ("T-shirt", "Tops", 35, 0.30, "Organic cotton jersey 180g", 3.0, "summer"),
    ("Workout Shirt", "Tops", 45, 0.32, "Recycled polyester", 1.0, "summer"),
    ("Crewneck", "Tops", 75, 0.33, "Brushed cotton fleece", 1.4, "winter"),
    ("Half Zip", "Tops", 85, 0.34, "Merino blend", 0.8, "winter"),
    ("Hoodie", "Tops", 89, 0.33, "Cotton fleece 380g", 1.6, "winter"),
    ("Puffer", "Tops", 189, 0.38, "Recycled nylon, synthetic down", 0.7, "deepwinter"),
    ("Sweatpants", "Bottoms", 79, 0.33, "Cotton fleece 380g", 1.2, "winter"),
    ("Leggings", "Bottoms", 59, 0.30, "Recycled nylon stretch", 0.9, "flat"),
    ("Shorts", "Bottoms", 49, 0.30, "Cotton twill", 0.9, "summer"),
    ("Sneakers", "Shoes", 129, 0.40, "Canvas / leather", 0.6, "flat"),
    ("Runners", "Shoes", 139, 0.40, "Knit upper, EVA sole", 0.5, "flat"),
    ("Slides", "Shoes", 39, 0.35, "EVA", 0.6, "summer"),
    ("Sunnies", "Accessories", 69, 0.30, "Acetate", 0.6, "summer"),
    ("Beanie", "Accessories", 29, 0.30, "Wool blend", 0.8, "deepwinter"),
    ("Frontpack", "Accessories", 55, 0.35, "Recycled nylon", 0.5, "flat"),
]
COLLECTION_BY_CURVE = {"summer": "SS26", "winter": "AW25", "deepwinter": "AW25", "flat": "Core"}


def season_factor(curve, d):
    m = d.month
    if curve == "summer":
        return [0.6, 0.6, 0.8, 1.0, 1.3, 1.6, 1.8, 1.7, 1.2, 0.8, 0.6, 0.6][m - 1]
    if curve == "winter":
        return [1.5, 1.3, 1.0, 0.8, 0.6, 0.5, 0.4, 0.5, 0.9, 1.2, 1.5, 1.8][m - 1]
    if curve == "deepwinter":
        return [1.8, 1.4, 0.8, 0.4, 0.2, 0.1, 0.1, 0.2, 0.6, 1.1, 1.7, 2.2][m - 1]
    return 1.0


def weekday_factor(d):
    return [0.8, 0.85, 0.9, 1.0, 1.2, 1.5, 0.75][d.weekday()]


def poisson(lam):
    if lam <= 0:
        return 0
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= R.random()
        if p <= L:
            return k
        k += 1


def write_csv(path, header, rows, delimiter=","):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(header)
        w.writerows(rows)


def pt_num(x):  # Sage Portugal export style: decimal comma
    return f"{x:.2f}".replace(".", ",")


def main():
    snap = json.load(open(RAW / "mockshop_snapshot.json", encoding="utf-8"))

    # ---- styles and variants -------------------------------------------------------------
    styles, variants, used_codes = [], [], set()
    for i, p in enumerate(snap):
        rule = next((r for r in RULES if r[0].lower() in p["title"].lower()), RULES[0])
        cat, price, ratio, fabric, weight, curve = rule[1:]
        coll = COLLECTION_BY_CURVE[curve]
        if p["handle"] in ("mens-crewneck", "womens-t-shirt", "light-puffer"):
            coll = "AW26"  # launched in September 2026
        if "Men's T-shirt" == p["title"]:
            coll = "Core"  # the white-t-shirt equivalent: always on sale
        words = p["handle"].upper().split("-")
        base = words[0][:3] if len(words) == 1 else ("".join(w[0] for w in words) + words[-1][1:])[:3]
        code, n = base, 0
        while code in used_codes:
            code = base[:2] + str(n + 2)
            n += 1
        used_codes.add(code)
        supplier = SUPPLIERS[i % 18][0] if cat != "Shoes" else "SUP06"
        if p["title"] == "Men's T-shirt":
            supplier = "SUP07"
        launch = {"AW25": "2025-09-15", "SS26": "2026-03-02", "AW26": "2026-09-01", "Core": "2024-02-01"}[coll]
        styles.append(dict(handle=p["handle"], title=p["title"], code=code, category=cat, collection=coll,
                           supplier=supplier, fabric=fabric, cost=round(price * ratio, 2), price=price,
                           launch=launch, weight=weight, curve=curve))
        for e in p["variants"]["edges"]:
            v = e["node"]
            opts = {o["name"]: o["value"] for o in v["selectedOptions"]}
            size = opts.get("Size", "OS")
            color = opts.get("Color", "Black")
            sku = f"{code}-{COLOR_CODE.get(color, color[:3].upper())}-{SIZE_CODE.get(size, size)}"
            vtitle = v["title"]
            if "Color" in opts and opts["Color"] not in vtitle:  # mock.shop "hoodie": colour missing
                vtitle = " / ".join(o["value"] for o in v["selectedOptions"])
            variants.append(dict(sku=sku, handle=p["handle"], size=size, color=color,
                                 shopify_id=v["id"], shopify_name=f'{p["title"]} - {vtitle}',
                                 shopify_qty=v["quantityAvailable"] or 0, style=styles[-1]))

    # ---- demand per variant ---------------------------------------------------------------
    size_w = {"Small": 0.8, "Medium": 1.3, "Large": 1.1, "X-Large": 0.6}
    color_w = {"Green": 0.7, "Olive": 1.0, "Ocean": 1.0, "Purple": 0.6, "Red": 0.8, "Clay": 1.0}
    for v in variants:
        v["base"] = v["style"]["weight"] * size_w.get(v["size"], 1.0) * color_w.get(v["color"], 0.9)

    def active(v, d):
        st = v["style"]
        if st["collection"] == "AW25":
            return d <= date(2026, 3, 31)
        if st["collection"] == "SS26":
            return d >= date(2026, 3, 2)
        if st["collection"] == "AW26":
            return d >= date(2026, 9, 1)
        return True

    # ---- store sales (Sage) ---------------------------------------------------------------
    store_rows = []
    sold_store = {}
    for d in DAYS:
        for loc in STORES:
            for v in variants:
                if not active(v, d):
                    continue
                lam = 0.055 * v["base"] * loc[5] * season_factor(v["style"]["curve"], d) * weekday_factor(d)
                q = poisson(lam)
                if q:
                    price = v["style"]["price"] * (FX[loc[4]] if loc[4] != "EUR" else 1)
                    if v["style"]["collection"] in ("AW25",) and d >= date(2026, 1, 8):
                        price *= 0.7  # winter sale
                    net = round(q * price / 1.23, 2) if loc[4] == "EUR" else round(q * price / 1.2, 2)
                    store_rows.append([d.isoformat(), loc[0], v["sku"], q, pt_num(net), loc[4]])
                    sold_store[v["sku"]] = sold_store.get(v["sku"], 0) + q
    write_csv(RAW / "sage_store_sales.csv",
              ["Data", "Loja", "Artigo", "Quantidade", "Valor liquido", "Moeda"], store_rows, ";")

    # ---- online orders (Shopify export) --------------------------------------------------
    order_rows, returns_rows, n_order = [], [], 1000
    countries = [("PT", "EUR", 0.38), ("ES", "EUR", 0.17), ("FR", "EUR", 0.1), ("DE", "EUR", 0.05),
                 ("US", "USD", 0.15), ("GB", "GBP", 0.15)]
    online_lines = {}
    weights = [v["base"] for v in variants]
    country_w = [x[2] for x in countries]
    for d in DAYS:
        day_cum = list(__import__("itertools").accumulate(
            w * season_factor(x["style"]["curve"], d) * (1 if active(x, d) else 0)
            for w, x in zip(weights, variants)))
        n = poisson(38 * weekday_factor(d) * (1.6 if d.month in (11, 12) else 1.0))
        for _ in range(n):
            n_order += 1
            c = R.choices(countries, country_w)[0]
            for _ in range(R.choice([1, 1, 1, 2, 2, 3])):
                v = R.choices(variants, cum_weights=day_cum)[0]
                q = 1 if R.random() < 0.9 else 2
                price = round(v["style"]["price"] * FX[c[1]], 2)
                order_rows.append([f"#E{n_order}", f"{d.isoformat()} {R.randint(8, 23):02d}:{R.randint(0, 59):02d}",
                                   c[1], q, f"{price:.2f}", v["shopify_name"], "", c[0]])
                online_lines[v["sku"]] = online_lines.get(v["sku"], 0) + q
                if R.random() < 0.08:
                    rd = d + timedelta(R.randint(6, 20))
                    if rd <= END:
                        returns_rows.append([f"R{len(returns_rows) + 5001}", f"#E{n_order}", rd.isoformat(),
                                             v["shopify_name"], q, "restocked"])
    # force the deliberate mismatch: returns of one variant not booked in Sage
    target = next(v for v in variants if v["shopify_name"] == "Men's T-shirt - Medium / Green")
    unbooked = [r for r in returns_rows if r[3] == target["shopify_name"] and r[2] >= "2026-08-01"]
    while sum(r[4] for r in unbooked) < 7:
        rd = date(2026, 8, 1) + timedelta(R.randint(0, 58))
        r = [f"R{len(returns_rows) + 5001}", f"#E{R.randint(20000, 21000)}", rd.isoformat(),
             target["shopify_name"], 1, "restocked"]
        returns_rows.append(r)
        unbooked.append(r)
    unbooked_qty = sum(r[4] for r in unbooked)
    returns_rows.sort(key=lambda r: r[2])
    write_csv(RAW / "shopify_orders.csv",
              ["Name", "Created at", "Currency", "Lineitem quantity", "Lineitem price", "Lineitem name",
               "Lineitem sku", "Shipping Country"], order_rows)
    write_csv(RAW / "shopify_returns.csv",
              ["Return", "Order", "Returned at", "Lineitem name", "Quantity", "Status"], returns_rows)

    # ---- SKU list (Sage article master, PT headers) -------------------------------------
    write_csv(RAW / "sage_artigos.csv", ["Artigo", "Descricao", "Tamanho", "Cor", "Familia"],
              [[v["sku"], v["shopify_name"], v["size"], v["color"], v["style"]["category"]] for v in variants], ";")

    # ---- stock snapshot (Sage), 2026-09-30 ----------------------------------------------
    stock_rows = []
    for v in variants:
        weekly = (sold_store.get(v["sku"], 0) / 52) or 0.2
        alive = active(v, END)
        for loc in STORES:
            share = loc[5] / sum(s[5] for s in STORES)
            cover = R.uniform(1, 9) if alive else R.uniform(0, 2)
            q = max(0, round(weekly * share * cover))
            if R.random() < 0.06:
                q = 0  # stockouts
            stock_rows.append([SNAPSHOT_DATE.isoformat(), loc[0], v["sku"], q])
        wh = round(weekly * R.uniform(3, 14)) if alive else round(weekly * R.uniform(4, 20))  # some overstock
        stock_rows.append([SNAPSHOT_DATE.isoformat(), "WH-OPO", v["sku"], wh])
        web = v["shopify_qty"] - (unbooked_qty if v is target else 0)
        stock_rows.append([SNAPSHOT_DATE.isoformat(), "WH-WEB", v["sku"], max(0, web)])
    write_csv(RAW / "sage_stock_by_location.csv", ["Data", "Armazem", "Artigo", "Quantidade"], stock_rows, ";")

    # ---- purchase orders (Sage) -----------------------------------------------------------
    po_rows, po_n = [], 300
    for st in styles:
        sup = next(s for s in SUPPLIERS if s[0] == st["supplier"])
        for k in range(R.randint(2, 4)):
            po_n += 1
            od = START + timedelta(R.randint(0, 330))
            exp = od + timedelta(weeks=sup[3])
            status = "Recebida" if exp <= END else "Aberta"
            for v in [x for x in variants if x["handle"] == st["handle"]]:
                q = max(5, round(v["base"] * R.uniform(20, 60)))
                po_rows.append([f"EC{po_n}", sup[0], od.isoformat(), exp.isoformat(), v["sku"], q,
                                pt_num(st["cost"]), status])
    write_csv(RAW / "sage_purchase_orders.csv",
              ["Encomenda", "Fornecedor", "Data encomenda", "Data prevista", "Artigo", "Quantidade",
               "Custo unitario", "Estado"], po_rows, ";")

    # ---- production plan (Excel export) ---------------------------------------------------
    plan_rows = []
    for st in styles:
        yearly = sum(sold_store.get(v["sku"], 0) + online_lines.get(v["sku"], 0)
                     for v in variants if v["handle"] == st["handle"])
        for season in ("AW26", "SS27"):
            planned = round(max(200, yearly * R.uniform(0.45, 0.6)), -1)
            if st["title"] == "Men's T-shirt" and season == "AW26":
                planned = 7000
            produced = round(planned * (0.4 if season == "AW26" else 0.0))
            plan_rows.append([season, st["code"], st["title"], st["supplier"], int(planned), int(produced),
                              "2026-08-15" if season == "AW26" else "2027-01-20"])
    write_csv(RAW / "production_plan.csv",
              ["Season", "Style code", "Style", "Supplier", "Planned units", "Produced to date",
               "First delivery"], plan_rows)

    # ---- product room (Notion export) -----------------------------------------------------
    write_csv(RAW / "notion_products.csv",
              ["Name", "Handle", "Style code", "Category", "Collection", "Supplier", "Fabric",
               "Unit cost (EUR)", "Price EUR", "Price USD", "Price GBP", "Launch date", "Status"],
              [[s["title"], s["handle"], s["code"], s["category"], s["collection"], s["supplier"], s["fabric"],
                f'{s["cost"]:.2f}', s["price"], round(s["price"] * FX["USD"]), round(s["price"] * FX["GBP"]),
                s["launch"], "Discontinued" if s["collection"] == "AW25" else "Active"] for s in styles])
    write_csv(RAW / "suppliers.csv", ["Supplier", "Name", "Country", "Lead time (weeks)"], SUPPLIERS)
    write_csv(RAW / "locations.csv", ["Location", "Name", "Type", "City", "Currency"],
              [l[:5] for l in LOCATIONS])

    facts = dict(mismatch_sku=target["sku"], mismatch_shopify_name=target["shopify_name"],
                 mismatch_unbooked_returns=unbooked_qty, generated_until=END.isoformat(),
                 n_variants=len(variants), n_styles=len(styles), n_store_rows=len(store_rows),
                 n_order_lines=len(order_rows), n_returns=len(returns_rows))
    (ROOT / "answers").mkdir(exist_ok=True)
    json.dump(facts, open(ROOT / "answers" / "facts.json", "w"), indent=2)
    print(json.dumps(facts, indent=2))


if __name__ == "__main__":
    main()
