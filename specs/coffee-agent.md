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

### Relations with the other sub-projects

| Relation | Direction | Nature |
| --- | --- | --- |
| `coffee_agent/` → `coffee/` | one-directional, outbound | imports coffee-can's storage layer; shares its SQLite file |
| `coffee/` → `coffee_agent/` | none | coffee-can does not know this project exists |
| `coffee_agent/` ↔ `coffee_server/` | none | no shared code; different purpose entirely |
| `coffee_agent/` ↔ `coffee_android/` | two-directional, **offline** | no code and no network path — a zip, carried by the user (§3.3) or by the agent over a USB cable (§3.4) |

**The coffee-can bridge.** `coffee_tools.py` inserts `../coffee/src` onto `sys.path` at import time and imports `coffee_can.repo` / `db` / `paths` directly, rather than installing the `coffee-can` package. That package's `pyproject.toml` pulls in PySide6 for its GUI, which this project has no reason to depend on; the three modules it needs are standard-library only. **Do not `uv pip install -e ./coffee`** — it would drag the GUI stack into this venv for nothing used here. If `coffee/` restructures its package layout, this bridge needs updating in lockstep.

Both projects read and write the same `~/.local/share/coffee-can/coffee.db` via `coffee_can.paths.db_path()`. There is no separate agent-side data store, and no synchronisation problem to solve — records created here appear in coffee-can's GUI and CLI immediately. `add_coffee_bean_image` copies files into `coffee_can.paths.images_dir(bean_id)` exactly as `repo.add_bean_image()` always has, so pages attached here are indistinguishable from ones added through the GUI.

Note the asymmetry with `coffee/`'s own OCR: this project does **not** use `coffee_can.ocr` (local Tesseract) or `coffee_can.claude_ocr` (structured field extraction). It makes its own direct Claude vision call returning plain transcribed text, keeping the model-does-the-parsing division of labour.

`coffee_server` is unrelated — a stateless multi-provider proxy with no tool loop and no memory. This project talks to provider SDKs directly and does not route through it.

**The Android bridge is not a bridge.** `sync_tools.py` moves the same records to and from the phone, but there is no link between the two programs at all: the desktop writes a zip, the user carries it, the phone reads it (and vice versa). That shape is not an implementation convenience — it is what keeps `specs/legal-accounts.md` §3.8's "no user content server-side" true while still letting one person's two devices hold the same log. See §3.3.

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
├── sync_tools.py     # coffee-can bridge: desktop <-> Android bundle export/import
├── usb_sync.py       # the same sync driven over an adb cable, no file to carry
├── graph.py          # SYSTEM_PROMPT, build_llm() backend switch, build_agent()
├── main.py           # the REPL, plus explain() for one-line error messages
└── documentations/   # default AGENT_WORKSPACE sandbox
```

Seven modules, wired in one direction:

```
                    tools.py ──────┐
config.py  ->       coffee_tools.py│
(.env)              sync_tools.py  +->  graph.py  ->  main.py
                    usb_sync.py ───┘    (backend)     (CLI loop)
```

All four tool modules read `config.py` and all feed `graph.py`'s tool list. `tools.py` and `coffee_tools.py` are independent peers; the two sync modules are the exceptions to the flat fan-in. `sync_tools.py` imports `_resolve` from `tools.py`, because the sandbox has exactly one chokepoint and a second copy of it is a second thing to get wrong. `usb_sync.py` imports `_export_to` and `_read_bundle` from `sync_tools.py`: the cable changes how a bundle *travels*, never what is in it, so there is exactly one implementation of the format.

### Module responsibilities

| Module | Responsibility |
| --- | --- |
| `config.py` | Calls `load_dotenv()` at import with an **explicit path** (`Path(__file__).parent/".env"`), not a bare call — a bare call walks up parent directories and would risk picking up the sibling `coffee_server/`'s `.env`. Exposes every setting as a module constant so config is resolved exactly once. Creates `WORKSPACE_ROOT` as an import side effect. |
| `tools.py` | The three file `@tool` functions and the `TOOLS` list. `_resolve()` is the single sandbox chokepoint. `MAX_CHARS = 12000` caps `read_document` output. |
| `coffee_tools.py` | `COFFEE_TOOLS`: six coffee-can registration/listing tools plus `extract_text_from_image`. Owns the `sys.path` bridge and the direct Anthropic vision call. |
| `sync_tools.py` | `SYNC_TOOLS`: export/inspect/apply for the desktop ↔ Android **bundle**, a zip the user carries between their own devices. Owns `BUNDLE_VERSION` (must match Android's `SyncBundle.VERSION`), the by-name conflict model, and the field maps that decide what crosses. |
| `usb_sync.py` | `USB_TOOLS`: the same bundle moved over `adb` instead of by hand. Owns the drop-box path, the device preflight, and the rule that the **app** must create the drop box (see §3.4). |
| `graph.py` | `SYSTEM_PROMPT`, `build_llm()` (the backend switch), and `build_agent()` — a thin wrapper over `create_react_agent` wired with `TOOLS + COFFEE_TOOLS + SYNC_TOOLS + USB_TOOLS`. |
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

Two commits touch `coffee_agent/` (1 Aug 2026). It arrived largely complete: the original five-module structure, the vLLM/Anthropic backend switch, the sandbox, and the coffee-can bridge all landed together, with the Qwen in-branch substitution following.

`sync_tools.py` is the one later addition (16 Aug 2026), written against `coffee_android`'s `SyncBundle.kt` as the other half of the same format. It is currently **untracked**, along with its wiring into `graph.py`.

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

### 3.3 Desktop ↔ Android sync tools (`sync_tools.py`)

```python
BUNDLE_VERSION: int = 1     # must equal coffee_android's SyncBundle.VERSION

export_coffee_bundle(destination: str) -> str
inspect_coffee_bundle(bundle: str) -> str
apply_coffee_bundle(bundle: str, resolutions: str = "{}") -> str
```

All three take workspace paths through `tools._resolve()`. `resolutions` is a JSON object mapping a conflicted bean name to `"phone"` / `"desktop"` / `"skip"`.

**Status: both directions, asymmetric conflict handling.** `SyncBundle.kt` both exports and imports, from Profile → "Sync with desktop" (sharing the zip via FileProvider one way, `ActivityResultContracts.OpenDocument` the other).

The two sides resolve conflicts differently *on purpose*, and the reason is about who can be asked rather than about the data. This side is driven by an agent that can put "phone or desktop?" to the user for each bean, so it does, and `"phone"` genuinely replaces a local bean. `SyncBundle.importFrom` has no turn-taking available, so it **never overwrites**: a bean whose name already exists is skipped and counted, and only genuinely new names are inserted. Declining is the only resolution that cannot destroy anything, which is what makes it the right default for the side that cannot ask.

Two keys the phone deliberately ignores on the way in: `stage_number` and an image's `position`, because the exporter writes both lists in order and the insertion index is authoritative.

**Why a file and not a server call.** `specs/legal-accounts.md` §3.8 binds the architecture to *no user content server-side*, and the Android app says so to the user in three languages. A bundle moves data between two devices the same person owns, carried by them, with the developer never in the path — so the claim stands. Routing sync through `coffee_server` would not, and would re-open §3.8 and the Play Data safety form; `CoffeeRepository`'s own docstring says as much from the phone's side.

**Bundle format** (zip, both sides write it):

| Member | Contents |
| --- | --- |
| `manifest.json` | `{version, source: "desktop"\|"android", beans, exported_at?}` |
| `beans.json` | Array of beans, each with `sessions[]` (each with `stages[]`) and `images[]` |
| `images/…` | The image files, referenced by each image entry's `file` |

Field names are **coffee-can's snake_case column names** on both sides — the bundle is a wire format between two schemas and one has to win; picking the desktop's lets `apply_coffee_bundle` hand values straight to `repo.update_bean_field` with no translation table to keep in step from two directions. **Null fields are omitted, and that is load-bearing**: `_differences()` reads an absent key as *no opinion* rather than as an empty value, which is what stops a column the phone never filled from disagreeing with a desktop default and manufacturing a phantom conflict on an identical bean.

**Conflict model.** Beans match **by name** — the only identifier the two databases share, since coffee-can's `beans.id` and Room's are independent autoincrement sequences. A name on both sides with any differing field is a conflict; `inspect_coffee_bundle` names them and the field that differs, and `apply_coffee_bundle` refuses to touch one without an explicit resolution, reporting it as unanswered instead. `"phone"` deletes the local bean first (cascading its sessions and stages, and unlinking its image files, which `ON DELETE CASCADE` cannot do) so a replaced bean can't end up carrying the other side's sessions. Matching on a mutable, non-unique field is a real limitation — a rename on either device imports as a second bean — and the tools say so in their own output rather than hiding it.

**What does not cross**, because the schemas diverged: Android's session `waterG`/`waterTempC` (no coffee-can column), coffee-can's session `humidity` (no Room field), and Room's stage `label` (its free `note` maps to `circling`). Both flavour-axis sets **do** cross, on beans *and* sessions — a bean whose `flavor_source` is `auto` derives its radar by averaging its sessions, so dropping the session axes would import beans that can never recompute one.

### 3.4 USB sync (`usb_sync.py`)

```python
send_coffee_data_to_phone() -> str
fetch_coffee_data_from_phone(destination: str = "from-phone.zip") -> str
```

The same bundle format, carried by the agent over `adb` instead of by the user. No network is involved in either direction, so §3.8 is untouched — this is the strongest form of "the developer never holds it" the architecture can offer.

**A cable cannot make an app read a file**, only the app may touch its own Room database. So each direction is *move the file, then fire an intent* (`app.coffeecan.action.IMPORT_BUNDLE` / `EXPORT_BUNDLE`, handled by `MainActivity.handleUsbSync`).

**The drop box is `/sdcard/Android/data/app.coffeecan/files/sync/`** — the one directory both sides reach unaided: `adb` runs as the shell user and may write there, and an app can always read its *own* external files dir with no permission. Since Android 11 it is closed to every other app on the phone.

> **The desktop must never `mkdir` that directory.** A directory created over `adb` is owned by the shell user, while everything else under `files/` is owned by the app; the app then gets `EACCES` writing its export into it and `File.exists()` returns **false** for a bundle pushed there — so the failure presents as "the desktop never sent anything" rather than as a permission error. `_wake_app_and_wait_for_dropbox()` launches the app and waits for it to create its own, which makes the ownership correct by construction. This was found on a real device, not reasoned about.

`fetch_coffee_data_from_phone` polls for the outgoing zip's size to stop changing across two reads before pulling — a mid-write archive pulls cleanly and only fails much later, at parse time. It stops after pulling and does **not** import: conflicts still go through §3.3's per-bean conversation.

### 3.5 Graph (`graph.py`)

```python
SYSTEM_PROMPT: str          # steers tool use; the only lever for Claude's behaviour (no sampling params)
build_llm() -> BaseChatModel    # the backend switch -- see §2
build_agent()                   # create_react_agent(build_llm(), TOOLS + COFFEE_TOOLS + SYNC_TOOLS + USB_TOOLS, prompt=SYSTEM_PROMPT)
```

### 3.6 Upstream APIs consumed

| API | Used by | Auth | Notes |
| --- | --- | --- | --- |
| Anthropic Messages API | `build_llm()` via `langchain_anthropic` | `ANTHROPIC_API_KEY` | thinking enabled by default; no sampling params |
| Anthropic Messages API (vision) | `extract_text_from_image`, direct SDK | `ANTHROPIC_API_KEY` | independent of `LLM_PROVIDER` |
| DashScope OpenAI-compatible | `build_llm()` via `langchain_openai` | `QWEN_API_KEY` | in-branch substitution for Claude |
| vLLM OpenAI-compatible (local) | `build_llm()` via `langchain_openai` | `api_key="EMPTY"` | `temperature=0.2` |
| coffee-can storage layer | `coffee_tools.py`, `sync_tools.py` | — | Python import, not a network API |
| `coffee_android`'s `SyncBundle` | `sync_tools.py` | — | A zip file the user carries; no network path exists between them, by design |

### 3.7 Configuration

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
| `ADB_PATH` | *(auto)* | `adb` for USB sync; falls back to `PATH`, then `~/android-sdk/platform-tools/adb` |
| `ANDROID_PACKAGE` | `app.coffeecan` | The application id the cable talks to |
