# coffee_android — API surface

> **Status, 2026-08-17.** §3's "endpoints that don't exist yet" now all exist
> and are called. For the built contract in one place — the seven endpoints, the
> `AiGateway` chokepoint's check order, the Room schema at `version = 3`, and
> the wire shapes — see **[design-spec.md](design-spec.md) §9–§10**. This
> document retains the per-endpoint design reasoning and the request/response
> detail behind each one.

Three layers: local Room persistence (§1, self-contained, no dependency),
`coffee_server`'s existing endpoint reused as-is (§2), and new `coffee_server`
endpoints this plan depends on but that don't exist yet (§3). §3 is a
cross-project dependency — flagged throughout, not something `coffee_android`
can build around on its own.

---

## 1. Local persistence — Room, mirroring `coffee-can`'s SQLite schema

Column-for-column port of `coffee/src/coffee_can/db.py`. Same table
boundaries, same cascade-delete relationships (`onDelete = CASCADE` on both
FK-bearing entities, matching the desktop app's `FOREIGN KEY ... ON DELETE
CASCADE`).

### Entities

```kotlin
@Entity(tableName = "beans")
data class BeanEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val origin: String? = null,
    val variety: String? = null,
    val altitude: String? = null,
    val roaster: String? = null,
    val producer: String? = null,
    val process: String? = null,
    val roastDate: String? = null,       // ISO date, nullable = "not set"
    val note: String? = null,
    val status: String = "draft",
    val flavorSource: String = "auto",   // "auto" | "manual"
    // 11 flavor axes, same order/names as repo.FLAVOR_AXES:
    val flavorFruity: Float? = null,
    val flavorFloral: Float? = null,
    val flavorTeaLike: Float? = null,
    val flavorSweet: Float? = null,
    val flavorNuttyCocoa: Float? = null,
    val flavorSpices: Float? = null,
    val flavorRoasted: Float? = null,
    val flavorCereal: Float? = null,
    val flavorGreenVegetative: Float? = null,
    val flavorSour: Float? = null,
    val flavorFermented: Float? = null,
    val createdAt: Long,
    val updatedAt: Long,
)

@Entity(
    tableName = "bean_images",
    foreignKeys = [ForeignKey(BeanEntity::class, ["id"], ["beanId"], onDelete = CASCADE)],
)
data class BeanImageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(index = true) val beanId: Long,
    val position: Int,
    val filePath: String,   // app-private storage, mirrors repo.add_bean_image's copy-in
    val rotation: Int = 0,  // display rotation only, source file untouched
)

@Entity(
    tableName = "brew_sessions",
    foreignKeys = [ForeignKey(BeanEntity::class, ["id"], ["beanId"], onDelete = CASCADE)],
)
data class BrewSessionEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(index = true) val beanId: Long,
    val brewDate: String? = null,
    val dripper: String? = null,
    val filterPaper: String? = null,
    val grinder: String? = null,
    val grindSize: String? = null,
    val waterPpm: String? = null,
    val humidity: String? = null,
    val doseG: Float? = null,
    val score: Float? = null,        // null = "not set", else 0..5 step 0.5
    val extraction: Float? = null,   // -1..1
    val note: String? = null,
    val status: String = "draft",
    // same 11 flavor_* columns as BeanEntity
    val flavorFruity: Float? = null,
    /* ...remaining 10 axes, identical to BeanEntity... */
    val createdAt: Long,
    val updatedAt: Long,
)

@Entity(
    tableName = "brew_stages",
    foreignKeys = [ForeignKey(BrewSessionEntity::class, ["id"], ["sessionId"], onDelete = CASCADE)],
)
data class BrewStageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(index = true) val sessionId: Long,
    val stageNumber: Int,
    val temperatureC: Float,
    val waterG: Float,
    val timeSeconds: Int,
    val circling: String? = null,
)
```

### DAOs — mapped from `repo.py`'s function surface

Room's typed `@Update` on a full entity replaces `repo.py`'s single-field
`update_bean_field`/`update_session_field` pattern (which exists in the
Python CLI/GUI to support field-at-a-time CLI edits and cheap `updated_at`
touches) — Compose screens autosave the whole entity on a debounced timer
instead, which is the idiomatic Room pattern and avoids hand-rolling a
field-name/value dynamic-update path that Room isn't built for.

```kotlin
@Dao
interface BeanDao {
    @Insert suspend fun insert(bean: BeanEntity): Long
    @Update suspend fun update(bean: BeanEntity)
    @Query("SELECT * FROM beans WHERE id = :id") suspend fun getById(id: Long): BeanEntity?
    // list_beans + session_count, one query via LEFT JOIN/COUNT instead of repo.py's per-row annotation:
    @Query("""
        SELECT beans.*, COUNT(brew_sessions.id) AS sessionCount FROM beans
        LEFT JOIN brew_sessions ON brew_sessions.beanId = beans.id
        GROUP BY beans.id ORDER BY beans.createdAt DESC
    """)
    fun listAll(): Flow<List<BeanWithSessionCount>>
    @Delete suspend fun delete(bean: BeanEntity)  // cascades to images + sessions
}

@Dao
interface BeanImageDao {
    @Insert suspend fun insert(image: BeanImageEntity): Long
    @Query("SELECT * FROM bean_images WHERE beanId = :beanId ORDER BY position")
    fun listForBean(beanId: Long): Flow<List<BeanImageEntity>>
    @Query("UPDATE bean_images SET rotation = :rotation WHERE id = :id")
    suspend fun setRotation(id: Long, rotation: Int)
    @Delete suspend fun delete(image: BeanImageEntity)  // + file cleanup in repository layer
}

@Dao
interface BrewSessionDao {
    @Insert suspend fun insert(session: BrewSessionEntity): Long
    @Update suspend fun update(session: BrewSessionEntity)
    @Query("SELECT * FROM brew_sessions WHERE id = :id") suspend fun getById(id: Long): BrewSessionEntity?
    @Query("SELECT * FROM brew_sessions WHERE beanId = :beanId ORDER BY brewDate DESC")
    fun listForBean(beanId: Long): Flow<List<BrewSessionEntity>>
    @Query("SELECT brewDate, COUNT(*) as count FROM brew_sessions GROUP BY brewDate")
    fun countByDate(): Flow<List<DateCount>>  // feeds ContributionCalendar
    @Delete suspend fun delete(session: BrewSessionEntity)
}

@Dao
interface BrewStageDao {
    @Insert suspend fun insert(stage: BrewStageEntity): Long
    @Update suspend fun update(stage: BrewStageEntity)
    @Query("SELECT * FROM brew_stages WHERE sessionId = :sessionId ORDER BY stageNumber")
    fun listForSession(sessionId: Long): Flow<List<BrewStageEntity>>
    @Delete suspend fun delete(stage: BrewStageEntity)
}
```

**Migrations (added after engineering review):** the desktop schema's own
history (`db.py`'s `_migrate()`) includes multiple additive `ALTER TABLE`
steps and one genuinely hard one — splitting a retired `flavor_sour_fermented`
column into `flavor_sour`/`flavor_fermented` with a best-effort, one-way data
carry — proof the flavor-axis set isn't as stable as a flat-column design
assumes. Room's migration path must be treated as production-critical from
the first schema change: every change ships a named `Migration(n, n+1)`
object, tested with `androidx.room.testing.MigrationTestHelper` before merge.
**`fallbackToDestructiveMigration()` is explicitly banned** — with no cloud
backup (per `specs/legal-android.md` §1), a skipped/failed migration on a
real device is unrecoverable user data loss, not an inconvenience.

`get_average_flavor_scores`/`get_bean_average_flavor_scores` (repo.py) —
ported as a repository-layer Kotlin function over `BrewSessionDao` query
results (average each non-null flavor column across sessions with any
nonzero flavor rating, matching the "all-zero = never rated, excluded" rule)
rather than a raw SQL aggregate — clearer in Kotlin and the row count here is
never large enough for SQL-side aggregation to matter.

**Choice lists** (`choice_lists.py`/`processes.py` equivalents — dripper,
grinder, filter paper, process options): ship as a plain Kotlin `object` with
`List<String>` constants, editable-dropdown UI (user can type a custom value,
matching the desktop app's editable combos) — no DB table needed, these were
never dynamic server-side data in the original app either.

---

## 2. `coffee_server` — how the client authenticates

> **Superseded in part, 2026-08-14.** The plan below was written when the app
> was going to call `/v1/ask` with a client-rendered prompt. It no longer does,
> and must not: a shipped client ships its API key, so an endpoint it can reach
> that accepts arbitrary text is a published general-purpose LLM on the
> developer's bill. The app now calls **`POST /v1/suggest`**, which takes the
> bean fields and the dripper and renders the prompt server-side
> (`coffee_server/prompts.py`). The key-related analysis below survives intact
> and is what the account requirement came out of.
>
> **What is built, as of 2026-08-14:** `/v1/suggest`, `/v1/vision`,
> `/v1/report`, `GET`+`DELETE /v1/account`, and `/v1/catalogue` + `/v1/news`
> (which return 503 until the compliance gates in §3.2 are met). Server-side
> per-account metering, daily quota and a sliding-window burst limit are in
> place, which closes the "no rate limit or spend cap in `config.py`" gap this
> section flagged. See `specs/coffee-server.md` §3.
>
> **Auth is now two things, not one:** the `X-API-Key` header *and*
> `Authorization: Bearer <Google ID token>`, verified server-side against
> Google's JWKS including audience. The key says "one of our clients"; the
> token says *which user*, and only the second can be metered or cut off. An
> extracted key alone now reaches nothing that costs money — which is the
> answer to the abuse-cost problem stated below, arrived at through
> `specs/legal-accounts.md` §3.8's account rather than through Play Integrity.

### `POST /v1/ask` (the original analysis, retained)

Originally intended for the **Ask-AI brew suggestion** feature. Client renders the same
prompt shape `qwen_brew_suggest.py` already uses server-side in the desktop
app (bean fields + chosen dripper → structured-JSON-response instruction),
sends it as `prompt`, and parses the returned `content` string as JSON
client-side into the same shape:

```json
// Request
{ "provider": "qwen", "prompt": "<rendered prompt>", "max_tokens": 2048 }
// Response
{ "provider": "qwen", "model": "qwen-max", "content": "{\"summary\":...,\"dose_g\":...,\"grind_size\":...,\"stages\":[...]}" }
```

Auth: `X-API-Key` header. **Revised after engineering review**: the original
draft argued a single shared key baked into the APK was fine because it
authenticates to a self-hosted gateway rather than a third-party API — that
answers a confidentiality question, not the actual risk, which is abuse cost.
This key gates *metered, billed* Anthropic/Qwen calls with no rate limit or
spend cap in `coffee_server/config.py` today; a string constant extracted
from a decompiled APK (close to guaranteed) lets anyone run up the
developer's own bill, indistinguishable in logs from legitimate traffic,
with no per-client attribution and no remedy short of rotating the key for
every installed client simultaneously. **Minimum viable fix for v1**: keep
one shared key (still simplest, `coffee_server` has no account system to
provision per-install tokens against), but pair it with server-side rate
limiting per key/IP and spend alerts on the Anthropic/Qwen billing dashboards
— currently absent from `config.py` entirely — plus a documented rotation
runbook. Stronger fixes (Play Integrity API attestation, per-install revocable
tokens) are real options, deliberately deferred past v1 rather than blocking
it. **Also split into two keys**, not one: a low-stakes read key for
`/v1/catalogue`/`/v1/news` (§3.2-3.3) and a separate key for the metered
`/v1/ask`/`/v1/vision` endpoints — a catalogue-triggered key rotation
shouldn't take down the AI features and vice versa.

---

## 3. `coffee_server` — the endpoints this plan depends on

> **Built on 2026-08-14.** All of §3.1–§3.3 exist now, plus `/v1/suggest`,
> `/v1/report` and `/v1/account`, which this section did not anticipate. The
> shapes below are the design; `specs/coffee-server.md` §3 is the built
> contract and wins where they differ. §3.2/§3.3's **client** was built on
> 2026-08-15 (`ui/screens/CanDrinkScreen.kt`, screens.md §7) but, same day, is
> **not wired live in v1** — the `-1` axis page shows a static placeholder
> instead, and the full screen ships in **v2**. The endpoints themselves
> still answer 503 until `specs/legal.md` rules 2–3 (outreach, the 14-day
> wait, a per-domain allowlist entry) and `specs/legal-accounts.md` rule 72
> (re-record the use case) are satisfied for real; `allowlist.json` still
> ships empty.

**Revised after specialist review, then revised again 2026-08-15**: §3.1 was
v1's only cross-project dependency for a while — app-dev review found it's
genuinely a small, straight port of existing `claude_ocr.py` logic to a new
route, while §3.2-3.3 moved to v1.1 after the same review found the catalogue
endpoint was real new infrastructure (scheduler, TTL cache, the full
kill-switch/circuit-breaker apparatus `specs/legal.md` mandates), comparable
in weight to the audio endpoint the original draft already deferred. That
infrastructure got built anyway (`coffee_server/crawler.py`,
`coffee_server/scheduler.py`), which removed the engineering reason for the
deferral, so the Can-Drink client moved back into v1. The audio endpoint
(§3.4) has no such build yet and stays deferred on its own, unrelated
grounds.

### 3.1 `POST /v1/vision` — bean-label OCR (blocks: Bean Detail's scan flow)

Centralizes what `claude_ocr.py`/`qwen_ocr.py` do today (vision call +
structured field extraction), server-side, so the Android client never holds
a provider key. Single-provider for v1 per `README.md`'s phasing
recommendation (Claude default, `provider` still present for future
flexibility, not for client-side fallback logic).

```json
// Request
{
  "provider": "anthropic",
  "image_base64": "<base64 JPEG/PNG>",
  "mime_type": "image/jpeg",
  "max_tokens": 1024
}
// Response — same field shape as ocr.py/claude_ocr.py's guess_bean_fields()
{
  "provider": "anthropic",
  "model": "claude-opus-5",
  "fields": {
    "name": "", "origin": "", "variety": "", "altitude": "",
    "roaster": "", "producer": "", "process": "", "roast_date": ""
  }
}
```

Server-side implementation note (for `coffee-server` spec, not this repo):
reuses the same vision + JSON-schema-output pattern already proven in
`claude_ocr.py` — this is a straight port of existing logic to a new
FastAPI route, not new AI-integration work.

**Payload size (added after engineering review):** the request has no
size/resolution cap as originally drafted — a raw phone photo can be several
MB before base64 inflation. The Android client must downscale/recompress
before encoding (roughly matching whatever resolution the vision API
actually uses internally, e.g. ~1568px long edge for Claude), both to bound
upload cost on mobile networks and to avoid gateway body-size failures. Note
this downscale step happens on a copy used for the network call — the
locally-persisted photo (already EXIF-stripped per §1's migration note and
`README.md` resolution #8) keeps its own separate handling.

### 3.2 `GET /v1/catalogue` — roaster listings (client built, live in v2 — see screens.md §7)

> The response shape below is the original design draft; the built one is
> `coffee_server/schemas.py`'s `CatalogueResponse`/`CatalogueItem` (`items`,
> not `listings`; `url`/`image_url`, not `product_url`/`photo_url`; no
> `in_stock` — the crawler's Shopify/WooCommerce parsers don't extract a
> stock signal, so the client doesn't filter or badge on one either, see
> screens.md §7). `net/ServerApi.kt`'s `CatalogueItemDto` mirrors the built
> shape, not this draft.

Replaces client-side `whats_new.py` calls entirely, per
`specs/legal-android.md` §4. Server crawls on the existing schedule/rate
limits from `specs/legal.md` §3.4 (unchanged — this endpoint changes *who
reads the cache*, not the crawl itself), caches, and serves reads.

**Revised after app-dev review**: query-param filtering removed. At "a
handful of storefronts" scale (`specs/legal-android.md` §4: five-to-eight
sites), a full unfiltered payload is small — server-side filtering buys
negligible payload savings but costs a network round-trip per filter change
and forecloses offline browsing. Client caches the full response into Room
and filters (roaster/origin/search/in-stock) locally instead.

```
GET /v1/catalogue
Headers: If-None-Match: <etag from last fetch>  (optional, standard 304 flow)
```
```json
// Response
{
  "fetched_at": "2026-08-04T03:45:00Z",
  "listings": [
    { "name": "", "roaster": "", "origin": "", "price": "", "weight": "",
      "in_stock": true, "photo_url": "", "product_url": "" }
  ]
}
```

`photo_url`/`product_url` point at the roaster's own site — the Android
client hotlinks `photo_url` directly via Coil (same "never cache a product
photo" rule as `specs/legal.md` §3.8 rule 31, now enforced by the *client*
never persisting it, same as `RemoteImageLabel` already does on desktop).
Gated behind the **read key** (§2's key-split resolution), not the AI-calls
key — this data isn't confidential, the split exists so an AI-key rotation
can't take this screen down as collateral damage.

### 3.3 `GET /v1/news` — ranked headlines (v1.1 still, unlike §3.2 — no client screen built yet)

Same centralization logic as §3.2, replacing client-side `coffee_news.py`.
Nearly free once §3.2's scheduler/cache infrastructure exists — bundled into
the same v1.1 pass rather than built separately. Same read key as §3.2.

```json
// Response
{ "fetched_at": "2026-08-04T02:00:00Z",
  "items": [ { "headline": "", "source": "", "age": "", "url": "" } ] }
```

### 3.4 (v1.1, not detailed here) audio endpoint for voice sessions

Same category of gap as §3.1 but for `qwen_brew.py`'s audio-understanding
call — deferred with voice session itself per `README.md`. Whoever picks
this up should follow §3.1's pattern (base64 payload in, structured JSON
fields out) rather than design a new shape from scratch.

---

## Screen → API call matrix

| Screen | Local Room | `coffee_server` | Ships in |
|---|---|---|---|
| Home | `BeanDao.listAll`, `BrewSessionDao.countByDate`, flavor average | — (catalogue preview strip removed — see README phasing) | closed-testing-ready |
| Bean Detail | `BeanDao`, `BeanImageDao`, `BrewSessionDao.listForBean` | `POST /v1/vision` (scan only) | CRUD: closed-testing-ready · scan: v1 |
| Scan Review | (writes back to Bean Detail's in-memory form state) | — | v1 |
| Brew Session Detail | `BrewSessionDao`, `BrewStageDao` | — | closed-testing-ready |
| Ask-AI Suggestion | writes via `BrewSessionDao`/`BrewStageDao` on accept | `POST /v1/ask` | v1 |
| Voice Session | writes via `BrewSessionDao`/`BrewStageDao` on accept | `POST /v1/audio` (§3.4) | v1.1 |
| Can-Drink Catalogue | `CatalogueDao`, Room-cached copy of `/v1/catalogue`'s response, filtered locally | `GET /v1/catalogue` (read key) | built 2026-08-15, but **not wired live in v1** — `-1` axis page shows a static placeholder instead; full screen ships **v2**, once legal.md's outreach/allowlist process completes |
| Camera Capture | writes file to app-private storage (EXIF-stripped on write), returns path | — | v1 |
| Profile Settings | local `DataStore`/prefs (mirrors `profile.py`'s single JSON blob — no DB table needed, same as desktop) | — | closed-testing-ready |
| Share Card export | reads `BeanDao`/`BrewSessionDao` for render data | — | closed-testing-ready |
| AI disclosure & consent | `DataStore` flags (`shown`, `accepted` — separate, see `screens.md` §11) | — | v1 |

## Error-handling & offline conventions (added after engineering review)

Applies to every `coffee_server` call (`/v1/ask`, `/v1/vision`, and the
v1.1 read endpoints), stated once here rather than repeated per screen:

- **Check connectivity before firing a request** (`ConnectivityManager`) and
  show a distinct "you're offline" state rather than firing and waiting on a
  timeout.
- **Explicit connect/read timeouts** on the shared OkHttp client — an
  unreachable `coffee_server` must fail visibly, not hang indefinitely.
- **No silent automatic retry** on `/v1/ask`/`/v1/vision` specifically — a
  retried call is a second billed request, and a background-queued retry
  (e.g. via WorkManager) would risk silently sending a photo after the user
  believed they'd cancelled, which is a consent problem under
  `specs/legal-android.md` §2.1, not just a UX one. AI calls are synchronous
  and best-effort by design, stated explicitly rather than left implicit.
- **All bean/session/stage CRUD works fully offline**, unconditionally — this
  is Room-local and the core value proposition; stated here as an explicit
  guarantee, not left to be assumed.

## Testing requirements (added after engineering review)

Not exhaustive test-plan detail (out of scope for a planning document), but
naming the three areas specialist review found genuinely load-bearing enough
to require tests from v1, not "later": Room migrations (`MigrationTestHelper`,
per §1); parsing of `/v1/ask`'s `content` and `/v1/vision`'s `fields` against
malformed/truncated/missing-field fixtures — `coffee_server`'s own
`AskResponse.content` is an untyped string with no server-side JSON
validation, and `ANTHROPIC_MAX_TOKENS` capping thinking+output together is a
documented truncation failure mode elsewhere in this repo (`coffee_agent`),
so it will happen here too; and an instrumented EXIF-strip regression test
(ingest a photo with known GPS tags, assert they're gone post-ingest).
