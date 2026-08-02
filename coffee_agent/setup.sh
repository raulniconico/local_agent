#!/usr/bin/env bash
# One-shot installer for the local vLLM + LangGraph file/paperwork agent.
set -euo pipefail
cd "$(dirname "$0")"

# --- 1. uv manages an isolated Python 3.12, since vLLM does not support
#        the system's Python 3.14 yet. This never touches system Python. ---
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Creating .venv (Python 3.12)..."
uv venv --python 3.12 .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing Python dependencies..."
uv pip install -r requirements.txt

# --- 2. Config file (read first: it decides whether we need the local model) ---
[ -f .env ] || cp .env.example .env
set -a
# shellcheck disable=SC1091
source .env
set +a

LLM_PROVIDER="${LLM_PROVIDER:-vllm}"

if [ "$LLM_PROVIDER" = "anthropic" ]; then
  echo
  echo "LLM_PROVIDER=anthropic — skipping Hugging Face login and model download."
  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "Set ANTHROPIC_API_KEY in coffee_agent/.env before running the agent."
  fi
  echo
  echo "Setup complete. Next step (from coffee_agent/):"
  echo "  source .venv/bin/activate && python main.py"
  exit 0
fi

# --- 3. Hugging Face auth (meta-llama/* repos are gated) ---
if [ -n "${HF_TOKEN:-}" ]; then
  huggingface-cli login --token "$HF_TOKEN"
else
  echo "Log in to Hugging Face (your account needs access to the Llama model repo):"
  huggingface-cli login
fi

# --- 4. Pre-download the model so the first `vllm serve` doesn't stall ---
MODEL_ID="${MODEL_ID:-meta-llama/Llama-3.2-3B-Instruct}"
echo "Downloading ${MODEL_ID}..."
python -c "from huggingface_hub import snapshot_download; snapshot_download('${MODEL_ID}')"

echo
echo "Setup complete. Next steps (both from coffee_agent/):"
echo "  1) In one terminal: ./serve_vllm.sh"
echo "  2) In another:      source .venv/bin/activate && python main.py"