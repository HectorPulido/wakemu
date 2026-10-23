"""Definition-only adapter for the existing eWG933 temporary spellbook runner.

The native runner still owns target registration, context-value transfer,
replacement/removal, actual actor level, retained Qf and native publication.
"""
from collections.abc import Mapping
import math


class MissingNativeMorphProfile(ValueError):
    """A valid eWG operand has no original published spellbook authority."""


def parse(effect, profile, *, profiles=None):
    """Return the exact native profile operand, or reject missing profile data.

    eWG reads the first value (default -1), uses value1==1 for actor level,
    and ignores further operands. Its applied value is narrowed to a Java short
    after the runtime's context-value transfer; that transfer requires separate
    live authority and must not silently change this static dependency domain.
    """
    if effect.get("effect_class") != 933:
        raise ValueError("Wrong native eWG operation family")
    count, raw = effect.get("parameter_count"), effect.get("parameters")
    values = profile.get("parameters") if isinstance(profile, Mapping) else None
    if (
        type(count) is not int
        or not 0 <= count <= 32767
        or not isinstance(raw, (tuple, list))
        or len(raw) != 2 * count
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in raw)
        or not isinstance(values, (tuple, list))
        or len(values) != count
        or any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in values
        )
    ):
        raise ValueError("Malformed native eWG parameters")
    value = values[0] if count else -1
    profile_id = ((value + 32768) % 65536) - 32768
    own_level = count >= 2 and values[1] == 1
    if profiles is None:
        from .combat_morph_spellbook import native_morph_profiles

        profiles = native_morph_profiles()
    entry = profiles.get(str(profile_id)) if isinstance(profiles, Mapping) else None
    if not isinstance(entry, Mapping):
        raise MissingNativeMorphProfile(
            "Missing original native morph profile: " + str(profile_id)
        )
    from .combat_morph_spellbook import build_morph_book

    # Reuse native raw-reference UIDs, order, level caps and capacity handling.
    # No player deck, spells or default profile are synthesized here.
    book = build_morph_book(entry, entry["minimum_level"])
    if entry.get("profile_id") != profile_id:
        raise ValueError("Mismatched native morph profile identity")
    return dict(
        profile_id=profile_id,
        calculated_value=value,
        own_level=own_level,
        profile_minimum_level=entry["minimum_level"],
        minimum_level_book=tuple(book.items()),
    )


def required_context(parsed):
    requirements = [
        "native_morph_execution",
        "native_morph_profile_dependencies",
        "native_morph_value_context",
        "native_runner_lifecycle",
    ]
    if parsed["own_level"]:
        requirements.append("native_morph_actor_level")
    return tuple(requirements)
