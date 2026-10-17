"""Read-only legacy QI occupancy checks preserving original mask semantics."""


def check_legacy_topology(state, slots, issue, unknown, checked):
    from .combat_qi_snapshot import NativeQISnapshot, RegisteredObstacle

    path = "fight.native_qi_byte_topology"
    arena, topology = state.get("native_qi_snapshot"), state.get(
        "native_qi_byte_topology"
    )
    if type(arena) is not dict or type(topology) is not dict:
        unknown(
            "spatial.cell_topology", path, "Complete terrain/QL topology unavailable"
        )
        return
    if len(topology) > 32767:
        unknown("coverage.limit", path, "QL cell inspection limit reached")
        return
    masks = arena.get("cell_masks")
    if type(masks) not in (list, tuple) or len(masks) > 32767:
        issue(
            "spatial.terrain",
            "fight.native_qi_snapshot",
            "Missing bounded native mask array",
        )
        return
    obstacles, work = [], 0
    for slot, row in enumerate(slots):
        if row is None:
            continue
        if (
            type(row) is not dict
            or type(row.get("indexed")) is not bool
            or type(row.get("movement_blocking")) is not bool
            or type(row.get("radius")) is not int
            or not -128 <= row["radius"] <= 127
            or type(row.get("position")) not in (list, tuple)
            or len(row["position"]) != 2
            or any(type(n) is not int for n in row["position"])
        ):
            issue(
                "spatial.registration",
                f"fight.native_qi_slots[{slot}]",
                "Incomplete native obstacle descriptor",
            )
            return
        if row["indexed"]:
            work += (2 * max(0, row["radius"]) + 1) ** 2
            if work > 131072:
                unknown(
                    "coverage.limit",
                    path,
                    "Aggregate footprint inspection limit reached",
                )
                return
            obstacles.append(RegisteredObstacle(slot, *row["position"], row["radius"]))
    try:
        # Audited pure geometry object: no catalog, Fight assignment or callbacks.
        occupancy = NativeQISnapshot(arena, obstacles=obstacles)
    except (ValueError, TypeError, KeyError, OverflowError):
        issue(
            "spatial.terrain",
            "fight.native_qi_snapshot",
            "Invalid native terrain or footprint bounds",
        )
        return
    observed, work = {}, 0
    for key, row in dict.items(topology):
        if type(key) is not str or len(key) > 40 or type(row) is not dict:
            issue("spatial.cell_topology", path, "Malformed QL coordinate or topology")
            return
        try:
            parts = key.split(",")
            cell = tuple(int(part) for part in parts)
        except ValueError:
            cell = ()
        if len(cell) != 2 or key != f"{cell[0]},{cell[1]}" or not occupancy.aK(*cell):
            issue(
                "spatial.cell_topology",
                path,
                "QL cell has no canonical in-bounds coordinate",
            )
            return
        keys, statuses = row.get("keys"), row.get("states")
        if (
            type(keys) is not list
            or type(statuses) is not list
            or len(keys) != len(statuses)
        ):
            issue("spatial.cell_topology", path, "Malformed QL set slot arrays")
            return
        work += len(keys)
        if work > 131072:
            unknown("coverage.limit", path, "Aggregate QL set inspection limit reached")
            return
        if (
            any(type(n) is not int or not -128 <= n <= 127 for n in keys)
            or any(type(n) is not int or n not in (0, 1, 2) for n in statuses)
            or any(
                type(row.get(name)) is not int
                for name in ("size", "free", "compact_removes")
            )
        ):
            issue("spatial.cell_topology", path, "Malformed QL set operands")
            return
        live = [uid for uid, status in zip(keys, statuses) if status == 1]
        if (
            len(live) != len(set(live))
            or row["size"] != len(live)
            or any(not 0 <= uid < 127 for uid in live)
            or not 0 <= row["free"] <= len(keys)
        ):
            issue(
                "spatial.cell_topology", path, "Invalid QL set membership or accounting"
            )
            return
        observed[cell] = frozenset(live)
    for cell in set(observed) | set(occupancy.occupancy):
        if observed.get(cell, frozenset()) != occupancy.occupancy.get(
            cell, frozenset()
        ):
            issue(
                "spatial.occupancy",
                path,
                "QL membership differs from registered obstacle footprints",
            )
            break
    touched = state.get("native_qi_touched_cells")
    if type(touched) not in (list, tuple) or len(touched) > 32767:
        unknown(
            "spatial.touched_authority",
            "fight.native_qi_touched_cells",
            "Native touched-cell history unavailable",
        )
    else:
        known = set()
        for cell in touched:
            if (
                type(cell) not in (list, tuple)
                or len(cell) != 2
                or any(type(n) is not int for n in cell)
                or not occupancy.aK(*cell)
            ):
                issue(
                    "spatial.touched_history",
                    "fight.native_qi_touched_cells",
                    "Invalid touched-cell coordinate",
                )
                break
            known.add(tuple(cell))
        else:
            if not (set(observed) | set(occupancy.occupancy)) <= known:
                issue(
                    "spatial.touched_history",
                    "fight.native_qi_touched_cells",
                    "Registered QL cell missing from touched history",
                )
            if known - set(observed):
                unknown(
                    "spatial.empty_cell_topology",
                    path,
                    "Some touched-empty cells have no explicit QL set history",
                )
    checked.extend(
        (
            "spatial.terrain",
            "spatial.occupancy",
            "spatial.cell_topology",
            "spatial.touched_history",
        )
    )
