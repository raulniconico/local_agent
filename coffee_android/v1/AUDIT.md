# coffee_android v1 — conformance audit

**Date:** 2026-08-14 · **Scope:** every file under `v1/`, read against
`specs/legal-android.md`, `specs/legal-accounts.md` §3.8 (rules 58–103),
`specs/coffee-server.md` + `coffee_server/` as deployed, `plan/README.md`,
`plan/api.md`, `plan/screens.md`, and the scheme E deck (`plan/scheme_e.py`).

**Nothing here was compiled or run.** There is no Android SDK, no Gradle and no
wrapper in this checkout. Every claim below comes from reading the source; the
frames in `screenshots/` are simulations of that source, not captures of a
running app (see `screenshots.py`'s docstring, and §5).

**Headline:** the compliance architecture is the strongest part of the build and
holds up rule by rule. **The design is not scheme E.** The app took scheme E's
*colour tokens* and its typeface and applied them to stock Material 3 components
at stock Material 3 metrics; scheme E is a denser design with its own type
scale, its own field and chip components, its own bar treatment and its own
brand mark, and almost none of that crossed over. `Theme.kt`'s claim to have
ported the deck "token for token" is true of colour and false of everything
else. §5 is the evidence, measured value by value.

The rest: two France-specific blockers written into the spec *after* the screens
were designed and with no home in the code, one silent data-loss bug on the
app's most important screen, and a class of Canvas unit errors only a device
would reveal.

| | Count |
| --- | --- |
| Release blockers (must fix before closed testing) | 4 |
| Defects (wrong behaviour or wrong statement, not blocking) | 7 |
| Scheme E design-system mismatches (measured) | 15 |
| Unbuilt v1 design targets | 7 |
| Stale documents that now contradict the code | 3 |
| Corrections to this audit's own first pass | 3 |

**Second pass, same day.** The first pass sampled six screens and trusted
`Theme.kt`'s comments. This one renders all 23 deck pages, diffs all 33 colour
tokens programmatically, walks every deck helper in `wireframes.py` against its
Compose counterpart, and checks every string the simulator draws against the
Kotlin. That found six more mismatches — and three errors of my own, corrected
in place at §5.3, §5.5 and §7.

---

## 1. The server coupling — correct

`plan/api.md`'s hard rule is that the app talks to `coffee_server` and to
nothing else. It does.

- `net/ServerApi.kt` is the only Retrofit interface, `net/ApiClient.kt` builds
  the only `OkHttpClient`, and `net/AiGateway.kt` is the only caller. No
  provider SDK, no provider hostname, no roaster host appears anywhere in the
  module. `legal-android.md` §4 rule 23 — satisfied structurally, not by
  convention.
- Endpoint parity against `coffee_server/main.py`, verified route by route:

  | Client | Server | Notes |
  | --- | --- | --- |
  | `POST v1/suggest` | ✓ | field shapes match `schemas.py` exactly |
  | `POST v1/vision` | ✓ | base64 + `media_type`, matches |
  | `POST v1/report` | ✓ | `operation` values match the server's `Literal` |
  | `GET v1/account` | ✓ | **one field missing client-side — see D3** |
  | `DELETE v1/account` | ✓ | |
  | `GET v1/catalogue`, `GET v1/news` | ✓ | declared, unused until v1.1 |
  | — | `POST v1/ask` | deliberately absent from the client, and the reason is
    written down: a shipped key on a free-form prompt endpoint publishes a
    general-purpose LLM on the developer's bill |

- The two-key split (resolution #6) is implemented in `ApiKeyInterceptor` by
  path, so a catalogue-key rotation cannot take the AI features down.
- Auth is a Google ID token minted per call, verified server-side only
  (`GoogleAuth.readClaims` parses `exp` and never checks the signature, with a
  comment saying why).
- Resolution #15 is fully honoured: connectivity is checked *before* firing,
  `retryOnConnectionFailure(false)`, explicit 10/60/30s timeouts, and
  `GatewayFailure` is a sealed hierarchy precisely so each case maps to a
  different sentence rather than one generic failure toast.

**One structural consequence worth stating plainly.** `SERVER_BASE_URL` is
`https://api.coffeecan.app/`, the Network Security Config refuses cleartext with
no domain exceptions, and `legal-accounts.md` §2.6 records the deployed gateway
as **plain HTTP on :8000**. So this build cannot reach the current deployment at
all. That is the correct posture — rules 13/27/101 make shipping the alternative
a triple failure — but it means TLS termination in front of `coffee_server` is a
release gate, not a nice-to-have.

---

## 2. Release blockers

### B1 — No age affirmation exists anywhere (rule 82)

`legal-accounts.md` rule 82 is a `[BLOCKER · Both]`: France exercised the
Art. 8(1) derogation downward via art. 45 of loi n° 78-17, so **the minimum-age
affirmation is 15**, and it applies because the AI features run on consent.

The rule's own text says this "contradicts what `+2.1_create_account` currently
draws" (13+). But `+2.1` is not merely wrong — it is **unreachable**. Sign-in is
now a single Google button on `+2_profile_empty`, there is no create-account
screen in `ui/Nav.kt`, and no route to one. So the one surface that ever carried
an affirmation has been deleted, and the affirmation went with it.

Nothing in the code records one: `ConsentStore` persists `accepted`, `shown`,
`grantedAt`, `withdrawnAt` and `acceptedVersion` per operation, and no age flag.

**Where it has to go.** The affirmation belongs on the surface that carries the
consent, which is `AiDisclosureSheet` — an unticked checkbox gating "Send the
photo" / "Send the details", plus an `ageAffirmedAt` key in `ConsentStore`.
Putting it on sign-in instead is defensible but weaker: sign-in is Art. 6(1)(b),
and it is the AI transfer that needs Art. 8 cover. Either way this is a product
decision that has not been made, not a line of code that was forgotten.

> **STATUS, 2026-08-15**: Fixed, on `AiDisclosureSheet` per this section's own
> recommendation. An unticked "I'm 15 or older" `Checkbox` appears whenever
> `ConsentStore.observeAgeAffirmed()` reads false, and gates the accept
> button's `enabled` -- disabled until checked, same shape as any other
> required-field gate in the app. One global `age_affirmed_at` DataStore key,
> not one per `AiOperation`: age is a fact about the person, not about which
> transfer they're authorising, so affirming it once (either operation) covers
> both from then on and the checkbox stops appearing. Defaults fail-closed
> (`initial = false` on the `collectAsState`, not `true`) so a slow first
> DataStore read never briefly enables the button for someone who hasn't
> affirmed. Verified with two new Paparazzi captures,
> `screenshots/0.11a_ai_disclosure_labels.png` (checkbox shown, button
> disabled) and `screenshots/+1.4_ai_disclosure_suggest.png` (already
> affirmed, checkbox gone, button live) -- see `screenshots/REAL_CAPTURES.md`.

### B2 — The app is English-only and cannot be localised without an extraction pass (rule 87)

Rule 87 is explicit about what France-only does *not* relieve, and about what
should be French: "listing, policy, both AI modals, `+2.2a`, `+2.2b`, the
deletion page". None of it is.

`res/values/strings.xml` contains exactly one string, `app_name`. There is no
`values-fr/`. Every other user-facing string in all 33 frames is a hardcoded
Kotlin literal — ~68 bare `Text("…")` call sites plus the interpolated and
pluralised ones inside `when` blocks, the `GatewayFailure` messages, the
`DisclosureCopy` table and the `AiOperation` enum labels.

This is not a translation task yet. It is an extraction task first, and two of
the hardest cases are the ones that matter most legally: the disclosure copy is
built by a `when(operation)` returning a data class, and the plural forms
("1 brew" / "N brews", "its 1 logged brew" / "its N logged brews") are hand-written
`when` branches that need `plurals` resources to survive French agreement rules.

> **STATUS, 2026-08-15**: Fixed. Every reachable string in `res/values/strings.xml`
> now has a name — roughly 230 `<string>` entries plus nine `<plurals>` blocks,
> extracted screen by screen from all thirteen `ui/screens/` and `ui/components/`
> files that render live UI, with call sites switched to `stringResource(...)` /
> `pluralStringResource(...)` (or `context.getString(...)` in the handful of
> coroutine/non-`@Composable` call sites — `AiDisclosureSheet`'s age checkbox,
> `LaunchedEffect` blocks, `ConsentStore`-adjacent catch clauses — where
> `stringResource` cannot be called). `GatewayFailure.displayMessage(context)`
> is the new seam for the two fixed-copy exception cases (`Offline`,
> `SignInRequired`, `ConsentMissing`); the genuinely dynamic ones (`RateLimited`,
> `Server`, `Malformed` — a server or SDK detail string) are deliberately left
> untranslated, since this app has no French text for content it didn't write.
> `res/values-fr/strings.xml` carries a complete, hand-written French
> translation of every one of those entries (verified 1:1 name-for-name against
> the English file with a scripted diff — nothing silently falls back).
>
> **Three deliberate exceptions**, each noted inline in `strings.xml`: the
> eleven flavour-axis names (`BeanEntity.FLAVOR_AXES` / `ShortFlavorAxes`) stay
> English — tasting-note domain vocabulary a mechanical pass shouldn't guess
> at; `Choices.kt`'s dripper/grinder/filter/process lists stay English —
> they're stored data values, not UI chrome, and translating them would
> silently rewrite what's in the database; and `CanDrinkScreen.kt`'s full v2
> composable (everything except the live `CanDrinkComingSoon` placeholder) is
> untouched, matching its own unreachable-in-v1 status elsewhere in this
> document. The app name and the "Can Drink" feature name are carried
> unchanged into French on purpose, the ordinary choice for a branded product
> name.
>
> Verified: `compileDebugKotlin` and `assembleDebug` both green at the
> shipping `compileSdk=36`; all 15 Paparazzi tests still pass; a fresh capture
> of `HomeScreenScreenshotTest#home` produced the byte-identical image hash to
> its pre-extraction capture, confirming the English default renders exactly
> as before. The French file was not render-verified through Paparazzi (that
> would need a `values-fr`-aware locale override in the test environment,
> not attempted here) — it's been checked for resource-name parity and XML
> well-formedness, not for how the translated strings actually lay out on
> screen.

### B3 — Backing out of a brew loses it silently

`ui/screens/BrewSessionScreen.kt:164` is the whole of its back handling:

```kotlin
BackHandler { onBack() }
```

Compare `BeanDetailScreen`, which has `leave()` (confirm-discard for a new
record, flush-then-pop for an existing one) *and* a `DisposableEffect` +
`LifecycleEventObserver` that flushes on `ON_STOP` through `app.appScope`.

Brew Session has neither. It tracks no `dirty` flag, registers no lifecycle
observer, and pops unconditionally. So: type a date, dripper, grinder, grind
size, dose, water, two temperatures, three pour stages, a score, an extraction
and eleven flavour axes — then press back — and every field is gone with no
prompt. Backgrounding the app and having it reclaimed does the same thing.

This contradicts resolution #4 ("save on `ON_STOP`/`ON_PAUSE` **and on
back-navigation**, not just the timer") and `screens.md` §4's "same
debounced-autosave-plus-lifecycle-flush pattern as Bean Detail (§2)". It is the
most user-damaging defect in the build, on the screen the app's docstring calls
"the screen the whole app exists to fill in".

`rememberSaveable` does not save it: it survives process death, but back
navigation pops the `NavBackStackEntry` and takes the saved state with it.

> **STATUS, 2026-08-15**: Fixed. `BrewSessionScreen.kt` now carries the exact
> pattern this section asks for, ported from `BeanDetailScreen`: a
> `baseline`/`baselineStages` pair captured at hydration time (not a blank
> `SessionDraft()` — a freshly recipe-reused new brew already has non-empty
> values on purpose, and diffing against empty would read it as dirty before
> anyone touched it), `dirty = draft != baseline || stages != baselineStages`,
> a `DisposableEffect` + `LifecycleEventObserver` flushing existing sessions
> through `app.appScope` on `ON_STOP`, and a `leave()` used by both
> `BackHandler` and the top bar's back `IconButton`: not dirty pops outright,
> a dirty new brew shows a "Discard this brew?" `AlertDialog`, a dirty
> existing brew flushes then pops. Compiles clean at `compileSdk=36`,
> `BrewSessionScreenScreenshotTest` passes unchanged under Paparazzi, full
> `assembleDebug` stays green.

### B5 — ACCESS_NETWORK_STATE was never declared, and it crashed the app

**Found on a real device, 2026-08-15**, the first time this project was ever
run on hardware from this checkout. `AndroidManifest.xml` declared `INTERNET`
and nothing else, but `net/AiGateway.kt`'s `requireOnline()` calls
`ConnectivityManager.getActiveNetwork()`, which requires
`android.permission.ACCESS_NETWORK_STATE`. Without it that call does not
return null -- it throws:

```
java.lang.SecurityException: ConnectivityService: Neither user 10400 nor
current process has android.permission.ACCESS_NETWORK_STATE.
    at app.coffeecan.net.AiGatewayKt.requireOnline(AiGateway.kt:228)
```

`requireOnline()` is the first line of **every** gateway call, so this broke
the label scan, the brew suggestion and the news feed identically -- every
network feature in the app, on every device, always.

**Why it was invisible for so long.** Nothing in the test suite reaches it:
Paparazzi renders composables, and `TestFakes.kt` overrides the gateway
outright, so no test has ever executed `requireOnline`. It cannot be caught by
reading either, unless you already know that `getActiveNetwork()` throws
rather than degrades.

**Why it crashed rather than failed.** `SecurityException` is not an
`IOException`, an `HttpException` or a `SerializationException`, so
`asGatewayFailure()`'s `else -> this` returned it unmapped. `NewsFeed.refresh`
caught only `GatewayFailure`, and the splash prefetch launches into `appScope`,
which had no `CoroutineExceptionHandler` -- an uncaught throwable there reaches
the thread's default handler and kills the process. That is the "crashed in the
first second" report: the prefetch fires during the reveal, and the process
died before the splash could hand off.

**Fixed** by declaring the permission (normal/install-time: no runtime prompt,
no Data safety row, and it reports whether *this device* has a network, not
anything about the user). Verified on an SM-S908U: the `SecurityException` is
gone, the app survives launch, and the `-1` page now renders the *accurate*
failure -- "You're offline", because `api.coffeecan.app` genuinely does not
resolve yet (B4) -- instead of the generic catch-all.

**Three hardening changes stay**, because each was a real defect the crash only
exposed: `NewsFeed.refresh` catches `Throwable` (rethrowing
`CancellationException`) and now **logs** it, `appScope` has a
`CoroutineExceptionHandler`, and the `-1` page keys its illustration off "did
this fail" rather than off two named failure kinds. Without the logging the
root cause could not be found at all: the first device run showed only the
generic "couldn't load" copy with no trace behind it.

### B4 — The build cannot sign in or reach the gateway as configured

Not a design fault, but it gates everything: `AI_API_KEY`, `READ_API_KEY` and
`GOOGLE_SERVER_CLIENT_ID` are all `""` in `app/build.gradle.kts`.
`GoogleAuth.isConfigured` is therefore false, `mint()` throws
`SignInUnavailableException` on every path, and both AI features are
permanently unreachable. `PRIVACY_POLICY_URL` and `ACCOUNT_DELETION_URL` point
at a domain that does not resolve, which rule 89 makes a hard block on `+2.2a`
shipping at all — and rule 57 puts that gate *before* the closed test opens,
because the 12 testers are real data subjects.

---

## 3. What the compliance architecture gets right

Recorded because it is the majority of the review and because "no findings" is
information. Each was checked against the rule text, not against the plan's
summary of it.

| Rule | Where it lives in the code | Verdict |
| --- | --- | --- |
| android §3.1 r1 (no media permissions) | `AndroidManifest.xml` declares only `INTERNET`; `media/PhotoSources.kt` uses `PickVisualMedia` | ✓ |
| android r2 (EXIF off at ingest) | `media/ImageIngest.kt` re-encodes rather than scrubbing named tags — structural, not a list to maintain; instrumented test exists (unrun) | ✓ |
| android r3 / screen 0.11b | `CAMERA` is not declared, so the rule stops applying rather than being satisfied; the manifest records the trap (a declared `CAMERA` must be *held* before `ACTION_IMAGE_CAPTURE` runs) | ✓ |
| android r4 · accounts r94/96 | `AiGateState.launch()` raises `AiDisclosureSheet` immediately before the transfer; `+2.2b` explicitly refuses to be the consent step | ✓ |
| android r5 | report control on the output itself (`ScanReviewSheet`, `SuggestionSheet`), mirrored in `+2.2b`, and **not** consent-gated | ✓ |
| android r6 | structured fields in, structured fields out; no free-text chat surface | ✓ |
| android r13 | `network_security_config.xml`, cleartext false, zero domain exceptions, with the temptation documented | ✓ |
| android r16 · accounts r69–71 | in-app deletion + web URL + a confirmation that states what is deleted *and* what is retained | ✓ |
| accounts r58/59 | "stay on this phone", never "never leaves your device"; the metering record is named on `+2.2a` | ✓ |
| accounts r60/61 | ID token only, no extra scopes; `GoogleAuth`'s docstring notes honestly that the token still carries an `email` claim and that the fix is server-side (`accounts.py` has no column for it) | ✓ |
| accounts r62 | `allowBackup="false"` + `dataExtractionRules` + `fullBackupContent` + `tools:replace`, with "verify in the merged manifest" written down | ✓ |
| accounts r88/90 | URL exposed, summary not a copy, **no in-app last-updated date** | ✓ |
| accounts r92 | rights rows deep-link to one control each; the backup clause is present and is what makes "we have no copy" honest | ✓ |
| accounts r95 | two consent flags, no master toggle | ✓ |
| accounts r97 | withdrawal is one tap, unconfirmed; re-grant is asymmetric and goes through the sheet | ✓ |
| accounts r98 | `withdrawnAt` distinguishes "never accepted" from "accepted then withdrew"; `acceptedVersion` re-prompts only on a material change | ✓ |
| accounts r99/100 | consequences stated in three separate true sentences; no non-retention, no "never shared", no server-country claim | ✓ |
| accounts r103 | no open-source licences row, per the recorded override | ✓ |
| android r18 | `targetSdk = 36` | ✓ |
| accounts r81 | CNIL named on `+2.2a` | ✓ |
| resolution #17 | `fallbackToDestructiveMigration()` correctly absent | ✓ (but see D5) |

---

## 4. Defects

### D1 — Canvas stroke widths and offsets are in pixels, not dp

> **STATUS, 2026-08-15. Fixed** (confirms the earlier "third pass" status
> block above, verified directly this time): every stroke width and offset
> in both `RadarChart.kt` and `ExtractionBar.kt` is `N.dp.toPx()`, no bare
> float literals remain.


`DrawScope` works in pixels. `ui/components/RadarChart.kt` uses raw floats
throughout:

```kotlin
drawPath(path, gridColor.copy(alpha = netAlpha), style = Stroke(width = 1f))
drawLine(..., strokeWidth = 1f)
drawPath(path, seriesColor, style = Stroke(width = 2.2f))
val anchor = point(i, radius + 14f)
```

On a 3× device that is a **0.33dp** net and a 0.73dp series line — the net will
be all but invisible, and the deck draws it as a readable layer. The label ring
sits `14px ≈ 4.7dp` clear of the polygon instead of 14dp, so the eleven labels
crowd the chart at exactly the small radii the docstring says the measured
layout exists to protect. `ExtractionBar`'s `strokeWidth = 1.5f` band edges have
the same problem, less visibly.

Fix is mechanical — `1.dp.toPx()`, `2.2.dp.toPx()`, `14.dp.toPx()` — but it
cannot be seen without a device, which is why it survived review. **The frames in
`screenshots/` deliberately render the intended dp values, not the buggy px
ones**, so do not use them to check this.

### D2 — `+2.2a` promises a long-press the code does not implement

`PrivacyScreen` prints *"Always the current version. Tap to open, hold to
copy."* The card carries `Modifier.clickable { open(POLICY_URL) }` and nothing
else. There is no `combinedClickable`, no `LocalClipboardManager`, no
`ClipboardManager` reference anywhere in the module. Rule 88 asks for the URL as
a "tappable, **selectable**" affordance; the screen currently claims a capability
it does not have, on the one screen where a wrong statement is a store risk.

### D3 — The Art. 15(3) access document under-reports

`coffee_server/schemas.py:181` returns `rate_limit_events_currently_held`.
`net/ServerApi.kt`'s `AccountResponseDto` has no such field, so `DataAccessSheet`
never renders it. Meanwhile `DeleteAccountDialog` tells the user deletion erases
"the identifier, usage counts **and rate-limit records**" — a category the export
does not show. Rule 93 lists rate-limit records among what the access response
holds. Add the field and a line to the rendered document.

### D4 — `+2.2b`'s consent row collapses five states into two

`OperationConsent` can distinguish never-asked, shown-but-declined, live,
withdrawn, and *lapsed because `disclosureVersion` was bumped*. `ConsentRow`
renders `if (live && grantedAt != null) "On since …" else "Off"`. A consent that
lapsed on a material change is therefore indistinguishable from one the user
turned off — and the two have different next actions (one is "we changed what we
send, please look again", the other is "you turned this off"). The state machine
already carries the information; only the label throws it away.

### D5 — `exportSchema = true` with nowhere to export to

`CoffeeDatabase` sets `exportSchema = true`, but `app/build.gradle.kts` passes
no `room.schemaLocation` to KSP and does not depend on `androidx.room:room-testing`.
Room will warn and emit nothing. Resolution #17's named mechanism —
"`Migration` objects tested with `MigrationTestHelper` from the first schema
change onward" — needs the version-1 schema JSON checked in *before* there is a
version 2, or the first migration is untestable. Two lines now, unrecoverable
later.

### D6 — A scan applied to a new bean can leave an "Untitled" bean behind

`BeanDetailScreen.applyScan` persists the bean before the user has pressed Save,
because a photo needs a row to attach to — documented, product-owner-approved,
and reasonable. The consequence is not documented: once that row exists, `leave()`
takes the `existing != null` branch, flushes and pops. The confirm-discard dialog
never fires, and a scan the user then abandoned leaves a bean on the shelf named
"Untitled". Arguably intended (the photo was saved); worth stating either way,
because "Untitled" is also the one place the app writes a real string where every
other path renders a blank name as "Unnamed bean".

### D7 — Four XML resources were not well-formed and would have failed the build

Found while adding drawables in the fourth pass, and **fixed there**, because
it is a syntax error rather than a judgement call: `--` is illegal inside an
XML comment, and four files used it as an em dash the way the Kotlin does.

| File | Occurrences |
| --- | --- |
| `AndroidManifest.xml` | 6 |
| `res/drawable/ic_launcher_foreground.xml` | 1 |
| `res/values/colors.xml` | 1 |
| `res/xml/network_security_config.xml` | 1 |

`AndroidManifest.xml` is the one that matters most: the manifest merger parses
it before anything else, so the module could not have produced an APK in this
state, and no amount of Kotlin review would have found it. Every occurrence is
now an em dash (`—`); the files declare `encoding="utf-8"` and the prose is
unchanged. **This is what "nothing here compiles" costs** — a whole class of
error that a single `aapt2` invocation catches and a careful reader does not.
`python3 -c "import xml.etree.ElementTree as ET; ET.parse(f)"` over
`app/src/main/**/*.xml` is a five-second check and is worth running before any
review that claims the module is buildable; it now passes on every file.

> **STATUS, 2026-08-15**: Re-checked after this pass added 15 more drawables
> (the dripper glyph set) — the batch generator hit this exact bug on its
> first run (real em dashes weren't in its template), fixed there before any
> file was committed. A repo-wide regex sweep for `--` inside `<!--...-->`
> bodies across `app/src/main/**/*.xml` (delimiters excluded, so `<!--` and
> `-->` themselves don't false-positive) comes back clean.

---

## 5. Scheme E conformance — the app is not scheme E

> **STATUS, third pass (2026-08-14, after the scheme E implementation pass).**
> §5.2–§5.5 and §5.7 are **fixed**; `check_design.py` now prints `ok` on all
> four sections. Landed: the eleven type roles including the three label
> weights, `displaySmall`, the chip pill as a token separate from `shapes.small`,
> the green-black scrim, the capsule field and its two-up grid, the deck's FAB
> fill *and* circle shape, a divider under every top bar, the 16dp gutter, the
> px→dp fix in both Canvas components, short radar labels at small sizes, the
> full extraction-bar drawing, and Home's pills / See-all / Search / process+
> roast meta / header caption.
>
> **Still open, and each is separate work:** the in-app brand mark (§5.6), the
> mascot and dripper glyphs (§5.6b), `0.2`'s photo hero and Images strip
> (§5.6c), the Ask-AI entry point (§5.6d), `+1.1`'s three-choice menu (§5.6e),
> Sessions rows (§5.6f), Home's contribution heatmap and the Share Card
> (§5.10). The subsections below are left as written — they are the measurement
> that produced the fix list, and the open items still need them.
>
> **STATUS, fourth pass (2026-08-14, illustration).** §5.6 is **fixed** and
> §5.6b is **mostly fixed**. `res/drawable/` now carries four generated
> `<vector>`s — the mark with and without its tagline, and the two mascot
> poses the built screens ask for — and `ui/components/Illustrations.kt`
> exposes them as `CoffeeCanLogo` / `MascotPourOver` / `MascotCamera`. Art
> landed on all five built screens that were missing it: `00_home_empty`
> (mark, 100dp), `+2_profile_empty` (mark, 88dp), `+1_sessions_empty`
> (pour-over, 184dp), a bean with no sessions (pour-over, 132dp) and `0.1`'s
> scan card (camera pose, 108dp). None of it is re-drawn: every coordinate is
> the deck's own geometry, flattened out of `wireframes.logo()` and
> `scheme_e.can_boy_*()` by script and pixel-diffed against the deck's render
> before landing. **Still missing from §5.6b, at the time:** the dripper
> glyphs (`plan/dripper_icons/`, Sessions rows and `+1.1`'s choice rows), the
> mark on `+1.1`'s "From Coffee Can" row at 40dp, and `00w`'s splash.
> `can_boy()` and `can_boy_sad()` stay unbuilt because their screens are.
>
> **STATUS, 2026-08-15.** The dripper glyphs and the `+1.1` mark are fixed
> (§5.6e, §5.6f, both done 2026-08-15). **Two items dropped, both checked
> against `scheme_e.py` directly rather than re-asserted:** "the mark in
> Home's top bar" isn't a real gap — `home()`'s `wf.top_bar(c, "Coffee Can",
> brand=True)` only sets a bigger/bolder title *text style*
> (`wireframes.top_bar`'s `brand` parameter never draws a logo glyph
> anywhere in its body); there is no mark to port. "`sparkle()` on the AI
> surfaces" is similarly not actionable — `sparkle()` is defined in
> `wireframes.py` but has zero call sites anywhere in `scheme_e.py`; the deck
> currently draws no AI glyph on any page (the closest hit is `log_brew()`'s
> docstring explicitly saying its own icon is "Deliberately NOT sparkle()").
> Implementing either would be inventing placement the deck doesn't specify.
> `00w`'s splash is the one item here still open — see §5.10.
> **Fixed, 2026-08-15, later the same day** — see §5.10 item 3's own status
> block for what shipped and why the intermediate "already built" note in
> between was itself wrong.
>
> **THE MASCOTS MOVE NOW, 2026-08-15.** Everything above describes the
> illustrations as flattened `VectorDrawable`s, which is right for a still and
> is precisely why nothing animated: flattening bakes the nested transforms
> into absolute path data, welding the arm that should pivot to the body it
> should pivot against. The deck's figures are functions with knobs, and
> `ui/components/CanBoy.kt` is now those functions in Compose — the deck's
> `d` strings parsed verbatim with `PathParser`, its `<g transform>` nesting
> reproduced as the same ordered `withTransform` calls, evaluated at runtime.
> `MascotCamera` runs `_shutter_pose`'s own beat (aim, press, flash, recoil,
> settle; 24 frames × 70ms), which is the one mascot animation the deck
> actually specifies — `MOTION` lists `0.1_bean_profile` and there is a GIF of
> it. `MascotHeartbreak` is new, for the news failure state. Verified the way
> this document keeps insisting on: rendered at 164×164 and pixel-diffed
> against the deck rendering the same function at the same size, worst channel
> delta 53–54/255 with nothing above 96.
>
> **Two of the three are extrapolations, and should be read as such.** The
> deck animates *only* the camera. `can_boy_sad` takes no knobs at all and is
> drawn already-broken, so the heart splitting is invented motion that settles
> on the deck's own frame; `can_boy_v60` has a `tilt` knob the deck never
> drives, and `MascotPourOver` does not use it — it rocks the whole flattened
> figure ±1.2°, which is a weaker thing than the kettle-only pivot `tilt`
> describes and is flagged in its own docstring. Porting `can_boy_v60` to
> Canvas is what would close that gap; it is a much larger figure (kettle,
> cone, server, stream, spiral rib) and was not attempted.
>
> Two things the implementation pass found that this section had wrong or
> missed, recorded here rather than silently corrected:
> 1. **The deck's gutter is not uniformly 16.** `wireframes.GUTTER = 16` for
>    cards and the top bar, but `wf.section()` and most of `scheme_e.py`'s field
>    grids hardcode `x=20`. §5.5's "deck 16 / build 20" is half the story; the
>    build now uses a uniform 16.
> 2. **The FAB's shape was wrong too, not just its fill.** M3 resolves it from
>    `shapes.large`, which this theme overrides to the deck's 24dp card radius,
>    so the default rendered a rounded square where the deck draws a 56dp disc.
>    §5.5 flagged only the colour.
>
> And one that `check_design.py` cannot see: **`labelSmall`'s 500 weight has no
> face to render in.** Only two static Fredoka files ship, so Medium resolves to
> the regular face. The checker compares *declared* weights and passes. Shipping
> `Fredoka-var.ttf` is what would close it; until then the declaration is
> aspirational, and `Theme.kt` now says so.

Put `screenshots/00_home.png` next to
`../plan/screenshots/scheme-e/00_home.svg` and they do not read as the same
product. That is not a rendering artefact of the simulation: it is what the
Kotlin produces. `ui/theme/Theme.kt` opens with

> *"THE SOURCE OF TRUTH IS `plan/variants.py`. … Every hex below is copied from
> there rather than sampled or approximated, because 'close enough' across forty
> tokens is how a build stops being the design and starts being a cover version
> of it."*

The hexes are indeed copied. Everything else in the deck — the type scale, the
field component, the chip shape, the bar treatment, the button treatment, the
brand mark, the chart's label set, and the page density that follows from all of
them — was not. The result is exactly the cover version that paragraph set out
to prevent, and it is the largest finding in this review.

### 5.1 What genuinely crossed over

Colour, and the reasoning behind colour. `PURE_GREEN`'s forty tokens are exact,
and the three-green separation is intact and correctly enforced: `Brand #34C759`
appears only on the adaptive-icon background, `primary #196D2E` under every
label, `vizSeries #2B9343` on data marks and never on a control. The `viz*`
family exists as a named group rather than being re-invented per chart. Fredoka
ships bundled with its OFL, and numeric columns keep a monospace face. The four
corner radii are right. `RadarChart` and `ExtractionBar` carry the deck's
*semantics* — absence drawn as absence, an inverted meter where chroma means
on-target — and `BagTile` draws a bag rather than a monogram. Every Canvas
component ships a `contentDescription` (resolution #11).

That is a real and non-trivial port. It is also where it stopped.

### 5.2 The type scale is wrong in all eleven roles

`variants.FREDOKA_STYLE` remaps the deck's type table through a weight map;
`Theme.kt` declares its own numbers. They agree on one role out of eleven.

| Role | Deck (sp / weight) | `Theme.kt` (sp / weight) | |
| --- | --- | --- | --- |
| `displaySmall` | 36 / 600 | **absent** | the deck's avatar letter has no style to use |
| `headlineMedium` | 28 / 600 | 30 / 400→600 | +2sp |
| `headlineSmall` | 22 / 600 | 24 / 600 | +2sp |
| `titleLarge` | 22 / 600 | 20 / 600 | −2sp |
| `titleMedium` | 16 / 600 | 15 / 600 | −1sp |
| `titleSmall` | 14 / 600 | 14 / 600 | ✓ the only match |
| `bodyLarge` | 16 / 400 | 15 / 400 | −1sp |
| `bodyMedium` | 14 / 400 | 13 / 400 | −1sp |
| `labelLarge` | 14 / **600** | 14 / **400** | **weight** |
| `labelMedium` | 12 / **600** | 12 / **400** | **weight** |
| `labelSmall` | 11 / **500** | 11 / **400** | **weight** |

The three label roles are the visible one. Scheme E sets every label
semi-bold — section actions, chip text, button labels, the "4 brews" count, the
consent-state line — and the app sets all three to `FontWeight.Normal`. That is
why the deck's small text reads as deliberate and the build's reads as thin
body copy. `Theme.kt` bundles a bold face for exactly this and then never asks
for it below `titleSmall`.

Body text being uniformly 1–2sp smaller than the deck is the second half: it is
why the build looks both airier *and* weaker than the design at the same time.

### 5.3 The deck has *two* field components and the app has one

**Correction to this audit's first pass**, which said flatly that "the field
component is the wrong component". That was half right, and the half that was
wrong matters.

`wireframes.py` ships two helpers. `textfield()` is a genuine M3 outlined field,
56dp, notched label — and it does **not** read `FIELD_STYLE`. `field()` is the
score-sheet motif, and under `FREDOKA_STYLE["field_style"] = "capsule"` it draws
a small label *above* a 30dp `surfaceContainer` capsule holding the value.

Scheme E uses both, deliberately, and the split is by *role*:

| Deck page | Bean name | Every other field |
| --- | --- | --- |
| `0.1` add-a-bean | `textfield()` — M3 outlined, 56dp, full width | `field()` capsules, **two-up grid**: Variety\|Altitude, Roaster\|Producer, Process\|Roast date |
| `0.2` saved bean | *(no editable name at all — it is the page title)* | `field()` capsules, same two-up grid, read mode |

So the app's `OutlinedTextField` is **correct for the one required field** and
wrong for the other eight, which should be half-width capsules in a 3×2 grid
occupying ~130dp total. The app stacks nine full-width 56dp boxes for ~600dp.
That is where most of Bean Detail's height goes, and it is why the deck's whole
add-a-bean page fits above the fold and the build's scrolls twice.

`LabeledField` and `ChoiceField` are already the single chokepoint for every
field in the app, so this is one new composable plus a grid at the call sites,
not nineteen rewrites.

### 5.4 Chips are not pills

`FREDOKA_STYLE["shape"]["chip"] = 999` — a full pill. `Theme.kt` has no chip
token; it maps `Shapes.small = FieldCorner (16dp)`, and M3's `AssistChip` and
`FilterChip` both resolve their shape from `shapes.small`. So every chip in the
build is a 16dp rounded rectangle where the deck draws a pill. Visible on the
suggestion sheet and the report sheet.

### 5.5 The bars, buttons and FAB are Material defaults, not deck treatments

| Element | Deck | Build |
| --- | --- | --- |
| Top bar | **hairline divider along its bottom edge** (`wireframes.top_bar` closes with a full-width `line()`) | M3 `TopAppBar`, no divider — the bar and the content share one flat field |
| Top bar title, no back | `headlineSmall` 22/600 | `titleLarge` 20/600 |
| Top bar title, with back | `titleMedium` 16/600 | `titleMedium` 15/600 |
| Bar actions | 48dp target, 24dp glyph, 48dp pitch | M3 `IconButton` defaults |
| Filled button | 40dp visual inside a **48dp touch target** | M3 `Button`, 40dp, no extra target padding |
| FAB | **`primary` fill, `onPrimary` glyph** | M3 default → **`primaryContainer` fill, `onPrimaryContainer` glyph** |
| Gutter | 16dp | 20dp |

**Correction to this audit's first pass:** it said the deck's filled button and
FAB carry a `primaryOutline` stroke. They do not. `wireframes.py` passes
`stroke=C.get("primaryOutline")`, and `PURE_GREEN` sets `primaryOutline=None` —
so under scheme E specifically both render strokeless. I read the generic helper
and never resolved the token for this scheme. The FAB *fill* finding stands and
is the loud one: the deck's is a solid dark-green disc, the build's a pale mint
one, because nobody passed `containerColor`.

The FAB is the loudest of these: the deck's is a solid dark-green disc that
anchors the page, the build's is a pale mint square-ish blob, because nobody
passed `containerColor`.

### 5.6 There is no brand mark in the app

> **Fixed, fourth pass.** `res/drawable/ic_brand_lockup.xml` and
> `ic_brand_wordmark.xml` are the shipped `icon.svg`'s own lettering, and
> `CoffeeCanLogo` puts it on `00_home_empty` at 100dp and `+2_profile_empty`
> at 88dp. The launcher icon is untouched and its comment still stands: a
> silhouette is the right call at 48dp, and this is a different decision about
> a different size. The measurement below is left as written.

`wireframes.logo()` renders the **shipped** mark — it reads
`coffee/src/coffee_can/assets/icon.svg` directly and draws the "Can" wordmark
over the brand disc, with the "Brewing chemist" tagline at sizes that can carry
it. The deck opens `+2_profile_empty` with it at 88dp and puts it in Home's top
bar via `brand=True`.

The Android module does not contain that asset, in any form. What it has is
`res/drawable/ic_launcher_foreground.xml`, a **hand-redrawn** can silhouette
(body, lid, pull-tab) whose own comment says *"The 'Can' wordmark is
deliberately not reproduced here."* That is a defensible call for a launcher
icon at 48dp. It is not a call about the in-app mark, and no in-app mark exists:
grep the module and there is no logo composable, no wordmark vector, no brand
asset of any kind. `ProfileScreen`'s signed-out state begins with the words "Not
signed in" against an empty background.

*(This audit's first pass drew a mark on that frame. It was wrong and the frame
has been re-rendered; `screenshots/+2_profile_empty.png` now shows what the code
actually produces, which is emptier.)*

> **STATUS, 2026-08-15.** Both halves of this are now resolved, and the second
> one reverses the call above. The in-app mark exists (`ic_brand_wordmark.xml`
> / `ic_brand_lockup.xml`, flattened from the deck's own `wireframes.logo()`
> and exposed as `CoffeeCanLogo`) — see §5.6b. And the **launcher icon is no
> longer the hand-redrawn silhouette**: on an explicit product decision it now
> draws the `Can` wordmark, reusing `ic_brand_wordmark.xml`'s path data
> verbatim rather than carrying a second, hand-drawn interpretation of the
> same mark that could drift from it. The "defensible call" this section
> credited was also never actually measured against a render — checked now,
> the wordmark stays legible and clear of the circular mask at the 48dp a
> launcher really uses (framing maths in the file's own comment: 0.968 scale,
> content 34.7 from centre against the 36 a 72dp circle mask allows). The
> tagline is still dropped, which is the part of the old reasoning that
> survives: it is illegible at icon sizes, and the deck drops it below 40dp
> for the same reason.

### 5.6b The illustration and icon vocabulary is entirely absent

> **Mostly fixed, fourth pass.** The mark and both mascot poses that built
> screens call for are in the module and on those screens; the dripper glyphs,
> `sparkle()`, the 40dp mark on `+1.1`'s row and Home's brand bar are not. Two
> deliberate departures from the table below, both stated at their call sites:
> `0.1`'s figure is **decoration beside** the existing `Button("Scan a label")`
> rather than the tap target the deck made it, because a 108dp picture with no
> role and no focus order is not a control; and `CoffeeCanLogo` centres the
> disc in its box where `wireframes.logo()` nudges disc and lettering together
> in the no-tagline lockup. The table is left as written.

Scheme E is not a flat Material app with a green palette; it carries a drawn
figure system, and none of it exists in Kotlin.

| Deck asset | Where the deck uses it | In the app |
| --- | --- | --- |
| `logo()` — the **shipped** mark, read straight from `coffee/src/coffee_can/assets/icon.svg`: "Can" wordmark on the brand disc, "Brewing chemist" tagline | `00w` splash (full-bleed), `+2_profile_empty` at 88dp, Home's bar via `brand=True`, and the `+1.1` "From Coffee Can" row | **nothing** — no vector, no composable, no asset |
| `can_boy_camera()` — the mascot holding a camera, mid-shutter | `0.1`'s scan card, where **the mascot is the tap target** ("Click me to scan") | replaced by a `Button("Scan a label")` |
| `can_boy_v60()` — the mascot brewing a pour-over | **`+1_sessions_empty` at 184dp, where it is the hero of the page**, and `0.2b_empty` at 132dp | **nothing** — both empty states are two lines of text on a blank field |
| `can_boy()` | `-1w` can-drink intro | v1.1, correctly not built |
| `can_boy_sad()` | `0.11b` permission-denied | screen correctly deleted |
| `dripper_icon()` — a per-dripper glyph (V60 cone, Chemex hourglass, Kalita flat-bottom) on a 28dp brand disc | **every row of `+1_sessions`**, and `+1.1`'s three choice rows | **nothing** — rows are text-only |
| `sparkle()` — "a neutral AI glyph; the brand mark does not belong on a consent screen" | the AI surfaces | not used |

**Correction, and it is the third of this kind in this document.** The row above
previously read *"`can_boy_v60()` | `-1w`, `+1.1c` vibe-brewing | v1.1 / not
built"*. Both attributions were wrong and I did not check either: `-1w` uses
plain `can_boy()`, `+1.1c_vibe_brewing` contains **no mascot call at all**, and
`can_boy_v60()` is in fact the hero of `+1_sessions_empty` — a **v1 screen that
is built** — and of `0.2b_empty`. Filing it under "v1.1 / not built" moved a
shipped-screen gap into the deferred pile. Verified this time by walking every
call site: `awk '/^def [a-z_0-9]+\(/{fn=$0} /can_boy[a-z_]*\(c,|wf\.logo\(/
{print fn" -> "$0}' scheme_e.py`.

**The full picture, which no earlier pass stated.** Every first-run and empty
state in scheme E carries art, and six of them are built screens shipping
without it:

| Deck page | Art the deck draws | Built? | In the app |
| --- | --- | --- | --- |
| `00w_welcome` | `logo` 290dp, no disc, full-bleed brand ground | no | — |
| `00_home_empty` | `logo` 100dp | **yes** | missing |
| `0.1` / `+1.1b` | `can_boy_camera` 108dp, **as the tap target** | **yes** | missing |
| `0.2b_empty` | `can_boy_v60` 132dp | **yes** | missing |
| `+1_sessions_empty` | `can_boy_v60` 184dp, hero | **yes** | missing |
| `+1.1_log_brew` | `logo` 40dp on the "From Coffee Can" row | **yes** | missing |
| `+2_profile_empty` | `logo` 88dp | **yes** | missing |
| `-1w` | `can_boy` 195dp | v1.1 | — |
| `0.11b` | `can_boy_sad` 164dp | deleted | — |

An empty state is the one screen where the app has nothing else to show, so it
is exactly where missing illustration costs the most: the deck's `+1_sessions_
empty` is a 184dp drawn figure with two lines under it, and the build is two
lines of text in the middle of a blank green field.

`plan/dripper_icons/` is a whole directory of source art. Nothing in
`v1/app/src/main/res/` references it.

The mark is the sharpest case because the asset already exists, shipped, in the
sibling project — `wireframes.logo()` literally parses that SVG at render time.
The Android module re-drew a *different* can silhouette by hand for the launcher
icon (`ic_launcher_foreground.xml`, whose comment says the wordmark is
"deliberately not reproduced here" — correct at 48dp, and not a decision about
the in-app mark) and then never brought the real one in at all.
**Both halves fixed 2026-08-15** — the in-app mark landed (§5.6b), and the
launcher icon was later rebuilt on `ic_brand_wordmark.xml`'s own path data, so
the hand-redrawn silhouette is gone and there is now exactly one drawing of
this mark in the module. See §5.6's status block.

### 5.6c `0.2` is a different screen in the deck, not a filled-in `0.1`

> **STATUS, 2026-08-15.** Fixed for the saved-bean (`!isNew`) branch: photo
> hero (real photo if attached, a gradient placeholder otherwise), no top app
> bar (floating back/delete discs — see below for why delete, not share),
> the pulled-up rounded panel with a drag handle, the headline title + meta
> line + divider, and an Images strip (0.2b) wired to a real, non-scanning
> attach flow. Verified against a real Paparazzi render, not just read —
> `screenshots/REAL_CAPTURES.md`. The fields themselves are still the same
> editable capsules as 0.1 rather than genuinely read-only, which the
> paragraph below already argues is the right call ("every field... are
> identical between a blank and a filled form"); what was actually wrong was
> the *chrome* around them, which is what this fix addresses. One
> undischarged substitution: the deck's top-right disc is Share Card export,
> which doesn't exist yet (§5.10) — Delete sits in that slot until it does,
> documented at the call site rather than silently dropped. `0.1` (the blank
> form) was already correct and is untouched.

`BeanDetailScreen`'s docstring justifies collapsing 0.1 and 0.2 into one
composable like this:

> *"The deck numbers them apart because a blank form and a filled one look
> different, not because they behave differently."*

That is not what the deck draws. `0.2_bean_detail` is structurally a different
page:

- a **photo hero** filling the top ~28% of the screen, with the bean's own image;
- **no top app bar at all** — back and share are circular scrim discs floating on
  the photo;
- the content arriving as a **panel pulled up over the photo**, rounded top
  corners and a drag handle;
- the title as a wrapping headline inside that panel, a meta line under it
  ("Guji, Ethiopia · Natural · Roasted 28 Jul"), then a hairline rule;
- the fields in **read mode** — capsule grid, not editable boxes.

The build renders 0.2 as 0.1 with values in it: same top app bar, same nine
stacked editable outlined fields, no photo, no panel, no share. The
one-composable decision is defensible as engineering; the *reason given for it*
is a misreading of the deck, and it should be restated as "we are not building
the display presentation in v1" rather than "there is no display presentation".

`0.2b` adds an **Images strip** — three page thumbnails plus an "+ Add img"
tile — which is the carousel `plan/README.md` already lists as unbuilt.

### 5.6d Ask-AI is on the wrong screen

`screens.md` §5: *"Modal sheet launched from **Bean Detail's session list**."*
The deck agrees — `0.2b` puts **"Ask AI"** in the `Sessions` section header.

The build puts it on **Brew Session Detail**, in the `Brew details` section
header, and Bean Detail's Sessions header action is "New brew" instead. So the
suggestion arrives *after* you have opened a brew form rather than as a way of
starting one, and the deck's Bean Detail has no path to it at all.

Not necessarily wrong as a product call — asking with a dripper already chosen
gives the model more to work with — but it is undocumented, it contradicts
`screens.md`, and `plan/README.md`'s "what exists" table lists it under 0.21b as
"a sheet over the brew form" without noting the move.

### 5.6e `+1.1` collapsed two screens into one

> **STATUS, 2026-08-15. Fixed.** `WhichBeanSheet` now draws the deck's three
> visual peers verbatim — title, subtitle, and three icon rows with real
> glyphs (`CoffeeCanLogo`/`BagGlyph`/`DripperGlyph`, not `BagTile`s), each a
> chevron-tipped row. "From Coffee Can" now pushes a real `+1.1a`
> (`PickBeanScreen`) instead of listing beans inline. Verified against a real
> Paparazzi render — `screenshots/REAL_CAPTURES.md`.

The deck's `+1.1` is a **three-choice menu sheet** — title "Log a brew",
subtitle "Which bean is in the cup?", then three icon rows with chevrons:
*From Coffee Can* / *Add a new bean* / *Vibe brewing*, each with a one-line
explanation and a brand-disc glyph. Picking the first lands on `+1.1a`, which is
the actual bean list.

The build's `WhichBeanSheet` merges them: title "Which bean?", up to six real
beans with `BagTile`s, then an `OutlinedButton` "Add a new bean" and a
`TextButton` "Just start brewing". One tap shorter, and the three options are no
longer visually peers — two of them have become buttons under a list. Again
defensible, again undocumented, and it loses the subtitle that explains what the
sheet is for.

### 5.6f `+1_sessions` rows are missing half their content

> **STATUS, 2026-08-15. Fixed, with two corrections to this table itself
> found by reading `scheme_e.py`'s actual `sessions()` source rather than
> re-deriving it: the disc is 40dp (`r=20`), not 28dp, and the date is
> `onSurfaceVariant`, not `primary` green — only the chevron was genuinely
> missing.** All five real rows now fixed: real dripper glyphs (15 vectors,
> `Illustrations.kt`'s `DripperGlyph`, not just V60), the extraction verdict
> in the meta line, the inset divider, the chevron, and a Sort action on the
> top bar. One documented, deliberate divergence: dripper names show the
> full stored string ("Hario V60") rather than the deck's shortened demo
> values ("V60") — no abbreviation rule is specified anywhere for the other
> 14 drippers, so inventing one risked being wrong; a real render caught
> that the long form needs `maxLines = 1` to avoid wrapping the fixed-height
> row, which is now in place. Verified against a real Paparazzi render —
> `screenshots/REAL_CAPTURES.md`.

| | Deck | Build |
| --- | --- | --- |
| Leading element | 28dp brand disc with the **dripper glyph** | nothing |
| Dripper name | abbreviated — "V60", "Kalita", "Chemex" | full — "Hario V60", "Kalita Wave", "Origami Dripper" |
| Meta line | `V60 · 15.0 g · 4.5 · **well extracted**` | `Hario V60 · 15.0 g · 4.5` |
| Date | right-aligned in **`primary` green**, with a **chevron** after it | `onSurfaceVariant`, no chevron |
| Divider | inset to start after the icon | full gutter-to-gutter |
| Top bar | carries a **sort** action | no actions |

The extraction verdict is the interesting omission: `SessionEntity.extraction`
is stored, `ExtractionBar` already turns it into the words "Under-extracted /
Well extracted / Over-extracted" for its `contentDescription`, and the log row —
the one place you scan for *why* a brew was good — leaves it out.

### 5.6g Smaller placement divergences found in the sweep

- ~~**`0.1`'s empty radar.**~~ **Fixed, 2026-08-15.** `RadarSection`
  (`BeanDetailScreen.kt`) takes a `showChart` flag; `0.1`'s call site passes
  `draft.manual || tasted.n > 0`, which is false on a bean that's never been
  saved unless a manual override was already set, and renders the deck's
  short caption-only card instead of a 260dp empty net. `0.2` always shows
  the chart, matching the deck's own `0.2` page, which never omits it.
- ~~**Radar caption placement.**~~ **Fixed, 2026-08-15.** The caption sits
  below the card now, not inside it, on Bean Detail (`00_home`'s own
  caption was already on the section-header row — see §5.9's corrections).
- ~~**Section-header actions the build is missing:** `Search` (Home), `Sort`
  (Sessions), `Ask AI` (Bean Detail), `Add img` (Bean Detail).~~ **STATUS,
  2026-08-15**: `Search` and `Sort` were already built (stale claims,
  corrected in §5.9). `Add img` is built (§5.6c) but as a tile at the end of
  the Images strip, not header text — checked against the deck's own
  `0.2b_bean_detail_lower.svg` render, which draws it the same way, so the
  tile is the correct reading and this bullet's framing was imprecise, not
  the build. `Ask AI` on Bean Detail is the one still-real item here, and
  it's the same divergence §5.6d already documents (Ask-AI lives on Brew
  Session Detail instead) — a product-placement question, not fixed by this
  pass.
- **`+2.2a` / `+2.2b` are the closest match in the whole deck** — same sections,
  same order, same copy, switches in the same place. They were specified rule by
  rule after the visual language was set, which is exactly why they came out
  faithful, and it is worth noticing that the screens with the tightest written
  spec are the ones that got built right.

### 5.6h What the sweep confirmed as already-correct

Checked and found matching, so they are not open items: all 33 colour tokens
(verified programmatically against `PURE_GREEN`, including the five-step heatmap
ramp); the four corner radii; `RadarChart`'s and `ExtractionBar`'s empty-state
semantics; `BagTile`'s glyph construction and seeded gradient; the
`secondaryContainer` scan card; every string on `+2.2a` and `+2.2b`; and the
whole of §3's compliance table, re-checked against the rule text.

Deck tokens with no Compose equivalent, and whether that matters: `camGround`
(the deleted camera screen) and `cardInk`/`cardInkDim`/`radarInk` (the unbuilt
Share Card) — legitimately not needed yet. `vizUnder`/`vizWell`/`vizOver` — **not
needed either**, and worth recording why, because it is a trap: they look like
scheme E's extraction colours and they are not. `wireframes.extraction_bar()`
branches on `if C.get("vizDeviation")`, `PURE_GREEN` sets it, so scheme E takes
the *first* branch and the blue/orange three-zone ramp is the fallback for the
older schemes. The app's token choice here is right.

`scrim #06140A` **is** missing: the deck's scrim is a green-black at 0.55–0.6
opacity, and the build inherits M3's default (`colorScheme.scrim` unset →
black, at `0.32f`). Every sheet and dialog in the app therefore dims its
background less, and neutrally, where the deck dims more and in-palette.

And the extraction bar itself, while correctly *coloured*, is a much reduced
drawing:

| | Deck | Build |
| --- | --- | --- |
| On-target band | middle **third**, square ends | middle **quarter** (0.375–0.625), rounded |
| Centre | a `vizBandEdge` tick extending 3dp past the track | nothing |
| Value | a **filled bar from centre to value** plus a 3dp thumb taller than the track, with a surface-coloured halo | a single dot |
| Readout | a numeric readout above the bar | none |
| Zone labels | "Under" / "Well extracted" / "Over" beneath, the active one emphasised | none — the words exist only in `contentDescription` |

So a sighted user sees a dot on a bar and a TalkBack user hears "Well
extracted". The deck showed both the same thing.

### 5.11b The deck's navigation model is not implemented, and three documents disagree about what it is

`scheme_e.py`'s module docstring opens by defining the whole deck as a swipe
axis centred on Home:

> *"Numbering follows the swipe axis, centred on Home: … `-2 <- swipe left`,
> `-1 <- swipe left`, `00 HOME`, `+1 swipe right ->`, `+2 swipe right ->`"*

Every page number in the deck encodes it. `0.x` means *off-axis*, reached by
tapping rather than swiping. It is not decoration on top of the design; it is
the information architecture the design was drawn for.

**The module contained no gesture code at all** — as found, and fixed since;
the resolution is at the end of this section, and the finding is left standing
so the decision it produced can be read against it. `grep -rE
"HorizontalPager|VerticalPager|rememberPagerState|AnchoredDraggable|swipeable|
draggable|detectHorizontalDrag|pointerInput"` over `app/src/main` returned
nothing. Every transition was `navController.navigate(...)` against a back
stack.

**What makes this more than an unbuilt feature is that the code advertises it.**
`ui/Nav.kt`'s `Routes` object is named after the axis and says so:

> *"Routes are named for scheme E's page numbers so a screen can be found from
> the design deck and vice versa. The numbering is the swipe axis: Home at 00,
> negative to the left, positive to the right, off-axis pages at 0.x."*

So the route table reads `"00_home"`, `"+1_sessions"`, `"+2_profile"` and looks
like an implemented axis. It is a naming convention over push navigation.

**Three documents, three different models, and none of them cite the others:**

| Source | Model |
| --- | --- |
| `plan/scheme_e.py` (the deck) | horizontal swipe axis across `-2 … +2` |
| `plan/README.md` resolution #19 | debates **bottom navigation vs push-only**, picks push-only — and never mentions the swipe axis at all |
| the code | push-only, no gestures |

The plan's decision record therefore resolved a question the deck had already
answered differently, without noticing. Resolution #19's stated reason ("revisit
if/when Catalogue returns in v1.1 and there are three real top-level
destinations") is about flattening a back stack — a bottom-nav argument. It is
not an argument against the axis.

**What it costs, visibly, on screens already built.** Push navigation needs
doors that a swipe axis does not, and every one of them is a divergence
already logged elsewhere in this section as if it were independent:
Home's profile icon and its "Every brew you've logged" row (§5.9) exist only
because Sessions and Profile are otherwise unreachable; Sessions and Profile
carry back arrows the deck does not draw; and Home's top bar consequently
carries two actions where the deck has none. Fixing those *without* the axis
would strand two destinations — which is why they are not a simple fidelity
fix and should not be treated as one.

**This is a product decision, not a defect**, and it is recorded here because
nobody appears to have taken it deliberately: the deck assumed swipe, the plan
debated something else, and the code shipped a third thing. The options are (a)
keep push-only and amend the deck's numbering note so it stops describing
navigation the app does not have, (b) build the axis with `HorizontalPager` over
the four top-level surfaces, restoring the deck's bare top bar, or (c) bottom
navigation, which resolution #19 already declined. Only (b) makes `00_home`
match the deck.

**RESOLVED: OPTION (b) IS TAKEN, and built.** The product owner chose the axis.
What shipped:

- **`ui/Axis.kt`** — `AxisPage` (an enum carrying each page's deck number),
  `AXIS_PAGES` (the axis left to right) and `HOME_INDEX` (**derived**, never a
  literal `0`, because `-1` Can-Drink inserts at the left in v1.1 and Home
  re-centres), plus `SwipeAxis`, one `HorizontalPager` over
  `[00 Home, +1 Sessions, +2 Profile]` opening on `HOME_INDEX`.
- **`ui/Nav.kt`** — `Routes.Home`, `Routes.Sessions` and `Routes.Profile` are
  gone; one `Routes.Axis` destination holds the pager and is the start
  destination. Every `0.x`-and-deeper route stays exactly what it was, pushed
  *on top of* the axis — which is what `0.x` meant all along. The `Routes`
  docstring, which claimed the numbering "is the swipe axis" while the code had
  no gesture in it, now says which half of the numbering it owns.
- **Each axis page keeps its own `Scaffold`** rather than one hoisted outside
  the pager. The deck's pages are whole frames with their own bars ("Coffee
  Can" + brand, "Sessions" + sort, "Profile" + Log out), so the bar swipes with
  its page; a hoisted Scaffold would pin the bar and cross-fade the title,
  which is tab-bar behaviour the deck does not draw. The three Scaffolds are
  siblings inside the pager, not nested, so insets apply once per visible page.
- **Back is swipe *plus* an affordance**, which is the deck's own model:
  `top_bar(..., back=True)` is drawn on `+1` and `+2`. The correction to the
  paragraph above — the deck *does* draw those back arrows; only Home's two
  actions were push-model doors. Both the arrow and the system gesture
  `animateScrollToPage(HOME_INDEX)`; `BackHandler` is disabled on Home so back
  leaves the app there.
- **Home lost its two doors**: the profile icon (the deck's axis note is
  explicit that "profile lives on the swipe axis only") and the "Every brew
  you've logged" row, whose own comment said it existed because the swipe was
  unbuilt. **"Add bean" stays** — the deck's `00` page draws no action, but the
  same axis note says `0.1` is "reached by tapping Add bean from Home". The
  deck contradicts itself there and the note is the half that describes a
  reachable screen.
- `screenshots.py` moved with it: no person glyph in `top_bar`'s vocabulary at
  all now, and Home's bar draws one action.

**The open cost, and it is an accessibility one, not a polish one.** Nothing
visible now points to `+1` or `+2`. The gesture is the only *sighted* route
there; the back arrows are a route home, not a route out. For assistive tech
the pager's scroll semantics do expose paging (an accessibility service can
scroll it without a gesture), and `SwipeAxis` adds named
`CustomAccessibilityAction`s — "Go to Sessions", "Go to Profile" — so the
destinations are named rather than left as "scroll forward". That is a real
non-gesture route, and it is still weaker than the push model it replaced,
because discoverability for a sighted user with no accessibility service is now
zero. **The deck has the same hole** — it draws no page indicator, no rail, no
dots — so closing it means adding something the deck does not have. Flagged
here rather than smoothed over; a page indicator on the axis is the obvious
candidate and is not built.

### 5.11c Resolution #16's delete affordances are half-built

Found by the same grep. Resolution #16 records: *"Added swipe/destructive-action
delete to Brew Session Detail's session list and to each stage row."*

- **Stage rows:** built — `StageRow` carries a trailing `IconButton` with a
  close glyph. ✓
- **Bean Detail's sessions list:** **not built.** `SessionLine` is a `Column`
  with `clickable` and nothing else — no swipe, no destructive action, no
  overflow. A logged brew can only be deleted by opening it and using the top
  bar's delete icon.

Not a scheme E issue (the deck does not draw a delete affordance there either),
but it is an accepted specialist finding recorded as done and only half done.

### 5.7 The radar uses the wrong label set for a small chart

`wireframes.radar11` carries two label lists and picks the short one —
`Fruity, Floral, Tea, Sweet, Nutty, Spices, Roasted, Cereal, Green, Sour,
Ferment` — precisely because Home's chart is small (r=60). `RadarChart` always
passes `BeanEntity.FLAVOR_AXES`, the full names, including `Tea-like`,
`Nutty/Cocoa`, `Green/Veg` and `Fermented`.

The docstring says measured layout exists so that *"at small radii an eyeballed
offset clips 'Green/Veg' and 'Nutty/Cocoa' first"*. Measuring stops them
clipping; it does not stop eleven long labels from being the loudest thing on
the card. The deck solved that by shortening the words, and the parameter to do
it — `labels: List<String>` — is already on the composable and never used.

### 5.8 Density, as a consequence

Deck Home fits, above the fold: three bean cards at 72dp, a "See all 4 beans"
row, a 140dp Brewing-activity heatmap card, and a 178dp My-flavor card with its
caption. Build Home fits: four bean cards at 88dp and one 224dp radar card.
The deck's Home carries three distinct pieces of information; the build's
carries one and a half.

That is not one decision — it is 5.2 through 5.7 compounding. Every card is
taller because the type is looser and the fields are boxes; the radar card is
224dp because full labels need the room; the heatmap never got built partly
because there was no room left for it.

**Closed on Home, sixth pass.** The shelf card's two overridden sizes (14sp
name, 11sp meta) came across, the flavour card went 224 → 178dp, the heatmap
was built, and the two `Spacer`s above the section headings went — `SectionHeader`
already carries 12dp of top padding, so a spacer on top of it was double-counting
the gap. Home now shows all three pieces of information the deck does. It still
lands ~34dp lower down the page than the deck: 4dp of it is the status bar, and
the rest is `SectionHeader`'s 40dp against the deck's 36 and the "See all" row's
36 against its 30, both shared conventions rather than anything Home chose. The
practical cost is that the flavour card's bottom edge reaches the screen edge
instead of stopping 34dp short of it; nothing the deck shows is off screen.

### 5.9 Per-page divergences beyond the system-level ones

| Deck page | Divergence | Called out in code? |
| --- | --- | --- |
| `00_home` | ~~top bar carries "Add bean" + a person icon~~ — the person icon is gone with the axis (§5.11b); "Add bean" stays, on the deck's own axis note. ~~The brand mark in the bar is still missing (§5.6)~~ — **stale, 2026-08-15: not a real gap, see §5.6b's status note — the deck's own `top_bar(..., brand=True)` never draws a mark, only a bigger title style, which the build already has** | yes |
| ~~`00_home`~~ | ~~no **Search** action on "Your beans"~~ — **stale, 2026-08-15: built**, confirmed against a real render | no |
| ~~`00_home`~~ | ~~all beans render; the deck shows three plus "See all N beans"~~ — **stale, 2026-08-15: built** (§5.8's sixth pass), confirmed against a real render | no |
| ~~`00_home`~~ | ~~brew count is plain coloured text; the deck uses a `primaryContainer` **pill**~~ — **stale, 2026-08-15: built**, confirmed against a real render | no |
| ~~`00_home`~~ | ~~bean card meta is the roaster; the deck shows process + roast date~~ — **stale, 2026-08-15: built** ("Natural · Roasted 28 Jul"), confirmed against a real render | no |
| ~~`00_home`~~ | ~~no "Average across N sessions" caption on the My-flavor heading~~ — **stale, 2026-08-15: this is built** (`HomeScreen.kt`'s `SectionHeader("My flavor", caption = ...)`), confirmed against a real render | no |
| `0.1` | the scan card keeps the copy and position, no can-boy | yes |
| ~~`0.2` / `0.2b`~~ | ~~no photo hero, no Images carousel~~ — **fixed 2026-08-15, §5.6c** | yes |
| `0.11` / `0.11b` | superseded by the photo-source sheet; the mascot viewfinder is gone | yes, with the manifest trap that makes it mandatory |
| `+2` signed in | no avatar, no Change photo, no Name, no Email | yes — **and this is the spec winning, not a regression**: rule 60 deleted all four |

### 5.10 Specified for v1 and not built

1. **Share Card export** (`screens.md` §10) — no share icon on either top bar, no
   `GraphicsLayer` render, no `ACTION_SEND`. `FileProvider` is configured and
   `file_paths.xml` already declares `share/`, so the plumbing waits on the
   screen. In the **closed-testing** milestone, not deferred to v1.1.
2. ~~**Contribution calendar** — the deck's "Brewing activity" card.~~ Built,
   `ui/components/ContributionCalendar.kt`, over the `dailyCounts()` query that
   was already there. 21 columns, the width the card fits, from that week's
   Monday back; month labels derived from the dates on screen rather than the
   deck's four hard-coded ones. Home now carries both summary panes.
3. ~~**Welcome / splash `00w`**~~ — **stale claim, 2026-08-15**, corrected the
   same day it was written. The earlier note here said "nothing here was
   missing" on the strength of `Theme.CoffeeCan.Splash` alone -- but that
   theme is the *platform* SplashScreen API, which draws a small centred
   icon from a static `windowSplashScreenAnimatedIcon` and hands off the
   instant Compose has a first frame (by design -- Play's own guidance is
   against holding it open past that point). It cannot draw the deck's
   actual `welcome()`: a full-bleed 290dp wordmark, a 1000ms ease-out-cubic
   opacity reveal, held for 2000ms total. That half genuinely did not exist
   -- confirmed by reading `MainActivity.kt` in full, which had no second
   screen for it to hand off to. **Fixed the same day**: a real
   `ui/screens/WelcomeScreen.kt`, the nav graph's own start destination
   (`Routes.Welcome` in `Nav.kt`, popped with `inclusive = true` the moment
   it navigates to `Routes.Axis`, so back from Home never returns to it).
   `CoffeeCanLogo(size = 290.dp, tagline = true, disc = false)` — the disc
   is dropped for the same reason the deck drops it, a Brand disc on a Brand
   ground is invisible — faded in via a hand-written `Easing` reproducing
   `scheme_e.py`'s `_ease_out_cubic` frame-for-frame rather than
   approximating it with a stock Compose curve. Verified with a real
   Paparazzi capture at the resting (fade = 1) state (`WelcomeScreenContent`
   split out for exactly that, since a plain `snapshot()` doesn't advance
   `Animatable`'s frame clock and would otherwise always capture fade = 0)
   — `screenshots/00w_welcome.png`, superseding the simulator for this frame.
   This also fixed a second, related bug the user reported directly: Home
   briefly rendering `00_home_empty` on every cold launch of a phone that
   actually has beans, before the real list arrived and swapped it in. Root
   cause: `HomeScreen.kt` collected `observeBeans()` with
   `initial = emptyList()`, which is indistinguishable from "the shelf is
   genuinely empty" for however long Room's first query takes to answer,
   since a Flow's first emission isn't synchronous with collection start.
   Fixed with `initial = null` and a three-way branch (loading / empty /
   populated) instead of two; the loading branch is now what the splash
   covers, rather than a wrong screen the splash used to expose for one
   frame.

   **Follow-up, same day, from real-device feedback the sandbox can't
   reproduce (no emulator here — see the memory note on that):** the
   `windowSplashScreenAnimatedIcon` originally left in place
   (`@drawable/ic_brand_wordmark`) drew the logo solid, immediately, before
   `WelcomeScreen` ever mounted — so the actual on-device sequence was
   "logo pops in solid → resets to invisible → fades back in", not a
   single fade. Fixed by pointing that attribute at a new empty
   `ic_splash_icon_none.xml` instead: the platform phase now shows *only*
   Brand green, matching `WelcomeScreenContent`'s own t=0 frame exactly, so
   the hand-off has no visible seam and the fade is the only time the logo
   ever appears. `Theme.CoffeeCan.Splash`'s own comment — which had
   explicitly argued a second Compose splash screen must never exist
   alongside the platform one — is annotated rather than silently
   overridden, since that was a real prior stance and the fade requirement
   is what changed it. Total time on screen is now 3000ms (1000ms reveal +
   2000ms hold), also a same-day product decision, up from 2000ms.
   Re-verified: all 33 Paparazzi tests still pass, `assembleDebug` green at
   `compileSdk = 36`.

   **Second follow-up, same day — the first fix was incomplete and the bug
   was still reproducing on device.** The blank splash icon it introduced
   was a 1dp vector *declaring no path at all*, which is degenerate enough
   that the platform can reject it and fall back to the launcher icon —
   i.e. the exact thing it was written to prevent, made worse by the
   launcher icon having just become the "Can" wordmark. Fixed properly with
   three changes that are each load-bearing, now documented as such in
   `WelcomeScreen.kt`'s own docstring: (1) `ic_splash_icon_none.xml` is now
   a normal 240x240 vector containing a real full-bleed path filled
   `#00000000` — unambiguously valid, paints nothing; (2) `MainActivity`
   calls `setOnExitAnimationListener { it.remove() }`, cutting the splash
   away with no exit animation, since the default one zooms and fades the
   icon out and would otherwise run *concurrently* with this screen's
   fade-in of the same mark; (3) the Compose side already started at
   `fade = 0` and was never the problem — now pinned by a regression test,
   `WelcomeScreenScreenshotTest#welcomeFirstFrame`, whose captured frame is
   verified to contain exactly one colour (`#34C759`, 288000 px, zero logo
   pixels) against the resting frame's 7309 near-white wordmark pixels.
   Timing also corrected to the actual spec: **2000ms reveal, then frozen
   1000ms** (was 1000ms + 2000ms — same 3s total, wrong split). 34 tests
   pass. Note what still cannot be checked here: whether the platform splash
   really draws nothing is an on-device property, and there is no
   emulator in this environment — items (1) and (2) are reasoned from the
   SplashScreen contract, not observed.
4. ~~**The in-app brand mark** (§5.6).~~ Built, fourth pass, on the two empty
   states. Home's top bar was never actually a gap here (§5.6b's
   2026-08-15 status note) — only the splash (item 3 above) is still open.
5. ~~**Home's "My flavor" caption.**~~ **Stale, 2026-08-15**: built
   (`HomeScreen.kt`), confirmed against a real render — see the §5.9 table.
6. ~~**Search** on Home's bean list.~~ **Stale, 2026-08-15**: built
   (`HomeScreen.kt`'s `searching`/`query` state and `CapsuleField`),
   confirmed against a real render — see the §5.9 table.
7. ~~**Photo carousel / rotate / remove**~~ — display + attach built 2026-08-15
   (`ImagesStrip`, §5.6c); **rotate and remove are still missing** —
   `BeanImageEntity.rotation` is stored and read by nothing, and there's no
   delete affordance on a thumbnail once it's attached.

Correctly *not* built: `-1_can_drink`, `-1w_can_drink_intro`, the news ticker
(v1.1 per resolution #2), and voice session (v1.1).

### 5.11 How to close it

Roughly in cost order, and the first three are most of the visual gap:

1. **Fix `SchemeETypography`** — eleven values, one file. Add `displaySmall`,
   correct the ten sizes, and set the three label weights to 600/600/500. Free,
   and it changes every screen at once.
2. **Give the components their deck treatments** — `FloatingActionButtonDefaults`
   `containerColor = primary`, a `HorizontalDivider` under each `TopAppBar`, a
   pill shape for chips, `GUTTER = 16.dp`, `scrim = #06140A`. An afternoon.
3. **Add the capsule field and the two-up grid.** A small composable wrapping
   `BasicTextField`, plus a `FieldPair` at the call sites — `LabeledField` and
   `ChoiceField` are already the single chokepoint, so it is one new composable
   and a layout change, not nineteen rewrites. This is the item that decides
   whether the build looks like scheme E or like Material 3 wearing its colours,
   and it is also what makes Bean Detail fit on a screen (§5.3, §5.8).
4. **Pass short labels to `RadarChart`** at Home and brew-preview sizes. One
   argument; the parameter already exists (§5.7). While there, use the empty
   *caption* rather than the empty *net* on a new bean (§5.6g).
5. ~~**Vector the shipped mark** into `res/drawable/` and put it on
   `+2_profile_empty`, Home's bar and the splash.~~ Done for the two empty
   states, fourth pass; Home's bar and the splash remain (§5.6).
6. **Finish `ExtractionBar`** — centre tick, fill-from-centre, readout and the
   three zone labels. The words already exist in its `contentDescription`;
   sighted users should see what TalkBack says (§5.6h).
7. **Port the dripper glyphs** into Sessions rows, and add the extraction word to
   the row's meta line (§5.6f). `plan/dripper_icons/` is the source art.
8. Then the unbuilt surface: Share Card, heatmap, Images strip.

Items 1, 2 and 4 are hours and touch every screen at once — do them before
anything else, including before the blockers if a designer and an engineer can
work in parallel, because every screen built on the wrong scale has to be
revisited.

None of this is architectural. The app's structure is sound and the port stalled
at the presentation layer — which is why it is fixable in days rather than being
a rewrite, and why it should be fixed before more screens are added on top of the
wrong scale.

## 6. Documents that now contradict the code

Not nits: each of these would mislead the next person who reads the spec before
the source.

1. **`plan/scheme_e.py` `+2.1_create_account`** draws email/password sign-up, a
   sync data statement, and a **13+** affirmation. All three are dead: rule 60
   removed email, the no-server-storage architecture removed sync, and rule 82
   raises the age to 15 while naming this exact page as the contradiction. The
   page is also unreachable from `+2_profile_empty`, whose own docstring says
   there is one button and no second destination. **Retire the page** rather than
   leaving a deck frame that reads as the spec — and note that whatever replaces
   it is where B1's affirmation would naturally have lived.
2. **`plan/screens.md` §1** still lists an activity heatmap in Home's content and
   `BrewSessionDao.countByDate()` among its calls. The DAO exists
   (`SessionDao.dailyCounts`); the composable does not.
3. **`plan/screens.md` §9** still specifies avatar / Name / Email fields and an
   "OSS license attribution" row for Profile. Rules 60 and 103 killed all four,
   and the code correctly has none of them.

Also worth reconciling, less urgently: `plan/README.md` §Architecture states
"MVVM — one `ViewModel` per screen, `StateFlow`-exposed UI state". There is no
`ViewModel` in the module; state lives in `rememberSaveable` plus repository
flows collected in the composable, and `lifecycle-viewmodel-compose` is an unused
dependency. The choice is defensible for screens this size and `rememberSaveable`
genuinely does survive process death — but B3 is exactly the kind of bug a
per-screen ViewModel with an explicit save path makes harder to write, so the
divergence deserves a decision rather than silence.

---

## 7. The screenshots

`screenshots/` holds 33 PNGs at 1080×2400, one per reachable destination, sheet
and dialog. They are produced by `screenshots.py` from the same tokens, layout
order and literal strings as the Kotlin — **simulations, not captures**, for the
reason at the top of this file. Re-render with `python3 screenshots.py`.

They are faithful about: colour, type scale (the app's, **not** the deck's — see
§5.2), shape radii, control inventory, copy, and the order of things down the
page. They are approximate about: text line breaking, and any effect of real
device insets. They deliberately render D1's Canvas strokes at the *intended* dp
values, so they cannot be used to check that finding.

**Corrections, second pass.** The simulator was audited the same way the app
was: every string it draws was extracted and checked against the `.kt` sources
and against `coffee_server`. Three fabrications were found and fixed.

1. **A brand mark on `+2_profile_empty`.** The code draws no mark there — none
   exists in the module at all (§5.6). The helper is deleted and the frame
   re-rendered; it is emptier now. *(Fourth pass: the mark is back on that
   frame, and legitimately — `ProfileScreen.kt` draws it now. The simulator's
   `illustration()` does not re-draw it either; it parses the app's own
   `res/drawable/*.xml`, so a figure can only appear here if the resource the
   Kotlin points at exists.)*
2. **The access document's closing sentence.** The frame paraphrased it. That
   string is `what_is_not_here`, sent by `coffee_server/accounts.py`, and it is
   a legal statement about what exists — it now reads verbatim as the server
   sends it.
3. **The usage and quota keys.** The frame showed `read_labels` / `suggest_brew`
   (which are the *client's* `AiOperation.key` values, used only in
   `/v1/report`). The server meters under `vision` / `suggest` and quotes
   `DAILY_QUOTA` as `ask 60, suggest 60, vision 40`. Fixed to the real values.

The rule this establishes: the simulator may only draw what the Kotlin draws —
including when that is nothing, and including when the real string is uglier
than an invented one. Sample *data* (bean names, dates, counts) is fair to
invent, the way the deck invents its own; chrome, copy and server payloads are
not. Compare against `../plan/screenshots/scheme-e/` to see the gap, never
against this directory to reassure yourself there isn't one.

*(A residual, stated rather than fixed: `0.13_scan_review` shows six of
`ScanReviewSheet`'s nine fields. The sheet scrolls and the frame is the top of
it; Process, Roast date and Note are below the fold.)*

| File | Screen |
| --- | --- |
| `00_home` · `00_home_empty` | Home, populated and first-run |
| `0.1_bean_new` | Bean Detail, new — the scan card as hero |
| `0.2_bean_detail` · `0.2b_bean_detail_lower` | Bean Detail, saved, above and below the fold |
| `0.2c_flavor_manual` | the eleven-slider manual override sheet |
| `0.2d_delete_bean` · `0.2e_saved_snackbar` | cascade confirm; Snackbar save confirmation |
| `0.11_photo_source` | "Which photo?" — what replaced the deck's viewfinder |
| `0.11a_ai_disclosure_labels` | **the consent modal for photos** |
| `0.12_scanning` · `0.12b_scan_offline` · `0.12c_scan_blocked` | in flight; offline; rule 98's inline off-state |
| `0.13_scan_review` · `0.13b_scan_review_empty` | Scan Review, with a "was:" hint; the empty read |
| `+1_sessions` · `+1_sessions_empty` | the whole log |
| `+1.1_which_bean` · `+1.1b_which_bean_empty` | the sheet both FABs open |
| `+1.2_log_brew` · `+1.2b_log_brew_lower` | Brew Session, both halves |
| `+1.3_stage_editor` | the pour-stage sheet |
| `+1.4_ai_disclosure_suggest` | **the consent modal for text** |
| `+1.5_suggestion` · `+1.6_delete_brew` | the AI recipe; delete confirm |
| `+2_profile` · `+2_profile_empty` | Profile, signed in and out |
| `+2.2a_privacy` · `+2.2b_how_we_use_ai` · `+2.2c_report` | the legal screens and the report sheet |
| `+2.3_data_access` · `+2.4_delete_account` | Art. 15(3) access; Art. 17 erasure |

---

## 8. Recommended order of work

1. ~~**B3**~~ — done, 2026-08-15: see §3's status block.
2. ~~**D5**~~ — done: `room.schemaLocation` is set in `app/build.gradle.kts`.
3. ~~**B1**~~ — done, 2026-08-15: see §3's status block. Landed on
   `AiDisclosureSheet`, the recommended option.
4. **D1** — `.dp.toPx()` across `RadarChart` and `ExtractionBar`. Cheap, and
   invisible until someone runs it.
5. **D2, D3, D4** — three small honesty fixes on the three screens where a wrong
   statement is a store risk.
6. **§5.11 items 1–2** — the type scale and the component treatments. One file
   and an afternoon respectively, and together they are most of the visual gap
   between the build and the deck. Do these **before** any new screen is added,
   because every screen added first has to be revisited afterwards.
7. **§5.11 item 3** — the capsule field. The decision that settles whether this
   app looks like scheme E or like Material 3 in scheme E's colours.
8. ~~**B2**~~ — done, 2026-08-15: see §3's status block.
9. **B4** and TLS in front of `coffee_server` — release-configuration gates that
   are nobody's design problem but block everything downstream of them.
10. Then the unbuilt v1 surface: Share Card, the heatmap, the mark.
