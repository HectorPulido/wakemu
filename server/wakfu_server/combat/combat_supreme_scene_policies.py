"""Explicit Wakemu ultimate-scene placements on unchanged native terrain.

Community diagrams establish relative arena structure. Absolute coordinates
below are reconstructed server policy, never recovered original server spawns.
Native costs, states, phase callbacks and dynamic mechanisms are not replaced.
"""
from collections import deque

from .combat_geometry import prepare_geometry


SCENE_POLICIES = {
    1988: dict(
        map_id=363,
        provider="crow",
        observation_url="https://methodwakfu.com/wp-content/uploads/2019/03/Position-de-d-part.jpg",
    ),
    3582: dict(
        map_id=959,
        provider="steel",
        observation_url="https://methodwakfu.com/wp-content/uploads/2019/04/Zone_Safe.png",
    ),
    2430: dict(
        map_id=545,
        provider="dragon_pig",
        observation_url="https://methodwakfu.com/pvm/boss-ultimes/antre-du-dragon-cochon/",
    ),
    3433: dict(
        map_id=1092,
        provider="nogord",
        observation_url="https://methodwakfu.com/wp-content/uploads/2023/07/Nogord_Zones_Explosion_Elementaires-1.png",
    ),
    4770: dict(
        map_id=1229,
        provider="ombrage",
        observation_url="https://methodwakfu.com/wp-content/uploads/2021/09/Ombrage_Zones_Ombre.png",
    ),
    5664: dict(
        map_id=1435,
        provider="nox",
        observation_url="https://methodwakfu.com/pvm/boss-ultimes/coeur-de-lhorloge-de-nox/",
    ),
    4378: dict(
        map_id=1156, provider="ogrest", observation_url="https://wakfu.guide/ogrest/"
    ),
    3870: dict(
        map_id=1056,
        provider="fulmoon",
        observation_url="https://wakfulabs.com/dungeons/boss-ultimes/cime-grand-totem/",
    ),
    5500: dict(
        map_id=1400,
        provider="talkasha",
        observation_url="https://wakfu.guide/talkasha/",
    ),
}


def policy_for_reference(reference):
    """Return a copy of a declared placement policy, or None for other IDs.

    Alternate profiles and Neo variants do not inherit a scene by family/name.
    """
    policy = SCENE_POLICIES.get(reference)
    return None if policy is None else dict(policy)


def _component(native, origin, *, allowed=None):
    cells = native.cells if allowed is None else frozenset(allowed)
    if origin not in cells:
        raise ValueError("Reconstructed scene landmark is absent from native terrain")
    visited = {origin}
    pending = deque((origin,))
    while pending:
        current = pending.popleft()
        for destination in native.outgoing.get(current, ()):
            if (
                destination in cells
                and destination not in visited
                and (destination, current) in native.edges
            ):
                visited.add(destination)
                pending.append(destination)
    return frozenset(visited)


def _layout(native, reference, board, source, anchor, *, platform=(), direction=3):
    declaration = SCENE_POLICIES[reference]
    if native.map_id != declaration["map_id"]:
        raise ValueError("Ultimate scene native map identity mismatch")
    board = frozenset(board)
    cells = board | frozenset(platform)
    footprint = frozenset(
        (source[0] + x, source[1] + y, source[2])
        for x in range(-1, 2)
        for y in range(-1, 2)
    )
    if not footprint <= cells or anchor not in board or anchor in footprint:
        raise ValueError("Native terrain cannot fit the reconstructed boss and player")
    reached = _component(native, anchor, allowed=board - footprint)
    # Pick actual nearby interior floor cells; a finite party field is a
    # construction input, not a claim about official starting-cell coordinates.
    interior = [
        cell
        for cell in reached
        if sum(
            (cell, adjacent) in native.edges and adjacent in reached
            for adjacent in (
                (cell[0] + 1, cell[1], cell[2]),
                (cell[0] - 1, cell[1], cell[2]),
                (cell[0], cell[1] + 1, cell[2]),
                (cell[0], cell[1] - 1, cell[2]),
            )
        )
        >= 3
    ]
    party = tuple(
        sorted(
            interior,
            key=lambda cell: (
                abs(cell[0] - anchor[0])
                + abs(cell[1] - anchor[1])
                + abs(cell[2] - anchor[2]),
                cell,
            ),
        )[:15]
    )
    if len(party) < 6 or anchor not in party:
        raise ValueError("Reconstructed ultimate scene lacks six native party slots")
    policy = "wakemu.supreme." + declaration["provider"] + ".observed_native_fit.v1"
    return dict(
        policy=policy,
        route_key=policy,
        authority="authorized_wakemu_content_reconstruction",
        observation_url=declaration["observation_url"],
        original_world_coordinates=False,
        map_id=native.map_id,
        reference=reference,
        source=source,
        caster_cell=source,
        anchor=anchor,
        cells=cells,
        edges=frozenset((a, b) for a, b in native.edges if a in cells and b in cells),
        party_placement_cells=party,
        boss_footprint=footprint,
        boss_direction=direction,
        glyph_cells=(),
        setup_scope="placement_only_native_dynamic_producers_preserved",
        complete_encounter_qualified=False,
    )


def reconstructed_dragon_pig_scene(geometry):
    """Use the circular lower arena, excluding its long entrance corridor."""
    native = prepare_geometry(geometry)
    floor = frozenset(
        cell
        for cell in native.cells
        if -11 <= cell[0] <= 10 and -55 <= cell[1] <= -35 and cell[2] == 0
    )
    board = _component(native, (0, -44, 0), allowed=floor)
    if len(board) < 200:
        raise ValueError("Native Dragon Pig circular arena is incomplete")
    return _layout(native, 2430, board, (0, -44, 0), (0, -38, 0))


def reconstructed_nogord_scene(geometry):
    """Fit the guide's isolated 3x3 boss island beside the main floor."""
    native = prepare_geometry(geometry)
    source = (-17, 0, 0)
    platform = frozenset((x, y, 0) for x in range(-18, -15) for y in range(-1, 2))
    if not platform <= native.cells or _component(native, source) != platform:
        raise ValueError(
            "Native Nogord isolated boss island does not match the observed shape"
        )
    board = _component(native, (0, 0, 0))
    if len(board) < 500 or platform & board or any(abs(cell[2]) > 2 for cell in board):
        raise ValueError(
            "Native Nogord floor differs from its guide-qualified main board"
        )
    return _layout(
        native, 3433, board, source, (0, 5, 0), platform=platform, direction=1
    )


def reconstructed_ombrage_scene(geometry):
    """Select the actual isolated clock diamond, excluding the outer map."""
    native = prepare_geometry(geometry)
    board = _component(native, (0, 0, 0))
    if len(board) != 185 or any(
        abs(x) > 7 or abs(y) > 7 or z != 0 for x, y, z in board
    ):
        raise ValueError(
            "Native Ombrage clock diamond does not match the observed scene"
        )
    result = _layout(native, 4770, board, (0, 0, 0), (4, 0, 0))
    party = ((4, 0, 0), (2, 3, 0), (-2, 3, 0), (-4, 0, 0), (-2, -3, 0), (2, -3, 0))
    if not set(party) <= board:
        raise ValueError(
            "Native Ombrage diamond lacks the reconstructed six-ray party field"
        )
    result.update(
        party_placement_cells=party,
        policy="wakemu.supreme.ombrage.observed_native_fit.v2",
    )
    result["route_key"] = result["policy"]
    return result


def resolve_supreme_scene(reference, geometry, *, steel_side="left"):
    """Resolve only exact registered native identities on their declared map."""
    declaration = policy_for_reference(reference)
    if declaration is None:
        return None
    native = prepare_geometry(geometry)
    if native.map_id != declaration["map_id"]:
        raise ValueError("Ultimate scene native map identity mismatch")
    provider = declaration["provider"]
    if provider == "nox":
        from .combat_nox_scene_layout import reconstructed_nox_scene

        return reconstructed_nox_scene(native)
    if provider in ("fulmoon", "talkasha"):
        from .combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
            reconstructed_talkasha_scene,
        )

        return (
            reconstructed_fulmoon_scene
            if provider == "fulmoon"
            else reconstructed_talkasha_scene
        )(native)
    if provider == "crow":
        from .combat_crow_steel_scene_layout import reconstructed_crow_scene

        result = reconstructed_crow_scene(native)
        result.update(
            reference=reference, boss_direction=3, complete_encounter_qualified=False
        )
        return result
    if provider == "steel":
        from .combat_crow_steel_scene_layout import reconstructed_steel_scene

        result = reconstructed_steel_scene(native, side=steel_side)
        result.update(
            reference=reference,
            boss_direction=1 if steel_side == "left" else 3,
            complete_encounter_qualified=False,
        )
        return result
    if provider == "ogrest":
        from .combat_ogrest_scene_layout import reconstructed_ogrest_scene

        return reconstructed_ogrest_scene(native)
    return {
        "dragon_pig": reconstructed_dragon_pig_scene,
        "nogord": reconstructed_nogord_scene,
        "ombrage": reconstructed_ombrage_scene,
    }[provider](native)
