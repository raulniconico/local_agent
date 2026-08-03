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
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

# A truthful, contactable User-Agent (specs/legal.md §3.5 rule 17/18): never
# spoof a browser. Replace the contact address if this ever leaves personal
# use -- it should resolve to something the actual operator reads.
_CONTACT = "raulniconico@outlook.com"
USER_AGENT = f"CoffeeCanWhatsNew/0.1 (personal/non-commercial use; contact: {_CONTACT})"

_TIMEOUT = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=20.0)
_PAGE_DELAY_SECONDS = 3.0  # between paginated requests to the same host -- §3.4
_CACHE_TTL = timedelta(minutes=15)  # avoids re-hitting a host on every re-open


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
)


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
    """Fetch (or return cached) listings for one roaster. Raises
    RoasterUnavailableError on any network/parse failure rather than letting
    an exception surface from a background thread -- see whats_new_dialog.py."""
    label, domain, platform = ROASTERS[roaster_key]

    if not force and roaster_key in _cache:
        cached_at, cached_listings = _cache[roaster_key]
        if datetime.now(timezone.utc) - cached_at < _CACHE_TTL:
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

    _cache[roaster_key] = (datetime.now(timezone.utc), listings)
    return listings
