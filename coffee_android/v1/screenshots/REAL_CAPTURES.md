# Which PNGs in this directory are real

`screenshots.py`'s own docstring has always said the frames it draws are
simulations, not captures -- there was no way to compile this checkout, so a
hand-maintained Python approximation was the best available evidence, and
`AUDIT.md` records three cases where that approximation had drifted from the
actual Kotlin (fabricated a brand mark, paraphrased a legal string, showed
the wrong metering keys).

That's no longer the only option. `app/src/test/java/app/coffeecan/screenshot/`
now has real Paparazzi tests -- the actual Compose code, compiled and
rendered through layoutlib on the JVM, no emulator needed (see
`PaparazziEnvironment.kt` for the one caveat: it runs at `compileSdk = 35`,
toggled back to 36 immediately after, because Paparazzi 1.3.5 doesn't yet
know API 36's `android.os.Build`). Run them and copy the output into this
directory with `collect_paparazzi.py` (scratch script, not checked in --
recreate it from the test-run's `build/reports/paparazzi/debug/runs/*.js`
files, which map test name to output PNG).

**Real captures, as of 2026-08-15** (superseding the simulator for these):

| File | Test |
| --- | --- |
| `+1.1_log_brew.png` | `WhichBeanSheetScreenshotTest#logBrewSheet` |
| `+1.1a_pick_bean.png` | `PickBeanScreenScreenshotTest#pickBean` |
| `+1.1c_vibe_brewing.png` | `BrewSessionScreenScreenshotTest#newSession` |
| `brew_session_populated.png` | `BrewSessionScreenScreenshotTest#populatedSession` (no deck page number -- the deck only draws the blank vibe-brewing state, not a filled-in edit) |
| `0.1_bean_new.png` | `BeanDetailScreenScreenshotTest#beanNew` |
| `0.2_bean_detail.png` | `BeanDetailScreenScreenshotTest#beanDetail` -- task #10's photo-hero rebuild, re-captured. No photo attached in the test's fake data, so the hero renders `BeanPhotoHero`'s gradient placeholder branch, not a real photo -- and the deck's top-right disc is Share Card export (task #13, not built), so this shows Delete in that slot instead, per the code's own documented substitution. Only the visible-without-scrolling portion; the Images/Sessions sections further down the panel aren't re-verified against the deck by this capture. |
| `00_home.png` / `00_home_empty.png` | `HomeScreenScreenshotTest#home` / `#homeEmpty` |
| `+1_sessions.png` | `SessionsScreenScreenshotTest#sessions` |
| `+2_profile.png` / `+2_profile_empty.png` | `ProfileScreenScreenshotTest#signedIn` / `#signedOut` |
| `+2.2a_privacy.png` | `PrivacyScreenScreenshotTest#privacy` |
| `+2.2b_how_we_use_ai.png` | `AiDisclosureScreenScreenshotTest#aiDisclosure` |
| `0.11a_ai_disclosure_labels.png` | `AiDisclosureSheetScreenshotTest#readLabelsNeedsAgeAffirmation` -- also the first real render of AUDIT.md B1's age checkbox, unaffirmed state |
| `+1.4_ai_disclosure_suggest.png` | `AiDisclosureSheetScreenshotTest#suggestBrewAgeAlreadyAffirmed` -- same checkbox, already-affirmed state (hidden, button live) |

**Second batch, also 2026-08-15** -- the sheets and dialogs, unlocked by
splitting each one's content out of its `ModalBottomSheet`/depended-on state
(`WhichBeanSheet`'s own precedent), plus confirming `AlertDialog` itself
renders fine directly under Paparazzi with no such split needed:

| File | Test |
| --- | --- |
| `+1.3_stage_editor.png` | `BrewSessionScreenScreenshotTest#stageEditor` |
| `+1.5_suggestion.png` | `BrewSessionScreenScreenshotTest#suggestion` |
| `+1.6_delete_brew.png` | `BrewSessionScreenScreenshotTest#deleteBrewDialog` |
| `brew_session_discard.png` | `BrewSessionScreenScreenshotTest#discardBrewDialog` -- no deck page number, same reasoning as `brew_session_populated.png`: AUDIT.md B3's discard-confirm dialog didn't exist when the deck was drawn |
| `+2.2c_report.png` | `AiDisclosureScreenScreenshotTest#reportSheet` |
| `0.2c_flavor_manual.png` | `BeanDetailScreenScreenshotTest#flavorManual` |
| `0.2d_delete_bean.png` | `BeanDetailScreenScreenshotTest#deleteBeanDialog` |
| `bean_detail_discard.png` | `BeanDetailScreenScreenshotTest#discardBeanDialog` -- same no-deck-number reasoning as `brew_session_discard.png` |
| `0.11_photo_source.png` | `BeanDetailScreenScreenshotTest#photoSource` |
| `0.12_scanning.png` / `0.12b_scan_offline.png` / `0.12c_scan_blocked.png` | `BeanDetailScreenScreenshotTest#scanning` / `#scanOffline` / `#scanBlocked` -- `ScanSection` made `internal` for this; the card's `secondaryContainer` fill against `background` is genuinely this subtle in the app's own theme, confirmed against `0.1_bean_new.png`'s full-screen rendering of the same card |
| `0.13_scan_review.png` / `0.13b_scan_review_empty.png` | `ScanReviewSheetScreenshotTest#scanReview` / `#scanReviewEmpty` |
| `+1_sessions_empty.png` | `SessionsScreenScreenshotTest#sessionsEmpty` |
| `+2.4_delete_account.png` | `AccountControlsScreenshotTest#deleteAccount` |
| `+2.3_data_access.png` | `AccountControlsScreenshotTest#dataAccessSignedOut` -- **partial**: only the signed-out "there is no account" read is real. The signed-in body calls `app.ai.accountRecord(context)` from a `LaunchedEffect`, which isn't stubbed anywhere in this test suite (`TestFakes.kt` fakes `repository`/`consent`/`accounts`, not the AI gateway) -- that half of the sheet is still simulated. |

Removed outright rather than kept alongside a real replacement, because they
no longer correspond to anything in the code: `+1.1_which_bean.png` (the old,
now-rewritten sheet content -- see task #8), `+1.1b_which_bean_empty.png`
(the "no beans" state of that same old inline sheet, which no longer exists
in that shape), and `+1.2_log_brew.png` / `+1.2b_log_brew_lower.png`
(`screenshots.py`'s own invented number for the brew session screen -- the
real deck files under `plan/screenshots/scheme-e/` never actually used
`+1.2` for anything).

**Third capture, 2026-08-15, later the same day**: `00w_welcome.png` --
`WelcomeScreenScreenshotTest#welcome`, the resting (fade = 1) state of the
real `ui/screens/WelcomeScreen.kt` this pass added. Supersedes the note
below, which was true of the *previous* build (the platform SplashScreen API
only, no Compose screen behind it) but not of this one -- see AUDIT.md
§5.10 item 3's status block for the full story, including the Home-flash
bug this same change fixed.

**Fourth batch, 2026-08-15** -- the `-1` page, which is now coffee news rather
than the Can-Drink catalogue (product decision; see `plan/README.md`). These
are new files, not replacements: the deck has no `-1` news frame to compare
against, because the page did not exist when the deck was drawn.

| File | Test |
| --- | --- |
| `-1_news.png` | `NewsScreenScreenshotTest#news` -- also the check that only rule 74's four fields reach the screen, and that an undated item renders its source without a dangling separator |
| `-1_news_unavailable.png` | `NewsScreenScreenshotTest#newsUnavailable` -- the 503 branch, which is what ships today: `CRAWLER_ENABLED` is off, so this is the state a real user sees |
| `-1_news_offline.png` | `NewsScreenScreenshotTest#newsOffline` -- offline with an empty cache, the one empty state that offers a retry |

**Fifth batch, 2026-08-15** -- the mascots, which now animate.

| File | Test |
| --- | --- |
| `mascot_shutter_flash.png` | `MascotScreenshotTest#shutterFlash` -- the camera pose at p = 0.53, mid-burst, the phase the deck's own `bean_profile_empty` default freezes on |
| `mascot_heartbreak.png` | `MascotScreenshotTest#heartbreakSettled` -- `can_boy_sad`'s resting frame, heart fully broken |

These exist because a Paparazzi snapshot never advances the animation clock,
so every other capture of an animated mascot is necessarily its **first**
frame. That is why `-1_news_unavailable.png` and `-1_news_offline.png` show
can-boy with the heart still *whole*: on a device it breaks 280ms after the
page appears. `0.1_bean_new.png` likewise shows the camera pose at phase 0
(no burst), which is its rest pose and close to the still it replaced.

Both poses are drawn live now (`ui/components/CanBoy.kt`) rather than from
flattened `VectorDrawable`s, and were pixel-diffed against the deck rendering
the same function at the same size before landing: worst channel delta 53/255
on `can_boy_sad` and 54/255 on `can_boy_camera`, with nothing above 96 and
~0.17% of pixels above 32 -- stroke antialiasing, not structure.

**Still simulated**:
- `0.2b_bean_detail_lower`, `0.2e_saved_snackbar` -- below-the-fold content and a transient Snackbar state respectively; lower priority, not attempted this pass.
- The signed-in half of `+2.3_data_access` -- see the table above.

Treat every other file in this directory exactly as `screenshots.py`'s
docstring always said: evidence of what the source claims, not proof it
renders that way.
