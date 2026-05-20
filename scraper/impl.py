"""Implementation for the scraper CLI (site-aware, stdlib-only).

This module contains the scraping helpers and the main function.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import re
import urllib.request
import urllib.error
import importlib

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "scraper" / "sources.json"

PRICE_RE = re.compile(r"(\d{1,3}(?:[ .\u00A0]\d{3})*(?:,\d{1,2})?)\s*(kr|nok|norske kroner|norsk kr|kr.)?", re.I)
PACK_RE = re.compile(r"(\d+)\s*(stk|pk|pakke|pcs|krt|kartong|eske|box)\b", re.I)
PER_UNIT_RE = re.compile(r"(pr\.?\s*(stk|pcs|piece|pr stk|/stk|pris per stk|pris/pr stk))", re.I)


def normalize_price_str(s: str) -> float | None:
    if not s:
        return None
    s = s.replace('\u00A0', '').replace(' ', '').replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^0-9\.]', '', s)
    try:
        return float(s)
    except Exception:
        return None


def extract_price_pack_from_text(text: str) -> list[dict]:
    results = []
    for m in PRICE_RE.finditer(text):
        price_raw = m.group(1)
        currency = m.group(2) or 'NOK'
        price = normalize_price_str(price_raw)
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


def fetch_products_from_html(html: str, url: str, limit: int = 30) -> list[dict]:
    items = []
    text = re.sub(r"\s+", " ", re.sub(r'<[^>]+>', ' ', html))
    matches = extract_price_pack_from_text(text)
    for m in matches[:limit]:
        snippet = m.get('snippet') or ''
        title = snippet.split('. ')[0][:120]
        items.append({
            'title': title,
            'url': url,
            'snippet': snippet,
            'price': m.get('price'),
            'currency': m.get('currency'),
            'pack_qty': m.get('pack_qty'),
            'per_unit_flag': m.get('per_unit_flag', False),
        })
    return items


def fetch_html(url: str) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return raw.decode('utf-8', errors='replace')
    except Exception:
        return None


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
        url = src.get('category_url')
        if not url:
            continue
        html = fetch_html(url)
        items = []
        if html:
            # try per-site parser module
            mod_name = f"scraper.sites.{src.get('id')}"
            try:
                mod = importlib.import_module(mod_name)
                if hasattr(mod, 'parse_category'):
                    items = mod.parse_category(html, url)
                if hasattr(mod, 'parse_product_detail') and items:
                    for item in items:
                        item_url = item.get('url')
                        if not item_url:
                            continue
                        detail_html = fetch_html(item_url)
                        if not detail_html:
                            continue
                        try:
                            detail = mod.parse_product_detail(detail_html, item_url)
                            if isinstance(detail, dict):
                                for k, v in detail.items():
                                    if v is not None:
                                        item[k] = v
                        except Exception:
                            continue
            except ModuleNotFoundError:
                items = []
            if not items:
                items = fetch_products_from_html(html, url)

        if items:
            for it in items:
                record = {
                    'store_id': src.get('id'),
                    'store_name': src.get('name'),
                    'vendor': it.get('vendor') or src.get('name'),
                    'url': it.get('url') or url,
                    'title': it.get('title') or it.get('snippet') or '',
                    'caliber': it.get('caliber'),
                    'pack_qty': it.get('pack_qty'),
                    'price': it.get('price'),
                    'bulk_price': it.get('bulk_price'),
                    'currency': it.get('currency'),
                    'per_unit_flag': it.get('per_unit_flag', False),
                    'snippet': it.get('snippet'),
                    'scraped_at': now,
                }
                results.append(record)
        else:
            # fallback: page title
            try:
                m = re.search(r"<title>(.*?)</title>", html or "", re.I | re.S)
                title = m.group(1).strip() if m else ''
            except Exception:
                title = ''
            record = {
                'store_id': src.get('id'),
                'store_name': src.get('name'),
                'vendor': src.get('name'),
                'url': url,
                'title': title,
                'caliber': None,
                'pack_qty': None,
                'price': None,
                'bulk_price': None,
                'currency': None,
                'per_unit_flag': False,
                'scraped_at': now,
            }
            results.append(record)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'Wrote {len(results)} entries to {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
