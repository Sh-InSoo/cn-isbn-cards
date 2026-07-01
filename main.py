"""
main.py – cn-isbn entry point

Daily check (from day 22) for the monthly NPPA (China) game license announcements.

Two-phase monthly flow (see README):
  Phase 1 — report & handoff (runs once, the day all three announcements appear):
      scrape → Slack text report → push  data/cn-isbn-YYYYMM.json  (numbers only)
  Phase 2 — cloud routine (external): reads that JSON, publishes the analysis
      Canvas, and pushes  data/cn-isbn-YYYYMM-editorial.json  back to the repo.
  Phase 3 — rich cards (this script, on a LATER daily run): once the editorial
      JSON is present, render the 5-card carousel and upload it to Slack.
      Handled by card_publisher.publish_cards_if_ready().

Because the editorial layer is produced by the routine AFTER the Phase-1 push,
the cards arrive on the next NAS run, not the same one — the daily cron retries
until the editorial JSON shows up.

Exits cleanly (code 0) without doing work if:
  - Day < START_DAY
  - The three announcements aren't all published yet (Phase 1 retries tomorrow)
"""

from __future__ import annotations
import os
import sys
import logging
from datetime import datetime

from config import Config
from state_manager import StateManager
from scraper import NPPAScraper
from slack_client import SlackClient

Config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _run_report(year: int, month: int, year_month: str,
                state: StateManager, slack: SlackClient) -> bool:
    """Phase 1: scrape, send the text report, and push the handoff JSON.

    Returns True if the report was sent (all three announcements published),
    False if not all three are out yet (caller should retry on a later run).
    """
    scraper = NPPAScraper()
    results: dict[str, dict | None] = {}
    for category in ("import", "domestic", "change"):
        results[category] = scraper.get_monthly_data(category, year, month)

    missing = [cat for cat, d in results.items() if d is None]
    if missing:
        labels = {"import": "进口", "domestic": "国产", "change": "变更"}
        logger.info(
            f"Not yet published: {', '.join(labels[m] for m in missing)}. "
            "Will retry tomorrow."
        )
        return False

    logger.info("All three announcements found. Computing YTD...")
    ytd_cache = state.get_ytd_counts(year)
    ytd: dict[str, int] = {}
    for category in ("import", "domestic", "change"):
        cache_key = f"{category}_{year_month}"
        if cache_key in ytd_cache:
            ytd[category] = ytd_cache[cache_key]
        else:
            logger.info(f"Counting YTD for {category}...")
            ytd[category] = scraper.count_ytd(category, year, month)
            ytd_cache[cache_key] = ytd[category]
    state.save_ytd_counts(year, ytd_cache)
    logger.info(
        f"YTD counts: import={ytd['import']}, domestic={ytd['domestic']}, "
        f"change={ytd['change']}"
    )

    # ── Text report ────────────────────────────────────────────────────────
    logger.info(f"Sending text report to Slack channel {Config.SLACK_CHANNEL}...")
    slack.send_report(year=year, month=month, results=results, ytd=ytd)

    # ── Comparison data (MoM / YoY / YTD-prev) for the card stats ───────────
    comparison: dict = {}
    try:
        from comparison import get_comparison_counts
        logger.info("Computing MoM / YoY comparison data...")
        current_counts = {
            "import": results["import"]["count"],
            "domestic": results["domestic"]["count"],
        }
        comparison = get_comparison_counts(scraper, year, month, current_counts)
    except Exception as e:
        logger.warning(f"Comparison data failed (cards will omit YoY/MoM): {e}")

    # ── Handoff to the cloud routine ────────────────────────────────────────
    # Push the numbers so the routine can publish the Canvas AND produce the
    # editorial JSON that Phase 3 needs. A push failure must not abort the run.
    try:
        from data_export import export_and_push
        export_and_push(year, month, results, ytd, comparison)
    except Exception as e:
        logger.error(f"data_export handoff failed (routine may be skipped): {e}")

    return True


def main():
    now = datetime.now()
    year, month, day = now.year, now.month, now.day

    # Test overrides via environment variables
    if os.environ.get("TEST_YEAR"):
        year = int(os.environ["TEST_YEAR"])
    if os.environ.get("TEST_MONTH"):
        month = int(os.environ["TEST_MONTH"])
    if os.environ.get("TEST_DAY"):
        day = int(os.environ["TEST_DAY"])

    year_month = f"{year:04d}{month:02d}"

    logger.info("=" * 60)
    logger.info(f"cn-isbn  |  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    if day < Config.START_DAY:
        logger.info(
            f"Today is the {day}th. Monitoring starts on the "
            f"{Config.START_DAY}th. Exiting."
        )
        return

    Config.validate()
    state = StateManager(Config.STATE_FILE)
    slack = SlackClient(Config.SLACK_BOT_TOKEN, Config.SLACK_CHANNEL)

    # ── Phase 1: report & handoff (once per month) ──────────────────────────
    if not state.already_sent(year_month):
        if not _run_report(year, month, year_month, state, slack):
            return  # not all three published yet — retry on a later run
        state.mark_sent(year_month)
        logger.info(f"cn-isbn report complete for {year}/{month:02d}")
    else:
        logger.info(
            f"Report for {year_month} already sent — checking card status..."
        )

    # ── Phase 3: rich cards (waits for the routine's editorial JSON) ─────────
    # Skippable via SKIP_CARDS for text-only runs / debugging.
    if os.environ.get("SKIP_CARDS", "").lower() in ("1", "true", "yes"):
        logger.info("[cards] SKIP_CARDS set — skipping card publish.")
        return

    try:
        from card_publisher import publish_cards_if_ready
        status = publish_cards_if_ready(year, month, slack=slack)
        logger.info(f"[cards] {status}")
    except Exception as e:
        logger.error(f"[cards] publish failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()
