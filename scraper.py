from __future__ import annotations
import time
import logging
import requests
from bs4 import BeautifulSoup
from config import Config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,ko;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nppa.gov.cn/",
}

# import/change publish one cumulative annual page; domestic publishes one page per month
ANNUAL_CATEGORIES = {"import", "change"}


class NPPAScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # Low-level fetch
    # ------------------------------------------------------------------
    def _fetch(self, url: str, retries: int = 3) -> str | None:
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                resp.encoding = self._detect_encoding(resp)
                return resp.text
            except Exception as e:
                wait = 10 * (attempt + 1)
                logger.warning(f"Fetch attempt {attempt + 1} failed [{url}]: {e}. Retry in {wait}s")
                time.sleep(wait)
        logger.error(f"All retries failed for {url}")
        return None

    @staticmethod
    def _detect_encoding(resp) -> str:
        ct = resp.headers.get("Content-Type", "")
        if "gb" in ct.lower():
            return "gb18030"
        try:
            resp.content.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "gb18030"

    # ------------------------------------------------------------------
    # Link finders
    # ------------------------------------------------------------------
    def find_monthly_link(self, category: str, year: int, month: int) -> str | None:
        """Domestic category: one page per month, URL contains YYYYMM.

        The listing page only shows its most recent entries (see
        _iter_listing_pages), which is fine for this call — it's only ever
        used for "the current announcement month", which is always recent.
        For historical lookups (YTD of a past year) use count_ytd instead,
        which paginates.
        """
        listing_url = Config.NPPA_URLS[category]
        html = self._fetch(listing_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        year_month = f"{year:04d}{month:02d}"

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if year_month in href:
                return self._absolute(href, listing_url)

        logger.info(f"No link found for {category} {year_month} in {listing_url}")
        return None

    def find_annual_link(self, category: str, year: int) -> str | None:
        """Import/change categories: one cumulative page per year, URL contains YYYY."""
        listing_url = Config.NPPA_URLS[category]
        html = self._fetch(listing_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        year_str = f"{year:04d}"

        for a in soup.find_all("a", href=True):
            if year_str in a["href"]:
                return self._absolute(a["href"], listing_url)

        logger.info(f"No annual link found for {category} year {year} in {listing_url}")
        return None

    def _iter_listing_pages(self, listing_url: str, max_pages: int = 40,
                            max_empty_pages: int = 5):
        """Yield each numbered listing page's HTML in order: listing_url
        itself (page 1), then index_2.html, index_3.html, ... .

        The NPPA listing pages show a fixed recent window (~15 entries) with
        NO next-page link in the page-1 HTML, but numbered pages
        (index_2.html, index_3.html, ...) do exist and return older entries
        — confirmed by direct fetch. There's no reliable "last page" marker,
        so we stop once `max_empty_pages` consecutive fetches fail (404/
        network error) or `max_pages` is reached, whichever comes first.
        """
        empty_streak = 0
        for page in range(1, max_pages + 1):
            page_url = listing_url if page == 1 else (
                listing_url.rstrip("/") + f"/index_{page}.html")
            html = self._fetch(page_url, retries=1)
            if not html:
                empty_streak += 1
                if empty_streak >= max_empty_pages:
                    return
                continue
            empty_streak = 0
            yield html

    @staticmethod
    def _absolute(href: str, base: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"https://www.nppa.gov.cn{href}"
        return base.rstrip("/") + "/" + href.lstrip("/")

    # ------------------------------------------------------------------
    # Table parsers
    # ------------------------------------------------------------------
    def parse_game_table(self, html: str) -> list[dict]:
        """Parse a monthly domestic page — all rows belong to the same month."""
        soup = BeautifulSoup(html, "lxml")
        tables = soup.find_all("table")
        if not tables:
            logger.warning("No table found in announcement page")
            return []

        main_table = max(tables, key=lambda t: len(t.find_all("tr")))
        rows = main_table.find_all("tr")
        if len(rows) < 2:
            return []

        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True) for c in header_cells]

        games = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            values = [c.get_text(strip=True) for c in cells]
            if not any(values):
                continue
            game = dict(zip(headers, values))
            games.append(game)

        return games

    def parse_games_by_month(self, html: str, year: int, month: int) -> list[dict]:
        """Parse a cumulative annual page and return only games approved in the target month.

        The approval date (e.g. '2026年04月28日') is always the last column.
        The import table header has one extra column vs data rows, so zip alignment
        maps '名称' correctly (column 1) even though later columns shift.
        """
        soup = BeautifulSoup(html, "lxml")
        tables = soup.find_all("table")
        if not tables:
            return []

        main_table = max(tables, key=lambda t: len(t.find_all("tr")))
        rows = main_table.find_all("tr")
        if len(rows) < 2:
            return []

        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True) for c in header_cells]

        month_pattern = f"{year}年{month:02d}月"
        games = []

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            values = [c.get_text(strip=True) for c in cells]
            if not any(values):
                continue
            if not any(month_pattern in v for v in values):
                continue
            game = dict(zip(headers, values))
            games.append(game)

        return games

    # ------------------------------------------------------------------
    # YTD counter
    # ------------------------------------------------------------------
    def count_ytd(self, category: str, year: int, through_month: int) -> int:
        """Count total approvals Jan-through_month for the given year."""
        if category in ANNUAL_CATEGORIES:
            link = self.find_annual_link(category, year)
            if not link:
                return 0
            html = self._fetch(link)
            if not html:
                return 0
            total = 0
            for m in range(1, through_month + 1):
                total += len(self.parse_games_by_month(html, year, m))
            return total

        # Domestic: each month has its own page, discovered from a listing
        # page. The listing only shows its most recent entries per (numbered)
        # page — older months roll off page 1 over time (bug found 2026-09-01:
        # a July run correctly found all of Jan-Jul 2025 on page 1, but by
        # September, Jan-May 2025 had scrolled past it, silently underccounting
        # ytd_domestic_prev). Page through the listing until every requested
        # month's link is found (or pages run out).
        wanted = {f"{year:04d}{m:02d}" for m in range(1, through_month + 1)}
        found_links: dict[str, str] = {}
        listing_url = Config.NPPA_URLS[category]

        for html in self._iter_listing_pages(listing_url):
            still_missing = wanted - found_links.keys()
            if not still_missing:
                break
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                for ym in still_missing:
                    if ym in href:
                        found_links[ym] = self._absolute(href, listing_url)

        missing = wanted - found_links.keys()
        if missing:
            logger.warning(
                f"[count_ytd] domestic {year}: could not locate a page for "
                f"{sorted(missing)} — YTD total will undercount by that many "
                f"months' worth of approvals."
            )

        total = 0
        for link in found_links.values():
            page_html = self._fetch(link)
            if not page_html:
                continue
            games = self.parse_game_table(page_html)
            total += len(games)
            time.sleep(1)

        return total

    # ------------------------------------------------------------------
    # Main public method
    # ------------------------------------------------------------------
    def get_monthly_data(self, category: str, year: int, month: int) -> dict | None:
        """Return scraped data for a category/month, or None if not published yet."""
        logger.info(f"Scraping [{category}] for {year}/{month:02d} ...")

        if category in ANNUAL_CATEGORIES:
            link = self.find_annual_link(category, year)
            if not link:
                return None
            html = self._fetch(link)
            if not html:
                return None
            games = self.parse_games_by_month(html, year, month)
            if not games:
                logger.info(f"[{category}] No games found for {year}/{month:02d} in annual page")
                return None
        else:
            link = self.find_monthly_link(category, year, month)
            if not link:
                return None
            html = self._fetch(link)
            if not html:
                return None
            games = self.parse_game_table(html)

        logger.info(f"[{category}] {year}/{month:02d}: found {len(games)} games at {link}")

        return {
            "category": category,
            "year": year,
            "month": month,
            "url": link,
            "games": games,
            "count": len(games),
        }
