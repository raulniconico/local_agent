"""The once-daily crawl trigger, decoupled from request traffic.

`specs/legal.md` §3.4 and `specs/legal-android.md` rule 23 both require the
catalogue/news crawl to run on a fixed daily schedule, not in response to
whichever request happens to find a stale cache. This is that schedule: one
background thread that sleeps until a randomised minute inside 03:30-05:00
Europe/Paris, then calls the same `crawler.catalogue()`/`crawler.news()` the
read endpoints call. It does not change what is crawled or whether crawling
is permitted -- `CRAWLER_ENABLED` and the per-domain allowlist in
`crawler.py` still gate every request exactly as before.
"""

import logging
import random
import threading
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import config
import crawler

logger = logging.getLogger("server.scheduler")

_PARIS = ZoneInfo("Europe/Paris")
_WINDOW_START_MINUTE = 3 * 60 + 30  # 03:30
_WINDOW_END_MINUTE = 5 * 60  # 05:00

_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None


def _next_run_at(now: datetime) -> datetime:
    """A randomised minute inside today's 03:30-05:00 window, or tomorrow's
    if that window has already passed -- the randomisation is rule 18's
    "no recognisable drumbeat" concern applied to the daily schedule itself,
    not just the per-request delay."""
    minute_of_day = random.randint(_WINDOW_START_MINUTE, _WINDOW_END_MINUTE)
    candidate = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=minute_of_day)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _run_once() -> None:
    for name, fn in (("catalogue", crawler.catalogue), ("news", crawler.news)):
        try:
            fn()
            logger.info("scheduled %s refresh completed", name)
        except crawler.CrawlerUnavailableError as exc:
            # Not an error worth an alert: an empty allowlist, or a run
            # that hit its budget, is the crawler behaving as designed.
            logger.warning("scheduled %s refresh skipped: %s", name, exc)


def _run_loop() -> None:
    while not _stop_event.is_set():
        now = datetime.now(_PARIS)
        target = _next_run_at(now)
        wait_seconds = (target - now).total_seconds()
        logger.info("next scheduled crawl at %s (in %.0f min)", target.isoformat(), wait_seconds / 60)
        if _stop_event.wait(wait_seconds):
            return
        _run_once()


def start() -> None:
    """No-op when the crawler is disabled -- there is nothing to schedule,
    and starting a thread that only ever hits CrawlerUnavailableError would
    just be a confusing log line once a day."""
    global _thread
    if not config.CRAWLER_ENABLED:
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_run_loop, name="crawler-scheduler", daemon=True)
    _thread.start()
    logger.info("crawler scheduler started (daily window 03:30-05:00 Europe/Paris)")


def stop() -> None:
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=5)