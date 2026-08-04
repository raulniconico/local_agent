#!/usr/bin/env python3
"""Scheme E — the official design. Built page by page on scheme D's palette
and type (pure green + Fredoka + rounded shapes).

    python3 scheme_e.py         # write the SVG pages
    python3 scheme_e.py --gif   # also build the motion GIFs

Pages live in screenshots/scheme-e/.

Numbering follows the swipe axis, centred on Home:

    00w   welcome / splash — off-axis, shown once at cold launch
    0.5   add-a-bean form — off-axis, reached by tapping Add bean from Home
    -2    <- swipe left     -1    <- swipe left
    00    HOME
    +1    swipe right ->    +2    swipe right ->

A page's state is a suffix on the same number (00_home, 00_home_empty), since
states are the same destination, not a different one.
"""
from __future__ import annotations
import math, pathlib, random, sys, subprocess, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wireframes as wf
import variants as V

OUT = HERE / "screenshots" / "scheme-e"
W, H = wf.W, wf.H

# scheme D's tokens and type, adopted as scheme E's baseline
wf.C.update(V.PURE_GREEN)
wf.SEQ[:] = V.PURE_GREEN_SEQ
V._apply_style(V.FREDOKA_STYLE)

BRAND = wf.BRAND_MARK          # #34C759 — the logo's own green
wf.AVATAR = "R"

# Inline the typeface so a page looks the same in a browser, an IDE preview
# and the exported GIF — not just where Fredoka happens to be installed.
wf.EMBED["Fredoka"] = str(pathlib.Path.home() / ".local/share/fonts/Fredoka-var.ttf")

# Display face for the big headlines. Fredoka is the logo's own face, so the
# headline and the mark share letterforms. Chewy was evaluated for these
# moments and rejected: it is a third voice that does not match the logo, and
# it ships in one weight only.
FREDOKA = "Fredoka,'Liberation Sans',sans-serif"
CHEWY = "Chewy,Fredoka,'Liberation Sans',sans-serif"   # evaluated, not used
HEADLINE = FREDOKA


# ------------------------------------------------------------- 00 welcome ---
def welcome(fade: float = 1.0):
    """Cold-launch splash. The field is the logo's own green, so the disc is
    dropped — a #34C759 disc on a #34C759 ground is invisible. What remains is
    the wordmark knocked out in white, which is how the mark is meant to sit
    on its own colour.

    `fade` drives the 1s ease-out reveal; 1.0 is the resting state.
    """
    c = wf.Canvas("Welcome — scheme E", bg=BRAND)
    # Dark status-bar ink: light-content icons would be 2.22:1 on this green.
    # #002602 is onPrimaryContainer and measures 7.40:1.
    n = len(c.body)
    wf.status_bar(c)
    c.body[n:] = [b.replace(wf.C["onSurfaceVariant"], "#002602") for b in c.body[n:]]

    c.add(f'<g opacity="{fade:.4f}">')
    wf.logo(c, W / 2, H / 2 - 4, 290, tagline=True, disc=False)
    c.add("</g>")
    return c


# --------------------------------------------------------------- bag tile --
def bag_tile(c, x, y, w, h, code, r=None):
    """origin_tile()'s gradient (wireframes.py), topped with a small drawn
    coffee bag instead of a two-letter code watermark. Letters read as an
    avatar/initial -- the metaphor for a *person* -- which is the wrong
    association for produce you can hold; a generated figure reads as "this
    is coffee" on sight instead. The gradient is still seeded off `code`, so
    tiles keep their per-bean colour variety.

    A loose bean cluster was the first pass here; a bag reads as *the thing
    on your shelf* rather than raw produce, and it's what every specialty
    roaster's own product photography actually shows. So the figure is
    drawn off real roaster-bag conventions rather than invented: a
    gusseted stand-up pouch, a folded/crimped top seal (the pleat creases),
    a circular one-way degassing valve, and a labelled patch -- the same
    cues that make a Stumptown or Blue Bottle bag legible as "coffee" before
    you read a word on it. Green is the main fill (this app's brand colour),
    not a photographic kraft-paper brown, since the figure is a generated
    brand asset, not a product photo.

    The label itself takes its cue from two of the roasters already named in
    -1_can_drink's sample data (Tanat, Terres de Café) rather than from a
    third invented style -- WebFetch on their sites gives only text (no
    actual product photo pixels), but what came back was consistent: Terres
    de Café leans on a linoprint/woodblock-stamp look and an origin marker
    above the name; Tanat stays minimal, one deliberate mark rather than a
    busy label. So: a single bold stamped cup silhouette, plus a thin origin
    rule above it, and nothing else on the patch.
    """
    r = wf.R_MD if r is None else r
    gid = c.uid("bt")
    seed = sum(ord(ch) for ch in code)
    a = ["#DCEFDD", "#D2ECD8", "#E3F3E1", "#CDE9D2"][seed % 4]
    b = ["#4C9A5B", "#3E8B4C", "#5AAE68", "#347A44"][(seed // 3) % 4]
    c.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0.9" y2="1">'
                  f'<stop offset="0" stop-color="{a}"/>'
                  f'<stop offset="1" stop-color="{b}"/></linearGradient>')
    wf.rect(c, x, y, w, h, f"url(#{gid})", r)

    m = min(w, h)
    cx0, cy0 = x + w / 2, y + h / 2
    ink = "#1B4D2A"
    c.add(f'<g transform="translate({cx0:.1f} {cy0:.1f}) scale({m/100:.3f})">')
    # body: slightly wider at the base, like a gusseted stand-up pouch
    c.add(f'<path d="M-24 -30 Q-24 -36 -18 -36 L18 -36 Q24 -36 24 -30 '
          f'L26 26 Q26 34 18 34 L-18 34 Q-26 34 -26 26 Z" '
          f'fill="{b}" stroke="{ink}" stroke-width="2.2"/>')
    # folded top seal, with pleat creases
    c.add(f'<path d="M-19 -36 Q-19 -42 -13 -42 L13 -42 Q19 -42 19 -36 Z" '
          f'fill="{b}" stroke="{ink}" stroke-width="2.2"/>')
    for lx in (-11, -1, 9):
        c.add(f'<path d="M{lx} -41 L{lx+3} -37" stroke="{ink}" stroke-width="1.4" '
              f'stroke-linecap="round"/>')
    # label patch: a thin origin rule (Terres de Café's flag-strip habit,
    # generalised rather than an invented flag per bean) over a single bold
    # stamped cup -- Tanat's one-mark restraint, not a busy label
    c.add(f'<rect x="-17" y="-6" width="34" height="24" rx="4" fill="{a}" '
          f'stroke="{ink}" stroke-width="1.6"/>')
    c.add(f'<path d="M-15 -3.5 h30" stroke="{ink}" stroke-width="1.6" opacity="0.5"/>')
    c.add(f'<g transform="translate(0 8)" fill="{ink}">')
    c.add('<path d="M-7.5 -4.2 Q-7.8 -4.6 -7.2 -4.8 L7.2 -4.8 Q7.9 -4.6 7.6 -4.1 '
          'L6.3 4.4 Q5.9 6.6 3.6 6.6 L-3.6 6.6 Q-5.9 6.6 -6.3 4.4 Z"/>')
    c.add(f'<path d="M7.4 -3.0 Q11 -3 11 0.4 Q11 3.6 7.1 3.4" fill="none" '
          f'stroke="{ink}" stroke-width="1.6"/>')
    for sx in (-3, 1.4):
        c.add(f'<path d="M{sx} -7.4 Q{sx+1.4} -9.4 {sx} -11.2" fill="none" '
              f'stroke="{ink}" stroke-width="1.3" stroke-linecap="round" opacity="0.75"/>')
    c.add('</g>')
    # one-way degassing valve
    c.add(f'<circle cx="10" cy="-20" r="5.4" fill="none" stroke="{ink}" stroke-width="2"/>')
    c.add(f'<circle cx="10" cy="-20" r="1.8" fill="{ink}"/>')
    c.add('</g>')


# -------------------------------------------------------------- 00 home ----
def home(beans=None):
    """Home once at least one bean profile exists: the empty state's single
    CTA (home_empty) is replaced by a grid of bean blocks -- the same card
    language as -1_can_drink's product blocks (title, meta, a status pill),
    just carrying bean fields instead of roaster/price/stock.

    Where -1_can_drink's cards top out with photo() (a plausible stand-in
    for a real roaster photo scraped off the web), these top out with
    bag_tile() instead: a bean a user just added has no photo yet, and
    photo()'s gradient is a *placeholder for one that will exist* -- exactly
    wrong for a card that may never get one. bag_tile() draws a small figure
    (a coffee bag) in place of a real photo rather than falling back to
    text -- see its docstring for why that beats origin_tile()'s two-letter
    watermark.

    `beans` is a sequence of (name, roast_meta, brew_count, origin_code);
    defaults to a small sample so the page renders on its own.
    """
    beans = beans or [
        ("Ethiopia Guji Natural", "Natural · Roasted 28 Jul", 4, "ET"),
        ("Colombia Huila Washed", "Washed · Roasted 20 Jul", 2, "CO"),
        ("Kenya Nyeri AB", "Washed · Roasted 02 Aug", 0, "KE"),
        ("Guatemala Huehue", "Washed · Roasted 15 Jul", 1, "GT"),
    ]
    c = wf.Canvas("Home — scheme E")
    wf.status_bar(c)
    wf.top_bar(c, "Coffee Can", brand=True, actions=("avatar",))
    wf.section(c, 112, "Your beans", "Search")

    card_h, photo_h, row_gap = 164, 84, 12
    for i, (name, meta, sessions, code) in enumerate(beans):
        cx = wf.GUTTER + (i % 2) * 168
        cy = 128 + (i // 2) * (card_h + row_gap)
        wf.card(c, cy, card_h, x=cx, w=152)
        bag_tile(c, cx, cy, 152, photo_h, code, r=wf.R_LG)
        wf.rect(c, cx, cy + photo_h - 16, 152, 16, wf.C["cardSurface"])
        wf.text(c, cx + 12, cy + 100, name, "titleMedium", size=13)
        wf.text(c, cx + 12, cy + 116, meta, "bodyMedium", wf.C["onSurfaceVariant"], size=11)
        if sessions:
            wf.rect(c, cx + 12, cy + 140, 66, 16, wf.C["primaryContainer"], wf.R_XS)
            label = "1 brew" if sessions == 1 else f"{sessions} brews"
            wf.text(c, cx + 45, cy + 152, label, "labelSmall",
                    wf.C["onPrimaryContainer"], "middle")
        else:
            wf.rect(c, cx + 12, cy + 140, 92, 16, wf.C["surfaceContainer"], wf.R_XS)
            wf.text(c, cx + 58, cy + 152, "No brews yet", "labelSmall",
                    wf.C["onSurfaceVariant"], "middle")

    rows = -(-len(beans) // 2)
    grid_bottom = 128 + rows * card_h + (rows - 1) * row_gap
    wf.section(c, grid_bottom + 32, "Brewing activity")
    wf.card(c, grid_bottom + 46, 140)
    wf.heatmap(c, 28, grid_bottom + 78, 304)

    # FAB, clear of the bar tips -- adds another 0.5 bean profile
    fab_cy = grid_bottom + 46 + 140 + 44
    wf.circle(c, 312, fab_cy, 28, wf.C["primary"], stroke=wf.C.get("primaryOutline"))
    wf.path(c, f"M300 {fab_cy} h24 M312 {fab_cy - 12} v24", stroke=wf.C["onPrimary"], sw=2.6)
    wf.gesture_bar(c)
    return c


# ---------------------------------------------------------- 00 home (v1) ---
def home_list(beans=None):
    """Alternate take on the populated Home: full-width profile cards in a
    single column, instead of home()'s 2-up block grid.

    The grid borrows -1_can_drink's language, which fits that page well --
    browsing many roasters' products is a discovery task, and a photo-led
    grid is the right pattern for discovery. Home isn't that: it's a
    handful of bags someone already owns, not a catalogue to browse. A
    list trades density (fewer beans per screen) for room per bean -- a
    bigger origin tile, a clearer single tap target, a chevron instead of a
    same-sized twin -- which is the right trade once the collection itself
    is small. bean_row() (wireframes.py's pre-scheme-e sketch of this same
    idea) made the same call; this restores it in scheme E's own type/tokens
    rather than reusing home()'s grid just for consistency's sake.
    """
    beans = beans or [
        ("Ethiopia Guji Natural", "Natural · Roasted 28 Jul", 4, "ET"),
        ("Colombia Huila Washed", "Washed · Roasted 20 Jul", 2, "CO"),
        ("Kenya Nyeri AB", "Washed · Roasted 02 Aug", 0, "KE"),
        ("Guatemala Huehue", "Washed · Roasted 15 Jul", 1, "GT"),
    ]
    c = wf.Canvas("Home · list variant — scheme E")
    wf.status_bar(c)
    wf.top_bar(c, "Coffee Can", brand=True, actions=("avatar",))
    wf.section(c, 112, "Your beans", "Search")

    card_w, card_h, tile, row_gap = W - 2 * wf.GUTTER, 86, 72, 10
    start_y = 124
    for i, (name, meta, sessions, code) in enumerate(beans):
        cx, cy = wf.GUTTER, start_y + i * (card_h + row_gap)
        wf.card(c, cy, card_h, x=cx, w=card_w)
        bag_tile(c, cx + 12, cy + 7, tile, tile, code, r=wf.R_MD)
        tx = cx + 12 + tile + 14
        wf.text(c, tx, cy + 30, name, "titleMedium", size=14)
        wf.text(c, tx, cy + 47, meta, "bodyMedium", wf.C["onSurfaceVariant"], size=11)
        if sessions:
            label = "1 brew" if sessions == 1 else f"{sessions} brews"
            wf.rect(c, tx, cy + 54, len(label) * 6.2 + 20, 16, wf.C["primaryContainer"], wf.R_XS)
            wf.text(c, tx + 10, cy + 66, label, "labelSmall", wf.C["onPrimaryContainer"])
        else:
            wf.rect(c, tx, cy + 54, 92, 16, wf.C["surfaceContainer"], wf.R_XS)
            wf.text(c, tx + 10, cy + 66, "No brews yet", "labelSmall", wf.C["onSurfaceVariant"])
        wf.path(c, f"M{cx+card_w-24} {cy+card_h/2-5} l5 5 l-5 5", stroke=wf.C["outline"], sw=1.6)

    list_bottom = start_y + len(beans) * card_h + (len(beans) - 1) * row_gap
    wf.section(c, list_bottom + 28, "Brewing activity")
    wf.card(c, list_bottom + 42, 140)
    wf.heatmap(c, 28, list_bottom + 74, 304)

    fab_cy = list_bottom + 42 + 140 + 40
    wf.circle(c, 312, fab_cy, 28, wf.C["primary"], stroke=wf.C.get("primaryOutline"))
    wf.path(c, f"M300 {fab_cy} h24 M312 {fab_cy - 12} v24", stroke=wf.C["onPrimary"], sw=2.6)
    wf.gesture_bar(c)
    return c


# ------------------------------------------------------------ 01b home ----
def home_empty(headline_font=None, shake=0.0):
    """First run, no beans yet. Layout unchanged from the draft; the avatar
    defaults to R and the headline carries the display face.

    `shake` (-1..1) offsets the CTA for the idle attention wiggle."""
    hf = headline_font or HEADLINE
    c = wf.Canvas("Home · empty state — scheme E")
    wf.status_bar(c)
    wf.top_bar(c, "Coffee Can", brand=True, actions=("avatar",))
    wf.logo(c, 180, 286, 100)
    wf.text(c, 180, 400, "No beans yet", "headlineMedium", wf.C["onSurface"],
            "middle", family=hf, size=34)
    for i, ln in enumerate(("Add the bag you're brewing this week",
                            "and start keeping the log.")):
        wf.text(c, 180, 436 + i * 24, ln, "bodyLarge", wf.C["onSurfaceVariant"],
                "middle")
    bx, by, bw = 68, 500, 224
    if shake:
        # ~5dp of travel with a hair of counter-rotation: a nudge, not a buzz
        cx, cy = bx + bw / 2, by + 24
        c.add(f'<g transform="translate({6 * shake:.2f} 0) '
              f'rotate({1.0 * shake:.2f} {cx} {cy})">')
    wf.button(c, bx, by, bw, "Add your first bean")
    if shake:
        c.add("</g>")
    wf.gesture_bar(c)
    return c


# --------------------------------------------------------- 0.5 add-a-bean ---
def bean_profile_empty():
    """The blank "add a bean" form: what 02/02b (bean_detail /
    bean_detail_lower in wireframes.py) look like before any data exists.
    Reached by tapping Add bean from Home (00_home_empty's CTA, or the top
    bar's add action once beans exist).

    02b buries its "Scan label" action as one more tile in the Documents
    grid, well down the second scroll page — fine for a bean that already
    has data, but for a brand-new one that tile *is* the fastest way to fill
    in the rest of the form, so it moves to the page's first action instead
    of competing with fields the user hasn't touched yet.

    02's photo hero has nothing to show yet either (no bag has been scanned),
    so that space becomes the scan prompt rather than staying empty.
    """
    c = wf.Canvas("Bean profile — empty (0.5)")
    wf.status_bar(c)
    wf.top_bar(c, "New bean", back=True)

    wf.rect(c, wf.GUTTER, 104, W - 2 * wf.GUTTER, 140, wf.C["secondaryContainer"], wf.R_LG)
    icon_cy = 104 + 54
    c.add(f'<g transform="translate(0 {icon_cy - 263:.1f})">')
    wf.rect(c, 156, 246, 48, 34, "none", wf.R_SM, stroke=wf.C["onSecondaryContainer"], sw=2)
    wf.circle(c, 180, 263, 9, "none", stroke=wf.C["onSecondaryContainer"], sw=2)
    c.add("</g>")
    wf.text(c, 180, 104 + 100, "Scan label", "titleMedium",
            wf.C["onSecondaryContainer"], "middle")
    wf.text(c, 180, 104 + 122, "Point your camera at the bag to fill this in",
            "labelSmall", wf.C["onSecondaryContainer"], "middle")

    wf.text(c, 180, 268, "or enter it by hand", "labelMedium", wf.C["outline"], "middle")

    wf.textfield(c, wf.GUTTER, 286, W - 2 * wf.GUTTER, "Bean name", "")
    rows = (("Variety", "", "Altitude", ""),
            ("Roaster", "", "Producer", ""),
            ("Process", "", "Roast date", ""))
    for i, (l1, v1, l2, v2) in enumerate(rows):
        ry = 374 + i * 52
        wf.field(c, 20, ry, 145, l1, v1, placeholder=True)
        wf.field(c, 195, ry, 145, l2, v2, placeholder=True)

    wf.section(c, 546, "Flavor", "Set manually")
    wf.card(c, 560, 90)
    wf.text(c, 180, 598, "Log a brew to start building this bean's",
            "bodyMedium", wf.C["onSurfaceVariant"], "middle")
    wf.text(c, 180, 618, "flavor profile", "bodyMedium", wf.C["onSurfaceVariant"], "middle")

    wf.button(c, wf.GUTTER, 674, W - 2 * wf.GUTTER, "Save bean")
    wf.gesture_bar(c)
    return c


# ----------------------------------------------------------------- can-boy --
# A separate mascot mark, distinct from the shipped logo (wf.logo /
# coffee_can/assets/icon.svg, unmodified). White line only, flat, on its own
# green disc so the white reads against this page's light background. Arms
# and legs are each a single stroked line -- no double green+white pass, no
# filled hand/foot caps. The "Can" lettering is not redrawn in outline: it
# reuses the shipped wordmark's own solid glyphs (wf._LOGO_WORD) rescaled
# into the belly, so the text matches the real logo exactly.
def can_boy(c, cx, cy, size, bean_angle=0.0):
    """Spec'd in a 100x100 box; `size` is the rendered edge in dp.

    `bean_angle` pivots the raised arm -- can-boy's own left hand, screen
    right since he faces the viewer -- about the shoulder (degrees); the
    bean rides along with it. The shake animation drives this frame to frame.
    """
    g = size / 100.0
    c.add(f'<g transform="translate({cx - size/2:.2f} {cy - size/2:.2f}) scale({g:.4f})">')
    c.add(f'<circle cx="50" cy="50" r="50" fill="{wf.BRAND_MARK}"/>')

    # the figure itself is drawn smaller than the disc and shrunk toward its
    # centre: the raised arm swings through +-15 deg, and at full size that
    # carried the hand and bean past the disc's edge
    c.add('<g transform="translate(50 50) scale(0.82) translate(-50 -50)">')
    c.add('<g fill="none" stroke="#FFFFFF" stroke-linecap="round" stroke-linejoin="round">')
    # limbs, drawn under the can so its outline overlaps the shoulder/hip join
    c.add('<g stroke-width="4.2">')
    c.add('<path d="M30 40 Q19 44 17 55"/>')   # right arm, hand on hip
    c.add('<path d="M41 75 L37 90"/>')          # left leg
    c.add('<path d="M59 75 L63 90"/>')          # right leg
    c.add('</g>')
    # left arm, raised, holding the bean -- pivots as one piece at the
    # shoulder (70,38) so the wave and the bean shake together, not the bean
    # wobbling in a fixed hand
    c.add(f'<g transform="translate(70 38) rotate({bean_angle:.2f})">')
    c.add('<path d="M0 0 Q11 -9 9 -22" fill="none" stroke="#FFFFFF" stroke-width="4.2"/>')
    # the bean, at the hand's rest position (9,-22) relative to the shoulder
    # -- an S crease with unequal bulges reads as a bean seam rather than an eye
    c.add('<g transform="translate(9 -22) rotate(-10)" stroke="#FFFFFF" stroke-width="2.4">')
    c.add('<ellipse cx="0" cy="0" rx="4.6" ry="6.2" fill="none"/>')
    c.add('<path d="M0.5 -4.5 C1.8 -2.1 -1.8 1.6 0.2 4.5" fill="none" stroke-width="1.6"/>')
    c.add('</g>')
    c.add('</g>')
    # the can itself: lid + a barrel-bulged body, funky rather than a
    # straight-sided box so it reads as a can and not a carton
    c.add('<g stroke-width="5.2">')
    c.add('<path d="M33 27 C 29 41, 29 60, 33 74 C 40 78, 60 78, 67 74 '
          'C 71 60, 71 41, 67 27"/>')
    c.add('<ellipse cx="50" cy="24" rx="19" ry="6.5"/>')
    c.add('</g>')
    # pull tab: a small ring on a short rivet stem
    c.add('<g transform="translate(58 12) rotate(-12)" stroke-width="3">')
    c.add('<ellipse cx="0" cy="0" rx="5.4" ry="3.6"/>')
    c.add('<path d="M0 3.6 L-0.8 7.6"/>')
    c.add('</g>')
    c.add('</g>')

    # 'Can': the shipped wordmark's own solid paths, recentred (their bbox
    # centre is ~63.5,50.3 in the icon's 128 viewBox) and scaled into the belly
    # -- small enough to clear the body outline's stroke width on both sides
    c.add('<g transform="translate(50 57) scale(0.5) translate(-63.54 -50.33)" '
          'fill="#FFFFFF">' + "".join(wf._LOGO_WORD) + '</g>')
    c.add("</g>")  # close the shrink-toward-centre group
    c.add("</g>")


# ------------------------------------------------------------- -1w intro ----
def can_drink_intro(bean_angle=0.0):
    """First run of the Can Drink page (swipe left from Home)."""
    c = wf.Canvas("Can Drink · intro — scheme E")
    wf.status_bar(c)
    can_boy(c, 180, 208, 195, bean_angle=bean_angle)
    wf.text(c, 180, 424, "What's good", "headlineMedium", wf.C["onSurface"],
            "middle", family=HEADLINE, size=33)
    wf.text(c, 180, 460, "right now", "headlineMedium", wf.C["onSurface"],
            "middle", family=HEADLINE, size=33)
    for i, ln in enumerate(("Fresh arrivals from specialty roasters —",
                            "new origins, processes and prices,",
                            "gathered in one place.")):
        wf.text(c, 180, 504 + i * 24, ln, "bodyLarge", wf.C["onSurfaceVariant"],
                "middle")
    wf.button(c, 68, 636, 224, "Start")
    wf.text(c, 180, 716, "Swipe right to go back to your beans", "labelMedium",
            wf.C["outline"], "middle")
    wf.gesture_bar(c)
    return c


# --------------------------------------------------------------- -1 drink ---
# The real Can Drink catalogue -- where "Start" on the -1w intro lands. Same
# card pattern as wireframes.catalogue() (the pre-scheme-e sketch of this
# page, still rendered per-variant via PAGES in that file), just restyled
# through scheme E's tokens/type and, per the brief, showing six roasters'
# beans instead of four -- picked at random from a larger pool each run, the
# way the real app would rotate what's featured.
_BEAN_POOL = (
    ("Kenya AA Karatu", "Lomi · Kenya", "€16 · 250 g", True, True),
    ("Panama Geisha", "Tanat · Panama", "€42 · 100 g", False, True),
    ("Brazil Cerrado", "Coutume · Brazil", "€13 · 250 g", False, False),
    ("Guatemala Huehue", "Belleville · Guatemala", "€15 · 250 g", False, True),
    ("Ethiopia Guji", "Terres de Café · Ethiopia", "€17 · 250 g", True, True),
    ("Colombia Pink Bourbon", "La Cabra · Colombia", "€19 · 250 g", False, True),
    ("Rwanda Nyungwe", "Café Lomi · Rwanda", "€14 · 250 g", False, False),
    ("Yemen Haraaz", "Cafés Méo · Yemen", "€38 · 100 g", True, True),
    ("Honduras Marcala", "Hexagon · Honduras", "€12 · 250 g", False, True),
    ("Costa Rica Tarrazú", "Dak · Costa Rica", "€16 · 250 g", False, True),
)


def can_drink(seed=11):
    """The Can Drink catalogue, six beans deep. `seed` pins the random six
    for a reproducible build; drop it for a genuinely different six each run."""
    c = wf.Canvas("Can Drink — scheme E")
    wf.status_bar(c)
    wf.top_bar(c, "Can Drink", back=True, actions=("sort",))
    wf.rect(c, wf.GUTTER, 104, W - 2 * wf.GUTTER, 56, wf.C["surfaceContainer"], 28)
    wf.circle(c, 44, 132, 8, "none", stroke=wf.C["onSurfaceVariant"], sw=2)
    wf.line(c, 50, 138, 56, 144, wf.C["onSurfaceVariant"], 2)
    wf.text(c, 72, 138, "Search roasters and beans", "bodyLarge", wf.C["onSurfaceVariant"])
    x = wf.chip(c, wf.GUTTER, 168, "In stock", selected=True)
    x = wf.chip(c, x, 168, "Roaster", menu=True)
    wf.chip(c, x, 168, "Origin", menu=True)

    beans = random.Random(seed).sample(_BEAN_POOL, 6)
    wf.text(c, 20, 236, f"Newest first · {len(_BEAN_POOL) * 7} beans", "labelMedium",
            wf.C["onSurfaceVariant"])

    card_h, photo_h, row_gap = 164, 84, 12
    for i, (name, roaster, price, new, stock) in enumerate(beans):
        cx = wf.GUTTER + (i % 2) * 168
        cy = 248 + (i // 2) * (card_h + row_gap)
        wf.card(c, cy, card_h, x=cx, w=152)
        wf.photo(c, cx, cy, 152, photo_h, r=wf.R_LG)
        wf.rect(c, cx, cy + photo_h - 16, 152, 16, wf.C["cardSurface"])
        if new:
            wf.rect(c, cx + 10, cy + 8, 42, 18, wf.C["tertiary"], 9)
            wf.text(c, cx + 31, cy + 21, "New", "labelSmall", wf.C["onTertiary"], "middle")
        wf.text(c, cx + 12, cy + 100, name, "titleMedium", size=13)
        wf.text(c, cx + 12, cy + 116, roaster, "bodyMedium", wf.C["onSurfaceVariant"], size=11)
        wf.text(c, cx + 12, cy + 132, price, "bodyMedium", wf.C["onSurfaceVariant"], size=11)
        if stock:
            wf.rect(c, cx + 12, cy + 140, 66, 16, wf.C["primaryContainer"], wf.R_XS)
            wf.text(c, cx + 45, cy + 152, "In stock", "labelSmall",
                    wf.C["onPrimaryContainer"], "middle")
        else:
            wf.rect(c, cx + 12, cy + 140, 74, 16, wf.C["surfaceContainer"], wf.R_XS)
            wf.text(c, cx + 49, cy + 152, "Sold out", "labelSmall",
                    wf.C["onSurfaceVariant"], "middle")
        wf.ext_link(c, cx + 128, cy + 141)
    wf.gesture_bar(c)
    return c


PAGES = [("00w_welcome.svg", welcome),
         ("00_home.svg", home),
         ("00_home_1.svg", home_list),
         ("00_home_empty.svg", home_empty),
         ("0.5_bean_profile.svg", bean_profile_empty),
         ("-1w_can_drink_intro.svg", can_drink_intro),
         ("-1_can_drink.svg", can_drink)]

# ----------------------------------------------------------------- motion ---
def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def welcome_frames():
    """1s ease-out reveal, then hold."""
    n, ms, hold = 20, 50, 12
    fr = [(welcome(_ease_out_cubic(i / (n - 1))), ms) for i in range(n)]
    return fr + [(welcome(1.0), ms)] * hold


def home_empty_frames():
    """Idle attention wiggle on the CTA: a 600ms damped shake once every 3s.

    The rest of the cycle is two long-duration copies of the resting frame, so
    the GIF shows the true 3s cadence without carrying 60 redundant frames.
    """
    n, ms = 15, 40
    fr = []
    for i in range(n):
        t = i / (n - 1)
        fr.append((home_empty(shake=math.sin(2 * math.pi * 3 * t) * math.exp(-3.2 * t)),
                   ms))
    rest = home_empty()
    return fr + [(rest, 1200), (rest, 1200)]


def can_drink_intro_frames():
    """Can-boy shakes the held bean, a continuous ±15° rock rather than a
    one-off idle wiggle -- it's the page's whole reason for a GIF, not a
    background detail."""
    n, ms = 24, 60
    return [(can_drink_intro(bean_angle=15 * math.sin(2 * math.pi * i / n)), ms)
            for i in range(n)]


MOTION = {"00w_welcome": welcome_frames, "00_home_empty": home_empty_frames,
          "-1w_can_drink_intro": can_drink_intro_frames}


def build_gif(name: str, frames_fn):
    """Render every frame in one browser pass as a grid, then slice it up."""
    from PIL import Image

    spec = frames_fn()
    cols = 6
    rows = -(-len(spec) // cols)
    cells = "".join(f'<div>{c.render()}</div>' for c, _ in spec)
    html = (f"<html><head><meta charset=utf-8><style>"
            f"*{{margin:0;padding:0;border:0}}"
            f"body{{display:grid;grid-template-columns:repeat({cols},{W}px);"
            f"width:{cols*W}px;background:#000}}"
            f"div{{width:{W}px;height:{H}px;overflow:hidden}}"
            f"svg{{width:{W}px;height:{H}px;display:block}}"
            f"</style></head><body>{cells}</body></html>")

    with tempfile.TemporaryDirectory() as td:
        page = pathlib.Path(td, "grid.html"); page.write_text(html)
        shot = pathlib.Path(td, "grid.png")
        subprocess.run(["google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={cols*W},{rows*H}",
                        f"--screenshot={shot}", str(page)],
                       check=True, capture_output=True)
        sheet = Image.open(shot).convert("RGB")
        frames = [sheet.crop(((i % cols) * W, (i // cols) * H,
                              (i % cols) * W + W, (i // cols) * H + H))
                  for i in range(len(spec))]

    gif = OUT / f"{name}.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:],
                   duration=[ms for _, ms in spec], loop=0, optimize=True, disposal=2)
    return gif, len(frames), sum(ms for _, ms in spec)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, fn in PAGES:
        (OUT / fname).write_text(fn().render())
        print("wrote", fname)
    if "--gif" in sys.argv:
        for name, frames_fn in MOTION.items():
            g, k, total = build_gif(name, frames_fn)
            print(f"wrote {g.name}  {k} frames, {total/1000:.1f}s cycle, "
                  f"{g.stat().st_size//1024} KB")
