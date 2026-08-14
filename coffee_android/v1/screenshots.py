#!/usr/bin/env python3
"""Simulated screenshots of coffee_android v1, one PNG per page.

    python3 screenshots.py            # write screenshots/*.png
    python3 screenshots.py --svg      # keep the intermediate SVGs too

WHY THIS EXISTS. This checkout has no Android SDK, no Gradle and no wrapper,
so the app cannot be built or run here (plan/README.md, "Nothing here has been
compiled"). A screenshot of a running app is therefore not obtainable. What is
obtainable, and what this file produces, is a *simulation*: every frame below
is drawn from the real thing -- `app/src/main/java/app/coffeecan/**`'s layout,
`ui/theme/Theme.kt`'s tokens verbatim, and the exact user-facing strings as
they appear in the Kotlin. Nothing here is drawn from the design deck
(`plan/scheme_e.py`), which is the *target*; these frames are the *build*, and
the difference between the two is the point of the audit they accompany.

TREAT THEM AS EVIDENCE OF WHAT THE CODE SAYS, NOT PROOF THAT IT RUNS. A
Compose measure/layout pass is not reimplemented here -- text wrapping is
approximated, and a real device would differ in the last pixel of every line
box. What is faithful is the token, the copy, the control inventory and the
order of things down the page, which is what a design review reads a
screenshot for.

Geometry: 360x800dp, the deck's canvas, rasterised at 3x to 1080x2400 -- a
Pixel-class portrait screen. dp is the unit throughout; the scale is applied
once, at rasterisation.
"""
from __future__ import annotations

import datetime
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "screenshots"
W, H = 360, 800
SCALE = 3

# --------------------------------------------------------------- tokens ---
# Copied token for token out of ui/theme/Theme.kt. Do not "tidy" these: the
# whole value of the simulation is that a colour here is the colour the app
# compiles in, so a drifted hex would make the frame a nice picture of nothing.
C = dict(
    brand="#34C759",
    primary="#196D2E", onPrimary="#FFFFFF",
    primaryContainer="#C3EDC5", onPrimaryContainer="#002602",
    secondary="#556855",
    secondaryContainer="#E3F6E3", onSecondaryContainer="#233524",
    tertiaryContainer="#9FECD1",
    error="#84241A", errorContainer="#FEDED7",
    surface="#F2FAF2", onSurface="#1B241C", onSurfaceVariant="#515D51",
    card="#FFFFFF",
    surfaceContainerLow="#EAF5EA", surfaceContainer="#E0EFE1",
    surfaceContainerHigh="#D4E6D4", surfaceContainerHighest="#C9DCCA",
    surfaceVariant="#DCECDD",
    outline="#6D7B6D", outlineVariant="#C3D3C4",
    inverseSurface="#323C32", inverseOnSurface="#EAF3EA",
    vizSeries="#2B9343", vizInk="#515D51", vizGrid="#C3D3C4",
    vizTrack="#E0EFE1", vizBand="#B0E8B6", vizBandEdge="#43A756",
    vizDeviation="#506051", vizThumb="#152817",
)

# Theme.kt's `VizSequential` -- the heatmap ramp, light to dark. Five steps, so
# the top one is open-ended: ContributionCalendar buckets four brews and up into
# SEQ[4] rather than letting a heroic Sunday fall off the end of the list.
SEQ = ["#EBF2EC", "#AADBAF", "#65B972", "#299141", "#155E27"]

# Theme.kt's Shapes: card 24, sheet 32, thumb 16, field 16, extraSmall 8.
R_CARD, R_SHEET, R_THUMB, R_FIELD, R_XS = 24, 32, 16, 16, 8

FONT = "Fredoka, 'Trebuchet MS', sans-serif"
MONO = "'DejaVu Sans Mono', monospace"

# SchemeETypography, sp -> (size, weight). The deck's own table
# (wireframes.T through FREDOKA_STYLE's weight map), which is what Theme.kt now
# declares -- check_design.py diffs the two on every run.
TYPE = {
    "displaySmall": (36, 600),
    "headlineMedium": (28, 600), "headlineSmall": (22, 600),
    "titleLarge": (22, 600), "titleMedium": (16, 600), "titleSmall": (14, 600),
    "bodyLarge": (16, 400), "bodyMedium": (14, 400),
    "labelLarge": (14, 600), "labelMedium": (12, 600), "labelSmall": (11, 500),
}

GUTTER = 16          # theme/Theme.kt's `Gutter`, in every screen's Column
TOPBAR_H = 64
STATUS_H = 28
BAR_BOTTOM = STATUS_H + TOPBAR_H     # first free y under the app bar

AXES = ["Fruity", "Floral", "Tea-like", "Sweet", "Nutty/Cocoa", "Spices",
        "Roasted", "Cereal", "Green/Veg", "Sour", "Fermented"]
# components/RadarChart.kt ShortFlavorAxes -- passed at Home's 200dp chart and
# the brew form's 240dp preview, where the full names are the loudest thing on
# the card. The 260dp bean chart keeps the full set.
SHORT_AXES = ["Fruity", "Floral", "Tea", "Sweet", "Nutty", "Spices",
              "Roasted", "Cereal", "Green", "Sour", "Ferment"]


# ---------------------------------------------------------------- canvas ---
def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Canvas:
    """A page. Primitives only -- every widget below is built out of these."""

    def __init__(self, title: str):
        self.title = title
        self.parts: list[str] = []
        self.defs: list[str] = []
        self._clip = 0

    # -- primitives --
    def rect(self, x, y, w, h, fill, r=0, stroke=None, sw=1, opacity=None):
        a = f'x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"'
        if r:
            a += f' rx="{r}" ry="{r}"'
        a += f' fill="{fill}"'
        if stroke:
            a += f' stroke="{stroke}" stroke-width="{sw}"'
        if opacity is not None:
            a += f' opacity="{opacity}"'
        self.parts.append(f"<rect {a}/>")

    def circle(self, cx, cy, r, fill, stroke=None, sw=1, opacity=None):
        a = f'cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}"'
        if stroke:
            a += f' stroke="{stroke}" stroke-width="{sw}"'
        if opacity is not None:
            a += f' opacity="{opacity}"'
        self.parts.append(f"<circle {a}/>")

    def path(self, d, fill="none", stroke=None, sw=1.6, opacity=None, cap="round"):
        a = f'd="{d}" fill="{fill}"'
        if stroke:
            a += (f' stroke="{stroke}" stroke-width="{sw}"'
                  f' stroke-linecap="{cap}" stroke-linejoin="round"')
        if opacity is not None:
            a += f' opacity="{opacity}"'
        self.parts.append(f"<path {a}/>")

    def line(self, x1, y1, x2, y2, stroke, sw=1, opacity=None):
        a = (f'x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"'
             f' stroke="{stroke}" stroke-width="{sw}"')
        if opacity is not None:
            a += f' opacity="{opacity}"'
        self.parts.append(f"<line {a}/>")

    def text(self, x, y, s, style="bodyMedium", fill=None, anchor="start",
             size=None, weight=None, family=None, opacity=None, letter=None):
        sz, wt = TYPE[style]
        sz = size or sz
        wt = weight or wt
        fill = fill or C["onSurface"]
        a = (f'x="{x:.2f}" y="{y:.2f}" font-family="{family or FONT}"'
             f' font-size="{sz}" font-weight="{wt}" fill="{fill}"'
             f' text-anchor="{anchor}"')
        if letter is not None:
            a += f' letter-spacing="{letter}"'
        if opacity is not None:
            a += f' opacity="{opacity}"'
        self.parts.append(f"<text {a}>{esc(s)}</text>")

    # -- text helpers --
    @staticmethod
    def width(s: str, size: float) -> float:
        """Fredoka is a touch wide; 0.545em is the measured average advance."""
        return len(s) * size * 0.545

    def wrap(self, x, y, s, max_w, style="bodyMedium", fill=None, lh=None,
             anchor="start", size=None, limit=None):
        """Greedy wrap. Returns the y below the last line."""
        sz = size or TYPE[style][0]
        lh = lh or sz * 1.34
        words, line, lines = s.split(" "), "", []
        for word in words:
            trial = f"{line} {word}".strip()
            if self.width(trial, sz) > max_w and line:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        if limit:
            lines = lines[:limit]
        for i, ln in enumerate(lines):
            self.text(x, y + i * lh, ln, style, fill, anchor, size=size)
        return y + (len(lines) - 1) * lh

    def render(self) -> str:
        defs = "\n".join(self.defs)
        body = "\n".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * SCALE}" '
            f'height="{H * SCALE}" viewBox="0 0 {W} {H}">'
            f"<title>{esc(self.title)}</title><defs>{defs}</defs>"
            f'<rect width="{W}" height="{H}" fill="{C["surface"]}"/>'
            f"{body}</svg>"
        )


# ----------------------------------------------------------- app chrome ---
def status_bar(c: Canvas, ink=None):
    """Edge-to-edge: MainActivity calls enableEdgeToEdge(), so the app's own
    background runs under the system bar and the icons sit on it."""
    ink = ink or C["onSurface"]
    c.text(20, 18, "9:41", "labelSmall", ink, size=11, weight=600)
    for i, h in enumerate((3, 5, 7, 9)):          # signal
        c.rect(292 + i * 5, 17 - h, 3, h, ink, 1)
    c.rect(316, 9, 16, 9, "none", 2, stroke=ink, sw=1.2)
    c.rect(318, 11, 10, 5, ink, 1)
    c.rect(333, 12, 1.6, 3, ink, 0.8)


def gesture_bar(c: Canvas):
    c.rect(W / 2 - 54, H - 12, 108, 4, C["onSurface"], 2, opacity=0.35)


def top_bar(c: Canvas, title, back=False, title_style="titleMedium",
            actions=None, action_text=None):
    """Material3 TopAppBar, containerColor = background (every screen sets it).

    `actions` is a list of glyph names drawn right-to-left from the edge;
    `action_text` is a worded action (Home's "Add bean", Profile's "Log out").

    There is no "person" glyph in this vocabulary any more: Home's profile
    icon was the push model's door to +2, and +2 is a swipe now (ui/Axis.kt).
    A glyph the app no longer draws does not belong in the simulator either.
    """
    y = STATUS_H
    if back:
        c.path(f"M28 {y + 32} h16 M34 {y + 26} l-6 6 l6 6",
               stroke=C["onSurface"], sw=1.8)
        c.text(56, y + 37, title, title_style)
    else:
        c.text(20, y + 38, title, title_style)

    x = W - 20
    for glyph in reversed(actions or []):
        x -= 24
        if glyph == "delete":
            c.path(f"M{x + 4} {y + 25} h16 M{x + 7} {y + 25} v14 h10 v-14"
                   f" M{x + 9} {y + 22} h6",
                   stroke=C["onSurface"], sw=1.7)
        x -= 8
    if action_text:
        # A TextButton in the actions slot: primary ink, 14sp labelLarge.
        c.text(W - 20 - (24 if actions else 0) - 8, y + 37, action_text,
               "labelLarge", C["primary"], "end")
    # components/TopBarDivider.kt -- every screen's topBar slot is a Column of
    # the bar and this rule. The bar is painted in `surface`, so without it the
    # title reads as the page's first line rather than as chrome.
    c.line(0, y + TOPBAR_H, W, y + TOPBAR_H, C["outlineVariant"], 1)
    return y + TOPBAR_H


def section(c: Canvas, y, text, action=None, caption=None):
    """SectionHeader from ui/screens/AiDisclosureScreen.kt (shared).
    padding top 12, bottom 8; titleSmall on the left, and on the right either a
    TextButton (`action`) or a muted note (`caption`, Home's "Average across N
    sessions"). Returns the y where the section's content starts."""
    c.text(GUTTER, y + 12 + 14, text, "titleSmall")
    if action:
        c.text(W - GUTTER, y + 12 + 14, action, "labelLarge", C["primary"], "end")
    elif caption:
        c.text(W - GUTTER, y + 12 + 14, caption, "labelSmall",
               C["onSurfaceVariant"], "end")
    return y + 12 + 20 + 8


def card(c: Canvas, y, h, x=GUTTER, w=None, fill=None, r=R_CARD):
    w = w or (W - 2 * GUTTER)
    c.rect(x, y, w, h, fill or C["card"], r)
    return y + h


def divider(c: Canvas, y, x=GUTTER, w=None):
    w = w or (W - 2 * GUTTER)
    c.line(x, y, x + w, y, C["outlineVariant"], 1)


def button(c: Canvas, y, label, x=GUTTER, w=None, kind="filled", h=40):
    """M3 Button: pill (shapes full), 40dp tall, labelLarge."""
    w = w or (W - 2 * GUTTER)
    if kind == "filled":
        c.rect(x, y, w, h, C["primary"], h / 2)
        ink = C["onPrimary"]
    elif kind == "outlined":
        c.rect(x, y, w, h, "none", h / 2, stroke=C["outline"])
        ink = C["primary"]
    else:                                   # text
        ink = C["primary"]
    c.text(x + w / 2, y + h / 2 + 5, label, "labelLarge", ink, "middle")
    return y + h


def field(c: Canvas, y, label, value="", x=GUTTER, w=None, placeholder=None,
          h=56, multiline=False):
    """M3 OutlinedTextField: 56dp, 16dp corner (shapes.small = FieldCorner),
    label notched into the border when the field holds a value."""
    w = w or (W - 2 * GUTTER)
    filled = bool(value) or bool(placeholder)
    c.rect(x, y, w, h, "none", R_FIELD, stroke=C["outline"], sw=1)
    if filled:
        lw = Canvas.width(label, 12) + 8
        c.rect(x + 12, y - 6, lw, 12, C["surface"])
        c.text(x + 16, y + 4, label, "labelMedium", C["onSurfaceVariant"], size=12)
        c.text(x + 16, y + h / 2 + 5, value or placeholder, "bodyLarge",
               C["onSurface"] if value else C["outline"])
    else:
        c.text(x + 16, y + h / 2 + 5, label, "bodyLarge", C["onSurfaceVariant"])
    return y + h


def capsule(c: Canvas, y, label, value="", x=GUTTER, w=None, placeholder="—"):
    """components/Fields.kt CapsuleField: a 12sp label, 4dp of air, then a 30dp
    `surfaceContainer` pill holding the value at 12dp of inset. 46dp all in
    against the outlined box's 56, and used two-up, so a pair of them is a
    third of the height of two boxes."""
    w = w or (W - 2 * GUTTER)
    c.text(x, y + 11, label, "labelMedium", C["onSurfaceVariant"], letter=0.4)
    c.rect(x, y + 16, w, 30, C["surfaceContainer"], 15)
    c.text(x + 12, y + 36, value or placeholder, "bodyLarge",
           C["onSurface"] if value else C["outline"])
    return y + 46


def capsule_pair(c: Canvas, y, left, right, x=GUTTER, w=None, gap=12):
    """FieldPair: two capsules, equal halves, one 12dp gutter. `left`/`right`
    are (label, value) or None for a hanging half-row."""
    w = w or (W - 2 * GUTTER)
    half = (w - gap) / 2
    for i, pair in enumerate((left, right)):
        if pair is None:
            continue
        capsule(c, y, pair[0], pair[1], x=x + i * (half + gap), w=half)
    return y + 46


def choice_field(c: Canvas, y, label, value, x=GUTTER, w=None):
    """ChoiceField = OutlinedTextField + ExposedDropdownMenu trailing icon."""
    w = w or (W - 2 * GUTTER)
    field(c, y, label, value, x, w)
    c.path(f"M{x + w - 28} {y + 25} l6 6 l6 -6", stroke=C["onSurfaceVariant"], sw=1.7)
    return y + 56


def slider(c: Canvas, y, x, w, value, lo=0.0, hi=5.0, unset=False):
    """M3 Slider, 4dp track, 20dp thumb, steps drawn as tick dots."""
    t = 0.0 if unset else (value - lo) / (hi - lo)
    c.rect(x, y - 2, w, 4, C["surfaceContainerHigh"], 2)
    if not unset:
        c.rect(x, y - 2, w * t, 4, C["primary"], 2)
    c.circle(x + w * t, y, 10, C["primary"] if not unset else C["outline"])


def switch(c: Canvas, x, cy, on):
    """M3 Switch, 52x32 track."""
    c.rect(x, cy - 16, 52, 32, C["primary"] if on else C["surfaceContainerHighest"],
           16, stroke=None if on else C["outline"])
    r, cx = (12, x + 36) if on else (8, x + 16)
    c.circle(cx, cy, r, C["onPrimary"] if on else C["outline"])
    if on:
        c.path(f"M{cx - 5} {cy} l3.5 3.5 l6 -7", stroke=C["primary"], sw=2)


def chip(c: Canvas, x, y, label, selected=False, h=32):
    """`shape = ChipShape` at every call site: the deck's chip is a pill, and
    M3 would otherwise take `shapes.small` (= the 16dp field corner)."""
    w = Canvas.width(label, 14) + 28
    c.rect(x, y, w, h, C["secondaryContainer"] if selected else "none", h / 2,
           stroke=None if selected else C["outline"])
    c.text(x + w / 2, y + h / 2 + 5, label, "labelLarge",
           C["onSecondaryContainer"] if selected else C["onSurfaceVariant"], "middle")
    return x + w + 8


def fab(c: Canvas, cy=H - 16 - 28 - 16):
    """M3 FAB, 56dp. Both the shape and the fill are passed explicitly at each
    call site, because both M3 defaults are wrong against this deck: the fill
    would be `primaryContainer` (a pale mint blob where the deck draws a solid
    dark-green disc), and the shape resolves from `shapes.large`, which this
    theme overrides to the deck's 24dp card radius -- giving a rounded square
    where the deck draws a circle."""
    cx = W - 16 - 28
    c.circle(cx, cy, 28, C["primary"])
    c.path(f"M{cx - 11} {cy} h22 M{cx} {cy - 11} v22",
           stroke=C["onPrimary"], sw=2.4)


def scrim(c: Canvas):
    """`colorScheme.scrim` at M3's 0.32. The token is now PURE_GREEN's
    green-black #06140A rather than the framework's neutral default, so a sheet
    dims the page in palette."""
    c.rect(0, 0, W, H, "#06140A", opacity=0.32)


def sheet(c: Canvas, top):
    """ModalBottomSheet: shapes.extraLarge (32) on the top corners, drag handle."""
    c.rect(0, top, W, H - top, C["surfaceContainerLow"], R_SHEET)
    c.rect(0, top + R_SHEET, W, H - top - R_SHEET, C["surfaceContainerLow"])
    c.rect(W / 2 - 16, top + 12, 32, 4, C["onSurfaceVariant"], 2, opacity=0.4)
    return top + 34


def dialog(c: Canvas, top, h):
    """M3 AlertDialog: shapes.extraLarge (32), surfaceContainerHigh."""
    c.rect(28, top, W - 56, h, C["surfaceContainerHigh"], R_SHEET)
    return top


def snackbar(c: Canvas, label, y=H - 92):
    c.rect(GUTTER, y, W - 2 * GUTTER, 48, C["inverseSurface"], R_FIELD)
    c.text(GUTTER + 16, y + 29, label, "bodyMedium", C["inverseOnSurface"])


# ---------------------------------------------------------- app widgets ---
_VECTORS: dict[str, tuple[float, list[tuple[str, dict]]]] = {}


def _vector(name: str):
    """Read one VectorDrawable out of the app's own res/drawable.

    THE POINT IS THAT THIS IS NOT A COPY. ui/components/Illustrations.kt draws
    these four drawables and nothing else, so parsing the shipped XML is the
    one way to be sure the simulation cannot show a figure the build does not
    have -- the failure mode this whole file exists to avoid. It also means
    the art here changes if and only if the resource does.

    Returns (viewport size, [(pathData, attrs)]). The drawables are flat --
    no <group>, because their transforms were baked into absolute coordinates
    when they were generated -- so there is no transform stack to walk.
    """
    if name not in _VECTORS:
        ns = "{http://schemas.android.com/apk/res/android}"
        root = ET.parse(HERE / "app/src/main/res/drawable" / f"{name}.xml").getroot()
        assert root.tag == "vector" and not root.findall("group"), name
        size = float(root.get(ns + "viewportWidth"))
        paths = [(p.get(ns + "pathData"),
                  {k.replace(ns, ""): v for k, v in p.attrib.items()})
                 for p in root.findall("path")]
        _VECTORS[name] = (size, paths)
    return _VECTORS[name]


def illustration(c: Canvas, name, cx, cy, size, disc=True):
    """One of Illustrations.kt's figures, centred on (cx, cy).

    The composable is a Box painting `Brand` as a circle with the vector drawn
    over it at the same size, which is exactly what this emits."""
    box, paths = _vector(name)
    s = size / box
    if disc:
        c.circle(cx, cy, size / 2, C["brand"])
    c.parts.append(f'<g transform="translate({cx - size / 2:.2f} '
                   f'{cy - size / 2:.2f}) scale({s:.5f})">')
    for d, a in paths:
        at = f'd="{d}" fill="{a.get("fillColor", "none")}"'
        if a.get("strokeColor"):
            at += (f' stroke="{a["strokeColor"]}" stroke-width="{a["strokeWidth"]}"'
                   f' stroke-linecap="{a.get("strokeLineCap", "butt")}"'
                   f' stroke-linejoin="{a.get("strokeLineJoin", "miter")}"')
        c.parts.append(f"<path {at}/>")
    c.parts.append("</g>")


def bag_tile(c: Canvas, x, y, size, code):
    """ui/components/BagTile.kt, glyph for glyph: gusseted pouch, crimped top
    seal with pleat creases, one-way valve ring, white line only, on the
    seeded gradient. The two-letter code is what `origin.take(2)` produces --
    which is why Guatemala reads GU here and not GT."""
    label = (code or "??")[:2].upper()
    seed = sum(ord(ch) for ch in (code or "??"))
    top = ["#DCEFDD", "#D2ECD8", "#E3F3E1", "#CDE9D2"][seed % 4]
    bot = ["#4C9A5B", "#3E8B4C", "#5AAE68", "#347A44"][(seed // 3) % 4]
    gid = f"bag{abs(seed)}{int(x)}{int(y)}"
    c.defs.append(
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="0.9" y2="1">'
        f'<stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bot}"/></linearGradient>'
    )
    c.rect(x, y, size, size, f"url(#{gid})", 12)
    s = size / 100 * 1.3
    cx, cy = x + size / 2, y + size / 2

    def p(px, py):
        return f"{cx + px * s:.2f} {cy + py * s:.2f}"

    c.path(
        f"M{p(-24, -30)} Q{p(-24, -36)} {p(-18, -36)} L{p(18, -36)}"
        f" Q{p(24, -36)} {p(24, -30)} L{p(26, 26)} Q{p(26, 34)} {p(18, 34)}"
        f" L{p(-18, 34)} Q{p(-26, 34)} {p(-26, 26)} Z",
        stroke="#FFFFFF", sw=4.4 * s)
    c.path(f"M{p(-19, -36)} Q{p(-19, -42)} {p(-13, -42)} L{p(13, -42)}"
           f" Q{p(19, -42)} {p(19, -36)}", stroke="#FFFFFF", sw=4.4 * s)
    for px in (-10, 0, 10):
        c.path(f"M{p(px, -41)} L{p(px + 3, -37)}", stroke="#FFFFFF", sw=2.4 * s)
    c.circle(cx + 10 * s, cy - 20 * s, 6 * s, "none", stroke="#FFFFFF", sw=3 * s)
    c.text(cx, cy + 10 * s, label, "titleMedium", "#FFFFFF", "middle",
           size=30 * s, weight=700)


def radar(c: Canvas, cx, cy, size, values, labels=None):
    """ui/components/RadarChart.kt. radius = min(cx,cy)*0.66 of the composable
    box; the net rises to 0.85 alpha and the polygon disappears entirely when
    every axis is null -- absence drawn as absence, not as a zero-area shape."""
    empty = values is None or all(v is None for v in values)
    labels = labels or AXES
    radius = size / 2 * 0.66
    n = len(labels)
    step = 2 * math.pi / n
    alpha = 0.85 if empty else 0.35

    def pt(i, r):
        a = -math.pi / 2 + step * i
        return cx + r * math.cos(a), cy + r * math.sin(a)

    for ring in range(1, 6):
        r = radius * ring / 5
        d = "M" + " L".join(f"{px:.2f} {py:.2f}" for px, py in
                            (pt(i, r) for i in range(n))) + " Z"
        c.path(d, stroke=C["vizGrid"], sw=0.7, opacity=alpha)
    for i in range(n):
        px, py = pt(i, radius)
        c.line(cx, cy, px, py, C["vizGrid"], 0.7, opacity=alpha)

    if not empty:
        pts = [pt(i, radius * min(max(v / 5.0, 0), 1))
               for i, v in enumerate(values) if v is not None]
        if len(pts) >= 3:
            d = "M" + " L".join(f"{px:.2f} {py:.2f}" for px, py in pts) + " Z"
            c.path(d, fill=C["vizSeries"], opacity=0.18)
            c.path(d, stroke=C["vizSeries"], sw=1.6)

    ink = C["vizGrid"] if empty else C["vizInk"]
    for i, label in enumerate(labels):
        ax, ay = pt(i, radius + 10)
        anchor = "middle"
        if ax < cx - 4:
            anchor = "end"
        elif ax > cx + 4:
            anchor = "start"
        c.text(ax, ay + 3, label, "labelSmall", ink, anchor, size=8)


def heatmap(c: Canvas, x, y, w, days, today, weeks=21):
    """ui/components/ContributionCalendar.kt, drawn in the card's own
    coordinates: the component takes the whole 140dp card interior and insets
    itself, so (x, y) here is the card's top-left, not the grid's.

    Every number below is the composable's: a 12dp inset, a 30dp weekday
    gutter, the grid 32dp down, an 11dp cell on a 2dp gap, and the legend
    baseline 16dp under the seventh row. `weeks` is clamped to what the width
    actually fits, which at 360dp is all 21 of them.

    The month row is derived from the dates on screen rather than hard-coded
    the way the deck's `wireframes.heatmap` hard-codes May/Jun/Jul/Aug, so it
    shows every month the grid actually spans.
    """
    cell, gap, inset = 11, 2, 12
    pitch = cell + gap
    grid_left = x + inset + 30
    grid_top = y + 32
    right = x + w - inset
    cols = min(weeks, int((right - grid_left + gap) / pitch))
    start = (today - datetime.timedelta(days=today.weekday())
             - datetime.timedelta(weeks=cols - 1))

    last_name, last_x = None, -1e9
    for col in range(cols):
        name = (start + datetime.timedelta(weeks=col)).strftime("%b")
        if name == last_name:
            continue
        last_name = name
        lx, tw = grid_left + col * pitch, Canvas.width(name, 11)
        if lx < last_x or lx + tw > right:
            continue
        last_x = lx + tw + 4
        c.text(lx, grid_top - 4, name, "labelSmall", C["vizInk"])

    for row, name in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
        c.text(grid_left - 8, grid_top + row * pitch + cell - 1, name,
               "labelSmall", C["vizInk"], "end")

    for col in range(cols):
        for row in range(7):
            day = start + datetime.timedelta(days=col * 7 + row)
            # Future days in the current week are left blank: the palest step
            # is a claim that nothing happened, and tomorrow has not had the
            # chance to.
            if day > today:
                continue
            c.rect(grid_left + col * pitch, grid_top + row * pitch, cell, cell,
                   SEQ[min(days.get(day, 0), 4)], 2)

    ly = grid_top + 7 * pitch + 16
    c.text(right - 12, ly, "More", "labelSmall", C["vizInk"], "end")
    sr = right - 12 - 34
    for step in range(4, -1, -1):
        c.rect(sr - cell, ly - 9, cell, cell, SEQ[step], 2)
        sr -= pitch
    c.text(sr - 4, ly, "Less", "labelSmall", C["vizInk"], "end")


def extraction_bar(c: Canvas, x, y, w, value, h=12):
    """ui/components/ExtractionBar.kt -- an inverted meter: chroma means
    on-target, so the saturated band is the middle third and both ends are
    drab.

    The canvas is 12dp taller than the track (the thumb and the centre tick
    overshoot it), and the three zone words sit under it in a weighted Row with
    the active one emphasised -- the same three words the contentDescription
    reads out. `None` draws the track with no marker and emphasises nothing."""
    top = y + 6
    mid, third = x + w / 2, w / 3
    c.rect(x, top, w, h, C["vizTrack"], h / 2)
    c.rect(x + third, top, third, h, C["vizBand"])
    for bx in (x + third, x + 2 * third):
        c.line(bx, top, bx, top + h, C["vizBandEdge"], 1.5)
    c.line(mid, top - 3, mid, top + h + 3, C["vizBandEdge"], 1.5)
    if value is not None:
        v = min(max(value, -1), 1)
        vx = mid + v * (w / 2)
        c.rect(min(mid, vx), top, abs(vx - mid), h, C["vizDeviation"])
        c.rect(vx - 3, top - 5, 6, h + 10, C["surface"], 3)
        c.rect(vx - 1.5, top - 3.5, 3, h + 7, C["vizThumb"], 1.5)
    zones = ((x, "start", "Under", value is not None and value < -1 / 3),
             (mid, "middle", "Well extracted",
              value is not None and -1 / 3 <= value <= 1 / 3),
             (x + w, "end", "Over", value is not None and value > 1 / 3))
    for lx, anchor, label, hot in zones:
        c.text(lx, y + h + 26, label, "labelSmall",
               C["onSurface"] if hot else C["onSurfaceVariant"], anchor,
               weight=600 if hot else None)
    return y + h + 32


def google_button(c: Canvas, y, label="Sign in with Google"):
    """ProfileScreen.GoogleSignInButton -- 240x48, #FFFFFF fill, #747775
    stroke, #1F1F1F ink, Google's own typeface. The one control the design
    system does not restyle."""
    x, w, h = (W - 240) / 2, 240, 48
    c.rect(x, y, w, h, "#FFFFFF", 24, stroke="#747775")
    g = x + 30
    cy = y + h / 2
    for col, d in (("#EA4335", "M{0} {1} a9 9 0 0 1 15.6 -5.2"),
                   ("#4285F4", "M{0} {1} a9 9 0 0 1 -6.4 12.8")):
        c.path(d.format(f"{g - 9:.1f}", f"{cy:.1f}"), stroke=col, sw=3)
    c.path(f"M{g - 9} {cy} a9 9 0 0 0 6 8.5", stroke="#34A853", sw=3)
    c.path(f"M{g - 1} {cy - 0.5} h10", stroke="#4285F4", sw=3)
    c.text(x + w / 2 + 14, cy + 5, label, "labelLarge", "#1F1F1F", "middle",
           size=15, family="'Liberation Sans', Arial, sans-serif")
    return y + h



def spinner(c: Canvas, cx, cy, r=9, sw=2):
    c.circle(cx, cy, r, "none", stroke=C["primary"], sw=sw, opacity=0.25)
    c.path(f"M{cx} {cy - r} a{r} {r} 0 0 1 {r} {r}", stroke=C["primary"], sw=sw)


# ------------------------------------------------------------ page data ---
# One consistent fixture across every frame, so the same log is visible from
# Home, from the bean, and from the session list -- the way it would be on a
# real phone. Brew counts, session rows and the Home average agree.
# (name, roaster, origin, brews, process, roast day). The shelf card's second
# line is now process + roast date -- BeanEntity.shelfMeta() -- so the sample
# carries both; the roaster is still here because the card falls back to it and
# +1.1's picker still shows it.
BEANS = [
    ("Ethiopia Guji Natural", "Terres de Café", "Ethiopia", 4, "Natural", "28 Jul"),
    ("Colombia Huila Washed", "Café Lomi", "Colombia", 2, "Washed", "20 Jul"),
    ("Kenya Nyeri AB", "Belleville", "Kenya", 0, "Washed", "02 Aug"),
    ("Guatemala Huehue", "Coutume", "Guatemala", 1, "Washed", "15 Jul"),
]

MY_FLAVOR = [3.7, 2.8, 2.0, 3.9, 2.6, 1.5, 1.9, 1.7, 0.7, 2.5, 2.3]
BEAN_FLAVOR = [4.2, 3.1, 2.4, 4.0, 1.8, 1.2, 1.5, 1.0, 0.5, 2.2, 3.0]
SESSION_FLAVOR = [4.5, 3.0, 2.5, 4.0, 1.5, 1.0, 1.5, 1.0, 0.5, 2.0, 3.5]

SESSIONS = [
    ("Ethiopia Guji Natural", "Hario V60 · 15.0 g · 4.5", "11 Aug"),
    ("Colombia Huila Washed", "Kalita Wave · 18.0 g · 3.5", "09 Aug"),
    ("Ethiopia Guji Natural", "Hario V60 · 15.0 g · 4.0", "07 Aug"),
    ("Guatemala Huehue", "Chemex · 30.0 g · 3.0", "04 Aug"),
    ("Ethiopia Guji Natural", "Origami Dripper · 14.0 g · 4.5", "02 Aug"),
    ("Colombia Huila Washed", "Hario V60 · 16.0 g", "30 Jul"),
    ("Ethiopia Guji Natural", "Hario V60 · 15.0 g · 3.5", "28 Jul"),
]

# Home's Brewing-activity grid, from the same log. `today` has to be fixed or
# every re-render would move the grid under the deck page it is compared with.
#
# THE CARD IS SPARSE ON PURPOSE. The deck fills its heatmap with
# `random.seed(7)` noise at about 48% density; this one shows the seven
# sessions above, one per day, because that is the log the rest of the frame
# is drawn from -- the same log the "Average across 7 sessions" caption counts
# and the same seven rows +1_sessions lists. Densifying it would make the frame
# agree with the deck and disagree with itself.
TODAY = datetime.date(2026, 8, 14)
BREW_DAYS: dict[datetime.date, int] = {}
for _row in SESSIONS:
    _day = datetime.datetime.strptime(f"{_row[2]} 2026", "%d %b %Y").date()
    BREW_DAYS[_day] = BREW_DAYS.get(_day, 0) + 1

BEAN = dict(
    name="Ethiopia Guji Natural", origin="Ethiopia", variety="Heirloom",
    altitude="1 950 m", roaster="Terres de Café", producer="Buku Abel",
    process="Natural (Dry) Process", roast="28 Jul 2026",
    note="Blueberry, jasmine, syrupy. Bought at the\nMarché des Enfants Rouges.",
)


# ---------------------------------------------------------------- pages ---
def home():
    """00 -- HomeScreen.kt, populated.

    Three cards of the four on the shelf, then a "See all N beans" row: the
    list is capped so both summary panes clear the fold. Cards are 72dp (a 64dp
    tile with 4dp of air, not 12), the second line is process + roast date at
    the deck's own 11sp override, the name is its 14sp one, and the brew count
    is a filled pill rather than a coloured word.

    Under the list, the two panes coffee-can's desktop shows side by side:
    the 140dp Brewing-activity calendar and the 178dp My-flavor radar.

    THE BAR HAS ONE ACTION NOW. The profile icon is gone and so is the
    "Every brew you've logged" row that used to close the scroll: both were
    doors push navigation needed, and +1 and +2 are a swipe right from here
    (ui/Axis.kt). Still missing against the deck: the brand mark in the bar,
    and "Add bean" itself, which the deck's 00 page does not draw but its own
    axis note requires (see HomeScreen.kt)."""
    c = Canvas("00 Home")
    status_bar(c)
    y = top_bar(c, "Coffee Can", action_text="Add bean")
    y = section(c, y, "Your beans", action="Search")

    for name, roaster, origin, brews, process, roast in BEANS[:3]:
        card(c, y, 72)
        bag_tile(c, GUTTER + 12, y + 4, 64, origin[:2])
        tx = GUTTER + 12 + 64 + 14
        # 14 and 11, not titleMedium's 16 and bodyMedium's 14: HomeScreen
        # overrides both sizes at these two call sites, the way the deck does.
        c.text(tx, y + 26, name, "titleMedium", size=14)
        c.text(tx, y + 44, process + " · Roasted " + roast, "bodyMedium",
               C["onSurfaceVariant"], size=11)
        label = ("No brews yet" if not brews else
                 ("1 brew" if brews == 1 else f"{brews} brews"))
        pw = Canvas.width(label, 11) + 16
        c.rect(tx, y + 50, pw, 16, C["primaryContainer"] if brews
               else C["surfaceContainer"], 4)
        c.text(tx + 8, y + 62, label, "labelSmall",
               C["onPrimaryContainer"] if brews else C["onSurfaceVariant"])
        c.path(f"M{W - GUTTER - 24} {y + 31} l5 5 l-5 5", stroke=C["outline"], sw=1.6)
        y += 78
    y -= 6                      # the 6dp gap sits between cards, not after the last

    # A Text with 8dp of padding above and below its 20dp line box.
    c.text(W - GUTTER, y + 23, f"See all {len(BEANS)} beans", "labelLarge",
           C["primary"], "end")
    y += 36

    # No spacer before either heading: SectionHeader's own 12dp of top padding
    # is the gap, and a Spacer on top of it is what used to push the flavour
    # card off the fold.
    y = section(c, y, "Brewing activity")
    card(c, y, 140)
    heatmap(c, GUTTER, y, W - 2 * GUTTER, BREW_DAYS, TODAY)
    y += 140

    y = section(c, y, "My flavor",
                caption=f"Average across {len(SESSIONS)} sessions")
    card(c, y, 178)
    # `size` is the composable's box; RadarChart's own radius is half of it
    # times 0.66, so 178 draws r=58.7 against the deck's r=60.
    radar(c, W / 2, y + 89, 178, MY_FLAVOR, labels=SHORT_AXES)
    fab(c)
    gesture_bar(c)
    return c


def home_empty():
    """00_home_empty -- HomeScreen.HomeEmpty. Centred in the content area,
    40dp side padding, opening with the mark at 100dp (CoffeeCanLogo, the
    shipped icon.svg's own lettering on the Brand disc)."""
    c = Canvas("00 Home, first run")
    status_bar(c)
    top_bar(c, "Coffee Can", action_text="Add bean")
    # Arrangement.Center over a taller stack than before: the 100dp mark and
    # its 24dp spacer push the headline's baseline down by half of 124.
    cy = (BAR_BOTTOM + H) / 2 - 40 + 62
    illustration(c, "ic_brand_lockup", W / 2, cy - 100, 100)
    c.text(W / 2, cy, "No beans yet", "headlineMedium", anchor="middle")
    c.wrap(W / 2, cy + 34, "Add the bag you're brewing this week and start "
           "keeping the log.", W - 80, "bodyLarge", C["onSurfaceVariant"],
           anchor="middle")
    button(c, cy + 92, "Add your first bean", x=88, w=184)
    fab(c)
    gesture_bar(c)
    return c


def bean_new():
    """0.1 -- BeanDetailScreen with beanId = null.

    The scan card is the hero here and a one-line row on a saved bean; the
    header block and the Sessions section are both absent because there is no
    bean yet. Save is disabled until a name exists."""
    c = Canvas("0.1 New bean")
    status_bar(c)
    y = top_bar(c, "New bean")

    # 138 -> 254: every line in the card moves down by the mascot's 108dp plus
    # its 8dp spacer. MascotCamera is decoration only; "Scan a label" is still
    # the control, which is where this deliberately parts company with the
    # deck (there the figure is the tap target, labelled "Click me to scan").
    card(c, y, 254, fill=C["secondaryContainer"])
    illustration(c, "ic_mascot_camera", W / 2, y + 70, 108)
    c.text(W / 2, y + 150, "Scan the bag", "titleMedium",
           C["onSecondaryContainer"], "middle")
    c.text(W / 2, y + 170, "Point your camera at the label to fill this in",
           "labelSmall", C["onSecondaryContainer"], "middle")
    button(c, y + 184, "Scan a label", x=W / 2 - 66, w=132)
    c.text(W / 2, y + 242, "or enter it by hand below", "labelMedium",
           C["onSecondaryContainer"], "middle")
    y += 254 + 16

    # One outlined box for the one required field, then the capsule grid: the
    # deck's split by role, and the reason the whole form now fits above the
    # fold with the radar card under it.
    y = field(c, y, "Bean name") + 14
    y = capsule_pair(c, y, ("Origin", ""), ("Variety", "")) + 10
    y = capsule_pair(c, y, ("Altitude", ""), ("Roaster", "")) + 10
    y = capsule_pair(c, y, ("Producer", ""), ("Process", "")) + 10
    capsule(c, y, "Roast date", "", w=(W - 2 * GUTTER - 12) / 2,
            placeholder="Not set")
    y += 46 + 14
    y = field(c, y, "Note", h=96) + 24
    y = section(c, y, "Radar", action="Set manually")
    card(c, y, 300)
    radar(c, W / 2, y + 140, 260, None)
    gesture_bar(c)
    return c


def bean_detail():
    """0.2 -- BeanDetailScreen for a saved bean, above the fold."""
    c = Canvas("0.2 Bean detail")
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True, actions=["delete"])

    bag_tile(c, GUTTER, y, 72, "Et")
    tx = GUTTER + 72 + 14
    c.wrap(tx, y + 24, f'{BEAN["origin"]} · {BEAN["process"]} · '
           f'Roasted {BEAN["roast"]}', W - tx - GUTTER, "bodyMedium",
           C["onSurfaceVariant"])
    c.text(tx, y + 62, "4 brews", "labelSmall", C["primary"])
    y += 72 + 16

    card(c, y, 56, fill=C["secondaryContainer"])
    c.text(GUTTER + 16, y + 33, "Scan the label to update these fields",
           "bodyMedium", C["onSecondaryContainer"])
    c.text(W - GUTTER - 16, y + 33, "Scan", "labelLarge", C["primary"], "end")
    y += 56 + 16

    y = field(c, y, "Bean name", BEAN["name"]) + 14
    y = capsule_pair(c, y, ("Origin", BEAN["origin"]),
                     ("Variety", BEAN["variety"])) + 10
    y = capsule_pair(c, y, ("Altitude", BEAN["altitude"]),
                     ("Roaster", BEAN["roaster"])) + 10
    # A capsule ellipsises the same way the box did -- the stored process is
    # longer than half a row.
    y = capsule_pair(c, y, ("Producer", BEAN["producer"]),
                     ("Process", BEAN["process"][:13] + "…")) + 10
    half = (W - 2 * GUTTER - 12) / 2
    capsule(c, y, "Roast date", BEAN["roast"], w=half)
    # Clear sits under the capsule, inside RoastDateField's own Column, so it
    # only exists once there is a date to clear and it grows the row rather
    # than crowding the half-width capsule with two trailing buttons.
    c.text(GUTTER, y + 62, "Clear", "labelMedium", C["primary"])
    y += 66 + 14
    y = field(c, y, "Note", BEAN["note"].split("\n")[0], h=96)
    gesture_bar(c)
    return c


def bean_detail_lower():
    """0.2b -- the same screen scrolled past the fold: radar, its caption,
    the sessions list and the save button."""
    c = Canvas("0.2b Bean detail, lower")
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True, actions=["delete"])

    y = field(c, y, "Note", BEAN["note"].split("\n")[0], h=96) + 24
    y = section(c, y, "Radar", action="Set manually")
    card(c, y, 300)
    radar(c, W / 2, y + 140, 260, BEAN_FLAVOR)
    c.text(W / 2, y + 288, "Averaged from 4 sessions · fixed axis order, 0–5 scale",
           "labelSmall", C["onSurfaceVariant"], "middle", size=9)
    y += 300 + 24

    y = section(c, y, "Sessions", action="New brew")
    for name, meta, day in [s for s in SESSIONS if s[0] == BEAN["name"]][:3]:
        c.text(GUTTER, y + 22, f"{day} 2026", "titleMedium")
        c.text(GUTTER, y + 40, meta, "bodyMedium", C["onSurfaceVariant"])
        divider(c, y + 52)
        y += 52
    y += 24
    button(c, y, "Save changes")
    gesture_bar(c)
    return c


def bean_detail_lower_empty():
    """0.2b_empty -- a saved bean with nothing brewed against it yet.

    A separate frame and not a variant note, because it is where the pour-over
    mascot runs at 132dp: the same figure and the same beat as the whole-app
    +1_sessions_empty, sized down because here it shares the screen. The radar
    is at its empty net and its caption says so, which is the state the deck
    draws too."""
    c = Canvas("0.2b Bean detail, no sessions")
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True, actions=["delete"])

    y = field(c, y, "Note", "", h=96) + 24
    y = section(c, y, "Radar", action="Set manually")
    card(c, y, 300)
    radar(c, W / 2, y + 140, 260, None)
    c.text(W / 2, y + 288, "Log a brew to start building this bean's flavor profile",
           "labelSmall", C["onSurfaceVariant"], "middle", size=9)
    y += 300 + 24

    y = section(c, y, "Sessions", action="New brew")
    illustration(c, "ic_mascot_pour_over", W / 2, y + 8 + 66, 132)
    c.text(W / 2, y + 8 + 132 + 12 + 11, "No brews logged for this bean yet.",
           "bodyMedium", C["onSurfaceVariant"], "middle")
    gesture_bar(c)
    return c


def bean_flavor_sheet():
    """0.2c -- BeanDetailScreen.FlavorSheet, skipPartiallyExpanded so all
    eleven axes are reachable without a scroll-inside-a-drag. An untouched
    axis reads "not set", never 0."""
    c = Canvas("0.2c Set flavor manually")
    bean_detail_lower_background(c)
    scrim(c)
    y = sheet(c, 96)
    c.text(GUTTER, y + 20, "Set flavor manually", "titleLarge")
    c.wrap(GUTTER, y + 44, "Overrides the average from this bean's sessions "
           "until you switch back.", W - 2 * GUTTER, "bodyMedium",
           C["onSurfaceVariant"])
    y += 78
    for i, label in enumerate(AXES):
        c.text(GUTTER, y + 14, label, "labelLarge")
        unset = BEAN_FLAVOR[i] is None
        slider(c, y + 10, GUTTER + 112, 148, BEAN_FLAVOR[i], unset=unset)
        c.text(W - GUTTER, y + 14, f"{BEAN_FLAVOR[i]:.1f}", "labelSmall",
               C["onSurfaceVariant"], "end")
        y += 34
    y += 8
    y = button(c, y, "Use these values") + 6
    button(c, y, "Back to the session average", kind="text")
    return c


def bean_detail_lower_background(c: Canvas):
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True, actions=["delete"])
    y = section(c, y + 120, "Radar", action="Set manually")
    card(c, y, 300)
    radar(c, W / 2, y + 140, 260, BEAN_FLAVOR)


def photo_source_sheet():
    """0.11 -- BeanDetailScreen.PhotoSourceSheet.

    This is what replaced the deck's in-app viewfinder. Capture hands off to
    ACTION_IMAGE_CAPTURE and selection to the system Photo Picker, so the app
    declares no camera permission and 0.11b (permission denied) has no
    reachable state at all."""
    c = Canvas("0.11 Which photo?")
    bean_new_background(c)
    scrim(c)
    y = sheet(c, 470)
    c.text(24, y + 26, "Which photo?", "headlineSmall")
    y += 48
    y = button(c, y, "Take a photo of the bag", x=24, w=W - 48) + 8
    y = button(c, y, "Choose one I already have", x=24, w=W - 48, kind="text") + 12
    c.wrap(24, y + 12, "Location data is removed from the photo on this phone, "
           "before anything is sent.", W - 48, "labelSmall", C["onSurfaceVariant"])
    return c


def bean_new_background(c: Canvas):
    status_bar(c)
    y = top_bar(c, "New bean")
    card(c, y, 138, fill=C["secondaryContainer"])
    c.text(W / 2, y + 34, "Scan the bag", "titleMedium",
           C["onSecondaryContainer"], "middle")
    y += 154
    y = field(c, y, "Bean name") + 14
    capsule_pair(c, y, ("Origin", ""), ("Variety", ""))


def ai_disclosure_labels():
    """The compliance artifact -- AiDisclosureSheet(ReadLabels), raised by the
    gate immediately before the transfer it authorises. One modal per
    operation; this one names the incidental-content risk in the photo."""
    c = Canvas("AI disclosure · read labels")
    bean_new_background(c)
    scrim(c)
    y = sheet(c, 372)
    c.text(24, y + 26, "Read this label with AI?", "headlineSmall")
    y = c.wrap(24, y + 62, "The photo you take is sent to be read. A photo can "
               "show more than the label — check what's in frame.", W - 48,
               "bodyLarge") + 26
    y = c.wrap(24, y, "It goes to our server, and from there to Anthropic "
               "(United States) or Qwen (China). Nothing else on this phone is "
               "sent.", W - 48, "bodyLarge") + 26
    y = c.wrap(24, y, "The fields it reads come back for you to review before "
               "anything is saved.", W - 48, "bodyMedium") + 22
    y = c.wrap(24, y, "Typing it in by hand always works instead.", W - 48,
               "bodyMedium", C["onSurfaceVariant"]) + 20
    y = button(c, y, "Send the photo", x=24, w=W - 48) + 6
    button(c, y, "Not now", x=24, w=W - 48, kind="text")
    return c


def ai_disclosure_suggest():
    """The second modal -- AiDisclosureSheet(SuggestBrew). Different payload,
    different copy, separate consent flag: rules 95/96."""
    c = Canvas("AI disclosure · suggest brew")
    brew_background(c)
    scrim(c)
    y = sheet(c, 400)
    c.text(24, y + 26, "Send these details for a suggestion?", "headlineSmall")
    y = c.wrap(24, y + 62, "The bean details you typed and the dripper you "
               "picked are sent. No photo.", W - 48, "bodyLarge") + 26
    y = c.wrap(24, y, "It goes to our server, and from there to Anthropic "
               "(United States) or Qwen (China). Nothing else on this phone is "
               "sent.", W - 48, "bodyLarge") + 26
    y = c.wrap(24, y, "The suggested recipe comes back for you to accept or "
               "ignore.", W - 48, "bodyMedium") + 22
    y = c.wrap(24, y, "Typing it in by hand always works instead.", W - 48,
               "bodyMedium", C["onSurfaceVariant"]) + 20
    y = button(c, y, "Send the details", x=24, w=W - 48) + 6
    button(c, y, "Not now", x=24, w=W - 48, kind="text")
    return c


def scanning():
    """0.12 -- the scan in flight. The card keeps its position and swaps its
    content, so nothing below it moves while the request is out."""
    c = Canvas("0.12 Reading the label")
    status_bar(c)
    y = top_bar(c, "New bean")
    card(c, y, 56, fill=C["secondaryContainer"])
    spinner(c, GUTTER + 26, y + 28)
    c.text(GUTTER + 46, y + 33, "Reading the label…", "bodyLarge",
           C["onSecondaryContainer"])
    y += 56 + 16
    y = field(c, y, "Bean name") + 10
    y = field(c, y, "Origin") + 10
    half = (W - 2 * GUTTER - 12) / 2
    field(c, y, "Variety", w=half)
    field(c, y, "Altitude", x=GUTTER + half + 12, w=half)
    y += 66
    field(c, y, "Roaster", w=half)
    field(c, y, "Producer", x=GUTTER + half + 12, w=half)
    y += 66
    choice_field(c, y, "Process", "")
    gesture_bar(c)
    return c


def scan_offline():
    """0.12b -- GatewayFailure.Offline. Two failures need two sentences: this
    one is about the network, the "couldn't read that photo" one is about the
    photo, and the form stays editable underneath either way."""
    c = Canvas("0.12b Scan failed, offline")
    status_bar(c)
    y = top_bar(c, "New bean")
    card(c, y, 96, fill=C["secondaryContainer"])
    c.wrap(GUTTER + 16, y + 28, "You're offline. The label scan needs a "
           "connection — type the details in for now.", W - 2 * GUTTER - 32,
           "bodyMedium", C["onSecondaryContainer"])
    c.text(GUTTER + 28, y + 78, "Try again", "labelLarge", C["primary"], "middle")
    c.text(GUTTER + 110, y + 78, "Dismiss", "labelLarge", C["primary"], "middle")
    y += 96 + 16
    y = field(c, y, "Bean name") + 10
    y = field(c, y, "Origin") + 10
    half = (W - 2 * GUTTER - 12) / 2
    field(c, y, "Variety", w=half)
    field(c, y, "Altitude", x=GUTTER + half + 12, w=half)
    y += 66
    field(c, y, "Roaster", w=half)
    field(c, y, "Producer", x=GUTTER + half + 12, w=half)
    gesture_bar(c)
    return c


def scan_blocked():
    """0.12c -- rule 98's inline off-state. Not a modal and not a re-ask: the
    person who turned label scanning off already decided."""
    c = Canvas("0.12c Scan turned off")
    status_bar(c)
    y = top_bar(c, "New bean")
    card(c, y, 72, fill=C["secondaryContainer"])
    c.wrap(GUTTER + 16, y + 30, "Label scanning is off. Turn it back on in "
           "Profile › How we use AI.", W - 2 * GUTTER - 32, "bodyMedium",
           C["onSecondaryContainer"])
    y += 72 + 16
    y = field(c, y, "Bean name") + 10
    y = field(c, y, "Origin") + 10
    half = (W - 2 * GUTTER - 12) / 2
    field(c, y, "Variety", w=half)
    field(c, y, "Altitude", x=GUTTER + half + 12, w=half)
    y += 66
    field(c, y, "Roaster", w=half)
    field(c, y, "Producer", x=GUTTER + half + 12, w=half)
    gesture_bar(c)
    return c


def scan_review():
    """screens.md §3 -- ScanReviewSheet. Every guessed field is editable, and
    a "was:" hint appears only where a value would actually be replaced."""
    c = Canvas("Scan review")
    bean_new_background(c)
    scrim(c)
    y = sheet(c, 60)
    c.text(24, y + 26, "What the label says", "headlineSmall")
    c.text(24, y + 46, "Read by AI. Check it — then edit anything it got wrong.",
           "labelSmall", C["onSurfaceVariant"])
    y += 62
    c.rect(24, y, 72, 72, C["surfaceContainerHigh"], R_THUMB)
    bag_tile(c, 24, y, 72, "Et")
    y += 84

    # ScanReviewSheet renders all nine of LABELS; the sheet scrolls, so this
    # frame is the top of it. Process / Roast date / Note are below the fold.
    rows = [("Bean name", "Ethiopia Guji Natural", ""),
            ("Origin", "Ethiopia", ""),
            ("Variety", "Heirloom", ""),
            ("Altitude", "1 950 m", ""),
            ("Roaster", "Terres de Café", "Terre de Cafe"),
            ("Producer", "Buku Abel", "")]
    for label, value, was in rows:
        y = field(c, y, label, value, x=24, w=W - 48) + 10
        if was:
            c.text(24, y + 6, f"was: {was}", "labelSmall", C["onSurfaceVariant"])
            y += 16
    y += 4
    y = button(c, y, "Apply and keep the photo", x=24, w=W - 48) + 4
    y = button(c, y, "Discard", x=24, w=W - 48, kind="text") + 2
    button(c, y, "Report this reading", x=24, w=W - 48, kind="text")
    return c


def scan_review_empty():
    """The empty read -- a blurry shot or a photo of a mug. A state, not an
    error: it says what happened and leaves manual entry where it was."""
    c = Canvas("Scan review, nothing read")
    bean_new_background(c)
    scrim(c)
    y = sheet(c, 200)
    c.text(24, y + 26, "What the label says", "headlineSmall")
    c.text(24, y + 46, "Read by AI. Check it — then edit anything it got wrong.",
           "labelSmall", C["onSurfaceVariant"])
    y += 62
    c.rect(24, y, 72, 72, C["surfaceContainerHigh"], R_THUMB)
    c.wrap(108, y + 26, "Couldn't read much from this photo — the fields are "
           "blank, fill them in by hand.", W - 132, "bodyMedium")
    y += 88
    for label in ("Bean name", "Origin", "Variety"):
        y = field(c, y, label, "", x=24, w=W - 48) + 10
    y += 4
    y = button(c, y, "Apply", x=24, w=W - 48) + 4
    y = button(c, y, "Discard", x=24, w=W - 48, kind="text") + 2
    button(c, y, "Report this reading", x=24, w=W - 48, kind="text")
    return c


def delete_bean():
    """The cascade confirm. Naming the brew count is the point of the
    dialog -- it is the part nobody expects from "delete bean"."""
    c = Canvas("Delete bean")
    bean_detail_background(c)
    scrim(c)
    top = 280
    dialog(c, top, 196)
    c.text(52, top + 44, "Delete this bean?", "headlineSmall", size=22)
    c.wrap(52, top + 78, "This removes the bean, its photos and its 4 logged "
           "brews. It can't be undone.", W - 104, "bodyMedium")
    c.text(W - 52, top + 164, "Delete", "labelLarge", C["primary"], "end")
    c.text(W - 128, top + 164, "Cancel", "labelLarge", C["primary"], "end")
    return c


def bean_detail_background(c: Canvas):
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True, actions=["delete"])
    bag_tile(c, GUTTER, y, 72, "Et")
    y += 88
    y = field(c, y, "Bean name", BEAN["name"]) + 14
    capsule_pair(c, y, ("Origin", BEAN["origin"]), ("Variety", BEAN["variety"]))


def sessions():
    """+1 -- SessionsScreen. Dense rows with a hairline divider and no card
    chrome, unlike Home: a log is more numerous than a shelf."""
    c = Canvas("+1 Sessions")
    status_bar(c)
    y = top_bar(c, "Sessions", back=True)
    c.text(GUTTER, y + 20, f"Newest first · {len(SESSIONS)} sessions",
           "labelMedium", C["onSurfaceVariant"])
    y += 32
    for name, meta, day in SESSIONS:
        c.text(GUTTER, y + 26, name, "titleMedium")
        c.text(GUTTER, y + 44, meta, "bodyMedium", C["onSurfaceVariant"])
        c.text(W - GUTTER, y + 36, day, "bodyMedium", C["onSurfaceVariant"], "end")
        divider(c, y + 60)
        y += 60
    fab(c)
    gesture_bar(c)
    return c


def sessions_empty():
    """+1_sessions_empty -- SessionsScreen.SessionsEmpty, with the pour-over
    mascot at 184dp above the headline. Nothing else is on this page."""
    c = Canvas("+1 Sessions, empty")
    status_bar(c)
    top_bar(c, "Sessions", back=True)
    cy = (BAR_BOTTOM + H) / 2 - 20 + 100
    illustration(c, "ic_mascot_pour_over", W / 2, cy - 134, 184)
    c.text(W / 2, cy, "No brews yet", "headlineMedium", anchor="middle")
    c.wrap(W / 2, cy + 34, "Every brew you log lands here, newest first. "
           "Tap + to add one.", W - 80, "bodyLarge", C["onSurfaceVariant"],
           anchor="middle")
    fab(c)
    gesture_bar(c)
    return c


def which_bean():
    """+1.1 -- WhichBeanSheet, hoisted into the nav graph because both FABs
    open it. Three answers, and the third is the interesting one."""
    c = Canvas("+1.1 Which bean?")
    sessions_background(c)
    scrim(c)
    y = sheet(c, 300)
    c.text(24, y + 26, "Which bean?", "headlineSmall")
    y += 46
    for name, roaster, origin, _, _p, _r in BEANS[:4]:
        bag_tile(c, 24, y + 6, 44, origin[:2])
        c.text(80, y + 24, name, "bodyLarge")
        c.text(80, y + 42, roaster, "bodyMedium", C["onSurfaceVariant"])
        divider(c, y + 60, x=24, w=W - 48)
        y += 64
    y += 12
    y = button(c, y, "Add a new bean", x=24, w=W - 48, kind="outlined") + 4
    button(c, y, "Just start brewing", x=24, w=W - 48, kind="text")
    return c


def which_bean_empty():
    """+1.1 with nothing on the shelf: the vibe-brewing path is the one that
    still works, and the copy says so."""
    c = Canvas("+1.1 Which bean?, no beans")
    status_bar(c)
    top_bar(c, "Coffee Can", action_text="Add bean")
    scrim(c)
    y = sheet(c, 528)
    c.text(24, y + 26, "Which bean?", "headlineSmall")
    y += 48
    c.wrap(24, y + 14, "No beans yet. Add the bag, or start brewing and name "
           "it later.", W - 48, "bodyMedium", C["onSurfaceVariant"])
    y += 56
    y = button(c, y, "Add a new bean", x=24, w=W - 48, kind="outlined") + 4
    button(c, y, "Just start brewing", x=24, w=W - 48, kind="text")
    return c


def sessions_background(c: Canvas):
    status_bar(c)
    y = top_bar(c, "Sessions", back=True)
    y += 32
    for name, meta, day in SESSIONS[:4]:
        c.text(GUTTER, y + 26, name, "titleMedium")
        c.text(GUTTER, y + 44, meta, "bodyMedium", C["onSurfaceVariant"])
        divider(c, y + 60)
        y += 60


def brew_background(c: Canvas):
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True)
    y = section(c, y, "Brew details", action="Ask AI")
    card(c, y, 300)
    field(c, y + 60, "Dripper", "Hario V60", x=GUTTER + 16, w=W - 2 * GUTTER - 32)


def brew():
    """+1.1 log brew -- BrewSessionScreen, top. A new session pre-fills from
    the bean's last one: recipe reuse is the actual workflow."""
    c = Canvas("+1.1 Log a brew")
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True)
    y = section(c, y, "Brew details", action="Ask AI")

    # 16 of card padding, the 52dp brewed row, then four 46dp capsule pairs
    # with Arrangement.spacedBy(10) between every child, and 16 again.
    ch = 16 + 52 + 10 + 4 * 46 + 3 * 10 + 16
    card(c, y, ch)
    iy, ix, iw = y + 16, GUTTER + 16, W - 2 * GUTTER - 32
    c.text(ix, iy + 14, "Brewed", "labelMedium", C["onSurfaceVariant"])
    c.text(ix, iy + 34, "Tuesday 11 August 2026", "bodyLarge")
    c.text(W - GUTTER - 16, iy + 30, "Change", "labelLarge", C["primary"], "end")
    iy += 62
    # Eight capsules in four pairs, in the deck's +1.1c order. Every one of
    # them is optional, and eight outlined boxes for eight optional answers is
    # a form that looks like it is demanding them.
    iy = capsule_pair(c, iy, ("Dripper", "Hario V60"),
                      ("Grinder", "Comandan…"), x=ix, w=iw) + 10
    iy = capsule_pair(c, iy, ("Grind size", "24 clicks"),
                      ("Filter", "Hario V60 02…"), x=ix, w=iw) + 10
    iy = capsule_pair(c, iy, ("Dose (g)", "15.0"),
                      ("Water (g)", "250"), x=ix, w=iw) + 10
    iy = capsule_pair(c, iy, ("Water °C", "93"),
                      ("Water ppm", "72"), x=ix, w=iw)
    y += ch + 20

    y = section(c, y, "Pour stages", action="Add stage")
    for i, (water, temp, at, label) in enumerate(
            [("45 g", "93 °C", "0:00", "Bloom"), ("120 g", "93 °C", "0:45", "")]):
        c.text(GUTTER, y + 26, str(i + 1), "titleMedium")
        c.text(GUTTER + 36, y + 26, " · ".join([water, temp, at]), "bodyLarge")
        if label:
            c.text(GUTTER + 36, y + 44, label, "bodyMedium", C["onSurfaceVariant"])
        c.path(f"M{W - GUTTER - 18} {y + 20} l10 10 M{W - GUTTER - 8} {y + 20} "
               f"l-10 10", stroke=C["onSurface"], sw=1.6)
        divider(c, y + 56)
        y += 56
    gesture_bar(c)
    return c


def brew_lower():
    """+1.1b -- the same screen below the fold: the evaluation card, the live
    radar and the eleven sliders it is made of."""
    c = Canvas("+1.1b Log a brew, lower")
    status_bar(c)
    y = top_bar(c, BEAN["name"], back=True)
    y = section(c, y, "How was it?")
    card(c, y, 300)
    iy, ix, iw = y + 16, GUTTER + 16, W - 2 * GUTTER - 32
    c.text(ix, iy + 14, "Score", "labelLarge")
    slider(c, iy + 10, ix + 96, 120, 4.5)
    c.text(W - GUTTER - 16, iy + 14, "4.5", "labelSmall", C["onSurfaceVariant"], "end")
    iy += 24
    c.text(ix, iy + 30, "Clear score", "labelLarge", C["primary"])
    iy += 42
    c.text(ix, iy + 12, "Extraction", "labelLarge")
    ey = extraction_bar(c, ix, iy + 22, iw, 0.1)
    slider(c, ey + 14, ix, iw, 0.1, lo=-1, hi=1)
    iy = ey + 34
    field(c, iy, "Note", "Bright, clean. Cut the bloom shorter.", x=ix, w=iw, h=88)
    y += 300 + 20

    y = section(c, y, "Flavor")
    card(c, y, 320)
    radar(c, W / 2, y + 128, 240, SESSION_FLAVOR, labels=SHORT_AXES)
    ry = y + 246
    for i in range(3):
        c.text(GUTTER + 12, ry + 12, AXES[i], "labelLarge")
        slider(c, ry + 8, GUTTER + 116, 132, SESSION_FLAVOR[i])
        c.text(W - GUTTER - 12, ry + 12, f"{SESSION_FLAVOR[i]:.1f}", "labelSmall",
               C["onSurfaceVariant"], "end")
        ry += 24
    y += 320 + 24
    button(c, y, "Log this brew")
    gesture_bar(c)
    return c


def stage_editor():
    """+1.2 -- StageEditorSheet. skipPartiallyExpanded, and the time is typed
    rather than dialled: the parser takes "105", "1:45" and "1m45"."""
    c = Canvas("+1.2 Stage editor")
    brew_background(c)
    scrim(c)
    y = sheet(c, 330)
    c.text(24, y + 26, "Stage 2", "headlineSmall")
    y += 46
    y = field(c, y, "Label", "Second pour", x=24, w=W - 48) + 12
    half = (W - 48 - 12) / 2
    field(c, y, "Water (g)", "120", x=24, w=half)
    field(c, y, "Temp (°C)", "93", x=24 + half + 12, w=half)
    y += 68
    y = field(c, y, "At (time)", "0:45", x=24, w=W - 48) + 12
    y = field(c, y, "Note", "swirl gently", x=24, w=W - 48) + 12
    button(c, y, "Done", x=24, w=W - 48)
    return c


def suggestion():
    """+1.3 -- SuggestionSheet. Nothing is applied until the user says so,
    the provider is named on the output itself, and the report control sits
    where somebody who just read something wrong is already looking."""
    c = Canvas("+1.3 Suggested recipe")
    brew_background(c)
    scrim(c)
    y = sheet(c, 344)
    c.text(24, y + 26, "A suggested recipe", "headlineSmall")
    c.text(24, y + 46, "Written by AI (anthropic). Check it before you brew.",
           "labelSmall", C["onSurfaceVariant"])
    y = c.wrap(24, y + 70, "A natural Ethiopian at this roast level takes a "
               "slightly coarser grind and a gentle bloom; keep the total "
               "contact under three minutes.", W - 48, "bodyLarge") + 26
    x = chip(c, 24, y, "15.0 g")
    chip(c, x, y, "medium-fine")
    y += 46
    for i, line in enumerate((
            "45 g · 93 °C · at 0:00 · gentle swirl",
            "120 g · 93 °C · at 0:45 · centre pour",
            "250 g · 92 °C · at 1:30 · slow spiral")):
        c.text(24, y + 14 + i * 20, f"{i + 1}. {line}", "bodyMedium")
    y += 76
    y = button(c, y, "Use this recipe", x=24, w=W - 48) + 4
    button(c, y, "Report this suggestion", x=24, w=W - 48, kind="text")
    return c


def delete_brew():
    c = Canvas("Delete brew")
    brew_background(c)
    scrim(c)
    top = 300
    dialog(c, top, 176)
    c.text(52, top + 44, "Delete this brew?", "headlineSmall", size=22)
    c.wrap(52, top + 78, "The bean and its other brews stay. This can't be "
           "undone.", W - 104, "bodyMedium")
    c.text(W - 52, top + 144, "Delete", "labelLarge", C["primary"], "end")
    c.text(W - 128, top + 144, "Cancel", "labelLarge", C["primary"], "end")
    return c


def profile_empty():
    """+2 signed out -- ProfileScreen with signedIn = false.

    One button, not a "Log in"/"Create an account" pair: Google is the only
    method, so the first sign-in is the account creation. The list is titled
    "About & legal" and the version row holds the slot Delete account takes
    when there is an account."""
    c = Canvas("+2 Profile, signed out")
    status_bar(c)
    y = top_bar(c, "Profile", back=True)
    y += 24
    # The mark, 88dp, wordmark + tagline: ProfileScreen.kt's signed-out branch
    # now opens with CoffeeCanLogo, which draws the shipped icon.svg's own
    # lettering (res/drawable/ic_brand_lockup.xml) on the Brand disc.
    illustration(c, "ic_brand_lockup", W / 2, y + 44, 88)
    y += 88 + 16
    c.text(W / 2, y + 24, "Not signed in", "headlineMedium", anchor="middle")
    y = c.wrap(W / 2, y + 58, "Your beans and sessions stay on this phone. "
               "Sign in for AI label reading and coffee news.", W - 80,
               "bodyLarge", C["onSurfaceVariant"], anchor="middle") + 26
    y = google_button(c, y) + 28

    y = section(c, y, "About & legal")
    card(c, y, 3 * 58)
    rows = [("Privacy Policy", None, False),
            ("How we use AI", "What we send, and how to turn it off", False),
            ("Version", "1.0.0 (1)", True)]
    for i, (label, sub, value_row) in enumerate(rows):
        ry = y + i * 58
        two = sub and not value_row
        c.text(GUTTER + 16, ry + (28 if two else 34), label, "bodyLarge")
        if two:
            c.text(GUTTER + 16, ry + 46, sub, "bodyMedium", C["onSurfaceVariant"])
        if value_row:
            c.text(W - GUTTER - 16, ry + 34, sub, "bodyMedium",
                   C["onSurfaceVariant"], "end")
        else:
            c.path(f"M{W - GUTTER - 26} {ry + 27} l6 6 l-6 6",
                   stroke=C["outline"], sw=1.6)
        if i < len(rows) - 1:
            divider(c, ry + 58, x=GUTTER + 16, w=W - 2 * GUTTER - 32)
    gesture_bar(c)
    return c


def profile():
    """+2 signed in.

    No avatar, no Name, no Email -- rule 60 removed every reason they
    existed, and the code has no field for any of them. That is the widest
    divergence from the deck's +2, and it is the spec winning."""
    c = Canvas("+2 Profile, signed in")
    status_bar(c)
    y = top_bar(c, "Profile", back=True, action_text="Log out")
    y += 12
    y = section(c, y, "Account & legal")
    card(c, y, 3 * 58)
    rows = [("Privacy Policy", None, False),
            ("How we use AI", "What we send, and how to turn it off", False),
            ("Delete account", "Unlinks Google. Your log stays on this phone.", True)]
    for i, (label, sub, danger) in enumerate(rows):
        ry = y + i * 58
        ink = C["error"] if danger else C["onSurface"]
        c.text(GUTTER + 16, ry + (28 if sub else 34), label, "bodyLarge", ink)
        if sub:
            c.text(GUTTER + 16, ry + 46, sub, "bodyMedium", C["onSurfaceVariant"])
        c.path(f"M{W - GUTTER - 26} {ry + 27} l6 6 l-6 6",
               stroke=ink if danger else C["outline"], sw=1.6)
        if i < len(rows) - 1:
            divider(c, ry + 58, x=GUTTER + 16, w=W - 2 * GUTTER - 32)
    gesture_bar(c)
    return c


def privacy():
    """+2.2a -- PrivacyScreen. A short summary plus the canonical URL, never a
    copy of the policy; no last-updated date of its own; and no sentence
    claiming data never leaves the device."""
    c = Canvas("+2.2a Privacy")
    status_bar(c)
    y = top_bar(c, "Privacy", back=True)
    y = section(c, y, "In short")
    card(c, y, 232)
    by = y + 26
    for line in (
            "Your beans, brews, notes and photos stay on this phone. We have no copy.",
            "Signed in, we keep your Google account ID so AI and news requests can be metered.",
            "AI features send your photo, or the notes you typed, to Anthropic (US) or Qwen (CN).",
            "Roaster photos load from each roaster's own site, which shows them your device."):
        c.text(GUTTER + 14, by, "•", "bodyMedium", C["primary"])
        by = c.wrap(GUTTER + 28, by, line, W - 2 * GUTTER - 44, "bodyMedium") + 26
    y += 232 + 10
    y = c.wrap(GUTTER, y + 12, "Uninstalling deletes what's on this phone. If "
               "your phone backs itself up, that backup is governed by whoever "
               "runs it.", W - 2 * GUTTER, "labelSmall", C["onSurfaceVariant"]) + 20

    y = section(c, y, "Your data")
    card(c, y, 3 * 58)
    rows = [("Export my data", "The account ID and usage counts we hold", False),
            ("Delete account", "Unlinks Google. Your log stays on this phone.", True),
            ("Turn AI features off", "What we send, and how to stop sending it", False)]
    for i, (label, sub, danger) in enumerate(rows):
        ry = y + i * 58
        ink = C["error"] if danger else C["onSurface"]
        c.text(GUTTER + 16, ry + 28, label, "bodyLarge", ink)
        c.text(GUTTER + 16, ry + 46, sub, "bodyMedium", C["onSurfaceVariant"])
        c.path(f"M{W - GUTTER - 26} {ry + 27} l6 6 l-6 6",
               stroke=ink if danger else C["outline"], sw=1.6)
        if i < len(rows) - 1:
            divider(c, ry + 58, x=GUTTER + 16, w=W - 2 * GUTTER - 32)
    y += 3 * 58 + 8

    c.text(GUTTER + 12, y + 14, "Already uninstalled? You can also delete it at",
           "labelSmall", C["onSurfaceVariant"])
    c.text(GUTTER + 12, y + 30, "coffeecan.app/delete", "labelSmall", C["primary"])
    y += 46

    y = section(c, y, "The full policy")
    card(c, y, 68)
    c.text(GUTTER + 16, y + 30, "coffeecan.app/privacy", "bodyLarge", C["primary"])
    c.text(GUTTER + 16, y + 50, "Always the current version. Tap to open, hold to copy.",
           "labelSmall", C["onSurfaceVariant"])
    y += 68 + 24
    c.text(GUTTER, y + 12, "Questions: hello@coffeecan.app", "labelSmall",
           C["onSurfaceVariant"])
    c.text(GUTTER, y + 28, "You can also complain to the CNIL (cnil.fr).",
           "labelSmall", C["onSurfaceVariant"])
    gesture_bar(c)
    return c


def how_we_use_ai():
    """+2.2b -- AiDisclosureScreen. Explanation first, controls after; two
    switches and no master toggle; and the consequence line sits under them
    permanently, in both states."""
    c = Canvas("+2.2b How we use AI")
    status_bar(c)
    y = top_bar(c, "How we use AI", back=True)
    y = section(c, y, "What we send")
    card(c, y, 196)
    by = c.wrap(GUTTER + 16, y + 30, "Coffee Can can read a bean bag's label "
                "from a photo, and suggest brew settings from details you've "
                "typed. Both are optional.", W - 2 * GUTTER - 32, "bodyMedium")
    c.wrap(GUTTER + 16, by + 30, "What you send goes to our server, and from "
           "there to Anthropic (United States) or Qwen (China). Nothing else on "
           "this phone is sent.", W - 2 * GUTTER - 32, "bodyMedium")
    y += 196 + 20

    y = section(c, y, "AI features")
    # ConsentRow's text sits in a weight(1f) Column beside the switch, so the
    # "sends" line wraps rather than running under it -- at 14sp bodyMedium the
    # second row takes two lines and the card grows by one line's worth.
    rows = (("Read labels from photos", "Sends the photo you take",
             "On since 3 August", True, 92),
            ("Suggest brew settings", "Sends the details you typed. No photo.",
             "Off", False, 110))
    tw = W - 2 * GUTTER - 32 - 64          # the 52dp switch plus 12 of gap
    card(c, y, sum(r[4] for r in rows))
    ry = y
    for i, (title, sends, state, on, rh) in enumerate(rows):
        c.text(GUTTER + 16, ry + 30, title, "bodyLarge")
        by = c.wrap(GUTTER + 16, ry + 50, sends, tw, "bodyMedium",
                    C["onSurfaceVariant"])
        c.text(GUTTER + 16, by + 20, state, "labelSmall",
               C["primary"] if on else C["outline"])
        switch(c, W - GUTTER - 68, ry + rh / 2, on)
        if i == 0:
            divider(c, ry + rh, x=GUTTER + 16, w=W - 2 * GUTTER - 32)
        ry += rh
    y = ry + 10
    c.text(GUTTER, y + 12, "Typing everything in by hand always works, with or "
           "without these.", "labelSmall", C["onSurfaceVariant"])
    y += 30

    y = section(c, y, "If you turn them off")
    card(c, y, 92)
    by = y + 30
    for line in ("Nothing new is sent.",
                 "Your log, and labels already read, stay put.",
                 "Copies already sent aren't recalled."):
        c.text(GUTTER + 14, by, "•", "bodyMedium", C["primary"])
        c.text(GUTTER + 28, by, line, "bodyMedium")
        by += 21
    y += 92 + 20
    card(c, y, 56)
    c.text(GUTTER + 16, y + 33, "Report a bad suggestion", "bodyLarge")
    c.path(f"M{W - GUTTER - 26} {y + 25} l6 6 l-6 6", stroke=C["outline"], sw=1.6)
    gesture_bar(c)
    return c


def report_sheet():
    """+2.2b's ReportSheet -- legal-android rule 5's route, mirrored here from
    the AI output itself. Deliberately not consent-gated."""
    c = Canvas("Report AI output")
    how_we_use_ai_background(c)
    scrim(c)
    y = sheet(c, 350)
    c.text(24, y + 26, "Report AI output", "headlineSmall")
    y = c.wrap(24, y + 56, "Tell us what was wrong with it. This goes to the "
               "developer, not to the AI provider.", W - 48, "bodyMedium",
               C["onSurfaceVariant"]) + 26
    x = chip(c, 24, y, "Read labels from photos")
    chip(c, x, y, "Suggest brew settings", selected=True)
    y += 46
    field(c, y, "What went wrong?", "It read the roaster as the origin.",
          x=24, w=W - 48, h=100)
    y += 112
    button(c, y, "Send report", x=24, w=W - 48)
    return c


def how_we_use_ai_background(c: Canvas):
    status_bar(c)
    y = top_bar(c, "How we use AI", back=True)
    y = section(c, y, "What we send")
    card(c, y, 136)
    y += 156
    section(c, y, "AI features")


def data_access():
    """The Art. 15(3) access document -- DataAccessSheet. It is small because
    that is genuinely everything the developer holds."""
    c = Canvas("What we hold about you")
    privacy_background(c)
    scrim(c)
    y = sheet(c, 258)
    c.text(24, y + 26, "What we hold about you", "headlineSmall")
    y += 54
    # Every value below is what the SERVER actually sends, not a plausible
    # invention: the op codes are coffee_server/main.py's `meter(sub, ...)`
    # arguments ("vision", "suggest"), the limits are config.DAILY_QUOTA's
    # defaults, and the closing sentence is accounts.py's own
    # `what_is_not_here` string verbatim. An access document is a legal
    # statement about what exists; paraphrasing it in a mock is the same
    # category of error as drawing a logo the app does not have.
    lines = [
        "Account identifier (Google 'sub'): 118207…4471",
        "Created: 3 Aug 2026, 09:12",
        "Last seen: 11 Aug 2026, 07:48",
        "",
        "Usage counters:",
        "  2026-08-11  vision  2",
        "  2026-08-11  suggest  1",
        "  2026-08-09  vision  1",
        "Daily limits: ask 60, suggest 60, vision 40",
        "",
        "Your beans, brew sessions, notes and photos are",
        "on your phone only. This server has never received",
        "them and has no copy to give you.",
    ]
    for i, line in enumerate(lines):
        c.text(24, y + i * 19, line, "bodyMedium",
               C["onSurfaceVariant"] if line.startswith("  ") else C["onSurface"],
               family=MONO if line.startswith("  ") else FONT, size=12)
    y += len(lines) * 19 + 14
    button(c, y, "Save a copy", x=24, w=W - 48)
    return c


def privacy_background(c: Canvas):
    status_bar(c)
    y = top_bar(c, "Privacy", back=True)
    y = section(c, y, "In short")
    card(c, y, 232)
    y += 210
    section(c, y, "Your data")


def delete_account():
    """DeleteAccountDialog. The subtitle is the feature: someone with four
    years of brews will never press a button that might take them."""
    c = Canvas("Delete account")
    privacy_background(c)
    scrim(c)
    top = 230
    dialog(c, top, 268)
    c.text(52, top + 46, "Delete your account?", "headlineSmall", size=22)
    by = c.wrap(52, top + 82, "This unlinks Google and erases the account "
                "record: the identifier, usage counts and rate-limit records. "
                "It cannot be undone.", W - 104, "bodyLarge") + 28
    c.wrap(52, by, "Your beans, brews, notes and photos stay on this phone. "
           "They were never on our server, so there is nothing there to delete.",
           W - 104, "bodyMedium", C["onSurfaceVariant"])
    c.text(W - 52, top + 236, "Delete", "labelLarge", C["primary"], "end")
    c.text(W - 128, top + 236, "Cancel", "labelLarge", C["primary"], "end")
    return c


def saved_snackbar():
    """The save confirmation, as a Material3 Snackbar rather than the deck's
    bespoke flash bar (README resolution #10)."""
    c = Canvas("Saved")
    bean_detail_background(c)
    snackbar(c, "Saved")
    gesture_bar(c)
    return c


def welcome():
    """00w -- the launch theme, not a screen.

    There is no composable behind this frame and there must not be: from
    Android 12 the platform draws a splash from the launch theme on every cold
    start, so a Compose welcome destination would be a second one. What is
    drawn here is `res/values/themes.xml`'s `Theme.CoffeeCan.Splash` resolved
    by hand -- `windowSplashScreenBackground` filling the window and
    `windowSplashScreenAnimatedIcon` centred in it.

    THE DECK'S 00w IS BIGGER THAN THIS AND CANNOT BE MATCHED. It sets the mark
    at 290dp with the tagline; the system splash centres one icon in a 288dp
    canvas whose inner 192dp is the safe area, which lands the mark near 120dp
    and makes the tagline texture rather than words. Drawing the deck's version
    here would be drawing a screen the app cannot produce.
    """
    c = Canvas("00w Welcome")
    c.rect(0, 0, W, H, C["brand"])
    status_bar(c, ink=C["onPrimary"])
    illustration(c, "ic_brand_wordmark", W / 2, H / 2, 120, disc=False)
    gesture_bar(c)
    return c


PAGES = [
    ("00w_welcome.png", welcome),
    ("00_home.png", home),
    ("00_home_empty.png", home_empty),
    ("0.1_bean_new.png", bean_new),
    ("0.2_bean_detail.png", bean_detail),
    ("0.2b_bean_detail_lower.png", bean_detail_lower),
    ("0.2b_bean_detail_lower_empty.png", bean_detail_lower_empty),
    ("0.2c_flavor_manual.png", bean_flavor_sheet),
    ("0.2d_delete_bean.png", delete_bean),
    ("0.2e_saved_snackbar.png", saved_snackbar),
    ("0.11_photo_source.png", photo_source_sheet),
    ("0.11a_ai_disclosure_labels.png", ai_disclosure_labels),
    ("0.12_scanning.png", scanning),
    ("0.12b_scan_offline.png", scan_offline),
    ("0.12c_scan_blocked.png", scan_blocked),
    ("0.13_scan_review.png", scan_review),
    ("0.13b_scan_review_empty.png", scan_review_empty),
    ("+1_sessions.png", sessions),
    ("+1_sessions_empty.png", sessions_empty),
    ("+1.1_which_bean.png", which_bean),
    ("+1.1b_which_bean_empty.png", which_bean_empty),
    ("+1.2_log_brew.png", brew),
    ("+1.2b_log_brew_lower.png", brew_lower),
    ("+1.3_stage_editor.png", stage_editor),
    ("+1.4_ai_disclosure_suggest.png", ai_disclosure_suggest),
    ("+1.5_suggestion.png", suggestion),
    ("+1.6_delete_brew.png", delete_brew),
    ("+2_profile.png", profile),
    ("+2_profile_empty.png", profile_empty),
    ("+2.2a_privacy.png", privacy),
    ("+2.2b_how_we_use_ai.png", how_we_use_ai),
    ("+2.2c_report.png", report_sheet),
    ("+2.3_data_access.png", data_access),
    ("+2.4_delete_account.png", delete_account),
]


# --------------------------------------------------------- rasterisation ---
def chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("no Chrome/Chromium on PATH; cannot rasterise")


def rasterise(svg: str, png: pathlib.Path, browser: str, workdir: pathlib.Path):
    html = workdir / (png.stem.replace("+", "p") + ".html")
    html.write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<style>html,body{margin:0;padding:0;background:#F2FAF2}"
        "svg{display:block}</style>" + svg,
        encoding="utf-8",
    )
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1",
         f"--window-size={W * SCALE},{H * SCALE}",
         f"--screenshot={png}", f"--user-data-dir={workdir / 'profile'}",
         html.as_uri()],
        check=True, capture_output=True,
    )


def main():
    keep_svg = "--svg" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    browser = chrome()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        for name, fn in PAGES:
            svg = fn().render()
            if keep_svg:
                (OUT / (name[:-4] + ".svg")).write_text(svg, encoding="utf-8")
            rasterise(svg, OUT / name, browser, workdir)
            print(f"  {name}")
    print(f"{len(PAGES)} screenshots -> {OUT}")


if __name__ == "__main__":
    main()
