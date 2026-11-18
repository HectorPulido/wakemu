"""Qualified fixed scene constructors, distinct from generated world spawns.

The admitted scene already pins its native room, configuration and each fixed
constructor source. This does not relax physical terrain, actor dimensions,
overlap, movement costs or ordinary world formation policy.
"""


def complete_fixed_roster(record, members, *, helper_manifest=None):
    """Qualify fixed originals plus separately sealed initial scene helpers."""
    if record is None:
        return False
    from .combat_encounter_scene_policy import _verified
    from .combat_fixed_actor_placement import member_positions

    record = _verified(record)
    descriptor = record["descriptor"]
    if descriptor.get("full_room_scope") is not True or not descriptor.get(
        "fixed_actor_placements"
    ):
        return False
    positions = member_positions(descriptor, members, room_cells=record["room_cells"])
    if not members:
        return False
    if len(positions) == len(members):
        return True
    if helper_manifest is None:
        return False
    # Friendly initial actors have their own typed constructor and are placed
    # by adapt_helper_placement. They must not be mistaken for an uncovered
    # ordinary spawn, or acquire an invented fixed enemy anchor.
    from .combat_encounter_scene_helpers import validated_manifest

    source = validated_manifest(helper_manifest)
    scope = record["scope"]
    if (source["map_id"], source["instance_id"]) != (
        scope["map_id"],
        scope["instance_id"],
    ):
        raise ValueError("Fixed scene helper belongs to another admitted room")
    admission = source.get("mission_admission")
    if admission is not None and admission["room"] != scope["room_order"]:
        raise ValueError("Fixed scene helper belongs to another admitted stage")
    originals = {(row["id"], row["reference"]) for row in source["originals"]}
    helpers = {(row["actor_id"], row["reference"]) for row in source["helpers"]}
    actual = {(row["id"], row["ref"]) for row in members}
    fixed = {(members[index]["id"], members[index]["ref"]) for index in positions}
    return (
        len(actual) == len(members)
        and not originals & helpers
        and actual == originals | helpers
        and fixed == originals
    )


def npc_room_cells(fight, actor):
    """Retain the same source-qualified surface scope after actual admission.

    Only initial bound NPC identities inherit their fixed scene's room. Born
    summons, controlled actors and ordinary fights keep their native filters.
    The existing scene record survives the normal fight checkpoint lifecycle.
    """
    record = getattr(fight, "native_encounter_scene", None)
    if record is None or getattr(actor, "controlled", False):
        return frozenset()
    from .combat_encounter_scene_policy import _verified

    record = _verified(record)
    bindings = record["scope"].get("actor_bindings", ())
    if not isinstance(bindings, (list, tuple)) or not bindings:
        return frozenset()
    members = [dict(id=row["actor_id"], ref=row["ref"]) for row in bindings]
    if not complete_fixed_roster(
        record,
        members,
        helper_manifest=getattr(fight, "native_scene_helper_manifest", None),
    ):
        return frozenset()
    if sum(row["actor_id"] == actor.id for row in bindings) != 1:
        return frozenset()
    provenance = getattr(fight, "native_qi_surface_provenance", None)
    if (
        not isinstance(provenance, dict)
        or provenance.get("map_id") != record["scope"]["map_id"]
        or fight.actors.get(actor.id) is not actor
    ):
        raise ValueError("Fixed scene walking differs from its bound native actor/map")
    return frozenset(map(tuple, record["room_cells"])) & frozenset(fight.walkable)
