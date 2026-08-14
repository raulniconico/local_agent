# coffee_ios — Apple App Store compliance spec

**Status: deferred, not cancelled.** Nothing is being built for iOS. This file
exists so that the Apple-sourced analysis already paid for is not lost when it
is needed, and so `specs/legal-android.md` and `specs/legal-accounts.md` can be
read as Android/Play documents without Apple rules interleaved through them.

Created 2026-08-13, when the product narrowed to a France-only Android launch
with Google-only sign-in. Everything here was **produced by the two-specialist
reviews recorded in `specs/legal-accounts.md`** (§2, §3, and §3.8's re-ruling)
and is carried over verbatim in substance, with its original rule numbers cited
so the reasoning behind each can be read at source.

> **Read this before any iOS work begins, and re-verify every citation.** These
> findings were correct when written against a *different* product shape — one
> with cross-device sync and three sign-in methods. The architecture changed
> underneath them. Treat this as a preserved argument, not a current checklist.

- [1. Why this is a separate file](#1-why-this-is-a-separate-file)
- [2. The blocker Google-only sign-in creates](#2-the-blocker-google-only-sign-in-creates)
- [3. Carried rules](#3-carried-rules)
- [4. What changes if iOS is revived](#4-what-changes-if-ios-is-revived)

---

## 1. Why this is a separate file

`legal-accounts.md` was written as a two-store document because accounts and
sync were shipping on both. The 2026-08-13 change removed the second store from
scope, and a spec that keeps ruling on a platform nobody is building for makes
every Android rule harder to read — the reader has to decide, per rule, whether
it binds them.

The split is by **compelling authority**, not by topic. A rule stays in the
Android documents if Play or French/EU law compels it; it moves here if Apple
is its only source. Where both compel the same thing by different routes, the
rule stays on the Android side and is noted here.

---

## 2. The blocker Google-only sign-in creates

**This is the first thing to resolve if iOS is revived, and it is not a
detail.**

**Guideline 4.8 (Login Services).** An app offering a third-party login service
must offer at least one equivalent option that limits data collection to name
and email, lets the user keep the email private, and does not track them.
Sign in with Apple is the canonical satisfier. **Google-only sign-in is an
automatic 4.8 rejection on iOS.**

There is a subtlety worth recording, because it may keep the app clean: 4.8
applies where the app *uses a third-party login service*. An app offering
**only its own** account system does not trigger it. So the exemption case is
"no federated login at all" — not "one federated login". Adding Sign in with
Apple alongside Google is the ordinary path; the alternative is dropping
federated sign-in entirely, which is a worse product.

**The consequence for account identity** is the one that must be designed for
*now*, not later: an account created with Sign in with Apple on iOS must be
reachable from Android, or accounts fork by platform. `legal-accounts.md`
rule 7 already requires keying on an internal ID with `(provider, subject)`
rather than on email — **that rule is what keeps this option open**, and it
survives in the Android spec precisely for this reason. Do not "simplify" it
away while iOS is deferred.

**Guideline 4.8 was recorded as an open disagreement** between the two
specialists (`legal-accounts.md` §7.1) on whether the *Android* app also needs
a Sign in with Apple button. That disagreement is dormant, not resolved.

---

## 3. Carried rules

Each entry cites its original rule number in `legal-accounts.md` so the full
reasoning can be read there.

### 3.1 Sign-in and identity

| Original | Rule |
| --- | --- |
| 2 | **Sign in with Apple is required** wherever another third-party login is offered (4.8), and appears **first** in the button stack. |
| 5 | The iOS sign-in screen is a **different screen** from Android's — three buttons, not two. Do not attempt one shared design; the branded buttons cannot be restyled to match each other. |
| 8, 9 | The **Apple relay email** (`@privaterelay.appleid.com`) is a durable unique identifier for a person: masked ≠ uncollected. It is still Contact Info → Email, still Linked. Register the **relay sender domain** with Apple and configure SPF/DKIM, or mail to relay addresses silently fails. |
| 11 | **Verify the identity token server-side.** Never trust a client-supplied identity assertion. |
| 14, 15 | **Add-a-password** for federated users, so no user is stranded on a platform lacking their identity provider. *(Void on Android under Google-only sign-in — revives here the moment two providers exist.)* |
| 44 | The privacy-policy link on the create-account screen opens the in-app screen, not a browser, so a half-completed sign-up is not lost. |

### 3.2 Deletion and revocation

| Original | Rule |
| --- | --- |
| 20 | **Token revocation on account deletion is mandatory on Apple** (5.1.1(v)), where it is merely hygiene on Play. `legal-accounts.md` rule 69 makes the equivalent Google revocation a `[SHOULD]`; on iOS the Apple equivalent is a `[BLOCKER]`. Build it once, on the server, and both are satisfied. |
| 26 | Apple explicitly **rejects a web-only deletion route**. The in-app path is mandatory; the web page is additional. |
| §6.10 | The web deletion page must re-authenticate with **every** provider the account system accepts — Sign in with Apple JS included. With Google-only this simplified to one integration; it grows back. |

### 3.3 Privacy declarations and the equal-protection sentence

| Original | Rule |
| --- | --- |
| 33 | **The App Privacy questionnaire**: Contact Info → Email Address, Identifiers → User ID, User Content → Photos and Other User Content, all *Data Linked to You*, purpose App Functionality. Third-party SDK collection is declared as the developer's own, so GoogleSignIn's collection lands on this app's label. **Leave "Data Used to Track You" empty and ship no ATT prompt** — nothing here meets Apple's tracking definition, and a prompt with nothing to track mismatches the label and invites a review question. *(Re-derive against the local-only architecture: most User Content rows should disappear the way they did on Play.)* |
| 70 | **Guideline 5.1.1(i) requires an affirmative confirmation** that third parties receiving user data "will provide the same or equal protection of user data as stated in the app's privacy policy". This must be an affirmative sentence in the app's own voice, naming Anthropic and Alibaba/Qwen, in the recipients section of the policy, mirrored in one line on the AI screen. **"They have their own privacy policies" is a deflection, not the confirmation the guideline demands.** |
| 37a | **This is what makes the AI provider terms a hard blocker on iOS.** On Play, the pessimistic route is available — declare the AI leg as *shared with third parties* and ship (`legal-accounts.md` rule 102). **That route does not rescue Apple**: the 5.1.1(i) sentence remains unsignable without the terms, and a false confirmation is independently removable under 5.1.2(i). So on a shared codebase, obtaining the terms is effectively mandatory. |
| 46 | **Privacy manifests** for the app target and for the GoogleSignIn SDK. |
| 36 | **The AI-consent withdrawal toggle is `[BLOCKER · Apple]`.** On Play it has no counterpart — Play's PD&C governs *obtaining* consent only, and Play's sole interest is that a described control actually exist and work. On Android the toggle's only compelling source is GDPR Art. 7(3); on iOS it is Apple's rule as well. |

### 3.4 Guest mode, commercial posture and review

| Original | Rule |
| --- | --- |
| §2.2 | **Apple requires guest mode where Play merely permits it** (5.1.1(v)): an app may not require an account for features not tied to one. This app's core loop works fully offline, which is what makes it clean — and the same written "fully offline-capable" admission is what defeats a legitimate-interest argument for the AI transfer (`legal-accounts.md` rule 84). One sentence doing double duty against two shortcuts. |
| 54 | **Individual vs. Organization enrolment must be decided before enrolling** — changing later is an entity migration, not a setting. |
| §2.11, 84 | **Apple publishes the legal seller name.** France's LCEN art. 6 III-2 anonymity option for a non-professional natural person — which preserves the developer's privacy on Play, where only a developer name is published — **does not survive iOS**. |
| 89 | **The third-party licence attribution surface binds identically on iOS** via Guideline 5.2.1 ("only include content that you created or that you have a licence to use"). `legal-accounts.md` rule 103 records that the Android row was removed on the product owner's instruction over both specialists' objection; that decision does not travel here automatically. |
| 40 / 65 | **The demo-account problem is *harder* on Apple than on Play**: a human reviewer consumes the credential every submission, and Google-only sign-in gives no non-federated path. See `legal-accounts.md` rules 65–68 for the Play resolution; Apple's is not the same and needs its own answer. |

---

## 4. What changes if iOS is revived

A short, honest list of what must be redone rather than read:

1. **Re-derive the App Privacy label from scratch** against the local-only
   architecture. The carried rule 33 above describes a *sync* app. Most of its
   User Content rows should disappear, exactly as they did on Play.
2. **Re-open Guideline 4.8** and decide between adding Sign in with Apple and
   dropping federated login entirely.
3. **Re-verify every citation.** Apple's guidelines are revised several times a
   year and none of these were checked after 2026-08-13.
4. **Re-run the two-specialist review** on the iOS shape specifically. This file
   is the Apple half of a review conducted for a different product; it is a
   starting position, not a conclusion.
5. **Decide the licences surface**, which on iOS is an acknowledgements screen
   and is bound by 5.2.1 independently of whatever Android does.
