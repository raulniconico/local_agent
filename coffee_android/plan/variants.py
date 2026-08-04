#!/usr/bin/env python3
"""Alternative colour schemes for the coffee_android deck.

Layout, type, motif and content are identical to the base deck — only the
token dict changes. Each scheme writes into its own subfolder of
`screenshots/`. Run from `plan/`:  python3 variants.py
"""
from __future__ import annotations
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wireframes as wf

BASE = pathlib.Path(__file__).resolve().parent / "screenshots"

# --------------------------------------------------------------------------
# A · "Orchard" — light green surfaces, the logo's own #34C759 as the main
# colour. #34C759 is 2.09:1 on the page, so it is used only as a FILL carrying
# dark ink (6.72:1); `primaryText` carries every text and thin-graphic use.
# --------------------------------------------------------------------------
ORCHARD = dict(
    primary="#34C759", onPrimary="#062E12", primaryText="#12662C",
    primaryContainer="#CBF2D3", onPrimaryContainer="#062E12",
    secondary="#59695C", secondaryContainer="#DCEAE0", onSecondaryContainer="#1A2A1E",
    tertiary="#8B5000", onTertiary="#FFFFFF",
    tertiaryContainer="#FFDCBF", onTertiaryContainer="#301B00",
    error="#AB3426", errorContainer="#FEDBD3",
    surface="#F3FAF4", onSurface="#14251A", onSurfaceVariant="#4C5B4F",
    cardSurface="#FFFFFF", surfaceContainerLow="#EDF7EF",
    surfaceContainer="#E4F2E7", surfaceContainerHigh="#D8EADC",
    surfaceContainerHighest="#CDE2D2", surfaceVariant="#E4F2E7",
    outline="#74857A", outlineVariant="#CFDFD3",
    inverseSurface="#2A382E", inverseOnSurface="#EDF7EF", inversePrimary="#7FE49A",
    scrim="#0C1A10", primaryOutline="#1E8A3E",
    dSurface="#101A13", dOnSurface="#E4EFE7", dOnSurfaceVariant="#BFCFC4",
    dPrimary="#7FE49A", dContainer="#1B2A20", dOutline="#3A4A3F",
    vizInk="#4C5B4F", vizGrid="#CFDFD3", vizTrack="#E4F2E7", vizSeries="#7E4A2E",
    vizUnder="#2A6FD6", vizWell="#12662C", vizOver="#C2410C", vizBand="#E4F2E7",
)

# --------------------------------------------------------------------------
# B · "Bright" — white page, green accent. Cards carry a faint green tint so
# they separate from a pure-white background without an outline.
# --------------------------------------------------------------------------
BRIGHT = dict(
    primary="#1B7F3B", onPrimary="#FFFFFF", primaryText="#1B7F3B",
    primaryContainer="#C6EFCF", onPrimaryContainer="#04310E",
    secondary="#5A635C", secondaryContainer="#E3E9E4", onSecondaryContainer="#1A211C",
    tertiary="#8B5000", onTertiary="#FFFFFF",
    tertiaryContainer="#FFDCBF", onTertiaryContainer="#301B00",
    error="#AB3426", errorContainer="#FEDBD3",
    surface="#FFFFFF", onSurface="#1A1C1A", onSurfaceVariant="#4A5250",
    cardSurface="#F6FAF7", surfaceContainerLow="#F6FAF7",
    surfaceContainer="#ECF3EE", surfaceContainerHigh="#E3EBE5",
    surfaceContainerHighest="#DAE3DC", surfaceVariant="#ECF3EE",
    outline="#757E78", outlineVariant="#DCE4DE",
    inverseSurface="#2E322F", inverseOnSurface="#F1F4F1", inversePrimary="#89D890",
    scrim="#0E1410",
    dSurface="#121513", dOnSurface="#E4E8E5", dOnSurfaceVariant="#C1C8C3",
    dPrimary="#89D890", dContainer="#1E221F", dOutline="#3C433E",
    vizInk="#4A5250", vizGrid="#DCE4DE", vizTrack="#ECF3EE", vizSeries="#7E4A2E",
    vizUnder="#2A6FD6", vizWell="#1B7F3B", vizOver="#C2410C", vizBand="#ECF3EE",
)


# --------------------------------------------------------------------------
# C · "Pure green" — one hue family, no brown in the chrome. Merged from three
# specialist rulings; where they conflicted the measured argument won:
#   primary  #196D2E  (2 of 3, and continuity with the shipped scheme)
#   surface  #F2FAF2  (the only ramp anyone measured end to end)
#   error    #84241A  darkened to tone 30 — #AB3426 computes 6.07:1 but
#                     simulates to 2.99:1 for deuteranopes, because WCAG's
#                     luminance coefficients don't model reduced long-
#                     wavelength sensitivity. This is the one non-green.
#   tertiary #016B53  nudged 25 deg toward teal: three container families at
#                     one hue measure dE 7.8 and are not tellable apart. The
#                     yellow rotation was rejected — it reads olive, i.e.
#                     brown by another name.
# Data marks live below L* 80 so charts separate from chrome (L* 86-100).
# --------------------------------------------------------------------------
PURE_GREEN = dict(
    primary="#196D2E", onPrimary="#FFFFFF", primaryText="#196D2E",
    primaryContainer="#C3EDC5", onPrimaryContainer="#002602",
    secondary="#556855", secondaryContainer="#E3F6E3", onSecondaryContainer="#233524",
    tertiary="#016B53", onTertiary="#FFFFFF",
    tertiaryContainer="#9FECD1", onTertiaryContainer="#002A1E",
    error="#84241A", errorContainer="#FEDED7",
    surface="#F2FAF2", onSurface="#1B241C", onSurfaceVariant="#515D51",
    cardSurface="#FFFFFF", surfaceContainerLow="#EAF5EA",
    surfaceContainer="#E0EFE1", surfaceContainerHigh="#D4E6D4",
    surfaceContainerHighest="#C9DCCA", surfaceVariant="#DCECDD",
    outline="#6D7B6D", outlineVariant="#C3D3C4",
    inverseSurface="#323C32", inverseOnSurface="#EAF3EA", inversePrimary="#89D890",
    scrim="#06140A", primaryOutline=None,
    camGround="#101A12", cardInk="#F2FAF2", cardInkDim="#C3D3C4",
    radarInk="#89D890",
    dSurface="#121912", dOnSurface="#DDE5DD", dOnSurfaceVariant="#BDCABD",
    dPrimary="#89D890", dContainer="#1D261E", dOutline="#3E4A3E",
    vizInk="#515D51", vizGrid="#C3D3C4", vizTrack="#E0EFE1",
    # data green sits a tone band clear of primary so "a bar" never reads
    # as "a button" (dE 11.8 / CVD 11.4)
    vizSeries="#2B9343",
    # inverted meter: chroma itself means "on target"
    vizBand="#B0E8B6", vizBandEdge="#43A756",
    vizDeviation="#506051", vizThumb="#152817",
)
PURE_GREEN_SEQ = ["#EBF2EC", "#AADBAF", "#65B972", "#299141", "#155E27"]

SCHEMES = [("scheme-a-light-green", ORCHARD, None),
           ("scheme-b-green-white", BRIGHT, None),
           ("scheme-c-pure-green", PURE_GREEN, PURE_GREEN_SEQ)]
_BASE_TOKENS = dict(wf.C)
_BASE_SEQ = list(wf.SEQ)

if __name__ == "__main__":
    for folder, tokens, seq in SCHEMES:
        out = BASE / folder
        out.mkdir(parents=True, exist_ok=True)
        wf.C.clear(); wf.C.update(_BASE_TOKENS); wf.C.update(tokens)
        wf.SEQ[:] = seq if seq else _BASE_SEQ
        wf.OUT = out
        for name, fn in wf.SCREENS:
            (out / name).write_text(fn().render())
        print(f"{folder}: {len(wf.SCREENS)} frames")
    wf.C.clear(); wf.C.update(_BASE_TOKENS); wf.SEQ[:] = _BASE_SEQ
