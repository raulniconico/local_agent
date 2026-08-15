"""The crawl triggers, decoupled from request traffic.

`specs/legal.md` §3.4 and `specs/legal-android.md` rule 23 both require the
crawl to run on a fixed schedule, not in response to whichever request happens
to find a stale cache. This is that schedule. It does not change *what* is
crawled or *whether* crawling is permitted -- `CRAWLER_ENABLED` and the
per-domain allowlist in `crawler.py` still gate every request exactly as
before, and both are unmet today.

TWO CADENCES, NOT ONE, since 2026-08-15:

  * the **catalogue** keeps legal.md rule 15's schedule verbatim -- once daily,
    a randomised minute inside 03:30-05:00 Europe/Paris. Nothing about that
    changed and nothing here should change it;
  * the **news feeds** poll hourly, on a product decision.

>>> SPEC DIVERGENCE, READ BEFORE ENABLING THE CRAWLER. <<<

legal.md rule 15's rate-limit table says "Schedule: once daily" without
distinguishing catalogue crawling from feed polling, so hourly news is a
divergence from a binding document, not an interpretation of it. It is
recorded here rather than quietly taken:

  * WHY IT IS ARGUABLE. Rule 19 already requires conditional requests, and
    `_refresh_news` now sends `If-None-Match`/`If-Modified-Since` through the
    same `Fetcher` as everything else (it previously used a bare client and
    sent neither). An unchanged feed answers `304` in ~200 bytes and is never
    parsed. Twenty-four conditional polls of one feed is a fraction of rule
    15's own 250-request-per-run budget and far less traffic than the single
    catalogue crawl in the same day. Feeds are also the one resource on a
    site *designed* to be polled.
  * WHY IT IS STILL A DIVERGENCE. "Once daily" is what the table says, the
    rule 16 note is explicit that the caps exist to contain bugs rather than
    to be approached, and the `+URL` bot page promised by rule 17 states an
    update frequency to the public that must match reality. RUBRIC's
    `update_frequency` in `crawler.py` also still reads "Once daily" and
    describes the catalogue.
  * WHAT TO DO ABOUT IT. Before `CRAWLER_ENABLED` is ever turned on, either
    amend legal.md rule 15 to name the feed cadence separately, or set
    `NEWS_INTERVAL_SECONDS=86400` and revert `NEWS_TTL_SECONDS` to match. Do
    not resolve this by leaving it undiscussed. Nothing goes out today either
    way -- the allowlist is empty and the crawler is disabled.
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

#: How often the news feeds are polled. See the divergence note above.
NEWS_INTERVAL_SECONDS = int(getattr(config, "NEWS_TTL_SECONDS", 3600))

_stop_event = threading.Event()
_threads: list[threading.Thread] = []


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


def _refresh(name: str, fn) -> None:
    try:
        fn()
        logger.info("scheduled %s refresh completed", name)
    except crawler.CrawlerUnavailableError as exc:
        # Not an error worth an alert: an empty allowlist, or a run that hit
        # its budget, is the crawler behaving as designed.
        logger.warning("scheduled %s refresh skipped: %s", name, exc)
    except Exception:  # noqa: BLE001
        # A scheduler thread that dies takes the cadence with it silently,
        # which is worse than a logged traceback and a retry next interval.
        logger.exception("scheduled %s refresh raised", name)


def _catalogue_loop() -> None:
    while not _stop_event.is_set():
        now = datetime.now(_PARIS)
        target = _next_run_at(now)
        wait_seconds = (target - now).total_seconds()
        logger.info("next catalogue crawl at %s (in %.0f min)", target.isoformat(), wait_seconds / 60)
        if _stop_event.wait(wait_seconds):
            return
        _refresh("catalogue", crawler.catalogue)


def _news_loop() -> None:
    # Refresh once at startup so the first client to ask is not served an
    # empty feed for up to an hour, then settle into the interval. The jitter
    # is rule 18's drumbeat concern again: a fixed :00 poll across every
    # deployment is a recognisable pattern in someone's access log.
    while not _stop_event.is_set():
        _refresh("news", crawler.news)
        jitter = random.uniform(0, min(300, NEWS_INTERVAL_SECONDS * 0.1))
        if _stop_event.wait(NEWS_INTERVAL_SECONDS + jitter):
            return


def start() -> None:
    """No-op when the crawler is disabled -- there is nothing to schedule,
    and starting threads that only ever hit CrawlerUnavailableError would
    just be confusing log lines."""
    if not config.CRAWLER_ENABLED:
        return
    _stop_event.clear()
    _threads.clear()
    for name, target in (("crawler-scheduler", _catalogue_loop), ("news-scheduler", _news_loop)):
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
        _threads.append(thread)
    logger.info(
        "crawler scheduler started (catalogue: daily 03:30-05:00 Europe/Paris; "
        "news: every %.0f min)",
        NEWS_INTERVAL_SECONDS / 60,
    )


def stop() -> None:
    _stop_event.set()
    for thread in _threads:
        thread.join(timeout=5)
    _threads.clear()
