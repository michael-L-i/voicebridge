import json
import time
from pathlib import Path

from voicebridge.config import CONFIG_DIR

SESSIONS_DIR = CONFIG_DIR / "sessions"


class SessionState:
    """Per-session persisted state: transcript offset, spoken-summary history,
    and the voice_active TTL flag (set by voice_speak/voice_listen in M4;
    always false until then)."""

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
        return {"last_offset": 0, "summaries": [], "voice_active_until": 0}

    def _save(self) -> None:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data))

    @property
    def last_offset(self) -> int:
        return self._data.get("last_offset", 0)

    @property
    def prior_summaries(self) -> list[str]:
        return self._data.get("summaries", [])

    @property
    def voice_active(self) -> bool:
        return time.time() < self._data.get("voice_active_until", 0)

    def mark_voice_active(self, ttl_seconds: float = 300) -> None:
        self._data["voice_active_until"] = time.time() + ttl_seconds
        self._save()

    def advance_offset_only(self, new_offset: int) -> None:
        """Record that these transcript lines were considered (even if we
        decided not to narrate them), so a skipped turn isn't re-read and
        re-judged forever."""
        self._data["last_offset"] = new_offset
        self._save()

    def record_narration(self, new_offset: int, spoken_text: str, keep: int) -> None:
        self._data["last_offset"] = new_offset
        self._append_summary(spoken_text, keep)

    def record_summary(self, spoken_text: str, keep: int) -> None:
        """Like record_narration but for voice_speak, which has no transcript
        offset of its own -- still shares the same continuity history so
        narration and active voice_speak calls reference each other naturally."""
        self._append_summary(spoken_text, keep)

    def _append_summary(self, spoken_text: str, keep: int) -> None:
        summaries = self._data.get("summaries", [])
        summaries.append(spoken_text)
        self._data["summaries"] = summaries[-keep:]
        self._save()
