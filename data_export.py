"""
data_export.py — NAS-side handoff to the cloud routine.

The existing NAS pipeline (main.py) already computes `results`, `ytd`, and
`comparison` for a fully-published month. This module serializes that exact data
to a JSON file inside a cloned GitHub repo and pushes it, so the cloud routine
can read it and produce the Slack Canvas summary.

Wiring (in main.py, right before `state.mark_sent(year_month)`):

    from data_export import export_and_push
    export_and_push(year, month, results, ytd, comparison)

Env vars (set on the NAS):
    DATA_REPO_DIR   absolute path to the cloned cn-isbn-cards repo on the NAS
                    (default: /app/data-repo). The container must have this repo
                    cloned with push credentials (HTTPS token or SSH key).
    GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL  optional commit identity.

The cloud routine only ever reads these files; it never writes back. Dedup on the
cloud side is done by checking Slack for an existing post for the same month, so a
re-push (idempotent overwrite) is harmless.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Schema version — bump if the JSON shape changes so the routine can guard on it.
SCHEMA_VERSION = 1


def build_payload(
    year: int,
    month: int,
    results: dict,
    ytd: dict,
    comparison: dict,
) -> dict:
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
        # comparison keys are optional (absent when upstream fetch failed).
        "comparison": comparison or {},
    }


def export_and_push(
    year: int,
    month: int,
    results: dict,
    ytd: dict,
    comparison: dict,
    repo_dir: str | None = None,
) -> Path:
    """Write data/cn-isbn-YYYYMM.json into the repo and git-push it.

    Returns the path written. Raises on git failure so the NAS log surfaces it;
    callers may wrap in try/except if a push failure should not abort the run.
    """
    repo_dir = Path(repo_dir or os.environ.get("DATA_REPO_DIR", "/app/data-repo"))
    if not (repo_dir / ".git").exists():
        raise FileNotFoundError(
            f"DATA_REPO_DIR is not a git checkout: {repo_dir}. "
            "Clone the cn-isbn-cards repo there (with push credentials) first."
        )

    payload = build_payload(year, month, results, ytd, comparison)
    rel_path = Path("data") / f"cn-isbn-{payload['year_month']}.json"
    out_path = repo_dir / rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"[data_export] wrote {out_path} ({out_path.stat().st_size} bytes)")

    env = os.environ.copy()
    if os.environ.get("GIT_AUTHOR_NAME"):
        env["GIT_COMMITTER_NAME"] = os.environ["GIT_AUTHOR_NAME"]
    if os.environ.get("GIT_AUTHOR_EMAIL"):
        env["GIT_COMMITTER_EMAIL"] = os.environ["GIT_AUTHOR_EMAIL"]

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True,
            env=env,
            capture_output=True,
            text=True,
        )

    try:
        git("pull", "--rebase", "--autostash")  # avoid non-fast-forward rejects
        git("add", str(rel_path))
        git(
            "commit",
            "-m",
            f"data: {payload['year_month']} 판호 리포트 (import={payload['results']['import']['count']}, "
            f"domestic={payload['results']['domestic']['count']}, change={payload['results']['change']['count']})",
        )
        git("push")
        logger.info(f"[data_export] pushed {rel_path} to remote")
    except subprocess.CalledProcessError as e:
        # "nothing to commit" is fine (idempotent re-run); re-raise anything else.
        if "nothing to commit" in (e.stdout or "") + (e.stderr or ""):
            logger.info("[data_export] no changes to push (already up to date)")
        else:
            logger.error(f"[data_export] git failed: {e.stderr or e.stdout}")
            raise

    return out_path
