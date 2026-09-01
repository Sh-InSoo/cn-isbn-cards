import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self, state_file: Path):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"State file read error: {e}, starting fresh")
        return {"sent": [], "checked": {}}

    def _save(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def already_sent(self, year_month: str) -> bool:
        """Returns True if we already sent a report for this year_month (e.g. '202505')"""
        return year_month in self._data.get("sent", [])

    def mark_sent(self, year_month: str):
        sent = self._data.setdefault("sent", [])
        if year_month not in sent:
            sent.append(year_month)
        self._save()
        logger.info(f"Marked {year_month} as sent")

    def get_ytd_counts(self, year: int) -> dict:
        """Return cached YTD counts for the year"""
        return self._data.get("ytd", {}).get(str(year), {})

    def save_ytd_counts(self, year: int, counts: dict):
        self._data.setdefault("ytd", {})[str(year)] = counts
        self._save()
