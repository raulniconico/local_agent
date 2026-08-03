# Crawling French roasters' on-sale coffee beans — legal & safety spec

A binding design specification for any component of this repo that automatically
collects **publicly listed coffee-bean product data** (name, origin, varietal,
process, roast date, price, weight, stock, tasting notes) from the official
e-commerce sites of large French roasters — Tanat, Terres de Café, Datura,
Belleville Brûlerie, Lomi, Coutume, L'Arbre à Café.

Produced from a three-way expert review (French/EU hard law · crawler
engineering · commercial risk & governance) conducted 2026-08-03. Site
observations in §2 were measured live on that date and **must be re-verified
before any run**.

Not legal advice. Consult a French *avocat* in IP/IT before any public or
monetised launch.

- [1. Project background](#1-project-background)
- [2. Development details](#2-development-details)
- [3. API — the binding rules](#3-api--the-binding-rules)
- [4. Addendum — X (formerly Twitter) cohort crawling](#4-addendum--x-formerly-twitter-cohort-crawling)

---

## 1. Project background

### What this covers

The coffee-can database (`coffee/`) stores bean profiles that today are typed in
by hand. A crawler that reads roasters' public catalogues could pre-fill them,
and could answer a question no single roaster can — *"who has an Ethiopian
natural in stock, roasted this week?"*. That is the legitimate, defensible core
of the idea.

The risk does not live in the HTTP requests. **It lives in what is stored and
what is published.** The three reviews converged on this from different
directions, and the whole spec follows from it.

### The use-case gradient — decide once, in writing

| Use case | Verdict | Why |
| --- | --- | --- |
| **(a)** Private, single-user database feeding coffee-can | **GO** | No republication, no commercial exploitation, no plausible damages, GDPR household exemption plausibly applies |
| **(b)** Publishing / open-sourcing the *harvested corpus* | **NO** | Converts "guy with a script" into "guy who built a competing database" — the frame that makes sui generis extraction and *parasitisme* claims live. Publish the scraper, not the scrape |
| **(c)** Public price-comparison site with ads / affiliate | **PERMISSION REQUIRED** | Commercial exploitation *and* a regulated activity under art. L.111-7 code conso. Only after outreach (§1.3) and with the D.111-16 disclosure rubric shipped |
| **(d)** Training / fine-tuning a model on the corpus | **NO** | Maximally unauthorised use, the exact use European rightsholders are reserving against, and irrelevant to a brew log |

Scope creep is the actual risk vector — the private tool that quietly becomes a
public site is how people get surprised. **Record the chosen use case in the
repo and re-open this spec before changing it.**

### The single highest-value action: ask first

These are small, founder-led businesses whose growth problem is *discovery*.
Their revealed preference is to be found; their incentive to sue is near zero
and their incentive to cooperate is real. A "yes" produces strictly better data
than scraping — a clean structured feed that does not break when they retheme,
prices you are *allowed* to display, and a named human to email.

Send outreach **before** writing the crawler. Realistic outcome from 8–10
roasters: 2–4 replies, 1–3 yes. The "no"s are equally valuable — a documented
refusal is the difference between a good-faith project and a reckless one, and
silence after a documented good-faith attempt is the best posture available for
the domains you do end up crawling.

Ask specifically for a **Google Merchant / Shopping product feed** — any roaster
running Google Shopping already maintains one, structured and *already licensed
for third-party aggregation*, at zero marginal cost to them. Affiliate networks
(Awin, Effiliation, Kwanko, Shopify Collabs) are the fallback framing; no public
affiliate programme was found for Terres de Café, Lomi or Belleville, so treat
this as a direct-email conversation.

<details>
<summary>Outreach template (French)</summary>

> **Objet : Référencement de vos cafés dans une app de suivi de dégustation**
>
> Bonjour,
>
> Je développe une petite application de suivi de dégustation de café de
> spécialité (carnet de brassage, historique des cafés goûtés). Les utilisateurs
> saisissent aujourd'hui les informations à la main : origine, variété, process,
> date de torréfaction.
>
> J'aimerais pouvoir proposer vos cafés directement dans l'application, avec un
> lien vers votre boutique pour l'achat — sans jamais vendre ni afficher de prix
> hors contexte.
>
> Disposez-vous d'un flux produit (le flux Google Merchant / Shopping, un export
> CSV ou XML, ou un accès API) que je pourrais consulter périodiquement ? À
> défaut, je m'adapte à ce qui vous convient — y compris un simple export
> manuel.
>
> Je suis évidemment ouvert à un cadre d'affiliation si cela vous intéresse, et
> je m'engage à citer systématiquement la source et à renvoyer le trafic vers
> votre site.
>
> Bien cordialement,
> [Nom] — [email] — [lien du projet]

</details>

### What the enforcement pipeline actually looks like

Not court. In order: **nothing happens** (months) → **a block** (403s, zero cost
to you) → **an email from a human** (this is a gift, not an attack) → **mise en
demeure** from an avocat (€800–2 500 for you to answer *even when you are
entirely in the right*) → *référé* (€10k+ each side; a ten-person roaster will
essentially never go here over product listings).

The cost asymmetry runs against you. Ryanair lost against Opodo on appeal in
Paris in 2012 — excellent precedent, and it still cost Opodo, a company with a
legal department, several years. **A correct legal position you cannot afford to
defend is not an asset.** This is why §1.3 (ask) outranks everything in §3.

### Reputational risk outranks legal risk

French specialty coffee is a few hundred people who all know each other.
*"Ce mec qui a fait tomber notre Shopify"* travels faster and hurts longer than
any judgment. Your name will be attached via GitHub. That reputation, not €5k of
damages you will never be ordered to pay, is the asset actually at risk.

---

## 2. Development details

### 2.1 Legal analysis — heading by heading

Risk levels are for **this** use case, per use-case column (a) private /
(b) published / (c) commercial.

#### Droit d'auteur — **low for facts, high for prose and photos** *(a: low · b: low–high · c: high)*

Art. L.112-1 CPI protects *œuvres de l'esprit*; the threshold is originality —
the author's own intellectual creation (*Infopaq* C-5/08, *Painer* C-145/10,
*Cofemel* C-683/17). "Sweat of the brow" is not enough (*Football Dataco*
C-604/10).

- **Price, weight, roast date, origin, varietal, process, stock** — raw facts,
  no protection. "Éthiopie / Guji / lavé / 250 g / 18,50 €" cannot be original.
- **Tasting notes** — genuinely borderline. A bare descriptor list ("fruits
  rouges, cacao, agrumes") is standardised vocabulary and likely unprotected; a
  paragraph of evocative prose is likely protected.
- **Photos** — split. A product shot on a white cyclorama involves no free
  creative choices; styled/lifestyle photography is protected (*Painer*).

The *courte citation* exception (L.122-5 3° a) is narrow and French courts
consistently refuse it for images. Do not rely on it.

→ **Mitigation:** store facts + your own normalised tags. Never persist the
description paragraph. Never re-host images. This one rule collapses copyright
risk to near zero across all three use cases.

#### Sui generis database right — **low–medium, lower than intuition suggests** *(a: low · b: low–med · c: med)*

L.341-1 CPI / Directive 96/9 art. 7 protect substantial investment in
**obtaining, verifying or presenting** contents. *British Horseracing Board v
William Hill* (C-203/02) and *Fixtures Marketing* hold that investment in
**creating** data does not count. A roaster's catalogue is data the roaster
*creates* — it sets its own prices, names its own products, writes its own
notes. That is the *BHB* fact pattern almost exactly.

Contrast **LeBonCoin v Entreparticuliers** (CA Paris, 2 févr. 2021, n° 17/17688;
€50k economic + €20k reputational): LeBonCoin *obtains* third-party listings and
invests in moderation and fraud control, with ~50 dedicated staff. An artisan
roaster with 40 SKUs has no comparable obtaining or verification investment.
Residual exposure sits in **"présentation"**, which L.341-1 does list and which
French courts have read generously.

Art. 7(5) / **L.342-2** (repeated systematic extraction of insubstantial parts)
is the classic recurring-crawler trap, but *BHB* limits it to acts that
cumulatively reconstitute a substantial part or seriously prejudice the
investment (*Directmedia* C-304/07, *Apis-Hristovich* C-545/07). Note that CA
Paris in *LeBonCoin* shifted to L.342-1 and held the extractor's purpose
irrelevant.

***Innoweb v Wegener*** (C-202/12) — a dedicated meta-search engine as a
"parasitic competing product" — is directly on point for a price comparator,
**but presupposes a protected database.** If the roaster fails the *BHB* test,
*Innoweb* never engages.

→ **Mitigation:** low frequency, keep no per-roaster historical full-catalogue
archive that could reconstitute their base, always aggregate *across* roasters
so the output is never a substitute for any single source, always link back.

#### TDM exceptions — **medium, and narrower than commonly assumed** *(all cases)*

Art. 3 DSM (scientific research) is unavailable — reserved to research and
heritage institutions. Art. 4 DSM, transposed at **L.122-5-3 III** (copyright)
and **L.342-3 5°** (sui generis) CPI, permits TDM for any purpose including
commercial, subject to (i) **lawful access** and (ii) **no machine-readable
reservation** (recital 18 expressly contemplates website terms and conditions).

Two things to be blunt about:

1. **Art. 4 plausibly covers crawl-and-store; it does not cover publication.**
   It authorises reproductions *for the purposes of* TDM, with retention only
   "for as long as necessary" (art. 4(2)). **There is no TDM exception for
   communication to the public.** It protects the pipeline, not the product.
2. **The opt-out standard is unsettled.** *Kneschke v LAION* (OLG Hamburg,
   5 U 104/24, 10 déc. 2025) held a natural-language ToS reservation was not
   machine-readable for 2021 usage. That is German, time-bound, and in tension
   with recital 18. **Do not assume a prose "no scraping" clause is legally
   inert in France.**

Further: the exception is a copyright/sui generis defence **only**. It does
nothing about *parasitisme*, contract claims, or a DGCCRF consumer-information
complaint — and a fully compliant crawler can still receive a mise en demeure
that costs €2 000 to answer.

→ **Mitigation:** honour `robots.txt`, `ai.txt`, `/.well-known/tdmrep.json` and
`tdm-reservation` headers, **and** treat any CGU/CGV clause prohibiting
reproduction or automated access as an effective reservation.

#### Contract / CGU-CGV — **medium, and the sting in the tail** *(a: low · b: med · c: med–high)*

***Ryanair v PR Aviation*** (C-30/14) inverts the intuition: where a database is
protected by *neither* copyright *nor* sui generis right, the Directive's
mandatory lawful-user freedoms do not apply — so the owner is **free to impose
fully enforceable contractual restrictions**. **The weaker the roaster's IP
position, the stronger its contract position. You do not get to win both
arguments.**

Under art. 1119 code civil, general conditions bind only if brought to the other
party's knowledge and accepted. A crawler that never registers, never clicks
accept and never authenticates has a strong no-contract-formed argument (classic
browsewrap weakness). Clickwrap behind an account binds — one more reason never
to create accounts.

Terres de Café's CGV clause is IP-framed (*"Tous les éléments du site … restent
la propriété intellectuelle et exclusive"*, prohibiting reproduction/
redistribution "même partielle"), not access-framed: it restricts exactly what
the field-level discipline avoids, and does not prohibit automated reading.

#### GDPR — **low if disciplined, medium if naive** *(a: low · b/c: med)*

Personal data creeps in from four directions: **review author names**, **roaster
staff names**, **named producers/farmers at origin** (real identified natural
persons, routinely printed on specialty bags and routinely overlooked), and the
roaster's own server logs of your crawler.

Private use plausibly falls under the household exemption (art. 2(2)(c)), but
*Lindqvist* (C-101/01) and *Ryneš* (C-212/13) make clear **publication destroys
it**. Published or commercial, art. 6(1)(f) legitimate interest is the only
realistic basis. The CNIL's 2025 *moissonnage* focus states scraping *"n'est pas
interdit en lui-même mais doit faire l'objet d'une analyse au cas par cas"* and
requires pre-defined collection criteria, filtering, immediate deletion of
irrelevant data, and — critically — **excluding sites that clearly oppose
scraping**, absent which the processing falls outside data subjects' reasonable
expectations. Art. 14 applies (indirect collection); the disproportionate-effort
carve-out at 14(5)(b) is read narrowly and still **requires publishing the
information**.

→ **Mitigation:** collect zero natural persons **by construction**, not by
filtering afterwards. That reduces this heading to near zero.

#### Criminal — **low as designed, high if evasion is added** *(all cases)*

Code pénal art. 323-1 (*accès/maintien frauduleux dans un STAD* — 3 ans /
100 000 €), 323-2 (*entrave au fonctionnement* — 5 ans / 150 000 €), 323-3
(*extraction frauduleuse* — 5 ans / 150 000 €); attempt punishable (323-7).

***Bluetouff*** (Cass. crim., 20 mai 2015, n° 14-81.336) is controlling and its
holding is precise: acquitted of *accès* frauduleux, **convicted of *maintien*
frauduleux** because he was **aware the resource was protected**, even though
the files were reachable via Google. The operative rule is **awareness of a
protection**.

Crawling an open shop with no auth is not a criminal act. What crosses the line
is **evidence of deliberate evasion**: solving or bypassing a CAPTCHA, rotating
IPs or proxies after a block, spoofing User-Agent or TLS fingerprint to defeat
bot detection, ignoring a 403 and continuing, or **disabling TLS certificate
verification**. Each converts a civil dispute into *Bluetouff* facts. On 323-2,
accidental degradation lacks intent — but **continuing to hammer a host after
429s or after a complaint supplies it.**

#### Concurrence déloyale / parasitisme — **the most likely head of claim** *(a: low · b: low–med · c: med–high)*

Art. 1240 code civil. *Parasitisme* — *se placer dans le sillage d'autrui afin
de tirer profit, sans rien dépenser, de ses efforts et de son savoir-faire* —
requires **neither an IP right nor confusion**, which makes it the catch-all
that survives when copyright and sui generis both fail.

Two real defences: the claimant must prove the specific investments
appropriated (Cass. com., 16 févr. 2022, n° 20-13.542), and the *cumul* rule
requires **faits distincts** — parasitisme cannot simply re-protect what failed
the IP test on identical facts. A comparator that aggregates across many
roasters, adds its own normalisation and **drives traffic back** is materially
different from a clone that substitutes for the source. Monetisation is what
pushes this to medium–high.

#### Price-display law — **N/A private, medium–high commercial** *(a: n/a · b: med · c: med–high)*

Art. **L.111-7** code conso and **arts. D.111-16 et seq.** (décret n° 2016-505,
in force 1 juillet 2016, largely superseding the arrêté du 11 mars 2015) require
a comparison site to carry a **dedicated rubric directly accessible from every
page** disclosing: ranking criteria and their definitions; contractual or
capital links with listed merchants; existence of paid referencing and its
effect on ranking; price components and extra costs; whether the comparison is
exhaustive; and the **frequency and method of updating**.

More dangerous, and independent of that: **a stale price is a *pratique
commerciale trompeuse*** under L.121-2 code conso, and liability attaches to
**the comparator, not the roaster**. The complaint that reaches the roaster
("your site says €14, they charge €17") is *the* realistic trigger for the mise
en demeure in §1.4. **Price drift is the single most likely regulatory trigger
in this project.**

These duties bind *professionnels*; a purely private non-published database is
outside their scope, an unmonetised public one is arguable, and any monetisation
brings them squarely into play.

#### Risk summary

| Heading | (a) Private | (b) Published | (c) Commercial |
| --- | --- | --- | --- |
| Droit d'auteur | Low | Low (facts) / High (prose + photos) | High |
| Sui generis | Low | Low–Medium | Medium |
| TDM / art. 4 | Low | Medium (no publication cover) | Medium |
| Contract / CGU | Low | Medium | Medium–High |
| GDPR | Low (household) | Medium | Medium |
| Criminal | Low | Low | Low — **unless evasion** |
| Parasitisme | Low | Low–Medium | **Medium–High** |
| Price display | N/A | Medium | **Medium–High** |

#### Where the law is genuinely unsettled

1. Whether a natural-language CGU clause is a valid art. 4(3) machine-readable
   reservation in France — *Kneschke* says no for 2021, recital 18 suggests yes,
   no French ruling exists.
2. Whether "building a product database" is TDM within art. 2(2) DSM —
   plausible, untested.
3. Whether an artisan roaster's catalogue clears the *BHB* obtaining-vs-creating
   line via "présentation" investment — French courts have been notably generous
   to database producers.

The rules in §3 are drafted so the project survives the adverse answer on all
three.

### 2.2 Measured site survey (2026-08-03 — re-verify before use)

**Two corrections to the target list before any code is written.**

- **`tanat.fr` is not Tanat.** It serves a certificate for
  `cluster114.hosting.ovh.net` (hostname mismatch — a correct client must fail
  closed), `robots.txt` 404s, and the homepage is a 1 830-byte parked page. The
  real roaster is **`tanat.coffee`**. Crawling `tanat.fr` would direct automated
  traffic at an unrelated third party under a mistaken identity — the worst
  possible fact pattern in a complaint. **Never disable certificate verification
  to "make it work"; a cert error means you have the wrong host.**
- **Cafés Lugat has no online catalog.** `cafeslugat.com` 301-redirects *every*
  path to `www.cafes-lugat.com` (path-destroying catch-all, so `robots.txt`
  "succeeds" with 200 `text/html`); the sitemap index has one child, `lastmod`
  2024-08-01, and there is no WooCommerce. **Out of scope.**

| Site | Platform | First-party structured endpoint | Sitemap | Edge |
| --- | --- | --- | --- | --- |
| daturacoffee.com | Shopify | **`/products.json`** (24) | `sitemap_products_1.xml`, per-URL `lastmod` | Cloudflare |
| cafesbelleville.com | Shopify | **`/products.json`** (250+, paginates) | yes | Cloudflare |
| coutumecafe.com | Shopify | **`/products.json`** (107) | yes | Cloudflare |
| larbreacafe.com | Shopify | **`/products.json`** (137) | `/sitemap.xml` 301→www | Cloudflare |
| tanat.coffee | WooCommerce | **`/wp-json/wc/store/v1/products`** | Yoast `product-sitemap.xml` | Cloudflare |
| terresdecafe.com | PrestaShop | none | **none** (all sitemap paths 404) | none — bare Apache/OVH |
| lomi.cafe | Next.js/Vercel | none found | `/sitemap.xml` | Vercel |
| cafes-lugat.com | WordPress, no WC | n/a | stale | **out of scope** |

**The headline engineering finding: 6 of 8 sites expose a first-party structured
endpoint the site itself publishes. ~520 products retrievable in ~8–12 HTTP
requests per run, versus ~520 product pages plus pagination for identical facts
— a 40–60× traffic multiplier avoided.** For most of this project HTML scraping
is not merely riskier, it is worse engineering.

Shopify `products.json` yields `title`, `handle` (→ canonical URL),
`updated_at`, `vendor`, `product_type`, `tags`, and per-variant `price`,
`available`, `grams`, `sku`, `compare_at_price`. Origin/varietal/process/roast
date are not first-class — they live in `body_html` (~1.2 KB of marketing prose,
i.e. exactly the copyrightable part you must not keep) or variant option names,
and must be parsed out.

**robots.txt content.** terresdecafe (PrestaShop, 337 lines): no `Crawl-delay`,
**no `Sitemap:`**, and Disallows covering `/*?search_query=`, `/*?order=`,
`/*?tag=`, `/*?n=`, `/*?back=` plus cart/auth/account/order/search controllers —
i.e. every faceted URL a naive crawler generates. tanat.coffee (Yoast, 20
lines): Disallows `*?s=`, `*?orderby=`, `*/page/*`, and **seven filter facets
including `?filter_country=` and `?filter_process=`** — precisely the facets a
coffee crawler is tempted to enumerate, explicitly forbidden. Use the Store API.
Shopify sites: standard template. `daturacoffee.com` serves the newer agent-era
variant with a human-authored preamble (*"Checkouts are for humans. Do NOT
complete checkout, payment, or order placement automatically"*), publishes
`/agents.md`, and explicitly `Allow: /` for catalog reading.

**No AI/TDM user-agent blocks anywhere** — zero matches for
`GPTBot|CCBot|ClaudeBot|Google-Extended|PerplexityBot|Bytespider` across all
five e-commerce hosts. **Absence is not consent**, and a reservation may still
be asserted in the CGU.

**Anti-bot posture:** five of six sit behind Cloudflare in default posture; all
requests above succeeded with a plain non-browser UA, no challenge.
**terresdecafe has no CDN at all** — it absorbs load directly on origin, and its
404 page is 96 KB, so URL guessing is expensive for *them*. It gets the most
conservative settings of the set. Rate limits were deliberately **not** probed:
finding the threshold requires abusing the host and the answer is only useful
for evasion.

**Structured markup.** terresdecafe product pages carry **no JSON-LD** but do
carry schema.org **microdata** (`Product`, `Offer`, `BreadcrumbList`). `extruct`
must therefore be configured with
`syntaxes=['json-ld','microdata','opengraph']`, not JSON-LD alone — this is the
common PrestaShop failure mode.

Two parsing traps generalise: an HTML body returned for `robots.txt` parses to
*zero rules* in every library, silently meaning "allow everything"; and a
catch-all redirect can make a nonexistent `robots.txt` look like a 200.

### 2.3 Recommended stack

Scrapy is overkill for ~12 requests/day and its default concurrency is a footgun
here. The httpx path, consistent with this repo's Python 3.12 / uv setup:

```
uv add httpx[http2] protego selectolax extruct hishel tenacity pydantic
```

- **`httpx`** — one client per host, `limits=Limits(max_connections=1,
  max_keepalive_connections=1)`, `timeout=Timeout(connect=10, read=30,
  write=10, pool=30)`, `follow_redirects=True`, `max_redirects=3`, HTTP/2 on.
  **Leave `verify=True`** (the tanat.fr lesson).
- **`protego`** — robots parsing. *Not* stdlib `urllib.robotparser`, which
  mishandles `Allow` precedence, `*`/`$` wildcards and `Crawl-delay` in ways
  that matter for the PrestaShop `Disallow: /*?order=` patterns.
- **`hishel`** — transparent ETag / Last-Modified conditional caching over
  httpx, SQLite-backed.
- **`tenacity`** — `wait_exponential_jitter(initial=5, max=45)`,
  `stop_after_attempt(3)`, retry only on 429/503/timeouts, **never on 403**.
- **`extruct`** — with microdata enabled (mandatory for terresdecafe).
- **`selectolax`** (`LexborHTMLParser`) — only for the two HTML-only sites.
- **`pydantic`** — one `BeanObservation` model as the *single* write path into
  SQLite, with the personal-data drop-list and the tasting-note cap enforced in
  its validators, so minimisation is structural rather than remembered.

Crawl state (per-URL etag / last_modified / content_hash / last_fetched_at;
per-host robots hash + fetched_at; breaker state) belongs in the **same SQLite
file** as the coffee log under a `crawl_*` table namespace, consistent with this
repo's single-SQLite pattern.

If Scrapy is used anyway: `ROBOTSTXT_OBEY=True`,
`ROBOTSTXT_PARSER='scrapy.robotstxt.ProtegoRobotParser'`,
`CONCURRENT_REQUESTS_PER_DOMAIN=1`, `DOWNLOAD_DELAY=3.0`,
`RANDOMIZE_DOWNLOAD_DELAY=True`, `AUTOTHROTTLE_ENABLED=True`,
`AUTOTHROTTLE_START_DELAY=3.0`, `AUTOTHROTTLE_MAX_DELAY=60`,
`AUTOTHROTTLE_TARGET_CONCURRENCY=0.5`, `RETRY_TIMES=2`,
`RETRY_HTTP_CODES=[429,503]`, `HTTPCACHE_ENABLED=True`,
`HTTPCACHE_POLICY='...RFC2616Policy'`, `CLOSESPIDER_PAGECOUNT=250`.

### 2.4 Points of disagreement, resolved

Three positions were stress-tested in review and survive only in qualified form.

**"Art. 4 TDM makes this fine."** It does not, for three reasons. It requires
**lawful access**, which is arguably lost the moment collection involves
circumventing a block. Its opt-out is **not standardised**, and a French court
reading *"toute extraction automatisée est interdite"* in the CGV is not
obviously going to hold robots.txt silence overrides it. And it is a
copyright/sui generis defence only — it does nothing about parasitisme,
contract, or consumer law. **Treat art. 4 as a fallback, never as the plan.**

**"A reachable `/products.json` is permission."** It is not. Shopify exposes
that endpoint by *platform default*; the merchant almost certainly does not know
it exists. Treating a platform default as consent is the reasoning Meta lost
with in *Bright Data* — and note that was a **US contract-law** ruling about
logged-off scraping which does not port to French parasitisme or sui generis
analysis, so it must not be cited as a European green light. Use `/products.json`
because it is **1/50th the load** and less likely to cause harm, not because it
implies a licence.

**"Polite crawling solves it."** Politeness mitigates *harm*; it is not a source
of *permission*. It reduces server load only, and does nothing about the
commercial harms below. And if a plan's robustness depends on not being noticed,
it has already conceded the ethics.

### 2.5 Commercial harm — the design levers

Aggregation **harms** when it (i) *commoditizes* — reducing a €22 Gesha and a
€22 supermarket bag to one sortable price column attacks the exact
differentiation these businesses live on; (ii) *disintermediates* — you become
the destination and they become a fulfilment backend, losing the newsletter
signup and subscription conversion that is their real economics; (iii)
*misinforms* — a stale price generates a complaint at their counter; (iv)
*reveals* — a public price-history graph hands competitors a repricing tool and
trains customers to wait for sales.

It **helps** when it surfaces "who has an Ethiopian natural in stock, roasted
this week" — a query no single roaster can answer.

Four design choices keep it in "helps" territory, and they are cheap:

1. **Default sort is never price.** Sort by roast date, origin, freshness. Price
   shown, not ranked.
2. **No price-history charts.** This single line item removes most of the
   commercial-harm argument.
3. **Availability + roast date as the headline value**, price as secondary.
4. **Suppress rather than show stale** — expire beyond a defined TTL.

---

## 3. API — the binding rules

Normative. Every rule below is a design constraint on any crawler in this repo.

### 3.1 Scope & consent

1. **Decide and record the use case** — (a)/(b)/(c)/(d) from §1.2 — in a
   committed one-paragraph purpose statement before the first request. If it
   cannot be stated without hedging, do not build it.
2. **Outreach first.** Emails to every target domain, 14-day wait, replies
   logged, *before* the crawler runs.
3. **Per-domain allowlist file**, in the repo, recording for each roaster:
   contact email, date contacted, response (yes / no / silence), feed URL if
   any, robots.txt check date + hash, and the CGU/CGV scraping clause **quoted
   verbatim** with a decision and date. **No site is crawled until it is on the
   list.** Explicit "no" and CGU-prohibition domains are hard-excluded **in
   code**, not by convention.
4. **Never authenticate, register, accept CGU, or pass a login wall.** This
   preserves the art. 1119 no-contract-formed defence and keeps *Ryanair v PR
   Aviation* out of play.
5. **Re-review this spec before any monetisation.** Affiliate links, ads or a
   paid tier move parasitisme and consumer-law exposure from low/medium to
   medium–high.

### 3.2 Acquisition — strictly ordered, never skip a tier

6. **Tier 1: official API / affiliate / merchant feed.** Always preferred.
7. **Tier 2: first-party structured endpoint** — Shopify
   `/products.json?limit=250&page=N`, WooCommerce
   `/wp-json/wc/store/v1/products?per_page=100&page=N`. Covers 6 of 8 sites.
8. **Tier 3: sitemap-guided fetch of product pages** — only where no tier-2
   endpoint exists (terresdecafe, lomi.cafe), only product-pattern URLs, parsed
   with `extruct` including microdata.
9. **Tier 4: bounded category pagination** — terresdecafe only (no sitemap);
   `rel=next` / numbered pagination only; hard cap **40 listing pages**.
10. **Read `/agents.md` where published** (daturacoffee.com) and log that you
    did.

### 3.3 robots.txt & opt-out

11. **Obey robots.txt literally, per-path**, parsed with `protego`. For
    terresdecafe this specifically means no `?search_query=`, `?order=`,
    `?tag=`, `?n=`, `?back=`, and no auth/cart/account controllers; for
    tanat.coffee, none of the seven `?filter_*=` facets.
12. **Fail closed.** On 4xx/5xx, timeout, TLS error, or a body whose
    `Content-Type` is not `text/plain`, crawl **nothing** on that host this run.
    Never fall back to "allow all".
13. **Treat a robots.txt change as a stop signal.** Store a SHA-256; on change,
    halt that host, alert, require human review. Editing robots.txt is a
    roaster's most likely first reaction — you must notice within one run.
14. **Honour every opt-out channel** — `robots.txt`, `ai.txt`,
    `/.well-known/tdmrep.json`, `tdm-reservation` headers — **and** treat a
    prose anti-scraping or anti-reproduction clause in CGU/CGV as an effective
    reservation, notwithstanding *Kneschke v LAION*. The point is unsettled; do
    not be the test case.
15. Absence of a `Crawl-delay` means use the §3.4 defaults, **not** "go fast".

### 3.4 Rate limiting & scheduling

| Setting | Value |
| --- | --- |
| Concurrency per host | **1** — never parallel to one origin |
| Delay, same host | **3.0 s** base ± **1.5 s** jitter (~0.25 req/s) |
| terresdecafe.com (no CDN, 96 KB 404s) | **5.0 s** base |
| Cross-host parallelism | max **2** hosts |
| Connect / read timeout | 10 s / 30 s |
| Retries per URL | **2**, then abandon for the run |
| Backoff on 429/503 | **5 s → 15 s → 45 s**, full jitter |
| `Retry-After` | always obeyed; > 300 s ⇒ abandon the host for the run |
| Global cap per run | **250 requests total, 60 per host** — hard counter that aborts |
| Schedule | **once daily, 03:30–05:00 Europe/Paris**, randomised start minute |
| Repeat failure | 3 consecutive failed runs on a host ⇒ auto-disable, manual re-enable |

16. These caps exist to contain **bugs**, not to be approached — a real tier-2
    run is ~12 requests. A crawl-loop bug is the realistic failure mode here,
    not a policy disagreement.

### 3.5 Identification

17. **Truthful, descriptive User-Agent with a resolvable contact:**

    ```
    User-Agent: CoffeeBeanIndexBot/0.1 (+https://example.org/bot; contact@example.org)
    From: contact@example.org
    Accept-Language: fr-FR,fr;q=0.9
    ```

    The `+URL` must resolve to a real page stating what is collected, how often,
    from which IPs, and a one-click opt-out address a human actually reads.
18. **Never spoof a browser User-Agent.** It is the single most damaging
    technical decision available: an affirmative, logged, per-request
    misrepresentation that destroys the "public data, politely collected"
    posture, makes you un-contactable so escalation is the roaster's only
    remedy, defeats any claim you respected robots.txt (UA-specific rules cannot
    apply to a UA you lied about), and supplies evidence of intent to
    circumvent. A truthful UA is also your best *defence* — it lets a sysadmin
    identify your traffic as benign in five seconds.

### 3.6 Conditional requests & caching

19. Persist `ETag` / `Last-Modified` per URL; send `If-None-Match` /
    `If-Modified-Since` on every request. A 304 costs both sides ~200 bytes.
20. Store a SHA-256 of the normalised body; identical hash ⇒ skip parsing, write
    only `last_seen_at`.
21. Use Shopify's per-product `updated_at` and the sitemap's per-URL `lastmod`
    as the change oracle — fetch a product page only when
    `lastmod > last_fetched_at`.
22. Disk response cache with a **6 h floor** so re-runs and debugging never hit
    origin. `Accept-Encoding: gzip, br`.

**Target steady state: ~8 conditional requests per day returning 304 or a few KB
of JSON — less than one human loading one product page with images.** That
number belongs in the spec and in the `+URL` page.

### 3.7 Hard boundaries

23. **Never request:** `/cart`, `/checkout*`, `/checkouts/`, `/orders`,
    `/account*`, `/admin`, `/wp-admin/`, `/wp-login.php`, `/services`, `/sf_*`,
    `/webservice/`, `/config/`, `/vendor/`, `*?s=`, `*?search_query=`,
    `*?orderby=`, `*?order=`, `*?filter_*=`, `*?tax_product_cat=`, `*/page/*`.
    Implement as a **deny-regex applied after robots evaluation** — belt and
    braces, so a robots parsing bug cannot expose them.
24. **Never** submit a form, POST, send cookies you were not given, add to a
    cart, or complete a checkout.
25. **Never** solve or outsource a CAPTCHA; rotate IPs, proxies or residential
    exits; alter TLS/JA3 fingerprints; retry a 403 with different headers; use
    `undetected-chromedriver`, `curl_cffi` or FlareSolverr.
26. **Never disable TLS certificate verification.** This blocks `tanat.fr`
    permanently and correctly.
27. **When blocked (403, challenge page, sustained 429): stop, log, alert, leave
    the host disabled until a human decides.** Do not route around it. A block
    is a communication; the correct reply is an email, not a workaround. **This
    is the point of no return** — routing around a block converts "we didn't
    want that traffic" into "they knew and evaded" (*Bluetouff*; C. pén. 323-1).
28. If a site's configuration means plain HTTP cannot reach it, **that is the
    answer, not the problem.**

### 3.8 Data minimisation

29. **Store facts, not expression.** Persist only: `roaster`, `name`, `origin`,
    `varietal`, `process`, `roast_date`, `price_cents`, `currency`,
    `weight_grams`, `in_stock`, `source_url` (canonical), `fetched_at`,
    `http_status`, `etag`.
30. **Never persist `body_html` in full** — Shopify hands you ~1.2 KB of
    marketing prose per product; that is the copyrightable part and you do not
    need it.
31. **Never download, re-host, cache or thumbnail product images.** Record the
    URL only. **If a photo is shown in-app at all, hotlink it live** — fetch
    the image bytes only at the moment of display, hold the result only as an
    in-memory pixmap, and never write it to disk. That keeps every product
    photo a live pointer to the roaster's own CDN, the same as a browser
    loading an `<img>` src, rather than a copy this project ever holds — see
    `gui/whats_new_dialog.py`'s preview panel, which fetches on row selection
    only (one request at a time, never all rows at once) and aborts the
    in-flight request the moment the selection moves on.
32. **Tasting notes**: prefer normalising into your own controlled vocabulary
    and storing nothing verbatim. If verbatim is unavoidable, cap at **200
    characters**, store as an attributed excerpt, and attribute as a quote.
33. **Retain no per-roaster full-catalogue historical archive** that could
    reconstitute their base — only the cross-roaster aggregate needed for
    comparison (L.342-1/L.342-2 CPI; *BHB*).
34. **Zero natural persons by construction.** Strip at *parse time*, before any
    write: customer reviews, reviewer names, author-attributed ratings, Q&A
    blocks, `schema.org/Review`, `Person`, `aggregateRating.author`; roaster
    staff and About-page names; producer/farmer names. Add an explicit drop-list
    in the extractor **and a unit test asserting no `Review`/`Person` node
    survives**. Never persist raw HTML containing them "to parse later" — that
    is still storage.

### 3.9 Publication (use cases b/c only)

35. **Always attribute and deep-link**, product-level, on every displayed item.
    Never reproduce a roaster's logo or visual identity. Always aggregate across
    multiple roasters so the output is never a substitute for any single source.
36. **Never present a price as yours** — render *"prix constaté chez X le
    [date]"* with the crawl timestamp visible.
37. **Never show a stale price.** Refresh ≥ every 24 h; suppress listings older
    than **48 h** rather than displaying them (L.121-2 code conso — liability is
    yours, not the roaster's).
38. **Default sort is never price. No price-history charts.** Headline value is
    availability + roast date.
39. **Before publishing anything**: ship an art. 13/14 privacy notice with an
    objection channel, **and** the D.111-16 comparison rubric disclosing ranking
    criteria, absence (or existence) of paid referencing, non-exhaustiveness, and
    update frequency.
40. Publish the **scraper**, not the **scrape** — and see **§3.11**, which
    governs that and applies to *every* use case, including private (a).

### 3.10 Observability, kill switch & incident response

41. **Per-request log line**: timestamp, host, URL, status, bytes, elapsed,
    cache-hit, robots-decision. Retain 90 days. Per-run summary per host.
42. **Circuit breaker**: ≥ 5 consecutive non-2xx/304, **or** 4xx+5xx rate > 20 %
    over a 20-request window, **or** any 403/429 ⇒ trip immediately, abort that
    host, alert. **Reset is a human action, never automatic.**
43. **Kill switch**: a `blocklist` array in one config file plus a
    `CRAWLER_DISABLED=1` env var for total stop. Blocklisting a domain must take
    under 2 minutes with no code change or redeploy. **Test it quarterly** — an
    untested kill switch is not a kill switch.
44. **Documented opt-out**: the `+URL` page states that any email naming a
    domain results in blocklisting within 24 h, no questions, no negotiation.
    Log every complaint and the timestamp of the blocklist commit — that log is
    your evidence of good faith.

**Incident-response runbook — first 24 hours**

| When | Action |
| --- | --- |
| **Hour 0** | **Stop collection for that domain.** Kill switch, *before* replying. |
| **Hour 0–1** | **Preserve, don't delete.** Snapshot logs and code state. Deleting after notice looks like consciousness of guilt. |
| **Hour 1–4** | **Reply as a human, in French, non-defensively.** *"Merci de m'avoir contacté. J'ai immédiatement arrêté la collecte concernant votre site. Voici exactement ce que je collectais et à quelle fréquence. Souhaitez-vous que je supprime les données déjà collectées ?"* **Do not argue TDM exceptions with a small business owner** — it turns an annoyed founder into an offended one. |
| **Hour 4–24** | Do what they asked, add the domain to the **permanent** exclusion list, confirm in writing. |
| **If from an avocat** | Same first three steps, then **stop writing** and get 30 minutes with a French IP/IT lawyer before anything substantive. Budget €500–1 500 for this *before* launching (c). |
| **Never** | Resume quietly, switch IPs, or go public complaining about them. That last one turns an incident into a reputation. |

### 3.11 Publishing the crawler source

Applies to **every** use case, including private (a) — the code can be public
while the data never is. Publishing the source is lawful, and on balance
advisable, but it is a separate question from whether the crawling is lawful:
**a public repo does not legitimise a run, and §3.1–§3.10 continue to govern
unchanged.**

**Why the code itself is not the problem.** There is no offence in French or EU
law for distributing a tool that reads public web pages. The code is your own
work, you hold copyright in it, and no roaster has a claim over selectors that
describe their HTML. The one real hook is **C. pén. art. 323-3-1** — offering or
making available, *sans motif légitime*, a program *"conçu ou spécialement
adapté"* to commit the 323-1/323-3 offences (transposing Directive 2013/40
art. 7) — together with complicity by furnishing means (art. 121-7). A crawler
that obeys robots.txt, identifies truthfully and stops on 403 is neither
designed nor adapted for fraudulent access, and a brew-log is a plain *motif
légitime*.

**So the risk inverts from the intuition: the exposure is not the crawling code,
it is the evasion code published alongside it.** Honour §3.7 and there is
nothing problematic left to publish.

45. **Ship no §3.7 capability, even unused, even behind a flag, even
    commented-out.** No proxy rotation, UA spoofing, TLS/JA3 manipulation,
    CAPTCHA solving, or Cloudflare bypass. These are what move a repo toward
    *"spécialement adapté"* under art. 323-3-1, and a README that *instructs*
    evasion moves it toward art. 121-7.

46. **No captured content in the repo, and the condition is stricter than it
    sounds.** Exclude, in roughly descending order of how often it leaks:
    - **Test fixtures** — recorded HTTP responses, VCR/`pytest-recording`
      cassettes, a saved `products.json`, any golden-file test against a real
      product page. *This is the most common leak.* Use hand-written synthetic
      fixtures, or a site you control.
    - **The SQLite file and the `hishel` response cache** — `.gitignore` both
      *before* the first commit.
    - **Sample outputs** — demo CSVs, result screenshots, README examples
      containing real prices.
    - **Product images** — never, in any form, including as test data.
    - **The allowlist's CGV quotes** (rule 3) — one sentence each. A short quote
      in a compliance record is defensible; a mirrored CGV page is not.

47. **Git history counts.** Deleting a fixture in a later commit does not remove
    it. If content is ever committed, rewrite history rather than adding a
    delete commit.

48. **Write the code to be read by the roaster's lawyer.** This is the strongest
    argument for publishing at all: a repo whose first screenful shows
    `protego`, a 3 s delay, a contact address in the User-Agent and a
    `blocklist` config is contemporaneous, timestamped, third-party-hosted
    evidence of good faith that cannot be fabricated after the fact. The same
    repo containing a `proxies.py` is a gift to opposing counsel. **The repo is
    exhibit A either way; choose which.**

49. **Expect the repo to be found, and frame it accordingly.** Naming the
    roasters is lawful (nominative reference, and the domains are needed
    anyway), but it makes the project discoverable — which is precisely what
    converts "nobody noticed" into the human email of §1.4, and that is a good
    trade. Frame the README around the application, not the extraction: *"a
    brew-log that can pre-fill bean data from roasters' public catalogues"*,
    with the §3.5 contact address and the rule-44 opt-out stated in the README
    itself. Same content as "a scraper for French roasters"; entirely different
    reception.

50. **A licence and a disclaimer are not load-bearing.** MIT plus "use
    responsibly" shifts no liability for your own runs. Include them; do not
    rely on them.

---

## 4. Addendum — X (formerly Twitter) cohort crawling

*Added 2026-08-03 after a second three-way review (French/EU hard law ·
platform contract & non-EU law · commercial risk & governance), on the same
terms as the review that produced §§1–3.*

### 4.1 The question

Whether to additionally crawl **X (formerly Twitter)** posts from three
cohorts: **(a)** World Brewers Cup champions, **(b)** the 50 top roasters'
brand accounts, **(c)** well-known coffee bloggers and influencers.

### 4.2 Verdict — **NO**, on all three cohorts, and §3 already says so

**Do not crawl `x.com`.** This is not a close call and it does not turn on any
contested legal theory. Two independent grounds each dispose of it on their
own, and both are *already binding rules in §3* — the addendum adds no new
principle, it applies existing ones to a target the project wants.

**Ground 1 — robots.txt.** Measured 2026-08-03, `https://x.com/robots.txt`
returns HTTP 200, 2 932 bytes, 130 lines, ending:

```
User-agent: *
Disallow: /
```

Three agents get path-level `Allow` carve-outs — `Googlebot`, `Bingbot`,
`facebookexternalhit` — and even they are barred from `/*/media`, `/*/photo$`,
`/*/likes`, `/*/followers`, `/*/following`, `/*/analytics` and `/search?q=`,
i.e. precisely the paths a coffee-photo crawler wants most. `Google-Extended`,
`FacebookBot` and `Discordbot` are each given `Disallow: *`. For any other
user-agent, **every path on the host is disallowed**.

**Rule 11 ("obey robots.txt literally, per-path") and rule 14 end the enquiry
there.** There is no path, no facet and no exception to find. Note the
contrast with §2.2: the roaster hosts `Allow: /` and publish structured
endpoints *for* catalogue reading. X does the opposite, in the single most
orthodox machine-readable form the law recognises (RFC 9309). The `Kneschke v
LAION` question flagged in §2.5 as unsettled — whether prose CGU binds as an
art. 4(3) reservation — **never arises**, because X does not rely on prose.

Two traps worth recording. `/.well-known/tdmrep.json` and `/ai.txt` both return
**200 `text/html`, ~272 KB — the SPA shell**, not a TDM file. A naive client
concludes "no reservation present". It is present; it is in robots.txt. This is
the §2.2 `cafeslugat.com` catch-all trap in a new costume, and rule 12 (fail
closed) covers it.

**Ground 2 — rule 34 is structurally unsatisfiable here.** Rule 34 requires
**zero natural persons by construction**. In §§1–3 personal data was an
avoidable *contaminant* — review author names, staff photos — that
minimisation removed at the schema level. For cohorts (a) and (c) the natural
person **is the selection criterion**: the corpus is defined as "posts by these
people". No filter cures that, because filtering happens after a design step
that has already failed. Cohort (b) is thinner but not exempt — French
speciality roasting is founder-led, and named staff, tagged baristas and faces
appear constantly on "brand" accounts.

### 4.3 The three-way discussion

#### French/EU hard law — **high, and worse than §2.1 on every axis**

Each head that came out low for roaster catalogues inverts here.

- **GDPR.** Art. 6(1)(f) is the only candidate basis and it does not survive
  the balancing test against a source crawled over an explicit blanket
  exclusion. CNIL's *moissonnage* focus sheet and EDPB Opinion 28/2024 both
  require **excluding sources that clearly oppose scraping**; `Disallow: /` is
  the clearest possible opposition. Art. 14 transparency is unsatisfiable in
  practice, and the 14(5)(b) disproportionate-effort derogation never removes
  the duty to *publish* the information. Art. 9 special categories leak in
  structurally — these are people posting daily about health, diet, religious
  observance and politics. The household exemption (*Lindqvist* C-101/01,
  *Ryneš* C-212/13) is unavailable the moment anything is published.
  → **Mitigation:** the only defensible shape is **post ID + canonical URL +
  fetch timestamp, nothing else** — no text, no media, no profile fields, no
  engagement counts. That is rule 34's discipline applied to a new surface, and
  it makes erasure a row deletion.
- **Copyright.** §2.1's fact/expression split survives but shifts. *Infopaq*
  (C-5/08) holds eleven words can qualify; *Cofemel* (C-683/17) makes
  originality the sole criterion. "New Ethiopian natural, in stock Friday" is
  unprotected; a crafted thread on extraction theory is not. **Cohort (c) sits
  almost entirely on the protected side** — that is what monetisation buys
  them. Photos are near-always protected (*Painer* C-145/10). A retweet
  reproduces the *underlying* work, so the retweeter's consent is irrelevant to
  the original author's rights.
- **Sui generis database right — do not reuse §2.1's optimism.** The database
  here is **X's, not the roasters'**. The *BHB* obtaining-vs-creating argument
  that made artisan catalogues doubtful does not help: X obtains third-party
  content rather than creating it, and invests heavily in verification and
  presentation — the *LeBonCoin v Entreparticuliers* fact pattern, amplified.
  The genuine defence is quantitative (three small cohorts are not a
  substantial part under L.342-2), not qualitative.
- **TDM exceptions — both fail.** Art. 3 (L.122-5-3 I/II) is reserved to
  research organisations and cultural heritage institutions; a brew-log is
  neither, whoever operates it. Art. 4 fails on both limbs: lawful access (X
  gates most timeline browsing behind auth) and reservation (`Disallow: /`).
  And per §2.1, **art. 4 protects the pipeline, never the product**.
- **Criminal — the hardest single point.** A login wall *plus* `Disallow: /`
  *plus* an express ToS prohibition is a purpose-built record of awareness of a
  protection — the operative test in ***Bluetouff*** (Cass. crim., 20 mai 2015,
  n° 14-81.336). Session cookies you were not issued, an unofficial API client,
  proxy rotation, or continuing after a 403 convert a civil dispute into
  **C. pén. art. 323-1** facts. §3.7 rules 25–27 apply here with no relaxation.
- **Droit à l'image** (art. 9 C. civ.) is autonomous of the GDPR: consent-based,
  no legitimate-interest balancing, no "it was public" defence. The
  public-figure carve-out is narrow and tied to an information purpose;
  **corpus-building is not one**, so cohort (a)'s semi-public status buys
  almost nothing.

#### Platform contract & non-EU law — **the ToS is drafted to close the gap §2.1 relied on**

- **X's anti-scraping clause is express.** ToS §4(iii) prohibits automated
  access other than through published interfaces, with the parenthetical
  *"crawling or scraping the Services in any form, for any purpose without our
  prior written consent is expressly prohibited"*. The pre-2023 carve-out that
  permitted crawling *in accordance with robots.txt* **has been removed** —
  robots.txt compliance is no longer a defence under X's own terms, and
  robots.txt says no in any event.
- **The browsewrap argument is materially weaker than in §2.1.** Art. 1119 code
  civil helped against a roaster whose CGU nobody accepted. X binds by *use*
  ("and/or using the Services, which constitutes acceptance"), which is exactly
  the drafting hole that lost Meta its case; X wrote around it. And browsewrap
  binds a party with **actual knowledge** of the terms — *this document is that
  knowledge*. Writing the analysis forecloses the defence that depends on not
  having read it.
- **Forum.** An EU-resident project gets the **EU/EFTA/UK terms: Irish law,
  Irish courts**, counterparty **X Internet Unlimited Company** (Dublin). The
  Texas / Wichita–Tarrant County clause belongs to the non-EU version and is a
  common, expensive misreading.
- **The case law does not authorise what it is usually cited for.** *hiQ II*
  (31 F.4th 1180, 2022) held only that scraping public data likely is not
  "without authorization" under the **CFAA** — then in Dec 2022 hiQ took a
  **consent judgment, $500 000, a permanent injunction and an order to destroy
  derived data** on contract and state-law grounds. **Contract is the live
  weapon, not the CFAA.** *X Corp v. Bright Data* was dismissed on Copyright
  Act preemption (X holds only a non-exclusive licence to user content), but
  Alsup then allowed amendment where X alleged *"sophisticated efforts to
  access X with knowledge that such access was beyond the scope of any
  authorization"* — **the copying claims died, the evasion claims lived**,
  which is §3.7's thesis restated by a US court.
- **The compliant route exists and is cheap.** X's pay-per-usage API prices
  post reads at **$0.005**, with a 2 000 000 read/month cap and 24-hour
  deduplication. At ~300 accounts and ~1.5 posts/day this is **~$70/month**
  plus a bounded one-off backfill, using under 1% of the cap with ~30× rate
  limit headroom. **This is the only Tier-1 route, and the only form "prior
  written consent" takes at scale.**
- **Resellers make it worse, not better.** Buying a scraped X corpus does not
  cure the platform breach, and it strictly worsens the GDPR position: you
  become controller of personal data with no provenance, no lawful-basis story,
  no art. 14 notice and no way to honour erasure. It also creates a dated,
  discoverable invoice proving knowledge. *Meta v. Bright Data* held a seller
  could sell; it says nothing about whether **you** may buy and process.

#### Commercial risk & governance — **the purpose is undefined, and that is the top finding**

- **No field maps to a column.** Every field the roaster crawl collects lands in
  a table coffee-can already has. Apply that test to a tweet and **nothing
  maps** — there is no `sentiment` column, no `hype_index`, no `influencer_id`.
  The honest purposes are *trend signal*, *training data* (already **NO** at
  §1.2(d)), or *undecided*. All three are the same failure: **the dataset was
  chosen first and the purpose reverse-engineered from it**, which is the exact
  inversion of what CNIL requires and what art. 5(1)(b) purpose limitation
  presupposes.
  → **Narrowest purpose that is actually useful:** a bean-level attribute —
  *"this lot was used in a World Brewers Cup winning routine, with this
  recipe"*. That is brew-log-shaped, attaches to an existing record, and is a
  fact about **coffee**, not about a person. It needs no cohort feed at all.
- **The traffic-back defence does not exist here.** §2.5 leans hard on the
  comparator *driving traffic back* to collapse parasitisme exposure. A tweet
  corpus returns nothing to its author. The entire "aggregates, links back, not
  a substitute for the source" argument is unavailable.
- **The reaction channel is inverted, and it cross-contaminates.** A roaster's
  first move is a sysadmin noticing traffic. A champion's or blogger's first
  move is a **quote-tweet** — their native medium, on the platform, to an
  audience that is literally the project's target users. Cost to them: ninety
  seconds; half-life: permanent; and attached to the repo by name (rule 49 cuts
  both ways). The roasters emailed under rule 3 see it the same afternoon.
  **This risks the defensible programme in order to fund the indefensible one.**
- **Enforcement realism.** In descending order of likelihood: X's automated
  defences block within the first run (at which point rule 27 says *stop*, and
  the entire commercial scraping toolchain exists to violate that rule); a data
  subject files a CNIL complaint — **free, individual, and obligatory to answer
  within a month**, which dissolves the §1.4 cost-asymmetry comfort entirely; a
  public callout; a brand's lawyer; litigation last. Unlike a ten-person
  roaster, **X operates a standing anti-scraping enforcement function** and has
  a demonstrated appetite for suing.
- **Cohort (a) does not need X at all.** World Coffee Events publishes champions
  *and the competition coffee and brew method* — the substantive fields a brew
  log wants — mirrored by Sprudge, Fresh Cup and the trade press. The full
  history of champions is a **two-hour hand-curated table**: first-party, more
  accurate than tweets, no personal-data-by-inference, and **Tier 1 under rule
  6**. Cohort (b) is simply redundant: `products.json` `updated_at` already
  answers "what dropped this week" (§2.2). Cohort (c) is an outreach problem —
  ~20 emails, the §1.3 finding sharpened.

### 4.4 Risk summary — X cohorts

| Heading | (a) WBrC champions | (b) 50 roaster accounts | (c) Bloggers |
| --- | --- | --- | --- |
| robots.txt / opt-out | **Disallowed** | **Disallowed** | **Disallowed** |
| GDPR | **High** | Medium | **High** |
| Droit d'auteur | Medium (photos: high) | Medium | **High** |
| Sui generis (X's) | High | High | High |
| Contract / ToS | High | High | High |
| Criminal (323-1) | Med–High if evasion | Med–High if evasion | Med–High if evasion |
| Droit à l'image | **High** | Low–Medium | **High** |
| Community/reputational | **High** | Medium | **High** |
| **Overall** | **HIGH — no** | **MED–HIGH — redundant** | **HIGH — no** |

### 4.5 API — binding rules (continuing §3)

51. **`x.com` and all X-owned hosts are hard-excluded in code**, in the same
    blocklist as an explicit "no" domain (rule 3). `Disallow: /` for
    `User-agent: *` is dispositive under rule 11; there is no per-path
    exception to find.
52. **No HTML scraping of X, ever** — not the web app, not `mobile.x.com`, not
    Nitter-class mirrors, not `syndication.twimg.com`, not embed/oEmbed used as
    a bulk path, not `archive.org` snapshots of X pages used as a proxy.
53. **Never authenticate, never carry a session cookie, never harvest or reuse
    a guest token.** Extends rule 4. On this target it is also the line between
    a contestable browsewrap argument and an unambiguous clickwrap breach, and
    between *Bluetouff* facts and none.
54. **If X data is used at all, the official X API v2 is the only tier.** There
    is no Tier 2, 3 or 4 for this source. Rule 6 applies unmodified.
55. **Never buy X data from a reseller or ingest a third-party X corpus.**
56. **Set a hard spend cap in the Developer Console before the first request**,
    plus a request counter that aborts the run. Pay-per-use turns rule 16's
    crawl-loop bug from a politeness incident into a bill.
57. **Post IDs and canonical URLs only.** No text, no media bytes, no profile
    fields, no engagement counts. Link, never copy (rule 31), applied verbatim.
58. **Implement deletion propagation before first ingest.** Content deleted,
    suspended, withheld or geotag-stripped on X must be deleted downstream.
59. **No ranking, scoring, sentiment index or leaderboard of named
    individuals** — under any use case, including private (a).
60. **Licensed-source-first for competition data.** Organiser publication
    (World Coffee Events) is Tier 1 for cohort (a); X is not a tier.
61. **Resolve competitor identity against the official results list by full
    name and year, never by acronym.** **WBrC** (World Brewers Cup) and **WBC**
    (World Barista Championship) are different competitions with different
    winners; mis-resolving them attributes one identified person's posts to
    another, which is an art. 5(1)(d) accuracy breach about both — and, if the
    posts are unflattering, a loi 1881 exposure. **Hard-fail an ambiguous
    record rather than guessing.**
62. **Purpose gate.** No field may be ingested that does not map to an existing
    coffee-can column or a committed migration. No "collect now, decide later"
    table may exist. Rule 34 may not be waived for a component whose selection
    criterion *is* a natural person — amend it in writing with a documented
    art. 6(1)(f) balancing and art. 14 notice, or drop the component.

### 4.6 Verification status — re-check before relying on any of this

- ✅ **Measured directly, 2026-08-03:** `x.com/robots.txt` (HTTP 200, 2 932
  bytes, 130 lines; `User-agent: *` → `Disallow: /` at lines 116–117; carve-outs
  for `Googlebot`, `Bingbot`, `facebookexternalhit` only; `Google-Extended`,
  `FacebookBot`, `Discordbot` each `Disallow: *`).
- ⚠️ **Reviewer-verified, not re-measured here:** the verbatim ToS §4(iii) text
  and the EU/non-EU dual-version split; X API pay-per-use pricing, the 2M
  monthly cap and the 24-hour dedup rule; Developer Agreement redistribution,
  deletion-propagation and off-X-matching terms. One reviewer received HTTP 402
  fetching the ToS directly while another retrieved it with a browser UA —
  **quote the live text before relying on it.**
- ❌ **Could not verify:** which X entity is the sui generis database "maker"
  for Directive 96/9 art. 11 purposes; whether any French court has yet ruled on
  scraping a platform over an explicit `Disallow: /` (none found); the current
  appellate status of the US cases cited, which move quickly and should be
  re-checked rather than cited from here.
- Named 2026 competition results were reported by the governance reviewer from
  trade press and are **illustrative, not verified** — take champion data from
  the organiser under rule 60, not from this document.

**The point of §4 is not that X is a special case. It is that §3, applied
honestly to a source the project wanted, said no — and the discipline is to
accept that from the rules rather than to look for a path around them.**

---

## Bottom line

**GO** on (a) private single-user, under §3. **NO** on (b) publishing the
corpus and (d) model training. **(c)** only after outreach, with feeds where
granted and the D.111-16 rubric shipped.

**NO** on crawling X for any cohort (§4): `Disallow: /` for all user-agents
makes rule 11 dispositive, and rule 34 cannot be met by a corpus whose
selection criterion is a natural person. Champion data comes from the
organiser; roaster drops come from `products.json`; bloggers come from asking.

Two things carry most of the risk reduction:

- **Send the emails before writing the crawler.** It changes the legal frame
  (consent beats exception), the reputational frame (partner, not parasite) and
  the ethical frame — and produces materially better data than scraping ever
  will. The defensible crawler is the second-best answer to a question ten
  emails mostly dissolve.
- **Store facts, never expression; link, never copy.** That single discipline
  collapses copyright, sui generis and parasitisme exposure simultaneously,
  across every use case.

## Sources

[CNIL — intérêt légitime & moissonnage](https://www.cnil.fr/fr/focus-interet-legitime-collecte-par-moissonnage) ·
[CNIL — réutilisation commerciale](https://www.cnil.fr/fr/reutilisation-de-vos-donnees-publiees-sur-internet-des-fins-commerciales-quels-sont-vos-droits) ·
[CMS — arrêt LeBonCoin, droit sui generis](https://cms.law/fr/fra/news-information/arret-leboncoin-web-scraping-droit-sui-generis-sur-les-bases-de-donnees) ·
[Dalloz — droit sui generis et scraping](https://dalloz.businesscomm.fr/nos-actualites-juridiques/la-consolidation-de-la-position-francaise-du-droit-sui-generis-enfin-une-limite-pour-le-scraping-de-donnees-ij) ·
[Bird & Bird — OLG Hamburg, Kneschke v LAION](https://www.twobirds.com/en/insights/2025/germany/higher-regional-court-hamburg-confirms-ai-training-was-permitted-(kneschke-v,-d-,-laion)) ·
[Kluwer — TDM opt-outs](https://legalblogs.wolterskluwer.com/copyright-blog/laion-round-2-machine-readable-but-still-not-actionable-the-lack-of-progress-on-tdm-opt-outs-part-1/) ·
[Collin Avocats — affaire Bluetouff](https://www.collin-avocats.fr/affaire-bluetouff-condamnation-pour-maintien-frauduleux-dans-un-stad-et-vol-de-fichiers-informatiques-via-google/) ·
[Legalis — Opodo / Ryanair, CA Paris 2012](https://www.legalis.net/actualite/opodo-peut-continuer-de-vendre-des-billets-ryanair/) ·
[Quinn Emanuel — Meta v. Bright Data](https://www.quinnemanuel.com/the-firm/news-events/client-alert-meta-v-bright-data-significant-decision-for-web-scraping-industry/) ·
[Haas Avocats — comparateurs de prix](https://www.haas-avocats.com/actualite-juridique/comparateurs-de-prix-quelles-obligations-envers-les-consommateurs/) ·
[economie.gouv.fr — obligations des comparateurs](https://economie.gouv.fr/particuliers/comparateurs-ligne-obligations-information?language=fr)

§4 (X addendum):
[x.com/robots.txt](https://x.com/robots.txt) ·
[X Terms of Service](https://x.com/en/tos) ·
[X API pricing](https://docs.x.com/x-api/getting-started/pricing) ·
[X Developer Policy](https://developer.x.com/en/developer-terms/policy) ·
[hiQ II, 9th Cir. 2022](https://cdn.ca9.uscourts.gov/datastore/opinions/2022/04/18/17-16783.pdf) ·
[Proskauer — hiQ consent judgment](https://www.proskauer.com/blog/hiq-and-linkedin-reach-proposed-settlement-in-landmark-scraping-case) ·
[Skadden — X Corp v. Bright Data](https://www.skadden.com/insights/publications/2024/05/district-court-adopts-broad-view) ·
[EDPB Opinion 28/2024](https://www.edpb.europa.eu/our-work-tools/our-documents/opinion-board-art-64/opinion-282024-certain-data-protection-aspects_en) ·
[World Coffee Events — results](https://worldcoffeeevents.org/)

Site-level findings (robots.txt, endpoints, headers, markup, TLS) measured
directly against the live hosts on 2026-08-03. `x.com/robots.txt` re-measured
independently on the same date; see §4.6 for what was and was not verified.