# AI agent guide for wallet.py

Flask app to ingest B3/Avenue/Generic extracts, store in SQLite via SQLAlchemy, transform with pandas, and visualize with Plotly.

## Architecture
- Entry: `wallet.py` boots app (creates tables + runs debug).
- App init: `app/__init__.py` configures `sqlite:///wallet.db`, logging, and `uploads/`.
- Routes/UI: `app/routes.py` — upload (`/`) -> `importing.py`; views: `/b3_movimentation`, `/b3_negotiation`, `/avenue`, `/generic`, `/consolidate`, `/view/<source>/<asset>`, `/history/<source>/<asset>`.
- Import: `app/importing.py` cleans DataFrames and inserts with dedupe key `origin_id=f"{filepath}:{sha256}:{row}"`.
- ORM + mappers: `app/models.py` defines tables and `*_sql_to_df` mappers that convert SQL rows to normalized DataFrames.
- Analytics: `app/processing.py` builds per-asset `asset_info` + `dataframes` and computes avg price, realized/not-realized gain, rentability; pulls quotes via `yfinance` and FX via `utils/scraping.py`.
- Utils: `app/utils/parsing.py` (ticker/BRL parsing), `app/utils/scraping.py` (requests_cache, FX, yfinance helpers).

## Conventions
- Canonical DataFrame columns used downstream: `Date`, `Asset`, `Movimentation`, `Quantity`, `Price`, `Total`.
- B3/Avenue keep PT-BR on ingest; mappers rename to canonical columns and `pd.to_datetime` the date.
- Tickers: derive `Asset` with `parse_b3_ticker` from `Produto`/`Código de Negociação`.
- Dedupe: only `origin_id` checked on import (field-by-field filters are commented out).

## Workflows
- Run locally:
  ```sh
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ./wallet.py  # http://localhost:5000
  ```
- Uploads saved under `uploads/` and used in `origin_id`; moving files alters future dedupe keys.
- B3 Movimentation filter: WTForms fields in `B3MovimentationFilterForm` must match ORM columns; `process_b3_movimentation_request` auto-builds filters (LIKE for text/date, `==` for floats).
- Asset page contract: `process_*_asset_request()` returns `{valid,name,source,ticker,dataframes:{buys,sells,wages,taxes[,rent_wages][,movimentation][,negotiation]}, ...metrics}` consumed by `view_asset_helper()` and templates.

## Integrations & caching
- Quotes/history: `yfinance` — B3 adds `.SA`; crypto uses `-USD` then BRL via `usd_exchange_rate('BRL')`.
- FX: `utils/scraping.usd_exchange_rate()`; HTML scraping via `scrape_data` with `requests_cache` to `request_cache.sqlite`.

## Gotchas
- DB stores dates as strings; always convert after reads (see mappers).
- `plot_price_history` needs `asset_info['info']['symbol']` from `get_online_info`.
- Portuguese movimentation labels must align when merging (e.g., "Compra", "Venda").
- Network failures are handled with `flash` + logs; analytics continue with zeros/defaults.

## Extending
- New source: add ORM + mapper in `models.py`, importer in `importing.py`, processor in `processing.py`, route/template wiring in `routes.py`/`templates/`.
- New B3 filter: add field to `B3MovimentationFilterForm` with the ORM column name.
- New metric: compute in `consolidate_asset_info` and render in templates.

Missing or unclear? Mention which feature you’re extending (e.g., table rendering, history) and this guide can be refined.
