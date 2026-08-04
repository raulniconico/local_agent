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



# ----------------------------------------------------------------- can-boy --
# A separate mascot mark, distinct from the shipped logo (wf.logo /
# coffee_can/assets/icon.svg, unmodified). White line only, flat, on its own
# green disc so the white reads against this page's light background. Arms
# and legs are each a single stroked line -- no double green+white pass, no
# filled hand/foot caps. The "Can" lettering is not redrawn in outline: it
# reuses the shipped wordmark's own solid glyphs (wf._LOGO_WORD) rescaled
# into the belly, so the text matches the real logo exactly.
def can_boy(c, cx, cy, size):
    """Spec'd in a 100x100 box; `size` is the rendered edge in dp."""
    g = size / 100.0
    c.add(f'<g transform="translate({cx - size/2:.2f} {cy - size/2:.2f}) scale({g:.4f})">')
    c.add(f'<circle cx="50" cy="50" r="50" fill="{wf.BRAND_MARK}"/>')

    c.add('<g fill="none" stroke="#FFFFFF" stroke-linecap="round" stroke-linejoin="round">')
    # limbs, drawn under the can so its outline overlaps the shoulder/hip join
    c.add('<g stroke-width="4.2">')
    c.add('<path d="M30 40 Q19 44 17 55"/>')   # left arm, hand on hip
    c.add('<path d="M70 38 Q81 29 79 16"/>')   # right arm, raised
    c.add('<path d="M41 75 L37 90"/>')          # left leg
    c.add('<path d="M59 75 L63 90"/>')          # right leg
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
    c.add("</g>")


# ------------------------------------------------------------- -1w intro ----
def can_drink_intro():
    """First run of the Can Drink page (swipe left from Home)."""
    c = wf.Canvas("Can Drink · intro — scheme E")
    wf.status_bar(c)
    can_boy(c, 180, 210, 220)
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
