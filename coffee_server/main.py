"""FastAPI gateway. Every AI call and every crawl in this project happens here.

Two kinds of endpoint live in this file and they are not interchangeable:

  * `/v1/ask` -- the original free-form proxy. Gateway key only. Kept for
    `coffee_agent` and local tooling. **The Android app must not use it**: a
    shipped client ships its key, and an endpoint taking arbitrary prompts
    would publish a general-purpose LLM on the developer's bill.
  * `/v1/suggest`, `/v1/vision` -- structured in, structured out, prompt
    rendered server-side (prompts.py). Gateway key **and** a verified Google
    account, metered per account. This is what the app calls.
  * `/v1/catalogue`, `/v1/news` -- reads of a server-side cache that this
    server fills by crawling (crawler.py). The client never touches a
    roaster's host: `specs/legal-android.md` §4 rule 23.
  * `/v1/account`, `DELETE /v1/account` -- the GDPR Art. 15 access document
    and the Art. 17 erasure route, over the only personal data that exists
    here (accounts.py).

Stateless with respect to user content: no bean, session, note or photo is
ever written to disk. The one thing that *is* persisted is the account record
metering requires -- see accounts.py, which is also why the architecture is
stated as "no user content server-side" rather than "no storage"
(`specs/legal-accounts.md` rule 58).

Run locally with:
    uvicorn main:app --reload
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import accounts
import config
import crawler
import prompts
import providers
from auth import meter, require_account, require_api_key, require_read_key
from schemas import (
    AccountResponse,
    AskRequest,
    AskResponse,
    BeanFields,
    CatalogueResponse,
    NewsResponse,
    ReportRequest,
    SuggestRequest,
    SuggestResponse,
    SuggestStage,
    VisionRequest,
    VisionResponse,
)

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

    if not config.GOOGLE_CLIENT_IDS:
        # Not fatal: /v1/ask and the read endpoints still work, and a dev box
        # has no reason to hold a client ID. It *is* worth saying out loud,
        # because every metered endpoint will 503 until it is set.
        logger.warning(
            "GOOGLE_CLIENT_IDS is unset -- /v1/suggest, /v1/vision and /v1/account "
            "will refuse every request. The Android client cannot work against this server."
        )
    if not config.CRAWLER_ENABLED:
        logger.info("Catalogue/news crawler is disabled (CRAWLER_ENABLED unset). See crawler.py.")
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


# --------------------------------------------------------- metered endpoints --
# Both dependencies, always: the API key says "one of our clients", the account
# says "this user", and only the second one can be metered or cut off.


@app.post(
    "/v1/suggest",
    response_model=SuggestResponse,
    dependencies=[Depends(require_api_key)],
)
def suggest(request: SuggestRequest, sub: str = Depends(require_account)) -> SuggestResponse:
    """Ask-AI brew suggestion. Fields in, recipe out.

    Qwen preferred: this is the text-reasoning task the desktop app already
    points at Qwen (`qwen_brew_suggest.py`), and it is the cheaper of the two.
    """
    try:
        provider = providers.pick_provider(request.provider, preferred="qwen")
    except providers.ProviderNotConfiguredError as exc:
        raise HTTPException(400, str(exc)) from exc

    meter(sub, "suggest")

    bean = request.bean.model_dump()
    prompt = prompts.brew_suggestion(bean, request.dripper, request.dose_g)

    try:
        model, content = providers.ask(
            provider, messages=None, prompt=prompt, system=None, model=None, max_tokens=2048
        )
    except providers.ProviderRequestError as exc:
        raise HTTPException(502, f"upstream {provider} API error: {exc}") from exc

    data = _parse_json_object(content)
    if data is None:
        raise HTTPException(502, f"{provider} did not return usable JSON")

    stages = []
    for raw in data.get("stages") or []:
        if not isinstance(raw, dict):
            continue
        circling = str(raw.get("circling") or "").strip() or None
        stages.append(
            SuggestStage(
                temperature_c=_to_float(raw.get("temperature_c")),
                water_g=_to_float(raw.get("water_g")),
                time_seconds=_to_int(raw.get("time_seconds")),
                circling=circling,
            )
        )

    # A fixed dose is a constraint, not a suggestion: the user is going to
    # weigh out that much whatever the model says, and writing the model's
    # drifted number into their session would record a brew that never
    # happened. Same rule as the desktop app's.
    dose = request.dose_g if request.dose_g else _to_float(data.get("dose_g"))

    return SuggestResponse(
        provider=provider,
        model=model,
        summary=str(data.get("summary") or "").strip(),
        dose_g=dose,
        grind_size=str(data.get("grind_size") or "").strip(),
        stages=stages,
    )


@app.post(
    "/v1/vision",
    response_model=VisionResponse,
    dependencies=[Depends(require_api_key)],
)
def vision(request: VisionRequest, sub: str = Depends(require_account)) -> VisionResponse:
    """Bean-label OCR. Centralises what `claude_ocr.py`/`qwen_ocr.py` do on the
    desktop so the client never holds a provider key.

    Anthropic preferred: it supports a schema-validated structured output for
    this, which turns "usually the right JSON" into "the right JSON".
    """
    approx_bytes = len(request.image_base64) * 3 // 4
    if approx_bytes > config.MAX_IMAGE_BYTES:
        raise HTTPException(413, f"image is larger than {config.MAX_IMAGE_BYTES} bytes")

    try:
        provider = providers.pick_provider(request.provider, preferred="anthropic")
    except providers.ProviderNotConfiguredError as exc:
        raise HTTPException(400, str(exc)) from exc

    meter(sub, "vision")

    prompt = prompts.LABEL_OCR
    if provider != "anthropic":
        prompt += prompts.LABEL_OCR_JSON_INSTRUCTION

    try:
        model, content = providers.vision(
            provider,
            image_base64=request.image_base64,
            media_type=request.media_type,
            prompt=prompt,
            schema=prompts.LABEL_OCR_SCHEMA,
        )
    except providers.ProviderRequestError as exc:
        raise HTTPException(502, f"upstream {provider} API error: {exc}") from exc

    data = _parse_json_object(content) or {}
    fields = BeanFields(
        **{
            name: (str(data.get(name) or "").strip() or None)
            for name in prompts.BEAN_FIELD_NAMES
        }
    )
    # "Read nothing useful" is a real outcome (a blurry shot, a photo of a mug)
    # and the client renders it as its own message rather than as an
    # inexplicably blank form -- so say so here instead of making it guess.
    empty = not any(getattr(fields, name) for name in prompts.BEAN_FIELD_NAMES)

    return VisionResponse(provider=provider, model=model, fields=fields, empty=empty)


@app.post("/v1/report", dependencies=[Depends(require_api_key)])
def report(request: ReportRequest, sub: str = Depends(require_account)) -> dict:
    """`legal-android.md` rule 5: somewhere for a user to flag AI output.

    A log line a human reads, deliberately not a row in the account record: a
    report is about the model's output, not about the reporter. The account is
    named only so a flood can be traced to one source.
    """
    logger.warning(
        "AI output reported: operation=%s account=%s reason=%s output=%r",
        request.operation, sub[:8] + "...", request.reason, (request.output or "")[:500],
    )
    return {"status": "received"}


# ----------------------------------------------------------- read endpoints --
# Cheap, cached, no provider spend -- hence the separate read key. Still
# sign-in-gated at the app level, but not metered per account: serving a cached
# list is not a cost that needs rationing.


@app.get("/v1/catalogue", response_model=CatalogueResponse, dependencies=[Depends(require_read_key)])
def catalogue() -> CatalogueResponse:
    try:
        items, fetched_at, rubric = crawler.catalogue()
    except crawler.CrawlerUnavailableError as exc:
        # 503, not 500: nothing is broken. The feature is gated on compliance
        # work that has not happened, and the message says which.
        raise HTTPException(503, str(exc)) from exc
    return CatalogueResponse(items=items, fetched_at=fetched_at, rubric=rubric)


@app.get("/v1/news", response_model=NewsResponse, dependencies=[Depends(require_read_key)])
def news() -> NewsResponse:
    try:
        items, fetched_at = crawler.news()
    except crawler.CrawlerUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    return NewsResponse(items=items, fetched_at=fetched_at)


# -------------------------------------------------------- account endpoints --


@app.get("/v1/account", response_model=AccountResponse, dependencies=[Depends(require_api_key)])
def account(sub: str = Depends(require_account)) -> AccountResponse:
    """GDPR Art. 15(3). Everything held about this user, which is very little."""
    return AccountResponse(**accounts.access_record(sub))


@app.delete("/v1/account", dependencies=[Depends(require_api_key)])
def delete_account(sub: str = Depends(require_account)) -> dict:
    """GDPR Art. 17 and Play's Account Deletion policy.

    Erases the account record outright. It does not touch the user's phone --
    there is no route from here to it, which is the point of the architecture
    and what the in-app copy has to keep saying plainly.
    """
    accounts.delete(sub)
    return {"status": "deleted", "local_data": "untouched; it is on the device and this server has no copy"}


# ---------------------------------------------------------------- utilities --


def _parse_json_object(text: str):
    """Model replies are JSON *by request*, not by guarantee.

    A model that wraps its object in prose or a ```json fence has still done
    the work, and throwing that away would be a worse outcome than one
    substring search. Anything that is still not an object returns None and
    becomes a clean 502 upstream.
    """
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("```")[1]
        candidate = candidate[4:] if candidate.lower().startswith("json") else candidate
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
