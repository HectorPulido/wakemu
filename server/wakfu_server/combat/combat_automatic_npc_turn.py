"""Explicit Wakemu end-only authority for ordinary roots lacking a controller.

This policy never changes fqL, grants an attack, or admits a turnless actor.
Only the complete native turn boundary may consume this constructor authority.
"""

SOURCE = "wakemu.ordinary_root_automatic_turn_end.v1"


def initial_root_manifest(fight, monsters):
    """Preflight immutable operands of the actual ordinary NPC constructor."""
    result = {}
    for identity, monster in monsters.items():
        actor = fight.actors.get(identity)
        if (
            type(identity) is not int
            or identity == 0
            or actor is None
            or actor.id != identity
            or actor.controlled
            or actor.owner_id is not None
            or getattr(actor, "native_summon_source", None) is not None
            or identity in getattr(fight, "native_summon_registrations", {})
            or monster.get("id") != identity
            or type(monster.get("ref")) is not int
            or monster["ref"] <= 0
            or type(actor.effective_level) is not int
            or not 0 <= actor.effective_level <= 32767
        ):
            raise ValueError("Invalid fresh ordinary root turn authority")
        result[str(identity)] = dict(
            source=SOURCE,
            actor_id=identity,
            reference=monster["ref"],
            level=actor.effective_level,
        )
    return result


def install_root_manifest(fight, manifest):
    """Install only a preflighted new roster; checkpoint copies retain provenance."""
    current = getattr(fight, "native_ordinary_npc_turn_roots", {})
    if not isinstance(current, dict) or not isinstance(manifest, dict):
        raise ValueError("Invalid ordinary root turn manifest")
    if set(current) & set(manifest):
        raise ValueError("Ordinary root turn authority already installed")
    for key, row in manifest.items():
        if (
            not isinstance(row, dict)
            or row.get("source") != SOURCE
            or type(row.get("actor_id")) is not int
            or key != str(row["actor_id"])
            or row["actor_id"] not in fight.actors
            or type(row.get("reference")) is not int
            or row["reference"] <= 0
            or type(row.get("level")) is not int
            or not 0 <= row["level"] <= 32767
        ):
            raise ValueError("Missing ordinary root constructor provenance")
    fight.native_ordinary_npc_turn_roots = {
        **current,
        **{key: dict(row) for key, row in manifest.items()},
    }


def requires_automatic_npc_turn_end(fight, actor):
    """Return end-only authority for the actual unowned, non-AI current root."""
    if (
        actor is None
        or fight.phase != "active"
        or fight.actors.get(actor.id) is not actor
        or fight.current is not actor
        or actor.controlled
        or actor.owner_id is not None
        or actor.hp <= 0
        or getattr(actor, "native_controlled_by_ai", None) is not False
        or getattr(actor, "native_summon_source", None) is not None
        or actor.id in getattr(fight, "native_summon_registrations", {})
    ):
        return False
    manifest = getattr(fight, "native_ordinary_npc_turn_roots", None)
    if manifest is None:
        return False  # Unattested older snapshots never acquire new authority.
    if not isinstance(manifest, dict):
        raise ValueError("Invalid ordinary root turn manifest")
    row = manifest.get(str(actor.id))
    if row is None:
        return False
    if (
        not isinstance(row, dict)
        or row.get("source") != SOURCE
        or row.get("actor_id") != actor.id
        or type(row.get("reference")) is not int
        or row["reference"] <= 0
        or type(row.get("level")) is not int
        or row.get("level") != actor.effective_level
    ):
        raise ValueError("Missing ordinary root turn provenance")
    from .combat_property_stack import property_present
    from .combat_controller_registry import _row
    from .combat_global_pv_collections import global_fighter_participates
    from .combat_timeline_snapshot import counters
    from .combat_qi_fight import current_registry

    counts = getattr(actor, "native_fight_property_counts", None)
    if counts is None:
        raise ValueError("Missing ordinary root property authority")
    if property_present(counts, 114):
        return False
    controller = _row(fight, actor.id)
    if (
        controller["original_controller"] != actor.id
        or controller["current_controller"] != actor.id
        or not global_fighter_participates(fight, actor.id)
    ):
        return False
    if actor.id not in fight.order or str(actor.id) not in counters(fight):
        raise ValueError("Missing ordinary root native timeline membership")
    registry = current_registry(fight)
    slot = getattr(actor, "native_obstacle_id", None)
    if (
        type(slot) is not int
        or not 0 <= slot < len(registry.slots)
        or registry.slots[slot] is None
        or registry.slots[slot].get("identity") != ["actor", actor.id]
    ):
        raise ValueError("Missing ordinary root QI turn authority")
    return True
