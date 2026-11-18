"""Source-pinned timed light exploration; callers supply authenticated facts.

No clock, quest mutation or live routing lives here. Native sources declare
lamps, traps, switches and the floor; explicit policy declares timing and the
exit's required collected light. Unrecovered server operands stay external.
"""

from copy import deepcopy
from hashlib import sha256
import json

SCHEMA = "owned-world-light-trial-v1"


def digest(config):
    return sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate(config):
    def point(value):
        return (
            isinstance(value, list)
            and len(value) == 3
            and all(type(v) is int for v in value)
        )

    if (
        type(config) is not dict
        or config.get("schema") != SCHEMA
        or not isinstance(config.get("id"), str)
        or not config["id"]
        or not isinstance(config.get("evidence"), str)
        or not config["evidence"]
        or not isinstance(config.get("cells"), list)
        or not config["cells"]
        or any(not point(p) for p in config["cells"])
        or len(set(map(tuple, config["cells"]))) != len(config["cells"])
        or not point(config.get("start"))
        or config["start"] not in config["cells"]
        or not isinstance(config.get("exit_cells"), list)
        or not config["exit_cells"]
        or any(not point(p) or p not in config["cells"] for p in config["exit_cells"])
        or not isinstance(config.get("trap_cells"), list)
        or any(not point(p) or p not in config["cells"] for p in config["trap_cells"])
        or type(config.get("duration_ms")) is not int
        or config["duration_ms"] <= 0
        or type(config.get("required_light")) is not int
        or config["required_light"] <= 0
        or type(config.get("start_source")) is not int
        or config["start_source"] <= 0
        or not isinstance(config.get("lamps"), list)
        or not config["lamps"]
        or not isinstance(config.get("switches"), list)
        or not isinstance(config.get("edges"), list)
        or not config["edges"]
    ):
        raise ValueError(
            "Light trial needs its exact finite floor and explicit timing policy"
        )
    cells = set(map(tuple, config["cells"]))
    sources = {config["start_source"]}
    for source in config["lamps"] + config["switches"]:
        if (
            type(source) is not dict
            or type(source.get("source_id")) is not int
            or source["source_id"] <= 0
            or source["source_id"] in sources
            or not isinstance(source.get("approaches"), list)
            or not source["approaches"]
            or any(not point(p) or tuple(p) not in cells for p in source["approaches"])
        ):
            raise ValueError(
                "Light trial action needs a distinct qualified native source"
            )
        sources.add(source["source_id"])
    for lamp in config["lamps"]:
        if any(
            type(lamp.get(key)) is not int or lamp[key] <= 0
            for key in ("light", "extra_ms")
        ):
            raise ValueError("Each lamp needs its declared light and time operands")
    switches = {row["source_id"] for row in config["switches"]}
    if not isinstance(config.get("gates"), list):
        raise ValueError("Light trial needs explicit native gate edges")
    for gate in config["gates"]:
        if (
            not isinstance(gate.get("switches"), list)
            or not gate["switches"]
            or not set(gate["switches"]) <= switches
            or gate.get("edge") not in config["edges"]
        ):
            raise ValueError("Light trial gate needs its real switch and native edge")
    if any(
        not isinstance(edge, list)
        or len(edge) != 2
        or any(not point(p) or tuple(p) not in cells for p in edge)
        or sum(abs(edge[0][i] - edge[1][i]) for i in (0, 1)) != 1
        for edge in config["edges"]
    ):
        raise ValueError("Light trial movement needs actual adjacent native edges")


def begin(config, *, now_ms, source_id, position, attempt=1):
    validate(config)
    if (
        type(now_ms) is not int
        or now_ms < 0
        or type(attempt) is not int
        or attempt <= 0
        or source_id != config["start_source"]
        or list(position) != config["start"]
    ):
        raise ValueError(
            "Light trial must begin through its authenticated starting source"
        )
    return dict(
        schema=SCHEMA,
        profile_sha256=digest(config),
        attempt=attempt,
        position=list(position),
        stage="active",
        last_ms=now_ms,
        deadline_ms=now_ms + config["duration_ms"],
        light=0,
        lamps=[],
        switches=[],
    )


def advance(config, state, event):
    validate(config)
    if (
        state.get("schema") != SCHEMA
        or state.get("profile_sha256") != digest(config)
        or state.get("position") not in config["cells"]
        or state.get("stage") not in {"active", "success", "failed", "declined"}
        or type(event.get("now_ms")) is not int
        or event["now_ms"] < state.get("last_ms", 0)
        or event.get("kind") not in {"move", "interact", "tick", "decline"}
    ):
        raise ValueError(
            "Light trial checkpoint/action lacks its pinned monotonic authority"
        )
    after = deepcopy(state)
    if state["stage"] != "active":
        return dict(state=after, events=[])
    after["last_ms"] = event["now_ms"]
    # Expiry wins races with a lamp or exit at the exact deadline.
    if event["now_ms"] >= state["deadline_ms"]:
        after["stage"] = "failed"
        after["position"] = list(config["start"])
        return dict(state=after, events=["expired", "return_to_start"])
    if event["kind"] == "decline":
        after["stage"] = "declined"
        return dict(state=after, events=["declined"])
    if event["kind"] == "move":
        edge = [event.get("from"), event.get("to")]
        if edge not in config["edges"] or edge[0] != state["position"]:
            raise ValueError("Light trial requires the actual contiguous accepted path")
        for gate in config["gates"]:
            if gate["edge"] == edge and not set(gate["switches"]) <= set(
                state["switches"]
            ):
                raise ValueError("The native labyrinth gate is still closed")
        after["position"] = list(edge[1])
        if edge[1] in config["trap_cells"]:
            after["position"] = list(config["start"])
            return dict(state=after, events=["trap", "return_to_start"])
        if (
            edge[1] in config["exit_cells"]
            and state["light"] >= config["required_light"]
        ):
            after["stage"] = "success"
            return dict(state=after, events=["success"])
    if event["kind"] == "interact":
        source = next(
            (
                row
                for row in config["lamps"] + config["switches"]
                if row["source_id"] == event.get("source_id")
            ),
            None,
        )
        if source is None or state["position"] not in source["approaches"]:
            raise ValueError("Light trial action lacks its native source approach")
        category = "lamps" if source in config["lamps"] else "switches"
        if source["source_id"] in state[category]:
            return dict(state=after, events=[])
        after[category].append(source["source_id"])
        if category == "lamps":
            after["deadline_ms"] += source["extra_ms"]
            after["light"] += source["light"]
        return dict(
            state=after,
            events=["light_collected" if category == "lamps" else "gate_opened"],
        )
    return dict(state=after, events=[])
