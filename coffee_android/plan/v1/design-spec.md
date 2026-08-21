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

**Built and shipping in v1:** the four axis pages (News, Home, Can travel,
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

**A full-screen `Dialog` is a second, unrelated case of the same rule, and it
is worse.** Inside a `Dialog`, `WindowInsets.safeDrawing` reads **zero** —
the dialog gets its own window and Compose does not propagate the activity's
insets into it. `Modifier.safeDrawingPadding()` on the dialog's content
therefore pads by nothing while the content still draws behind the bars,
because the activity is `enableEdgeToEdge()`. Setting
`DialogProperties(decorFitsSystemWindows = false)` does not fix it either.
**Read the insets outside the dialog and pass them in** — that is what
`FlavorNoteSheet` does (§5.6). Measured on a real S22 before the fix: the
heading rendered under the status bar and Confirm under the navigation bar,
with 61px of screen left below a button that wanted 90 for its own margin.

**Every inset is zero under Paparazzi**, so the goldens render correctly either
way. Only a real device shows this. It is the standing argument for keeping at
least one physical-device pass in the loop.

### 4.4 The 8192px clip ceiling — the other rule Paparazzi cannot catch

**Never wrap a whole scrolling page in something that clips.** A `Surface`, a
`Card`, `Modifier.clip(…)` and `clipToBounds()` all come out as a
`graphicsLayer` with `clip = true`, which is a platform `RenderNode` carrying
`clipToBounds`. Compose answers "did this touch land inside that layer?" in
`RenderNodeLayer.isInLayer`, and for a bounds-clipped layer the answer is
literally `y < renderNode.height` — **and a RenderNode's height saturates at
8192px (2^13)**. Every touch below that line inside the node is answered
"outside the layer", and the control under the finger never hears about it.

Nothing *looks* wrong, which is why this survived two bug reports. The display
list is not cut at the same number, so the page draws to its true end and
merely stops responding. Measured on an S22 (1440×3088, density 3.75) with
`PhotoHeroPage`'s panel at 9823px: a drag at panel-local y **8191** sets its
slider, the identical drag at **8192** does nothing.

8192px is not far away. The brew form's panel is 8242px with no pour stages at
all and gains 274px per stage, so it crossed the line at the *third* stage —
which is exactly how it was reported ("once I add more than 2 stages … sour,
fermented bar and log this brew don't work anymore"). It arrives sooner on a
phone set to a larger Display size: that S22 renders at density 3.75 rather
than its native 2.8125, so the same page is a third taller in pixels.

The fix is to **paint rather than clip** — `Modifier.background(color, shape)`
draws the same rounded top without creating a layer, and hit testing falls back
to plain node bounds, which are exact at any height. Provide `LocalContentColor`
by hand when replacing a `Surface`, which is the one other thing it was doing.
If something genuinely needs clipping, clip a *child*: no card, chart or
thumbnail here is anywhere near 8192px tall.

Paparazzi misses this twice over — it never dispatches a touch, and at its
360×800 config the panel is a quarter of the height it reaches on a real dense
phone. Only a device shows it, which is §4.3's argument again.

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

**The rule is enforced by reading, not by the type system, so it drifts.**
`+1.1` shipped **Barista** — an optional one-word name — as a full 56dp
outlined box, which gave it exactly the weight of the required café name
above it. Corrected 2026-08-20 (§8.6b). When adding a field, the question is
not "is it text?" but "is it required, or long?"

**A `FieldPair` half may hang empty.** With an odd number of capsule fields
one half is blank, and that is the shape `FieldPair` was built to allow —
rendered, it reads as deliberate. Promoting the odd field back to a box to
avoid the gap is the wrong trade; it breaks the rule above to fix a
non-problem.

### 5.2 Charts and meters

| Component | Shape | Notes |
| --- | --- | --- |
| `RadarChart` | 11-axis Canvas polygon | `TextMeasurer`-based label layout, not guessed offsets. Two label sets (§5.3) and two ink styles — in-app on white, and white-on-green at 4× for the Share Card, one drawing routine. Optionally **interactive** (§5.6): pinch-zoom, pan, double-tap reset, tap-an-axis, and a ring of tasting notes hung off the labels |
| `FlavorNoteSheet` | full-screen picker | Ten note bubbles for one axis, at most five chosen. See §5.6 |
| `ExtractionBar` | −1…+1 axis, three zones | under / well extracted / over, with `VizBand` + `VizBandEdge` + `VizDeviation` |
| `ValueBar` | slide bar | Score and all eleven flavour axes. Draggable — a 2026-08-17 change: dragging directly on what had been a read-only meter proved the better control, and the palette was copied across so a slider stops looking like an unrelated second widget |
| `ContributionCalendar` | heatmap grid | `ActivityWeeks = 21`; selected cell enlarges ×1.3 |
| `DurationPickerDialog` | two snapping wheels | Pour-stage elapsed time, `m` 0–29 (1-row gap) and `ss` 0, 5, …, 55 (5-row gap, 2026-08-20 — 60 rows to dial a second nobody times a pour to was the friction), in a standard `AlertDialog`. **Not** M3 `TimePicker`: that dials an hour and a minute on a 24-hour clock and labels itself so, which is the wrong question in the wrong units for an offset from the start of a brew |

### 5.3 Two flavour-axis label sets

Same eleven axes, same fixed order, two spellings:

- **Full** (`BeanEntity.FLAVOR_AXES` / `localizedFlavorAxes()`) — Fruity,
  Floral, Tea-like, Sweet, Nutty/Cocoa, Spices, Roasted, Cereal,
  Green/Vegetative, Sour, Fermented. Used on **every slider row** and by the
  Share Card, both of which have the width of the screen.
- **Short** (`ShortFlavorAxes` / `localizedShortFlavorAxes()`) — Fruity,
  Floral, Tea, Sweet, Nutty, Spices, Roasted, Cereal, Green, Sour, Ferment.
  Used on **all three in-app radars**.

Measured label placement stops "Nutty/Cocoa" being *clipped*; it does not stop
it being the widest thing on a small card. Hence two sets.

**No radar draws the full set, since 2026-08-19.** The bean profile did, on the
reasoning that a 260dp chart had the room. It did not, and the shortfall was
not marginal: "Green/Vegetative" sits at 171.8° — nine o'clock to within a
degree — so the arm out to its anchor spends 99.8dp of the box's 130dp
half-width before its own 74dp of text begins, and the last 44dp were being
clipped against the box edge by `RadarChart`'s `clipToBounds`. Fitting the full
name at that radius needs a 348dp-wide chart, which no phone card provides, so
the choice was the short name or a radar at half size. Reported directly; see
§5.3a.

**Order is part of the format.** It matches `repo.FLAVOR_AXES` on the desktop,
and the sync bundle writes the eleven `flavor_*` **column names** in that order
— verified identical on both sides, so a bundle round-trips safely.

**One label differs from the desktop, harmlessly.** Axis 9 is `Green/Veg` here
and `Green/Vegetative` in `coffee/src/coffee_can/repo.py`. Only the *display*
string differs; the column (`flavor_green_vegetative`) is the same, which is
what the bundle carries. Worth closing for consistency the next time either
side's labels are touched — but it is not a data defect, and changing the
column name to match would be.

### 5.3a One radar size, and a measured label ring

**All three in-app radars draw at `RadarChartSize` = 260dp** — Home's shelf
average (§8.3), a bean's own profile (§8.4) and the brew form's live preview
(§8.8). They were 307dp, 260dp and 240dp until 2026-08-19, so the same eleven
axes changed scale as the reader moved between the screens that show them. The
constant lives in `ui/components/RadarChart.kt` and is that composable's
default `size`; a call site that hard-codes a Dp is drift.

`size` is the composable's **box**, not the polygon. The label ring is reserved
out of it, so the drawn radius is `size/2 × 0.66` — 85.8dp — or `× 0.48` when
the chart carries tasting notes, which reach further out than a label alone.

**The fraction is a ceiling, not a guarantee, and `labelRingRadius` is the
floor under it.** A proportion cannot know how wide a word is: 34% of the
half-box holds "Green" and does not hold its French "Végétal", and what an
under-reservation produces is a clipped word rather than a smaller chart.
`RadarChart` therefore also solves `drawRadar`'s own placement arithmetic for
the radius — `(radius + gap)·|cos θ| + labelWidth ≤ half` per axis, and the
matching sine form for a note stack — and draws at whichever of the two is
smaller. In English at the default text size the fraction wins and the
measurement costs nothing; in French it pulls the net in by about 2dp. The
Share Card already sized itself this way (`widestLabel`); this closes the same
gap on the in-app chart. Covered by `RadarChartLabelFitScreenshotTest` in three
locales.

### 5.6 The interactive radar and its tasting notes

`RadarChart` draws a static chart by default and every older call site leaves it
that way — Home draws four inside a scrolling list, where a chart that swallowed
drags would be a chart you cannot scroll past. **The brew form (§8.8) is the one
screen that turns the interaction on.**

Four opt-in parameters, all defaulting to off:

| Parameter | Does |
| --- | --- |
| `zoomable` | pinch to zoom (1×–5×, about the pinch centroid), drag to pan, double-tap to reset |
| `onAxisTap` | fires for a tap in an axis's wedge — the outer half of the spoke plus its label ring, **not** the label's text box, which is a 12px touch target |
| `focusedAxis` | animates scale and pan so that axis's label lands mid-box, magnified 2× |
| `noteLabels` | per axis, notes to hang under the label as (name, colour) |

**A tier below the eleven scores.** The axes say *how floral*; the notes say
which florals. Eleven axes × ten notes, in `ui/components/FlavorNotes.kt`:
Floral is Jasmine, Rose, Chamomile, Black tea, Hibiscus, Lavender, Honeysuckle,
Orange blossom, Elderflower, Bergamot, and the other ten axes carry an
equivalent set. **At most five per axis** (`FlavorNoteSelection.MAX_PER_AXIS`) —
past five a selection stops describing and starts being the whole list, and five
is also as many as the chart can stack under one label before neighbouring axes
collide.

**Each note carries its own colour**, the ingredient's own pulled up to a
pastel, spread far enough round the hue wheel that ten stay distinguishable in
one grid. All are light, so a single dark ink (`NoteInk`) reads on every one of
them. **These are not design tokens**: they live beside the data rather than in
`Theme.kt`, `check_design.py` does not check them, and `../variants.py` has no
opinion about them. `VizSequential` set the precedent.

**A bubble is drawn as a bubble, not as a disc.** The first attempt — one
radial fill, one white gleam, a flat rim — was rejected as looking cheap, and it
did: it had no *thin-film* behaviour at all, which is the thing the eye actually
uses to tell a soap bubble from a coloured circle. The reference is Apple's
iOS 15.4 🫧. `bubbleLayers` now draws eight layers, each answering for one
optical effect, bottom to top:

| # | Layer | The optics |
| --- | --- | --- |
| 1 | contact shadow, offset down-right, drawn *under* the bubble | a translucent shell shows its own shadow through itself, the way glass does |
| 2 | body — radial ramp in the note's colour, nearly clear in the middle, dense at the edge | a film has constant thickness, but your line of sight crosses more of it the nearer the silhouette you look. That is why a bubble is a *ring* of colour, not a disc of one |
| 3 | iridescence — five overlapping strokes of one sweep gradient at shrinking radii | interference colour lives where the film is optically thickest, so it belongs in the same annulus as the body's dense band |
| 4 | the note's colour again, as a thin edge | so the palest notes have a contour at all |
| 5 | transmitted-light crescent, low and *inside* the contour | light entering the top is refracted twice and leaves through the bottom, so the inside of the bottom rim is far brighter than the top. Set inside the edge, not on it — on the edge it just thickens the rim |
| 6 | the bright rim, angled per bubble | |
| 7 | specular highlight, up and left, **squashed and tilted** | it is a broad soft source reflected on a curved surface; a round highlight reads as a sticker |
| 8 | a small secondary glint, up and right | a second reflection, and what stops the surface reading as a single smooth dome |

Two findings worth keeping, both arrived at by rendering and looking:

- **Only a four-hue window of the interference series is used per bubble**, never
  the whole wheel. Sweeping all eight round every bubble came back as ten
  identical rainbows. The alphas alternate strong and faint for the same
  reason — a ring of eight hues at one strength is a CD, not a bubble; a real
  film shows a couple of strong bands with washed-out arcs between them.
- **A glaze of the note's colour goes back on top of the iridescence.** Without
  it the sheen wins and every bubble in the grid is the same rainbow. A film's
  interference colour is a *modulation* of what the wall already transmits, so
  re-tinting on top is both the honest order of operations and what keeps Rose
  telling apart from Lavender. **The note colour is load-bearing** — it is what
  identifies the note — so any future change to this stack has to be checked
  against that first.

The contour is still `bubbleOutline`: nine radii round the circle each knocked
off true by up to 9%, joined by quadratics whose controls are the samples and
whose endpoints are the midpoints between them — that construction is what keeps
it smooth, since curving through the sample points themselves leaves a corner at
each one. Seeded from the note key, so a note is the same bubble every time and
does not reshape when it moves in the grid. Radii are normalised so the widest
lobe is exactly the box; an outline that overflowed would be clipped square and
come back with flat sides.

**Drift**: per-bubble infinite transitions on x and y, periods
`2600/3350 ms + index × 190/230`. Two periods that differ from each other *and*
from the neighbours', so a bubble traces a slow open loop rather than a line
and ten of them never fall into step — ten circles rising together reads as a
machine. Measured on a real S22, three frames two seconds apart: Jasmine moved
30px vertically and 14 horizontally, Hibiscus 27 and 14, Bergamot 18 and 7.

**Size carries no drift.** An earlier build gave scale the same unsynced-period
treatment as x/y (a ±1.5% "breathe"), on the reasoning that a living thing
doesn't hold perfectly still. But size here is not decoration — 108dp *is*
"selected", 84dp *is* "not" — and two bubbles breathing on different periods
meant two simultaneously-selected notes were almost never exactly the same
size at any instant you looked. Reported directly against Fruity's Grape +
Blueberry. Removed; drift and the sheen's slow turn stay unsynced, since
neither carries a meaning that two must agree on.

**The shader stack renders identically under layoutlib and on hardware** —
checked on the S22, because gradients and blend modes are exactly where the two
are entitled to disagree.

**An axis sets its own name in bold when it carries notes _or_ is the focused
one.** The stack beneath a scored axis is already a visual claim on that part of
the ring, and a label at the same weight as its nine silent neighbours reads as
though the notes belong to no one in particular. Weight is the only cue left:
colour is spoken for (the dots carry note identity) and size is spoken for (the
note tier is deliberately smaller).

The **focused** half of that rule is why `drawRadar` takes `emphasisedAxis`
separately from `noteLabels`. Bolding only on the first note chosen made the
label look like it was reacting to the choice; the focused axis is the *subject*
of the picker and has to read as its heading from the first frame, before
anything is selected.

**The chart's labels are Fredoka**, like everything else in the app. They were
the one text in the build still setting in the platform sans — the Share Card's
copy of the same chart had always passed `Fredoka` + `FontWeight.Bold`
explicitly, and the in-app chart was simply never given a family. `RadarStyle`
now defaults to it, so the two agree by construction rather than by memory.

Three layout rules that were each a bug first:

- **Note stacks radiate away from the centre** — up on the top half, down on the
  bottom. Always stacking downwards ran the notes of every upper axis back over
  the chart and into the next label clockwise.
- **Notes cost radius.** A chart carrying any pulls its net in from 0.66 to 0.48
  of the half-box to pay for the margin, and the Box is `clipToBounds()` —
  a `DrawScope` is not clipped to its layout bounds by default.
- **A focused axis with notes is framed off-centre**, biased a fifth of the box
  in the direction its stack grows. Centring the label exactly — which is what
  "centre the label" literally asks for — hangs five notes off the edge.

**Every note stack is left-justified as a block** (2026-08-20, direct product
request) — one shared left edge, taken from the widest line, not one edge per
line. The old rule hung each note off its own width, which on the left half
(where the stack grows away from centre by keeping its edge *nearest* the axis
fixed) gave every line a different starting x with nothing to read down. The
shared edge is anchored at the widest line's own old position, so the stack's
outward reach — what the radius budget above accounts for — is unchanged; only
the ragged edge moves from the inside of the column to the outside.

**Zoom and pan take two fingers, and that is load-bearing.**
`detectTransformGestures` treats a *single*-finger drag as a pan and consumes
it. This chart sits in the middle of a vertically scrolling form, so with that
gesture installed a swipe to scroll the page instead dragged the chart: the page
did not move, and the radar slid out of its own box leaving a blank rectangle —
which then also made every axis tap miss. The gesture handler ignores
single-pointer events entirely so they fall through to the scroll container, and
user pans are clamped so the chart can never be pushed somewhere there is
nothing left to double-tap. **No golden can catch this**; it took a device.

**Selection is a screenshot-testable resting state, not an animation.**
Paparazzi never advances its frame clock and its `offsetMillis` overload takes a
`View`, not a composable, so bubbles that animate in from zero photograph as an
empty rectangle. Both the bubble entrance and the focus zoom check
`LocalInspectionMode` and snap to the resting state; `FlavorNoteSheetScreenshotTest`
provides it, because Paparazzi does not set it itself.

### 5.4 Imagery

| Component | Purpose |
| --- | --- |
| `BeanIcon` | a bean's mark on the shelf — its own first photo, or a generated stand-in |
| `BagTile` | that stand-in: initials on a tinted bag silhouette |
| `PhotoHeroPage` | the bean-detail hero. `HeroHeight` 224dp, `PanelPeek` 96dp, `UnknownAspectFraction` 0.62, drag-to-settle at 700f. The panel under the photo is a **painted background, deliberately not a `Surface`** — §4.4 |
| `ZoomableImageViewer` | pinch/double-tap, `MaxScale` 4× |
| `TopBarDivider` | the hairline rule under every app bar |
| `MonthHeading` | `+1`'s date grouping — the month in `titleSmall`, then a hairline to the page edge. Private to `JourneysScreen`; the rule is what ties a short heading to the full page width so it divides the column rather than captioning the print below it (§8.6) |

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
   -1            00            +1             +2
  News    ←→   HOME    ←→  Can travel  ←→  Profile
```

Implemented as one `HorizontalPager` over those four pages (`ui/Axis.kt`), with
every `0.x` page pushed on top of it.

**`+1` changed hands on 2026-08-19.** It was Sessions, the brew log; it is now
Can travel, the journeys page (§8.6). Sessions was not removed — it became a
pushed `0.3`, reached from Home's History action — and its whole family was
renumbered with it, because in this scheme a number states *how a screen is
reached*, not what it contains:

| was | is | screen |
| --- | --- | --- |
| `+1` | `0.3` | Sessions |
| `+1.1` | `0.31` | Brew Session Detail |
| `+1.1a` | `0.31a` | Pick Bean |
| `+1.2`…`+1.6` | `0.32`…`0.35` | the brew form's sheets and dialogs |

`+1.1` now means the journey profile (§8.6b), under the new `+1`. This is the
second slot to change hands: `-1` was Can Drink before it was News.

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
| `PickBean` | `0.31a_pick_bean` |
| `NewBean` | `0.1_bean_profile` |
| `BeanDetail` | `0.2_bean_detail/{beanId}` |
| `Sessions` | `0.3_sessions` |
| `BrewSession` | `0.31_log_brew/{beanId}/{sessionId}` |
| `NewJourney` | `+1.1_journey` |
| `JourneyDetail` | `+1.1_journey/{journeyId}` |
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

Empty state: the **pour-over mascot** at 160dp — the same figure `0.3`'s empty
state uses, replacing the brand lockup on 2026-08-19 (the lockup opens the
splash and the sign-in page, so a third appearance here made the first screen
after the splash look like the splash again) — over the headline, one
sentence and a CTA carrying the deck's idle wiggle (1000ms shake, 4000ms rest).
Search is the shelf heading's action.

**The top bar carries one worded action, "History"**, and it **pushes** `0.3`
Sessions (2026-08-19, direct product request). It was a pager move for as long
as Sessions was `+1`; when Can travel took that slot the action stayed and its
mechanism changed, which is the same fact the renumbering in §7.1 records.

**The FAB logs a brew** — it raises the same hoisted "which bean?" sheet
`0.3` Sessions' FAB does, so a "+" means one thing wherever it appears. It has
been both things twice; the current call is 2026-08-19. Adding a bean did not
lose its door: that sheet offers "Add a new bean", and an empty shelf shows its
own CTA.

### 8.4 `0.1` / `0.2` / `0.2b` Bean Detail

The largest screen in the app (1400 lines). One bean, created or edited.

- **Photo hero** (`PhotoHeroPage`) — the bag photo, draggable panel, Images
  strip, zoomable viewer.
- **Scan card** — "Scan the label to update these fields", with offline and
  consent-blocked variants.
- **Fields** — name as an outlined box; origin, variety, altitude, roaster,
  producer, process, roast date as capsules two to a row; note free-text.
- **Sessions list** (`0.2`/`0.2b` only — an unsaved `0.1` bean has none yet),
  delete-with-cascade confirm, discard-draft confirm, share disc.
- **Delete** (`0.2`/`0.2b` only) sits beside Save at the foot of the panel
  (`RemoveButton`), not as `PhotoHeroPage`'s pulled disc — that placement
  moved here 2026-08-20, direct product request. `DeleteBeanDialog` still
  gates the actual delete; only the reach changed. Share stays the photo's
  top-right disc. Save carries the row's weight (`Modifier.weight(1f)`) and
  Delete wraps its own icon+label — the row's primary action, not a coin
  flip between two equal buttons.
- **Flavour** — radar plus a manual-override sheet. `flavorSource` is `auto`
  (averaged from this bean's sessions) or `manual`. On `0.2`/`0.2b` this sits
  below the sessions list, not above it — the radar reflects those sessions,
  so it reads as their summary rather than a caption ahead of them. On `0.1`
  it stays directly under Fields since there is no sessions list yet to
  follow.

**New beans are held as in-memory draft state** (`rememberSaveable`) until the
first real edit or explicit save — `status` is `draft` until then. A screen the
OS kills mid-flow never orphans an empty row.

### 8.5 `0.11` / `0.12` / `0.13` Photo source → Scanning → Scan Review

Photo source sheet (take a photo / choose a photo), scanning state, then
**Scan Review**: the guessed fields, each editable, with "was:" hints showing
what would change, an empty-read state, and a report control.

Nothing reaches the form until the user accepts.

### 8.6 `+1` Can travel

The cafés you have been to, as a stack of Polaroids — square photo, 10dp
surround, a deep chin carrying the café's name and `city · date`. One column,
**232dp** wide and centred, each print at a tilt of up to ±1.6° seeded by its
own row id (`PolaroidCard`), **grouped under a month heading**. Empty state:
`MascotEiffel`, this app's **only piece of original mascot artwork** — every
other pose is exported from the design deck, so this is the one figure whose
Kotlin is the original and whose `screenshots.py` twin is the copy.

#### The ground, and why these two screens have one (2026-08-20)

**`+1` and `+1.1` draw on `surfaceContainerLow`, not `background`.** This is
the load-bearing change of the redesign and it is worth stating as a rule:
*this app's one page of white objects needs something to be white against.*

Everything on these two screens is `PolaroidPaper` (#FDFDFA) — the prints, the
camera's body, the three sheets in the stack — and `surface`/`background` is
`#FFFFFF` (§2.2's accepted deviation from the deck's `#F2FAF2`). Rendered
honestly, the print **dissolved**: its grey emulsion square floated above two
lines of text with no object around them, and `PolaroidCard`'s 3dp shadow was
carrying the entire silhouette alone. §2.2's stated answer — "adjacent cards
are separated by an inset rule and a standalone block by its own heading" —
is an answer for *cards and text*, and does not reach content that is
literally white paper.

`surfaceContainerLow` is an existing token, ~4% off white, so swiping in from
Home does not jar. Two things fall out of it for free:

- the prints and the stack read as objects lying on a surface again, which is
  the entire concept these screens were built on;
- **`+1.1`'s "Open in Maps" card becomes visible.** It is `CardColor`
  (#FFFFFF) with no outline and no elevation, so on a white page it rendered
  as a pin glyph and two lines of text with no boundary and no affordance —
  the one row on the page that fires an `Intent`, drawn as if it were static
  copy. It now reads as a white card on a tinted ground, and carries a
  trailing chevron as well.

**This was invisible in the simulator until 2026-08-20**, because
`screenshots.py` carried the deck's `#F2FAF2` for `surface` while claiming to
be `Theme.kt` token-for-token — so every frame it had ever produced drew white
cards on a tinted page, contrast the build did not have. `check_design.py`
knew (`ACCEPTED_DEVIATIONS`); the simulator never got the memo. Corrected.

**Redrawn twice on 2026-08-20**, both times on direct product rejection —
first for standing can-boy wedged between the tower's legs, then for
*"the lines are granulate, it just doesn't like EIffel, and the can boy also
don't know what it is doing"*. Three things came out of the second pass, and
they are the ones worth not undoing:

- **The tower's outline is a single path**, ground → spire → ground. It used
  to be eight strokes meeting end to end, and each joint stacked two round
  caps into a visible lump. That was "granulate", and it is why the outline
  must not be split back up for per-section stroke weights.
- **The profile is generated, not eyeballed** — `w(h) = 15.8·exp(−2.3195·h)`,
  sampled at the real platform heights (18% / 35% / 85%) and fitted with
  C1-continuous cubics from the analytic tangent. The concave flare is the
  Eiffel's signature; a straight taper is a pylon, which is what the first
  pass drew. **The great arch is restored** — dropped in the original
  2026-08-19 figure because can-boy stood inside the legs and white-on-white
  cannot occlude, a constraint that died when he moved out from under it.
  Of every change tried, adding the arch moved the read the furthest.
- **He leans back from the waist, not the feet**, so both feet stay on the
  tower's ground line, and his head cocks *toward* the tower (the first pass
  tilted it away, which is what "doesn't know what it is doing" was). The
  pull tab is the only asymmetric feature on a faceless figure, so keeping it
  aimed up at the spire is the closest thing to a gaze direction available.

Verified legible at 184dp, 96dp and 64dp. See `CanBoyEiffel`'s docstring for
the fault-by-fault reasoning and what was tried and cut.

**Each journey is a stack of its three prints, two to a row**
(`PolaroidStackCard`, 2026-08-20, direct product request: "the stack size will
allow two stacks can be tile in the same line"). This page argued for a single
column for a long time, on the grounds that a 2-up grid "halves the print" —
true while a cell was *one* print whose picture had to be worth looking at. A
cell now stands *for* a journey rather than displaying one, so it survives at
half width where a lone photograph did not, and the page shows four cafés where
it showed one and a half. **The pile is as deep as the journey has photographs** (2026-08-20, direct
product request) — three sheets always told the same story about a café with
one picture and a café with three, and the count is real information the
drawing was throwing away. Floored at one: a café with no pictures is still a
single unexposed sheet, because zero sheets leaves a caption floating with no
object under it. The sheets behind carry their own photographs now rather than
being blank paper, which is the evidence for the depth. Only the front sheet
carries the chin caption. Its sheets take 0.88 of the lane so the 18dp
splay lands inside it, and the chin is 46dp because two caption lines measure
~41dp — 34dp sheared the date off along its baseline, which the golden caught.

**Months group before journeys pair**, never the reverse: chunking the flat
list into twos and reading the month off the first of each pair files a 31 July
journey under August whenever a month ends on an odd count.

**The FAB is the Polaroid camera** (`PolaroidCameraButton`, 2026-08-20, direct
product request) — the same drawing `+1.1` uses at a third the size, 60dp of
box putting its body at roughly a Material FAB's 56dp span. A Material FAB is
this app's generic "make one of these": right on the shelf, wrong on a wall of
Polaroids. A first pass drew a *print* with a `+` on it, which had it backwards
— a print is what you end up with, the camera is what you press. Every detail
survives the shrink; checked by rendering at 52/68/76dp before choosing 60.
It flashes on the same 4.4s loop as `+1.1`'s — see §8.6b.

**There is no arrow, and one was tried.** A bowed `DoodleArrow` swept from the
empty state's copy down to the camera in the corner, on the reasoning that this
FAB does not look like a FAB. Rejected the same day — "tooo ugly": it was the
one grey diagram line on a screen whose whole register is white paper objects,
and the heaviest mark in the empty state after the mascot. The component is
deleted, not disabled. The copy names the camera and the camera flashes; the
words and the motion do the pointing.

It still goes straight to a blank `+1.1`. There is no "which one?" sheet in
front of it, unlike the brew FAB, because a journey belongs to nothing.

#### Two prints fit, and months replaced the subtitle

**232dp, down from 288.** A print is `width + 64dp` tall, so 288 gave 352dp
and fitted one and a half on a 360×800 screen — a five-café trip was five
screens of scrolling. 232 gives 296dp and fits two whole prints plus the next
month's heading. The "big enough to actually look at" argument above is about
not being a *thumbnail*; 232dp is not one.

**`Newest first · N journeys` is gone**, replaced by `MonthHeading` — the
month in `titleSmall`, then a hairline to the page edge. The subtitle was one
line restating the sort order plus a number nobody needs; grouping says the
same thing structurally (the order *is* visible once the months are) and adds
the one axis a travel log actually has. The rule is not decoration: it ties a
four-word heading to the full page width so it reads as dividing the column
rather than as a caption that drifted above the print below it.

Grouping is done **in the composable, not the repository** — the month is a
property of how this page reads, not of a journey, and nothing else in the app
asks. `observeJourneys()` already returns newest-first, so emitting a heading
whenever the month changes is the whole algorithm. Headings are keyed on the
month string so the list does not rebuild them all when one journey moves.

**Month labels are `Locale.ENGLISH`, matching `PRINT_DAY`**, which has always
formatted print captions in English regardless of app language. A localised
heading would sit directly above an unlocalised caption — "août 2026" over
"16 Aug 2026". Localising *both* is a separate change with its own goldens.

**Tried and rejected, all by rendering them:**

| Direction | Why not |
| --- | --- |
| Per-month count on the right of each heading | Duplicates the prints directly beneath it, and buys a plurals resource in three locales |
| Keeping the subtitle above the first month heading | Two stacked headings; read as clutter immediately |
| **Scatter** — prints alternating left/right at ±2.6° | The next print ran over the previous one's chin. The caption is the data on this page |
| **Pile** — prints overlapping vertically | Buried every caption but the last. Good object, wrong content |
| A hairline border on the print paper | Works, but reads as a bordered card rather than as paper. The ground solves it without touching the object |

### 8.6a `0.3` Sessions / History

**A cup's row is green** — `JourneyGround`, the exact ground `+1` and `+1.1`
lie on (2026-08-20, direct product request). A cup is a session with a café
attached, so it lands in this list beside brews made at home and without a cue
the two are indistinguishable. Reusing the travel side's own token is the
point: a green row reads as "one of those" rather than as a status this list
invented. Nothing else changes — same height, same glyph, same divider —
because a cup is not a different *kind* of record, just one drunk elsewhere.

Every brew across every bean, newest first, with the dripper glyph at 64dp,
dose, score and extraction verdict. Header states the count. Empty state and
delete are both built. A **pushed** destination since 2026-08-19, reached from
Home's History action — so it carries a real back arrow again, and it no
longer claims `AxisPageInsets` (there is no axis Scaffold above a push, so
claiming only top and sides would leave its last row under the system bar).

### 8.6b `+1.1` Journey Profile

One café: name, visit date, city, **address**, **barista**, note, and up to
three photographs. No scan card (a café has no label), no radar (a journey has
no flavour), no sessions list (a brew belongs to a bean).

**A Polaroid camera and its prints, not a photo hero** (2026-08-20, direct
product request). The page opens on a drawn Polaroid camera at 156dp, then its
caption, then three sheets of film tiled across the gutter (`PolaroidTiles`).
The block reads top to bottom as: press this, here is what it does, here is
what came out. The first build shipped the film with no camera at all —
"where is polaraid camera?" — having read "draw a Polaroid" as the print
rather than the device.

**The camera is the shutter.** Tapping it opens the photo-source sheet — "tap
on the polaroid to take picture or import form album" — which leaves the prints
free to be prints: a tap on one opens it, and an empty sheet is simply empty
rather than a second add button.

**"Tap me", hand-lettered on the camera's hood** (2026-08-20, direct product
request), replacing an arrow and a grey label that were rejected as "tooo
ugly". It is **drawn as strokes, not set in a font** — the logo's white line,
the register `CanBoy.kt` draws every mascot in — and it **swings left–right**
on a 2.6s eased loop, deliberately not a multiple of the flash's 4.4s so the
two drift in and out of phase rather than locking to one beat.

**Its placement was decided by contrast, not by taste.** The request was white
lettering upper-left of the camera; the page's ground is `surfaceContainerLow`,
on which `#FFFFFF` measures ~1.1:1 — the exact failure that killed the arrow.
Three renders were compared: white outside the camera (invisible, confirmed by
eye), `onSurfaceVariant` outside it (legible, but no longer the white line that
was asked for), and white **on the hood** — the only dark field on the screen,
where white sings. So the mark rides on the camera. Its numbers are a
clearance budget: the viewfinder ends at x=43 and the flash window starts at
x=132 in the camera's 200-unit space, so the lettering runs 50→122 and reaches
45→127 at full swing.

**The "Tap the camera to add a photo" caption survives alongside it**, which
looks redundant and is not: "Tap me" is a *label on the object* saying which
thing is pressable, the sentence says what pressing it does. The mark vanishes
once one photo exists; the caption stays until all three sheets are used.

**TILED HERE, STACKED ON `+1`.** The sheets emerged from the camera's slot as
an overlapping pile until 2026-08-20, when the request moved the caption under
the camera and asked for the papers tiled below it. The pile had a real cost on
*this* page: two of the three pictures were permanently a few millimetres of
paper edge, reachable only by tapping a sliver to bring them forward. Tiling
shows all three at once, which is what a page about one café's photographs
should do — and it deleted the front/back state, the reordering tap and the
z-order hit-testing rule with it. The stack survives where it is still right:
`+1`'s list, where a cell stands *for* a journey rather than showing its
contents.

**The flash fires, then waits four seconds, forever.** Both cameras — this one
and the `+1` FAB — loop a white burst out of the flash window: keyframes, not a
reversing tween, because a flash is a hard spike and a slow decay rather than a
wave (a reversing tween spends half its cycle un-flashing, which reads as a
lamp on a dimmer). **The long dark tail is the effect**: at a 1s cycle this is a
blinking light and therefore an error indicator; at 4s it reads as a camera
someone is idly taking pictures with. Frozen at 0 under `LocalInspectionMode`,
so the goldens capture the resting camera.

**The camera's five livery colours are not palette and `check_design.py` does
not check them.** They are the object's own identity, the single cue that says
Polaroid rather than "a camera" — the same standing `FlavorNotes.kt`'s bubble
fills have, and the one place in this app where a non-palette colour is right.

**The film is the capacity.** Three sheets is the cap (`PolaroidStackCapacity`)
— there is no overflow row and no "+N", because the drawing *is* the limit.
Empty sheets are drawn unexposed rather than as placeholder tiles, the same
argument `PolaroidCard` makes for the list.

**This collapsed the two states into one.** `+1.1` used to be two layouts: a
blank journey as a plain form, a saved one as `PhotoHeroPage`'s hero-and-panel
with delete on the pulled disc. The hero was the only structural difference,
and a blank journey's film is three unexposed sheets — a state the drawing
already has. So there is now one app bar over one column, and delete sits
beside Save (`RemoveButton`), the same relocation `0.2` and `0.31` took.

**There is no embedded map, by decision.** An "Open in Maps" card fires a
`geo:` intent carrying the address to whatever maps app the user has.
Embedding the Maps SDK would put a second network destination inside an app
whose "talks to `coffee_server` and nothing else" property is what lets
`legal-accounts.md` §3.8 say what it says, and would add an API key, a tile
fetch and a Data safety change — for a feature whose job is to answer "where
was this?".

**Latitude and longitude are gone from the form** (same request). The card now
always uses the search form, `geo:0,0?q=<address, city>`, rather than centring
a pin. **The columns remain** on `journeys`: dropping them means rebuilding the
table, which would destroy coordinates a user typed with no server-side copy to
restore from, and §2's additive-only rule outranks tidiness. Nothing reads or
writes them. **Nothing here is ever sensed** — the app holds no location
permission and asks for none, and that was true of the coordinates too.

**The barista is a person who is not the user.** Free text, optional, never
required, never leaves the device, matched against nothing.

#### The 2026-08-20 redesign

**The page draws on `surfaceContainerLow`, like `+1`** — see §8.6's "The
ground". That is what makes these two one place rather than a warm list
followed by a plain Material form, and it is what makes the Open-in-Maps card
visible at all.

**The camera-and-stack block came in from 321dp to ~275dp** (camera 180→156,
stack 152→132, scaled by the same factor so the camera stays wider than the
print). On a *blank* journey that block is empty apparatus above an empty
form, and 321dp of it landed before the first field. Rendered at both sizes,
156 loses nothing: the hood, lens and livery all still read, and the camera
remains the page's obvious first action rather than merely its largest object.

**The form is sectioned** — *Café* (name, then address | city as a capsule
pair), *The visit* (visited on | barista). **Address became a capsule**
(2026-08-20, direct product request: it should match the date and barista
boxes) — as a full-width field it made the optional half of the location as
heavy as the required café name, the same §5.1 rule the barista was demoted
for. **Notes is gone** (same request): its column survives unread, for the
reason the coordinates do, and the Cups block now carries the "what was it
actually like" half of a visit that a journey note stood in for. The first heading was *The place* and was
renamed on request; city moved up into it, because a café's city does not
change between visits where the date and the barista do, and moving it is what
lets *The visit* be a genuine pair instead of a capsule with an empty half. Six fields, a map row and a note ran as
one undifferentiated column, which on a blank journey is eight identical empty
things to work down; three headings turn it into three short answerable
questions for about 60dp.

**Barista is a capsule now, not a 56dp outlined box** — this screen was
breaking §5.1's own rule ("outlined box for a required or free-text field,
capsule for everything else") by giving an optional one-word name exactly the
weight of the required café name. The demotion is the point, not the ten
pixels. It **hangs on a half-row**: there are three capsule-able fields and
`FieldPair` lays out two, and a hanging half is the shape `FieldPair` was
built to allow. Tried and rejected: promoting it back to a box (breaks the
rule again) and pairing it with the address (a street line truncates badly in
a 30dp half-width pill).

**The map row gained a trailing chevron.** It is the one control on the page
that leaves the app, and a `CardColor` card with no outline and no elevation
is a very quiet boundary for that. The chevron is the platform's own "this
goes somewhere" mark and costs one glyph.

**The blank state was checked, not assumed.** The concern was that a new
journey opens on a lot of empty apparatus. Rendered, it does not read that
way: the camera is unmistakably the call to action and the three unexposed
sheets read as film waiting, which is the state the drawing already has (see
"The stack is the capacity"). No separate blank-state layout was added — that
is the collapse this screen just made, and re-splitting it to save 275dp would
trade a structural simplification for a cosmetic one.

**The Cups block** sits below the fields on a *saved* journey: what you drank
here, each row a cup, with an "Add a cup" action opening `+1.2`. Absent rather
than disabled on a blank form — a cup needs a café to belong to, and offering
the action before the café has a row would mean inventing one behind the
user's back, the same rule `0.2`'s sessions list follows.

### 8.6c `+1.2` Cup Profile

One **cup**: a coffee you drank at a café. The page is, in order, `0.1`'s
identity fields (`BeanFieldsGrid`), `0.1`'s images strip (`ImagesStrip`), then
`0.31`'s **Brew details**, **Pour stages**, **How was it** and **Flavor**
(`BrewFormSections`). Direct product request, 2026-08-20.

**A cup is a bean plus a session, not a third kind of thing.** Saving writes
one `BeanEntity` (what the coffee was) and one `SessionEntity` (how it tasted)
whose `journeyId` points at the café. Nothing new was modelled, and two things
fall out free: the cup appears in History because History lists sessions, and
every section on the page is the real one rather than a lookalike.

**Every block is borrowed, and that drove a refactor.** The four brew sections
were inline in `BrewSessionScreen` and had to be lifted into
`BrewFormSections` — ~230 lines carrying eleven flavour sliders, a radar, a
stage editor and thirteen capsules, which is the largest block in the app a
second copy could have happened to. The extracted composable is **stateless**:
every mutation leaves through `onDraftChange`/`onStagesChange`, so two screens
that keep their drafts in different places share one UI. Verified as a pure
refactor — all 94 goldens passed unchanged immediately after the move.

**What deliberately did not come along:** the Ask-AI action, the "asking…"
spinner, the error line and the consent-blocked notice. Those are
`AiGateHost`-gated and a cup's AI story is a decision nobody has taken, so
`+1.2` has none; `detailsHeader` and `afterDetails` are the slots that let
`0.31` inject them without the shared file knowing what an AI gate is.

**`editing` is always true here.** A cup has no Modify/Save-changes mode:
unlike a brew, you write it down once at the café rather than returning to a
recipe you keep adjusting.

**No scan card.** It is `0.1`'s, consent-gated, and unreasoned-about for a cup.

### 8.7 `0.31a` Which bean? → Pick Bean

The FAB opens a sheet with three choices, in this order since 2026-08-21
(direct product request): **Add a new bean**, **From Coffee Can**, **Vibe
brewing** (log now, name it later). The deck drew *From Coffee Can* first,
which was right while that row listed beans inline — the sheet opened on what
you already had. It now pushes `+1.1a` like the others, so all three are
equally a destination and the commonest reason to be here (a bag you have just
opened) leads. Pick Bean is its own screen. The sheet is raised by Home's FAB
**and** by `0.3` Sessions', through one hoisted in `Nav.kt` — which is what let
Home's FAB take over Sessions' job.

**Vibe brewing does not leave a bean behind if you back out.**
`createBlankBean()` inserts a real row the moment the row is tapped, because a
session needs a parent; backing out of the form used to strand a nameless,
photoless, brewless bean on Home's shelf as "Unnamed bean" (Home does not
filter on `status`, so marking it a draft would not have hidden it).
`BrewSessionScreen.leaveWithoutSaving()` now deletes it. **The test is
emptiness, not provenance** — nothing is threaded down to say "this came from
vibe brewing", because a bean with no name, no photos and no brews contains
nothing whatever its origin, and this is the only path that can produce one
(Bean Detail refuses to save a nameless bean). Discarding counts as leaving
without saving; an explicit save does not.

### 8.8 `0.31` Brew Session Detail

One brew, created or edited (1001 lines). Brew fields (dripper, grinder, grind
size, filter, dose, water, temperature, ppm, humidity, total time), **Pour
stages** with its own editor sheet, then **How was it?** — Score `ValueBar`,
`ExtractionBar`, note — then **Flavor**: the radar over eleven `ValueBar`
sliders.

**The radar here is the interactive one** (§5.6). Tapping an axis zooms the
chart onto that label and opens `FlavorNoteSheet`, a full-screen picker of ten
tasting-note bubbles for that axis; confirming hangs the chosen notes off the
label. Zoom and pan stay available whether or not the form is unlocked —
*reading* five notes stacked under each of eleven labels is what the zoom is for
— but taps only open the picker while `editing`, the same condition every field
answers to. Each slider row also carries the axis's notes as a trailing button,
which is the reachable way in: a `Canvas` has no accessibility nodes, so a
chart-only affordance would put the feature out of reach of anyone not using
their eyes to find it.

Drafts, discard confirm and delete confirm are all built. Ask-AI opens as a
sheet over the form.

**Delete** (an already-saved brew only) sits beside Modify/Save changes at
the form's foot (`RemoveButton`), the same relocation as Bean Detail's and
for the same reason — moved off `PhotoHeroPage`'s pulled disc 2026-08-20,
direct product request. `DeleteBrewDialog` still gates the actual delete.
Modify/Save changes carries the row's weight; Delete wraps its own
icon+label, same sizing rule as Bean Detail's.

**A new brew pre-fills from the bean's last one** — dripper, grinder, grind
size, filter, dose, water, temperature and ppm, i.e. the whole **Brew details**
section. Never the result: no score, no extraction, no tasting axes, because
carrying those over would be the app recording an opinion the user has not
formed. Pour stages are *not* carried; the pour plan is what changes between
brews of the same bag. The pre-filled values become the dirty-check baseline,
so a reused form does not open asking to be saved.

**Modify shows a disabled Save, and this reverses a 2026-08-17 decision.** The
third button state used to render *nothing* until the form was dirty, on the
reasoning that a greyed button on a form you have just been told to edit reads
as a fault while an empty slot reads as "not yet". In use it did not: pressing
Modify appeared to do nothing, because the one control that had been there
vanished, and the only evidence the form had unlocked was the fields going live
further up the page — off screen, since the button is at the bottom. Save now
appears the moment Modify is pressed, disabled until something differs. The
guard the empty slot used to encode survives in `enabled`, so a write that would
do nothing but bump `updatedAt` is still impossible.

**The per-axis Notes affordance exists only while editing.** On a locked form a
disabled "Notes" button on all eleven rows is eleven invitations to press
something that cannot be pressed. Read-only rows keep the *answer* — the chosen
note names, as plain text — and drop the control; an axis with nothing chosen
shows nothing at all rather than greying out.

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

Room, mirroring `coffee-can`'s SQLite schema column-for-column — **except the
last two tables, which have no desktop counterpart at all**.
**`version = 5`, `exportSchema = true`**, with named `MIGRATION_1_2`,
`MIGRATION_2_3`, `MIGRATION_3_4` and `MIGRATION_4_5`.
`fallbackToDestructiveMigration()` is banned.

Eight entities:

| Table | Notes |
| --- | --- |
| `beans` | identity + provenance, `status` (`draft`/`saved`), `flavorSource` (`auto`/`manual`), and **eleven flavour columns** |
| `bean_images` | `position`, `filePath`, `rotation` |
| `sessions` | brew parameters, `score`, `extraction`, note, **the same eleven flavour columns**, and `flavorNotes` |
| `session_stages` | one pour each |
| `catalogue_items` | crawler cache |
| `news_items` | feed cache — four fields, no snippet column |
| `sessions.journeyId` | nullable, indexed — the café a brew was drunk at, which is what makes it a **cup** (§8.6c). **No foreign key, deliberately**: a cascade would delete a brew because the user tidied away a café, so deleting a journey orphans its cups back into ordinary brews. **Sync ignores it** — `sync_tools._SESSION_FIELDS` is an allowlist and `SyncBundle.toSessionEntity` builds by name, so neither side changed and a cup exported to the desktop arrives as an ordinary brew, which is honest since the desktop has no journeys table |
| `journeys` | `+1`'s cafés: name, `location` (city), `address`, `barista`, `visitedAt`, note — plus `latitude`/`longitude`, retained but no longer read or written (§8.6b) |
| `journey_images` | `position`, `filePath`, `rotation` — the same contract as `bean_images`, in its own tree under `filesDir/journey_images/` |

**`journeys` is the first table whose shape is ours to choose**, and two
consequences follow that are easier to state than to rediscover. The sync
bundle does **not** carry journeys — `coffee_agent/sync_tools.py` has nothing
to write them into, and inventing a bean-side column for them would be exactly
the drift the column-for-column rule exists to prevent. And `journey_images/`
had to be added to `data_extraction_rules.xml` by hand: the Auto Backup
exclusion names `bean_images/` by path, so a second image tree is *not*
covered by inheritance.

`BeanImageEntity` and `JourneyImageEntity` both implement `HeroPhoto`
(`position` + `filePath`), which is what lets `PhotoHeroPage` draw either
without a second copy of itself and without the two tables sharing rows.

**The eleven flavour columns exist on `sessions` as well as `beans`, and that
is what makes `auto` work**: a bean with `flavorSource = auto` derives its radar
by averaging its sessions. A sync bundle carrying only the bean columns imports
beans that can never recompute one.

**`sessions.flavorNotes` holds the tasting notes under each axis** (§5.6), as
one nullable TEXT column keyed by axis *slug* — `{"floral":["jasmine","rose"]}`,
never by index, so the desktop reads a name it already has a column for instead
of both sides agreeing about list order forever. `FlavorNoteSelection` owns the
format and is the only thing that should read the string. Note *keys* are
stored, never names: the app ships in three languages and a bundle written on a
French phone has to import as the same notes on an English one.

It is a column and not a join table because it is a small closed list per row
that nothing queries *by* — no screen asks which sessions taste of jasmine, they
all ask what this session tastes of, which is the row already loaded.

Sessions carry it and **beans do not**: a bean's radar is the average of its
sessions and there is no average of "jasmine" and "bergamot".

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
| Rendering | Paparazzi, `app/src/test/…/screenshot/` | 68 goldens in `app/src/test/snapshots/images/` — real compiled Compose through layoutlib, no emulator |
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
in order: the goldens in `../../v1/app/src/test/snapshots/images/` (68, always
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
