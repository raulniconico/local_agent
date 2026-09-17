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
| `titleSmall` | 14sp | SemiBold | -- (see the note on section headings below) |
| `bodyLarge` | 16sp | Normal | body copy |
| `bodyMedium` | 14sp | Normal | secondary copy |
| `labelLarge` | 14sp | SemiBold | button labels |
| `labelMedium` | 12sp | SemiBold | chips, pills |
| `labelSmall` | 11sp | Medium | captions |

**Section headings are 20sp, which is not a role.** `SectionHeader` --
"My beans", "Images", "Radar", "Cups" and the rest -- has been raised twice by
direct product request: off `titleSmall` (14sp, the same size as the body copy
under it) onto `titleMedium` on 2026-08-17, and onto a flat **20sp** on
2026-08-22. It stays a per-component override rather than becoming a twelfth
role because the next rung up, `titleLarge` at 22sp, is what the axis's app
bars draw their titles with, and a heading at exactly the screen title's size
flattens the hierarchy instead of sharpening it. The constant is
`SectionHeadingSize` beside the composable; `screenshots.py`'s `section()`
carries the same number, and `SECTION_GAP` beside it carries
`SectionHeaderGap` (§4.2).

**Three app bars moved up with it.** `+2.2a` Privacy, `+2.2b` How we use AI and
`0.1` Add bean drew their titles at `titleMedium` while the other six used
`titleLarge`; at 16sp they would have been *smaller* than the headings beneath
them. They are `titleLarge` now, so every bar on every screen is one size.

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
| `SectionHeaderGap` | 24dp | every section heading to its content, on every page |
| `SectionSpacing` | 20dp | the end of one section to the next section's heading — and where `SectionRule` draws |
| `SectionCardPadding` | 16dp, **top 0** | inside a card that sits directly under a section heading |
| `ShelfCardHeight` | 124dp | Home's bean card: `ShelfTile` plus `ShelfCardPadV` above and below |
| `ShelfTile` | 104dp | the artwork inside that card |
| `SessionCardHeight` | 80dp | a brew row: `SessionGlyph` plus the same padding |
| `SessionGlyph` | 64dp | the dripper disc inside that row |
| `ShelfCardPadH` / `PadV` | 12dp / 8dp | card padding |
| `RadarLabelTrim` | 20dp | label band a *static* radar's box may stop paying for |
| `ContributionCalendarHeight` | 169dp | derived, not chosen — see `GridTop` |

`Gutter` is not a Material metric and not a per-screen decision: it is why a
card edge lines up with a section heading lines up with a divider on every
screen. It was 20dp in the first build, which compounded with the type scale
into a measurable density gap.

**`SectionRule` is the line between one section and the next** (2026-08-30,
direct product request: a split line between sections on Home, then "apply … to
every page except can read"). A `HorizontalDivider` in `outlineVariant`, in the
page's own gutter, on every page that has sections: `00` Home, `0.1`/`0.2` Bean
Detail, `0.31`/`+1.2` Brew and Cup, `+1.1` Journey, `+2` I can, `+2.2a` Privacy
and `+2.2b` How we use AI. **`-1` Can read is the one page without it, and not
by exception** — it is a feed of cards with no `SectionHeader` anywhere on it,
so the request's carve-out took no code.

Three rules govern where it goes, and the last two are what keep it from
becoming decoration:

- **It replaces `SectionSpacing`, it never adds to it.** The rule lands on the
  midpoint of `SectionSpacing + SectionHeaderTop` — the whole distance from a
  section's last pixel to the next one's first word — and the two spacers it
  emits sum to the single one it replaced. Every page is exactly as tall as it
  was, which on Home is the difference between the flavour card being above the
  fold and below it (§5.8).
- **Never under a page's own header.** `0.2`'s panel headline, `+1.2`'s bean
  summary, `+1.1`'s Polaroid stack and `+2`'s avatar are not sections; a rule
  under one reads as chrome divided from content on a page that has no chrome
  there — the same argument that removed `TopBarDivider` from `+1.1` and from
  `0.2`'s panel on 2026-08-25. **The first section of a page gets no rule above
  it.** Two call sites are conditional for exactly this reason: `0.2`'s rule
  above Sessions is drawn only while `editing` (in view mode the basics block
  above it is absent, so Images becomes the first section), and `0.31`/`+1.2`'s
  rule above the brew sections only when the bean block is shown.
- **Never between the items *inside* a section.** The inset hairline between
  Home's bean cards went out with the same request that brought this one, and
  **`SessionCardDivider` and the pour-stage rule went out the next**
  (2026-08-30: "remove split line between session card, and split line between
  stages"). It is one decision: if a horizontal line means "a new section starts
  here", it cannot also mean "here is the next bag of coffee", "the next brew"
  or "the next pour". Brew cards abut on `0.2`, `0.3` and `+1.1` and are told
  apart by the air around each dripper disc, exactly as beans are; pour rows are
  told apart by the number down their left and the 12dp each pads by. There is
  no `SessionCardDivider` any more, and no rule under the last stage — that one
  had also been closing the section with a line that meant nothing.

  **`+2.5`'s share card keeps its rule between cups, and that is not drift.**
  In the app a cup is a dense row; on the card it is a name, a photograph, a
  facts line and its own radar, with 28dp of air either side of the line — what
  it separates is closer to two sections than to two rows.

**`SectionHeaderGap` is one number for the whole app** (2026-08-24, direct
product request: "unify all section-title margin in all the pages, use the
Images section margin by default"). It was 16dp, which is what the images strip
had always shown, and is **24dp since 2026-08-30** — half again, by direct
product request, tried on one Home section and then applied everywhere. Being
one number is what made that a two-line change: the trial needed a per-caller
override on `SectionHeader`, and promoting it meant deleting the override again
rather than leaving a knob behind for the next caller to reach for. `SectionHeader` emits it itself; **callers must not add a
`Spacer` after a heading**, which is how three different gaps came to exist —
8dp from the composable, 16 wherever a caller added its own, and 20 on any
heading carrying a verb. That last one was invisible in the source: a
`TextButton` is 48dp tall (Material 3 floors a clickable `Surface` at the
minimum interactive size) against a 24dp text box, and the Row centres both, so
an action left 12dp of dead space under its heading. `SectionHeader`
*subtracts* that slack from the gap rather than letting it add to it — the
button keeps its full touch target and "Sessions" ends the same distance above
its list as "Images" does above its photographs.

**It is subtracted at both ends, and the first cut only did one.** Taking the
slack off the gap *below* while leaving the padding above alone means a heading
with a verb still **starts** 12dp lower than one without — so on `0.31`, whose
headings all carry verbs, every section sat 12dp further from the section above
it than the same heading does on a page of plain ones. Half a fix reads exactly
like the bug it was meant to remove, one end up. Reported as "the inter-section
margin is not being respected" and measured at 49dp against a plain heading's
37 before it was corrected. It is measured from the text
box, not the ink, so the gap cannot depend on whether a heading happens to end
in a descender.

**`RadarLabelTrim` is a layout trim, never a drawing one** (2026-08-24). The
chart's box is square because the net is round, and the net's radius reserves
34% of the half-box for the label ring. Horizontally that band is spent in
full — "Green" sits at nine o'clock and needs every dp of it. Vertically it is
spent on one 9sp word, so the topmost label's ink starts ~27dp below the box's
own top edge, and the reader sees that as the heading floating above the chart.
A static call site may therefore give the box a height 2×`RadarLabelTrim`
shorter and let the chart overflow it: the chart still measures and draws at
its declared `size`, and what the card clips is white space. Nothing in
`drawRadar` changes, which is what keeps `ShareCard`'s copy of it in step.

**The brew form's chart is the one that cannot have it.** It **zooms and
carries notes** — either puts ink where the trim assumes white — so it pays the
full band and gives back only its card's 12dp of top padding.

Home's took two attempts, and the reason is worth keeping. The first try
failed: while "Average across N sessions" was pinned inside that card's
top-left corner, pulling the chart up 20dp brought "Ferment" onto the caption's
line. **The trim and a corner label want the same 20dp.** The caption moved to
the heading's own `caption` slot — which is what `SectionHeader` documents that
slot for, and where `screenshots.py` had been drawing it all along, so the app
was the half that had wandered — and only then was the band actually free.

**`SectionCardPadding` is why a card under a heading has no top padding.** The
heading has already spent `SectionHeaderGap` reaching the card's top edge; a
further 16 inside makes 32, and because `CardColor` and `background` are both
plain white (§4.1's one accepted deviation) there is no card edge in between for
the reader to attribute the second 16 to. So it does not read as the card's
padding at all — it reads as the heading floating, which is the same complaint
that moved `ContributionCalendar`'s `GridTop`, `SessionCardHeight` and the radar
card's vertical padding. On `0.31` it measured 40dp from "Brew details" to
"Brewed" against the images strip's 16. A card that is *not* under a heading
keeps a symmetric 16: nothing above it has already paid.

**`SectionSpacing` is the other half of a section's rhythm** (2026-08-24,
direct product report: on `+1.1` "the margin between section is not being
respected"). It was five numbers — Home 24, Privacy / How-we-use-AI / the brew
form 20, Profile 28, the bean panel 24, and **`+1.1` 4**, which is why "The
visit" sat almost on the address row while every other page gave its headings
room. Twenty now, everywhere. Unlike `SectionHeaderGap` it stays on the
callers rather than folding into `SectionHeader`: a heading that *opens* a page
has nothing above it to be spaced from (`+1.1`'s "Café", `0.2`'s "Basics"), and
a composable that always paid it would indent those for nothing. What the token
buys is that one grep finds every one of them.

**`ShelfCardHeight` and `SessionCardHeight` share a rule, not a number**
(corrected 2026-08-24). Both are *their own artwork plus `ShelfCardPadV` above
and below*, which is what makes Home's bean card and a brew row the same kind
of object. The brew row used to literally *be* `ShelfCardHeight`, on the
reasoning that one constant keeps them in step — but that constant is sized for
a 104dp photo tile and a brew row's artwork is a 64dp disc, so it bought 22dp
of empty space above the disc and 22 below, on a row with no card colour to
make that read as padding. Measured on a device, it put the Sessions heading
51dp above its own list against the images strip's 16.

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
| `RadarChart` | 11-axis Canvas polygon | Fewer than three scored axes draw a **dot** (one) or a **line** (two) rather than nothing — a polygon needs three vertices, and until 2026-08-22 that was the only branch, so the first two sliders someone moved changed nothing on the chart above them. `TextMeasurer`-based label layout, not guessed offsets. Two label sets (§5.3) and two ink styles — in-app on white, and white-on-green at 4× for the Share Card, one drawing routine. Optionally **interactive** (§5.6): pinch-zoom, pan, double-tap reset, tap-an-axis, and a ring of tasting notes hung off the labels |
| `FlavorNoteSheet` | full-screen picker | Ten note bubbles for one axis, at most five chosen. See §5.6 |
| `ExtractionBar` | −1…+1 axis, three zones | under / well extracted / over, with `VizBand` + `VizBandEdge` + `VizDeviation`. **A tap on the band commits 0 while the bar is still unset** (2026-08-29, direct product request) — the middle *is* this bar's default, and until then saying so meant dragging off centre and back, because these bars refuse taps everywhere else (see `ValueBar`). Only while unset: once there is a reading, a tap on the band is again indistinguishable from the touch that stopped a fling |
| `ConcentrationBar` | −1…+1 axis, three zones | **Weak / Right / Strong** under the track (2026-08-29, direct product request; they were "Too weak / Just right / Too strong" from 2026-08-22). `concentrationVerdict` keeps the long words for TalkBack, exactly as extraction draws "Under" and announces "Under-extracted" — shortening the labels is what created the gap the long form fills, since a screen-reader user has no track to give the short word its scale. The **same private `DeviationBar`** `ExtractionBar` wraps — only the three zone words differ, because strength is the same *kind* of judgement as extraction: the middle is the target and both ends are a miss. Deliberately not a `ValueBar` from light to strong, which would make the right-hand end the good end |
| `ValueBar` | slide bar | Score and all eleven flavour axes. Draggable — a 2026-08-17 change: dragging directly on what had been a read-only meter proved the better control, and the palette was copied across so a slider stops looking like an unrelated second widget. **Drag only, never tap**: the gesture waits for horizontal touch slop, so a touch that starts on one of eleven bars stacked down a scrolling form scrolls the page instead of rewriting a score (2026-08-17 report). `DeviationBar`'s middle-tap is the one opt-in exception, and these bars do not take it — their default is the empty *left* end, so a middle tap here would be plain tap-to-set under another name |
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
| `AxisFootFade` | the fade at the foot of an axis page, so the floating capsule emerges from the page instead of sitting on it. `+2 read` and `00 Home` |
| `FloatingHeroButton` | back / share / pulled-delete on a photo hero. **The axis bar's capsule at `HeroButtonSize`** — see below |
| `ZoomableImageViewer` | pinch/double-tap, `MaxScale` 4×. Its Close button is the **one** floating circle that is still a 35% black scrim — see below |
| `TopBarDivider` | the hairline rule under every app bar |
| `MonthHeading` | `+1`'s date grouping — the month in `titleSmall`, then a hairline to the page edge. Private to `JourneysScreen`; the rule is what ties a short heading to the full page width so it divides the column rather than captioning the print below it (§8.6) |

**`AxisFootFade` is one gradient for both pages that have one** (shared
2026-08-25, direct product request to put `+2 read`'s fade on Home). An axis
page's content runs *under* the bar — that is what lets the bar be a floating
capsule rather than a docked strip — but content arriving at a hard edge behind
a translucent control makes the control look dropped on rather than floating
over. The fade is **pinned to the viewport, not attached to anything in the
list**, so whatever happens to be passing under it fades: a card, the gap
between two, the end of the pile. `+2` reached that the long way — its third
sheet used to dim and drop to headline-only, which took a rank computation, a
scroll-offset fold test and an alpha animation to decide *which* sheet that was;
a positional fade does the same job in one place and cannot get the index wrong.
It is transparent at the top so where it begins is invisible and only where it
ends has weight.

**It is not `axisChromeScrimFoot`, and the difference is deliberate.** That one
stops at `AxisChromeAlpha` and exists for `+1`, whose wall of white Polaroids
has to stop competing with a *white camera FAB* sitting on it. `AxisFootFade`
goes to full `background`, because what it clears is the bar, and the bar is
itself translucent — fading to 88% would leave the page faintly readable through
two translucent layers at once. `+1` keeps its own; the two are different
problems that happen to sit at the same end of a page.

*Not modelled in the deck.* `screenshots.py` has never drawn either foot
treatment, on `+2` or on `+1`, so the simulator frames show content running to
the capsule at full strength.

**`FloatingHeroButton` is the axis bar, smaller** (2026-08-25, direct product
request: same outside shape as the nav bar — colour, alpha, corner — at a
reduced size). Every value is the bar's own, read from where `Axis.kt` reads
them: `CircleShape`, `background` at `AxisChromeAlpha`, `axisChromeSheen()` over
it, and `AxisBarShadow`. Copying the *tokens* rather than the numbers is the
point — the buttons and the bar are one object appearing twice, so a theme
change moves both, and `AxisBarShadow` became a constant precisely so the depth
could not drift between them.

**`HeroButtonSize` is 30dp, down from the 48 that was actually on screen**, with
a 16dp glyph inside it (`Icon`'s 24dp default left a ring two dp thick). The
number it replaces read **40 in the source and 48 in the render**, and that gap
is worth recording because it defeated two attempts at this: `IconButton`
appends `minimumInteractiveComponentSize()` *after* the caller's modifier, which
expands the node to 48dp, and `Modifier.background` paints at whatever size the
node is finally placed at — so a `.size(...)` in the modifier passed **to**
`IconButton` constrains only the icon and has no effect at all on a disc drawn
behind it. The painted disc is therefore a `Box` **inside** the button's content
slot, where nothing downstream can inflate it. `HeroButtonTouch` (48dp) names
the target separately; the two are independent on purpose, because chrome over
someone's photograph should be small and a tap target should not be.
`HeroButtonMargin` came down 12 → 4 to compensate: the disc is centred in a 48dp
target and so already sits 9dp inside it, and leaving the margin alone would
have made the buttons shrink and drift inward at once.

It replaced a 35% black scrim disc with a white glyph. That disc's argument was
that these sit on an arbitrary user photograph, so neither a light nor a dark
tint alone can be relied on for contrast — **true of a translucent disc, and not
of this one**: at 88% the frost is very nearly opaque, so the glyph reads
against a known near-white rather than against the photo, and the shadow does
the separating. The glyph therefore flips to `onBackground`, and delete's from a
hand-picked light red (#FF6B5C) to `colorScheme.error` — that token is tuned for
a light surface, which is what this now is, and it was only ever overridden
because the old disc was black.

**Every other back arrow in the app stays a plain `TopAppBar` icon.** `0.1`,
`0.3`, `+1.1`, `+1.3`, `+2.2a`, `+2.2b` and the bean picker all have a real bar
to hold one; a floating disc is what a page with *no* bar needs, which is `0.2`
and `0.31` (and so vibe brewing and `+1.2`, which are that same screen). The
one remaining exception is `ZoomableImageViewer`'s Close: it floats over a
full-screen black scrim rather than over the page, so the frosted treatment
would be a bright blob on black rather than chrome on a photograph.

`HeroButtonClearance` — the margin, the *target* and 8dp — is what `0.2` and
`0.31`'s pinned title bars inset by at each end so the label never lands on the
buttons. It is derived rather than typed: both screens carried `72.dp` by hand
until the buttons got smaller and neither noticed.

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
- **The images strip** (`ImagesStrip`, shared by `0.1`, `0.2` and the brew/cup
  form) sizes its tiles to **three to a line** (`ImagesPerLine`, 2026-08-24,
  direct product request). The tile is not a constant: `BoxWithConstraints`
  divides the width the strip was given by three, less the two `ImageGap`s, so
  the third photograph ends flush with the gutter on any handset rather than
  landing wherever an 88dp tile happened to fall. `ImageTile` survives as the
  **floor** for a container too narrow for that. The drag's step pitch follows
  the measured tile, or a reorder would displace at the wrong distance on every
  screen but the one it was tuned on. It carries **two gestures on one long
  press** (2026-08-23, direct product request). Long-press *and move* drags a photo to reorder the strip; long-press
  *and release* opens a menu with **Delete photo**. Both come from one
  `detectDragGesturesAfterLongPress` — it fires `onDragStart` the moment the
  press lands, and the release decides which act it was — because a separate
  `combinedClickable(onLongClick = …)` would contest the same gesture and
  neither would win reliably. A plain tap still opens the viewer. Order matters
  beyond taste: position 0 is the photo `PhotoHeroPage` and the share card use,
  so "which picture represents this bean" was a decision the user could not
  previously make. The order is held locally during the drag and written once on
  release (`reorderImages`), because committing per frame would round-trip Room
  mid-gesture; `deleteBeanImage` renumbers the survivors, since `addImage` takes
  the *count* as the next position and a gap would let two rows claim one slot.
  The drag arithmetic is a pure function (`List.moving`) covered by
  `ImageReorderTest`, and the gesture itself by `ImagesStripDragTest` — the
  module's only instrumented UI test, and the only harness in the project that
  can drive a press-hold-then-move.

  **It shipped broken once, which is why that test exists.** The first cut keyed
  `Modifier.pointerInput` on the strip's own order, so the first reorder step
  cancelled the very gesture coroutine performing it and the photo snapped back.
  Nothing could have caught it: Paparazzi renders one static frame, `adb input
  motionevent` is a separate process per event so the moves never join the
  gesture, and `sendevent` needs root. Key a gesture's `pointerInput` on
  identity, never on state the gesture itself writes.

- **Dripper glyphs** — one per entry in `Choices.DRIPPERS` (15: Hario V60,
  Chemex, Kalita Wave, Melitta, Clever, Bee House, Origami, Fellow Stagg, Orea,
  April, Cafec Flower, Timemore Crystal Eye, Hario Switch, Kono Meimon, OXO
  Brew), on a `SessionGlyph` 64dp disc in every session card.

  **Each is drawn from its product's real dimensions** (redrawn 2026-08-22,
  direct product report: "Origami in reality is wider than V60, but in your
  design they seem almost the same"). The first set drew six of the cones with
  one identical call and separated them only by the ribs on the front, which at
  26–41dp are three grey pixels. `plan/dripper_icons/generate.py` now converts
  each brewer's real top diameter and height through one `SCALE`, so what you
  see is the proportion the product has: Origami is 11.8 × 7.2 cm against V60's
  11.6 × 8.2, Orea is the shallowest on the widest flat base, Kono the deepest
  cone, Clever the only one taller than it is wide, and Timemore the only
  faceted rim. The identifying detail sits on top of the right silhouette
  instead of doing the whole job alone.

  **The pipeline is two scripts and both are in the repo now.**
  `generate.py` writes the SVGs; `convert_drippers.py` flattens them into
  `res/drawable/ic_dripper_*.xml` (and `--check` fails if any XML is stale).
  The converter was referenced by `Illustrations.kt` from the day the vectors
  landed but had never been kept, so the fifteen XMLs were hand-flattened once
  and could not be regenerated. Do not hand-edit the XML.

---

## 7. Navigation model

### 7.1 A swipe axis **and** a bar that drives it

The deck defines the whole app as one horizontal axis centred on Home, which is
why every page is numbered rather than named:

```
   -1            00            +1             +2
  News    ←→   HOME    ←→  Can travel  ←→   I can
```

**`+2` is called "I can"** (2026-08-24, direct product request; it was
"Profile"). Untranslated in all three locales, like `Can travel` and `read`
before it — the name is a pun on the mascot and a translation of it is just a
different word. `profile_title` and `nav_profile` both carry it; the route
constant, the `AxisPage` entry and §8.9's number are unchanged, since renaming
a page is not moving it.

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

**Four glyphs, no words** (2026-08-24, direct product request). The tabs lost
their labels, and three of the four Material icons went with them:

| tab | glyph | replaced |
| --- | --- | --- |
| `-1` read | `ic_nav_news` — a sheet, a masthead band, three lines | `Icons.Filled.Newspaper`, whose folded corner and unequal blocks silt up at 22dp |
| `00` Home | `ic_brand_wordmark` — the shipped mark's "Can", no disc | `Icons.Filled.Home` |
| `+1` Can travel | `ic_nav_polaroid` — a Polaroid *camera*: body, viewfinder hump, lens, flash | `Icons.Filled.Luggage`, which named the metaphor rather than the page |
| `+2` I can | `Icons.Filled.Person` | — the one place the generic glyph is right |

The travel glyph was a *print* first — a portrait frame with the caption
border at the foot — and was replaced by the camera the same day: the page's
own FAB draws a Polaroid camera, so the tab and the button now show one object
at two sizes.

Two consequences worth stating. **The four `nav_*` strings must stay**: they
moved onto each icon's `contentDescription`, so the bar is still named for a
screen reader, and deleting them as unused would leave four unlabelled
buttons. And **the wordmark is laid out large, not drawn small and scaled**:
its lettering fills 62×36 of a 128-unit box, so at a 22dp icon size it renders
6dp of ink beside 22dp glyphs. The first fix was `Modifier.scale(2.1f)` and it
came back visibly blurry — `scale` is a draw-time graphics-layer transform, so
the vector was rasterised at 22dp and *then* magnified. `AxisWordmark` (56dp)
gives the Icon a larger layout size instead, so the rasteriser works at that
size; forking the generated drawable to crop it would also work and would then
drift.

**The selected shape is one layer painted behind the row, and the four shapes
tile the capsule** (2026-08-24, direct product request). Home and Can travel —
the two tabs flanking the `+` — take a **full-height circle**, touching the
capsule's top and bottom edge. `read` and `I can` take **what is left at each
end**: the capsule's own rounded cap on the outside, and on the inside the
near half of the neighbouring circle, *concave*, so the pieces interlock with
neither seam nor gap.

**The two glyphs beside the `+` sit closer to it than a square slot allows.**
`AxisMidTab` is 48dp while their indicator circle stays `AxisBarHeight`, so
the circle overhangs its own slot by 6dp a side and laps over its neighbours.
Nothing breaks when it does: the `+` disc draws on top of it, the indicator
subtracts that disc anyway, and the end shapes take their closing arc from the
circle's *centre* rather than from any slot edge. Every centre in
`drawAxisIndicator` is computed from `AxisMidTab`, so the two cannot disagree.

**Home and Can travel also claim the space around the `+`.** Two full-height
circles in adjacent slots are tangent at one point, so the space
between them is a pair of curved slivers that no indicator could otherwise
fill — they showed as nicks bitten out of the bar beside the `+`. The selected
shape now runs as a band from its own circle's **centre** to the `+`'s, minus
whatever is standing in that slot. Starting at the centre rather than at the
slot edge is the detail that matters: claiming only the slot met the circle at
a tangent point, which has no width, and left a hole on each side of the join.

**The `+` spans the bar's full height and is the same button on every page.**
It logs a brew, everywhere. That was arrived at the long way: for two revisions
it changed on `+1` — first to a white camera glyph, then to a white disc
holding the full-colour Polaroid camera, with the action switching to "start a
journey" so the button would not show one thing and do another. Reverted to one
green `+`, which also gives back what the switch cost: while `+1` owned this
slot, logging a brew was the one action unreachable from the page you were on.
`+1` has its own camera FAB for its own action.

**Nothing in the bar ripples.** The default `indication` washed a grey circle
over a glyph on touch, which on a translucent capsule read as a smudge rather
than as feedback — and the selected shape moving under the finger already is
the feedback. `indication = null` on every tab and on the centre button;
`PolaroidCamera` gained a `ripple` parameter for its copy in the bar and keeps
the ripple everywhere else, where it is a FAB on a page. `Role.Tab` and the
selected state are still reported, so nothing is lost to TalkBack.

The whole construction rests on one coincidence: the capsule's cap radius and
a full-height circle's radius are both `h / 2`, so every edge in the indicator
is an arc of the same radius and an end piece's closing arc is literally the
same arc as its neighbour's outer edge. It is drawn in `drawAxisIndicator`
rather than as a per-tab `Modifier.background(shape)` because that closing arc
is centred on a point inside the *next* tab, which a tab-local shape cannot
reach. The row consequently carries **no padding of its own** — the capsule's
bounds and the row's bounds are the same rectangle, which is what lets an
indicator reach the top and bottom edges. Slots are `AxisEndTab` (54dp),
`AxisBarHeight` square, `AxisBarHeight` square (the `+`), `AxisBarHeight`
square, `AxisEndTab`.

This supersedes `README.md` resolution #19, which declined bottom navigation.

### 7.1a The same capsule on a detail page — `DetailActionBar`

A saved record's page carries the **same capsule with actions in the slots**
(2026-08-25, direct product request: "use the same nav bar assembly in the
homepage on the bean profile page and journey cup page"). `ui/DetailActionBar.kt`
reads every value from the axis bar's own tokens — `AxisBarHeight`,
`AxisBarMargin`, `AxisChromeAlpha`, `AxisBarShadow`, `axisChromeSheen`,
`AxisEndTab`, `CircleShape` — rather than copying numbers, so a theme change
moves both and the two cannot drift into being *nearly* the same capsule. Its
caller pairs it with `AxisFootFade` and pays `AxisBarClearance` inside the
scroll, exactly as an axis page does.

**It appears only on a record that exists.** A blank form has nothing to share
and nothing to delete; its one act is Save, which the foot of the form still
carries. So `0.1`, a new brew and a new café show the button and no capsule.

**One arrangement, on all three pages** (2026-08-30, direct product request,
first for a café and a cup, then "put the same nav bar in the bean profile
page"):

| Slot | | |
| --- | --- | --- |
| share | flat, left | `IosShare`, `onBackground` |
| **add** | **the disc** | `+`, `primary`, full height |
| modify | flat | the pencil, then the tick |
| delete | flat, right | `error` — **only while modifying** |

The disc is the bar's one filled, full-height, brand-coloured slot, and it
carries the act the page is *for* — on Home, logging a brew. Every page that
has this bar is a page about a list, so the disc adds to it: a **brew** on
`0.2` (the same call as the Sessions heading's `+`), a **cup** on `+1.1` (the
Cups heading's "Add a cup") and a **pour stage** on `0.31`/`+1.2` (the Pour
stages heading's `StageEdit.new`). Share, which was the disc until that
request, steps down into the flat slot to its left — the arrangement Home
already teaches, a green `+` between quieter things. There is no second
arrangement: the leaf variant this bar had for five days is gone, because the
last page that was a leaf turned out not to be one, and a branch no caller
takes is a branch that drifts.

**Delete is red, never the disc, and in the `add` arrangement it is not drawn
until Modify has been pressed.** A full-height disc under the thumb is exactly
where an accidental press lands, so delete stays a flat slot tinted
`colorScheme.error` — the same treatment `RemoveButton` gives it at the foot of
a form. Where the bar's centre is a `+`, a permanent delete one slot from it is
a mis-tap that destroys a visit; Modify is already the page's "I am here to
change this" gesture, so it is the gate, and the slot arrives with an
`expandHorizontally` so the capsule is seen to grow it. The bean bar keeps
delete always visible: it has no `+` for it to be confused with.

**Modify is a mode, so its slot has two states** — the pencil of
`ic_action_modify`, then `Icons.Filled.Check` once pressed, greyed until
something differs (`modifyEnabled`). Drawn greyed rather than removed, for the
reason §8.8 gives at length: an empty slot reads as "pressing Modify did
nothing".

**Back leaves the mode before it leaves the page** (2026-08-30, direct product
request). On a saved record — all three pages — the back control, the system
gesture and `+1.1`'s right-swipe all drop modify mode and stay put; a second
back leaves. A record being *created* is editing from its first frame and has
no view mode to fall back to, so back there means what it always did. What
happens to a pending edit is each page's existing policy, unchanged: `0.31` and
`+1.1` ask (`Discard changes?`) and then revert to what was loaded, while `0.2`
flushes it, because a bean's edit is never lost by leaving (§8.4) and a mode
that dropped it would leave the header showing values the database does not
have.

`DetailActionBarScreenshotTest` is the golden for the four states, because each
screen golden covers only whichever one its page opens in.

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
| `Cup` | `+1.2_cup/{journeyId}/{sessionId}/{beanId}` — resolves to `BrewSessionScreen` (§8.6c) |
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

**The sheets sit in `NewsGutter`, now `Gutter / 2` — 8dp.** Three values in
one afternoon (2026-08-24), each a direct request to go narrower: 150% of
`Gutter`, then `Gutter`, then half of it. 24dp took enough width out of a
column of newsprint that headlines wrapped a word early; 8dp is the floor,
since below it the sheet's edge and the screen's edge stop reading as two
different things. It stays its own token: this margin has now been tuned
alone three times while every other screen kept `Gutter`, and folding it back
would silently widen the next edit to the whole app.

**The reading mascot is 160dp**, like every other page mascot since
2026-08-24; it was 108.

**And can-boy turns the page with his hand** (2026-08-29, direct product
request: "the page is turned without canboy's touching the page"). The leaf
already foreshortened about the fold rather than flapping out of plane
(2026-08-28); what it did not have was a cause. The right hand now leaves the
reading pose, closes on the leaf's outer top corner, pulls it in, and lets go
— the arm and the leaf read the same corner out of `CanBoyNews`'s
`newsCorner`, so they cannot drift apart.

**It lets go a quarter of the way over, and the wordmark is the reason.** The
hand never travels further left than the reading pose it starts from, because
that pose is already the closest the deck ever put a limb to the name — 1.66
units, with a white 4.2 stroke beside white lettering, where merging into one
shape and crossing look the same. The fold could physically be touched (25.5
units from the shoulder against an arm of about 25) and reaching it would lay
the forearm over the belly. So the gesture is a flick, which is what a hand
does to a newspaper anyway: take the corner, lift it off the spread, let the
page fall. `page` became the whole gesture's clock in the same edit and
**must now be fed linearly** — `NewsScreen` sweeps it over 1.8s of the 4.4s
cycle and eases nothing, since the leaf's width is a cosine of it and the
reach and return are eased in the figure.

#### 8.2a The sheets are frosted glass

2026-09-17, direct product request: "apply this effect on the newspapers in can
read page". The same material as Home's panes (§8.3a), on an object that is not
a pane.

**The page is the light thing and the glass is the grey one.** That relationship
is the whole effect and the first pass had it backwards: panes *lighter* than
the page, keeping dark ink — which on a white page is a translucent white card,
i.e. nothing. Reported as "the newspaper should be more grey and blur, just as
the sample … The text be white". The mock's panes are darker than what they lie
on and carry near-white text.

So the sheet fills from `inverseSurface` at `NewsprintGlassAlpha` 0.74 and inks
from `inverseOnSurface` — the pair scheme E already defines for exactly this
inversion, so no colour is introduced and `check_design.py` has the same token
table to diff. Three things followed, and each was a colour that had been chosen
to work on white stock and was invisible on dark glass: the graded rules became
the ink held back (`ink.copy(alpha = 0.38f)`) instead of `outlineVariant`, the
folio date became `ink` at 0.72 instead of `onSurfaceVariant`, and `OpenMark`'s
tint became a parameter instead of `primary` #196D2E — the one affordance on the
card had become the one thing on it nobody could see.

**0.74 is a legibility floor, not a taste setting.** The standfirst is
`inverseOnSurface` over whatever the fill mixes to against the page's bloom;
below about 0.7 that drops under 4.5:1 and stops meeting AA. That leaves only a
quarter of the backdrop coming through, which is why `FrostRadiusPx` went 72 →
110 in the same change: a quarter of a *heavily* diffused field reads as
frosting where a quarter of a lightly blurred one reads as dirt. And
`BackdropVeil` went 0.45 → 0.62 ("the background is too grey, reduce the grey")
— the bloom had been carrying the separation between page and surface, which is
the wrong way round; the glass carries it now.

**What did not change is the sheet.** The torn `PaperSheet` outline, the
nameplate, the graded double rule, the fold and the headline's per-call-site
size override are untouched — none of them depended on the stock being opaque or
pale. `NewspaperCard` is a `Box` wearing `Modifier.glassSurface` instead of a
`Card`: a Card would paint its container colour over the glass, and the three
things it was providing (shape, click, border) are all still there.

**`Modifier.glassSurface` exists because of this screen.** Home's sections are
rectangles and could be a `GlassPanel`; a sheet of newsprint has its own
outline, its own click and its own edge colour. Handing the material out as a
modifier is what lets the two share every ingredient — clip, backdrop blur,
fill, sheen, lit edge — without the sheet having to pretend to be a pane. The
shape it is given is used for the clip **and** the border, so those cannot
disagree.

**The edge is lit at the top and printed at the foot.** The default glass edge
falls from white 0.60 to white 0.10, which leaves the bottom of a sheet
undefined; the sheets pass a gradient ending at their own hairline instead, so
the pile does not dissolve into itself.

**Home's panes are still light glass**, and after this change the two pages no
longer wear the same face — `00` has near-white panes with dark ink, `-1` has
grey ones with white. They still share the material, the backdrop and every
constant but the fill and the ink, so matching Home to the mock is a two-argument
change at its `GlassPanel` call sites if that is wanted.

**`paperTone()` and `NewsprintStock` are gone.** Both existed to answer "how far
from white must a white sheet be to read as paper on a white page", and the
answer had been round three times — a warm grey, then a third of the way to
`surfaceContainerLow`, then flat #FFFFFF, i.e. white paper on a white page held
apart by a hairline alone. The sheet no longer answers it with a *tone*: it
separates by **material**, which is the one axis this screen had not used. The
file keeps a comment naming them, because the question was real and someone will
be tempted to reintroduce it.

**The feed has no photographs of its own** — a news item carries five text
fields and no image (`legal-accounts.md` rule 74) — so this page borrows the
shelf's through `beanBackdropPhotos`, reading `observeBeans()` for the backdrop
and nothing else. That is also what keeps the two pager pages on one backdrop.

### 8.3 `00` Home

Bean shelf, **Brewing activity** contribution calendar, and **My flavor** — an
eleven-axis radar averaged across every session, labelled with the session
count.

**A rule between the sections, and none between the bags** (2026-08-30, direct
product request, both halves of it). Home draws `SectionRule` (§4.2) between
the shelf and **Brewing activity**, and again between the calendar and **My
flavor** — and the inset hairline that used to separate one bean card from the
next is gone. It is one decision: a horizontal line now means *a new section
starts here*, so spending the same mark between two bags of coffee made the
shelf read as three things rather than as the one block its heading counts.
Bean cards are flush, and since `CardColor` and `background` are the same white
(§4.1), what separates them is the air around each one's artwork.

**The shelf heading counts the shelf and is the door to it** (2026-08-29,
direct product request). It reads `My beans (4)` — the name at
`SectionHeadingSize`, the count beside it in the same size at `Normal` weight
and `onSurfaceVariant`, so it is an aside to the name and never a second
heading. To its right, a `…` (`ic_action_more`) where the magnifying glass had
been since 2026-08-25. **Both the glyph and the words open `0.31a`**, which is
deliberate: the words are the discoverable target and the glyph is the one that
looks pressable, and a heading whose label and whose button went to two
different places is exactly what this app's one-icon rule exists to prevent.

**Three things left Home in that one edit**, and they were one decision:
the "See all N beans" / "Show fewer" row under the cards, the inline search
field, and the magnifying glass that was the only door to it. The shelf is now
*always* its first three bags, and everything about the rest of them — seeing
them, searching them — is `0.31a`, which already had its own search over the
same list. The `showAll` fold state and `HomeScreen`'s `initialQuery` test hook
went with them, as did `HomeSearchScreenshotTest`. `home_search_open`,
`home_search_label` and `home_search_placeholder` survive because Pick Bean
still uses all three; `home_search_close`, `home_no_matches`, `home_show_fewer`
and `home_see_all` were deleted from all three locales.

**`…` is drawn, not `Icons.Filled.MoreHoriz`.** `material-icons-core` ships
`MoreVert` (⋮) and not the horizontal ellipsis, and the two do not mean the
same thing: ⋮ reads as "more actions on this row", … as "there is more of
this", which is what this control says about the shelf above it. Pulling in
`material-icons-extended` for one glyph would land a few thousand vectors in
the APK, so `ic_action_more.xml` draws three r=2 dots — the same
filled-single-path register as `ic_action_modify` and both nav glyphs.

**The shelf card has four layers** (2026-08-26, direct product request), left
to right `BeanIcon`, the text column, chevron:

1. the **name**, bold, 14sp — with the **roast date** beside it, bare ("28
   Jul") and spoken in full. It is the one fact on the card that goes stale, so
   it rides with the name rather than with the roaster below;
2. the **lot** — variety · process · farm, 11sp. Origin is deliberately absent:
   it is nearly always in the bean's own name a line above, and a card that
   prints Ethiopia twice has spent its narrowest line saying nothing new;
3. the **roast** — roaster · roast level, 11sp. The roaster came back onto the
   card here, having been left off on the deck's reasoning that it "is usually
   in the bean's own name" — true of some bags, never true of the level, which
   nothing on this screen used to show;
4. the **brew-count pill**.

A bean with neither line to draw says "No details yet" once rather than holding
two blank rows open — the vibe-brewing row is exactly such a bean.

**Bottom-right corner: the freezer badge** — a snowflake and the number of days
since `beans.frozenDate`, when there is one (§9). The number alone, with the
snowflake carrying the unit and the plural spoken through `contentDescription`.
It replaced the café label that used to sit there, and for the opposite reason:
that one drew a fact the shelf's own filter had made unreachable (below), while
this draws a fact only the shelf can show, since a bag in the freezer is
precisely a bag you are not looking at. It is also the only number on this
screen that changes without anybody touching the app, which is why it is drawn
as a count and not as the date it is stored as.

**"Average across N sessions" is the heading's caption, not a corner label**
(2026-08-24). It spent a week pinned inside the radar card's top-left, so that
it read as the chart's own caption rather than a page-level line; that corner is
also the only place `RadarLabelTrim` (§4.2) can give back, and while the caption
held it this heading sat 41dp above its chart. `SectionHeader`'s `caption` slot
is where the composable documents it belonging and where the deck had been
drawing it, so the move put the two back in step and let the chart come up.
Absent, not blank, when nobody has scored anything.

**The calendar's card is `ContributionCalendarHeight`, and that is derived**
(§4.2). The component draws in the card's own coordinates and takes no padding
modifier, so the card has to track its geometry exactly rather than be a guess.
Its `GridTop` came down from 32 to 20 on 2026-08-24 and the card from 184 to
169 with it: at 32 × `Enlarge` the band above the month row was 41.6dp of card
for one 11sp line, and against a white page with no card edge to say otherwise
the reader saw it as the Brewing-activity heading floating rather than as the
calendar's padding.

**A bean that came from a café is not on this shelf** (2026-08-22, direct
product request). `+1.2` writes a real `BeanEntity` so a cup has something to
belong to (§8.6c), but that row records *what you drank out*, not a bag you
own, and listing it under "My beans" claims you have it. Home filters it out.
Nothing is lost: `0.3` History lists every session, so the cup is there with
its café beside it, and `+1.1`'s own Cups block lists it under the café it was
drunk at. `+1.1a`'s picker is **not** filtered — you can log a home brew of a
coffee you first met at a café, if you went and bought the bag.

**The filter's field is `cafeName`, which is derived and never stored.**
`BeanWithDetails.cafeName` is a correlated subquery for the earliest cup of
that bean whose journey still exists — earliest because the question is where
the bag came *from*, not where it was last drunk. `beans` gains no column:
the edge already exists on `sessions.journeyId` (§9), and a copy on the bean
would be both a cached derivation (`coupling-spec.md` §4.2) and a new column
on a table the sync bundle carries. It carries the orphan rule for free —
deleting a journey nulls it, and deleting a journey is already defined as
orphaning its cups back into ordinary brews, so the bean reappearing on the
shelf is that same rule rather than an exception to it.

**The label this field used to draw on a Home card is gone** (it was added
2026-08-21 and made unreachable by the filter a day later: a card that could
draw a café name is a card that is no longer on this screen). `0.3`'s row keeps
its own corner, from `SessionWithBeanName.cafeName`. Pinned by
`HomeScreenScreenshotTest.homeHidesBeansFromAJourney`, whose fixture is the
`home()` shelf plus one café bean and must render the same four cards and the
same "See all 4 beans".

Empty state: the **pour-over mascot** at 160dp — the same figure `0.3`'s empty
state uses, replacing the brand lockup on 2026-08-19 (the lockup opens the
splash and the sign-in page, so a third appearance here made the first screen
after the splash look like the splash again) — over the headline, one
sentence and a CTA carrying the deck's idle wiggle (1000ms shake, 4000ms rest).
Search is the shelf heading's action.

**The empty state is anchored from the top, not centred, and it shares that
anchor with `+1_can_travel_empty`** (2026-08-24, direct product request: "too
low, make it upper and align their position"). Two rules, both stated on
`ui/Axis.kt`'s `AxisEmptyTopFraction`. First, the column is padded clear of the
floating bar by `AxisBarClearance` — an axis page's content area deliberately
runs *under* that bar, so a column filling it measures against a bottom edge
nobody can see and lands about half the bar's height low. Second, the mascot
centres inside a fixed `AxisEmptyMascotSlot` whose top sits at
`AxisEmptyTopFraction` of the content height, so the two poses land on one
centreline and both headlines on one baseline. The slot was 184dp while the
two poses were 160 and 184; since 2026-08-24 **every page mascot is 160dp**
(direct product request: one size, Home's) and the slot is 160 with them. It
is kept even though both poses now fill it exactly — it is what made them
agree when they differed, and what will keep them agreeing if one is resized
alone. The one figure that is *not* 160 is `0.1`'s scan-card camera pose, at
108dp: it sits inside a card above a title, body, button and hint rather than
being the page, and growing it pushes a form apart.
Centring cannot do that: the two blocks are unequal — this one carries a CTA
button — so centring landed the discs **36dp apart** (measured off the
`homeEmpty` / `journeysEmpty` goldens, which render in dp) and the mascot
hopped on the swipe between them. Anchored, both centre at 299.5dp; the fix
also raised Home's disc by 47dp and Can travel's by 83dp.

**The top bar carries one worded action, "History"**, and it **pushes** `0.3`
Sessions (2026-08-19, direct product request). It was a pager move for as long
as Sessions was `+1`; when Can travel took that slot the action stayed and its
mechanism changed, which is the same fact the renumbering in §7.1 records.

**The FAB logs a brew** — it raises the same hoisted "which bean?" sheet
`0.3` Sessions' FAB does, so a "+" means one thing wherever it appears. It has
been both things twice; the current call is 2026-08-19. Adding a bean did not
lose its door: that sheet offers "Add a new bean", and an empty shelf shows its
own CTA.

#### 8.3a Each section is a pane of frosted glass

2026-09-17, direct product request against an Apple "Liquid Glass" mock: on Home
"each section is shown into a frosted glass". `ui/components/GlassPanel.kt`.

**Four ingredients, and the first one is not on the panel.** A translucent pane
over `background` is a white rectangle on a white page — `background` *is*
`Surface`, #FFFFFF — and a *blurred* white rectangle is the same white
rectangle. The mock gets its glass for free from a photograph behind it. This
was got wrong twice before it was got right: first a pane on the bare white page
(nothing to see), then a green wash behind it — reported as "the glass is not
blur … make the background white".

**The backdrop is the user's own bags.** `GlassBackdropHost` draws up to
`BackdropPhotos` = 3 of the shelf's photographs full-bleed behind everything,
blurred past recognition (`BackdropSoftness` 56dp), held at `BackdropAlpha` 0.70,
under a veil of `background` at `BackdropVeil` 0.45. What survives is a soft
field of colour with no edges in it — white paper with a bloom on it. They are
already on this screen, one per card, so the page is tinted by the coffee the
user actually owns and changes when the shelf does; a texture would be
decoration, this is the same content at a different distance.

**And the pane's blur is real.** Compose has no backdrop filter —
`Modifier.blur` blurs the node it is on, never what is behind it, which is why
§8.8a's `CardOverlay` blurs the *page*. What Compose 1.7 does have is
`GraphicsLayer`, and that is the mechanism:

| Layer | Holds | Drawn |
| --- | --- | --- |
| `backdrop` | `HomeBackdrop`, recorded | once, sharp, as the page |
| `frosted` | `drawLayer(backdrop)` under a `BlurEffect(FrostRadiusPx)` | by **each pane**, behind itself, translated by its own position |

`GlassBackdrop` (layer + origin) travels down on `LocalGlassBackdrop`; a surface
with none just draws its fill. Since 2026-09-17 the host is **shared with `-1`**
(§8.2a) — Home and Can read are two pages of one `HorizontalPager`, and a
backdrop that changed between them would be a material change you watch happen
mid-swipe. Both positions are *measured* — the backdrop node
is inside a `Scaffold` and the pane is inside a scrolling column, and only one of
those is stable. `clip` comes before `drawBehind` in the pane's modifier chain,
so the blurred copy stops at the pane's rounded edge instead of painting a
full-screen rectangle out from its corner.

Two layers and not one, because one cannot be both: the backdrop has to be sharp
outside a pane and diffuse inside it, and that difference **is** the glass. It is
the one signature no amount of translucency imitates.

**Below API 31 the page is plain white and the panes are fill alone.**
`RenderEffect` is 31+, and `Modifier.blur` is a no-op there — so the backdrop
photographs would arrive *sharp* at 70% under the body copy, which is worse than
having no backdrop at all. Both floors are the same floor, and it is the one
`AxisChromeAlpha` documents.

The pane itself is a fill at `GlassFillAlpha` 0.70, `axisChromeSheen()` over it,
and a 1dp **gradient** border, white 0.60 at the top falling to 0.10. The lit top
edge is what separates "frosted glass" from "a translucent rectangle".


**The sheen is the bars' own.** `axisChromeSheen` already frosts the top bars and
the floating capsule, and its own note states this panel's argument — "real glass
catches more light where it meets an edge". A pane with a private gradient would
be a second frosted material in an app that has one. What the pane does **not**
borrow is `AxisChromeAlpha` (0.88): that is tuned for chrome over scrolling
content, and at 0.88 over a wash a pane is opaque.

**No backdrop blur, and none is needed.** Compose has no backdrop filter —
`Modifier.blur` blurs the node it is on, not what is behind it (§8.8a's
`CardOverlay` blurs the *page* for that reason). Frosting would mean blurring a
copy of the wash behind each pane, and the wash has no detail in it, so the blur
is indistinguishable from it. The effect renders identically on every API level
the app ships to, which is the bar `AxisChromeAlpha` sets for an always-visible
surface.

**No golden can show any of this.** `TestFakes` beans carry no image files, so
every Home golden records the backdrop as plain white and the panes as very
nearly invisible. That is correct, and it is the limit: the frames verify the
*layout* of the panes and nothing about the material. The effect needs eyes on a
device with real photographs on the shelf, running 12 or newer.

**Three things went out with the panes, as one decision:**

| Removed | Why |
| --- | --- |
| The two `SectionRule()`s | A hairline *and* a glass edge are two marks for one boundary. Separation is now the wash showing through a `GlassPanelGap` |
| The white `Card` round the calendar and the radar | `CardColor` is #FFFFFF; a card inside a pane is an opaque rectangle covering the material it stands on. The pane **is** the card |
| `BeanCard`'s `CardColor` container → `Color.Transparent` | Same reason, three times over. It never read as a surface anyway — it was white on white, and the rule between bags went on 2026-08-30 |

**`GlassPanel`'s `contentPadding` defaults to vertical only, and that is
load-bearing.** Two of the three panes hold something that must keep its current
width. The shelf's cards were widened out of the page gutter to `ShelfGutter`
(0dp) by direct request on 2026-08-24/25; and `ContributionCalendar` clamps its
column count to `(width − inset) / pitch` with a **fixed** cell size, so 16dp of
pane padding per side silently costs it two weeks of history rather than drawing
the same grid smaller. So the panes bleed and each heading pays `GlassPadH` by
hand — which is also what the mock does, its rows running to the pane edge under
an inset label.

That does move the shelf's breakout one level down: the cards now run to the
**pane's** edges rather than the screen's, so they sit at the page `Gutter`
where they used to sit at 0. The margin the 2026-08-24 request was about is now
carried by the pane, which is the object that has one.

### 8.4 `0.1` / `0.2` / `0.2b` Bean Detail

The largest screen in the app (1400 lines). One bean, created or edited.

- **Photo hero** (`PhotoHeroPage`) — the bag photo, draggable panel, Images
  strip, zoomable viewer.
- **Header** — the bean's name at 26sp, then `BeanHeaderSummary` (§8.8), and
  **no rule under it** (2026-08-24, direct product report: "the header lower
  boundary line is not removed"). The hairline there was left over from when
  this page had a real app bar and had stopped meaning anything: the panel is
  pulled up over a photograph with its own drag handle and rounded corners, so
  the header is already bounded by the shape it sits in, and a line under it
  read as chrome divided from content on a page that has no chrome there — the
  same argument that took `TopBarDivider` off `+1.1` the same day. What
  separates the header from the first section is `SectionSpacing` (§4.2).
- **Images** (`ImagesStrip`, §5.1) — **first in the block Modify unlocks**
  (2026-08-29, direct product request: "in the modification mode of bean
  profile, the image section should be before Basic information"). Same
  argument as Images-before-Radar on `0.1`, one section further up: the bag is
  in the user's hand while they are editing, and this is the one section that
  waits on neither a scan nor a brew. **View mode is unchanged** — the basics
  are not drawn there at all, so the strip already opens the page's content,
  and every gap either way is the one it was.
  **The "Add img" tile shows in modify mode, or on a bean with no photographs
  at all** (same request). An empty strip's tile is the section's whole
  content, so gating that one on a mode leaves a heading over an empty row and
  puts "photograph this bag" behind Modify — on the page whose subject is the
  bag. `ImagesStrip` takes this as `canAdd`, defaulting to `enabled`, kept
  separate from it so reorder, the long-press delete and the reorder hint stay
  exactly as they were in view mode.
- **Process, Origin and Variety open a picker dialog** (`0.2f`,
  `CapsuleChoicePicker`, 2026-08-29, direct product request) rather than
  filtering under the capsule the way the brew form's `Choices`-backed fields
  do. These three are the fields that are *browsed*, not half-remembered:
  `PROCESSES` is 45 named methods most of them variations on four words,
  `VARIETIES` is ~100 cultivars, `ORIGINS` is every country — and a dropdown
  showed them through a 30dp capsule with the keyboard over the bottom half of
  the screen. Origin and Variety were free text until then, which is what let
  one bag say "Ethiopia" and the next "ethiopa".
  The dialog is a search box, the list (height-capped, the current value in
  `primary` + SemiBold), and **Add new**, which takes whatever is in the search
  box — the search field is also the new-value field, and the button says so by
  carrying the typed text ("Add “Yeast Natural”"). Disabled while the box is
  empty or holds a name the list already has. The list stays **open**, which is
  what `Choices` is for (§9): a closed picker would reject real bags. The
  addition lands on the bean and not in `Choices` — the desktop keeps per-user
  additions in its own config, and there is no store for them on this side.
- **The three lists.** `VARIETIES` runs **by family, not alphabetically** — the
  Geshas, the Ethiopian landraces and JARC selections, the Bourbons, the
  Typicas, their crosses, the SL and Indian selections, the Timor hybrids and
  their descendants, the F1s, and the recent Colombian and Ecuadorian finds —
  so "Yellow Catuaí" sits beside "Red Catuaí" instead of 40 rows away; the
  search box is the other way of looking. `ORIGINS` leads with the twenty
  coffee countries in the order they were asked for (Ethiopia, Colombia,
  Kenya, Panama, Guatemala, Costa Rica, Brazil, El Salvador, Rwanda, Burundi,
  Honduras, Indonesia, Peru, Nicaragua, Mexico, China, Yemen, Tanzania,
  Ecuador, Papua New Guinea) and then every other country alphabetically.
  Those are **enumerated from `Locale.getISOCountries()`, not typed out** —
  ~250 entries is a list to maintain against a world that changes — and their
  **English** names, because the value crosses to the desktop in a sync bundle
  and a column whose contents depended on the phone's language would collate
  three ways. Each row carries its **country flag**, built from the same
  ISO alpha-2 code the name was looked up from (two regional indicator
  symbols, so no asset and no table of 250 emoji). The flag is `display`, which
  decorates the row and never the value: `beans.origin` holds "Ethiopia", and
  so do the shelf card, the share card and the bundle.
- **Scan card** — "Scan the label to update these fields", with offline and
  consent-blocked variants.
- **Fields** — name as an outlined box; then **nine** capsules two to a row:
  origin | region, variety | farm, altitude | producer, roaster | process, and
  **roast date hanging alone**; note free-text. The order is provenance
  narrowing to the bag — where it grew, what it is and who grew it, how high
  and who bought it, who roasted it and how, and when — and Producer still
  leads Roaster because the chain runs farm → producer → roaster (2026-08-26,
  direct product request). `farm` closed the hanging half-row the grid used to
  end on; **`region` reopened it on 2026-08-29**, because nine is odd and
  something has to hang. The foot is where a half-row reads as the end of a
  list rather than as a missing field.
- **Sessions list** (`0.2`/`0.2b` only — an unsaved `0.1` bean has none yet),
  delete-with-cascade confirm, discard-draft confirm, share disc. **With no
  brews logged the section is a block, not a figure and a sentence**
  (2026-08-29, direct product request: "make this block same style as
  non-added Pour stages block") — `StagesTimerCard`'s construction, which is
  `ScanSection`'s: a `secondaryContainer` card at `CardCorner`, 16dp padding, a
  108dp pour-over mascot over a `titleMedium` line, a centred `labelSmall` line
  and a filled **New brew** button. It was a 160dp mascot over one
  `onSurfaceVariant` line — the app's colour for information already dealt with
  — which read as a report on a page of controls. No button under the card — and the
  stages block has none either since 2026-08-30, so the two are now the same
  shape as well as the same construction. The heading's
  action is a **`+`, not the words "New brew"** (2026-08-29, direct product
  request) — `SectionHeader`'s `actionIcon`, which *renders* the action rather
  than replacing it, so the string is still what TalkBack announces and still
  what `check_design.py` diffs. It is one of two headings in the app that earn
  a glyph (Home's Search is the other), and it earns it because the app already
  spells "log a brew" as a `+` on both FABs and on the Axis bar's centre disc:
  this heading was the last place that verb was still a word.
- **Delete** (`0.2`/`0.2b` only) sits beside Save at the foot of the panel
  (`RemoveButton`), not as `PhotoHeroPage`'s pulled disc — that placement
  moved here 2026-08-20, direct product request. `DeleteBeanDialog` still
  gates the actual delete; only the reach changed. Share stays the photo's
  top-right disc. Save carries the row's weight (`Modifier.weight(1f)`) and
  Delete wraps its own icon+label — the row's primary action, not a coin
  flip between two equal buttons.
- **Roast** — a seven-stop `Slider` (light → extra dark), the stop's shade
  carried by the thumb and active track, its name spelled underneath; then
  colour value, weight loss and expansion rate behind *More details*. An unset
  bean parks the thumb on the **middle** stop and reads "Medium" while storing
  nothing, so **a tap on that middle stop selects Medium** (2026-08-29, direct
  product request). M3's `Slider` calls `onValueChange` only when the value
  actually changes, so tapping the stop already under the thumb used to write
  nothing at all and the bean saved with no roast level — the user had to drag
  off medium and back to record what the slider was already showing them.
  `onValueChangeFinished` is where that tap becomes visible.
- **Freezer** (`0.2`/`0.2b` only) — under the header summary: a snowflake, a
  checkbox and, once set, "Frozen 12 Aug 2026 · 14 days" (2026-08-26, direct
  product request). Checking the box **opens the date picker and writes
  nothing** — "frozen" with no day is not a state the column can hold (§9) —
  so cancelling leaves the bean unfrozen and the box unticks itself.
  Unchecking clears the date, the one place a date on this page can go back to
  unset. It sits with the header rather than in the fields grid because it is
  not a property of the coffee: every field in that grid describes the lot,
  this describes what the owner of this bag did with it. **The affordance is
  modify-mode only, the answer is not** — the same rule the roast slider and
  the note rows follow: in view mode a frozen bag states when and how long, and
  an unfrozen one draws nothing rather than an inert box.
- **Flavour** — radar plus a manual-override sheet. `flavorSource` is `auto`
  (averaged from this bean's sessions) or `manual`. On `0.2`/`0.2b` this sits
  below the sessions list, not above it — the radar reflects those sessions,
  so it reads as their summary rather than a caption ahead of them. **On `0.1`
  it comes after Images** (2026-08-26, direct product request: "when create a
  new bean profile, the Images section should be priori to the Radar"). The
  two had the opposite order, which put the one section a brand-new bean can
  fill in below the one it cannot: nothing has been tasted yet, so Flavor is a
  caption card explaining that there is no profile, while the bag in the user's
  hand is photographable now.

**New beans are held as in-memory draft state** (`rememberSaveable`) until the
first real edit or explicit save — `status` is `draft` until then. A screen the
OS kills mid-flow never orphans an empty row.

### 8.5 `0.11` / `0.12` / `0.13` Photo source → Scanning → Scan Review

Photo source sheet (take a photo / choose a photo), scanning state, then
**Scan Review**: the guessed fields, each editable, with "was:" hints showing
what would change, an empty-read state, and a report control.

Nothing reaches the form until the user accepts.

**Roast date is a picker here too, not a text box** (2026-09-03). It opens the
same `DatePickerDialog` the bean page's roast-date capsule opens and shares the
same three ISO helpers (`formatIsoDate`, `toEpochMillisOrNull`, `toIsoDate`, all
`internal` in `BeanDetailScreen.kt`) — a second parse would be a second answer
to what a date is. It is the field a scan gets wrong most often, because a bag
printing "07/08/26" does not say which number is the month, and correcting that
meant retyping ISO-8601 on a keyboard. A guess the picker cannot represent
("2026-07", "July 2026") is shown verbatim and applied verbatim; blanking it
would delete something the label actually said.

**Eleven fields**: name, origin, **region**, variety, altitude, roaster,
producer, **farm**, process, roast date, note. The list is `/v1/vision`'s
(`prompts.BEAN_FIELD_NAMES`) and it is written out in six statements that must
agree — `BeanFieldsDto`, `ScanReviewSheet`'s map and labels,
`BeanDraft.asMap`/`merging`, `repo.LABEL_FIELDS` and the server's prompt and
schema — **in the same order**, which `check_couplings.py` enforces. `farm` was
added on 2026-08-26 with prompt wording that keeps it apart from `producer`:
the grower is a person or a cooperative, the farm is the estate, finca, washing
station or mill. `region` was added on 2026-08-29, two revisions after the
column itself: the column landed first with the scan deliberately left alone —
this list reaches a deployed service, and reshaping its output schema as a side
effect of adding a form field is the thing `repo.LABEL_FIELDS`' opt-out shape
makes easy to do by accident. **Origin and region are defined to the model as one
instruction** (`prompts.LABEL_OCR`, corrected 2026-09-03). Adding `region` to
the field list made the schema *ask* for it without the prompt ever saying what
it was, and a key defined only by its name is answered from the name: a bag
reading "Ethiopia Yirgacheffe" came back with the whole string in `origin` and
`region` empty, or with "Ethiopia" in both. The two-level split — a country
from `Choices.ORIGINS`, then a subdivision from `Regions.forOrigin` — is this
app's, not the label's, and cannot be stated in either field alone, so the
prompt names `origin` as the country and nothing else, `region` as the area
inside it, and says explicitly to split a combined line. The same wording is in
`coffee/src/coffee_can/claude_ocr.py` and `qwen_ocr.py`; the three are a §4
pair-set and a bag should read the same on any of them.

**A running `coffee_server` must be redeployed
before the phone's scan actually returns a region**; until then the field
arrives absent, which is what an unread field has always looked like.
**`frozenDate` is deliberately not on the list** — a bag label cannot state the
day its owner put it in a freezer, and the same exclusion is made on the
desktop (`repo.LABEL_FIELDS`) and on the server for the same reason.

**Apply dismisses the sheet before it does the work, and nothing after the row
lands may kill the process** (2026-09-17, direct product report: saving a bean
added by scanning a label "will break and exit although the data is saved").

`applyScan` cleared `scanPhoto`/`scanResult` as the *last* statements of its
coroutine — after `showSnackbar`, which suspends for the snackbar's whole life.
So for about four seconds after Apply the review sheet was still up, still
offering its Apply button, over a page that had already flipped from `0.1` to
`0.2` underneath it. A second press re-entered with the same `scanPhoto`, whose
file `ImageIngest.attach` had already **moved**: `renameTo` fails on a source
that is gone, `copyTo` throws `NoSuchFileException`, and an uncaught throw in a
`rememberCoroutineScope` launch is fatal. The bean row had been written by then,
which is exactly what was reported.

Two rules follow, and both are general to this screen rather than to the scan:

- **State that guards re-entry is cleared synchronously**, before the first
  suspend point. It also means the `isNew` branch swap `persist()` triggers
  happens with no sheet standing on top of it.
- **Every file/Room write in a `rememberCoroutineScope` launch here is
  guarded.** `applyScan`, the Images strip's `addPhoto` and the foot capsule's
  Save all `runCatching` and report in a snackbar (`bean_photo_attach_failed`,
  `bean_save_failed`). This screen already reports every gateway failure in a
  sentence; a crash is the one report the user cannot act on. The same ordering
  bug held the page in modify mode for four seconds after a save, and `editing`
  now drops before the snackbar rather than after it.

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

**The FAB and its "Tap me" were removed on 2026-08-24 and restored the same
day.** For one revision the axis bar's centre slot was the only camera and
carried the mark; the mark had nowhere to hang but the page above the capsule,
where it read as a label on the page rather than on the button. The bar keeps a
camera of its own — a white disc with the camera inside it, §7.1 — so **`+1`
offers the action twice on purpose**: once in the chrome, once as the object
the page is about.

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

**Empty state: the heartbreak mascot at 160dp** (2026-08-24, direct product
request; it was the pour-over pose at 184dp). Note what this shares: the same
figure is `-1`'s "feed would not load" state, so it now carries two meanings.
The reading that reconciles them is the one this page wants — an empty log is
a small sadness, and the mascot is disappointed on the user's behalf rather
than reporting a fault. The copy is unchanged and still says plainly that
nothing is here yet, which is what stops it reading as an error.
`plan/v1/screenshots.py`'s `sessions_empty()` frame **still draws the
pour-over and cannot be fixed from that file**: there is no `ic_mascot_sad`
drawable for `_vector()` to read, because `CanBoySad` is Compose draw calls
only. Read the Kotlin for this screen, not the deck.

**A cup's row is green** — `JourneyGround`, the exact ground `+1` and `+1.1`
lie on (2026-08-20, direct product request). A cup is a session with a café
attached, so it lands in this list beside brews made at home and without a cue
the two are indistinguishable. Reusing the travel side's own token is the
point: a green row reads as "one of those" rather than as a status this list
invented. Nothing else changes — same height, same glyph, same divider —
because a cup is not a different *kind* of record, just one drunk elsewhere.

**And it names the café, bottom-right** (2026-08-21, direct product request).
The green already says *that* this was drunk out; `SessionWithBeanName.cafeName`
— the `journeys` row resolved by the same query that supplies the bean's name,
`LEFT JOIN` so the six brews in seven that were made at home are not dropped —
says *which*, which is the half worth reading back a month later. Null on a brew made at home and on a cup whose café has
been deleted — and, since Home stopped listing beans that came from a café
(§8.3), this is the app's only café corner.

**The card itself is `SessionCard`, and `0.2` draws it too** (2026-08-22,
direct product request). It was private to this screen while the bean page
drew its own flat `SessionLine` — no disc, no card, no cup colouring — so the
same brew looked like two kinds of record depending on which screen you
reached it from. One composable now, with the two callers varying **the two
strings and nothing else**: History titles the row with the bean and trails
the date, while `0.2` is already one bean's page, so the date is the title and
there is nothing left to trail. `SessionCardHeight` — the same
*construction* as Home's shelf card and, since 2026-08-24, not the same number
(§4.2) —
because a brew and a bean are deliberately the same object.

Every brew across every bean, newest first, with the dripper glyph at 64dp,
dose, score and extraction verdict. Header states the count. Empty state and
delete are both built. A **pushed** destination since 2026-08-19, reached from
Home's History action — so it carries a real back arrow again, and it no
longer claims `AxisPageInsets` (there is no axis Scaffold above a push, so
claiming only top and sides would leave its last row under the system bar).

### 8.6b `+1.1` Journey Profile

One café: name, visit date, city, **address**, note, up to three photographs,
and the **Cups** block. A saved café carries the foot capsule (§7.1a) in
its `add` arrangement — share, a green `+` that adds a cup, modify, and delete
once modify is pressed. The `+` is deliberately **not** gated on modify mode: a
cup is a row of its own, so adding one changes nothing about the café, and the
Cups heading's action was never gated either. No scan card (a café has no label) and no radar (a
journey has no flavour). **No barista either, since 2026-08-25** — a café has
many and which one made the cup is a fact about the cup, so the box is on
`+1.2` (§8.6c). The paragraphs under "The 2026-08-20 redesign" below still
argue about a barista capsule on this page; they are that day's record, not
the current layout.

**Its app bar is frosted, and has no rule under it** (2026-08-24, direct
product report: the header "doesn't have shade and transparent", and "its
boundary line should be removed"). It was the last bar on the journey path
still painting an opaque strip and closing it with a `TopBarDivider` — the
exact seam `axisChromeScrim()` exists to remove, and one `+1` had already
dropped. The two pages are meant to read as one place, so the bar you push
from and the bar you land on cannot be different objects. The graded scrim
**replaces** the divider rather than joining it: the frost holds for most of
the bar's height and releases over the last third, so the page emerges from
under the bar instead of starting at a line, and drawing both would be a soft
edge with a hard one on top of it. The content column spends the bar's height
as a spacer *inside* its scroll rather than as viewport padding — the same call
`JourneysScreen`'s list makes, and for the same reason: top padding fills the
strip behind a translucent bar with the page's own background, which would put
the frost over a flat colour and make it a solid bar again.

**Swipe right to go back to `+1`** (2026-08-23, direct product request). This
page is a push on top of the axis, and the axis is horizontal — Can travel is
the page you came from, so dragging the café rightwards putting it back is a
gesture the app has already taught. It replaces nothing: the back disc and the
system gesture still work and all three end in the same `leave()`, so a café
with unsaved edits asks before it goes whichever way you left it. Implemented
with `detectHorizontalDragGestures`, which waits for horizontal touch slop and
so leaves the page's own vertical scroll untouched; the page follows the finger
and springs back below a 96dp threshold, because a gesture that can fail
silently should show that it is being read. Rightward only — nothing sits to
the left of this screen.

**A cup is a `SessionCard`, like every other list of brews** (2026-08-22,
direct product request). It replaced `CupLine`, a bean name with a score at the
end of it. The bean names the row and nothing trails: this page already
supplies the café and the date, so repeating either would be the one fact the
reader has. **Its cups are drawn untinted** — `tintCups = false`, the only
caller that passes it. The green a cup carries in `0.3` is `JourneyGround`, and
this whole page *is* `JourneyGround`, so tinting here would be a card with no
boundary on a ground of its own colour. The rule is unchanged, not excepted:
the green says "drunk out" only where the page around it does not already.

The block is below one screen's fold, so the simulator carries a second frame
for it (`+1.1b_journey_profile_lower.png`), the way `0.2b` does for the bean
page. The Paparazzi golden stops above it too — verified on a device.

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

**That sheet says "Take a memory of the café" here**, not "Take a photo of the
bag" (2026-08-21, direct product request). `PhotoSourceSheet` takes the one
line as a `@StringRes` parameter and defaults to the bean wording; the journey
camera and a cup (§8.6c) pass `journey_photo_take` instead. Everything else on
the sheet — the "Which photo?" title, "Choose one I already have", and the
note that location data is stripped on the phone before anything is sent — is
the same promise whatever the picture is of, which is why this is a parameter
and not a second sheet.

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

**The form was sectioned** — *Café* (name, then address | city as a capsule
pair), *The visit* (visited on | barista). Both headings are gone now: *The
visit* on 2026-08-25 and *Café* on 2026-08-30 (above), so what the paragraphs
below describe as two sections is one unheaded form. **Address became a capsule**
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

**There is no "Café" heading, and the name box is modify-mode only**
(2026-08-30, direct product request). Both halves say the same thing: the app
bar above this form is already the café's name, in `titleLarge`, on every frame
of the page. A heading reading *Café* over a box reading *Belleville Brûlerie*
under a bar reading *Belleville Brûlerie* is the name twice and a label for it
once, on a page whose entire subject is that café. What is left is a form of
the *other* facts — address, city, date, note — which needs no heading to say
whose they are. `journey_section_place` was deleted from all three locales.

**An empty note box is absent in view mode** (2026-08-29, direct product
request). A locked field still shows its *value* — that rule is unchanged for
every field but the name — but a locked field with nothing in it is a label
over 88dp of nothing. `JourneyFields` draws the note only when
`enabled || value.isNotBlank()`, so Modify still offers it unconditionally,
which is the only place it could be offered from. The name box was the other
half of that rule until 2026-08-30 and is now simply absent while locked, which
does not contradict it: the value is not lost, it is in the bar. The address,
city and visit-date capsules are untouched — the request named the boxes, and a
capsule with no value is one 30dp row, not a section-sized hole.

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

One **cup**: a coffee you drank at a café. A saved one carries the same foot
capsule as `0.31` (§7.1a, §8.8) in its `add` arrangement, where the green `+`
adds a **pour stage** — a café is a list of cups, a cup is a list of pours.
Unlike `+1.1`'s, that `+` **unlocks modify mode — on the write, not on the
press**: a pour is a field of this record, written into `stages` and persisted
only by the tick, so a page that stayed locked would strand the edit with no
control on screen to commit it, and on the cup path the Pour stages section is
folded away until a stage exists. But a `+` that registered nothing must leave
the page as it was found (2026-08-30, direct product request), so the unlock
sits beside the commit: press `+`, dismiss, and the page is still locked and
still clean.

**It is `0.31` with a café behind it, and has no composable of its own**
(2026-08-21, direct product request: a cup "will also use this vibe brewing
page"). `CupDetailScreen` drew `0.1`'s bean fields above `0.31`'s four
sections; `0.31` grew a **Bean details** block of its own that same day for
vibe brewing (§8.8), which left the cup screen with nothing that was its own,
so it was deleted and `Routes.Cup` now resolves to `BrewSessionScreen`. The
route survives — the back stack has to tell a cup from a brew — and carries a
`beanId` as well as the café's id, because that screen edits a bean row that
already exists: `+1.1`'s "Add a cup" creates the blank one on the way out,
exactly as the vibe-brewing row in `0.31a` does, and an abandoned cup takes it
away again through the same `leaveWithoutSaving` sweep.

Everything `journeyId` changes is a label, a column or one field: **New cup**
as the title fallback, **Save this cup** on the button, **Delete this cup?** on
the delete prompt, **Take a shot** on the photo sheet, the `journeyId` written
onto the session, no Ask AI, the images strip above the fold, Brew details
folded to start — and, since 2026-08-26, the **Barista** box (below). The form
is otherwise the same form.

*Three wordings for one sheet, and the third is not redundant* (2026-08-21,
direct product request). `PhotoSourceSheet`'s take-label follows the table the
picture lands in, not the screen it was raised from. This sheet hangs off the
**Bean details** block and writes a `BeanImageEntity`, so `+1.1`'s "Take a
memory of the café" — which really does write `journey_images` (§8.6b) — was
naming the wrong subject here; and "Take a photo of the bag" names an object
that is usually not on the table at a café. **Take a shot** is neither, and it
keeps the sheet honest about what it is attaching the picture to.

**The save button no longer waits for a name — the refusal does** (2026-08-23,
direct product report: "I add a new cup, I modify it but I can't save it").
The rule below is unchanged and still binds; what moved is where it lives. It
used to sit in the button's `enabled`, which made a dead grey control at the
foot of a form the user had just filled in with a score, a radar and a
photograph, with nothing anywhere saying that one empty field three sections
above was the reason — and a disabled button cannot be asked. The button is now
live whenever the form is savable at all, and `save()` refuses out loud with a
snackbar (`cup_needs_name`). The same commit stopped `save()` swallowing a
failed write behind a debug log: a write that fails now says so
(`brew_save_failed`) instead of looking like one that worked.

**Why a cup waits for a name at all.** `+1.2`'s own rule, kept: a cup is a
coffee you are recording because of what it was, and a nameless one is a row
in a café's list with nothing in it. Vibe brewing makes the opposite promise —
brew now, name the bean later — so it still saves blank.

**A saved cup opens read-only, with Modify**, which is a change from the old
screen: it inherits `0.31`'s view/modify mode along with everything else,
rather than being permanently editable.

The paragraphs below record how the page was built and why the shared blocks
exist; they are still true of what it draws. Original request 2026-08-20.

**A cup is a bean plus a session, not a third kind of thing.** Saving writes
one `BeanEntity` (what the coffee was) and one `SessionEntity` (how it tasted)
whose `journeyId` points at the café. Nothing new was modelled, and two things
fall out free: the cup appears in History because History lists sessions, and
every section on the page is the real one rather than a lookalike.

**Every block is borrowed, and that drove a refactor** whose value outlasted
the screen that prompted it. The four brew sections were inline in
`BrewSessionScreen` and had to be lifted into `BrewFormSections` — ~230 lines carrying eleven flavour sliders, a radar, a
stage editor and thirteen capsules, which is the largest block in the app a
second copy could have happened to. The extracted composable is **stateless**:
every mutation leaves through `onDraftChange`/`onStagesChange`, so two screens
that keep their drafts in different places share one UI. Verified as a pure
refactor — all 94 goldens passed unchanged immediately after the move.

**What deliberately did not come along:** the Ask-AI action, the "asking…"
spinner, the error line and the consent-blocked notice. Those are
`AiGateHost`-gated, and a cup has no bean for `suggestBrew` to reason about;
`detailsHeader` and `afterDetails` are the slots that keep them out of the
shared file, and a cup passes a plain heading through the first and nothing
through the second. Unchanged by the 2026-08-21 merge — the cup path simply
sets the same condition false on the screen it now shares.

**Barista lives here, and above the fold** (2026-08-26, direct product
request). `+1.1` shipped it as a property of the *café*, 2026-08-25 moved it to
the session — a café has many baristas, and which one made the cup is a fact
about the cup — and this is where the box itself now is: `showBarista` is
passed by this path alone, exactly as `photosOutsideFold` is.

It is drawn **first inside the Brew details card, within the fold** — which
reverses the placement it shipped with one day earlier (2026-08-26, direct
product request: "the barista input box should be hidden in the more details in
cup page"). It sat outside the fold on the argument that a cup's fold hid
*everything*, so the one question a café cup could answer would have been
collapsed by default. That argument expired the same day: the fold on a cup now
keeps whatever has been answered and hides only the empty boxes (below), so a
filled barista survives it like any other filled field and an empty one waits
behind "More details" with the rest of the unasked questions.

**No scan card.** It is `0.1`'s, consent-gated, and unreasoned-about for a cup.

**The images strip is above the fold here, and only here** (2026-08-23, direct
product request). `BeanDetailsSection` keeps the eight secondary bean fields
behind *More details* on every path, and the photo strip used to be folded with
them. A cup is the one route where that hid something: the photograph is the
point of recording a café coffee, the bean row is always brand new so
`PhotoHeroPage` at the top of the page has nothing to show, and the strip's "+"
tile is therefore the only door to attaching one. `photosOutsideFold = true` is
passed by this path alone — every other caller arrives on a bean whose pictures
the hero is already displaying, so a second copy above the brew fields would
duplicate what the reader is looking at. The strip carries its own **Images**
heading either way, so above the fold it reads as a section of the page rather
than a row that escaped from one.

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

**A tapped bean opens `0.2`, its own page — not a brew form** (2026-08-29,
direct product request). It was `Routes.brewSession(id)`, because this screen
existed only as the second step of "log a brew". Since Home's shelf heading
also opens it, it is now the app's one *list of every bean* and its tap does
the unsurprising thing.

That has a price, and it is stated rather than hidden: the FAB path — "which
bean?" → "pick a bean" → tap — now lands on `0.2` and needs its **New brew** to
finish, one tap more than before. It falls only on beans that were not in the
sheet's own shortlist, which still brews directly. The alternative considered
and rejected was an argument on the route so the same screen could mean two
things depending on who opened it; a screen whose tap target is invisible in
its own source is the worse trade.

### 8.8 `0.31` Brew Session Detail

**Pour stages opens on the can clock** (2026-08-29, direct product request:
the section was being skipped every brew). What was there was one `bodyMedium`
line in `onSurfaceVariant` — the colour this app uses for information already
dealt with — under a heading whose only control was a right-aligned
`TextButton`. It read as *this section is off*, which is why it got skipped.

The empty state is now **`ScanSection`'s construction, reused deliberately**:
the same `secondaryContainer` card at `CardCorner`, 16dp padding, a centred
column, a 108dp mascot over a `titleMedium` line, a centred `labelSmall` line
and a filled `Button`. Those two blocks are the same sentence about two
different jobs — *this is tedious, let the app do it* — and someone who has met
one on the new-bean form should recognise the other without reading it.

**And the pours land in that same card** (2026-08-30, direct product request:
the stages "shown on a green background just as 'Time your pours' block but
without clock and other texts"). Filled and empty are one object in one place
on the page — the card does not vanish when the first pour arrives, it fills
up. It keeps the `secondaryContainer`, the `CardCorner` and the 16dp gutter,
and drops everything that was there to *ask*: the mascot, the title, the body
and the timer button. Rows keep no colour of their own —
`CardDefaults.cardColors(containerColor = …)` resolves content to
`onSecondaryContainer` — and carry no rule between them (§4.2).

**And the block is the same size locked as unlocked** (2026-08-30, direct
product request). `StageRow`'s delete slot is always laid out; only the
`IconButton` inside it comes and goes. Dropping the button outright changed the
section twice over: the row lost the 48dp that Material's
`minimumInteractiveComponentSize` was setting through it, so every pour — and
the card around them — got shorter, and the two weights left behind re-divided
the whole width, so the numbers moved sideways too. A locked page has to be the
same page. The slot holds an *empty* `Box` rather than a disabled button: a
greyed X on a page with no editing on it offers something the page cannot do,
which is the opposite trade from `DetailActionBar`'s greyed tick (§7.1a) — that
one is greyed precisely because the mode it belongs to is on screen.

`BrewStagesScreenshotTest` carries three goldens (the third is the timer, below): the section in place at 1600dp,
because every session in the main brew test records no pours at all, and the two
modes stacked, because `editing` is the screen's own state and a saved session
always opens locked, so the only way to photograph both is to draw the rows
directly.

**The manual route is the heading's `+`, and there is nothing under the card**
(2026-08-30, direct product request: "remove add a stage button under the green
block, replace the 'add a stage' button beside title by + icon"). A full-width
`OutlinedButton` sat below it, on the argument that the alternative here is one
act with one sheet and so deserves a real button; what that missed is that the
heading already carried the same words as a `TextButton`. One section, one act,
two controls — the lower of them the widest thing in the block. The heading's
survives, now as `Icons.Filled.Add` via `actionIcon`, the same move `0.2`'s
Sessions heading made on 2026-08-29 and for the same reason: the app spells
"add one of these" as a `+` on both FABs, on the axis bar's centre disc and on
every detail page's foot capsule. `brew_action_add_stage` is still passed and is
still what TalkBack reads and what `check_design.py` diffs. The card is left
saying what the section is for and offering the timer, which is the one thing it
can do that the heading cannot.

**Only while editing.** A saved brew that recorded no stages is reporting a
fact rather than being asked for one, so the old sentence stays on a read-only
page. A café cup never reaches this at all — `keepFilledWhileFolded` already
folds stages away for a drink you did not pour.

**The timer is built** (2026-08-31, direct product request: "when start timer,
the can clock logo will show be bigger and show timer instead the can clock.
Double tap on the timer will start timing a new stage, single tap when a stage
starts will note the time when the pouring is over in this stage. Add a final
button when all the stages are finished"). `Start timer` was drawn disabled
until then, which was the honest state of a block whose timer did not exist;
`enabled = onStartTimer != null` survived the wiring rather than being deleted
with it, because the same expression is what keeps the button honest on any
future path that cannot offer timing.

**The card has three heads, and the pours sit under whichever is drawn.** The
section had branched into two whole cards — the invitation, or the list — and
the timer would have made it a third; what actually varies is the *head*:
nothing (a list on a locked page), the invitation (mascot, title, body,
`Start timer`), or the running clock. The card, its `secondaryContainer`, its
`CardCorner` and its 16dp are the section's; the head is drawn inside it. This
is not a tidy-up: **the running timer appends pours to the list as they
happen**, so a timer that lived in a card the pours did not share would vanish
at the moment it started being useful.

**The readout stands in the mascot's own 108dp.** Starting the clock swaps one
object for another in place rather than resizing the card under a thumb that is
about to tap it again. The figure is not shrunk beside the numbers or moved to
a corner: the request is that the clock *becomes* the timer, and a can with a
painted-on 10:10 dial standing next to a real running clock would be the page
telling the time twice.

**It is the app's one scaled type role, and it is scaled, not invented.**
`displaySmall` — the largest role in the theme, declared there precisely so a
screen does not invent one — is 36sp, which is *smaller* than the mascot it
replaces, and the request was that it get bigger. The readout keeps everything
that makes the role this app's type (Fredoka, SemiBold) and overrides only the
size, at 64sp: a stopwatch read at arm's length across a counter, not a new
heading level anything else may reach for.

**Two gestures on one target, and the target is the readout.** A double tap
starts a pour (`atSec` = now); a single tap ends the open one (`endSec` = now).
A pour is timed with wet hands while water is going into a cone, so what the
block needs is one target the size of the card and a gesture that cannot be
missed by aiming — not two small buttons. Compose delays the single tap by the
double-tap timeout when both are registered, so a double tap never also fires a
single one and the two cannot both write to the same pour. The line under the
readout says which state it is in: *Double tap to start a pour* when nothing is
running, *Pour N is running — tap when it's done* when one is.

**Nothing is stamped with a time nobody observed.** A double tap while a pour
is still open does *not* close it — the pour may have ended twenty seconds
earlier and the user simply did not tap, and the gap between a pour ending and
the next starting is the drawdown. The end stays unmarked, which the facts line
draws as the absence it is. The final button follows the same rule.

**The final button is at the foot of the card, under everything the task
produced**, and it is the only way out of the running state. It stops the clock
and leaves what was recorded; it invents no end for an open pour, and there is
nothing else for it to do, because the pours are already in the list.

**The clock is an origin, not a tick count**, and it is `BrewSessionScreen`'s
`rememberSaveable`, not the block's `remember`. A brew is four minutes with the
phone on the counter: a timer that lived in the composable that draws it would
be reset by a rotation, and one that accumulated ticks would drift and would
have to be paused. What is stored is the wall time of `Start` plus which pour
is open; the elapsed seconds are computed every frame. It reads the clock
through `BrewClock`, the seam that already exists so a golden of a *running*
timer is not a picture of the second it was recorded in.

**TalkBack gets named actions, not gestures.** A double tap *is* TalkBack's
activate, so the pair is unusable with a screen reader by construction; both
acts are published as custom accessibility actions on the same node, which
offers them without a second set of visible controls everybody else has to look
at. The section heading's `+` remains the route that needs no timer at all.

`BrewStagesScreenshotTest.pourTimerHeads` is the golden: the invitation and the
running clock, in the card, with a pour timed end to end and a second one still
open.

#### 8.8a The can clock

The mascot: **the same can, with a clock's face and two hand-lettered "ding"s
over its head.** `canTorso()` and `bellyWordmark()` are unchanged, so the lid,
body, pull tab and name are the objects every other pose draws — a timer for
this app is *the* can with a clock on it, not a clock borrowed from an icon set
and stood next to the brand.

- **The wordmark moves down 7 units, and only here.** The dial wants the upper
  body and the name occupies y 48..66 at the shared placement. Shifting the
  *call* rather than the function keeps that placement true for the five poses
  that use it, and keeps the name at its own scale — shrinking it was the other
  way out, and the name is the one thing on this figure that may not be
  redrawn. At +7 the glyphs sit y 55..73, the dial ends at 52.5, the body's
  bottom curve is at 77.5.
- **The dial is a prop and is drawn at prop weight** — 3.0, against the body's
  5.2 and the limbs' 4.2, the same weight the pull tab uses. Four ticks, not
  twelve: at 108dp twelve are a grey ring. The hands read **10:10**, the one
  position that leaves the face open instead of striking through it.
- **The ring is one burst in three seconds.** A figure that rings continuously
  is a nag and one that rings once is missed; a burst every ~3s is about the
  interval at which a still page re-attracts the eye, and it leaves two-thirds
  of the cycle quiet so the card is calm to read while you type under it. The
  burst window is `win()` — the same shape the camera flash uses — and it damps
  the shake as well as raising the dings, so the can is still by the time they
  have gone. The can rocks about **its own base**, not its middle: a can rung
  by its alarm rocks on the surface it stands on.
- **The dings are strokes, not a font**, for the reason `TapMeMark` is: this is
  the white line every mascot is drawn in, and a typeface beside them reads as
  a caption that wandered into the picture. They are authored in a 44×22 box on
  a 16 baseline so the four letters share one x-height.
- **They stay on the disc, which is what sizes them.** White on brand green,
  with nothing but pale ground outside it — a ding that clears the edge does
  not read as leaving, it disappears. At 0.5 scale the pair spans x 18..82
  against a disc 15.3..84.7 wide at that height.

Verified legible at 108dp (its drawn size) and 84dp; at 64dp the dial starts to
silt up, so do not take this figure below ~84dp. `MascotPoseSheetTest`'s
`canClockRing` is the golden that covers the burst — every other golden of this
figure captures `phase` 0, the quiet frame.



One brew, created or edited. **Bean details** (see below), then brew fields
(dripper, grinder, grind size, filter, dose, water, **alkalinity**, ppm,
humidity, total time), **Pour stages** with its own editor sheet, then **How
was it?** — Score `ValueBar`, `ExtractionBar`, `ConcentrationBar`, note — then
**Flavor**: the radar over eleven `ValueBar` sliders.

**Barista is a cup's field, and is not drawn here** (2026-08-26, direct product
request: "remove barista box in brew details of session page. However, a
barista box is needed in Cup profile page of a journey"). It spent 2026-08-25
in the details card on every path, on the argument that a friend's pour-over
and a competition brew also have somebody who made them. In use that is not
what the field is for: almost every row in this app is a coffee the user made,
so on this page the capsule was an always-blank question sitting between Filter
and Dose. `sessions.barista` is unchanged and still travels in the bundle —
what narrowed is the input, which `BrewFormSections`' `showBarista` now gates on
`journeyId != null`. A brew logged at home keeps whatever its column already
held: `SessionDraft` still hydrates the value and writes it back, the same
treatment `waterTempC` gets. See §8.6c for where the box went.

**Concentration sits directly under Extraction** (2026-08-22, direct product
request), not beside Score: they are the two axes of the brewing control chart
and a brew that missed is diagnosed by reading the pair. A cup can be fully
extracted and watery, or under-extracted and syrupy; one number cannot say
both.

**Brew details and Pour stages fold behind "More details"** (2026-08-22,
direct product request), the same control `BeanDetailsSection` carries, on
`SectionHeader`'s new `secondaryAction` slot to the left of Ask AI. Both
sections fold together, because the switch answers one question — *did you
make this coffee?* — and the pours are the second half of that answer. It
opens **expanded for a brew and folded for a cup**: a home brew is *about* the
grind and the pours, while a café cup has neither, and eight empty capsules
between the bean's name and the flavour wheel are eight answers nobody is
going to give. The flag is seeded from `journeyId` and then owned by the user,
including across rotation. Unlike Bean details' toggle it stays visible while
the form is locked — what it reveals there is values you can read, not input
boxes you cannot type into.

**On a cup the fold hides only what is empty** (2026-08-26, direct product
request: "brew details by default show the already input details and … other
unfulfilled details will show after more details is tapped"). Folded, a cup
draws the answers it has — the date, the barista, a grind size somebody
happened to mention — and opening it brings the empty boxes back so they can be
filled. Pour stages follow the same rule: present when there are any, absent
when there are none. A brew made at home passes `keepFilledWhileFolded = false`
and keeps the original all-or-nothing fold, because there the section is the
form's subject and hiding it whole is the point. The eight capsules are
collected and **repacked** into pairs rather than written as four fixed
`FieldPair`s — dropping one half of a fixed pair leaves a hole mid-card — and
each carries a `key`, so a list whose length changes with the fold cannot hand
one capsule's remembered dropdown state to another.

**Water alkalinity sits where Water °C used to** (2026-08-21, direct product
request). The temperature column stays in `sessions` and still round-trips
through the draft (§9); it simply has no input any more, and the pour stages
below still ask per pour — which is where a temperature that changes mid-brew
was always recorded.

**The title header pins, frosted, exactly as `0.2`'s does** (2026-08-24,
direct product request: on a new cup and on a new session "the header section
should have a shade and reside on top effect just as the title header in bean
profile page"). The bean's name freezes into a strip at the top of the window
the moment the headline has travelled under the status bar, over
`axisChromeScrim()` + `axisChromeSheen()` so the photo and the panel pass
beneath it. `titleTopPx` is **measured**, not inferred from the scroll offset:
the hero shrinks before the panel moves, so a threshold on the offset fires at
the wrong time on a photo with a different aspect. The strip is inset 72dp at
both ends to clear the floating back and share discs — it is a label, not a
replacement top bar, and it must not land on the controls already up there.
`0.2` and `0.31` are the same shape of page, so this is deliberately the same
construction and not a similar one.

**Bean details sits above Brew details — on a bean that still has to be named**
(`BeanDetailsSection`, 2026-08-21; gated 2026-08-24). It shows **one** input,
the bean's name, and **More details** as the section heading's own trailing
action; pressing that reveals `0.1`'s own `BeanFieldsGrid` (origin, variety,
altitude, roaster, producer, farm, process, roast date, note) and
`ImagesStrip` beneath it, with the photo sheet and the roast-date picker wired
exactly as on `0.1`.

**A cup draws it only in modify mode** (2026-08-26, direct product request:
"the entire Bean details section should be hidden once the cup is logged … the
bean details will only show when modification mode"). A logged cup's coffee is
already stated by `BeanHeaderSummary` under the headline; the block adds a
stack of locked input boxes saying the same thing again, between the cup's name
and the score and flavour wheel the page was opened for. Pressing Modify brings
it back, because then the boxes are boxes. A **new** cup is untouched —
`editing` is true from its first frame — and the brew path still keys on
`beanNamed` alone.

**A brew of a bean out of the can draws none of it** (2026-08-24, direct
product request: "when add new session in an already created bean, remove bean
details in the add session page — the details are written on the header
section"). On that path the block was eight capsules and a photo strip
restating a bean the user picked *by name* two taps earlier, sitting between
the headline and the brew fields they came for. `BeanHeaderSummary` — `0.2`'s
own summary lines, the same composable, so the two pages state a bean's
identity in one voice — takes its place: origin · process · roast level, then
the roast date. Nothing is lost, because everything the block could show that
those two lines cannot is an *input*, and inputs for a bean belong on the bean.

The test is `beanNamed`, and it is **emptiness, not provenance** — the same
rule `leaveWithoutSaving` applies. Nothing is threaded down to say "this came
from vibe brewing"; a bean with no name is one this form has to be able to
name, whatever route produced it, which keeps vibe brewing on the full block
without it having to announce itself. It is read off the **stored row at
hydration**, never off `beanDraft`, because the draft's name changes as the
user types and a live test would tear the section off the page mid-word on the
one path that needs it most. **A cup keeps the block whatever its bean is
called** (`cup ||`): `photosOutsideFold` exists because a cup's photograph is
the point and there is never one yet, so dropping the block on a saved cup
would take the only "+" tile with it.

**It is a toggle, and it lives on the heading** (2026-08-21, direct product
request). Open, the action reads **Less details** and a second press folds the
block away again. Both halves reverse the first cut of this block, which put a
full-width text button under the name field and made the reveal one-way on the
argument that a control able to hide fields someone has typed into can lose
them from view. Nothing is lost: the draft is held by the screen, not by the
composables, so collapsing and reopening returns every value — while having no
way back meant one exploratory tap pushed Brew details down the page for the
rest of the session. `SectionHeader` already carries a trailing action slot,
and using it is what makes the label read as the heading's own switch rather
than as one more control in the form's stack.

*Why a brew form edits a bean at all:* two of the ways in arrive on a bean with
no name — vibe brewing creates a blank row so the session has something to
belong to, and a cup (§8.6c) is a coffee this phone has never seen — and until
this block existed neither could say what the coffee *was* without leaving the
form. *Why it starts collapsed on the paths that still draw it:* the block is eight
optional inputs plus a photo strip, and opening it pushes Brew details a screen
and a half down. (Until 2026-08-24 that argument also had to cover a bean whose
fields are full, because the block was drawn there too; now it simply is not.)

The bean draft follows the same discipline as the session beside it — typing
reaches Room only on Save, it counts towards `dirty`, and it locks with the
rest of the form in view mode (`BeanFieldsGrid`/`ImagesStrip` take an
`enabled` flag for this; while locked, the details toggle and the "Add img"
tile are absent rather than dead — a block already open stays open and simply
reads as text, so what the lock hides is the control, not the fields). The one exception is a photograph, which is a
file plus a row and is attached immediately — the exception `0.1` and `+1.1`
already make.

**Ask AI is on this header only for a bean out of the can** (2026-08-21,
direct product request: "in the vibe brewing, remove ask AI"). `suggestBrew`
sends the *bean* — name, origin, roaster, process — and asks what to do with
it; on the vibe-brewing and cup paths there is no such bean yet, only a blank
row the form is in the middle of filling in, so the action offered a recipe
derived from nothing. The condition is `bean.name.isNotBlank() && journeyId ==
null`, evaluated on the stored row rather than the draft so the button cannot
appear and disappear as someone types.

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

**Delete** (an already-saved brew only) is a slot of the foot capsule
(§7.1a) — moved off `PhotoHeroPage`'s pulled disc 2026-08-20 to sit beside
Modify/Save changes at the form's foot as a `RemoveButton`, then into the
capsule with them on 2026-08-25, and behind Modify on 2026-08-30, once the
capsule's centre became `+`. `DeleteBrewDialog` still gates the actual delete.
On a *new* brew, which has no capsule, the foot Row is still the one place
Save lives.

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

**A stage nobody typed into is never registered** (2026-08-30, direct product
request). All three add actions — the Pour stages heading, the empty-state
card and the foot capsule's `+` — used to append a blank `StageDraft` and
*then* open the editor on it, so dismissing the sheet left a row of dashes in
the list and a form that had only been looked at believed it had unsaved
changes. A new pour is now held outside `stages` until Done (`StageEdit`, with
its seed): dismiss adds nothing, Done on an empty form adds nothing, and Done
on an *existing* pour cleared to empty removes it — the same end state as the
row's own X. Neither confirm button greys itself out; a dead control explains
nothing, and Done simply has nothing to add.

**`Velocity (g/s)`** (2026-08-30, direct product request) is a **fourth
measurement, not a derived one** — `At` is when the pour *starts*, so
`waterG / atSec` is a different number and no arithmetic over the other three
produces it. That is why it needed a column on both sides (`MIGRATION_14_15`,
`brew_stages.velocity`), an entry in `sync_tools._STAGE_FIELDS` and a
`SyncBundle` key, taking the bundle to **v8**; a stage field missing from any
one of those simply never travels, and nothing fails when it does not. It also
joins the row's facts line — that line is *every measurement this pour has*,
and a field the editor asks for but the list never shows is one nobody can
check without reopening the sheet.

**`At` and `Ends` are the pair in one `Row`, and Velocity moved down a row**
(2026-08-31). It shipped for a day beside `At`, on the argument that when a
pour happens and how fast it goes read as one question; a pour's *two clock
times* are a closer pair than that, the timer fills both with its two taps, and
three numeric fields across a 360dp sheet is three fields nobody can read.
Velocity keeps its half-width box with nothing beside it so every input on the
sheet is one of two widths. Both times are pickers sharing one
`DurationPickerDialog` and one piece of state — two booleans could both be
true, and the second dialog would open behind the first with the same title.

`Ends`, not `Ends (time)`: at half width with a trailing clock icon the longer
label wraps to two lines and the empty field grows taller than `At` beside it.

**A pour's end is `session_stages.endSec`, and it is a third independent
measurement.** It is not the next pour's `atSec` — what sits between the two is
the drawdown — and not derivable from velocity. Same cascade as `velocity` one
day earlier: `MIGRATION_15_16`, `brew_stages.end_seconds`, `_STAGE_FIELDS`,
both halves of `SyncBundle`, bundle **v9**. In the facts line the two read as
one range, `0:00 → 0:35`, which is also what makes an unmarked end visible: a
pour the timer never closed reads as a bare `0:00`.

**The stage sheet's clock fields are pickers, not typed fields** — a trailing
clock icon on each of `At (time)` and `Ends`, tapping anywhere on the field
opens `DurationPickerDialog`. They write `m:ss`; `parseSeconds` still accepts
`"105"` and `"1m45"` for AI suggestions and older rows.

### 8.8a `0.31c` A session as a card over its bean — `BrewPresentation.Card`

**Tapping a session on `0.2` no longer navigates** (2026-09-17, direct product
request: it "won't redirect to the session page, but show a carte pop upon the
bean profile page … the carte is slightly smaller than the screen, when it pops
up, the background (bean page) is blured out … in this carte, the format is
identical to the original page but remove the head page and bean detail").

**It is `0.31`, not a summary of one.** `BrewSessionScreen` takes a
`BrewPresentation` (`Page` | `Card`); everything the page can do to a session —
modify, save, share, delete, add a pour stage, ask the gateway — the card does,
because it is the same composable. `Card` drops exactly two blocks:

| Dropped | Why |
| --- | --- |
| **the head page** — `PhotoHeroPage`: the photograph, the floating back disc, the pinned frosted title | A hero inside a card is a second page inside the first, and the bean's photographs are what the blurred page behind it is showing |
| **the bean detail** — `BeanHeaderSummary` and `BeanDetailsSection` | The card is opened from that bean's own profile; both restate, a centimetre away, what the reader was looking at when they tapped |

The headline stays and gains a `Close` `IconButton` beside it: the headline is
not the head page, and the hero's back disc — the page's way out — went with the
hero. `BrewCanvas` is the one call site that swaps the frame, so the body
between the two presentations cannot drift.

**Only existing sessions.** The Sessions heading's `+` and the foot capsule's
green disc still navigate to `0.31` as a destination. A new brew is a form to
fill in, often with a running pour timer; a card over the bean it is about would
be standing in for a page rather than summarising one.

**The card and the blur — `CardOverlay` / `Modifier.pageBehindCard`.** The card
is `SheetCorner`, `background`, 16dp of elevation, inset from the **safe** area
by 12dp horizontally and 20dp vertically. Behind it: `blur(20.dp)` on the bean
page under a 40% `scrim` tint — `coffee_website`'s `.lb-scrim` recipe
(`blur(20px) saturate(135%)` over `--deep` at 40%), because the two surfaces mean
the same thing and should not look like two effects.

Three consequences, each of which has a reason to exist:

- **It is not a dialog or a sheet.** Those are new windows, and a new window
  cannot blur what is behind it, because what is behind it belongs to another
  window. The overlay lives inside `BeanDetailScreen`'s composition, which is the
  only way `pageBehindCard` can reach that screen's nodes at all.
- **`Modifier.blur` is API 31+, and `minSdk` is 26.** This is the wall
  `AxisChromeAlpha` documents (§7.1) and it has not moved. What has changed is
  the surface: a transient modal may be richer on newer devices where a
  permanently visible bar may not — provided the floor still reads, which is why
  the scrim goes to 0.55 where there is no blur and 0.40 where there is.
- **`DetailActionBar` gained `insetNavigationBar`** (default `true`, so no
  existing caller changed). The card's foot is already clear of the navigation
  bar; paying the inset twice floats the capsule a gesture-bar's height up inside
  its own card.

**It moves in, it does not appear** (2026-09-17, direct product request: "add a
move in for the card, not jump out"). `CardOverlay` holds a
`MutableTransitionState` that starts false and is flipped true on its first
composition, so the entrance has somewhere to begin: the card rises an eighth of
the screen and fades in over 260ms on `LinearOutSlowIn`, the scrim fades on its
own curve beside it, and the exit mirrors both at 180ms on `FastOutLinearIn` —
the pair `Nav.kt`'s camera flood already uses. The transition state is what buys
the **exit**, which a plain `if (open)` cannot have at all, and it is why the
content lambda is handed a `dismiss`: a close button wired to the caller's
`onDismiss` would cut the card out of the composition mid-animation.

**And it opens filled, never on a default form** (2026-09-17, direct product
report: the card "will load a default page then load the information"). Room
answers a flow after the first composition, so `0.31`'s first frames are a blank
`SessionDraft` under `brew_title_fallback`. On a page that is invisible — the
navigation transition covers it. A card has no cover: it opens in the same
window, over a page the reader is still looking at. `BrewCanvas` therefore draws
nothing in card mode until `hydrated && beanHydrated` — the same two flags the
draft itself waits on, not a third test that could disagree — and an empty card
rather than a skeleton, because a skeleton is a second layout to keep in step
and this wait is measured in frames. Both flags are `rememberSaveable`, so a card
restored after process death comes back filled instead of blanking itself.

`SessionCardOverlayScreenshotTest` is the golden. It reconstructs the stack
rather than tapping into it. **The blur does render in it** — layoutlib applies
the `RenderEffect` — so the frame is evidence for the API 31+ path; what it
cannot show is the API 26..30 path, where `Modifier.blur` is a no-op and the
0.55 scrim is the whole effect. It provides `LocalInspectionMode` so the
entrance is photographed at its resting state, the way `FlavorNoteSheet` does:
Paparazzi's frame clock never advances, and the first recording of this golden
was an invisible card over a blurred page.

### 8.9 `+2` I can

Two states, signed out and signed in. The mark, the state line — *"Your beans
and sessions stay on this phone. Sign in for AI label reading and coffee
news."* — and the sign-in button. Then **About & legal**: Language, Sync with
desktop, Privacy Policy, How we use AI, and the account controls.

**The sync dialog has a third row on one account only.** "Sync with server
(test)" appears when `AiGateway.syncAvailable` returns true, which happens only
for the account `coffee_server`'s `SYNC_ALLOWED_EMAILS` names — see
`specs/legal-accounts.md` §3.8a and `specs/coffee-server.md` §3.2f. It is
`null`-gated rather than boolean-gated so the row cannot be drawn without an
action behind it, and it sits *below* the two file rows because those are the
shipped feature and this tests a different architecture: one where the server
holds a copy of the log, which the two above exist specifically to avoid.

Tapping it runs **pull, merge, push** — importing the remote bundle before
uploading, so two devices alternating converge instead of overwriting each
other. The merge is `SyncBundle.importFrom`, the same one desktop sync uses,
with the same guarantee and the same limitation: it never overwrites, so an
edit made on the other phone does not travel. A failure (offline, not
allowlisted, server down) hides the row rather than raising an error, because
its only consumer is a button's visibility.

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

**The sheet opens fully expanded and shows the card whole** (2026-08-30, direct
product request). `ModalBottomSheet` is partially expanded by default, which
left the preview cut off at the fold until it was dragged up, so it takes
`skipPartiallyExpanded` — the same call `StageEditorSheet` makes, for the same
reason: this sheet has one subject, and half a view of it is not a state worth
stopping in. The preview is also no longer sized from the width alone: a card
is 1080 wide and *as tall as its content* (a journey's grows with its cups), so
it takes the smaller of 62% of the column and what 55% of the window leaves,
which keeps the Share button under it on every card. The column scrolls
regardless, so a short screen degrades to scrolling rather than to a button
nobody can reach. `ShareCardSheetScreenshotTest` is the golden for the fit, at
both card shapes; `ShareCardSheetContent` is split out for it exactly as
`StageEditorSheetContent` is.

### 8.13 `-1 (v2)` Can Drink

Complete and unwired — see §1.

---

## 9. Data model

Room, mirroring `coffee-can`'s SQLite schema column-for-column — **except the
last two tables, which have no desktop counterpart at all**. As of 2026-08-23
the mirror is exact again for `beans`, `sessions` and `session_stages`: the
desktop grew `brew_sessions.water_g` / `water_temp_c` / `water_alkalinity` /
`total_time_sec` and `brew_stages.label`, which had drifted phone-only, so the
only session column with no counterpart is `journeyId` — and that one is
structural, since `journeys` is ours alone.
**`version = 15`, `exportSchema = true`**, with named `MIGRATION_1_2` through
`MIGRATION_14_15`. `fallbackToDestructiveMigration()` is banned, and every
migration is **additive only** — which is why two sets of columns are still in
the schema with nothing reading them (`journeys.latitude`/`longitude`, §8.6b,
and `sessions.waterTempC`, below).

Eight entities:

| Table | Notes |
| --- | --- |
| `beans` | identity + provenance, `status` (`draft`/`saved`), `flavorSource` (`auto`/`manual`), and **eleven flavour columns** |
| `beans.farm` | the estate or washing station a lot came from (2026-08-26, direct product request) — the left box on the basics grid's second line, the third item on the shelf card's lot line, and a row on the scan-review sheet: it is on `/v1/vision`'s field list and in `/v1/suggest`'s bean, unlike `frozenDate`, which no label can state. **Beside `producer`, not instead of it**: a producer is a person or a cooperative, a farm is a place, and one producer's two farms make two distinguishable coffees. Crosses as `farm` (bundle **v6**) |
| `beans.frozenDate` | ISO-8601 day the bag went into the freezer, null for one that did not (2026-08-26, direct product request). **One nullable date is the whole state** — there is deliberately no `frozen` boolean beside it to disagree with, because freezing is a thing that happened on a day and the count of days since is the only reason anyone records it. `0.2` draws it under the name (snowflake, checkbox, "Frozen 12 Aug 2026 · 14 days"); Home draws the count alone in the card's bottom-right corner. Crosses as `frozen_date` (bundle **v6**) |
| `beans.region` | where inside `origin` the lot grew (2026-08-29) — "Yirgacheffe" under "Ethiopia". Free text like `origin`; what the picker offers is `Regions`' list for the country, coffee regions first and ISO 3166-2 subdivisions after. **Kept when `origin` changes**: a region that no longer matches its country is wrong and visible, and deleting what someone typed is wrong and invisible. Crosses as `region` (bundle **v7**), and is storage-only on the desktop like `farm` — no CLI prompt and no GUI box reads it. **On the scan field list since 2026-08-29** (§8.5), which is a later pass than the column: a bag prints its region more often than it prints a farm |
| `beans.roastLevel` + `colorValue`/`weightLoss`/`expansionRate` | the roast block (2026-08-24) — `roastLevel` holds a `ROAST_LEVELS` **key**, never an index and never a translated label. Crosses as `roast_level` etc. (bundle v5) |
| `bean_images` | `position`, `filePath`, `rotation` |
| `sessions` | brew parameters, `score`, `extraction`, `concentration`, note, **the same eleven flavour columns**, and `flavorNotes` |
| `sessions.concentration` | −1…+1, how strong the cup was — the second slider in How was it (2026-08-22, direct product request). Null is "not rated", never a balanced zero. It was the first of the late columns to cross: the desktop grew `brew_sessions.concentration`, a CLI prompt and a GUI bar the same day, taking `SyncBundle.VERSION`/`BUNDLE_VERSION` to **3** |
| `sessions.waterAlkalinity` | carbonate hardness, ppm as CaCO₃ — the Brew details field that took Water °C's place (2026-08-21, direct product request). **Beside `waterPpm`, not instead of it**: ppm is total dissolved solids, alkalinity is buffering, and two waters at the same TDS read completely differently in the cup. Phone-only for two days; **it crosses since 2026-08-23** (bundle **v4**), together with `waterG`, `waterTempC` and `totalTimeSec` |
| `sessions.waterTempC` | **retained, no longer surfaced** — the field the line above replaced. Dropping it means rebuilding the table and destroying temperatures a user typed, with no server-side copy to restore from. Unlike `journeys.latitude` it is still *carried*, twice over: `SessionDraft` hydrates it and writes it back untouched, so re-saving an older brew keeps it, and the bundle carries it as `water_temp_c` since v4. A pour's temperature was never this column — `session_stages.waterTempC` is, and it is unaffected |
| `session_stages` | one pour each. `label` (which pour) and `note` (how it was poured) are two columns and cross as two — `note` as the desktop's `circling`, `label` as `brew_stages.label`, which the desktop grew on 2026-08-23. **`velocity`** (grams per second, 2026-08-30, `MIGRATION_14_15`) is the fourth measurement and is *not* derivable from the other three: `atSec` is when the pour starts, not how long it runs. `brew_stages.velocity` and bundle **v8** are its other two halves. **`endSec`** (2026-08-31, `MIGRATION_15_16`) is the fifth, and is when the pour *stopped* — not the next pour's `atSec`, which is separated from it by the drawdown. `brew_stages.end_seconds` and bundle **v9**; the Pour stages timer's single tap is what records it |
| `catalogue_items` | crawler cache |
| `news_items` | feed cache — four fields, no snippet column |
| `sessions.journeyId` | nullable, indexed — the café a brew was drunk at, which is what makes it a **cup** (§8.6c). **No foreign key, deliberately**: a cascade would delete a brew because the user tidied away a café, so deleting a journey orphans its cups back into ordinary brews (`coffee_can.db`'s `journey_id` copies that, unenforced for the same reason). **Sync carries it by name, not by id** (v4, 2026-08-23): the session goes out with a `journey` key holding the café's name and the café rows travel in `journeys.json`, because the two `journeys.id` sequences are as unrelated as the two `beans.id` ones |
| `journeys` | `+1`'s cafés: name, `location` (city), `address`, `barista`, `visitedAt`, note — plus `latitude`/`longitude`, retained but no longer read or written (§8.6b) |
| `journey_images` | `position`, `filePath`, `rotation` — the same contract as `bean_images`, in its own tree under `filesDir/journey_images/` |

**`journeys` is the first table whose shape is ours to choose**, and two
consequences follow that are easier to state than to rediscover. The sync
bundle **does** carry journeys, as of 2026-08-23 — but note *how*: rather than
inventing a bean-side column for them (which would be exactly the drift the
column-for-column rule exists to prevent), `coffee_can.db` grew matching
`journeys` / `journey_images` tables and a `brew_sessions.journey_id`, with no
desktop UI behind any of them. The desktop can hold a café and hand it back; it
still cannot show you one. A cup travels with its café's **name**, never its
id, for the same reason beans match by name. And `journey_images/`
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

**Step 3 fails on its own schedule, and the UI must offer a way back
(2026-09-03).** `AccountStore` is durable; Credential Manager's authorisation
state is not. When the silent mint stops working — Play services' One Tap
cooldown after a dismissed sheet is the usual mechanism, which is why the
symptom is "it worked when I signed in and stopped days later" — the profile
screen still reads *signed in* while every metered call is refused. Three
things follow, and all three are load-bearing:

- `GoogleAuth.reauthenticate()` uses **`GetSignInWithGoogleOption`**, not the
  `GetGoogleIdOption` everything else uses. The cooldown is attached to the One
  Tap option, so a retry built on it cannot escape it; the button flow has no
  such state. It is reached only from a deliberate tap, which is why it does
  not violate the "never open a chooser mid-operation" rule that keeps
  `idToken()` silent.
- Credential Manager's *cancellation* and *interrupted* exceptions map to
  `SignInRequired`, not `SignInUnavailable`. On the silent path there is no
  sheet for anyone to cancel, so a cancellation there is Play services
  declining by itself — and sorted as "unavailable" it surfaced as the scan
  card's generic "couldn't read that photo", sending the user to retake a
  photograph that was never the problem.
- The failed-scan card offers **Sign in** in place of Try again whenever the
  failure was the account, and re-sends the photo already taken rather than
  restarting at the camera.

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
  - **The capture intent asks for the back lens** (`media/PhotoSources.kt`,
    `RearCameraCapture`, 2026-09-03). Delegating capture means the camera app
    picks the lens, and camera apps reopen on the one their user last chose —
    so a phone whose owner last took a selfie opened the *front* camera on a
    bean bag. Three extras are sent because Android never standardised one:
    `android.intent.extras.CAMERA_FACING=0`,
    `android.intent.extras.LENS_FACING_BACK=1`,
    `android.intent.extra.USE_FRONT_CAMERA=false`. **They are hints.** A camera
    app that reads none of them behaves exactly as before; there is no
    stronger version short of declaring `CAMERA` and driving CameraX in-app,
    which is the trade the bullet above refuses.
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
| Rendering | Paparazzi, `app/src/test/…/screenshot/` | 77 goldens in `app/src/test/snapshots/images/` — real compiled Compose through layoutlib, no emulator |
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
| `screens.md` §9 | Profile has avatar / Name / Email / OSS-licence rows | **Partly restored 2026-08-23.** Avatar and Name are back on the product owner's instruction, overriding rule 60 (see `legal-accounts.md` rule 60 for the recorded override and its two disclosure costs). Email and the OSS-licence row remain removed — rules 60 and 103 respectively |
| `api.md` §2 | `/v1/ask` is the AI endpoint | The app calls `/v1/suggest` and `/v1/vision`; `/v1/ask` is forbidden to this client |
| `AUDIT.md` header | "Nothing here was compiled or run"; "the design is not scheme E" | The app compiles, installs and runs; the scheme E pass landed and type/shape now conform |
| `../../v1/README.md` | "33 simulated screenshots, 1080×2400"; "All four sections pass" | 45 files, mostly 360×800 Paparazzi output; one colour token and the copy check do not pass |

`scheme_e.py`'s `can_boy_news` is **three passes behind the shipped figure**
and should not be read as its description: its spread peaks at the fold and its
two leaves are unequal wedges (redrawn 2026-08-24), its `page` knob lifts and
curls the right leaf out of the plane (replaced by an in-plane turn 2026-08-28,
for want of headroom under the wordmark), and its arms are static (the right
one turns the page since 2026-08-29). `CanBoy.kt` is the drawing for this one
figure; nothing checks the two against each other.

`scheme_e.py`'s `+2.1_create_account` page should be **retired**: it draws
email/password sign-up, a sync data statement and a 13+ affirmation. Rule 60
removed email, the no-server-storage architecture removed sync, and rule 82
raises the age to 15.
