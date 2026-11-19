"""One process-wide pause for provider outages, shared by every model caller."""
import threading
import time
from datetime import datetime, timezone
from evorium.events import emit

_lock = threading.RLock()
_until = 0
_failures = 0


def reset():
    global _until, _failures
    _until = 0
    _failures = 0


def paused():
    return time.time() < _until


def until():
    return datetime.fromtimestamp(_until, timezone.utc).isoformat() if paused() else None


def failed(exc):
    global _until, _failures
    if 'budget cap' in str(exc).lower() or 'balance' in str(exc).lower():
        return
    with _lock:
        if paused():
            return
        _failures += 1
        minutes = min(15, 2 ** min(_failures - 1, 4))
        _until = time.time() + minutes * 60
        emit(f"DeepSeek isn't answering; trying again in {minutes} {'minute' if minutes == 1 else 'minutes'}.", 'error')


def succeeded():
    global _until, _failures
    with _lock:
        if _failures:
            emit('DeepSeek is answering again.')
        _until = 0
        _failures = 0
