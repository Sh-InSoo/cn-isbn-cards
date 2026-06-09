import os
from pathlib import Path

BASE_DIR = Path(os.environ.get("APP_BASE_DIR", "/app"))


class Config:
    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "#cn-isbn")

    STATE_FILE = BASE_DIR / "data" / "state.json"
    LOG_FILE   = BASE_DIR / "logs" / "cn-isbn.log"
    CARDS_DIR  = BASE_DIR / "data" / "cards"

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
