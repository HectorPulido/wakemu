"""Source-qualified world stealth adapter for the existing owned trial reducer.

Each accepted native cell is an explicitly reviewed world turn. Original
cinematic wall-clock patrols remain provenance; they are not combat timing.
The native13130 Attack action, at an actual declared rear floor, produces a
rear strike. No dialogue, client victory flag or ordinary fight is involved.
"""

from copy import deepcopy

from wakfu_server import owned_world_stealth_trial as stealth


def validate(trial):
    config = trial["program"]
    stealth.validate(config)
    if (
        config.get("world_turn_policy") != "accepted_cell"
        or type(config.get("map_id")) is not int
        or config["map_id"] <= 0
        or not config.get("reviewed_reconstruction")
        or trial.get("sources", [])
        or any(
            type(guard.get("reference")) is not int
            or guard["reference"] <= 0
            or type(guard.get("level")) is not int
            or guard["level"] <= 0
            or not isinstance(guard.get("native_profile_sha256"), str)
            or len(guard["native_profile_sha256"]) != 64
            for guard in config["guards"]
        )
    ):
        raise ValueError(
            "World stealth requires its reviewed movement/action/native actor declaration"
        )
    return config


def advance(trial, current, event):
    config = validate(trial)
    before = deepcopy(current)
    after = deepcopy(current)
    program = after.get("program")
    begin = False
    events = []
    if event["kind"] == "movement":
        cells = event.get("cells")
        if not isinstance(cells, list) or not cells:
            raise ValueError("World stealth requires the actual accepted path")
        if program is None or program.get("stage") in {"failed", "declined"}:
            starting = next(
                (
                    index
                    for index, point in enumerate(cells)
                    if list(point) == config["start"]
                ),
                None,
            )
            if starting is None:
                return dict(
                    state=after,
                    changed=False,
                    begin=False,
                    success=False,
                    failure=False,
                    events=[],
                )
            cells = cells[starting:]
            program = stealth.begin(
                config,
                cells[0],
                attempt=1 if program is None else program["attempt"] + 1,
            )
            begin = True
        for origin, target in zip(cells, cells[1:]):
            if list(origin) == list(target):
                continue
            result = stealth.advance(
                config,
                program,
                dict(kind="movement", cells=[list(origin), list(target)]),
            )
            program = result["state"]
            events.extend(result["events"])
            if program["stage"] != "active":
                break
            result = stealth.advance(config, program, dict(kind="turn"))
            program = result["state"]
            events.extend(result["events"])
            if program["stage"] != "active":
                break
    elif event["kind"] == "stealth_attack":
        if program is None:
            raise ValueError("Stealth strike requires an active physical attempt")
        result = stealth.advance(
            config, program, dict(kind="rear_strike", guard_id=event["guard_id"])
        )
        program = result["state"]
        events.extend(result["events"])
    if program is not None:
        after["program"] = program
    return dict(
        state=after,
        changed=after != before,
        begin=begin,
        success=program is not None and program["stage"] == "success",
        failure=program is not None and program["stage"] == "failed",
        events=events,
    )


def feedback(trial, current):
    program = current.get("program")
    if program is None:
        return []
    config = trial["program"]
    if program["stage"] == "failed":
        text = "The guards detected you. Return to the entrance and try again."
    elif program["stage"] == "success":
        text = (
            "Infiltration complete. Use the far exit to return to the school gardens."
        )
    else:
        rows = []
        for guard in config["guards"]:
            status = program["guards"][str(guard["id"])]
            if status["hits"] >= config["rear_hits"]:
                rows.append(f'{guard["id"]}: neutralized')
                continue
            pose = guard["patrol"][status["patrol_index"]]
            rows.append(
                f'{guard["id"]}: {tuple(pose["position"])} rear {tuple(pose["rear_cell"])} '
                f'hits {status["hits"]}/{config["rear_hits"]} '
                f'alert {status["suspicion"]}/{config["suspicion_turns"]} '
                f'vision {pose["vision_cells"]}'
            )
        text = "Guards — " + "; ".join(rows)
    return [dict(kind="information", text=text)]
