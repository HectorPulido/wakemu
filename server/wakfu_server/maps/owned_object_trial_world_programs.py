"""Movement-driven programs within the normal owned object trial transaction."""

from copy import deepcopy

from wakfu_server import owned_world_resource_trial, owned_world_tile_trial

KINDS = {
    "sliding_tiles",
    "resource_course",
    "light_course",
    "stealth_course",
    "safe_course",
}


def validate(trial, sources):
    if trial["kind"] == "safe_course":
        from wakfu_server import owned_world_safe_course

        return owned_world_safe_course.validate(trial, sources)
    if trial["kind"] == "light_course":
        from wakfu_server import owned_world_light_program

        return owned_world_light_program.validate(trial, sources)
    if trial["kind"] == "stealth_course":
        from wakfu_server import owned_world_stealth_program

        return owned_world_stealth_program.validate(trial)
    program = trial.get("program")
    if trial["kind"] == "sliding_tiles":
        owned_world_tile_trial.validate(program)
        if trial.get("sources", []):
            raise ValueError("Sliding tiles start from their actual empty native floor")
    else:
        owned_world_resource_trial.validate(program)
        if program["tick_boundary"] != "move":
            raise ValueError(
                "World resource trial requires the accepted-movement turn producer"
            )
        if (
            trial.get("sources") != [program["chest_source_id"]]
            or program["chest_source_id"] not in sources
        ):
            raise ValueError("Resource course requires its original qualified chest")


def advance(trial, current, event):
    """Consume the accepted native movement path, never a requested endpoint."""
    if trial["kind"] == "safe_course":
        from wakfu_server import owned_world_safe_course

        return owned_world_safe_course.advance(trial, current, event)
    if trial["kind"] in {"light_course", "stealth_course"}:
        from wakfu_server import owned_world_light_program, owned_world_stealth_program

        module = (
            owned_world_light_program
            if trial["kind"] == "light_course"
            else owned_world_stealth_program
        )
        return module.advance(trial, current, event)
    config = trial["program"]
    module = (
        owned_world_tile_trial
        if trial["kind"] == "sliding_tiles"
        else owned_world_resource_trial
    )
    before = deepcopy(current)
    after = deepcopy(current)
    program = after.get("program")
    begin = success = failure = False
    events = []
    if event["kind"] == "movement":
        cells = event.get("cells")
        if not isinstance(cells, list) or not cells:
            raise ValueError("World trial requires its actual accepted path")
        if program is None or program.get("stage") in {"failed", "declined"}:
            start = (
                config["cells"][config["initial"].index(0)]
                if trial["kind"] == "sliding_tiles"
                else config["start"]
            )
            starting = next(
                (index for index, cell in enumerate(cells) if list(cell) == start), None
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
            program = module.begin(
                config,
                cells[0],
                attempt=1 if program is None else program["attempt"] + 1,
            )
            begin = True
        for origin, target in zip(cells, cells[1:]):
            if origin == target:
                continue
            if trial["kind"] == "sliding_tiles" and list(target) not in config["cells"]:
                result = module.advance(config, program, dict(kind="decline"))
                program = result["state"]
                events.extend(result["events"])
                break
            result = module.advance(
                config,
                program,
                dict(kind="move", **{"from": list(origin), "to": list(target)}),
            )
            program = result["state"]
            events.extend(result["events"])
            if program["stage"] in {"success", "failed", "declined"}:
                break
    elif trial["kind"] == "resource_course" and program is not None:
        if event.get("source_id") != config["chest_source_id"]:
            return dict(
                state=after,
                changed=False,
                begin=False,
                success=False,
                failure=False,
                events=[],
            )
        result = module.advance(
            config, program, dict(kind="chest", source_id=event["source_id"])
        )
        program = result["state"]
        events.extend(result["events"])
    if program is not None:
        after["program"] = program
        success = program["stage"] == "success"
        failure = program["stage"] == "failed"
    return dict(
        state=after,
        changed=after != before,
        begin=begin,
        success=success,
        failure=failure,
        events=events,
    )


def feedback(trial, current):
    """Use the existing native information delivery for authoritative progress."""
    if trial["kind"] == "safe_course":
        from wakfu_server import owned_world_safe_course

        return owned_world_safe_course.feedback(trial, current)
    if trial["kind"] in {"light_course", "stealth_course"}:
        from wakfu_server import owned_world_light_program, owned_world_stealth_program

        module = (
            owned_world_light_program
            if trial["kind"] == "light_course"
            else owned_world_stealth_program
        )
        return module.feedback(trial, current)
    program = current.get("program")
    if program is None:
        return []
    if trial["kind"] == "resource_course":
        instruction = {
            "outward": "Reach the chest",
            "chest": "Open the chest",
            "return": "Return to the entrance",
            "success": "Course complete",
            "failed": "Oxygen exhausted",
            "declined": "Attempt cancelled",
        }[program["stage"]]
        text = f'Oxygen: {program["resource"]}/{trial["program"]["capacity"]}. {instruction}.'
    else:
        labels = ["_" if value == 0 else str(value) for value in program["tiles"]]
        width = trial["program"].get("display_width", 4)
        text = "Tiles: " + " / ".join(
            " ".join(labels[index : index + width])
            for index in range(0, len(labels), width)
        )
    return [dict(kind="information", text=text)]
