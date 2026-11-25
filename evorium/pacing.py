"""UK wall-clock allowance for autonomous DeepSeek spending."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from evorium.db import connect

UK = ZoneInfo('Europe/London')
AUTO_SHARE = Decimal('.70')
BACKGROUND_SHARE = Decimal('.20')  # Part of the auto allowance, for planning, reactions and narration.
# Relative weights. The three evening hours have the largest hourly allowance.
BANDS = ((0, 7, 5), (7, 12, 15), (12, 17, 20), (17, 19, 12),
         (19, 22, 32), (22, 23, 6), (23, 24, 5))
TOTAL_WEIGHT = sum(weight for _, _, weight in BANDS)
RECENT_CONVERSATIONS = 12
DEFAULT_CONVERSATION_USD = Decimal('.004')
scope = ContextVar('budget_scope', default='player')
conversation_id = ContextVar('budget_conversation', default=None)


@contextmanager
def spending(kind):
    token = scope.set(kind)
    try:
        yield
    finally:
        scope.reset(token)


@contextmanager
def tracking(cid):
    token = conversation_id.set(cid)
    try:
        yield
    finally:
        conversation_id.reset(token)


def stamp(at):
    return at.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _boundary(day, hour):
    return (datetime.combine(day, time.min, UK) + timedelta(hours=hour)).astimezone(timezone.utc)


def day_bounds(at):
    day = at.astimezone(UK).date()
    return stamp(_boundary(day, 0)), stamp(_boundary(day, 24))


def _window(at):
    local = at.astimezone(UK)
    elapsed = 0
    for start_hour, end_hour, weight in BANDS:
        if local.hour < end_hour:
            start, end = (_boundary(local.date(), h) for h in (start_hour, end_hour))
            progress = Decimal(str((at - start).total_seconds())) / Decimal(str((end - start).total_seconds()))
            return start, Decimal(elapsed), progress * weight
        elapsed += weight


def planned(at, cap):
    _, previous, current = _window(at)
    return Decimal(str(cap)) * AUTO_SHARE * (previous + current) / TOTAL_WEIGHT


def available(c, at, cap, kind):
    """Amount still available for this type of autonomous work in the current window."""
    cap = Decimal(str(cap))
    start, end = day_bounds(at)
    band, previous, accrued = _window(at)
    evening = 17 <= at.astimezone(UK).hour < 23
    window_start = start if evening else stamp(band)
    quota = cap * AUTO_SHARE * (accrued + (previous if evening else 0)) / TOTAL_WEIGHT
    overall = current = background = Decimal(0)
    for row in c.execute(
        """SELECT budget_scope, est_cost_usd, created_at FROM llm_calls
           WHERE created_at>=? AND created_at<? AND budget_scope!='player'""", (start, end)
    ):
        cost = Decimal(str(row['est_cost_usd']))
        overall += cost
        if row['created_at'] >= window_start:
            current += cost
            if row['budget_scope'] == 'background':
                background += cost
    left = min(cap * AUTO_SHARE - overall, planned(at, cap) - overall, quota - current)
    if kind == 'background':
        left = min(left, quota * BACKGROUND_SHARE - background)
    return max(Decimal(0), left)


def conversation_estimate(c, at, turns, peak):
    """Use recent paid dialogue and notes, normalized to an off-peak per-request cost."""
    rows = c.execute(
        """SELECT l.est_cost_usd, l.created_at FROM llm_calls l JOIN conversations v ON l.conversation_id=v.id
           WHERE l.budget_scope='auto' AND v.status='completed' AND v.id IN (
               SELECT id FROM conversations WHERE status='completed' AND id IN (
                   SELECT conversation_id FROM llm_calls WHERE budget_scope='auto'
               ) ORDER BY id DESC LIMIT ?
           ) AND l.est_cost_usd>0""", (RECENT_CONVERSATIONS,)
    ).fetchall()
    typical = sum((Decimal(str(row['est_cost_usd'])) / (2 if peak(datetime.fromisoformat(row['created_at'])) else 1)
                   for row in rows), Decimal(0)) / len(rows) if rows else DEFAULT_CONVERSATION_USD / 5
    return typical * (turns + 1) * (2 if peak(at) else 1)
