# `coffee_agent/` — the local file & paperwork agent

A sandboxed CLI agent that searches, reads and drafts documents on your machine, driven by a LangGraph ReAct loop over a swappable model backend — and able to fill in coffee-can's database for you.

- [1. Project background](#1-project-background)
- [2. Development details](#2-development-details)
- [3. API](#3-api)

---

## 1. Project background

### What it is designed for

A local assistant for paperwork. You point it at a folder, and it can search that folder, read what it finds (`.txt`, `.md`, `.pdf`, `.docx`, `.csv`, spreadsheets), and draft new documents back into it. The interface is a plain terminal REPL.

Two things make it more than a wrapper around a chat API:

**The model behind it is swappable, and that swap is the load-bearing design decision.** `LLM_PROVIDER` selects between a fully local Llama served by vLLM (nothing leaves the machine, works offline, needs an NVIDIA GPU) and the Claude API (no GPU, much stronger reasoning, per-token cost, data leaves the machine). Because `create_react_agent` accepts any LangChain `BaseChatModel`, the prompt, tools, sandbox and CLI are shared verbatim — a backend change stays confined to `build_llm()`.

**Every filesystem path funnels through one chokepoint.** `_resolve()` in `tools.py` canonicalises a model-supplied path, following symlinks, and rejects anything landing outside `AGENT_WORKSPACE`. So `../../.ssh/id_rsa`, an absolute `/etc/passwd`, and a symlink pointing out of the workspace are all refused, with the model told why.

The second half of the project is a bridge into coffee-can: point the agent at a CSV of brew notes, or a photo of a bag label, and it reads or OCRs the content, works out the fields itself, and registers a bean profile or brewing session. Field extraction is deliberately *not* reimplemented here — the tools hand the model raw text and it does the parsing, the same division of labour as the rest of the project.

### Relations with the other two sub-projects

| Relation | Direction | Nature |
| --- | --- | --- |
| `coffee_agent/` → `coffee/` | one-directional, outbound | imports coffee-can's storage layer; shares its SQLite file |
| `coffee/` → `coffee_agent/` | none | coffee-can does not know this project exists |
| `coffee_agent/` ↔ `coffee_server/` | none | no shared code; different purpose entirely |

**The coffee-can bridge.** `coffee_tools.py` inserts `../coffee/src` onto `sys.path` at import time and imports `coffee_can.repo` / `db` / `paths` directly, rather than installing the `coffee-can` package. That package's `pyproject.toml` pulls in PySide6 for its GUI, which this project has no reason to depend on; the three modules it needs are standard-library only. **Do not `uv pip install -e ./coffee`** — it would drag the GUI stack into this venv for nothing used here. If `coffee/` restructures its package layout, this bridge needs updating in lockstep.

Both projects read and write the same `~/.local/share/coffee-can/coffee.db` via `coffee_can.paths.db_path()`. There is no separate agent-side data store, and no synchronisation problem to solve — records created here appear in coffee-can's GUI and CLI immediately. `add_coffee_bean_image` copies files into `coffee_can.paths.images_dir(bean_id)` exactly as `repo.add_bean_image()` always has, so pages attached here are indistinguishable from ones added through the GUI.

Note the asymmetry with `coffee/`'s own OCR: this project does **not** use `coffee_can.ocr` (local Tesseract) or `coffee_can.claude_ocr` (structured field extraction). It makes its own direct Claude vision call returning plain transcribed text, keeping the model-does-the-parsing division of labour.

`coffee_server` is unrelated — a stateless multi-provider proxy with no tool loop and no memory. This project talks to provider SDKs directly and does not route through it.

---

## 2. Development details

### Layout

```
coffee_agent/
├── setup.sh          # one-time installer: uv venv (3.12) + deps; HF login + model download only for vllm
├── serve_vllm.sh     # starts the vLLM OpenAI-compatible server
├── requirements.txt
├── .env / .env.example
├── config.py         # reads .env once; exposes settings as module constants
├── tools.py          # search/read/write file tools + the sandbox chokepoint
├── coffee_tools.py   # coffee-can bridge: bean/session registration + image OCR
├── graph.py          # SYSTEM_PROMPT, build_llm() backend switch, build_agent()
├── main.py           # the REPL, plus explain() for one-line error messages
└── documentations/   # default AGENT_WORKSPACE sandbox
```

Five modules, wired in one direction:

```
                    tools.py ─┐
config.py  ->                 +->  graph.py  ->  main.py
(.env)         coffee_tools.py ┘   (backend)     (CLI loop)
```

`tools.py` and `coffee_tools.py` are independent peers — both read `config.py`, both feed `graph.py`'s tool list, neither depends on the other.

### Module responsibilities

| Module | Responsibility |
| --- | --- |
| `config.py` | Calls `load_dotenv()` at import with an **explicit path** (`Path(__file__).parent/".env"`), not a bare call — a bare call walks up parent directories and would risk picking up the sibling `coffee_server/`'s `.env`. Exposes every setting as a module constant so config is resolved exactly once. Creates `WORKSPACE_ROOT` as an import side effect. |
| `tools.py` | The three file `@tool` functions and the `TOOLS` list. `_resolve()` is the single sandbox chokepoint. `MAX_CHARS = 12000` caps `read_document` output. |
| `coffee_tools.py` | `COFFEE_TOOLS`: six coffee-can registration/listing tools plus `extract_text_from_image`. Owns the `sys.path` bridge and the direct Anthropic vision call. |
| `graph.py` | `SYSTEM_PROMPT`, `build_llm()` (the backend switch), and `build_agent()` — a thin wrapper over `create_react_agent` wired with `TOOLS + COFFEE_TOOLS`. |
| `main.py` | The REPL. `explain()` maps SDK exceptions to one-line messages; `_using_qwen()` mirrors `build_llm()`'s selection logic to label errors with the right provider. |

### The backend switch

`build_llm()` resolves in this order:

1. **`LLM_PROVIDER=anthropic`**
   - If **both** `QWEN_API_KEY` and `QWEN_MODEL` are set → `ChatOpenAI` pointed at `QWEN_BASE_URL`. This is **not** a third `LLM_PROVIDER` value; it is an in-branch substitution, and it is checked *before* the `ANTHROPIC_API_KEY` requirement.
   - Otherwise → `ChatAnthropic`, raising if `ANTHROPIC_API_KEY` is unset.
2. **`LLM_PROVIDER=vllm`** → `ChatOpenAI` against `VLLM_BASE_URL` with `api_key="EMPTY"` and `temperature=0.2`.
3. Anything else → `ValueError` at startup.

Provider SDKs are imported lazily inside each branch, so neither backend requires the other's dependency.

`main.py`'s `_using_qwen()` duplicates the `QWEN_API_KEY and QWEN_MODEL` condition. **If the selection logic in `build_llm()` changes, update `_using_qwen()` in lockstep** or `explain()` will attribute errors to the wrong provider.

### Constraints that are easy to break

- **Never pass `temperature`, `top_p`, or `top_k` to `ChatAnthropic`.** Claude Opus 5 rejects sampling parameters with a 400. The vLLM branch setting `temperature=0.2` while the Anthropic branch sets nothing is deliberate asymmetry, not an oversight. Steer Claude via `SYSTEM_PROMPT` instead. Qwen's `ChatOpenAI` call sets none either, though unlike Claude it would accept them.
- **Message content shape differs by backend.** `ChatOpenAI` returns `content` as a string; Claude returns a list of content blocks (thinking + text), because Opus 5 has thinking on by default. Always read assistant text via `message.text` (a `str` subclass normalising both), never `message.content` — passing the raw list to `rich.Markdown` raises `TypeError`.
- **`ANTHROPIC_MAX_TOKENS` caps thinking *and* visible output together**, so a low value truncates answers mid-sentence.
- **Imports between these modules are absolute** (`from config import ...`). The directory is invoked as a flat script directory (`cd coffee_agent && python main.py`), not as a package. A relative import breaks it with "attempted relative import with no known parent package".
- **`write_document` overwrites without confirmation**, and on the `anthropic` backend every filename and document body the tools return is transmitted to the Claude API — including files opened while exploring and judged irrelevant. The sandbox limits which files can be *touched*, not where their contents *go*.
- **Conversation state is lossy.** `main.py` keeps history as `(role, text)` tuples, so tool calls, tool results and reasoning blocks are discarded between turns — the agent re-reads files it already opened. Retaining the full message list from `agent.invoke()` is the fix, but it means handling provider-specific block shapes in history too.

### Conventions

- `.env` holds real API keys and is git-ignored (the root `.gitignore`'s bare `.env` pattern matches at any depth). Never `git add -A` here; stage files explicitly. Add any new config key to `.env.example` with an empty or placeholder value.
- `setup.sh` reads `.env` before doing any work and **exits early when `LLM_PROVIDER=anthropic`**, skipping the Hugging Face login and multi-gigabyte model download. Anything vLLM-specific added to setup belongs after that early exit.
- User-facing failures go through `explain()` rather than surfacing a traceback; `AGENT_DEBUG=1` is the escape hatch.
- **No test suite, linter, or CI.** To verify a change, exercise the code — e.g. construct both backends without hitting the network:
  ```bash
  for p in vllm anthropic; do LLM_PROVIDER=$p ANTHROPIC_API_KEY=x \
    .venv/bin/python -c "from graph import build_agent; build_agent()"; done
  ```
- The venv is uv-managed and has **no `pip`**. Install with `uv pip install --python .venv/bin/python <pkg>` and add the package to `requirements.txt`.

### Development history

Two commits touch `coffee_agent/` (1 Aug 2026). It arrived largely complete: the five-module structure, the vLLM/Anthropic backend switch, the sandbox, and the coffee-can bridge all landed together, with the Qwen in-branch substitution following.

`requirements.txt`, `setup.sh` and `serve_vllm.sh` are currently **untracked**. The design intent is documented in the repo-root `CLAUDE.md` in more depth than the commit history conveys.

---

## 3. API

### 3.1 File tools (`tools.py`)

Exported as `TOOLS`. Paths may be relative (resolved against `AGENT_WORKSPACE`) or absolute (which must still land inside it).

```python
@tool
search_files(query: str, mode: Literal["name","content"] = "name", max_results: int = 30) -> str
```
Walks `AGENT_WORKSPACE` recursively. `mode="name"` matches `query` as a case-insensitive substring of the filename; `mode="content"` greps inside text-like files (`.txt`, `.md`, `.py`, `.csv`, `.json`, `.rst`). It does **not** search inside PDFs or Word documents. Returns workspace-relative paths, capped at `max_results`. Content mode is a linear scan that reads each candidate into memory — fine for a document folder, slow over a very large tree.

```python
@tool
read_document(path: str) -> str
```
Extracts plain text from `.txt`, `.md`, `.pdf`, `.docx`, `.xlsx`, `.xls`, plus the text extensions above. **Output is truncated at `MAX_CHARS` (12,000) with a notice appended** — for a long PDF the model sees only the beginning. Raise `MAX_CHARS` if that is too tight; the Claude backend has ample context.

```python
@tool
write_document(path: str, content: str) -> str
```
Writes `.txt`, `.md`, or `.docx`, choosing the format from the extension. For `.docx`, blank lines in `content` become paragraph breaks. Missing parent directories are created. **Overwrites an existing file without confirmation.**

```python
_resolve(path: str) -> Path            # not a tool -- the sandbox chokepoint
```
Resolves relative paths against `WORKSPACE_ROOT`, canonicalises (following symlinks), and raises `ValueError` unless the result stays inside `WORKSPACE_ROOT`. **Any new filesystem tool must route through it** — never call `open()`, `write_text()` or `unlink()` on a model-supplied path directly.

### 3.2 Coffee-can tools (`coffee_tools.py`)

Exported as `COFFEE_TOOLS`. All write to coffee-can's shared SQLite database. `bean` arguments accept either a numeric id or an exact name.

```python
@tool list_coffee_beans() -> str
@tool list_coffee_brew_sessions(bean: str = "") -> str

@tool create_coffee_bean(name: str, origin="", variety="", altitude="", roaster="",
                         producer="", process="", roast_date="") -> str
```
Registers a bean profile and marks it complete. **Always creates a new row** — call `list_coffee_beans` first to avoid duplicates (the system prompt instructs the model to do so).

```python
@tool add_coffee_bean_image(bean: str, path: str) -> str
```
Copies a photo already in the workspace (`.jpg`/`.jpeg`/`.png`/`.webp`/`.pdf`) into coffee-can's own storage as a page on that bean, so it appears in coffee-can's GUI/CLI. Capped at `coffee_can.paths.MAX_IMAGES_PER_BEAN` (5). Intended to be called with the same photo just OCR'd, so a bean filled in from a label keeps that label attached.

```python
@tool create_coffee_brew_session(bean: str, brew_date="", dripper="", filter_paper="",
                                 grinder="", grind_size="", water_ppm="", humidity="",
                                 dose_g=None, score=None, note="") -> str

@tool add_coffee_brew_stage(session_id: int, temperature_c=None, water_g=None,
                            time_seconds=None, circling="") -> str
```
Register a session against an existing bean, and append one pour to it.

```python
@tool extract_text_from_image(path: str) -> str
```
OCRs a photo in the workspace via a **direct Anthropic vision call** (its own `Anthropic(api_key=...)` client, not through `build_llm()`/LangChain) and returns plain transcribed text for the model to parse itself. Uses `ANTHROPIC_OCR_MODEL`, `_OCR_MAX_TOKENS = 2048`.

> **This makes `ANTHROPIC_API_KEY` a hard requirement for this one tool regardless of `LLM_PROVIDER`** — the only place in the project where that is true, because it is an independent API call rather than a turn of the chat model. It fails with an actionable message rather than crashing when unset.

There is no dedicated file-import tool: for CSV/spreadsheet/text sources the agent calls `read_document` and works out the fields itself before calling the `create_coffee_*` tools.

### 3.3 Graph (`graph.py`)

```python
SYSTEM_PROMPT: str          # steers tool use; the only lever for Claude's behaviour (no sampling params)
build_llm() -> BaseChatModel    # the backend switch -- see §2
build_agent()                   # create_react_agent(build_llm(), TOOLS + COFFEE_TOOLS, prompt=SYSTEM_PROMPT)
```

### 3.4 Upstream APIs consumed

| API | Used by | Auth | Notes |
| --- | --- | --- | --- |
| Anthropic Messages API | `build_llm()` via `langchain_anthropic` | `ANTHROPIC_API_KEY` | thinking enabled by default; no sampling params |
| Anthropic Messages API (vision) | `extract_text_from_image`, direct SDK | `ANTHROPIC_API_KEY` | independent of `LLM_PROVIDER` |
| DashScope OpenAI-compatible | `build_llm()` via `langchain_openai` | `QWEN_API_KEY` | in-branch substitution for Claude |
| vLLM OpenAI-compatible (local) | `build_llm()` via `langchain_openai` | `api_key="EMPTY"` | `temperature=0.2` |
| coffee-can storage layer | `coffee_tools.py` | — | Python import, not a network API |

### 3.5 Configuration

**Backend selection**

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `vllm` | `vllm` or `anthropic`. Anything else is a startup error. |

**`LLM_PROVIDER=anthropic`**

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | *(unset)* | Required unless Qwen is configured. Also readable from the shell environment. |
| `ANTHROPIC_MODEL` | `claude-opus-5` | Chat model |
| `ANTHROPIC_MAX_TOKENS` | `8192` | Caps thinking **and** visible output together |
| `QWEN_API_KEY` | *(unset)* | Set **with** `QWEN_MODEL` to use Qwen instead of Claude |
| `QWEN_MODEL` | *(unset)* | e.g. `qwen-max`. Both must be set or Claude is used. |
| `QWEN_MAX_TOKENS` | `8192` | Output cap |
| `QWEN_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | DashScope endpoint |

> ⚠️ **Documentation drift.** `README.md` states the `QWEN_BASE_URL` default is the international endpoint (`dashscope-intl…`), but `config.py:31` actually defaults to the **mainland China** endpoint (`dashscope.aliyuncs.com`, no `-intl`). The sibling `coffee_server/` and `coffee/` both default to `-intl`. DashScope keys are region-locked, so this mismatch produces a `401 Incorrect API key provided` for an international key unless `QWEN_BASE_URL` is set explicitly. Either the code or the README should change.

**`LLM_PROVIDER=vllm`**

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_ID` | `meta-llama/Llama-3.2-3B-Instruct` | HF repo `setup.sh` downloads |
| `SERVED_MODEL_NAME` | `local-llama` | Model name requested from vLLM |
| `VLLM_PORT` | `8000` | Port for the vLLM server |
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | Endpoint the agent calls |
| `HF_TOKEN` | *(unset)* | Lets `setup.sh` log in non-interactively |

> Note: `config.py:14` reads **`SERVED_MODEL_NAME`** into a constant named `MODEL_ID`. `MODEL_ID` in `.env` is consumed by `setup.sh`/`serve_vllm.sh` (which model to download and serve), not by `config.py`.

**Both backends**

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENT_WORKSPACE` | `~/Documents` | Sandbox root; created if missing |
| `ANTHROPIC_OCR_MODEL` | `claude-opus-5` | Vision model for `extract_text_from_image`; deliberately separate from `ANTHROPIC_MODEL` |
| `AGENT_DEBUG` | *(unset)* | `1` re-raises with a full traceback instead of a one-line message |
