"""
comparison.py – Compute MoM and YoY comparison counts for the card stats card.
Uses the existing NPPAScraper so no extra HTTP sessions are opened.
"""

import logging
from scraper import NPPAScraper

logger = logging.getLogger(__name__)


def get_comparison_counts(scraper: NPPAScraper, year: int, month: int,
                           current_counts: dict) -> dict:
    """
    current_counts: {"import": <this month's import count>,
                      "domestic": <this month's domestic count>}
                     — needed to turn the MoM fetch into a delta.

    Returns a dict with optional keys:
        mom_import       – current_counts["import"] - count(import, year, month-1)
        mom_domestic     – current_counts["domestic"] - count(domestic, year, month-1)
        yoy_import       – count(import, year-1, month)   [raw count, not a delta —
        yoy_domestic     – count(domestic, year-1, month)  render_cards.py computes the % itself]
        ytd_import_prev  – ytd(import, year-1, through=month)
        ytd_domestic_prev – ytd(domestic, year-1, through=month)
    All values are int; key is absent when data cannot be fetched.
    """
    result: dict = {}
    prev_year = year - 1

    # ── Month-over-month (stored as a delta — the template renders it as-is) ───
    if month > 1:
        prev_month = month - 1
        logger.info(f"[comparison] MoM: fetching {year}/{prev_month:02d} counts...")
        try:
            d = scraper.get_monthly_data("import", year, prev_month)
            if d:
                result["mom_import"] = current_counts["import"] - d["count"]
        except Exception as e:
            logger.warning(f"MoM import fetch failed: {e}")

        try:
            d = scraper.get_monthly_data("domestic", year, prev_month)
            if d:
                result["mom_domestic"] = current_counts["domestic"] - d["count"]
        except Exception as e:
            logger.warning(f"MoM domestic fetch failed: {e}")

    # ── Year-over-year ────────────────────────────────────────────────────────
    logger.info(f"[comparison] YoY: fetching {prev_year}/{month:02d} counts...")
    try:
        d = scraper.get_monthly_data("import", prev_year, month)
        if d:
            result["yoy_import"] = d["count"]
    except Exception as e:
        logger.warning(f"YoY import fetch failed: {e}")

    try:
        d = scraper.get_monthly_data("domestic", prev_year, month)
        if d:
            result["yoy_domestic"] = d["count"]
    except Exception as e:
        logger.warning(f"YoY domestic fetch failed: {e}")

    # ── YTD previous year ─────────────────────────────────────────────────────
    logger.info(f"[comparison] YTD prev year: counting {prev_year} through {month:02d}...")
    try:
        result["ytd_import_prev"] = scraper.count_ytd("import", prev_year, month)
    except Exception as e:
        logger.warning(f"YTD prev import failed: {e}")

    try:
        result["ytd_domestic_prev"] = scraper.count_ytd("domestic", prev_year, month)
    except Exception as e:
        logger.warning(f"YTD prev domestic failed: {e}")

    logger.info(f"[comparison] done: {result}")
    return result
