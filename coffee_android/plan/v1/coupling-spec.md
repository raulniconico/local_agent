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

- [0. The audit, in five steps](#0-the-audit-in-five-steps) — **start here; step 0 decides how much of the rest you owe**
- [1. Chokepoints — the structural rule](#1-chokepoints--the-structural-rule)
  - [1.1 The directory boundary](#11-the-directory-boundary-is-itself-a-chokepoint)
- [2. The change → cascade table](#2-the-change--cascade-table)
- [3. Cross-project couplings](#3-cross-project-couplings)
- [4. Behavioural rules implemented more than once](#4-behavioural-rules-implemented-more-than-once)
- [5. State and lifecycle couplings](#5-state-and-lifecycle-couplings)
- [6. Verification commands](#6-verification-commands) — `./audit.sh`
- [7. What this spec cannot cover](#7-what-this-spec-cannot-cover) — read before claiming a change is verified

Method and process moved to `AUDIT.md` §9 on 2026-08-29 — the reachability
discipline (a grep hit is a candidate, not a finding) and the rules for keeping
this file true. Neither is about a change you are making right now, and this
document is read while you are making one.

---

## 0. The audit, in five steps

Run this before *and* after the edit. Step 0 is new, and is the one that
decides how much of the rest you owe.

### Step 0 — does this change touch a coupling at all?

Most edits do not. If **all** of these are true —

- it adds no user-facing string, design token, database column, endpoint,
  permission, or generated file;
- it changes no public signature, no chokepoint's *behaviour* (§1), and no
  constant another file derives from (§2.6 lists them);
- it stays inside one file's own drawing or logic;

— then you owe **step 4 only**: `./audit.sh`, and eyes on the frames if it is
visual. Say so in the change description rather than implying the whole audit
ran. A page-turning arm inside one mascot composable is exactly this case.

Anything else, or any doubt, is steps 1–4. The steps are cheap; it is *reading
all of §2* that is not, and step 0 exists so the table can stay long.

### Steps 1–4

1. **Locate yourself against §1.** Are you editing a chokepoint or a caller of
   one? Chokepoint → audit every caller. Caller → usually audit nothing.
2. **Look your change up in §2.** The table is keyed by what you touched, not
   by what breaks. Read your row, not the table.
3. **Grep the concept, not the symbol** (§3). Anything that crosses into
   `coffee/` or `coffee_agent/` shares a *column name* or a *file format*, never
   a function name. `grep -rn flavorAxesFor` finds two callers;
   `grep -rn flavor_source` finds the other three implementations.
4. **Run `./audit.sh`** (§6). Five checks, one exit code. What it cannot see is
   §7, and a green run is not a verified change.

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
| Anything visual at all | 84 Paparazzi goldens re-record | `V2` |

`ACCEPTED_DEVIATIONS` is **not** a suppression list: an entry without a
decision recorded in `Theme.kt` is drift wearing a disguise. It still prints
both values on every run. Today it holds exactly one entry (`surface`).

### 2.2 Copy and localisation

| You changed | Also move | Verify |
| --- | --- | --- |
| Any user-facing string | `res/values/strings.xml` **and** `values-fr/` **and** `values-zh/` | `V3` |
| A string the mock deck also draws | `screenshots.py` — `check_design.py` diffs 110 strings against it | `V1` |
| Added a new string | All three locales; goldens; `LocaleScreenshotTest` renders all three | `V2`, `V3` |

Current parity: **545** keys in `values/`, **543** in each of `values-fr/` and
`values-zh/` (measured, 2026-08-26; the 505/503 recorded here before that was
stale, as the 444/442 before it was — which is the argument for measuring
rather than trusting this line). 122 of those were added on 2026-08-19 with the flavour-note
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
| `data/Entities.kt` — added/renamed a column | Room `version` (currently **15**) + a new `Migration`; `data/Daos.kt`; **`data/SyncBundle.kt`** export *and* import; `../../../coffee_agent/sync_tools.py` `_BEAN_FIELDS`/`_SESSION_FIELDS`/`_STAGE_FIELDS`/`_JOURNEY_FIELDS`; `coffee/src/coffee_can/db.py` schema **and `_migrate`**; `coffee/src/coffee_can/repo.py`'s matching `*_FIELDS` allowlist; `design-spec.md` §9 | `V4`, `V4b`, `V5` |
| …but a column on **`journeys`** | **all of it, since 2026-08-23.** This row used to say "only the first three" because `journeys` had no desktop counterpart; it has one now (`coffee_can.db`'s `journeys`/`journey_images`, storage-only — the desktop still has no café screen and gains none), and the bundle carries cafés. Treat a journey column exactly like a session column | `V4`, `V4b`, `V5` |
| The bundle format | `SyncBundle.VERSION` **and** `sync_tools.BUNDLE_VERSION` — they must stay equal | `V5` |
| A DAO query | Whether `CoffeeRepository` should expose it at all; whether `TestFakes.kt` needs the new method | `V2` |
| An `AxisPage`, or which screen sits in a `+n` slot | **The number of every screen under it.** A deck number states *how a screen is reached*, so a screen that leaves the axis has to be renumbered into `0.x` and everything beneath it with it — routes in `ui/Nav.kt`, the frame names and `Canvas` titles in `screenshots.py`, `design-spec.md` §7.1's table and §8's headings, and any docstring quoting the old number (`grep -rn '+1\.' --include=*.kt`). A screen that becomes a push also gains a back arrow and **loses `AxisPageInsets`**, which nothing will fail on — Paparazzi renders every inset as zero | `V1`, `V1b`, `V2` |
| Which act a FAB performs | The other FAB, if they are meant to match. Home's and `0.3` Sessions' raise one sheet hoisted in `Nav.kt`; that hoisting is what makes "the same +" possible at all, and a screen that opened its own copy would drift silently | `V2` |
| A container that wraps a whole scrolling page (`Surface`, `Card`, `Modifier.clip`, `clipToBounds`) | Nothing else in code — but every touch below **8192px** of that node's own top stops arriving, while the page keeps drawing perfectly (`design-spec.md` §4.4). Paint the background instead of clipping it, and hand `LocalContentColor` down yourself | *device only — no command in §6 sees it* |
| A `HeroPhoto` implementation, or `PhotoHeroPage`'s image type | Both `BeanImageEntity` and `JourneyImageEntity` implement it, so a new member is a new **column** on two tables and a new migration, not just an interface change | `V2`, `V4` |
| Anything in `CanBoyEiffel` | `screenshots.py`'s `can_boy_eiffel()`, **by hand**. This is the one figure where the Kotlin is the original and the simulator is the copy — every other mascot is read out of `res/drawable/ic_mascot_*.xml` by `_vector()`, so it cannot drift. Nothing checks this one | `V1b` |
| A new mascot pose, or an animated knob on one | **A strip in `MascotPoseSheetTest`.** Every other golden captures a figure at knob = 0, so the motion is drawn by code no test renders — that is how `CanBoyNews` grew an arm under 84 passing goldens. Also: a screen that *contains* an animated figure should freeze it under `LocalInspectionMode` (`ReadingCanBoy`, `PolaroidCard`'s flash) so its own golden holds a stated frame | `V2` |
| `CanBoyNews`'s `page`, its hand, or `newsLeaf` | **`NewsScreen`'s `ReadingCanBoy`, which must keep feeding `page` linearly** — since 2026-08-29 the knob is the whole gesture's clock (reach, carry, release), not the leaf's angle, so an easing on the driver eats the reach; the figure eases its own phases. The hand and the leaf must both keep reading `newsCorner`, or the grip drifts off the paper it is holding. `scheme_e.py`'s `can_boy_news` is three passes behind and is **not** the description (§12.3 of `design-spec.md`) | `V2` — but note it renders `page` = 0 only, so it proves the reading pose and **nothing about the turn**: the moving frames are eye-checked |
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

**The `beans` table is the same story, and it is the one to copy.** `farm` and
`frozenDate` were added on 2026-08-26 and every row of the table above fired at
once: `Entities.kt`, `MIGRATION_12_13` (Room **13**), both halves of
`SyncBundle` with `VERSION` → **6**, `sync_tools._BEAN_FIELDS` and
`BUNDLE_VERSION` → 6, `db.py`'s `SCHEMA` *and* its `_migrate` loop,
`repo.BEAN_FIELDS`, and `design-spec.md` §9. `check_schema_parity.py` is what
proves the set is complete — it went from 108 columns to 110 and stayed green,
which is the only evidence that neither column joined `humidity` in the
silently-not-travelling category.

`beans.region` ran the same course on 2026-08-29 — Room **14**
(`MIGRATION_13_14`), `SyncBundle.VERSION` and `BUNDLE_VERSION` → **7**,
`db.py`, `repo.BEAN_FIELDS`, `sync_tools._BEAN_FIELDS`, §9 — and parity went
110 → **111**. `session_stages.velocity` ran it again on
2026-08-30 — Room **15** (`MIGRATION_14_15`), `VERSION`/`BUNDLE_VERSION` →
**8**, `db.py`, `sync_tools._STAGE_FIELDS`, §9 — and parity went 111 →
**112**. It is the first one on the *stage* table rather than on `beans` or
`sessions`, and the only row of the table that behaved differently is
`repo.py`: a stage is written through `add_stage`/`update_stage`, which take
arguments rather than reading a `*_FIELDS` allowlist, so the column had to be
added to both signatures **and** both SQL statements. `update_stage` is a
full-row update, so a caller that omits the new argument clears the column —
the docstring says so at the point where it matters.

`session_stages.endSec` ran the identical course on 2026-08-31 — Room **16**
(`MIGRATION_15_16`), `VERSION`/`BUNDLE_VERSION` → **9**, `db.py`'s `SCHEMA`
*and* `_migrate`, both `repo.add_stage`/`update_stage` signatures and their SQL,
`sync_tools._STAGE_FIELDS`, both halves of `SyncBundle`, §9 — and parity went
112 → **113**. It is worth reading beside `velocity` rather than instead of it:
the two are the same row of this table fired one day apart on the same table,
which is what a well-behaved column addition looks like when the map is
followed. What made this one arrive at all is a **UI** change (the Pour stages
timer, §8.8), which is the direction to watch: an interaction that can measure
something new is a schema change wearing a screen's clothes, and the cascade is
owed in full.

The one row it deliberately did *not* fire is §2.3b: `region`
is excluded from `repo.LABEL_FIELDS`, so no OCR prompt and no server schema
moved. That exclusion is the decision, not an oversight, and `LABEL_FIELDS`
says so at the point of exclusion.

The evidence for that rule is five fields that quietly stopped travelling and
were repaired in bundle v4 (2026-08-23) — including `sessions.humidity`, which
had a column on **both** sides the whole time and simply was not on
`sync_tools._SESSION_FIELDS`, an allowlist and not a reflection of the table.
Nothing failed; the data did not arrive. The blow-by-blow is `AUDIT.md` §9.3,
and its shape is worth knowing: **no Room column changed**, so no migration was
owed and the row above keyed on `Entities.kt` never fired — the one keyed on
"the bundle format" did.

The lesson for the table above: when you add a column, the failure you are
guarding against is not a crash. It is a field that quietly stops travelling,
which surfaces months later as "my phone did not get my brews".

Two bundle invariants that fail silently rather than loudly:

- **Omit nulls; never write them.** An absent key means "no opinion". Writing
  an explicit null manufactures phantom conflicts against the other side's
  column default and stops a re-import from being a no-op.
- **Flavour axes travel on sessions, not just beans.** A bean with
  `flavor_source = "auto"` derives its radar by averaging sessions; ship the
  bean columns alone and it imports a bean that can never recompute one.

### 2.3b The scan field list

| You changed | Also move | Verify |
| --- | --- | --- |
| The fields `/v1/vision` returns | `coffee_server/prompts.py` `BEAN_FIELD_NAMES` + `BEAN_FIELD_LABELS` (the output schema and the Qwen key list are generated from the first), `coffee_server/schemas.py` `BeanFields`, `net/ServerApi.kt` `BeanFieldsDto`, `net/AiGateway.kt`'s `suggestBrew` mapping, `ui/components/ScanReviewSheet.kt` (**two** lists: the field map and `labels()`), `BeanDraft.asMap` **and** `BeanDraft.merging`, `design-spec.md` §8.5 | `V2`, `V7` |
| `coffee_can.repo.BEAN_FIELDS` | Whether the new column belongs on `repo.LABEL_FIELDS` — it is **opt-out**, so a column lands on all three desktop OCR prompts unless the exclusion list says otherwise | `V7` |

**`LABEL_FIELDS` is why that second row exists.** The three desktop OCR modules
used to filter `BEAN_FIELDS` themselves with `"flavor_" not in field`. When
`frozen_date` was added on 2026-08-26 that substring test let it straight
through, and `ocr.py`, `claude_ocr.py` and `qwen_ocr.py` all began asking a
vision model to read a freezer date off a coffee bag — nothing failed, and the
model dutifully returned `""` every time. One derived tuple with its exclusions
written down replaced three copies of the test.

The server's `BEAN_FIELD_NAMES` is a **hand-written copy** of that tuple:
`coffee_server` does not import coffee-can and should not start. Nothing checks
the two agree, which puts this pair in §4 rather than §1.

### 2.4 Network

| You changed | Also move | Verify |
| --- | --- | --- |
| `net/ServerApi.kt` | `coffee_server`'s route; `design-spec.md` §10.2–10.3; `../api.md` reasoning | `V6` |
| `app/build.gradle.kts`'s `buildConfigField` URLs and emails | **`../v1/check_design.py`'s `COMPOSED` set** — the app assembles `"Questions: " + BuildConfig.SUPPORT_EMAIL` at runtime, so the deck's literal is pinned there rather than in `strings.xml`. Change the email without changing that entry and the drift check fails. Also `screenshots.py` and `scheme_e.py`, which draw the same strings | `check_design.py` |
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
| `SectionSpacing`, or where a section is spaced from the one above it | **`plan/v1/screenshots.py`'s `SECTION_SPACING`**. And keep it on the callers: folding it into `SectionHeader` would indent every page-opening heading by 20dp for nothing. `grep -rn 'Spacer(Modifier.height([0-9]*\.dp))' --include=*.kt app/src/main` next to a `SectionHeader` is the check — five loose literals is what this token replaced | `V1b`, `V2` |
| `ContributionCalendar`'s `GridTop`, `Enlarge`, or its row pitch | **`ContributionCalendarHeight`**, which is derived from all three, and `screenshots.py`'s `heatmap()` `grid_top` plus `home()`'s card height — the deck draws both by hand in its own unscaled coordinates. The component owns the whole card interior and takes **no padding modifier**, so a height that stops tracking it shows up as trailing white, not as a clipped legend, and nothing fails | `V1b`, `V2` |
| `SectionHeaderGap`, or `SectionHeader`'s own padding | **`plan/v1/screenshots.py`'s `SECTION_GAP`**, which `section()` returns. And check no caller has re-grown a `Spacer` after a heading: `grep -rn -A1 'SectionHeader(' --include=*.kt app/src/main \| grep Spacer` must be empty — the composable owns the gap, and a caller adding its own is exactly how the app came to have three different ones | `V1b`, `V2` |
| A card placed directly under a `SectionHeader` | Pad it with **`SectionCardPadding`**, never a symmetric `16.dp` — the heading already paid the top. `for f in ui/screens/*.kt; do awk '/SectionHeader\(/{h=NR} h && NR<=h+14 && /padding\(/ {print FILENAME":"NR}' $f; done` lists every card interior within reach of a heading; anything in that list not using the token is drift. Also `screenshots.py`'s `SECTION_CARD_TOP`, which the three deck frames that draw a card interior read | `V1b`, `V2` |
| The `action`/`secondaryAction` slot, or what `SectionHeader` puts in it | `SectionActionSlack` assumes a **48dp** `TextButton` against a **24dp** text box, and subtracts the difference from the gap **at both ends** — the padding above the heading as well as the spacer below. Taking it off only one end leaves headings with a verb sitting 12dp low, which is what shipped for a day. Swap the button for anything of another height and every heading with a verb silently drifts from every heading without one — the failure this constant exists to stop, and one no golden catches on a heading whose action happens to be absent in the fixture | `V2` |
| `SessionGlyph`, `ShelfTile`, or `ShelfCardPadV` | The height derived from it — `SessionCardHeight` follows `SessionGlyph`, `ShelfCardHeight` follows `ShelfTile`, and **each is `artwork + 2 * ShelfCardPadV`**. Do not re-point one at the other's total: they are the same *rule*, not the same number, and conflating them is what put 44dp of air in a brew row. Also `screenshots.py`'s `session_card` `h`, which draws the number by hand | `V1b`, `V2` |
| `RadarLabelTrim`, or a radar call site's zoom/notes | The trim assumes **white** at the box's top and bottom edges, so a call site with `zoomable = true` or a non-empty `noteLabels` must not use it — the brew form's is the one that cannot. **Nor may anything else be pinned in that box's top or bottom corners**: Home's "Average across N sessions" was, and the trim brought "Ferment" onto its line until the caption moved to the heading's `caption` slot. Trim and corner label want the same 20dp; only one may have it | `V2` — *and look at the frame, since a clipped label still renders as a plausible chart* |
| `ImagesPerLine`, `ImageGap`, or `ImagesStrip`'s tile arithmetic | **`plan/v1/screenshots.py`'s `image_tile()`**, which divides `W`/`GUTTER` the same way and would otherwise draw a tile size no handset produces. The drag's step pitch is derived from the same number *inside* the composable — if you reintroduce a constant there, a reorder displaces at the wrong distance on every screen but the one it was tuned on | `V1`, `V1b`, `V2` |
| `AxisFootFade`, or `AxisBarClearance` | Both pages that emit the fade — `NewsScreen` and `HomeScreen` — get it from the one composable, so a change to the gradient is automatic. What is **not** automatic: the fade's height is `AxisBarClearance` plus its ramp, so anything that changes the bar's own height or margin moves the fade on both pages, and a page that pads its content by `AxisBarClearance` (every axis page must — `Axis.kt`) moves with it too. Do not "unify" `axisChromeScrimFoot` into this: `+1` fades to 88% to sit under a white FAB, this fades to 100% to sit under a translucent bar | *device only — Paparazzi renders every inset as zero, so `AxisBarClearance` collapses and the fade lands in the wrong place in a golden* |
| The axis bar's chrome — `AxisChromeAlpha`, `axisChromeSheen`, `AxisBarShadow`, its `CircleShape` | **`PhotoHeroPage`'s `FloatingHeroButton`**, which since 2026-08-25 is the same capsule at `HeroButtonSize`. They are one object appearing twice and share the tokens, not the numbers — so this cascade is automatic *provided* nobody re-inlines a literal. `grep -rn 'shadowElevation = \|alpha = 0\.8' --include=*.kt app/src/main` catches a re-inlined one | `V2` |
| Styling a control by putting `background`/`shadow`/`size` on the modifier passed **to** an M3 `IconButton` | Nothing — and that is the trap. The button appends `minimumInteractiveComponentSize()` after your modifier, so the node is placed at 48dp and your background paints at 48dp however small you sized it. `HeroButtonSize` read 40 and rendered 48 for months, and an edit to 34 changed nothing visible. Put the painted shape in the **content slot** instead | *device or golden only — the source reads as if it worked* |
| `HeroButtonSize`, `HeroButtonTouch` or `HeroButtonMargin` | **`HeroButtonClearance`** follows on its own — but only because `0.2` and `0.31`'s pinned title bars now read it. They carried `72.dp` by hand until 2026-08-25, when the buttons shrank and the bars kept insetting for the old ones. Nothing failed; the label just sat further in than it needed to | `V2` |
| A top bar to or from the frosted treatment (`axisChromeScrim` + `axisChromeSheen`, `Color.Transparent`) | **Drop `TopBarDivider`** — the graded scrim replaces the rule, and drawing both is a soft edge with a hard one on top. And spend the bar's height as a **spacer inside the scroll**, never as `.padding(padding)`: top padding fills the strip behind the bar with the page's own background, so the frost lands on a flat colour and reads as solid again. `JourneysScreen` (as `contentPadding`) and `JourneyDetailScreen` (as a `Spacer`) are the two worked examples | `V2` |
| `GlassPanel`'s fill, sheen or edge | `axisChromeSheen` has **three** consumers now — the axis bars, `DetailActionBar` and this — so a change to the gradient moves all of them. That is the intent (one frosted material), but it means a tweak made for Home's panes lands on the bar over every other screen. `GlassFillAlpha` is the pane's own and is the knob to reach for | `V2` |
| `GlassBackdropHost`, or removing it from a page | **Every `glassSurface` on that page stops working.** The surface is translucent over `background` = #FFFFFF, so with no backdrop it is a white rectangle on a white page and a blur of it changes nothing — which is what was reported twice. `BackdropAlpha` and `BackdropVeil` move together: the veil keeps it a white page, the alpha leaves the blur something to move around. **Two callers now** (`00` Home, `-1` Can read) and they are two pages of one pager: change one and change the other, or the material shifts mid-swipe | *device only, with real photos on the shelf — `TestFakes` beans have no image files, so every Home and News golden records this as plain white* |
| `Modifier.glassSurface`, or `GlassPanel` | `GlassPanel` is a thin wrapper over the modifier now, so a change to the material reaches Home's three panes **and** every newspaper sheet on `-1`. The shape argument is used for the clip *and* the border — pass one and you have changed both. Order in the chain is load-bearing twice: `clip` before `drawBehind` (or the blurred copy paints full-screen out from the corner) and the fill *after* the backdrop (or the glass is a blurred picture with an opaque sheet in front of it) | `V2` for layout, *device* for the material |
| A glass surface's `fill` (light ↔ dark) | **Every colour inside it.** A dark fill needs `inverseOnSurface` ink, rules as that ink held back, and any icon tinted `primary` re-pointed — `NewspaperCard` had to move all three, and the one that bit was `OpenMark`, whose #196D2E went invisible on grey. It also sets the *alpha floor*: white text has to clear 4.5:1 against whatever the fill mixes to over the backdrop, which is what pins `NewsprintGlassAlpha` at 0.74 and what `FrostRadiusPx` was raised to compensate for | `V2` for the frame, and **check the contrast by hand** — no check in this repo measures it |
| The two `GraphicsLayer`s in `HomeScreen`, or `LocalGlassBackdrop` | A pair; neither works alone. `backdrop` is drawn sharp as the page, `frosted` is `drawLayer(backdrop)` under the `BlurEffect` and is what each pane paints behind itself — collapse them into one and you get either a blurred page or an unblurred pane. `clip` must stay **before** `drawBehind` in the pane's chain or the copy paints full-screen from the pane's corner. Both origins are measured, never assumed | *device only* |
| `GlassPanel`'s `contentPadding`, or giving Home's panes horizontal padding | **`ContributionCalendar` loses weeks, silently.** It clamps `cols = min(weeks, (width − inset) / pitch)` with a *fixed* cell size, so a narrower pane draws fewer columns rather than a smaller grid — and the golden still records, just with less history in it. The shelf is the other half: its cards were widened out of the gutter by direct request, and pane padding insets them again. Both panes bleed, and each heading pays `GlassPadH` itself | `V2` — *and count the month labels in the frame* |
| Anything in `BrewSessionScreen`'s panel body | **It renders twice** — as `0.31` the destination and as the card over `0.2` (`BrewPresentation`, `design-spec.md` §8.8a). The frame is the only thing `BrewCanvas` varies, so a section added to the body appears in both whether or not you meant it to; the two places that *are* presentation-specific are the headline row's close button and `beanBlockShown`'s leading `!asCard`. Goldens: `BrewSessionScreenScreenshotTest` **and** `SessionCardOverlayScreenshotTest` | `V2` |
| `CardOverlay`'s scrim, inset or `pageBehindCard`'s radius | The **pair** of scrim alphas, not one of them: 0.40 rides on a real `blur` (API 31+), 0.55 is the whole effect on 26..30, and changing one without the other makes the card mean two different amounts of "behind". `Modifier.blur` is silently a no-op below 31 — the same wall `AxisChromeAlpha` documents. The recipe is `coffee_website/style.css`'s `.lb-scrim`; move them together or say why not | `V2` for the 31+ half — layoutlib **does** apply the `RenderEffect`, which was guessed wrong once. The 26..30 half is *device or emulator on 11 or older*, and nothing renders it |
| `CardOverlay`'s entrance or exit | The golden's `LocalInspectionMode provides true`, which is what makes the card photograph at its resting state — Paparazzi's frame clock never advances, so a card that animates in is otherwise captured invisible and the golden silently becomes a picture of the blurred page. `CardOverlay` reads the flag itself; the test supplies it. Same trap, same answer, as `FlavorNoteSheetScreenshotTest` | `V2` — *and the failure mode is a golden that records successfully and shows nothing* |
| `DetailActionBar`'s `navigationBarsPadding` | `insetNavigationBar`, which the card passes `false` — its foot is already inset from the safe area by `CardOverlay`. A bar that pays the inset unconditionally floats a gesture-bar's height up inside its own card, and no golden sees it: Paparazzi renders every inset as zero | *device only* |
| Which of `0.31`'s three paths draws `BeanDetailsSection` | `BrewSessionScreen.beanNamed` is read **once, at hydration, off the stored row** — `beanDraft.name` changes as the user types and would tear the block off mid-word. The `cup ||` in front of it is load-bearing: `photosOutsideFold` is a cup's only door to a photograph. The deck mirrors the split — `screenshots.py`'s `bean_block` for the blank-bean frames, `bean_summary` for `0.31` | `V1b`, `V2` |

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
| **News item shape** | the JSON key (`title`, `source`, `url`, `published_at`, `excerpt`) | `crawler.py`'s `_refresh_news` → `schemas.NewsItem` → `ServerApi.kt`'s `NewsItemDto` → `NewsItemEntity` (**and a Room migration**) → `NewsFeed.kt`'s mapper → `NewspaperCard`. **Five hops, and the middle three are silent on failure**: a field added at either end without the others simply never arrives, and nothing errors |
| **What may appear on a news card** | `EXCERPT_MAX_CHARS`, `_BOILERPLATE` | `crawler.py`. Five fields since the 2026-08-24 override of `legal-accounts.md` rule 74 — headline, source, date, link, and the publisher's **verbatim** standfirst. **Adding a sixth is a legal change, not a schema change**, and rewriting the fifth with a model is the specific act rule 74 still forbids. The 200-char cap lives server-side on purpose: capping in the app would still mean the device held the untruncated text |
| **What may be fetched at all** | the filename | `coffee_server/news_sources.json` (press RSS, live) vs `allowlist.json` (roasters, empty). Two files with two different justifications — see `specs/legal.md`'s scope note. Do not merge them, and do not move an entry between them |
| **The gateway's hostname** | `SERVER_BASE_URL` | `v1/local.properties` → `BuildConfig` → `net/AiGateway.kt`; must be **HTTPS**, because `network_security_config.xml` forbids cleartext with no exceptions. Changing the deployed host means `coffee_server/deploy/.env`'s `API_HOST`, the DNS A record, and a Caddy redeploy — the certificate is bound to the name |

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

```bash
cd coffee_android/plan/v1
./audit.sh            # everything with a pass/fail: V1, V2, V2b, V3, V4b, V5, V6, V7
./audit.sh --fast     # the same minus the Paparazzi goldens (~20s of the ~25s)
```

One command, one exit code, a summary naming whichever check failed. It runs
from the audit side and shells into the module for the Gradle half, which is
the practical face of §1.1's boundary: the Python tooling may not live inside
the thing it checks, and the goldens may not live outside it.

**What `audit.sh` covers, and what it replaced.** V3, V5, V6 and V7 used to be
greps whose output a human had to read and judge; they are now
`check_couplings.py`, because each already had exactly one right answer and was
a grep only in the sense that nobody had written the loop. Each of its four
checks has been fault-injected — break the coupling, watch the check name it —
which is the only evidence that a checker that has never failed is worth
running.

**What is still yours.** `V4` (Room version and migrations) and `V2a` (the
device gesture harness) have no pass/fail this side of a schema diff or a
device, and are below. So are steps 1–3 of §0, which is where most of the
coupling in this repo lives.

<details>
<summary>The individual commands, for when you want one of them alone</summary>

```bash
# ============ from coffee_android/plan/v1/  (the audit side) ============

# V1 — design tokens + mock copy fidelity (36 colour, 11 type, 5 shape, 110 strings)
python3 check_design.py            # must exit 0

# V3/V5/V6/V7 — locale parity, bundle version, network surface, scan field list
python3 check_couplings.py         # must exit 0

# V1b — redraw the simulator frames after any copy or visual change
python3 screenshots.py             # -> screenshots/*.png

# V4b — schema parity: every Room column has a desktop column AND is on a
# sync allowlist.  Run it on any Entities.kt or db.py change; it is the only
# check that catches a field which silently stops travelling.
python3 check_schema_parity.py     # must exit 0

# ============ from coffee_android/v1/  (the module) ============

# V2 — Paparazzi goldens (89 images, 118 @Test).  -Ppaparazzi IS REQUIRED.
./gradlew :app:verifyPaparazziDebug -Ppaparazzi     # verify against the 89 goldens
./gradlew :app:recordPaparazziDebug -Ppaparazzi     # re-record, then READ the diff
./gradlew :app:testDebugUnitTest    -Ppaparazzi     # goldens + geometry + ingest tests

# V2a — the ONE gesture harness. Paparazzi renders a static frame and adb
# cannot press-hold-then-move (`input motionevent` is per-process; `sendevent`
# needs root), so ImagesStrip's long-press drag is only checkable here.
#
#   *** THIS COMMAND DESTROYS THE APP'S DATA ON THE DEVICE IT RUNS ON. ***
#
# AGP uninstalls both APKs when a connected test run finishes, and uninstalling
# takes /data/data/app.coffeecan with it -- the Room database and every photo
# the app had copied in. Auto Backup is off for this app by design
# (res/xml/data_extraction_rules.xml, legal-accounts rule 62), so Android holds
# no copy to restore from. This happened for real on 2026-08-23, on the
# maintainer's own phone, with months of beans and brews on it.
#
# RUN IT ON AN EMULATOR OR A THROWAWAY DEVICE. If it must be a real one, take a
# copy first -- the debug build is debuggable, so this works without root:
#   adb shell run-as app.coffeecan tar -c -f - databases files > backup.tar
./gradlew :app:connectedDebugAndroidTest          # emulator/test device ONLY

# V2b — the dripper icons are generated; the XML must not be hand-edited
cd ../plan/dripper_icons && python3 convert_drippers.py --check   # 0 = in step

# V3 — locale parity. Now check_couplings.py; this is the hand version, kept
# because it prints the keys and the script prints the verdict.
cd app/src/main/res && for L in fr zh; do echo "== $L =="; comm -23 \
  <(grep -o 'name="[^"]*"' values/strings.xml   | LC_ALL=C sort -u) \
  <(grep -o 'name="[^"]*"' values-$L/strings.xml | LC_ALL=C sort -u); done

# V4 — Room schema/migration
grep -n 'version = \|MIGRATION' app/src/main/java/app/coffeecan/data/CoffeeDatabase.kt

# V5 — bundle format parity across the two projects
grep -rn 'BUNDLE_VERSION *=\|const val VERSION' \
  app/src/main/java/app/coffeecan/data/SyncBundle.kt ../../coffee_agent/sync_tools.py

# V7 — the scan field list. SIX places state it now (repo.LABEL_FIELDS,
# prompts.BEAN_FIELD_NAMES, prompts.BEAN_FIELD_LABELS, BeanFieldsDto, and
# ScanReviewSheet's two), and check_couplings.py compares all six as ordered
# sequences -- the order is part of the rule. "Nothing checks this
# automatically" was true until 2026-08-29.
grep -n 'BEAN_FIELD_NAMES = \|LABEL_FIELDS = ' \
  ../../../coffee_server/prompts.py ../../../coffee/src/coffee_can/repo.py -A 4
grep -n 'farm' app/src/main/java/app/coffeecan/net/ServerApi.kt \
  app/src/main/java/app/coffeecan/net/AiGateway.kt \
  app/src/main/java/app/coffeecan/ui/components/ScanReviewSheet.kt

# V6 — the app's whole network surface; nothing may appear outside this file
grep -rn '@GET\|@POST\|@DELETE' app/src/main/java/app/coffeecan/net/ServerApi.kt
grep -rn 'ServerApi\|ApiClient' app/src/main/java/app/coffeecan/ui/   # must be empty
```

</details>

### V2's two traps are now closed in the build, not in your head

Both used to live here as prose you had to remember, and both failed silently
when you didn't. Neither is your problem any more; this section records what
changed so nobody re-adds the ritual.

**The JDK.** This machine's default is 25, which the bundled Kotlin plugin
cannot parse — `JavaVersion.parse` throws during configuration and Gradle
prints the bare message `25.0.4`, no stack trace, no task name, which reads
like a corrupt checkout. `gradle/gradle-daemon-jvm.properties` (`toolchainVersion=17`)
now selects the daemon's JVM before any of that runs, so **no `JAVA_HOME`
export is needed for any command in this file**. It has to be that file: a
guard in `settings.gradle.kts` is already too late, because the Kotlin DSL
compiles that script on the same bad JVM. Regenerate with
`./gradlew updateDaemonJvm --jvm-version=17`.

**The `compileSdk` flip.** Paparazzi 1.3.5 cannot render at `compileSdk = 36`
(its `android.os.Build` shim throws `NoSuchElementException` from
`Renderer.configureBuildProperties` before a composable draws). This was a hand
edit to 35 before a screenshot run and back to 36 after, and it was called the
easiest coupling in this repo to leave in the wrong state *because nothing
failed when you did* — while `specs/legal-android.md` rule 18 says 36 is what
ships. It is now `compileSdk = if (paparazziRun) 35 else 36`, driven by
`-Ppaparazzi`: the source can no longer hold 35, and a screenshot task without
the flag stops on a `taskGraph` guard that names it. `targetSdk` never moves.

```bash
grep -n 'compileSdk\|targetSdk' app/build.gradle.kts   # both read 36; the 35 is a branch
```

### V2 renders one frame, so animated figures need a pose sheet

Paparazzi never advances an animation clock: a composable driven by
`rememberInfiniteTransition` is captured at whatever value it holds on first
composition, and everything after that is unchecked. That is a real hole and it
was open — `CanBoyNews` grew a page-turning arm on 2026-08-29 while all 84
goldens passed, because none of them draws the figure past `page` = 0.

`MascotPoseSheetTest` closes it for that figure: one golden holding six frames
of the gesture at the phase boundaries `CanBoy.kt` names, so a diff points at
the constant that moved. A trajectory also fails differently from a pose — the
bug it would have caught first was an elbow that drew the arm hooking back on
itself, obvious with the frames side by side and invisible in any one of them.
**Any figure whose knob is animated wants a strip, not another single frame.**

Screens that *contain* such a figure should freeze it under
`LocalInspectionMode` (`NewsScreen.kt`'s `ReadingCanBoy`, `PolaroidCard.kt`'s
flash), so their goldens hold a stated frame rather than a nearly-zero one.

### Eight goldens do not reproduce byte-for-byte on this machine

Recording twice in a row is byte-identical, so this is not jitter: seven images
(`home` ×3, `flavorCardWithCaption`, `searchMatchingEveryBean…`, `journeyNew`,
`pickBean`) simply render slightly differently here than on whatever machine
recorded them — 0.03–0.23% of pixels, max channel delta 20–227, always in one
small box. `verifyPaparazziDebug` passes them on tolerance.

The cost is that `recordPaparazziDebug` shows seven phantom diffs on every run,
which is exactly the noise that teaches people to stop reading diffs. Left
alone deliberately: re-recording them belongs in its own commit that changes
nothing else, not folded into an unrelated edit. Until then, after any record,
restore the images your change cannot explain.

---

## 7. What this spec cannot cover

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
