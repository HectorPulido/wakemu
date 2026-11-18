"""Fixed School board/course witnesses on the caller's existing StoryProbe.

No connection, solver, quest/item grant, victory or runtime mutation is supplied.
Every step is an ordinary accepted movement; the chest uses its native action.
"""
import struct
import time
import json
from pathlib import Path

from tools.line4_owned_actions import capture


def _context(probe, map_id, profile_id):
    current = probe.current()
    if current["map_id"] != map_id or current.get("instance_id", 0) <= 0:
        raise ValueError(("Enter the actual School trial first", map_id))
    profile = probe.configuration()["topology"].get("owned_object_trials", {})
    if profile.get("id") != profile_id:
        raise ValueError(("Unexpected pinned School trial", profile.get("id")))
    return profile


def _state(probe, profile):
    prefix = f"owned-object-trial:{profile['id']}:{probe.current()['instance_id']}:"
    with probe.store.connection() as db:
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s "
            "AND left(event_key,%s)=%s ORDER BY (payload->'state'->>'revision')::bigint DESC,"
            "created_at DESC,event_key DESC LIMIT 1",
            (probe.character["id"], len(prefix), prefix),
        ).fetchone()
    return {} if row is None else row["payload"]["state"]["trials"]


def _wait(predicate, label):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError(("Actual School action did not settle", label))


def _step(probe, profile, trial_id, point):
    probe.walk(tuple(point))

    def arrived():
        trial = _state(probe, profile).get(trial_id, {})
        program = trial.get("program", {})
        if program.get("stage") in ("failed", "declined"):
            raise AssertionError(("Actual School course failed", program))
        return trial if program.get("position") == list(point) else None

    return _wait(arrived, list(point))


def run_sword_board(probe):
    """Execute/resume only the profile's exact twelve-swap board witness."""
    profile = _context(probe, 1025, "huppermage-tiles-1025")
    trial = next(row for row in profile["trials"] if row["kind"] == "sliding_tiles")
    current = _state(probe, profile).get(trial["id"], {})
    if current.get("complete"):
        return current
    config = trial["program"]
    route = config["solution_cells"]
    program = current.get("program", {})
    start = program.get("moves", 0) if program.get("stage") == "active" else 0
    if not 0 <= start < len(route):
        raise ValueError("The actual board is outside its fixed witness")
    # Verify a fixed witness prefix, rather than searching for another solution.
    expected = list(config["initial"])
    for left, right in zip(route[:start], route[1 : start + 1]):
        a, b = config["cells"].index(left), config["cells"].index(right)
        expected[a], expected[b] = expected[b], expected[a]
    if program.get("stage") == "active" and (
        program.get("tiles") != expected or program.get("position") != route[start]
    ):
        raise ValueError(
            "Resume requires the actual board to match the fixed witness prefix"
        )
    mark = probe.peer.mark()
    try:
        if not program or program.get("stage") != "active":
            probe.walk(tuple(route[0]))
        for point in route[start + 1 :]:
            result = _step(probe, profile, trial["id"], point)
        result = _state(probe, profile).get(trial["id"], {})
        if not result.get("complete") or 5622 not in probe.progress()["objectives"]:
            raise AssertionError(("Actual board did not earn5622", result))
        probe.note(
            "actual School twelve-swap sword board completed",
            quest_id=2785,
            objective_id=5622,
            resumed_after_swaps=start,
            final_cell=route[-1],
        )
        return result
    finally:
        capture(probe, mark)


def run_flooded_round_trip(probe):
    """Follow the pinned42-edge channel out, open26172, and retrace it."""
    profile = _context(probe, 1026, "huppermage-flooded-1026")
    trial = next(row for row in profile["trials"] if row["kind"] == "resource_course")
    config = trial["program"]
    route = config["reviewed_reconstruction"]["manual_route"]
    current = _state(probe, profile).get(trial["id"], {})
    if current.get("complete"):
        return current
    stage = current.get("program", {}).get("stage", "outward")
    if stage in ("failed", "declined"):
        raise ValueError(
            "Start a fresh real flooded attempt before resuming this witness"
        )
    here = [probe.current()[key] for key in ("x", "y", "z")]
    if here not in route:
        raise ValueError(("The actual owner is off the fixed air-bubble channel", here))
    mark = probe.peer.mark()
    try:
        if stage == "outward":
            for point in route[route.index(here) + 1 :]:
                current = _step(probe, profile, trial["id"], point)
            stage = (
                _state(probe, profile)
                .get(trial["id"], {})
                .get("program", {})
                .get("stage")
            )
        if stage == "chest":
            if [probe.current()[key] for key in ("x", "y", "z")] != route[-1]:
                raise ValueError(
                    "Approach the original chest from the fixed channel end"
                )
            probe.peer.send(12870, struct.pack(">qHH", config["chest_source_id"], 0, 0))
            _wait(
                lambda: _state(probe, profile)
                .get(trial["id"], {})
                .get("program", {})
                .get("stage")
                == "return",
                "actual26172 chest action",
            )
            stage = "return"
        if stage != "return":
            raise AssertionError(
                ("Actual flooded stage does not permit the return leg", stage)
            )
        here = [probe.current()[key] for key in ("x", "y", "z")]
        for point in reversed(route[: route.index(here)]):
            current = _step(probe, profile, trial["id"], point)
        result = _state(probe, profile).get(trial["id"], {})
        if not result.get("complete") or 5632 not in probe.progress()["objectives"]:
            raise AssertionError(
                ("Actual outward/chest/return did not earn5632", result)
            )
        probe.note(
            "actual School flooded outward chest return completed",
            quest_id=2786,
            objective_id=5632,
            native_chest=config["chest_source_id"],
            outward_edges=len(route) - 1,
        )
        return result
    finally:
        capture(probe, mark)


def run_infiltration_route(probe):
    """Resume the existing46-step witness, with no search or optional attacks."""
    from protocol_codec import DIRECTIONS

    profile = _context(probe, 1028, "huppermage-infiltration-1028")
    trial = next(row for row in profile["trials"] if row["kind"] == "stealth_course")
    current = _state(probe, profile).get(trial["id"], {})
    if current.get("complete"):
        return current
    route_path = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/school130_infiltration_acceptance_route.json"
    )
    route = json.loads(route_path.read_text())["cells"]
    config = trial["program"]
    edges = {tuple(map(tuple, edge)) for edge in config["edges"]}
    if (
        len(route) != 47
        or route[0] != config["start"]
        or route[-1] not in config["exits"]
        or any(
            (tuple(left), tuple(right)) not in edges
            for left, right in zip(route, route[1:])
        )
    ):
        raise ValueError(
            "The existing infiltration witness differs from the pinned native course"
        )
    program = current.get("program")
    start = 0 if program is None else program["turns"]
    if program is not None and (
        program["stage"] != "active"
        or any(status["hits"] for status in program["guards"].values())
    ):
        raise ValueError(
            "The literal infiltration witness requires its active unstruck patrol state"
        )
    here = [probe.current()[key] for key in ("x", "y", "z")]
    if (
        not 0 <= start < len(route)
        or here != route[start]
        or (program is not None and program["position"] != here)
    ):
        raise ValueError(
            (
                "Actual infiltration owner is outside its fixed witness prefix",
                start,
                here,
            )
        )
    directions = {(dx, dy): key for key, (_, dx, dy) in DIRECTIONS.items()}
    mark = probe.peer.mark()
    try:
        for index in range(start + 1, len(route)):
            left, right = route[index - 1], route[index]
            encoded = (directions[(right[0] - left[0], right[1] - left[1])] << 5) | (
                (right[2] - left[2]) & 31
            )
            # Same native13331 movement layout as walk_native, exactly one cell.
            # A single10-second budget covers both real position and receipt.
            probe.peer.send(
                13331, struct.pack(">iiihB", 0, *left, 1) + bytes([encoded])
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                current = _state(probe, profile).get(trial["id"], {})
                actual = current.get("program", {})
                if actual.get("stage") in ("failed", "declined"):
                    raise AssertionError(
                        ("Actual infiltration attempt failed", index, actual)
                    )
                position = [probe.current()[key] for key in ("x", "y", "z")]
                if position == right and actual.get("position") == right:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError(
                    (
                        "Actual infiltration step did not settle within10seconds",
                        index,
                        left,
                        right,
                    )
                )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = _state(probe, profile).get(trial["id"], {})
            if current.get("complete") and 5650 in probe.progress()["objectives"]:
                probe.note(
                    "actual School46-step infiltration completed",
                    quest_id=2791,
                    objective_id=5650,
                    resumed_after_steps=start,
                    final_cell=route[-1],
                )
                return current
            time.sleep(0.05)
        raise AssertionError(
            ("Actual infiltration success did not publish5650 within5seconds", current)
        )
    finally:
        capture(probe, mark)


def run_light_labyrinth(probe, *, resume_index=None):
    """Walk the pinned314-action witness and use actual native lamps/levers."""
    profile = _context(probe, 1027, "huppermage-labyrinth-1027")
    trial = next(row for row in profile["trials"] if row["kind"] == "light_course")
    config = trial["program"]
    route = config["representative_route"]
    current = _state(probe, profile).get(trial["id"], {})
    if current.get("complete"):
        return current
    instance = probe.current()["instance_id"]
    cursor = probe.receipt.get("school_light_witness", {})
    program = current.get("program", {})
    mark = probe.peer.mark()
    try:
        if program.get("stage") not in ("active",):
            probe.walk(tuple(config["start"]))
            probe.peer.send(12870, struct.pack(">qHH", config["start_source"], 0, 0))
            _wait(
                lambda: _state(probe, profile)
                .get(trial["id"], {})
                .get("program", {})
                .get("stage")
                == "active",
                "actual starting lever",
            )
            index = 0
        else:
            index = (
                cursor.get("next_index", 0)
                if cursor.get("instance_id") == instance
                else 0
            )
            if resume_index is not None:
                index = resume_index
        if type(index) is not int or not 0 <= index <= len(route):
            raise ValueError("Invalid literal light witness resume index")
        expected_position = config["start"]
        expected_lamps, expected_switches = set(), set()
        lamp_ids = {row["source_id"] for row in config["lamps"]}
        for action in route[:index]:
            if action["kind"] == "movement":
                expected_position = action["cells"][-1]
            else:
                (
                    expected_lamps
                    if action["source_id"] in lamp_ids
                    else expected_switches
                ).add(action["source_id"])
        program = _state(probe, profile).get(trial["id"], {}).get("program", {})
        if (
            program.get("position") != expected_position
            or set(program.get("lamps", ())) != expected_lamps
            or set(program.get("switches", ())) != expected_switches
        ):
            raise ValueError(
                (
                    "Actual light checkpoint differs from the literal witness prefix",
                    index,
                    program,
                )
            )
        from wakfu_server.actor_approach import movement_request

        while index < len(route):
            action = route[index]
            if action["kind"] == "movement":
                # Preserve every literal accepted cell; stop before each action
                # so its lever/lamp transaction commits before the next path.
                path = [action["cells"][0]]
                while (
                    index < len(route)
                    and route[index]["kind"] == "movement"
                    and len(path) < 256
                ):
                    cells = route[index]["cells"]
                    if cells[0] != path[-1] or len(cells) != 2:
                        raise ValueError("The pinned light path is not contiguous")
                    path.append(cells[-1])
                    index += 1
                probe.peer.send(13331, movement_request(path))

                def arrived():
                    current = _state(probe, profile).get(trial["id"], {})
                    program = current.get("program", {})
                    if program.get("stage") in ("failed", "declined"):
                        raise AssertionError(
                            ("Actual light path failed or expired", program)
                        )
                    return current if program.get("position") == path[-1] else None

                _wait(arrived, ("actual literal light path", path[-1]))
            elif action["kind"] == "interact":
                source = action["source_id"]
                category = "lamps" if source in lamp_ids else "switches"
                probe.peer.send(12870, struct.pack(">qHH", source, 0, 0))

                def accepted():
                    program = (
                        _state(probe, profile).get(trial["id"], {}).get("program", {})
                    )
                    if program.get("stage") != "active":
                        raise AssertionError(
                            ("Actual light source failed or expired", source, program)
                        )
                    return source in program.get(category, ())

                _wait(accepted, ("actual light source", source))
                index += 1
            else:
                raise ValueError(
                    ("Unknown pinned light witness action", action["kind"])
                )
            probe.receipt["school_light_witness"] = dict(
                instance_id=instance, next_index=index
            )
            probe.save()
        result = _state(probe, profile).get(trial["id"], {})
        if not result.get("complete") or 5638 not in probe.progress()["objectives"]:
            raise AssertionError(("Actual timed light course did not earn5638", result))
        probe.note(
            "actual School timed light labyrinth completed",
            quest_id=2790,
            objective_id=5638,
            literal_actions=len(route),
            lamps=result["program"]["lamps"],
            switches=result["program"]["switches"],
            timing="Reviewed120s initial and30s per collected light; original native callbacks",
        )
        return result
    finally:
        capture(probe, mark)
