"""Literal installed guild identity codecs and structural validation.

This module grants no guild capability. Name censorship, identity uniqueness,
source/cost authorization and world-machine context remain separate authorities.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

CATALOG_SHA256 = "f6d8051422ebc96c3d20f977d5130c53494d5dca80fc2c7b41bc8bb4376c5ca0"


@lru_cache(maxsize=1)
def catalog():
    raw = Path(__file__).with_name("native_guild_identity_catalog.json").read_bytes()
    if sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("Conflicting native guild identity catalog")
    result = json.loads(raw)
    if (
        result["schema_version"] != 1
        or len(result["name_character_classes"]) != 256
        or len(result["permissions"]) != 27
    ):
        raise ValueError("Incomplete native guild identity catalog")
    return result


def _components(emblem_id, background_id, background_color, emblem_color):
    data = catalog()
    if (
        type(emblem_id) is not int
        or emblem_id not in data["emblem_ids"]
        or type(background_id) is not int
        or background_id not in data["background_ids"]
        or any(
            type(value) is not int or not 0 <= value < data["color_count"]
            for value in (background_color, emblem_color)
        )
    ):
        raise ValueError("Guild blazon component is outside the native picker")
    return dict(
        emblem_id=emblem_id,
        background_id=background_id,
        background_color=background_color,
        emblem_color=emblem_color,
    )


def encode_blazon(*, emblem_id, background_id, background_color, emblem_color):
    """eHs/GS: high32=(emblem,background), low32=(backgroundColor,emblemColor)."""
    _components(emblem_id, background_id, background_color, emblem_color)
    value = (
        (emblem_id << 48)
        | (background_id << 32)
        | (background_color << 16)
        | emblem_color
    )
    return value if value < (1 << 63) else value - (1 << 64)


def decode_blazon(value):
    """Decode and validate all four original short components, without truncation."""
    if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
        raise ValueError("Guild blazon requires a native signed64 identity")
    parts = tuple((value >> shift) & 65535 for shift in (48, 32, 16, 0))
    result = _components(*parts)
    if encode_blazon(**result) != value:
        raise ValueError("Noncanonical native guild blazon")
    return result


def permission_bits():
    """Native fgI identifiers are mask bit positions, not enum ordinals."""
    return {row["name"]: row["bit"] for row in catalog()["permissions"]}


def permission_mask(names):
    bits = permission_bits()
    result = 0
    for name in names:
        if type(name) is not str or name not in bits:
            raise ValueError("Unknown native guild permission")
        result |= 1 << bits[name]
    return result


def validate_rank_mask(mask, *, highest=False, lowest=False):
    """fgz.ZJ fixes highest=all original rights and lowest=no rights."""
    data = catalog()
    if (
        type(mask) is not int
        or mask < 0
        or mask & ~data["highest_rank_authorizations"]
        or type(highest) is not bool
        or type(lowest) is not bool
        or highest
        and lowest
    ):
        raise ValueError("Invalid native guild rank authorizations")
    if highest and mask != data["highest_rank_authorizations"]:
        raise ValueError("The highest native guild rank must retain all rights")
    if lowest and mask != data["lowest_rank_authorizations"]:
        raise ValueError("The lowest native guild rank must retain no rights")
    return mask


def _java_trim(text):
    return text.strip("".join(chr(value) for value in range(33)))


def _native_title(text):
    """BV.aV: lowercase, then Character.toUpperCase at each letter-run start."""
    result = []
    in_word = False
    for char in _java_trim(text).lower():
        if char.isalpha():
            if not in_word:
                upper = char.upper()
                # Java Character case mapping returns one char, unlike String.
                if len(upper) == 1:
                    char = upper
            in_word = True
        else:
            in_word = False
        result.append(char)
    return "".join(result)


def normalize_name(name):
    """eRo.tC presentation normalization; not a database uniqueness key."""
    if type(name) is not str:
        raise ValueError("A native guild name must be text")
    if re.fullmatch(r"[A-Z0-9]{3}-.*", name):
        value = name[:4] + _native_title(name[4:])
    else:
        value = _native_title(name)
    for pattern, replacement in ((r"[ ]+", " "), (r"[-]+", "-"), (r"[']+", "'")):
        value = re.sub(pattern, replacement, value)
    return value


def _fold_char(char):
    """BV.aW/bh: NFD lowercase, basic combining marks removed, fixed ligatures."""
    value = unicodedata.normalize("NFD", char).lower()
    value = "".join(c for c in value if not 0x300 <= ord(c) <= 0x36F)
    return _java_trim(value.replace("œ", "oe").replace("æ", "ae").replace("—", "-"))


def _java_split(pattern, value):
    if value == "":
        return [""]
    parts = re.split(pattern, value)
    while parts and parts[-1] == "":
        parts.pop()
    return parts


def structural_name_error(name):
    """Return the original eRz.fHK/eRx result name for already-normalized input.

    This is the structural step only: eRo.tF also applies original censorship.
    No absence of a censorship provider is interpreted as full name approval.
    """
    if type(name) is not str:
        raise ValueError("A native guild name must be text")
    data = catalog()
    classes = data["name_character_classes"]
    if any(
        ord(char) >= len(classes) or classes[ord(char)] not in (1, 2, 3)
        for char in name
    ):
        return "ERROR_BAD_CHAR"
    (
        minimum,
        maximum,
        vowels_max,
        consonants_max,
        repeats_max,
        specials_max,
        vowels_min,
        consonants_min,
        specials_part_max,
        part_max,
    ) = data["guild_name_rule_parameters"]
    if len(name) < minimum:
        return "ERROR_NAME_TOO_SHORT"
    if len(name) > maximum:
        return "ERROR_NAME_TOO_LONG"
    vowels = consonants = specials = 0
    repeats = 1
    prior = "/"
    for char in name:
        kind = classes[ord(char)]
        if kind == 1:
            vowels += 1
            consonants = 0
        elif kind == 2:
            consonants += 1
            vowels = 0
        else:
            specials += 1
            vowels = consonants = 0
        repeats = repeats + 1 if _fold_char(prior) == _fold_char(char) else 1
        prior = char
        if vowels > vowels_max:
            return "ERROR_TOO_MANY_CONSECUTIVE_VOWEL"
        if consonants > consonants_max:
            return "ERROR_TOO_MANY_CONSECUTIVE_CONSONANT"
        if repeats > repeats_max:
            return "ERROR_TOO_MANY_CONSECUTIVE_IDENTICAL"
        if specials > specials_max:
            return "ERROR_TOO_MANY_SPECIAL"
    for part in _java_split(r"[ -]", name):
        kinds = [classes[ord(char)] for char in part]
        if kinds.count(1) < vowels_min:
            return "ERROR_TOO_FEW_VOWEL_IN_PART"
        if kinds.count(2) < consonants_min:
            return "ERROR_TOO_FEW_CONSONANT_IN_PART"
        if kinds.count(3) > specials_part_max:
            return "ERROR_TOO_MANY_SPECIAL_IN_PART"
        if len(part) > part_max:
            return "ERROR_PART_TOO_LONG"
    if len(name) > 1 and (name[0] == "-" or name[-1] == "-"):
        return "ERROR_INVALID_DASH_POSITION"
    for part in _java_split(r"[ \-']", name):
        if not part or part[0].islower() or part[1:] != part[1:].lower():
            return "ERROR_NAME_WITH_BAD_CASE"
    return "OK"


def validate_name_structure(name, *, normalize=True):
    if type(normalize) is not bool:
        raise ValueError("Native name normalization mode must be explicit")
    value = normalize_name(name) if normalize else name
    error = structural_name_error(value)
    if error != "OK":
        raise ValueError(error)
    return value
