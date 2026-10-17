"""Native faY environmental snapshots with an explicit local placement policy."""
import struct

POLICY = "wakemu.compact-interior-range-v1"
SOURCE = "buK.cvb.myK.fec.fbm.null_owner.faY"
REFERENCE = 910


def prepare_environment_glyphs(fight, arena, terrain_identity):
    """Choose one free interior point; this is local policy, not official layout."""
    if arena.get("native_border_policy") is None:
        return
    from .combat_battleground_border import POLICY as BORDER_POLICY

    if arena.get("native_border_policy") != BORDER_POLICY:
        raise ValueError("Unknown interior placement terrain policy")
    if type(terrain_identity) is not int:
        raise ValueError("Missing environmental glyph UID source")
    excluded = {tuple(c) for c in arena["native_border_cells"]}
    excluded.update(tuple(actor.position) for actor in fight.actors.values())
    cells = set(fight.walkable) - excluded
    if not cells:
        fight.native_environment_glyph_constructors = []
        return
    all_cells = fight.walkable
    cx = min(c[0] for c in all_cells) + max(c[0] for c in all_cells)
    cy = min(c[1] for c in all_cells) + max(c[1] for c in all_cells)
    cell = min(cells, key=lambda c: (abs(2 * c[0] - cx) + abs(2 * c[1] - cy), c))
    identity = terrain_identity - 1
    if identity in fight.actors or identity == terrain_identity:
        raise ValueError("Environmental glyph identity collision")
    fight.native_environment_glyph_constructors = [
        dict(
            uid=identity,
            reference=REFERENCE,
            cell=tuple(cell),
            policy=POLICY,
            source=SOURCE,
        )
    ]


def verify_environment_glyph(fight, row):
    constructors = getattr(fight, "native_environment_glyph_constructors", ())
    original = next(
        (source for source in constructors if source.get("uid") == row.get("uid")), None
    )
    if (
        original is None
        or original.get("policy") != POLICY
        or original.get("source") != SOURCE
        or tuple(original.get("cell", ())) != tuple(row.get("cell", ()))
        or original.get("reference") != REFERENCE
        or row.get("native_environment_source") != SOURCE
        or row.get("native_environment_policy") != POLICY
        or row.get("reference") != REFERENCE
        or row.get("native_area_contract") != "faY"
        or row.get("owner_id") is not None
        or row.get("level") != 0
        or row.get("direction") != -1
        or tuple(row.get("cell", ())) not in fight.walkable
        or tuple(row.get("cell", ())) in getattr(fight, "native_border_cells", ())
        or tuple(tuple(cell) for cell in row.get("native_cells_xy", ()))
        != (tuple(row["cell"][:2]),)
    ):
        raise ValueError("Missing environmental faY constructor authority")


def ensure_environment_glyphs(fight):
    from .combat_effect_area import native_effect_areas
    from .combat_global_pv_collections import register_global_area

    constructors = getattr(fight, "native_environment_glyph_constructors", ())
    for source in constructors:
        identity = source["uid"]
        existing = fight.native_effect_areas.get(identity)
        if existing is not None:
            verify_environment_glyph(fight, existing)
            continue
        if getattr(fight, "native_environment_glyphs_installed", False):
            continue  # A removed native Qq must not be reconstructed by a factory.
        definition = native_effect_areas().get(str(REFERENCE), {})
        if (
            source.get("source") != SOURCE
            or source.get("policy") != POLICY
            or source.get("reference") != REFERENCE
            or definition.get("type") != "GLYPH"
            or definition.get("native_shape_class") != "anD"
            or definition.get("raw_bdh") != []
            or definition.get("native_area_properties") != [4]
            or definition.get("effect_ids") != [152452]
            or definition.get("entry_masks") != [10001, 10008, 10000]
            or definition.get("exit_masks") != [10002]
        ):
            raise ValueError("Missing native environmental glyph prototype")
        cell = tuple(source["cell"])
        row = dict(
            uid=identity,
            reference=REFERENCE,
            cell=cell,
            level=0,
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
            native_environment_source=SOURCE,
            native_environment_policy=POLICY,
        )
        verify_environment_glyph(fight, row)
        fight.native_effect_areas[identity] = row
        register_global_area(fight, identity)
    fight.native_environment_glyphs_installed = True


def environment_sections(fight, *, viewer_id=None):
    """Project local neutral glyph visibility through the native owner header.

    Prototype910 has INVISIBLE_FOR_ENEMIES. Its faV affiliation defaults to -1
    without an owner, which hides it from fighters but reveals it to observers.
    A real participant owner in myK binds the visual carrier to that viewer's
    team. This projection never changes the authoritative neutral area owner
    or effects; spectators retain the native null-owner representation.
    """
    if viewer_id is not None and viewer_id not in fight.actors:
        raise ValueError("Environmental glyph viewer is not a fight actor")
    visual_owner = 0 if viewer_id is None else viewer_id
    installed = getattr(fight, "native_environment_glyphs_installed", False)
    sections = []
    for source in getattr(fight, "native_environment_glyph_constructors", ()):
        row = fight.native_effect_areas.get(source["uid"]) if installed else None
        if installed and row is None:
            continue
        if row is not None:
            verify_environment_glyph(fight, row)
        cell = tuple(source["cell"] if row is None else row["cell"])
        # faY910 aQc initializes rMq=false. Explicit faY.fTl appearance keeps
        # the aBn reference (0,0,0); the point shape ignores that reference.
        sections.append(
            struct.pack(
                ">qqiihqhib", REFERENCE, source["uid"], *cell, visual_owner, 0, -1, -1
            )
            + struct.pack(">Biihb", 0, 0, 0, 0, -1)
        )
    return sections
