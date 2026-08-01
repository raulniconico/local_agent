import os
from pathlib import Path

from dotenv import load_dotenv

# Explicit path, not a bare load_dotenv() -- that walks up parent directories
# looking for a .env, which would silently pick up a different .env (e.g. the
# sibling server/ project's) if this package is ever run from another cwd.
load_dotenv(Path(__file__).resolve().parent / ".env")

# "vllm" runs the model locally on your GPU; "anthropic" calls the Claude API.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "vllm").lower()

MODEL_ID = os.environ.get("SERVED_MODEL_NAME", "local-llama")
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "8192"))

# Model used for the coffee tools' image OCR (coffee_agent/coffee_tools.py), independent
# of the main chat backend -- OCR is a single direct Anthropic API call, so it
# runs even when LLM_PROVIDER=vllm.
ANTHROPIC_OCR_MODEL = os.environ.get("ANTHROPIC_OCR_MODEL", "claude-opus-5")

# Under LLM_PROVIDER=anthropic, build_llm() uses Qwen instead of Claude for the
# main chat model whenever both of these are set (see graph.py) -- an
# OpenAI-compatible alternative to the Claude API, not a third LLM_PROVIDER value.
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "")
QWEN_MAX_TOKENS = int(os.environ.get("QWEN_MAX_TOKENS", "8192"))
QWEN_BASE_URL = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

WORKSPACE_ROOT = Path(os.environ.get("AGENT_WORKSPACE", "~/Documents")).expanduser().resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)