#!/usr/bin/env python3
"""Diff the build against scheme E, and the simulator against the build.

    python3 check_design.py          # report; exit 1 if anything drifted

THIS EXISTS BECAUSE READING THE CODE'S OWN COMMENTS IS NOT A CHECK. `Theme.kt`
opens by asserting scheme E was ported "token for token … every hex copied
rather than approximated". The colours are indeed exact. The type scale was
wrong in ten of eleven roles, and a review that trusted the comment reported the
theme as faithful. See AUDIT.md §5.

Three checks, in the order they would have caught that:

  1. COLOUR   -- every PURE_GREEN token against its Compose val. Passes today.
  2. TYPE     -- every role's size and weight against the deck's own table,
                 after variants._apply_style(FREDOKA_STYLE) has been applied.
                 This is the one that fails.
  3. SIMULATOR-- every string screenshots.py draws, against the .kt sources and
                 coffee_server. Catches a mock that flatters the build by
                 drawing chrome or copy the app does not have.

What this deliberately does NOT check: layout, density, component choice,
illustration. Those need eyes on a rendered deck page (`plan/screenshots/
scheme-e/*.svg`) next to the matching `screenshots/*.png`, and no assertion
here substitutes for doing that.

Nor does it check PER-SCREEN TYPE OVERRIDES, and this is the blind spot most
likely to be misread as a pass. Check 2 diffs two *tables* — the deck's `wf.T`
against `SchemeETypography` — but the deck does not only use its table. It
overrides the size at individual call sites (`00_home`'s bean name is
`wf.text(..., "titleMedium", size=14)` against a 16sp role; its meta line is
`"bodyMedium", size=11` against 14), and a screen that renders those two lines
at the theme's sizes is visibly not the deck page while every assertion here
still reports green. Grepping `size=` in `plan/scheme_e.py` lists them; each
one has to be carried over by hand at the matching Compose call site, as a
`style = ...typography.X.copy(fontSize = N.sp)`.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PLAN = HERE.parent / "plan"
THEME = HERE / "app/src/main/java/app/coffeecan/ui/theme/Theme.kt"
SRC = HERE / "app/src/main"
SERVER = HERE.parent.parent / "coffee_server"

sys.path.insert(0, str(PLAN))
import variants as V           # noqa: E402
import wireframes as wf        # noqa: E402

wf.C.update(V.PURE_GREEN)
wf.SEQ[:] = V.PURE_GREEN_SEQ
V._apply_style(V.FREDOKA_STYLE)

theme = THEME.read_text()
failures: list[str] = []
deviations: list[str] = []

# Tokens where the app deliberately departs from the deck, each with the
# decision behind it. `deck_key -> (app_hex, why)`.
#
# THIS IS NOT A SUPPRESSION LIST, AND MUST NOT BECOME ONE. An entry here says
# "the deck is the stale side, and here is the reasoning" -- it is reported
# under its own heading, and it still says exactly which two values differ, so
# the deviation stays visible on every run. The reason it exists at all is that
# a check which can never go green is a check people stop reading; the 72
# false positives this script used to print (see the strings.xml note further
# down) are what that failure mode looks like. Anything added here needs the
# same standard: a decision recorded in Theme.kt, not a value someone changed.
ACCEPTED_DEVIATIONS = {
    "surface": (
        "#FFFFFF",
        "page and cards are both plain white; nothing outlines a block, so "
        "adjacent cards are separated by an inset rule and a standalone block "
        "by its own heading (Theme.kt)",
    ),
}


def report(section: str, bad: list[str], checked: int):
    print(f"\n=== {section} ({checked} checked) ===")
    if not bad:
        print("  ok")
        return
    for line in bad:
        print(f"  {line}")
    failures.append(f"{section}: {len(bad)}")


# ------------------------------------------------------------------ colour ---
# Compose writes Color(0xFFRRGGBB); the deck writes #RRGGBB. Strip the alpha
# before comparing, or every single token reads as a mismatch (it did, once).
compose_colors = {
    m.group(1): "#" + m.group(2)[-6:].upper()
    for m in re.finditer(r'val (\w+) = Color\((0x[0-9A-Fa-f]{8})\)', theme)
}

COLOUR_MAP = [
    ("surface", "Surface"), ("onSurface", "OnSurface"),
    ("onSurfaceVariant", "OnSurfaceVariant"), ("cardSurface", "CardSurface"),
    ("surfaceVariant", "SurfaceVariant"),
    ("surfaceContainerLow", "SurfaceContainerLow"),
    ("surfaceContainer", "SurfaceContainer"),
    ("surfaceContainerHigh", "SurfaceContainerHigh"),
    ("surfaceContainerHighest", "SurfaceContainerHighest"),
    ("primary", "Primary"), ("primaryContainer", "PrimaryContainer"),
    ("onPrimaryContainer", "OnPrimaryContainer"), ("secondary", "Secondary"),
    ("secondaryContainer", "SecondaryContainer"),
    ("onSecondaryContainer", "OnSecondaryContainer"), ("tertiary", "Tertiary"),
    ("tertiaryContainer", "TertiaryContainer"),
    ("onTertiaryContainer", "OnTertiaryContainer"), ("error", "ErrorRed"),
    ("errorContainer", "ErrorContainer"), ("outline", "Outline"),
    ("outlineVariant", "OutlineVariant"), ("inverseSurface", "InverseSurface"),
    ("inverseOnSurface", "InverseOnSurface"), ("inversePrimary", "InversePrimary"),
    ("brandMark", "Brand"),
    ("vizSeries", "VizSeries"), ("vizInk", "VizInk"), ("vizGrid", "VizGrid"),
    ("vizTrack", "VizTrack"), ("vizBand", "VizBand"),
    ("vizBandEdge", "VizBandEdge"), ("vizDeviation", "VizDeviation"),
    ("vizThumb", "VizThumb"),
]

bad = []
for deck_key, kt_name in COLOUR_MAP:
    want = wf.C.get(deck_key) or (wf.BRAND_MARK if deck_key == "brandMark" else None)
    got = compose_colors.get(kt_name)
    if want is None:
        continue
    if got is None:
        bad.append(f"{deck_key:24} deck {want}  -> no Compose val `{kt_name}`")
    elif want.upper() != got:
        accepted = ACCEPTED_DEVIATIONS.get(deck_key)
        if accepted and accepted[0].upper() == got:
            deviations.append(f"{deck_key:24} deck {want.upper()}  app {got}"
                              f"  -- {accepted[1]}")
        else:
            bad.append(f"{deck_key:24} deck {want.upper()}  app {got}")

seq_block = re.search(r'VizSequential = listOf\((.*?)\n\)', theme, re.S)
app_seq = ["#" + x[-6:].upper() for x in re.findall(r'0x[0-9A-Fa-f]{8}', seq_block.group(1))]
if app_seq != [s.upper() for s in wf.SEQ]:
    bad.append(f"heatmap ramp        deck {wf.SEQ}  app {app_seq}")

# The simulator keeps its own copy of the ramp, the way it keeps its own copy of
# every other token, so that copy has to be diffed too: a hand-transcribed hex
# in a third file is precisely the drift this script exists to catch.
sim_seq = re.search(r'^SEQ = \[(.*?)\]', (HERE / "screenshots.py").read_text(), re.M | re.S)
sim = [s.upper() for s in re.findall(r'#[0-9A-Fa-f]{6}', sim_seq.group(1))] if sim_seq else []
if sim != app_seq:
    bad.append(f"heatmap ramp (sim)  app {app_seq}  screenshots.py {sim}")
report("colour tokens", bad, len(COLOUR_MAP) + 2)

# -------------------------------------------------------------------- type ---
# Theme.kt: role = TextStyle(fontFamily = X, fontSize = Nsp, fontWeight = W)
# A role with no explicit fontWeight is FontWeight.Normal (400).
WEIGHT = {"Normal": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
app_type = {}
for m in re.finditer(
    r'(\w+) = TextStyle\(fontFamily = \w+, fontSize = (\d+)\.sp'
    r'(?:, fontWeight = FontWeight\.(\w+))?\)', theme
):
    app_type[m.group(1)] = (int(m.group(2)), WEIGHT.get(m.group(3), 400))

bad = []
for role, (size, weight, _family) in sorted(wf.T.items()):
    got = app_type.get(role)
    if got is None:
        bad.append(f"{role:16} deck {size}sp/{weight}  -> role not defined in Theme.kt")
        continue
    if got != (size, weight):
        bad.append(f"{role:16} deck {size}sp/{weight}   app {got[0]}sp/{got[1]}")
report("type scale", bad, len(wf.T))

# ------------------------------------------------------------------- shape ---
SHAPE_MAP = {"card": "CardCorner", "sheet": "SheetCorner",
             "thumb": "ThumbCorner", "field": "FieldCorner"}
app_shape = {m.group(1): int(m.group(2))
             for m in re.finditer(r'val (\w+Corner) = (\d+)\.dp', theme)}
bad = []
for deck_key, kt_name in SHAPE_MAP.items():
    want, got = wf.SHAPE[deck_key], app_shape.get(kt_name)
    if want != got:
        bad.append(f"{deck_key:8} deck {want}dp  app {got}dp")
# chip has no Compose token at all -- M3 chips fall back to shapes.small
if "chip" in wf.SHAPE and wf.SHAPE["chip"] >= 999:
    if "ChipCorner" not in app_shape:
        bad.append("chip     deck pill (999)  app <no token; M3 chips inherit "
                   "shapes.small = FieldCorner>")
report("shape tokens", bad, len(SHAPE_MAP) + 1)

# --------------------------------------------------------------- simulator ---
# Every literal screenshots.py draws as copy must exist in the Kotlin (or, for
# the account sheet, in coffee_server). Sample DATA is exempt -- bean names and
# dates are invented here the way the deck invents its own.
#
# res/values/strings.xml IS PART OF THE SOURCE FOR THIS CHECK, and leaving it
# out is not a small omission. The localisation pass (AUDIT.md B2) moved every
# user-facing string out of the Kotlin and into the resources; a check that
# reads only *.kt therefore reported ~72 strings as "drawn but not in source"
# that were present all along, which is worse than no check at all -- a wall of
# false positives is how a real drift stops being noticed. Only `values/` is
# read: `values-fr/` and `values-zh/` are translations of these same strings,
# and the deck is drawn in English.
kt = "\n".join(p.read_text() for p in SRC.rglob("*.kt"))
kt += (HERE / "app/build.gradle.kts").read_text()
strings_xml = HERE / "app/src/main/res/values/strings.xml"
if strings_xml.exists():
    # Unescape the XML-and-Android escaping so a resource reads as the sentence
    # it renders as: \' and \" are Android's, &amp;/&lt;/&gt;/&#39; are XML's.
    xml_text = strings_xml.read_text()
    for esc, plain in ((r"\'", "'"), (r'\"', '"'), ("&amp;", "&"),
                       ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'"),
                       ("&quot;", '"')):
        xml_text = xml_text.replace(esc, plain)
    kt += "\n" + xml_text
if SERVER.exists():
    kt += "\n".join(p.read_text() for p in SERVER.glob("*.py"))
# Collapse whitespace, then dissolve every string-concat seam: Kotlin's
# `"a" + "b"`, Kotlin's implicit `"a" +\n "b"`, and Python's adjacent-literal
# `"a" "b"` in coffee_server all become one run of text. Without this, any
# sentence the source wraps across two lines reads as missing.
flat = re.sub(r'\s+', ' ', kt)
flat = re.sub(r'"\s*\+?\s*"', '', flat)

DATA = re.compile(
    r'^(?:[\d.,:\-–—/ ]+|.*\.png|--[a-z-]+=?.*|google-chrome.*|chromium.*)$|'
    r'Ethiopia|Colombia|Kenya|Guatemala|Terres|Lomi|Belleville|Coutume|Buku|'
    r'Heirloom|1 950|Hario|Kalita|Chemex|Origami|Comandan|clicks|'
    r'2026-|118207|Aug 2026|Tuesday|natural Ethiopian|Bright, clean|'
    r'swirl|centre pour|slow spiral|Blueberry|medium-fine|read the roaster|'
    r'Terre de Cafe'
)

tree = ast.parse((HERE / "screenshots.py").read_text())
lits: set[str] = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("text", "wrap") and len(node.args) > 2:
        arg = node.args[2]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            lits.add(arg.value)
        elif isinstance(arg, ast.BinOp):
            try:
                lits.add(ast.literal_eval(arg))
            except Exception:
                pass
for node in ast.walk(tree):
    if isinstance(node, (ast.Tuple, ast.List)):
        for e in node.elts:
            if isinstance(e, ast.Constant) and isinstance(e.value, str) and len(e.value) > 12:
                lits.add(e.value)

SVG_PATH = re.compile(r'^[Mm][\d{\s.-]')

# Strings the app assembles at runtime from values, so no contiguous literal
# exists to match. Each is listed with where its pieces actually come from, so
# an entry cannot quietly become cover for a fabrication.
COMPOSED = {
    # ProfileScreen/PrivacyScreen: "Questions: " + BuildConfig.SUPPORT_EMAIL
    "Questions: hello@coffeecan.app",
    # DataAccessSheet: "Daily limits: " + quotaPerDay.entries.joinToString{},
    # keys and values from coffee_server/config.py DAILY_QUOTA
    "Daily limits: ask 60, suggest 60, vision 40",
    # SuggestionSheet: "Written by AI (${result.provider}). Check it before
    # you brew." -- provider is a server response field
    "Written by AI (anthropic). Check it before you brew.",
}

bad, checked = [], 0
for s in sorted(lits):
    t = s.strip()
    if len(t) < 6 or DATA.search(t) or SVG_PATH.match(t) or t in COMPOSED:
        continue
    checked += 1
    probe = re.sub(r'\s+', ' ', t)[:52]
    if probe in flat:
        continue
    # The Kotlin interpolates ("Averaged from $sessions sessions …",
    # "its $n logged brews"). Retry with each rendered number treated as a
    # wildcard so it can match the placeholder that produced it. The escaped
    # space stays outside the wildcard -- `\S` cannot cross one.
    loose = re.escape(probe)
    loose = re.sub(r'\d[\d.,:–-]*', r'\\S{1,24}', loose)
    if re.search(loose, flat):
        continue
    bad.append(f'drawn but not in source: "{t[:70]}"')
report("simulator copy fidelity", bad, checked)

# ----------------------------------------------------------------- verdict ---
print()
if deviations:
    print("ACCEPTED DEVIATIONS (recorded decisions, not drift):")
    for line in deviations:
        print(f"  {line}")
    print()
if failures:
    print("DRIFT: " + "; ".join(failures))
    print("See plan/v1/design-spec.md §12. Layout and component choice are NOT "
          "covered here — render plan/screenshots/scheme-e/*.svg and compare "
          "by eye.")
    sys.exit(1)
print("no drift in the checked dimensions (colour, type, shape, mock fidelity)")
