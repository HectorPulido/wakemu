"""Adapted Krosmoglob floors on real admitted terrain, with original effects.

Original absolute anchors are unavailable. These anchors are deliberately
server-designed, not reported as recovered map coordinates. The reviewed guide
describes a central blue floor for the single-glob variant and three floors for
the three security globs. No armor phase, helper summon or10009 is synthesized.
"""
from collections import Counter

POLICY = "wakemu.adapted-native-security-crosses-v1"
AUTHORITY = "authorized_wakemu_native_content_reconstruction"
SOURCE_URL = "https://methodwakfu.com/quetes/xelorium-present/"
_HELPERS = frozenset((3516, 3517))


def _scope(members, catalog):
    references = tuple(sorted(member["ref"] for member in members))
    if references == (3514,):
        return 847, 1
    counts = Counter(references)
    if len(references) == 3 and set(references) <= _HELPERS:
        return 850, 3
    if (
        counts[3518] == 1
        and len(references) == 4
        and set(references) <= _HELPERS | {3518}
    ):
        profile = catalog["npc_profiles"]["3518"]
        boss = next(member for member in members if member["ref"] == 3518)
        hp = profile["at_base_level"]["1"]["maximum"]
        # Original3518: each actual helper death executes148500/12500.
        # Its optional307 child is disabled by an original literalFalse guard.
        if (
            hp != 30000
            or profile["curves"].get("1") != [30000, 0.0]
            or type(boss.get("max_hp")) is not int
            or type(boss.get("hp")) is not int
            or boss.get("max_hp") != hp
            or not 0 < boss.get("hp", 0) <= hp
        ):
            raise ValueError(
                "Security roster does not satisfy the native HP/death contract"
            )
        return 850, 3
    return None


def prepare_security_glyphs(character, members, arena, *, catalog=None):
    """Declare source-backed floors before durable placement; never move actors."""
    from .combat_environment_participant_footprints import participant_footprints
    from .combat_obstacle_condition import footprint
    from .combat_arena_selection import _reachable

    references = tuple(member["ref"] for member in members)
    if not references or not set(references) <= _HELPERS | {3514, 3518}:
        return arena
    # An explicitly authored scene remains authoritative.
    from .combat_encounter_roles import ORDINARY_POLICY

    role = arena.get("native_encounter_roles")
    if (
        arena.get("native_initial_glyphs") is not None
        or arena.get("native_encounter_scene_layout") is not None
        or isinstance(role, dict)
        and role.get("policy") != ORDINARY_POLICY
    ):
        return arena
    if catalog is None:
        from .combat_actor_snapshot import native_actor_catalog

        catalog = native_actor_catalog()
    scope = _scope(members, catalog)
    if scope is None:
        return arena
    reference, count = scope
    if (
        character["map_id"] != arena["map_id"]
        or any(member.get("map_id") != character["map_id"] for member in members)
        or any(
            member.get("instance_id", 0) != character.get("instance_id", 0)
            for member in members
        )
    ):
        raise ValueError("Adapted security scene leaves the actual participant scope")
    facts = participant_footprints(character, members, catalog=catalog)
    occupied = {
        xy
        for row in facts["actors"]
        for xy in footprint(row["position"], row["physical_radius"])
    }
    cells, edges = set(arena["validated_cells"]), set(arena["valid_edges"])
    origins = [tuple(row["position"]) for row in facts["actors"]]
    reachable = set(cells)
    for origin in origins:
        if origin not in cells:
            raise ValueError("Adapted security participant leaves native terrain")
        reachable.intersection_update(_reachable(origin, cells, edges))
    border = {tuple(cell[:2]) for cell in arena.get("native_border_cells", ())}
    cx = min(cell[0] for cell in cells) + max(cell[0] for cell in cells)
    cy = min(cell[1] for cell in cells) + max(cell[1] for cell in cells)
    candidates = []
    for cell in reachable:
        x, y, z = cell
        shape = {(x, y, z), (x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z)}
        xy = {point[:2] for point in shape}
        if (
            not shape <= reachable
            or xy & (occupied | border)
            or any(
                (cell, other) not in edges or (other, cell) not in edges
                for other in shape - {cell}
            )
        ):
            continue
        candidates.append((abs(2 * x - cx) + abs(2 * y - cy), cell, xy))
    used, selected = set(), []
    for _distance, cell, xy in sorted(candidates, key=lambda row: row[:2]):
        if xy & used:
            continue
        selected.append(dict(reference=reference, cell=list(cell), level=0))
        used.update(xy)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError(
            "Native terrain cannot fit the separated adapted security floors"
        )
    return dict(
        arena,
        native_initial_glyphs=selected,
        native_initial_glyph_policy=POLICY,
        native_initial_glyph_authority=AUTHORITY,
        native_initial_glyph_source_url=SOURCE_URL,
        native_environment_participant_footprints=facts,
    )
