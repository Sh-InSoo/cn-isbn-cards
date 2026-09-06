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


def republish_cards(
    year: int,
    month: int,
    *,
    slack=None,
    thread_ts: str | None = None,
    comment: str | None = None,
    label: str = "",
    expect: str | None = None,
    cards_dir=None,
    scrape_path=None,
) -> str:
    """Re-render the month's cards from the CURRENT editorial JSON on GitHub
    and (optionally) upload them again — ignoring the .published marker.

    Used after an editorial correction: the daily run won't touch a month
    whose marker exists, so re-publishing is an explicit, manual step.

      thread_ts  reply into the original card post's thread instead of posting
                 a new top-level message (recommended for corrections).
      comment    headline text for the Slack post (default: generic 정정본 text).
      label      short version tag appended to file titles, e.g. "v3".
      expect     substring that MUST appear in the fetched editorial JSON —
                 guards against re-uploading a stale version when GitHub's
                 CDN/API hasn't caught up with a push yet.

    Returns "rendered" (slack=None) or "republished". The marker is left as-is.
    """
    year_month = f"{year:04d}{month:02d}"
    cards_dir = Path(cards_dir or Config.CARDS_DIR)
    scrape = Path(scrape_path) if scrape_path else (
        Config.DATA_DIR / f"cn-isbn-{year_month}.json")
    if not scrape.exists():
        raise FileNotFoundError(f"local scrape JSON not found: {scrape}")

    editorial_text = _fetch_editorial(year_month)
    if editorial_text is None:
        raise FileNotFoundError(
            f"editorial JSON for {year_month} not on GitHub "
            f"({Config.GITHUB_REPO}@{Config.GITHUB_BRANCH})")
    if expect and expect not in editorial_text:
        raise RuntimeError(
            f"fetched editorial JSON does not contain --expect text {expect!r}; "
            "GitHub may not have the latest push yet — retry in a minute.")

    cards_dir.mkdir(parents=True, exist_ok=True)
    editorial_path = cards_dir / f"cn-isbn-{year_month}-editorial.json"
    editorial_path.write_text(editorial_text, encoding="utf-8")

    from render_cards import generate_cards_html
    card_paths = generate_cards_html(scrape, editorial_path, cards_dir)
    logger.info(f"[cards] re-rendered {len(card_paths)} cards for {year_month}")

    if slack is None:
        return "rendered"

    tag = f" {label}" if label else ""
    if comment is None:
        comment = (
            f":white_check_mark:  *{year}년 {month}월 판호 카드뉴스 정정본{tag} (5장)* — "
            "이전 버전 대신 이 5장을 사용해 주세요."
        )
    slack.upload_cards(
        year=year, month=month, card_paths=card_paths,
        thread_ts=thread_ts, initial_comment=comment,
        title_suffix=f" 정정본{tag}" if tag else " 정정본",
    )
    logger.info(f"[cards] re-uploaded {len(card_paths)} cards to Slack"
                + (f" (thread {thread_ts})" if thread_ts else ""))
    return "republished"


# ── CLI ───────────────────────────────────────────────────────────────────────
#
#   Re-publish after an editorial fix (run inside the NAS container so the
#   bot token + NAS chromium are used):
#
#     docker compose run --rm cn-isbn python card_publisher.py \
#         --month 202608 --republish --thread-ts 1788204224.727639 \
#         --label v3 --expect "3종이 한국 IP"
#
#   Add --no-upload to only re-render (e.g. on the desktop with APP_BASE_DIR=.).
#
def _cli(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Render/publish the monthly 5-card carousel.")
    p.add_argument("--month", required=True, metavar="YYYYMM")
    p.add_argument("--republish", action="store_true",
                   help="ignore the .published marker: re-fetch editorial, "
                        "re-render, re-upload")
    p.add_argument("--thread-ts", metavar="TS",
                   help="Slack thread to reply into (original card post ts)")
    p.add_argument("--comment", help="override the Slack headline text")
    p.add_argument("--label", default="",
                   help="version tag for titles/comment, e.g. v3")
    p.add_argument("--expect",
                   help="substring that must be present in the fetched editorial")
    p.add_argument("--no-upload", action="store_true",
                   help="render only; do not touch Slack")
    a = p.parse_args(argv)

    if len(a.month) != 6 or not a.month.isdigit():
        p.error("--month must be YYYYMM")
    year, month = int(a.month[:4]), int(a.month[4:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    slack = None
    if not a.no_upload:
        Config.validate()
        from slack_client import SlackClient
        slack = SlackClient(Config.SLACK_BOT_TOKEN, Config.SLACK_CHANNEL)

    if a.republish:
        status = republish_cards(
            year, month, slack=slack, thread_ts=a.thread_ts,
            comment=a.comment, label=a.label, expect=a.expect)
    else:
        if a.thread_ts or a.comment or a.label or a.expect:
            p.error("--thread-ts/--comment/--label/--expect require --republish")
        status = publish_cards_if_ready(year, month, slack=slack)

    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
