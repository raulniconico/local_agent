# coffee_android — design plan

Status: **build started** — the Gradle project in `../v1/` is real code now,
partway through the closed-testing milestone (see "What exists in code" below
for the line between built and planned). This document went through one full
round of review by three specialist agents (UI design, engineering, app
development) — their findings are folded in throughout, most visibly in
"Specialist review — resolutions" below. See `specs/legal-android.md` for the
policy constraints this plan is written to satisfy; treat that document as
binding, this one as the proposal built on top of it.

> **⚠️ This document is the design *proposal*. It is no longer the
> specification of the build.**
>
> The app moved a long way between 2026-08-14 and 2026-08-17, and several
> decisions recorded below were overtaken by the code. **[design-spec.md](design-spec.md)
> is the standardised specification of what v1 actually is** — written by
> reading every source file and checking it against a running install on a
> physical device. Read that first; read this one for the *reasoning* and the
> review history that produced it.
>
> Statements below that the code has since overtaken are marked **[SUPERSEDED]**
> inline, and design-spec.md §12.3 lists every one of them in a table.

- [design-spec.md](design-spec.md) — **the current, binding v1 design
  specification**: colour, type, shape, components, navigation, every screen,
  data model, API contract, localisation, accessibility, verification
- [README.md](README.md) — this file: architecture, phasing, open decisions,
  and the specialist-review history
- [api.md](api.md) — every API surface: local Room schema/DAOs, `coffee_server`
  endpoints (existing + proposed new ones), and which screen calls what
- [screens.md](screens.md) — one section per screen: purpose, fields, states,
  Compose realization, API calls, wireframe
- [screenshots/](screenshots/) — wireframe mockups (SVG), one per screen —
  **wireframes, not real screenshots**; see note at the top of screens.md.
  Real device captures live in [`../../docs/screenshots/`](../../docs/screenshots)

---

## What exists in code

Built and wired into the nav graph (`../v1/app/src/main/java/app/coffeecan/`).
The whole Gradle project moved under `../v1/` on 2026-08-14 so that a shipped
version is a directory rather than a git tag; `../v1/README.md` is its own
entry point and `../v1/AUDIT.md` is the spec/deck conformance review of exactly
this code.

| Deck page | Screen | State |
| --- | --- | --- |
| -1 | **Coffee news** — headline, source, date, link; prefetched during the splash, cached in Room, hourly server refresh | built 2026-08-15 (`ui/screens/NewsScreen.kt`). Shows only the four fields `legal-accounts.md` rule 74 permits — no snippet, no AI summary, and `NewsItemEntity` has nowhere to store one. Real headlines are still gated on `CRAWLER_ENABLED` + the allowlist + rule 72, so the shipped state is the "no feed yet" 503 branch. |
| -1 (v2) | Can Drink — roaster catalogue, search/Roaster/Origin/Sort filters, rubric disclosure | **built, and now unwired** — news took the `-1` slot on 2026-08-15, so `CanDrinkScreen.kt` and its `CanDrinkComingSoon` placeholder are both kept whole but unreferenced, for v2. Wiring it back is still a one-line swap in `Axis.kt`, but it now needs a home: `-2` is the obvious one, and is already the next slot the axis would accept. |
| 00 | Home — bean list, "My flavor" radar | built; contribution calendar and the catalogue strip are not |
| 0.1 / 0.2 / 0.2b | Bean Detail — full manual CRUD, process dropdown, roast-date picker, flavor radar + manual-override sheet, sessions list, delete-with-cascade confirm, **label scan**, photo hero + Images strip | built 2026-08-15; the photo hero and Images strip (`coil-compose`, already pulled in for -1 Can Drink) landed on the `0.2`/`0.2b` (saved-bean) branch — see AUDIT.md §5.6c |
| 3 (screens.md) | Scan Review — editable guessed fields, "was:" hints, empty-read state, report control | built |
| 10 (screens.md) | Share Card export — render a shareable PNG, preview it, hand it to the system share sheet | built 2026-08-16 (`share/ShareCard.kt`, `share/ShareSheet.kt`); reached from the share disc on `0.2` and on a saved brew. Renders coffee-can desktop's card design, **not** the wireframe's — the two specs disagreed and the desktop's implemented design was chosen; see AUDIT.md §5.10 item 1 |
| 0.11 / 0.11b | Camera capture / permission denied | **superseded, see below** |
| +1 | Sessions — the whole log, newest first | built, rows open the brew |
| +1.1 | "Which bean?" sheet — pick / add / vibe-brew | built; both FABs open it |
| 4 (screens.md) | Brew Session Detail + Stage editor + Ask-AI | built |
| +2, +2.2a, +2.2b | Profile, Privacy, AI disclosure & consent | built, with real Google sign-in, working access/erasure/report controls |
| 0.21b | Ask-AI suggestion sheet | built as a sheet over the brew form |

Data layer: Room entities/DAOs mirroring `db.py` (including the eleven flavor
columns on `sessions`, which is what the "auto" bean radar averages over),
`CoffeeRepository`, `ConsentStore`, `AccountStore`.

Network layer: `net/AiGateway.kt` is the **single chokepoint** — every AI call
checks consent for that specific operation, then connectivity, then mints a
Google ID token, and nothing retries. `account/GoogleAuth.kt` is the only place
an identity token is obtained. The app talks to `coffee_server` and to nothing
else: no provider SDK, no provider hostname, no roaster's host.

Theme: scheme E ported token-for-token from `variants.py` `PURE_GREEN`, with
Fredoka bundled in `res/font/` and the deck's rounded shape set (card 24, field
16, sheet 32) and `viz*` chart colours.

### Decision, 2026-08-14: the system camera, not CameraX

Photos come from the system Photo Picker (existing) and `ACTION_IMAGE_CAPTURE`
(new), so **the app declares no camera permission at all**. That deletes screen
0.11b entirely — there is no permission to deny — and makes `legal-android.md`
rule 3 inapplicable rather than merely satisfied. It also removes the
multi-week CameraX cluster from the path to closed testing.

There is a trap that makes the removal mandatory rather than cosmetic: an app
that *declares* `CAMERA` must also hold it at runtime before
`ACTION_IMAGE_CAPTURE` will launch. Re-adding the permission would break
capture, not enable it.

**What this gives up:** the deck's 0.11 — can-boy holding the camera, the
shutter burst — is a branded moment the system camera app cannot provide. The
scan prompt card keeps the copy and the position; the illustration is missing.
Swapping CameraX back in later touches `PhotoSources.takePhoto` and nothing
else, since ingest and review sit behind the same callback.

EXIF is stripped by **re-encoding** (`media/ImageIngest.kt`), not by clearing
named tags: scrubbing is a list that has to stay correct forever, while a pixel
round-trip carries nothing across by construction. The downscale to 2048px is a
side benefit the vision endpoint wanted anyway. Covered by an instrumented test
(`app/src/androidTest/.../ImageIngestTest.kt`) — written, not yet run.

~~**Not started:** Camera Capture (0.11/0.11b) and Scan Review (§3) … the
welcome/splash page (00w) … news~~

**[SUPERSEDED 2026-08-17.]** All of that shipped. Photo source, scanning, Scan
Review (`ui/components/ScanReviewSheet.kt`), the welcome splash
(`ui/screens/WelcomeScreen.kt`) and News (`ui/screens/NewsScreen.kt`) are built
and wired, and `AiGateway.readLabel` is live behind the consent sheet.

**Genuinely not started:** voice sessions (needs an audio endpoint on
`coffee_server`), Home's catalogue strip, and dark mode. The `-1w` Can-Drink
first-run intro goes with the Can-Drink screen itself, which is complete but
unwired pending `CRAWLER_ENABLED` + the allowlist process — see the table above
and screens.md §7.

**What "built" means here, as of 2026-08-16**: compiled, and rendered. The
checkout has an SDK and a wrapper (`v1/README.md` has the commands), the app
installs and runs on a real phone, and Paparazzi renders every screen listed
above through layoutlib on the JVM. What is still unverified is *behaviour that
needs fingers* — gestures, animation timing, share targets — since there is no
emulator here and on-device checks depend on someone holding the phone. The
server half has been run too: see `specs/coffee-server.md`.

---

## What this is

A native Android port of `coffee-can` (`coffee/`), the existing PySide6
desktop app for logging hand-brew coffee. Same data model, same core
workflows (bean profiles, brew sessions, flavor tracking), rebuilt as a
Kotlin + Jetpack Compose app for Google Play. Full feature parity is the
stated goal (per the "full port" decision made before this stage); §Phasing
below proposes what ships in v1 vs. what's sound to defer, as a
recommendation for the specialist review — not a unilateral cut.

## Two decisions this plan had to resolve before it could be written

Both surfaced only after inventorying the existing app in detail (see task
history) — flagging them up front because they shape almost every screen and
API section below.

### 1. `coffee_server` is text-only today; two features need it extended

`coffee_server`'s only real endpoint, `POST /v1/ask`, accepts a plain-string
`prompt` or `messages` and returns plain-string `content` — no image, no
audio field anywhere in its schema (verified by reading `schemas.py` and
`providers.py` directly). `coffee-can`'s own OCR (`claude_ocr.py`,
`qwen_ocr.py`) and voice transcription (`qwen_brew.py`) call Anthropic/Qwen's
**vision/audio** APIs *directly*, bypassing `coffee_server` entirely — the
desktop app was never built to go through a gateway for these.

Since the tech-stack decision for this project was explicitly "call
`coffee_server`, never embed provider keys client-side," bean-label OCR (an
image-in feature) cannot ship as designed without `coffee_server` growing a
vision-capable endpoint first. This is **a dependency on the sibling
`coffee_server` project**, not something `coffee_android` can work around
alone — see `api.md` §2 for the proposed new endpoint shape, written so
whoever picks up `coffee_server` work has a concrete target. Voice sessions
have the identical problem one level further out (audio, not image) — see
§Phasing.

### 2. The roaster-catalogue and news features cannot run client-side

Also only visible once the actual data flow was inventoried: `coffee-can`'s
"Can drink" shelf, "Can see" catalogue, and news ticker scrape roaster
storefronts and RSS feeds **directly from the GUI process** — fine for one
desktop instance, but `specs/legal-android.md` §4 (added after this was
found) explains why fanning that out across every Android install breaks the
single-crawler premise the whole rate-limiting/legal posture in
`specs/legal.md` was built on. **This plan assumes those features move
behind new `coffee_server` endpoints that do one centralized, scheduled crawl
and serve every client a cached read** — again a `coffee_server`-side
dependency, detailed in `api.md` §3.

Both dependencies are called out explicitly in each affected screen's section
in `screens.md` so they aren't missed during specialist review.

## Architecture

- **UI:** Jetpack Compose, Material3, Navigation Compose for screen-to-screen
  flow. One `Activity`, Compose-only — no XML layouts, no Fragments.
- **Window insets on the swipe axis: the outer Scaffold owns the bottom, the
  pages own the top.** The four axis pages (Home, News, Sessions, Profile)
  each carry their own `Scaffold`, and each must pass
  `contentWindowInsets = AxisPageInsets` (`ui/Axis.kt`) rather than take the
  default. The default is `systemBars`, and the axis `Scaffold` has *already*
  padded the pager by its bottom bar's height — a figure that includes the
  system navigation inset, because `NavigationBar` consumes that inset
  internally. A page that also claims the bottom applies that inset twice and
  leaves a dead band above the bar: measured at 37dp on a device with
  three-button navigation, and roughly half that on gestures.
  **Paparazzi cannot catch this** — every inset is zero there, so the goldens
  render correctly either way and only a real device shows it.
- **State:** ~~MVVM — one `ViewModel` per screen, `StateFlow`-exposed UI
  state~~ **[SUPERSEDED]** — there is no `ViewModel` in the module. State lives
  in `rememberSaveable` plus repository flows collected in the composable, and
  `lifecycle-viewmodel-compose` is an unused dependency. Defensible for screens
  this size, and `rememberSaveable` genuinely does survive process death.
- **Local persistence:** Room, schema mirroring `coffee-can`'s SQLite
  (`db.py`) column-for-column — see `api.md` §1. On-device-only, no cloud
  sync. ~~no accounts~~ **[SUPERSEDED]** — Google sign-in ships, and an
  account exists to meter AI usage; `specs/legal-accounts.md` §3.8 (rules
  58–103) is the binding statement of that architecture and supersedes
  `legal-android.md` §1 here. Still no user content server-side.
- **Network:** Retrofit + OkHttp, one `ApiService` interface against
  `coffee_server`, `X-API-Key` header interceptor. No other network calls
  from the client after §2's centralization fix — see `api.md` §3.
- **Images:** Android Photo Picker (`PickVisualMedia`) for existing photos,
  ~~CameraX~~ **[SUPERSEDED]** the system camera via `ACTION_IMAGE_CAPTURE` for
  capture (see the 2026-08-14 decision below), Coil (sharing the app's single
  `OkHttpClient` instance, so the TLS-only Network Security Config actually
  covers image loads too) for image loading — matches `specs/legal-android.md`
  §3.1 rules 1-2 exactly (no `READ_MEDIA_IMAGES`). EXIF is stripped on ingest
  before the file is ever persisted, never filtered later at upload time
  (resolution #8) — though **[SUPERSEDED]** in method: it is done by
  re-encoding the pixels in `media/ImageIngest.kt`, not via
  `androidx.exifinterface` tag-clearing, because a scrub list has to stay
  correct forever while a pixel round-trip carries nothing across by
  construction.
- **New/orphaned-draft safety:** Bean Detail and Brew Session Detail hold a
  new record as **in-memory draft state** (`ViewModel` + `SavedStateHandle`)
  until first real edit or explicit save, rather than inserting into Room the
  instant the screen opens — process death mid-flow (backgrounding, OS memory
  reclaim) has no back-press event to run desktop-style cleanup on, so an
  insert-on-open pattern would orphan empty rows permanently. Autosave itself
  is a debounced whole-entity `@Update`, flushed early on `ON_STOP`/
  `ON_PAUSE`/back-navigation so the loss window on process death is bounded
  by the lifecycle, not just the debounce timer (resolutions #3-#4).
- **Reusable UI components** (mirroring `widgets.py`): `RadarChart` (Canvas-
  drawn, 11-axis — the highest-effort composable in the app; needs
  `TextMeasurer`-based label layout, not guessed offsets, to avoid clipping
  at small sizes), `ExtractionBar` (Canvas-drawn, -1..1 with 3 zones),
  `ContributionCalendar` (heatmap grid), `ChoiceDropdown` family (dripper/
  grinder/filter/process, editable exposed-dropdown), `ImageCarousel`
  (`HorizontalPager`). Each Canvas-drawn component ships an explicit
  `Modifier.semantics { contentDescription = ... }` textual summary — Compose
  `Canvas` has zero accessibility-tree presence by default (resolution #11).
  Save confirmation uses Material3 `Snackbar`, not a bespoke flash-bar
  composable (resolution #10).
- **Theme:** **[SUPERSEDED in every number — see design-spec.md §2–§4.]** The
  shipped theme is Material3 built from `variants.py`'s `PURE_GREEN` +
  `FREDOKA_STYLE`, not `theme.py`. Resolution #5's substance held — the bright
  green never carries text — but there are **three** greens, not two:
  `Brand` `#34C759` (decorative only), `primary` **`#196D2E`** (not `#1E7A3D`;
  every label, link and button word), and `VizSeries` `#2B9343` (data marks
  only, a full tone band clear of primary so a chart mark is never mistaken for
  a control). Background is `#FFFFFF` (not `#F2F2F7`) and cards are **24dp**
  (not 14dp) — the radii moved with the typeface. `check_design.py` diffs all
  36 colour, 11 type and 5 shape tokens on every run.

Phasing below was reworked materially after specialist review — see
"Phasing (revised after specialist review)" further down; the v0 phasing
draft that originally lived in this spot is superseded by that section.

## Specialist review — resolutions

Three specialists (UI/UX, engineering, app-development) reviewed the v0 draft
independently. Full reports aren't reproduced here; this is the PM synthesis
— what changed, what didn't, and why. Where two or three specialists
converged on the same finding independently, that's noted, since it's the
strongest signal in the whole review.

| # | Finding | Verdict | Change |
|---|---|---|---|
| 1 | **All three specialists independently flagged the same bug**: the AI-disclosure screen (§11) says "shown once, ever," but `specs/legal-android.md` §2.1 explicitly requires "one-time **and periodically re-shown**." The screen's copy is also photo-specific but gates the text-only Ask-AI flow too, and "shown" vs. "accepted" were conflated (declining once would permanently lock a user out with no re-prompt). | **Accepted, all three parts.** | Re-show periodically (every 90 days or every Nth AI attempt, whichever is simpler to implement) until accepted; track `shown`/`accepted` as separate flags — declining shows manual entry and re-prompts on the next AI attempt; genericize the copy to cover both "photo" and "text details" rather than hard-coding photo language. See `screens.md` §11 update. |
| 2 | (App-dev) Can-Drink Catalogue is the one v1 feature whose `coffee_server` dependency isn't "just a port" — it needs a scheduler, TTL cache, and the full kill-switch/circuit-breaker apparatus `specs/legal.md` mandates, comparable in weight to the audio work already deferred. It's also the single most legally-sensitive feature in the app (its own addendum in `specs/legal-android.md` §4) and the least essential to the core logging workflow. | **Accepted at the time; superseded 2026-08-15.** | *Original change (2026-08-14):* move Can-Drink Catalogue to v1.1, alongside News. *Superseded:* the flagged `coffee_server` infrastructure (scheduler, TTL cache, allowlist/robots apparatus) got built anyway (`coffee_server/crawler.py`, `scheduler.py`), so the engineering-weight rationale no longer holds; the screen shipped into v1 on 2026-08-15 (see screens.md §7). The legal-compliance point in this finding is still fully live and un-resolved by the code shipping — real data is still gated on `specs/legal.md`'s outreach/allowlist process and `legal-accounts.md` rule 72, tracked separately from this UI-readiness finding. |
| 3 | (UI + Engineering, independently) Porting the desktop's "insert a row the instant the screen opens, delete it on back-nav if untouched" pattern is unsafe on Android: a Compose screen can be torn down by process death (backgrounding, OS memory reclaim) with no back-press event ever firing, orphaning empty rows permanently. | **Accepted.** | Bean Detail and Brew Session Detail switch to **in-memory draft state** (`ViewModel` + `SavedStateHandle`), writing to Room only on first real edit or explicit save — no DB row for a screen that was opened and abandoned. |
| 4 | (Engineering) Debounced whole-entity autosave (replacing the desktop's per-field immediate commit) has a real loss window: "everything since the last debounce fire," not "the field being typed." | **Accepted.** | Pair the UI debounce timer with a lifecycle-triggered flush — save on `ON_STOP`/`ON_PAUSE` and on back-navigation, not just the timer. |
| 5 | (UI) `#34C759` (the ported desktop accent) fails WCAG AA contrast (~2.2:1) as text or as a fill behind white text — verified by computation, and the plan already uses a passing darker green (`#1E7A3D`) in one place (Share Card) but not consistently. | **Accepted.** | Two tokens: `accent` (`#34C759`, decorative-only — chart lines, slider tracks, heatmap cells) and `accentText`/`onAccent` (`#1E7A3D`, every button label/link/text-on-green). Route both through Material3's `primary`/`onPrimary` pair rather than ad hoc per-screen color picks. |
| 6 | (Engineering) Gating the read-only `/v1/catalogue`/`/v1/news` behind the same key as metered AI calls ties an unrelated feature's availability to the AI endpoints' abuse/rotation blast radius. | **Accepted.** | Split into two keys: a low-stakes read key (catalogue/news) and a separate key for the metered AI endpoints (`/v1/ask`, `/v1/vision`), so rotating one doesn't break the other. |
| 7 | (Engineering) A single shared `X-API-Key` compiled into every APK, gating *metered, billed* AI calls with no rate limit or spend cap, is a real cost-exposure risk once decompiled — "it's my own server" answers the wrong question (confidentiality, not abuse). | **Accepted, minimum viable fix for v1.** | Add server-side rate limiting per key and billing spend alerts on the Anthropic/Qwen dashboards before submission; document a key-rotation runbook. Stronger fixes (Play Integrity attestation, per-install tokens) are v1.1+ options, not v1 blockers. |
| 8 | (Engineering + App-dev) "Strip EXIF location" was asserted with no library, call site, or pipeline stage named — for the spec's own "highest-priority action item," that's a gap. | **Accepted.** | Name `androidx.exifinterface` explicitly; strip immediately on ingest (Photo Picker result *and* CameraX capture), before the file is ever copied into `BeanImageEntity.filePath` — never a filter applied only at upload time. Add an instrumented regression test (ingest a photo with known GPS tags, assert they're gone). |
| 9 | (UI) Four form fields (temperature slider+numeric, water numeric, time picker, circling text) in a default partially-expanded `ModalBottomSheet`, combined with IME behavior, is a known Compose failure mode. | **Accepted.** | Force `skipPartiallyExpanded = true` (near-full-height sheet); render time as a compact tappable row that launches the standard `TimePickerDialog` as its own overlay, rather than embedding a wheel/dial picker inline. |
| 10 | (UI) The custom "Saved ✓" flash bar re-implements what `Snackbar` already does (IME/nav-bar-inset avoidance, motion, dismissal timing) for no visual benefit. | **Accepted.** | Use `SnackbarHost`/`Snackbar` (with the corrected `accentText` color from #5) instead of a bespoke composable. |
| 11 | (UI) `RadarChart`, `ExtractionBar`, `ContributionCalendar` are Canvas-drawn — Compose `Canvas` produces zero accessibility-tree nodes by default, so three of the highest-traffic screens would be silent to TalkBack. | **Accepted.** | Each component ships an explicit `Modifier.semantics { contentDescription = ... }` with a generated textual summary (e.g. ExtractionBar → "Extraction: well extracted, 62%") as part of the component's own spec, not left to later polish. |
| 12 | (App-dev) Share Card was described almost dismissively ("rendered locally, Compose Canvas, no API calls") but is actually the highest-risk build item in the whole plan — Compose has no one-line equivalent to Qt's fixed-size `QPixmap`+`QPainter`, needs the `GraphicsLayer`/`rememberGraphicsLayer()` API (not the older `AndroidView`+`PixelCopy` route), and needs the same manual y-cursor text-layout arithmetic the Python version has, ported to `TextMeasurer`. | **Accepted as a risk flag**, no scope change — this is exactly the kind of thing specialist review exists to surface before someone underestimates it. `screens.md` §10 updated to name `GraphicsLayer` explicitly and flag build-effort accordingly. |
| 13 | (App-dev) `GET /v1/catalogue`'s server-side query-param filtering buys little at "a handful of storefronts" scale, costs a network round-trip per filter change, and forecloses offline browsing that an unfiltered + client-cached design would give for free. | **Accepted**, applies once catalogue work resumes in v1.1. | Endpoint returns the full unfiltered listing set (+ `ETag`/`If-Modified-Since`); Android caches it in Room and filters locally. |
| 14 | (App-dev) The closed-testing gate (12 testers, 14 continuous days, `specs/legal-android.md` rule 19) only starts once there's a build worth giving testers — bundling essentially the whole app into one "v1" milestone means the 14-day clock can't start until nearly everything is done. | **Accepted.** | Added an explicit **closed-testing-ready milestone** distinct from "v1 feature-complete" — see phasing below. Tester recruitment is a logistics task with no owner yet; flagged, not resolved, by this plan. |
| 15 | (Engineering) No stated behavior for AI calls when offline/unreachable; no connect/read timeouts named; no guarantee stated that core CRUD works fully offline. | **Accepted.** | Detect connectivity before firing AI requests (distinct "you're offline" state, not a timeout wait); explicit OkHttp timeouts; no silent background retry (a queued retry would silently re-send a photo after the user thought they'd cancelled — a real consent problem, not just a UX one); explicit written guarantee that bean/session CRUD is fully offline-capable. |
| 16 | (UI) No delete affordance specified for sessions or stages anywhere in the plan, despite Home documenting bean deletion. | **Accepted — plain gap, fixed.** | Added swipe/destructive-action delete to Brew Session Detail's session list and to each stage row. |
| 17 | (Engineering) No Room migration strategy named, despite the desktop schema's real history of additive and one genuinely hard migration (splitting a retired flavor axis). | **Accepted.** | Named `Migration` objects tested with `MigrationTestHelper` from the first schema change onward; `fallbackToDestructiveMigration()` explicitly banned in `api.md`. |
| 18 | (App-dev) Missing engineering surface a real submission needs: adaptive icon, splash screen, a stated ProGuard/R8 decision, a stated crash-reporting decision, `FileProvider` (required for Share Card's `ACTION_SEND` and CameraX's capture handoff — not optional polish), OSS license attribution, an About/Legal home beyond a bare Profile row. | **Accepted.** | All added to scope explicitly (see Phasing) rather than left implicit: ship unminified for v1 (defer R8 rule-writing), explicitly no crash reporter for v1 (revisit v1.1 — adding one later needs its own Data Safety disclosure update), `FileProvider` configured from the start since Share Card literally cannot function without it. |
| 19 | (UI) Bottom navigation bar vs. push-only navigation for the three top-level surfaces (Home/Catalogue/Profile) — raised as a genuine option. | **Not adopted for v1**, revisit if/when Catalogue returns in v1.1 and there are three real top-level destinations again worth flattening the back-stack for. | **Superseded.** This debate had two options and the answer was a third one that neither side raised: `scheme_e.py`'s module docstring had already defined the deck as a **horizontal swipe axis** centred on Home (`-2 … 00 … +2`, with `0.x` meaning off-axis), and every page number in the deck encodes it. #19 resolved bottom-nav-vs-push without noticing, so its "no change" was a decision about the wrong question. The axis is now what the app implements — one `HorizontalPager` over `[-1 News, 00 Home, +1 Sessions, +2 Profile]` with every `0.x` page pushed on top of it (`v1/app/src/main/java/app/coffeecan/ui/Axis.kt`). **[SUPERSEDED again, 2026-08-17: bottom nav is no longer declined.]** A `NavigationBar` ships *over* the pager and drives it — selection follows `pagerState.currentPage`, so swiping moves the bar and tapping animates the pager. It was added because the axis created the defect open item 1 below describes: once Home's profile icon and "Every brew you've logged" row were removed, nothing *visible* pointed to `+1` or `+2`. See design-spec.md §7.1. |
| 20 | (UI) Sort control / "new" badge for the merged catalogue screen, so "browse one roaster's latest" (the old "What's New" use case) isn't lost inside the merge. | **Accepted in principle, deferred with the screen itself to v1.1.** | Noted in the v1.1 catalogue spec so it isn't lost by the time that work resumes. |

## Phasing (revised after specialist review)

**Closed-testing-ready milestone (build this first, start tester recruitment
against it):** Home (bean list + calendar + flavor radar, catalogue strip
omitted), Bean Detail (full CRUD, photo carousel, manual entry — **no scan
yet**), Brew Session Detail + Stage editor, Profile Settings, Share Card
export, app icon/splash/`FileProvider` wired up. Zero `coffee_server`
dependency — this build can start the 12-tester/14-day clock while OCR work
continues in parallel, closing the schedule gap specialist review flagged
(#14).

**v1 (Play submission target):** everything above, plus Bean Detail's label
scan → Scan Review (via the new `POST /v1/vision` endpoint, the **only**
cross-project dependency v1 carries now, down from three), Ask-AI brew
suggestion (existing `/v1/ask`, no `coffee_server` change), Camera Capture,
and the AI disclosure/consent screen. **Recommend simplifying OCR to a
single provider** (server-side Claude vision), dropping the desktop app's
three-way Qwen→Claude→local-Tesseract fallback — unanimous agreement across
all three specialist reviews that bundling Tesseract4Android for a fallback
path a working server call makes mostly redundant isn't worth it for v1.

**v1.1 (deferred, each with a stated reason, not silently dropped):**
- ~~Can-Drink Catalogue~~ — **code moved back into v1 on 2026-08-15, but not
  wired live**; see resolution #2's superseded note and screens.md §7. Its
  `coffee_server` infra (scheduler, cache, circuit-breaker) got built in the
  meantime, so the engineering rationale for the original v1.1 deferral no
  longer applies — but the app's highest legal-compliance surface
  (`specs/legal-android.md` §4) is still real, so the product decision (same
  day) is to ship the `-1` axis page as a static placeholder in v1 and hold
  the full screen for **v2**, once `CRAWLER_ENABLED`/`allowlist.json` are
  real. The full screen is done, tested-by-reading, and one line away from
  going live whenever that process completes.
- **News ticker** — shares the catalogue's backend work, now nearly free
  since that work already landed; still deferred only because no screen spec
  for it exists yet, not for infrastructure reasons.
- **Voice session** — needs `coffee_server` to grow an audio-capable
  endpoint (same shape of gap as vision, one level further out) plus its own
  microphone-specific disclosure design (a materially different
  sensitive-permission case from camera/photo — don't assume screen 11's
  copy covers it without revisiting `specs/legal-android.md` §2.1 first).

This phasing is still a recommendation the engineering owner can push back
on, but it's now internally consistent — every v1 feature either has zero
`coffee_server` dependency or depends on the one endpoint all three
specialists agreed is genuinely small (a straight port of existing
`claude_ocr.py` logic to a new route). Realistic budget, per the app-dev
review: **2-3 months of build time before the closed-testing-ready
milestone's 14-day clock can even start**, given the RadarChart/Share-Card/
CameraX cluster is real, multi-week R&D work for a first Android app, not a
weekend port.

## Remaining open items (not resolved by this review, flagged for later)

1. ~~Bottom navigation bar~~ — **closed 2026-08-17.** The discoverability gap
   this item described (nothing *visible* pointed from Home to `+1` or `+2`;
   the pager's accessibility actions named the destinations for a screen reader
   and drew nothing for anyone else) was fixed by adding a `NavigationBar` that
   drives the pager rather than replacing it. Both the gesture and a visible
   affordance now exist. See design-spec.md §7.1.
2. Sort/new-badge for the catalogue screen — carry into the v1.1 catalogue
   spec when that work resumes (#20).
3. Tester recruitment for the closed-testing gate has no owner yet (#14) —
   a logistics task, not a design one, but blocking.
4. Play Integrity attestation / per-install tokens as a stronger fix for the
   shared-API-key risk (#7) — v1.1+, not a v1 blocker given the minimum-viable
   rate-limit/alerting fix.