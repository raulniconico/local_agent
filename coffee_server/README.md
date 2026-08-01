# LLM Gateway

A small stateless FastAPI server that proxies chat requests to Anthropic
(Claude), Qwen, or DeepSeek. A client picks the provider per request; the
server just forwards the call and returns the text. No conversation memory,
no tool-calling loop — that's what the sibling `../coffee_agent` local agent is for.
This is meant to run as a Docker container in front of your own client apps.

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

`provider` is required and must be `"anthropic"`, `"qwen"`, or `"deepseek"`.
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

- **Rate limiting / per-client quotas** — right now one shared `SERVER_API_KEY`
  authenticates all clients equally; nothing stops one client from running up
  the bill.
- **Streaming responses** — `/v1/ask` waits for the full completion before
  responding. Fine for short answers, awkward for long ones.
- **Structured logging/metrics/tracing** beyond the one startup log line.
- **Multiple API keys / per-key usage tracking** — currently a single shared
  secret, not per-client credentials.
