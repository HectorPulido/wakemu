"""Bounded native archaeology actions for an existing authenticated QA probe.

The owner supplies TLS and any explicitly authorized public travel setup.
All private movement follows the pinned original Sm6 graph. This helper never
assigns quests, changes inventory/stats, awards a victory or sends a cinematic
completion callback. Timed occupations and films finish through normal idle.
"""
from collections import deque
from copy import deepcopy
import struct
import time

from tools.quest_instance_combat_probe import walk_native


def _record(probe, boundary, **fields):
    probe.receipt.setdefault("journey", []).append(dict(boundary=boundary, **fields))
    probe.save()


def _wait(predicate, label, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError(("Archaeology boundary timed out", label))


def _view(probe, configuration):
    current = probe.current()
    profile = configuration["topology"]["owned_object_trials"]
    prefix = f"owned-object-trial:{profile['id']}:{current['instance_id']}:"
    with probe.store.connection() as db:
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s "
            "AND left(event_key,%s)=%s ORDER BY "
            "(payload->'state'->>'revision')::bigint DESC,created_at DESC,event_key DESC LIMIT 1",
            (current["id"], len(prefix), prefix),
        ).fetchone()
    if row is None:
        return dict(state=dict(revision=0, trials={}), presentation_due_ms=0)
    return row["payload"]


def _films(probe, configuration):
    def elapsed():
        due = _view(probe, configuration).get("presentation_due_ms", 0)
        return due <= probe.store.now().timestamp() * 1000

    _wait(elapsed, "original once-only presentation", timeout=25)


def _configuration(probe):
    current = probe.current()
    if current["map_id"] != 1001 or current.get("instance_id", 0) <= 0:
        raise ValueError(
            "Enter original archaeology source 25474/2290 before the trial helper"
        )
    with probe.store.connection() as db:
        row = db.execute(
            "SELECT c.configuration FROM dungeon_instances i JOIN dungeon_runtime_configurations c "
            "ON c.route_key=i.context_route_key AND c.policy_version=i.context_policy_version "
            "JOIN dungeon_instance_members m USING(instance_id) "
            "WHERE i.instance_id=%s AND m.character_id=%s AND m.status='active'",
            (current["instance_id"], current["id"]),
        ).fetchone()
    configuration = None if row is None else row["configuration"]
    if (
        configuration is None
        or configuration["topology"].get("owned_object_trials", {}).get("id")
        != "archaeology-2698"
    ):
        raise ValueError(
            "The selected owner lacks its pinned archaeology configuration"
        )
    return configuration


def _path(edges, start, goals):
    adjacency = {}
    for left, right in edges:
        adjacency.setdefault(tuple(left), []).append(tuple(right))
    previous, pending, found = {tuple(start): None}, deque([tuple(start)]), None
    goals = set(map(tuple, goals))
    while pending:
        point = pending.popleft()
        if point in goals:
            found = point
            break
        for target in sorted(adjacency.get(point, ())):
            if target not in previous:
                previous[target] = point
                pending.append(target)
    if found is None:
        raise AssertionError(
            ("No actual native archaeology path", start, sorted(goals))
        )
    path = [found]
    while previous[path[-1]] is not None:
        path.append(previous[path[-1]])
    return list(reversed(path))


def _interact(probe, configuration, source_id, *, approach=None):
    _films(probe, configuration)
    profile = configuration["topology"]["owned_object_trials"]
    source = next(row for row in profile["sources"] if row["id"] == source_id)
    current = probe.current()
    start = tuple(current[k] for k in ("x", "y", "z"))
    goals = [approach] if approach is not None else source["approaches"]
    path = _path(
        configuration["topology"]["exploration_geometry"]["edges"], start, goals
    )
    walk_native(probe, configuration, path[-1])
    before = _view(probe, configuration)["state"]["revision"]
    before_objectives = set(probe.progress()["objectives"])
    mark = probe.peer.mark()
    print(
        f"Archaeology source {source_id}: actual {source['duration_ms']}ms action",
        flush=True,
    )
    probe.peer.send(12870, struct.pack(">qHH", source_id, source["action"], 0))

    def completed():
        view = _view(probe, configuration)
        if view["state"]["revision"] <= before:
            return None
        event = view.get("event", {})
        if event.get("kind") != "interact" or event.get("source_id") != source_id:
            return None
        return view

    view = _wait(
        completed,
        f"actual occupation {source_id}",
        timeout=source["duration_ms"] / 1000 + 15,
    )
    for objective in (set(probe.progress()["objectives"]) - before_objectives) & {
        5330,
        5331,
        5332,
    }:
        probe.peer.matching(
            13832,
            mark,
            lambda body: len(body) == 12
            and struct.unpack(">qi", body) == (probe.character["id"], objective),
        )
    _record(
        probe,
        "actual timed archaeology interaction",
        source_id=source_id,
        approach=list(path[-1]),
        native_duration_ms=source["duration_ms"],
        durable_revision=view["state"]["revision"],
    )
    probe.receipt.setdefault("trace", []).extend(probe.peer.gameplay_trace(mark))
    probe.save()
    return view


def run_archaeology_trial(probe):
    """Resume the real ordered scrolls, distinct digs and fragile carry only."""
    configuration = _configuration(probe)
    if 2698 not in set(probe.progress()["running"]) | set(
        probe.progress()["completed"]
    ):
        raise ValueError(
            "The archaeology quest must be naturally admitted before acceptance"
        )
    profile = configuration["topology"]["owned_object_trials"]
    _wait(
        lambda: _view(probe, configuration).get("event"),
        "actual loaded entry receipt",
        timeout=15,
    )
    for trial in profile["trials"][:2]:
        current = _view(probe, configuration)["state"]["trials"].get(trial["id"], {})
        if current.get("complete"):
            continue
        sources = (
            trial["sources"][current.get("index", 0) :]
            if trial["kind"] == "ordered_objects"
            else [
                identity
                for identity in trial["sources"]
                if identity not in current.get("discovered", ())
            ]
        )
        for identity in sources:
            _interact(probe, configuration, identity)
        assert _view(probe, configuration)["state"]["trials"][trial["id"]]["complete"]
    carry = profile["trials"][2]
    current = _view(probe, configuration)["state"]["trials"].get(carry["id"], {})
    if not current.get("complete"):
        if not current.get("carrying"):
            _interact(
                probe, configuration, carry["pickup_source"], approach=(3, -18, -10)
            )
        _films(probe, configuration)
        # Filtering the QA path to a subset of original edges preserves the
        # actual server movement authority and avoids native hazard shortcuts.
        safe = deepcopy(configuration)
        hazards = set(map(tuple, carry["hazard_cells"]))
        ramps = {tuple(map(tuple, edge)) for edge in carry["safe_edges"]}
        safe["topology"]["exploration_geometry"]["edges"] = [
            [left, right]
            for left, right in configuration["topology"]["exploration_geometry"][
                "edges"
            ]
            if tuple(left) not in hazards
            and tuple(right) not in hazards
            and (
                abs(left[2] - right[2]) <= carry["max_height_delta"]
                or (tuple(left), tuple(right)) in ramps
            )
        ]
        owner = probe.current()
        path = _path(
            safe["topology"]["exploration_geometry"]["edges"],
            tuple(owner[k] for k in ("x", "y", "z")),
            carry["destination_cells"],
        )
        mark = probe.peer.mark()
        walk_native(probe, safe, path[-1])
        _wait(
            lambda: 2698 in probe.progress()["completed"],
            "actual fragile delivery /2698",
        )
        probe.peer.matching(
            13832,
            mark,
            lambda body: len(body) == 12
            and struct.unpack(">qi", body) == (probe.character["id"], 5332),
        )
        probe.peer.matching(
            13422,
            mark,
            lambda body: len(body) == 20
            and struct.unpack_from(">qi", body) == (probe.character["id"], 2698),
        )
        _record(
            probe,
            "actual native safe fragile carry",
            cells=[list(cell) for cell in path],
            edge_count=len(path) - 1,
            quest_id=2698,
        )
        probe.receipt.setdefault("trace", []).extend(probe.peer.gameplay_trace(mark))
        probe.save()
    assert {5330, 5331, 5332} <= set(probe.progress()["objectives"])
    _films(probe, configuration)
    return configuration


def enter_archaeology_trial(probe):
    """Use the original quest-visible entrance from its actual public floor."""
    current = probe.current()
    if current["map_id"] == 1001 and current.get("instance_id", 0) > 0:
        return _configuration(probe)
    if (current["map_id"], current.get("instance_id", 0)) != (1134, 0):
        raise ValueError(
            "Reach the public Amakna archaeology entrance before native admission"
        )
    probe.walk((-21, 66, -16))
    travel(probe, 25474, 2290, 1001)
    return _configuration(probe)


def travel(probe, source, destination, target_map):
    """Actual normal teleporter request and map acknowledgments, no callback."""
    mark = probe.peer.mark()
    probe.peer.send(12296, struct.pack(">qiBi", source, destination, 0, 2))
    _ack_transition(probe, mark, target_map)
    _record(
        probe,
        "actual native archaeology transport",
        source_id=source,
        destination_id=destination,
        target_map=target_map,
    )


def _ack_transition(probe, mark, target_map):
    def arrived():
        probe.ack_loads(mark, timeout=0.6)
        return probe.current()["map_id"] == target_map

    _wait(arrived, f"actual map transition to {target_map}")


def _talk(probe, actor, action, path):
    mark = probe.peer.mark()
    probe.peer.send(13222, struct.pack(">qq", actor, action))
    probe.peer.matching(
        12969, mark, lambda body: struct.unpack_from(">i", body)[0] == path[0][0]
    )
    for node, choice, target in path:
        before = probe.peer.mark()
        probe.peer.send(12058, struct.pack(">ii", node, choice))
        probe.peer.matching(
            12218, before, lambda body: struct.unpack_from(">i", body)[0] == target
        )
    probe.receipt.setdefault("trace", []).extend(probe.peer.gameplay_trace(mark))
    probe.save()
    return mark


def run_archaeology_followups(probe, *, public_position=None):
    """Natural2699–2705 producers; caller owns any authorized public setup.

    public_position(probe,map_id,cell) may shorten public travel only. Each
    objective still requires its real physical source or guarded dialogue.
    No such callback is used inside the archaeology instance or fragile carry.
    """

    def position(map_id, cell):
        if probe.current()["map_id"] != map_id:
            if public_position is None:
                raise ValueError(
                    (
                        "Normal public travel required before the next source",
                        map_id,
                        cell,
                    )
                )
            public_position(probe, map_id, cell)
        else:
            probe.walk(cell)
        assert (
            probe.current()["map_id"] == map_id
            and probe.current().get("instance_id", 0) == 0
        )

    state = probe.progress()
    if 2698 not in state["completed"]:
        raise ValueError("Genuine2698 completion is required before its debrief")
    if probe.current()["map_id"] == 1001:
        cfg = _configuration(probe)
        _films(probe, cfg)
        from wakfu_server import generic_transports

        source = generic_transports.source(1001, 31332)
        goals = [
            tuple(row[k] for k in ("x", "y", "z"))
            for row in source["approach_positions"]
        ]
        if not goals:
            goals = [tuple(int(source[k]) for k in ("x", "y", "z"))]
        here = tuple(probe.current()[k] for k in ("x", "y", "z"))
        walk_native(
            probe,
            cfg,
            _path(cfg["topology"]["exploration_geometry"]["edges"], here, goals)[-1],
        )
        travel(probe, 31332, 3943, 1134)
    laura = -2251799927089062
    if 2699 not in probe.progress()["completed"]:
        position(1134, (-23, 77, -11))
        _talk(
            probe, laura, 698, [(3219, 8013, 3252), (3252, 8051, 3254), (3254, 8053, 0)]
        )
        _wait(lambda: 2699 in probe.progress()["completed"], "Laura2699 hand-in")
    if 2700 not in probe.progress()["completed"]:
        position(1134, (-23, 77, -11))
        mark = _talk(probe, laura, 698, [(3219, 8106, 3287), (3287, 8107, 0)])
        _ack_transition(probe, mark, 1135)
        # Laura's script arrival is setup for the original portal, not5334.
        if 5334 in probe.progress()["objectives"]:
            raise AssertionError("Laura travel alone earned the actual site objective")
        position(1135, (-41, 84, -60))
        travel(probe, 25523, 2263, 1003)
        _wait(lambda: 2700 in probe.progress()["completed"], "real site transport2700")
    if 2701 not in probe.progress()["completed"]:
        position(1003, (-9, -3, -15))
        mark = probe.peer.mark()
        probe.peer.send(12870, struct.pack(">qHH", 25603, 0, 0))
        probe.peer.matching(
            13832,
            mark,
            lambda body: len(body) == 12
            and struct.unpack(">qi", body) == (probe.character["id"], 5335),
        )
        _wait(
            lambda: 2701 in probe.progress()["completed"], "actual temple examination"
        )
    scientists = (
        (
            2702,
            -2251799934992702,
            705,
            (-9, -4, -15),
            [(3267, 8066, 3274), (3274, 8073, 0)],
        ),
        (
            2703,
            -2251799934992703,
            706,
            (-8, -3, -15),
            [(3269, 8068, 3293), (3293, 8119, 0)],
        ),
        (
            2704,
            -2251799934992704,
            704,
            (-9, -1, -15),
            [(3227, 8014, 3272), (3272, 8071, 3273), (3273, 8072, 0)],
        ),
    )
    for quest, actor, action, cell, path in scientists:
        if quest not in probe.progress()["completed"]:
            position(1003, cell)
            _talk(probe, actor, action, path)
            _wait(
                lambda: quest in probe.progress()["completed"],
                f"native scientist {quest}",
            )
            _record(
                probe,
                "native guarded scientist hand-in",
                quest_id=quest,
                actor_id=actor,
            )
    if 2705 not in probe.progress()["completed"]:
        if probe.current()["map_id"] == 1003:
            position(1003, (19, -12, 1))
            travel(probe, 25522, 2262, 1135)
        position(1134, (16, 7, 0))
        _talk(
            probe,
            -1724034232352753,
            703,
            [
                (3225, 8008, 3275),
                (3275, 8074, 3276),
                (3276, 8075, 3277),
                (3277, 8078, 0),
            ],
        )
        _wait(
            lambda: 2705 in probe.progress()["completed"], "actual Magnum final hand-in"
        )
        _record(probe, "actual Magnum2705 hand-in", quest_id=2705)
    return probe.progress()
