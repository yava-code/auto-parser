import logging
import re
import random
import time
import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

FUEL_MAP = {
    "Benzyna+LPG": "Petrol+LPG",
    "Benzyna": "Petrol",
    "Diesel": "Diesel",
    "Elektryczny": "Electric",
    "Hybryda": "Hybrid",
    "LPG": "LPG",
    "CNG": "CNG",
}

TRANS_MAP = {
    "Manualna": "Manual",
    "Automatyczna": "Automatic",
    "Półautomatyczna": "Semi-automatic",
}

BODY_MAP = {
    "Sedan": "Sedan",
    "Kombi": "Estate",
    "Hatchback": "Hatchback",
    "SUV": "SUV",
    "Coupe": "Coupe",
    "Cabrio": "Cabrio",
    "Minivan": "Minivan",
    "Van": "Van",
    "Pickup": "Pickup",
}

COLOR_MAP = {
    "Czarny": "Black",
    "Biały": "White",
    "Srebrny": "Silver",
    "Szary": "Grey",
    "Niebieski": "Blue",
    "Czerwony": "Red",
    "Zielony": "Green",
    "Brązowy": "Brown",
    "Beżowy": "Beige",
    "Żółty": "Yellow",
    "Pomarańczowy": "Orange",
    "Fioletowy": "Purple",
    "Złoty": "Gold",
}


def _headers():
    return {
        "User-Agent": random.choice(UA_POOL),
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.otomoto.pl/",
    }


def fetch_page(base_url: str, page: int) -> str | None:
    url = f"{base_url}?page={page}"
    try:
        r = httpx.get(url, headers=_headers(), timeout=20, follow_redirects=True)
        if r.status_code != 200:
            log.warning("page %d: HTTP %d, skipping", page, r.status_code)
            return None
        log.debug("page %d: fetched %d bytes", page, len(r.text))
        return r.text
    except Exception as e:
        log.error("page %d: request failed — %s", page, e)
        return None


def _safe_text(tag) -> str | None:
    try:
        return tag.get_text(" ", strip=True) if tag else None
    except Exception:
        return None


def _match_map(text: str, mapping: dict) -> str | None:
    for key, val in mapping.items():
        if re.search(r"\b" + re.escape(key) + r"\b", text, flags=re.IGNORECASE):
            return val
    return None


def parse_listings(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []
    cards = soup.select("article[data-id]")
    log.debug("found %d article cards", len(cards))

    for card in cards:
        try:
            row = _parse_card(card)
            if row:
                results.append(row)
        except Exception as e:
            log.warning("card parse error: %s", e)

    return results


def _parse_card(card) -> dict | None:
    # url
    a_tag = card.select_one("a[href*='otomoto.pl/osobowe']")
    if a_tag and "href" in a_tag.attrs:
        url = a_tag["href"]
    else:
        data_id = card.get("data-id")
        if not data_id:
            return None
        url = f"https://www.otomoto.pl/osobowe/oferta/{data_id}"

    # brand + model
    title_tag = card.select_one("h2") or card.select_one("h1")
    title = _safe_text(title_tag) or ""
    parts = title.split(maxsplit=1)
    brand = parts[0] if parts else None
    model = parts[1] if len(parts) > 1 else None

    # flatten card text for regex searches
    card_text = " ".join(_safe_text(el) or "" for el in card.select("*")).replace("\xa0", " ")

    # year
    year_raw = card.get("data-year") or card_text
    m_year = re.search(r"\b(19|20)\d{2}\b", str(year_raw))
    year = int(m_year.group()) if m_year else None

    # mileage — negative lookbehind prevents matching mid-word digits like "A4 85 000 km"
    mileage_km = None
    m_mil = re.search(r"(?<!\w)(\d[\d\s]*)\s*(km|tys\.)", card_text, flags=re.IGNORECASE)
    if m_mil:
        num_str = re.sub(r"[^\d]", "", m_mil.group(1))
        if num_str:
            mul = 1000 if "tys" in m_mil.group(2).lower() else 1
            mileage_km = int(num_str) * mul

    # power (KM/HP → kW)
    power_kw = None
    m_pow = re.search(r"([\d\s.,]+)\s*(KM|HP|kW)", card_text, flags=re.IGNORECASE)
    if m_pow:
        num_str = re.sub(r"[^\d.,]", "", m_pow.group(1)).replace(",", ".")
        if num_str:
            try:
                val = float(num_str)
                unit = m_pow.group(2).lower()
                power_kw = round(val / 1.36) if unit in ("km", "hp") else val
            except ValueError:
                pass

    # engine displacement in cc
    engine_cc = None
    m_eng = re.search(r"([\d\s.,]+)\s*cm3", card_text, flags=re.IGNORECASE)
    if not m_eng:
        # look for common pattern like "2.0" before common identifiers
        m_eng2 = re.search(r"\b(\d[\.,]\d)\s*(?:TDI|TSI|TFSI|HDI|CDTI|dCi|JTD|TCI|T|d)\b", card_text)
        if m_eng2:
            try:
                engine_cc = float(m_eng2.group(1).replace(",", ".")) * 1000
            except ValueError:
                pass
    else:
        num_str = re.sub(r"[^\d]", "", m_eng.group(1))
        if num_str:
            engine_cc = float(num_str)

    # categorical fields
    fuel_type = _match_map(card_text, FUEL_MAP)
    transmission = _match_map(card_text, TRANS_MAP)
    body_type = _match_map(card_text, BODY_MAP)
    color = _match_map(card_text, COLOR_MAP)

    # doors (look for "4 drzwi", "5-drzwiowy" etc.)
    doors = None
    m_doors = re.search(r"\b([2-6])\s*drzwi", card_text, flags=re.IGNORECASE)
    if not m_doors:
        m_doors = re.search(r"\b([2-6])-?drzwiow", card_text, flags=re.IGNORECASE)
    if m_doors:
        doors = int(m_doors.group(1))

    # location (city / region — often in span with data-testid)
    location = None
    loc_tag = card.select_one("[data-testid*='location'], .ooa-ysit2e, .e1oqyyyi9")
    if loc_tag:
        location = _safe_text(loc_tag)

    # price in EUR
    price_eur = None
    curr_elem = card.find(string=re.compile(r"PLN|EUR", re.IGNORECASE))
    if curr_elem:
        parent = curr_elem.parent
        parent_text = (_safe_text(parent.parent) or _safe_text(parent)) if parent else ""
        m_price = re.search(r"([\d\s]+)\s*(PLN|EUR)", parent_text or "", flags=re.IGNORECASE)
        if m_price:
            num_str = re.sub(r"[^\d]", "", m_price.group(1))
            if num_str:
                val = float(num_str)
                price_eur = val if "eur" in m_price.group(2).lower() else round(val / 4.25, 0)

    return {
        "url": url,
        "brand": brand,
        "model": model,
        "year": year,
        "mileage_km": mileage_km,
        "power_kw": power_kw,
        "fuel_type": fuel_type,
        "transmission": transmission,
        "price_eur": price_eur,
        "color": color,
        "body_type": body_type,
        "location": location,
        "engine_cc": engine_cc,
        "doors": doors,
    }


def scrape(base_url: str = "https://www.otomoto.pl/osobowe", n_pages: int = 1) -> list[dict]:
    all_rows = []
    for page in range(1, n_pages + 1):
        html = fetch_page(base_url, page)
        if not html:
            break
        rows = parse_listings(html, base_url)
        log.info("page %d: %d listings", page, len(rows))
        all_rows.extend(rows)
        if page < n_pages:
            time.sleep(random.uniform(1.5, 3.5))
    log.info("scrape done: %d total listings from %d pages", len(all_rows), n_pages)
    return all_rows
