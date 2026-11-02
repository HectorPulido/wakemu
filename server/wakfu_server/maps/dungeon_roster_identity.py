"""Resolve reviewed roster names against explicit native locale identities.

This is a whole-name lookup, not a similarity or species-pool guess. Locale
records are preparation inputs; the game server never reads client archives.
"""
import unicodedata


def normalized_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Reviewed monster name is absent")
    value = value.replace("’", "'").replace("‘", "'")
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char)).split()
    )


def anonymous_name(value):
    return (
        isinstance(value, str)
        and bool(value.strip())
        and normalized_name(value) == "random monster species"
    )


def resolve_reference(name, native_monsters):
    """Require one exact native ID after documented locale typography folding."""
    requested = normalized_name(name)
    candidates = {
        monster["ref"]
        for monster in native_monsters
        if any(
            isinstance(monster.get(field), str)
            and monster[field].strip()
            and normalized_name(monster[field]) == requested
            for field in ("name", "name_fr")
        )
    }
    if len(candidates) != 1:
        reason = "ambiguous" if candidates else "unresolved"
        raise ValueError(f"Reviewed monster name is {reason}: {name}")
    return candidates.pop()
