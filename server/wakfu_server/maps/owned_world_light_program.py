"""Authenticated owned-object adapter for a declared timed light course."""

from copy import deepcopy

from wakfu_server import owned_world_light_trial as light


def validate(trial, sources):
    config = trial["program"]
    light.validate(config)
    identities = {config["start_source"]} | {
        row["source_id"] for row in config["lamps"] + config["switches"]
    }
    if set(trial.get("sources", ())) != identities or not identities <= set(sources):
        raise ValueError("Light course lacks its exact qualified native actions")
    if any(
        type(gate.get("object_id")) is not int or gate["object_id"] <= 0
        for gate in config["gates"]
    ):
        raise ValueError("Light course gates need original Door identities")


def gate_effects(trial, current):
    config = trial["program"]
    program = current.get("program") or {}
    switches = set(program.get("switches", ()))
    result = {}
    for gate in config["gates"]:
        closed = not set(gate["switches"]) <= switches
        row = dict(
            kind="element_state",
            object_id=gate["object_id"],
            state=int(closed),
            visible=closed,
            usable=False,
            blocks_movement=closed,
        )
        if gate["object_id"] in result and result[gate["object_id"]] != row:
            raise ValueError("One native light-course Door has conflicting switches")
        result[gate["object_id"]] = row
    return list(result.values())


def reconnect_effects(trial, current, *, now_ms):
    """Restore the native timer and spent lights without changing the attempt."""
    program = current.get("program")
    callbacks = trial["program"].get("native_callbacks", {})
    if program is None or program["stage"] != "active":
        return []
    if type(now_ms) is not int or now_ms < program["last_ms"]:
        raise ValueError("Light presentation requires the current server clock")
    remaining = program["deadline_ms"] - now_ms
    if remaining <= 0:
        return []  # The normal persisted deadline poll owns expiry and relocation.
    config = trial["program"]
    effects = []
    if "start" in callbacks:
        effects.append(
            dict(
                kind="scenario_event",
                scenario=callbacks["scenario"],
                event=callbacks["start"],
                arguments=[remaining],
            )
        )
    if "lamp" in callbacks:
        extra = sum(
            row["extra_ms"]
            for row in config["lamps"]
            if row["source_id"] in program["lamps"]
        )
        started = program["deadline_ms"] - config["duration_ms"] - extra
        for identity in program["lamps"]:
            effects.append(
                dict(
                    kind="scenario_event",
                    scenario=callbacks["scenario"],
                    event=callbacks["lamp"],
                    arguments=[
                        extra,
                        started,
                        now_ms,
                        1,
                        config["duration_ms"],
                        identity,
                    ],
                )
            )
    return effects


def advance(trial, current, event):
    config = trial["program"]
    after = deepcopy(current)
    program = after.get("program")
    begin = False
    events = []
    effects = []
    if program is None or program["stage"] in {"failed", "declined"}:
        if (
            event["kind"] != "interact"
            or event.get("source_id") != config["start_source"]
        ):
            return dict(
                state=after,
                changed=False,
                begin=False,
                success=False,
                failure=False,
                events=[],
                effects=[],
            )
        program = light.begin(
            config,
            now_ms=event["now_ms"],
            source_id=event["source_id"],
            position=event["position"],
            attempt=1 if program is None else program["attempt"] + 1,
        )
        begin = True
    elif event["kind"] == "movement":
        cells = event.get("cells")
        if not isinstance(cells, list) or not cells or cells[0] != program["position"]:
            raise ValueError("Light course requires its actual accepted owner path")
        for origin, target in zip(cells, cells[1:]):
            if origin == target:
                continue
            result = light.advance(
                config,
                program,
                dict(
                    kind="move",
                    now_ms=event["now_ms"],
                    **{"from": list(origin), "to": list(target)},
                ),
            )
            program = result["state"]
            events.extend(result["events"])
            if "return_to_start" in result["events"] or program["stage"] != "active":
                break
    elif event["kind"] in {"tick", "interact"}:
        result = light.advance(
            config,
            program,
            dict(
                kind="tick" if event["kind"] == "tick" else "interact",
                now_ms=event["now_ms"],
                source_id=event.get("source_id"),
            ),
        )
        program = result["state"]
        events.extend(result["events"])
    if program is not None:
        after["program"] = program
    if "return_to_start" in events:
        effects.append(dict(kind="relocate", position=list(config["start"])))
    callback = config.get("native_callbacks")
    if callback is not None and "light_collected" in events:
        extra = sum(
            row["extra_ms"]
            for row in config["lamps"]
            if row["source_id"] in program["lamps"]
        )
        started = program["deadline_ms"] - config["duration_ms"] - extra
        effects.append(
            dict(
                kind="scenario_event",
                scenario=callback["scenario"],
                event=callback["lamp"],
                arguments=[
                    extra,
                    started,
                    event["now_ms"],
                    1,
                    config["duration_ms"],
                    event["source_id"],
                ],
            )
        )
    changed = after != current
    if changed and (begin or event["kind"] == "interact"):
        effects.extend(gate_effects(trial, after))
    return dict(
        state=after,
        changed=changed,
        begin=begin,
        success=program is not None and program["stage"] == "success",
        failure=program is not None and program["stage"] == "failed",
        events=events,
        effects=effects,
    )


def feedback(trial, current):
    program = current.get("program")
    if program is None:
        return []
    remaining = max(0, program["deadline_ms"] - program["last_ms"]) // 1000
    return [
        dict(
            kind="information",
            text=(
                f'Light: {program["light"]}/{trial["program"]["required_light"]}. '
                f'Time: {remaining}s. {program["stage"]}.'
            ),
        )
    ]
