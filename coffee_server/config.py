"""Environment-driven settings for the API gateway.

Independent of the top-level ../app/config.py -- this server is a separate
deployable unit (its own Docker image, its own .env) with no dependency on
the local agent's sandbox or tool config.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Explicit path, not a bare load_dotenv() -- that walks up parent directories
# looking for a .env, which would silently pick up ../.env (the sibling app/
# agent's config, with its own API keys) instead of staying self-contained.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Shared secret clients must send in the X-API-Key header. Required -- see
# main.py's startup check, which refuses to run without it.
SERVER_API_KEY = os.environ.get("SERVER_API_KEY", "")

# The read key, for /v1/catalogue and /v1/news.
#
# TWO KEYS, NOT ONE (coffee_android/plan/api.md §2). Both ship inside the same
# APK, so neither is a secret in any strong sense -- the split is about blast
# radius, not confidentiality. The metered endpoints (/v1/ask, /v1/suggest,
# /v1/vision) cost money per call; the read endpoints serve a cache. Rotating
# the key after a catalogue-scraping incident must not take the AI features
# down with it, and vice versa. Falls back to SERVER_API_KEY so an existing
# single-key deployment keeps working.
READ_API_KEY = os.environ.get("READ_API_KEY", "") or SERVER_API_KEY

# Comma-separated list of allowed CORS origins, or "*" for any. Safe to leave
# as "*" here since auth is a header the client sets explicitly (not a
# cookie), so cross-origin requests still need the real API key.
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

PORT = int(os.environ.get("PORT", "8000"))

# --- Anthropic (Claude) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "8192"))

# --- Qwen (Alibaba DashScope, OpenAI-compatible) ---
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen-max")
QWEN_MAX_TOKENS = int(os.environ.get("QWEN_MAX_TOKENS", "8192"))
QWEN_BASE_URL = os.environ.get("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")


# --- Vision (bean-label OCR) ---
# Its own model variable, deliberately separate from ANTHROPIC_MODEL: the chat
# model and the OCR model should be able to move independently, the same split
# coffee_agent makes with ANTHROPIC_OCR_MODEL.
ANTHROPIC_VISION_MODEL = os.environ.get("ANTHROPIC_VISION_MODEL", "claude-opus-5")
QWEN_VISION_MODEL = os.environ.get("QWEN_VISION_MODEL", "qwen3.5-omni-flash")
# A bean-bag photo. 6 MB of base64 is a ~4.5 MB JPEG, far past what a label
# needs; the cap exists so one client cannot turn a 4G upload into a bill.
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", str(6 * 1024 * 1024)))

# --- Accounts, metering and abuse cutoff ---
# specs/legal-accounts.md rules 58-60: the account record exists solely to
# authorise, meter and cut off abuse. It holds the Google `sub` and counters,
# never user content. Rule 60 is why only `openid` is asked of Google and why
# nothing here has a column for an email address.
#
# GOOGLE_CLIENT_IDS is the audience allowlist for the ID tokens the Android app
# presents. Empty disables account auth entirely, which in turn disables every
# metered endpoint -- fail closed, so a misconfigured deployment cannot serve
# paid calls to anonymous callers.
GOOGLE_CLIENT_IDS = [c.strip() for c in os.environ.get("GOOGLE_CLIENT_IDS", "").split(",") if c.strip()]
ACCOUNT_DB_PATH = Path(os.environ.get("ACCOUNT_DB_PATH", Path(__file__).resolve().parent / "accounts.db"))

# ----------------------------------------------------------- server sync ----
# A TEST FEATURE, OFF UNLESS EXPLICITLY ALLOWLISTED, AND IT IS THE ONE PLACE
# THIS SERVER HOLDS USER CONTENT.
#
# Everything else here is stateless with respect to what the user writes: the
# only per-user row is the metering record, and `specs/legal-accounts.md` §3.8
# binds the *shipped* architecture to no user content server-side -- which is
# what the app's privacy screen tells users, in three languages, and what the
# Play Data safety form declares. Device-to-device sync through here would flip
# the developer to data controller for coffee logs.
#
# This exists so that architecture can be tried before it is committed to, on
# the developer's own account only. SYNC_ALLOWED_EMAILS is an allowlist of
# verified Google `email` claims; empty (the default, and what production
# ships) means every sync endpoint 404s as if it did not exist. Adding an
# address to it is a decision with legal consequences for whoever is added --
# do not add a second one without reopening §3.8.
SYNC_ALLOWED_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("SYNC_ALLOWED_EMAILS", "").split(",")
    if e.strip()
}

# One bundle per account, named by a hash of the `sub` -- see sync_store.py.
SYNC_DIR = Path(os.environ.get("SYNC_DIR", Path(__file__).resolve().parent / "sync_blobs"))

# A bundle is a zip of a coffee log with its photos, so this is generous; it is
# here to stop a bad or hostile client filling the disk, not to shape a feature.
SYNC_MAX_BYTES = int(os.environ.get("SYNC_MAX_BYTES", str(64 * 1024 * 1024)))

# Per-account daily caps, counted per operation and reset on a rolling UTC day.
# These are abuse cutoffs, not product limits: a person logging their morning
# brew hits neither.
DAILY_QUOTA = {
    "ask": int(os.environ.get("DAILY_QUOTA_ASK", "60")),
    "suggest": int(os.environ.get("DAILY_QUOTA_SUGGEST", "60")),
    "vision": int(os.environ.get("DAILY_QUOTA_VISION", "40")),
}
# Burst limit, per account, per operation, over a sliding window. Stops a loop
# in a client (or a script holding an extracted key and a real account) from
# spending a whole day's quota in ten seconds.
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "6"))

# --- Catalogue & news crawler ---
# OFF BY DEFAULT, AND THAT IS A COMPLIANCE POSITION, NOT A DEFAULT-TO-TWEAK.
# specs/legal.md rules 2-3 require per-domain outreach, a 14-day wait and a
# committed allowlist entry per roaster *before* the first request, and
# specs/legal-accounts.md rule 72 requires legal.md §1.2's use case to be
# re-opened and re-recorded before catalogue/news results are served to Play
# users at all. Neither has happened. See crawler.py.
CRAWLER_ENABLED = os.environ.get("CRAWLER_ENABLED", "").lower() in {"1", "true", "yes"}
# The press feeds behind /v1/news. A SEPARATE file from allowlist.json on
# purpose: that one records the outreach-and-CGU paperwork legal.md rules 2-3
# demand before a French roaster's *shop* may be crawled, and those rules were
# scoped to exactly that. A trade publication's RSS feed is a different act
# under a different regime -- see crawler.py's NEWS SOURCES note.
CRAWLER_NEWS_SOURCES_PATH = Path(
    os.environ.get(
        "CRAWLER_NEWS_SOURCES_PATH", Path(__file__).resolve().parent / "news_sources.json"
    )
)

CRAWLER_ALLOWLIST_PATH = Path(
    os.environ.get("CRAWLER_ALLOWLIST_PATH", Path(__file__).resolve().parent / "allowlist.json")
)
CATALOGUE_TTL_SECONDS = int(os.environ.get("CATALOGUE_TTL_SECONDS", str(24 * 3600)))
# One hour, product decision 2026-08-15 (was two). See scheduler.py's
# NEWS_INTERVAL_SECONDS for the cadence this pairs with and, importantly, for
# the specs/legal.md rule 15 divergence that hourly news polling opens.
NEWS_TTL_SECONDS = int(os.environ.get("NEWS_TTL_SECONDS", str(3600)))
# specs/legal.md rule 17: truthful, descriptive, with a contact that resolves.
# Rule 18 forbids ever replacing this with a browser string.
CRAWLER_USER_AGENT = os.environ.get(
    "CRAWLER_USER_AGENT",
    "CoffeeBeanIndexBot/0.1 (+https://coffee-can.org/bot; bot@coffee-can.org)",
)
CRAWLER_CONTACT_EMAIL = os.environ.get("CRAWLER_CONTACT_EMAIL", "bot@coffee-can.org")


def configured_providers() -> set[str]:
    """Providers with an API key set, i.e. usable right now."""
    configured = set()
    if ANTHROPIC_API_KEY:
        configured.add("anthropic")
    if QWEN_API_KEY:
        configured.add("qwen")
    return configured
