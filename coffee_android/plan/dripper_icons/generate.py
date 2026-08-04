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

Every dripper is a variation on one of two base silhouettes -- a tapered
cone (V60, Melitta, Bee House, Origami, Cafec Flower, Timemore, Hario
Switch, Kono Meimon) or a flat-bottomed brewer (Kalita Wave, Fellow Stagg,
Orea, April, OXO) -- plus Chemex and Clever Dripper, which don't fit either
family. Rather than inventing 15 arbitrary shapes, each one keeps its real
product's single most identifying visual trait (V60's spiral rib, Kalita's
wavy rim, Chemex's wood collar, etc.) and drops everything else, since at
icon size one strong, correct cue reads faster than several faint ones.
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
def cone(top_cx, top_y, top_rx, bottom_y, bottom_rx, sw=MAIN):
    """Truncated-cone silhouette: top rim ellipse, two slanted walls, and a
    small bottom rim standing in for the single/triple pour hole."""
    return (
        f'<ellipse cx="{top_cx}" cy="{top_y}" rx="{top_rx}" ry="6" stroke-width="{sw}"/>'
        f'<path d="M{top_cx-top_rx} {top_y} L{top_cx-bottom_rx} {bottom_y}" stroke-width="{sw}"/>'
        f'<path d="M{top_cx+top_rx} {top_y} L{top_cx+bottom_rx} {bottom_y}" stroke-width="{sw}"/>'
        f'<ellipse cx="{top_cx}" cy="{bottom_y}" rx="{bottom_rx}" ry="2.6" stroke-width="{sw*0.7:.1f}"/>'
    )


def flat_bottom(top_cx, top_y, top_rx, bottom_y, bottom_rx, sw=MAIN):
    """Trapezoid brewer: wide top rim tapering to a genuinely FLAT bottom
    (an arc, not a point) -- the Kalita/Orea/April/Stagg/OXO family, as
    opposed to cone()'s pointed base."""
    return (
        f'<ellipse cx="{top_cx}" cy="{top_y}" rx="{top_rx}" ry="6" stroke-width="{sw}"/>'
        f'<path d="M{top_cx-top_rx} {top_y} L{top_cx-bottom_rx} {bottom_y}" stroke-width="{sw}"/>'
        f'<path d="M{top_cx+top_rx} {top_y} L{top_cx+bottom_rx} {bottom_y}" stroke-width="{sw}"/>'
        f'<path d="M{top_cx-bottom_rx} {bottom_y} A{bottom_rx} 3 0 0 0 {top_cx+bottom_rx} {bottom_y}" '
        f'stroke-width="{sw}"/>'
    )


# --------------------------------------------------------------- drippers --
def hario_v60():
    b = cone(50, 30, 26, 82, 5)
    # one continuous spiral rib -- V60's own signature, and what separates
    # it from every straight-ribbed or unribbed cone below
    b += (f'<path d="M32 38 Q50 44 68 40 Q52 52 36 50 Q52 62 64 56 '
          f'Q54 70 42 66 Q52 76 58 74" stroke-width="{DETAIL}"/>')
    _write("hario-v60", b)


def melitta():
    b = cone(50, 32, 22, 80, 6)
    # straight vertical ribs, not spiral -- the plainest, most traditional
    # cone in the set, and the direct contrast to V60's spiral
    for dx in (-13, -6.5, 0, 6.5, 13):
        b += f'<path d="M{50+dx*0.86:.1f} 37 L{50+dx*0.30:.1f} 76" stroke-width="{DETAIL}"/>'
    _write("melitta", b)


def kalita_wave():
    b = flat_bottom(50, 32, 27, 72, 15)
    # the wavy/scalloped filter rim is the Wave's whole namesake -- drawn
    # exaggerated so it still survives a 24dp inline size
    wave = "M23 32 "
    for i in range(1, 9):
        x = 23 + i * 6.75
        y = 32 + (4.5 if i % 2 else -4.5)
        wave += f"Q{x-3.4:.1f} {y:.1f} {x:.1f} 32 "
    b += f'<path d="{wave}" stroke-width="{DETAIL}"/>'
    for dx in (-6, 0, 6):
        b += f'<circle cx="{50+dx}" cy="72" r="1.7" stroke-width="{DETAIL*0.8:.1f}"/>'
    _write("kalita-wave", b)


def clever_dripper():
    b = cone(50, 34, 24, 78, 5)
    # a flat lid, collared onto the rim, plus a valve nub at the point --
    # the immersion brewer's tell: no other cone here has a lid, because a
    # cone this steep should drain straight through without one
    b += f'<ellipse cx="50" cy="25" rx="22" ry="5" stroke-width="{MAIN}"/>'
    b += f'<path d="M28 25 L26 34 M72 25 L74 34" stroke-width="{DETAIL}"/>'
    b += f'<ellipse cx="50" cy="20.5" rx="6" ry="2.6" stroke-width="{DETAIL}"/>'
    b += f'<circle cx="50" cy="80" r="3.4" stroke-width="{DETAIL}"/>'
    _write("clever-dripper", b)


def bee_house():
    # a real belly, not a gentle taper -- the "beehive" curve, drawn
    # pronounced enough that it doesn't read as a variant V60 at a glance
    b = (f'<ellipse cx="50" cy="28" rx="26" ry="6" stroke-width="{MAIN}"/>'
         f'<path d="M24 28 Q14 52 30 66 Q38 73 42 80" stroke-width="{MAIN}" fill="none"/>'
         f'<path d="M76 28 Q86 52 70 66 Q62 73 58 80" stroke-width="{MAIN}" fill="none"/>'
         f'<ellipse cx="50" cy="80" rx="8" ry="2.4" stroke-width="{MAIN*0.7:.1f}"/>')
    for dx in (-9, 0, 9):
        b += f'<path d="M{50+dx*1.15:.1f} 36 L{50+dx*0.4:.1f} 75" stroke-width="{DETAIL}"/>'
    _write("bee-house-dripper", b)


def origami_dripper():
    b = cone(50, 30, 26, 82, 5)
    # a fan of sharp pleated folds around the rim -- many small notches,
    # unlike Kalita's few round waves or Cafec's soft petals below
    for i in range(10):
        ang = -70 + i * 15.5
        x1 = 50 + 26 * math.sin(math.radians(ang))
        b += (f'<path d="M{x1:.1f} 31 L{50+(x1-50)*0.32:.1f} '
              f'{30+((82-30)*0.82):.1f}" stroke-width="{DETAIL}"/>')
    _write("origami-dripper", b)


def fellow_stagg():
    b = flat_bottom(50, 30, 24, 74, 16)
    # twin pour spouts, integrated into the rim as small notches -- Stagg
    # X's signature double lip
    for sx in (-1, 1):
        x = 50 + sx * 21
        b += (f'<path d="M{x-3:.1f} 26.5 Q{x:.1f} 21 {x+3:.1f} 26.5" '
              f'stroke-width="{DETAIL+0.4}"/>')
    _write("fellow-stagg", b)


def orea_brewer():
    b = flat_bottom(50, 32, 22, 76, 18)
    # deliberately just the swirl flow-channel on the flat base and nothing
    # else -- Orea's one distinguishing mark, in keeping with how minimal
    # the real brewer is
    b += (f'<path d="M50 76 Q60 76 60 70 Q60 64 50 64 Q42 64 42 69 '
          f'Q42 73 47 73" stroke-width="{DETAIL}"/>')
    _write("orea-brewer", b)


def april_brewer():
    b = flat_bottom(50, 32, 23, 76, 17)
    # the plainest silhouette in the set on purpose -- April's whole
    # identity is minimalism, so one small centred hole is the entire mark
    b += f'<circle cx="50" cy="76" r="1.8" stroke-width="{DETAIL}"/>'
    _write("april-brewer", b)


def cafec_flower():
    b = cone(50, 30, 25, 82, 5)
    # soft rounded petal bumps around the rim -- gentler and rounder than
    # Origami's sharp folds, which is the "flower" reading
    petal = ""
    for i in range(7):
        x = 27 + i * 7.7
        petal += f"Q{x+3.85:.1f} 24 {x+7.7:.1f} 30 "
    b += f'<path d="M27 30 {petal}" stroke-width="{DETAIL}"/>'
    _write("cafec-flower-dripper", b)


def timemore_crystal_eye():
    b = cone(50, 30, 24, 82, 5)
    # faceted (straight, diamond-cut) panel lines for the "crystal" look,
    # plus the brand's own circular "eye" motif low on the cone
    for dx in (-12, -4, 4, 12):
        b += f'<path d="M{50+dx*1.05:.1f} 34 L{50+dx*0.30:.1f} 78" stroke-width="{DETAIL}"/>'
    b += (f'<ellipse cx="50" cy="58" rx="7" ry="4.5" stroke-width="{DETAIL}"/>'
          f'<path d="M46.5 58 L53.5 58" stroke-width="1.6"/>')
    _write("timemore-crystal-eye", b)


def hario_switch():
    b = cone(50, 30, 26, 82, 5)
    # V60's own spiral rib (same family), plus the switch lever a plain V60
    # doesn't have, low on the flank
    b += (f'<path d="M32 38 Q50 44 68 40 Q52 52 36 50 Q52 62 64 56 '
          f'Q54 70 42 66" stroke-width="{DETAIL}"/>')
    b += f'<path d="M68 66 L76 66" stroke-width="{DETAIL+0.6}"/>'
    b += f'<circle cx="66" cy="66" r="2.2" stroke-width="{DETAIL}"/>'
    _write("hario-switch", b)


def kono_meimon():
    b = cone(50, 30, 25, 82, 5)
    # just three short ribs, low on the cone only -- the Meimon's tell,
    # leaving the upper wall bare (unlike Melitta's full-height ribs). Three
    # reads as "ribbed" without the clutter more lines caused at icon size.
    for dx in (-9, 0, 9):
        b += f'<path d="M{50+dx*0.60:.1f} 60 L{50+dx*0.32:.1f} 78" stroke-width="{DETAIL}"/>'
    _write("kono-meimon", b)


def oxo_brew():
    b = flat_bottom(50, 38, 24, 80, 16)
    # the rainmaker: a perforated disc hovering above the brewer, unique to
    # OXO's design and the strongest possible single differentiator here
    b += f'<ellipse cx="50" cy="18" rx="17" ry="4.2" stroke-width="{MAIN}"/>'
    for dx, dy in ((-8, 0), (0, -1.4), (8, 0), (-4, 1.6), (4, 1.6)):
        b += f'<circle cx="{50+dx}" cy="{18+dy}" r="1.1" stroke-width="1.6"/>'
    b += f'<path d="M50 22 L50 32" stroke-width="{DETAIL}"/>'
    _write("oxo-brew", b)


def chemex():
    # an hourglass carafe -- a completely different family from every
    # cone/flat-bottom brewer above -- plus the wood-collar band at the
    # neck, Chemex's other unmistakable trait
    b = ('<path d="M32 14 L68 14 L58 46 Q66 58 66 66 Q66 82 50 82 '
         f'Q34 82 34 66 Q34 58 42 46 Z" stroke-width="{MAIN}"/>')
    b += f'<path d="M30 14 L70 14" stroke-width="{MAIN}"/>'
    b += f'<path d="M31 51 L69 51" stroke-width="{DETAIL+0.6}"/>'
    b += f'<path d="M31 58 L69 58" stroke-width="{DETAIL+0.6}"/>'
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
    written = sorted(p.stem for p in OUT.glob("*.svg"))
    _preview(written)
    print(f"wrote {len(written)} icons + _preview.svg")
