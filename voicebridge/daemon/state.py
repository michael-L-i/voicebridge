import json

from voicebridge.config import CONFIG_DIR

SESSIONS_DIR = CONFIG_DIR / "sessions"


class SessionState:
    """Per-session spoken-summary history, so a follow-up voice_speak call can
    naturally reference what was already said earlier in the conversation."""

    def __init__(self, state_key: str):
        self.state_key = state_key
        self.path = SESSIONS_DIR / f"{state_key.replace('/', '_')}.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except json.JSONDecodeError:
                pass
        return {"summaries": []}

    def _save(self) -> None:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data))

    @property
    def prior_summaries(self) -> list[str]:
        return self._data.get("summaries", [])

    def record_summary(self, spoken_text: str, keep: int) -> None:
        summaries = self._data.get("summaries", [])
        summaries.append(spoken_text)
        self._data["summaries"] = summaries[-keep:]
        self._save()
