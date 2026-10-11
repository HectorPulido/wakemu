"""Scope newly imported NPC spells without changing native ownership."""


def imports_enabled(policy, monster_ref, actor_level, spell):
    if policy is None:
        return True
    if (
        not isinstance(policy, dict)
        or policy.get("schema") != "native-npc-activation-v1"
        or not isinstance(policy.get("legacy_spell_ids"), list)
        or any(type(s) is not int for s in policy["legacy_spell_ids"])
        or not isinstance(policy.get("enabled_monsters"), dict)
    ):
        raise ValueError("Invalid native NPC activation policy")
    record = policy["enabled_monsters"].get(str(monster_ref))
    if record is not None:
        if (
            not isinstance(record, dict)
            or type(record.get("min_level")) is not int
            or type(record.get("max_level")) is not int
            or not 1 <= record["min_level"] <= record["max_level"]
            or not isinstance(record.get("spell_ids"), list)
            or any(type(s) is not int for s in record["spell_ids"])
        ):
            raise ValueError("Invalid native NPC activation range")
        return (
            record["min_level"] <= actor_level <= record["max_level"]
            and spell in record["spell_ids"]
        )
    return False
