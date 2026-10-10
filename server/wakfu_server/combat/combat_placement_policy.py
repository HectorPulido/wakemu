"""Freeze one locally configured native-terrain layout per durable encounter."""
from psycopg.types.json import Jsonb
from contextlib import nullcontext
from psycopg.pq import TransactionStatus
from .combat_placement_cells import generate
from .combat_wire import arena


def _policy(value):
    if not isinstance(value, dict) or set(value) != {
        "version",
        "slots_per_team",
        "variation_enabled",
    }:
        raise ValueError("Invalid placement policy fields")
    if type(value["version"]) is not int or not 1 <= value["version"] < 2**31:
        raise ValueError("Invalid placement policy version")
    if (
        type(value["slots_per_team"]) is not int
        or not 1 <= value["slots_per_team"] <= 127
    ):
        raise ValueError("Invalid placement capacity")
    if type(value["variation_enabled"]) is not bool:
        raise ValueError("Invalid placement variation policy")
    return dict(value)


def _arena(map_id, instance_id, layout):
    cells = {tuple(c) for c in layout["cells"]}
    edges = {tuple(tuple(c) for c in edge) for edge in layout["edges"]}
    placement = {
        int(team): {tuple(c) for c in group}
        for team, group in layout["placement"].items()
    }
    from .combat_qi_surface_catalog import (
        native_qi_surfaces,
        native_qi_surface_provenance,
    )
    from .combat_qi_surface_selection import native_surface_indices

    # Placement regenerates wire masks, so preserve the actual native Vy
    # selection rather than silently replacing every surface index with zero.
    indices = native_surface_indices(native_qi_surfaces(map_id), cells)
    result = arena(
        map_id,
        layout["wire_instance_id"],
        sorted(cells),
        placement,
        surface_indices=indices,
        border_cells=layout.get("native_border_cells", []),
    )
    result.update(
        validated_cells=cells,
        valid_edges=edges,
        placement_cells=placement,
        native_qi_surface_provenance=native_qi_surface_provenance(map_id),
        participant_positions=layout.get("participant_positions", []),
        native_border_cells=frozenset(
            tuple(c) for c in layout.get("native_border_cells", [])
        ),
        native_border_policy=layout.get("native_border_policy"),
    )
    return result


def freeze(
    store,
    *,
    account_id,
    generation,
    character_id,
    fight_id,
    map_id,
    instance_id,
    selected_arena,
    seeds,
    db=None
):
    """Authorize owner, lock encounter, then reuse its committed layout on retry."""
    if db is not None and db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Placement requires an active borrowed transaction")
    with store.connection() if db is None else nullcontext(db) as db:
        fight = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,)
        ).fetchone()
        if fight is None or fight["status"] not in ("placement", "active"):
            raise ValueError("Placement encounter is unavailable")
        store.lock_character(db, account_id, generation, character_id)
        if not db.execute(
            "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND account_id=%s AND character_id=%s AND session_generation=%s",
            (fight_id, account_id, character_id, generation),
        ).fetchone():
            raise ValueError("Placement owner is not admitted")
        prior = db.execute(
            "SELECT map_id,instance_id,layout FROM fight_placement_layouts WHERE fight_id=%s",
            (fight_id,),
        ).fetchone()
        if prior is not None:
            if (prior["map_id"], prior["instance_id"]) != (map_id, instance_id):
                raise ValueError("Placement encounter scope changed")
            return _arena(map_id, instance_id, prior["layout"])
        row = db.execute(
            "SELECT value FROM settings WHERE name='fight_placement_policy'"
        ).fetchone()
        policy = _policy(None if row is None else row["value"])
        cells, edges = selected_arena["validated_cells"], selected_arena["valid_edges"]
        relocations = selected_arena.get("participant_positions", [])
        if relocations:
            if [tuple(pair[0]) for pair in relocations] != [tuple(c) for c in seeds[1]]:
                raise ValueError("Encounter relocation source changed")
            seeds = {0: seeds[0], 1: [tuple(pair[1]) for pair in relocations]}
        placement = generate(
            cells,
            edges,
            seeds,
            slots_per_team=policy["slots_per_team"],
            variation_seed=(fight_id << 31) | policy["version"]
            if policy["variation_enabled"]
            else None,
            spread_teams=selected_arena.get("native_border_policy")
            == "wakemu.compact-cardinal-perimeter-v1",
            avoid_cells=selected_arena.get("native_border_cells", ()),
        )
        layout = dict(
            native_border_cells=sorted(selected_arena.get("native_border_cells", [])),
            native_border_policy=selected_arena.get("native_border_policy"),
            participant_positions=relocations,
            cells=sorted(cells),
            edges=sorted(edges),
            wire_instance_id=selected_arena["instance_id"],
            placement={str(t): sorted(group) for t, group in placement.items()},
        )
        result = _arena(map_id, instance_id, layout)
        db.execute(
            "INSERT INTO fight_placement_layouts(fight_id,map_id,instance_id,policy,layout) VALUES(%s,%s,%s,%s,%s)",
            (fight_id, map_id, instance_id, Jsonb(policy), Jsonb(layout)),
        )
        return result
