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

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

import accounts
import config
import crawler
import prompts
import providers
import scheduler
import sync_store
from auth import meter, require_account, require_api_key, require_read_key, sync_allowed
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
    else:
        scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="LLM Gateway", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    # DELETE is here for `/v1/account` and nothing else: the web deletion page
    # at coffee-can.org/delete is a browser calling this API cross-origin, and
    # without the method on this list the preflight fails and Play's required
    # deletion route silently does not work.
    allow_methods=["POST", "GET", "DELETE"],
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


@app.delete("/v1/account")
def delete_account(sub: str = Depends(require_account)) -> dict:
    """GDPR Art. 17 and Play's Account Deletion policy.

    Erases the account record outright. It does not touch the user's phone --
    there is no route from here to it, which is the point of the architecture
    and what the in-app copy has to keep saying plainly.

    THE ONLY ENDPOINT WITHOUT `require_api_key`, deliberately (2026-08-25).
    `legal-accounts.md` rules 18-19 require a **public web** deletion page that
    works for someone who has already uninstalled and authenticates by
    re-signing in with Google. That page is static HTML on coffee-can.org, so
    anything it must send is readable by anyone who views source -- and putting
    the metered key there would publish the gate for `/v1/suggest` and
    `/v1/vision` in order to protect a route that erases nothing but the
    caller's own row.

    Nothing is actually given up. `require_api_key` is a coarse traffic gate,
    never the authorisation: `require_account` verifies a Google ID token whose
    audience must match this deployment, and the `sub` it returns is the only
    record touched. Someone holding a valid token for an account can already
    spend that account's quota; letting them delete their own row is not a new
    capability. Do not "restore consistency" by adding the dependency back
    without also solving where the page is supposed to keep the key.
    """
    accounts.delete(sub)
    # The test-only bundle goes with it. On a production deployment this is a
    # no-op because nothing was ever stored; where sync is switched on, an
    # erasure request that left the user's whole coffee log on the disk would
    # be Art. 17 answered with a lie.
    sync_store.delete(sub)
    return {"status": "deleted", "local_data": "untouched; it is on the device and this server has no copy"}


# ------------------------------------------------------- server sync (test) --
#
# OFF UNLESS `SYNC_ALLOWED_EMAILS` NAMES YOU, and 404 for everyone else -- see
# `auth.sync_allowed` for why the gate is on this side and why it is a 404.
#
# This is the only part of this server that holds user content, and it exists
# to try phone-to-phone sync before deciding whether to reopen
# `specs/legal-accounts.md` §3.8 and ship it. Read `sync_store`'s docstring
# before touching any of it.
#
# THE SERVER IS A DUMB BLOB STORE AND MUST STAY ONE. It takes the same
# `SyncBundle` zip the app already writes for desktop sync and hands it back
# unread. Merging happens on the phone, which is the only place that can ask
# the user what to do about a conflict -- and keeping the merge there keeps one
# format, one version number and one set of rules across all three programs
# (`data/SyncBundle.kt`, `coffee_agent/sync_tools.py`, and this).


@app.get("/v1/sync/status", dependencies=[Depends(require_api_key)])
def sync_status(sub: str = Depends(sync_allowed)) -> dict:
    """Whether this account may sync, and whether anything is stored for it.

    The app calls this to decide whether to draw the button at all. Reaching a
    200 here *is* the answer -- an account that is not allowlisted gets the
    same 404 as one hitting a server where the feature does not exist.
    """
    payload = sync_store.load(sub)
    return {"enabled": True, "has_bundle": payload is not None, "bytes": len(payload or b"")}


@app.get("/v1/sync", dependencies=[Depends(require_api_key)])
def sync_download(sub: str = Depends(sync_allowed)) -> Response:
    """This account's stored bundle, byte for byte.

    204 rather than 404 when nothing is stored: "you have never uploaded" is a
    normal first-run state on a new phone, and the client renders it as "there
    was nothing to pull" rather than as a failure. A 404 here would be
    indistinguishable from the not-allowlisted 404 the gate returns.
    """
    payload = sync_store.load(sub)
    if payload is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(content=payload, media_type="application/zip")


@app.post("/v1/sync", dependencies=[Depends(require_api_key)])
async def sync_upload(request: Request, sub: str = Depends(sync_allowed)) -> dict:
    """Replaces this account's stored bundle with the request body.

    The body is read as raw bytes rather than multipart: the client already has
    a zip on disk and there is exactly one part, so a multipart wrapper would
    be a second encoding to get wrong on two sides.

    THE SIZE CHECK RUNS BEFORE THE WRITE, not after, and does not trust
    Content-Length -- that header is whatever the client said. `request.body()`
    is bounded by the ASGI server's own limits, so this is the belt to that
    braces: it refuses an oversized payload rather than letting it land on the
    disk and deleting it afterwards.
    """
    payload = await request.body()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty body")
    if len(payload) > config.SYNC_MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"bundle is {len(payload)} bytes; the limit is {config.SYNC_MAX_BYTES}",
        )
    # A bundle is a zip and nothing else is accepted. This is a sanity check on
    # a client bug, not a security boundary -- the bytes are never unpacked
    # here -- but storing something that is not a bundle would only fail later,
    # on another device, where it is much harder to work out why.
    if payload[:2] != b"PK":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "body is not a zip")
    sync_store.store(sub, payload)
    return {"status": "stored", "bytes": len(payload)}


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
