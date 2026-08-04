#!/usr/bin/env python3
"""Scheme E — the official design. Built page by page on scheme D's palette
and type (pure green + Fredoka + rounded shapes).

    python3 scheme_e.py         # write the SVG pages
    python3 scheme_e.py --gif   # also build the motion GIFs

Pages live in screenshots/scheme-e/.

Numbering follows the swipe axis, centred on Home:

    00w   welcome / splash — off-axis, shown once at cold launch
    -2    <- swipe left     -1    <- swipe left
    00    HOME
    +1    swipe right ->    +2    swipe right ->

A page's state is a suffix on the same number (00_home, 00_home_empty), since
states are the same destination, not a different one.
"""
from __future__ import annotations
import math, pathlib, sys, subprocess, tempfile

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



# --------------------------------------------------------- the can character ---
# A new pose of the mascot that already exists in the desktop app
# (widgets.py: default_avatar_pixmap / thumbs_up_can_pixmap / WalkingCanStrip).
# On-model proportions are preserved: body 22x19 with a 24x8 lid overlapping by
# 3, feet at a 3:2 ellipse ratio, stubby and heavily rounded — squarer corners
# are what made earlier attempts read as a waste bin.
#
# Limbs are drawn TWICE: a green pass (the outline) then, after the body, a
# white pass inset by the stroke width. That is what lets an arm join the body
# with a continuous contour instead of a gap. Layer order is load-bearing —
# see _LAYERS below; interleaving it puts a green bar across the can's flank.
CAN_INK = "#196D2E"


def can_character(c, x, y, size):
    """Spec'd in a 100x100 box; `size` is the rendered edge in dp."""
    g = size / 100.0
    c.add(f'<g transform="translate({x - 2.3 * g:.2f} {y}) scale({g:.4f})" '
          f'stroke-linecap="round" stroke-linejoin="round">')

    # 1 · ground
    c.add('<ellipse cx="50" cy="82" rx="26" ry="3.4" fill="#C3D3C4" opacity="0.55"/>')

    LIMBS = (  # (path or ellipse, green width, white width)
        ('<path d="M27.4 38 C20.2 40.4 15.4 45 14.8 50.4 '
         'C14.4 54.4 18.6 55.6 22.4 52.4 L24.6 49.6" fill="none"', 10.0, 5.2),
        ('<path d="M73 38.2 C79.4 37.4 84.4 34.6 86.8 30" fill="none"', 10.0, 5.2),
        ('<path d="M38.6 62 L37.4 73.4" fill="none"', 9.4, 4.6),
        ('<path d="M61.4 62 L62.6 73.4" fill="none"', 9.4, 4.6),
    )
    BLOBS = (  # (cx, cy, green rx, green ry, white rx, white ry)
        (25.0, 48.0, 6.6, 6.0, 4.2, 3.6),      # akimbo fist, on the hip
        (88.2, 27.6, 6.6, 6.2, 4.2, 3.8),      # raised fist, holding the bean
        (35.0, 76.0, 9.0, 6.8, 6.6, 4.4),      # feet, planted wider than the
        (65.0, 76.0, 9.0, 6.8, 6.6, 4.4),      # walk-cycle spacing
    )

    # 2 · green pass
    for d, gw, _ in LIMBS:
        c.add(f'{d} stroke="{CAN_INK}" stroke-width="{gw}"/>')
    for cx, cy, rx, ry, _, _ in BLOBS:
        c.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{CAN_INK}"/>')

    # 3 · the can itself, over the green pass
    c.add(f'<rect x="25.8" y="25" width="48.4" height="41.8" rx="8.8" '
          f'fill="#FFFFFF" stroke="{CAN_INK}" stroke-width="2.4"/>')
    c.add(f'<rect x="23.6" y="14" width="52.8" height="17.6" rx="6.6" '
          f'fill="#C3EDC5" stroke="{CAN_INK}" stroke-width="2.4"/>')

    # 4 · white pass — punches the joins through the body outline
    for d, _, ww in LIMBS:
        c.add(f'{d} stroke="#FFFFFF" stroke-width="{ww}"/>')
    for cx, cy, _, _, rx, ry in BLOBS:
        c.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#FFFFFF"/>')

    # 5 · label band, covering the leg tops
    c.add('<rect x="28.8" y="53" width="42.4" height="11.6" rx="5" fill="#34C759"/>')
    c.add(f'<text x="50" y="63.3" font-family="{FREDOKA}" font-size="13" '
          f'font-weight="600" letter-spacing="0.4" text-anchor="middle" '
          f'fill="#FFFFFF">Can</text>')

    # 6 · face — onSurface, deliberately NOT the contour green, so it reads as
    #     a face rather than as more outline
    c.add('<circle cx="41" cy="36" r="3" fill="#1B241C"/>')
    c.add('<circle cx="59" cy="36" r="3" fill="#1B241C"/>')
    c.add('<path d="M43 41.5 Q50 50 57 41.5" fill="none" stroke="#1B241C" '
          'stroke-width="2.8"/>')

    # 7 · curled fingers — what sells a blob as a hand
    for d in ("M21.6 46.6 L26.6 46", "M21.8 49.6 L27 49",
              "M84.8 27.8 L91 27", "M85.2 30.4 L90.8 29.6"):
        c.add(f'<path d="{d}" fill="none" stroke="{CAN_INK}" stroke-width="1.5"/>')

    # 8 · the bean, last so it sits in front of the fingers and reads as held.
    #     The crease is an S with unequal bulges: a symmetric curve reads as an
    #     eye, a straight one as a pill seam.
    c.add('<g transform="translate(88.4 19.5) rotate(-15)">'
          f'<ellipse cx="0" cy="0" rx="5.2" ry="6.9" fill="#7E4A2E" '
          f'stroke="{CAN_INK}" stroke-width="2"/>'
          '<path d="M0.7 -5.6 C2.4 -2.8 -2.2 2 0.3 5.6" fill="none" '
          'stroke="#F2FAF2" stroke-width="1.7" stroke-linecap="round"/></g>')
    c.add("</g>")


# ------------------------------------------------------------- -1w intro ----
def can_drink_intro():
    """First run of the Can Drink page (swipe left from Home)."""
    c = wf.Canvas("Can Drink · intro — scheme E")
    wf.status_bar(c)
    can_character(c, 56, 92, 248)
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


PAGES = [("00w_welcome.svg", welcome),
         ("00_home_empty.svg", home_empty),
         ("-1w_can_drink_intro.svg", can_drink_intro)]

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


MOTION = {"00w_welcome": welcome_frames, "00_home_empty": home_empty_frames}


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
