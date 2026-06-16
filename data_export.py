"""
data_export.py — NAS-side handoff to the cloud routine (git-less).

The NAS has no git, so instead of `git push` this writes the computed scrape
numbers two ways:
  1. a LOCAL copy at  {DATA_DIR}/cn-isbn-YYYYMM.json  (so card_publisher can read
     the scrape side without any network), and
  2. a push to GitHub via the Contents REST API (so the cloud routine, whose
     source is the repo, can read it and produce the analysis Canvas + the
     editorial JSON).

Wiring (in main.py Phase 1):
    from data_export import export_and_push
    export_and_push(year, month, results, ytd, comparison)

Env vars:
    GITHUB_TOKEN   fine-grained PAT with `contents: read & write` on the repo.
                   If unset, the local copy is still written and the GitHub push
                   is skipped (logged) — the run does not fail.
    GITHUB_REPO    default "Sh-InSoo/cn-isbn-cards"
    GITHUB_BRANCH  default "main"

The cloud routine only reads these files; a re-push (idempotent overwrite using
the current file SHA) is harmless.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from pathlib import Path

import requests

from config import Config

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_API = "https://api.github.com"


def build_payload(year: int, month: int, results: dict, ytd: dict,
                  comparison: dict) -> dict:
    """Assemble the handoff JSON. Numbers only — no fabricated fields."""
    return {
        "schema_version": SCHEMA_VERSION,
        "year": year,
        "month": month,
        "year_month": f"{year:04d}{month:02d}",
        "generated_at": datetime.now().astimezone().isoformat(),
        "results": {
            cat: {
                "count": (results.get(cat) or {}).get("count", 0),
                "url": (results.get(cat) or {}).get("url", ""),
                "games": (results.get(cat) or {}).get("games", []),
            }
            for cat in ("import", "domestic", "change")
        },
        "ytd": {
            "import": ytd.get("import", 0),
            "domestic": ytd.get("domestic", 0),
            "change": ytd.get("change", 0),
        },
        "comparison": comparison or {},
    }


def _github_put_file(rel_path: str, content: str, message: str) -> None:
    """Create/update a file on GitHub via the Contents API."""
    repo = Config.GITHUB_REPO
    branch = Config.GITHUB_BRANCH
    token = Config.GITHUB_TOKEN
    url = f"{_API}/repos/{repo}/contents/{rel_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Need the current blob SHA to update an existing file.
    sha = None
    r = requests.get(url, params={"ref": branch}, headers=headers, timeout=30)
    if r.status_code == 200:
        sha = r.json().get("sha")
    elif r.status_code != 404:
        r.raise_for_status()

    body = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    r = requests.put(url, json=body, headers=headers, timeout=30)
    r.raise_for_status()


def export_and_push(year: int, month: int, results: dict, ytd: dict,
                    comparison: dict, repo_dir=None) -> Path:
    """Write the scrape JSON locally and push it to GitHub via the API.

    `repo_dir` is accepted for backward compatibility but ignored (git-less).
    Returns the local path written. GitHub push failures raise (caller wraps in
    try/except); a missing GITHUB_TOKEN is a warning, not an error.
    """
    payload = build_payload(year, month, results, ytd, comparison)
    ym = payload["year_month"]
    rel_path = f"data/cn-isbn-{ym}.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2)

    # 1. Local copy (card_publisher reads the scrape side from here).
    local = Config.DATA_DIR / f"cn-isbn-{ym}.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(content, encoding="utf-8")
    logger.info(f"[data_export] wrote local {local} ({local.stat().st_size} bytes)")

    # 2. Push to GitHub for the cloud routine.
    if not Config.GITHUB_TOKEN:
        logger.warning(
            "[data_export] GITHUB_TOKEN not set — wrote local copy only, "
            "skipped GitHub push (routine won't see this month)."
        )
        return local

    c = payload["results"]
    msg = (f"data: {ym} 판호 리포트 (import={c['import']['count']}, "
           f"domestic={c['domestic']['count']}, change={c['change']['count']})")
    _github_put_file(rel_path, content, msg)
    logger.info(f"[data_export] pushed {rel_path} to GitHub via Contents API")
    return local
