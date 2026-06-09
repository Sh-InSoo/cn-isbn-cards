"""
slack_client.py
Sends the cn-isbn monthly report to a Slack channel.
Requires: slack_sdk, SLACK_BOT_TOKEN with chat:write + files:write scopes.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

CATEGORY_META = {
    "import":   (":inbox_tray:",              "进口网络游戏 · 수입 게임 판호"),
    "domestic": (":flag-cn:",                 "国产网络游戏 · 국산 게임 판호"),
    "change":   (":arrows_counterclockwise:", "游戏审批变更 · 판호 변경"),
}

MAX_GAMES_LISTED = 20


class SlackClient:
    def __init__(self, token: str, channel: str):
        self.client = WebClient(token=token, timeout=300)
        self.channel = channel

    # ── Text report ───────────────────────────────────────────────────────────
    def send_report(self, year: int, month: int, results: dict, ytd: dict):
        lines = [
            f":bar_chart:  *{year}년 {month}월 중국 판호(ISBN) 월간 리포트*",
            "─" * 50,
        ]

        for category in ("import", "domestic", "change"):
            data = results.get(category) or {}
            emoji, title = CATEGORY_META[category]
            count = data.get("count", 0)
            url = data.get("url", "")
            ytd_n = ytd.get(category, 0)

            lines.append("")
            lines.append(f"{emoji} *[{title}]*")
            lines.append(f"• 이번 달: *{count}건*   |   YTD: *{ytd_n}건*")
            if url:
                lines.append(f"• 원문: {url}")

            games = data.get("games", [])
            if games:
                names = [self._game_name(g) for g in games[:MAX_GAMES_LISTED]]
                names = [n for n in names if n]
                if names:
                    lines.append("```")
                    lines.extend(f"- {n}" for n in names)
                    if len(games) > MAX_GAMES_LISTED:
                        lines.append(f"... (총 {len(games)}건 중 {MAX_GAMES_LISTED}건 표시)")
                    lines.append("```")
            lines.append("─" * 50)

        body = "\n".join(lines)

        try:
            result = self.client.chat_postMessage(
                channel=self.channel,
                text=body,
                mrkdwn=True,
            )
            logger.info(f"Text report posted to {self.channel} (ts={result['ts']})")
        except SlackApiError as e:
            logger.error(f"Slack text report failed: {e.response['error']}")
            raise

    # ── Instagram card images ─────────────────────────────────────────────────
    def upload_cards(self, year: int, month: int, card_paths: list[str]):
        """Upload 5 card images as a single grouped Slack message."""
        if not card_paths:
            logger.warning("No card paths provided — skipping upload")
            return

        initial_comment = (
            f":frame_with_picture:  *{year}년 {month}월 중국 판호 인스타 리포트 (5장)*\n"
            f"NPPA 수입 · 국산 · 변경 현황 카드뉴스 — @gippie_sh"
        )

        # Build file_uploads list
        file_uploads = []
        for i, path in enumerate(card_paths, 1):
            if not os.path.exists(path):
                logger.warning(f"Card {i} not found: {path}")
                continue
            file_uploads.append({
                "file": path,
                "filename": Path(path).name,
                "title": f"{year}년 {month}월 판호 리포트 {i:02d}/05",
            })

        if not file_uploads:
            logger.error("No valid card files found")
            return

        try:
            result = self.client.files_upload_v2(
                channel=self.channel,
                initial_comment=initial_comment,
                file_uploads=file_uploads,
                timeout=300,
            )
            logger.info(f"Uploaded {len(file_uploads)} cards to {self.channel}")
            return result
        except SlackApiError as e:
            logger.error(f"Card upload failed: {e.response['error']}")
            raise

    @staticmethod
    def _game_name(game: dict) -> str:
        for key in ("游戏名称", "名称", "游戏", "name", "Name"):
            if key in game and game[key]:
                return game[key]
        for v in game.values():
            if v:
                return v
        return ""
