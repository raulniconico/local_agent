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
| `GET /v1/news` | read key | no | cached headlines from eight trade-press RSS feeds. **Working** |
| `GET /v1/catalogue` | read key | no | cached roaster catalogue. **503 today** — `allowlist.json` is empty, see `crawler.py` |
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

### `GET /v1/news`

`X-API-Key: <READ_API_KEY>`. Serves cached headlines from the trade-press RSS
feeds in `news_sources.json` — seven enabled publications, refreshed hourly by
`scheduler.py`. Each item is headline, source, date and canonical link, and
**only** those four: `specs/legal-accounts.md` rule 74 forbids any snippet
beyond the headline and specifically forbids an AI-written summary, because the
*droit voisin* exclusion covers hyperlinks and very short extracts but not
summaries.

```json
{"items": [{"title": "…", "source": "Sprudge",
            "url": "https://…", "published_at": 1787486440}],
 "fetched_at": 1787490000}
```

**Why press feeds are not gated like roasters.** `specs/legal.md` is scoped to
crawling *French roasters' e-commerce catalogues*; its rules 2–3 (outreach
email, 14-day wait, verbatim CGU quotation) buy permission for an act whose
permission is genuinely in doubt. An RSS feed is the inverse — the publisher
emits it *in order to be read by machines*, which is the tier-2 first-party
structured endpoint §3.2 rule 7 tells you to prefer. So `news_sources.json` is
a **separate file** from `allowlist.json` with its own justification, rather
than a flag on the same list. What still applies, and is enforced by routing
every fetch through `Fetcher`: robots.txt, the per-host delay, conditional
GETs, and a truthful User-Agent with a working contact address.

A feed that refuses this crawler is disabled rather than worked around —
`comunicaffe.com` returns `403` and carries its reason in the file. Do not
change the User-Agent to get past a refusal; `specs/legal.md` rule 18 forbids
it.

### `GET /v1/catalogue`

`X-API-Key: <READ_API_KEY>`. Serves the roaster-catalogue cache. **Returns 503
today**, deliberately: `allowlist.json` has `"sources": []`, because
`specs/legal.md` rules 2–3 and `specs/legal-accounts.md` rule 72 are unmet.
Setting `CRAWLER_ENABLED=1` with an empty allowlist still crawls nothing — the
switch is not the permission. Adding a domain there is a legal decision someone
records, not a configuration change.

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

## Configuration

Three files, none of which are interchangeable:

| File | Holds | Copied to the server? |
| --- | --- | --- |
| `.env` | the app's own secrets and behaviour flags | **yes**, by `deploy.sh` |
| `deploy/.env` | which instance, which key, which hostname | **no** — local only |
| `news_sources.json`, `allowlist.json` | what may be fetched | yes, as part of the code |

`.env.example` is the canonical annotated list; `specs/coffee-server.md` §3.5
has the full table with defaults. The four settings that change whether a
feature works at all:

| Variable | Effect when unset |
| --- | --- |
| `SERVER_API_KEY` | **server refuses to start.** No "run without auth" mode |
| `GOOGLE_CLIENT_IDS` | every metered endpoint returns `503`, fail-closed |
| `CRAWLER_ENABLED` | `/v1/news` and `/v1/catalogue` return `503` |
| `ACCOUNT_DB_PATH` | `accounts.db` lands inside the container and is destroyed on each redeploy |

`READ_API_KEY` falls back to `SERVER_API_KEY` when unset, so one value can
serve both until you want to rotate them independently.

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
- **EC2** — `docker run` directly, with **Caddy** terminating TLS in front of
  it. See [Deploying with deploy.sh](#deploying-with-deploysh) and the
  [step-by-step guide](#step-by-step-from-nothing-to-a-working-https-gateway)
  below, which automate exactly this. This is the deployed path today.

In all cases: **never bake `.env` into the image** (`.dockerignore` already
excludes it) — inject `SERVER_API_KEY` and the provider keys as environment
variables from the platform's secret store at deploy time.

## Deploying with deploy.sh

`deploy/deploy.sh` automates the whole EC2 path end to end and is **idempotent**
— re-running it after a code change is the redeploy command, not a way to
accumulate instances. It creates or reuses the instance, ships this directory
and your `.env` over SSH, rebuilds and restarts the container, installs and
configures **Caddy** for HTTPS, and health-checks the result.

It checks its own local prerequisites (`aws`, `ssh`, `scp`, `rsync`, `curl`)
and runs `deploy/install-deps.sh` if any are missing (needs `sudo`).

### Two modes

| `API_HOST` in `deploy/.env` | What you get |
| --- | --- |
| set (e.g. `api.coffee-can.org`) | Caddy on 80/443 with automatic Let's Encrypt certs, HTTP→HTTPS redirect, container bound to `127.0.0.1` only, `APP_PORT` **revoked** from the security group |
| empty | the older behaviour: plain HTTP on `APP_PORT`, open to the world, no Caddy |

TLS mode is strongly preferred and is what the Android app requires — the app
sets `usesCleartextTraffic="false"` with no domain exceptions, so it cannot
talk to a plain-HTTP gateway at all.

---

## Step-by-step: from nothing to a working HTTPS gateway

Everything below is done once. Afterwards, deploying is a single command.

### 1. AWS credentials

```bash
aws configure
```

Needs EC2 full access plus `ssm:GetParameters` (for the AMI lookup). If you
will also let the script-adjacent DNS steps run from this account, add
`route53:{ListHostedZones,ChangeResourceRecordSets,GetChange}`.

### 2. An EC2 key pair, in `pem` format

EC2 console → Key Pairs → Create key pair → **File format: `pem`** (not `ppk`
— a `.ppk` pair's private key cannot be re-downloaded in `pem` form later, as
AWS only offers the download once, at creation).

```bash
chmod 600 /path/to/your-key.pem     # ssh refuses group/world-readable keys
```

Verify the file matches the pair AWS holds before you rely on it — a mismatch
produces `Permission denied (publickey)` several minutes into a deploy:

```bash
ssh-keygen -lf /path/to/your-key.pem
aws ec2 describe-key-pairs --key-names <pair-name> \
  --query 'KeyPairs[0].KeyFingerprint' --output text
```

For an ed25519 pair those two must match (AWS prints the same base64 SHA-256,
without the `SHA256:` prefix).

### 3. Server secrets

```bash
cd coffee_server
cp .env.example .env
$EDITOR .env
```

At minimum set `SERVER_API_KEY` and one provider key. For the Android app also
set `GOOGLE_CLIENT_IDS` (see step 7). This file is copied to the instance and
is **never** baked into the image (`.dockerignore` excludes it).

### 4. Deploy config

```bash
cd coffee_server/deploy
cp .env.example .env
$EDITOR .env
```

Set `KEY_NAME` (the pair's name **in AWS**, not a path), `KEY_FILE` (its local
path — relative paths resolve against `deploy/`), and `AWS_REGION`. Leave
`API_HOST`/`SITE_HOST` empty for now; you will fill them in at step 6.

### 5. First deploy, without TLS

```bash
./deploy.sh
```

This prints the instance's public IP. Confirm it works:

```bash
curl http://<ip>:8000/healthz          # {"status": "ok"}
```

### 6. A domain, an Elastic IP, and DNS

**Attach an Elastic IP first.** A certificate is bound to a name, the name is
bound to an A record, and letting the address change out from under it breaks
both the app and renewal. `deploy.sh` does *not* do this for you:

```bash
ALLOC=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
aws ec2 associate-address --instance-id <instance-id> --allocation-id "$ALLOC"
aws ec2 describe-addresses --allocation-ids "$ALLOC" \
  --query 'Addresses[0].PublicIp' --output text
```

**Point DNS at it.** With the zone in Route 53:

```bash
aws route53 change-resource-record-sets --hosted-zone-id <ZONE> --change-batch '{
  "Changes": [{"Action": "UPSERT", "ResourceRecordSet": {
    "Name": "api.example.org", "Type": "A", "TTL": 300,
    "ResourceRecords": [{"Value": "<elastic-ip>"}]}}]}'
```

Wait until it resolves publicly before continuing — Caddy's certificate request
fails if the name does not yet resolve:

```bash
dig +short api.example.org
```

A newly registered domain can take an hour or more: the registry may show the
nameservers while the TLD zone has not published the delegation yet. Ask the
authoritative server directly to tell the two apart:

```bash
dig @<one-of-your-ns> api.example.org A     # your zone's answer
dig @a0.org.afilias-nst.info example.org NS # has the TLD published it?
```

Public resolvers can also keep serving `NXDOMAIN` for up to the negative-cache
TTL (often an hour) after the delegation lands. That is normal and not a fault
to chase.

### 7. Google sign-in (needed for the metered endpoints)

You need **two** OAuth clients in the same Google Cloud project, and only one
of them goes in config:

| Client type | Where it goes | Why |
| --- | --- | --- |
| **Web application** | `GOOGLE_CLIENT_IDS` here, and `GOOGLE_SERVER_CLIENT_ID` in the app | becomes the ID token's `aud`; this server allowlists it |
| **Android** | nowhere in config | Google matches it implicitly by package name + signing SHA-1 to decide whether to mint a token at all |

Getting these the wrong way round produces Credential Manager error **28444**
(`DEVELOPER_CONSOLE_IS_NOT_SET_UP_CORRECTLY`) on the phone, with nothing
reaching this server. `GOOGLE_CLIENT_IDS` is comma-separated so a rotation can
list both during a changeover; the Google `sub` is stable across client IDs, so
no account is orphaned by one.

### 8. Redeploy with TLS

```bash
cd coffee_server/deploy
$EDITOR .env       # API_HOST=api.example.org   SITE_HOST=example.org
./deploy.sh
```

The script now installs Caddy, writes `/etc/caddy/Caddyfile`, opens 80 and 443,
revokes the world-facing `APP_PORT` rule, rebinds the container to
`127.0.0.1`, and health-checks `https://$API_HOST/healthz`.

Port **80 must stay open**: it carries the ACME HTTP-01 challenge, not just the
redirect, so certificate issuance fails without it.

### 9. Verify

```bash
curl https://api.example.org/healthz                       # {"status": "ok"}
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST https://api.example.org/v1/ask                   # 401 — auth enforced
curl -s -o /dev/null -w '%{http_code}\n' \
  http://<elastic-ip>:8000/healthz                         # 000 — plaintext closed
```

And end to end through the gateway:

```bash
curl -H "X-API-Key: $SERVER_API_KEY" -H "Content-Type: application/json" \
  -d '{"provider": "qwen", "prompt": "Say OK"}' \
  https://api.example.org/v1/ask
```

---

### Redeploy

```bash
./deploy/deploy.sh
```

Reuses the instance and security group matched by the `INSTANCE_NAME` tag, and
rebuilds/restarts the container. Safe to run after any code or `.env` change.

### Operating

```bash
ssh -i $KEY_FILE ec2-user@<ip> docker logs coffee-server-app   # app logs
ssh -i $KEY_FILE ec2-user@<ip> sudo journalctl -u caddy -n 50  # TLS / cert logs
ssh -i $KEY_FILE ec2-user@<ip> sudo tail /var/log/caddy/api.log # access log
```

`accounts.db` lives on a bind mount at `~/coffee_server/data` on the instance,
**not** inside the container — every deploy does `docker rm -f`, so an in-image
database would lose the per-user metering records each time.

### Known gaps in the deploy path

- Old `/32` SSH rules from previous runs are not removed when your public IP
  changes. An accumulating allowlist of your own past IPs, not an open one.
- The Elastic IP and the DNS records are **not** created by the script (step 6
  is manual, once). A first run against a name that does not yet resolve brings
  the app up but leaves Caddy retrying ACME until DNS lands.
- Certificates renew automatically, but no ACME account email is configured, so
  no expiry-warning mail is sent. Add one in the `Caddyfile` if you want it.

### Tear down

```bash
./deploy/destroy.sh
```

Terminates the instance and deletes the security group. Deliberately not part
of the deploy flow — a forgotten EC2 instance keeps billing. **Release the
Elastic IP separately**, or it keeps billing on its own once detached:

```bash
aws ec2 release-address --allocation-id <alloc-id>
```

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
- **Multi-instance deployment** — `accounts.db` is SQLite on a bind mount on
  the instance (`ACCOUNT_DB_PATH=/data/accounts.db`), so it survives redeploys,
  but it is still one file on one host. Two instances behind a load balancer
  would each meter separately. Moving to a shared store is the first thing to
  do before scaling out.
- **Catalogue crawling itself.** `scheduler.py` now exists and runs (catalogue
  daily in the 03:30–05:00 Europe/Paris window with a randomised start minute,
  news hourly), and the news half is live. The catalogue half has nothing to
  crawl until `allowlist.json` gains an entry, which is a legal decision
  (`specs/legal.md` rules 2–3, `legal-accounts.md` rule 72), not a code change.
