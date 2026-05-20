"""Simple scraper CLI prototype.

Reads `scraper/sources.json`, fetches each category URL, extracts the page <title>
and writes a minimal `products.json` with one record per source.

Usage:
    python -m scraper.main --output docs/data/products.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import re
import urllib.request
import urllib.error


PRICE_RE = re.compile(r"(\d{1,3}(?:[ .\u00A0]\d{3})*(?:,\d{1,2})?)\s*(kr|nok|norske kroner|norsk kr|kr.)?", re.I)
PACK_RE = re.compile(r"(\d+)\s*(stk|pk|pakke|pcs|krt|kartong|eske|box)\b", re.I)
PER_UNIT_RE = re.compile(r"(pr\.?\s*(stk|pcs|piece|pr stk|/stk|pris per stk|pris/pr stk))", re.I)

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "scraper" / "sources.json"


def normalize_price_str(s: str) -> float | None:
    if not s:
        return None
    # Remove non-breaking spaces, replace thousand separators and comma decimals
    s = s.replace('\u00A0', '').replace(' ', '').replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^0-9\.]', '', s)
    try:
        return float(s)
    except Exception:
        return None


def extract_price_pack_from_text(text: str) -> list[dict]:
    results = []
    # find all price occurrences in the text
    for m in PRICE_RE.finditer(text):
        price_raw = m.group(1)
        currency = m.group(2) or 'NOK'
        price = normalize_price_str(price_raw)

        # look for pack qty near the price: search window around match
        start = max(0, m.start() - 100)
        end = min(len(text), m.end() + 100)
        window = text[start:end]
        pack = None
        pack_m = PACK_RE.search(window)
        if pack_m:
            try:
                pack = int(pack_m.group(1))
            except Exception:
                pack = None

        per_unit = bool(PER_UNIT_RE.search(window))

        results.append({
            'price': price,
            'currency': 'NOK' if currency else None,
            'pack_qty': pack,
            'per_unit_flag': per_unit,
            'snippet': window.strip(),
        })
    return results


def fetch_products_from_category(client: object, url: str, limit: int = 30) -> list[dict]:
    """Attempt to extract product-like entries from a category page.

    Returns a list of records {title, url, price, pack_qty, currency, scraped_at, snippet}.
    This is heuristic-based and intended as a starting point for per-site parsers.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ammunition-price-scraper/0.1 (+https://github.com/)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            html = raw.decode('utf-8', errors='replace')
    except Exception:
        return []

    items = []
    # crude: use the full page text to find price/pack occurrences
    text = re.sub(r"\s+", " ", re.sub(r'<[^>]+>', ' ', html))
    matches = extract_price_pack_from_text(text)
    seen = 0
    for m in matches[:limit]:
        title = ''
        # try to get <a> text near the match
        snippet = m.get('snippet') or ''
        # extract a short title from snippet
        title = snippet.split('. ')[0][:120]
        items.append({
            'title': title,
            'url': url,
            'snippet': snippet,
            'price': m.get('price'),
            'currency': m.get('currency'),
            'pack_qty': m.get('pack_qty'),
        })
        seen += 1
    return items


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            sources = json.load(f)
    except Exception as e:
        print("Failed to read sources.json:", e, file=sys.stderr)
        return 2

    results = []
    now = datetime.now(timezone.utc).astimezone().isoformat()

    for src in sources:
        url = src.get("category_url")
        if url:
            items = fetch_products_from_category(None, url)
        else:
            items = []

        if items:
            for it in items:
                record = {
                    "store_id": src.get("id"),
                    "store_name": src.get("name"),
                    "url": it.get("url") or url,
                    "title": it.get("title") or it.get("snippet") or "",
                    "caliber": None,
                    "pack_qty": it.get("pack_qty"),
                    "price": it.get("price"),
                    "currency": it.get("currency"),
                    "per_unit_flag": it.get('per_unit_flag', False),
                    "snippet": it.get('snippet'),
                    "scraped_at": now,
                }
                results.append(record)
        else:
            # fallback: fetch page title
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ammunition-price-scraper/0.1 (+https://github.com/)"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    raw = resp.read()
                    html = raw.decode('utf-8', errors='replace')
                    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
                    title = m.group(1).strip() if m else ""
            except Exception:
                title = ""
            record = {
                "store_id": src.get("id"),
                "store_name": src.get("name"),
                "url": url,
                "title": title,
                "caliber": None,
                "pack_qty": None,
                "price": None,
                "currency": None,
                "scraped_at": now,
            }
            results.append(record)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(results)} entries to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
