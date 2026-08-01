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

# --- DeepSeek (OpenAI-compatible) ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_MAX_TOKENS = int(os.environ.get("DEEPSEEK_MAX_TOKENS", "8192"))
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")


def configured_providers() -> set[str]:
    """Providers with an API key set, i.e. usable right now."""
    configured = set()
    if ANTHROPIC_API_KEY:
        configured.add("anthropic")
    if QWEN_API_KEY:
        configured.add("qwen")
    if DEEPSEEK_API_KEY:
        configured.add("deepseek")
    return configured
