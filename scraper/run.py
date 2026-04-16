import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import SessionLocal, init_db
from db.models import RawListing
from scraper.parser import scrape

TARGET_URL = os.getenv("TARGET_URL", "https://www.autoscout24.com/lst")
SCRAPE_PAGES = int(os.getenv("SCRAPE_PAGES", "5"))


def run(n_pages=None, url=None):
    url = url or TARGET_URL
    n_pages = n_pages or SCRAPE_PAGES

    init_db()
    rows = scrape(url, n_pages)

    if not rows:
        print("[run] no rows scraped — check TARGET_URL or network")
        return 0

    session = SessionLocal()
    inserted = 0
    skipped_no_url = 0
    skipped_exists = 0
    try:
        for i, row in enumerate(rows):
            if i < 2:
                print(f"[run] Sample row parsed: {row}")
                
            if not row.get("url"):
                skipped_no_url += 1
                continue
            
            try:
                exists = session.query(RawListing).filter_by(url=row["url"]).first()
                if exists:
                    skipped_exists += 1
                    continue
                
                session.add(RawListing(**row))
                session.commit()
                inserted += 1
            except Exception as e:
                session.rollback()
                print(f"[run] DB error on row {row.get('url')}: {e}")
                
    finally:
        session.close()

    print(f"[run] done — inserted: {inserted}, skipped (no URL): {skipped_no_url}, skipped (already exists): {skipped_exists}")
    return inserted


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=SCRAPE_PAGES)
    ap.add_argument("--url", type=str, default=TARGET_URL)
    args = ap.parse_args()
    run(n_pages=args.pages, url=args.url)
