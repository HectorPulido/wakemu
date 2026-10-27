"""Install explicit reconstructed encounter placement before durable admission."""
import copy


def _apply_team_roles(character, members, selected_arena):
    from wakfu_server.combat_encounter_roles import (
        role_assignment,
        roles_from_record,
    )

    references = [member["ref"] for member in members]
    prior = selected_arena.get("native_encounter_roles")
    if prior is not None:
        # A selected admission keeps its immutable version across pointer changes.
        roles_from_record(
            prior, map_id=character["map_id"], monster_references=references
        )
        return selected_arena
    roles = role_assignment(character["map_id"], references)
    return apply_role_assignment(selected_arena, roles)


def apply_role_assignment(selected_arena, roles):
    """Project one reviewed role record onto the existing native surfaces."""
    from wakfu_server.combat_encounter_roles import (
        EncounterRoles,
        ORDINARY_POLICY,
        roles_from_record,
    )

    if (
        not isinstance(roles, EncounterRoles)
        or roles_from_record(roles.record(), map_id=selected_arena["map_id"]) != roles
    ):
        raise ValueError("Reviewed role assignment for this native arena required")
    prior = selected_arena.get("native_encounter_roles")
    if prior is not None:
        if roles_from_record(prior, map_id=selected_arena["map_id"]) != roles:
            raise ValueError(
                "Selected native arena already has another role assignment"
            )
        return selected_arena
    if roles.policy == ORDINARY_POLICY:
        # Scoped ordinary encounters also need optional policy admission before
        # Ready. Their existing team flags, wire and geometry remain untouched.
        return dict(selected_arena, native_encounter_roles=roles.record())
    from .combat_wire import arena

    cells = selected_arena["validated_cells"]
    placement = roles.placement_cells(
        selected_arena["placement_cells"][0],
        selected_arena["placement_cells"][1],
    )
    # Preserve the exact already-selected surfaces while regenerating the
    # placement flags with the reviewed native team identities.
    x, y, width = (selected_arena[key] for key in ("x", "y", "width"))
    indices = {
        (cx, cy): selected_arena["cell_masks"][(cy - y) * width + cx - x] & 63
        for cx, cy, _z in cells
    }
    from .combat_arena_empty_gaps import restored_gap_indices

    wire = arena(
        selected_arena["map_id"],
        selected_arena["instance_id"],
        sorted(cells),
        placement,
        obstacle_values=selected_arena.get("team_values"),
        surface_indices=indices,
        border_cells=selected_arena.get("native_border_cells", ()),
        gap_surface_indices=restored_gap_indices(
            selected_arena["map_id"], cells, selected_arena
        ),
    )
    result = dict(selected_arena)
    result.update(
        wire, placement_cells=placement, native_encounter_roles=roles.record()
    )
    return result


def resolve_layout(character, members, *, geometry_loader=None):
    if not members:
        return None
    from .combat_supreme_scene_policies import (
        policy_for_reference,
        resolve_supreme_scene,
    )

    matches = []
    for member in members:
        reference = member.get("ref")
        policy = policy_for_reference(reference)
        rushu = reference == 5306 and character.get("map_id") == 1332
        if rushu or (
            policy is not None and character.get("map_id") == policy["map_id"]
        ):
            matches.append((reference, policy, rushu))
    if not matches:
        return None
    if len(members) != 1:
        raise ValueError("Reconstructed placement requires its declared singleton")
    reference, policy, rushu = matches[0]
    if geometry_loader is None:
        from .combat_geometry import published_geometry

        geometry_loader = published_geometry
    if not rushu:
        return resolve_supreme_scene(reference, geometry_loader(policy["map_id"]))
    from .combat_rushu_scene_layout import reconstructed_scene

    return reconstructed_scene(geometry_loader(1332))


def prepare_encounter_scene(character, members, selected_arena, *, layout=None):
    """Keep authoritative world origins while selecting separate fight positions."""
    members = list(members)
    if layout is None:
        layout = resolve_layout(character, members)
    if layout is None:
        result = (
            _apply_team_roles(character, members, selected_arena)
            if members
            else selected_arena
        )
        from .combat_emiw_scene_policy import prepare_emiw_border
        from .combat_security_scene_policy import prepare_security_glyphs
        from .combat_adapted_light_scene import prepare_adapted_light

        return prepare_adapted_light(
            character,
            members,
            prepare_security_glyphs(character, members, prepare_emiw_border(result)),
        )
    if (
        character.get("map_id") != layout["map_id"]
        or selected_arena.get("map_id") != layout["map_id"]
        or any(m.get("map_id") != layout["map_id"] for m in members)
        or any(
            m.get("instance_id", 0) != character.get("instance_id", 0) for m in members
        )
        or len(members) != 1
    ):
        raise ValueError("Reconstructed encounter participant scope changed")
    cells, edges = set(layout["cells"]), set(layout["edges"])
    anchor, source = tuple(layout["anchor"]), tuple(layout["source"])
    party = {tuple(cell) for cell in layout["party_placement_cells"]}
    footprint = {tuple(cell) for cell in layout["boss_footprint"]}
    if (
        not party <= cells
        or not footprint <= cells
        or anchor not in party
        or party & footprint
    ):
        raise ValueError("Invalid reconstructed encounter placement authority")
    if any(start not in cells or end not in cells for start, end in edges):
        raise ValueError("Reconstructed encounter edges leave the native room")
    border_cells = {tuple(cell) for cell in layout.get("native_border_cells", ())}
    border_policy = layout.get("native_border_policy")
    reserved = (
        party | footprint | {tuple(cell) for cell in layout.get("glyph_cells", ())}
    )
    if (
        not border_cells <= cells
        or border_cells & reserved
        or (border_cells and border_policy is None)
    ):
        raise ValueError("Reconstructed encounter border overlaps its declared scene")
    scope = layout.get("native_border_scope_cells")
    from .combat_battleground_border import DECLARED_COMPONENT_POLICY

    if scope is None and border_policy == DECLARED_COMPONENT_POLICY:
        raise ValueError("Missing declared encounter border component")
    if scope is not None:
        from .combat_battleground_border import validate_border_component
        from .combat_arena_selection import cardinal_border_cells

        scope = validate_border_component(cells, edges, scope)
        if (
            border_policy != DECLARED_COMPONENT_POLICY
            or not party <= scope
            or border_cells != cardinal_border_cells(scope)
        ):
            raise ValueError("Invalid declared encounter border component")
    from .combat_qi_surface_catalog import (
        native_qi_surfaces,
        native_qi_surface_provenance,
    )
    from .combat_qi_surface_selection import native_surface_indices
    from .combat_wire import arena

    gap_policy = layout.get("native_los_gap_policy")
    gap_indices = None
    if gap_policy is not None:
        from .combat_arena_empty_gaps import selected_gap_indices

        gap_indices = selected_gap_indices(layout["map_id"], cells, gap_policy)

    result = arena(
        layout["map_id"],
        selected_arena["instance_id"],
        sorted(cells),
        {0: party, 1: {source}},
        surface_indices=native_surface_indices(
            native_qi_surfaces(layout["map_id"]), cells
        ),
        border_cells=border_cells,
        gap_surface_indices=gap_indices,
    )
    metadata = {
        key: copy.deepcopy(layout.get(key, ()))
        for key in (
            "policy",
            "authority",
            "observation_url",
            "original_world_coordinates",
            "map_id",
            "source",
            "caster_cell",
            "anchor",
            "glyph_cells",
            "party_placement_cells",
            "boss_footprint",
        )
    }
    direction = layout.get("boss_direction", 3)
    if type(direction) is not int or not 0 <= direction <= 7:
        raise ValueError("Invalid reconstructed boss facing")
    metadata["boss_direction"] = direction
    terrain_effect = layout.get(
        "terrain_effect_id", selected_arena.get("terrain_effect_id", 46)
    )
    if type(terrain_effect) is not int or not 0 < terrain_effect < 2**31:
        raise ValueError("Invalid reconstructed encounter terrain reference")
    if "terrain_effect_id" in layout:
        metadata["terrain_effect_id"] = terrain_effect
    if gap_policy is not None:
        metadata["native_los_gap_policy"] = gap_policy
    # Persist only plain policy facts; terrain is already frozen independently.
    for key in ("source", "caster_cell", "anchor"):
        metadata[key] = list(metadata[key])
    for key in ("glyph_cells", "party_placement_cells", "boss_footprint"):
        metadata[key] = [list(cell) for cell in metadata[key]]
    result.update(
        terrain_effect_id=terrain_effect,
        validated_cells=cells,
        valid_edges=edges,
        placement_cells={0: party, 1: {source}},
        participant_positions=[
            ((members[0]["x"], members[0]["y"], members[0]["z"]), source)
        ],
        participant_player_position=(
            (character["x"], character["y"], character["z"]),
            anchor,
        ),
        native_encounter_scene_layout=metadata,
        native_qi_surface_provenance=native_qi_surface_provenance(layout["map_id"]),
        native_border_cells=frozenset(border_cells),
        native_border_policy=border_policy,
    )
    if scope is not None:
        result["native_border_scope_cells"] = scope
    if gap_policy is not None:
        result.update(
            native_los_gap_policy=gap_policy,
            native_los_gap_surfaces=[
                [x, y, index] for (x, y), index in sorted(gap_indices.items())
            ],
        )
    glyph_keys = (
        "native_initial_glyphs",
        "native_initial_glyph_policy",
        "native_initial_glyph_authority",
        "native_initial_glyph_source_url",
    )
    if any(key in layout for key in glyph_keys):
        if not all(key in layout for key in glyph_keys):
            raise ValueError("Incomplete declared initial glyph authority")
        glyphs = layout["native_initial_glyphs"]
        if not isinstance(glyphs, (list, tuple)) or any(
            not isinstance(layout[key], str) or not layout[key]
            for key in glyph_keys[1:]
        ):
            raise ValueError("Invalid declared initial glyph policy")
        seen = set()
        for glyph in glyphs:
            if (
                not isinstance(glyph, dict)
                or not {"reference", "cell"} <= glyph.keys()
                or set(glyph) - {"reference", "cell", "level", "activation"}
                or type(glyph["reference"]) is not int
                or glyph["reference"] <= 0
                or not isinstance(glyph["cell"], (list, tuple))
                or len(glyph["cell"]) != 3
                or any(type(v) is not int for v in glyph["cell"])
                or tuple(glyph["cell"]) not in cells
                or type(glyph.get("level", 0)) is not int
                or glyph.get("level", 0) < 0
            ):
                raise ValueError("Invalid declared initial glyph placement")
            from .combat_scene_area_activation import validate_scene_activation

            validate_scene_activation(
                glyph.get("activation"), reference=glyph["reference"]
            )
            identity = (glyph["reference"], tuple(glyph["cell"]))
            if identity in seen:
                raise ValueError("Duplicate declared initial glyph")
            seen.add(identity)
        result.update({key: copy.deepcopy(layout[key]) for key in glyph_keys})
        result["native_initial_glyphs"] = [
            dict(copy.deepcopy(glyph), cell=list(glyph["cell"])) for glyph in glyphs
        ]
    return _apply_team_roles(character, members, result)


def scene_player_position(character, arena):
    original = (character["x"], character["y"], character["z"])
    relocation = arena.get("participant_player_position")
    if relocation is None:
        return original
    scene = arena.get("native_encounter_scene_layout")
    from wakfu_server.combat_encounter_roles import roles_from_record

    record = arena.get("native_encounter_roles")
    player_team = 0 if record is None else roles_from_record(record).player_team
    if (
        not isinstance(scene, dict)
        or len(relocation) != 2
        or tuple(relocation[0]) != original
        or tuple(relocation[1]) != tuple(scene["anchor"])
        or tuple(relocation[1]) not in arena["placement_cells"][player_team]
    ):
        raise ValueError("Reconstructed player placement differs from its world origin")
    return tuple(relocation[1])
