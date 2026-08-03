""""What's New" -- reads each roaster's own first-party product listing
endpoint (Shopify's /products.json, WooCommerce's Store API) to show what's
currently on sale, so a bean profile can be pre-filled from a real listing
instead of typed in from scratch.

This is the crawler governed by ../../specs/legal.md. Two constraints from
that spec are load-bearing here and must not be relaxed without re-reading
it first:

- **Tier 2 only.** Every roaster below is fetched through a first-party JSON
  endpoint the platform itself publishes for product listings -- never HTML
  scraping. This is the spec's acquisition hierarchy (specs/legal.md §3.2):
  prefer the lightest, most-intended-for-reuse source available. Roasters
  with no such endpoint (Terres de Café, Lomi) and Cafés Lugat (no online
  catalog at all) are deliberately not in ROASTERS -- adding them means
  building the heavier sitemap/HTML tier (§3.2 rules 8-9) with its own
  robots.txt handling, not just appending a row here.
- **Facts only, never expression** (§3.8). A listing keeps name, price,
  weight, availability, a link, and a short *excerpt* of the roaster's own
  description -- never the full marketing copy. See Listing and _excerpt()
  below.
- **Images are hotlinked, never downloaded.** `Listing.image_url` is a
  pointer to the roaster's own CDN/media URL, fetched by the GUI only at the
  moment it's actually displayed and never written to disk (see
  gui/whats_new_dialog.py's preview panel). This module itself never issues a
  request for image bytes -- only the JSON listing, which contains the URL as
  text. That keeps the reproduction question off the table entirely: no copy
  of the image is ever made here, the same as a browser loading an <img> src.
"""

import html
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import httpx

from .paths import data_dir

# A truthful, contactable User-Agent (specs/legal.md §3.5 rule 17/18): never
# spoof a browser. Replace the contact address if this ever leaves personal
# use -- it should resolve to something the actual operator reads.
_CONTACT = "raulniconico@outlook.com"
USER_AGENT = f"CoffeeCanWhatsNew/0.1 (personal/non-commercial use; contact: {_CONTACT})"

_TIMEOUT = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=20.0)
_PAGE_DELAY_SECONDS = 3.0  # between paginated requests to the same host -- §3.4
#: Matches coffee_news.py's reasoning exactly: nine outlets there, five
#: roasters (several paginated) here -- either way too much to repeat on
#: every window open, and a roaster's own shelf doesn't turn over within a
#: day. 24h rather than the RSS feed's 2h because a product catalogue changes
#: far slower than a news cycle.
_CACHE_TTL = timedelta(hours=24)
#: Persisted to the data dir, not just held in memory, for the same reason as
#: coffee_news.py's cache: the app is normally launched fresh (pipx entry
#: point) rather than left running, so an in-memory-only cache would expire
#: with every quit and 24h would never actually be observed. One file with a
#: key per roaster rather than one file per roaster -- five fetches happen
#: together at startup, so there's no benefit to invalidating them separately.
_CACHE_FILE = "whats_new_cache.json"


class RoasterUnavailableError(Exception):
    """Raised when a roaster's endpoint can't be reached or doesn't parse."""


@dataclass(frozen=True)
class Listing:
    roaster: str
    name: str
    price_display: str
    weight_display: str
    in_stock: bool
    url: str
    note_excerpt: str
    image_url: str
    fetched_at: datetime
    #: The seller's own product type / category string, lowercased. These
    #: shops sell brewers, grinders and glassware alongside beans, so callers
    #: that only want coffee need a way to tell them apart -- see
    #: looks_like_coffee(). Defaulted so it stays additive: it is the
    #: platform's own classification, not one we infer.
    category: str = ""
    #: When the seller published the listing, for "newest first" ordering.
    #: Shopify exposes `published_at`; the WooCommerce Store API's product
    #: *list* carries no date at all, so Tanat's listings are always None --
    #: sort them last rather than inventing a timestamp.
    published_at: datetime | None = None


# name -> (display domain, platform, homepage URL). Domains and platforms are
# exactly what specs/legal.md §2.2's live survey (2026-08-03) found; re-check
# that survey before trusting this list without re-verifying it yourself.
ROASTERS = {
    "datura": ("Datura Coffee", "daturacoffee.com", "shopify"),
    "belleville": ("Belleville Brûlerie", "cafesbelleville.com", "shopify"),
    "coutume": ("Coutume", "coutumecafe.com", "shopify"),
    "larbre": ("L'Arbre à Café", "larbreacafe.com", "shopify"),
    "tanat": ("Tanat", "tanat.coffee", "woocommerce"),
}

_cache: dict[str, tuple[datetime, list]] = {}


def _cache_path():
    return data_dir() / _CACHE_FILE


def _is_fresh(cached_at: datetime) -> bool:
    return datetime.now(timezone.utc) - cached_at < _CACHE_TTL


def _listing_to_json(listing: Listing) -> dict:
    payload = asdict(listing)
    payload["fetched_at"] = listing.fetched_at.isoformat()
    payload["published_at"] = listing.published_at.isoformat() if listing.published_at else None
    return payload


def _listing_from_json(payload: dict) -> Listing:
    payload = dict(payload)
    payload["fetched_at"] = datetime.fromisoformat(payload["fetched_at"])
    payload["published_at"] = (
        datetime.fromisoformat(payload["published_at"]) if payload.get("published_at") else None
    )
    return Listing(**payload)


def _load_disk_cache(roaster_key: str) -> "tuple[datetime, list[Listing]] | None":
    """The last stored fetch for one roaster, or None if there isn't one, the
    file can't be read, or it doesn't parse. Never raises into the caller --
    a corrupt cache file must fall back to a fresh fetch, not a dead pane."""
    try:
        whole = json.loads(_cache_path().read_text(encoding="utf-8"))
        entry = whole[roaster_key]
        cached_at = datetime.fromisoformat(entry["cached_at"])
        listings = [_listing_from_json(item) for item in entry["listings"]]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return cached_at, listings


def _store_disk_cache(roaster_key: str, cached_at: datetime, listings: "list[Listing]") -> None:
    """Persist one roaster's fetch for the next launch, preserving whatever
    other roasters' entries are already in the file. Written via a temp file
    and os.replace so a crash mid-write can't corrupt a still-valid cache."""
    path = _cache_path()
    try:
        whole = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        whole = {}
    whole[roaster_key] = {
        "cached_at": cached_at.isoformat(),
        "listings": [_listing_to_json(listing) for listing in listings],
    }
    temporary = path.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(whole), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        # A read-only or full data dir costs a cache, never the listing itself.
        temporary.unlink(missing_ok=True)


def _excerpt(raw_html: str, limit: int = 200) -> str:
    """A short, attributed plain-text excerpt of a description -- never the
    full body. Caps well under the point copyright analysis treats prose as
    likely original (specs/legal.md §2.1, droit d'auteur); this is a pointer
    to the roaster's own page, not a republication of it."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


#: Category words that mean "this is not a bag of coffee". Matched against
#: Listing.category, which is the seller's own classification -- these shops
#: all list brewers, grinders, glassware, subscriptions and gift cards in the
#: same endpoint as the beans.
_NON_COFFEE_CATEGORY_WORDS = (
    "accessoire", "accessory", "equipment", "matériel", "materiel", "brewing gear",
    "cadeau", "gift", "carte", "abonnement", "subscription", "box",
    "mug", "tasse", "verre", "glass", "kinto", "alessi", "hario", "chemex",
    "moulin", "grinder", "balance", "scale", "kettle", "bouilloire",
    "filtre", "filter", "papier", "paper", "livre", "book", "merch", "textile",
    "thé", "the vert", "infusion", "rooibos", "tisane", "matcha",
    # Tanat files espresso machines and a sample roaster under these, and
    # L'Arbre à Café its barista courses. Note what is *not* here: a bare
    # "machine", because Tanat also tags real beans by the machine they suit
    # ("machine auto", "moka bialetti") -- only the plural shop section
    # "machines à cafés" means the machine itself.
    "équipement", "equipement", "machines à cafés", "machines a cafes",
    "percolateur", "formation", "atelier",
)

#: Words that mean "not a bag of coffee" when they appear in the *name*.
#: Deliberately much narrower than the category list above, because a name is
#: matched whole-word and a wrong hit here silently hides a real coffee: no
#: "filtre" (Belleville sells a "Sélection Découverte Café Filtre"), no
#: "espresso", no origin or process vocabulary. Everything listed is a thing
#: no roaster puts on a bag of beans.
_NON_COFFEE_NAME_WORDS = (
    "thé", "thes", "thés", "tea", "tisane", "infusion", "rooibos", "matcha", "chai",
    "spoon", "cuillère", "cuillere", "tamper", "pichet", "jug", "knock", "leveler",
    "leveling", "distributeur", "moulin", "grinder", "bouilloire", "kettle",
    "cafetière", "cafetiere", "cafétière", "dripper", "chemex", "carafe", "mug",
    "tasse", "assiette", "saucer", "verre", "gobelet", "balance", "machine",
    "purificateur", "affiche", "chocolat", "abonnement", "subscription",
    "payment", "papier", "paper", "filtres", "stylo", "bols",
    # Gear brands, the same tactic the category list already uses: these
    # shops sell kit whose product_type is empty, so the brand in the name is
    # the only thing left to go on ("Hario - My Cafe Drip Filter", "OXO -
    # Boîte pop ... pour le café") -- both of which name-drop coffee and
    # would otherwise read as beans.
    "hario", "kinto", "alessi", "chemex", "oxo", "motta", "acme",
    "comandante", "delonghi", "lelit",
)
_NON_COFFEE_NAME_PATTERN = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(word) for word in _NON_COFFEE_NAME_WORDS)
)
#: The positive half of looks_like_coffee_bag(): the seller calling it coffee.
_COFFEE_WORD_PATTERN = re.compile(r"\b(?:caf[ée]s?|coffee|espresso|arabica|gesha|geisha)\b")


def looks_like_coffee(listing: "Listing") -> bool:
    """Whether a listing is a bag of coffee rather than kit.

    Best-effort and deliberately conservative: it reads only the seller's own
    `product_type`/tags/categories, never the marketing prose, and when a shop
    publishes no category at all it answers True rather than silently hiding
    beans. Callers that must not show equipment should treat it as a filter,
    not as a guarantee."""
    category = listing.category
    if not category:
        return True
    return not any(word in category for word in _NON_COFFEE_CATEGORY_WORDS)


#: Producing country -> the words a listing might use for it. Both spellings
#: are needed: these roasters write in French but several label the beans
#: themselves in English. Growing regions and famous estates count as their
#: country -- a bag sold as "Yirgacheffe" is Ethiopian -- because this exists
#: to group a browsing list, not to make a provenance claim.
ORIGINS = {
    "Ethiopia": ("ethiopia", "ethiopie", "éthiopie", "yirgacheffe", "yirgacheffé",
                 "guji", "sidamo", "sidama", "harrar", "harar", "limu", "jimma", "djimmah"),
    "Kenya": ("kenya", "kenyan", "nyeri", "kirinyaga"),
    "Rwanda": ("rwanda", "nyamasheke"),
    "Burundi": ("burundi", "kayanza"),
    "Tanzania": ("tanzania", "tanzanie"),
    "Uganda": ("uganda", "ouganda"),
    "DR Congo": ("congo", "kivu"),
    "Colombia": ("colombia", "colombie", "colombien", "colombienne", "huila", "nariño",
                 "narino", "tolima", "antioquia"),
    "Brazil": ("brazil", "brésil", "bresil", "brésilien", "cerrado", "mogiana", "minas"),
    "Peru": ("peru", "pérou", "perou", "cajamarca"),
    "Bolivia": ("bolivia", "bolivie"),
    "Ecuador": ("ecuador", "équateur", "equateur"),
    "Panama": ("panama", "boquete", "esmeralda", "volcan"),
    "Costa Rica": ("costa rica", "tarrazu", "tarrazú"),
    "Guatemala": ("guatemala", "huehuetenango", "acatenango", "antigua"),
    "Honduras": ("honduras", "marcala"),
    "El Salvador": ("el salvador", "salvador"),
    "Nicaragua": ("nicaragua",),
    "Mexico": ("mexico", "mexique", "chiapas", "oaxaca"),
    "Indonesia": ("indonesia", "indonésie", "indonesie", "sumatra", "java", "sulawesi",
                  "bali", "flores"),
    "India": ("india", "inde"),
    "Yemen": ("yemen", "yémen"),
    "China": ("china", "chine", "yunnan"),
    "Vietnam": ("vietnam", "viet nam", "viêt nam"),
    "Myanmar": ("myanmar", "birmanie"),
    "Papua New Guinea": ("papua", "papouasie"),
    "Timor": ("timor",),
    "Haiti": ("haiti", "haïti"),
    "Jamaica": ("jamaica", "jamaïque", "jamaique"),
    "Cuba": ("cuba",),
}

#: Whole words only. As substrings several of these are disastrous -- "inde"
#: is inside "indépendant" and "index", "java" inside "javanais" -- and a
#: filter that quietly files a Colombian bag under India is worse than one
#: that files it under nothing.
_ORIGIN_PATTERNS = {
    label: re.compile(r"\b(?:%s)\b" % "|".join(re.escape(term) for term in terms))
    for label, terms in ORIGINS.items()
}
_BLEND_PATTERN = re.compile(r"\b(?:blend|assemblage|mélange|melange)\b")

#: What detect_origin() answers for a bag with no single country -- kept as a
#: named constant because it is also a filter value in the GUI.
BLEND_LABEL = "Blend"


def detect_origin(listing: "Listing") -> str:
    """Best-effort producing country for a listing, or "" if it can't tell.

    Reads the seller's own name and category first and only falls back to the
    description excerpt, so a passing mention ("roasted like a Brazilian") in
    the prose can't outrank a country in the title. When several countries
    appear, the earliest one in the text wins; when none does but the listing
    calls itself a blend, the answer is BLEND_LABEL.

    Deliberately a heuristic over text the roaster wrote for humans -- none of
    these endpoints publishes origin as a field. Treat it as a way to narrow a
    browsing list, never as data to copy into a bean profile."""
    for haystack in (f"{listing.name} {listing.category}".lower(), listing.note_excerpt.lower()):
        best, position = "", None
        for label, pattern in _ORIGIN_PATTERNS.items():
            match = pattern.search(haystack)
            if match and (position is None or match.start() < position):
                best, position = label, match.start()
        if best:
            return best
        if _BLEND_PATTERN.search(haystack):
            return BLEND_LABEL
    return ""


def looks_like_coffee_bag(listing: "Listing") -> bool:
    """Whether a listing is a bag of beans, not kit, tea or paperwork.

    Stricter than looks_like_coffee(), and needed because that function's
    "no category means yes" rule is generous where it matters most: several
    of these shops publish an empty `product_type` for a chunk of the
    catalogue, and everything in it -- cupping spoons, filter papers, herbal
    infusions, even a "Update Payment Info" placeholder product -- sails
    through. A shelf that shows three items has no room to be that generous.

    Three tests, all over fields the seller wrote themselves:
    looks_like_coffee() must pass, the name must not contain a word no
    roaster prints on a bag of beans, and the listing must positively look
    like coffee -- either detect_origin() found a country or the seller
    calls it café/coffee/espresso somewhere.

    Still a heuristic, and still the conservative direction: it drops real
    coffees whose names say nothing (a bag called only "Le Mistral" with no
    origin in its description), which costs a browsing list far less than
    presenting a milk pitcher as a coffee."""
    if not looks_like_coffee(listing):
        return False
    name = listing.name.lower()
    if _NON_COFFEE_NAME_PATTERN.search(name):
        return False
    return bool(
        detect_origin(listing) or _COFFEE_WORD_PATTERN.search(f"{name} {listing.category}")
    )


def _parse_iso(value) -> "datetime | None":
    """Parse a platform timestamp, tolerating absence and junk -- a feed's
    ordering is never worth an exception from a background thread."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _format_price(amount: float, currency: str) -> str:
    symbol = "€" if currency.upper() == "EUR" else currency.upper() + " "
    return f"{symbol}{amount:.2f}"


def _fetch_shopify(domain: str, roaster_label: str, client: httpx.Client) -> list[Listing]:
    products: list = []
    page = 1
    while True:
        response = client.get(
            f"https://{domain}/products.json", params={"limit": 250, "page": page}
        )
        response.raise_for_status()
        batch = response.json().get("products", [])
        products.extend(batch)
        if len(batch) < 250:
            break
        page += 1
        time.sleep(_PAGE_DELAY_SECONDS)

    now = datetime.now(timezone.utc)
    listings = []
    for product in products:
        variants = product.get("variants") or [{}]
        prices = [float(v["price"]) for v in variants if v.get("price") is not None]
        weights = sorted({v.get("grams") for v in variants if v.get("grams")})
        in_stock = any(v.get("available") for v in variants)
        price_display = (
            _format_price(min(prices), "EUR")
            if len(set(prices)) <= 1
            else f"{_format_price(min(prices), 'EUR')}–{_format_price(max(prices), 'EUR')}"
        ) if prices else "—"
        weight_display = ", ".join(f"{int(w)} g" for w in weights) if weights else "—"
        listings.append(
            Listing(
                roaster=roaster_label,
                name=product.get("title", "(untitled)"),
                price_display=price_display,
                weight_display=weight_display,
                in_stock=in_stock,
                url=f"https://{domain}/products/{product.get('handle', '')}",
                note_excerpt=_excerpt(product.get("body_html", "")),
                image_url=(product.get("image") or {}).get("src")
                or next((img.get("src", "") for img in product.get("images") or []), ""),
                fetched_at=now,
                category=" ".join(
                    [product.get("product_type") or ""] + (product.get("tags") or [])
                ).lower(),
                published_at=_parse_iso(product.get("published_at")),
            )
        )
    return listings


def _fetch_woocommerce(domain: str, roaster_label: str, client: httpx.Client) -> list[Listing]:
    products: list = []
    page = 1
    while True:
        response = client.get(
            f"https://{domain}/wp-json/wc/store/v1/products",
            params={"per_page": 100, "page": page},
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        products.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(_PAGE_DELAY_SECONDS)

    now = datetime.now(timezone.utc)
    listings = []
    for product in products:
        prices = product.get("prices") or {}
        minor_unit = int(prices.get("currency_minor_unit", 2))
        currency = prices.get("currency_code", "EUR")
        raw_price = prices.get("price")
        price_display = (
            _format_price(int(raw_price) / (10**minor_unit), currency)
            if raw_price is not None
            else "—"
        )
        listings.append(
            Listing(
                roaster=roaster_label,
                name=product.get("name", "(untitled)"),
                price_display=price_display,
                weight_display="—",  # not exposed by the Store API's product list
                in_stock=bool(product.get("is_in_stock")),
                url=product.get("permalink", f"https://{domain}"),
                note_excerpt=_excerpt(product.get("short_description") or product.get("description", "")),
                image_url=next(
                    (img.get("thumbnail") or img.get("src", "") for img in product.get("images") or []), ""
                ),
                fetched_at=now,
                category=" ".join(
                    c.get("name", "") for c in product.get("categories") or []
                ).lower(),
            )
        )
    return listings


_FETCHERS = {"shopify": _fetch_shopify, "woocommerce": _fetch_woocommerce}


def fetch_listings(roaster_key: str, force: bool = False) -> list[Listing]:
    """Fetch (or return cached) listings for one roaster.

    Served from the cache -- in memory first, then the copy in the data dir --
    while it is inside _CACHE_TTL (24h), so relaunching the app inside that
    window never re-hits a roaster's server. `force=True` skips both and
    refreshes.

    Raises RoasterUnavailableError on any network/parse failure rather than
    letting an exception surface from a background thread -- see
    whats_new_dialog.py."""
    label, domain, platform = ROASTERS[roaster_key]

    if not force:
        if roaster_key not in _cache:
            disk = _load_disk_cache(roaster_key)
            if disk is not None:
                _cache[roaster_key] = disk
        if roaster_key in _cache:
            cached_at, cached_listings = _cache[roaster_key]
            if _is_fresh(cached_at):
                return cached_listings

    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            listings = _FETCHERS[platform](domain, label, client)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise RoasterUnavailableError(f"Couldn't reach {label}: {exc}") from exc

    cached_at = datetime.now(timezone.utc)
    _cache[roaster_key] = (cached_at, listings)
    _store_disk_cache(roaster_key, cached_at, listings)
    return listings
