# coffee_android v1

The Kotlin/Compose app itself — a self-contained Gradle project. Everything
under here is version 1; a future version becomes a sibling `../v2/` rather than
a branch, so a shipped version stays readable as a directory.

```
v1/
  settings.gradle.kts   build.gradle.kts   gradle.properties
  app/                  the module (namespace app.coffeecan)
  screenshots/          33 simulated screenshots, 1080x2400 PNG
  screenshots.py        what draws them
  check_design.py       scheme E drift check; passes on colour, type and shape
  AUDIT.md              conformance review of exactly this code
```

The design plan, the API contract and the per-screen specs live one level up in
`../plan/`; the binding compliance documents live in `../../specs/`. Read
`../plan/README.md` before changing anything here, and `AUDIT.md` for what this
build currently gets wrong.

## Building

**Not from this checkout.** There is no Android SDK, no Gradle and no wrapper
here — `gradlew` is missing and has to be generated on a machine that has
Gradle, on JDK 17 or 21:

```bash
cd coffee_android/v1
gradle wrapper --gradle-version 8.9
./gradlew assembleDebug
```

Four `buildConfigField`s in `app/build.gradle.kts` ship empty and the app is
inert without them — sign-in throws and both AI features are unreachable (see
AUDIT.md B4). Real values belong in `local.properties` or CI secrets, never
committed:

| Field | What it is |
| --- | --- |
| `AI_API_KEY` | gateway key for the metered endpoints |
| `READ_API_KEY` | gateway key for `/v1/catalogue` and `/v1/news` |
| `GOOGLE_SERVER_CLIENT_ID` | the OAuth **web** client ID, checked as the token audience by `coffee_server/auth.py` |
| `SERVER_BASE_URL` | defaults to `https://api.coffeecan.app/` |

The Network Security Config refuses cleartext with no exceptions, so a local
`coffee_server` on plain HTTP is unreachable by design. Terminate TLS in front
of it rather than relaxing the config.

## Screenshots

```bash
python3 screenshots.py          # -> screenshots/*.png
python3 screenshots.py --svg    # keep the vector source alongside
```

Needs Chrome or Chromium on `PATH` for rasterisation, and Fredoka installed for
correct type; no Python dependencies. **These are simulations drawn from the
Kotlin, not captures of a running app** — this checkout cannot run one. The
docstring in `screenshots.py` says exactly what they are faithful about and what
they are not. When a screen changes, change the corresponding function there in
the same commit, the way `../plan/scheme_e.py` is kept in step with the deck.

## Checking the design against scheme E

```bash
python3 check_design.py      # exits 1 while drift remains
```

Diffs all 33 colour tokens, all 11 type roles and the shape set against
`../plan/variants.py` `PURE_GREEN` + `FREDOKA_STYLE`, then checks that every
string `screenshots.py` draws exists in the Kotlin or in `coffee_server`.

It exists because reading `Theme.kt`'s own comment is not a check: the first
version of that comment correctly claimed the colours were copied exactly, and a
review that trusted it missed a type scale wrong in ten of eleven roles. All
four sections pass today — the eleven type roles, the chip pill and the scrim
were brought over in the scheme E pass, along with the capsule field, the deck's
FAB fill, the bar dividers and the 16dp gutter.

**Still open**, and each is separate work: the in-app brand mark, the can-boy
mascot, the dripper glyphs, Home's contribution heatmap, `0.2`'s photo hero and
Images strip, the Share Card, and `+1.1`'s three-choice menu. `AUDIT.md` §5.6
through §5.10 is the list.

**What it cannot check is layout, density, component choice and illustration.**
For those, render a deck page and put it next to the matching frame:

```bash
google-chrome --headless=new --window-size=1080,2400 \
  --screenshot=/tmp/deck.png ../plan/screenshots/scheme-e/00_home.svg
```

## The two things easiest to break

- **`net/AiGateway.kt` is the chokepoint.** Consent, connectivity and auth are
  checked in one place. Never call `ServerApi` from a screen, and never add a
  second `OkHttpClient` — the app talks to `coffee_server` and to nothing else
  (`../../specs/legal-android.md` §4 rule 23).
- **`AndroidManifest.xml` has no `CAMERA` permission and must not gain one.**
  Adding it does not enable capture, it breaks it: Android requires an app that
  *declares* `CAMERA` to also hold it before `ACTION_IMAGE_CAPTURE` will launch.
  The same file's `allowBackup="false"` is what keeps the app's headline claim
  true; verify it in the merged manifest, not here.
