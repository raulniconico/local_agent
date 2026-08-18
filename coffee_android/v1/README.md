# coffee_android v1

The Kotlin/Compose app itself — a self-contained Gradle project. Everything
under here is version 1; a future version becomes a sibling `../v2/` rather than
a branch, so a shipped version stays readable as a directory.

```
v1/
  settings.gradle.kts   build.gradle.kts   gradle.properties
  app/                  the module (namespace app.coffeecan), 53 Kotlin files
  screenshots/          44 PNGs + REAL_CAPTURES.md; a mix of Paparazzi output
                        (360x800) and screenshots.py simulations (1080x2400)
  screenshots.py        what draws the simulations
  check_design.py       scheme E drift check; colour, type, shape, copy
  AUDIT.md              HISTORICAL conformance review (2026-08-14)
```

**Start with [`../plan/v1/design-spec.md`](../plan/v1/design-spec.md)** — the
standardised specification of what this build is: colour, type, shape,
components, navigation, every screen, the data model and the API contract.
`../plan/README.md`, `screens.md` and `api.md` are the design *proposal* that
preceded it, and `AUDIT.md` is a historical audit whose headline findings have
since been fixed. The binding compliance documents live in `../../specs/`.

## Building and installing

The wrapper is generated (Gradle 8.11.1) and `local.properties` points at a
real SDK, so this checkout builds as it stands. **`JAVA_HOME` must name a JDK
17** — it is not tidiness: on a newer JDK the Kotlin compiler aborts with
`IllegalArgumentException: <version>` out of `JavaVersion.parse` before it
looks at any of this code.

```bash
cd coffee_android/v1
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk    # -r keeps the database
adb shell am start -n app.coffeecan/.MainActivity           # optional
```

`adb` lives in `$ANDROID_HOME/platform-tools/`, which is not necessarily on
`PATH`; `adb devices` should list the phone before the install (USB debugging
on, and the RSA prompt accepted on the device). `installDebug` does the build
and the install in one step and is equivalent.

The APK is signed with the local debug key. Reinstalling over a build signed
by a *different* key fails rather than damaging anything, but the only way
past it is `adb uninstall app.coffeecan`, **which deletes the on-device
database and photos** — export a sync bundle first (Profile → "Send to
desktop", or `coffee_agent`'s USB tools).

Neither Play Store nor release signing is set up here; nothing in this section
produces a shippable artifact.

Four `buildConfigField`s in `app/build.gradle.kts` ship empty, and a build
made without them is **half an app**: everything local works — beans,
sessions, photos, the flavour radar, sync bundles — while sign-in throws and
both AI features (label scan, news) are unreachable (see AUDIT.md B4). That is
the state a plain `assembleDebug` here produces. Real values belong in
`local.properties` or CI secrets, never committed:

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
Kotlin, not captures of a running app** — for real frames, either install to a
phone (above) or render a composable through Paparazzi
(`app/src/test/.../screenshot/`, goldens in `app/src/test/snapshots/images/`;
see `PaparazziEnvironment.kt` for the `compileSdk = 35` toggle that run
needs). The
docstring in `screenshots.py` says exactly what they are faithful about and what
they are not. When a screen changes, change the corresponding function there in
the same commit, the way `../plan/scheme_e.py` is kept in step with the deck.

## Checking the design against scheme E

```bash
python3 check_design.py      # exits 1 while drift remains
```

Diffs all 36 colour tokens, all 11 type roles and the shape set against
`../plan/variants.py` `PURE_GREEN` + `FREDOKA_STYLE`, then checks that every
string `screenshots.py` draws exists in the Kotlin, in `res/values/strings.xml`
or in `coffee_server`.

It exists because reading `Theme.kt`'s own comment is not a check: the first
version of that comment correctly claimed the colours were copied exactly, and a
review that trusted it missed a type scale wrong in ten of eleven roles. All
four sections pass today, with **one recorded deviation** it prints under its
own heading — `surface` is `#FFFFFF` in the app against the deck's `#F2FAF2`,
because page and cards are both plain white and nothing outlines a block.

**It must read the resources, not just the Kotlin.** The localisation pass moved
every user-facing string into `strings.xml`; a version of this script that read
only `*.kt` reported ~72 present strings as missing, which is worse than no
check — a wall of false positives is how a real drift stops being noticed.

**Closed since the scheme E pass:** the in-app brand mark, the can-boy mascot,
the dripper glyphs, Home's contribution heatmap, `0.2`'s photo hero and Images
strip, the Share Card, and `+1.1`'s three-choice menu are all built.
`AUDIT.md` is historical — see `../plan/v1/design-spec.md` for what v1 is now.

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
