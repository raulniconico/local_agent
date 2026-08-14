# LLM Gateway

A small FastAPI server that proxies chat and vision requests to Anthropic
(Claude) or Qwen, and serves the `coffee_android` app. A client picks the
provider per request; the server forwards the call and returns the result. No
conversation memory, no tool-calling loop — that's what the sibling
`../coffee_agent` local agent is for. Meant to run as a Docker container in
front of your own client apps.

**No user content is stored** — no bean, session, note or photo is written to
disk, and request payloads are never logged. One small record *is* kept per
signed-in Android user (the Google `sub`, day counters, quota state, a ban
flag) because metering and abuse cutoff are impossible without one. See
`accounts.py`, and `specs/legal-accounts.md` rule 58 for why the distinction is
stated this way rather than as "we store nothing".

## Endpoints at a glance

| Endpoint | Auth | Metered | Purpose |
| --- | --- | --- | --- |
| `POST /v1/ask` | API key | no | free-form proxy. For `coffee_agent` and local tooling — **the Android app must not use it** (see below) |
| `POST /v1/suggest` | API key + Google ID token | yes | bean fields + dripper → a brew recipe |
| `POST /v1/vision` | API key + Google ID token | yes | bean-label photo → bean fields |
| `POST /v1/report` | API key + Google ID token | no | flag bad AI output |
| `GET`/`DELETE /v1/account` | API key + Google ID token | no | GDPR access / erasure |
| `GET /v1/catalogue`, `/v1/news` | read key | no | cached crawl results. **503 today** — see `crawler.py` |
| `GET /healthz` | none | no | load-balancer probe |

**Why `/v1/suggest` exists when `/v1/ask` already did.** A shipped mobile
client ships its API key, so any endpoint it can reach is an endpoint a
stranger can reach. If that endpoint accepts arbitrary text, the app has
published a general-purpose LLM on your bill. `/v1/suggest` and `/v1/vision`
take structured fields and build the prompt here (`prompts.py`), so the worst
an extracted key plus a Google account buys is coffee recipes, rate-limited.

**Why the Google token.** The API key answers "one of our clients?"; the token
answers *which user*, which is the only thing that can be metered, quota'd or
banned. Set `GOOGLE_CLIENT_IDS` to your OAuth **web** client ID(s) — the
metered endpoints fail closed with 503 until you do.

## API

### `POST /v1/ask`

Requires header `X-API-Key: <SERVER_API_KEY>`.

Request body — provide exactly one of `prompt` or `messages`:

```json
{
  "provider": "qwen",
  "prompt": "What's the capital of France?",
  "system": "Answer in one word.",
  "model": "qwen-max",
  "max_tokens": 100
}
```

or, for multi-turn history:

```json
{
  "provider": "anthropic",
  "messages": [
    {"role": "user", "content": "Hi, I'm planning a trip to Kyoto."},
    {"role": "assistant", "content": "Great choice! When are you going?"},
    {"role": "user", "content": "Next April."}
  ]
}
```

`provider` is required and must be `"anthropic"` or `"qwen"`.
`system`, `model`, and `max_tokens` are all optional overrides — omit `model`
to use that provider's configured default, omit `max_tokens` to use its
configured cap.

Response:

```json
{"provider": "qwen", "model": "qwen-max", "content": "Paris."}
```

Errors: `401` (missing/wrong `X-API-Key`), `400` (bad request body, or a
`provider` with no API key configured on this server), `502` (the upstream
provider API itself returned an error — message included).

### `POST /v1/suggest`

Headers: `X-API-Key` **and** `Authorization: Bearer <Google ID token>`.

```json
{"bean": {"name": "Ethiopia Guji", "process": "Natural", "note": "blueberry"},
 "dripper": "Hario V60", "dose_g": 15}
```
```json
{"provider": "qwen", "model": "qwen-max", "summary": "…", "dose_g": 15.0,
 "grind_size": "medium-fine",
 "stages": [{"temperature_c": 92, "water_g": 30, "time_seconds": 30, "circling": "swirl gently"}]}
```

A supplied `dose_g` is a **constraint**: it is forced back into the response
after the model answers, because the user is going to weigh out that much
whatever the model says.

### `POST /v1/vision`

Same headers. `{"image_base64": "…", "media_type": "image/jpeg"}` →
`{"provider", "model", "fields": {…}, "empty": false}`. `413` past
`MAX_IMAGE_BYTES` (6 MB). `empty: true` means the photo was unreadable, which
is a normal answer, not an error.

### `POST /v1/report`, `GET`/`DELETE /v1/account`

Same headers. `/v1/report` logs a flagged AI output for a human to read.
`GET /v1/account` returns everything held about the caller; `DELETE` erases it
and touches nothing on their phone, because there is no route from here to it.

### `GET /v1/catalogue`, `GET /v1/news`

`X-API-Key: <READ_API_KEY>`. Serve the crawler's cache. **Both return 503
today**, deliberately: `allowlist.json` is empty and `CRAWLER_ENABLED` is off,
because `specs/legal.md` rules 2–3 (per-domain outreach, a 14-day wait, a
committed allowlist entry) and `specs/legal-accounts.md` rule 72 are unmet.
Setting `CRAWLER_ENABLED=1` with an empty allowlist still crawls nothing — the
switch is not the permission.

### `GET /healthz`

Unauthenticated. Returns `{"status": "ok"}`. Point your load balancer /
ECS health check here.

## Running locally

```bash
cd coffee_server
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
$EDITOR .env   # set SERVER_API_KEY and at least one provider's API key
source .venv/bin/activate
uvicorn main:app --reload
```

```bash
curl -s http://localhost:8000/v1/ask \
  -H "X-API-Key: $SERVER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider": "qwen", "prompt": "Say OK and nothing else."}'
```

The server refuses to start if `SERVER_API_KEY` is empty (see `main.py`'s
startup check) — this is a public-facing proxy in front of paid APIs, so
there's no "run without auth" mode. If no provider keys are set at all, it
still starts (logging a warning) but every `/v1/ask` call returns `400`.

## Running in Docker

```bash
cd coffee_server
docker build -t llm-gateway .
docker run --rm -p 8000:8000 --env-file .env llm-gateway
```

## Deploying to AWS

The image is a plain HTTP server listening on `8000`, so it fits any of:

- **App Runner** — simplest option. Push the image to ECR, point App Runner
  at it, set environment variables (or wire them from Secrets Manager) in
  the App Runner service config.
- **ECS on Fargate** — push to ECR, create a task definition referencing the
  image, set env vars in the task definition (use `secrets` sourcing from
  Secrets Manager/SSM for the API keys, not plain `environment` values), put
  the service behind an ALB with a health check on `/healthz`.
- **EC2** — `docker run` directly, same as local, behind your own reverse
  proxy / ALB. See [Deploying with deploy.sh](#deploying-with-deploysh)
  below for a script that automates exactly this.

In all cases: **never bake `.env` into the image** (`.dockerignore` already
excludes it) — inject `SERVER_API_KEY` and the provider keys as environment
variables from the platform's secret store at deploy time.

## Deploying with deploy.sh

`deploy/deploy.sh` automates the EC2 path above end-to-end: creates the
instance (or reuses one it already made), ships this directory's code and
your `.env` to it over SSH, and builds/(re)starts the Docker container there.
Re-running it after a code change redeploys — it doesn't create a second
instance.

It checks for its own local prerequisites (`aws`, `ssh`, `scp`, `rsync`,
`curl`) on startup and, if anything's missing, runs `deploy/install-deps.sh`
automatically to install them via `apt`/`dnf`/`yum`/Homebrew (whichever is
present) — this needs `sudo` and will prompt for your password. Run
`./deploy/install-deps.sh` yourself beforehand if you'd rather install things
before `deploy.sh` touches anything.

### One-time AWS setup

1. **Configure the AWS CLI**: `aws configure` (needs an IAM user or role
   with EC2 full access and `ssm:GetParameters`, e.g. the AWS-managed
   `AmazonEC2FullAccess` policy plus SSM read access for the AMI lookup). The
   CLI itself gets installed automatically by `deploy.sh` if it isn't
   already, but `aws configure`'s credential prompts are interactive, so run
   that part yourself.
2. **Create an EC2 key pair in `.pem` format** — EC2 console → Key Pairs →
   Create key pair → File format: `pem` (not `ppk`; a `.ppk`-format pair's
   private key can't be re-downloaded in `.pem` form after creation, since
   AWS only lets you download it once, at creation time — if you already
   made a `.ppk` one for manual/PuTTY access, this is a second, separate
   pair used only by this script). Save the downloaded file somewhere local
   and `chmod 400` it.
3. **Fill in `coffee_server/.env`** (copy from `.env.example` if you haven't)
   with real `SERVER_API_KEY` and at least one provider's API key — this is
   the file that gets copied to the instance.
4. **Configure the deploy script**:
   ```bash
   cd coffee_server/deploy
   cp .env.example .env
   $EDITOR .env   # set KEY_NAME (the pair's name in AWS) and KEY_FILE (its local .pem path)
   ```

### Deploy / redeploy

```bash
./deploy/deploy.sh
```

This prints the instance's public IP and a ready-to-use `curl` command once
`/healthz` responds. Run it again anytime after changing code or `.env` — it
reuses the same instance and security group (matched by the `INSTANCE_NAME`
tag in `deploy/.env`) and just rebuilds/restarts the container.

What it does *not* handle: it does not remove old `/32` SSH security-group
rules from a previous run if your public IP has since changed (harmless —
just an accumulating allowlist of your own past IPs, not an open one), and
it does not attach an Elastic IP, so the public IP can change if the
instance is stopped and restarted (it won't change from re-running
`deploy.sh`, which only stops/restarts the *container*, not the instance).

### Tear down

```bash
./deploy/destroy.sh
```

Terminates the instance and deletes the security group `deploy.sh` created.
Not part of the deploy flow itself — a forgotten running EC2 instance keeps
billing, so this is worth using explicitly when you're done rather than
relying on remembering to do it via the console.

## Not included (yet)

Things worth adding before real production traffic, deliberately left out to
keep this a starting point rather than a guess at requirements you haven't
stated:

- **Rate limiting for `/v1/ask`** — the *metered* endpoints now have per-account
  daily quotas and a sliding-window burst limit (`accounts.py`), but `/v1/ask`
  is still key-only and unmetered, since it has no account to charge. Do not
  expose it to a published client.
- **Streaming responses** — `/v1/ask` waits for the full completion before
  responding. Fine for short answers, awkward for long ones.
- **Structured logging/metrics/tracing** beyond the startup log lines.
- **Spend alerts on the provider dashboards** — quotas cap what one *account*
  can do; they do not cap what a thousand accounts can do. Set a billing alarm
  on the Anthropic and Qwen consoles as well.
- **Multi-instance deployment** — `accounts.db` is SQLite on the container's
  own disk. Two instances behind a load balancer would each meter separately.
  Moving to a shared store is the first thing to do before scaling out.
- **A crawler scheduler** — `crawler.py` refreshes on demand behind its TTL.
  Production wants the once-daily 03:30–05:00 Europe/Paris window
  `specs/legal.md` §3.4 specifies, with a randomised start minute.
