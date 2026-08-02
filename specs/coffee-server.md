# `coffee_server/` — LLM Gateway

A small stateless FastAPI service that proxies chat requests to Anthropic, Qwen, or DeepSeek — the client picks the provider per request, the server forwards the call and returns the text.

- [1. Project background](#1-project-background)
- [2. Development details](#2-development-details)
- [3. API](#3-api)

---

## 1. Project background

### What it is designed for

A single authenticated HTTP endpoint in front of three LLM vendors. Client apps hold one credential (`X-API-Key`) and one URL instead of three vendor SDKs and three sets of provider keys; the provider keys stay on the server. Swapping vendors becomes a field in the request body rather than a client-side code change.

It is deliberately **stateless pass-through**:

- No conversation memory. Multi-turn works by the client sending its full history in `messages` each time.
- No tool-calling loop, no agent behaviour.
- No storage of any kind.

That minimalism is the point — it is why the project talks to provider SDKs directly instead of pulling in LangChain/LangGraph for a job that is just "send messages, get text back".

The service ships as a Docker image (plain HTTP on `:8000`, so it fits App Runner, ECS/Fargate, or EC2), and `deploy/deploy.sh` automates the whole EC2 path end to end.

**Security posture.** The server **refuses to start** if `SERVER_API_KEY` is empty — this is a public-facing proxy in front of paid APIs, so there is no "run without auth" mode. If no provider keys are set it still starts, logging a warning, and every `/v1/ask` returns 400.

### Relations with the other two sub-projects

**This sub-project is fully independent of the other two.** It shares no code, no configuration, and no data with them. It is not specific to coffee at all — it is a general-purpose LLM gateway that happens to live in this repo, and would work unchanged if lifted out of it.

| Relation | Status |
| --- | --- |
| `coffee_server/` ↔ `coffee/` | none — never touches coffee-can's database |
| `coffee_server/` ↔ `coffee_agent/` | none — no imports either way |

Worth being explicit about the near-misses, because the resemblance is superficial:

- **It is not what `coffee_agent` talks to.** `coffee_agent` is a local tool-using ReAct agent that calls provider SDKs directly; this is a remote stateless proxy with no tools and no memory. `providers.py`'s docstring calls out the contrast deliberately. The two are alternative shapes of "talk to an LLM", not layers of one stack.
- **It is not what `coffee/` uses for OCR or brew suggestions.** `coffee/` calls Claude, Qwen and DeepSeek directly from its own modules.
- **Its `.env` is separate and must stay that way.** `config.py` loads `.env` by an explicit path (`Path(__file__).parent/".env"`) rather than a bare `load_dotenv()`, precisely because a bare call walks up parent directories and would silently pick up a sibling project's `.env` and its keys.

The three projects overlap only in that all three call the same set of vendors, and each maintains its own credentials for doing so.

---

## 2. Development details

### Layout

```
coffee_server/
├── main.py             # FastAPI app, routes, startup check, CORS
├── schemas.py          # Pydantic request/response models
├── providers.py        # per-provider call implementations + dispatch
├── auth.py             # X-API-Key dependency
├── config.py           # env-driven settings
├── requirements.txt
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

Five modules, ~380 lines total.

### Module responsibilities

| Module | Responsibility |
| --- | --- |
| `main.py` | Builds the `FastAPI` app; defines both routes; the `lifespan` startup check that raises if `SERVER_API_KEY` is unset and logs which providers are configured; CORS middleware. Translates `providers`' two exception types into HTTP 400 and 502. |
| `schemas.py` | `ChatMessage`, `AskRequest`, `AskResponse`. Carries the validation rules — the `provider` `Literal`, the `max_tokens` bounds, and the model validator enforcing exactly one of `prompt`/`messages`. |
| `providers.py` | One function per vendor plus a dispatch table. Normalises the two request shapes into a message list, handles the Anthropic-vs-OpenAI system-prompt difference, and wraps every upstream failure in `ProviderRequestError`. Provider SDKs are imported lazily inside each call. |
| `auth.py` | A single FastAPI dependency comparing the `X-API-Key` header against `config.SERVER_API_KEY` with `hmac.compare_digest` (constant-time). Re-checks that the server key is non-empty and 500s if not, rather than trusting the startup invariant. |
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
  │  qwen/deepseek: _call_openai_compatible() prepends system as a message
  │  ProviderNotConfiguredError → 400   ProviderRequestError → 502
  ▼
AskResponse{provider, model, content}
```

### Deployment topology

`deploy/deploy.sh` is idempotent — it reuses the instance and security group matched by the `INSTANCE_NAME` tag, so re-running it after a code change is the redeploy command rather than a way to accumulate instances.

1. **Prerequisite check** — verifies `aws`, `ssh`, `scp`, `rsync`, `curl` locally, and runs `install-deps.sh` automatically if any are missing (needs `sudo`).
2. **Default VPC** — looks it up; errors with the fix command if there isn't one.
3. **Security group** — created or reused. Two rules, which are the entire access policy: **SSH (22) restricted to the deploying machine's current public IP** (from `checkip.amazonaws.com`), and **`APP_PORT` open to the world** — the app itself enforces `X-API-Key`.
4. **Instance** — `run-instances` with `user-data.sh`, or reuse of a pending/running one with the right tag. `INSTANCE_TYPE` defaults to `t3.micro`. `user-data.sh` runs once on first boot via cloud-init and installs Docker and rsync (Amazon Linux 2023 ships with neither).
5. **Wait** for SSH and Docker to come up, since user-data runs asynchronously after boot.
6. **Ship** — `rsync` of the source, then a separate `scp` of `coffee_server/.env`. The `.env` is *not* in the image; it is injected at run time via `--env-file`.
7. **Build and restart** — over SSH: `docker build -t coffee-server .`, `docker rm -f coffee-server-app`, then `docker run -d --restart unless-stopped -p ${APP_PORT}:8000 --env-file .env`.
8. **Health check** — polls `/healthz` up to 20 times at 3-second intervals, then prints the URL and a ready-to-use `curl`, or points at `docker logs coffee-server-app` on failure.

`deploy/destroy.sh` terminates the instance and deletes the security group. It is deliberately not part of the deploy flow — a forgotten EC2 instance keeps billing.

**Operational basics:** logs via `ssh -i $KEY_FILE ec2-user@<ip> docker logs coffee-server-app`; restart by re-running `deploy.sh`; teardown via `destroy.sh`.

**Documented gaps in the deploy path:** old `/32` SSH rules from previous runs are not removed when your public IP changes (an accumulating allowlist of your own past IPs, not an open one), and no Elastic IP is attached, so the public IP can change if the *instance* is stopped and started (re-running `deploy.sh` only restarts the container).

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
| `provider` | `"anthropic"` \| `"qwen"` \| `"deepseek"` | **yes** | — | must also be configured on the server |
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

### 3.3 Internal API (`providers.py`)

```python
ask(provider, *, messages, prompt, system, model, max_tokens) -> tuple[str, str]
```
Returns `(resolved_model, response_text)`. `provider` is assumed already validated against the `Literal` in `AskRequest`.

```python
call_anthropic(*, messages, prompt, system, model, max_tokens) -> tuple[str, str]
call_qwen(**kwargs)      -> tuple[str, str]   # via _call_openai_compatible
call_deepseek(**kwargs)  -> tuple[str, str]   # via _call_openai_compatible
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
| DeepSeek | `openai` | `deepseek-chat` | `https://api.deepseek.com/v1` |

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
| `DEEPSEEK_API_KEY` | no | *(empty)* | Enables the `deepseek` provider |
| `DEEPSEEK_MODEL` | no | `deepseek-chat` | |
| `DEEPSEEK_MAX_TOKENS` | no | `8192` | |
| `DEEPSEEK_BASE_URL` | no | `https://api.deepseek.com/v1` | |

At least one provider key is needed for the service to be useful; with none, it starts and logs a warning, and every `/v1/ask` returns 400.

**Deploy-time** (`coffee_server/deploy/.env`, local only — never copied to the server)

| Variable | Default | Purpose |
| --- | --- | --- |
| `KEY_NAME` | *(empty)* | EC2 key pair name **as registered in AWS**, not a path. Must be `pem` format. |
| `KEY_FILE` | `~/Downloads/coffee-server-key.pem` | Local path to that pair's private key |
| `AWS_REGION` | *(empty)* | Falls back to whatever `aws configure` has set |
| `INSTANCE_TYPE` | `t3.micro` | Free-tier eligible |
| `INSTANCE_NAME` | `coffee-server` | Tag used to find/reuse the instance and security group; change it to manage a second independent deployment |
| `APP_PORT` | `8000` | Host port published from the container and opened to the internet |

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
