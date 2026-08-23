#!/usr/bin/env python3
"""Generates one small icon per dripper in the shipped default list
(coffee/src/coffee_can/assets/drippers.json) -- 15 total.

    python3 generate.py

Writes standalone icons into this folder, one per dripper (plus a
_preview.svg/.png grid, on the brand green, for eyeballing the whole set at
once -- not itself a shipped icon).

Each icon is 100x100, transparent background, white line only: no fill
anywhere, a single stroke colour, round caps/joins -- the same recipe
scheme_e.py's can_boy() and bag_tile() already use for every other
generated figure in this design system, so a dripper icon sitting next to
those reads as the same family rather than a fourth illustration style.
(Deliberately NOT wired into scheme_e.py or any page -- these are meant to
be dropped in later; this folder only produces the assets.)

THE SILHOUETTE CARRIES THE IDENTITY, NOT THE DETAIL INSIDE IT (rewritten
2026-08-22, direct product report: "Origami in reality is wider than V60,
but in your design they seem almost the same"). The first set drew nearly
every cone with one shared call -- V60, Origami, Cafec, Timemore, Kono and
Hario Switch were all literally `cone(50, 30, 26, 82, 5)` -- and told them
apart only by the ribs scribbled on the front. At the size these actually
render (a 26dp glyph on a 40dp disc, 41dp on a 64dp one) those ribs are two
or three grey pixels and the shapes are indistinguishable.

So each dripper is now drawn from its REAL PROPORTIONS. Every one of these
brewers has a top diameter within a few millimetres of 11.5cm -- that is
what a #2 filter is -- so what actually separates them on sight is DEPTH and
what the bottom does, not width:

    brewer            real top x height     drawn as
    Orea V3           11.5 x 6.0 cm         the shallowest, on the widest flat base
    Origami M         11.8 x 7.2            wide and shallow, 20 sharp pleats
    Kalita Wave 185   11.5 x 7.0            shallow, flat base, wavy rim
    April             11.5 x 7.0            shallow, flat base, nothing else
    Timemore B75      11.6 x 7.6            mid-depth, faceted walls
    Bee House         11.0 x 7.5            mid-depth, wide flat flange
    Hario V60 02      11.6 x 8.2            deep 60-degree cone, spiral rib
    Cafec Flower      11.5 x 8.3            deep cone, petal ribs
    Melitta 1x4       11.0 x 7.5            wedge: straight sides, slot base
    Fellow Stagg X    11.4 x 8.9            tall, near-vertical walls, flat base
    Kono Meimon       10.9 x 8.9            the deepest, narrowest cone
    OXO Brew          12.5 x 10.0           deep, flat base, rainmaker lid
    Hario Switch      11.5 x 10.0           V60 plus the valve housing under it
    Clever L          12.4 x 11.8           taller than it is wide, and lidded
    Chemex 6-cup      13.0 x 16.5           an hourglass carafe, its own family

One scale converts those to the canvas (SCALE px per cm), so the ratios you
see are the ratios the products have -- Origami really is 1.6 wide-to-deep
where V60 is 1.4, and drawn side by side that is now obvious. The identifying
detail (V60's spiral, Kalita's waves, Chemex's collar) stays on top of the
right silhouette rather than doing the whole job alone.
"""
import math
import pathlib

OUT = pathlib.Path(__file__).resolve().parent

MAIN = 5.5     # silhouette stroke width -- matches can_boy()/bag_tile()'s body weight
DETAIL = 2.6   # interior ribs/valves/rims -- matches bag_tile()'s pleat-crease weight


def _write(name, body):
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
           f'width="100" height="100">\n'
           f'<g fill="none" stroke="#FFFFFF" stroke-linecap="round" '
           f'stroke-linejoin="round">\n{body}\n</g>\n</svg>\n')
    (OUT / f"{name}.svg").write_text(doc)


def _preview(names):
    """A grid sheet on the brand green, for visual QA -- not a shipped icon."""
    cols, cell = 5, 120
    rows = -(-len(names) // cols)
    cells = []
    for i, n in enumerate(names):
        x, y = (i % cols) * cell, (i // cols) * cell
        inner = (OUT / f"{n}.svg").read_text().split(">", 1)[1].rsplit("</svg>", 1)[0]
        cells.append(f'<g transform="translate({x+10} {y+10})">{inner}</g>')
        cells.append(f'<text x="{x+60}" y="{y+112}" font-size="9" fill="#ffffff" '
                      f'text-anchor="middle" font-family="sans-serif">{n}</text>')
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{cols*cell}" '
           f'height="{rows*cell}">\n<rect width="100%" height="100%" fill="#34C759"/>\n'
           + "\n".join(cells) + "\n</svg>\n")
    (OUT / "_preview.svg").write_text(doc)


# ---------------------------------------------------------------- helpers --
# One scale for the whole set, so two icons drawn side by side stand in the
# proportion the two products do. 5.4 px/cm puts an 11.5cm brewer at 62px wide
# inside the 100px box, which leaves room for MAIN's stroke and for OXO's
# rainmaker and Clever's lid to sit above their bodies.
SCALE = 5.4
MID = 52.0     # the body's vertical centre; everything is laid out around it


def _dims(dia_cm, height_cm):
    """Real centimetres -> (top radius, top y, bottom y), centred on MID."""
    rx = dia_cm * SCALE / 2
    h = height_cm * SCALE
    return rx, MID - h / 2, MID + h / 2


def rim(cx, y, rx, sw=MAIN):
    """The top opening, in the same fixed perspective for every brewer: ry is
    a constant fraction of rx, so a wider mouth reads as wider rather than as
    tilted differently."""
    return f'<ellipse cx="{cx}" cy="{y:.1f}" rx="{rx:.1f}" ry="{rx*0.2:.1f}" stroke-width="{sw}"/>'


def walls(cx, top_y, top_rx, bot_y, bot_rx, sw=MAIN):
    return (f'<path d="M{cx-top_rx:.1f} {top_y:.1f} L{cx-bot_rx:.1f} {bot_y:.1f}" stroke-width="{sw}"/>'
            f'<path d="M{cx+top_rx:.1f} {top_y:.1f} L{cx+bot_rx:.1f} {bot_y:.1f}" stroke-width="{sw}"/>')


def cone(dia_cm, height_cm, hole_rx=4.5, cx=50):
    """A brewer that tapers to a drip hole: the V60 family. `hole_rx` is the
    hole, drawn as a small rim so the cone is visibly open rather than pointed.
    Returns (body, top_rx, top_y, bot_y) so a caller can put its own detail on
    the wall it just got the coordinates of."""
    rx, ty, by = _dims(dia_cm, height_cm)
    body = rim(cx, ty, rx) + walls(cx, ty, rx, by, hole_rx)
    body += (f'<ellipse cx="{cx}" cy="{by:.1f}" rx="{hole_rx}" ry="{hole_rx*0.5:.1f}" '
             f'stroke-width="{MAIN*0.7:.1f}"/>')
    return body, rx, ty, by


def bucket(dia_cm, height_cm, base_cm, cx=50):
    """A brewer with a genuinely flat bottom -- the Kalita/Orea/April/Stagg/OXO
    family. The base is a real measurement too: Orea's is nearly as wide as its
    mouth, April's is half of it, and that is most of what tells them apart."""
    rx, ty, by = _dims(dia_cm, height_cm)
    brx = base_cm * SCALE / 2
    body = rim(cx, ty, rx) + walls(cx, ty, rx, by, brx)
    body += (f'<path d="M{cx-brx:.1f} {by:.1f} A{brx:.1f} {brx*0.16:.1f} 0 0 0 '
             f'{cx+brx:.1f} {by:.1f}" stroke-width="{MAIN}"/>')
    return body, rx, ty, by


def _wall_x(top_rx, ty, by, bot_rx, t, cx=50):
    """A point a fraction `t` down the right-hand wall -- for hanging ribs on
    a wall whose slope differs per brewer instead of guessing coordinates."""
    return cx + top_rx + (bot_rx - top_rx) * t, ty + (by - ty) * t


# --------------------------------------------------------------- drippers --
def hario_v60():
    """Deep 60-degree cone, one big hole, one continuous spiral rib."""
    b, rx, ty, by = cone(11.6, 8.2, hole_rx=5.5)
    # The spiral: three sweeps down the front, each narrower than the last, so
    # it reads as turning around the cone rather than as stacked arcs.
    b += (f'<path d="M{50-rx*0.72:.1f} {ty+11:.1f} Q50 {ty+18:.1f} {50+rx*0.66:.1f} {ty+13:.1f} '
          f'Q50 {ty+26:.1f} {50-rx*0.50:.1f} {ty+24:.1f} '
          f'Q50 {ty+36:.1f} {50+rx*0.40:.1f} {ty+33:.1f} '
          f'Q50 {ty+43:.1f} {50-rx*0.22:.1f} {ty+41:.1f}" stroke-width="{DETAIL}"/>')
    _write("hario-v60", b)


def origami_dripper():
    """WIDER AND SHALLOWER THAN THE V60, which is the whole point of drawing
    these from real dimensions: 11.8 across by 7.2 deep against V60's 11.6 by
    8.2. Twenty sharp pleats, drawn as eight -- enough to read as pleated at
    26dp, where twenty is a grey smear -- and a wide flat-ish base, since an
    Origami sits in a holder rather than tapering to a point."""
    b, rx, ty, by = bucket(11.8, 7.2, 3.6)
    brx = 3.6 * SCALE / 2
    # A zigzag along the rim: the folds seen edge-on, and the fastest read of
    # "pleated" there is.
    n = 8
    zig = f'M{50-rx:.1f} {ty:.1f} '
    for i in range(1, n + 1):
        x = -rx + 2 * rx * i / n
        y = ty + (rx * 0.2 if i % 2 else -rx * 0.2)
        zig += f'L{50+x-rx/n:.1f} {y:.1f} L{50+x:.1f} {ty:.1f} '
    b += f'<path d="{zig}" stroke-width="{DETAIL}"/>'
    # and the folds themselves running down the wall
    for i in range(-3, 4):
        f = i / 3.5
        b += (f'<path d="M{50+rx*f*0.97:.1f} {ty+rx*0.2*0.9:.1f} '
              f'L{50+brx*f*0.95:.1f} {by-1:.1f}" stroke-width="{DETAIL*0.85:.1f}"/>')
    _write("origami-dripper", b)


def cafec_flower():
    """A V60-depth cone (11.5 x 8.3) whose twenty ribs stop short of the rim
    and curve -- the 'flower' of the name. Same family as V60, one step
    narrower at the mouth, and told apart by petals rather than a spiral."""
    b, rx, ty, by = cone(11.5, 8.3, hole_rx=5.0)
    # Five ribs that curve inward and stop short of the rim -- Cafec's flower
    # ribs. A straight fan belongs to Melitta and a folded crown to Origami;
    # the curve is what makes this one a flower rather than either of those.
    # No scalloped rim line: at icon size it sat on top of the rim ellipse and
    # read as a wobble in the rim rather than as petals.
    for f in (-1.0, -0.5, 0.0, 0.5, 1.0):
        x0 = 50 + rx * 0.86 * f
        b += (f'<path d="M{x0:.1f} {ty+9:.1f} Q{50 + (x0-50)*0.92:.1f} {ty+28:.1f} '
              f'{50 + (x0-50)*0.14:.1f} {by-5:.1f}" stroke-width="{DETAIL*0.85:.1f}"/>')
    _write("cafec-flower-dripper", b)


def melitta():
    """The wedge, and the only brewer here whose mouth is not a circle seen in
    perspective: a Melitta cone is flat-sided, so it draws as straight walls
    down to a narrow SLOT rather than a round hole. That, not a rib pattern, is
    what stops it reading as a plain V60."""
    rx, ty, by = _dims(11.0, 7.5)
    srx = 1.5 * SCALE / 2
    b = rim(50, ty, rx) + walls(50, ty, rx, by, srx)
    b += f'<path d="M{50-srx:.1f} {by:.1f} L{50+srx:.1f} {by:.1f}" stroke-width="{MAIN}"/>'
    # three plain vertical ribs -- the traditional cone, and the deliberate
    # contrast to V60's spiral
    for i in (-1, 0, 1):
        b += (f'<path d="M{50+rx*i*0.55:.1f} {ty+8:.1f} L{50+srx*i*0.8:.1f} {by-3:.1f}" '
              f'stroke-width="{DETAIL}"/>')
    _write("melitta", b)


def kono_meimon():
    """The deepest, narrowest cone in the set (10.9 x 8.9) -- steeper than a
    V60 and drawn as such -- with ribs only in the lower third, which is the
    Meimon's real tell: the upper wall is deliberately bare."""
    b, rx, ty, by = cone(10.9, 8.9, hole_rx=5.0)
    xw, yw = _wall_x(rx, ty, by, 5.0, 0.52)               # halfway down the wall
    for f in (-0.62, 0.0, 0.62):
        x0 = 50 + (xw - 50) * f
        b += (f'<path d="M{x0:.1f} {yw:.1f} L{50 + (x0-50)*0.30:.1f} {by-4:.1f}" '
              f'stroke-width="{DETAIL}"/>')
    _write("kono-meimon", b)


def clever_dripper():
    """TALLER THAN IT IS WIDE (12.4 x 11.8), which no other brewer here is, so
    the silhouette alone separates it before the lid and valve are read."""
    b, rx, ty, by = cone(12.4, 11.8, hole_rx=5.0)
    b += rim(50, ty - 6, rx * 0.86)                       # the lid, sitting proud
    b += (f'<path d="M{50-rx*0.86:.1f} {ty-6:.1f} L{50-rx*0.93:.1f} {ty:.1f} '
          f'M{50+rx*0.86:.1f} {ty-6:.1f} L{50+rx*0.93:.1f} {ty:.1f}" stroke-width="{DETAIL}"/>')
    b += f'<ellipse cx="50" cy="{ty-10:.1f}" rx="5" ry="2.2" stroke-width="{DETAIL}"/>'
    b += f'<circle cx="50" cy="{by-1:.1f}" r="3.2" stroke-width="{DETAIL}"/>'   # the valve
    _write("clever-dripper", b)


def hario_switch():
    """A V60 cone standing on the valve housing that makes it a switch (11.5 x
    10.0 all in) -- so it is visibly deeper than a plain V60, with the lever on
    the flank rather than only a rib to tell them apart."""
    b, rx, ty, by = cone(11.5, 8.0, hole_rx=5.0)
    b += (f'<path d="M{50-rx*0.70:.1f} {ty+11:.1f} Q50 {ty+18:.1f} {50+rx*0.62:.1f} {ty+13:.1f} '
          f'Q50 {ty+27:.1f} {50-rx*0.42:.1f} {ty+25:.1f}" stroke-width="{DETAIL}"/>')
    # the housing under the cone, and the lever on it
    b += (f'<path d="M{50-6:.1f} {by:.1f} L{50-6:.1f} {by+9:.1f} '
          f'A6 4 0 0 0 {50+6:.1f} {by+9:.1f} L{50+6:.1f} {by:.1f}" stroke-width="{MAIN*0.8:.1f}"/>')
    b += (f'<path d="M{50+7:.1f} {by+4:.1f} L{50+15:.1f} {by+2:.1f}" stroke-width="{DETAIL+0.8}"/>')
    _write("hario-switch", b)


def timemore_crystal_eye():
    """Mid-depth cone (11.6 x 7.6) whose mouth is FACETED, not round -- the
    only polygonal rim in the set, and the one cue that survives at 26dp where
    a rib pattern does not. The "crystal" is the shape of the thing, so it
    belongs in the outline rather than in a mark drawn on the front."""
    b, rx, ty, by = cone(11.6, 7.6, hole_rx=5.0)
    # Replace the elliptical rim this cone drew with a hexagon in the same
    # perspective: same width, same depth, straight edges.
    b = b.replace(rim(50, ty, rx), "", 1)
    ry = rx * 0.2
    pts = [(-rx, 0), (-rx * 0.5, ry), (rx * 0.5, ry), (rx, 0), (rx * 0.5, -ry), (-rx * 0.5, -ry)]
    d = "M" + " L".join(f"{50+x:.1f} {ty+y:.1f}" for x, y in pts) + " Z"
    b = f'<path d="{d}" stroke-width="{MAIN}"/>' + b
    for f in (-0.5, 0.5):                 # the two front facet edges, continued
        b += (f'<path d="M{50+rx*f:.1f} {ty+ry:.1f} L{50+5.0*f*0.9:.1f} {by-2:.1f}" '
              f'stroke-width="{DETAIL*0.85:.1f}"/>')
    _write("timemore-crystal-eye", b)


def bee_house():
    """A bellied ceramic body on a WIDE FLAT FLANGE -- the lip that rests
    across a mug, which is the Bee House's silhouette in one line and nothing
    else here has."""
    rx, ty, by = _dims(11.0, 7.5)
    flange = rx * 1.16
    b = rim(50, ty, flange)
    b += (f'<path d="M{50-flange:.1f} {ty:.1f} Q{50-rx*0.98:.1f} {ty+18:.1f} '
          f'{50-rx*0.42:.1f} {by:.1f}" stroke-width="{MAIN}"/>'
          f'<path d="M{50+flange:.1f} {ty:.1f} Q{50+rx*0.98:.1f} {ty+18:.1f} '
          f'{50+rx*0.42:.1f} {by:.1f}" stroke-width="{MAIN}"/>')
    b += (f'<path d="M{50-rx*0.42:.1f} {by:.1f} A{rx*0.42:.1f} {rx*0.09:.1f} 0 0 0 '
          f'{50+rx*0.42:.1f} {by:.1f}" stroke-width="{MAIN}"/>')
    for dx in (-3.5, 3.5):                                # the two drip holes
        b += f'<circle cx="{50+dx}" cy="{by-0.5:.1f}" r="1.5" stroke-width="1.6"/>'
    _write("bee-house-dripper", b)


def kalita_wave():
    """Shallow (11.5 x 7.0), flat 5.5cm base, three holes -- and the scalloped
    filter rim it is named for, drawn exaggerated so it survives 26dp."""
    b, rx, ty, by = bucket(11.5, 7.0, 5.5)
    n = 6
    wave = f'M{50-rx:.1f} {ty:.1f} '
    for i in range(1, n + 1):
        x = -rx + 2 * rx * i / n
        wave += f'Q{50+x-rx/n:.1f} {ty-rx*0.26:.1f} {50+x:.1f} {ty:.1f} '
    b += f'<path d="{wave}" stroke-width="{DETAIL}"/>'
    for dx in (-4.5, 0, 4.5):
        b += f'<circle cx="{50+dx}" cy="{by-1:.1f}" r="1.5" stroke-width="1.6"/>'
    _write("kalita-wave", b)


def orea_brewer():
    """THE SHALLOWEST BREWER HERE (11.5 x 6.0) on the widest flat base --
    nearly straight walls, which is exactly what an Orea looks like and what
    separates it from April and Kalita at a glance."""
    b, rx, ty, by = bucket(11.5, 6.0, 8.4)
    brx = 8.4 * SCALE / 2
    b += (f'<path d="M50 {by-2:.1f} Q{50+brx*0.62:.1f} {by-2:.1f} {50+brx*0.62:.1f} {by-7:.1f} '
          f'Q{50+brx*0.62:.1f} {by-12:.1f} 50 {by-12:.1f} '
          f'Q{50-brx*0.48:.1f} {by-12:.1f} {50-brx*0.48:.1f} {by-8:.1f}" '
          f'stroke-width="{DETAIL}"/>')
    _write("orea-brewer", b)


def april_brewer():
    """Kalita's proportions with none of its marks: April's identity is that
    there is nothing to draw but the shape and one centred hole."""
    b, rx, ty, by = bucket(11.5, 7.0, 5.5)
    b += f'<circle cx="50" cy="{by-1:.1f}" r="1.7" stroke-width="{DETAIL}"/>'
    _write("april-brewer", b)


def fellow_stagg():
    """Tall for a flat-bottom brewer (11.4 x 8.9) with near-vertical walls --
    a deep cylinder next to Kalita's shallow bowl -- plus the twin pour lips."""
    b, rx, ty, by = bucket(11.4, 8.9, 7.6)
    for sx in (-1, 1):
        x = 50 + sx * rx * 0.80
        b += (f'<path d="M{x-3.4:.1f} {ty-rx*0.14:.1f} Q{x:.1f} {ty-rx*0.44:.1f} '
              f'{x+3.4:.1f} {ty-rx*0.14:.1f}" stroke-width="{DETAIL+0.4}"/>')
    _write("fellow-stagg", b)


def oxo_brew():
    """Deep flat-bottom body (12.5 x 10.0) under the perforated rainmaker lid
    -- the strongest single differentiator in the set, and now on a body that
    is genuinely the biggest one too."""
    b, rx, ty, by = bucket(12.5, 8.6, 6.5)
    lid = ty - 15
    b += rim(50, lid, rx * 0.66)
    for dx, dy in ((-8, 0), (0, -1.4), (8, 0), (-4, 1.6), (4, 1.6)):
        b += f'<circle cx="{50+dx}" cy="{lid+dy:.1f}" r="1.2" stroke-width="1.5"/>'
    # the stem it hangs from, clear of both the lid and the rim so the two
    # read as two objects
    b += f'<path d="M50 {lid+5:.1f} L50 {ty-3:.1f}" stroke-width="{DETAIL}"/>'
    _write("oxo-brew", b)


def chemex():
    """An hourglass carafe -- its own family, and the one icon whose outline
    is a closed shape rather than a rim over two walls."""
    b = ('<path d="M33 15 L67 15 L58 46 Q67 57 67 66 Q67 84 50 84 '
         f'Q33 84 33 66 Q33 57 42 46 Z" stroke-width="{MAIN}"/>')
    b += f'<path d="M31 15 L69 15" stroke-width="{MAIN}"/>'
    b += f'<path d="M32 50 L68 50" stroke-width="{DETAIL+0.6}"/>'
    b += f'<path d="M32 57 L68 57" stroke-width="{DETAIL+0.6}"/>'
    _write("chemex", b)


DRIPPERS = [hario_v60, melitta, kalita_wave, clever_dripper, bee_house,
            origami_dripper, fellow_stagg, orea_brewer, april_brewer,
            cafec_flower, timemore_crystal_eye, hario_switch, kono_meimon,
            oxo_brew, chemex]

if __name__ == "__main__":
    for fn in DRIPPERS:
        fn()
    # read the written stems back off disk rather than re-deriving them from
    # function names, since a couple don't map 1:1 (cafec_flower wrote
    # "cafec-flower-dripper", not "cafec-flower")
    # `not startswith("_")`: the sheet this line feeds is itself an .svg in
    # this folder, so a second run would find _preview.svg and draw the sheet
    # inside itself, shifting every cell by one.
    written = sorted(p.stem for p in OUT.glob("*.svg") if not p.stem.startswith("_"))
    _preview(written)
    print(f"wrote {len(written)} icons + _preview.svg")
