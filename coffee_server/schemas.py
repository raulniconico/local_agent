"""Request/response shapes for every endpoint.

Note the difference between `/v1/ask` and the two endpoints the Android client
actually uses. `/v1/ask` takes a free-form prompt: it is a general proxy, kept
for `coffee_agent` and for local tooling. `/v1/suggest` and `/v1/vision` take
**structured fields** and render the prompt server-side (see prompts.py).

That is not a style preference. A shipped mobile client necessarily ships its
API key, so any endpoint it can reach is an endpoint a stranger can reach; if
that endpoint accepts arbitrary text, the app has published a free
general-purpose LLM on the developer's bill. Structured inputs also keep the
feature inside `specs/legal-android.md` rule 6 -- structured, factual,
advisory output rather than open-ended chat -- which is the argument that makes
this a supporting feature rather than a chatbot for Play's purposes.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AskRequest(BaseModel):
    provider: Literal["anthropic", "qwen"]
    prompt: Optional[str] = None
    messages: Optional[list[ChatMessage]] = None
    system: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, gt=0, le=32768)

    @model_validator(mode="after")
    def _exactly_one_of_prompt_or_messages(self) -> "AskRequest":
        if bool(self.prompt) == bool(self.messages):
            raise ValueError("provide exactly one of 'prompt' or 'messages'")
        return self


class AskResponse(BaseModel):
    provider: str
    model: str
    content: str


# --------------------------------------------------------------- /v1/suggest --

class BeanFields(BaseModel):
    """What the user typed about a bean. Every field optional: a bag with
    nothing but a name is a normal input, not an error."""

    name: Optional[str] = Field(default=None, max_length=200)
    origin: Optional[str] = Field(default=None, max_length=200)
    variety: Optional[str] = Field(default=None, max_length=200)
    altitude: Optional[str] = Field(default=None, max_length=100)
    roaster: Optional[str] = Field(default=None, max_length=200)
    producer: Optional[str] = Field(default=None, max_length=200)
    process: Optional[str] = Field(default=None, max_length=200)
    roast_date: Optional[str] = Field(default=None, max_length=40)
    note: Optional[str] = Field(default=None, max_length=2000)


class SuggestRequest(BaseModel):
    """Bean + dripper in, recipe out. No prompt field, deliberately -- see the
    module docstring."""

    bean: BeanFields
    dripper: str = Field(max_length=100)
    dose_g: Optional[float] = Field(default=None, gt=0, le=200)
    provider: Optional[Literal["anthropic", "qwen"]] = None


class SuggestStage(BaseModel):
    temperature_c: Optional[float] = None
    water_g: Optional[float] = None
    time_seconds: Optional[int] = None
    circling: Optional[str] = None


class SuggestResponse(BaseModel):
    """Parsed and normalised server-side, so the client gets a typed shape
    instead of a JSON string it has to defend against.

    The desktop app does this same normalisation in
    qwen_brew_suggest._normalize() because JSON mode guarantees valid JSON, not
    the *right* JSON. Doing it here means one implementation instead of one per
    client, and a truncated or malformed model reply becomes a 502 rather than
    a crash in a phone.
    """

    provider: str
    model: str
    summary: str
    dose_g: Optional[float] = None
    grind_size: str = ""
    stages: list[SuggestStage] = Field(default_factory=list)


# ---------------------------------------------------------------- /v1/vision --

class VisionRequest(BaseModel):
    """A bean-bag label photo, base64-encoded.

    The client is expected to have stripped EXIF before this point
    (`legal-android.md` rule 2 -- at ingest, not at upload). The server cannot
    verify that it did, which is exactly why the rule places the strip at
    capture time on the device.
    """

    image_base64: str
    media_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"
    provider: Optional[Literal["anthropic", "qwen"]] = None


class VisionResponse(BaseModel):
    provider: str
    model: str
    fields: BeanFields
    # True when the model returned nothing usable -- a blurry shot, a photo of
    # something that is not a label. The client shows "couldn't read much from
    # this photo" rather than an inexplicably empty form (plan/screens.md §3).
    empty: bool = False


# ------------------------------------------------- /v1/catalogue and /v1/news --

class CatalogueItem(BaseModel):
    """Facts only. `specs/legal.md` rules 29-33, promoted to Play-load-bearing
    by `legal-accounts.md` rule 73: never `body_html`, never a re-hosted image,
    tasting notes normalised or <=200 chars with attribution. `image_url` is a
    live pointer to the roaster's own CDN -- the client hotlinks it and never
    caches it."""

    roaster: str
    name: str
    url: str
    image_url: Optional[str] = None
    origin: Optional[str] = None
    process: Optional[str] = None
    price_eur: Optional[float] = None
    weight_g: Optional[int] = None
    tasting_note: Optional[str] = Field(default=None, max_length=200)
    first_seen_at: Optional[int] = None


class CatalogueResponse(BaseModel):
    items: list[CatalogueItem] = Field(default_factory=list)
    #: Unix seconds. The client shows this; a cache with no visible age is a
    #: comparator making an implicit freshness claim (rule 76 / L.121-2).
    fetched_at: Optional[int] = None
    #: The D.111-16 rubric, served with the data it describes so the catalogue
    #: screen can render it without hard-coding French consumer law into an APK.
    rubric: dict = Field(default_factory=dict)


class NewsItem(BaseModel):
    """Headline, source, date, link. Nothing else, ever: no snippet beyond the
    headline and specifically no AI-generated summary (`legal-accounts.md`
    rule 74 -- droit voisin, arts. L.218-1 et seq. CPI)."""

    title: str
    source: str
    url: str
    published_at: Optional[int] = None


class NewsResponse(BaseModel):
    items: list[NewsItem] = Field(default_factory=list)
    fetched_at: Optional[int] = None


# -------------------------------------------------------------- /v1/account --

class AccountResponse(BaseModel):
    """The Art. 15(3) access document. See accounts.access_record()."""

    account: Optional[dict] = None
    usage: list[dict] = Field(default_factory=list)
    rate_limit_events_currently_held: int = 0
    quota_per_day: dict = Field(default_factory=dict)
    what_is_not_here: str = ""


class ReportRequest(BaseModel):
    """`legal-android.md` rule 5: a route for a user to flag AI output.

    Deliberately carries the flagged text and nothing identifying beyond the
    account the request is already authenticated as. Stored as a log line for a
    human, not in the account record -- a report is about the model's output,
    not about the reporter.
    """

    operation: Literal["read_labels", "suggest_brew"]
    reason: Optional[str] = Field(default=None, max_length=1000)
    output: Optional[str] = Field(default=None, max_length=4000)
