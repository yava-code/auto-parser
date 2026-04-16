import re
import random
import time
import httpx
from bs4 import BeautifulSoup

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _headers():
    return {
        "User-Agent": random.choice(UA_POOL),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def fetch_page(base_url: str, page: int) -> str | None:
    params = {"page": page} if page > 1 else {}
    try:
        r = httpx.get(base_url, params=params, headers=_headers(), timeout=15, follow_redirects=True)
        if r.status_code != 200:
            print(f"[scraper] page {page}: HTTP {r.status_code}, skipping")
            return None
        return r.text
    except Exception as e:
        print(f"[scraper] page {page}: request failed — {e}")
        return None


def _safe_text(tag) -> str | None:
    try:
        return tag.get_text(strip=True) if tag else None
    except Exception:
        return None


def _parse_price(raw: str | None) -> float | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return float(digits) if digits else None


def _parse_int(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _parse_float(raw: str | None) -> float | None:
    if not raw:
        return None
    m = re.search(r"[\d.,]+", raw)
    if not m:
        return None
    try:
        return float(m.group().replace(",", "."))
    except ValueError:
        return None


def parse_listings(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []

    # Iterate over main container
    cards = soup.select("article[data-testid='list-item']")

    if not cards:
        # fallback for older layouts
        cards = soup.select("article.cldt-summary-full-item")

    for card in cards:
        try:
            # Try to fetch URL
            url_tag = card.select_one("a[data-anchor-overlay='true']") or card.select_one("a[href*='/offers/']")
            if card.has_attr("data-guid"):
                url = "https://www.autoscout24.com/offers/" + card.get("data-guid")
            else:
                url = url_tag["href"] if url_tag else None
                if url and not url.startswith("http"):
                    from urllib.parse import urljoin
                    url = urljoin("https://www.autoscout24.com", url)

            # Direct attribute parsing (for the newer react-based layout)
            if card.has_attr("data-make"):
                brand = card.get("data-make")
                model = card.get("data-model")
                price_eur = _parse_price(card.get("data-price"))
                mileage_km = _parse_int(card.get("data-mileage"))
                
                year_raw = card.get("data-first-registration")
                year = None
                if year_raw:
                    m = re.search(r"\b(19|20)\d{2}\b", year_raw)
                    year = int(m.group()) if m else None
            else:
                # Fallbacks for older layout if `data-make` isn't present
                title_tag = card.select_one("h2")
                title = _safe_text(title_tag) or ""
                parts = title.split(None, 1)
                brand = parts[0] if parts else None
                model = parts[1] if len(parts) > 1 else None

                subtitle = _safe_text(card.select_one("[class*='subtitle']"))
                year = None
                if subtitle:
                    m = re.search(r"\b(19|20)\d{2}\b", subtitle)
                    year = int(m.group()) if m else None

                mileage_km = _parse_int(_safe_text(card.select_one("[data-testid='mileage']")))
                
                price_tag = card.select_one("[data-testid='price-label']") or card.select_one("[class*='price']")
                price_eur = _parse_price(_safe_text(price_tag))

            # engine
            engine_tag = card.select_one('div[data-testid="VehicleDetails-speedometer"] span[class*="ListItemPill_text"]')
            engine_raw = _safe_text(engine_tag) if engine_tag else _safe_text(card.select_one("[data-testid='displacement']"))
            engine_l = _parse_float(engine_raw)

            # fuel type
            fuel_tag = card.select_one('div[data-testid="VehicleDetails-gas_pump"] span[class*="ListItemPill_text"]')
            fuel_type = None
            if fuel_tag:
                 fuel_type = _safe_text(fuel_tag)

            # transmission (scan all pills or fallback to attrs)
            transmission = None
            trans_keywords = {"Manual", "Automatic", "Semi-automatic", "Schaltgetriebe", "Automatik"}
            pills = card.select('span[class*="ListItemPill_text"]')
            if not pills:
                 pills = card.select("li")
                 
            # Find fuel_type in pills if not found by specific testid
            fuel_keywords = {"Petrol", "Diesel", "Electric", "Hybrid", "LPG", "CNG", "Benzin", "Diesel"}
            
            for p in pills:
                text = _safe_text(p)
                if text:
                    if not fuel_type and any(k.lower() in text.lower() for k in fuel_keywords):
                        fuel_type = text
                    if not transmission and any(k.lower() in text.lower() for k in trans_keywords):
                        transmission = text

            results.append({
                "url": url,
                "brand": brand,
                "model": model,
                "year": year,
                "mileage_km": mileage_km,
                "engine_l": engine_l,
                "fuel_type": fuel_type,
                "transmission": transmission,
                "price_eur": price_eur,
            })
        except Exception as e:
            print(f"[parser] card error: {e}")
            continue

    return results


def scrape(base_url: str, n_pages: int) -> list[dict]:
    all_rows = []
    for page in range(1, n_pages + 1):
        html = fetch_page(base_url, page)
        if not html:
            break
        rows = parse_listings(html, base_url)
        print(f"[scraper] page {page}: {len(rows)} listings")
        all_rows.extend(rows)
        if page < n_pages:
            time.sleep(random.uniform(1.5, 3.5))
    return all_rows
