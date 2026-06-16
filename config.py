import os
from pathlib import Path

BASE_DIR = Path(os.environ.get("APP_BASE_DIR", "/app"))


class Config:
    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "#cn-isbn")

    STATE_FILE = BASE_DIR / "data" / "state.json"
    LOG_FILE   = BASE_DIR / "logs" / "cn-isbn.log"
    DATA_DIR   = BASE_DIR / "data"
    CARDS_DIR  = BASE_DIR / "data" / "cards"

    # GitHub handoff via HTTPS (the NAS has no git):
    #   push  scrape JSON     → GitHub Contents API (needs GITHUB_TOKEN, contents:write)
    #   pull  editorial JSON  → public raw read (no auth needed)
    GITHUB_REPO   = os.environ.get("GITHUB_REPO", "Sh-InSoo/cn-isbn-cards")
    GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
    GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")

    NPPA_BASE = "https://www.nppa.gov.cn"
    NPPA_URLS = {
        "import":   "https://www.nppa.gov.cn/bsfw/jggs/yxspjg/jkwlyxspxx/",
        "domestic": "https://www.nppa.gov.cn/bsfw/jggs/yxspjg/gcwlyxspxx/",
        "change":   "https://www.nppa.gov.cn/bsfw/jggs/yxspjg/yxspbgxx/",
    }

    CATEGORY_LABELS = {
        "import":   "进口网络游戏审批信息",
        "domestic": "国产网络游戏审批信息",
        "change":   "游戏审批变更信息",
    }

    START_DAY = 22

    @classmethod
    def validate(cls):
        if not cls.SLACK_BOT_TOKEN:
            raise EnvironmentError("Missing env var: SLACK_BOT_TOKEN")
