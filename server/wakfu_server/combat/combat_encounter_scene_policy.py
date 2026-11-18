"""Source-bound room scene declarations projected onto actual fight actors."""

from copy import deepcopy
from hashlib import sha256
import json
from functools import lru_cache
from pathlib import Path


def _digest(record):
    return sha256(
        json.dumps(
            record, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _state_programs(descriptor):
    """Reject malformed authoring before an admitted fight is constructed."""
    programs = descriptor.get("state_programs", ())
    if type(programs) not in (list, tuple):
        raise ValueError("Malformed authored encounter state programs")
    for row in programs:
        if (
            type(row) is not dict
            or type(row.get("target_references")) is not list
            or not row["target_references"]
            or any(type(n) is not int or n <= 0 for n in row["target_references"])
            or len(set(row["target_references"])) != len(row["target_references"])
            or type(row.get("state_id")) is not int
            or row["state_id"] <= 0
            or type(row.get("level")) is not int
            or not 0 <= row["level"] <= 32767
            or type(row.get("protected")) is not bool
            or type(row.get("source_sha256")) is not str
            or len(row["source_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in row["source_sha256"])
        ):
            raise ValueError(
                "Encounter state program needs its flat native state declaration"
            )
    return programs


def prepare_scene(descriptor, *, scope, room_cells):
    """Freeze authoring data only after normal pinned-room encounter admission."""
    if descriptor is None:
        return None
    if (
        type(descriptor) is not dict
        or descriptor.get("schema_version") != 1
        or type(descriptor.get("full_room_scope")) is not bool
    ):
        raise ValueError("Invalid reviewed encounter scene schema")
    for key in ("policy_id", "authority", "source_uri"):
        if type(descriptor.get(key)) is not str or not descriptor[key].strip():
            raise ValueError("Encounter scene lacks source authority")
    _state_programs(descriptor)
    if "reviewed_cellless_casts" in descriptor:
        from .combat_scene_cellless_casting import declarations

        declarations(descriptor)
    if "controlled_state_programs" in descriptor:
        from .combat_scene_controlled_states import declarations

        declarations(descriptor)
    if descriptor.get("turn_end_order") is not None:
        from .combat_encounter_scene_turn_order import validate_declared_turn_order

        validate_declared_turn_order(descriptor["turn_end_order"])
    if descriptor.get("external_event_participants") is not None:
        from .combat_encounter_scene_external_participant import (
            validate_external_participants,
        )

        validate_external_participants(descriptor["external_event_participants"])
    if "native_border_reference" in descriptor:
        _native_border_reference(descriptor)
    if "native_boundary_failure" in descriptor:
        from .combat_scene_boundary_failure import declaration

        declaration(descriptor)
    if "native_escape_failure" in descriptor:
        from .combat_scene_triggered_failure import declaration

        declaration(descriptor)
    cells = sorted(set(tuple(cell) for cell in room_cells))
    if not cells or any(
        len(cell) != 3 or any(type(n) is not int for n in cell) for cell in cells
    ):
        raise ValueError("Encounter scene lacks exact native room terrain")
    if "box_goals" in descriptor:
        from .combat_scene_box_goals import declaration

        declaration(descriptor, cells)
    if "ball_goals" in descriptor:
        from .combat_scene_ball_goals import declaration

        declaration(descriptor, cells)
    if "native_movement_escape" in descriptor:
        from .combat_scene_movement_escape import declaration

        declaration(descriptor, cells)
    if type(scope) is not dict or any(
        type(scope.get(key)) is not int
        for key in ("map_id", "instance_id", "group_id", "room_order", "policy_version")
    ):
        raise ValueError("Encounter scene lacks an admitted group scope")
    if (
        type(scope.get("route_key")) is not str
        or type(scope.get("evidence_hashes")) is not dict
    ):
        raise ValueError("Encounter scene lacks pinned configuration evidence")
    glyphs = descriptor.get("native_initial_glyphs", ())
    if type(glyphs) not in (list, tuple):
        raise ValueError("Invalid authored initial glyph declarations")
    for glyph in glyphs:
        if (
            type(glyph) is not dict
            or type(glyph.get("reference")) is not int
            or glyph["reference"] <= 0
            or type(glyph.get("level")) is not int
            or glyph["level"] < 0
            or tuple(glyph.get("cell", ())) not in cells
        ):
            raise ValueError("Authored initial glyph leaves its native room")
    reserved = declared_spawn_cells(descriptor)
    if not reserved <= set(cells):
        raise ValueError("Authored native spawn reservation leaves its room")
    from .combat_fixed_actor_placement import declarations

    if declarations(descriptor, room_cells=cells) and not descriptor["full_room_scope"]:
        raise ValueError("Fixed actor scene requires its complete native room")
    if len({tuple(row["cell"]) for row in glyphs}) != len(glyphs):
        raise ValueError("Authored initial glyph positions overlap")
    result = dict(
        schema_version=1,
        descriptor=deepcopy(descriptor),
        scope=deepcopy(scope),
        room_cells=[list(cell) for cell in cells],
    )
    result["sha256"] = _digest(result)
    return result


def declared_spawn_cells(descriptor):
    """Reserve authored native birth slots during formation, not during play."""
    values = descriptor.get("native_initial_spawn_cells", ())
    if not isinstance(values, (list, tuple)) or any(
        not isinstance(cell, (list, tuple))
        or len(cell) != 3
        or any(type(value) is not int for value in cell)
        for cell in values
    ):
        raise ValueError("Invalid authored native spawn reservation")
    cells = frozenset(tuple(cell) for cell in values)
    if len(cells) != len(values):
        raise ValueError("Duplicate authored native spawn reservation")
    return cells


def _native_border_reference(descriptor):
    """Resolve an authored faP prototype; geometry remains the actual QI.P."""
    if "native_border_reference" not in descriptor:
        return None
    reference = descriptor["native_border_reference"]
    if type(reference) is not int or not 0 < reference < 2**31:
        raise ValueError("Invalid scene native border reference")
    from .combat_effect_area import native_effect_areas

    definition = native_effect_areas().get(str(reference))
    if (
        not isinstance(definition, dict)
        or definition.get("type") != "BATTLEGROUND_BORDER"
        or definition.get("native_class") != "bcF"
        or definition.get("raw_bdh") != []
    ):
        raise ValueError("Scene requires an original nonblocking faP prototype")
    return reference


def _verified(record):
    if (
        type(record) is not dict
        or set(record)
        != {"schema_version", "descriptor", "scope", "room_cells", "sha256"}
        or record.get("schema_version") != 1
        or record["sha256"]
        != _digest({key: value for key, value in record.items() if key != "sha256"})
    ):
        raise ValueError("Frozen encounter scene source changed")
    return record


def arena_scene(record, selected_arena, character, members):
    """Attach exact declarations without introducing NPCs or native geometry."""
    if record is None:
        return selected_arena
    record = _verified(record)
    descriptor, scope = record["descriptor"], record["scope"]
    if (
        selected_arena["map_id"] != scope["map_id"]
        or character["instance_id"] != scope["instance_id"]
    ):
        raise ValueError("Encounter scene arena changed admitted scope")
    selected = set(map(tuple, selected_arena["validated_cells"]))
    if descriptor["full_room_scope"] and selected != set(
        map(tuple, record["room_cells"])
    ):
        raise ValueError("Encounter scene must retain its complete native room")
    if any(
        tuple(glyph["cell"]) not in selected
        for glyph in descriptor.get("native_initial_glyphs", ())
    ):
        raise ValueError("Selected arena cropped an authored initial glyph")
    from .combat_environment_participant_footprints import participant_footprints

    footprint_members = [dict(member) for member in members]
    relocations = selected_arena.get("participant_positions", ())
    if relocations:
        if len(relocations) != len(footprint_members) or [
            tuple(pair[0]) for pair in relocations
        ] != [
            tuple(member[axis] for axis in ("x", "y", "z"))
            for member in footprint_members
        ]:
            raise ValueError("Encounter scene footprint relocation changed its roster")
        for member, (_, destination) in zip(footprint_members, relocations):
            member.update(zip(("x", "y", "z"), destination))
    from .combat_encounter_scene_layout import scene_player_position

    footprint_character = dict(character)
    if selected_arena.get("native_initial_player_relocation") is not None:
        footprint_character.update(
            zip(("x", "y", "z"), scene_player_position(character, selected_arena))
        )
    result = dict(
        selected_arena,
        native_encounter_scene=deepcopy(record),
        native_environment_participant_footprints=participant_footprints(
            footprint_character, footprint_members
        ),
    )
    for key in (
        "native_initial_glyphs",
        "native_initial_glyph_policy",
        "native_initial_glyph_authority",
        "native_initial_glyph_source_url",
    ):
        if key in descriptor:
            result[key] = deepcopy(descriptor[key])
    if descriptor.get("native_initial_glyphs"):
        for key, source in (
            ("native_initial_glyph_policy", "policy_id"),
            ("native_initial_glyph_authority", "authority"),
            ("native_initial_glyph_source_url", "source_uri"),
        ):
            if key not in result:
                value = descriptor[source]
                if key == "native_initial_glyph_policy" and not value.startswith(
                    "wakemu."
                ):
                    value = "wakemu." + value
                result[key] = value
    reference = _native_border_reference(descriptor)
    if reference is not None:
        from .combat_battleground_border import SUPPORTED_POLICIES

        if (
            result.get("native_border_policy") not in (None, *SUPPORTED_POLICIES)
            or result.get("native_emiw_border") is not None
            or result.get("native_encounter_scene_layout", {}).get("terrain_effect_id")
            is not None
        ):
            raise ValueError("Scene border conflicts with existing terrain authority")
        if result.get("native_border_policy") is None:
            from .combat_arena_selection import cardinal_border_cells
            from .combat_battleground_border import RECONSTRUCTED_POLICY
            from .combat_arena_empty_gaps import restored_gap_indices
            from .combat_wire import arena
            from .combat_qi_surface_catalog import native_qi_surfaces

            cells = result["validated_cells"]
            borders = cardinal_border_cells(cells)
            x, y, width = (result[key] for key in ("x", "y", "width"))
            indices = {
                (cx, cy): result["cell_masks"][(cy - y) * width + cx - x] & 63
                for cx, cy, _z in cells
            }
            placement = result["placement_cells"]
            if selected_arena.get("native_party_reserved_cells") is not None:
                from .combat_encounter_roles import role_assignment, roles_from_record
                from .combat_placement_policy import _party_reserved_cells
                from .combat_placement_footprints import covered_cells
                from .combat_placement_cells import generate
                from .combat_sn_path import NativeSnColumns
                from .combat_walk_surface_policy import (
                    native_player_point_placement_allowed,
                )

                role_record = result.get("native_encounter_roles")
                roles = (
                    role_assignment(
                        result["map_id"], [member["ref"] for member in members]
                    )
                    if role_record is None
                    else roles_from_record(role_record, map_id=result["map_id"])
                )
                player_team, npc_team = roles.player_team, roles.npc_team
                # Revalidate the producer before replacing the reservation
                # invalidated by this newly installed native perimeter.
                reserved = _party_reserved_cells(
                    selected_arena,
                    cells,
                    placement,
                    player_team,
                )
                if reserved & set(borders):
                    npc_cells = set(map(tuple, result["native_party_npc_cells"]))
                    origin = scene_player_position(character, result)
                    radius = next(
                        actor["physical_radius"]
                        for actor in result[
                            "native_environment_participant_footprints"
                        ]["actors"]
                        if actor["id"] == character["id"] and actor["reference"] is None
                    )
                    columns = NativeSnColumns.from_published(result["map_id"])
                    if (
                        columns.source_sha256
                        != result["native_qi_surface_provenance"]["source_sha256"]
                    ):
                        raise ValueError("Scene party placement native source changed")
                    opposing = set(placement[npc_team])
                    forbidden = set(borders) | npc_cells | opposing
                    bodies = {}
                    for center in cells:
                        try:
                            body = covered_cells(center, radius, cells)
                        except ValueError:
                            continue
                        if body & forbidden or not all(
                            native_player_point_placement_allowed(columns, cell)
                            for cell in body
                        ):
                            continue
                        bodies[center] = body
                    placement = generate(
                        cells,
                        result["valid_edges"],
                        {player_team: [origin], npc_team: sorted(opposing)},
                        slots_per_team=6,
                        team_capacities={
                            player_team: max(6, len(placement[player_team])),
                            npc_team: len(opposing),
                        },
                        occupied_cells=set(borders) | npc_cells,
                        avoid_cells=borders,
                        eligible_cells={player_team: set(bodies), npc_team: opposing},
                    )
                    occupied = set(npc_cells) | set(borders)
                    chosen = []
                    for center in sorted(
                        placement[player_team],
                        key=lambda cell: (
                            cell != origin,
                            abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]),
                            abs(cell[2] - origin[2]),
                            cell,
                        ),
                    ):
                        if bodies[center] & occupied:
                            continue
                        chosen.append(center)
                        occupied.update(bodies[center])
                        if len(chosen) == 6:
                            break
                    if len(chosen) != 6 or origin not in chosen:
                        raise ValueError(
                            "Native scene lacks safe party reservation capacity"
                        )
                    result["native_party_reserved_cells"] = [
                        list(cell) for cell in chosen
                    ]
            wire = arena(
                result["map_id"],
                result["instance_id"],
                sorted(cells),
                placement,
                obstacle_values=result.get("team_values"),
                surface_indices=indices,
                native_surfaces=native_qi_surfaces(result["map_id"]),
                border_cells=borders,
                gap_surface_indices=restored_gap_indices(
                    result["map_id"], cells, result
                ),
            )
            result.update(
                wire,
                placement_cells=placement,
                native_border_cells=borders,
                native_border_policy=RECONSTRUCTED_POLICY,
            )
        result["terrain_effect_id"] = reference
    return result


def bind_scene(fight, selected_arena, monsters):
    """Bind one sealed declaration to the actual initial roster before snapshots."""
    record = selected_arena.get("native_encounter_scene")
    if record is None:
        return None
    record = deepcopy(_verified(record))
    if getattr(fight, "native_encounter_scene", None) is not None:
        raise ValueError("Encounter scene was already frozen")
    from .combat_fixed_actor_placement import bind_initial_directions

    bind_initial_directions(fight, record["descriptor"], monsters)
    bindings = []
    for identity, monster in sorted(monsters.items()):
        actor = fight.actors.get(identity)
        if actor is None or actor.controlled or monster["id"] != identity:
            raise ValueError("Encounter scene requires actual initial NPC identities")
        bindings.append(
            dict(
                actor_id=identity,
                ref=monster["ref"],
                descriptor_level=actor.effective_level,
            )
        )
    record["scope"]["actor_bindings"] = bindings
    record["sha256"] = _digest(
        {key: value for key, value in record.items() if key != "sha256"}
    )
    fight.native_encounter_scene = record
    return frozen_scene(fight)


def frozen_scene(fight):
    """Return a fresh descriptor copy, or the unchanged legacy unscoped None."""
    record = getattr(fight, "native_encounter_scene", None)
    if record is None:
        return None
    record = _verified(record)
    from .combat_encounter_roles import assigned_roles

    if assigned_roles(fight).map_id != record["scope"]["map_id"]:
        raise ValueError("Frozen encounter scene belongs to another fight map")
    return deepcopy(record["descriptor"])


def scene_state_declarations(fight, monsters):
    """Resolve authored state programs against actual actor IDs and native levels."""
    descriptor = frozen_scene(fight)
    if descriptor is None:
        return ()
    record = _verified(fight.native_encounter_scene)
    result = []
    references = {binding["ref"] for binding in record["scope"]["actor_bindings"]}
    programs = _state_programs(descriptor)
    for program in programs:
        targets = program.get("target_references") if type(program) is dict else None
        if (
            type(targets) is not list
            or not targets
            or any(
                type(reference) is not int or reference <= 0 for reference in targets
            )
            or len(set(targets)) != len(targets)
            or not set(targets).issubset(references)
        ):
            raise ValueError(
                "Encounter state program lacks its actual initial recipients"
            )
    for binding in record["scope"]["actor_bindings"]:
        identity, reference = binding["actor_id"], binding["ref"]
        actor, monster = fight.actors.get(identity), monsters.get(identity)
        if (
            actor is None
            or monster is None
            or monster["ref"] != reference
            or actor.controlled
        ):
            raise ValueError("Encounter scene actor identity changed")
        if actor.effective_level != binding["descriptor_level"]:
            raise ValueError("Encounter scene descriptor level changed")
        states = []
        for program in programs:
            if reference not in program["target_references"]:
                continue
            state = {
                key: deepcopy(program[key])
                for key in ("state_id", "level", "protected", "source_sha256")
            }
            repeated = program.get("repeat_at_round_start")
            if repeated is not None:
                if (
                    type(repeated) is not dict
                    or repeated.get("event_id") != 1003
                    or repeated.get("channel") != 61
                ):
                    raise ValueError(
                        "Encounter scene round listener lacks native event authority"
                    )
                state["repeat_at_round_start"] = deepcopy(repeated["root_ids"])
            states.append(state)
        if states:
            result.append(
                dict(
                    binding,
                    policy_id=descriptor["policy_id"],
                    authority=descriptor["authority"],
                    source_uri=descriptor["source_uri"],
                    states=states,
                )
            )
    return tuple(result)


def scene_actor_binding(fight, actor, monsters):
    """Return a qualified initial NPC binding; newly born actors are unscoped."""
    if frozen_scene(fight) is None:
        return None
    record = _verified(fight.native_encounter_scene)
    rows = [
        row for row in record["scope"]["actor_bindings"] if row["actor_id"] == actor.id
    ]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("Duplicate frozen encounter scene actor")
    row, monster = rows[0], monsters.get(actor.id)
    if (
        fight.actors.get(actor.id) is not actor
        or monster is None
        or monster.get("id") != actor.id
        or monster.get("ref") != row["ref"]
        or actor.effective_level != row["descriptor_level"]
        or actor.controlled
    ):
        raise ValueError("Frozen encounter scene actor binding changed")
    return deepcopy(row)


_COMPATIBILITY_SHA256 = (
    "debc294bd56f002284454d430c2b766838eb90367e21ec568461e052e85c0af9"
)


@lru_cache(maxsize=1)
def _compatibility():
    raw = (
        Path(__file__)
        .with_name("native_encounter_scene_compatibility.json")
        .read_bytes()
    )
    if sha256(raw).hexdigest() != _COMPATIBILITY_SHA256:
        raise ValueError("Reviewed encounter scene compatibility source changed")
    data = json.loads(raw)
    if (
        data.get("schema_version") != 1
        or data.get("authority") != "authorized_wakemu_native_content_reconstruction"
        or type(data.get("records")) is not list
    ):
        raise ValueError("Invalid encounter scene compatibility catalog")
    return data["records"]


def compatible_room_scene(configuration, room):
    """Project only reviewed scene metadata onto an exact historical source pin.

    This never loads an active pointer, changes a run/catalog, moves an actor,
    or replays entry. Unmatched historical configurations keep their legacy path.
    """
    records = [
        record
        for record in _compatibility()
        if record["route_key"] == configuration["route"]["key"]
        and record["policy_version"] == configuration["version"]
    ]
    if not records:
        return None
    if len(records) != 1:
        raise ValueError("Ambiguous reviewed scene compatibility source")
    record = records[0]
    if (
        _digest(configuration) != record["configuration_sha256"]
        or configuration["evidence_hashes"]["plan"] != record["plan_sha256"]
        or configuration["compiled_plan"]["document_sha256"]
        != record["document_sha256"]
    ):
        raise ValueError("Historical encounter scene configuration source changed")
    matches = [row for row in record["rooms"] if row["room_order"] == room["order"]]
    if len(matches) != 1 or _digest(room) != matches[0]["room_sha256"]:
        raise ValueError("Historical encounter scene room source changed")
    return deepcopy(matches[0]["encounter_scene"])
