# Pistol Ammunition Price Comparison — Simplified Plan

## Summary
Purpose: run a daily GitHub Action that crawls the pistol-ammunition category pages from a small list of Norwegian stores, extract minimal structured data (product links and key attributes where possible), merge identical products over time, and publish a static JSON dataset plus a small searchable/sortable UI via GitHub Pages.

This is a simplified, GitHub Actions–first design focused on practicality: the Action produces a single `docs/data/products.json` file and the static UI in `docs/` reads that file and displays the data and crawl date.

## Sources (initial)
The action will crawl these category pages (only the listed category paths):

- PVA S — https://www.pvas.no/ammunisjon/haandvaapen
- Jaktbutikken — https://jaktbutikken.no/produktkategori/ammunisjon/handvapen-ammunisjon/
- Intersport Bogstadveien — https://www.intersport-bogstadveien.no/h%C3%A5ndv%C3%A5pen-ammunisjons-priser._19338.html
- Jaktdepotet — https://www.jaktdepotet.no/h%C3%A5ndv%C3%A5penammunisjon
 - Norsegear — https://www.norsegear.no/range/ammunisjon/pistol

Each record in the output will include a direct link back to the source page (`url`).

## Minimal data model (written JSON)
- For the GitHub Action / Pages MVP we produce a JSON array of offer entries with fields:
  - `store_id`, `store_name`, `url`, `title`, `caliber` (nullable), `pack_qty` (nullable), `price` (nullable), `currency` (nullable), `scraped_at` (ISO8601)

The static UI will compute `price_per_unit` when `pack_qty` and `price` are present and show the crawl date (max `scraped_at`).

## Simplified pipeline
1. GitHub Action runs daily and executes a Python CLI: `python -m scraper.main --output docs/data/products.json`.
2. The CLI reads `scraper/sources.json`, fetches each category URL, extracts a small set of fields (title and product links where feasible), and writes merged JSON.
3. The workflow commits the updated `docs/data/products.json` back to the repo and GitHub Pages serves the `docs/` folder.

Notes: serving from `docs/` or `gh-pages` is both supported — pick either; this plan assumes `docs/` in `main` for simplicity.

## Crawl date visibility
- The UI will display the most recent `scraped_at` from the dataset and show per-record `scraped_at` timestamps so users know if data is outdated.

## Step-by-step plan for me to implement (order of work)
1. Add a compact `scraper/sources.json` containing the category URLs (done in scaffold).
2. Scaffold a minimal scraper CLI (`scraper/main.py`) that fetches each URL, grabs the page `<title>`, and records an entry with `store_id`, `store_name`, `url`, `title`, and `scraped_at`.
3. Add simple site modules (`scraper/sites/`) as placeholders to add site-specific parsing later.
4. Add a static `docs/index.html` UI that reads `docs/data/products.json`, displays a table of store entries with links, and shows the latest crawl date.
5. Add `.github/workflows/daily-scrape.yml` to run the scraper daily and commit `docs/data/products.json`.
6. Run the workflow locally (via the CLI) to produce initial `docs/data/products.json` and verify `docs/index.html` renders it.
7. Iterate: improve per-site parsing to extract product-level items (price, pack size), add normalization and fuzzy merge, then extend UI to compare prices and price-per-unit.


## Current implementation status (delta)
- The scraper CLI now heuristically detects prices and pack quantities on category pages and records `pack_qty`, `price`, `per_unit_flag`, and a `snippet` showing the nearby text. The static UI displays computed price-per-unit and the detected snippet so bulk discounts are visible.

## Immediate work I will start now
- Create/update files: `scraper/sources.json`, `scraper/main.py`, placeholder site parsers under `scraper/sites/`, `requirements.txt`, `docs/index.html`, initial `docs/data/products.json`, and `.github/workflows/daily-scrape.yml`.
- The CLI will be runnable locally and used by the Action to produce `docs/data/products.json`.

---

I'll now scaffold the minimal files and a working CLI prototype that fetches each category URL and writes `docs/data/products.json`. After creating the scaffold, I'll run the CLI locally (in the workspace) to generate the initial dataset and verify the static UI file displays it.

