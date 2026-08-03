# `coffee/` — coffee-can

A CLI + desktop GUI application for logging hand-brew coffee: one profile per bag of beans, brewing sessions logged against it, and a flavor profile that builds up over time.

- [1. Project background](#1-project-background)
- [2. Development details](#2-development-details)
- [3. API](#3-api)

---

## 1. Project background

### What it is designed for

`coffee-can` is the product at the centre of this repo. It solves a small, concrete problem: a person brewing coffee by hand wants to remember what they did and whether it worked. Commercial apps exist, but they are cloud accounts; this one keeps everything in a local SQLite file the user owns.

The data model has three levels:

1. **Bean profile** — one per bag: name, origin, variety, altitude, roaster, producer, process, roast date, free-text note, and up to five photos/PDFs of the bag itself.
2. **Brewing session** — one per cup, logged against a bean: date, dripper, filter paper, grinder, grind size, water ppm, humidity, dose, a 0–5 score, an extraction assessment, a tasting note, and eleven 0–5 flavor ratings.
3. **Brewing stage** — one per pour within a session: temperature, water weight, duration, and agitation/circling.

Two design decisions shape everything else:

- **One database, two front ends.** The GUI (`coffeecan-gui`) and the CLI (`coffeecan`) are equal peers over the same `~/.local/share/coffee-can/coffee.db`. Neither owns the data. A profile created in the CLI appears in the GUI immediately.
- **Draft rows are created eagerly.** Opening "New Profile" or "New Session" inserts the row straight away, so photos and stages can attach without a "save first" step. A row that is closed without ever being touched is deleted again, so the eager insert never leaves litter.

On top of the manual entry there is an optional AI layer, all of it degradable: a bag label can be photographed and read into fields, a brewing recipe can be suggested, and a session can be dictated by voice. Every one of these paths falls back to something simpler (or reports an actionable error) when unconfigured.

### Relations with the other two sub-projects

| Relation | Direction | Nature |
| --- | --- | --- |
| `coffee_agent/` → `coffee/` | one-directional, inbound | `coffee_agent` imports this project's storage layer directly |
| `coffee/` → `coffee_agent/` | none | this project does not know `coffee_agent` exists |
| `coffee/` ↔ `coffee_server/` | none | no code, config, or data shared |

**`coffee_agent` reads and writes this project's database.** It adds `coffee/src` to `sys.path` and imports `coffee_can.repo`, `coffee_can.db`, and `coffee_can.paths` directly, rather than installing `coffee-can` as a package — installing it would drag in PySide6 (the GUI stack) for no benefit. Records the agent creates land in the same SQLite file and show up in this app's own GUI and CLI, indistinguishable from manually entered ones.

The practical consequence for anyone working here: **`repo.py`, `db.py`, and `paths.py` are a published interface, not private implementation.** They must keep to the standard library only, and restructuring the package layout breaks the sibling project. `ocr.py`, `claude_ocr.py`, the `gui/` package, and `cli.py` are *not* used by `coffee_agent` — it does its own OCR through a direct Claude call.

`coffee_server` is unrelated. It is a general-purpose LLM proxy that happens to live in the same repo; it never touches coffee data. Note that this project calls provider APIs (Claude, Qwen) **directly** rather than through `coffee_server`.

---

## 2. Development details

### Layout

```
coffee/
├── pyproject.toml            # packaging; entry points; PySide6/click/rich/pytesseract/Pillow deps
├── README.md                 # user-facing docs
├── .env / .env.example       # API keys (git-ignored)
└── src/coffee_can/
    ├── db.py                 # schema + connection + migrations
    ├── repo.py               # all CRUD; the data-layer API
    ├── paths.py              # data dir, db path, image dirs, limits
    ├── formatting.py         # display/parse helpers shared by CLI and GUI
    ├── cli.py                # the `coffeecan` command tree (click + rich)
    ├── profile.py            # the local user's name/email/avatar
    ├── choice_lists.py       # shared loader for the JSON-backed dropdowns
    ├── drippers.py filters.py grinders.py processes.py
    ├── ocr.py                # local Tesseract OCR + regex field heuristics
    ├── claude_ocr.py         # label scanning via Claude vision
    ├── qwen_ocr.py           # label scanning via Qwen vision
    ├── qwen_brew_suggest.py  # brew recipe suggestion via Qwen (text)
    ├── qwen_brew.py          # voice → session parsing via Qwen-Omni audio
    ├── whats_new.py          # roasters' public catalogues via their own JSON endpoints
    ├── assets/               # icon.svg, Fredoka fonts, dropdown JSON seed lists
    └── gui/                  # PySide6 desktop app
```

### Module responsibilities

**Data layer** — the part `coffee_agent` also depends on. Standard library only.

| Module | Responsibility |
| --- | --- |
| `db.py` | Owns `SCHEMA` (all four tables) and `connect()`. `_migrate()` brings an older database up to date with additive `ALTER TABLE ADD COLUMN` calls; flavor columns are generated from `repo.FLAVOR_FIELDS`, so adding a flavor axis migrates automatically. |
| `repo.py` | Every read and write. Also owns the domain constants (`FLAVOR_AXES`, `BEAN_FIELDS`, `SESSION_FIELDS`, `EXTRACTION_*`) that drive columns, forms, charts and CLI output alike. Every write commits immediately, so an interrupted session never loses answered fields — that is what makes "save as draft" a side effect rather than a code path. |
| `paths.py` | `data_dir()` (honours `XDG_DATA_HOME`, and migrates the pre-rename `coffee-journal/` directory in place), `db_path()`, `images_dir(bean_id)`, plus `MAX_IMAGES_PER_BEAN` and `ALLOWED_IMAGE_SUFFIXES`. |
| `formatting.py` | Small pure helpers (`format_score`, `format_extraction`, `format_seconds`, `format_or_dash`, `parse_time_to_seconds`) shared by both front ends. |

**Front ends**

| Module | Responsibility |
| --- | --- |
| `cli.py` | The `coffeecan` command tree, built on `click`, rendered with `rich`. Interactive prompt helpers (`ask`, `ask_float`, `ask_time`) drive the add/edit flows field by field. |
| `gui/app.py` | Entry point: registers the bundled Fredoka fonts, applies the stylesheet, opens `MainWindow`. |
| `gui/main_window.py` | Welcome screen: header banner, the bean table, and a four-pane row (contribution calendar, flavor radar, the **What's New** news ticker, the **Can see** coffee shelf). Also `CoffeeShelfCard`, one clickable coffee on that shelf. |
| `gui/whats_new_dialog.py` | A roaster list, then a product table for whichever one is picked, fetched via `whats_new.py` on a background thread. Two stacked pages in one dialog rather than nested modals. Currently has no entry point in the window (`MainWindow._open_whats_new` is kept, unconnected). |
| `gui/can_see_dialog.py` | **Can see**'s "more": every fetched coffee in one table, filtered locally by roaster, origin, stock and name. Fed the listings the main window already holds, so opening it costs no requests. |
| `gui/bean_dialog.py` | The bean profile editor — fields, photo carousel, label scanning, the sessions table, and the per-bean flavor profile. Hosts the scan worker and its review dialog. |
| `gui/brew_dialog.py` | The session editor — brew details, the stages table with its `StageDialog`, and the evaluation block (score, extraction bar, note, eleven flavor sliders, live radar). |
| `gui/ai_brew_dialog.py` | "Ask AI": pick a dripper, get a Qwen recipe, review it, turn it into a real session with real stage rows. |
| `gui/voice_brew_dialog.py` | "Voice Session": record a description with `QMediaRecorder`, send it to Qwen-Omni, review, create the session. Imports QtMultimedia at module level so a build without it fails at import and the caller disables the button gracefully. |
| `gui/camera_dialog.py` | Live camera capture for label photos. Same module-level QtMultimedia pattern. |
| `gui/share_card.py` | Renders a bean or session to a shareable image. |
| `gui/profile_dialog.py` | The local user's name/email/avatar. |
| `gui/install_launcher.py` | `coffeecan-install-launcher`: writes a `.desktop` file and copies `assets/icon.svg` into the hicolor icon theme. |
| `gui/theme.py` | The global stylesheet — green palette, `variant="primary"`/`"destructive"` button classes. |
| `gui/background.py` | Owns the *lifetime* of background `QThread`s. A `QThread` destroyed while running aborts the process, and the dialog that started one is routinely closed before the call returns, so a running worker is owned by this module and app quit waits for it. |
| `gui/widgets.py` | All custom widgets (~1300 lines). See the API section. |

### Conventions and constraints

- **No test suite, linter, formatter, or CI.** Verification is done by exercising the code. Do not reference invented commands.
- **`.env` location depends on how the app was launched** — see the configuration table in §3. This is a recurring source of confusion: a pipx install cannot see `coffee/.env`.
- **Optional dependencies are imported lazily**, inside the function that needs them (`anthropic`, `openai`, `PySide6.QtMultimedia`, `QtPdf`). The app must work with none of them installed.
- **Adding a flavor axis is a one-line edit** to `repo.FLAVOR_AXES`. Columns, migrations, sliders, radar charts, averages and CLI output are all derived from it.

### Development history

Seven commits touch `coffee/` (31 Jul – 2 Aug 2026), in roughly four phases:

1. **Core tracker** — SQLite schema, `repo`/`db`/`paths`, the click CLI, then the PySide6 GUI. Renamed from "coffee-journal" to "coffee-can" early, leaving the data-dir migration in `paths.py` and the launcher cleanup in `install_launcher.py`.
2. **Richer capture** — bag photos and the carousel, local Tesseract OCR, then Claude vision as a higher-accuracy path, camera capture, the contribution calendar and radar charts.
3. **Social/sharing** — share cards for beans and sessions, the user profile card, the Fredoka font and green theme.
4. **AI assistance** — Qwen brew suggestions, and the walking-can busy indicator with `background.py` to keep slow calls off the GUI thread.

**The working tree currently has substantial uncommitted work** beyond the last commit (`4e1a553`): Qwen vision OCR (`qwen_ocr.py`) and its priority over Claude, voice sessions (`qwen_brew.py`, `gui/voice_brew_dialog.py`), the continuous extraction bar, the nullable score with its hint text, the flavor-axis split into eleven axes, and the `SaveButton` thumbs-up confirmation. `gui/background.py` and `gui/share_card.py` are still untracked.

---

## 3. API

### 3.1 Database schema

Created by `db.SCHEMA`, migrated by `db._migrate()`. `{flavor}` expands to the eleven `flavor_*` REAL columns from `repo.FLAVOR_FIELDS`.

**`beans`**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | autoincrement |
| `name` | TEXT NOT NULL | |
| `origin`, `variety`, `altitude`, `roaster`, `producer`, `process`, `roast_date`, `note` | TEXT | all optional |
| `status` | TEXT NOT NULL | default `'draft'`; set to `'complete'` on save |
| `flavor_source` | TEXT NOT NULL | default `'auto'`; `'manual'` pins a hand-set profile |
| `created_at`, `updated_at` | TEXT NOT NULL | `datetime('now')` |
| `{flavor}` | REAL | eleven columns |

**`bean_images`** — `id`, `bean_id` (FK → `beans`, ON DELETE CASCADE), `position` INTEGER, `file_path` TEXT, `rotation` INTEGER default 0.

**`brew_sessions`** — `id`, `bean_id` (FK, CASCADE), `brew_date`, `dripper`, `filter_paper`, `grinder`, `grind_size`, `water_ppm`, `humidity` TEXT; `dose_g` REAL; `score` REAL (NULL = unscored); `extraction` REAL (−1…+1, NULL = not assessed); `note` TEXT; `status`; `created_at`/`updated_at`; `{flavor}`.

**`brew_stages`** — `id`, `session_id` (FK, CASCADE), `stage_number` INTEGER, `temperature_c` REAL, `water_g` REAL, `time_seconds` INTEGER, `circling` TEXT.

> **Migration note.** `extraction` was briefly declared `INTEGER` before becoming `REAL`. Databases carrying the old declaration are left alone: SQLite only narrows a REAL to an INTEGER when lossless, so fractional values round-trip intact. Similarly, the retired `flavor_sour_fermented` column is kept (unreferenced) after the axis was split into `flavor_sour` and `flavor_fermented`; `_migrate_split_sour_fermented()` copies the old value to `flavor_sour` only, filling NULLs so it never repeats or overwrites later edits.

### 3.2 `repo.py` — the data-layer API

Also imported by `coffee_agent`. Every function takes an open `sqlite3.Connection` as its first argument.

**Constants**

| Name | Value / shape |
| --- | --- |
| `FLAVOR_AXES` | 11 `(field, label)` pairs: Fruity, Floral, Tea-like, Sweet, Nutty/Cocoa, Spices, Roasted, Cereal, Green/Vegetative, Sour, Fermented |
| `FLAVOR_FIELDS` | the field names from the above |
| `BEAN_FIELDS`, `SESSION_FIELDS` | writable column allowlists for `update_*_field` |
| `EXTRACTION_MIN` / `EXTRACTION_MAX` | `-1.0` / `1.0` |
| `EXTRACTION_ZONES` | `("Under extracted", "Well extracted", "Over extracted")` |
| `EXTRACTION_ZONE_EDGE` | `1/3` — where the outer zones begin |
| `NotFoundError` | raised by the `resolve_*` helpers |

**Beans**

```python
create_bean(conn, name) -> int
update_bean_field(conn, bean_id, field, value) -> None      # field must be in BEAN_FIELDS
set_bean_status(conn, bean_id, status) -> None
get_bean(conn, bean_id) -> sqlite3.Row | None
resolve_bean(conn, identifier) -> sqlite3.Row               # by id or exact name; raises NotFoundError
list_beans(conn)                                            # rows + session_count
delete_bean(conn, bean_id) -> None                          # cascades to sessions/images
```

**Bean images**

```python
add_bean_image(conn, bean_id, source_path: Path) -> int     # copies into images_dir(); ValueError past MAX_IMAGES_PER_BEAN
list_bean_images(conn, bean_id)
delete_bean_image(conn, image_id) -> None
rotate_bean_image(conn, image_id, degrees=90) -> int        # metadata only; never rewrites the file
```

**Sessions**

```python
create_session(conn, bean_id) -> int
update_session_field(conn, session_id, field, value) -> None   # field must be in SESSION_FIELDS
set_session_status(conn, session_id, status) -> None
get_session(conn, session_id) -> sqlite3.Row | None
resolve_session(conn, identifier) -> sqlite3.Row
list_sessions(conn, bean_id=None)
delete_session(conn, session_id) -> None
count_sessions_by_date(conn) -> dict                            # {ISO date: count}, for the calendar
```

**Stages**

```python
add_stage(conn, session_id, temperature_c, water_g, time_seconds, circling) -> int   # returns stage_number
list_stages(conn, session_id)
get_stage(conn, stage_id) -> sqlite3.Row | None
update_stage(conn, stage_id, temperature_c, water_g, time_seconds, circling) -> None
delete_stage(conn, stage_id) -> None
```

**Flavor aggregates** — both return `(session_count, [mean per axis in FLAVOR_AXES order])`, or `(0, None)` when nothing is rated. Sessions with every axis at 0/NULL are excluded.

```python
get_average_flavor_scores(conn)
get_bean_average_flavor_scores(conn, bean_id)
```

### 3.3 CLI — `coffeecan`

```
coffeecan bean  add                       # interactive: creates a profile field by field
             list                         # table of profiles + session counts
             show   <id-or-name>          # full detail plus its sessions
             edit   <id-or-name>
             delete <id-or-name>

coffeecan brew  add    <bean-id-or-name>  # interactive: details, stages, evaluation
             list   [--bean <id-or-name>]
             show   <session-id>
             edit   <session-id>          # resume a draft, add stages, evaluate later
             delete <session-id>
```

GUI entry points: `coffeecan-gui`, and `coffeecan-install-launcher` (one-time desktop integration).

### 3.4 Optional AI integrations

Four independent modules, each with the same contract shape: an `is_configured()` predicate, one public function, and a single exception type callers catch to fall back. The `openai` and `anthropic` packages are optional and imported lazily.

| Module | Public function | Provider / model | Key env vars | Raises |
| --- | --- | --- | --- | --- |
| `ocr.py` | `extract_text(path)`, `guess_bean_fields(path)` | local Tesseract + regex heuristics | — | `OcrUnavailableError` |
| `claude_ocr.py` | `guess_bean_fields(path) -> dict` | Anthropic vision, `ANTHROPIC_OCR_MODEL` (default `claude-opus-5`) | `ANTHROPIC_API_KEY` | `ClaudeOcrUnavailableError` |
| `qwen_ocr.py` | `guess_bean_fields(path) -> dict` | Qwen vision via DashScope, `QWEN_OMNI_MODEL` (default `qwen3.5-omni-flash`) | `QWEN_API_KEY`, `QWEN_BASE_URL` | `QwenOcrUnavailableError` |
| `qwen_brew_suggest.py` | `suggest_brew(bean_info, dripper) -> dict` | Qwen text chat via DashScope, `QWEN_CHAT_MODEL` (default `qwen3.6-plus`) | `QWEN_API_KEY`, `QWEN_BASE_URL` | `QwenBrewUnavailableError` |
| `qwen_brew.py` | `transcribe_brew_session(audio_bytes, audio_format, bean_info) -> dict` | Qwen-Omni audio, `QWEN_OMNI_MODEL` | `QWEN_API_KEY`, `QWEN_BASE_URL` | `QwenUnavailableError` |

All requests use a 90-second timeout, because the caller runs on a background thread behind a busy indicator with no way to cancel an in-flight SDK call.

**Label-scan fallback order.** `gui/bean_dialog.py`'s `_ScanWorker` tries **Qwen → Claude → local Tesseract**, dropping to the next on `is_configured()` returning false or the call raising. Qwen is deliberately first: an install typically has both keys set (Qwen for voice sessions, Anthropic for other features), and without an explicit order the scan would silently bill whichever was checked first.

**Returned shapes.** `guess_bean_fields` returns `{field: str}` over the non-flavor `BEAN_FIELDS`, empty string where absent. `suggest_brew` returns `{"summary": str, "dose_g": float|None, "grind_size": str, "stages": [{"temperature_c", "water_g", "time_seconds", "circling"}]}`; `transcribe_brew_session` returns the same plus `"dripper": str`. Both normalise defensively — neither endpoint's JSON mode guarantees a shape, and the Qwen modules strip markdown fences before parsing.

### 3.5 Reusable GUI widgets (`gui/widgets.py`)

| Widget / function | Purpose |
| --- | --- |
| `RadarChart(labels)` | N-axis 0–5 radar. `set_values(values, has_data=True)`. Handles any axis count. |
| `ExtractionBar(labels, minimum=-1.0, maximum=1.0)` | Continuous under/well/over-extracted bar with zone names drawn *inside* it, tinting light green → logo green → dark green as it moves. `value()` / `setValue()` / `valueChanged`. Not a `QSlider`: continuous, labels inside the groove, whole-bar tint. |
| `WalkingCanStrip` | Green strip with a can walking along the bottom. `_detour_rect()` is a subclass hook — return a rect and the can walks a lap around it. |
| `HeaderBanner` | Main-window header; `set_logo(label, size)` registers the logo as the can's detour target. |
| `WalkingCanLoader` | The same strip sized as an inline busy indicator. Requires the slow work to be off the GUI thread. |
| `SaveButton(text="Save")` | `flash_saved()` swaps the label for `thumbs_up_can_pixmap()` for 1.5 s, pinning the width so neighbours don't shift. |
| `ContributionCalendar` | GitHub-style day grid; `set_counts({date: n})`. |
| `ImageCarousel`, `ImageViewerDialog` | Paged photo/PDF viewer with rotation and zoom. |
| `ChoiceCombo` and `DripperCombo` / `GrinderCombo` / `FilterCombo` / `ProcessCombo` | Editable dropdowns seeded from `assets/*.json`, with "Other (type manually)…" persisting new entries to the data dir. |
| `ToggleSwitch`, `OptionalDateEdit`, `NoteEdit` | Animated switch; date picker with a "not set" state; auto-growing note field. |
| `circular_pixmap`, `default_avatar_pixmap`, `share_icon_pixmap`, `thumbs_up_can_pixmap` | Programmatically drawn pixmaps, so colour is controlled exactly rather than depending on glyph rendering. |

> `ToggleSwitch` is currently unused — it was the old "Scored" control, replaced when score became a nullable spinbox with hint text.

### 3.6 Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | enables Claude label scanning | *(unset)* |
| `ANTHROPIC_OCR_MODEL` | Claude vision model | `claude-opus-5` |
| `QWEN_API_KEY` | enables Qwen label scanning, voice sessions **and** "Ask AI" brew suggestions | *(unset)* |
| `QWEN_OMNI_MODEL` | must be omni/vision-capable — a text-only model cannot read a photo or audio | `qwen3.5-omni-flash` |
| `QWEN_BASE_URL` | DashScope OpenAI-compatible endpoint | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `QWEN_CHAT_MODEL` | text chat model for "Ask AI" brew suggestions and news ranking — text-only, does **not** need an omni model | `qwen3.6-plus` |
| `XDG_DATA_HOME` | relocates the data directory | `~/.local/share` |

**Which `.env` is read depends on how the app was launched:**

| Launch method | File read |
| --- | --- |
| pipx install (`coffeecan-gui`, app-menu icon) | `~/.local/share/coffee-can/.env` |
| from a source checkout | `coffee/.env` |

Each module calls `load_dotenv()` (walks up from the package) *and* `load_dotenv(data_dir()/".env")`. A pipx install lives in pipx's venv, so walking up never reaches the checkout — **editing only `coffee/.env` leaves the key invisible to an installed app**, and any feature with a fallback quietly uses the next provider down. Real environment variables always win over both files.

### 3.7 What's New — reading roasters' public catalogues (`whats_new.py`)

`whats_new.py` reads what a handful of French roasters currently have on
sale, from each roaster's *own* site: name, price, weight, in stock, a short
description excerpt, a link to the real product page, and the URL of the
listing photo. Two front ends consume it — the **Can see** pane and its
"more" dialog (§3.7.1), and `whats_new_dialog.py`, a per-roaster table that
is fully built but currently has no button wired to it.

This is the crawler `specs/legal.md` governs, and that spec's binding rules
are not optional here — this section only summarises how the code follows
them, not why. Two things anchor everything else in the module:

- **Tier 2 only** (`specs/legal.md` §3.2 rule 7): every roaster is fetched
  through the first-party JSON endpoint the platform itself exposes for
  listing products — Shopify's `/products.json`, WooCommerce's Store API
  (`/wp-json/wc/store/v1/products`) — never HTML scraping. `ROASTERS` in
  `whats_new.py` is exactly the five sites the spec's live survey (§2.2)
  confirmed have such an endpoint (Datura, Belleville Brûlerie, Coutume,
  L'Arbre à Café, Tanat). Terres de Café and Lomi (no tier-2 endpoint) and
  Cafés Lugat (no online catalog at all) are deliberately absent — adding
  them means building the heavier sitemap/HTML tier the spec describes, not
  appending a row to this dict.
- **Facts only, never expression** (`specs/legal.md` §3.8): a `Listing` keeps
  name, price, weight, stock, a canonical URL, `fetched_at`, and an
  `image_url`, plus a description *excerpt* — `_excerpt()` strips HTML and
  hard-caps at 200 characters, well under where droit d'auteur analysis
  treats prose as original.
- **Images are hotlinked, never downloaded** (`specs/legal.md` §3.8 rule 31).
  `whats_new.py` only ever extracts the image *URL* from the listing JSON —
  text, not bytes. Photos are fetched only at the moment they are displayed,
  by `widgets.RemoteImageLabel` (the shelf cards and both dialogs' preview
  panels) and `gui/whats_new_dialog.py`'s own older copy of the same logic:
  one request at a time, aborting whatever was in flight if the selection
  moves on, HTTP caching switched off, held only as an in-memory `QPixmap`,
  never written to disk. No image is ever part of the cached listing data, a
  fixture, or anything this project persists.

Other spec rules this module implements: a truthful, contactable
`User-Agent` (§3.5, never a spoofed browser string); a fixed 3-second delay
between paginated requests to the same host (§3.4); `RoasterUnavailableError`
on any network/parse failure rather than an exception surfacing on the GUI
thread (§3.7 "fail closed" in spirit); and a 15-minute in-memory cache so
reopening the dialog doesn't re-hit a roaster's server needlessly. It does
**not** implement the fuller crawler machinery the spec describes for a
recurring/scheduled crawl (robots.txt parsing, a circuit breaker, a
persisted kill switch, an allowlist file) — those govern a background daemon
making repeated unattended requests; this is a single on-demand fetch
triggered by a human clicking a button, which the spec's use-case gradient
(§1) already places in the lowest-risk, "GO" category. **If this ever grows
into a scheduled background refresh, re-read `specs/legal.md` §3 in full
before building it** — that change moves the feature into different rows of
the risk table.

`gui/whats_new_dialog.py` runs the fetch in a `QThread` (the same
`background.py`-owned-worker pattern as `ai_brew_dialog.py`'s Qwen call),
so a slow or dead network shows the walking-can loader instead of freezing
the window.

#### 3.7.1 "Can see" — the shelf and its "more" dialog

The overview card's right-hand pane, **Can see**, shows **three coffees
picked at random** from everything the roasters currently list in stock:
photo, name, and `roaster · origin · price`, each card opening the product
page in the browser when clicked. `more ›`, top-right of the pane, opens
`CanSeeDialog` — the same listings as one table, filterable by roaster,
origin, stock and name, with the live photo preview.

Three decisions worth keeping:

- **One fetch per launch, five roasters, in parallel.** `MainWindow`
  starts a `_TickerFetchWorker` per roaster at startup and picks the three
  cards only once every worker has answered (`_fill_shelf`). Reshuffling as
  each batch landed would both bias the picks toward whoever replied first
  and re-fetch photos on every batch.
- **The dialog fetches nothing.** It is constructed with the listings the
  window already holds. `whats_new.py`'s cache is per-process, so a fetch
  there would be either a no-op or five fresh requests for a browse — see
  `specs/legal.md` §3.4; the request budget is spent once, by the window.
- **The window keeps out-of-stock coffees**, filtering them out only for the
  shelf, so the dialog's "In stock only" toggle has something to toggle.

**What counts as a coffee here is `looks_like_coffee_bag()`, not
`looks_like_coffee()`.** The older function reads only the seller's own
category and answers True when there is none — right for a per-roaster table
where a stray accessory is one row among hundreds, far too generous for a
shelf of three: several of these shops publish an empty `product_type` for a
whole slice of the catalogue, and cupping spoons, filter papers, herbal
infusions and an "Update Payment Info" placeholder all came through it. The
stricter version adds two tests over the seller's own fields — the name must
not contain a word no roaster prints on a bag (a short whole-word list: tea
and infusion terms, brewing hardware, gear brands), and the listing must
positively look like coffee (`detect_origin()` found a country, or the seller
says café/coffee/espresso somewhere). Measured against all five live
catalogues on 2026-08-03 it keeps 83 of ~250 in-stock listings, and what it
drops is kit. Both halves stay deliberately conservative: it would rather
drop a real coffee whose name says nothing than present a milk pitcher as
one.

**Origin is inferred, not published.** None of these endpoints exposes an
origin field, so `whats_new.detect_origin()` matches `ORIGINS` — producing
countries with their French and English spellings, plus regions and famous
estates that imply a country — against the seller's own name and category,
falling back to the description excerpt. Matching is **whole-word regex, not
substring**: as substrings `inde` sits inside *indépendant* and `java`
inside *javanais*, and a filter that files a Colombian bag under India is
worse than one that files it under nothing. Earliest match wins when several
countries appear; a bag with no country that calls itself a blend answers
`BLEND_LABEL`; anything else answers `""` and is filterable as "Not stated".
It exists to group a browsing list — it is never written into a bean
profile, and must not be treated as a provenance claim.
