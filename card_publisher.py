"""
card_publisher.py — Phase 3 of the monthly pipeline: render the rich 5-card
carousel once the cloud routine's editorial JSON is available, then upload it
to Slack.

New orchestration (see README):

  1. [NAS]   scrape NPPA → text report → push  data/cn-isbn-YYYYMM.json
             (numbers only). Cards are NOT made yet.
  2. [Cloud] routine reads that JSON → publishes the analysis Canvas AND
             pushes  data/cn-isbn-YYYYMM-editorial.json  (spotlights, EN names,
             developers, 수입/국산 분석 …) back to the repo.
  3. [NAS]   a later daily run calls publish_cards_if_ready(): git-pull the repo,
             detect the editorial JSON, render the cards (render_cards.py) and
             upload them (slack_client.upload_cards).

Because the editorial layer is produced by the routine AFTER the NAS push, card
upload is naturally deferred to the next NAS run — hence the daily retry loop.

Card state is tracked by a local marker file (NAS-local, gitignored), so this
module is idempotent and needs NO change to the NAS StateManager.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)


def _git(repo_dir: Path, *args: str) -> None:
    env = os.environ.copy()
    if os.environ.get("GIT_AUTHOR_NAME"):
        env["GIT_COMMITTER_NAME"] = os.environ["GIT_AUTHOR_NAME"]
    if os.environ.get("GIT_AUTHOR_EMAIL"):
        env["GIT_COMMITTER_EMAIL"] = os.environ["GIT_AUTHOR_EMAIL"]
    subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=True, capture_output=True, text=True, env=env,
    )


def _marker_path(cards_dir: Path, year_month: str) -> Path:
    return cards_dir / f".published-{year_month}"


def publish_cards_if_ready(
    year: int,
    month: int,
    *,
    repo_dir: str | Path | None = None,
    cards_dir: str | Path | None = None,
    slack=None,
    pull: bool = True,
) -> str:
    """Render + upload the cards for the given month if the editorial JSON exists.

    Returns a status string (also logged):
      "already-published"    marker present — nothing to do (idempotent).
      "skipped-no-scrape"    the scrape JSON isn't in the repo yet.
      "deferred-no-editorial" scrape present but routine hasn't pushed editorial.
      "rendered"             cards rendered (slack=None → upload skipped).
      "published"            cards rendered AND uploaded to Slack.

    Never raises for the "not ready yet" cases — those are normal daily states.
    Rendering/upload errors propagate so the NAS log surfaces them (callers may
    wrap in try/except).
    """
    year_month = f"{year:04d}{month:02d}"
    repo_dir = Path(repo_dir or os.environ.get("DATA_REPO_DIR", "/app/data-repo"))
    cards_dir = Path(cards_dir or Config.CARDS_DIR)

    marker = _marker_path(cards_dir, year_month)
    if marker.exists():
        return "already-published"

    # Pull so we see the editorial JSON the routine pushed after our scrape.
    if pull and (repo_dir / ".git").exists():
        try:
            _git(repo_dir, "pull", "--rebase", "--autostash")
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"[cards] git pull failed (using local repo state): "
                f"{e.stderr or e.stdout}"
            )

    scrape = repo_dir / "data" / f"cn-isbn-{year_month}.json"
    editorial = repo_dir / "data" / f"cn-isbn-{year_month}-editorial.json"
    if not scrape.exists():
        logger.info(f"[cards] scrape JSON not found for {year_month}; skipping.")
        return "skipped-no-scrape"
    if not editorial.exists():
        logger.info(
            f"[cards] editorial JSON not ready for {year_month}; "
            "will retry next run."
        )
        return "deferred-no-editorial"

    # ── Render (HTML template → Playwright → 5×1080² PNG) ──
    from render_cards import generate_cards_html
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_paths = generate_cards_html(scrape, editorial, cards_dir)
    logger.info(f"[cards] rendered {len(card_paths)} cards for {year_month}")

    if slack is None:
        return "rendered"

    # ── Upload to Slack ──
    slack.upload_cards(year=year, month=month, card_paths=card_paths)
    logger.info(f"[cards] uploaded {len(card_paths)} cards to Slack")

    marker.write_text("ok\n", encoding="utf-8")
    return "published"
