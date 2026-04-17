"""
Playwright-based scraper — headless Chromium fallback for JS-heavy pages.
Install: pip install playwright && playwright install chromium

Used automatically when USE_PLAYWRIGHT=1 in environment,
or when httpx gets blocked (non-200 responses on too many pages).
"""
import asyncio
import logging
import random

log = logging.getLogger(__name__)

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
"""


async def fetch_page_playwright(url: str, timeout_ms: int = 30000) -> str | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.warning("playwright not installed — run: pip install playwright && playwright install chromium")
        return None

    log.info("playwright fetch: %s", url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="pl-PL",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()
        await page.add_init_script(_STEALTH_SCRIPT)

        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            # scroll to trigger lazy-loaded cards
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(800)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            html = await page.content()
            log.info("playwright: fetched %d bytes", len(html))
            return html
        except Exception as e:
            log.error("playwright page error: %s", e)
            return None
        finally:
            await browser.close()


async def scrape_playwright(base_url: str, n_pages: int = 1) -> list[dict]:
    """Drop-in async replacement for scraper.parser.scrape()."""
    from scraper.parser import parse_listings

    all_rows = []
    for page_num in range(1, n_pages + 1):
        url = f"{base_url}?page={page_num}"
        html = await fetch_page_playwright(url)
        if not html:
            log.warning("playwright: no HTML for page %d, stopping", page_num)
            break
        rows = parse_listings(html, base_url)
        log.info("playwright page %d: %d listings", page_num, len(rows))
        all_rows.extend(rows)
        if page_num < n_pages:
            await asyncio.sleep(random.uniform(2.0, 4.0))

    log.info("playwright scrape done: %d total listings", len(all_rows))
    return all_rows


def scrape_playwright_sync(base_url: str, n_pages: int = 1) -> list[dict]:
    """Sync wrapper for use in Celery tasks and CLI."""
    return asyncio.run(scrape_playwright(base_url, n_pages))
