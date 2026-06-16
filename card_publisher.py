"""
card_publisher.py — Phase 3: render the rich 5-card carousel once the cloud
routine's editorial JSON is available, then upload it to Slack. Git-less: the
NAS has no git, so the editorial layer is fetched over HTTPS instead of pulled.

Flow:
  1. [NAS]   scrape → text report → data_export writes a LOCAL scrape JSON
             ({DATA_DIR}/cn-isbn-YYYYMM.json) and pushes it to GitHub.
  2. [Cloud] routine reads it, publishes the Canvas, and git-pushes
             data/cn-isbn-YYYYMM-editorial.json (the cloud has git).
  3. [NAS]   a later run calls publish_cards_if_ready(): read the local scrape
             JSON, FETCH the editorial JSON from GitHub over HTTPS (public repo,
             no auth), render (render_cards.py), and upload (slack_client).

Because the editorial layer appears AFTER the NAS push, card upload is naturally
deferred to a later daily run — hence the retry loop. Card state is tracked by a
local marker file so this is idempotent and needs no git and no StateManager change.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from config import Config

logger = logging.getLogger(__name__)

_API = "https://api.github.com"


def _marker_path(cards_dir: Path, year_month: str) -> Path:
    return cards_dir / f".published-{year_month}"


def _fetch_editorial(year_month: str) -> str | None:
    """GET the editorial JSON from GitHub over HTTPS. Returns the raw text, or
    None if it doesn't exist yet (404). Public repo → no auth required, but a
    token (if set) raises the rate limit. Uses the Contents API to avoid the
    raw-CDN's stale-cache window."""
    repo = Config.GITHUB_REPO
    branch = Config.GITHUB_BRANCH
    url = f"{_API}/repos/{repo}/contents/data/cn-isbn-{year_month}-editorial.json"
    headers = {
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if Config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {Config.GITHUB_TOKEN}"

    r = requests.get(url, params={"ref": branch}, headers=headers, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text


def publish_cards_if_ready(
    year: int,
    month: int,
    *,
    slack=None,
    cards_dir=None,
    scrape_path=None,
) -> str:
    """Render + upload cards for the month if the editorial JSON is available.

    Returns a status string (also logged):
      "already-published"     marker present — nothing to do (idempotent).
      "skipped-no-scrape"     the local scrape JSON isn't present.
      "deferred-no-editorial" routine hasn't pushed the editorial JSON yet.
      "rendered"              cards rendered (slack=None → upload skipped).
      "published"             cards rendered AND uploaded to Slack.
    """
    year_month = f"{year:04d}{month:02d}"
    cards_dir = Path(cards_dir or Config.CARDS_DIR)

    marker = _marker_path(cards_dir, year_month)
    if marker.exists():
        return "already-published"

    scrape = Path(scrape_path) if scrape_path else (
        Config.DATA_DIR / f"cn-isbn-{year_month}.json")
    if not scrape.exists():
        logger.info(f"[cards] local scrape JSON not found ({scrape}); skipping.")
        return "skipped-no-scrape"

    editorial_text = _fetch_editorial(year_month)
    if editorial_text is None:
        logger.info(
            f"[cards] editorial JSON not on GitHub yet for {year_month}; "
            "will retry next run."
        )
        return "deferred-no-editorial"

    cards_dir.mkdir(parents=True, exist_ok=True)
    editorial_path = cards_dir / f"cn-isbn-{year_month}-editorial.json"
    editorial_path.write_text(editorial_text, encoding="utf-8")

    # ── Render (HTML template → Playwright → 5×1080² PNG) ──
    from render_cards import generate_cards_html
    card_paths = generate_cards_html(scrape, editorial_path, cards_dir)
    logger.info(f"[cards] rendered {len(card_paths)} cards for {year_month}")

    if slack is None:
        return "rendered"

    # ── Upload to Slack ──
    slack.upload_cards(year=year, month=month, card_paths=card_paths)
    logger.info(f"[cards] uploaded {len(card_paths)} cards to Slack")

    marker.write_text("ok\n", encoding="utf-8")
    return "published"
