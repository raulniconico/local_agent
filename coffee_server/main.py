"""FastAPI gateway that proxies chat requests to Anthropic, Qwen, or DeepSeek.

Stateless pass-through: each request carries its own provider choice and its
full message history (or a single prompt) and gets one response back -- no
session state, no tool-calling loop. Meant to run behind a load balancer as a
Docker container (see Dockerfile) on ECS/Fargate/App Runner/EC2.

Run locally with:
    uvicorn main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
import providers
from auth import require_api_key
from schemas import AskRequest, AskResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.SERVER_API_KEY:
        raise RuntimeError(
            "SERVER_API_KEY is not set. Refusing to start an unauthenticated "
            "gateway in front of paid provider APIs -- set it in .env."
        )
    configured = sorted(config.configured_providers())
    if not configured:
        logger.warning("No provider API keys are configured -- every /v1/ask request will fail with 400.")
    else:
        logger.info("Configured providers: %s", ", ".join(configured))
    yield


app = FastAPI(title="LLM Gateway", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict:
    """Unauthenticated -- for load balancer / ECS health checks."""
    return {"status": "ok"}


@app.post("/v1/ask", response_model=AskResponse, dependencies=[Depends(require_api_key)])
def ask(request: AskRequest) -> AskResponse:
    if request.provider not in config.configured_providers():
        raise HTTPException(400, f"provider '{request.provider}' is not configured on this server")

    try:
        model, content = providers.ask(
            request.provider,
            messages=request.messages,
            prompt=request.prompt,
            system=request.system,
            model=request.model,
            max_tokens=request.max_tokens,
        )
    except providers.ProviderNotConfiguredError as exc:
        raise HTTPException(400, str(exc)) from exc
    except providers.ProviderRequestError as exc:
        raise HTTPException(502, f"upstream {request.provider} API error: {exc}") from exc

    return AskResponse(provider=request.provider, model=model, content=content)
