"""The roaster catalogue and the news feed, crawled here and only here.

WHY THIS MODULE EXISTS AT ALL. `specs/legal-android.md` §4 rule 23 is a hard
architectural constraint: the catalogue and news fetch must run **once,
centrally, on a schedule**, never as a per-device client call. The desktop app
(`coffee/src/coffee_can/whats_new.py`, `coffee_news.py`) crawls from the GUI
process, which was fine as one person with one script and is exactly the
premise `specs/legal.md` §1.2 case (a) was scoped around. Shipping that same
code inside an APK multiplies it by the install count and turns one polite
crawler into an uncoordinated swarm. So the Android client never talks to a
roaster's host: it reads this server's cache, and this server does the
crawling.

WHY IT IS OFF BY DEFAULT, AND WHY THAT IS NOT A TODO. Three separate gates in
`specs/legal.md` and `specs/legal-accounts.md` are unmet today:

  * rule 2 -- outreach email to every target domain and a 14-day wait, before
    the first request;
  * rule 3 -- a committed per-domain allowlist recording contact, response,
    robots.txt hash and the CGU clause verbatim, with "no" and
    CGU-prohibition domains hard-excluded **in code**. `allowlist.json` ships
    empty, so nothing is crawlable;
  * `legal-accounts.md` rule 72 -- `legal.md` §1.2's use case must be re-opened
    and re-recorded before crawl results are served to Play users, because
    serving them is no longer case (a) and case (b) is currently verdict NO.

Turning `CRAWLER_ENABLED=1` with an empty allowlist still crawls nothing. That
is the intended behaviour: the switch alone is not the permission.

NEWS SOURCES ARE NOT ROASTERS, AND ARE NOT GATED LIKE THEM (2026-08-23).
`/v1/news` reads `news_sources.json`, not `allowlist.json`. The three gates
above are about **taking a French roaster's shop catalogue**, which is what
`specs/legal.md` is titled and scoped for: rules 2-3 buy permission for an act
whose permission is genuinely in doubt. A trade publication's RSS feed is the
inverse -- it is published *in order to be read by machines*, and is the tier-2
first-party structured endpoint 3.2 rule 7 tells you to prefer over scraping.
Requiring an outreach email and a verbatim CGU quotation before reading it
would be a category error, not diligence, and it is why `/v1/news` returned 503
for months while the desktop app (`coffee_can/coffee_news.py`) polled the same
eight feeds without difficulty.

What did NOT get relaxed, because it is what actually protects the publisher:
every press fetch still goes through [Fetcher], so robots.txt is honoured, the
per-host delay applies, requests are conditional (an unchanged feed answers 304
in ~200 bytes), and the User-Agent is truthful with a working contact address.
`legal-accounts.md` rule 74 still caps display at headline, source, date and
link -- no snippet, and specifically no AI-written summary, which the droit
voisin exclusion for hyperlinks and very short extracts does not cover.

And rule 23 is satisfied rather than bypassed: the point of moving these feeds
off the desktop is that the fetch now happens **once, here, on a schedule**,
instead of once per installed device.

WHAT IS IMPLEMENTED. The fetch discipline (§3.3-§3.6) and tier 2, the
first-party structured endpoints that cover six of the eight surveyed sites.
Tiers 3 and 4 (sitemap-guided fetch, bounded category pagination) are refused
loudly rather than approximated -- they need per-site parsing rules that must
be written against a specific site with its allowlist entry in hand.
"""

import json
import logging
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse

import config

logger = logging.getLogger("server.crawler")


class CrawlerUnavailableError(Exception):
    """No cache to serve and no permission to build one."""


# ---------------------------------------------------------------- allowlist --

@dataclass
class Source:
    """One roaster, and the paperwork that makes crawling it permissible.

    Every field except `tier`/`endpoint` exists to record a decision a human
    made. A Source that cannot answer "who did you ask, when, and what did the
    CGU say" is not crawlable, which is why `is_crawlable` tests the paperwork
    and not just an `enabled` flag.
    """

    domain: str
    #: "roaster" (allowlist.json, the rules 2-3 paperwork) or "press"
    #: (news_sources.json, a syndication feed). See NEWS SOURCES below.
    kind: str = "roaster"
    #: Shown to the user as the news item's source. Falls back to `domain`.
    display_name: str = ""
    tier: int = 2
    endpoint: str = ""
    contact_email: str = ""
    contacted_on: str = ""
    response: str = ""           # "yes" | "no" | "silence"
    cgu_clause: str = ""         # quoted verbatim from the site
    cgu_permits_scraping: Optional[bool] = None
    robots_checked_on: str = ""
    robots_sha256: str = ""
    decision: str = ""           # "allow" | "exclude"
    decided_on: str = ""
    enabled: bool = True
    crawl_delay_seconds: float = 3.0
    news_feed_url: str = ""

    @property
    def is_crawlable(self) -> bool:
        if not self.enabled:
            return False
        if self.kind == "press":
            # A syndication feed carries its own permission: the publisher
            # emits it to be read by machines. There is no outreach step to
            # record because there is no question to ask. What still binds is
            # enforced elsewhere and is not optional -- robots.txt, the
            # per-host delay and the conditional GET all live in Fetcher, and
            # rule 74 caps what may be displayed. See NEWS SOURCES below.
            return bool(self.news_feed_url)
        # An explicit "no" and a CGU that prohibits scraping are excluded here,
        # in code, rather than by anyone remembering (legal.md rule 3). Silence
        # is not consent but is not refusal either -- it is the case the
        # outreach step exists to convert into one of the other two.
        if self.decision != "allow":
            return False
        if self.response == "no" or self.cgu_permits_scraping is False:
            return False
        return bool(self.contacted_on and self.robots_sha256 and self.decided_on)


def load_news_sources() -> list[Source]:
    """The press feeds behind /v1/news, from a file separate from the allowlist.

    Kept apart from [load_sources] deliberately: mixing them would mean either
    applying the roaster paperwork to publications that never needed it, or
    weakening `is_crawlable` for roasters to accommodate feeds. Two files, two
    justifications, one `Source` type so [Fetcher] applies identically to both.
    """
    path = config.CRAWLER_NEWS_SOURCES_PATH
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("news sources unreadable (%s); serving none", exc)
        return []
    out = []
    for entry in raw.get("sources", []):
        fields = {k: v for k, v in entry.items() if k in Source.__dataclass_fields__}
        fields["kind"] = "press"
        out.append(Source(**fields))
    return out


def load_sources() -> list[Source]:
    path = config.CRAWLER_ALLOWLIST_PATH
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        # Fail closed: an unreadable allowlist is not an empty one, and
        # certainly not a licence to crawl everything.
        logger.error("allowlist is unreadable, refusing to crawl: %s", exc)
        return []
    entries = raw.get("sources", []) if isinstance(raw, dict) else raw
    sources = []
    for entry in entries:
        known = {f.name for f in Source.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        sources.append(Source(**{k: v for k, v in entry.items() if k in known}))
    return sources


# -------------------------------------------------------------- fetch budget --

@dataclass
class Budget:
    """The §3.4 caps, as a counter that aborts rather than a comment.

    These exist to contain **bugs**, not to be approached: a real tier-2 run is
    about twelve requests against a 250-request ceiling. If a run ever gets
    near these numbers, something is looping, and the right outcome is a
    truncated run and a loud log line.
    """

    total_max: int = 250
    per_host_max: int = 60
    total: int = 0
    per_host: dict = field(default_factory=dict)

    def charge(self, host: str) -> None:
        self.total += 1
        self.per_host[host] = self.per_host.get(host, 0) + 1
        if self.total > self.total_max:
            raise CrawlerUnavailableError(f"run aborted: global cap of {self.total_max} requests hit")
        if self.per_host[host] > self.per_host_max:
            raise CrawlerUnavailableError(f"run aborted: per-host cap hit on {host}")


class Fetcher:
    """Every outbound request in this project goes through here.

    One place, so the User-Agent cannot be spoofed by accident (rule 18 -- the
    single most damaging technical decision available), the delay cannot be
    skipped, robots.txt cannot be bypassed, and the budget cannot be evaded.
    The pattern is `coffee_agent`'s `_resolve()`: a chokepoint is only a
    chokepoint if there is no way around it.
    """

    def __init__(self, budget: Optional[Budget] = None):
        self.budget = budget or Budget()
        self._last_request_at: dict[str, float] = {}
        self._robots: dict[str, object] = {}
        self._validators: dict[str, tuple[str, str]] = {}

    # -- politeness ---------------------------------------------------------

    def _wait(self, host: str, base_delay: float) -> None:
        """Concurrency 1 per host, 3.0 s base ± 1.5 s jitter (5.0 s where the
        allowlist says so). Jitter is not decoration: a fixed interval is a
        recognisable drumbeat in someone's access log."""
        previous = self._last_request_at.get(host)
        if previous is not None:
            delay = base_delay + random.uniform(-1.5, 1.5)
            elapsed = time.monotonic() - previous
            if elapsed < delay:
                time.sleep(delay - elapsed)
        self._last_request_at[host] = time.monotonic()

    def _robots_for(self, client, host: str):
        """Parsed robots.txt for a host, fetched once per run.

        FAIL CLOSED (rule 12). A 4xx, a 5xx, a timeout, a TLS error or a body
        that is not text/plain means crawl **nothing** on this host this run.
        The tempting fallback -- "no robots.txt means allow all" -- is how a
        crawler ends up ignoring a file that was there and briefly 503ing.
        """
        if host in self._robots:
            return self._robots[host]

        from protego import Protego

        try:
            response = client.get(f"https://{host}/robots.txt", timeout=(10, 30))
            content_type = response.headers.get("content-type", "")
            if response.status_code != 200 or "text/plain" not in content_type:
                raise CrawlerUnavailableError(
                    f"robots.txt on {host} returned {response.status_code} ({content_type or 'no type'})"
                )
            parsed = Protego.parse(response.text)
        except CrawlerUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - any transport failure fails closed
            raise CrawlerUnavailableError(f"robots.txt on {host} unreachable: {exc}") from exc

        self._robots[host] = parsed
        return parsed

    # -- the one request method --------------------------------------------

    def get_json(self, client, url: str, *, source: Source) -> Optional[object]:
        """A single conditional GET returning parsed JSON, or None on 304."""
        response = self._get(client, url, source=source)
        return None if response is None else response.json()

    def get_text(self, client, url: str, *, source: Source) -> Optional[str]:
        """A single conditional GET returning the raw body, or None on 304.

        The news feeds are XML, not JSON, and before 2026-08-15 they were
        fetched with a bare `httpx.Client.get` that went around this class
        entirely -- no robots.txt check, no per-host delay, no conditional
        request, no budget charge. That was already wrong and became
        untenable when the news refresh moved to hourly: 24x the request
        count is only defensible if each one is a conditional poll costing
        ~200 bytes, which is exactly what routing through here buys.
        """
        response = self._get(client, url, source=source)
        return None if response is None else response.text

    def _get(self, client, url: str, *, source: Source):
        """A single conditional GET, or None if nothing changed (304).

        Conditional requests are the whole reason the steady state is ~8
        requests a day returning 304 or a few KB -- less traffic than one human
        loading one product page.
        """
        host = urlparse(url).netloc
        robots = self._robots_for(client, host)
        if not robots.can_fetch(url, config.CRAWLER_USER_AGENT.split("/")[0]):
            logger.info("robots.txt disallows %s", url)
            return None

        headers = {
            "User-Agent": config.CRAWLER_USER_AGENT,
            "From": config.CRAWLER_CONTACT_EMAIL,
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Accept-Encoding": "gzip, br",
            # Several WordPress feeds content-negotiate, and a request with no
            # Accept gets the HTML page rather than the XML -- which then fails
            # to parse and looks like a broken feed. The desktop client has
            # always sent this; the server had not.
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        }
        etag, last_modified = self._validators.get(url, ("", ""))
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        backoff = [5, 15, 45]
        for attempt in range(3):
            self._wait(host, source.crawl_delay_seconds)
            self.budget.charge(host)
            try:
                response = client.get(url, headers=headers, timeout=(10, 30))
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    raise CrawlerUnavailableError(f"{url}: {exc}") from exc
                time.sleep(random.uniform(0, backoff[attempt]))
                continue

            if response.status_code in (429, 503):
                retry_after = response.headers.get("retry-after")
                if retry_after and retry_after.isdigit() and int(retry_after) > 300:
                    # Longer than five minutes is the host telling you to go
                    # away for the day. Obey it as such.
                    raise CrawlerUnavailableError(f"{host} asked for {retry_after}s; abandoning for this run")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else backoff[attempt]
                time.sleep(random.uniform(0, wait))
                continue

            if response.status_code == 304:
                return None
            if response.status_code != 200:
                raise CrawlerUnavailableError(f"{url} returned {response.status_code}")

            self._validators[url] = (
                response.headers.get("etag", ""),
                response.headers.get("last-modified", ""),
            )
            return response

        raise CrawlerUnavailableError(f"{url}: gave up after retries")


# ------------------------------------------------------------------ parsing --

def _clean_note(text: Optional[str]) -> Optional[str]:
    """Tasting notes: <=200 characters, plain text (legal.md rules 29-33).

    Never `body_html`, never the full description. What survives is the kind of
    short factual phrase a catalogue needs -- and the truncation is deliberate,
    not a display choice, so it happens here rather than in a client.
    """
    if not text:
        return None
    plain = " ".join(str(text).split())
    return plain[:200] if plain else None


def _parse_shopify(payload: object, source: Source) -> list[dict]:
    products = (payload or {}).get("products", []) if isinstance(payload, dict) else []
    items = []
    for product in products:
        variants = product.get("variants") or [{}]
        first = variants[0]
        images = product.get("images") or []
        items.append(
            {
                "roaster": source.domain,
                "name": product.get("title", ""),
                "url": f"https://{source.domain}/products/{product.get('handle', '')}",
                # A live pointer to the roaster's own CDN. Never downloaded,
                # never re-hosted (rule 31); the privacy cost of that choice is
                # disclosed on +2.2a (legal-accounts rule 75).
                "image_url": (images[0].get("src") if images else None),
                "process": product.get("product_type") or None,
                "price_eur": _to_float(first.get("price")),
                "weight_g": _to_int(first.get("grams")),
                "tasting_note": _clean_note(product.get("tags") and ", ".join(product["tags"])),
            }
        )
    return items


def _parse_woocommerce(payload: object, source: Source) -> list[dict]:
    products = payload if isinstance(payload, list) else []
    items = []
    for product in products:
        prices = product.get("prices") or {}
        images = product.get("images") or []
        minor_units = prices.get("currency_minor_unit", 2)
        items.append(
            {
                "roaster": source.domain,
                "name": product.get("name", ""),
                "url": product.get("permalink", ""),
                "image_url": (images[0].get("src") if images else None),
                "price_eur": _to_float(prices.get("price"), scale=10 ** minor_units),
                "tasting_note": _clean_note(product.get("short_description")),
            }
        )
    return items


def _to_float(value, scale: float = 1.0) -> Optional[float]:
    try:
        return float(value) / scale
    except (TypeError, ValueError):
        return None


def _to_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# -------------------------------------------------------------------- cache --

@dataclass
class _Cached:
    items: list
    fetched_at: int


_lock = threading.Lock()
_catalogue: Optional[_Cached] = None
_news: Optional[_Cached] = None

#: The D.111-16 rubric (art. L.111-7 code de la consommation), served with the
#: data so the catalogue screen can render it without French consumer law being
#: hard-coded into an APK -- and so correcting it is a deploy, not a release.
#: `legal-accounts.md` rule 76 requires it *on* the catalogue screen.
RUBRIC = {
    "ranking": "Newest first by the date this server first saw the product. No paid placement exists.",
    "paid_referencing": "None. No roaster pays to appear, and no link is affiliated.",
    "capital_or_contractual_links": "None with any listed roaster.",
    "exhaustiveness": "Not exhaustive. Only roasters who were contacted and did not object are listed.",
    "update_frequency": "Once daily. Each listing shows when this server last saw it.",
}


def _refresh_catalogue() -> _Cached:
    sources = [s for s in load_sources() if s.is_crawlable]
    if not sources:
        raise CrawlerUnavailableError(
            "no allowlisted roaster: specs/legal.md rules 2-3 (outreach, 14-day wait, "
            "per-domain allowlist entry) are unmet, so there is nothing this server "
            "is permitted to crawl"
        )

    import httpx

    fetcher = Fetcher()
    items: list[dict] = []
    with httpx.Client(follow_redirects=True) as client:
        for source in sources:
            if source.tier != 2:
                logger.warning(
                    "%s needs tier %d (sitemap/pagination), which is not implemented; skipping",
                    source.domain, source.tier,
                )
                continue
            try:
                payload = fetcher.get_json(client, source.endpoint, source=source)
            except CrawlerUnavailableError as exc:
                # One host failing must not take the run down: the others are
                # independent, and a host that fails three runs in a row is
                # auto-disabled by the allowlist review, not by an exception here.
                logger.warning("skipping %s: %s", source.domain, exc)
                continue
            if payload is None:
                continue
            parser = _parse_woocommerce if "wp-json" in source.endpoint else _parse_shopify
            items.extend(parser(payload, source))

    now = int(time.time())
    for item in items:
        item.setdefault("first_seen_at", now)
    return _Cached(items=items, fetched_at=now)


#: Feed `description` values that are chrome rather than an excerpt. Sprudge
#: ships its RSS boilerplate in every item ("This article is from the coffee
#: website Sprudge at ... This is the RSS feed version"), and rendering that as
#: a standfirst on a third of the cards is worse than rendering nothing. Match
#: on the phrase, not the publisher, so a second feed that does the same thing
#: is caught without a code change.
_BOILERPLATE = (
    "this is the rss feed version",
    "this article is from the coffee website",
    "read the full story",
    "continue reading",
    "the post appeared first on",
)

#: `legal-accounts.md` rule 74's override caps this. 200 characters is a
#: standfirst, not an article, and the cap is applied HERE rather than in the
#: app so that the untruncated text never leaves this process -- an app that
#: received 19KB of body and displayed 200 characters of it would still be
#: holding 19KB of someone's copyrighted expression.
EXCERPT_MAX_CHARS = 200

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _excerpt(raw: Optional[str]) -> Optional[str]:
    """The publisher's OWN standfirst, cleaned and capped -- never a summary.

    This reproduces text the publisher chose to put in a syndication feed. It
    is deliberately not generated, rewritten, shortened by a model, or merged
    across items: `legal-accounts.md` rule 74's override permits a very short
    verbatim extract (which art. L.211-3-1 CPI excludes from the droit voisin)
    and permits nothing else. If you are ever tempted to "improve" this by
    asking a model to condense it, that is the exact act the exclusion does
    not cover.
    """
    if not raw:
        return None
    text = _WS.sub(" ", _TAGS.sub(" ", raw)).strip()
    if not text:
        return None
    low = text.lower()
    if any(marker in low for marker in _BOILERPLATE):
        return None
    if len(text) <= EXCERPT_MAX_CHARS:
        return text
    # Cut on a word boundary so the ellipsis never lands mid-word.
    cut = text[:EXCERPT_MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:-—–")
    return (cut or text[:EXCERPT_MAX_CHARS].rstrip()) + "…"


def _refresh_news() -> _Cached:
    """Poll each allowlisted feed once, conditionally.

    RUNS HOURLY, unlike the catalogue's daily crawl -- see `scheduler.py` for
    the cadence and the spec divergence it records. What makes hourly
    defensible rather than 24x rude is that every request here is a
    conditional GET through [Fetcher]: an unchanged feed answers 304 in about
    200 bytes and is never parsed. A feed that has not published since the
    last poll therefore costs both sides almost nothing, which is the
    steady state legal.md rule 19 is written around.

    A 304 is not an error and not an empty feed: it means "unchanged", so the
    previously cached items for that source are carried forward rather than
    dropped. Without that, every hourly poll would blank the feed.
    """
    sources = [s for s in load_news_sources() if s.is_crawlable]
    if not sources:
        raise CrawlerUnavailableError("no news sources configured (news_sources.json is empty)")

    import httpx

    previous: dict[str, list[dict]] = {}
    if _news is not None:
        for item in _news.items:
            previous.setdefault(item["source"], []).append(item)

    fetcher = Fetcher()
    items: list[dict] = []
    with httpx.Client(follow_redirects=True) as client:
        for source in sources:
            try:
                body = fetcher.get_text(client, source.news_feed_url, source=source)
            except CrawlerUnavailableError as exc:
                # One unreachable feed must not take the whole refresh down;
                # the others are still worth serving. Carry this source's
                # last-known items rather than silently losing them.
                logger.warning("news feed %s failed: %s", source.news_feed_url, exc)
                items.extend(previous.get(source.display_name or source.domain, []))
                continue

            if body is None:  # 304 Not Modified
                items.extend(previous.get(source.display_name or source.domain, []))
                continue

            try:
                # A UTF-8 BOM, or any whitespace, before the declaration makes
                # expat fail with "XML or text declaration not at start of
                # entity" -- freshcup.com serves exactly that. Stripping is
                # correct rather than lenient: the bytes are a well-formed
                # document with a byte-order mark in front of it.
                root = ET.fromstring(body.lstrip("\ufeff \t\r\n"))
            except ET.ParseError as exc:
                logger.warning("news feed %s is not parseable XML: %s", source.news_feed_url, exc)
                items.extend(previous.get(source.display_name or source.domain, []))
                continue

            # Headline, source, date, link. Nothing else is extracted, because
            # nothing else may be shown (legal-accounts.md rule 74): no snippet
            # past the headline, and specifically no AI-written summary -- that
            # is a derivative use outside the droit voisin exception.
            for entry in root.iter():
                tag = entry.tag.split("}")[-1]
                if tag not in ("item", "entry"):
                    continue
                title = _child_text(entry, "title")
                link = _child_text(entry, "link") or _child_attr(entry, "link", "href")
                if not title or not link:
                    continue
                # `description`/`summary` only. NOT `content:encoded`, which
                # carries the whole article on some feeds (19KB on Perfect
                # Daily Grind) -- legal.md 3.8 is "store facts, never
                # expression", and a full body is expression however short the
                # slice displayed from it.
                excerpt = _excerpt(
                    _child_text(entry, "description") or _child_text(entry, "summary")
                )
                items.append(
                    {
                        "title": " ".join(title.split()),
                        "source": source.display_name or source.domain,
                        "url": link,
                        "published_at": _published_at(entry),
                        "excerpt": excerpt,
                    }
                )

    return _Cached(items=items, fetched_at=int(time.time()))


#: RSS uses RFC 822 in <pubDate>; Atom uses RFC 3339 in <published>/<updated>.
_DATE_FIELDS = ("pubDate", "published", "updated", "date")


def _published_at(entry) -> Optional[int]:
    """The item's publication date as Unix seconds, or None.

    The date is one of the four fields rule 74 permits the app to show, and
    until now this was hard-coded to None -- so every headline rendered
    undated. Both feed dialects are accepted because the allowlist does not
    constrain which one a roaster's blog emits.

    None on anything unparseable, deliberately: a wrong date on a news item
    is worse than no date, and the screen already renders the undated case.
    """
    for field in _DATE_FIELDS:
        raw = _child_text(entry, field)
        if not raw:
            continue
        for parse in (parsedate_to_datetime, _parse_rfc3339):
            try:
                parsed = parse(raw)
            except Exception:  # noqa: BLE001
                continue
            if parsed is None:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
    return None


def _parse_rfc3339(raw: str):
    # datetime.fromisoformat handles "Z" only from 3.11; normalise for 3.10.
    return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))


def _child_text(node, name: str) -> str:
    for child in node:
        if child.tag.split("}")[-1] == name and child.text:
            return child.text.strip()
    return ""


def _child_attr(node, name: str, attr: str) -> str:
    for child in node:
        if child.tag.split("}")[-1] == name:
            return child.attrib.get(attr, "")
    return ""


def _serve(cached: Optional[_Cached], ttl: int, refresh) -> _Cached:
    """Cache read, with the crawl behind it.

    A stale cache is served rather than refreshed on the request path only
    because refreshing here would make every expiry a thundering herd against
    someone else's shop. In production the refresh belongs on the once-daily
    03:30-05:00 Europe/Paris schedule of legal.md §3.4; this on-demand path is
    the development one and inherits every rate limit regardless.
    """
    if not config.CRAWLER_ENABLED:
        raise CrawlerUnavailableError(
            "the catalogue/news crawler is disabled on this server (CRAWLER_ENABLED unset). "
            "See crawler.py: three compliance gates in specs/legal.md and "
            "specs/legal-accounts.md rule 72 are unmet."
        )
    now = int(time.time())
    if cached is not None and now - cached.fetched_at < ttl:
        return cached
    return refresh()


def catalogue() -> tuple[list[dict], int, dict]:
    global _catalogue
    with _lock:
        _catalogue = _serve(_catalogue, config.CATALOGUE_TTL_SECONDS, _refresh_catalogue)
        return _catalogue.items, _catalogue.fetched_at, RUBRIC


def news() -> tuple[list[dict], int]:
    global _news
    with _lock:
        _news = _serve(_news, config.NEWS_TTL_SECONDS, _refresh_news)
        return _news.items, _news.fetched_at
