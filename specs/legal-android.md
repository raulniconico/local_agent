# coffee_android — Google Play policy compliance spec

A binding design specification for `coffee_android`, the planned native Android
(Kotlin + Jetpack Compose) port of `coffee/` (coffee-can), covering what the
Google Play Developer Program Policies require before this app can ship on
Play. Distinct from `specs/legal.md`, which governs an unrelated feature (a
web crawler for French roaster catalogues) — that document's crawler-specific
findings (French/EU IP law, GDPR for scraped data, `robots.txt`) do not apply
here except where GDPR is invoked below in its own right, for this app's own
data flows.

Produced from a three-way expert review (Data Safety/Privacy & Permissions ·
Generative AI Content/IP/Rating · Technical & Store Compliance) conducted
2026-08-03 against live `support.google.com`/`developer.android.com` pages,
not training-data recall — Play policy churns often enough (target API level
moves ~yearly; the Photo & Video Permissions policy finished phasing in as
recently as May 2025; a third-party-AI clarification landed **three weeks
before this review**) that stale memory is actively dangerous here.

**Not legal advice.** Nothing below substitutes for review by counsel,
particularly the GDPR/international-transfer questions in §2.4, before a
production listing goes live.

- [1. Project background](#1-project-background)
- [2. Development details — the policy analysis](#2-development-details--the-policy-analysis)
- [3. API — the binding rules](#3-api--the-binding-rules)
- [4. Addendum — the roaster-catalogue and news features must not run client-side](#4-addendum--the-roaster-catalogue-and-news-features-must-not-run-client-side)

---

## 1. Project background

### What this covers

`coffee_android` is a v1 scoped as a straight port of `coffee-can`'s core
loop — bean profiles, brew sessions, photo-based OCR of bean-bag labels, and
AI-generated brew suggestions — onto Kotlin/Jetpack Compose, targeting a
first-time submission to Google Play's production track under an individual
("Personal") developer account.

Three architectural facts drive almost every finding below and should be
treated as load-bearing, not incidental:

1. **No accounts, no cloud sync, no server-side data store in v1.** All bean/
   brew data lives on-device (Room/SQLite), mirroring the desktop app's
   local-only design. This single fact exempts the app from the Account
   Deletion policy entirely and simplifies the Data Safety form — but it is
   fragile: the first version that adds an optional account or cloud backup
   re-triggers that policy in full (§3.5).
2. **AI features are proxied, never direct.** Photos and structured bean/
   session data are sent over HTTPS to `coffee_server` (the sibling FastAPI
   gateway, already built), which forwards to Anthropic Claude and/or Qwen.
   No AI-provider API key is ever shipped in the APK. This is good security
   hygiene and also the right shape for the July 2026 Play policy
   clarification on third-party AI integrations (§2.4).
3. **No in-app content is ever visible to other users.** The "share card"
   export is a one-way push through Android's OS share sheet to *external*
   apps — it is not a feed, review system, or any surface where one
   coffee_android user sees another's data. This is what keeps the app out of
   the User Generated Content policy's moderation-stack requirements (§2.2).

Each of these facts is a **design constraint to preserve**, not just a
description of the current plan — see §3 for what breaks if any of them
changes.

### Relationship to other specs

`coffee_android` will consume `coffee_server`'s existing gateway endpoints
(see `specs/coffee-server.md`) rather than calling Anthropic/Qwen directly,
and its data model is expected to mirror `coffee/`'s (`specs/coffee.md`)
closely enough that the two apps could eventually share a sync format —
that's a future-looking note, not a v1 commitment. The Android app-design plan
itself (screens, API calls, page-by-page realization) lives in
`coffee_android/plan/`, produced as the next stage after this spec.

---

## 2. Development details — the policy analysis

### 2.1 Data Safety, Privacy & Permissions

**Data Safety form (mandatory for every app, including this one).** Photos
must be declared as a collected data type since they leave the device for
OCR/suggestion processing. Whether that leg also counts as data **shared
with a third party** (a stricter Play category than "collected") turns on
Anthropic's and Qwen's actual data-use terms for the API tier `coffee_server`
uses: Play's own definition excludes transfers to a "service provider...
based on the developer's instructions" from "sharing," which is the pattern
here *if* Anthropic/Qwen don't retain the data for their own purposes (e.g.
model training). This is a documentation task, not a code task — get the
provider terms in writing before answering the form.

**EXIF/location leak risk — easy to miss, worth building around from day
one.** If bean-bag or session photos are read through a generic file API
that preserves EXIF GPS tags, and those photos transit the network or land in
an exported share-card image, the app can be forced into declaring
**Precise location** in Data Safety despite having no location feature at
all. Strip EXIF location before any photo leaves the device.

**Photo/media permissions.** Play's Photo and Video Permissions policy
(fully enforced since **May 28, 2025**) requires a Permissions Declaration
Form to justify `READ_MEDIA_IMAGES`/`READ_MEDIA_VIDEO`. coffee_android's
photo need — one bean-bag photo, one optional session photo — is the
textbook case the system **Android Photo Picker**
(`ACTION_PICK_IMAGES`/`PickVisualMedia`) exists for, and the Photo Picker
needs neither the permission nor the declaration. `CAMERA` (for direct
capture) is a separate, ordinary runtime permission with no declaration-form
regime attached.

**Privacy policy.** Required universally, but especially load-bearing here
because of the camera + remote-AI-processing flow: must be a live, public,
non-geofenced URL (no PDFs), linked from both Play Console metadata *and*
somewhere inside the app itself (a Settings screen), and must name the
`coffee_server` → Anthropic/Qwen flow, retention at each hop, and how a user
gets local data removed (uninstall/clear storage, since there's no account).

**Prominent disclosure & consent — the single highest-priority action item in
this whole spec.** Play's User Data policy requires an **in-app** disclosure,
shown immediately before the relevant action and requiring affirmative
consent, whenever a data use wouldn't be "reasonably expected" by the user —
distinct from, and prior to, the OS's own `CAMERA` permission dialog. A user
photographing a coffee bag for OCR does not automatically expect that photo
to leave the device for third-party AI processing; that gap is exactly what
this rule targets, and it was freshly reinforced by the July 2026 policy
clarification below. Concretely: show a one-time (and periodically re-shown)
in-app modal — "Your photo will be sent to an AI service to read the label
and suggest brew settings" — with an explicit affirmative action, the first
time the OCR/suggestion feature is triggered, gated separately from manual
entry (which needs no such disclosure).

### 2.2 Generative AI Content, IP & Content Rating

**Generative AI Content policy — a genuine gray area, not a clean exemption.**
Play's policy targets apps where "AI-generated chatbot interaction is a
central feature," and explicitly excludes apps that merely "use AI to
improve an existing feature" (Google's own example: AI-suggested email
drafts). coffee_android's narrow, structured OCR + brew-suggestion feature
reads as closer to the excluded category by analogy — but no official source
draws a bright line between "central" and "supporting," so this is
interpretation, not a quoted carve-out. Given the low cost of compliance, add
a lightweight "report/flag this suggestion" control on AI-generated text
regardless of which side of the line it falls on — cheap insurance against a
borderline classification on review. A **separate** obligation — declaring
AI-generated/edited *store-listing* assets (screenshots, promo video) — only
applies if such assets are actually used, and does not reach the in-app
feature at all.

**Content rating (IARC questionnaire).** Mandatory for every app; no
official source publishes the exact live question set (it's inside Play
Console only), so treat any categorization here as directional. Given no
violence/sexual/gambling/drug content and no cross-user interaction, the app
should land at the lowest tier across authorities (ESRB Everyone / PEGI 3).
Answer "no" to any UGC/interaction question — over-declaring UGC status would
pull in moderation obligations the app doesn't need (see below).

**IP/trademark from incidental roaster-branding in user photos — out of
Play-policy's lane.** Play's Intellectual Property policy targets the
*developer's own* use of a mark (app icon, listing assets), not a user
photographing their own purchased product for personal cataloguing — no
official language reaches that case, and it is functionally identical to any
receipt-scanner or notes app. This is a general trademark-law question, not
a store-policy one; flagged here explicitly so it isn't mistaken for a Play
compliance gap.

**Impersonation — the actually-live risk in this neighborhood.** Distinct
from IP: displaying a roaster's name as user-entered text data is fine;
designing the share-card's branding so it implies partnership/endorsement by
the roaster, or by Anthropic/Qwen, is not. Practical rule: keep app branding
visually subordinate to the user's own data on the share card, never
reproduce a roaster's *logo graphic* (as opposed to its name as plain text),
and never phrase the store listing as "official" or "partnered."

**User Generated Content policy — not triggered in v1, by Google's own
definition** ("content... visible to or accessible by at least a subset of
the app's users"). Nothing in coffee_android is visible to any user but its
owner; the share-card export leaves the app entirely via the OS share sheet
rather than surfacing inside it. This is the second architectural fact from
§1 doing real work — the moment any feature makes one user's data visible to
another (a public review feed, a shared roaster directory), the full UGC
moderation stack (terms-of-use gate, defined prohibited-content list,
in-app reporting *and* blocking) activates and should be scoped as its own
project, not retrofitted.

### 2.3 Technical & Store Compliance

**Target API level.** New apps must target **Android 16 (API level 36)**
starting **August 31, 2026** (extension available to November 1, 2026, but
don't plan around it). Build against API 36 from the start — this is a hard
upload-time gate, re-verify the number at actual submission since it moves
roughly yearly.

**New personal-account closed-testing gate — the most schedule-relevant item
in this entire spec.** Personal Play Console accounts created after November
13, 2023 must run a **closed test with ≥12 testers, each opted in
continuously for ≥14 days**, before production access is even available to
apply for (lowered from 20 testers in December 2024 — re-verify the number
hasn't moved again). Internal testing doesn't count toward this. This means
recruiting ~12 real external testers who will actually install and keep the
app for two weeks is a genuine, non-technical prerequisite that belongs in
the project timeline, not an afterthought at submission time.

**App Signing.** Play App Signing is the default, effectively-mandatory path
for a new AAB-based submission; an upload keystore is still generated and
held by the developer (keep it out of git, alongside any secrets, matching
this repo's existing `.env`-is-gitignored convention). No reason to opt into
self-managed app-signing keys for this project.

**Network security.** `targetSdkVersion 36` already blocks cleartext HTTP by
Android platform default; ship an explicit Network Security Config with
`cleartextTrafficPermitted="false"` and no domain exceptions as
belt-and-suspenders, and confirm `coffee_server`'s deployed endpoint actually
terminates TLS. This also satisfies Play's own User Data policy requirement
that personal data be transmitted with modern cryptography — a genuine
store-policy citation, not just an Android OS default.

**Permissions/manifest.** Confirmed independently by two of the three
reviews: use the Photo Picker, not `READ_MEDIA_IMAGES`; `CAMERA` alone needs
no declaration form. Requesting broader media permissions than the picker
supplies is the single most avoidable source of extra review friction for a
brand-new developer account that's already navigating the testing gate
above.

**Backend/API-key architecture.** No Play policy text specifically addresses
client-vs-server API key placement; the closest hooks are generic
"transmit user data securely" language. Routing AI calls through
`coffee_server` rather than embedding provider keys client-side is good
security hygiene and consistent with `coffee_agent`'s existing pattern in
this repo, but it is not itself a documented Play compliance requirement —
recorded here so it isn't mistaken for one.

**Mandatory content declarations.** A checklist, all "must actively answer"
even when the true answer is "no": Ads (no), Target audience (general),
Content rating questionnaire, Data Safety section, Government apps
declaration (no — relevant to confirm since a "yes" would require an
organizational account, not personal), News/COVID/Financial-features
declarations (all not applicable, still must be affirmatively answered).
None of these are skippable by leaving them blank; Play Console won't allow
a release without them completed.

**Account/data deletion.** Not triggered — the policy's trigger is
account-creation from within the app, which v1 has none of. The Data
Safety form's separate "can users request data deletion" question can be
answered honestly based on local-only storage (uninstall/clear-storage is a
complete, immediate deletion — stronger than the policy's own 90-day
automatic-deletion allowance) — but only once it's confirmed `coffee_server`
doesn't persist OCR/suggestion request payloads server-side; if it does,
that retention needs disclosing too (ties directly to §2.1's "collected vs.
shared" documentation task).

### 2.4 GDPR/CCPA and the July 2026 Play policy clarification

Two things converge here and should be read together, not separately.

**Independent of Play policy**, GDPR applies as a matter of EU law the
moment any EU user's photo is processed: the developer is the data
**controller**, `coffee_server` is a **processor**, and Anthropic/Qwen are
**sub-processors** — Qwen (Alibaba, China-based) adds an international-
transfer dimension (GDPR Ch. V, SCCs or equivalent) independent of whichever
backend `coffee_server` happens to be configured against, and Anthropic
(US-based) implicates the same question post-*Schrems II*. This is a genuine
legal-drafting task (DPA language, sub-processor disclosure, a data-subject
access/erasure contact channel) that exceeds what Play's own policy pages
require and should get outside-counsel sign-off before an EU-facing
production listing, not just an internal read of this spec.

**On the Play-policy side**, a clarification dated **2026-07-15** — three
weeks before this review, and the freshest finding in this entire spec —
states that Play's User Data policy requirements "also apply to third-party
AI integrations" and that developers "remain responsible for ensuring
compliance... including limited use, disclosure and consent" regardless of
who processes the data downstream. Practical effect for coffee_android: the
in-app disclosure-and-consent step from §2.1 must specifically name the
AI-processing step, not just camera access generally, and that bar should be
treated as actively enforced rather than a stale carryover rule, given how
recently it was restated.

---

## 3. API — the binding rules

Normative. Every rule below is a design constraint on `coffee_android` and
should be re-checked against live Play Console/support pages at actual
submission time — several of these numbers (§3.2, §3.3) have already moved
once and will move again.

### 3.1 Photos, permissions & disclosure

1. **Use the Android Photo Picker for existing-photo selection; `CAMERA` +
   CameraX/Camera2 for capture.** Never request `READ_MEDIA_IMAGES`,
   `READ_MEDIA_VIDEO`, `READ_EXTERNAL_STORAGE`, or `MANAGE_EXTERNAL_STORAGE`.
2. **Strip EXIF location data from every photo before it leaves the device**
   — before the network call to `coffee_server` and before it's embedded in
   any exported share-card image. Do this at the point of capture/selection,
   not as a filter later.
3. **Request `CAMERA` only at point of use** (the moment the user taps
   "take photo"), never at first launch.
4. **Show an in-app disclosure-and-consent modal before the first use of the
   OCR/brew-suggestion feature**, separate from and prior to the OS `CAMERA`
   permission dialog: plain-language statement that the photo is sent to a
   remote AI service, what's sent, and an explicit affirmative action to
   continue. Gate the AI path behind this; manual entry needs no such gate.

### 3.2 AI content & moderation

5. **Add a "report/flag" control on AI-generated brew-suggestion text**
   (and optionally OCR output), routed anywhere a developer can act on it —
   even a local export or email-to-developer flow satisfies the reporting
   requirement for an app this size. Treat this as cheap insurance against
   the unresolved "central vs. supporting feature" classification question
   (§2.2), not as optional polish.
6. **Keep the AI feature scoped to structured, factual/advisory output**
   (OCR transcription, brew parameter suggestions) rather than open-ended
   free-text chat — this preserves the strongest available argument that the
   feature is a supporting enhancement, not a central chatbot experience.
7. **Never check the Play Console "AI-generated store listing content"
   declaration** unless a screenshot or promo video is actually
   AI-generated/edited — this is unrelated to the in-app feature.

### 3.3 Branding, IP & impersonation

8. **Never use a roaster's logo graphic**, or Anthropic's/Qwen's logos, in
   the app icon, screenshots, or share-card image. Displaying a roaster's
   *name* as user-entered text data is fine.
9. **Keep app branding visually subordinate to the user's own data** on the
   exported share card — no layout choice may imply partnership or
   endorsement by any roaster or AI provider.
10. **Store listing may accurately describe AI-assisted features** ("uses AI
    to suggest brew parameters") but must not imply an exclusive partnership
    or official endorsement by Anthropic, Qwen, or any named roaster.

### 3.4 Data handling, transport & disclosures

11. **Document Anthropic's and Qwen's data-retention/data-use terms for the
    specific API products `coffee_server` uses**, in writing, before
    completing the Data Safety form — this determines whether the OCR/AI leg
    is "collected" or "shared with a third party" under Play's definitions.
12. **Confirm whether `coffee_server` persists OCR/suggestion request
    payloads server-side.** If it does, disclose that retention in both the
    privacy policy and the Data Safety form; if it doesn't, the "local-only,
    transient AI round-trip" framing throughout this spec holds.
13. **Ship a Network Security Config with `cleartextTrafficPermitted="false"`
    and no domain exceptions.** Confirm `coffee_server`'s deployed endpoint
    terminates TLS before submission.
14. **Publish a privacy policy** naming the `coffee_server` → Anthropic/Qwen
    flow, retention at each hop, and the local-deletion mechanism; link it
    from both Play Console metadata and an in-app Settings screen.
15. **Do not add EU-facing production distribution without a GDPR
    sub-processor/international-transfer review** (Qwen = China, Anthropic =
    US) signed off by counsel — this is explicitly flagged as exceeding what
    this spec or Play's own policy pages can resolve alone.

### 3.5 What changes the moment accounts or cloud sync are added

16. **The instant any future version adds an optional account or cloud
    backup, the full Account Deletion policy activates**: build the in-app
    deletion path *and* the public web-based deletion URL into that feature
    from the start, not as a follow-up. Do not ship an account feature
    without both.
17. **The instant any feature makes one user's data visible to another user**
    (a public review feed, a shared roaster directory, following) — even
    sync across the same user's own devices does *not* count, only
    cross-user visibility does — **the app becomes a UGC app** under Play's
    definition and needs, before launch of that feature: a terms-of-use
    acceptance gate, a defined prohibited-content list, and in-app reporting
    *and blocking* of other users' content. Scope this as its own project
    when it happens; do not retrofit.

### 3.6 Store submission mechanics

18. **Build against `targetSdkVersion 36` (Android 16)** — re-verify the
    exact required level at `developer.android.com/google/play/requirements/target-sdk`
    at actual submission time, since it advances roughly yearly and this
    project isn't built yet.
19. **Plan a closed-testing phase into the release timeline as a real
    milestone, not an afterthought**: recruit ≥12 testers who will install
    and keep the app for a continuous 14-day window before production access
    can even be requested — re-verify the tester count at submission time
    (it has already changed once, 20→12).
20. **Accept the default Play App Signing enrollment**; generate and
    securely store the upload keystore (git-ignored, matching this repo's
    `.env`-is-gitignored convention), never commit it.
21. **Complete every mandatory App Content declaration before the first
    closed-testing upload** — Ads, Target audience, Content rating
    questionnaire, Data Safety, Government apps, News/COVID/Financial
    (answered "not applicable" where true) — none are skippable by omission.
22. **Re-run the content rating questionnaire and the Data Safety form any
    time app content or data flow changes** — both are explicit,
    re-triggered obligations, not one-time setup.

---

## 4. Addendum — the roaster-catalogue and news features must not run client-side

Discovered while inventorying `coffee-can`'s existing pages for the design
plan (§1 already anticipated this in outline; this section resolves it):
the desktop app's "Can drink" shelf, "Can see" catalogue, and news ticker
call `whats_new.py` and `coffee_news.py` directly from the GUI process — one
desktop instance, scraping a handful of roaster storefronts and RSS feeds on
a 24h/2h cache.

**That is exactly the private, single-user, single-crawler-instance premise
`specs/legal.md` §1.2 use-case (a) was scoped around** — a household-exemption
argument, `BHB`-favorable sui generis analysis, and a rate-limiting model
(concurrency 1, ~12 requests/day) all implicitly assume there is *one*
crawler in the world making these requests.

**Porting those two modules unchanged into an Android client, distributed
through Google Play, breaks that premise the moment the app has more than a
handful of installs.** Each device independently re-scraping the same
roaster endpoints turns "a guy with a script" into an uncoordinated swarm
hitting the same five-to-eight storefronts, multiplies request volume by
install count with no coordination or shared cache, and — separately from
the traffic question — **Play distribution itself is a fact pattern closer to
"published app" than "private tool"** regardless of monetization, which is
exactly the axis `specs/legal.md` §1.2 uses to move risk from low to
medium/high across every heading (droit d'auteur, sui generis, parasitisme).

23. **The roaster-catalogue and news-ranking fetch must run centrally —
    once, on a schedule, server-side — never as a per-device client call.**
    Concretely: `whats_new.fetch_listings()` and `coffee_news.fetch_news()`
    (or their logical equivalents) belong behind a `coffee_server` endpoint
    that performs the actual crawl on the existing §3.4 rate-limit/schedule
    rules (still one crawler instance, still ~12 requests/day, unchanged),
    caches the result, and serves every Android client a **read from that
    cache** — never a device-initiated request to a roaster's own host. This
    is a hard architectural constraint on the design plan, not an
    optimization.
24. **This is also just better engineering independent of the legal
    reasoning** — one server-side cache instead of N independent client
    caches, no risk of thousands of devices thundering-herd a roaster site
    the moment a cache expires simultaneously, and it keeps `specs/legal.md`
    §3's entire kill-switch/circuit-breaker/blocklist apparatus meaningful
    (a per-device kill switch shipped inside an APK cannot be updated the
    instant a roaster complains; a server-side one can, within the 24h
    window rule 44 already promises).
25. **Re-open `specs/legal.md` §1.2 before this app reaches production
    distribution**, per that spec's own rule ("record the chosen use case...
    and re-open this spec before changing it") — Play distribution is a
    material change to the use-case classification even though the app
    itself charges nothing and shows no ads. This spec does not resolve that
    re-classification; it only flags that the trigger condition (a) → (b)-ish
    has been reached and hands it back to `specs/legal.md`'s own process.
26. **The `RemoteImageLabel` hotlink-only-on-selection pattern (never
    caching product photos) still ports directly** — that part of the
    design was already client-safe (a live pointer to the roaster's CDN, not
    a copy), and stays that way whether the request originates from a
    desktop process or, if ever necessary, a server-side proxy of the same
    live fetch. Photo hotlinking is not part of the centralization
    requirement above unless a future privacy/CORS constraint forces
    proxying it too.

---

## Open items carried into the design-plan stage

- Get Anthropic's and Qwen's data-retention terms in writing (rule 11) —
  blocks a fully accurate Data Safety form.
- Confirm `coffee_server`'s request-payload retention behavior (rule 12) —
  blocks the same form and the privacy policy's accuracy.
- Confirm `coffee_server`'s production endpoint is TLS-terminated (rule 13).
- Decide, before any EU-facing production listing, whether outside counsel
  reviews the GDPR sub-processor chain (rule 15) — flagged, not resolved,
  by this spec.
