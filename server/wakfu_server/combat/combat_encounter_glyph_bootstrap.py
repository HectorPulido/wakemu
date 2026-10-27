"""Declared neutral area constructors, independent of effect315.

The scene policy supplies positions and original prototype references. Native
bcT definitions still own geometry, properties, effects and event masks. Entity
UIDs belong to the server's initial PV namespace, not to a fabricated Qe.
"""
import struct

from .combat_obstacle_condition import footprint

SOURCE = "buK.cvb.myK.fec.fbm.null_owner.faY"
TRAP_SOURCE = "buK.cvb.myK.fec.fbm.null_owner.fbc"


def validate_environment_prototype(definition, *, level):
    """Validate the actual subtype selected by buK's initial area carrier."""
    if definition.get("type") != "TRAP":
        validate_glyph_prototype(definition, level=level)
        return
    from .combat_trap_area import trap_constructor

    trap_constructor(definition)
    maximum = definition.get("maximum_level")
    if (
        definition.get("native_shape_class") != "anD"
        or definition.get("shape_parameters") != []
        or definition.get("native_shape_description") != "point"
        or definition.get("native_hour_contract") is not False
        or definition.get("raw_bdf") != 0
        or definition.get("raw_bdg") != []
        or 12 in definition.get("native_area_properties", ())
        or type(definition.get("raw_bde")) is not int
        or type(maximum) is not int
        or type(level) is not int
        or not 0 <= level <= maximum
    ):
        raise ValueError("Unsupported native neutral fbc prototype")


def validate_glyph_prototype(definition, *, level):
    """Admit native isotropic glyphs without changing the point contract.

    Directed shapes need a separate source for their orientation. The scene
    codec retains the native null-owner direction -1, so only published point,
    circle and cross forms whose geometry is independent of facing are admitted.
    """
    if definition.get("native_shape_class") == "anD":
        validate_point_prototype(definition, level=level)
        return
    shape, parameters = (
        definition.get(key) for key in ("native_shape_class", "shape_parameters")
    )
    description = definition.get("native_shape_description")
    maximum = definition.get("maximum_level")
    if (
        definition.get("type") != "GLYPH"
        or definition.get("native_class") != "bcT"
        or shape not in ("anu", "anw")
        or not isinstance(parameters, list)
        or len(parameters) != 1
        or type(parameters[0]) is not int
        or not 0 <= parameters[0] < (1 << 31)
        or description
        != (
            f"circle-{parameters[0]}"
            if shape == "anu"
            else f"cross-h{parameters[0]}b{parameters[0]}-g{parameters[0]}d{parameters[0]}"
        )
        or definition.get("raw_bdh") != []
        or definition.get("raw_bdf") != 0
        or definition.get("raw_bdg") != []
        or definition.get("native_type_id") != 0
        or definition.get("native_container_type") != 3
        or definition.get("native_hour_contract") is not False
        or 12 in definition.get("native_area_properties", ())
        or type(maximum) is not int
        or type(level) is not int
        or not 0 <= level <= maximum
        or type(definition.get("raw_bde")) is not int
    ):
        raise ValueError("Unsupported native neutral faY prototype")


def glyph_cells(source, definition):
    """Return complete native geometry, never clipped to the arena or actors."""
    from .combat_effect_area_geometry import registered_area_cells

    validate_environment_prototype(definition, level=source.get("level", 0))
    return registered_area_cells(
        definition, tuple(source["cell"]), -1, reference=(0, 0, 0)
    )


def validate_point_prototype(definition, *, level):
    """Restrict the bootstrap codec to the audited neutral point constructor."""
    maximum = definition.get("maximum_level")
    if (
        definition.get("type") != "GLYPH"
        or definition.get("native_class") != "bcT"
        or definition.get("native_shape_class") != "anD"
        or definition.get("shape_parameters") != []
        or definition.get("raw_bdh") != []
        or definition.get("raw_bdf") != 0
        or definition.get("raw_bdg") != []
        or definition.get("native_type_id") != 0
        or definition.get("native_container_type") != 3
        or definition.get("native_hour_contract") is not False
        or 12 in definition.get("native_area_properties", ())
        or type(maximum) is not int
        or type(level) is not int
        or not 0 <= level <= maximum
    ):
        raise ValueError("Unsupported native neutral point faY prototype")


def prepare_declared_glyphs(fight, arena, terrain_identity, definitions):
    """Validate the whole scene declaration before publishing constructors."""
    declarations = arena.get("native_initial_glyphs")
    if declarations is None:
        return None
    policy = arena.get("native_initial_glyph_policy")
    authority = arena.get("native_initial_glyph_authority")
    source_url = arena.get("native_initial_glyph_source_url", "")
    if (
        not isinstance(declarations, list)
        or not declarations
        or not isinstance(policy, str)
        or not policy.startswith("wakemu.")
        or not isinstance(authority, str)
        or not authority
        or not isinstance(source_url, str)
        or type(terrain_identity) is not int
        or not len(declarations) < terrain_identity < (1 << 63)
        or getattr(fight, "native_environment_glyphs_installed", False)
    ):
        raise ValueError("Missing declared native glyph constructor authority")
    occupied = set()
    layout = arena.get("native_encounter_scene_layout", {})
    from wakfu_server.combat_encounter_roles import assigned_roles
    from .combat_environment_participant_footprints import verified_participant_cells

    roles = assigned_roles(fight)
    initial_occupied = verified_participant_cells(fight, arena)
    if initial_occupied is not None:
        occupied.update(initial_occupied)
    for actor in () if initial_occupied is not None else fight.actors.values():
        if actor.hp <= 0:
            continue
        if actor.physical_radius is not None:
            occupied.update(footprint(actor.position, actor.physical_radius))
            continue
        # create_placement precedes initialize_fight_snapshots. At this
        # boundary the selected native scene, not an invented radius0, owns
        # the boss footprint and all reserved party positions.
        if actor.team not in (roles.player_team, roles.npc_team):
            raise ValueError("Declared glyph participant has no encounter role")
        key = (
            "party_placement_cells"
            if actor.team == roles.player_team
            else "boss_footprint"
        )
        reserved = {tuple(cell) for cell in layout.get(key, ())}
        if tuple(actor.position) not in reserved or not reserved <= fight.walkable:
            raise ValueError("Missing pre-snapshot native scene footprint authority")
        occupied.update(cell[:2] for cell in reserved)
    border = arena.get("native_border_cells", getattr(fight, "native_border_cells", ()))
    forbidden = {(cell[0], cell[1]) for cell in border}
    forbidden.update(occupied)
    result, used_cells = [], set()
    for index, declaration in enumerate(declarations):
        if not isinstance(declaration, dict) or set(declaration) - {
            "reference",
            "cell",
            "level",
            "activation",
        }:
            raise ValueError("Invalid declared native glyph fields")
        reference, raw_cell = declaration.get("reference"), declaration.get("cell")
        level = declaration.get("level", 0)
        if (
            type(reference) is not int
            or reference <= 0
            or not isinstance(raw_cell, (tuple, list))
            or len(raw_cell) != 3
            or any(type(value) is not int for value in raw_cell)
        ):
            raise ValueError("Invalid declared native glyph reference/cell")
        cell = tuple(raw_cell)
        if (
            cell not in fight.walkable
            or cell[:2] in forbidden
            or cell[:2] in used_cells
        ):
            raise ValueError("Declared native glyph cell is unavailable")
        definition = definitions.get(str(reference), {})
        validate_environment_prototype(definition, level=level)
        from .combat_scene_area_activation import validate_scene_activation

        activation = declaration.get("activation")
        validate_scene_activation(activation, reference=reference)
        if activation is not None and (definition["type"] != "TRAP" or not source_url):
            raise ValueError("Missing declared scene trap activation provenance")
        identity = terrain_identity - index - 1
        if identity in fight.actors or identity in fight.native_effect_areas:
            raise ValueError("Declared native glyph PV identity collision")
        used_cells.add(cell[:2])
        result.append(
            dict(
                uid=identity,
                reference=reference,
                cell=cell,
                level=level,
                policy=policy,
                source=TRAP_SOURCE if definition["type"] == "TRAP" else SOURCE,
                authority=authority,
                source_url=source_url,
            )
        )
        if activation is not None:
            result[-1]["activation"] = dict(activation)
    return result


def point_glyph_row(source, definition):
    """Materialize the unchanged null-owner Qq/fbm/faY constructor fields."""
    cell = tuple(source["cell"])
    return dict(
        uid=source["uid"],
        reference=source["reference"],
        cell=cell,
        level=source.get("level", 0),
        owner_id=None,
        direction=-1,
        keep_after=False,
        native_hour_contract=False,
        native_area_contract="faY",
        native_qq_bhi=False,
        native_qq_guard_source="Qq.constructor",
        native_obstacle_id=-1,
        native_obstacle_source="fbm.constructor",
        native_type_id=definition["native_type_id"],
        native_removal_masks=(),
        native_cells_xy=(cell[:2],),
        native_geometry_reference=(0, 0, 0),
        native_geometry_reference_source="Qq.bcT.bcU_bcV_bcW",
        remaining_activations=definition["raw_bde"],
        native_running_effect_manager=False,
        child_effect_uids={},
        executing=False,
        native_fight_affiliation=-1,
        native_fight_affiliation_source="faV.constructor.null_owner",
        native_environment_source=source["source"],
        native_environment_policy=source["policy"],
    )


def glyph_row(source, definition):
    """Keep the subtype constructor and install its full native shape."""
    row = point_glyph_row(source, definition)
    row["native_cells_xy"] = glyph_cells(source, definition)
    if definition["type"] == "TRAP":
        from .combat_trap_area import install_trap_characteristics

        row["native_area_contract"] = "fbc"
        install_trap_characteristics(row, definition)
    return row


def point_glyph_section(source, *, cell, visual_owner):
    """Native fec/myK faY appearance; authoritative ownership stays neutral."""
    return struct.pack(
        ">qqiihqhib",
        source["reference"],
        source["uid"],
        *cell,
        visual_owner,
        source.get("level", 0),
        -1,
        -1,
    ) + struct.pack(">Biihb", 0, 0, 0, 0, -1)


def environment_section(source, *, cell, visual_owner):
    """fec header plus the actual subtype appearance (fbc has no suffix)."""
    section = point_glyph_section(source, cell=cell, visual_owner=visual_owner)
    if source.get("source") == TRAP_SOURCE:
        return section[: struct.calcsize(">qqiihqhib")]
    return section
