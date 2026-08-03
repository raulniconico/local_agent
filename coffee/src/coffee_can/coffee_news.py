"""Today's coffee news for the main window's "What's New" ticker.

**Why this is not "ask Qwen for the news".** A chat model has no live web
access: asked directly for "20 coffee news items from the last 24 hours with
links", DashScope's Qwen (even with `enable_search`) returns items weeks old,
no `search_info`, and no URLs -- measured 2026-08-03. Anything it did emit as
a URL would be generated text, and a ticker whose whole point is that
clicking opens the article cannot be built on invented links.

So the split is:

- **Where the facts come from: the publishers' own RSS feeds.** Real
  headlines, real permalinks, real `pubDate`s -- which is also the only way
  the "last 24 hours" window can actually be enforced rather than asserted.
- **What Qwen does: rank.** It sees a numbered list of headlines and returns
  the *indices* of the most important ones. It never supplies a title or a
  URL, so a hallucination can at worst reorder the list or be discarded --
  it can never produce a link that goes somewhere wrong. See _rank_with_qwen.

Both the ranking prompt and the deterministic specialty_score() bias the feed
towards specialty coffee -- notable origins and lots (Panama Geisha, Ethiopian
microlots), competitions (WBrC, WBC, Cup of Excellence), varieties, processing
and cupping -- and away from chain-store, capsule and foodservice items. The
score is applied *before* Qwen sees the list, so the bias survives the model
being unavailable, slow or wrong.

Qwen is optional. Without QWEN_API_KEY, or on any API failure, the feed falls
back to that score with recency as the tie-break.

On specs/legal.md: RSS is a first-party structured endpoint published by each
outlet *for* syndication -- the acquisition tier §3.2 rule 7 asks for. Only
facts and a pointer are kept (headline, source, timestamp, canonical URL);
no article body is fetched, stored or displayed, so §3.8's "store facts,
never expression; link, never copy" holds by construction.
"""

import html.entities as html_entities
import json
import os
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
from dotenv import load_dotenv

from .paths import data_dir

# Same two locations the other provider integrations check -- working
# directory (source checkout) and the app's data dir (packaged installs).
load_dotenv()
load_dotenv(data_dir() / ".env")

_CONTACT = "raulniconico@outlook.com"
USER_AGENT = f"CoffeeCanNews/0.1 (personal/non-commercial use; contact: {_CONTACT})"

#: Outlet -> feed URL. Every one verified live on 2026-08-03 to return HTTP
#: 200 with parseable `<item>`s and real permalinks. Feeds that were dead or
#: refused a non-browser UA that day, and are deliberately absent: STiR
#: (404), Global Coffee Report (403), Coffee Intelligence (DNS failure).
#: Re-check before adding: a feed that 403s a plain UA must not be worked
#: around (specs/legal.md §3.7 rule 25 -- a block is an answer).
SOURCES = {
    "Sprudge": "https://sprudge.com/feed",
    "Daily Coffee News": "https://dailycoffeenews.com/feed/",
    "Perfect Daily Grind": "https://perfectdailygrind.com/feed/",
    "Comunicaffe": "https://www.comunicaffe.com/feed/",
    "Barista Magazine": "https://www.baristamagazine.com/feed/",
    "Fresh Cup": "https://freshcup.com/feed/",
    "World Coffee Portal": "https://www.worldcoffeeportal.com/rss",
    "Coffee Review": "https://www.coffeereview.com/feed/",
    "SCA": "https://sca.coffee/sca-news?format=rss",
}

#: How specialty-leaning each outlet is, as a baseline nudge before the
#: headline itself is scored. Comunicaffe and World Coffee Portal publish
#: heavily and skew commodity/foodservice, so without this they crowd out the
#: specialty press on volume alone.
_SOURCE_BIAS = {
    "Coffee Review": 3,
    "Sprudge": 3,
    "Barista Magazine": 3,
    "SCA": 3,
    "Perfect Daily Grind": 2,
    "Daily Coffee News": 2,
    "Fresh Cup": 1,
    "World Coffee Portal": -1,
    "Comunicaffe": -2,
}

#: Headline terms that mark a story as specialty. Weighted, lowercased,
#: matched as substrings -- deliberately blunt, since this only orders a list
#: that is already correct, and is the whole ranking when Qwen is absent.
_SPECIALTY_TERMS = {
    # varieties and the famous lots
    3: (
        "geisha", "gesha", "panama", "esmeralda", "sudan rume", "wush wush",
        "pacamara", "sl28", "sl34", "bourbon", "typica", "caturra", "catuai",
        "ethiopia", "yirgacheffe", "guji", "sidama", "sidamo", "harrar", "limu",
        "cup of excellence", "best of panama", "world brewers cup", "wbrc",
        "world barista", "wbc", "barista championship", "brewers cup",
        "cupping score", "microlot", "micro-lot", "single origin", "single-origin",
        "q grader", "coffee review", "90 points", "specialty coffee",
    ),
    # process, origin and trade vocabulary
    2: (
        "anaerobic", "carbonic maceration", "natural process", "washed process",
        "honey process", "fermentation", "terroir", "varietal", "cultivar",
        "green coffee", "direct trade", "farmgate", "finca", "hacienda",
        "smallholder", "harvest", "roastery", "roaster", "cupping", "barista",
        "colombia", "kenya", "rwanda", "burundi", "costa rica", "guatemala",
        "honduras", "el salvador", "yemen", "peru", "nicaragua", "tanzania",
        "pour over", "pour-over", "filter coffee", "espresso", "competition",
        "champion", "championship",
    ),
}

#: The other direction: mass-market and foodservice stories that are coffee
#: news but not specialty news.
_COMMODITY_TERMS = (
    "starbucks", "dunkin", "mcdonald", "mccafe", "mccafé", "costa coffee",
    "pret a manger", "nespresso", "keurig", "jde peet", "vending",
    "foodservice", "franchise", "convenience store", "drive-thru", "forecourt",
    "capsule", "pods", "instant coffee", "soluble", "outlet", "chain",
    "automation", "petrol", "airport", "supermarket",
)

# Two days rather than one: the specialty outlets publish a few times a week,
# not daily, so a 24h window was filled mostly by the high-volume commodity
# feeds and left the specialty press underrepresented.
WINDOW = timedelta(hours=48)
LIMIT = 20

_TIMEOUT = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=20.0)
_CACHE_TTL = timedelta(minutes=15)
#: Feeds are ~50-200 KB. Anything far past that is not a feed, and parsing it
#: would hand an XML bomb to ElementTree.
_MAX_FEED_BYTES = 4_000_000

_QWEN_BASE_URL = os.environ.get(
    "QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)
#: Ranking is a short text-only classification job, so it shares the text
#: chat model with qwen_brew_suggest.py rather than QWEN_OMNI_MODEL (audio
#: and vision) -- see that module's table.
_QWEN_MODEL = os.environ.get("QWEN_CHAT_MODEL", "qwen3.6-plus")
_QWEN_TIMEOUT_SECONDS = 30.0
#: The OpenAI SDK retries twice by default, which turns one slow call into
#: three and multiplies the worst case by 3x. Ranking is optional garnish on
#: a feed that is already correctly ordered -- fail fast and fall back.
_QWEN_MAX_RETRIES = 0

_cache: "tuple[datetime, list] | None" = None


class NewsUnavailableError(Exception):
    """Raised when no feed could be reached or parsed."""


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime

    def age_display(self, now=None) -> str:
        delta = (now or datetime.now(timezone.utc)) - self.published_at
        hours = int(delta.total_seconds() // 3600)
        if hours < 1:
            return "just now"
        return f"{hours}h ago" if hours < 24 else f"{hours // 24}d ago"


def specialty_score(item: "NewsItem") -> int:
    """How specialty-leaning a headline looks: Panama Geisha, Ethiopian
    microlots, competitions and processing beat chain-store and foodservice
    news. Used to order the fallback feed and to shape the pool Qwen ranks,
    so the bias holds whether or not the API is configured."""
    haystack = f"{item.title} {item.url}".lower()
    score = _SOURCE_BIAS.get(item.source, 0)
    for weight, terms in _SPECIALTY_TERMS.items():
        score += weight * sum(1 for term in terms if term in haystack)
    score -= 3 * sum(1 for term in _COMMODITY_TERMS if term in haystack)
    return score


def is_ai_ranking_configured() -> bool:
    """Whether Qwen can be asked to rank. Ranking is optional -- see module
    docstring; without it the feed is reverse-chronological."""
    return bool(os.environ.get("QWEN_API_KEY"))


def _text(element) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""


def _parse_date(raw: str):
    """RSS uses RFC 822 `pubDate`; Atom uses ISO 8601 `updated`. Accept both,
    and treat a naive timestamp as UTC rather than dropping the item."""
    if not raw:
        return None
    for parse in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            parsed = parse(raw.strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


#: Named entities that are legal in XML without a DTD. Everything else in
#: the HTML set has to be rewritten before a strict parser will accept it.
_XML_BUILTIN_ENTITIES = frozenset(("amp", "lt", "gt", "quot", "apos"))
_ENTITY_PATTERN = re.compile(r"&([A-Za-z][A-Za-z0-9]{1,31});")


def _repair_feed(payload: str) -> str:
    """Make real-world RSS parseable by a strict XML parser.

    Two failures seen live on 2026-08-03, both of which silently cost a whole
    source: Fresh Cup serves a leading space before `<?xml` ("XML or text
    declaration not at start of entity"), and SCA's Squarespace feed embeds
    HTML named entities like `&nbsp;` that XML does not define without a DTD
    ("undefined entity"). Neither is worth losing an outlet over."""
    payload = payload.lstrip("﻿ \t\r\n")

    def to_numeric(match):
        name = match.group(1)
        if name in _XML_BUILTIN_ENTITIES:
            return match.group(0)
        codepoint = html_entities.name2codepoint.get(name)
        return f"&#{codepoint};" if codepoint else match.group(0)

    return _ENTITY_PATTERN.sub(to_numeric, payload)


def _parse_feed(payload: str, source: str) -> "list[NewsItem]":
    root = ElementTree.fromstring(_repair_feed(payload))
    items = []
    # RSS 2.0 <item> and Atom <entry>, without hard-coding either namespace.
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: child for child in node}
        title = _text(fields.get("title"))
        link_node = fields.get("link")
        # RSS puts the URL in the element's text; Atom puts it in @href.
        url = _text(link_node) or (link_node.get("href", "") if link_node is not None else "")
        published = _parse_date(
            _text(fields.get("pubDate")) or _text(fields.get("published")) or _text(fields.get("updated"))
        )
        if title and url.startswith("http") and published:
            items.append(NewsItem(title=title, url=url, source=source, published_at=published))
    return items


def _fetch_feed(source: str, url: str, client: httpx.Client) -> "list[NewsItem]":
    response = client.get(url)
    response.raise_for_status()
    if len(response.content) > _MAX_FEED_BYTES:
        raise ValueError(f"{source}: feed larger than {_MAX_FEED_BYTES} bytes")
    return _parse_feed(response.text, source)


def _rank_with_qwen(items: "list[NewsItem]", limit: int) -> "list[NewsItem]":
    """Ask Qwen which headlines matter most, by index.

    The model is shown numbered headlines and must answer with indices only.
    Every returned index is validated against the list we already hold, so
    the worst a bad reply can do is reorder or shorten the feed -- it can
    never introduce a headline or a URL the publisher did not publish. Any
    failure falls back to the caller's chronological order."""
    from openai import OpenAI  # optional dependency, imported lazily

    catalogue = "\n".join(f"{i}. [{item.source}] {item.title}" for i, item in enumerate(items))
    client = OpenAI(
        api_key=os.environ["QWEN_API_KEY"],
        base_url=_QWEN_BASE_URL,
        timeout=_QWEN_TIMEOUT_SECONDS,
        max_retries=_QWEN_MAX_RETRIES,
    )
    response = client.chat.completions.create(
        model=_QWEN_MODEL,
        # Thinking off. qwen3.6-plus reasons by default, and on a 17-headline
        # list that meant ~138s and a timeout (45s x 3 SDK retries) every
        # single run, so the ticker never populated. Picking indices from a
        # list is classification, not reasoning: with thinking disabled the
        # same call is ~2.6s and 70 completion tokens instead of thousands.
        extra_body={"enable_thinking": False},
        messages=[
            {
                "role": "system",
                "content": (
                    "You rank coffee news for a specialty coffee enthusiast who keeps a "
                    "hand-brew log. Rank HIGHEST: notable origins and lots (Panama "
                    "Geisha/Gesha, Ethiopian Yirgacheffe/Guji/Sidama, Kenyan SL28, "
                    "Colombian and Central American microlots), competitions and their "
                    "results (World Brewers Cup/WBrC, World Barista Championship, Cup of "
                    "Excellence, Best of Panama), varieties and processing methods "
                    "(anaerobic, carbonic maceration, natural, washed, honey), green "
                    "coffee quality, cupping scores and reviews, harvest and crop "
                    "conditions at origin, and notable roasters and baristas. "
                    "Rank LOWEST: mass-market and foodservice news -- chain store "
                    "openings, QSR menu launches, vending, capsules, instant coffee, "
                    "supermarket and petrol-forecourt coffee -- plus sponsored posts, "
                    "listicles and generic business items with no specialty angle."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Here are today's coffee headlines:\n\n{catalogue}\n\n"
                    f"Return the {limit} most relevant to specialty coffee, best first, "
                    'as JSON: {"indices": [3, 0, 7]}. Use only indices from the list. '
                    "No other text."
                ),
            },
        ],
        response_format={"type": "json_object"},
    )
    payload = json.loads(response.choices[0].message.content)
    seen, ranked = set(), []
    for index in payload.get("indices", []):
        if isinstance(index, int) and 0 <= index < len(items) and index not in seen:
            seen.add(index)
            ranked.append(items[index])
    if not ranked:
        raise ValueError("Qwen returned no usable indices")
    # A short reply shouldn't shrink the feed -- top up chronologically.
    ranked.extend(item for item in items if item not in ranked)
    return ranked[:limit]


def fetch_news(force: bool = False, rank: bool = True) -> "list[NewsItem]":
    """Today's coffee headlines, most important first.

    Raises NewsUnavailableError only if *every* source failed; one dead feed
    is skipped silently so a single outlet can't empty the ticker."""
    global _cache
    if not force and _cache is not None:
        cached_at, cached_items = _cache
        if datetime.now(timezone.utc) - cached_at < _CACHE_TTL:
            return cached_items

    collected, failures = [], []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    ) as client:
        for source, url in SOURCES.items():
            try:
                collected.extend(_fetch_feed(source, url, client))
            except (httpx.HTTPError, ElementTree.ParseError, ValueError) as exc:
                failures.append(f"{source}: {exc}")

    if not collected:
        raise NewsUnavailableError(
            "No coffee news source could be reached. " + "; ".join(failures[:3])
        )

    cutoff = datetime.now(timezone.utc) - WINDOW
    fresh, by_url = [], set()
    for item in sorted(collected, key=lambda i: i.published_at, reverse=True):
        if item.published_at >= cutoff and item.url not in by_url:
            by_url.add(item.url)
            fresh.append(item)

    # Specialty first, recency as the tie-break. This is the running order
    # without Qwen, and the order Qwen sees -- so a truncated or discarded
    # model reply degrades to a specialty-biased feed, never to a
    # chain-store one.
    fresh.sort(key=lambda i: (specialty_score(i), i.published_at), reverse=True)

    items = fresh[:LIMIT]
    if rank and len(fresh) > 1 and is_ai_ranking_configured():
        try:
            items = _rank_with_qwen(fresh, LIMIT)
        except Exception:
            # Ranking is a nicety; the sort above is already the right shape
            # and a background thread must not die over an optional API call.
            items = fresh[:LIMIT]

    _cache = (datetime.now(timezone.utc), items)
    return items
