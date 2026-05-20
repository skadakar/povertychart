# Ammunition Price Scraper (MVP)

This repository contains a minimal prototype that runs a daily GitHub Action to crawl configured category pages for pistol ammunition, writes `docs/data/products.json`, and serves a small static UI via GitHub Pages.

Quick start (local):

```bash
python -m pip install -r requirements.txt
python -m scraper.main --output docs/data/products.json
# Then open docs/index.html in a browser (or serve docs/ as static files)
```

The scheduled workflow is `.github/workflows/daily-scrape.yml` and the sources are in `scraper/sources.json`.
