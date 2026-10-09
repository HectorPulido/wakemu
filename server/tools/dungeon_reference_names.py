"""Conservative shared name matching for offline dungeon evidence tools."""
import re
import unicodedata

NAME_NORMALIZATION_POLICY = "unicode-nfc-casefold-apostrophe-dash-whitespace-v1"


def normalized_name(value):
    """Normalize typography only; retain accents, words, articles and plurals."""
    if not isinstance(value, str):
        raise ValueError("Native monster name must be text")
    value = unicodedata.normalize("NFC", value).casefold()
    value = value.translate(str.maketrans({char: "'" for char in "’‘ʼ＇"}))
    value = value.translate(str.maketrans({char: "-" for char in "‐‑–—−"}))
    return re.sub(r"\s+", " ", value).strip()
