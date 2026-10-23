"""Require the current ordinary NPC contract before generating dungeon actors."""


def current_policy():
    """Read three indexed policy records, without decoding the effect catalog."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    path = DATA_ROOT / "native-npc-spell-effect-trees.json"
    return {
        key: native_catalog.record(path, "activation_policy", key)
        for key in ("schema", "legacy_spell_ids", "enabled_monsters")
    }


def admitted(policy, reference, minimum, maximum, *, native):
    """Check an entire selected grade interval; costs and criteria stay native.

    An empty action book is legitimate only through the existing source-qualified
    event controller. A species-pool entry, boss flag or level is not admission.
    """
    if (
        not isinstance(policy, dict)
        or policy.get("schema") != "native-npc-activation-v1"
        or not isinstance(policy.get("enabled_monsters"), dict)
        or type(reference) is not int
        or type(minimum) is not int
        or type(maximum) is not int
        or not 1 <= minimum <= maximum <= 32767
    ):
        raise ValueError("Invalid dungeon NPC admission authority")
    row = policy["enabled_monsters"].get(str(reference))
    if row is None:
        return False
    if (
        not isinstance(row, dict)
        or type(row.get("min_level")) is not int
        or type(row.get("max_level")) is not int
        or not 1 <= row["min_level"] <= row["max_level"] <= 32767
        or type(row.get("spell_ids")) is not list
        or any(type(spell) is not int or spell <= 0 for spell in row["spell_ids"])
    ):
        raise ValueError("Invalid dungeon NPC admission record")
    if not row["min_level"] <= minimum <= maximum <= row["max_level"]:
        return False
    abilities = native.get("native_abilities")
    if type(abilities) is not list or any(
        not isinstance(ability, dict) or type(ability.get("spell_id")) is not int
        for ability in abilities
    ):
        raise ValueError("Missing native dungeon NPC action book")
    if row["spell_ids"]:
        return bool(
            set(row["spell_ids"]) & {ability["spell_id"] for ability in abilities}
        )
    if abilities:
        return False
    from wakfu_server.combat_npc_event_controller import event_controller_record

    return all(
        event_controller_record(policy, reference, level) is not None
        for level in {minimum, maximum}
    )


def require(policy, reference, minimum, maximum, *, native):
    if not admitted(policy, reference, minimum, maximum, native=native):
        raise ValueError(
            f"Dungeon monster {reference} lacks ordinary NPC admission at {minimum}..{maximum}"
        )
