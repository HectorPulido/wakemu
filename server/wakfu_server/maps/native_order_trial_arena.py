"""Build an order-trial battleground from pinned floor and native QI sources."""


def prepare(scoped, character, proof):
    """Keep the accepted mode approach and derive every QI index from Vy."""
    from wakfu_server import combat_terrain, native_order_trial_context
    from wakfu_server.combat_qi_surface_selection import native_surface_indices
    from wakfu_server.combat_wire import arena
    from wakfu_server.combat_environment_participant_footprints import (
        participant_footprints,
    )
    from wakfu_server.native_order_trial_admission import Admission, digest

    if (
        not isinstance(proof, Admission)
        or proof.mode not in ("normal", "hard")
        or proof.owner_id != character["id"]
        or proof.account_id != character["account_id"]
        or proof.instance_id != character["instance_id"]
        or proof.source_map_id != character["map_id"]
        or character["instance_id"] <= 0
    ):
        raise ValueError("Order arena requires the authenticated native mode owner")
    configuration = scoped["configuration"]
    geometry = native_order_trial_context.geometry(configuration)
    policy = native_order_trial_context.policy(configuration)
    if (
        policy != scoped["policy"]
        or geometry["map_id"] != character["map_id"]
        or proof.profile_sha256
        != digest(native_order_trial_context.admission(configuration))
    ):
        raise ValueError("Order arena differs from its authenticated owned context")
    mode = geometry["mode_approaches"][proof.mode]
    hero = tuple(character[key] for key in ("x", "y", "z"))
    if proof.source_id != mode["source_id"] or list(hero) not in mode["approach_cells"]:
        raise ValueError("Order arena lost its actual accepted button approach")
    floor = geometry["battle_floor"]
    cells = frozenset(map(tuple, floor["cells"]))
    edges = frozenset(tuple(map(tuple, edge)) for edge in floor["native_edges"])
    prepared = combat_terrain.prepare_terrain(character["map_id"])
    if (
        prepared.provenance["source_sha256"]
        != geometry["source_hashes"][
            f"client/contents/maps/tplg/{character['map_id']}.jar"
        ]
        or not cells <= prepared.geometry.cells
        or edges
        != frozenset(
            edge
            for edge in prepared.geometry.edges
            if edge[0] in cells and edge[1] in cells
        )
    ):
        raise ValueError("Order arena differs from its original native battleground")
    spawn = tuple(
        geometry["reviewed_arcade_layout"][proof.mode]["reviewed_spawn_anchor"]
    )
    if hero not in cells or spawn not in cells or hero == spawn:
        raise ValueError("Order arena lacks distinct native deployment cells")
    indices = native_surface_indices(prepared.surfaces, cells)
    gaps = combat_terrain.selected_gap_indices(
        character["map_id"], cells, combat_terrain.EMPTY_GAP_POLICY
    )
    placement = {1: {hero}, 0: {spawn}}
    result = arena(
        character["map_id"],
        1,
        sorted(cells),
        placement,
        surface_indices=indices,
        native_surfaces=prepared.surfaces,
        gap_surface_indices=gaps,
    )
    result.update(
        native_order_instance_id=character["instance_id"],
        validated_cells=cells,
        valid_edges=edges,
        placement_cells=placement,
        native_qi_surface_provenance=prepared.provenance,
        native_environment_participant_footprints=participant_footprints(character, ()),
        native_full_room_scope=True,
        native_los_gap_policy=combat_terrain.EMPTY_GAP_POLICY,
        native_los_gap_surfaces=[
            [x, y, index] for (x, y), index in sorted(gaps.items())
        ],
        native_border_cells=frozenset(),
        native_border_policy=None,
    )
    return result
