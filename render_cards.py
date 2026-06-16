"""
render_cards.py – Render the 5-card Instagram carousel from data using the
HTML template (templates/cards.html.j2) + headless Chromium (Playwright).

This replaces the hand-tweaked claude.ai HTML with a data-driven pipeline:

    scrape JSON  (cn-isbn-YYYYMM.json)          ← NPPA numbers (counts/ytd/comparison)
  + editorial JSON (cn-isbn-YYYYMM-editorial.json) ← curated narrative (spotlights,
                                                     EN names, developers, analysis)
  → template context → Jinja2 → HTML → Playwright screenshots → 5 × 1080² PNG

Usage:
    python render_cards.py --month 202604
    python render_cards.py --scrape data/cn-isbn-202604.json \
                           --editorial data/cn-isbn-202604-editorial.json \
                           --out data/cards

Requires: jinja2, playwright  (and `playwright install chromium`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
TEMPLATE_NAME = "cards.html.j2"

MONTH_EN = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
            "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

DEFAULT_SOCIAL = [
    {"platform": "Instagram", "handle": "@gippie_sh"},
    {"platform": "Threads",   "handle": "@gippie_sh"},
    {"platform": "Facebook",  "handle": "Shanghai Gippie"},
    {"platform": "LinkedIn",  "handle": "Shanghai Gippie"},
]


# ── Data merge ─────────────────────────────────────────────────────────────────
def _pct(curr: int, prev: int | None) -> int | None:
    if not prev:
        return None
    return round((curr - prev) / prev * 100)


def build_context(scrape: dict, editorial: dict) -> dict:
    """Merge NPPA numbers (scrape) + curated narrative (editorial) into the
    flat context the Jinja template consumes."""
    year = scrape["year"]
    month = scrape["month"]

    res = scrape.get("results", {})
    ic = (res.get("import")   or {}).get("count", 0)
    dc = (res.get("domestic") or {}).get("count", 0)
    cc = (res.get("change")   or {}).get("count", 0)

    ytd = scrape.get("ytd", {})
    cmp = scrape.get("comparison", {}) or {}

    ytd_i = ytd.get("import", 0)
    ytd_d = ytd.get("domestic", 0)
    ytd_total = ytd_i + ytd_d
    ytd_i_prev = cmp.get("ytd_import_prev")
    ytd_d_prev = cmp.get("ytd_domestic_prev")
    ytd_total_prev = (ytd_i_prev + ytd_d_prev) if (ytd_i_prev and ytd_d_prev) else None

    yoy_i_prev = cmp.get("yoy_import")
    yoy_d_prev = cmp.get("yoy_domestic")

    def block(curr, prev):
        pct = _pct(curr, prev)
        return {
            "cnt": curr,
            "prev": prev,
            "pct": pct,
            "dir": "up" if (pct is not None and pct >= 0) else "dn",
        }

    def yoy(curr, prev):
        pct = _pct(curr, prev)
        return {
            "prev": prev,
            "prev_year": year - 1,
            "pct": pct if pct is not None else 0,
            "dir": "up" if (pct is not None and pct >= 0) else "dn",
        }

    ytd_prev_note = None
    if ytd_i_prev and ytd_d_prev:
        ytd_prev_note = (f"수입 {ytd_i_prev}종 · 국산 {ytd_d_prev}종 · "
                         f"합계 {ytd_total_prev}종")

    return {
        "year": year,
        "month": month,
        "month_en": MONTH_EN[month],
        "counts": {"import": ic, "domestic": dc, "change": cc,
                   "total": ic + dc},
        "stats": {
            "mom_import": cmp.get("mom_import", 0),
            "mom_domestic": cmp.get("mom_domestic", 0),
            "yoy": {
                "import":   yoy(ic, yoy_i_prev),
                "domestic": yoy(dc, yoy_d_prev),
            },
            "ytd": {
                "import":   block(ytd_i, ytd_i_prev),
                "domestic": block(ytd_d, ytd_d_prev),
                "total":    block(ytd_total, ytd_total_prev),
            },
            "ytd_prev_note": ytd_prev_note,
        },
        # ── Curated narrative (editorial layer) ──
        "import_card": editorial["import_card"],
        "domestic_card": editorial["domestic_card"],
        "cta": editorial["cta"],
        "social": editorial.get("social", DEFAULT_SOCIAL),
        "posts": editorial.get("posts"),
    }


def render_html(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    return env.get_template(TEMPLATE_NAME).render(**context)


# ── Playwright screenshot ────────────────────────────────────────────────────
def screenshot_cards(html: str, out_dir: Path, year: int, month: int) -> list[str]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)

    # Write HTML to a temp file so relative font/CDN loads work over file://
    tmp = Path(tempfile.mkdtemp(prefix="cn-isbn-cards-"))
    html_path = tmp / "cards.html"
    html_path.write_text(html, encoding="utf-8")

    # Browser selection via RENDER_BROWSER_CHANNEL:
    #   unset           → try system msedge, then chrome, then bundled Chromium
    #                     (dev boxes/Windows reuse an installed browser → no DL)
    #   "chromium"      → force Playwright's bundled Chromium (NAS/Linux Docker)
    #   "msedge"/"chrome" → force that channel
    # ("" launch = bundled Chromium; requires `playwright install chromium`.)
    engine = os.environ.get("RENDER_BROWSER_CHANNEL", "").strip().lower()
    if engine in ("chromium", "bundled"):
        channels = [""]
    elif engine:
        channels = [engine]
    else:
        channels = ["msedge", "chrome", ""]

    # A system Chromium binary (e.g. Debian's /usr/bin/chromium on the NAS) used
    # for the bundled ("") launch, avoiding Playwright's blocked browser download.
    exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    # --no-sandbox is required to run Chromium as root inside the container.
    launch_args = ["--force-color-profile=srgb", "--no-sandbox",
                   "--disable-dev-shm-usage"]

    paths: list[str] = []
    with sync_playwright() as p:
        browser = None
        last_err = None
        for ch in channels:
            try:
                if ch:
                    browser = p.chromium.launch(channel=ch, args=launch_args)
                elif exec_path:
                    browser = p.chromium.launch(
                        executable_path=exec_path, args=launch_args)
                else:
                    browser = p.chromium.launch(args=launch_args)
                break
            except Exception as e:  # channel not installed → try next
                last_err = e
                continue
        if browser is None:
            raise RuntimeError(
                f"No usable Chromium-family browser found "
                f"(tried {channels}). Last error: {last_err}")
        page = browser.new_page(viewport={"width": 1200, "height": 1400},
                                device_scale_factor=1)
        page.goto(html_path.as_uri(), wait_until="networkidle")
        # Ensure web fonts are fully loaded before capture
        try:
            page.evaluate("async () => { await document.fonts.ready; }")
        except Exception:
            pass
        page.wait_for_timeout(400)

        for n in range(1, 6):
            p_out = out_dir / f"cn-isbn-{year}{month:02d}-card{n}.png"
            page.locator(f"#card{n}").screenshot(path=str(p_out))
            paths.append(str(p_out))

        browser.close()
    return paths


# ── Public API ─────────────────────────────────────────────────────────────────
def generate_cards_html(scrape_path: str | Path, editorial_path: str | Path,
                        out_dir: str | Path) -> list[str]:
    scrape = json.loads(Path(scrape_path).read_text(encoding="utf-8"))
    editorial = json.loads(Path(editorial_path).read_text(encoding="utf-8"))
    ctx = build_context(scrape, editorial)
    html = render_html(ctx)
    return screenshot_cards(html, Path(out_dir), ctx["year"], ctx["month"])


def main():
    ap = argparse.ArgumentParser(description="Render cn-isbn card news from data.")
    ap.add_argument("--month", help="YYYYMM; resolves data/cn-isbn-YYYYMM.json "
                                     "and data/cn-isbn-YYYYMM-editorial.json")
    ap.add_argument("--scrape", help="path to scrape JSON")
    ap.add_argument("--editorial", help="path to editorial JSON")
    ap.add_argument("--out", default=str(BASE_DIR / "data" / "cards"),
                    help="output directory for PNGs")
    ap.add_argument("--html-only", action="store_true",
                    help="write rendered HTML next to --out and skip screenshots")
    args = ap.parse_args()

    if args.month:
        ym = args.month
        scrape = BASE_DIR / "data" / f"cn-isbn-{ym}.json"
        editorial = BASE_DIR / "data" / f"cn-isbn-{ym}-editorial.json"
    else:
        if not (args.scrape and args.editorial):
            ap.error("provide --month, or both --scrape and --editorial")
        scrape = Path(args.scrape)
        editorial = Path(args.editorial)

    if args.html_only:
        s = json.loads(Path(scrape).read_text(encoding="utf-8"))
        e = json.loads(Path(editorial).read_text(encoding="utf-8"))
        html = render_html(build_context(s, e))
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        hp = out / "cards.html"
        hp.write_text(html, encoding="utf-8")
        print(f"wrote {hp}")
        return

    paths = generate_cards_html(scrape, editorial, args.out)
    print("Generated:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
