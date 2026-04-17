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
        "Accept-Language": "pl-PL,pl;q=0.9",
        "Referer": "https://www.otomoto.pl/"
    }

def fetch_page(base_url: str, page: int) -> str | None:
    url = f"{base_url}?page={page}"
    try:
        r = httpx.get(url, headers=_headers(), timeout=15, follow_redirects=True)
        if r.status_code != 200:
            print(f"[scraper] page {page}: HTTP {r.status_code}, skipping")
            return None
        return r.text
    except Exception as e:
        print(f"[scraper] page {page}: request failed — {e}")
        return None

def _safe_text(tag) -> str | None:
    try:
        return tag.get_text(" ", strip=True) if tag else None
    except Exception:
        return None

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

    cards = soup.select("article[data-id]")

    for card in cards:
        try:
            # url
            a_tag = card.select_one("a[href*='otomoto.pl/osobowe']")
            if a_tag and "href" in a_tag.attrs:
                url = a_tag["href"]
            else:
                data_id = card.get("data-id")
                url = f"https://www.otomoto.pl/osobowe/oferta/{data_id}"

            # brand, model
            title_tag = card.select_one("h2") or card.select_one("h1")
            title = _safe_text(title_tag) or ""
            parts = title.split(maxsplit=1)
            brand = parts[0] if parts else None
            model = parts[1] if len(parts) > 1 else None

            # year
            year_raw = card.get("data-year")
            if not year_raw:
                year_raw = " ".join([_safe_text(el) or "" for el in card.select("li, dd")])
            m_year = re.search(r"\b(19|20)\d{2}\b", str(year_raw))
            year = int(m_year.group()) if m_year else None

            # mileage_km
            mileage_km = None
            card_text = " ".join([_safe_text(el) or "" for el in card.select("*")]).replace("\xa0", " ")
            m_mil = re.search(r"([\d\s]+)\s*(km|tys\.)", card_text, flags=re.IGNORECASE)
            if m_mil:
                num_str = re.sub(r"[^\d]", "", m_mil.group(1))
                if num_str:
                    mul = 1000 if "tys" in m_mil.group(2).lower() else 1
                    mileage_km = int(num_str) * mul

            # power_kw
            power_kw = None
            m_pow = re.search(r"([\d\s.,]+)\s*(KM|HP|kW)", card_text, flags=re.IGNORECASE)
            if m_pow:
                num_str = re.sub(r"[^\d.,]", "", m_pow.group(1)).replace(",", ".")
                if num_str:
                    try:
                        val = float(num_str)
                        if "km" in m_pow.group(2).lower() or "hp" in m_pow.group(2).lower():
                            power_kw = round(val / 1.36)
                        else:
                            power_kw = val
                    except ValueError:
                        pass

            # fuel_type
            fuel_type = None
            fuel_map = {
                "Benzyna+LPG": "Petrol+LPG",
                "Benzyna": "Petrol",
                "Diesel": "Diesel",
                "Elektryczny": "Electric",
                "Hybryda": "Hybrid",
                "LPG": "LPG"
            }
            for pl_fuel, en_fuel in fuel_map.items():
                if re.search(r"\b" + re.escape(pl_fuel) + r"\b", card_text, flags=re.IGNORECASE):
                    fuel_type = en_fuel
                    break

            # transmission
            transmission = None
            trans_map = {
                "Manualna": "Manual",
                "Automatyczna": "Automatic",
                "Półautomatyczna": "Semi-automatic"
            }
            for pl_trans, en_trans in trans_map.items():
                if re.search(r"\b" + re.escape(pl_trans) + r"\b", card_text, flags=re.IGNORECASE):
                    transmission = en_trans
                    break

            # price_eur
            price_eur = None
            curr_elem = card.find(string=re.compile(r"PLN|EUR", re.IGNORECASE))
            if curr_elem:
                parent_text = curr_elem.parent.parent.get_text(" ", strip=True) if curr_elem.parent and curr_elem.parent.parent else curr_elem.parent.get_text(" ", strip=True)
                m_price = re.search(r"([\d\s]+)\s*(PLN|EUR)", parent_text, flags=re.IGNORECASE)
                if m_price:
                    num_str = re.sub(r"[^\d]", "", m_price.group(1))
                    if num_str:
                        val = float(num_str)
                        if "eur" in m_price.group(2).lower():
                            price_eur = val
                        else:
                            price_eur = round(val / 4.25, 0)

            results.append({
                "url": url,
                "brand": brand,
                "model": model,
                "year": year,
                "mileage_km": mileage_km,
                "power_kw": power_kw,
                "fuel_type": fuel_type,
                "transmission": transmission,
                "price_eur": price_eur,
            })
        except Exception as e:
            print(f"[parser] card error: {e}")
            continue

    return results

def scrape(base_url: str = "https://www.otomoto.pl/osobowe", n_pages: int = 1) -> list[dict]:
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
