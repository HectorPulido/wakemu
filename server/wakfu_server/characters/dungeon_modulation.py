"""Trusted temporary competitive profiles using an explicit local balance policy.

Owned build metadata, equipment and selection remain durable and unmodified.
The formula is configurable server policy, not official automatic-build parity.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL

NATIVE_BANDS = (20, 35, 50, 65, 80, 95, 110, 125, 140, 155, 170, 185, 200, 215, 230)


def load_context(db, character):
    """Read difficulty from current durable membership, never from UI requests.

    This intentionally does not invoke selection(): its write/lock path calls
    Store.character and would recurse if used during character hydration.
    """
    if character.get("instance_id", 0) == 0:
        return None
    row = db.execute(
        "SELECT i.instance_id,d.competitive,d.competitive_max_level,d.revision "
        "FROM dungeon_instances i "
        "JOIN dungeon_instance_members m ON m.instance_id=i.instance_id "
        "LEFT JOIN dungeon_difficulty_selections d ON d.instance_id=i.instance_id "
        "WHERE i.instance_id=%s AND m.character_id=%s "
        "AND i.status IN ('active','completed') AND m.status='active'",
        (character["instance_id"], character["id"]),
    ).fetchone()
    if row is None:
        return None
    if row["competitive"] is None:
        # Legacy runs can precede difficulty selection. Do not invent a cap or
        # write configuration from a read-only character hydration path.
        return None
    if type(row["competitive"]) is not bool:
        raise ValueError("Invalid authoritative competitive selection")
    cap = row["competitive_max_level"]
    revision = row["revision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid dungeon modulation selection revision")
    if row["competitive"]:
        if type(cap) is not int or cap not in NATIVE_BANDS:
            raise ValueError("Invalid native competitive level band")
    elif cap != 0 or type(cap) is not int:
        raise ValueError("Ordinary dungeon cannot impose a competitive level band")
    return dict(
        instance_id=row["instance_id"],
        selection_revision=revision,
        competitive=row["competitive"],
        maximum_level=cap,
    )


def capped_level(owned_level, context):
    """Compute only the bound; callers still need a complete native projection."""
    if type(owned_level) is not int or not 1 <= owned_level <= MAX_CHARACTER_LEVEL:
        raise ValueError("Invalid owned character/build level")
    if context is None or not context["competitive"]:
        return owned_level
    cap = context["maximum_level"]
    if type(cap) is not int or cap not in NATIVE_BANDS:
        raise ValueError("Invalid native competitive level band")
    return min(owned_level, cap)


POLICY_NAME = "dungeon_automatic_modulation_policy"
DEFAULT_POLICY = dict(
    version=1,
    hp_per_level=10,
    mastery_per_level=4,
    resistance_divisor=2,
    critical_divisor=10,
    initiative_per_level=1,
    ap_thresholds=[50, 125],
    mp_thresholds=[80],
)


def validate_policy(policy):
    """Reject malformed configuration rather than silently changing balance."""
    if not isinstance(policy, dict) or set(policy) != set(DEFAULT_POLICY):
        raise ValueError("Invalid automatic modulation policy fields")
    if type(policy["version"]) is not int or policy["version"] != 1:
        raise ValueError("Unsupported automatic modulation policy version")
    for key, lower, upper in (
        ("hp_per_level", 0, 100),
        ("mastery_per_level", 0, 50),
        ("resistance_divisor", 1, 200),
        ("critical_divisor", 2, 200),
        ("initiative_per_level", 0, 10),
    ):
        if type(policy[key]) is not int or not lower <= policy[key] <= upper:
            raise ValueError("Invalid automatic modulation coefficient")
    for key, limit in (("ap_thresholds", 6), ("mp_thresholds", 3)):
        thresholds = policy[key]
        if (
            not isinstance(thresholds, list)
            or len(thresholds) > limit
            or any(
                type(level) is not int or not 1 <= level <= MAX_CHARACTER_LEVEL
                for level in thresholds
            )
            or thresholds != sorted(set(thresholds))
        ):
            raise ValueError("Invalid automatic modulation resource thresholds")
    return dict(
        policy,
        ap_thresholds=list(policy["ap_thresholds"]),
        mp_thresholds=list(policy["mp_thresholds"]),
    )


def profile_stats(level, policy):
    """Add the same explicit flat profile to native world and combat stats."""
    if type(level) is not int or not 1 <= level <= MAX_CHARACTER_LEVEL:
        raise ValueError("Invalid automatic modulation level")
    policy = validate_policy(policy)
    stats = {
        1: level * policy["hp_per_level"],
        2: sum(level >= threshold for threshold in policy["ap_thresholds"]),
        3: sum(level >= threshold for threshold in policy["mp_thresholds"]),
        9: min(100, level // policy["critical_divisor"]),
        35: level * policy["initiative_per_level"],
    }
    stats.update(
        {identity: level * policy["mastery_per_level"] for identity in (21, 22, 23, 24)}
    )
    stats.update(
        {
            identity: level // policy["resistance_divisor"]
            for identity in (28, 29, 30, 31)
        }
    )
    return stats


def projected_deck(character, source, level):
    """Retain legal owned spell choices and slot positions without changing XP."""
    from wakfu_server.spells import (
        ACTIVE_SLOT_LEVELS,
        PASSIVE_SLOT_LEVELS,
        available_spells,
        default_deck,
        encode_deck,
        validate_deck,
    )

    source_level = character.get("effective_level", character["level"])
    decoded = validate_deck(
        source or default_deck(character),
        character["breed"],
        source_level,
        character=character,
    )
    available = {
        spell["id"]: spell
        for spell in available_spells(character["breed"], level, character=character)
    }
    slots = {}
    for key, thresholds in (
        ("active", ACTIVE_SLOT_LEVELS),
        ("passive", PASSIVE_SLOT_LEVELS),
    ):
        slots[key] = [
            spell
            if spell in available
            and available[spell]["kind"] == key
            and level >= thresholds[index]
            else 0
            for index, spell in enumerate(decoded[key])
        ]
    result = encode_deck(slots["active"], slots["passive"], level)
    validate_deck(result, character["breed"], level, character=character)
    return result


def project(character, context, policy):
    """Copy an owned snapshot and attach a temporary native automatic sheet."""
    if context is None or not context["competitive"]:
        return character
    if "dungeon_modulation" in character:
        raise ValueError("Automatic modulation cannot be projected twice")
    from wakfu_server.builds import effective_sheet_level, catalog_indices
    from wakfu_server.wire import proto_field

    policy = validate_policy(policy)
    owned_index = character.get("active_build_index", 0)
    owned_level = effective_sheet_level(character, owned_index)
    # Automatic mode is derived from the actual owned character, independent
    # of a lower manually selected sheet. The original choice is restored later.
    level = capped_level(character["level"], context)
    source = character.get("builds", {}).get(owned_index, {})
    original = dict(character, effective_level=owned_level)
    deck = projected_deck(original, bytes.fromhex(source.get("deck", "")), level)
    occupied = set(catalog_indices(character))
    index = next(
        (candidate for candidate in range(127, 0, -1) if candidate not in occupied),
        None,
    )
    if index is None:
        raise ValueError("No free native automatic build slot")
    sheet = b"".join(
        proto_field(tag, value)
        for tag, value in (
            (8, index),
            (18, b""),
            (24, level),
            (56, 0),
            (64, 1),
        )
    )
    result = dict(character)
    result["builds"] = dict(character.get("builds", {}))
    result["builds"][index] = dict(
        sheet=sheet.hex(),
        equipment=proto_field(424, level).hex(),
        deck=deck.hex(),
        aptitudes=proto_field(24, level).hex(),
    )
    result["active_build_index"] = index
    result["effective_level"] = level
    result["dungeon_modulation"] = dict(
        context,
        policy_version=policy["version"],
        build_index=index,
        owned_active_build_index=owned_index,
        owned_effective_level=owned_level,
        effective_level=level,
        stats=profile_stats(level, policy),
    )
    return result


def hydrate(db, character):
    """Attach only a server-derived profile; lifecycle callers reconcile HP."""
    context = load_context(db, character)
    if context is None or not context["competitive"]:
        return character
    row = db.execute(
        "SELECT value FROM settings WHERE name=%s", (POLICY_NAME,)
    ).fetchone()
    if row is None:
        raise ValueError("Missing automatic dungeon modulation policy")
    result = project(character, context, row["value"])
    from wakfu_server.health_policy import visible

    maximum = effective_health_max(result)
    result["max_hp"] = maximum
    result["hp"] = visible(
        maximum,
        result["hp_damage"],
        result["health_dead"],
        result.get("hp_zero_valid", False),
    )
    return result


def bonus_stats(character, index):
    """Expose profile bonuses only for its trusted temporary selected sheet."""
    context = character.get("dungeon_modulation")
    if context is None or index != context["build_index"]:
        return {}
    return dict(context["stats"])


def effective_health_max(character):
    """Use the normal reducer for the temporary or restored owned profile."""
    from wakfu_server.equipment_stats import effective_character

    return effective_character(character)["max_hp"]
