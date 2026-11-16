"""In-memory live event feed for the dashboard. Also mirrored to the server log."""

import logging
import threading
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger("evorium.live")
_lock = threading.Lock()
_events: deque = deque(maxlen=500)
_next_id = 1


def emit(text: str, level: str = "info") -> None:
    global _next_id
    with _lock:
        event = {"id": _next_id, "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"), "level": level, "text": text}
        _next_id += 1
        _events.append(event)
    (logger.warning if level == "error" else logger.info)(text)


def since(event_id: int) -> list[dict]:
    with _lock:
        return [e for e in _events if e["id"] > event_id]
