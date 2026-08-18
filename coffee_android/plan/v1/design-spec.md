# coffee_android v1 — design specification

**Status:** this is the **standardised specification of what v1 actually is**,
written on 2026-08-17 by reading every file under `../../v1/` and checking it
against a running install on a physical device (Galaxy S22 Ultra, Android 15).

**Read this before `../README.md`, `../screens.md` or `../api.md`.** Those
three are the *design proposal* — written before and during the build, and
carrying decisions that the code has since overtaken. This document is the
*specification of the build*. Where they disagree, this one is right, and §12
lists every disagreement so the older documents can be read safely rather than
discarded.

**Scope.** Design system (colour, type, shape, spacing), component library,
illustration vocabulary, navigation model, every screen, the data model, the
network contract, localisation, accessibility, and how each of those is
verified. It does not restate the compliance analysis — `../../../specs/`
`legal-android.md`, `legal-accounts.md` and `legal.md` remain binding, and this
document is written to satisfy them, never to reinterpret them.

---

## Contents

1. [What v1 is](#1-what-v1-is)
2. [Colour](#2-colour)
3. [Type](#3-type)
4. [Shape, spacing and elevation](#4-shape-spacing-and-elevation)
5. [Component library](#5-component-library)
6. [Illustration and brand](#6-illustration-and-brand)
7. [Navigation model](#7-navigation-model)
8. [Screens](#8-screens)
9. [Data model](#9-data-model)
10. [Network contract](#10-network-contract)
11. [Localisation, accessibility, permissions](#11-localisation-accessibility-permissions)
12. [Verification, and where the older documents are wrong](#12-verification-and-where-the-older-documents-are-wrong)

---

## 1. What v1 is

A native Android port of `coffee-can` (`../../../coffee/`), the PySide6 desktop
app for logging hand-brew coffee. Same data model, same workflows, rebuilt in
Kotlin + Jetpack Compose for Google Play. Package `app.coffeecan`,
`versionName` 1.0.0, one `Activity`, Compose-only, no XML layouts and no
Fragments.

**Built and shipping in v1:** the four axis pages (News, Home, Sessions,
Profile), Bean Detail with full CRUD and label scan, Brew Session Detail with
the stage editor and Ask-AI, Scan Review, Share Card export, Welcome, Pick
Bean, Privacy, AI disclosure and consent, account controls, desktop sync, and
three locales.

**Built but deliberately unwired:** Can-Drink Catalogue (`CanDrinkScreen.kt`,
582 lines, complete). News took the `-1` slot on 2026-08-15. Bringing it back
is a one-line change in `Axis.kt`, gated on `CRAWLER_ENABLED` and the allowlist
process in `../../../specs/legal.md`, not on engineering.

**Not built:** voice sessions (needs an audio endpoint), the contribution
calendar's catalogue strip, dark mode (§2.6).

**Scale:** 52 Kotlin source files under `app/src/main`, ~15,220 lines, plus 29 test files.

---

## 2. Colour

The source of truth is `../variants.py`'s `PURE_GREEN`, ported into
`ui/theme/Theme.kt`. `check_design.py` diffs every token on every run, so the
port is a checkable claim rather than an asserted one.

### 2.1 The three greens are not interchangeable

This is the single most important rule in the palette, and the one most likely
to be broken by someone adding a screen.

| Token | Hex | Role | Contrast on white |
| --- | --- | --- | --- |
| `Brand` | `#34C759` | **Decorative only** — the mark's disc, the mascot's disc, the splash | ~2.2:1 — fails WCAG AA as text *and* as a fill behind white text |
| `primary` | `#196D2E` | **Every** label, link, button word, and text-on-green | passes AA |
| `VizSeries` | `#2B9343` | **Data marks only** — the radar polygon and stroke | n/a — never carries text |

`VizSeries` is deliberately a full tone band clear of `primary` (ΔE 11.8, and
11.4 under simulated colour-vision deficiency) so a chart mark can never be
mistaken for a control. **Charts use it; controls never do.**

### 2.2 Material 3 scheme

```
primary              #196D2E     onPrimary              #FFFFFF
primaryContainer     #C3EDC5     onPrimaryContainer     #002602
secondary            #556855     onSecondary            #FFFFFF
secondaryContainer   #E3F6E3     onSecondaryContainer   #233524
tertiary             #016B53     onTertiary             #FFFFFF
tertiaryContainer    #9FECD1     onTertiaryContainer    #002A1E
error                #84241A     onError                #FFFFFF
errorContainer       #FEDED7     onErrorContainer       #3B0A05
background           #FFFFFF     onBackground           #1B241C
surface              #FFFFFF     onSurface              #1B241C
surfaceVariant       #DCECDD     onSurfaceVariant       #515D51
surfaceContainerLow  #EAF5EA     surfaceContainer       #E0EFE1
surfaceContainerHigh #D4E6D4     surfaceContainerHighest#C9DCCA
outline              #6D7B6D     outlineVariant         #C3D3C4
inverseSurface       #323C32     inverseOnSurface       #EAF3EA
inversePrimary       #89D890     scrim                  #06140A
```

**`surface` is the one deliberate deviation from the deck.** The deck specifies
`#F2FAF2`; the app uses `#FFFFFF`. Page and card are both plain white, and
nothing outlines a block — adjacent cards are separated by a single inset rule,
and a standalone block is delimited by its own section heading. It is a
decision, not a defect, and the deck is the side that is out of date:
`check_design.py` carries it in `ACCEPTED_DEVIATIONS` and prints it on every run
under its own heading, so the deviation stays visible without leaving the check
permanently red.

**`scrim` is set explicitly.** Left unset, Material dims sheets and dialogs with
a neutral black; `#06140A` keeps the page behind a sheet in-palette. Every
`ModalBottomSheet` and `AlertDialog` picks this up for free.

### 2.3 Visualization family

Material's `ColorScheme` has no slot for data colour, so these are named in the
theme rather than re-invented per chart.

| Token | Hex | Used by |
| --- | --- | --- |
| `VizSeries` | `#2B9343` | radar polygon + stroke |
| `VizInk` | `#515D51` | axis labels, numerals |
| `VizGrid` | `#C3D3C4` | radar web, gridlines |
| `VizTrack` | `#E0EFE1` | unfilled slide-bar track |
| `VizBand` | `#B0E8B6` | the extraction bar's "well extracted" band |
| `VizBandEdge` | `#43A756` | that band's edges |
| `VizDeviation` | `#506051` | the extraction bar's deviation block |
| `VizThumb` | `#152817` | every slide-bar thumb |
| `VizTickDot` | `#F7FCF8` | step dots on every slide bar |

**`VizTickDot` is lighter than everything it sits on, on purpose.** It began as
mid-grey `#D6D6D6` and read as dirt on an already-light track. A tick is a
measurement mark *scored into* the track, so it is never darker than the track
or the fill.

### 2.4 The slide-bar fill ramp

`VizFillLow` `#AFF2C0` → `VizFillHigh` `#34C759`, interpolated by the value's
own fraction.

**`VizFillHigh` is `Brand`, and that is a deliberate, bounded widening of the
"decorative only" rule.** The rule exists because `#34C759` fails AA as text or
behind white text. Neither applies here: nothing is ever drawn on top of this
fill, the value is redundantly carried by the stripe's length and the numeral
beside it, and the thumb riding on top is near-black. **Do not carry this
precedent to anything that has to be read.**

### 2.5 Heatmap ramp

`VizSequential`, five steps light→dark, from `PURE_GREEN_SEQ`:
`#EBF2EC` `#AADBAF` `#65B972` `#299141` `#155E27`.

### 2.6 Light only

Deliberate. `PURE_GREEN` carries a dark quartet, but shipping a dark mapping
nobody has reviewed against the deck is worse than not offering one.
`isSystemInDarkTheme()` is read in `CoffeeCanTheme` solely to make that choice
explicit at the call site rather than invisible. Adding dark mode means
reviewing all 36 tokens against the deck first.

---

## 3. Type

Fredoka — the logo's own face, so headline and mark share letterforms. Bundled
in `res/font/` rather than downloaded, because a downloadable font arrives late
or not at all and the first frame of a cold start is where identity is
established. OFL-licensed; the licence ships in `assets/licenses/`.

### 3.1 The eleven roles

| Role | Size | Weight | Typical use |
| --- | --- | --- | --- |
| `displaySmall` | 36sp | SemiBold | the avatar letter |
| `headlineMedium` | 28sp | SemiBold | screen titles |
| `headlineSmall` | 22sp | SemiBold | major headings |
| `titleLarge` | 22sp | SemiBold | app-bar titles |
| `titleMedium` | 16sp | SemiBold | card titles, bean names |
| `titleSmall` | 14sp | SemiBold | section headings |
| `bodyLarge` | 16sp | Normal | body copy |
| `bodyMedium` | 14sp | Normal | secondary copy |
| `labelLarge` | 14sp | SemiBold | button labels |
| `labelMedium` | 12sp | SemiBold | chips, pills |
| `labelSmall` | 11sp | Medium | captions |

**The three label roles are semi-bold, and that is load-bearing.** Set at 400
they read as undersized body copy — small, thin and accidental where the design
is small, firm and deliberate.

**Body sits at 16/14, not 15/13.** One sp does not sound like a change; across
every line of copy on every screen it is half of why an earlier build looked
simultaneously airier and weaker than the design.

### 3.2 Two weights against the deck's three

Ships regular and bold only. `labelSmall`'s Medium (500) is mapped explicitly
onto the regular face rather than left to Compose's weight matching — the
matcher would land there anyway, but leaving it implicit means the one role
asking for Medium is resolved by an algorithm rather than by the theme file.
Shipping the variable font would close this exactly; it is not worth the APK.

### 3.3 Numerals

Fredoka has no tabular figures, so anything whose columns must align — the pour
table, numeric readouts — uses `Numeric` (`FontFamily.Monospace`). The desktop
deck does the same, keeping IBM Plex Mono for those columns only.

---

## 4. Shape, spacing and elevation

### 4.1 Shape

| Token | Value | Applies to |
| --- | --- | --- |
| `CardCorner` | 24dp | cards (`shapes.large`) |
| `SheetCorner` | 32dp | bottom sheets (`shapes.extraLarge`) |
| `ThumbCorner` | 16dp | thumbnails (`shapes.medium`) |
| `FieldCorner` | 16dp | fields (`shapes.small`) |
| `ChipCorner` | 999dp | chips — a full pill |
| — | 8dp | `shapes.extraSmall` |

The radii moved with the typeface and were not an independent choice: a rounded
display face against 4dp radii reads as a mismatch.

**`ChipShape` is applied per chip, not through `shapes.small`.** M3 resolves
chip shape *and* `OutlinedTextField` shape from `shapes.small`. Rounding it to a
pill would give fields a 28dp capsule they were never drawn with; leaving it at
16 gives chips a rectangle they were never drawn with. The design has two
values, so the theme carries two. `999.dp` rather than `percent = 50` because it
is the deck's own number and Compose clamps to half the shorter side anyway.

### 4.2 Spacing

| Token | Value | Meaning |
| --- | --- | --- |
| `Gutter` | 16dp | the page gutter — **every** scrolling column pads by this |
| `ShelfCardHeight` | 96dp | one height for every card on Home and Sessions |
| `ShelfTile` | 80dp | the artwork inside that card |
| `ShelfCardPadH` / `PadV` | 12dp / 8dp | card padding |

`Gutter` is not a Material metric and not a per-screen decision: it is why a
card edge lines up with a section heading lines up with a divider on every
screen. It was 20dp in the first build, which compounded with the type scale
into a measurable density gap.

`ShelfCardHeight` exists so Home's bean card and Sessions' brew card stay the
same size **by construction** rather than by two numbers that happen to agree.

### 4.3 Window insets — the one rule Paparazzi cannot catch

**The outer `Scaffold` owns the bottom; the pages own the top.** Each of the
four axis pages carries its own `Scaffold` and **must** pass
`contentWindowInsets = AxisPageInsets` (`ui/Axis.kt`) rather than the default.

The default is `systemBars`, and the axis `Scaffold` has *already* padded the
pager by its bottom bar's height — a figure that includes the system navigation
inset, because `NavigationBar` consumes that inset internally. A page that also
claims the bottom applies it twice and leaves a dead band above the bar,
measured at 37dp with three-button navigation.

**Every inset is zero under Paparazzi**, so the goldens render correctly either
way. Only a real device shows this. It is the standing argument for keeping at
least one physical-device pass in the loop.

---

## 5. Component library

Reusable composables under `ui/components/`. Each Canvas-drawn component ships
an explicit `Modifier.semantics { contentDescription = … }` textual summary,
because a Compose `Canvas` has **zero** accessibility-tree presence by default.

### 5.1 Fields — there are two, chosen by role

`Fields.kt` is the densest design decision in the app.

- **`LabeledField` / `ChoiceField`** — a genuine M3 outlined box, 56dp with a
  notched label. Spent on required or free-text fields.
- **`CapsuleField` / `CapsuleChoiceField` / `CapsuleValue`**, inside a
  **`FieldPair`** — the score-sheet motif: a small label *above* a 30dp
  `surfaceContainer` capsule (`CapsuleHeight` 30dp, `CapsuleInset` 12dp), laid
  out two to a row.

**This split is a density decision, not a decorative one.** Nine stacked 56dp
boxes are ~600dp of form; the same nine as capsules in a 3×2 grid are ~130dp.
That is the difference between the add-a-bean page fitting above the fold and
scrolling twice.

Rule: outlined box for a required or free-text field, capsule for everything
else.

### 5.2 Charts and meters

| Component | Shape | Notes |
| --- | --- | --- |
| `RadarChart` | 11-axis Canvas polygon | `TextMeasurer`-based label layout, not guessed offsets. Two label sets (§5.3) and two ink styles — in-app on white, and white-on-green at 4× for the Share Card, one drawing routine |
| `ExtractionBar` | −1…+1 axis, three zones | under / well extracted / over, with `VizBand` + `VizBandEdge` + `VizDeviation` |
| `ValueBar` | slide bar | Score and all eleven flavour axes. Draggable — a 2026-08-17 change: dragging directly on what had been a read-only meter proved the better control, and the palette was copied across so a slider stops looking like an unrelated second widget |
| `ContributionCalendar` | heatmap grid | `ActivityWeeks = 21`; selected cell enlarges ×1.3 |
| `DurationPickerDialog` | two snapping wheels | Pour-stage elapsed time, `m` 0–29 and `ss` 0–59, in a standard `AlertDialog`. **Not** M3 `TimePicker`: that dials an hour and a minute on a 24-hour clock and labels itself so, which is the wrong question in the wrong units for an offset from the start of a brew |

### 5.3 Two flavour-axis label sets

Same eleven axes, same fixed order, two spellings:

- **Full** (`BeanEntity.FLAVOR_AXES`) — Fruity, Floral, Tea-like, Sweet,
  Nutty/Cocoa, Spices, Roasted, Cereal, Green/Veg, Sour, Fermented. Used on
  full-size charts and every slider.
- **Short** (`ShortFlavorAxes`) — Fruity, Floral, Tea, Sweet, Nutty, Spices,
  Roasted, Cereal, Green, Sour, Ferment. Used at small radii.

Measured label placement stops "Nutty/Cocoa" being *clipped*; it does not stop
it being the widest thing on a small card. Hence two sets.

**Order is part of the format.** It matches `repo.FLAVOR_AXES` on the desktop,
and the sync bundle writes the eleven `flavor_*` **column names** in that order
— verified identical on both sides, so a bundle round-trips safely.

**One label differs from the desktop, harmlessly.** Axis 9 is `Green/Veg` here
and `Green/Vegetative` in `coffee/src/coffee_can/repo.py`. Only the *display*
string differs; the column (`flavor_green_vegetative`) is the same, which is
what the bundle carries. Worth closing for consistency the next time either
side's labels are touched — but it is not a data defect, and changing the
column name to match would be.

### 5.4 Imagery

| Component | Purpose |
| --- | --- |
| `BeanIcon` | a bean's mark on the shelf — its own first photo, or a generated stand-in |
| `BagTile` | that stand-in: initials on a tinted bag silhouette |
| `PhotoHeroPage` | the bean-detail hero. `HeroHeight` 224dp, `PanelPeek` 96dp, `UnknownAspectFraction` 0.62, drag-to-settle at 700f |
| `ZoomableImageViewer` | pinch/double-tap, `MaxScale` 4× |
| `TopBarDivider` | the hairline rule under every app bar |

### 5.5 Compliance components

`AiDisclosureSheet` is **the** compliance artifact — see §8.11 and §11.3.
`ScanReviewSheet` and `AccountControls` are covered in §8.

---

## 6. Illustration and brand

`Illustrations.kt` and `CanBoy.kt` (426 lines) — **drawn live in Compose Canvas
rather than shipped as frozen pictures**, so the poses can move.

- **The mark** — a `Brand` disc with the "Can" wordmark. The disc is painted by
  the composable from the theme token; the wordmark is a `VectorDrawable`
  (`ic_brand_wordmark.xml`) whose path data is the design deck's own geometry,
  flattened and pixel-diffed against the deck's render before landing (max
  channel delta 35/255 on 10 antialiased pixels of a 400×400 raster). It is the
  drawing, not a lookalike.
- **Can-boy**, the mascot, at `FIGURE = 100f` internal units, in three poses:
  **pour-over** (rest and tilted), **shutter-flash** (the scan prompt), and
  **heartbreak** (whole and settled — empty and error states).
- **Dripper glyphs** — one per entry in `Choices.DRIPPERS` (15: Hario V60,
  Chemex, Kalita Wave, Melitta, Clever, Bee House, Origami, Fellow Stagg, Orea,
  April, Cafec Flower, Timemore Crystal Eye, Hario Switch, Kono Meimon, OXO
  Brew). Rendered at `SessionGlyph` 64dp on session rows.

---

## 7. Navigation model

### 7.1 A swipe axis **and** a bar that drives it

The deck defines the whole app as one horizontal axis centred on Home, which is
why every page is numbered rather than named:

```
   -1            00           +1            +2
  News    ←→   HOME    ←→  Sessions   ←→  Profile
```

Implemented as one `HorizontalPager` over those four pages (`ui/Axis.kt`), with
every `0.x` page pushed on top of it.

**The bottom bar is an addition to the deck, on a product decision.** The deck
draws no such bar. What makes it the right addition is a defect the axis
created: once Home's profile icon and its "Every brew you've logged" row were
removed — both push-model doors the deck never drew — **nothing visible pointed
to `+1` or `+2` at all**. Custom accessibility actions named the destinations
for a screen reader and drew nothing for anyone else.

**It drives the pager rather than replacing it.** Selection follows
`pagerState.currentPage`, so swiping moves the bar and tapping animates the
pager. One source of truth, and the gesture the deck designed around still
works.

This supersedes `README.md` resolution #19, which declined bottom navigation.

### 7.2 Routes

Named for the deck's page numbers so a screen can be found from a wireframe
(`ui/Nav.kt`):

| Route constant | Path |
| --- | --- |
| `Welcome` | `00w_welcome` |
| `Axis` | `axis` |
| `PickBean` | `+1.1a_pick_bean` |
| `NewBean` | `0.1_bean_profile` |
| `BeanDetail` | `0.2_bean_detail/{beanId}` |
| `BrewSession` | `+1.1_log_brew/{beanId}/{sessionId}` |
| `Privacy` | `+2.2a_privacy` |
| `AiDisclosure` | `+2.2b_ai` |

Sheets and dialogs are not routes — they are state within their host screen.

---

## 8. Screens

### 8.1 `00w` Welcome

Cold-launch splash, off-axis, shown exactly once. Reveal at 2000ms, total
3000ms (`WelcomeScreen.kt`).

### 8.2 `-1` News

Headline, source, date, link — and **only** those four fields.
`legal-accounts.md` rule 74 permits no snippet and no AI summary, and
`NewsItemEntity` has nowhere to store one. Prefetched during the splash, cached
in Room, hourly server refresh.

States: list, offline (heartbreak mascot, "Try again"), unavailable. Real
headlines remain gated on `CRAWLER_ENABLED` + allowlist + rule 72, so the
shipped state is the "no feed yet" branch.

### 8.3 `00` Home

Bean shelf (each row: `BeanIcon`, name, process · roast date, brew-count pill,
chevron), "See all N beans", **Brewing activity** contribution calendar, and
**My flavor** — an eleven-axis radar averaged across every session, labelled
with the session count.

Empty state: the pour-over mascot with an idle wiggle (1000ms shake, 4000ms
rest). Search is a top-level action. FAB logs a brew.

### 8.4 `0.1` / `0.2` / `0.2b` Bean Detail

The largest screen in the app (1400 lines). One bean, created or edited.

- **Photo hero** (`PhotoHeroPage`) — the bag photo, draggable panel, Images
  strip, zoomable viewer.
- **Scan card** — "Scan the label to update these fields", with offline and
  consent-blocked variants.
- **Fields** — name as an outlined box; origin, variety, altitude, roaster,
  producer, process, roast date as capsules two to a row; note free-text.
- **Flavour** — radar plus a manual-override sheet. `flavorSource` is `auto`
  (averaged from this bean's sessions) or `manual`.
- **Sessions list**, delete-with-cascade confirm, discard-draft confirm, share
  disc.

**New beans are held as in-memory draft state** (`rememberSaveable`) until the
first real edit or explicit save — `status` is `draft` until then. A screen the
OS kills mid-flow never orphans an empty row.

### 8.5 `0.11` / `0.12` / `0.13` Photo source → Scanning → Scan Review

Photo source sheet (take a photo / choose a photo), scanning state, then
**Scan Review**: the guessed fields, each editable, with "was:" hints showing
what would change, an empty-read state, and a report control.

Nothing reaches the form until the user accepts.

### 8.6 `+1` Sessions

Every brew across every bean, newest first, with the dripper glyph at 64dp,
dose, score and extraction verdict. Header states the count. Empty state and
delete are both built.

### 8.7 `+1.1` Which bean? → `+1.1a` Pick Bean

The FAB opens a sheet with three choices: pick an existing bean, add a bean, or
vibe-brew (log now, name it later). Pick Bean is its own screen.

### 8.8 `+1.1` Brew Session Detail

One brew, created or edited (1001 lines). Brew fields (dripper, grinder, grind
size, filter, dose, water, temperature, ppm, humidity, total time), **Pour
stages** with its own editor sheet, then **How was it?** — Score `ValueBar`,
`ExtractionBar`, note — then **Flavor**: the radar over eleven `ValueBar`
sliders.

Drafts, discard confirm and delete confirm are all built. Ask-AI opens as a
sheet over the form.

**A new brew pre-fills from the bean's last one** — dripper, grinder, grind
size, filter, dose, water, temperature and ppm, i.e. the whole **Brew details**
section. Never the result: no score, no extraction, no tasting axes, because
carrying those over would be the app recording an opinion the user has not
formed. Pour stages are *not* carried; the pour plan is what changes between
brews of the same bag. The pre-filled values become the dirty-check baseline,
so a reused form does not open asking to be saved.

**The stage sheet's `At (time)` is a picker, not a typed field** — a trailing
clock icon, tapping anywhere on the field opens `DurationPickerDialog`. It
writes `m:ss`; `parseSeconds` still accepts `"105"` and `"1m45"` for AI
suggestions and older rows.

### 8.9 `+2` Profile

Two states, signed out and signed in. The mark, the state line — *"Your beans
and sessions stay on this phone. Sign in for AI label reading and coffee
news."* — and the sign-in button. Then **About & legal**: Language, Sync with
desktop, Privacy Policy, How we use AI, and the account controls.

### 8.10 `+2.2a` Privacy · `+2.3` Data access · `+2.4` Delete account

The policy screen, the Art. 15(3) access document, and account deletion. The
access response is **typed** (`AccountResponseDto`), not a loose map, because
the screen rendering it is making a legal statement — a field arriving as the
wrong JSON type should fail loudly rather than render as an empty line reading
"we hold nothing".

### 8.11 `+2.2b` How we use AI · the disclosure sheet

`AiDisclosureScreen` is the settings surface; `AiDisclosureSheet` is the
**prominent disclosure and consent modal** shown immediately before a given AI
operation.

Consent is **per operation**, never global (§11.3).

### 8.12 `+2.5` Share Card

Renders a shareable PNG (`ShareCard.kt`, 593 lines) via `rememberGraphicsLayer`,
previews it, and hands it to the system share sheet through `FileProvider`.
Renders coffee-can desktop's card design, not the wireframe's — the two specs
disagreed and the desktop's implemented design was chosen.

### 8.13 `-1 (v2)` Can Drink

Complete and unwired — see §1.

---

## 9. Data model

Room, mirroring `coffee-can`'s SQLite schema column-for-column.
**`version = 3`, `exportSchema = true`**, with named `MIGRATION_1_2` and
`MIGRATION_2_3`. `fallbackToDestructiveMigration()` is banned.

Six entities:

| Table | Notes |
| --- | --- |
| `beans` | identity + provenance, `status` (`draft`/`saved`), `flavorSource` (`auto`/`manual`), and **eleven flavour columns** |
| `bean_images` | `position`, `filePath`, `rotation` |
| `sessions` | brew parameters, `score`, `extraction`, note, and **the same eleven flavour columns** |
| `session_stages` | one pour each |
| `catalogue_items` | crawler cache |
| `news_items` | feed cache — four fields, no snippet column |

**The eleven flavour columns exist on `sessions` as well as `beans`, and that
is what makes `auto` work**: a bean with `flavorSource = auto` derives its radar
by averaging its sessions. A sync bundle carrying only the bean columns imports
beans that can never recompute one.

`CoffeeRepository` is the single point through which the rest of the app talks
to storage.

---

## 10. Network contract

### 10.1 One chokepoint

`net/AiGateway.kt` is **the** chokepoint. Every AI request checks, in order:

1. **consent for that specific operation** (not a global flag),
2. **connectivity** — a distinct "you're offline" state, not a timeout wait,
3. **a freshly minted Google ID token**,

and **nothing retries**. A queued retry would silently re-send a photo after the
user believed they had cancelled — a consent problem, not merely a UX one.

`CatalogueGateway` is its read-only sibling for `/v1/catalogue` and `/v1/news`,
which take neither consent nor auth.

**Never call `ServerApi` from a screen, and never add a second `OkHttpClient`.**
Coil shares the app's single client so the TLS-only Network Security Config
covers image loads too.

### 10.2 The app calls seven endpoints and no other host

| Endpoint | Auth | Purpose |
| --- | --- | --- |
| `POST /v1/suggest` | Bearer | brew suggestion from structured fields |
| `POST /v1/vision` | Bearer | bean-label OCR |
| `POST /v1/report` | Bearer | report an AI output — **deliberately not consent-gated**, since reporting is how a user objects |
| `GET /v1/account` | Bearer | the Art. 15(3) access document |
| `DELETE /v1/account` | Bearer | erasure |
| `GET /v1/catalogue` | read key | crawler cache |
| `GET /v1/news` | read key | feed cache |

**`/v1/ask` is absent on purpose.** The gateway still exposes it for
`coffee_agent` and local tooling, and this app must never call it: it takes a
free-form prompt, and a shipped client ships its key — an app calling it would
be publishing a general-purpose LLM on the developer's bill. The two AI
endpoints above take **structured fields** and let the server own the prompt
(`coffee_server/prompts.py`).

### 10.3 Wire shapes

Snake_case on the server, camelCase in Kotlin, bridged by `@SerialName` rather
than by renaming either side. DTOs mirror `coffee_server/schemas.py`.

Two keys, not one: a low-stakes **read key** for catalogue/news and a separate
key for the **metered** AI endpoints, so rotating one does not break the other.

---

## 11. Localisation, accessibility, permissions

### 11.1 Three locales

English, French, Chinese (`values/`, `values-fr/`, `values-zh/`), chosen
in-app via `AppLocale` + `LocaleManager.setApplicationLocales`, persisted across
reinstalls. `SYSTEM` (empty tag) follows the device.

**All user-facing copy lives in `strings.xml`**, not in Kotlin literals. This is
the fix for the English-only blocker, and it is why any tool checking copy must
read the resources (§12.2).

### 11.2 Accessibility

Every Canvas-drawn component ships a generated `contentDescription` summary
(e.g. ExtractionBar → "Extraction: well extracted, 62%"). The axis exposes
custom accessibility actions naming its destinations. Two greens exist
specifically so nothing readable is ever set in the failing one (§2.1).

### 11.3 Consent

Two independent operations, `read_labels` and `suggest_brew`, each tracked with
`shown` / `accepted` / `withdrawnAt` — three flags, not one.

`withdrawnAt` is what stops the app nagging the one user who exercised a right:
`shown`/`accepted` alone cannot distinguish "never accepted" from "accepted,
then withdrew", so a re-prompt cadence written for the first case fires forever
on the second — which is not withdrawal.

### 11.4 Permissions — the whole list

`INTERNET` and `ACCESS_NETWORK_STATE`. That is all.

- **No `CAMERA` permission, and it must never gain one.** Photos come from the
  system Photo Picker and `ACTION_IMAGE_CAPTURE`. Adding the permission does
  not enable capture, it **breaks** it: Android requires an app that *declares*
  `CAMERA` to also hold it before `ACTION_IMAGE_CAPTURE` will launch.
- **No `READ_MEDIA_IMAGES`** — the Photo Picker hands over one photo.
- **`allowBackup="false"`**, with `tools:replace`, because a merged manifest can
  otherwise re-add it. Verify in the *merged* manifest.

### 11.5 EXIF

Stripped by **re-encoding** the pixels (`media/ImageIngest.kt`), not by clearing
named tags: a scrub list has to stay correct forever, while a pixel round-trip
carries nothing across by construction. The 2048px downscale is a side benefit
the vision endpoint wanted anyway. Covered by instrumented tests.

---

## 12. Verification, and where the older documents are wrong

### 12.1 How v1 is verified

| Layer | Tool | Covers |
| --- | --- | --- |
| Design tokens | `check_design.py` | 36 colour, 11 type, 5 shape tokens against `../variants.py` |
| Rendering | Paparazzi, `app/src/test/…/screenshot/` | 58 goldens in `app/src/test/snapshots/images/` — real compiled Compose through layoutlib, no emulator |
| Geometry | `ContributionCalendarGeometryTest`, `CropToFitTest` | layout maths |
| Ingest | `ImageIngestTest`, `ImageIngestOrientationTest` | EXIF strip, orientation |
| Insets, gesture, share targets | **a physical device only** | §4.3 |

**Paparazzi cannot catch window insets, gesture timing or share targets.** Keep
one device pass in the loop before any release.

### 12.2 State of the checks, as of 2026-08-17

`check_design.py` **passes all four sections** (exit 0), printing one recorded
deviation. Three things were fixed on 2026-08-17 to get it there, and each is
worth knowing about:

1. **Its copy check now reads `res/values/strings.xml`, not just `*.kt`.** The
   localisation pass moved every user-facing string into the resources, and a
   check that read only Kotlin reported ~72 present strings as missing. That is
   worse than no check: a wall of false positives is how real drift stops being
   noticed. It found 3 genuine drifts once the noise was gone.
2. **`screenshots.py` was three strings behind the app** — it drew a
   "Clear score" control that no longer exists, and two strings whose copy had
   changed. Fixed.
3. **`surface` is carried in `ACCEPTED_DEVIATIONS`** with its rationale (§2.2),
   reported under its own heading rather than as drift. That list is **not** a
   suppression mechanism: an entry needs a decision recorded in `Theme.kt`, and
   it still prints both values on every run.

Still true, and not fixable by a script: **`screenshots/*.png` is a mix.** Of
its 44 PNGs, 16 are byte-identical to a current Paparazzi golden and 28 have
drifted — including several that `REAL_CAPTURES.md` still lists as real. Trust,
in order: the goldens in `../../v1/app/src/test/snapshots/images/` (58, always
current with the last test run), then the physical-device captures in
`../../../docs/screenshots/`, then `screenshots/` in this folder.

### 12.3 Where the older plan documents are wrong

`../README.md`, `../screens.md` and `../api.md` are the *proposal*. These
specific statements in them are now false:

| Document | Says | Actually |
| --- | --- | --- |
| `README.md` §Architecture | "MVVM — one `ViewModel` per screen" | There is no `ViewModel` in the module. State is `rememberSaveable` + repository flows collected in the composable |
| `README.md` §Architecture | Theme built from `theme.py`, accent `#34C759`/`#1E7A3D`, background `#F2F2F7`, cards 14dp | Built from `variants.py` `PURE_GREEN`; `primary` is `#196D2E`; background `#FFFFFF`; cards 24dp |
| `README.md` §Architecture | "CameraX for capture" | System camera via `ACTION_IMAGE_CAPTURE`; no camera permission |
| `README.md` §Architecture | "no cloud sync, no accounts" | Google sign-in ships; accounts exist for metering |
| `README.md` resolution #19 | bottom navigation declined | A bottom bar ships, driving the pager (§7.1) |
| `README.md` "Not started" | Camera Capture and Scan Review not started | Both built |
| `screens.md` §1 | Home calls `BrewSessionDao.countByDate()` | `SessionDao.dailyCounts` |
| `screens.md` §9 | Profile has avatar / Name / Email / OSS-licence rows | Rules 60 and 103 removed all four; the code correctly has none |
| `api.md` §2 | `/v1/ask` is the AI endpoint | The app calls `/v1/suggest` and `/v1/vision`; `/v1/ask` is forbidden to this client |
| `AUDIT.md` header | "Nothing here was compiled or run"; "the design is not scheme E" | The app compiles, installs and runs; the scheme E pass landed and type/shape now conform |
| `../../v1/README.md` | "33 simulated screenshots, 1080×2400"; "All four sections pass" | 45 files, mostly 360×800 Paparazzi output; one colour token and the copy check do not pass |

`scheme_e.py`'s `+2.1_create_account` page should be **retired**: it draws
email/password sign-up, a sync data statement and a 13+ affirmation. Rule 60
removed email, the no-server-storage architecture removed sync, and rule 82
raises the age to 15.
