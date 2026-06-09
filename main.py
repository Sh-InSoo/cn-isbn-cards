"""
main.py – cn-isbn entry point

Daily check (from day 22) for the monthly NPPA (China) game license announcements.
Exits cleanly (code 0) without sending if:
  - Day < START_DAY
  - Already sent for this year-month
  - Not all three announcements published yet

New:  After the text report, generates 5 Instagram-style card images
      and uploads them to the same Slack channel.
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
            f"Today is the {day}th. Monitoring starts on the {Config.START_DAY}th. Exiting."
        )
        return

    Config.validate()
    state = StateManager(Config.STATE_FILE)
    if state.already_sent(year_month):
        logger.info(f"Report for {year_month} already sent. Exiting.")
        return

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
        return

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
        f"YTD counts: import={ytd['import']}, domestic={ytd['domestic']}, change={ytd['change']}"
    )

    # ── Text report ───────────────────────────────────────────────────────────
    logger.info(f"Sending text report to Slack channel {Config.SLACK_CHANNEL}...")
    slack = SlackClient(Config.SLACK_BOT_TOKEN, Config.SLACK_CHANNEL)
    slack.send_report(year=year, month=month, results=results, ytd=ytd)

    # ── Comparison data for card stats ────────────────────────────────────────
    comparison: dict = {}
    skip_cards = os.environ.get("SKIP_CARDS", "").lower() in ("1", "true", "yes")

    if not skip_cards:
        try:
            from comparison import get_comparison_counts
            logger.info("Computing MoM / YoY comparison data...")
            comparison = get_comparison_counts(scraper, year, month)
        except Exception as e:
            logger.warning(f"Comparison data failed (cards will omit YoY/MoM): {e}")

        # ── Image card generation ─────────────────────────────────────────────
        try:
            from image_gen import generate_cards
            logger.info("Generating Instagram card images...")
            card_paths = generate_cards(
                year=year,
                month=month,
                results=results,
                ytd=ytd,
                comparison=comparison,
                output_dir=Config.CARDS_DIR,
            )
            logger.info(f"Generated {len(card_paths)} cards: {card_paths}")

            # ── Card upload to Slack ──────────────────────────────────────────
            logger.info("Uploading cards to Slack...")
            slack.upload_cards(year=year, month=month, card_paths=card_paths)
        except ImportError:
            logger.warning("Pillow not installed — skipping card generation")
        except Exception as e:
            logger.error(f"Card generation/upload failed: {e}", exc_info=True)

    # ── Handoff to the cloud routine ──────────────────────────────────────────
    # Push the computed data to the GitHub repo so the cloud routine can read it
    # and publish the Slack Canvas summary. A push failure must not abort the run
    # (the text report + cards already reached Slack); re-push is idempotent.
    try:
        from data_export import export_and_push
        export_and_push(year, month, results, ytd, comparison)
    except Exception as e:
        logger.error(f"data_export handoff failed (routine summary may be skipped): {e}")

    state.mark_sent(year_month)
    logger.info(f"cn-isbn complete for {year}/{month:02d}")


if __name__ == "__main__":
    main()
