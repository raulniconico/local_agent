# coffee_android v1

The Kotlin/Compose app itself — a self-contained Gradle project. Everything
under here is version 1; a future version becomes a sibling `../v2/` rather than
a branch, so a shipped version stays readable as a directory.

```
v1/
  settings.gradle.kts   build.gradle.kts   gradle.properties
  gradlew  gradle/      the wrapper (Gradle 8.11.1)
  app/                  the module (namespace app.coffeecan), 53 Kotlin files
    src/main/           what ships
    src/test/           Paparazzi goldens + geometry/ingest tests (Gradle owns
                        these; they cannot live outside the module)
```

**This directory is the shipped implementation and nothing else.** Every audit,
check and monitoring artefact lives in [`../plan/v1/`](../plan/v1/) — the design
spec, the coupling spec, `check_design.py`, `screenshots.py`, the simulator
frames and the historical `AUDIT.md`. The split is deliberate: what ships and
what judges it are separate, so the module can be read (and shipped) without
wading through its own review, and the audit side can never be mistaken for
something a user runs. The audit tools read this directory and never write to
it.

**Start with [`../plan/v1/design-spec.md`](../plan/v1/design-spec.md)** — the
standardised specification of what this build is: colour, type, shape,
components, navigation, every screen, the data model and the API contract.
`../plan/README.md`, `../plan/screens.md` and `../plan/api.md` are the design
*proposal* that preceded it, and `../plan/v1/AUDIT.md` is a historical audit
whose headline findings have since been fixed — **the bare `AUDIT.md` cited
throughout this module's comments is that file.** `../plan/v1/coupling-spec.md`
is the change audit: run it before editing anything under `app/`. The binding
compliance documents live in `../../specs/`.

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

Four `buildConfigField`s are read from **`local.properties`** (git-ignored) by
`app/build.gradle.kts`, falling back to placeholders when it has nothing to
give. Copy [`local.properties.example`](local.properties.example) and fill it
in; that example file is the tracked documentation of every key, and the real
values are never committed.

A build made without them is **half an app**: everything local works — beans,
sessions, photos, the flavour radar, sync bundles — while sign-in throws and
both AI features (label scan, news) are unreachable (see AUDIT.md B4). That is
the state a plain `assembleDebug` produces on a fresh clone, and it is the
intended state — `SERVER_BASE_URL` falls back to an RFC 2606 `.invalid` host
that never resolves, so an unconfigured build fails loudly instead of quietly
talking to production.

| Field | What it is |
| --- | --- |
| `AI_API_KEY` | gateway key for the metered endpoints |
| `READ_API_KEY` | gateway key for `/v1/catalogue` and `/v1/news` |
| `GOOGLE_SERVER_CLIENT_ID` | the OAuth **web** client ID, checked as the token audience by `coffee_server/auth.py` |
| `SERVER_BASE_URL` | the gateway host, from `local.properties`; defaults to an unroutable `.invalid` host so an unconfigured build cannot reach production |

The Network Security Config refuses cleartext with no exceptions, so a local
`coffee_server` on plain HTTP is unreachable by design. Terminate TLS in front
of it rather than relaxing the config.

## Verifying a change

The tooling lives in `../plan/v1/` and is run from there, not from here:

```bash
cd ../plan/v1
python3 check_design.py        # 36 colour + 11 type + 5 shape tokens, 88 strings
python3 screenshots.py         # redraw the simulator frames -> screenshots/*.png
```

`check_design.py` reads this module (`Theme.kt`, `app/src/main/**`,
`res/values/strings.xml`, `app/build.gradle.kts`) and writes nothing into it.
It exists because reading `Theme.kt`'s own comment is not a check: the first
version of that comment correctly claimed the colours were copied exactly, and
a review that trusted it missed a type scale wrong in ten of eleven roles.

The tests that *do* live here are the ones Gradle owns:

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
./gradlew :app:verifyPaparazziDebug   # 72 goldens
./gradlew :app:recordPaparazziDebug   # re-record, then read the diff
```

Paparazzi needs `compileSdk = 35` for the duration of a run and **36 restored
immediately after** — see `app/src/test/.../PaparazziEnvironment.kt`, and
`../plan/v1/coupling-spec.md` §6, which is where that trap is documented.

**None of this covers layout, density, component choice, illustration, window
insets, gesture timing or share targets.** For the first four, render a deck
page next to the matching frame; for the rest there is no substitute for a
physical device.

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
