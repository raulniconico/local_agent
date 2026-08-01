# Coffee Can

One repo, three independent projects: a coffee bean/brew tracker, a local AI
agent that can (among other things) fill that tracker in for you, and a
cloud-deployable API gateway for talking to LLM providers. Each one has its
own dependencies, its own setup, and its own README — this page is a map,
not a duplicate of those.

## The three projects

### [`coffee/`](coffee) — coffee-can

The actual product: a CLI + desktop GUI app for logging hand-brew coffee.
Keep a profile per bag of beans (origin, variety, process, roast date, up to
five photos of the bag), then log brewing sessions against it (dripper,
grinder, water, per-stage pours, a 0–5 score and tasting note), and see a
flavor radar chart build up over time. Data lives in a local SQLite database
at `~/.local/share/coffee-can/`; the GUI and CLI read/write the exact same
files, and label photos can be OCR'd (Tesseract locally, or Claude's vision
API for better accuracy) to pre-fill a profile instead of typing it by hand.

Install with `pipx install .` from inside `coffee/`. See
[`coffee/README.md`](coffee/README.md) for the full CLI reference and GUI
walkthrough.

### [`coffee_agent/`](coffee_agent) — the agent

A local, sandboxed LLM agent (LangGraph ReAct loop) for searching, reading,
and drafting documents in a folder on your machine — plus a set of tools
that bridge directly into coffee-can's own database. Point it at a CSV,
spreadsheet, or a photo of a bag label or handwritten brew note, and it
reads/OCRs the content itself, works out the bean or brew-session fields,
and registers them into coffee-can — the same profiles then show up in
coffee-can's own GUI and CLI, since they share one SQLite file.

The model behind it is swappable: a fully local Llama served by vLLM (no
data leaves your machine), the Claude API, or Qwen — chosen via one `.env`
variable, with no other code changes. Fully self-contained: its own
`.venv`, `requirements.txt`, and `setup.sh`.

See [`coffee_agent/README.md`](coffee_agent/README.md) for setup, backend
comparison, the full tool list, and known limitations.

### [`coffee_server/`](coffee_server) — the server

A small stateless FastAPI gateway that proxies chat requests to Anthropic,
Qwen, or DeepSeek — a client picks the provider per request, the server
forwards the call and returns the text. Unrelated to coffee-can's storage;
this is a general-purpose multi-provider LLM proxy, guarded by a shared
`X-API-Key` so it's safe to expose publicly. Ships as a Docker image, with
`deploy/deploy.sh` automating the whole AWS EC2 path: create (or reuse) an
instance, ship the code, build and (re)start the container, health-check it.

See [`coffee_server/README.md`](coffee_server/README.md) for the API shape,
local/Docker instructions, and the AWS deployment walkthrough.

## How they relate

- **`coffee_agent` → `coffee`**: one-directional bridge. `coffee_agent`
  imports `coffee`'s storage layer (`coffee/src/coffee_can/repo.py`/`db.py`)
  directly off `coffee/src` rather than installing it as a package — see
  `coffee_agent/coffee_tools.py`. `coffee` has no dependency on
  `coffee_agent` and doesn't know it exists.
- **`coffee_server`** is fully independent of the other two — it doesn't
  touch coffee-can's database and isn't specific to coffee at all; it just
  happens to live in this repo. Useful on its own as a generic LLM gateway.
- No other code is shared between the three. Each has its own dependency
  set and its own virtual environment / install method.

## Project layout

```
agent/
├── coffee/            # coffee-can: CLI + GUI bean/brew tracker (pipx-installed)
│   └── src/coffee_can/
│       ├── repo.py, db.py, paths.py  # SQLite storage -- imported by coffee_agent
│       ├── ocr.py, claude_ocr.py     # coffee-can's own label OCR
│       └── gui/, cli.py              # PySide6 GUI and click CLI
├── coffee_agent/      # local ReAct agent (own .venv, own setup.sh)
│   ├── setup.sh, serve_vllm.sh, requirements.txt
│   ├── config.py, tools.py, coffee_tools.py, graph.py, main.py
│   ├── documentations/ # AGENT_WORKSPACE sandbox (path is relative to coffee_agent/, per .env)
│   └── README.md
├── coffee_server/     # LLM API gateway (own .venv, own Dockerfile)
│   ├── main.py, providers.py, auth.py, config.py, schemas.py
│   ├── deploy/        # deploy.sh, destroy.sh: AWS EC2 automation
│   └── README.md
└── CLAUDE.md          # guidance for AI coding agents working in this repo
```

## Where to start

- Want to log your own coffee? → [`coffee/README.md`](coffee/README.md)
- Want a local AI assistant (optionally wired into coffee-can)? →
  [`coffee_agent/README.md`](coffee_agent/README.md)
- Want to stand up a hosted LLM API endpoint? →
  [`coffee_server/README.md`](coffee_server/README.md)
