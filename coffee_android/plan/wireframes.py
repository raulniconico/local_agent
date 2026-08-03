#!/usr/bin/env python3
"""coffee_android wireframe generator — art direction "Cupping Table".

Canvas is 360 x 800 dp: 1 SVG unit == 1 dp on a baseline Android phone, so
every number in the output is a buildable spec rather than a drawing.
"""
from __future__ import annotations
import math, pathlib, html

OUT = pathlib.Path(__file__).resolve().parent / "screenshots"

W, H = 360, 800
STATUS_H, BAR_H, GESTURE_H = 24, 64, 24
GUTTER = 16

# ---------------------------------------------------------------- tokens ----
C = dict(
    primary="#B4401F", onPrimary="#FFFFFF",
    primaryContainer="#FFDFD2", onPrimaryContainer="#3E1207",
    secondary="#6B5B4E", secondaryContainer="#F0E5DA", onSecondaryContainer="#2A211A",
    tertiary="#2E6B4E", tertiaryContainer="#CFE9DA", onTertiaryContainer="#0B3F1E",
    error="#A32A1D", errorContainer="#FFDAD4",
    surface="#FAF7F2", onSurface="#211A15", onSurfaceVariant="#5C5147",
    cardSurface="#FFFFFF", surfaceContainer="#F3ECE3", surfaceVariant="#EFE7DC",
    outline="#8C7F72", outlineVariant="#DFD5C9",
    scrim="#1A120C",
    # dark (camera surfaces)
    dSurface="#14100D", dOnSurface="#F2EAE1", dOnSurfaceVariant="#C6B7A9",
    dPrimary="#FF8A5C", dContainer="#1E1815", dOutline="#3A302A",
    # viz
    vizInk="#5C5147", vizGrid="#DFD5C9", vizTrack="#EFE7DC", vizSeries="#B4401F",
    vizUnder="#2A6FD6", vizOver="#C2410C", vizBand="#EFE7DC",
)
# roast ramp for the activity heatmap: t0 is a NEUTRAL warm grey (absence),
# t1..t4 descend monotonically in lightness so the scale survives CVD.
SEQ = ["#E8E1D7", "#F2C9A8", "#E09A62", "#C0651F", "#7E340D"]

FD = "Fraunces,'Noto Serif Display',Georgia,serif"       # display / headline
FU = "Inter,'Liberation Sans','DejaVu Sans',sans-serif"  # UI / body
FM = "'IBM Plex Mono','DejaVu Sans Mono',monospace"      # tabular

# type roles: (size, weight, family)
T = dict(
    displaySmall=(36, 600, FD), headlineMedium=(28, 600, FD), headlineSmall=(22, 600, FD),
    titleLarge=(22, 600, FD), titleMedium=(16, 600, FU), titleSmall=(14, 600, FU),
    bodyLarge=(16, 400, FU), bodyMedium=(14, 400, FU),
    labelLarge=(14, 600, FU), labelMedium=(12, 600, FU), labelSmall=(11, 500, FU),
)
R_XS, R_SM, R_MD, R_LG, R_XL = 4, 8, 12, 16, 28

FLAVOR = ["Fruity", "Floral", "Tea-like", "Sweet", "Nutty/Cocoa", "Spices",
          "Roasted", "Cereal", "Green/Veg.", "Sour", "Fermented"]


# ------------------------------------------------------------- primitives ---
class Canvas:
    def __init__(self, title, bg=None):
        self.title, self.bg = title, bg or C["surface"]
        self.defs, self.body, self._uid = [], [], 0

    def uid(self, p="i"):
        self._uid += 1
        return f"{p}{self._uid}"

    def add(self, s): self.body.append(s)

    def render(self):
        d = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
                f'width="{W}" height="{H}" font-family="{FU}">\n'
                f'<title>{esc(self.title)}</title>\n{d}\n'
                f'<rect width="{W}" height="{H}" fill="{self.bg}"/>\n'
                + "\n".join(self.body) + "\n</svg>\n")


def esc(s): return html.escape(str(s), quote=False)


def text(c, x, y, s, role="bodyMedium", fill=None, anchor="start", family=None,
         size=None, weight=None, opacity=None, letter=None):
    fs, fw, fam = T[role]
    fs, fw, fam = size or fs, weight or fw, family or fam
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    o = f' opacity="{opacity}"' if opacity else ""
    ls = f' letter-spacing="{letter}"' if letter else ""
    c.add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{fs}" '
          f'font-weight="{fw}" fill="{fill or C["onSurface"]}"{a}{o}{ls}>{esc(s)}</text>')


def rect(c, x, y, w, h, fill, r=0, stroke=None, sw=1, dash=None, opacity=None):
    at = f' rx="{r}"' if r else ""
    at += f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    at += f' stroke-dasharray="{dash}"' if dash else ""
    at += f' opacity="{opacity}"' if opacity else ""
    c.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"{at}/>')


def line(c, x1, y1, x2, y2, stroke=None, sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    c.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
          f'stroke="{stroke or C["outlineVariant"]}" stroke-width="{sw}"{d}/>')


def circle(c, cx, cy, r, fill, stroke=None, sw=1, opacity=None):
    at = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    at += f' opacity="{opacity}"' if opacity else ""
    c.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{at}/>')


def path(c, d, fill="none", stroke=None, sw=1, rule=None, opacity=None):
    at = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    at += f' fill-rule="{rule}"' if rule else ""
    at += f' opacity="{opacity}"' if opacity else ""
    c.add(f'<path d="{d}" fill="{fill}"{at}/>')


# ------------------------------------------------------------- components ---
def status_bar(c, dark=False):
    ink = C["dOnSurfaceVariant"] if dark else C["onSurfaceVariant"]
    text(c, GUTTER, 16, "8:24", "labelSmall", ink)
    for i, hh in enumerate((4, 6, 8, 10)):           # signal
        rect(c, 296 + i * 5, 15 - hh + 6, 3, hh, ink, 1)
    path(c, "M320 15 q5 -4 10 0 M323 18 q2.5 -2 5 0", stroke=ink, sw=1.4)  # wifi
    rect(c, 334, 9, 18, 9, "none", 2, stroke=ink, sw=1)
    rect(c, 336, 11, 11, 5, ink, 1)


def gesture_bar(c, dark=False):
    rect(c, (W - 108) / 2, 790, 108, 4, C["dOutline"] if dark else C["outline"], 2,
         opacity=0.5)


def crescent(c, cx, cy, size, fill):
    """Brand mark: a filled crescent with the bean's centre crease as negative space."""
    mid = c.uid("cres")
    r = size / 2
    c.defs.append(
        f'<mask id="{mid}"><rect x="{cx-r-2}" y="{cy-r-2}" width="{size+4}" '
        f'height="{size+4}" fill="#fff"/>'
        f'<circle cx="{cx + r*0.42}" cy="{cy - r*0.30}" r="{r*0.86}" fill="#000"/>'
        f'</mask>')
    c.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" mask="url(#{mid})"/>')
    path(c, f"M{cx-r*0.62} {cy+r*0.52} Q{cx-r*0.05} {cy+r*0.02} "
            f"{cx+r*0.30} {cy+r*0.66}", stroke=fill, sw=size * 0.075, opacity=0.55)


def top_bar(c, title, back=False, actions=(), brand=False, ink=None, bg=None):
    ink = ink or C["onSurface"]
    if bg:
        rect(c, 0, STATUS_H, W, BAR_H, bg)
    cy = STATUS_H + BAR_H / 2
    tx = GUTTER
    if back:
        path(c, f"M{GUTTER+16} {cy-7} l-7 7 l7 7", stroke=ink, sw=2)
        tx = GUTTER + 40
    elif brand:
        crescent(c, GUTTER + 12, cy, 24, C["primary"])
        tx = GUTTER + 34
    text(c, tx, cy + 8, title,
         "titleLarge" if brand else ("headlineSmall" if not back else "titleMedium"),
         ink)
    x = W - GUTTER - 24
    for kind in reversed(actions):
        _bar_action(c, x, cy, kind, ink)
        x -= 48
    line(c, 0, STATUS_H + BAR_H, W, STATUS_H + BAR_H)


def _bar_action(c, x, cy, kind, ink):
    """48dp touch target, 24dp glyph."""
    if kind == "avatar":
        circle(c, x, cy, 15, C["secondaryContainer"])
        text(c, x, cy + 5, "Z", "labelLarge", C["onSecondaryContainer"], "middle")
    elif kind == "share":
        path(c, f"M{x} {cy+7} v-13 m0 -1 l-5 5 m5 -5 l5 5", stroke=ink, sw=2)
        path(c, f"M{x-8} {cy+1} v7 h16 v-7", stroke=ink, sw=2)
    elif kind == "close":
        path(c, f"M{x-7} {cy-7} l14 14 M{x+7} {cy-7} l-14 14", stroke=ink, sw=2)
    elif kind == "sort":
        for i, ww in enumerate((14, 10, 6)):
            line(c, x - 7, cy - 5 + i * 5, x - 7 + ww, cy - 5 + i * 5, ink, 2)


def section(c, y, label, action=None):
    text(c, 20, y, label, "titleSmall", C["onSurface"])
    if action:
        text(c, W - 20, y, action, "labelLarge", C["primary"], "end")


def card(c, y, h, x=GUTTER, w=W - 2 * GUTTER, r=R_LG, fill=None):
    rect(c, x, y, w, h, fill or C["cardSurface"], r)
    return y + h


def button(c, x, y, w, label, kind="filled", enabled=True, h=48):
    """48dp touch target. Pill shape is reserved for the primary action."""
    vh, vy = 40, y + (h - 40) / 2
    if kind == "filled":
        fill = C["primary"] if enabled else C["surfaceContainer"]
        ink = C["onPrimary"] if enabled else C["outline"]
        rect(c, x, vy, w, vh, fill, vh / 2)
    elif kind == "tonal":
        fill, ink = C["secondaryContainer"], C["onSecondaryContainer"]
        rect(c, x, vy, w, vh, fill, R_SM)
    elif kind == "outlined":
        ink = C["onSurface"]
        rect(c, x, vy, w, vh, "none", R_SM, stroke=C["outline"])
    elif kind == "danger":
        ink = C["error"]
        rect(c, x, vy, w, vh, "none", R_SM, stroke=C["error"])
    elif kind == "disabled":
        ink = C["outline"]
        rect(c, x, vy, w, vh, C["surfaceContainer"], R_SM)
    else:  # text
        ink = C["primary"]
    text(c, x + w / 2, vy + 25, label, "labelLarge", ink, "middle")


def field(c, x, y, w, label, value, placeholder=False):
    """The score-sheet motif: label above a hairline rule, value below."""
    text(c, x, y, label, "labelMedium", C["onSurfaceVariant"], letter=0.4)
    line(c, x, y + 8, x + w, y + 8)
    text(c, x, y + 30, value if value else "—", "bodyLarge",
         C["outline"] if (placeholder or not value) else C["onSurface"])


def textfield(c, x, y, w, label, value, h=56, required=False, focused=False):
    """M3 outlined text field, 56dp."""
    stroke = C["primary"] if focused else C["outline"]
    rect(c, x, y, w, h, C["cardSurface"], R_SM, stroke=stroke, sw=2 if focused else 1)
    rect(c, x + 12, y - 6, len(label) * 6.6 + 8, 12, C["cardSurface"])
    text(c, x + 16, y + 4, label + ("*" if required else ""), "labelMedium",
         C["primary"] if focused else C["onSurfaceVariant"])
    text(c, x + 16, y + 36, value if value else "—", "bodyLarge",
         C["onSurface"] if value else C["outline"])
    if focused:
        line(c, x + 16 + len(value) * 8.2, y + 22, x + 16 + len(value) * 8.2, y + 42,
             C["primary"], 2)


def chip(c, x, y, label, selected=False, menu=False, h=48):
    """32dp visual inside a 48dp touch target."""
    vh, vy = 32, y + 8
    tw = len(label) * 7.0 + (44 if (selected or menu) else 28)
    if selected:
        rect(c, x, vy, tw, vh, C["primaryContainer"], vh / 2)
        path(c, f"M{x+14} {vy+16} l4 4 l8 -9", stroke=C["onPrimaryContainer"], sw=2)
        text(c, x + 32, vy + 21, label, "labelLarge", C["onPrimaryContainer"])
    else:
        rect(c, x, vy, tw, vh, "none", vh / 2, stroke=C["outline"])
        text(c, x + 14, vy + 21, label, "labelLarge", C["onSurface"])
        if menu:
            path(c, f"M{x+tw-24} {vy+14} l5 6 l5 -6", stroke=C["onSurfaceVariant"], sw=2)
    return x + tw + 8


def photo(c, x, y, w, h, r=R_MD, label=None):
    """Placeholder standing in for a real bag photo."""
    gid = c.uid("ph")
    c.defs.append(
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="#D8CCBE"/><stop offset="1" stop-color="#A9968，4"/>'
        f'</linearGradient>')
    c.defs[-1] = c.defs[-1].replace("#A9968，4", "#A99684")
    rect(c, x, y, w, h, f"url(#{gid})", r)
    hid = c.uid("hl")
    c.defs.append(f'<radialGradient id="{hid}" cx="0.34" cy="0.28" r="0.75">'
                  f'<stop offset="0" stop-color="#FFFFFF" stop-opacity="0.34"/>'
                  f'<stop offset="1" stop-color="#3B2A1C" stop-opacity="0.26"/>'
                  f'</radialGradient>')
    rect(c, x, y, w, h, f"url(#{hid})", r)
    rect(c, x, y, w, h, "none", r, stroke=C["onSurface"], sw=1, opacity=0.08)
    if label:
        text(c, x + w / 2, y + h / 2 + 4, label, "labelSmall", "#6C5C4C", "middle")


def origin_tile(c, x, y, w, h, code, r=R_MD):
    """Deterministic fallback when a bean has no photo — never a grey box."""
    gid = c.uid("ot")
    seed = sum(ord(ch) for ch in code)
    a = ["#E3D3C0", "#DCC9B4", "#E8D8C4", "#D9CBBA"][seed % 4]
    b = ["#B58A5E", "#9E7A55", "#C29A6B", "#8E7457"][(seed // 3) % 4]
    c.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0.9" y2="1">'
                  f'<stop offset="0" stop-color="{a}"/>'
                  f'<stop offset="1" stop-color="{b}"/></linearGradient>')
    rect(c, x, y, w, h, f"url(#{gid})", r)
    text(c, x + w / 2, y + h / 2 + h * 0.16, code, "headlineMedium", C["onSurface"],
         "middle", size=h * 0.42, opacity=0.40)


def bean_row(c, y, name, meta, sessions, code=None, h=88):
    """Logbook row: every bean has a picture. No exceptions."""
    if code:
        origin_tile(c, GUTTER, y + 12, 64, 64, code)
    else:
        photo(c, GUTTER, y + 12, 64, 64)
    text(c, 92, y + 38, name, "titleMedium")
    text(c, 92, y + 60, meta, "bodyMedium", C["onSurfaceVariant"])
    text(c, W - 34, y + 50, sessions, "labelMedium", C["onSurfaceVariant"], "end")
    path(c, f"M{W-24} {y+43} l5 5 l-5 5", stroke=C["outline"], sw=1.6)
    line(c, 92, y + h, W, y + h)
    return y + h


# ------------------------------------------------------------------- viz ----
def flavor_bars(c, x, y, w, values, rows=None, pitch=28, gutter=90):
    """11-row horizontal bars. Replaces the radar everywhere except the export."""
    labels = FLAVOR if rows is None else [FLAVOR[i] for i in rows]
    vals = values if rows is None else [values[i] for i in rows]
    tx, tw = x + gutter, w - gutter
    top = [i for i, _ in sorted(enumerate(vals), key=lambda kv: -kv[1])[:2]]
    for i in range(6):                                    # fixed 0..5 scale
        gx = tx + i * tw / 5
        line(c, gx, y - 2, gx, y + len(vals) * pitch - 8, C["vizGrid"], 1)
    for i, (lab, v) in enumerate(zip(labels, vals)):
        by = y + i * pitch
        text(c, tx - 10, by + 8, lab, "labelSmall", C["vizInk"], "end")
        rect(c, tx, by, tw, 10, C["vizTrack"], R_XS)
        bw = max(2, v / 5 * tw)
        rect(c, tx, by, bw, 10, C["vizSeries"], R_XS)
        rect(c, tx, by, min(bw, 4), 10, C["vizSeries"])   # square at the baseline
        if i in top:
            text(c, tx + bw + 6, by + 9, f"{v:.1f}", "labelSmall", C["onSurfaceVariant"])
    ay = y + len(vals) * pitch
    text(c, tx, ay + 4, "0", "labelSmall", C["vizInk"], "middle")
    text(c, tx + tw, ay + 4, "5", "labelSmall", C["vizInk"], "middle")
    return ay + 12


def heatmap(c, x, y, w, weeks=21, cell=11, gap=2):
    """Calendar heatmap with the weekday axis, month axis and legend restored."""
    import random
    random.seed(7)
    pitch = cell + gap
    gx = x + 30
    weeks = min(weeks, int((x + w - gx) // pitch))
    for m, wk in (("May", 0), ("Jun", 5), ("Jul", 9), ("Aug", 14)):
        text(c, gx + wk * pitch, y - 4, m, "labelSmall", C["vizInk"])
    for i, d in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
        text(c, gx - 8, y + i * pitch + cell - 1, d, "labelSmall", C["vizInk"], "end")
    for wk in range(weeks):
        for d in range(7):
            t = 0 if random.random() < 0.52 else random.randint(1, 4)
            rect(c, gx + wk * pitch, y + d * pitch, cell, cell, SEQ[t], 2)
    ly = y + 7 * pitch + 16
    lx = x + w - 12
    text(c, lx, ly, "More", "labelSmall", C["vizInk"], "end")
    lx -= 34
    for t in range(4, -1, -1):
        rect(c, lx - 11, ly - 9, 11, 11, SEQ[t], 2)
        lx -= 13
    text(c, lx - 4, ly, "Less", "labelSmall", C["vizInk"], "end")
    return ly + 8


def extraction(c, x, y, w, value, readout, unset=False):
    """Bipolar meter. Hue encodes direction only; distance encodes severity."""
    th, cy = 12, y + 6
    rect(c, x, y, w, th, C["vizTrack"], th / 2)
    b0, b1 = x + w / 3, x + 2 * w / 3
    rect(c, b0, y, b1 - b0, th, C["vizBand"], 0)
    line(c, b0, y, b0, y + th, C["outline"], 1)
    line(c, b1, y, b1, y + th, C["outline"], 1)
    mid = x + w / 2
    line(c, mid, y - 3, mid, y + th + 3, C["outline"], 1)
    if not unset:
        vx = mid + value * (w / 2)
        col = C["vizUnder"] if value < 0 else C["vizOver"]
        rect(c, min(mid, vx), y, abs(vx - mid), th, col, 0)
        rect(c, vx - 2, y - 4, 4, th + 8, C["surface"], 3)
        rect(c, vx - 2, y - 4, 4, th + 8, C["onSurface"], 3)
    text(c, x, y - 12, readout, "labelLarge",
         C["outline"] if unset else C["onSurface"])
    for lx, an, lab, hot in ((x, "start", "Under", value < -1 / 3 and not unset),
                             (mid, "middle", "Well extracted",
                              -1 / 3 <= value <= 1 / 3 and not unset),
                             (x + w, "end", "Over", value > 1 / 3 and not unset)):
        text(c, lx, y + th + 18, lab, "labelSmall",
             C["onSurface"] if hot else C["onSurfaceVariant"], an,
             weight=600 if hot else 500)
    return y + th + 26


def _star(cx, cy, r):
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        rr = r if i % 2 == 0 else r * 0.42
        pts.append(f"{cx + rr*math.cos(a):.2f},{cy + rr*math.sin(a):.2f}")
    return "M" + "L".join(pts) + "Z"


def stars(c, x, y, score, size=24, gap=8):
    """Half-step stars with an explicit unset state — 5 empty stars must never
    read as 'scored 0'."""
    unset = score is None
    for i in range(5):
        cx, cy, r = x + i * (size + gap) + size / 2, y + size / 2, size / 2
        d = _star(cx, cy, r)
        path(c, d, "none", stroke=C["outline"], sw=1.4)
        if unset:
            continue
        fill = min(max(score - i, 0), 1)
        if fill <= 0:
            continue
        cid = c.uid("st")
        c.defs.append(f'<clipPath id="{cid}"><rect x="{cx-r}" y="{cy-r-1}" '
                      f'width="{2*r*fill}" height="{2*r+2}"/></clipPath>')
        c.add(f'<path d="{d}" fill="{C["primary"]}" clip-path="url(#{cid})"/>')
    rx = x + 5 * (size + gap) + 4
    text(c, rx, y + size / 2 + 6, "Not rated" if unset else f"{score:.1f} / 5",
         "labelLarge", C["outline"] if unset else C["onSurface"])


def radar11(c, cx, cy, r, values, stroke, ink, fill_op=0.16, labels=True):
    """Kept for the share-card export only: 1080px output, shape-as-signature,
    comparison is not the job."""
    n = len(values)
    ang = lambda i: math.radians(-90 + i * 360 / n)
    for ring in range(1, 6):
        rr = r * ring / 5
        pts = " ".join(f"{cx+rr*math.cos(ang(i)):.1f},{cy+rr*math.sin(ang(i)):.1f}"
                       for i in range(n))
        c.add(f'<polygon points="{pts}" fill="none" stroke="{ink}" '
              f'stroke-width="0.75" opacity="0.35"/>')
    for i in range(n):
        line(c, cx, cy, cx + r * math.cos(ang(i)), cy + r * math.sin(ang(i)),
             ink, 0.75)
    pts = []
    for i, v in enumerate(values):
        rr = r * v / 5
        pts.append(f"{cx+rr*math.cos(ang(i)):.1f},{cy+rr*math.sin(ang(i)):.1f}")
    c.add(f'<polygon points="{" ".join(pts)}" fill="{stroke}" '
          f'fill-opacity="{fill_op}" stroke="{stroke}" stroke-width="2" '
          f'stroke-linejoin="round"/>')
    for p in pts:
        x, yy = p.split(",")
        circle(c, x, yy, 2.4, stroke)
    if not labels:
        return
    short = ["Fruity", "Floral", "Tea", "Sweet", "Nutty", "Spices", "Roasted",
             "Cereal", "Green", "Sour", "Ferment"]
    for i, lab in enumerate(short):
        a = ang(i)
        lx, ly = cx + (r + 16) * math.cos(a), cy + (r + 16) * math.sin(a) + 3.5
        cos = math.cos(a)
        anchor = "middle" if abs(cos) < 0.25 else ("start" if cos > 0 else "end")
        text(c, round(lx, 1), round(ly, 1), lab, "labelSmall", ink, anchor)


def ext_link(c, x, y, col=None):
    col = col or C["outline"]
    path(c, f"M{x} {y+4} v7 h11 v-7", stroke=col, sw=1.4)
    path(c, f"M{x+4} {y+6} l7 -6 M{x+6} {y} h5 v5", stroke=col, sw=1.4)


def flash(c, cx, cy, col="#FFFFFF"):
    path(c, f"M{cx+2} {cy-9} l-7 11 h5 l-2 7 l7 -11 h-5 z", fill=col)


def scrim(c, op=0.6):
    rect(c, 0, 0, W, H, C["scrim"], opacity=op)


def sheet(c, top, r=R_XL, fill=None):
    gid = c.uid("sh")
    c.defs.append(f'<clipPath id="{gid}"><rect x="0" y="{top}" width="{W}" '
                  f'height="{H-top}"/></clipPath>')
    rect(c, 0, top, W, (H - top) + r, fill or C["surface"], r)
    rect(c, (W - 32) / 2, top + 12, 32, 4, C["outline"], 2, opacity=0.5)


def note(c, y, msg, kind="info"):
    """Inline, in-product messaging — never a developer annotation on the canvas."""
    bg = {"info": C["secondaryContainer"], "warn": C["errorContainer"]}[kind]
    ink = {"info": C["onSecondaryContainer"], "warn": C["error"]}[kind]
    lines = msg.split("|")
    h = 20 + len(lines) * 18
    rect(c, GUTTER, y, W - 2 * GUTTER, h, bg, R_MD)
    circle(c, GUTTER + 20, y + 20, 8, "none", stroke=ink, sw=1.5)
    text(c, GUTTER + 20, y + 24, "!", "labelMedium", ink, "middle")
    for i, ln in enumerate(lines):
        text(c, GUTTER + 38, y + 25 + i * 18, ln, "bodyMedium", ink)
    return y + h


def caption(c, y, msg):
    """Spec annotation — lives in the gutter BELOW the device frame, never inside it."""
    text(c, GUTTER, y, msg, "labelSmall", C["outline"])


def spinner(c, cx, cy, r, col):
    path(c, f"M{cx} {cy-r} a{r} {r} 0 1 1 {-r*0.7:.1f} {r*0.29:.1f}",
         stroke=col, sw=3)


BEAN_FLAVOR = [4.6, 3.9, 2.4, 4.1, 1.8, 1.2, 1.5, 1.0, 0.6, 2.9, 3.4]


# =========================================================== 01 · Home ======
def home():
    c = Canvas("Home — Cupping Table")
    status_bar(c)
    top_bar(c, "Coffee Can", brand=True, actions=("avatar",))
    section(c, 116, "Your beans", "Search")
    y = 132
    y = bean_row(c, y, "Ethiopia Guji Natural", "Natural · Roasted 28 Jul", "4 brews")
    y = bean_row(c, y, "Colombia Huila Washed", "Washed · Roasted 20 Jul", "2 brews")
    y = bean_row(c, y, "Kenya Nyeri AB", "Washed · Roasted 02 Aug", "No brews yet",
                 code="KE")
    section(c, 428, "Brewing activity")
    card(c, 442, 140)
    heatmap(c, 28, 474, 304)
    section(c, 614, "Your palate", "See all 11")
    card(c, 628, 144)
    idx = sorted(range(11), key=lambda i: -BEAN_FLAVOR[i])[:4]
    flavor_bars(c, 28, 648, 292, BEAN_FLAVOR, rows=idx, gutter=76)
    # FAB, clear of the bar tips — the only pill-shaped thing on the screen
    circle(c, 312, 716, 28, C["primary"])
    path(c, "M300 716 h24 M312 704 v24", stroke=C["onPrimary"], sw=2.6)
    gesture_bar(c)
    return c


def home_empty():
    c = Canvas("Home · empty state")
    status_bar(c)
    top_bar(c, "Coffee Can", brand=True, actions=("avatar",))
    crescent(c, 180, 296, 96, C["primary"])
    c.body[-2] = c.body[-2].replace(f'fill="{C["primary"]}"',
                                    f'fill="{C["primaryContainer"]}"')
    text(c, 180, 396, "No beans yet", "headlineMedium", C["onSurface"], "middle")
    for i, ln in enumerate(("Add the bag you're brewing this week and",
                            "start keeping the log.")):
        text(c, 180, 430 + i * 22, ln, "bodyLarge", C["onSurfaceVariant"], "middle")
    button(c, 76, 480, 208, "Add your first bean")
    gesture_bar(c)
    return c


# ==================================================== 02 · Bean Detail ======
def bean_detail():
    c = Canvas("Bean Detail — hero + score sheet")
    photo(c, 0, 0, W, 300, r=0)
    gid = c.uid("fade")
    c.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                  f'<stop offset="0" stop-color="{C["surface"]}" stop-opacity="0"/>'
                  f'<stop offset="1" stop-color="{C["surface"]}" stop-opacity="0.9"/>'
                  f'</linearGradient>')
    rect(c, 0, 170, W, 130, f"url(#{gid})")
    tid = c.uid("top")                      # keeps the status bar legible on any photo
    c.defs.append(f'<linearGradient id="{tid}" x1="0" y1="0" x2="0" y2="1">'
                  f'<stop offset="0" stop-color="{C["scrim"]}" stop-opacity="0.55"/>'
                  f'<stop offset="1" stop-color="{C["scrim"]}" stop-opacity="0"/>'
                  f'</linearGradient>')
    rect(c, 0, 0, W, 96, f"url(#{tid})")
    status_bar(c, dark=True)
    for cx, kind in ((36, "back"), (324, "share")):
        circle(c, cx, 52, 20, C["scrim"], opacity=0.45)
    path(c, "M40 45 l-7 7 l7 7", stroke="#FFFFFF", sw=2)
    path(c, "M324 59 v-13 m0 -1 l-5 5 m5 -5 l5 5", stroke="#FFFFFF", sw=2)
    path(c, "M316 53 v7 h16 v-7", stroke="#FFFFFF", sw=2)

    sheet(c, 272)
    text(c, 20, 322, "Ethiopia Guji", "headlineMedium")
    text(c, 20, 354, "Natural", "headlineMedium")
    text(c, 20, 380, "Guji, Ethiopia · Natural · Roasted 28 Jul", "bodyMedium",
         C["onSurfaceVariant"])
    line(c, 20, 400, 340, 400)
    rows = (("Variety", "Heirloom", "Altitude", "1 950 m"),
            ("Roaster", "Belleville", "Producer", ""),
            ("Process", "Natural", "Roast date", "28 Jul 2026"))
    for i, (l1, v1, l2, v2) in enumerate(rows):
        ry = 428 + i * 60
        field(c, 20, ry, 145, l1, v1)
        field(c, 195, ry, 145, l2, v2)
    section(c, 632, "Flavor", "Set manually")
    card(c, 648, 124)
    flavor_bars(c, 28, 664, 304, BEAN_FLAVOR, rows=[0, 1, 3])
    text(c, 332, 782, "all 11 axes below", "labelSmall", C["outline"], "end")
    return c


def bean_detail_lower():
    c = Canvas("Bean Detail — flavor, documents, sessions")
    status_bar(c)
    top_bar(c, "Ethiopia Guji Natural", back=True, actions=("share",))
    section(c, 116, "Flavor", "Set manually")
    card(c, 130, 326)
    flavor_bars(c, 28, 150, 304, BEAN_FLAVOR, pitch=26)
    text(c, 20, 474, "Averaged from 4 sessions · fixed axis order, 0–5 scale",
         "labelSmall", C["onSurfaceVariant"])
    section(c, 512, "Documents")
    for i, (x, rot) in enumerate(((20, -1.5), (104, 1.2), (188, -0.8))):
        c.add(f'<g transform="rotate({rot} {x+38} {572})">')
        rect(c, x + 2, 526, 76, 96, C["scrim"], 2, opacity=0.10)
        rect(c, x, 524, 76, 96, C["cardSurface"], 2, stroke=C["outlineVariant"])
        for k in range(5):
            line(c, x + 9, 544 + k * 13, x + 67 - (k % 2) * 16, 544 + k * 13,
                 C["outlineVariant"], 2)
        c.add("</g>")
    rect(c, 276, 524, 68, 96, C["secondaryContainer"], R_SM)
    path(c, "M304 562 h12 M310 556 v12", stroke=C["onSecondaryContainer"], sw=2)
    text(c, 310, 588, "Scan label", "labelSmall", C["onSecondaryContainer"], "middle")
    section(c, 652, "Sessions", "Ask AI")
    for i, (d, sub) in enumerate((("30 Jul", "V60 · 15.0 g · 4.5 · well extracted"),
                                  ("25 Jul", "Kalita · 16.0 g · 4.0 · slightly under"))):
        ry = 664 + i * 48
        text(c, 20, ry + 20, d, "titleMedium")
        text(c, 20, ry + 40, sub, "bodyMedium", C["onSurfaceVariant"], size=13)
        line(c, 20, ry + 48, 340, ry + 48)
    circle(c, 312, 712, 28, C["primary"])
    path(c, "M300 712 h24 M312 700 v24", stroke=C["onPrimary"], sw=2.6)
    gesture_bar(c)
    return c


def scan_states():
    c = Canvas("Bean Detail — scan states (state sheet, not a screen)")
    status_bar(c)
    top_bar(c, "Scan states", back=True)
    text(c, 20, 124, "Scanning", "titleSmall")
    card(c, 136, 168)
    for i, x in enumerate((32, 128)):
        rect(c, x, 152, 88, 112, C["surfaceContainer"], 2)
    rect(c, 32, 152, 296, 112, C["surface"], R_SM, opacity=0.72)
    spinner(c, 180, 208, 16, C["primary"])
    text(c, 180, 250, "Reading the label…", "bodyMedium", C["onSurfaceVariant"],
         "middle")
    text(c, 180, 288, "You can keep typing while this runs", "labelSmall",
         C["outline"], "middle")

    text(c, 20, 352, "Couldn't reach the server", "titleSmall")
    card(c, 364, 152)
    note(c, 380, "You're offline — the scan needs a connection.|"
                 "Everything on this form still saves locally.", "warn")
    button(c, 32, 452, 130, "Try again", "outlined")
    button(c, 174, 452, 154, "Enter by hand", "text")

    text(c, 20, 572, "Photo unreadable", "titleSmall")
    card(c, 584, 152)
    note(c, 600, "Couldn't read much from this photo.|"
                 "Try better light, or fill the fields in by hand.", "warn")
    button(c, 32, 672, 130, "Retake", "outlined")
    button(c, 174, 672, 154, "Enter by hand", "text")
    gesture_bar(c)
    return c


# ==================================================== 03 · Scan Review ======
def scan_review():
    c = Canvas("Scan Review — full screen")
    status_bar(c)
    top_bar(c, "Review scan", back=True)
    text(c, 20, 116, "Edit anything before it's applied to the bean.",
         "bodyMedium", C["onSurfaceVariant"])
    y = note(c, 132, "Couldn't read much from this photo — the blank|"
                     "fields were left for you to fill in.", "warn")
    fields = (("Name", "Ethiopia Guji Natural", True, True),
              ("Origin", "Guji, Ethiopia", False, False),
              ("Process", "Natural", False, False),
              ("Roast date", "28 Jul 2026", False, False),
              ("Variety", "Heirloom", False, False),
              ("Altitude", "1 950 m", False, False),
              ("Roaster", "", False, False),
              ("Producer", "", False, False))
    for i, (lab, val, req, foc) in enumerate(fields):
        textfield(c, GUTTER, y + 24 + i * 68, W - 2 * GUTTER, lab, val,
                  required=req, focused=foc)
    rect(c, 0, 712, W, 88, C["surface"])
    line(c, 0, 712, W, 712)
    button(c, GUTTER, 724, 140, "Discard", "text")
    button(c, 184, 724, 160, "Apply")
    gesture_bar(c)
    return c


# ================================================ 04 · Brew Session ========
def brew_session():
    c = Canvas("Brew Session — details & stages")
    status_bar(c)
    top_bar(c, "30 Jul · Ethiopia Guji", back=True, actions=("share",))
    section(c, 116, "Brew details")
    y = 132
    for i, (l1, v1, l2, v2) in enumerate(
            (("Dripper", "Hario V60", "Grinder", "Comandante"),
             ("Grind size", "22 clicks", "Dose", "15.0 g"),
             ("Water PPM", "72", "Humidity", ""))):
        ry = y + i * 60
        field(c, 20, ry, 145, l1, v1)
        field(c, 195, ry, 145, l2, v2)
    section(c, y + 200, "Pours", "Add pour")
    ty = y + 214
    card(c, ty, 196)
    hx = (36, 92, 156, 216)
    for lx, lab, an in ((36, "#", "start"), (148, "Temp", "end"),
                        (212, "Water", "end"), (268, "Time", "end"),
                        (282, "Pour", "start")):
        text(c, lx, ty + 26, lab, "labelMedium", C["onSurfaceVariant"], an, letter=0.4)
    line(c, 28, ty + 34, 332, ty + 34)
    rows = (("1", "93 °C", "50 g", "0:30", "circling"),
            ("2", "92 °C", "200 g", "1:45", "centre…"),
            ("3", "91 °C", "60 g", "2:20", "—"))
    for i, r in enumerate(rows):
        ry = ty + 34 + i * 48
        text(c, 36, ry + 30, r[0], "bodyMedium", C["onSurfaceVariant"], family=FM)
        text(c, 148, ry + 30, r[1], "bodyMedium", C["onSurface"], "end", family=FM)
        text(c, 212, ry + 30, r[2], "bodyMedium", C["onSurface"], "end", family=FM)
        text(c, 268, ry + 30, r[3], "bodyMedium", C["onSurface"], "end", family=FM)
        text(c, 282, ry + 30, r[4], "bodyMedium", C["onSurfaceVariant"], size=11)
        for k in range(3):
            circle(c, 326, ry + 24 + (k - 1) * 6, 1.6, C["outline"])
        if i < 2:
            line(c, 28, ry + 48, 332, ry + 48)
    line(c, 28, ty + 178, 332, ty + 178, C["onSurface"], 2)
    text(c, 148, ty + 194 - 4, "310 g", "labelMedium", C["onSurfaceVariant"], "end")
    text(c, 268, ty + 190, "2:20", "labelMedium", C["onSurfaceVariant"], "end")
    text(c, 36, ty + 190, "Total", "labelMedium", C["onSurfaceVariant"])
    section(c, 606, "Evaluation")
    card(c, 620, 128)
    text(c, 28, 646, "Score", "labelMedium", C["onSurfaceVariant"], letter=0.4)
    stars(c, 28, 658, 4.5, size=22, gap=7)
    line(c, 28, 704, 332, 704)
    text(c, 28, 730, "Extraction, note and 11 flavor axes below", "bodyMedium",
         C["onSurfaceVariant"])
    gesture_bar(c)
    return c


def brew_session_eval():
    c = Canvas("Brew Session — evaluation")
    status_bar(c)
    top_bar(c, "30 Jul · Ethiopia Guji", back=True, actions=("share",))
    section(c, 116, "Evaluation")
    card(c, 130, 300)
    text(c, 28, 156, "Score", "labelMedium", C["onSurfaceVariant"], letter=0.4)
    stars(c, 28, 168, 4.5)
    line(c, 28, 216, 332, 216)
    text(c, 28, 240, "Extraction", "labelMedium", C["onSurfaceVariant"], letter=0.4)
    extraction(c, 28, 268, 304, -0.35, "Slightly under  −0.35")
    line(c, 28, 336, 332, 336)
    text(c, 28, 360, "Note", "labelMedium", C["onSurfaceVariant"], letter=0.4)
    text(c, 28, 384, "Bright and floral, goes a little sour as it", "bodyLarge")
    text(c, 28, 406, "cools. Grind finer next time.", "bodyLarge")

    section(c, 466, "Flavor", "Edit all 11")
    card(c, 480, 200)
    flavor_bars(c, 28, 500, 304, BEAN_FLAVOR, rows=[0, 1, 3, 9, 10])
    text(c, 28, 664, "Tap “Edit all 11” to score every axis", "labelSmall",
         C["onSurfaceVariant"])
    text(c, 20, 716, "Saved automatically", "labelSmall", C["outline"])
    # M3 snackbar — replaces the fake full-width "Saved ✓" button
    rect(c, GUTTER, 728, W - 2 * GUTTER, 48, C["onSurface"], R_XS)
    text(c, 32, 757, "Session saved", "bodyMedium", C["surface"])
    text(c, 316, 757, "Undo", "labelLarge", C["dPrimary"], "end")
    gesture_bar(c)
    return c


def stage_editor():
    c = Canvas("Stage Editor sheet — specified but never drawn")
    photo(c, 0, 0, W, H, r=0)
    scrim(c, 0.55)
    sheet(c, 176)
    text(c, 20, 226, "Pour 2", "headlineSmall")
    text(c, 20, 250, "of 3 · Ethiopia Guji, 30 Jul", "bodyMedium",
         C["onSurfaceVariant"])
    text(c, 20, 296, "Temperature", "labelMedium", C["onSurfaceVariant"], letter=0.4)
    text(c, 340, 300, "92 °C", "titleMedium", C["onSurface"], "end", family=FM)
    rect(c, 20, 318, 320, 6, C["vizTrack"], 3)
    rect(c, 20, 318, 262, 6, C["primary"], 3)
    circle(c, 282, 321, 11, C["primary"])
    for v, x in ((-10, 20), (110, 340)):
        text(c, x, 346, f"{v} °C", "labelSmall", C["onSurfaceVariant"],
             "start" if v < 0 else "end")
    textfield(c, 20, 378, 150, "Water (g)", "200", focused=True)
    rect(c, 190, 378, 150, 56, C["cardSurface"], R_SM, stroke=C["outline"])
    rect(c, 202, 372, 34, 12, C["cardSurface"])
    text(c, 206, 382, "Time", "labelMedium", C["onSurfaceVariant"])
    text(c, 206, 414, "1:45", "bodyLarge", family=FM)
    circle(c, 316, 406, 11, "none", stroke=C["onSurfaceVariant"], sw=1.6)
    line(c, 316, 400, 316, 406, C["onSurfaceVariant"], 1.6)
    line(c, 316, 406, 320, 409, C["onSurfaceVariant"], 1.6)
    textfield(c, 20, 458, 320, "Pour style", "centre, slow")
    text(c, 20, 542, "Free text — “circling”, “centre pulse”, anything you use.",
         "labelSmall", C["onSurfaceVariant"])
    button(c, 20, 588, 150, "Delete pour", "danger")
    button(c, 190, 588, 150, "Save pour")
    text(c, 20, 676, "skipPartiallyExpanded = true · imePadding()", "labelSmall",
         C["outline"])
    gesture_bar(c)
    return c


def flavor_sliders():
    c = Canvas("Flavor sliders sheet — specified but never drawn")
    photo(c, 0, 0, W, H, r=0)
    scrim(c, 0.55)
    sheet(c, 96)
    text(c, 20, 146, "Score the cup", "headlineSmall")
    text(c, 20, 170, "Eleven axes · drag or tap the track", "bodyMedium",
         C["onSurfaceVariant"])
    button(c, 250, 130, 94, "Reset", "text")
    for i, (lab, v) in enumerate(zip(FLAVOR, BEAN_FLAVOR)):
        ry = 200 + i * 48
        text(c, 20, ry + 4, lab, "bodyMedium", C["onSurface"])
        text(c, 340, ry + 4, f"{v:.1f}", "labelLarge", C["onSurfaceVariant"], "end",
             family=FM)
        rect(c, 20, ry + 14, 320, 6, C["vizTrack"], 3)
        rect(c, 20, ry + 14, v / 5 * 320, 6, C["primary"], 3)
        circle(c, 20 + v / 5 * 320, ry + 17, 11, C["primary"])
    text(c, 20, 748, "Each row is a 48 dp target · values 0–5, step 0.1",
         "labelSmall", C["outline"])
    gesture_bar(c)
    return c


# ======================================================= 05 · Ask AI ========
def ask_ai():
    c = Canvas("Ask AI — result")
    photo(c, 0, 0, W, H, r=0)
    scrim(c, 0.55)
    sheet(c, 150)
    text(c, 20, 200, "Ask AI for a recipe", "headlineSmall")
    text(c, 20, 224, "Ethiopia Guji Natural · Natural · 4 past sessions",
         "bodyMedium", C["onSurfaceVariant"])
    textfield(c, 20, 252, 320, "Dripper", "Hario V60")
    button(c, 20, 324, 320, "Get suggestion", "tonal")
    rect(c, 20, 392, 320, 268, C["cardSurface"], R_LG, stroke=C["outlineVariant"])
    rect(c, 32, 406, 96, 24, C["secondaryContainer"], 12)
    circle(c, 46, 418, 5, C["onSecondaryContainer"])
    text(c, 58, 422, "AI-written", "labelSmall", C["onSecondaryContainer"])
    text(c, 32, 456, "Bright and floral — bloom heavy, then", "bodyLarge")
    text(c, 32, 478, "two even pours.", "bodyLarge")
    line(c, 32, 496, 328, 496)
    for i, (l, v) in enumerate((("Dose", "15.0 g"), ("Grind", "medium-fine, 22 clicks"))):
        text(c, 32, 520 + i * 22, l, "bodyMedium", C["onSurfaceVariant"])
        text(c, 328, 520 + i * 22, v, "bodyMedium", C["onSurface"], "end")
    line(c, 32, 552, 328, 552)
    for i, (n, s) in enumerate(((1, "93 °C · 50 g · 0:30 · circling"),
                                (2, "92 °C · 200 g · 1:45 · centre"))):
        text(c, 32, 576 + i * 22, str(n), "labelMedium", C["primary"], family=FM)
        text(c, 50, 576 + i * 22, s, "bodyMedium", C["onSurface"])
    text(c, 32, 634, "A starting point, not a rule — edit anything.", "labelSmall",
         C["onSurfaceVariant"])
    button(c, 20, 692, 140, "Cancel", "text")
    button(c, 176, 692, 164, "Create session")
    gesture_bar(c)
    return c


def ask_ai_states():
    c = Canvas("Ask AI — loading & failure (state sheet)")
    status_bar(c)
    top_bar(c, "Ask AI states", back=True)
    text(c, 20, 124, "Working", "titleSmall")
    card(c, 136, 200)
    button(c, 32, 152, 296, "Getting a suggestion…", "disabled")
    spinner(c, 180, 250, 14, C["primary"])
    text(c, 180, 296, "Usually about five seconds", "bodyMedium",
         C["onSurfaceVariant"], "middle")

    text(c, 20, 384, "Offline", "titleSmall")
    card(c, 396, 152)
    note(c, 412, "You're offline. This one needs a connection —|"
                 "your past recipes are all still here.", "warn")
    button(c, 32, 484, 130, "Try again", "outlined")

    text(c, 20, 604, "Server error", "titleSmall")
    card(c, 616, 152)
    note(c, 632, "The suggestion service didn't answer.|"
                 "Nothing was sent anywhere else.", "warn")
    button(c, 32, 704, 130, "Try again", "outlined")
    gesture_bar(c)
    return c


# ==================================================== 07 · Catalogue =======
def catalogue():
    c = Canvas("Can Drink catalogue — v1.1")
    status_bar(c)
    top_bar(c, "Can Drink", back=True, actions=("sort",))
    rect(c, GUTTER, 104, W - 2 * GUTTER, 56, C["surfaceContainer"], 28)
    circle(c, 44, 132, 8, "none", stroke=C["onSurfaceVariant"], sw=2)
    line(c, 50, 138, 56, 144, C["onSurfaceVariant"], 2)
    text(c, 72, 138, "Search roasters and beans", "bodyLarge", C["onSurfaceVariant"])
    x = chip(c, GUTTER, 168, "In stock", selected=True)
    x = chip(c, x, 168, "Roaster", menu=True)
    chip(c, x, 168, "Origin", menu=True)
    text(c, 20, 244, "Newest first · 42 beans", "labelMedium", C["onSurfaceVariant"])
    cards = (("Kenya AA Karatu", "Lomi · Kenya", "€16 · 250 g", True, True),
             ("Panama Geisha", "Tanat · Panama", "€42 · 100 g", False, True),
             ("Brazil Cerrado", "Coutume · Brazil", "€13 · 250 g", False, False),
             ("Guatemala Huehue", "Belleville · Guatemala", "€15 · 250 g", False, True))
    for i, (n, r, p, new, stock) in enumerate(cards):
        cx = GUTTER + (i % 2) * 168
        cy = 260 + (i // 2) * 234
        rect(c, cx, cy, 152, 218, C["cardSurface"], R_LG)
        photo(c, cx, cy, 152, 114, r=R_LG)
        rect(c, cx, cy + 98, 152, 16, C["cardSurface"])
        if new:
            rect(c, cx + 10, cy + 10, 42, 22, C["primaryContainer"], 11)
            text(c, cx + 31, cy + 25, "New", "labelSmall", C["onPrimaryContainer"],
                 "middle")
        text(c, cx + 12, cy + 136, n, "titleMedium", size=15)
        text(c, cx + 12, cy + 156, r, "bodyMedium", C["onSurfaceVariant"], size=12)
        text(c, cx + 12, cy + 174, p, "bodyMedium", C["onSurfaceVariant"], size=12)
        if stock:
            rect(c, cx + 12, cy + 186, 66, 22, C["tertiaryContainer"], R_XS)
            text(c, cx + 45, cy + 201, "In stock", "labelSmall",
                 C["onTertiaryContainer"], "middle")
        else:
            rect(c, cx + 12, cy + 186, 74, 22, C["surfaceContainer"], R_XS)
            text(c, cx + 49, cy + 201, "Sold out", "labelSmall", C["onSurfaceVariant"],
                 "middle")
        ext_link(c, cx + 128, cy + 190)
    text(c, 20, 748, "Opens the roaster's own page in your browser", "labelSmall",
         C["outline"])
    gesture_bar(c)
    return c


# ======================================================= 08 · Camera =======
def camera():
    c = Canvas("Camera capture", bg=C["dSurface"])
    rect(c, 0, 0, W, H, "#241C16")
    status_bar(c, dark=True)
    rect(c, 0, 0, W, 96, C["scrim"], opacity=0.45)
    rect(c, 0, 620, W, 180, C["scrim"], opacity=0.45)
    path(c, "M29 61 l14 14 M43 61 l-14 14", stroke="#FFFFFF", sw=2)
    text(c, 180, 74, "Scan bean label", "titleMedium", "#FFFFFF", "middle")
    for (ax, ay, dx, dy) in ((44, 210, 1, 1), (316, 210, -1, 1),
                             (44, 560, 1, -1), (316, 560, -1, -1)):
        path(c, f"M{ax} {ay+28*dy} v{-28*dy} h{28*dx}", stroke=C["dPrimary"], sw=3)
    text(c, 180, 600, "Fill the frame with the label", "bodyMedium", "#FFFFFF",
         "middle")
    circle(c, 180, 700, 34, "none", stroke="#FFFFFF", sw=3)
    circle(c, 180, 700, 27, "#FFFFFF")
    rect(c, 48, 676, 48, 48, "#FFFFFF", R_SM, opacity=0.16)
    photo(c, 52, 680, 40, 40, r=R_XS)
    text(c, 72, 742, "Photos", "labelSmall", "#FFFFFF", "middle")
    circle(c, 288, 700, 24, "#FFFFFF", opacity=0.16)
    flash(c, 288, 700)
    text(c, 288, 742, "Flash", "labelSmall", "#FFFFFF", "middle")
    gesture_bar(c, dark=True)
    return c


def camera_permission():
    c = Canvas("Camera — permission denied")
    status_bar(c)
    top_bar(c, "Scan bean label", back=True)
    circle(c, 180, 260, 48, C["secondaryContainer"])
    rect(c, 156, 246, 48, 34, "none", R_SM, stroke=C["onSecondaryContainer"], sw=2)
    circle(c, 180, 263, 9, "none", stroke=C["onSecondaryContainer"], sw=2)
    path(c, "M156 238 l48 48", stroke=C["onSecondaryContainer"], sw=2)
    text(c, 180, 352, "Camera is off", "headlineMedium", C["onSurface"], "middle")
    for i, ln in enumerate(("Scanning a label needs the camera. You",
                            "turned it off — you can turn it back on in",
                            "Settings.")):
        text(c, 180, 388 + i * 22, ln, "bodyLarge", C["onSurfaceVariant"], "middle")
    button(c, 80, 468, 200, "Open Settings")
    button(c, 60, 528, 240, "Pick a photo instead", "tonal")
    text(c, 180, 606, "Picking a photo needs no permission at all.", "labelSmall",
         C["onSurfaceVariant"], "middle")
    text(c, 180, 628, "You can also type everything by hand.", "labelSmall",
         C["onSurfaceVariant"], "middle")
    gesture_bar(c)
    return c


# ====================================================== 09 · Profile =======
def profile():
    c = Canvas("Profile")
    status_bar(c)
    top_bar(c, "Profile", back=True)
    circle(c, 180, 168, 44, C["secondaryContainer"])
    text(c, 180, 182, "Z", "displaySmall", C["onSecondaryContainer"], "middle")
    circle(c, 210, 198, 18, C["primary"])
    path(c, "M204 200 l4 4 l8 -9", stroke=C["onPrimary"], sw=2)
    c.body[-1] = c.body[-1].replace("M204 200 l4 4 l8 -9",
                                    "M204 202 l7 -7 M204 202 v3 h3")
    button(c, 118, 224, 124, "Change photo", "text")
    textfield(c, GUTTER, 292, W - 2 * GUTTER, "Name", "Zixing")
    textfield(c, GUTTER, 364, W - 2 * GUTTER, "Email", "zixing@example.com")
    section(c, 468, "About & legal")
    card(c, 482, 232)
    for i, (lab, sub) in enumerate((("Privacy Policy", None),
                                    ("How we use AI", "Re-read the disclosure"),
                                    ("Open-source licences", None),
                                    ("Version", "1.0.0 (14)"))):
        ry = 482 + i * 58
        two = sub and lab != "Version"
        text(c, 32, ry + (28 if two else 34), lab, "bodyLarge")
        if two:
            text(c, 32, ry + 46, sub, "bodyMedium", C["onSurfaceVariant"])
        if lab == "Version":
            text(c, 328, ry + 34, sub, "bodyMedium", C["onSurfaceVariant"], "end")
        else:
            path(c, f"M322 {ry+27} l6 6 l-6 6", stroke=C["outline"], sw=1.6)
        if i < 3:
            line(c, 32, ry + 58, 332, ry + 58)
    text(c, 20, 748, "Saved automatically", "labelSmall", C["outline"])
    gesture_bar(c)
    return c


# =================================================== 10 · Share card =======
def share_card():
    c = Canvas("Share card export")
    status_bar(c)
    top_bar(c, "Share", back=False, actions=("close",))
    # --- the exported artwork, drawn at its true 4:5 export ratio ---
    X, Y, CW, CH = 40, 108, 280, 350
    cid = c.uid("cc")
    c.defs.append(f'<clipPath id="{cid}"><rect x="{X}" y="{Y}" width="{CW}" '
                  f'height="{CH}" rx="{R_LG}"/></clipPath>')
    c.add(f'<g clip-path="url(#{cid})">')
    photo(c, X, Y, CW, CH, r=0)
    gid = c.uid("cg")
    c.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                  f'<stop offset="0" stop-color="{C["scrim"]}" stop-opacity="0.30"/>'
                  f'<stop offset="0.45" stop-color="{C["scrim"]}" stop-opacity="0.78"/>'
                  f'<stop offset="1" stop-color="{C["scrim"]}" stop-opacity="0.94"/>'
                  f'</linearGradient>')
    rect(c, X, Y, CW, CH, f"url(#{gid})")
    text(c, X + 20, Y + 44, "Ethiopia Guji", "headlineSmall", "#FFF6EE", size=24)
    text(c, X + 20, Y + 70, "Natural", "headlineSmall", "#FFF6EE", size=24)
    text(c, X + 20, Y + 92, "Guji, Ethiopia · Belleville", "labelSmall", "#E4D3C4")
    radar11(c, X + CW / 2, Y + 196, 62, BEAN_FLAVOR, "#FFB894", "#E4D3C4",
            fill_op=0.20)
    line(c, X + 20, Y + 288, X + CW - 20, Y + 288, "#E4D3C4", 0.75)
    text(c, X + 20, Y + 314, "4.5", "headlineSmall", "#FFF6EE", size=26, family=FM)
    text(c, X + 76, Y + 314, "/ 5 · well extracted", "bodyMedium", "#E4D3C4")
    crescent(c, X + CW - 34, Y + 306, 18, "#FFB894")
    text(c, X + CW - 20, Y + 330, "Coffee Can", "labelSmall", "#E4D3C4", "end")
    c.add("</g>")
    text(c, 180, 486, "1080 × 1350 · rendered on device", "labelSmall",
         C["onSurfaceVariant"], "middle")
    # variant switch — M3 segmented button
    rect(c, 60, 516, 240, 40, "none", 20, stroke=C["outline"])
    rect(c, 60, 516, 120, 40, C["primaryContainer"], 20)
    rect(c, 150, 516, 30, 40, C["primaryContainer"])
    line(c, 180, 516, 180, 556, C["outline"], 1)
    text(c, 120, 541, "This bean", "labelLarge", C["onPrimaryContainer"], "middle")
    text(c, 240, 541, "This brew", "labelLarge", C["onSurface"], "middle")
    button(c, GUTTER, 616, 158, "Save to photos", "tonal")
    button(c, 186, 616, 158, "Share")
    text(c, 180, 700, "The roaster is credited by name only.", "labelSmall",
         C["onSurfaceVariant"], "middle")
    text(c, 180, 720, "Your data stays the subject — we sign it small.",
         "labelSmall", C["onSurfaceVariant"], "middle")
    gesture_bar(c)
    return c


# ================================================= 11 · AI disclosure ======
def ai_disclosure():
    c = Canvas("AI disclosure & consent")
    photo(c, 0, 0, W, H, r=0)
    scrim(c, 0.6)
    D, DY, DW, DH = 24, 104, 312, 608
    rect(c, D, DY, DW, DH, C["cardSurface"], R_XL)
    circle(c, 180, DY + 56, 28, C["primaryContainer"])
    crescent(c, 180, DY + 56, 26, C["primary"])
    text(c, 180, DY + 118, "This uses an AI service", "headlineSmall", C["onSurface"],
         "middle")
    body = ("Your photo, and the bean and session|"
            "details you've typed in, may be sent|"
            "over the internet to an AI service to|"
            "read labels and suggest brew settings.||"
            "What's sent: only what the feature|"
            "needs — the photo you choose, or the|"
            "text on the bean you're looking at.||"
            "Nothing is sent unless you tap an AI|"
            "button. You can log everything by|"
            "hand without ever using this.")
    y = DY + 154
    for ln in body.split("|"):
        if ln:
            text(c, D + 24, y, ln, "bodyLarge", C["onSurfaceVariant"])
        y += 22 if ln else 8
    line(c, D + 24, DY + 430, D + DW - 24, DY + 430)
    button(c, D + 12, DY + 440, 160, "Privacy Policy", "text")
    text(c, D + 24, DY + 508, "You'll see this again now and then, until", "labelSmall",
         C["outline"])
    text(c, D + 24, DY + 524, "you accept it.", "labelSmall", C["outline"])
    # both actions INSIDE the dialog, confirm on the right
    button(c, D + 20, DY + 540, 104, "Not now", "text")
    button(c, D + 148, DY + 540, 144, "Continue")
    text(c, 180, 756, "Back and tap-outside behave exactly like “Not now”.",
         "labelSmall", "#E4D3C4", "middle")
    gesture_bar(c, dark=True)
    return c


# ---------------------------------------------------------------- driver ----
SCREENS = [
    ("01_home.svg", home),
    ("01b_home_empty.svg", home_empty),
    ("02_bean_detail.svg", bean_detail),
    ("02b_bean_detail_lower.svg", bean_detail_lower),
    ("02c_scan_states.svg", scan_states),
    ("03_scan_review.svg", scan_review),
    ("04_brew_session.svg", brew_session),
    ("04b_brew_session_eval.svg", brew_session_eval),
    ("04c_stage_editor.svg", stage_editor),
    ("04d_flavor_sliders.svg", flavor_sliders),
    ("05_ask_ai.svg", ask_ai),
    ("05b_ask_ai_states.svg", ask_ai_states),
    ("07_catalogue.svg", catalogue),
    ("08_camera.svg", camera),
    ("08b_camera_permission.svg", camera_permission),
    ("09_profile.svg", profile),
    ("10_share_card.svg", share_card),
    ("11_ai_disclosure.svg", ai_disclosure),
]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in SCREENS:
        (OUT / name).write_text(fn().render())
        print("wrote", name)
