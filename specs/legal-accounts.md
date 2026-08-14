# coffee accounts — Google Play & Apple App Store compliance spec

A binding design specification for the **account, authentication and cloud-sync
feature** of the coffee app on both stores: Sign in with Google, Sign in with
Apple, an app-owned email + password system, and server-side sync of the user's
own bean/brew data through `coffee_server`.

This is the project's first cross-platform legal spec. It supersedes nothing,
but it **discharges `specs/legal-android.md` §3.5 rule 16**, which predicted
that adding accounts would re-trigger the Account Deletion policy in full and
instructed that the work be scoped before it was built. That has now happened.
Everything here is binding on both the Android and iOS builds and on the shared
backend.

Produced from a **two-specialist review (Google Play · Apple App Store) with a
full cross-review round**, conducted **2026-08-07** against live
`support.google.com`, `developer.android.com`, `developers.google.com` and
`developer.apple.com` pages — not training-data recall. That distinction is
load-bearing in both directions and each side caught the other relying on it:
Apple's Guideline 4.8 was rewritten on **2024-01-25** from "you must offer Sign
in with Apple" into the criteria-based form analysed in §2.1, and 5.1.2(i) grew
its third-party-AI sentence on **2025-11-13**; on the Play side the Developer
Program Policy was consolidated with an effective date of **2026-07-15**, the
legacy Google Sign-In API is deprecated in favour of Credential Manager, and US
state age-assurance statutes went live inside the last ninety days. A spec
written from memory would give wrong advice on the single most expensive item
in this document.

**Not legal advice.** Nothing below substitutes for review by counsel,
particularly the GDPR questions in §2.9 and the trader-status determination in
§2.11, before a production listing goes live on either store. The account
system converts the GDPR analysis in `specs/legal-android.md` §2.4 from a
transient-processing question into a persistent-controller one; that is an
escalation, not a restatement.

- [1. Project background](#1-project-background)
- [2. Development details — the policy analysis](#2-development-details--the-policy-analysis)
- [3. API — the binding rules](#3-api--the-binding-rules)
- [4. Implementation roadmap — the dependency tiers](#4-implementation-roadmap--the-dependency-tiers)
- [5. The joint minimum-compliant configuration](#5-the-joint-minimum-compliant-configuration)
- [6. UI requirements](#6-ui-requirements)
- [7. Open disagreements](#7-open-disagreements)
- [8. What could not be verified](#8-what-could-not-be-verified)

---

## 1. Project background

### What this covers

The product is unchanged from `specs/legal-android.md`: bean profiles, brew
sessions, photo OCR of bean-bag labels, AI brew suggestions. Two things are new
and this document exists because of them:

1. **Accounts.** Sign in with Google, and the app's own email + password
   system.
2. **Cloud sync.** The user's own bean/brew/photo data, held server-side and
   synchronised across that user's devices.

And one thing is new about distribution: **the app will ship on the Apple App
Store as well as Google Play**, submitted by an individual developer on both,
against a **shared backend and a shared account system**. That sharing is what
makes a single spec necessary rather than two — a design that satisfies one
store's rule can violate the other's, and §2.12 lists every place that happens.

### The architectural fact that changed

`specs/legal-android.md` §1 named three load-bearing architectural facts and
warned that the first version to add an account re-triggers a policy in full.
**This change destroys the first fact and leaves the other two intact.**

- **"No accounts, no cloud sync, no server-side data store" is now false in
  every clause.** This activates Play's Account Deletion policy and Apple's
  Guideline 5.1.1(v), flips roughly half of Play's Data Safety form, promotes
  `coffee_server` from a stateless proxy to a system of record holding
  credentials and personal data, and adds review gates on both stores that did
  not previously apply.
- **"AI is proxied, never direct" still holds** and remains the right shape.
  Both stores now name third-party AI explicitly in their user-data rules.
- **"No cross-user visibility" still holds, and must keep holding.** Confirmed
  live against both stores' definitions in §2.10.

The single largest practical consequence is not any one policy: it is that the
app's **entire core dataset** moves from "never leaves the device, therefore
not collected" to "collected". That is a bigger declaration delta than the
photo/OCR flow the parent spec spent most of its §2.1 on, and it is invisible
to anyone who updates the forms by editing rather than re-deriving them.

### Relationship to other specs

| Spec | Relationship |
| --- | --- |
| `specs/legal-android.md` | The Play spec for the account-less app. Its rules 1–15 and 18–26 (photos, EXIF, disclosure, TLS, branding, submission mechanics) remain in force unchanged. Its §3.5 rule 16 is discharged by this document; rule 17 (the UGC tripwire) remains live and is restated here as rule 58. Its §1, §2.3 and §3.5 were amended when this spec landed. |
| `specs/coffee-server.md` | Describes the gateway as built: stateless, "No storage of any kind", one shared `X-API-Key`. **None of that survives contact with accounts** (§2.6). That spec needs rewriting in lockstep, not patching. |
| `coffee_android/plan/` | The Android design plan. Its claim that v1 carries exactly one cross-project dependency (`POST /v1/vision`) is now false — it carries two, and the second is much larger (§2.6). |
| `specs/legal.md` | Unrelated (the roaster-catalogue crawler). No interaction with this document. |

Rules are cited by number and labelled with the store that compels them —
**Play**, **Apple**, or **Both**. That label is the information an engineer
needs most, because a rule sourced to one store still binds the shared backend
and therefore the other platform.

---

## 2. Development details — the policy analysis

### 2.1 The sign-in screen — Apple regulates it, Play does not

This is the largest single divergence between the two stores, and it is a **UI**
divergence, which makes it expensive to discover late.

**Apple's Guideline 4.8** provides that an app using a third-party or social
login service to set up or authenticate the user's primary account "must also
offer as an equivalent option another login service" with three properties: it
limits data collection to name and email; it "allows users to keep their email
address private as part of setting up their account"; and it does not collect
in-app interactions for advertising without consent. **Google Sign-In is named
in the guideline by name**, so the trigger fires with no interpretation
required.

The question the whole finding turns on is whether the app's *own* email +
password system counts as the required second service. It does not: the three
criteria are conjunctive, and a first-party email/password account works by the
user handing the developer their real address. There is no mechanism by which
it "allows users to keep their email address private". Building one would mean
operating an email-masking relay, which is a mail-infrastructure product, not a
feature. The five published exemptions do not apply either — the first
("exclusively uses your company's own account setup and sign-in systems") is
defeated by the word *exclusively* the moment Google is offered alongside.

**Sign in with Apple is the widely-deployed service that plainly meets all
three criteria.** So on iOS the screen carries **three** entry points, not two.
The only other compliant iOS configuration is **email/password alone**, dropping
Google — which lands squarely inside the first exemption and removes the
GoogleSignIn SDK, its privacy-manifest exposure, OAuth brand verification and
two of the three web re-authentication integrations along with it. The
configuration that is never compliant is "Google plus our own".

**Play has no analogue.** Verified: nothing in the Developer Program Policy
requires offering any particular login service, requires parity among the
services offered, or constrains which identity providers appear. Adding Sign in
with Apple to the Android build creates no Play obligation, and omitting it
creates none either. Android's button count is therefore a **product** decision
about account portability, not a compliance one — see §7, where it remains an
open disagreement between the two reviews.

### 2.2 Guest mode — Apple requires what Play merely permits

Guideline 5.1.1(v) states: "If your app doesn't include significant
account-based features, let people use it without a login," and "Apps may not
require users to enter personal information to function, except when directly
relevant to the core functionality of the app or required by law."

This is a live rejection risk for this app specifically, and it is the finding
most likely to be dismissed as boilerplate. The Android design plan already
states in writing that bean and brew CRUD is "fully offline-capable"
(`coffee_android/plan/README.md`, resolution #15). That is a written admission
that the core functionality does not need an account. A reviewer applying the
sentence literally has everything needed to reject an iOS build that opens on a
sign-in wall.

Play permits either design. Apple requires this one. **So this one wins, on
both platforms, and there is nothing to trade off.** Adopting it on both is not
merely tidiness: if Android ships a wall and iOS does not, the two apps fork at
the navigation root and the backend acquires two contradictory assumptions
about whether a user ID always exists.

Two refinements that came out of cross-review and matter to the wireframe:

- On iOS, a "continue without an account" escape *on a launch-time sign-in
  screen* is **not sufficient**. The app must not open on that screen at all.
  Sign-in is reached from Settings, or from a dismissible non-blocking prompt.
  A wall-with-a-door still reads as a wall to a reviewer asking "can I use this
  app without logging in".
- The mitigation is architectural and cheap **if decided now**, and expensive
  once ViewModels assume a user ID exists.

A second-order effect worth recording: with guest mode, **sync is the only
account-gated surface in the entire app**. That makes the demo account's job
specific (§2.7) — it must demonstrate sync, which means seeding server-side
data, not just local data.

### 2.3 Account deletion — the union of two regimes, and only the union

Both stores require deletion; each forbids the other's shortcut. The union is
the only compliant design, and both single-mechanism "simplifications" break a
store.

**Play** requires two artifacts. An **in-app path** that is "intuitive for the
user" and "prominent (for example, within the account settings or a similar
section)". And a **publicly reachable web URL** that is "functional (for
example, loads without error)", "relevant in scope", references the app or
developer name, and — the clause that defines its purpose — lets a user request
deletion "without sending the user back to the app and requiring them to
re-download it". The URL is declared in a designated field **in the Data safety
form on the App content page**, not in the store listing's privacy-policy slot.

**Apple** requires deletion to be **initiated from within the app**, easy to
find, "typically... included in the app's account settings". A web page may
complete the flow only if the app links **directly** to it. Apple's guidance
disfavours phone/email/support-mediated flows for non-regulated apps, and warns
separately that routing users to a browser for initial sign-in or registration
"provides a poor user experience and is not appropriate".

Both stores reject deactivation. Play: "Temporary account deactivation,
disabling, or 'freezing' the app account does not qualify as account deletion."
Apple: "Offering to temporarily deactivate or disable an account is
insufficient." Play's enumeration of what must be deleted names
**authentication information** explicitly, so a design that deletes the
bean/session rows and leaves the credential record behind fails.

**Apple adds one obligation with no Play analogue**: apps using Sign in with
Apple must call Apple's REST API to **revoke the user's tokens** on deletion.
This is the easiest item in the document to forget, because deletion appears to
work perfectly without it.

**Retention.** Play permits retention "for legitimate reasons such as security,
fraud prevention or regulatory compliance" with disclosure; Apple permits it
only where applicable law requires, with disclosure. Build to Apple's narrower
rule. The honest list is short — at most a salted hash sufficient to prevent
immediate re-registration abuse, plus web-server logs on normal rotation — and
should be kept short.

**One routine, three entry points.** Cross-review converged on a single
server-side deletion implementation called by the iOS app, the Android app, and
the web page, because any design with two implementations will drift. The order
of operations inside it is not cosmetic:

1. Re-authenticate (fresh session in-app; full re-auth on the web).
2. **Load all identity rows before anything is purged.**
3. **Revoke Apple tokens — before deleting the token rows.** Purge first and
   you no longer hold the token you are required to revoke, and the failure is
   invisible: deletion looks like it worked.
4. Hard-delete the user row, all identity rows, the password hash, all sessions
   and refresh tokens, and every synced domain row.
5. **Purge the image objects from object storage**, not only their database
   rows. This is the step that gets missed — the row disappears, the file stays
   in the bucket, and the account is not deleted in any sense a regulator would
   accept.
6. Retain only what is disclosed; send the deletion confirmation email;
   idempotent; all tokens invalid immediately on every device.

Soft-delete is permissible internally only behind a bounded, disclosed purge
timer, and the soft-deleted account must not be signinable in the interim —
otherwise it is deactivation, which both stores name as insufficient.

### 2.4 Identity, email, and the private relay

This section corrects a premise carried in the Play draft's first round.

**A Sign in with Apple private relay address is deliverable.** It is a
forwarding address, not a black hole — but only if the sending domain is
registered. Apple's Private Email Relay Service documentation: "You must
register and validate every source email domain or subdomain you intend to
use," and "If you don't register all the source domains or emails that you use,
email sent to the private relay service will result in a bounce message."
Outbound mail must be authenticated with SPF and/or DKIM, and an **Individual**
developer account may register up to **32** email sources.

So the accurate statement is: relay addresses are deliverable **if and only if**
you have registered and validated your sending domain with Apple. If you have
not, mail bounces — silently, from the user's perspective. That converts an
apparent architectural impossibility into a configuration task with a deadline,
and adds a setup step neither draft originally had: **registering the sender
domain is a prerequisite for any account email at all** — verification,
password reset, deletion confirmation.

**The downstream conclusion survives the correction, and both reviews reached
it independently: an emailed link is the wrong authentication mechanism for the
web deletion page** — for every sign-in method, not just Apple's. The right
design is that the web page **re-authenticates the user with the same identity
providers the app offers** and then calls the same deletion routine. The user
proves who they are to Apple or Google, the server receives the same `sub` it
stored, and deletes that account. No email round-trip exists, so relay
deliverability is irrelevant to the primary flow — and it satisfies Play's
"without... requiring them to re-download it" condition exactly. Apple
prescribes nothing about how a web deletion request is authenticated, so Play's
requirement governs the web page and Apple's governs the app; they do not
conflict. Putting sign-in buttons on a *website* does not trigger Guideline
4.8, which governs apps.

A support-mediated request form may sit on the same web page as a clearly
secondary route for users who have lost access to their identity provider
entirely. It may **never** be the in-app path.

**Four schema consequences, all expensive to retrofit:**

1. **Never key an account on an email address.** The primary key is an internal
   opaque user ID; identities live in a separate table unique on
   `(provider, subject)` — Apple's `sub`, Google's `sub`, and a local
   `password` provider row. Email is a nullable *attribute*, not globally
   unique. This single decision makes everything else tractable.
2. **Persist Apple's name and email in the same transaction that creates the
   user.** Apple returns them **only on first authorization**; every later
   sign-in returns the `sub` alone, and they cannot be re-fetched. This is the
   most common Sign in with Apple bug and it looks like nothing in testing,
   because the developer's own test account already authorized once.
3. **A relay address can never match a password account's address**, so
   email-based linking is structurally impossible for hidden-email users. Two
   accounts for one human is the *expected* state, not a bug to fix with fuzzy
   matching. Provide explicit account linking in Settings instead.
4. **Read and store Apple's `is_private_email` and `email_verified` claims.**
   They tell the deletion, recovery and linking logic which case it is in. Do
   not pattern-match the domain — Apple announced on 2026-06-15 that relay
   addresses are migrating to `private.icloud.com`, so any allow-list of relay
   domains is a scheduled outage.

**Email verification has three states, not two.** An address from Apple or
Google arrives already verified by the provider and needs no round-trip. A
relay address is verified *and* unmatchable. Only the app's own email/password
path needs a verification flow. Never block account use on verifying a
federated address.

**Anywhere a rule assumes a reachable email, allow for the user being
unreachable.** Account recovery, deletion confirmations, and — the one with
legal teeth — GDPR Art. 34 communication of a breach to data subjects all
assume deliverability. Never make email the sole account-recovery mechanism,
and provide an in-app surface for anything that must reach the user.

### 2.5 The two privacy forms — one inventory, two outputs

Both stores require a data declaration, the taxonomies differ, and **the same
facts legitimately produce different-looking answers**. Anyone reconciling the
two forms to match would introduce an error into one of them, which is exactly
the tidy-up a careful reviewer would attempt.

**What changes on Play's Data safety form** relative to
`specs/legal-android.md` §2.1's account-less declarations:

- **Newly collected — Personal info → Email address**, and **→ User IDs**.
  Purposes: App functionality, Account management.
- **Newly collected — App activity → Other user-generated content, and Photos →
  Photos as a *stored, non-ephemeral* type.** This is the big one. Bean
  profiles, sessions, notes and photos are not "collected" today; sync makes
  the whole dataset collected and retained indefinitely by design, and the
  ephemeral-processing answer becomes unavailable for the synced copy.
- **Security → "All of the user data collected by your app is encrypted in
  transit"** must be answered yes, and must be *true* (§2.6).
- **Security → "provide a way for users to request that their data is
  deleted"** stays yes, but the justification changes completely: today it is
  true because uninstalling deletes everything. The alternative qualifying
  route Google offers — automatically deleting or anonymizing within 90 days of
  collection — is **unavailable** here, because sync data is retained for as
  long as the account exists.
- The **account-creation-method** question must now be answered, and the
  **deletion URL** field filled.
- **Sharing stays "no".** Sync to the developer's own backend is *collection*,
  not sharing. A managed identity or hosting provider is a service provider
  acting on the developer's instructions, which Play's definition excludes from
  sharing — *provided* there is a contract saying so (§2.9).

**What Apple's App Privacy label needs**: Contact Info → Email Address,
Identifiers → User ID, User Content → Photos and Other User Content, all as
**Data Linked to You**, purpose App Functionality. Data collected by
third-party SDKs is declared as the developer's own, so GoogleSignIn's
collection lands on this app's label. **"Data Used to Track You" stays empty** —
nothing here meets Apple's definition of tracking, and adding an ATT prompt with
nothing to track mismatches the label and invites a question at review.

**Where they legitimately diverge:**

| Fact | Apple | Play | Divergence |
| --- | --- | --- | --- |
| Synced bean/brew records | User Content → Other User Content, Linked | App activity → Other UGC, collected | None in substance; different names |
| Synced photos | User Content → Photos, Linked | Photos → Photos, stored | None in substance |
| **Transient OCR photo, not retained** | **Not disclosed at all** — Apple's carve-out excludes data "sent to your servers then immediately discarded after servicing the request" | Declarable as **processed ephemerally** — a visible declaration | **Shape, not substance.** Same fact, *no artifact* on Apple's form, *a visible one* on Play's |
| Account email | Contact Info → Email, Linked | Personal info → Email, with a required/optional axis | **Axis mismatch.** Apple has no required/optional axis; Play has no Linked/Not-Linked axis. Neither answer copies |
| Apple relay email | Still Contact Info → Email, still Linked | n/a | Masked ≠ uncollected. A durable unique identifier for a person |
| **Password** | **No credential category exists** | **No password type in Google's category list** | **Symmetric gap, confirmed from both sides.** Disclose password handling in the *privacy policy*; invent no category on either form |
| Name / avatar | Only if the name scope is requested and stored | Only if `profile` is requested and stored | None. Scope minimisation keeps the row off **both** forms |

Three structural differences matter more than any row. **Apple's label has no
"shared with third parties" axis at all**, folding third-party collection into
the developer's own declaration — so the unresolved Anthropic/Qwen retention
question (`specs/legal-android.md` rule 11) resolves a *visible field* on
Play's form and *nothing visible* on Apple's, where it decides only whether the
row exists. **Play's security-practices questions have no Apple counterpart**,
which means the TLS failure in §2.6 produces a *false declaration* on Play and
a *silent* compliance failure on Apple — silent is worse, not better. And
Apple's tracking axis has no Play counterpart.

**Operational conclusion: derive both forms from a single written data
inventory** — one table listing every field, where it goes, who touches it, how
long it lives — and treat that inventory as the source of truth the privacy
policy is written from too. Never derive one form from the other.

### 2.6 `coffee_server` cannot support this as specified

`specs/coffee-server.md` describes a service whose stated design principles are
"deliberately stateless pass-through" and "**No storage of any kind**", whose
entire security model is one shared `X-API-Key` compiled into every client, and
which is deployed as "plain HTTP on `:8000`" onto an EC2 instance whose security
group opens that port **to the world**, health-checked over `http://`. It has,
by its own documentation, no rate limiting, no per-client quotas and no
multiple-key support.

Every one of those properties is incompatible with holding accounts, and the
incompatibility is triple-driven — Apple's 5.1.1(v) and token revocation,
Play's deletion policy and Data Safety declarations, and GDPR Arts. 15/17/20/32
— three independent regimes landing on capabilities that do not exist.

- **TLS is a hard blocker, not a to-do.** `specs/legal-android.md` rule 13 said
  to *confirm* TLS termination, written when the payload was a coffee photo. It
  is now login credentials. Shipping password authentication to a cleartext
  endpoint open to the internet is simultaneously a policy violation on both
  stores, a false Data Safety declaration, and a GDPR Art. 32 failure.
- **A shared client key cannot express per-user authorization.** It cannot say
  "this user may read this user's beans". Fronting an account system turns the
  same extractable constant into an enabler for credential stuffing, account
  enumeration, and bulk read of other users' data if any authorization check is
  missed. The key is an **app**-level credential and must never be accepted as
  a **user**-level one.
- **Rate limiting moves from cost control to security control**, and must be
  tuned so a human reviewer cannot trip it (§2.7).
- **There is nowhere to put an account.** Deletion, export, revocation and the
  sync store all need server state that does not exist.

None of this is client work. It is `coffee_server` work, and it must be
tracked as a **second cross-project dependency alongside `POST /v1/vision`** —
one the Android design plan does not currently carry, and larger than the one
it does. `coffee_android/plan/api.md` §3's claim that v1 carries exactly one
such dependency is now false, and `specs/coffee-server.md`'s "no storage" and
"fully independent" framings need rewriting rather than patching.

### 2.7 Review mechanics — the demo account, brand verification, and the domain

**Both stores require reviewer credentials, and they collapse into one
artifact.** Play's text is strict: credentials must be "accessible at all
times, reusable, and valid regardless of user location", "maintained at all
times without any error", supplied in English, and where the app normally
requires 2FA or an OTP the developer must "provide reusable login credentials
that can bypass these requirements", with the stated consequence that "we may
not be able to review your app and, therefore, the app may be rejected."
Apple's Guideline 2.1 adds the parenthetical imperative "**(and turn on your
back-end service!)**" — an explicit requirement that the backend be live for
the duration of review.

The two differ procedurally rather than textually. Apple's is consumed by a
human reviewer on **every** submission; Play's is consumed when automated
scanning or a human escalation actually needs to get past the wall. The folk
wisdom that Play's field is "softer" is directionally true for a mature app —
**and false for this project**, because a new Personal account cannot reach
production without the production-access application, which is itself
human-reviewed. A human is guaranteed to look at this app at least once, at
exactly the moment the account system is new.

Build to Play's stricter written spec and Apple is satisfied automatically. One
permanent demo account that is: **email/password, never federated** — you
cannot hand a reviewer a Google account or an Apple ID, which is an independent
reason the email/password path must exist on both platforms; stable password,
no 2FA, no expiry, no geo restriction, English; **seeded with representative
data** including **server-side** data, since with guest mode sync is the only
account-gated surface; **an ordinary account, not a code path** — no
`if user.isReviewer` branches, which Apple's 2.3.1 prohibits as a hidden
feature and which is a security hole besides; exempt in practice from lockout
thresholds; and **provisioned with AI quota** so the reviewer can reach the
consent modal rather than being blocked by an exhausted key. Apple offers a
"built-in demo mode... with prior approval by Apple" as an alternative; **Play
has no equivalent**, so that escape hatch cannot be the joint answer.

**Google's OAuth brand verification gates the Play release** and requires a
live homepage on a Search-Console-verified authorized domain, a privacy policy
URL, a terms-of-service URL and a support email. Verification is usually fast —
automated in minutes, manual review 2–3 business days — and applies
**regardless of scope sensitivity**, so requesting only `openid`/`email` does
not exempt it. Google's button branding guidelines state that following them
"is required for app verification", making a non-compliant button a
verification failure rather than a design note. Scope discipline also protects
the schedule: `openid`/`email`/`profile` are non-sensitive, but any sensitive
scope pulls in a verification process with multi-week timelines and a demo-video
requirement.

**The domain is the shared critical path and neither draft gave it a
milestone.** It now serves six purposes: the privacy policy, the terms of
service, Play's web deletion URL, Google's OAuth brand-verification homepage on
a Search-Console-verified domain, Apple's Sign in with Apple JS return URL, and
registration as a **validated relay sender domain with SPF/DKIM**. Several of
these have review or DNS-propagation lead times that overlap badly. **Provision
it first.** The project does not currently have a website at all.

**Schedule, and it points the opposite way to expectation.** Play imposes 12
testers opted in for 14 continuous days (closed track only; internal testing
does not count), followed by a production-access application that is itself
reviewed, typically within 7 days. **Apple imposes no testing gate at all**;
TestFlight has no minimum count or duration and satisfies no Apple requirement.

But the inversion is smaller than it looks, because **the Android 14-day clock
does not require the account system.** The design plan already defines a
closed-testing-ready milestone — Home, Bean Detail, Brew Session Detail,
Profile, Share Card — with zero `coffee_server` dependency and no accounts.
That build can start the tester clock immediately while backend work proceeds
in parallel, which takes accounts off the Android critical path almost
entirely. The corrected picture:

- Android's long pole is **calendar time on the tester clock**, startable now.
- iOS's long pole is **the backend**, because Apple has no waiting period and
  will reach a human reviewer as soon as the accounts work is done.
- Therefore **the backend's required-by date is set by iOS, not Android**, and
  **the first human scrutiny of the account system will be Apple's** — the
  stricter of the two on exactly this surface. Design sign-in and deletion to
  Apple's rules first and check them against Play second.
- One consequence that strengthens rather than softens the schedule: the 12
  testers are **real data subjects**. The privacy policy, the hosting DPA, the
  deletion path and the export path must all be live **before the closed test
  opens**, not before production submission.

### 2.8 Age, children, and the age-assurance statutes

**Ratings are unaffected in outcome.** There is still no violence, sexual
content, gambling or drug content, and still no cross-user visibility, so every
interaction/capability question is answered "no" on both stores. Expected
results: lowest tier on IARC (Play) and **4+** on Apple's rebuilt 4+/9+/13+/16+/
18+ scale. Apple's questionnaire gained **social-media capability questions**
that become required for new submissions from **September 2026**; this project's
first submission lands after that, so they are mandatory from the start.
Over-declaring is not the safe option — ticking UGC or Social Media when
neither is true raises the rating, attaches a content descriptor, and invites a
reviewer to ask where the filtering, reporting and blocking are.

**Accounts do bite on the children question.** Collecting an email address from
a child pulls the app into Play's Families policy and COPPA. The mitigation is
cheap: **declare no under-13 band** in Play Console's target audience, state a
minimum age in the account terms, and **do not collect a date of birth** — a
minimum-age affirmation collects less and is sufficient. One consistency point:
Apple's age-rating questionnaire has an **Age Assurance** item, and a
self-declared checkbox is the weakest form of assurance; answer honestly and do
not declare it as more than it is.

**The age-assurance statutes are new since `specs/legal-android.md` was
written, and the two stores' postures are not symmetric.** Both were verified
live. Texas SB 2420 is **in effect** — a federal appeals court stayed the
December 2025 injunction, and Apple's own 2026-06-03 post says "new Apple
Accounts in Texas are now subject to the law", effective 2026-06-04. Google
ships the **Play Age Signals API** (beta; returning signals for Brazil from
2026-03-17 and for Texas accounts created after 2026-05-28); Apple ships the
**Declared Age Range API** returning statutory bands (under 13, 13–15, 16–17,
over 18) plus the assurance method and consent status.

The asymmetry is in framing, and the merged text must not flatten it. **Google
devolves the judgement**: "It is your responsibility to determine how these
laws apply to your app." **Apple's post is directive**, telling developers what
they must review and implement without stating a category scope. So the legal
question — do these statutes reach a general-audience coffee logger with no
age-restricted content and no purchases? — is one question answered once for
both platforms; but a recorded decision of "we are not integrating" is a
**slightly weaker position on the App Store than on Play**, and should be
written down as such.

The re-check trigger should be specific, and there is an obvious one: Apple
names in-app purchases among the things requiring parental consent for minors.
**The moment sync becomes a paid tier, three things fire at once** — Apple's
3.1.1 forces IAP, the Texas consent obligations attach to those purchases, and
Play's equivalent analysis re-opens.

### 2.9 GDPR/CCPA — the obligation grows, it does not shift

`specs/legal-android.md` §2.4 already placed the developer in the **controller**
role with `coffee_server` as processor and Anthropic/Qwen as sub-processors, and
routed the international-transfer question to counsel. Accounts do not change
that structure; they enlarge it in four ways.

1. **A durable identifier and a durable store.** An email address plus a
   persistent server-side record of a named individual's activity is personal
   data of a qualitatively different kind from a transient photo round-trip.
   Lawful basis for the account and sync is most naturally **Art. 6(1)(b),
   performance of a contract** — the user asked for their data to be synced —
   which is cleaner than consent because it does not evaporate when consent is
   withdrawn mid-sync. The AI processing keeps its own basis and its own
   consent gate, and the two must never be bundled into one "I agree".
2. **New processors.** Whoever hosts the account store is a processor requiring
   a DPA. Today that is AWS via `coffee_server/deploy/`, where `AWS_REGION`
   currently falls back to whatever `aws configure` has set — a data-residency
   decision being made by accident. It also determines whether the Play "shared"
   answer stays "no" (§2.5).
3. **Data-subject rights become real work.** Erasure (Art. 17) is satisfied by
   the same routine both stores require — a happy alignment; build one and let
   all three regimes point at it. But **access (Art. 15) and portability (Art.
   20) are newly meaningful**: with a server-side store you can be asked to
   produce a machine-readable export. Neither store requires it. The law does.
   It is cheap alongside the deletion work and expensive to retrofit.
   Retention must be stated as a **period**, not as "as long as necessary".
4. **Breach notification (Arts. 33/34) is newly live.** A local-only app
   essentially cannot suffer a breach of the developer's own systems; a server
   holding password hashes and email addresses can, on a 72-hour clock. Note
   the interaction with §2.4: a relay user who cannot be reached by email still
   has an Art. 34 communication right, so there must be an in-app surface.

Apple has additionally made the underlying law into a store rule — 5.1.2(i)
provides that apps sharing data without consent or without complying with
data-privacy laws "may be removed from sale" — so a GDPR failure here is also an
App Store failure. Apple's 5.1.1(i) is also more prescriptive than Play about
the privacy policy's contents: it must identify the data and every use,
**confirm that third parties receiving the data provide equal protection**, and
explain retention, deletion and consent withdrawal. That affirmative
equal-protection statement about Anthropic and Qwen by name requires having
their terms in hand — the same unresolved open item both specs already carry.

**CCPA/CPRA**, honestly: the statute's business thresholds are very unlikely to
be met by this project, so the operative obligations probably do not attach.
That is a threshold question about the developer, not the app, and should be
recorded as a reasoned conclusion rather than assumed. What applies regardless
is that the privacy policy must be **accurate** — an inaccurate policy is an
unfair-practices exposure independent of any privacy statute, and Play
separately requires the Data safety declarations to align with it.

### 2.10 UGC — confirmed still not triggered, on both stores

Verified against both live definitions. Play: "User-generated content (UGC) is
content that users contribute to an app, and which is visible to or accessible
by at least a subset of the app's users." Apple's Guideline 1.2 machinery —
filtering, reporting, blocking, published contact info — attaches to content
posted to the app and visible to others, and Apple's rebuilt age-rating
questionnaire keys its UGC and Social Media capabilities off the same facts.

**Cross-device sync makes a user's content visible to that same user on another
device. It does not make it visible to any other user**, so neither definition
is met and neither moderation stack activates. `specs/legal-android.md` rule 17
was correct and remains live.

Two tripwires on the sync design, not future product decisions:

- **Any shared account surface** — "invite someone to your can", a shared
  library, following — makes one user's content accessible to another and trips
  both definitions at once.
- **Any server-side aggregate surfaced back to users** — "beans popular with
  other users this month" — is derived from other users' content. Aggregate
  anonymized statistics are a reasonable argument away from UGC, but it is an
  argument, not the clean "no" the app currently enjoys. Do not let it in
  through an analytics feature.

Note that a terms-of-service acceptance gate is a UGC-policy artifact and
remains **not required** by either store here. A terms link is still needed for
Google's OAuth brand verification — different requirement, same document.

### 2.11 Commercial posture — billing, trader status, and developer PII

**Billing is not symmetric, and the asymmetry is the product of live
litigation.** Apple's Guideline 3.1.1 forces Apple IAP for a paid sync tier,
full stop. Google's own policy page states plainly that "Google will not
require the use of Google Play Billing in apps distributed on the Google Play
Store", will not prohibit other in-app payment methods, will not prohibit
developers from telling users about them, and will not require price parity —
with policy changes effective **2025-10-29**, programs from **2025-12-09**, and
transaction reporting plus service fees from **2026-10-01**. That carve-out is
**United States only**; EU alternatives run through the DMA regime and
elsewhere Play Billing requirements generally still apply.

The practical consequence is that Android's freedom is **payment-method
freedom, not fee freedom** — a service fee attaches to transactions regardless
of how money is collected — so the old "send Android users to the web"
arbitrage does not recover the margin, and a single global price is the least
likely thing to be correct.

**Developer PII exposure differs sharply, and it favours Play.** On Play, a
personal account must supply legal name, address, email and phone, but what is
**published** is the **developer name** — which may legally differ from the
legal name — plus a public email and optionally a phone and website. **The
legal address is not published for an ordinary personal account.** On Apple,
individual enrollment publishes the developer's **personal legal name as the
seller name on every product page, worldwide**, with no brand-name option short
of an organization enrollment. So a Personal/Individual account remains fine on
Play and does not force publication of the owner's name or home address; **all
entity-formation pressure comes from the Apple side.**

Two joint consequences:

- **Trader status is one factual question that must be answered identically to
  both stores.** Both require the DSA declaration, and both remove
  non-compliant apps from all 27 EU territories. Declaring "trader" to one and
  "non-trader" to the other is one fact answered two ways in two regulated
  filings. Apple additionally publishes the verified trader's address, phone
  and email on EU product pages, and permits individuals to supply a P.O. box or
  mail-forwarding address with documentation — a legitimate way to avoid
  publishing a home address, which must be arranged **before** submission.
- **Monetization is the switch that makes Play as exposed as Apple.** A paid
  app or IAP converts the Play account to a merchant account, which "must show
  their full address on Google Play". Combined with the trader analysis — where
  revenue generation is a stated factor — going paid simultaneously weakens the
  non-trader argument and forces address publication **on both stores**. "Stay
  free" is load-bearing for the developer's own privacy, not just a product
  decision.

Recorded so it is not mistaken for an obligation: Android's separate
**developer-verification** regime (Android Developer Console registration,
enforced for certified devices in Brazil, Indonesia, Singapore and Thailand
from 2026-09-30, expanding globally from 2027) governs **sideloaded**
distribution, not Play distribution. It adds nothing for this project.

### 2.12 Where the two stores diverge — the single reference table

The most useful table in this document. Everything else in §2 elaborates a row
here.

| # | Subject | Google Play | Apple App Store | Consequence for a shared design |
| --- | --- | --- | --- | --- |
| 1 | **Login-service parity** | No rule of any kind | **4.8**: offering Google compels a second qualifying service (in practice Sign in with Apple) | iOS carries three buttons or email-only. Android's count is a product decision (§7) |
| 2 | **Guest mode** | No rule; either design permitted | **5.1.1(v)**: if the app has no significant account-based features, it must be usable without login | Apple's rule wins on both platforms — adopt globally or the apps fork |
| 3 | **Deletion — in-app** | Required (prominent, in settings) | Required, and **web-only is insufficient** | Both require it; Apple forbids the web-only shortcut |
| 4 | **Deletion — public web URL** | **Required**, usable post-uninstall, declared in the Data safety form | Not required; permitted as a linked completion step | Only Play compels it. Union is the sole compliant design |
| 5 | **Token revocation** | No analogue | **Required** for Sign in with Apple accounts, via Apple's REST API | Backend-only obligation, ordered before purge |
| 6 | **Reviewer credentials** | "App access" / sign-in details; strict text; procedurally intermittent | **2.1** demo account + "turn on your back-end service!"; human, every submission | One demo account built to Play's stricter text satisfies both |
| 7 | **Demo-mode alternative** | **None** | Built-in demo mode with prior Apple approval | Cannot be the joint answer |
| 8 | **Privacy declaration** | Data safety form; has collected/shared and required/optional axes; has security-practice questions | App Privacy label; has Linked/Not-Linked and tracking axes; **no shared axis, no security questions** | Derive both from one inventory; never copy across |
| 9 | **"Collect" definition** | No carve-out for immediately-discarded data | **Excludes** data discarded immediately after servicing the request | The transient OCR leg legitimately appears on one form and not the other |
| 10 | **Credential category** | None in the taxonomy | None in the taxonomy | Symmetric gap — disclose password handling in the privacy policy |
| 11 | **Tracking consent** | No analogue | **ATT** — not triggered here; label stays empty | Do not add an ATT prompt defensively |
| 12 | **SDK privacy manifests** | No analogue | **Required**; GoogleSignIn is on Apple's list | Affects the iOS build's dependency hygiene only |
| 13 | **Age rating** | IARC questionnaire | Apple's own 4+…18+ questionnaire; social-media questions mandatory from Sept 2026 | Two questionnaires, one set of honest facts |
| 14 | **Age-assurance statutes** | Play Age Signals API; Google **devolves** the judgement | Declared Age Range API; Apple's post is **directive** | One legal decision, but a weaker "we declined" posture on Apple |
| 15 | **Billing if sync goes paid** | Play Billing **not required in the US** (injunction); service fee still applies; US-only carve-out | **3.1.1 forces Apple IAP** | No price or margin symmetry; decide before announcing pricing |
| 16 | **Published developer PII** | Chosen developer name + public email; **legal address not published** unless a merchant account | **Personal legal name as seller, worldwide**; EU trader address/phone/email published | Personal account fine on Play; entity pressure is Apple-side only |
| 17 | **Pre-release gate** | **12 testers × 14 continuous days** + production-access review (~7 days) | **None**; TestFlight satisfies nothing | iOS can submit first; backend date is set by iOS |
| 18 | **Membership cost** | One-time registration fee | **99 USD/year** recurring | Budget item only |
| 19 | **Registration UX** | No rule | Browser redirect for registration called out as inappropriate | Sign-up native on both |

---

## 3. API — the binding rules

Normative. Every rule is a design constraint on the iOS build, the Android
build, or the shared backend. Re-verify every live-policy claim at actual
submission time — Guideline 4.8 has been rewritten once, 5.1.2(i) amended once,
Play's Developer Program Policy consolidated once, and the billing position is
under active litigation.

**[BLOCKER]** marks a hard release blocker — realistic rejection, removal, or
false-declaration risk. **[SHOULD]** marks a strong recommendation that is not
on its own a rejection trigger. The store label names what **compels** the rule;
a rule sourced to one store still binds the shared backend and therefore both
platforms.

### 3.1 Accounts, sign-in and identity

1. **[BLOCKER · Both]** **Accounts are optional and the app is fully functional
   with no account.** All bean/brew CRUD works offline forever, with no
   sign-in. Sign-in gates cross-device sync and cloud backup only, never a
   feature that works offline today. *(Apple 5.1.1(v) compels it; Play permits
   either; adopt on both platforms so the apps and the backend do not fork.)*
2. **[BLOCKER · Apple]** **On iOS, if the sign-in screen offers Sign in with
   Google it must also offer Sign in with Apple.** The app's own email/password
   system does not satisfy Guideline 4.8's second criterion. Implement all
   three, or drop Google from the iOS build — never Google plus first-party
   alone.
3. **[BLOCKER · Both]** **Ship the email + password path on every platform.** It
   is the reviewer's route into the app on both stores (rule 40) and the
   fallback identity for cross-platform users.
4. **[BLOCKER · Play]** **On Android, implement sign-in with Credential Manager
   (`androidx.credentials`)** — `GetSignInWithGoogleOption` for the button,
   `GetGoogleIdOption` for the bottom sheet. **Do not use the legacy
   `GoogleSignInClient`/`GoogleSignInOptions` API**, which is deprecated with
   removal announced. Implement both surfaces.
5. **[BLOCKER · Apple]** **On iOS, use a current GoogleSignIn release that ships
   `PrivacyInfo.xcprivacy` and a valid signature, and verify both are present in
   the built binary.** GoogleSignIn is on Apple's mandatory privacy-manifest SDK
   list. Never vendor a hand-copied older SDK.
6. **[BLOCKER · Both]** **Request minimum scopes: `openid` + `email` from
   Google; the email scope only — not name — from Apple.** Every additional
   scope adds a row to *both* stores' privacy declarations, and any sensitive
   Google scope adds a multi-week verification process to the release schedule.
7. **[BLOCKER · Both]** **Key accounts on an internal opaque user ID, with a
   separate identities table unique on `(provider, subject)`.** Email is a
   nullable attribute, never a key, never assumed globally unique.
8. **[BLOCKER · Apple]** **Persist Sign in with Apple's name and email in the
   same transaction that creates the user.** Apple returns them only on first
   authorization and will never return them again.
9. **[BLOCKER · Both]** **Never auto-link an identity to an existing account on
   a private relay address** — even though Apple marks it verified — and never
   auto-link a Google sign-in to an existing password account on an *unverified*
   email. Provide explicit account linking in Settings instead.
10. **[BLOCKER · Both]** **Verify Google and Apple ID tokens server-side**
    (signature, issuer, audience, expiry) before provisioning or authenticating.
    Never trust a client-supplied email address or user ID.
11. **[BLOCKER · Both]** **Treat relay addresses as ordinary, first-class email
    addresses.** Never pattern-match, reject or normalize them; Apple is
    migrating them to `private.icloud.com`. Read and store the
    `is_private_email` and `email_verified` claims and branch on those.
12. **[BLOCKER · Both]** **Store passwords only as a memory-hard hash**
    (argon2id, scrypt or bcrypt) with a per-user salt. Never plaintext, never
    reversible, never a bare SHA digest. Authentication information is sensitive
    user data on both stores.
13. **[BLOCKER · Both]** **Rate-limit and lock out registration, login and
    password-reset endpoints**, tuned so a human reviewer retrying, mistyping
    and reinstalling cannot trip them.
14. **[SHOULD · Both]** **Verify email addresses on the app's own
    email/password path only.** Federated addresses arrive verified by the
    provider; never block account use on re-verifying one.
15. **[SHOULD · Both]** **Let a signed-in user add an email/password credential
    to an existing federated account**, so no user is stranded on a platform
    that lacks their identity provider.

### 3.2 Deletion, export and revocation

16. **[BLOCKER · Both]** **Implement exactly one server-side deletion routine
    with three entry points** — iOS app, Android app, web page. Two
    implementations will drift.
17. **[BLOCKER · Apple]** **Ship an in-app deletion path** in account settings,
    at most two taps from a top-level screen, self-service, with a confirmation
    stating what is deleted and what is retained. No support-email flow.
18. **[BLOCKER · Play]** **Publish a public web deletion page and declare its
    URL in the Data safety form's designated field.** It must load without
    error, name the app or developer, feature the request prominently, and work
    for someone who has already uninstalled, without reinstalling.
19. **[BLOCKER · Both]** **Authenticate the web deletion page by
    re-authentication with the same identity providers the app offers — not by
    emailing a link.** A support-mediated fallback may sit on the same page as a
    clearly secondary route; it may never be the in-app path.
20. **[BLOCKER · Apple]** **Revoke Apple tokens via Apple's REST API before
    purging identity and token rows.** Purging first makes the required
    revocation impossible and the failure invisible — deletion appears to work.
21. **[BLOCKER · Both]** **Hard-delete the user row, all identity rows, the
    password hash, all sessions and refresh tokens, and every synced domain
    row.** Deactivation, disabling or freezing does not qualify on either store.
    Soft-delete is permissible internally only behind a bounded, disclosed purge
    timer, during which the account must not be signinable.
22. **[BLOCKER · Both]** **Purge image objects from object storage**, not only
    their database rows.
23. **[BLOCKER · Both]** **State the post-deletion retention list and period
    explicitly in the privacy policy.** Build to Apple's narrower rule
    (law-required only); keep the list to a re-registration-abuse hash and
    normal-rotation server logs.
24. **[SHOULD · Both]** **If "delete synced data but keep account" ships, make
    it visually and verbally unmistakable from full deletion** — different
    section, different treatment, explicit consequence text in each
    confirmation. Two adjacent similar destructive actions is how users delete
    the wrong thing and how a reviewer decides the deletion path is not
    intuitive.
25. **[BLOCKER · Both]** **Build a user-facing data export.** Neither store
    requires it; GDPR Arts. 15 and 20 do, and it is cheap alongside deletion and
    expensive to retrofit.
26. **[BLOCKER · Apple]** **Register and validate every outbound email sender
    domain with Apple's Private Email Relay Service, with SPF and/or DKIM,
    before any account email is sent.** Mail to a relay address from an
    unregistered source bounces. An Individual account may register up to 32
    sources.

### 3.3 Backend and transport

27. **[BLOCKER · Both]** **Terminate TLS on `coffee_server` and remove all
    cleartext access before any authentication code ships.** The documented
    deployment — plain HTTP on `:8000`, port open to the world — must not carry
    credentials. This upgrades `specs/legal-android.md` rule 13 from "confirm"
    to "blocker".
28. **[BLOCKER · Both]** **Authorize every account and sync endpoint per user**,
    against the server-verified session, never against a client-supplied
    identifier. The shared `X-API-Key` is an app-level credential and must never
    be accepted as proof of user identity.
29. **[BLOCKER · Both]** **Give the production endpoint a stable address.** The
    documented absence of an Elastic IP means a stop/start moves the public
    address; an address that moves mid-review reads to a reviewer as a broken
    app.
30. **[SHOULD · Both]** **Record the account/sync backend as a second
    cross-project dependency** alongside `POST /v1/vision`, and rewrite
    `specs/coffee-server.md` rather than patching it — its "No storage of any
    kind" design principle is now false.

### 3.4 Privacy declarations, consent and policy

31. **[BLOCKER · Both]** **Maintain one written data inventory** — every field,
    where it goes, who touches it, how long it lives — and derive **both**
    stores' forms and the privacy policy from it. Never derive one form from the
    other; the same facts legitimately produce different answers (§2.5).
32. **[BLOCKER · Play]** **Re-derive the entire Data safety form from scratch.**
    At minimum add Personal info → Email address and User IDs; add App activity →
    Other user-generated content and Photos as **stored, non-ephemeral** types;
    answer the account-creation question; fill the deletion URL field; keep
    "encrypted in transit" answerable as yes.
33. **[BLOCKER · Apple]** **Complete the App Privacy questionnaire against the
    account-based reality**: Contact Info → Email Address, Identifiers → User
    ID, User Content → Photos and Other User Content, all *Data Linked to You*,
    purpose App Functionality. Declare third-party SDK collection as your own.
    Leave "Data Used to Track You" empty and ship no ATT prompt.
34. **[BLOCKER · Both]** **Update the privacy policy before the accounts
    release**, linked from both stores' metadata *and* in-app. It must satisfy
    Apple's 5.1.1(i) list — identify the data and every use, **affirmatively
    confirm that third parties receiving it provide equal protection**, and
    explain retention, deletion and consent withdrawal — and must align with
    both stores' declarations.
35. **[BLOCKER · Both]** **Keep AI-processing consent separate from account
    creation.** Signing up must never be construed as consent to send photos or
    brew data to a third-party AI service. One tap must never do two consent
    jobs.
36. **[BLOCKER · Apple]** **Provide an in-app way to withdraw AI consent** after
    it has been granted — a Settings toggle, not only a first-run modal.
37. **[BLOCKER · Both]** **Document Anthropic's and Qwen's data-retention terms
    in writing**, and confirm whether `coffee_server` persists request payloads.
    This now blocks *two* stores' forms and the privacy policy's
    equal-protection statement.
38. **[BLOCKER · Both]** **Disclose password handling in the privacy policy**,
    not as a declaration category. Neither store's taxonomy enumerates
    credentials; do not invent a category on either form.
39. **[SHOULD · Both]** **Do not add analytics or crash reporting in this
    release.** It would enlarge an already-large form revision, and on iOS an
    analytics or ads SDK is what would newly implicate ATT and could add a
    privacy-manifest-listed SDK.

### 3.5 Review and store mechanics

40. **[BLOCKER · Both]** **Maintain one permanent demo account**: email/password
    (never federated), stable password, no 2FA, no expiry, no geo restriction,
    English, seeded with representative **server-side** data, provisioned with
    AI quota, exempt in practice from lockout thresholds, and **an ordinary
    account with no reviewer-only code path**. Declare it in Play Console's
    sign-in details field and App Store Connect's App Review Information.
41. **[BLOCKER · Both]** **Keep the backend live, TLS-terminated and stable for
    the entire review window on both stores.**
42. **[BLOCKER · Play]** **Complete Google's OAuth brand verification before the
    production release, and start it early** — it requires a live homepage on a
    Search-Console-verified domain, a privacy policy URL, a terms-of-service URL
    and a support email.
43. **[BLOCKER · Play]** **Render the Sign in with Google button exactly to
    Google's branding guidelines.** Compliance is required for app verification,
    so this is not a style preference. Exact specification in §6.
44. **[BLOCKER · Apple]** **Use Apple's system-provided Sign in with Apple
    button** (`ASAuthorizationAppleIDButton` / `SignInWithAppleButton`; Sign in
    with Apple JS on web), never a hand-drawn imitation.
45. **[BLOCKER · Both]** **Provision the project domain first.** It serves six
    purposes with overlapping lead times: privacy policy, terms of service,
    Play's web deletion URL, Google's OAuth homepage on a Search-Console-verified
    domain, Apple's Sign in with Apple JS return URL, and a validated relay
    sender domain with SPF/DKIM. The project has no website today.
46. **[BLOCKER · Apple]** **Ship a privacy manifest for the app target itself**,
    declaring collected data types and the reasons for any "required reason" API
    usage.
47. **[BLOCKER · Both]** **Build sign-up and sign-in natively.** No browser
    redirect or web view for registration on either platform.
48. **[SHOULD · Both]** **State in the review notes what the account adds
    (sync).** With guest mode the reviewer can exercise most of the app without
    signing in, and an account feature that appears to do nothing is its own
    rejection risk.

### 3.6 Age and audience

49. **[BLOCKER · Play]** **Declare no under-13 age band** in Play Console's
    target audience, and state a minimum age in the account terms. Collecting an
    email address from children triggers Families policy and COPPA.
50. **[BLOCKER · Both]** **Re-run both stores' rating questionnaires** after the
    accounts change, answering "no" to every UGC, Social Media, Messaging and
    interaction capability. Expected: lowest IARC tier and Apple 4+.
51. **[BLOCKER · Both]** **Collect a minimum-age affirmation, never a date of
    birth**, and answer Apple's Age Assurance item honestly — a self-declared
    checkbox is the weakest form of assurance and must not be declared as more.
52. **[SHOULD · Both]** **Record a dated, jointly-owned decision on Apple's
    Declared Age Range API and Google's Play Age Signals API**, noting that
    Apple's posture is directive where Google's devolves the judgement, with
    **"any paid feature"** as the explicit re-check trigger.

### 3.7 EU, commercial and legal posture

53. **[BLOCKER · Both]** **Answer DSA trader status identically to both
    stores**, decided with counsel against the published factors. Both stores
    remove non-compliant apps from all 27 EU territories.
54. **[SHOULD · Apple]** **If distributing in the EU as an individual trader,
    arrange a mail-forwarding or P.O. box address before submission**, and
    decide Individual vs. Organization **before enrolling** — changing later is
    an entity migration, not a setting.
55. **[SHOULD · Both]** **Keep accounts and sync free for v1.** A paid tier
    forces Apple IAP, converts the Play account to a merchant account that must
    publish a full address, weakens the non-trader argument on both stores, and
    attaches minors' parental-consent obligations. Treat "make sync paid" as an
    event that re-opens this spec.
56. **[BLOCKER · Both]** **Do not launch EU distribution without a GDPR review
    of the controller/processor chain**, now including the account store itself
    and the hosting DPA and region, not only the AI round-trip.
57. **[BLOCKER · Both]** **Have the privacy policy, the hosting DPA, the
    deletion path and the export path live before the closed test opens.** The
    12 testers are real data subjects, not internal staff.

### 3.8 The local-only / Google-only / France architecture (2026-08-13)

> **Rules 1–57 above were written for a design with cross-device sync, three
> sign-in methods and an App Store submission. All three premises changed on
> 2026-08-13.** The new architecture: **no user content is stored server-side**
> (the device keeps everything and uploads nothing); **Google is the only
> sign-in method**; the account exists solely to authorise, meter and cut off
> abuse of the server endpoints; the server additionally runs the
> `specs/legal.md` crawler and serves a coffee-news feed; the listing is
> **France-only**; and **iOS is deferred to `specs/legal-ios.md`**.
>
> This section was produced by re-running the same two-specialist review
> (data-protection counsel · Google Play policy) against the changed facts, on
> 2026-08-13, and refereeing the two re-rulings into the single numbered set
> below. Where the two specialists reached the same conclusion by different
> routes, that is noted — the agreement is evidence, not redundancy.
>
> **Rules superseded by this section**, listed so nothing is silently dropped:
> 3 (email+password on every platform — void, see rule 65), 38 (password
> disclosure — void, no passwords exist), and the sync-dependent halves of 25
> (export) and 34. **Rules moved to `specs/legal-ios.md`**: 2, 5, 8, 9 (Apple
> half), 11, 14, 15, 20, 26, 33, 36, 44, 46, 54. **Rules 16–19 survive** with
> one identity provider instead of three. **Rule 40 is rewritten as rule 65.**

#### The premise correction both specialists made independently

58. **[BLOCKER · Play]** **State the architecture as "no user *content* is
    stored server-side", never as "no storage".** Metering and abuse cutoff
    cannot work without persisting a record keyed to a user — the Google
    `sub`, a quota counter, a reset window, a ban flag — retained for the life
    of the account. That record is personal data (pseudonymous identifier,
    GDPR Recitals 26/30) and it is precisely what access and deletion requests
    cover. Both specialists rejected the stated premise in the same terms,
    unprompted: a Data safety form derived from "no storage at all" is false.

59. **[BLOCKER · Both]** **Neither `+2.2a`, `+2.2b`, nor any marketing copy may
    say "your data never leaves your device."** With sync gone that sentence is
    *nearly* true, which is what makes it the single most likely false
    disclosure in the build — the AI path sends a bean-bag photo and the bean
    and session fields the user typed. "Your beans and sessions stay on this
    phone" is true and is the sentence to use. *(Play rates in-app text
    contradicting the Data safety declarations as the highest-probability
    enforcement route for this app; the remedy is removal, not resubmission.)*

#### Scope minimisation and the account record

60. **[BLOCKER · Both]** **Request `openid` only from Google. Do not request
    `email`, and do not request `profile`.** The account exists to meter and to
    cut off abuse; the opaque provider-scoped `sub` is sufficient for both.
    Losing sync removed every remaining reason `email` existed — no recovery,
    no verification, no account mail, no relay deliverability problem. Both
    specialists reached this independently and it is the cleanest win in the
    round: it removes **Personal info → Email address** from Play's Data safety
    form outright, and it removes name and avatar with it. *(GDPR Art. 5(1)(c).
    Re-adding `email` later is a rule 105 re-scope, not a shrug.)*
61. **[BLOCKER · Both]** **`sub` is still personal data. Never describe the
    account as anonymous.** Pseudonymous is the accurate word.
62. **[BLOCKER · Play]** **Disable Android Auto Backup for the app database and
    the images directory** — `android:allowBackup="false"`, or
    `android:dataExtractionRules` (API 31+) plus `android:fullBackupContent`
    (below 31) with both excluded — and **verify it in the merged manifest, not
    the source**, since a dependency's manifest can re-add it at merge time.
    `allowBackup` defaults to **true**, so in a default build Android uploads
    the whole local log to the user's Google Drive. That makes the app's
    headline claim false and the Data safety form wrong. If backup is instead
    left enabled deliberately, it must be declared as a transfer to Google
    Drive in the policy and on the form.

#### The lawful bases, restated for this architecture

63. **[BLOCKER · Both]** **State the basis per purpose, never as one blanket
    basis:** the Google `sub` and account record = **Art. 6(1)(b)**, necessary
    to provide the endpoint access the user asked for; the AI transfer =
    **Art. 6(1)(a)** consent (rules 76–84 of the previous round survive intact);
    metering, quota, rate limiting, abuse cutoff and server logs =
    **Art. 6(1)(f)**, Recital 49, with the interest named. Note that
    6(1)(f) is now unusually strong here because security *is* the account's
    entire reason to exist.
64. **[BLOCKER · Both]** **The developer is not a controller for the on-device
    database.** Art. 4(7) requires determining purposes *and* means; the
    developer supplies only the means, and nothing is transmitted or
    accessible. There is no Art. 4(2) processing by or on behalf of the
    developer, and the user's own use additionally falls inside Art. 2(2)(c).
    **This flips the moment the app phones home about local content, or a
    crash reporter or a backup uploads it** — which is what makes rule 62 a
    controllership question and not just a copy question.

#### Reviewer access — the blocker Google-only sign-in creates

65. **[BLOCKER · Play]** **Rule 40's "email/password, never federated" demo
    account is void as written, and its reason survives.** A reviewer cannot be
    handed a live personal Google account, and both AI and the news feed are
    sign-in-gated, so a reviewer without credentials cannot reach the
    prominent-disclosure modal — the one surface Play most wants to see. What
    satisfies Play now: **a dedicated Google Account created solely for
    review**, its credentials in Play Console's App access / Sign-in details
    field, **2FA off** (Play's "bypassable" clause means *do not enable it*),
    no Advanced Protection, stable password, no geo restriction, a recovery
    contact the developer controls, and **exempt from quota and ban
    thresholds** — an exhausted quota is now the most likely way a reviewer
    sees a broken app.
66. **[BLOCKER · Play]** **The most brittle item in the new review path is
    Google's own security heuristics**, which may challenge a sign-in from an
    unfamiliar datacentre IP with a verification prompt the reviewer cannot
    pass. Keep 2FA off, keep the account warm across varied networks, never let
    it go dormant between submissions, and re-verify it immediately before each
    one.
67. **[BLOCKER · Play]** **The OAuth test-user allowlist is necessary but not
    sufficient, and the two are commonly confused.** While the consent screen is
    in *Testing* only allowlisted accounts can sign in (100 cap, 7-day token
    expiry) — that gates *who*, it does not give a reviewer a *credential*. Use
    it in closed testing for the 12 testers plus the review account. Production
    requires the consent screen **Published** with brand verification complete
    (rule 42), after which the allowlist is irrelevant.
68. **[BLOCKER · Play]** **Rule 40's "no reviewer-only code path" survives and
    still binds.** No `if user.isReviewer` branch. Its "seeded with
    representative server-side data" clause is void — there is none — so the
    credential's job narrows to *letting the reviewer reach the AI consent
    modal and the news feed*. State in App access notes, **in English**, that
    sign-in is Google-only and what it unlocks.

#### Account deletion with an empty account

69. **[BLOCKER · Play]** **Play's Account Deletion policy still fires.** The
    trigger is the app *offering account creation*, not the app storing data.
    "Delete my account" must: hard-delete the identity row `(google, sub)` and
    the internal user ID; invalidate every session and token on every device;
    delete the metering, quota and ban records keyed to that user. **[SHOULD]**
    also revoke the Google OAuth grant (`POST oauth2.googleapis.com/revoke`) —
    hygiene on Play, a hard requirement on Apple, so it moves with
    `legal-ios.md` but is cheap to build now.
70. **[BLOCKER · Play]** **The deletion confirmation must state that the
    on-device log survives**, in plain language: *"Your coffee log stays on this
    phone. This removes your account from our server and signs you out."*
    Without it a reviewer assessing whether the path is "intuitive" reads a
    confirmation that does not say what happens, and users guess wrong in both
    directions — some fearing they will lose four years of brews, others
    expecting deletion to wipe the phone.
71. **[BLOCKER · Play]** **The web deletion page keeps its purpose with no data
    behind it.** A user who has uninstalled still has an identity row, live
    tokens, a quota record and a standing OAuth grant; the page kills them. It
    re-authenticates with **Google only** now, so §6.10 item 38 simplifies from
    three integrations to one and Sign in with Apple JS leaves this spec.

#### The crawler and the news feed

72. **[BLOCKER · Both]** **`specs/legal.md` §1.2 must be re-opened and the use
    case re-recorded before the catalogue or news feed ships.** Both specialists
    raised this unprompted and neither would grant it. Serving crawl results to
    Play users is no longer use case **(a)** (a private single-user database
    feeding coffee-can) — it is a server-side aggregation across many roasters,
    redistributed to many users, on a public store listing. That is at minimum
    case **(b)**, which `legal.md` currently marks **verdict NO** ("publish the
    scraper, not the scrape"), and it edges into **(c)** "permission required"
    on any displayed price or any monetisation. `legal-android.md` §4 rule 25's
    re-opening trigger has fired. The `legal.md` §1.3 outreach step — ask the
    roasters first — is the cheapest route through it.
73. **[BLOCKER · Both]** **`legal.md` rules 29–33 are now Play-load-bearing, not
    only French-law-load-bearing.** Facts only, never `body_html`, never re-host
    images, tasting notes normalised or ≤200 chars with attribution. These are
    precisely what keeps the app off Play's IP-takedown path, whose process is
    a rights-holder complaint rather than a proactive check. Say so in both
    specs so neither is relaxed on the other's authority.
74. **[BLOCKER · Both]** **News feed: headline, source name, date and link
    only.** No snippet beyond the headline, and **specifically no AI-generated
    summary of an article** — a derivative use outside the exception, which
    would also collide with `legal.md`'s TDM analysis. *(Droit voisin des
    éditeurs de presse, arts. L.218-1 et seq. CPI, loi n° 2019-775 transposing
    DSM art. 15: hyperlinks and "very short extracts" are excluded from the
    right; summaries are not.)*
75. **[BLOCKER · Both]** **Disclose that product photos are hotlinked from each
    roaster's own server**, so opening a listing reveals the user's IP address
    and User-Agent to a third party they have no relationship with. Hotlinking
    is required by `legal.md` rule 31 for copyright reasons and this is its
    privacy cost. Play's taxonomy has no IP-address type and needs no Data
    safety row; GDPR Art. 13(1)(e) needs the sentence. *(Counsel's finding;
    the Play specialist independently confirmed there is no form artifact.)*
76. **[BLOCKER · Both]** **Ship the D.111-16 rubric on the catalogue screen,
    directly accessible from it — not in the privacy policy.** Ranking
    criteria, capital and contractual links with listed roasters, whether any
    referencing is paid, exhaustiveness, and update frequency. *(L.111-7 code
    de la consommation and arts. D.111-16 et seq. `legal.md` calls its
    application to an unmonetised public catalogue "arguable"; do not sit in
    the arguable case.)* And note `legal.md` rule 37's staleness suppression is
    the live exposure: **L.121-2 pratique commerciale trompeuse liability
    attaches to the comparator, not to the roaster.**
77. **[SHOULD · Play]** **Give the news and catalogue feed its own reporting
    channel — an IP/takedown contact — separate from the Gen-AI report control
    of `legal-android.md` rule 5.** Different policy basis, different recipient.
78. **[SHOULD · Play]** **Re-run the content rating (IARC) and record the News
    declaration as a reasoned "no" rather than an obvious one.** A coffee-news
    feed makes both live judgements where `legal-android.md` §2.3 treated them
    as trivially inapplicable. A curated, server-side, fixed-source feed is not
    "unfiltered internet access" — **but that flips if the app ever renders
    arbitrary linked pages in-app, so open source links in a Custom Tab or the
    system browser**, never an in-app WebView on an arbitrary URL.
79. **[SHOULD · Play]** **The `legal.md` §3.10 rule 43 blocklist and its 24h
    response window is now a Play asset**, not only a French-law one: a roaster
    complaint or a Play IP takedown can be honoured within hours with no client
    release, and Play's takedown process asks precisely how fast you can
    comply.

#### France-only distribution

80. **[BLOCKER · Both]** **Narrowing the listing to France reduces Play surface
    and maximises GDPR surface.** Every user is an EU data subject from day one,
    so rule 56's GDPR review of the controller/processor chain is **immediately
    triggered, not deferred**, and DSA trader status (rule 53) now carries total
    consequence — non-compliance removes the app from all 27 EU territories,
    which for a France-only listing is the entire listing.
81. **[BLOCKER · Both]** **CNIL is the lead supervisory authority** (Art. 56) and
    is the authority named under Art. 13(2)(d). France-established means **no
    Art. 27 representative is required**; rule 74 of the previous round
    resolves to a statement rather than a decision.
82. **[BLOCKER · Both]** **The minimum-age affirmation is 15, not 13.** France
    exercised the Art. 8(1) GDPR derogation downward via art. 45 of loi n° 78-17,
    so consent-based processing below 15 requires parental authorisation. The
    AI feature runs on consent and is sign-in-gated. **This contradicts what
    `+2.1_create_account` currently draws** and amends rules 49 and 51.
83. **[BLOCKER · Both]** **Record the art. 82 loi Informatique et Libertés
    conclusion**: CNIL's doctrine extends art. 82 (ePrivacy art. 5(3)) beyond
    cookies to any read or write on terminal equipment, with an exemption for
    what is strictly necessary to the service the user expressly requested. The
    local SQLite database is exempt, so **no consent banner is needed** — but
    reading an advertising identifier or adding any analytics SDK would require
    art. 82 consent *independently of GDPR*. This is the strongest reason yet
    to keep rule 39 (no analytics, no crash reporting), and CNIL's
    *recommandation applications mobiles* has made this its most active mobile
    enforcement area.
84. **[SHOULD · Both]** **LCEN loi n° 2004-575 art. 6 III-2 lets a
    non-professional natural person stay anonymous to the public** provided the
    host holds their identity — which preserves §2.11's Play-side privacy
    posture, where Play publishes a developer name and not a legal address.
    **It does not survive iOS**, which publishes the legal seller name; carried
    to `legal-ios.md`.
85. **[SHOULD · Play]** **US state privacy statutes drop out in practice while
    the listing is France-only.** The CCPA determination was already
    threshold-negative; CalOPPA's Do Not Track sentence becomes belt-and-braces
    rather than an obligation. **Record rules 71–72 of the previous round as
    inapplicable rather than deleting them** — Play country targeting is a
    Console setting, not a technical block, and adding US distribution revives
    both immediately. Keep the DNT sentence anyway: it costs one line and is the
    accurate one either way.
86. **[SHOULD · Play]** **Age assurance narrows.** Play Age Signals keys to
    account country, so Texas and Brazil are out of scope for a France-only
    listing; rule 52's decision record may read "not applicable to a France-only
    listing", **with listing expansion as an explicit re-check trigger**
    alongside "any paid feature".
87. **[BLOCKER · Play]** **Two things France-only does *not* relieve.** The
    privacy-policy URL must still be **non-geofenced** — restricting
    distribution does not license geofencing the policy, and Google fetches it
    from wherever it is. And **App access instructions must still be in
    English**, Play's own requirement, even for a French listing. Everything
    else user-facing — listing, policy, both AI modals, `+2.2a`, `+2.2b`, the
    deletion page — should be in French.

#### The two legal screens

88. **[BLOCKER · Play]** **What Play requires in-app is a *link* to the
    canonical privacy-policy URL, not a copy of its text.** `+2.2a` must expose
    that URL as a tappable, selectable affordance opening exactly the URL
    declared in Console. A screen that renders prose and never exposes the URL
    does not discharge `legal-android.md` rule 14. **The same URL goes in three
    places** — App content, the Data safety section, and `+2.2a`.
89. **[BLOCKER · Play]** **`+2.2a` may not ship before the rule 45 domain is
    live and the URL is declared in Console.** A legal row opening a dead link
    is a reviewer-visible defect on the one surface Play named. This gate is
    **earlier than either submission**: rule 57 requires the policy live before
    the closed test opens, because the 12 testers are real data subjects.
90. **[SHOULD · Play]** **`+2.2a` renders a short accurate summary alongside the
    URL, generated from the rule 31 data inventory rather than written
    freehand.** *(This resolves a genuine disagreement: counsel initially ruled
    bundled full text compulsory under GDPR Art. 12(1) and withdrew it on
    rebuttal — for an offline account-less user no personal data reaches the
    developer, so Art. 13 is not engaged, and every moment it is engaged the
    device has network by construction. The Play specialist withdrew its
    "drift" objection in the same round against a build-generated copy. The
    surviving design is the intersection: summary plus URL.)* The in-app screen
    carries **no last-updated date of its own** — the date belongs to the hosted
    document, and a baked date is the one field guaranteed to drift.
91. **[BLOCKER · Play]** **Any server-side change that alters the policy's
    factual content is gated on a client release** — a `coffee_server` routing
    change, a new processor, or a change to the crawler's source list or what
    the news feed displays. This is the operational price of rendering any
    policy text in-app and belongs in `specs/coffee-server.md` too.
92. **[BLOCKER · Both]** **`+2.2a` states, precisely rather than reassuringly,
    what happens to local data** — that the developer has no copy and no way to
    get one, so there is nothing to export or delete on the user's behalf and
    nothing to restore if the phone is lost; that uninstalling deletes it; and
    **that a phone backup contains it and is governed by whoever runs the
    backup** (see rule 62).
93. **[BLOCKER · Both]** **The access response is a small JSON document: the
    Google `sub`, usage counters and quota state, rate-limit records, server
    logs.** Nothing else exists. **Art. 20 portability no longer engages** —
    usage counters are observed and derived data, outside portability per WP29's
    portability guidelines — so this is an **Art. 15(3) access** obligation
    only. The previous round's rule 66 (JSON plus photo files in an archive) is
    void with sync.
94. **[BLOCKER · Play]** **`+2.2b` is not, and may never be presented as, the
    disclosure-and-consent step.** Play's Prominent Disclosure & Consent
    requirement states the disclosure must not require navigating into a menu or
    settings. The `legal-android.md` rule 4 modal is the compliance artifact;
    `+2.2b` is a re-readable copy and a withdrawal control.
95. **[BLOCKER · Both]** **Two AI consent controls, not one, and no master
    toggle above them** — "read labels from photos" (sends a photo) and
    "suggest brew settings" (sends the bean and session fields typed, no photo),
    both default off, each with its own state-and-date line. The data
    categories differ materially: a photograph carries incidental content the
    user did not intend to send. Both specialists converged here from different
    instruments — GDPR Recital 43 / Art. 7(2) for counsel, and for Play the
    observation that a modal shown at Scan Label which also authorises a later
    Ask-AI transfer means **that transfer had no disclosure immediately before
    it**. A parent switch would recreate the bundling defect inside the settings
    screen. **The news feed needs no third toggle and no PD&C modal** — a user
    tapping a news feed reasonably expects a network fetch, and nothing of
    theirs is transmitted beyond the account token.
96. **[BLOCKER · Both]** **One disclosure modal per AI operation**, each shown
    immediately before that operation and describing only its own payload. This
    supersedes `plan/screens.md` §11 fix 3's genericised "and/or" copy, which was
    the right fix for a combined modal and is unnecessary once they split.
    Each modal names **both** providers, since routing is server-side.
97. **[BLOCKER · Both]** **Withdrawal takes effect on the toggle immediately,
    with no confirmation dialog and no persuasion copy**; a neutral consequence
    line sits under the control permanently, in both states. Granting costs one
    affirmative tap, so withdrawal must not cost more. **Re-granting is
    asymmetric by design**: tapping an off toggle opens that operation's
    disclosure sheet and consent is recorded by the sheet's affirmative action,
    not by the tap. *(Art. 7(3) sets a floor under the ease of withdrawal, not
    a symmetry requirement in both directions; Art. 4(11) requires a re-grant to
    be informed; Play's PD&C refuses settings-screen consent. Do not "restore
    symmetry" by adding friction to withdrawal — that is the one move Art. 7(3)
    actually prohibits.)*
98. **[BLOCKER · Both]** **An explicit withdrawal must not re-arm the periodic
    re-prompt.** `screens.md` §11's `shown`/`accepted` pair cannot distinguish
    "never accepted" from "accepted, then withdrew", so as written it re-prompts
    on every AI attempt forever — nagging exactly the user who exercised an
    Art. 7(3) right. Add `withdrawnAt`; after withdrawal the AI entry points
    show an inline, non-modal off-state linking to `+2.2b`, and re-granting is
    user-initiated. Store `acceptedDisclosureVersion` too, and re-prompt on a
    **material** change — a new or changed provider, a new destination country,
    a new data category in the payload, or a provider beginning to retain, train
    on or human-review the data. Rewording for clarity does not re-prompt.
99. **[BLOCKER · Both]** **`+2.2b` states what withdrawal does and does not do**:
    future sending stops; beans, sessions and transcriptions already in the log
    are untouched; and it does not reach back into any copy the AI provider
    holds. The last clause is fact-dependent on rule 37 and must not be written
    as "your data is deleted from the AI provider" unless a documented
    per-request deletion route exists. It almost certainly does not.
100. **[BLOCKER · Both]** **Neither screen may assert non-retention,
    non-sharing, or any data-residency fact while rules 11, 12, 27 and 37 are
    open.** No "your photo isn't stored", no "we never share your data", no
    region or jurisdiction claim. **An absent sentence is a compliance
    non-event; a wrong one is a removal.** Rule 12 (`coffee_server` payload
    retention) becomes *more* load-bearing under this architecture, not less:
    "nothing of yours is stored on our server" is now the app's headline claim
    and it is false if the gateway logs request bodies.
101. **[BLOCKER · Play]** **`+2.2a`'s "encrypted in transit" statement is a
    release gate on rule 27.** The Google ID token and the AI payload both
    travel; shipping the sentence against the documented cleartext deployment is
    simultaneously a false in-app disclosure, a false Data safety declaration
    and a GDPR Art. 32 failure.
102. **[BLOCKER · Play]** **Rule 37a is amended: with Apple gone, the pessimistic
    route is genuinely available.** The AI feature ships on either (a) Anthropic's
    and Qwen's retention terms in writing, or (b) a written, dated decision to
    declare the OCR/suggestion leg as *shared with third parties* on the Data
    safety form. Play's form has no "unknown" option, so the answer is
    submission-blocking either way. **(a) remains strongly preferred** — GDPR
    Art. 13(1)(e)/(f) needs the recipients named regardless, and (b) makes
    "shares your photos and activity with third parties" the app's entire
    visible data story on the store card, since with sync gone the AI leg is the
    only reason those types appear at all. **The Apple half of 37a revives the
    moment `legal-ios.md` lands.**

#### The third-party licences row — decision recorded

103. **[Decision, 2026-08-13 — overridden]** **Both specialists ruled the
    "Open-source licences" row must not be removed, and it has been removed on
    the product owner's instruction.** Recorded here rather than dropped
    silently, per their own prescription, and reversing `plan/README.md` item 18's
    accepted resolution.
    - **The finding.** The row was never a claim that this app is open source;
      it is the attribution notice the app's **bundled** dependencies require it
      to reproduce. Apache-2.0 §4(a) requires recipients of the **Object form**
      to receive a copy of the licence — unconditioned on a NOTICE file and
      undischarged by the app being closed-source — and §4(d) directs NOTICE
      attributions into "a display generated by the Derivative Works... wherever
      such third-party notices normally appear", which on a mobile app is this
      screen and nowhere else. MIT conditions its grant on the notice being
      "included in all copies"; BSD-2/3 clause 2 requires reproduction in "the
      documentation and/or other materials provided with the distribution".
      These are **conditions of the grant, not covenants** — distribution
      without them is distribution without a licence (*Jacobsen v. Katzer*,
      535 F.3d 1373 (Fed. Cir. 2008)) — and **Apache-2.0 provides no cure
      period**, so a shipped build in breach stays in breach until a corrected
      build ships.
    - **The Play position, stated for balance.** No Play policy requires in-app
      licence attribution, no Console question asks about it, and its absence is
      invisible at review. The exposure is downstream and complaint-driven, via
      Play's IP policy and the DDA's rights warranty.
    - **The recommended fix, unanimous and declined.** Retitle the row
      "Third-party software" — a one-string change that answers the stated
      objection ("it is not an open source app") in full, since the objection
      was to what the label implies rather than to the notices. Generate the
      screen at build time from the resolved dependency graph (`app.cash.licensee`
      preferred over `play-services-oss-licenses`: no Play Services dependency,
      and one `artifacts.json` can drive an iOS acknowledgements surface later).
    - **If the removal stands**, the notices must exist somewhere reachable —
      an About block on `+2.2a`, or a page on the rule 45 domain — and **the
      licence inventory must be produced regardless**, because any (A)GPL, LGPL
      or SSPL dependency is a stop-ship rather than a notice question, and that
      cannot be known until the inventory exists.

### 3.9 Tripwires — what re-opens this spec

> Renumbered from 58–60 on 2026-08-13 so §3.8's architecture rules could take
> the run from 58. Tripwires stay last in the section order deliberately.

104. **[BLOCKER · Both]** **Any feature making one user's data visible or
    accessible to another user makes this a UGC app on both stores** —
    activating Play's moderation stack and Apple's Guideline 1.2 together, and
    changing both rating questionnaires. Shared libraries, invites and
    "popular with other users" surfaces all cross the line; same-user
    cross-device sync does not. Scope as its own project; do not retrofit.
    **Live risk under the 2026-08-13 architecture:** the news and catalogue
    feed is not UGC today, and becomes UGC the moment it carries user comments,
    ratings, or a "popular with other users" surface (rule 78).
105. **[SHOULD · Both]** **Any additional OAuth scope, any new processor, and any
    change to what sync stores re-opens the data inventory, both stores' forms,
    and the privacy policy.** Treat all four as one changeset, permanently.
    **Amended 2026-08-13:** "what sync stores" is now "what the server stores"
    — the metering record — and re-adding the `email` scope dropped by rule 60
    is exactly the kind of change this tripwire exists to catch.
106. **[BLOCKER · Both]** **Any paid feature re-opens the billing analysis on
    both stores, the trader determination, and the age-assurance decision** —
    three regimes that fire simultaneously (§2.8, §2.11). **Amended
    2026-08-13:** it additionally slides the crawler from `legal.md` use case
    (b) toward (c), "permission required" (rule 72), and revives the US state
    statutes retired by rule 85 if the listing widens.

---

## 4. Implementation roadmap — the dependency tiers

The rules above are grouped thematically; this is the order they must actually
be built in. The single most common way this project could waste effort is
completing store declarations (Tier 3) before the backend they describe
(Tier 0) exists.

**Tier 0 — the critical-path root. Nothing else can be finished first.**
The `coffee_server` account system: persistent per-user store, per-user identity,
per-user authorization on every endpoint (rule 28), TLS termination with no
cleartext path (rule 27), a stable address (rule 29), server-side token
verification (rule 10), password hashing and auth rate limiting (rules 12–13),
and the account schema of rule 7. Tier 0 gates **both** platforms.

**Tier 1 — server capabilities the store policies name directly.**
The single deletion routine with its ordered operations (rules 16, 20–22),
the web deletion endpoint and its re-authentication (rules 18–19), Apple token
revocation (rule 20), data export (rule 25), and the relay sender-domain
registration (rule 26). The project **domain** (rule 45) belongs here too and
should be provisioned before anything else in this tier, because brand
verification, Search Console, DNS propagation and Apple's sender validation all
have independent lead times that overlap badly.

**Tier 2 — client work, on both platforms.**
Sign-in UI and the button specifications (rules 2–6, 43–44), guest-mode
architecture (rule 1), account linking (rules 9, 15), in-app deletion and export
entry points (rules 17, 24), the AI consent step and its withdrawal toggle
(rules 35–36), native sign-up (rule 47), and the iOS privacy manifests
(rules 5, 46).

**Tier 3 — declarations, last, because they must describe what was built.**
The data inventory (rule 31), both stores' privacy forms (rules 32–33), the
privacy policy (rule 34), rating questionnaires and audience (rules 49–51),
trader status (rule 53), the demo account and review notes (rules 40, 48), and
the age-signal decision record (rule 52). Re-doing any of these after a Tier 0
or Tier 1 change is pure waste.

**Scheduling note.** The Android closed test (12 testers × 14 continuous days)
can run against the account-less build defined in the design plan's
closed-testing-ready milestone, **in parallel with Tiers 0–1**. Start that clock
early. But rule 57 binds: if the closed test is run against a build that *does*
include accounts, the GDPR artifacts must already be live.

---

## 5. The joint minimum-compliant configuration

The smallest account design that satisfies both stores at once. Two
configurations are compliant; the choice between them is a real product
decision, not a formality.

**Option A — the absolute minimum: email + password only, on both platforms.**
No Google Sign-In means Apple's Guideline 4.8 never fires, which removes Sign in
with Apple, the GoogleSignIn SDK and its privacy-manifest exposure, Credential
Manager, OAuth brand verification, the scope decisions, and two of the three web
re-authentication integrations. If nobody is attached to Google sign-in, this is
dramatically smaller and it satisfies both stores.

**Option B — the minimum that keeps the stated product requirement (Google
sign-in):**

- **Accounts optional on both platforms.** The app launches into full local
  functionality; nothing that works offline today is ever gated. Sign-in is
  reached from Settings or a dismissible prompt, framed as sync.
- **Sign-in methods:** iOS carries **three** — Sign in with Apple, Sign in with
  Google, email + password. Android carries **at least two** — Sign in with
  Google and email + password — with Sign in with Apple via Sign in with Apple
  JS as an open question (§7). The **web** page carries **all three** regardless.
- **Email + password is mandatory everywhere** — it is the reviewer's path on
  both stores.
- **Minimum scopes:** `openid` + `email` from Google; email scope only, not
  name, from Apple.
- **Account schema:** internal opaque user ID as primary key;
  `identities(provider, subject, user_id)` unique on `(provider, subject)`;
  email a nullable attribute carrying `email_verified` and `is_private_email`.
  Never key on email; never auto-link on a relay address; explicit linking in
  Settings.
- **Backend:** TLS with no cleartext path; per-user authorization on every
  endpoint against the server-verified session; the shared `X-API-Key` never
  accepted as user identity; argon2id/scrypt/bcrypt hashing; auth rate limiting
  tuned so a reviewer cannot trip it; server-side ID-token verification.
- **One deletion routine**, three entry points, Apple revocation before purge,
  object-storage purge included. **One export endpoint.**
- **One domain** hosting the privacy policy, terms, the web deletion page with
  all three providers' re-auth, and the OAuth homepage — Search-Console
  verified, registered and validated with Apple as a relay sender domain, SPF
  and/or DKIM configured.
- **One permanent demo account** — email/password, seeded server-side, no 2FA,
  no expiry, no special code path, with AI quota.
- **AI consent** a separate, in-feature, pre-transmission step on both
  platforms, withdrawable from Settings, never bundled into sign-up.
- **Age:** no under-13 band on Play; honest "no" to Apple's capability
  questions; a minimum-age affirmation with no date of birth; a dated joint
  decision on the age-signal APIs with "any paid feature" as the trigger.
- **Two forms, one inventory.** Derive Apple's and Play's declarations from a
  single written data inventory; never copy one into the other.
- **Free.** Keep accounts and sync unpaid for v1.

---

## 6. UI requirements

Binding on the sign-in and create-account screens. A wireframe is drawn
directly from this section, so it is stated concretely. **There are two
platform variants — draw both.** Do not attempt a single shared screen; the
button counts differ and the branded buttons cannot be restyled to match each
other.

### 6.1 Before the screen is ever reached (both platforms)

1. The app **launches into full local functionality with no account**. This
   screen is never the first thing a new user sees and never blocks the app.
2. Entry points are a **Settings/Profile row**, and optionally a **dismissible,
   non-blocking** prompt once the user has data worth syncing. Dismissal always
   leaves the user in a working app.
3. The framing is **"sync across your devices"**, never "create an account to
   continue".

### 6.2 iOS variant — three sign-in buttons, Apple first

4. **Sign in with Apple** — Apple's system-provided button, **first in the
   stack**. Required by Guideline 4.8 because the Google button exists.
5. **Sign in with Google** — Google's official button, second.
6. **Continue with email** — the app's own path, third. Directly reachable,
   never behind a "more options" disclosure: it is the reviewer's route in.
7. **Continue without an account** — at least as visually available as the three
   sign-in options. Not a footnote, not grey-on-grey.

If the product drops Google from the iOS build, items 4 and 5 both disappear
and only the email path remains. That is the only other compliant iOS
configuration.

### 6.3 Android variant — two sign-in buttons

8. **Sign in with Google** — Google's official button, first.
9. **Continue with email** — the app's own path, second. Same reachability rule
   as item 6.
10. **Continue without an account** — same treatment as item 7.
11. *(Optional third, pending the §7 decision: **Sign in with Apple** via Sign
    in with Apple JS, placed below Google. No Play rule constrains its presence
    or placement.)*
12. Also implement the Credential Manager **bottom-sheet** flow alongside the
    button; the wireframe should show both entry points.

### 6.4 Prominence, ordering and styling (both variants)

13. All sign-in affordances are **equivalent options**: same width, same height,
    same vertical stack, no primary/secondary styling that subordinates one.
    None may be below the fold or behind a disclosure.
14. **Equal prominence does not mean identical styling.** The Apple and Google
    buttons carry mandated, mutually incompatible visual specifications and
    **neither may be restyled to the app's green tokens** (`accent` /
    `accentText`). Match their **dimensions and spacing**, not their colours.
    This is a compliance constraint on both sides, not a design compromise to be
    resolved in review — the wireframe must accept two differently-styled
    buttons of identical dimensions stacked together.
15. Match the other buttons' height and corner radius to the platform's
    system-provided button, not the reverse.
16. On iOS, confirm Apple's Human Interface Guidelines prominence rule for the
    Sign in with Apple button in a real browser before finalising (§8);
    first-and-equal satisfies every reading of it.

### 6.5 Sign in with Google button — exact specification (both platforms)

Required for Google's app verification, not a style preference.

17. Call-to-action text is exactly one of **"Sign in with Google"**, **"Sign up
    with Google"**, or **"Continue with Google"** (localized permitted). Never
    "Google" alone, never a bare "G".
18. One of three themes, exact values: **light** `#FFFFFF` fill / `#747775`
    stroke / `#1F1F1F` text; **dark** `#131314` / `#8E918F` / `#E3E3E3`;
    **neutral** `#F2F2F2` fill / no stroke / `#1F1F1F` text. No other background
    colour.
19. Typeface **Google Sans Medium**. Padding: Android 12px / 10px / 12px; iOS
    16px / 12px / 16px.
20. The **standard full-colour "G" mark, unmodified, on a white background** —
    never monochrome, never a custom icon. Scale only with aspect ratio
    preserved.

### 6.6 Text and links visible before an account is created (both variants)

21. **Two separate statements, not one.** This is the correction agreed in
    cross-review, because a single "we only collect your name and email" line is
    inaccurate once sync exists and would contradict both stores' data
    declarations — which Play separately requires to align with the privacy
    policy:
    - *what the account stores*: "Your account stores your email address."
    - *what sync uploads*: "Syncing uploads your beans, brews and photos to our
      server so they appear on your other devices."
22. **Privacy policy link**, tappable, opening the same URL declared in both
    stores' metadata.
23. **Terms of service link** — also required for Google's OAuth brand
    verification.
24. A **minimum-age affirmation** consistent with a 13+ account minimum: a
    checkbox, or a stated minimum age in the terms line. **Do not collect a date
    of birth.**

### 6.7 Consent mechanics (both variants)

25. **No pre-ticked checkboxes.** Affirmative action only; navigating away or
    scrolling is never consent.
26. Any acceptance checkbox covers **only** the account terms and privacy policy
    — one purpose, one control.
27. **The AI-processing consent must not appear on this screen** and must not be
    bundled into the sign-up action or into terms acceptance. It stays a
    separate step at first use of the OCR/suggestion feature.

### 6.8 What must not be on the screen

28. No redirect into a browser or web view for **registration** — native only.
    *(Deletion on the web is fine; registration is not.)*
29. No ATT prompt anywhere in this flow (iOS).
30. No request for phone number, date of birth, display name, or avatar.
31. Nothing conditioning account creation on accepting marketing, tracking or
    optional data collection.

### 6.9 Elsewhere in the app, same changeset (both platforms)

32. **Delete account** — a destructive action in account settings, at most two
    taps from a top-level screen, self-service, with a confirmation stating in
    plain language what is deleted and what is retained and for how long.
33. **Delete synced data (keep account)**, if built — visually and verbally
    unmistakable from item 32: different section, different treatment, explicit
    consequence text in each confirmation.
34. **Export my data.**
35. **A toggle to withdraw AI-processing consent** after it has been granted.
36. **Privacy policy link**, and a link to the **web deletion page**, so the
    in-app and web deletion routes are discoverable from one place.
37. **Add a password to this account** for federated users, so no user is
    stranded on a platform lacking their identity provider.

### 6.10 The web deletion page (not an app screen, but part of this design)

38. **Re-authentication with all three providers** — Sign in with Apple JS,
    Google Identity Services, email/password — then the same server-side
    deletion routine the apps call.
39. It must work for someone who has **already uninstalled**, without
    reinstalling, and must reference the app or developer name.
40. A **support-mediated fallback** sits below as a clearly secondary route for
    users who have lost access to their identity provider. It is acceptable
    here; it is never acceptable as the in-app path.

---

## 7. Open disagreements

Recorded rather than smoothed over. Neither is resolved by this document.

**7.1 Does the Android app need a Sign in with Apple button?**

*The Apple reviewer's position:* three sign-in methods on **both** platforms.
Otherwise an account created with Sign in with Apple on iOS is unreachable from
Android and accounts fork by platform, which the shared-backend premise does not
tolerate. Sign in with Apple JS is the system-provided mechanism for exactly
this case.

*The Play reviewer's position:* **Play has no rule of any kind here** — verified —
so this is a product decision, not a compliance one, and it should not be
written into a compliance spec as a requirement. The forking problem is real but
has a cheaper mitigation: rule 15's "add a password credential to an existing
federated account" gives every cross-platform user a route that works
everywhere, without a third SDK integration on Android.

*What both agree on:* the **web** deletion/account page needs all three
providers regardless (rule 19), so the Sign in with Apple JS integration must be
built either way — which narrows the disagreement to whether the Android *app*
also surfaces it, and materially lowers its cost.

*Recommendation pending decision:* build Sign in with Apple JS for the web
(required), ship rule 15's credential-linking (cheap, useful regardless), and
treat the Android button as **optional and deferrable**. §6.3 item 11 is written
to accommodate it without requiring it.

*Play-side caution if it is added:* run it in a Custom Tab or the system
browser, **never an embedded WebView**. A WebView rendering a third party's
credential form is a credential-capture pattern and a genuine exposure under
Play's deceptive-behaviour and user-data rules.

**7.2 How hard to push the age-assurance decision.**

Both reviewers agree the legal question is answered once for both platforms, and
that a dated decision record with a re-check trigger is the right artifact
(rule 52). They disagree on emphasis: the Play side reads it as a low-priority
legal-exposure question that a general-audience coffee logger with no
age-restricted content and no purchases is a poor fit for; the Apple side notes
Apple's announcement is **directive** rather than devolved and therefore treats
"we are not integrating" as a weaker position on the App Store. The spec records
both postures (§2.8) rather than picking one. This should be resolved with
counsel, not between the two reviews.

---

## 8. What could not be verified

Consolidated from both reviews. Stated explicitly rather than asserted with
false confidence.

**Play side**

- **The partial-deletion declaration in Play Console.** No first-party public
  wording was found for a "users can request that some data is deleted (without
  deleting the account)" option. Rule 24 is written as product guidance, not as
  a declaration requirement. Verify in the live Console, which is authoritative
  and not publicly documented.
- **Exact Play Console field labels.** The reviewer-credentials section appears
  as both "App access" and "Sign-in details" across Google's own pages; the
  account-creation-method question's exact wording comes from a secondary
  source. The requirements behind both are verified; the labels are not.
- **Credential Manager's OAuth client-ID type.** High confidence it is the Web
  application (server) client ID rather than an Android client ID, but no single
  unambiguous verbatim sentence was retrieved. It will be obvious at first
  integration.
- **The legacy Google Sign-In removal date.** Google's live migration page says
  only "will be removed... in a future release", with no date, despite a 2024
  blog projecting 2025. Does not affect rule 4 either way.
- **Play's alternative-billing fee percentages and the injunction's expiry
  date** — from secondary reporting. The policy statements and the four dates in
  §2.11 are first-party.
- **Whether Play's public developer profile ever surfaces the legal name** for a
  personal account. Google's documentation distinguishes developer name from
  legal identity and lists the legal name as not publicly shown; no contrary
  first-party statement was found, but confirm in the Console before relying on
  it.
- **Whether Play requires feature parity between the closed-tested build and the
  build submitted for production access.** No such rule was found; absence of a
  found rule is weaker than a confirmed absence. Material because §4 recommends
  starting the tester clock on an account-less build.
- **The exact Console flow for the DSA trader declaration**, and whether Play's
  published trader fields match Apple's field-for-field. The obligation and the
  removal consequence are verified; the comparison is not.

**Apple side**

- **The Human Interface Guidelines' specific Sign in with Apple *button* rules**
  — minimum size, corner radius, allowed titles, and the widely-repeated
  requirement that it be at least as prominent as other sign-in buttons. Apple's
  HIG pages are JavaScript-rendered and returned no body text. That HIG
  compliance is *required* was verified; the specific parameters were not. §6.4
  item 16 reflects this.
- **Whether Apple has published any interpretive statement on whether a
  first-party email/password system satisfies Guideline 4.8's three criteria.**
  None was found. §2.1's conclusion is a close reading of the guideline's own
  text and is the conservative reading.
- **Whether a user can switch off relay forwarding after the fact.** Apple's
  configuration page addresses only the developer disabling bounce
  notifications. Treat "the address may become undeliverable" as a design
  assumption to be safe against, not a verified fact.
- **The specific "required reason" API categories** behind privacy-manifest
  entries (Apple's TN3183). The technote's existence and the manifest obligation
  were confirmed; the API list was not enumerated.
- **Any App Review Guidelines revision between 2026-06-08 and 2026-08-07.** The
  live page displayed no last-updated date and Apple's news feed showed no
  later guidelines announcement — weaker evidence than a dated page.
- **Effective dates on Apple's third-party SDK requirements page.** The
  obligation is stated; the version fetched carried no enforcement dates.

**Both / neither**

- **Anthropic's and Qwen's actual data-retention terms**, and whether
  `coffee_server` persists request payloads. Unresolved since
  `specs/legal-android.md` rules 11–12; now blocking **two** stores' forms and
  the privacy policy's equal-protection statement (rule 37).
- **Anything inside either store's console.** The live IARC question set, Play's
  Data safety form flow, and App Store Connect's declaration screens are
  console-only. Everything here about form *content* derives from published help
  documentation, not from the forms themselves.
- **Cross-verification.** Each reviewer verified their own store's citations
  against live pages and relied on the other's sourcing for the other store.
  Neither independently re-verified the other's claims.
