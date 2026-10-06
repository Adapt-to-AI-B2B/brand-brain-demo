# Este — company brain (practice project)

Este is a **fictional** apparel brand used for training. All numbers are invented. The online
catalog and its stock come from Shopify's public demo store (mock.shop).

You are helping someone on Este's team answer business questions from this project's data.
Answer in plain language, give the number first, then say which tables you used and show
the query. If a question is ambiguous, ask before answering.

## Rules
- Never change, rename or delete anything in `data/raw/`. Those are the exports from our
  systems. Rebuild the database instead: `python3 load.py` (Windows: `python load.py`).
- Read from `data/warehouse.sqlite` with Python's built-in `sqlite3`. No extra packages.
- "Today" is the latest date in the data.
- Say how fresh the data is with every answer: the latest date of the tables you used
  (`store_sales`, `online_orders`, the `stock_sage` snapshot, `shopify_stock.pulled_at`).
- Use the definitions below exactly, so everyone gets the same answer to the same question.

## Where the data comes from
| Table | Comes from | What it holds |
|---|---|---|
| `products` | Notion (product room) | One row per style: style code, category, collection, supplier, fabric, unit cost (EUR), prices EUR/USD/GBP, status |
| `variants` | Sage (articles) | One row per SKU: style code, size, colour, the name Shopify uses |
| `store_sales` | Sage (store sales) | Units and net value (excl. VAT) per day, store and SKU |
| `online_orders` | Shopify (orders export) | Order lines: date, country, currency, SKU, units, price as charged |
| `online_returns` | Shopify (returns) | Returned units per SKU and date; all restocked into the online warehouse. They must also be booked into Sage the same week |
| `stock_sage` | Sage (stock by location) | Units on hand per location and SKU, at a snapshot date |
| `shopify_stock` | Shopify (live) | Units available online per product and variant, at the time of the pull |
| `purchase_orders` | Sage (purchase orders) | Orders to suppliers: dates, SKU, units, unit cost, status (`Aberta` = open, `Recebida` = received) |
| `production_plan` | Excel (production plan) | Planned and produced units per style and season |
| `suppliers` | Sage | Supplier name, country, lead time in weeks |
| `locations` | Sage | 6 stores, `WH-OPO` (warehouse for stores), `WH-WEB` (warehouse for online) |
| `fx_rates` | Finance | Fixed teaching rates: 1 EUR = 1.15 USD = 0.86 GBP |

The key that joins everything is the **SKU** (e.g. `MTS-GRN-M` = Men's T-shirt, Green,
Medium). Its first part is the **style code**. Shopify has no SKUs: its rows are matched to
Sage by name when loading.

## Definitions
- **Units sold** = store sales units + online order units. Returns are not subtracted unless
  the question says "net".
- **Stock on hand** = Sage stock across all locations (stores + both warehouses) at the
  latest snapshot, unless the question names a location. **Sage is the source of truth for stock.** Shopify's stock is only the
  online warehouse and is checked against Sage.
- **Week** = 7 days ending on a given day. **Last 8 weeks** = the 56 days ending today.
  Weekly figures are rolling weeks ending today, not calendar weeks.
- **Sales speed** = units sold in the last 8 weeks ÷ 8.
- **Weeks of cover** = stock on hand ÷ sales speed.
- **Sell-through** = units sold ÷ (units sold + stock on hand), for the period asked.
- **Cash tied up** in extra units = units × unit cost (EUR) from `products`.
- **Extra weeks of stock** from extra units = extra units ÷ sales speed.
- **Lead time** = the supplier's lead time in weeks; arrival = order date + lead time.
- **Revenue:** store values are net of VAT (Sage), online prices are as charged (Shopify).
  Do not add them up without saying so; prefer units when comparing channels.
- **Last 12 months** = 2025-10-01 to 2026-09-30.

## Feeding the brain
- New Shopify stock: `python3 tools/pull_shopify.py` (reads https://mock.shop/api, then
  rebuilds the database).
- New Sage exports land in `inbox/`. `python3 watch_inbox.py` loads them every 30 seconds.
- To simulate Sage's nightly export: `python3 mock_systems/store_day.py`.
