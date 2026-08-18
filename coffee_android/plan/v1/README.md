# `plan/v1/` — the binding specification set

Everything in this folder **binds current work** on `coffee_android/v1/`.
Everything in the parent `plan/` folder is the *proposal and its review
history*, kept for provenance and superseded wherever the two disagree.

| File | Read it when |
| --- | --- |
| [`design-spec.md`](design-spec.md) | **Before any change to `../../v1/`.** What v1 is: colour, type, shape, components, navigation, every screen, data model, API contract, localisation, accessibility, verification. §12.3 lists every place the older plan documents are now wrong |
| [`coupling-spec.md`](coupling-spec.md) | **Before any change, as the audit.** What else moves when you change one thing, and the commands that prove you found it all |

The two are complements, not overlaps: `design-spec.md` is the *target state*,
`coupling-spec.md` is the *blast radius*. A change can satisfy one and violate
the other — a correctly restyled component whose golden was never re-recorded
passes the design spec and fails the coupling spec.

## What stayed in `../` and why

- **`../README.md`, `../api.md`, `../screens.md`** — the pre-build proposal and
  the specialist-review resolutions. Historical. `design-spec.md` §12.3
  tabulates their specific false statements; do not patch them into agreement,
  the record of what was decided and then overtaken is the point.
- **`../variants.py`, `../wireframes.py`, `../scheme_e.py`** — generators, not
  specifications. `variants.py` *is* the source of truth for design tokens, but
  it is executable and sits in a tight import cluster: `variants` imports
  `wireframes`, `scheme_e` imports both, and `../../v1/check_design.py:46`
  resolves them by `HERE.parent / "plan"`. Moving one moves all three plus two
  `sys.path` lines in `../../v1/`, for no gain. They are referenced from here as
  `../variants.py` and audited by `check_design.py`.
- **`../screenshots/`, `../dripper_icons/`** — rendered assets. See
  `coupling-spec.md` §8 for why `../screenshots/*.png` must never be used as
  evidence that the app looks a certain way.

## Paths

Both documents in this folder use paths **relative to this folder**:
`../` is `plan/`, `../../v1/` is the app module, `../../../specs/` is the
repo-level specs directory.
