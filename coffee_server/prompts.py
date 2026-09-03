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

# The bean fields OCR extracts. This is `coffee_can.repo.LABEL_FIELDS` written
# out by hand -- the desktop derives it by exclusion from BEAN_FIELDS, and the
# same two exclusions apply for the same reasons: the flavour axes are scored
# from brews rather than printed on a bag, and `frozen_date` is the day the
# *owner* put the bag in a freezer, which no roaster can know.
#
# WRITTEN OUT RATHER THAN IMPORTED, because this server does not import
# coffee-can (it has no reason to carry that project's storage layer, and the
# two deploy independently). That makes it a copy, so it is one of the pairs
# `coupling-spec.md` §4 is about: a field added here is a field to add there.
BEAN_FIELD_NAMES = (
    # `region` is the second level of `origin` (2026-08-29) -- "Yirgacheffe"
    # under "Ethiopia". A bag prints it far more often than it prints a farm,
    # and it is the half of the origin a buyer actually remembers.
    "name", "origin", "region", "variety", "altitude", "roaster", "producer",
    "farm", "process", "roast_date", "note",
)

BEAN_FIELD_LABELS = {
    "name": "Name",
    "origin": "Origin",
    "region": "Region",
    "variety": "Variety",
    "altitude": "Altitude",
    "roaster": "Roaster",
    "producer": "Producer",
    "farm": "Farm",
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


# WHY EVERY FIELD ON THIS LIST NEEDS A SENTENCE. The schema below makes the
# model return all eleven keys; it does not tell it what any of them mean. A key
# the prompt never defines is answered from the name alone, and "region" is the
# one where that fails visibly: with nothing said, a label reading "Ethiopia
# Yirgacheffe" comes back with the whole string in `origin` and `region` empty,
# or with "Ethiopia" in both. Neither is wrong *as English* -- it is the app's
# two-level split (a country from `Choices.ORIGINS`, then a subdivision from
# `Regions.forOrigin`) that the model was never told about. `origin` and
# `region` are defined together, as one instruction, for that reason: the split
# is between them and cannot be stated in either alone.
LABEL_OCR = (
    "This is a photo of a coffee bag label. Extract these fields, using an "
    'empty string for anything not present on the label. "name" is the '
    "specific coffee's name or lot -- not the roaster's brand, which goes "
    'in "roaster". "origin" is the COUNTRY the coffee was grown in, and '
    'nothing else -- its plain English name on its own ("Ethiopia", '
    '"Colombia", "Panama"), never a country and a region run together. '
    '"region" is the growing area INSIDE that country, at whatever level the '
    'label states it: a coffee region, department, zone, municipality or '
    'washing-station district (e.g. "Yirgacheffe", "Guji", "Huila", '
    '"Boquete", "Nyeri"). A label that prints one line like "Ethiopia '
    'Yirgacheffe", "Colombia - Huila" or "Huila, Colombia" is stating both: '
    'split it, country into "origin" and the rest into "region". If the label '
    'names only a region and no country, put the region in "region" and the '
    'country it belongs to in "origin"; if it names only a country, leave '
    '"region" empty rather than repeating the country there. Do not put a '
    'farm, estate, mill or cooperative name in "region" -- those belong in '
    '"farm". "producer" is the grower -- a person, a family or a '
    'cooperative -- and "farm" is the place the lot was grown or processed: '
    "an estate, finca, washing station or mill (e.g. \"Finca El Puente\", "
    '"Kii Factory"). A label often prints one and not the other; put each '
    'where it belongs rather than copying one into both. "process" should be '
    "a short, standard process name "
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
