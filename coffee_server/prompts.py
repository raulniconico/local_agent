"""Every prompt this server sends, in one file.

WHY THE PROMPTS LIVE SERVER-SIDE. The Android client sends fields, never a
prompt (see schemas.py's module docstring). That means prompt wording, the
JSON shape asked for, and the defensive parsing of what comes back are all
things that can be fixed by a deploy rather than by a Play release that takes
days to reach users -- and it means an extracted API key buys a stranger a
coffee-recipe generator, not a general-purpose model.

The two prompts are ports of the desktop app's, deliberately near-verbatim
(`coffee/src/coffee_can/qwen_brew_suggest.py` and `claude_ocr.py`): the same
question should get the same answer whichever app asked it, and any divergence
should be a decision someone made rather than a rewrite that happened.
"""

import json
from typing import Optional

# The bean fields OCR extracts -- coffee_can.repo.BEAN_FIELDS minus the flavor
# axes, which are not printed on a bag label.
BEAN_FIELD_NAMES = (
    "name", "origin", "variety", "altitude", "roaster", "producer",
    "process", "roast_date", "note",
)

BEAN_FIELD_LABELS = {
    "name": "Name",
    "origin": "Origin",
    "variety": "Variety",
    "altitude": "Altitude",
    "roaster": "Roaster",
    "producer": "Producer",
    "process": "Process",
    "roast_date": "Roast date",
    "note": "Note",
}

# Qwen's JSON mode guarantees syntactically valid JSON, not that it matches any
# particular shape, so the prompt spells the shape out by example -- and the
# reply still gets parsed defensively downstream.
_RECIPE_EXAMPLE = {
    "summary": (
        "A short (2-4 sentence) explanation of the recipe: ratio, why this "
        "grind/temperature, anything else worth noting. Plain text, no markdown."
    ),
    "dose_g": 15,
    "grind_size": "medium-fine",
    "stages": [
        {"temperature_c": 92, "water_g": 30, "time_seconds": 30, "circling": "swirl gently"},
        {"temperature_c": 92, "water_g": 120, "time_seconds": 45, "circling": "none"},
        {"temperature_c": 92, "water_g": 100, "time_seconds": 45, "circling": "swirl gently"},
    ],
}


def brew_suggestion(bean: dict, dripper: str, dose_g: Optional[float] = None) -> str:
    """The Ask-AI prompt. `bean` is a {field: value} dict; blanks are skipped.

    A fixed `dose_g` becomes a constraint rather than a suggestion, and the
    caller forces the returned dose back to it afterwards -- the user is going
    to weigh out that much whatever the model says, and letting a model that
    drifted to 16 g write 16 g into the session would record a brew that never
    happened.
    """
    lines = [
        f"{BEAN_FIELD_LABELS.get(field, field)}: {value}"
        for field, value in bean.items()
        if value
    ]
    bean_summary = "\n".join(lines) if lines else "(no details recorded for this bean)"
    dose_line = (
        f"The dose is fixed at {dose_g:g} g of coffee -- use exactly that for "
        '"dose_g" and scale the water in every stage to it.\n\n'
        if dose_g
        else ""
    )
    return (
        "You are a specialty coffee hand-brew expert. Given this coffee bean:\n\n"
        f"{bean_summary}\n\nand this dripper: {dripper}\n\n"
        f"{dose_line}"
        "Suggest a brewing recipe and reply with a single JSON object only, "
        "no other text, in exactly this shape (temperature_c/water_g/"
        "time_seconds are numbers, not strings):\n\n"
        f"{json.dumps(_RECIPE_EXAMPLE, indent=2)}\n\n"
        '"stages" should list every pour in order, bloom first, typically '
        "2-5 stages depending on the dripper and recipe."
    )


LABEL_OCR = (
    "This is a photo of a coffee bag label. Extract these fields, using an "
    'empty string for anything not present on the label. "name" is the '
    "specific coffee's name or lot -- not the roaster's brand, which goes "
    'in "roaster". "process" should be a short, standard process name '
    "(e.g. Washed, Natural, Honey, Anaerobic Natural) matching the label's "
    'own wording rather than an invented one. "roast_date" should be ISO '
    "format (YYYY-MM-DD) if a full date is printed, otherwise whatever "
    'partial date is shown. "note" is the label\'s tasting/flavour notes '
    '(e.g. "blueberry, dark chocolate, jasmine") plus any other remark '
    "worth keeping that has no field of its own, such as a roast level or "
    "a brew recommendation -- transcribe what's printed, don't invent "
    "tasting notes that aren't on the label."
)

LABEL_OCR_JSON_INSTRUCTION = (
    "\n\nReply with a single JSON object only, no other text, with exactly "
    f"these keys: {', '.join(BEAN_FIELD_NAMES)}. Every value is a string; use "
    '"" for anything the label does not show.'
)

#: Anthropic's structured-output schema for the same extraction. Used where the
#: provider supports it, which turns "usually valid JSON" into "valid JSON".
LABEL_OCR_SCHEMA = {
    "type": "object",
    "properties": {field: {"type": "string"} for field in BEAN_FIELD_NAMES},
    "required": list(BEAN_FIELD_NAMES),
    "additionalProperties": False,
}
