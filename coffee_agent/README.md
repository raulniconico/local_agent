# File & Paperwork Agent

An LLM agent that searches your files and helps with paperwork — reading,
summarizing, and drafting documents. [LangGraph](https://github.com/langchain-ai/langgraph)
drives a tool-calling (ReAct) loop on top of a **swappable model backend**,
selected with `LLM_PROVIDER`:

- **`vllm`** (default) — runs entirely on your machine.
  [vLLM](https://github.com/vllm-project/vllm) serves a local Llama model
  behind an OpenAI-compatible API. Needs an NVIDIA GPU.
- **`anthropic`** — calls the Claude API. No GPU, no model download, and a much
  stronger model driving the tool loop; in exchange your file contents leave
  the machine and you pay per token.

The tools, the sandbox, and the CLI are identical either way — only the model
behind them changes.

**Contents:** [Choosing a backend](#choosing-a-backend) ·
[How it works](#how-it-works) · [Requirements](#requirements) ·
[Setup](#setup) · [Running](#running) · [Configuration](#configuration) ·
[Tools](#tools-available-to-the-agent) · [Sandbox](#the-sandbox) ·
[Privacy](#privacy-local-vs-remote) · [Cost](#cost-anthropic-backend) ·
[Limitations](#known-limitations) · [Troubleshooting](#troubleshooting)

---

## Choosing a backend

|                          | `LLM_PROVIDER=vllm`                            | `LLM_PROVIDER=anthropic`                          |
|--------------------------|------------------------------------------------|---------------------------------------------------|
| Hardware                 | NVIDIA GPU (8GB+ VRAM)                         | Anything, including a laptop                      |
| Setup time               | Model download (several GB) + HF login         | Paste an API key                                  |
| Marginal cost            | Free (electricity)                             | Per token — see [Cost](#cost-anthropic-backend)   |
| Data leaves machine      | No                                             | **Yes** — see [Privacy](#privacy-local-vs-remote) |
| Works offline            | Yes                                            | No                                                |
| Tool-calling reliability | Fiddly — depends on the vLLM tool parser       | Native and reliable                               |
| Long documents           | Limited by `--max-model-len` (4096 by default) | 1M-token context on Opus/Sonnet 5                 |

A practical split: use `vllm` for anything sensitive or offline, and
`anthropic` when the task needs real reasoning across several documents. The
3B local model is serviceable for "find and summarize this file" and struggles
with multi-step work like "reconcile these three invoices against the contract."

Switching is a one-line edit in `.env`; nothing else in the project changes.

**Qwen as a Claude alternative.** Under `LLM_PROVIDER=anthropic`, setting both
`QWEN_API_KEY` and `QWEN_MODEL` makes the agent call Qwen (via its
OpenAI-compatible API) instead of Claude for the main chat model — cheaper,
but without Claude's native tool-calling reliability or huge context window.
This isn't a third `LLM_PROVIDER` value; it's a swap-in within the
`anthropic` branch, so everything else in this table (data leaves the
machine, needs network, etc.) still applies. Unset either Qwen variable to
go back to Claude. See [Configuration](#configuration).

## How it works

```
you  <->  coffee_agent/main.py (CLI)  <->  LangGraph ReAct agent  <->  vLLM server  <->  Llama-3.2-3B-Instruct
                                                   |                   ...or the Claude API
                                                   v
                                       coffee_agent/tools.py (search / read / write files,
                                                              sandboxed to AGENT_WORKSPACE)
```

Each time you send a message, the agent runs a **ReAct loop**:

1. The model receives the system prompt, the conversation so far, and the JSON
   schemas of every tool below.
2. It either answers directly, or emits a tool call (say
   `search_files(query="invoice", mode="name")`).
3. LangGraph executes that call locally against your filesystem and feeds the
   result back to the model.
4. Steps 2–3 repeat — reading a file, then another, then drafting — until the
   model produces a final answer with no further tool calls.

Only step 4's text is printed. The intermediate tool calls happen silently, so
a single prompt may involve several model round-trips (relevant to
[cost](#cost-anthropic-backend)).

`graph.py` builds the model in `build_llm()` and hands it to
`create_react_agent`. Because LangGraph accepts any LangChain chat model, the
backend switch touches nothing else — the tools, prompt, and loop are shared.

## Requirements

**For `LLM_PROVIDER=anthropic`:** just `curl` (used by the `uv` installer) and
an Anthropic API key from [console.anthropic.com](https://console.anthropic.com/).
Skip the GPU and Hugging Face requirements entirely.

**For `LLM_PROVIDER=vllm`:**

- NVIDIA GPU with CUDA drivers (tested against an 8GB card; see notes below)
- A Hugging Face account with access to `meta-llama/Llama-3.2-3B-Instruct`
  (a gated repo — you must request access and be approved)
- `curl` (used by the `uv` installer)

vLLM does not yet support very new Python versions, so `setup.sh` provisions
its own isolated Python 3.12 via [`uv`](https://docs.astral.sh/uv/) — it will
not touch your system Python or any other project's environment.

**For the `extract_text_from_image` coffee tool (either backend):** an
`ANTHROPIC_API_KEY`, even under `LLM_PROVIDER=vllm` — it's a direct Claude
vision API call, independent of the chat backend. Everything
else works without it; only image OCR needs it, and it fails with an
actionable message rather than crashing if it's missing.

## Setup

```bash
cd coffee_agent
./setup.sh
```

This will:

1. Install `uv` if missing, then create `.venv` with Python 3.12.
2. Install all dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` (if it doesn't already exist).

Then, **only if `LLM_PROVIDER=vllm`** (the default):

4. Prompt you to run `huggingface-cli login` (or use `HF_TOKEN` if set).
5. Pre-download the model so the first server start doesn't stall.

### Setting up for Claude instead

Create the config file and set the provider *before* running the installer, so
it knows to skip the Hugging Face login and the multi-gigabyte download:

```bash
cd coffee_agent
cp .env.example .env
$EDITOR .env          # set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY=...
./setup.sh
```

`setup.sh` re-reads `.env` on every run, so you can switch
backends later and re-run it to pick up whatever the new provider needs.

## Running

All commands below assume you're in the `coffee_agent/` directory (`cd coffee_agent` from the repo root).

### With Claude (`LLM_PROVIDER=anthropic`)

No model server to start. In `.env`:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

then:

```bash
source .venv/bin/activate
python main.py
```

`ANTHROPIC_API_KEY` can also come from your shell environment instead of
`.env` — the SDK reads it either way, and a real environment
variable takes precedence. Keeping it out of `.env` is the safer habit if the
project directory is ever shared or committed.

### With the local model (`LLM_PROVIDER=vllm`)

Start the model server and leave it running in its own terminal:

```bash
./serve_vllm.sh
```

Wait for it to log that it's listening on port 8000 — startup includes weight
loading and CUDA warmup and can take a minute. In a second terminal:

```bash
source .venv/bin/activate
python main.py
```

### Using it

```
you> find any invoices from last month and summarize what's owed
you> draft a follow-up letter as followup.docx based on invoice_042.pdf
```

Type `exit` or `quit`, or press Ctrl-D/Ctrl-C, to leave.

## Configuration

All settings live in `.env` (copied from
`.env.example`). Variables are grouped by which backend uses
them; the ones for the backend you aren't running are ignored.

**Backend selection**

| Variable       | Default | Purpose                                                                           |
|----------------|---------|-----------------------------------------------------------------------------------|
| `LLM_PROVIDER` | `vllm`  | `vllm` (local GPU) or `anthropic` (Claude API). Anything else is a startup error. |

**`LLM_PROVIDER=anthropic`**

| Variable               | Default         | Purpose                                             |
|------------------------|-----------------|-----------------------------------------------------|
| `ANTHROPIC_API_KEY`    | *(unset)*       | Required unless Qwen is configured (see below). Also readable from the shell environment. |
| `ANTHROPIC_MODEL`      | `claude-opus-5` | Which Claude model to call — see below              |
| `ANTHROPIC_MAX_TOKENS` | `8192`          | Output cap per response                             |

Also under `LLM_PROVIDER=anthropic`: if both `QWEN_API_KEY` and `QWEN_MODEL`
are set, `build_llm()` (`graph.py`) uses Qwen instead of Claude for the
main chat model, and the `ANTHROPIC_*` variables above are ignored for that
purpose (`ANTHROPIC_OCR_MODEL`/`ANTHROPIC_API_KEY` are still used by the
coffee tools' image OCR regardless — see [Coffee-can tools](#coffee-can-tools)).

| Variable          | Default                                                | Purpose                                                    |
|-------------------|---------------------------------------------------------|-------------------------------------------------------------|
| `QWEN_API_KEY`    | *(unset)*                                              | Leave unset to use Claude instead.                          |
| `QWEN_MODEL`      | *(unset)*                                              | e.g. `qwen-max`, `qwen-plus`. Leave unset to use Claude instead. |
| `QWEN_MAX_TOKENS` | `8192`                                                 | Output cap per response                                     |
| `QWEN_BASE_URL`   | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Alibaba DashScope's OpenAI-compatible endpoint. Mainland China accounts use `https://dashscope.aliyuncs.com/compatible-mode/v1` instead; a non-DashScope Qwen provider needs its own URL here. |

**`LLM_PROVIDER=vllm`**

| Variable            | Default                            | Purpose                                            |
|---------------------|------------------------------------|----------------------------------------------------|
| `MODEL_ID`          | `meta-llama/Llama-3.2-3B-Instruct` | HF repo to download and serve                      |
| `SERVED_MODEL_NAME` | `local-llama`                      | Model name the agent requests from vLLM            |
| `VLLM_PORT`         | `8000`                             | Port for the vLLM server                           |
| `VLLM_BASE_URL`     | `http://localhost:8000/v1`         | OpenAI-compatible endpoint the agent calls         |
| `HF_TOKEN`          | *(unset)*                          | Optional, lets `setup.sh` log in non-interactively |

**Both backends**

| Variable          | Default       | Purpose                                                                |
|-------------------|---------------|------------------------------------------------------------------------|
| `AGENT_WORKSPACE` | `~/Documents` | Sandbox root — the agent can only read/write here. Created if missing. |
| `AGENT_DEBUG`     | *(unset)*     | Set to `1` to re-raise errors with the full traceback instead of a one-line message. |

### Choosing a Claude model

Any current Claude model works; the agent sends only `model` and `max_tokens`,
so there are no model-specific parameters to adjust.

| `ANTHROPIC_MODEL`  | Input / output per 1M tokens | Notes                                                                   |
|--------------------|------------------------------|-------------------------------------------------------------------------|
| `claude-opus-5`    | $5 / $25                     | Default. Best at multi-document reasoning.                              |
| `claude-sonnet-5`  | $3 / $15                     | Strong and cheaper; a good default if cost matters.                     |
| `claude-haiku-4-5` | $1 / $5                      | Cheapest and fastest; 200K context. Fine for simple find-and-summarize. |

Opus 5 and Sonnet 5 have a 1M-token context window, so document length is
effectively a non-issue — the `read_document` truncation
([below](#tools-available-to-the-agent)) will bite long before the context does.

> **Note on sampling parameters.** The vLLM path sets `temperature=0.2`; the
> Anthropic path deliberately sets *no* `temperature`, `top_p`, or `top_k`,
> because Claude Opus 5 rejects them with a 400 error. Steer the model's
> behavior by editing `SYSTEM_PROMPT` in `graph.py` instead. If you add
> sampling parameters back for a model that accepts them, keep them out of the
> Opus 5 path.

## Tools available to the agent

- **`search_files(query, mode="name", max_results=30)`** — walks
  `AGENT_WORKSPACE` recursively. `mode="name"` matches `query` as a
  case-insensitive substring of the filename; `mode="content"` greps inside
  text-like files (`.txt`, `.md`, `.py`, `.csv`, `.json`, `.rst`) — it does
  **not** search inside PDFs or Word documents. Returns workspace-relative
  paths, capped at `max_results`.
- **`read_document(path)`** — extracts plain text from `.txt`, `.md`, `.pdf`,
  or `.docx` (plus the other text extensions above). **Output is truncated at
  ~12,000 characters**, with a notice appended; for a long PDF the agent sees
  only the beginning. Raise `MAX_CHARS` in `tools.py` if that's too tight
  — the Claude backend has ample context for much more.
- **`write_document(path, content)`** — writes a `.txt`, `.md`, or `.docx`
  file, choosing the format from the extension. For `.docx`, blank lines in
  `content` become paragraph breaks. Missing parent directories are created.

Paths may be relative (resolved against `AGENT_WORKSPACE`) or absolute (which
must still land inside it).

### Coffee-can tools

`coffee_tools.py` bridges into the sibling [`../coffee`](../coffee) project (a
bean-profile and hand-brew tracker) by importing its `repo`/`db` modules
straight off `../coffee/src` — not by installing `coffee-can` as a package, since
that would pull in its GUI dependency (PySide6) for no benefit here. Both
projects share the same SQLite database coffee-can's own CLI/GUI use
(`~/.local/share/coffee-can/coffee.db` by default), so records created here
show up there too.

- **`list_coffee_beans()`** / **`list_coffee_brew_sessions(bean="")`** — list
  existing profiles/sessions, optionally filtered by bean (id or exact name).
- **`create_coffee_bean(name, origin="", variety="", altitude="", roaster="", producer="", process="", roast_date="")`**
  — registers a new bean profile and marks it complete. Always creates a new
  row; check `list_coffee_beans` first to avoid duplicates.
- **`add_coffee_bean_image(bean, path)`** — copies a photo already in the
  workspace (`.jpg`/`.jpeg`/`.png`/`.webp`/`.pdf`) into coffee-can's own
  storage as a page image on that bean, so it shows up in coffee-can's own
  GUI/CLI too. The agent calls this with the same photo it just OCR'd so a
  bean filled in from a bag-label photo keeps that photo attached — up to a
  few pages per bean (`coffee_can.paths.MAX_IMAGES_PER_BEAN`).
- **`create_coffee_brew_session(bean, brew_date="", dripper="", filter_paper="", grinder="", grind_size="", water_ppm="", humidity="", dose_g=None, score=None, note="")`**
  — registers a brewing session against an existing bean (by id or name).
- **`add_coffee_brew_stage(session_id, temperature_c=None, water_g=None, time_seconds=None, circling="")`**
  — appends one pour/stage to an existing session.
- **`extract_text_from_image(path)`** — OCRs a photo in the workspace (bag
  label, handwritten brew note) via a direct Claude API vision call and
  returns the transcribed text for the model to parse itself. **Requires
  `ANTHROPIC_API_KEY` regardless of `LLM_PROVIDER`** — set it in `.env` even if
  you're on the `vllm` backend, since this is an independent API call, not a
  turn of the main chat model. Uses `ANTHROPIC_OCR_MODEL` (defaults to
  `claude-opus-5`, same as the chat model default but configurable
  separately). The model is expected to review/confirm extracted fields with
  you before registering anything, since OCR is best-effort, and each call
  sends the photo to the Claude API.

There's no dedicated file-import tool: for CSV/spreadsheet/text sources, the
agent reads the file with `read_document` and works out bean/session fields
itself before calling the `create_coffee_*` tools.

### Desktop ↔ phone sync tools

`sync_tools.py` moves beans, sessions, stages and page images between this
machine's coffee-can database and the Android app
([`../coffee_android`](../coffee_android)), through a **bundle** — a `.zip`
you carry between the two devices yourself.

**Nothing goes through a server, and that is deliberate.** The Android app
tells the user their data stays on the phone and that there is no copy of it
anywhere else (`specs/legal-accounts.md` §3.8). A bundle keeps that true: it
travels between two devices the same person owns, by whatever means they
choose (USB, a share sheet, a USB stick), and the developer never holds it.

**Over USB, the agent does the whole thing itself** — no file to carry:

- **`send_coffee_data_to_phone()`** — packages this machine's data, copies it
  across the cable and tells the app to import it.
- **`fetch_coffee_data_from_phone(destination="from-phone.zip")`** — asks the
  app to package its log, pulls it back, and stops there. It deliberately does
  *not* import: run `inspect_coffee_bundle` and resolve conflicts first.

Both need the phone plugged in with USB debugging on (Settings → Developer
options), and `adb` on `PATH` or `ADB_PATH` set. If no phone is connected they
say so, and the manual file-carrying tools below still work.

- **`export_coffee_bundle(destination)`** — writes every bean, its sessions,
  stages and images to a zip inside the workspace (`.zip` appended if you
  omit it), in the same format the phone reads.
- **`inspect_coffee_bundle(bundle)`** — a dry run over a bundle the phone
  produced: how many beans are new, how many already match, and which are in
  **conflict**. Changes nothing.
- **`apply_coffee_bundle(bundle, resolutions="{}")`** — imports it.
  `resolutions` is a JSON object mapping each conflicted bean name to
  `"phone"` (take the bundle's version), `"desktop"` (keep what's here) or
  `"skip"`. New beans need no entry.

**Conflicts are never resolved silently.** A bean present on both sides with
any differing field is reported, and `apply_coffee_bundle` leaves it untouched
until it's given an explicit choice for it — so a half-answered run cannot
overwrite anything. `"phone"` **deletes the local bean** and everything
hanging off it (its sessions, stages and image files) before writing the
bundle's version; a half-replaced bean carrying the other side's sessions is
the one outcome nobody wants. The system prompt tells the agent to inspect
first and ask you per conflict.

Two limits worth knowing before you rely on it:

- **Beans are matched by name**, because that is the only identifier the two
  databases share — coffee-can's `beans.id` and Room's are independent
  sequences. Rename a bean on one device and it imports as a second bean.
- **Not every field crosses.** The schemas diverged: the Android session has
  `waterG`/`waterTempC`, which coffee-can's `brew_sessions` has no column
  for, and coffee-can has `humidity`, which Room has no field for. Room's
  stage `label` stays behind too (its free `note` maps to coffee-can's
  `circling`). Those are left out rather than crammed into
  approximately-right columns.

Bundles carry a version number (`BUNDLE_VERSION`, matching Android's
`SyncBundle.VERSION`); a bundle from a newer app than this agent understands
is refused rather than imported partially.

> **Both directions work, but they resolve conflicts differently.** The phone
> exports and imports from Profile → "Sync with desktop". Coming *this* way,
> you get the full per-bean adjudication above. Going the other way, the app
> **never overwrites**: it adds beans whose names are new, leaves the rest
> untouched, and reports how many it skipped. The asymmetry is about who can
> be asked — this side has an agent that can put the question to you per bean,
> and the phone has no such conversation available, so it declines rather than
> guesses. So an edit you make here will not reach a bean the phone already
> holds — only genuinely new beans cross in that direction.

## The sandbox

Every tool call resolves its path through `_resolve()` in `tools.py`, which
canonicalizes the path — following any symlinks — and rejects it unless the
result is inside `AGENT_WORKSPACE`. So `../../.ssh/id_rsa`, an absolute
`/etc/passwd`, and a symlink pointing out of the workspace are all refused, and
the model is told why rather than silently failing.

Two things the sandbox does **not** do:

- **`write_document` overwrites without asking.** If the model picks the name
  of an existing file, that file's previous contents are gone. Point
  `AGENT_WORKSPACE` at a directory you keep backed up (or under version
  control) rather than at irreplaceable originals.
- **It does not constrain where file *contents* go.** See below.

## Privacy: local vs remote

The sandbox limits which files the agent can *touch*; it does not limit where
their contents *go*. Under `LLM_PROVIDER=anthropic`, every document the agent
reads is sent to the Claude API as a tool result, and filenames surface there
too via `search_files` — including files it opened while exploring and decided
weren't relevant.

If `AGENT_WORKSPACE` holds material that must not leave the machine, keep
`LLM_PROVIDER=vllm`, or point `AGENT_WORKSPACE` at a directory you're
comfortable sending off-box. The default of `~/Documents` is broad; narrowing
it to something like `~/Documents/paperwork` is worth doing for the remote
backend regardless.

## Cost (anthropic backend)

Rough, order-of-magnitude only — measure your own usage before relying on it.

A single prompt costs more than one API call, because the ReAct loop re-sends
the whole conversation on every step. A turn that searches, reads one document,
and answers is three calls; input tokens are paid again each time, and a
12,000-character document is roughly 3,000 tokens.

That puts a typical document-reading turn on Opus 5 in the **low single-digit
cents**, and a long session that reads several files at a few tens of cents.
Sonnet 5 is meaningfully cheaper, Haiku 4.5 more so. Costs scale with document
size and the number of tool-calling steps, so the expensive prompts are the
open-ended ones that make the agent open many files.

To keep a lid on it: narrow `AGENT_WORKSPACE`, lower `MAX_CHARS` in
`tools.py`, and be specific in prompts ("read `invoice_042.pdf`" rather
than "look through my invoices").

## Known limitations

- **Conversation memory is text-only.** `main.py` stores each turn as a
  `(role, text)` pair, so tool calls, their results, and (on Claude) reasoning
  blocks are dropped once a turn ends. The agent remembers what it *said* about
  a file, not that it read it — ask a follow-up question about a document and it
  will typically re-read it. Fixing this means keeping the full message list
  returned by `agent.invoke()` instead of just the final text.
- **No directory listing.** There is no `list_files` tool. Asking for a folder
  structure makes the agent fall back on `search_files` with a broad query,
  which returns a flat list capped at `max_results` (30 by default) — not a
  tree, and not necessarily complete.
- **No conversation persistence.** History lives in memory; quitting loses it.
- **No streaming.** Output appears only when the turn is complete, which on a
  multi-step turn can be a noticeable wait with no feedback.
- **`search_files` content mode is a linear scan**, reading each candidate file
  into memory. It's fine for a document folder and slow over very large trees.
- **Local-model tool calling is fragile.** A 3B model will sometimes ignore the
  tools or malform a call; the Claude backend is far more reliable here.
- **Phone sync matches beans by name, and it is one bundle at a time.** A bean
  renamed on either device imports as a second bean, and a few fields have no
  column on the far side (see [the sync tools](#desktop--phone-sync-tools)).
  There is no incremental or automatic sync — you export, carry the file, and
  import, each time.

## Tuning for your GPU

Applies to `LLM_PROVIDER=vllm` only.

`serve_vllm.sh` defaults to `--gpu-memory-utilization 0.90 --max-model-len 4096`,
sized for an 8GB card running the 3B model. If you have more VRAM to spare,
raise `--max-model-len` for longer documents. If you hit a CUDA out-of-memory
error, lower it further (e.g. `2048`) or reduce `--gpu-memory-utilization`.

The script also sets `VLLM_USE_FLASHINFER_SAMPLER=0`, because FlashInfer
JIT-compiles its sampling kernels with the system `nvcc` — 12.4 here, which
can't target this GPU's `sm120` (that needs CUDA ≥ 12.9). Drop that line once
the CUDA toolkit is upgraded.

## Troubleshooting

Errors during a turn are reported as a single line and the session continues —
the failed turn is dropped from history so the next request stays well-formed.
Set `AGENT_DEBUG=1` to get the underlying traceback instead:

```bash
AGENT_DEBUG=1 python main.py
```

Misconfiguration (an unknown `LLM_PROVIDER`, or `anthropic` with no API key) is
caught at startup, before the prompt appears.

### Claude backend

- **`401 authentication_error`**: `ANTHROPIC_API_KEY` is missing, malformed, or
  revoked. Confirm it's actually reaching the process — a stale exported shell
  variable overrides the value in `.env`.
- **`400 invalid_request_error` mentioning `temperature`, `top_p`, or `top_k`**:
  something is passing sampling parameters to a model that rejects them. Remove
  them from the `ChatAnthropic(...)` call in `graph.py`.
- **`404 not_found_error`**: bad `ANTHROPIC_MODEL`. Use an exact ID such as
  `claude-opus-5` — no date suffix.
- **Responses cut off mid-sentence**: the reply hit `ANTHROPIC_MAX_TOKENS`.
  Raise it. Note the cap covers the model's internal reasoning as well as the
  visible answer, so leave headroom.
- **`429 rate_limit_error`**: you're above your account's rate limit; wait and
  retry, or move to a cheaper/faster model.

### Qwen (active whenever `QWEN_API_KEY`/`QWEN_MODEL` are both set)

- **`401 Incorrect API key provided`**: the key is wrong for the endpoint in
  `QWEN_BASE_URL`. DashScope keys are region-locked — a mainland-China key
  gets this error against the `-intl` endpoint and vice versa; swap
  `QWEN_BASE_URL` between `https://dashscope.aliyuncs.com/compatible-mode/v1`
  and `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` and retry. If
  neither works, the key may be for a different Qwen-hosting provider
  entirely, which needs its own `QWEN_BASE_URL`.
- **Agent unexpectedly uses Claude**: either `QWEN_API_KEY` or `QWEN_MODEL` is
  empty — both must be set. Check for a stale exported shell variable
  overriding `.env`, same as the Claude key issue above.

### Local vLLM backend

- **`RuntimeError: Failed to find C compiler`**: vLLM uses Triton kernels
  (e.g. for sampling) that need a C compiler unconditionally — `--enforce-eager`
  does not avoid this, it only skips `torch.compile`/CUDA-graph capture (which
  is still worth keeping on an 8GB card to save VRAM). Install a compiler:
  `sudo apt install -y build-essential`.
- **Tool calls aren't triggering / agent ignores tools**: vLLM's tool-calling
  support (`--enable-auto-tool-choice --tool-call-parser llama3_json`) is
  version-sensitive. Check `vllm --version`; if calls still don't fire, you
  may need to pass an explicit `--chat-template` pointing at vLLM's
  `tool_chat_template_llama3.*_json.jinja` example file.
- **CUDA out of memory on startup**: lower `--max-model-len` and/or
  `--gpu-memory-utilization` in `serve_vllm.sh`.
- **403 / gated repo error downloading the model**: make sure your Hugging
  Face account has requested and been granted access to
  `meta-llama/Llama-3.2-3B-Instruct` on huggingface.co, and that
  `huggingface-cli login` succeeded.
- **`Can't reach the vLLM server at ...`**: the server isn't running, is still
  loading weights, or is on another port. Start it with `serve_vllm.sh` and
  wait for it to report that it's listening; check that `VLLM_BASE_URL` matches
  `VLLM_PORT`. If you meant to use Claude, set `LLM_PROVIDER=anthropic` in
  `.env` — this error means the agent is on the local backend.

### Either backend

- **`'<path>' is outside the allowed workspace`**: the model tried to reach
  outside `AGENT_WORKSPACE`. This is the sandbox working as intended — widen
  `AGENT_WORKSPACE` if the file genuinely should be in scope.
- **`Unknown LLM_PROVIDER '<x>'`**: `LLM_PROVIDER` must be exactly `vllm` or
  `anthropic`.

## Project layout

```
agent/
├── coffee_agent/       # this project -- fully self-contained (own .venv/deps/setup)
│   ├── setup.sh        # one-time installer (uv venv, deps; HF login + model download only for vllm)
│   ├── serve_vllm.sh   # starts the vLLM OpenAI-compatible server
│   ├── requirements.txt
│   ├── .env.example
│   ├── config.py       # reads .env, resolves the workspace root
│   ├── tools.py        # search_files / read_document / write_document + sandbox
│   ├── coffee_tools.py # bean/brew-session registration + image OCR, via ../coffee
│   ├── sync_tools.py   # desktop <-> phone bundle export/inspect/import, via ../coffee
│   ├── graph.py        # system prompt, build_llm() backend switch, ReAct agent
│   └── main.py         # CLI chat loop -- run as `python main.py`, not `-m`
├── coffee_android/    # sibling project: the phone half of bundle sync (data/SyncBundle.kt)
├── coffee/            # sibling project: coffee-can bean/brew tracker (CLI + GUI)
│   └── src/coffee_can/
│       ├── repo.py, db.py, paths.py  # SQLite storage, imported by coffee_agent/coffee_tools.py
│       ├── ocr.py, claude_ocr.py     # coffee-can's own OCR (not used by coffee_agent/ -- it OCRs directly via Claude)
│       └── gui/, cli.py              # PySide6 GUI and click CLI (not used by coffee_agent/)
└── coffee_server/     # separate deployable unit: AWS-hosted LLM API gateway (its own .env, see coffee_server/README.md)
```