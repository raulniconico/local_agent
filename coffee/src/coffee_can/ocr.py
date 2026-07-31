"""Best-effort extraction of bean profile fields from a photo of a coffee
bag label, via local OCR (Tesseract, through pytesseract) plus a handful of
regex/keyword heuristics.

This is never authoritative -- label layouts vary wildly and OCR on a
photographed (not scanned) label is inherently noisy. Callers must always
surface the results as pre-filled, editable suggestions for the user to
confirm, never write them straight to the database.
"""

import re
from pathlib import Path

from PIL import Image
from pytesseract import TesseractNotFoundError, image_to_string

from . import processes
from .repo import BEAN_FIELDS

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# field -> the label words that introduce it. A separator (":", "-") is
# optional and so is putting the value on the label's own line -- labels are
# printed in every shape imaginable, e.g. "Origin: Ethiopia", "Origin
# Ethiopia", or "Origin" on its own line with "Ethiopia" on the next.
_FIELD_KEYWORDS = {
    "origin": ("country of origin", "origin", "country", "region"),
    "variety": ("variety", "varietal", "cultivar"),
    "altitude": ("altitude", "elevation"),
    "producer": ("producer", "washing station", "grown by", "grower", "farm", "estate"),
    "roaster": ("roasted by", "roastery", "roaster"),
}
_ROAST_DATE_KEYWORDS = ("roast date", "roasted on", "roast")

_ALL_LABEL_KEYWORDS = tuple(kw for kws in _FIELD_KEYWORDS.values() for kw in kws) + _ROAST_DATE_KEYWORDS + ("process",)

# Tried in order against whatever text a date is expected to be in; the first
# one that matches wins.
_DATE_PATTERNS = (
    r"(\d{4}-\d{1,2}-\d{1,2})",
    r"(\d{1,2}[/.]\d{1,2}[/.]\d{2,4})",
    r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",  # "15 June 2026" / "15 Jun 26"
    r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})",  # "June 15, 2026"
)

# A bare altitude ("1,800-2,000 masl", "1900 m", "1650masl") with no label at
# all -- very common on specialty bags that skip the word "Altitude" entirely.
_ALTITUDE_PATTERN = re.compile(
    r"(\d{1,3}(?:,\d{3})*\s*(?:-|to)?\s*(?:\d{1,3}(?:,\d{3})*)?\s*m(?:\.?a\.?s\.?l\.?)?)\b", re.IGNORECASE
)

# Roaster brand names are essentially never introduced by a "Roaster:" label
# on the actual bag -- it's just the company name/logo, most often the most
# prominent text on the label. There's no fixed list to match against (unlike
# process), but roastery names overwhelmingly contain one of these words
# ("Blue Bottle Coffee", "Onyx Coffee Lab", "Verve Coffee Roasters", "Heart
# Roasters", ...), so a short line containing one is a decent unlabeled guess.
_ROASTER_NAME_HINTS = ("coffee", "roasters", "roastery", "roasting co")
_ROASTER_LINE_MAX_LEN = 40


class OcrUnavailableError(Exception):
    """Raised when the Tesseract binary isn't installed/reachable."""


def extract_text(image_path: Path) -> str:
    try:
        return image_to_string(Image.open(image_path))
    except TesseractNotFoundError as exc:
        raise OcrUnavailableError(
            "Tesseract OCR isn't installed. Install it with your system package "
            "manager (e.g. 'sudo apt install tesseract-ocr') and try again."
        ) from exc


def _find_labeled_value(lines: list, keywords: tuple) -> str:
    """Look for a line starting with one of `keywords`, and return whatever
    follows it -- same line (with or without a ":"/"-" separator), or, if
    the keyword is alone on its line, the next line (unless that next line
    is itself some other field's label)."""
    pattern = re.compile(r"^\s*(?:%s)\s*[:\-]?\s*(.*)$" % "|".join(re.escape(kw) for kw in keywords), re.IGNORECASE)
    other_label_pattern = re.compile(r"^\s*(?:%s)\b" % "|".join(re.escape(kw) for kw in _ALL_LABEL_KEYWORDS), re.IGNORECASE)
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(1).strip(" .:-")
        if value:
            return value
        if i + 1 < len(lines) and not other_label_pattern.match(lines[i + 1]):
            return lines[i + 1].strip()
    return ""


def _guess_roast_date(lines: list, joined: str) -> str:
    labeled_value = _find_labeled_value(lines, _ROAST_DATE_KEYWORDS)
    for candidate in (labeled_value, joined):
        if not candidate:
            continue
        for pattern in _DATE_PATTERNS:
            match = re.search(pattern, candidate, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return ""


def _guess_roaster(lines: list) -> str:
    labeled_value = _find_labeled_value(lines, _FIELD_KEYWORDS["roaster"])
    if labeled_value:
        return labeled_value
    for line in lines:
        if len(line) <= _ROASTER_LINE_MAX_LEN and any(hint in line.lower() for hint in _ROASTER_NAME_HINTS):
            return line
    return ""


def _guess_altitude(lines: list, joined: str) -> str:
    labeled_value = _find_labeled_value(lines, _FIELD_KEYWORDS["altitude"])
    if labeled_value:
        return labeled_value
    match = _ALTITUDE_PATTERN.search(joined)
    return match.group(1).strip() if match else ""


def _simplify_process_name(name: str) -> str:
    """Strip the parenthetical qualifier and a trailing "Process"/"(general)"
    from a canonical process name, e.g. "Washed (Wet) Process" -> "Washed" --
    labels almost never print our full canonical string verbatim, but they
    usually do print this shorter core phrase."""
    core = re.sub(r"\s*\([^)]*\)", "", name).strip()
    core = re.sub(r"\s*process\s*$", "", core, flags=re.IGNORECASE).strip()
    return core or name


def _guess_process(joined: str) -> str:
    lowered = joined.lower()
    matches = []
    for name in processes.load_processes():
        core = _simplify_process_name(name)
        if core.lower() in lowered:
            matches.append((len(core), name))
    if not matches:
        return ""
    # Prefer the most specific (longest core phrase) match, so e.g.
    # "Anaerobic Natural" wins over a shorter "Natural" hit on the same text.
    matches.sort(reverse=True)
    return matches[0][1]


def guess_bean_fields(image_path: Path) -> dict:
    """Best-effort {field: value} guesses for every field in BEAN_FIELDS
    except flavor_source/the flavor axes (those aren't on a bag label).
    Anything not confidently found is left as an empty string."""
    text = extract_text(image_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)

    fields = {field: "" for field in BEAN_FIELDS if "flavor_" not in field}

    for field in ("origin", "variety", "producer"):
        fields[field] = _find_labeled_value(lines, _FIELD_KEYWORDS[field])

    fields["roaster"] = _guess_roaster(lines)
    fields["altitude"] = _guess_altitude(lines, joined)
    fields["roast_date"] = _guess_roast_date(lines, joined)
    fields["process"] = _guess_process(joined)

    if not fields.get("name") and lines:
        fields["name"] = lines[0]  # often the brand/product name on its own line

    return fields
