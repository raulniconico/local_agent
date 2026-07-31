#!/usr/bin/env bash
# Launches vLLM's OpenAI-compatible server with tool-calling enabled,
# tuned to fit an 8GB-VRAM GPU with Llama-3.2-3B-Instruct.
set -euo pipefail
cd "$(dirname "$0")"

# shellcheck disable=SC1091
source .venv/bin/activate
set -a
[ -f .env ] && source .env
set +a

# FlashInfer JIT-compiles its sampling kernels with the system nvcc, which is 12.4
# here and cannot target this GPU's sm120 (needs CUDA >= 12.9). Without this the
# server dies at warmup with "FlashInfer requires GPUs with sm75 or higher".
# Drop this once the CUDA toolkit is upgraded to 12.9+/13.x.
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"

MODEL_ID="${MODEL_ID:-meta-llama/Llama-3.2-3B-Instruct}"
SERVED_NAME="${SERVED_MODEL_NAME:-local-llama}"
PORT="${VLLM_PORT:-8000}"

# gpu-memory-utilization / max-model-len are conservative for 8GB VRAM.
# If you hit CUDA OOM, lower --max-model-len further (e.g. 2048).
# If you have headroom to spare, raise them for longer documents.
exec vllm serve "$MODEL_ID" \
  --served-model-name "$SERVED_NAME" \
  --port "$PORT" \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --enforce-eager \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json