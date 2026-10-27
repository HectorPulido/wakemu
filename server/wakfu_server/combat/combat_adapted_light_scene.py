"""Explicit server-designed initial light zone for ordinary shadow henchmen.

The original841/10009 producer is unrecovered. This deliberately different
initial scene uses the proven neutral842 constructor and leaves3355 and its
original off-light cancellation untouched. It does not claim to restore the
original trap activation, timing or coordinates.
"""
POLICY = "wakemu.server-designed-initial-light842-v1"
AUTHORITY = "authorized_wakemu_adapted_initial_scene"


def prepare_adapted_light(
    character, members, arena, *, catalog=None, activation_policy=None
):
    references = tuple(member["ref"] for member in members)
    if not references or not set(references) <= {3530, 3531}:
        return arena
    from .combat_encounter_roles import ORDINARY_POLICY

    role = arena.get("native_encounter_roles")
    if (
        arena.get("native_initial_glyphs") is not None
        or arena.get("native_encounter_scene_layout") is not None
        or isinstance(role, dict)
        and role.get("policy") != ORDINARY_POLICY
    ):
        return arena
    if activation_policy is None:
        from .combat_npc_attack import npc_spell_catalog

        activation_policy = npc_spell_catalog().get("activation_policy", {})
    if activation_policy.get("schema") != "native-npc-activation-v1":
        raise ValueError("Missing actual shadow-henchman initialization authority")
    for reference in references:
        profile = activation_policy.get("enabled_monsters", {}).get(str(reference), {})
        raw = profile.get("initial_state_triples", ())
        if (
            not isinstance(raw, (list, tuple))
            or len(raw) % 3
            or not any(
                tuple(raw[index : index + 3]) == (3355, 1, 0)
                for index in range(0, len(raw), 3)
            )
        ):
            raise ValueError(
                "Adapted initial light requires actual native3355 ownership"
            )
    if catalog is None:
        from .combat_actor_snapshot import native_actor_catalog

        catalog = native_actor_catalog()
    from .combat_environment_participant_footprints import participant_footprints
    from .combat_obstacle_condition import footprint
    from .combat_arena_selection import _reachable

    if (
        character["map_id"] != arena["map_id"]
        or any(member.get("map_id") != character["map_id"] for member in members)
        or any(
            member.get("instance_id", 0) != character.get("instance_id", 0)
            for member in members
        )
    ):
        raise ValueError("Adapted initial light leaves its actual participant scope")
    facts = participant_footprints(character, members, catalog=catalog)
    occupied = {
        xy
        for row in facts["actors"]
        for xy in footprint(row["position"], row["physical_radius"])
    }
    cells, edges = set(arena["validated_cells"]), set(arena["valid_edges"])
    reachable = set(cells)
    for row in facts["actors"]:
        origin = tuple(row["position"])
        if origin not in cells:
            raise ValueError("Shadow-henchman participant leaves native terrain")
        reachable.intersection_update(_reachable(origin, cells, edges))
    border = {tuple(cell[:2]) for cell in arena.get("native_border_cells", ())}
    cx = min(cell[0] for cell in cells) + max(cell[0] for cell in cells)
    cy = min(cell[1] for cell in cells) + max(cell[1] for cell in cells)
    candidates = []
    for cell in reachable:
        x, y, z = cell
        # Exact native anu circle3, independently qualified against prototype842.
        shape = {
            (x + dx, y + dy, z)
            for dx in range(-3, 4)
            for dy in range(-3, 4)
            if abs(dx) + abs(dy) <= 3
        }
        if not shape <= reachable or {point[:2] for point in shape} & (
            occupied | border
        ):
            continue
        candidates.append((abs(2 * x - cx) + abs(2 * y - cy), cell))
    if not candidates:
        raise ValueError("Native terrain cannot fit the adapted initial light circle")
    _distance, cell = min(candidates)
    return dict(
        arena,
        native_initial_glyphs=[dict(reference=842, cell=list(cell), level=0)],
        native_initial_glyph_policy=POLICY,
        native_initial_glyph_authority=AUTHORITY,
        native_initial_glyph_source_url="wakemu:server-designed-initial-light842-v1",
        native_environment_participant_footprints=facts,
    )
