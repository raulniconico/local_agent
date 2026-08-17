# coffee_android — screens

> **⚠️ Design proposal, not the built spec.** Most of this document describes
> the app as planned in early August 2026. The screens now exist in code;
> **[design-spec.md](design-spec.md) §8 is the specification of what each one
> actually is**, and §12.3 there lists the specific statements below that the
> code has overtaken. Read this for intent and per-screen reasoning.

Each section: purpose, fields/state, Compose realization, API calls (see
`api.md` for full contracts), and a wireframe. **The wireframes in
`screenshots/` are hand-drawn SVG mockups, not real app screenshots** — they
date from the planning stage, when the app did not yet exist. They show layout
and content intent, not final visual polish.

Real screenshots now exist in two forms: Paparazzi renders of the compiled
Compose (`../v1/app/src/test/snapshots/images/`) and captures from a physical
device (`../../docs/screenshots/`).

11 screens/sheets total, down from the desktop app's 12 dialogs — "Can
Drink" and "What's New" are proposed merged into one catalogue screen (see
README.md resolution #2). **Updated after specialist review: the merged
Can-Drink Catalogue screen (§7) moved to v1.1** — its `coffee_server`
dependency turned out to be real new infrastructure, not a port, and it
carries the app's highest legal-compliance surface. It's kept in this
document (unbuilt-but-specified) rather than deleted, same treatment as
Voice Session (§6). See `README.md`'s "Phasing (revised after specialist
review)" for the authoritative per-screen ship target — the ordering below
reflects the original review structure, not shipping order.

---

## 1. Home

**Wireframe:** `screenshots/sheme_1/01_home.svg`

**Purpose:** landing screen — bean list plus an at-a-glance activity/flavor
overview, ported from `main_window.py`'s `MainWindow`.

**Content:**
- Top app bar: app name, profile-settings gear icon (→ Profile Settings)
- Bean list (`LazyColumn` of cards): name, origin, process, roast date,
  session count — tap → Bean Detail; long-press → delete confirm
- "New Profile" FAB → Bean Detail (new)
- Activity heatmap (`ContributionCalendar` composable) — from session dates
- Flavor radar (app-wide average) — from `BeanDao`/`BrewSessionDao`
  aggregation

**Deferred to v1.1** (per revised phasing): both the desktop app's news
ticker pane *and* the Can-Drink preview strip that the v0 draft had here —
the Catalogue screen itself moved to v1.1 (see §7's note), so Home has
nothing to preview yet. v1's Home omits both entirely rather than shipping
an empty placeholder or a strip pointing at an unbuilt screen; add the strip
back when §7 ships.

**API calls:** `BeanDao.listAll()`, ~~`BrewSessionDao.countByDate()`~~
**[SUPERSEDED — the DAO shipped as `SessionDao.dailyCounts`]**, flavor
average (local only). No `coffee_server` calls on this screen until the
Catalogue strip returns in v1.1. The activity heatmap above **is** built
(`ContributionCalendar`, 21 week columns) — an earlier note in `v1/AUDIT.md`
§6 saying the composable did not exist has itself been overtaken.

**States:** empty (no beans yet → illustration + "Add your first bean" CTA
instead of an empty list), loaded. (The v0 draft's catalogue-preview-loading/
-failed states move to §7 along with the feature itself.)

---

## 2. Bean Detail

**Wireframe:** `screenshots/sheme_1/02_bean_detail.svg`

**Purpose:** create/edit one bean profile — the most complex screen, ported
from `bean_dialog.py`. **Revised after specialist review**: the desktop
app's immediate-persist-on-open pattern (insert a row the instant the dialog
opens, delete it on close if never touched) doesn't survive Android process
death — there's no back-press event to run that cleanup on if the OS kills
the app in the background. A new bean instead lives as **in-memory draft
state** (`ViewModel` + `SavedStateHandle`, so it survives process death) and
is written to Room only on first real field edit or explicit save.

**Fields:** Name (required), Origin, Variety, Altitude, Roaster, Producer,
Process (`ChoiceDropdown`), Roast date (optional date picker, "not set"
state), Note (multiline, auto-grow).

**Sections below the form:**
- **Photos**: `ImageCarousel` (`HorizontalPager`), "Scan Label" button (→
  Photo Picker or Camera Capture → `POST /v1/vision` → Scan Review),
  "Add Photo/PDF" (no scan), rotate/remove per photo
- **Flavor Profile**: `RadarChart`, "Generate from Sessions" (auto-average)
  vs. "Set Manually" (11 sliders in a sheet)
- **Sessions list**: date / dripper / score, "New Session" → Brew Session
  Detail, "Ask AI" → Ask-AI Suggestion sheet, tap row → Brew Session Detail
- Share icon (top bar) → Share Card export

**API calls:** `BeanDao`, `BeanImageDao`, `BrewSessionDao.listForBean`
(local); `POST /v1/vision` (scan flow only) — see the AI-disclosure
requirement below.

**Legal tie-in (`specs/legal-android.md` §3.1 rule 4):** first tap of "Scan
Label" ever, in the app's lifetime, shows the AI-disclosure/consent screen
(§11 below) before the Photo Picker/Camera opens — not on every scan, not
gating manual entry at all.

**States:** loading (existing bean), saving (debounced autosave + lifecycle
flush on `ON_STOP`/back-nav, `Snackbar` confirm rather than a bespoke flash
bar — see README resolutions #4/#10), scan-in-progress (spinner over the
Photos section, matching `WalkingCanLoader`'s branded busy indicator),
scan-failed (inline error, form stays editable manually — scan is an
assist, never a blocker; distinguish "you're offline"/"server unreachable"
from "photo unreadable," see `api.md`'s error-handling conventions).

---

## 3. Scan Review

**Wireframe:** `screenshots/sheme_1/03_scan_review.svg`

**Purpose:** review/edit AI-guessed fields before they overwrite the Bean
Detail form — ported from `bean_dialog.py`'s `_ScanReviewDialog`. Modal
bottom sheet over Bean Detail, not a separate screen (matches its
lightweight, transient role in the desktop app).

**Content:** editable copies of every guessed field (name + all detail
fields, pre-filled from `POST /v1/vision`'s `fields` response), "Apply"
(writes into Bean Detail's form state + attaches the scanned photo via
`BeanImageDao.insert`) / "Discard" (closes sheet, photo not attached).

**API calls:** none directly — consumes the `POST /v1/vision` result already
fetched by Bean Detail.

**States (added after UI review):** a blurry photo, a non-label photo, or a
partial OCR read can come back with most/all `fields` empty or null — don't
render a silently-empty form. Show a one-line inline note ("Couldn't read
much from this photo — fields left blank, edit by hand") whenever `fields`
comes back mostly empty, so the user understands why nothing pre-filled
rather than assuming the feature is broken.

---

## 4. Brew Session Detail (+ Stage Editor sheet)

**Wireframe:** `screenshots/sheme_1/04_brew_session.svg`

**Purpose:** create/edit one brewing session — ported from `brew_dialog.py`.
Same in-memory-draft pattern as Bean Detail (§2's revision applies here
identically — see that section); a new session pre-fills Brew Details by
copying the bean's most recent session (recipe reuse), matching the desktop
app exactly.

**Fields (Brew Details):** Date (required, max = today), Dripper, Filter
Paper, Grinder (`ChoiceDropdown`s), Grind size, Water PPM, Humidity (text),
Dose (numeric).

**Sessions list — delete (added after UI review, was missing entirely from
the v0 draft):** swipe-to-delete or a destructive row action on Bean
Detail's sessions list, consistent with Home's long-press-to-delete pattern
for beans.

**Stages list:** stage # / temp / water / time / circling, plus a delete
action per row (also missing from v0) — "Add Stage" / tap row to edit →
**Stage Editor bottom sheet** (temperature slider+numeric -10..110°C, water
numeric 0-1000g, time field, circling free text) — proposed as a sheet
rather than its own screen (README.md resolution #9) since it's a small,
focused edit over an already-open session. **Revised after UI review**: use
`rememberModalBottomSheetState(skipPartiallyExpanded = true)` so the sheet
opens near-full-height rather than Compose's default partial-expand — four
inputs plus IME behavior is a known failure mode at partial height. Render
the time field as a compact tappable row ("Time: 1:45 — tap to edit") that
launches the standard `TimePickerDialog` as its own overlay, rather than
embedding a wheel/dial picker inline inside the sheet.

**Evaluation section:** Score (0-5 step 0.5, "not set"), Extraction
(`ExtractionBar`, -1..1, 3 zones), Note, 11 flavor sliders + live radar
preview.

**API calls:** `BrewSessionDao`, `BrewStageDao` (all local — this screen has
no AI/network integration of its own, matching the desktop app).

**States:** same debounced-autosave-plus-lifecycle-flush/`Snackbar`-confirm
pattern as Bean Detail (§2).

---

## 5. Ask-AI Suggestion

**Wireframe:** `screenshots/sheme_1/05_ask_ai.svg`

**Purpose:** text-based recipe suggestion — ported from `ai_brew_dialog.py`.
Modal sheet launched from Bean Detail's session list.

**Content:** Dripper picker, "Get Suggestion" button → `POST /v1/ask` →
read-only rendered result (summary, dose, grind, numbered stages),
"Create Session" (enabled once a result exists — writes a new
`BrewSessionEntity` + `BrewStageEntity` rows and navigates to Brew Session
Detail) / "Cancel".

**API calls:** `POST /v1/ask` (existing endpoint, no `coffee_server` changes
needed — see `api.md` §2).

**States (added after engineering review — the v0 draft only specified the
happy path):** loading (disable "Get Suggestion," inline spinner in place of
the result panel), failed (inline error text + "Try Again," result panel
stays empty, sheet stays open — apply the same offline/timeout distinction
as `api.md`'s error-handling conventions rather than a generic failure
message).

**Legal tie-in:** covered by the same one-time AI-disclosure screen as
scanning (§11) — both are "photo/text leaves the device for AI processing"
cases under `specs/legal-android.md` §2.1's prominent-disclosure rule, one
disclosure covers both entry points.

---

## 6. Voice Session (v1.1 — deferred, included for completeness)

**Wireframe:** none yet — deliberately not designed in detail this pass
(README.md phasing). Ported from `voice_brew_dialog.py` once
`coffee_server`'s audio endpoint (`api.md` §3.4) exists. Will need its own
microphone-specific disclosure step, not just a reuse of §11 as written
(microphone access is a materially different sensitive-permission case from
camera/photo under `specs/legal-android.md` §2.1 — revisit that section when
this ships, don't assume the existing disclosure copy covers it).

---

## 7. Can-Drink Catalogue — **built, ships as a placeholder in v1; full screen is v2**

**2026-08-15, same day, revised again**: the full screen (below) is built and
correct, but the product decision is to *not* present a live-looking
catalogue UI to real users while the data behind it is still real-world-gated
on unsent outreach emails. `ui/Axis.kt`'s `-1` page renders
`CanDrinkComingSoon` (`ui/screens/CanDrinkScreen.kt`) instead: a static
"Can Drink is brewing" screen with no network call at all. The full
`CanDrinkScreen` composable stays in the tree, fully wired to
`CatalogueGateway`/Room/Coil, and swapping it back in for v2 is a one-line
change in `Axis.kt` once `specs/legal.md`'s outreach/allowlist process and
`legal-accounts.md` rule 72 are actually satisfied — see the rest of this
section for the full spec, which is unchanged and still current for v2.

**Wireframe:** `screenshots/sheme_1/07_catalogue.svg` (pre-scheme-E sketch);
`screenshots/scheme-e/-1_can_drink.svg` and `-1w_can_drink_intro.svg` are the
current deck pages (`scheme_e.py`'s `can_drink()`/`can_drink_intro()`).

**Moved back into v1 on 2026-08-15**, reversing the v1.1 deferral below (kept
for the record): the `coffee_server` half app-dev flagged as new
infrastructure — the scheduler, the TTL cache, `crawler.py`'s
allowlist/robots/rate-limit apparatus — was since built anyway (see
`specs/coffee-server.md`, `coffee_server/scheduler.py`), so the dependency
that justified the deferral no longer exists as a blocker to *writing* this
screen. **What still blocks it from serving real data in production is
unchanged and is not a code gap**: `crawler.py`'s `CRAWLER_ENABLED` defaults
off and `allowlist.json` ships empty until the real outreach-and-14-day-wait
(`specs/legal.md` rules 2-3) and the `legal-accounts.md` rule 72 re-verdict
both happen for real, in the world, not in code. That's also, separately,
why the *product* decision above is to keep the built screen unwired in v1
rather than let it render its empty/503 state to real users — a "coming
soon" placeholder reads as intentional; a catalogue screen that's
permanently empty reads as broken.
<details><summary>Original v1.1 deferral note (2026-08-14, superseded)</summary>

app-dev review found this screen's `coffee_server` dependency is real new
infrastructure (scheduler, TTL cache, the full kill-switch/circuit-breaker
apparatus `specs/legal.md` mandates) rather than a port — comparable in
weight to the audio endpoint the v0 draft already deferred — and it carries
the single largest legal-compliance surface in the app
(`specs/legal-android.md` §4's dedicated addendum).
</details>

**Purpose:** browse roaster listings — merges `can_see_dialog.py`'s
filterable full catalogue and `whats_new_dialog.py`'s per-roaster browse
into one screen: a Roaster filter chip row covers the "browse one roaster"
use case `whats_new_dialog.py` existed for, without a second screen. A sort
control (Newest / Name / Price, defaulting to Newest) covers "What's New"'s
actual value that a plain merge would have dropped, and a "New" badge marks
recently-added listings, per the review flag this section used to carry.

**Filters:** Roaster (dropdown chip), Origin (dropdown chip, includes "Not
stated"), search text field, Sort (Newest / Name / Price) — all applied
**client-side** over a Room-cached copy of the full catalogue response (see
API note below), not sent as query params.

**Dropped from the original spec, on real-data grounds, not a scope cut**:
the "In stock only" toggle and in-stock/sold-out badge. `schemas.py`'s
`CatalogueItem` carries no stock field and `crawler.py`'s Shopify/WooCommerce
parsers extract none — the wireframe's `stock` values were illustrative
sample data, never a wire contract. Add both back together if the crawler
ever parses `variants[].available`; drawing an "In stock" pill against data
that was never fetched would be showing the user a fact nobody checked.

**Added beyond the original spec**: an explicit "via {roaster}" attribution
line on every card (not just the roaster name as a data field) and an info
affordance opening the D.111-16 ranking rubric `crawler.py` already serves
(`RUBRIC`, ~line 354) — `specs/legal-accounts.md` rule 76 requires that
rubric "directly accessible from" this screen, and a Google-Play-policy
review (2026-08-15) flagged both as the two UI gaps against Play's IP and
impersonation policies once outreach/allowlist compliance is otherwise met.

**Content:** listing grid (name, "via {roaster}" attribution, origin, price,
weight, hotlinked photo via Coil — disk cache disabled app-wide, per
`specs/legal-android.md` §4 rule 26), tap → open `product_url` in external
browser (`Intent.ACTION_VIEW`, matching desktop's `QDesktopServices`).

**API calls:** `GET /v1/catalogue` (`coffee_server/main.py`, gated behind the
read key not the AI key — `net/ServerApi.kt`, `net/CatalogueGateway.kt`). The
endpoint returns the full unfiltered listing set; the client caches it in
Room (`data/CatalogueItemEntity.kt` via `CoffeeDatabase` v2) and filters
locally — this also gives a usable (if stale) offline catalogue view for
free, which query-param filtering wouldn't.

**States:** loading (spinner while the cache is empty), empty-after-filter
("No beans match that"), empty-cache load-failed (retry button), and a
**stale-but-usable fallback**: a refresh failure with something already
cached shows the last saved list plus a small banner, never the full error
state — implemented in `ui/screens/CanDrinkScreen.kt`.

**Not yet built**: the `-1w_can_drink_intro` first-run page (the `can_boy`
illustration + "Start" CTA). The screen currently opens straight to the list
on every visit, cache-first, rather than gating first-run behind an intro
card — worth adding back if a real first-run distinction proves useful once
the catalogue has real data behind it.

---

## 8. Camera Capture

> **Superseded, 2026-08-14 — not built, and deliberately not.** Capture now
> hands off to the device's own camera app (`ACTION_IMAGE_CAPTURE`) and
> selection to the system Photo Picker, so this app declares no camera
> permission and there is no in-app viewfinder to design. **8b (permission
> denied) has no reachable state at all** and is dropped rather than deferred.
> The trade — losing the mascot viewfinder — and the manifest trap that makes
> the permission removal mandatory are recorded in `README.md` under
> "Decision, 2026-08-14". Revive this section only alongside a real CameraX
> screen, and re-read `specs/legal-android.md` §3.1 first: that change reopens
> rules 3 and 4 together.

**Wireframe:** `screenshots/sheme_1/08_camera.svg`

**Purpose:** photograph a bean label — ported from `camera_dialog.py`.
CameraX `PreviewView` full-screen, capture button, matches the desktop
app's live-preview-then-grab-frame flow but using CameraX's proper still-
capture API instead of grabbing a video frame (the desktop app's
`QVideoWidget.grab()` approach was itself a workaround for Qt Multimedia's
limitations, not a pattern worth porting).

**Content:** live preview, capture shutter button, cancel (back). The
alignment-guide overlay drawn over the preview (see wireframe) must account
for the `PreviewView`'s displayed aspect ratio possibly differing from the
captured image's actual resolution/aspect ratio — a naive fixed overlay box
can misrepresent what's actually captured.

**Permission (stated explicitly per legal-android.md rule 3, was implicit in
v0):** `CAMERA` is requested on entry to this screen / first shutter tap,
never at app launch.

**States (added after UI review):** permission-denied — rationale text +
"Open Settings" button, with the Photo Picker path (no permission required)
offered as the actual escape hatch, matching how "Add Photo/PDF" already
works in Bean Detail without needing `CAMERA` at all.

**API calls:** none — returns a local file path to the caller (Bean Detail),
which downscales the copy sent to `POST /v1/vision` per `api.md` §3.1's
payload-size note; the persisted copy is EXIF-stripped on write regardless
of whether scanning is used.

---

## 9. Profile Settings

**Wireframe:** `screenshots/sheme_1/09_profile.svg`

**Purpose:** single app-wide user profile — ported from `profile_dialog.py`.

**Fields:** ~~avatar (circular, tap to change via Photo Picker or remove),
Name, Email.~~ **[SUPERSEDED — all three are gone, and must not come back.]**
`legal-accounts.md` rule 60 removed email from the architecture entirely: the
app requests **no scopes at all**, never reads the ID token's `email` claim, and
the server has no column one could go into. The shipped screen shows the brand
mark, the signed-in/signed-out state line, and the account controls — no
avatar, no name, no email.

**Content:** also the natural home for the privacy-policy link required by
`specs/legal-android.md` §3.4 rule 14 ("linked... from an in-app Settings
screen") — add a "Privacy Policy" row here even though the desktop app's
`ProfileSettingsDialog` has no equivalent, since Android needs one and this
is the obvious existing screen for it. **Added after app-dev review**:
expand this into a labeled "About & Legal" subsection (Privacy Policy, a
re-openable copy of the AI-disclosure text from §11 for users who dismissed
it with "Not now" and want to read it again without re-triggering an AI
feature, app version number, ~~OSS license attribution~~) rather than a single
bare row — a real submission needs all of these somewhere and Profile is the
only screen with an obvious claim to them.

**[SUPERSEDED in one part]:** the OSS-licence row was removed under
`legal-accounts.md` rule 103. The shipped "About & legal" section is Language,
Sync with desktop, Privacy Policy, and How we use AI, plus the account
controls. Fredoka's OFL licence ships in `assets/licenses/` rather than being
surfaced as a settings row.

**Desktop sync** (added 16 Aug 2026): a "Sync with desktop" row above the
legal ones — a setting, not a disclosure — opening a dialog with the two
directions a bundle can travel. **"Send to desktop"** works: `SyncBundle.export`
writes a zip of every bean, session, stage and image into `cacheDir/share/`
and hands it to the share sheet through the FileProvider grant.
**"Receive from desktop"** opens a bundle through
`ActivityResultContracts.OpenDocument` and merges it. It **never overwrites**:
beans whose names are new are inserted, beans already here are left untouched
and counted, and the snackbar reports both numbers. The desktop can afford a
real per-bean "phone or desktop?" adjudication because an agent drives it and
can ask; this screen has no such conversation available, and the alternative
to asking is guessing with someone's whole log — so it declines instead. The
subtitle promises exactly that guarantee ("add what's new"), which is what
makes an import safe to tap.

The row's subtitle names the *shape* of the sync ("as a file you carry
yourself") at the point of tapping. That is load-bearing, not copywriting:
the Privacy Policy two rows down promises we hold no copy, and a row offering
bare "sync" would read as retracting it. A file moving between two machines
one person owns keeps the promise intact — routing it through
`coffee_server` would not, and would re-open `specs/legal-accounts.md` §3.8
and the Play Data safety form first.

The desktop half is `coffee_agent/sync_tools.py` (`inspect_coffee_bundle` /
`apply_coffee_bundle`), which owns the by-name conflict model. The two write
one format and must change together — `SyncBundle.VERSION` and
`sync_tools.BUNDLE_VERSION` must stay equal.

**API calls:** none — local `DataStore`/prefs only. Sync is a file the user
carries; no endpoint is involved in either direction.

---

## 10. Share Card export

> **BUILT 2026-08-16** — `share/ShareCard.kt` (the renderer) and
> `share/ShareSheet.kt` (preview + `ACTION_SEND`), reached from the share disc
> on Bean Detail and Brew Session Detail. **The export follows the desktop
> PNG, not the wireframe below.** The two disagreed — this section's own
> "same visual design as the desktop PNG" against `wireframes.share_card()`'s
> 1080x1350 scrim-over-photo card — and the product owner settled it on the
> desktop's actual implemented design. So: 1080 wide, 1920 floor, green ground,
> white text, photo then name then radar-with-caption then the detail rows;
> a brew adds a divider, a dated heading, its brew details, stages, score and
> note. The wireframe's segmented "This bean / This brew" switch is not built
> either — each page shares its own subject, which is what the share disc being
> *on* that page already means — and neither is "Save to photos", since the
> system sheet lists Photos and Files itself. See AUDIT.md §5.10 item 1 for the
> full record, including the two knowing divergences (no profile header, and
> the desktop's decorative green kept behind white text).

**Wireframe:** `screenshots/sheme_1/10_share_card.svg`

**Purpose:** render and export a shareable image — ported from
`share_card.py`'s `render_share_card`/`render_session_share_card` +
`_ShareTipsDialog`. Triggered from the share icon on Bean Detail or Brew
Session Detail.

**Content:** rendered preview, same visual design as the desktop PNG (green
background, white text, `RadarChart` reused), "Save/Share" → Android share
sheet (`Intent.ACTION_SEND` via `FileProvider` — required, a bare `file://`
URI across app boundaries throws `FileUriExposedException` on modern
Android) instead of desktop's save-to-disk-then-show-path flow.

**Build-effort flag (added after app-dev review — this was under-flagged in
the v0 draft, which described it almost as "just a Canvas, no API calls"):**
this is the highest-risk build item in the whole plan. Compose has no
one-line equivalent to Qt's fixed-size `QPixmap`+`QPainter`; producing a
precise, fixed-resolution, off-screen bitmap for export needs the
`GraphicsLayer`/`rememberGraphicsLayer()` API (Compose UI 1.7+ — not the
older `AndroidView`+`PixelCopy` route), plus the same manual y-cursor
text-layout arithmetic the Python `share_card.py` does today (unknown
content height → render to a scratch canvas → crop), ported to
`TextMeasurer`. Budget accordingly; don't let this screen's apparent
simplicity in the wireframe set the estimate.

**API calls:** none — pure local rendering from already-loaded bean/session
data.

**Legal tie-in:** keep app branding visually subordinate to the user's own
data on this card, never reproduce a roaster's logo graphic (name-as-text
only) — `specs/legal-android.md` §2.2/§3.3 rules 8-9, directly relevant here
since this is the one screen whose whole purpose is producing an image that
leaves the app.

---

## 11. AI disclosure & consent

**Wireframe:** `screenshots/sheme_1/11_ai_disclosure.svg` (shows the photo-triggered
variant of the copy — see the genericization fix below; the text-only
variant swaps the first paragraph, layout is identical).

**Purpose:** the in-app disclosure `specs/legal-android.md` §2.1/§3.1 rule 4
requires before first use of any AI feature — not present in the desktop app
at all (desktop Play policy doesn't apply there), so this has no direct
ancestor dialog to port from; designed fresh against the legal spec's
requirements.

**Revised after specialist review — all three reviewers independently found
the same three problems with the v0 draft, in order of severity:**

1. **Cadence bug (critical):** the v0 draft said "shown once, ever... not
   shown again unless app data is cleared," which directly contradicts
   `specs/legal-android.md` §2.1's actual text: *"show a one-time **(and
   periodically re-shown)**"*. Fixed: re-show periodically — every 90 days,
   or every Nth AI-feature attempt, whichever proves simpler to implement —
   until the user has explicitly accepted, not merely seen it.
2. **Shown vs. accepted were conflated.** The v0 draft's single flag meant a
   user who tapped "Not now" once could never be re-prompted, permanently
   locking them out of AI features with no path back short of clearing app
   data. Fixed: track `shown` and `accepted` as separate `DataStore` flags.
   "Not now" — and system back / tap-outside, treated identically, not as an
   unhandled edge case — records `shown=true, accepted=false` and returns to
   manual entry; the modal re-appears on the *next* AI-feature attempt
   regardless of prior `shown` state, until `accepted=true`.
3. **Copy is photo-specific but gates a text-only entry point too.** The
   wireframe's copy ("Your photo will be sent...") is accurate for Scan
   Label but false for Ask-AI Suggestion (§5), which sends dripper choice +
   bean text fields, no photo. Fixed: genericize — *"Your photo and/or the
   bean/session details you've entered may be sent to an AI service..."* —
   one shared copy rather than building two variants for v1.

**Content:** plain-language statement (genericized per fix 3 above), what's
sent, explicit affirmative "Continue" action (no auto-dismiss, no
navigate-away-as-consent per the spec's explicit prohibition on both) —
these parts of the v0 draft were already right and are unchanged. Re-openable
from Profile Settings' "About & Legal" section (§9) for a user who wants to
re-read it without re-triggering an AI feature.

**API calls:** none — local `DataStore` flags (`shown`, `accepted`,
`lastShownAt`) gate whether either AI entry point (§2's Scan Label, §5's
Ask-AI) proceeds straight through or shows this screen first.
