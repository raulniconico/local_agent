# `plan/v1/` — the audit, checking and monitoring workflow for v1

Two directories, one hard boundary:

| | Holds | Rule |
| --- | --- | --- |
| `../../v1/` | **The shipped implementation.** Gradle module, Kotlin sources, resources, and the tests Gradle owns | Nothing here judges itself |
| `plan/v1/` (here) | **Everything that judges it.** The binding specs, the drift checker, the simulator, the frames, the historical audit | Reads `../../v1/`; never writes to it |

The split exists so the module can be read and shipped without wading through
its own review, and so nothing on the audit side can be mistaken for something
a user runs. The one thing that *cannot* move here is `../../v1/app/src/test/`:
Gradle resolves unit tests inside the module, so the Paparazzi goldens stay
with the code they render.

## Specifications — read before changing anything

| File | Read it when |
| --- | --- |
| [`design-spec.md`](design-spec.md) | **Before any change to `../../v1/`.** What v1 is: colour, type, shape, components, navigation, every screen, data model, API contract, localisation, accessibility, verification. §12.3 lists every place the older plan documents are now wrong |
| [`coupling-spec.md`](coupling-spec.md) | **Before *and* after any change, as the audit.** What else moves when you change one thing, and the commands that prove you found it all. Its §0 is a four-step checklist |

The two are complements, not overlaps: `design-spec.md` is the *target state*,
`coupling-spec.md` is the *blast radius*. A change can satisfy one and violate
the other — a correctly restyled component whose golden was never re-recorded
passes the design spec and fails the coupling spec.

## Tooling — run from this directory

```bash
python3 check_design.py      # exit 0 = no drift.  36 colour + 11 type + 5 shape
                             # tokens against ../variants.py, and 109 strings
                             # against the module's Kotlin/strings.xml/coffee_server
python3 screenshots.py       # redraw the simulator frames -> screenshots/*.png
python3 screenshots.py --svg # keep the vector source alongside
```

`screenshots.py` needs Chrome or Chromium on `PATH` and Fredoka installed for
correct type; neither script has Python dependencies. Both resolve the module
as `APP = ../../v1` and read it read-only.

| File | |
| --- | --- |
| `check_design.py` | The drift checker. Its `ACCEPTED_DEVIATIONS` is **not** a suppression list — an entry needs a decision recorded in `Theme.kt`, and both values still print on every run |
| `screenshots.py` | Draws the simulator frames *from the Kotlin*. When a screen changes, change its function here in the same commit, the way `../scheme_e.py` is kept in step with the deck |
| `screenshots/` | 49 simulated PNGs + `REAL_CAPTURES.md`. **Not evidence** — see `coupling-spec.md` §8 |
| `AUDIT.md` | The 2026-08-14 conformance review. **Historical**, not current state — but it is the `AUDIT.md` that ~40 comments across `../../v1/app/src/` cite by bare name, so it stays readable and stays here |

## What stayed in `../` and why

- **`../README.md`, `../api.md`, `../screens.md`** — the pre-build proposal and
  the specialist-review resolutions. Historical. `design-spec.md` §12.3
  tabulates their specific false statements; do not patch them into agreement,
  the record of what was decided and then overtaken is the point.
- **`../variants.py`, `../wireframes.py`, `../scheme_e.py`** — the *deck*
  generators, one level up because they describe scheme E itself rather than
  this build of it, and because they are a tight import cluster: `variants`
  imports `wireframes`, `scheme_e` imports both. `check_design.py` reaches them
  by `PLAN = HERE.parent`. `../variants.py` remains the source of truth for
  every design token.
- **`../screenshots/`** — the rendered *deck* (23 SVGs, schemes A–E). Distinct
  from `screenshots/` here, which is the *app* simulator's output.

## Paths

Every document and script in this folder uses paths relative to this folder:
`../` is `plan/`, `../../v1/` is the Gradle module, `../../../specs/` is the
repo-level specs directory.
