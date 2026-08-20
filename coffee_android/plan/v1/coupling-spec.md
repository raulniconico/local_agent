# coffee_android v1 — coupling specification

> **What this is.** `design-spec.md` says what v1 *should look like and do*.
> This document says **what else moves when you change one thing**, and how to
> prove you found it all. Read it *before* editing anything under
> `../../v1/app/src/`, not after the review.
>
> It exists because roughly half the coupling in this app is not detectable by
> reading the file you are editing. Some of it crosses a language boundary into
> `coffee/` and `coffee_agent/`, some lives only in a doc comment, and some is
> a rule implemented identically in three places that share no identifier.

## Contents

- [0. The audit, in four steps](#0-the-audit-in-four-steps)
- [1. Chokepoints — the structural rule](#1-chokepoints--the-structural-rule)
  - [1.1 The directory boundary](#11-the-directory-boundary-is-itself-a-chokepoint)
- [2. The change → cascade table](#2-the-change--cascade-table)
- [3. Cross-project couplings](#3-cross-project-couplings)
- [4. Behavioural rules implemented more than once](#4-behavioural-rules-implemented-more-than-once)
- [5. State and lifecycle couplings](#5-state-and-lifecycle-couplings)
- [6. Verification commands](#6-verification-commands)
- [7. The reachability discipline](#7-the-reachability-discipline)
- [8. What this spec cannot cover](#8-what-this-spec-cannot-cover)
- [9. Keeping this document true](#9-keeping-this-document-true)

---

## 0. The audit, in four steps

Run this before *and* after the edit. It takes about a minute.

1. **Locate yourself against §1.** Are you editing a chokepoint or a caller of
   one? Chokepoint → audit every caller. Caller → usually audit nothing.
2. **Look your change up in §2.** The table is keyed by what you touched, not
   by what breaks.
3. **Grep the concept, not the symbol** (§3). Anything that crosses into
   `coffee/` or `coffee_agent/` shares a *column name* or a *file format*, never
   a function name. `grep -rn flavorAxesFor` finds two callers;
   `grep -rn flavor_source` finds the other three implementations.
4. **Run §6.** `check_design.py` and the Paparazzi goldens are the only
   automatic parts; everything else in this document is a grep you have to
   choose to run.

**Grep for your own name in comments.** This codebase records edges in prose:

```bash
grep -rn '<TheThingYouAreChanging>' --include=*.kt --include=*.py \
  coffee_android coffee coffee_agent | grep -v '/build/'
```

The hits inside comment blocks are the hand-written edge list — e.g.
`share/ShareCard.kt:160` names `CoffeeRepository.flavorAxesFor` as its
authority, and `data/Daos.kt:103` explicitly disclaims the decision
("the repository — **not this query** — decides that"). No call-graph tool
finds either.

---

## 1. Chokepoints — the structural rule

The app is built so that behavioural coupling is *structural*: one function
owns a decision and everything else routes through it. This is what makes the
question "what depends on this behaviour?" answerable at all.

| Chokepoint | Owns | Stated at |
| --- | --- | --- |
| `net/AiGateway.kt` | **All** network access for AI ops. Consent → connectivity → auth, in that order, once | `CoffeeCanApp.kt:71`, `AiGateway.kt:32` |
| `net/CatalogueGateway.kt` | The read-only, unmetered, consent-free endpoints | `CoffeeCanApp.kt` |
| `data/CoffeeRepository.kt` | All Room access. Screens never touch a DAO | `Daos.kt:103` |
| `CoffeeRepository.flavorAxesFor` | Manual-vs-averaged radar, for **every** consumer | `ShareCard.kt:160` |
| `media/ImageIngest.kt` | "THE ONE FILE IN THIS APP THAT EVER HOLDS EXIF" | `ImageIngest.kt:96` |
| `ui/AppLocale.kt` | Locale resolution, via `attachBaseContext` | `CoffeeCanApp.kt:33` |
| `consent/ConsentStore.kt` | Per-operation consent and its version | `AiGateway.kt:35` |
| `data/SyncBundle.kt` | The entire on-disk bundle format | `SyncBundle.kt:68` |
| `data/FlavorNoteSelection.kt` | The encoding of `sessions.flavorNotes`, and the five-per-axis cap | `FlavorNoteSelection.kt` |

**The rule.** Editing a chokepoint's *behaviour* obliges you to audit every
caller. Editing a caller obliges you to audit nothing — **unless** you
introduced a second path around the chokepoint, which is the one change this
architecture cannot absorb. A screen that calls `ServerApi` directly, or an
`open()` on a model-supplied path outside `_resolve()`, defeats the design
silently: nothing fails, and the guarantee is simply gone.

### 1.1 The directory boundary is itself a chokepoint

`coffee_android/` is split so that **what ships and what judges it never mix**:

| Directory | Contains | Invariant |
| --- | --- | --- |
| `../../v1/` | The Gradle module: Kotlin, resources, manifest, and the tests Gradle owns | Contains nothing that audits it |
| `../` (`plan/`) | The scheme E deck and its generators (`variants.py`, `wireframes.py`, `scheme_e.py`) and the superseded proposal | The design *target*, independent of any build |
| `.` (`plan/v1/`) | Specs, `check_design.py`, `screenshots.py`, simulator frames, `AUDIT.md` | **Reads `../../v1/`; never writes to it** |

Three rules follow, and each has bitten before:

1. **An audit artefact never lands in `../../v1/`.** A checker that ships is a
   checker a user can run and a reviewer stops trusting as independent. If you
   add a script, it goes here.
2. **The audit side is read-only over the module.** `check_design.py` and
   `screenshots.py` both resolve it as `APP = HERE.parent.parent / "v1"` and
   only ever `read_text()` it. A tool that rewrote the thing it checks could
   make itself pass.
3. **`../../v1/app/src/test/` is the deliberate exception.** Gradle resolves
   unit tests inside the module; the Paparazzi goldens physically cannot live
   here. So the module holds exactly one class of verification, and it is the
   one the build system forces.

Consequence worth stating plainly: **`../../v1/` is a shippable artefact on its
own, and `plan/v1/` is not runnable without it.** The dependency points one way.
If you ever find the module reaching into `plan/`, that is the boundary
breaking, and it breaks silently.

---

## 2. The change → cascade table

Keyed by what you edited. "Verify" columns are commands in §6.

### 2.1 Design tokens

| You changed | Also move | Verify |
| --- | --- | --- |
| A colour / type / shape value in `ui/theme/Theme.kt` | Nothing — **`../variants.py` `PURE_GREEN` is the source of truth**, not Theme.kt. Change the deck first, or record the divergence in `check_design.py`'s `ACCEPTED_DEVIATIONS` *with a rationale written into `Theme.kt`* | `V1`, then `V2` |
| A token in `../variants.py` | `Theme.kt`, and re-render the deck (`python3 ../scheme_e.py`) | `V1`, `V2` |
| Anything visual at all | 72 Paparazzi goldens re-record | `V2` |

`ACCEPTED_DEVIATIONS` is **not** a suppression list: an entry without a
decision recorded in `Theme.kt` is drift wearing a disguise. It still prints
both values on every run. Today it holds exactly one entry (`surface`).

### 2.2 Copy and localisation

| You changed | Also move | Verify |
| --- | --- | --- |
| Any user-facing string | `res/values/strings.xml` **and** `values-fr/` **and** `values-zh/` | `V3` |
| A string the mock deck also draws | `screenshots.py` — `check_design.py` diffs 91 strings against it | `V1` |
| Added a new string | All three locales; goldens; `LocaleScreenshotTest` renders all three | `V2`, `V3` |

Current parity: **496** keys in `values/`, **494** in each of `values-fr/` and
`values-zh/` (measured, 2026-08-19; the 444/442 recorded here before that was
already stale by 28 keys, which is the argument for measuring rather than
trusting this line). 122 of those were added on 2026-08-19 with the flavour-note
catalogue — 110 note names plus 12 for the picker — which is why the count
jumped from 322. The two deliberate gaps are `app_name` and `app_title_home` —
brand, untranslated on purpose. **Any third gap is a bug.**

The 110 note names are generated-shaped but hand-authored, and the three locales
were emitted from **one table** so a translation cannot go missing from one file
only. Adding a note means adding it to all three, in the same order.

Never hard-code a user-facing string in a composable. `check_design.py`'s copy
check reads `res/values/strings.xml`; a literal in Kotlin is invisible to it,
and invisible to two thirds of the users.

### 2.3 Data model

| You changed | Also move | Verify |
| --- | --- | --- |
| `data/Entities.kt` — added/renamed a column | Room `version` (currently **6**) + a new `Migration`; `data/Daos.kt`; **`data/SyncBundle.kt`** export *and* import; `../../../coffee_agent/sync_tools.py` `_BEAN_FIELDS`/`_SESSION_FIELDS`; `coffee/src/coffee_can/db.py` schema; `design-spec.md` §9 | `V4`, `V5` |
| …but a column on **`journeys`** | only the first three. `journeys` has no desktop counterpart and is **not** in the sync bundle, so the two Python legs of that row do not apply — `address`/`barista` (v6) touched Room, the entity and the screen and nothing else | `V4` |
| The bundle format | `SyncBundle.VERSION` **and** `sync_tools.BUNDLE_VERSION` — they must stay equal | `V5` |
| A DAO query | Whether `CoffeeRepository` should expose it at all; whether `TestFakes.kt` needs the new method | `V2` |
| An `AxisPage`, or which screen sits in a `+n` slot | **The number of every screen under it.** A deck number states *how a screen is reached*, so a screen that leaves the axis has to be renumbered into `0.x` and everything beneath it with it — routes in `ui/Nav.kt`, the frame names and `Canvas` titles in `screenshots.py`, `design-spec.md` §7.1's table and §8's headings, and any docstring quoting the old number (`grep -rn '+1\.' --include=*.kt`). A screen that becomes a push also gains a back arrow and **loses `AxisPageInsets`**, which nothing will fail on — Paparazzi renders every inset as zero | `V1`, `V1b`, `V2` |
| Which act a FAB performs | The other FAB, if they are meant to match. Home's and `0.3` Sessions' raise one sheet hoisted in `Nav.kt`; that hoisting is what makes "the same +" possible at all, and a screen that opened its own copy would drift silently | `V2` |
| A container that wraps a whole scrolling page (`Surface`, `Card`, `Modifier.clip`, `clipToBounds`) | Nothing else in code — but every touch below **8192px** of that node's own top stops arriving, while the page keeps drawing perfectly (`design-spec.md` §4.4). Paint the background instead of clipping it, and hand `LocalContentColor` down yourself | *device only — no command in §6 sees it* |
| A `HeroPhoto` implementation, or `PhotoHeroPage`'s image type | Both `BeanImageEntity` and `JourneyImageEntity` implement it, so a new member is a new **column** on two tables and a new migration, not just an interface change | `V2`, `V4` |
| Anything in `CanBoyEiffel` | `screenshots.py`'s `can_boy_eiffel()`, **by hand**. This is the one figure where the Kotlin is the original and the simulator is the copy — every other mascot is read out of `res/drawable/ic_mascot_*.xml` by `_vector()`, so it cannot drift. Nothing checks this one | `V1b` |
| A flavour note's key, or the per-axis cap | `ui/components/FlavorNotes.kt` (catalogue), `FlavorNoteSelection` (codec + cap), all three `strings.xml`, and **anything already stored** — a renamed key is silently dropped on decode, which reads to the user as their selection vanishing | `V2`, `V3` |
| `RadarChart`'s drawing geometry | `share/ShareCard.kt` draws through the same `drawRadar`; its `RadarStyle` is a second instance of the same data class, so a new field needs a default or the share card stops compiling | `V2` |
| `RadarChartSize`, or a radar's `size`/`labels` at a call site | The **three** in-app charts are one size and one label set by design (`design-spec.md` §5.3a): `HomeScreen` (inside `minOf(maxWidth, …)`), `BeanDetailScreen.RadarSection`, `BrewSessionScreen`. Also `plan/v1/screenshots.py` — `home`, `bean_new`, `bean_detail_lower`, `bean_detail_lower_empty`, `bean_detail_lower_background`, `brew_lower` all draw the number by hand | `V1b`, `V2` |
| An axis label, or a translation of one | `RadarChart` sizes its net from the **measured** labels, so a longer word shrinks every chart rather than clipping — re-record and *look at* `RadarChartLabelFitScreenshotTest`'s three locales, which is the only place that shrinkage is visible | `V2`, `V3` |

Migrations are **additive only** (see `CoffeeDatabase.kt:59`). A destructive
migration drops a user's brew log, and there is no server-side copy to restore
from — that is the direct consequence of `specs/legal-accounts.md` §3.8.

A **fourth** cross-language hop was added on 2026-08-19 and is easy to miss:
`sessions.flavorNotes` is carried by `SyncBundle` as `flavor_notes`, listed in
`sync_tools._SESSION_FIELDS`, whitelisted in `repo.SESSION_FIELDS`, and given a
column by `db.py`'s migration — **four files in three languages for one field**,
and the desktop renders none of it. The column exists there so a
phone → desktop → phone round trip does not quietly lose what the phone put
there; `_write_bean` swallows unknown fields, so omitting any one of those four
would have failed silently rather than loudly.

Two bundle invariants that fail silently rather than loudly:

- **Omit nulls; never write them.** An absent key means "no opinion". Writing
  an explicit null manufactures phantom conflicts against the other side's
  column default and stops a re-import from being a no-op.
- **Flavour axes travel on sessions, not just beans.** A bean with
  `flavor_source = "auto"` derives its radar by averaging sessions; ship the
  bean columns alone and it imports a bean that can never recompute one.

### 2.4 Network

| You changed | Also move | Verify |
| --- | --- | --- |
| `net/ServerApi.kt` | `coffee_server`'s route; `design-spec.md` §10.2–10.3; `../api.md` reasoning | `V6` |
| Added an endpoint | Justify it against `specs/legal-android.md` §4 rule 23 — **this app talks to that gateway and no other host, and that is a compliance rule, not a convenience** | `V6` |
| A call site that needs the network | Route it through `AiGateway` or `CatalogueGateway`. Never through `ApiClient`/`ServerApi` | `V6` |

Seven endpoints, and `/v1/ask` is **forbidden to this client** even though the
gateway still serves it (`ServerApi.kt:21`).

### 2.5 Consent, permissions, privacy

| You changed | Also move | Verify |
| --- | --- | --- |
| What is sent to the AI, or when | `ConsentStore` operation set; `AiDisclosureSheet`; `PrivacyScreen`; `specs/legal-android.md`; the Play Data Safety form | `V6` |
| The disclosure text materially | **Bump `ConsentStore.disclosureVersion`** (currently `1`) — `isLive()` compares it, so stale consent is correctly invalidated and re-asked | `V2` |
| A permission | `AndroidManifest.xml`; `design-spec.md` §11.4; Data Safety | manual |

`AiGateway.reportOutput` is **deliberately not consent-gated** — reporting is
how a user objects to output, and gating an objection behind consent is exactly
backwards (`AiGateway.kt:103`). Do not "fix" it into the `call()` path.

### 2.6 UI structure

| You changed | Also move | Verify |
| --- | --- | --- |
| Added a screen | `ui/Nav.kt` `Routes` + the arg-builder fn; a screenshot test; `design-spec.md` §8 | `V2` |
| Added an axis page | `ui/Axis.kt` `AXIS_PAGES` (`HOME_INDEX` derives itself); the bottom bar; `design-spec.md` §7.1 | `V2` |
| A screen's Scaffold | Keep it **per page, inside the pager** — hoisting it applies window insets twice (`Axis.kt:99`) | device only |
| A composable's look | Its golden(s). `grep -rn 'import app.coffeecan.*<Name>' app/src/test/` names the test that owns it | `V2` |
| A repository method a screen uses | Mark it `open` and add it to `TestFakes.kt` — screenshot tests substitute the repository (`CoffeeCanApp.kt:45`) | `V2` |

---

## 3. Cross-project couplings

These are the ones a within-module search misses entirely, because **no
identifier is shared across the boundary**. Grep the *concept*.

| Concept | Grep for | Lands in |
| --- | --- | --- |
| A bean/session column | the **snake_case DB column name** (`flavor_source`, `roast_date`) | `coffee_android` Kotlin, `coffee/src/coffee_can/db.py` + `repo.py`, `coffee_agent/sync_tools.py` |
| Bundle format | `BUNDLE_VERSION`, `SyncBundle.VERSION` | both sides; must be equal |
| Dropdown vocabulary | `Choices.kt` ← ported verbatim from `coffee/src/coffee_can/assets/*.json` | suggestions, **not** an enum — free text stays valid |
| Wire shapes | endpoint path string (`v1/suggest`) | `ServerApi.kt`, `coffee_server/schemas.py` |
| Design tokens | the hex value | `Theme.kt`, `../variants.py` |

**The asymmetry in sync conflict resolution is deliberate.** `coffee_agent`
adjudicates per bean because an agent is driving and can ask the user;
`SyncBundle.importFrom` **never overwrites** — new names insert, existing ones
are skipped and counted — because it has no way to put the question. Do not
unify these into one code path. Beans match **by name** (the two `id` sequences
are unrelated), so a rename imports as a second bean; that limitation is stated
in tool output rather than hidden, and should stay stated.

---

## 4. Behavioural rules implemented more than once

Where a rule genuinely could not be shared — different language, different
process — record it here so the copies can be diffed by hand.

### 4.1 Manual-vs-averaged flavour radar

| Side | Predicate | Where |
| --- | --- | --- |
| Android | `bean.flavorSource == FLAVOR_MANUAL` | `CoffeeRepository.kt:132` |
| Desktop | `flavor_source == "manual" and any(f is not None …)` | `bean_dialog.py:679,698,726`; `share_card.py:212` |

**These predicates differ**, and the difference is real: the desktop falls back
to the session average for a manual bean with all-null axes; Android draws a
blank radar captioned "manual".

Neither UI can currently produce that state — both write the axes *before*
flipping the flag (`BeanDetailScreen.kt:676`, `bean_dialog.py:706-708`) — so
this is **latent, not a live bug**. The path that could reach it is
`SyncBundle.kt:438`, which takes `flavor_source` straight off a bundle without
the guard. If you ever make manual-with-null-axes writable, close this first.

### 4.2 Where derived values must *not* be cached

`FlavorAverages` is computed per query and never stored (`Daos.kt:100`). A
cached mean goes stale the instant a session is edited, and nothing on screen
would tell the user which one they were reading. Same reasoning forbids caching
the radar into the bean row.

---

## 5. State and lifecycle couplings

**There is no `ViewModel` in this module.** State is `rememberSaveable` plus
repository flows collected in the composable. That moves a whole class of
coupling into places grep does not reach.

| Coupling | Consequence of missing it |
| --- | --- |
| `BeanDraftSaver` (`BeanDetailScreen.kt:1336`) has a `save` half and a `restore` half | Add a field to `BeanDraft` and update only `save`, and the field is silently dropped on rotation or process death. No test fails |
| Nullable floats cross the Bundle as `NaN` | A Bundle has no nullable-float list; `NaN` is the one value a 0..5 slider cannot produce. Don't switch to `-1f` |
| `CoffeeCanApp`'s `open val`s | Screenshot tests substitute an in-memory DB through them. A `val` that isn't `open` can't be faked |
| Consent → online → auth ordering in `AiGateway.call` | Reordering leaks a request before consent is confirmed |
| Locale via `attachBaseContext` | Strings resolved off a raw context come back in the *device* language while the screen around them is in the chosen one (`CoffeeCanApp.kt:33`) |

---

## 6. Verification commands

**The checks run from two different directories**, which is the practical face
of the boundary in §1.1: the standalone Python tooling lives on the audit side,
and the Gradle tasks must run inside the module because Gradle owns them.

```bash
# ============ from coffee_android/plan/v1/  (the audit side) ============

# V1 — design tokens + mock copy fidelity (36 colour, 11 type, 5 shape, 88 strings)
python3 check_design.py            # must exit 0

# V1b — redraw the simulator frames after any copy or visual change
python3 screenshots.py             # -> screenshots/*.png

# ============ from coffee_android/v1/  (the module) ============

# V2 — Paparazzi goldens (72).  SEE THE TWO WARNINGS BELOW.
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64   # NOT the default JDK -- see below
./gradlew :app:verifyPaparazziDebug                 # verify against the 72 goldens
./gradlew :app:recordPaparazziDebug                 # re-record, then READ the diff
./gradlew :app:testDebugUnitTest                    # goldens + geometry + ingest tests

# V3 — locale parity: must print exactly app_name and app_title_home, nothing else
cd app/src/main/res && for L in fr zh; do echo "== $L =="; comm -23 \
  <(grep -o 'name="[^"]*"' values/strings.xml   | LC_ALL=C sort -u) \
  <(grep -o 'name="[^"]*"' values-$L/strings.xml | LC_ALL=C sort -u); done

# V4 — Room schema/migration
grep -n 'version = \|MIGRATION' app/src/main/java/app/coffeecan/data/CoffeeDatabase.kt

# V5 — bundle format parity across the two projects
grep -rn 'BUNDLE_VERSION *=\|const val VERSION' \
  app/src/main/java/app/coffeecan/data/SyncBundle.kt ../../coffee_agent/sync_tools.py

# V6 — the app's whole network surface; nothing may appear outside this file
grep -rn '@GET\|@POST\|@DELETE' app/src/main/java/app/coffeecan/net/ServerApi.kt
grep -rn 'ServerApi\|ApiClient' app/src/main/java/app/coffeecan/ui/   # must be empty
```

### V2 needs JDK 17 explicitly

The default JDK on this machine is **25.0.3**, which this toolchain cannot
parse: `JavaVersion.parse` throws `IllegalArgumentException: 25.0.3` before any
of this project's code is looked at. The failure is not a helpful one — the
build aborts in under a second with the bare message `25.0.3` and no stack
trace, which reads like a corrupt install rather than a toolchain mismatch.
JDK 17 is installed alongside it; set `JAVA_HOME` as in V2 above and every
Gradle task works.

### The `compileSdk` flip is part of V2, and it is easy to leave broken

Paparazzi 1.3.5 cannot render at `compileSdk = 36` — its `android.os.Build`
reflection shim throws before a composable draws. The documented workflow
(`app/src/test/java/app/coffeecan/screenshot/PaparazziEnvironment.kt:20`) is to
flip `compileSdk` to **35 for the duration of a screenshot run and restore 36
immediately after**. `targetSdk` stays 36 always — that one is
`specs/legal-android.md` §4 rule 18 and it ships.

```bash
grep -n 'compileSdk\|targetSdk' app/build.gradle.kts   # compileSdk MUST read 36 at rest
```

Run that after every screenshot session. It is the single easiest coupling in
this repo to leave in the wrong state, because nothing fails when you do.

---

## 7. The reachability discipline

A grep hit is a *candidate*, not a finding. Before reporting or "fixing":

1. **Can the divergent state actually be produced?** Trace every writer. §4.1 is
   the worked example — two genuinely different predicates, and no writer that
   reaches the gap.
2. **If not reachable today, what would make it reachable?** Say so, and label
   the finding **latent** rather than a bug. A latent divergence with the path
   named is useful; a bug report that turns out to be unreachable burns the
   reader's trust in the next one.
3. **Only then** decide whether unifying is right. §3's conflict-resolution
   asymmetry is a case where two different behaviours are *correct* and merging
   them would be the regression.

---

## 8. What this spec cannot cover

Be explicit about this in any review that claims a change is verified.

| Not covered | Why | What would cover it |
| --- | --- | --- |
| Window insets | layoutlib has no window; `design-spec.md` §4.3 | a physical device |
| Gesture timing, pager fling | Paparazzi renders one static frame | a physical device |
| Share targets | needs a real chooser | a physical device |
| Room migration on real data | tests build fresh DBs | a device upgraded from v2 |
| Anything sequential | goldens prove layout, never order | reading the composable top to bottom |
| **Flow-emission timing** | `TestFakes` fakes every query with `flowOf(...)`, which emits **synchronously** on collection; Room emits asynchronously. Any bug that depends on "the query has not answered yet" is structurally invisible to every screenshot test | reading the hydration path, or a device |

**The `flowOf` gap is not hypothetical** — it hid a dead feature for months.
`BrewSessionScreen`'s recipe reuse read `previous` off `collectAsState`'s
*initial* value and set `hydrated = true` regardless, so on a real device the
pre-fill never ran and every new brew opened blank; under Paparazzi the fake
emitted before the effect body and it always looked correct. When you write a
`LaunchedEffect` that consumes collected state, ask what that state holds on the
frame the effect first runs, and treat "empty" and "not loaded" as different
values — `collectAsState(initial = null)` is how you keep them apart.

**`screenshots/*.png` is not evidence.** 16 of its 44 PNGs match a current
golden; 28 have drifted, several of them still labelled real captures in
`REAL_CAPTURES.md`. Trust, in order: `../../v1/app/src/test/snapshots/images/`
(72, always current with the last run) → `../../../docs/screenshots/` (device)
→ that directory last. Never validate a design claim against it.

---

## 9. Keeping this document true

This file is only worth reading if it is accurate, and a coupling spec decays
faster than the code it describes.

- Add a row when you create a coupling that a reader of one file could not
  infer from that file.
- **Delete a row when you remove the coupling.** A stale entry sends the next
  reader to audit something that no longer exists, which is how a checklist
  stops being read at all.
- Prefer making a coupling *structural* (route it through a chokepoint in §1)
  over documenting it here. A row in this table is the fallback for coupling
  that could not be designed away — not the goal.
- When a count in this document changes (496/494 strings, 72 goldens, Room
  version 3, `disclosureVersion` 1), update it in the same commit. Those
  numbers are the tripwires; a wrong one is worse than none.
