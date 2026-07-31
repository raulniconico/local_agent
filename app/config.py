import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# "vllm" runs the model locally on your GPU; "anthropic" calls the Claude API.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "vllm").lower()

MODEL_ID = os.environ.get("SERVED_MODEL_NAME", "local-llama")
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "8192"))

WORKSPACE_ROOT = Path(os.environ.get("AGENT_WORKSPACE", "~/Documents")).expanduser().resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)