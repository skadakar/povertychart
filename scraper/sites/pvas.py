import re
from urllib.parse import urljoin

PRICE_RE = re.compile(r"(\d{1,3}(?:[ .\u00A0]\d{3})*(?:,\d{1,2})?)\s*(kr|nok|norske kroner|norsk kr|kr.)?", re.I)
PACK_RE = re.compile(r"(\d+)\s*(stk|pk|pakke|pcs|krt|kartong|eske|box)\b", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'<[^>]+>', ' ', s)).strip()


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


def parse_category(html: str, base_url: str) -> list[dict]:
    items = []
    # look for product links only (heuristic: URL contains 'produkt' or '/p/')
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href = m.group(1)
        if not href:
            continue
        href_lower = href.lower()
        # skip common non-product links
        if href_lower.startswith('tel:') or href_lower.startswith('mailto:') or href_lower.startswith('javascript:'):
            continue
        if any(ext in href_lower for ext in ('.js', '.css', '.svg', '.png', '.jpg', '.jpeg', '.ico')):
            continue
        if 'node_modules' in href_lower or 'min-side' in href_lower or 'login' in href_lower:
            continue
        # must contain product-ish token
        if 'produkt/' not in href_lower and '/produkt' not in href_lower and '/p/' not in href_lower and 'product' not in href_lower:
            continue
        text = _norm(m.group(2))
        if len(text) < 3:
            continue
        # inspect nearby text for price
        start = max(0, m.start() - 300)
        end = min(len(html), m.end() + 300)
        window = _norm(html[start:end])
        price_m = PRICE_RE.search(window)
        if not price_m:
            continue
        price = normalize_price_str(price_m.group(1))
        pack = None
        pack_m = PACK_RE.search(window)
        if pack_m:
            try:
                pack = int(pack_m.group(1))
            except Exception:
                pack = None
        items.append({
            'title': text,
            'url': urljoin(base_url, href),
            'snippet': window,
            'price': price,
            'currency': 'NOK',
            'pack_qty': pack,
            'per_unit_flag': False,
        })
    return items
