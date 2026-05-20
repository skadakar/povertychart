import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PRICE_RE = re.compile(r"(\d{1,3}(?:[ .\u00A0]\d{3})*(?:,\d{1,2})?)\s*(kr|nok|norske kroner|norsk kr|kr.)?", re.I)
PACK_RE = re.compile(r"(\d+)\s*(stk|pk|pakke|pcs|krt|kartong|eske|box)\b", re.I)
CALIBER_PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?\s?x\s?\d+(?:\.\d+)?\b", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s?mm(?:\s+[A-Za-zÆØÅæøå]+)?\b", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s?ACP\b", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s?cal\b", re.I),
]


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


def parse_caliber(text: str) -> str | None:
    if not text:
        return None
    for pattern in CALIBER_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return None


def parse_bulk_price(html: str) -> float | None:
    for pattern in [
        re.compile(r'"packagePrice"\s*:\s*\{[^}]*"formatted"\s*:\s*"([^"]+)"', re.I),
        re.compile(r'"price2"\s*:\s*"([^"]+)"', re.I),
        re.compile(r'"price3"\s*:\s*"([^"]+)"', re.I),
    ]:
        match = pattern.search(html)
        if match:
            price = normalize_price_str(match.group(1))
            if price is not None:
                return price
    return None


def parse_category_generic(html: str, base_url: str) -> list[dict]:
    items = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href = m.group(1)
        if not href:
            continue
        href_lower = href.lower()
        if href_lower.startswith('tel:') or href_lower.startswith('mailto:') or href_lower.startswith('javascript:'):
            continue
        if any(ext in href_lower for ext in ('.js', '.css', '.svg', '.png', '.jpg', '.jpeg', '.ico')):
            continue
        if 'node_modules' in href_lower or 'min-side' in href_lower or 'login' in href_lower:
            continue
        if '/produkt' not in href_lower and 'produkt' not in href_lower and 'product' not in href_lower:
            continue
        text = re.sub(r"\s+", " ", re.sub(r'<[^>]+>', ' ', m.group(2))).strip()
        if len(text) < 3:
            continue
        start = max(0, m.start() - 300)
        end = min(len(html), m.end() + 300)
        window = re.sub(r"\s+", " ", re.sub(r'<[^>]+>', ' ', html[start:end])).strip()
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
            'caliber': parse_caliber(text),
        })
    return items


def parse_category(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for block in soup.select('div.item.js-uc193-item, div.item.stock-availability-in-stock, div.item.stock-availability-out-of-stock'):
        link = block.select_one('h2 a.js-product-link') or block.select_one('a.js-product-link')
        if not link:
            continue
        title = link.get_text(' ', strip=True) or link.get('title') or ''
        if not title:
            image = link.select_one('img')
            if image and image.get('alt'):
                title = image.get('alt').strip()
        if not title:
            continue
        href = link.get('href')
        if not href:
            continue
        price_tag = block.select_one('span.Price.notranslate, span.c-price__value.notranslate, span.c-price__value.js-sellprice-formatted')
        price = normalize_price_str(price_tag.get_text(' ', strip=True)) if price_tag else None
        pack_qty = None
        pack_match = PACK_RE.search(title)
        if pack_match:
            try:
                pack_qty = int(pack_match.group(1))
            except ValueError:
                pack_qty = None
        else:
            block_text = block.get_text(' ', strip=True)
            pack_match = PACK_RE.search(block_text)
            if pack_match:
                try:
                    pack_qty = int(pack_match.group(1))
                except ValueError:
                    pack_qty = None
        items.append({
            'title': title,
            'url': urljoin(base_url, href),
            'snippet': block.get_text(' ', strip=True),
            'price': price,
            'currency': 'NOK' if price is not None else None,
            'pack_qty': pack_qty,
            'per_unit_flag': False,
            'caliber': parse_caliber(title),
        })
    if items:
        return items
    return parse_category_generic(html, base_url)


def parse_product_detail(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    detail = {}
    title_tag = soup.select_one('h1.uc-product-view__product-name, h1')
    title = title_tag.get_text(' ', strip=True) if title_tag else None
    if title:
        detail['title'] = title
    price_tag = soup.select_one('span.js-sellprice-formatted, span.Price.notranslate, span.c-price__value.notranslate')
    if price_tag:
        detail['price'] = normalize_price_str(price_tag.get_text(' ', strip=True))
        detail['currency'] = 'NOK'
    if title:
        caliber = parse_caliber(title)
        if caliber:
            detail['caliber'] = caliber
        pack_match = PACK_RE.search(title)
        if pack_match:
            try:
                detail['pack_qty'] = int(pack_match.group(1))
            except ValueError:
                detail['pack_qty'] = None
    brand_tag = soup.select_one('h2.uc-product-view__product-brand-name a, .uc-product-view__product-brand-name-link')
    if brand_tag:
        detail['vendor'] = brand_tag.get_text(' ', strip=True)
    bulk_price = parse_bulk_price(html)
    if bulk_price is not None:
        detail['bulk_price'] = bulk_price
    return detail
