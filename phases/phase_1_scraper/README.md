# Phase 1 — Catalogue build

## Direct scrape: investigated and blocked

We investigated Blinkit's internal product-search endpoints (as used by the consumer web client). Findings:

| Check | Result |
|---|---|
| Storefront | Behind **Cloudflare** bot protection |
| Search API | Returns **HTTP 403** without a valid browser session / challenge clearance |
| Headers tested | `auth_key`, `lat`, `lon`, `app_client: consumer_web`, browser User-Agent |
| Conclusion | **Direct scraping is not viable** for a reliable, automatable catalogue refresh |

Documented for evaluators: the architecture's scheduled-refresh path is designed around a scraper, but this build uses a **hybrid catalogue** instead of live fetch.

## Catalogue sources (this build)

| Source | File | Role |
|---|---|---|
| **Apify** | `data/blinkit_products.csv` | Real Blinkit product rows (cat food, cat litter @ Sarjapur). Every row included. `source: "apify"`. |
| **Generated** | `phases/phase_1_scraper/generated_products.py` | Synthetic fill to ~250 SKUs covering all tiles in `categories.json`. Real Indian brand names and realistic prices. `source: "generated"`. |

## Build

```bash
python -m phases.phase_1_scraper.build_catalog
```

Writes:

- `data/catalog.json`
- `data/raw/<UTC timestamp>/manifest.json`

## Future refresh

If Blinkit endpoints become accessible (or via a licensed data provider), replace `build_catalog.py`'s Apify import path with live fetch — the manifest and `catalog.json` schema stay the same.
