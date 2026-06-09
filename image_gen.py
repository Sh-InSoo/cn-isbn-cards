"""
image_gen.py – Generate 5-card Instagram carousel for cn-isbn monthly report.
1080×1080 px per card.  Requires Pillow.

Fonts (from FONTS_DIR, default /app/fonts):
  Korean/Latin : Pretendard-Bold.otf / Pretendard-Regular.otf
  Chinese      : PingFangSC-Regular.ttf

Cards:
  1. Cover          – dark bg, summary counts
  2. Stats          – cream bg, monthly + YoY + YTD tables
  3. Import games   – dark navy bg, all import games
  4. Domestic games – cream bg, notable domestic games
  5. Closing        – red bg, import quota CTA
"""

from __future__ import annotations
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Palette ──────────────────────────────────────────────────────────────────
DARK_BG    = (13, 17, 23)
NAVY_BG    = (13, 27, 42)
CREAM_BG   = (248, 244, 232)
RED_BG     = (192, 38, 26)

BLUE       = (26, 171, 255)
GREEN      = (34, 204, 102)
RED_PILL   = (220, 50, 50)

WHITE      = (255, 255, 255)
OFF_WHITE  = (220, 222, 230)
LIGHT_GRAY = (155, 158, 175)
MID_GRAY   = (100, 102, 115)
DARK_BOX   = (22, 22, 28)
NAVY_BOX   = (18, 35, 62)

CREAM_BOX       = (238, 233, 218)
CREAM_OUTLINE   = (200, 192, 172)
CREAM_DARK      = (60,  52,  42)
CREAM_MID       = (100, 92,  72)
CREAM_LIGHT     = (140, 132, 112)

SIZE   = 1080
MARGIN = 72

MONTH_KR = ["", "1월", "2월", "3월", "4월", "5월", "6월",
             "7월", "8월", "9월", "10월", "11월", "12월"]
MONTH_EN = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
             "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# ── Font loading ──────────────────────────────────────────────────────────────
FONTS_DIR = Path(os.environ.get("FONTS_DIR", "/app/fonts"))

_KR_CACHE: dict = {}   # Korean / Latin  → Pretendard
_CN_CACHE: dict = {}   # Chinese         → PingFang SC


def _find_kr(bold: bool) -> str | None:
    """Pretendard for Korean + Latin text."""
    fname = "Pretendard-Bold.otf" if bold else "Pretendard-Regular.otf"
    candidates = [
        str(FONTS_DIR / fname),
        # fallback to NotoSansCJK if Pretendard not present
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _find_cn() -> str | None:
    """PingFang SC for Chinese text."""
    candidates = [
        str(FONTS_DIR / "PingFangSC-Regular.ttf"),
        str(FONTS_DIR / "PingFang Regular.otf"),
        # fallback to NotoSansCJK CJK coverage
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def F(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Korean / Latin font – Pretendard."""
    key = (size, bold)
    if key not in _KR_CACHE:
        path = _find_kr(bold)
        try:
            _KR_CACHE[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default()
        except Exception:
            _KR_CACHE[key] = ImageFont.load_default()
    return _KR_CACHE[key]


def FC(size: int) -> ImageFont.FreeTypeFont:
    """Chinese font – PingFang SC (Regular only)."""
    key = size
    if key not in _CN_CACHE:
        path = _find_cn()
        try:
            _CN_CACHE[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default()
        except Exception:
            _CN_CACHE[key] = ImageFont.load_default()
    return _CN_CACHE[key]


# ── PIL helpers ───────────────────────────────────────────────────────────────
def new_card(bg: tuple) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (SIZE, SIZE), bg)
    return img, ImageDraw.Draw(img)


def tw(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    bb = draw.textbbox((0, 0), text, font=fnt)
    return bb[2] - bb[0]


def th(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    bb = draw.textbbox((0, 0), text, font=fnt)
    return bb[3] - bb[1]


def T(draw, text, x, y, fnt, fill, anchor="lt"):
    draw.text((x, y), text, font=fnt, fill=fill, anchor=anchor)


def RR(draw, x1, y1, x2, y2, r=12, fill=None, outline=None, ow=2):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill,
                            outline=outline, width=ow)


def dot_grid(draw, bg):
    """Subtle dot texture."""
    dot_color = tuple(min(255, c + 18) for c in bg)
    for gx in range(0, SIZE, 56):
        for gy in range(0, SIZE, 56):
            draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=dot_color)


def page_num(draw, n: int, total: int, dark: bool):
    txt = f"{n:02d} / {total:02d}"
    fnt = F(26)
    col = LIGHT_GRAY if dark else CREAM_LIGHT
    tw_ = tw(draw, txt, fnt)
    T(draw, txt, SIZE - MARGIN - tw_, MARGIN, fnt, col)


def header(draw, label: str, n: int, dark: bool, accent=BLUE):
    """Top-left: accent line + label.  Top-right: page number."""
    lc = accent if dark else CREAM_MID
    draw.rectangle([MARGIN, MARGIN, MARGIN + 44, MARGIN + 4], fill=accent)
    T(draw, label, MARGIN, MARGIN + 16, F(24), lc)
    page_num(draw, n, 5, dark)


def pill(draw, x, y, text, fnt, bg=None, outline=BLUE, tc=BLUE, px=16, py=8):
    """Return (x_advance, height)."""
    tw_ = tw(draw, text, fnt)
    th_ = th(draw, text, fnt)
    w = tw_ + px * 2
    h = th_ + py * 2
    RR(draw, x, y, x + w, y + h, r=h // 2, fill=bg, outline=outline, ow=2)
    T(draw, text, x + px, y + py, fnt, tc)
    return w + 10, h


def sep(draw, y: int, col, w: int = 1):
    draw.line([(MARGIN, y), (SIZE - MARGIN, y)], fill=col, width=w)


# ── Card 1 — Cover ────────────────────────────────────────────────────────────
def card_cover(year: int, month: int,
               import_cnt: int, domestic_cnt: int, change_cnt: int) -> Image.Image:
    img, draw = new_card(DARK_BG)
    dot_grid(draw, DARK_BG)

    # Ghost month digit (background watermark)
    gfnt = F(400, bold=True)
    ghost = str(month)
    gw = tw(draw, ghost, gfnt)
    T(draw, ghost, SIZE - MARGIN - gw + 40, SIZE // 2 - 120, gfnt, (18, 34, 68))

    # Header
    header(draw, "CHINA GAME MARKET", 1, dark=True, accent=BLUE)

    # Count pills
    pill_fnt = F(28)
    tags = [f"수입 {import_cnt}종", f"국산 {domestic_cnt}종", f"자격변경 {change_cnt}건"]
    px = MARGIN
    py = MARGIN + 66
    for tag in tags:
        adv, _ = pill(draw, px, py, tag, pill_fnt, bg=None, outline=BLUE, tc=BLUE)
        px += adv

    # Title block
    ty = 560
    T(draw, "NPPA  판호 승인 현황", MARGIN, ty, F(26), LIGHT_GRAY)
    T(draw, f"{year}년", MARGIN, ty + 48, F(82, bold=True), WHITE)
    T(draw, MONTH_KR[month], MARGIN, ty + 138, F(82, bold=True), BLUE)
    T(draw, "판호 리포트", MARGIN, ty + 228, F(82, bold=True), WHITE)

    total = import_cnt + domestic_cnt
    T(draw, f"발표일 {year}년 {month}월  ·  총 {total}종 승인",
      MARGIN, ty + 330, F(26), LIGHT_GRAY)

    # Footer
    fy = SIZE - MARGIN - 14
    draw.line([(MARGIN, fy - 22), (MARGIN + 52, fy - 22)], fill=WHITE, width=2)
    T(draw, f"SHANGHAI GIPPIE  ·  {MONTH_EN[month]} {year}",
      MARGIN, fy, F(24), MID_GRAY)
    return img


# ── Card 2 — Stats ────────────────────────────────────────────────────────────
def card_stats(year: int, month: int,
               import_cnt: int, domestic_cnt: int, change_cnt: int,
               ytd_import: int, ytd_domestic: int,
               mom_import: int | None = None,
               mom_domestic: int | None = None,
               yoy_import: int | None = None,
               yoy_domestic: int | None = None,
               ytd_import_prev: int | None = None,
               ytd_domestic_prev: int | None = None) -> Image.Image:
    img, draw = new_card(CREAM_BG)
    total = import_cnt + domestic_cnt
    prev_year = year - 1

    # "승인 현황" header box
    RR(draw, MARGIN, MARGIN, MARGIN + 132, MARGIN + 44, r=6,
       fill=None, outline=CREAM_OUTLINE, ow=2)
    T(draw, "승인 현황", MARGIN + 14, MARGIN + 9, F(26, bold=True), CREAM_MID)
    page_num(draw, 2, 5, dark=False)

    # Main title
    ty = MARGIN + 72
    T(draw, f"{month}월 판호 총 {total}종", MARGIN, ty, F(70, bold=True), CREAM_DARK)
    T(draw, f"자격변경 {change_cnt}건 포함", MARGIN, ty + 80, F(28), CREAM_LIGHT)

    # Two stat boxes
    by = ty + 130
    bh = 168
    bw = (SIZE - 2 * MARGIN - 14) // 2
    for i, (label, cnt, mom, accent) in enumerate([
        ("수입 게임", import_cnt, mom_import, BLUE),
        ("국산 게임", domestic_cnt, mom_domestic, GREEN),
    ]):
        bx = MARGIN + i * (bw + 14)
        RR(draw, bx, by, bx + bw, by + bh, r=14, fill=DARK_BOX)
        T(draw, label, bx + 18, by + 14, F(24), LIGHT_GRAY)
        T(draw, str(cnt), bx + 18, by + 42, F(72, bold=True), WHITE)
        T(draw, "종 승인", bx + 18, by + 116, F(24), LIGHT_GRAY)
        if mom is not None:
            sign = "▲" if mom >= 0 else "▼"
            mt = f"전월比 {sign}+{abs(mom)}종" if mom >= 0 else f"전월比 {sign}{abs(mom)}종"
            mc = accent if mom >= 0 else RED_PILL
            pfnt = F(22)
            pw = tw(draw, mt, pfnt) + 20
            px_ = bx + bw - pw - 10
            py_ = by + bh - 36
            RR(draw, px_, py_, px_ + pw, py_ + 28, r=12, fill=mc)
            T(draw, mt, px_ + 10, py_ + 4, pfnt, WHITE)

    # YoY section
    yoy_y = by + bh + 28
    sep(draw, yoy_y, CREAM_OUTLINE)
    T(draw, f"전년동월 비교  ·  {prev_year}년 {month}월",
      MARGIN, yoy_y + 10, F(23), CREAM_LIGHT)
    ry = yoy_y + 46
    rfnt = F(26)
    rbfnt = F(26, bold=True)
    for (emoji, cat, curr, prev) in [
        ("🌐", "수입 게임", import_cnt, yoy_import),
        ("🇨🇳", "국산 게임", domestic_cnt, yoy_domestic),
    ]:
        T(draw, f"{emoji}  {cat}", MARGIN, ry, rfnt, CREAM_MID)
        if prev is not None:
            pct = round((curr - prev) / max(prev, 1) * 100)
            sign = "▲" if pct >= 0 else "▼"
            pc = GREEN if pct >= 0 else RED_PILL
            base = f"{prev_year}년 {prev}종  →  "
            curr_txt = f"{year}년 {curr}종"
            pct_txt = f"   {sign}{abs(pct)}%"
            x0 = MARGIN + 240
            T(draw, base, x0, ry, rfnt, CREAM_LIGHT)
            x1 = x0 + tw(draw, base, rfnt)
            T(draw, curr_txt, x1, ry, rbfnt, CREAM_DARK)
            x2 = x1 + tw(draw, curr_txt, rbfnt)
            T(draw, pct_txt, x2, ry, rbfnt, pc)
        else:
            T(draw, f"{curr}종", SIZE - MARGIN - tw(draw, f"{curr}종", rbfnt), ry, rbfnt, CREAM_DARK)
        ry += 46

    # YTD section
    ytd_y = ry + 16
    sep(draw, ytd_y, CREAM_OUTLINE)
    T(draw, f"{year}년 1-{month}월 누적 발급수량",
      MARGIN, ytd_y + 10, F(23), CREAM_LIGHT)
    ytd_by = ytd_y + 46
    ytd_bh = 102
    ytd_bw = (SIZE - 2 * MARGIN - 22) // 3
    ytd_total = ytd_import + ytd_domestic
    prev_ytd_total = (ytd_import_prev or 0) + (ytd_domestic_prev or 0)

    for i, (cnt, lbl, prev) in enumerate([
        (ytd_import,   "수입게임", ytd_import_prev),
        (ytd_domestic, "국산게임", ytd_domestic_prev),
        (ytd_total,    "합계",    prev_ytd_total if (ytd_import_prev and ytd_domestic_prev) else None),
    ]):
        bx = MARGIN + i * (ytd_bw + 11)
        RR(draw, bx, ytd_by, bx + ytd_bw, ytd_by + ytd_bh, r=10,
           fill=CREAM_BOX, outline=CREAM_OUTLINE, ow=1)
        cc = BLUE if i == 0 else CREAM_DARK
        T(draw, str(cnt), bx + ytd_bw // 2, ytd_by + 10,
          F(46, bold=True), cc, anchor="mt")
        T(draw, lbl, bx + ytd_bw // 2, ytd_by + 62,
          F(22), CREAM_MID, anchor="mt")
        if prev is not None and prev > 0:
            pct = round((cnt - prev) / max(prev, 1) * 100)
            sign = "▲" if pct >= 0 else "▼"
            pc = GREEN if pct >= 0 else RED_PILL
            T(draw, f"{prev_year}比 {sign}{abs(pct)}%",
              bx + ytd_bw // 2, ytd_by + 82, F(20), pc, anchor="mt")

    # Footer note
    if ytd_import_prev and ytd_domestic_prev:
        note_y = ytd_by + ytd_bh + 14
        draw.line([(MARGIN, note_y + 8), (MARGIN + 24, note_y + 8)],
                  fill=CREAM_LIGHT, width=2)
        note = (f"  {prev_year}년 Jan-{MONTH_EN[month]} 누적: "
                f"국산 {ytd_domestic_prev}종 · 수입 {ytd_import_prev}종 (NPPA 공식 발표)")
        T(draw, note, MARGIN + 24, note_y, F(20), CREAM_LIGHT)

    return img


# ── Card 3 — Import games ─────────────────────────────────────────────────────
def card_import(year: int, month: int, games: list[dict]) -> Image.Image:
    img, draw = new_card(NAVY_BG)
    dot_grid(draw, NAVY_BG)

    header(draw, "수입게임 판호 현황", 3, dark=True, accent=BLUE)

    cy = MARGIN + 72

    if not games:
        T(draw, "이번 달 수입 게임 승인 없음", MARGIN, cy, F(32), LIGHT_GRAY)
        return img

    # Total count banner
    cnt_fnt = F(36, bold=True)
    banner_txt = f"2026년 {month}월  수입 승인 게임  {len(games)}종"
    T(draw, banner_txt, MARGIN, cy, cnt_fnt, WHITE)
    cy += 52

    sep(draw, cy, (40, 62, 95), w=1)
    cy += 18

    # Column headers
    hdr_fnt = F(23)
    COL_X    = [MARGIN, MARGIN + 310, MARGIN + 620, MARGIN + 840]
    COL_HDR  = ["게임명 (중문)", "출판사", "운영사", "승인일"]
    for hx, hl in zip(COL_X, COL_HDR):
        T(draw, hl, hx, cy, hdr_fnt, MID_GRAY)
    cy += 32

    sep(draw, cy, (40, 62, 95))
    cy += 12

    row_fnt    = FC(26)   # Chinese game names / company names
    row_fnt_sm = FC(22)   # smaller Chinese (date)
    for i, game in enumerate(games):
        if cy > SIZE - MARGIN - 50:
            T(draw, f"… 외 {len(games) - i}종", MARGIN, cy, F(24), LIGHT_GRAY)
            break
        name = (game.get("名称") or "")[:14]
        pub  = (game.get("出版单位") or "")[:10]
        ops  = (game.get("运营单位") or "")[:10]
        date = (game.get("批准时间") or "")[-9:]  # e.g. "2026年01月" portion

        # Alternate row shade
        if i % 2 == 0:
            RR(draw, MARGIN - 4, cy - 4, SIZE - MARGIN + 4, cy + 32, r=6,
               fill=(18, 38, 65))

        T(draw, name, COL_X[0], cy, row_fnt,    WHITE)
        T(draw, pub,  COL_X[1], cy, row_fnt,    LIGHT_GRAY)
        T(draw, ops,  COL_X[2], cy, row_fnt,    LIGHT_GRAY)
        T(draw, date, COL_X[3], cy, row_fnt_sm, MID_GRAY)
        cy += 40

    return img


# ── Card 4 — Domestic games ───────────────────────────────────────────────────
def card_domestic(year: int, month: int, games: list[dict]) -> Image.Image:
    img, draw = new_card(CREAM_BG)
    header(draw, "국산 게임 주목작", 4, dark=False, accent=BLUE)

    cy = MARGIN + 70

    total = len(games)
    T(draw, f"{year}년 {month}월  국산 게임  {total}종 승인",
      MARGIN, cy, F(36, bold=True), CREAM_DARK)
    cy += 56

    sep(draw, cy, CREAM_OUTLINE)
    cy += 18

    # 2-column name grid
    col_w = (SIZE - 2 * MARGIN - 24) // 2
    rfnt = FC(26)   # Chinese game names
    MAX_ROWS = 18
    for i, game in enumerate(games[:MAX_ROWS * 2]):
        name = (game.get("名称") or "")[:16]
        col = i % 2
        row = i // 2
        gx = MARGIN + col * (col_w + 24)
        gy = cy + row * 40
        if gy > SIZE - MARGIN - 60:
            rem = total - i
            T(draw, f"… 외 {rem}종", gx, gy, F(23), CREAM_LIGHT)
            break

        # Circle bullet
        bx, by_ = gx + 6, gy + 10
        draw.ellipse([bx, by_, bx + 9, by_ + 9], fill=BLUE)
        T(draw, name, gx + 22, gy, rfnt, CREAM_DARK)

        # Light separator every row change
        if col == 1 and row < MAX_ROWS - 1:
            sep_y = gy + 36
            draw.line([(MARGIN, sep_y), (SIZE - MARGIN, sep_y)],
                      fill=CREAM_OUTLINE, width=1)

    # Footer note
    T(draw, f"총 {total}종 · NPPA 공식 발표",
      MARGIN, SIZE - MARGIN - 28, F(22), CREAM_LIGHT)

    return img


# ── Card 5 — Closing ──────────────────────────────────────────────────────────
def card_closing(year: int, month: int,
                 ytd_import: int, import_cnt: int) -> Image.Image:
    img, draw = new_card(RED_BG)
    header(draw, "FOR GLOBAL STUDIOS", 5, dark=True, accent=WHITE)

    cy = MARGIN + 72

    # Quota info box
    dark_red = (155, 28, 18)
    RR(draw, MARGIN, cy, SIZE - MARGIN, cy + 82, r=12, fill=dark_red)
    T(draw, f"{ytd_import}종", MARGIN + 22, cy + 10, F(50, bold=True), WHITE)
    T(draw, f"{year}년 1-{month}월 수입 판호 소진",
      MARGIN + 22, cy + 56, F(25), (255, 195, 185))
    note = "연간 발급 총량은 정해져 있습니다"
    T(draw, note, SIZE - MARGIN - tw(draw, note, F(25)) - 22, cy + 56, F(25), (255, 180, 170))
    cy += 100

    # CTA headline
    T(draw, "남은 수량,",      MARGIN, cy,       F(80, bold=True), WHITE)
    T(draw, "지금 확보하세요", MARGIN, cy + 84,  F(80, bold=True), WHITE)
    cy += 186

    # Description block
    accent_bar_top = cy
    desc_lines = [
        ("중국 수입 판호는 연간 총량이 한정됩니다.", False, (255, 210, 200)),
        ("하반기로 갈수록 경쟁은 치열해지고",         True,  WHITE),
        ("남은 슬롯은 줄어듭니다.",                   True,  WHITE),
        ("빠른 준비가 시장 진입의 첫 번째 우위입니다.", False, (255, 210, 200)),
    ]
    for line, bold_, col in desc_lines:
        T(draw, line, MARGIN + 18, cy, F(27, bold=bold_), col)
        cy += 38
    # Left accent bar
    draw.rectangle([MARGIN, accent_bar_top - 2, MARGIN + 4, cy + 2], fill=WHITE)

    # Contact section
    contact_y = SIZE - MARGIN - 164
    sep(draw, contact_y, (218, 75, 65), w=1)
    T(draw, "문의  ·  SHANGHAI GIPPIE", MARGIN, contact_y + 12, F(22), (255, 205, 195))

    sns_y = contact_y + 48
    sns = [
        ("INSTAGRAM", "@gippie_sh"),
        ("THREADS",   "@gippie_sh"),
        ("FACEBOOK",  "Shanghai Gippie"),
        ("LINKEDIN",  "Shanghai Gippie"),
    ]
    sw = (SIZE - 2 * MARGIN - 14) // 2
    sh = 48
    for i, (platform, handle) in enumerate(sns):
        sx = MARGIN + (i % 2) * (sw + 14)
        sy = sns_y + (i // 2) * (sh + 8)
        RR(draw, sx, sy, sx + sw, sy + sh, r=8, fill=dark_red)
        T(draw, platform, sx + 14, sy + 10, F(22), (255, 195, 185))
        T(draw, handle, sx + sw - tw(draw, handle, F(22, bold=True)) - 14,
          sy + 10, F(22, bold=True), WHITE)

    return img


# ── Public API ────────────────────────────────────────────────────────────────
def generate_cards(
    year: int,
    month: int,
    results: dict,
    ytd: dict,
    comparison: dict | None = None,
    output_dir: str | Path | None = None,
) -> list[str]:
    """
    Generate all 5 cards.  Returns list of saved PNG paths.

    comparison (optional):
      mom_import, mom_domestic  – month-over-month delta (int)
      yoy_import, yoy_domestic  – same-month previous year count (int)
      ytd_import_prev, ytd_domestic_prev – YTD previous year (int)
    """
    if output_dir is None:
        output_dir = Path("/app/data/cards")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    imp  = results.get("import")   or {}
    dom  = results.get("domestic") or {}
    chg  = results.get("change")   or {}
    cmp  = comparison or {}

    ic = imp.get("count", 0)
    dc = dom.get("count", 0)
    cc = chg.get("count", 0)

    cards_imgs = [
        card_cover(year, month, ic, dc, cc),
        card_stats(
            year, month, ic, dc, cc,
            ytd.get("import", 0), ytd.get("domestic", 0),
            mom_import     = cmp.get("mom_import"),
            mom_domestic   = cmp.get("mom_domestic"),
            yoy_import     = cmp.get("yoy_import"),
            yoy_domestic   = cmp.get("yoy_domestic"),
            ytd_import_prev  = cmp.get("ytd_import_prev"),
            ytd_domestic_prev = cmp.get("ytd_domestic_prev"),
        ),
        card_import(year, month, imp.get("games", [])),
        card_domestic(year, month, dom.get("games", [])),
        card_closing(year, month, ytd.get("import", 0), ic),
    ]

    paths = []
    for idx, img in enumerate(cards_imgs, 1):
        p = output_dir / f"cn-isbn-{year}{month:02d}-card{idx}.png"
        img.save(str(p), "PNG", optimize=True)
        paths.append(str(p))

    return paths
