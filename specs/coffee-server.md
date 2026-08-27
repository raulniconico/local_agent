# `coffee_server/` — LLM Gateway

A small stateless FastAPI service that proxies chat requests to Anthropic or Qwen — the client picks the provider per request, the server forwards the call and returns the text.

- [1. Project background](#1-project-background)
- [2. Development details](#2-development-details)
- [3. API](#3-api)

---

## 1. Project background

### What it is designed for

A single authenticated HTTP endpoint in front of three LLM vendors. Client apps hold one credential (`X-API-Key`) and one URL instead of three vendor SDKs and three sets of provider keys; the provider keys stay on the server. Swapping vendors becomes a field in the request body rather than a client-side code change.

It is deliberately **stateless with respect to user content**:

- No conversation memory. Multi-turn works by the client sending its full history in `messages` each time.
- No tool-calling loop, no agent behaviour.
- **No user content is stored.** No bean, session, note or photo is ever written to disk, and request payloads are never logged.

That minimalism is the point — it is why the project talks to provider SDKs directly instead of pulling in LangChain/LangGraph for a job that is just "send messages, get text back".

**What it does store, and why the distinction matters.** Since 2026-08-14 the
server keeps one small record per signed-in Android user: the Google `sub`, day
counters, quota state and a ban flag (`accounts.py`). It is not an optional
addition — metering and abuse cutoff are impossible without a record keyed to a
user, and this server sits in front of paid provider APIs behind a key that
ships inside a published APK. `specs/legal-accounts.md` rule 58 is explicit
that the architecture must therefore be described as "no user *content*
server-side" and **never** as "no storage": that record is pseudonymous
personal data, it is what a GDPR access or deletion request covers, and a Data
Safety form derived from "we store nothing" would be false.

**Since 2026-08-14 it is also `coffee_android`'s backend**, which changed the
shape of the project in three ways worth naming up front:

- it grew **structured** endpoints (`/v1/suggest`, `/v1/vision`) that render
  their own prompts, alongside the original free-form `/v1/ask`;
- it grew an **identity** dependency (a verified Google ID token) on everything
  that costs money;
- it grew a **crawler** (`crawler.py`, off by default) so that roaster
  catalogue and news data is fetched once here rather than by every installed
  device — `specs/legal-android.md` §4 rule 23.

The service ships as a Docker image (plain HTTP on `:8000`, so it fits App Runner, ECS/Fargate, or EC2), and `deploy/deploy.sh` automates the whole EC2 path end to end.

**Security posture.** The server **refuses to start** if `SERVER_API_KEY` is empty — this is a public-facing proxy in front of paid APIs, so there is no "run without auth" mode. If no provider keys are set it still starts, logging a warning, and every `/v1/ask` returns 400.

### Relations with the other two sub-projects

**It shares no code with any of them** — no imports in either direction, no shared configuration, no shared database. It is still deployable in isolation. What changed on 2026-08-14 is that it is no longer *purpose*-independent: `coffee_android` cannot function without it, and three of its endpoints exist only to serve that client.

| Relation | Status |
| --- | --- |
| `coffee_server/` ↔ `coffee/` | no code shared. Two prompts in `prompts.py` are deliberate near-verbatim **ports** of `claude_ocr.py`'s and `qwen_brew_suggest.py`'s, so the same question gets the same answer in both apps; they are copies, and drift between them should be a decision, not an accident |
| `coffee_server/` ↔ `coffee_agent/` | none — no imports either way. `coffee_agent` may call `/v1/ask` like any other client |
| `coffee_server/` ↔ `coffee_android/` | **the Android app's only backend.** It calls `/v1/suggest`, `/v1/vision`, `/v1/report`, `/v1/account` and (v1.1) `/v1/catalogue`, `/v1/news` — and nothing else, anywhere. See `coffee_android/plan/api.md` |

Worth being explicit about the near-misses, because the resemblance is superficial:

- **It is not what `coffee_agent` talks to.** `coffee_agent` is a local tool-using ReAct agent that calls provider SDKs directly; this is a remote stateless proxy with no tools and no memory. `providers.py`'s docstring calls out the contrast deliberately. The two are alternative shapes of "talk to an LLM", not layers of one stack.
- **It is not what `coffee/` uses for OCR or brew suggestions.** `coffee/` calls Claude and Qwen directly from its own modules. (DeepSeek was removed from the whole repo on 2026-08-03 — both here and in `coffee/`.)
- **Its `.env` is separate and must stay that way.** `config.py` loads `.env` by an explicit path (`Path(__file__).parent/".env"`) rather than a bare `load_dotenv()`, precisely because a bare call walks up parent directories and would silently pick up a sibling project's `.env` and its keys.

The three projects overlap only in that all three call the same set of vendors, and each maintains its own credentials for doing so.

---

## 2. Development details

### Layout

```
coffee_server/
├── main.py             # FastAPI app, routes, startup check, CORS
├── schemas.py          # Pydantic request/response models
├── providers.py        # per-provider call implementations + dispatch (chat + vision)
├── prompts.py          # every prompt the server sends, rendered server-side
├── auth.py             # X-API-Key dependencies + Google ID token verification
├── accounts.py         # the account record: sub, counters, quota, ban. SQLite
├── crawler.py          # roaster catalogue (gated, idle) + press news (live)
├── allowlist.json      # per-domain ROASTER permissions (specs/legal.md rule 3) — empty
├── news_sources.json   # trade-press RSS feeds — 7 enabled, 1 disabled on a 403
├── config.py           # env-driven settings
├── requirements.txt    # two extras are load-bearing -- see below
├── Dockerfile          # python:3.12-slim, uvicorn on :8000
├── .dockerignore       # excludes .env -- never baked into the image
├── .gitignore          # .env, .venv, *.pem, *.ppk
├── .env / .env.example
└── deploy/
    ├── deploy.sh       # create-or-reuse EC2 instance, ship code, build, restart, health-check
    ├── destroy.sh      # terminate instance + delete security group
    ├── install-deps.sh # installs aws/ssh/scp/rsync/curl via apt/dnf/yum/brew
    ├── user-data.sh    # cloud-init: installs Docker + rsync on first boot
    └── .env.example    # deploy-time config (KEY_NAME, KEY_FILE, region, instance type…)
```

Eight modules.

### Module responsibilities

| Module | Responsibility |
| --- | --- |
| `main.py` | Builds the `FastAPI` app; defines every route; the `lifespan` startup check that raises if `SERVER_API_KEY` is unset and warns when `GOOGLE_CLIENT_IDS` is unset or the crawler is disabled; CORS middleware. Translates `providers`' two exception types into HTTP 400 and 502, and `crawler`'s into 503. Owns `_parse_json_object`, the tolerant reader for model replies that arrive fenced or wrapped in prose. |
| `schemas.py` | Every request/response model. Its docstring carries the load-bearing distinction: `/v1/ask` takes a free-form prompt, `/v1/suggest` and `/v1/vision` take **structured fields** — because a shipped client ships its key, so an endpoint it can reach that accepts arbitrary text is a published general-purpose LLM. |
| `prompts.py` | Every prompt, in one file, server-side. Lets prompt wording and the JSON shape asked for be fixed by a deploy rather than by a Play release, and keeps an extracted key worth a coffee-recipe generator rather than a model. |
| `providers.py` | One function per vendor for chat and for vision, plus dispatch tables. Normalises request shapes, handles the Anthropic-vs-OpenAI system-prompt difference, uses Anthropic's schema-validated structured output for OCR where available, and wraps every upstream failure in `ProviderRequestError`. `pick_provider()` decides who serves a request: the client may express a preference and does not get to insist. SDKs are imported lazily. |
| `auth.py` | Two independent guards answering different questions. `require_api_key`/`require_read_key` ask "is this one of our clients?" (a constant-time compare against a key that ships in the APK, so a weak claim by construction). `require_account` asks "**which user** is this?" — a Google ID token verified against Google's JWKS including **audience**, without which any Google token in the world would authenticate. `meter()` maps the account store's refusals onto 429/403. |
| `accounts.py` | The account record and nothing more: `sub`, day counters, sliding-window rate events, ban flag, in SQLite. Also the GDPR Art. 15 access document and Art. 17 erasure. Quota is charged **before** the provider call, so a client that reliably triggers a 502 cannot get unmetered retries. |
| `crawler.py` | The catalogue and news fetch, centrally. Implements `specs/legal.md` §3.3–§3.6 — robots.txt fail-closed, one request at a time per host with jittered delay, budget counters that abort, conditional requests, a truthful User-Agent. **Two source lists, gated differently** (§3.2e): roasters behind the empty `allowlist.json`, press RSS behind `news_sources.json`, which is live. |
| `config.py` | Reads every setting from the environment at import, with an explicitly-pathed `load_dotenv`. `configured_providers()` returns the set of vendors with a key set. |

### Request flow

```
client
  │  POST /v1/ask  + X-API-Key
  ▼
auth.require_api_key          → 401 if the header is missing/wrong
  ▼
schemas.AskRequest            → 422 if the body fails validation
  │                             (bad provider, both/neither prompt+messages, max_tokens out of range)
  ▼
main.ask
  │  is request.provider in config.configured_providers()?   → 400 if not
  ▼
providers.ask → _PROVIDER_CALLS[provider]
  │  _to_pairs()  normalises prompt|messages → [{role, content}]
  │  anthropic: _split_leading_system() lifts a leading system message
  │             into Anthropic's separate `system` field
  │  qwen: _call_openai_compatible() prepends system as a message
  │  ProviderNotConfiguredError → 400   ProviderRequestError → 502
  ▼
AskResponse{provider, model, content}
```

The metered endpoints add two steps in front and one behind, and the order is
deliberate:

```
android client
  │  POST /v1/suggest  + X-API-Key + Authorization: Bearer <Google ID token>
  ▼
auth.require_api_key             → 401  "one of our clients?"
  ▼
auth.require_account             → 401 bad token · 503 if GOOGLE_CLIENT_IDS unset
  │  verify signature/iss/exp/**aud** against Google's JWKS → sub
  │  accounts.touch(sub)         ← first call for a sub *is* account creation
  ▼
providers.pick_provider()        → 400 only if nothing at all is configured
  ▼
auth.meter(sub, "suggest")       → 429 burst · 429 daily quota · 403 banned
  │  charged BEFORE the upstream call, deliberately
  ▼
prompts.brew_suggestion()        ← the prompt is built here, never sent by the client
  ▼
providers.ask → upstream         → 502 on any provider failure
  ▼
main._parse_json_object()        → 502 if the reply is not usable JSON
  ▼
SuggestResponse{provider, model, summary, dose_g, grind_size, stages[]}
```

`pick_provider` runs before metering so that a request nobody can serve is a
400 rather than a charge against the user's quota.

### Deployment topology

`deploy/deploy.sh` is idempotent — it reuses the instance and security group matched by the `INSTANCE_NAME` tag, so re-running it after a code change is the redeploy command rather than a way to accumulate instances.

1. **Prerequisite check** — verifies `aws`, `ssh`, `scp`, `rsync`, `curl` locally, and runs `install-deps.sh` automatically if any are missing (needs `sudo`).
2. **Default VPC** — looks it up; errors with the fix command if there isn't one.
3. **Security group** — created or reused. The rules are the entire access policy: **SSH (22) restricted to the deploying machine's current public IP** (from `checkip.amazonaws.com`), plus — when `API_HOST` is set — **80 and 443 open to the world**, with any world-facing `APP_PORT` rule revoked. Port 80 is required for the ACME HTTP-01 challenge, not merely for the HTTPS redirect: cert issuance fails without it. With `API_HOST` empty the script keeps the older behaviour and opens `APP_PORT` to the world instead.
4. **Instance** — `run-instances` with `user-data.sh`, or reuse of a pending/running one with the right tag. `INSTANCE_TYPE` defaults to `t3.micro`. `user-data.sh` runs once on first boot via cloud-init and installs Docker and rsync (Amazon Linux 2023 ships with neither).
5. **Wait** for SSH and Docker to come up, since user-data runs asynchronously after boot.
6. **Ship** — `rsync` of the source, then a separate `scp` of `coffee_server/.env`. The `.env` is *not* in the image; it is injected at run time via `--env-file`.
7. **Build and restart** — over SSH: `docker build -t coffee-server .`, `docker rm -f coffee-server-app`, then `docker run -d --restart unless-stopped --env-file .env`, with two additions that matter: the port is published as `127.0.0.1:${APP_PORT}:8000` when `API_HOST` is set (Caddy reaches it over the loopback, so it is never on a public interface), and `~/coffee_server/data` is bind-mounted to `/data` with `ACCOUNT_DB_PATH=/data/accounts.db`. **The bind mount is load-bearing:** every deploy does `docker rm -f`, so an in-image `accounts.db` would take the per-user metering records with it each time.
7b. **TLS front end** — when `API_HOST` is set: installs the Caddy binary if absent, writes `/etc/caddy/Caddyfile` (a `reverse_proxy` vhost for `API_HOST`, plus a `file_server` vhost over `/srv/site` for `SITE_HOST` and `www.$SITE_HOST` when that is set too), installs a systemd unit, and restarts it. Caddy obtains and renews Let's Encrypt certificates automatically and redirects HTTP→HTTPS with a 308. The unit uses `LogsDirectory=caddy` rather than a hand-rolled `mkdir`+`chown`: on Amazon Linux a manually created log directory carries the wrong SELinux context and Caddy exits with "permission denied" opening its own log **despite owning the directory**. No ACME account `email` is configured, deliberately — that address is sent to Let's Encrypt, and none has been chosen; certs still issue and renew, only expiry-warning mail is lost.
8. **Health check** — polls `/healthz` up to 20 times at 3-second intervals — against `https://$API_HOST` when set, else `http://<ip>:$APP_PORT` — then prints the base URL and a ready-to-use `curl`, or points at `docker logs coffee-server-app` on failure.

`deploy/destroy.sh` terminates the instance and deletes the security group. It is deliberately not part of the deploy flow — a forgotten EC2 instance keeps billing.

**Operational basics:** logs via `ssh -i $KEY_FILE ec2-user@<ip> docker logs coffee-server-app`; restart by re-running `deploy.sh`; teardown via `destroy.sh`.

**Documented gaps in the deploy path:** old `/32` SSH rules from previous runs are not removed when your public IP changes (an accumulating allowlist of your own past IPs, not an open one). `deploy.sh` also does not allocate the Elastic IP or create the DNS records itself — both were done once by hand (see below) and the script assumes `API_HOST` already resolves to the instance; a first run against a name that does not resolve yet will bring the app up but leave Caddy retrying ACME until DNS lands.

**The live deployment (as of 2026-08-23):** instance `i-0abfc509863f30bc0` in `eu-west-3`, Elastic IP `13.36.4.67`, Route 53 hosted zone `Z02940141ZRYBNM9AY30X` for `coffee-can.org` with `api`, apex and `www` all pointing at that address. The Elastic IP matters more than it did before TLS: a certificate is bound to a name, the name is bound to an A record, and letting the address change out from under it breaks both the app and renewal.

### Secrets handling

- `.env` is git-ignored, and `.dockerignore` excludes it so it is **never baked into the image**.
- `*.pem` and `*.ppk` are git-ignored. `deploy/coffee-server-key.pem` exists locally and is correctly untracked — verified: zero `.pem` files are in the index.
- `deploy/.env` is local deploy-time config (which instance, which key file) and is never copied to the server, unlike `coffee_server/.env` which is.
- For managed platforms the README is explicit: source `SERVER_API_KEY` and provider keys from Secrets Manager/SSM via the task definition's `secrets` block, not plain `environment` values.

### Development history

Two commits touch `coffee_server/` — `c210356` "add server" (1 Aug 2026) and `822494c` (2 Aug 2026). The service arrived essentially complete in the first: the five modules, both endpoints, all three providers, the Docker image, and the full `deploy/` automation.

Currently untracked: `.dockerignore` and `.gitignore` only. The `deploy/` directory is committed (5 files).

**Deliberately not implemented yet**, per the README — these are stated omissions rather than oversights:

- Rate limiting / per-client quotas. One shared `SERVER_API_KEY` authenticates all clients equally; nothing stops one client running up the bill.
- Streaming responses. `/v1/ask` waits for the full completion.
- Structured logging, metrics, or tracing beyond the single startup log line.
- Multiple API keys or per-key usage tracking.

---

## 3. API

### 3.1 `GET /healthz`

Unauthenticated. For load balancer / ECS health checks.

```
200 OK   {"status": "ok"}
```

### 3.2 `POST /v1/ask`

Requires header `X-API-Key: <SERVER_API_KEY>`.

**Request body** (`schemas.AskRequest`)

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `provider` | `"anthropic"` \| `"qwen"` | **yes** | — | must also be configured on the server |
| `prompt` | string | exactly one of | — | single-turn shorthand |
| `messages` | `ChatMessage[]` | `prompt`/`messages` | — | full history for multi-turn |
| `system` | string | no | — | system prompt override |
| `model` | string | no | provider's configured default | |
| `max_tokens` | integer | no | provider's configured cap | must satisfy `0 < n ≤ 32768` |

`ChatMessage` — `{"role": "system" | "user" | "assistant", "content": str}`.

> A model validator enforces **exactly one** of `prompt` or `messages`: sending both, or neither, is a validation error. Note it tests truthiness, so an empty string or empty list counts as absent.

**System-prompt handling differs by provider.** Anthropic takes `system` as its own top-level field and rejects a `"system"` role inside `messages`, so `_split_leading_system()` lifts a leading system message out of the list (an explicit `system` field wins if both are given). The OpenAI-compatible providers get it prepended as a message instead, unless one is already there.

**Response** (`schemas.AskResponse`)

```json
{"provider": "qwen", "model": "qwen-max", "content": "Paris."}
```

`model` is the *resolved* model — the request's `model` if given, otherwise the server's configured default for that provider.

**Errors**

| Status | Cause |
| --- | --- |
| `401` | missing or wrong `X-API-Key` |
| `422` | body failed schema validation (bad `provider` value, both/neither `prompt`+`messages`, `max_tokens` out of range) |
| `400` | `provider` valid but has no API key configured on this server |
| `500` | server itself is missing `SERVER_API_KEY` (defensive; startup normally prevents this) |
| `502` | the upstream provider API returned an error — its message is included |

**Examples**

```bash
# single-turn
curl -s http://localhost:8000/v1/ask \
  -H "X-API-Key: $SERVER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider": "qwen", "prompt": "What is the capital of France?",
       "system": "Answer in one word.", "model": "qwen-max", "max_tokens": 100}'

# multi-turn
curl -s http://localhost:8000/v1/ask \
  -H "X-API-Key: $SERVER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic",
       "messages": [
         {"role": "user", "content": "Hi, I am planning a trip to Kyoto."},
         {"role": "assistant", "content": "Great choice! When are you going?"},
         {"role": "user", "content": "Next April."}
       ]}'
```

### 3.2a `POST /v1/suggest` — brew suggestion (the Android client's Ask-AI)

Requires **both** `X-API-Key` and `Authorization: Bearer <Google ID token>`. Metered as `suggest`.

**Request** — structured, never a prompt:

```json
{"bean": {"name": "Ethiopia Guji", "origin": "Guji", "process": "Natural",
          "roaster": "Belleville", "note": "blueberry, jasmine"},
 "dripper": "Hario V60", "dose_g": 15, "provider": "qwen"}
```

Every `bean` field is optional and length-capped. `provider` is a *preference*; an unconfigured one silently falls back (`providers.pick_provider`), because a user asking for a recipe wants a recipe, not a lecture about server configuration. Qwen is preferred — it is the text-reasoning task the desktop app already points there, and the cheaper of the two.

**Response** — parsed and normalised server-side, so the client gets a typed shape rather than a JSON string to defend against:

```json
{"provider": "qwen", "model": "qwen-max",
 "summary": "…", "dose_g": 15.0, "grind_size": "medium-fine",
 "stages": [{"temperature_c": 92, "water_g": 30, "time_seconds": 30, "circling": "swirl gently"}]}
```

**A supplied `dose_g` is a constraint, not a suggestion**: it is forced back into the response after the model replies. The user is going to weigh out that much whatever the model says, and writing a drifted number into their session would record a brew that never happened. Same rule as `qwen_brew_suggest.py`'s.

### 3.2b `POST /v1/vision` — bean-label OCR

Requires both credentials. Metered as `vision`. Centralises what `claude_ocr.py`/`qwen_ocr.py` do on the desktop, so the Android client never holds a provider key.

```json
// request
{"image_base64": "<base64>", "media_type": "image/jpeg"}
// response
{"provider": "anthropic", "model": "claude-opus-5",
 "fields": {"name": "…", "origin": "…", "…": null}, "empty": false}
```

The field list is `prompts.BEAN_FIELD_NAMES`: **name, origin, variety, altitude, roaster, producer, farm, process, roast_date, note** — the response `fields` object, the Anthropic output schema and the Qwen key list are all generated from it, so adding a field means editing that tuple and `schemas.BeanFields`, and nothing else here.

**It is a hand-written copy of `coffee_can.repo.LABEL_FIELDS`**, since this server does not import coffee-can. Same two exclusions from `BEAN_FIELDS`, for the same reasons: the eleven flavour axes are scored from brews rather than printed on a bag, and `frozen_date` is the day the bag's *owner* put it in a freezer, which no roaster can know. `farm` joined both lists on 2026-08-26, with prompt wording that keeps it apart from `producer` — the grower is a person or a cooperative, the farm is the estate, finca, washing station or mill — because a label that prints only one had been getting it copied into both.

Anthropic is preferred here because it supports schema-validated structured output for this, which turns "usually the right JSON" into the right JSON; the Qwen branch appends an explicit key list to the prompt instead. `413` if the decoded image exceeds `MAX_IMAGE_BYTES` (6 MB default). **`empty: true` is a real outcome, not an error** — a blurry shot or a photo of a mug — and the client renders it as its own message rather than as an inexplicably blank form.

EXIF stripping is the *client's* job, at ingest (`legal-android.md` rule 2). The server cannot verify it happened, which is precisely why the rule places it at capture time on the device.

### 3.2c `POST /v1/report` — flag AI output

Requires both credentials, **not** metered and not consent-gated. `{"operation": "read_labels"|"suggest_brew", "reason": str?, "output": str?}` → `{"status": "received"}`. Written to the log for a human, deliberately not into the account record: a report is about the model's output, not about the reporter. Satisfies `legal-android.md` rule 5.

### 3.2d `GET` / `DELETE /v1/account` — access and erasure

Requires both credentials. `GET` returns the entire Art. 15(3) access document — the `sub`, usage counters, quota state, held rate-limit events, and a sentence stating what is *not* here. `DELETE` erases the record outright (hard delete, no tombstone) and touches nothing on the device, because there is no route from here to it.

### 3.2e `GET /v1/catalogue`, `GET /v1/news` — v1.1, cache reads

Require `X-API-Key` matching **`READ_API_KEY`** (the metered key is also accepted). No account, no metering: serving a cached list is not a cost that needs rationing.

**The two halves are gated differently, and that is the point (2026-08-23).**

`GET /v1/news` **works.** It serves cached headlines from the RSS feeds in `news_sources.json` — seven trade publications, refreshed hourly. Items carry headline, source, date and canonical link and nothing else, per `legal-accounts.md` rule 74: no snippet past the headline and specifically no AI-written summary, since the *droit voisin* exclusion (arts. L.218-1 CPI, DSM art. 15) covers hyperlinks and very short extracts but not summaries.

`GET /v1/catalogue` still returns `503`, with a message naming the reason: `specs/legal.md` rules 2–3 (outreach, the 14-day wait, a per-domain allowlist entry) and `specs/legal-accounts.md` rule 72 (`legal.md` §1.2's use case must be re-opened before crawl results are served to Play users) are unmet. `allowlist.json` ships with `"sources": []`, so **`CRAWLER_ENABLED=1` alone still crawls nothing**: the switch is not the permission.

**Why press feeds are not on the roaster allowlist.** `specs/legal.md` is titled and scoped to crawling *French roasters' e-commerce catalogues*; rules 2–3 buy permission for an act whose permission is genuinely in doubt. An RSS feed is the inverse — published *in order to be read by machines*, which is the tier-2 first-party structured endpoint §3.2 rule 7 tells you to prefer. Requiring an outreach email and a verbatim CGU quotation before reading one is a category error, and it is why `/v1/news` returned `503` for months while `coffee/src/coffee_can/coffee_news.py` polled the same eight feeds from the desktop without difficulty. Two files, two justifications, one `Source` type carrying a `kind` of `"roaster"` or `"press"` so `Fetcher` applies identically to both.

What did **not** get relaxed: robots.txt, the per-host delay, conditional GETs and the truthful User-Agent all still apply, because they are what actually protects the publisher. A feed that refuses this crawler is disabled with its reason recorded (`comunicaffe.com`, `403`), never worked around — `legal.md` rule 18 forbids changing the User-Agent to get past a refusal. `legal-android.md` rule 23 is *satisfied* rather than bypassed: moving these feeds server-side is what makes the fetch happen once, centrally, instead of once per installed device.

`/v1/catalogue` carries a `rubric` object alongside its items — the art. D.111-16 ranking/links/exhaustiveness/frequency disclosure — served with the data so the catalogue screen renders it without French consumer law being compiled into an APK, and so correcting it is a deploy rather than a release (`legal-accounts.md` rule 76).

### 3.2f `GET /v1/sync/status`, `GET`/`POST /v1/sync` — server sync (**test only**)

**This is the only part of this server that holds user content, and it is off
unless an account is explicitly allowlisted.** Everything else here is
stateless with respect to what the user writes: the only per-user row is the
metering record. `specs/legal-accounts.md` §3.8 binds the *shipped*
architecture to no user content server-side — which is what the Android app's
privacy screen says in three languages, and what the Play Data safety form
declares. Desktop sync is a file the user carries between their own two devices
precisely so the developer never holds a copy.

These three endpoints exist so phone-to-phone sync can be **tried** before
anyone decides whether to reopen §3.8 and ship it. See `sync_store.py`'s
docstring and `legal-accounts.md` §3.8a.

| | |
| --- | --- |
| Auth | `X-API-Key` **and** `Depends(auth.sync_allowed)` |
| Gate | the verified Google `email` claim must be in `SYNC_ALLOWED_EMAILS`, and `email_verified` must be true |
| Metered | no — not an AI operation, and not billed |

**The gate is here, not in the client, and it answers 404.** The Android app
never learns its own email address (`account/GoogleAuth.kt`, `legal-accounts`
rule 60), so it cannot make this decision; and a client-side allowlist would be
no gate at all, since anyone can rebuild an app. 404 rather than 403 for both
"not allowlisted" and "feature off" (`SYNC_ALLOWED_EMAILS` empty, the default
and what production runs): a 403 would advertise a private feature to everyone
who probed for it. `email_verified` is required as well as `email`, because an
unverified claim is a string the account holder typed.

```
GET  /v1/sync/status  ->  200 {"enabled": true, "has_bundle": bool, "bytes": int}
GET  /v1/sync         ->  200 application/zip  |  204 (nothing stored yet)
POST /v1/sync         <-  raw application/zip  ->  200 {"status": "stored", "bytes": int}
```

**The server is a dumb blob store and must stay one.** It takes the same
`SyncBundle` zip the Android app already writes for desktop sync
(`data/SyncBundle.kt`, `coffee_agent/sync_tools.py` on the other side) and
hands it back unread — one bundle per account, replacing the last. It does not
parse, merge or version-check the contents. **The merge happens on the phone**,
which is the only place that can ask the user anything, and keeping it there
keeps one format, one version number and one set of merge rules across all
three programs.

The client's cycle is **pull, merge, push**, in that order: importing the
remote bundle *before* uploading means the copy it sends back already contains
what the other phone added, so two devices alternating converge. Uploading
first would make the last phone to sync the winner. The merge is
`SyncBundle.importFrom`, which never overwrites — a bean whose name is already
present is skipped and counted (a real limitation shared with the file route:
an edit made on the other phone does not travel).

Other properties worth keeping:

- **204, not 404, when nothing is stored.** "You have never uploaded" is a
  normal first run on a new phone, and a 404 there would be indistinguishable
  from the gate's own 404.
- **Blobs are named by `sha256(sub)`, not by `sub`.** The account id is
  pseudonymous personal data (rule 61) and a directory listing is the easiest
  place in a deployment to leak one by accident.
- **Writes are `tempfile` + `os.replace`.** A phone that drops its connection
  mid-upload would otherwise leave a truncated zip where its whole log was.
- **`DELETE /v1/account` deletes the bundle too** — Art. 17 answered with the
  log still on disk would be a lie.
- Body must start with `PK` and fit `SYNC_MAX_BYTES` (default 64 MB), checked
  before anything is written.

### 3.3 Internal API (`providers.py`)

```python
ask(provider, *, messages, prompt, system, model, max_tokens) -> tuple[str, str]
```
Returns `(resolved_model, response_text)`. `provider` is assumed already validated against the `Literal` in `AskRequest`.

```python
call_anthropic(*, messages, prompt, system, model, max_tokens) -> tuple[str, str]
call_qwen(**kwargs)      -> tuple[str, str]   # via _call_openai_compatible
```

| Exception | Meaning | Becomes |
| --- | --- | --- |
| `ProviderNotConfiguredError` | requested provider has no API key on this server | HTTP 400 |
| `ProviderRequestError` | wraps any upstream SDK/HTTP failure | HTTP 502 |

> **Sampling parameters are deliberately never sent.** `call_anthropic` passes only `model`, `max_tokens`, `messages` and optionally `system`, because Claude Opus 5 rejects `temperature`/`top_p` with a 400 — the same constraint the sibling `coffee_agent` works under.

Text extraction differs by shape: Anthropic returns content blocks, joined with `"".join(block.text for block in response.content if block.type == "text")`; the OpenAI-compatible path reads `response.choices[0].message.content or ""`.

### 3.4 Upstream APIs consumed

| Provider | SDK | Default model | Default base URL |
| --- | --- | --- | --- |
| Anthropic | `anthropic` | `claude-opus-5` | SDK default |
| Qwen | `openai` | `qwen-max` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |

### 3.5 Configuration

**Server** (`coffee_server/.env`, copied to the instance by `deploy.sh`)

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SERVER_API_KEY` | **yes** | *(empty)* | Shared secret for `X-API-Key`. **The server refuses to start without it.** |
| `ALLOWED_ORIGINS` | no | `*` | Comma-separated CORS origins. `*` is safe here — auth is an explicit header, not a cookie, so cross-origin callers still need the real key. |
| `PORT` | no | `8000` | Read into config; the Dockerfile's `CMD` hardcodes `--port 8000`. |
| `ANTHROPIC_API_KEY` | no | *(empty)* | Enables the `anthropic` provider |
| `ANTHROPIC_MODEL` | no | `claude-opus-5` | |
| `ANTHROPIC_MAX_TOKENS` | no | `8192` | |
| `QWEN_API_KEY` | no | *(empty)* | Enables the `qwen` provider |
| `QWEN_MODEL` | no | `qwen-max` | |
| `QWEN_MAX_TOKENS` | no | `8192` | |
| `QWEN_BASE_URL` | no | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Mainland-China accounts need the non-`-intl` host |

| `READ_API_KEY` | no | falls back to `SERVER_API_KEY` | The catalogue/news key. Split from the metered key so a catalogue-triggered rotation cannot take the AI features down with it — `coffee_android/plan/api.md` §2 |
| `GOOGLE_CLIENT_IDS` | for the Android client | *(empty)* | Comma-separated OAuth **web** client IDs. The audience allowlist for ID tokens. Empty **fails closed**: `/v1/suggest`, `/v1/vision` and `/v1/account` all 503, because serving paid calls to unauthenticated callers is the failure the whole module exists to prevent |
| `ACCOUNT_DB_PATH` | no | `coffee_server/accounts.db` | SQLite file holding the account records. Not user content — see `accounts.py`. **`deploy.sh` sets this to `/data/accounts.db` and bind-mounts it**, so the records survive the `docker rm -f` every deploy performs |
| `DAILY_QUOTA_ASK` / `_SUGGEST` / `_VISION` | no | `60` / `5` / `5` | Per-account daily caps, per UTC day. `_SUGGEST` is Ask AI and `_VISION` is Scan photo; both went to **5** on 2026-08-25 by direct product request, which makes them product limits rather than the abuse cutoffs they were at 60/40 |
| `RATE_LIMIT_WINDOW_SECONDS` | no | `60` | Sliding burst window |
| `RATE_LIMIT_MAX_REQUESTS` | no | `6` | Requests per account per operation per window |
| `ANTHROPIC_VISION_MODEL` | no | `claude-opus-5` | Separate from the chat model on purpose, so one can move without the other |
| `QWEN_VISION_MODEL` | no | `qwen3.5-omni-flash` | |
| `MAX_IMAGE_BYTES` | no | `6291456` | Beyond this, `/v1/vision` returns 413 |
| `CRAWLER_ENABLED` | no | *off* | Gates **both** halves. On today. Turning it on with an empty *roaster* allowlist still crawls no roaster; the press feeds are a separate list and do run |
| `CRAWLER_ALLOWLIST_PATH` | no | `coffee_server/allowlist.json` | Roaster permissions. Empty today |
| `CRAWLER_NEWS_SOURCES_PATH` | no | `coffee_server/news_sources.json` | Press RSS feeds. **A separate file from the allowlist on purpose** — see §3.2e |
| `CATALOGUE_TTL_SECONDS` / `NEWS_TTL_SECONDS` | no | `86400` / `7200` | |
| `QUOTA_EXEMPT_EMAILS` | no | *(falls back to `SYNC_ALLOWED_EMAILS`)* | Accounts the daily cap does not apply to — the developer's own. Comma-separated verified Google email addresses, matched at token-verification time and **never stored**; what reaches the database is one boolean per account (`accounts.unlimited`). The burst limiter and the ban check still apply to an exempt account. Defaults to `SYNC_ALLOWED_EMAILS` because both name the developer's own account and the live server already sets that one — set this explicitly to break the two apart |
| `SYNC_ALLOWED_EMAILS` | no | *(empty)* | **The server-sync test gate — §3.2f.** Comma-separated verified Google email addresses. Empty (the default, and what production runs) makes every sync endpoint 404 as if it did not exist. **Adding an address has legal consequences for whoever is added**: it makes the developer a data controller for that person's coffee log. Do not add a second one without reopening `legal-accounts.md` §3.8 |
| `SYNC_DIR` | no | `coffee_server/sync_blobs` | Where the per-account bundles live, named `sha256(sub).zip`. **Needs the same bind-mount treatment as `ACCOUNT_DB_PATH`** if the feature is ever used on a deployed instance, or every deploy's `docker rm -f` throws the bundles away |
| `SYNC_MAX_BYTES` | no | `67108864` | Upload cap. A bundle is a zip of a log plus its photos, so this is generous; it is there to stop a bad client filling the disk |
| `CRAWLER_USER_AGENT` | no | `CoffeeBeanIndexBot/0.1 (+https://coffee-can.org/bot; bot@coffee-can.org)` | `specs/legal.md` rule 17 requires it to be truthful with a contact that resolves; **rule 18 forbids ever replacing it with a browser string** |
| `CRAWLER_CONTACT_EMAIL` | no | `bot@coffee-can.org` | Sent as the `From` header |

At least one provider key is needed for the service to be useful; with none, it starts and logs a warning, and every `/v1/ask` returns 400.

### Two dependency extras that are not optional

Both were found by the failure they cause, and both fail *late* — the image
builds, the server starts, and the breakage appears only when a real request
exercises the path:

| Requirement | Without the extra |
| --- | --- |
| `google-auth[requests]` | `auth.py` imports `google.auth.transport.requests`, which needs the `requests` package. Plain `google-auth` imports fine, then **every** token verification returns `500 "The requests library is not installed"`. Invisible until account auth is both configured and used |
| `httpx[brotli]` | `Fetcher` advertises `Accept-Encoding: gzip, br`. With no brotli decoder, httpx returns undecoded bytes and XML parsing fails at line 1 column 0. Five of eight news feeds did exactly this |

The second is worth stating as a rule: **advertise only the encodings you can
decode.** The desktop client worked throughout precisely because it never
advertised `br`.

**Deploy-time** (`coffee_server/deploy/.env`, local only — never copied to the server)

| Variable | Default | Purpose |
| --- | --- | --- |
| `KEY_NAME` | *(empty)* | EC2 key pair name **as registered in AWS**, not a path. Must be `pem` format. |
| `KEY_FILE` | `~/Downloads/coffee-server-key.pem` | Local path to that pair's private key |
| `AWS_REGION` | *(empty)* | Falls back to whatever `aws configure` has set |
| `INSTANCE_TYPE` | `t3.micro` | Free-tier eligible |
| `INSTANCE_NAME` | `coffee-server` | Tag used to find/reuse the instance and security group; change it to manage a second independent deployment |
| `APP_PORT` | `8000` | Port published from the container. Bound to `127.0.0.1` and fronted by Caddy when `API_HOST` is set; published publicly only in the no-TLS fallback |
| `API_HOST` | *(empty)* | Public hostname Caddy terminates TLS on and reverse-proxies to `APP_PORT`. **Must already resolve to the instance before the first run**, or ACME issuance fails. Empty disables Caddy entirely and restores plain HTTP on `APP_PORT` |
| `SITE_HOST` | *(empty)* | Apex for the website vhost, which also serves `www.<SITE_HOST>` from `/srv/site`. Empty means no website vhost |

### 3.6 Running

```bash
# local
cd coffee_server
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env && $EDITOR .env      # SERVER_API_KEY + at least one provider key
source .venv/bin/activate
uvicorn main:app --reload

# docker
docker build -t llm-gateway .
docker run --rm -p 8000:8000 --env-file .env llm-gateway

# aws ec2 (create or redeploy)
./deploy/deploy.sh
./deploy/destroy.sh
```

FastAPI serves interactive docs at `/docs` and the OpenAPI schema at `/openapi.json` (app title "LLM Gateway", version `0.1.0`).
