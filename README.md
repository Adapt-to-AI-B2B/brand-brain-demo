# Este — company brain (practice project)

A ready-made "company brain" for learning Claude Code. **Este is a fictional apparel brand**:
every number here is invented. The online catalog comes from Shopify's public demo store
(mock.shop).

## Get it
1. On this page, click the green **Code** button → **Download ZIP**.
2. Unzip it into the projects folder of your Claude Code workspace.
3. Open the folder in VS Code.

That's all for now. **Don't start asking questions yet**: we'll do that together in the live
session.

## What's inside
| Folder / file | What it is |
|---|---|
| `data/raw/` | Exports from Este's systems: Shopify, Sage, Notion, the production-plan spreadsheet |
| `data/warehouse.sqlite` | All of it in one database, ready to ask questions of |
| `CLAUDE.md` | What Claude reads first: where each number comes from, and what the words mean |
| `questions.md` | 25 questions to try in class |
| `load.py` | Rebuilds the database from the exports |
| `tools/pull_shopify.py` | Pulls live stock from Shopify |
| `mock_systems/store_day.py` | Pretends to be Sage sending its nightly export |
| `watch_inbox.py` | The scheduled job that loads new exports |

Needs Python 3 (no extra packages). Check: `python3 --version` (Mac) or `python --version`
(Windows).
