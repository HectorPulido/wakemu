"""Spell-specific gameplay oracles for recorded actual trap movement."""


def qualify_outcome(spell, details):
    if spell == 5182:
        if tuple(details["final_position"]) == tuple(details["requested_endpoint"]):
            raise AssertionError("Repulsion did not alter the movement endpoint")
        if not any(
            row.get("event") == "combat_effect"
            and row.get("effect_class") == 300
            and row.get("caster_id") == details["trap_uid"]
            and row.get("status") == "completed"
            for row in details["movement_trace"]
        ):
            raise AssertionError("Repulsion lacks completed trap-source displacement")
        return True, "repulsion_changed_requested_endpoint"
    if spell == 5183:
        if not (
            details["mover_hp_after"] < details["mover_hp_before"]
            or details["mover_armor_after"] < details["mover_armor_before"]
        ):
            raise AssertionError("Damage trap did not reduce mover HP or armor")
        return True, "damage_reduced_mover_hp_or_armor"
    if spell == 5184:
        return False, "paired_teleport_context_not_qualified"
    raise ValueError("Unsupported trap gameplay oracle")
