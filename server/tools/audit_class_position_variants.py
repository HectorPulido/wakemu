#!/usr/bin/env python3
"""General native preplacement position variants for seven bounded action gaps."""
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".runtime/combat-review-20261008/normal-cast-bounded43-source.json"
REFERENCES = frozenset((752, 6492, 6284, 5566, 7087))


def placement_pair(cells, distance, preferred):
    """Choose actual same-height aligned cells with an existing terrain corridor."""
    cells = frozenset(tuple(cell) for cell in cells)
    for origin in sorted(cells, key=lambda cell: (cell != preferred, cell)):
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            corridor = tuple(
                (origin[0] + dx * step, origin[1] + dy * step, origin[2])
                for step in range(distance + 1)
            )
            if all(cell in cells for cell in corridor):
                return origin, corridor[-1]
    raise ValueError("No actual same-height native placement corridor for distance")


def run(output):
    import audit_ready_start as ready
    from audit_class_normal_casts import NormalCastAudit
    from wakfu_server.combat_arena_selection import bounded_arena
    from wakfu_server.spells import available_spells, ACTIVE_SLOT_LEVELS

    source = json.loads(SOURCE.read_text())
    pairs = [row for row in source["pairs"] if row["spell_reference"] in REFERENCES]
    if len(pairs) != 7:
        raise ValueError("Frozen seven action-position gaps changed")
    queues = defaultdict(deque)
    records, cases = [], []
    for pair in pairs:
        flags = pair["contexts"][0]["flags"]
        for distance in dict.fromkeys((1, 2, 3, flags["minimum"], flags["maximum"])):
            row = dict(
                breed=pair["breed"],
                level=pair["level"],
                action=pair["spell_reference"],
                distance=distance,
                source_minimum=flags["minimum"],
                source_maximum=flags["maximum"],
                source_flags=flags,
            )
            records.append(row)
            key = row["breed"], row["level"], None
            queues[key].append(row)
            cases.append(key)
    current = {}

    def geometry(native, origin, target, breed, level, passive):
        row = queues[breed, level, passive].popleft()
        current["row"] = row
        origin, target = placement_pair(native["cells"], row["distance"], origin)
        terrain = bounded_arena(native, origin, [target], radius=12)
        row.update(
            origin=list(origin),
            target=list(target),
            actual_native_cell_count=len(terrain["cells"]),
        )
        return origin, target, terrain

    def deck(breed, level, passive):
        active = sorted(
            row["id"]
            for row in available_spells(breed, level)
            if row["kind"] == "active"
        )
        action = current["row"]["action"]
        if action not in active:
            raise ValueError("Requested action lacks original class ownership")
        capacity = sum(level >= value for value in ACTIVE_SLOT_LEVELS)
        return list(dict.fromkeys([action, *active]))[:capacity]

    def inspect(runtime, character, monster, deck, packets, stats):
        row = current["row"]
        # The bounded arena is small; search its complete native cell population.
        limit = len(runtime.fight.walkable)
        if not 1 <= limit <= 4096:
            raise ValueError("Native placement arena exceeds complete-search budget")
        audit = NormalCastAudit(
            candidate_limit=limit,
            maximum_eligible=1,
            action_selector=lambda actions: [
                action for action in actions if action["reference"] == row["action"]
            ],
        )
        result = audit(runtime, character, monster, deck, packets, stats)
        result["native_preplacement_variant"] = dict(row)
        return result

    result = ready.run(
        output,
        basics_only=True,
        turn_cycle=True,
        turn_steps=0,
        cases_override=cases,
        preplacement_geometry_provider=geometry,
        active_deck_provider=deck,
        on_runtime=inspect,
    )
    result.update(
        scope="Original class actions with NPC positions chosen before Store/Ready/QI",
        placement_cases=records,
        already_created_actor_moved=False,
        full_client_verified=False,
    )
    Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
