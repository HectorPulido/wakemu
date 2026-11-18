"""Actual2676 post greetings and captain boarding on an existing QA peer.

The caller owns login and public positioning. This module never creates a
session, grants items, edits quest progress or manufactures an entry packet.
"""

import struct
import time


QUEST = 2676
POST_OBJECTIVES = (8331, 8332, 8334, 8333, 8336)
CAPTAIN = 1740
ROUTE = "quest-npc-980-1740-158-3206-7954"


def _publication(probe):
    with probe.store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='native_quest_conversation_contracts'"
        ).fetchone()
    if row is None:
        raise ValueError("No active native NPC publication")
    return row["value"]


def _record(probe, mark):
    """Persist mission-only frames before a subsequent dialogue/entry can fail."""
    with probe.peer.observation_lock:
        rows = tuple(enumerate(probe.peer.records[mark:], start=mark))
    frames = probe.receipt.setdefault("line4_native_mission_frames", [])
    seen = {(row["sequence"], row["opcode"]) for row in frames}
    for sequence, (opcode, body) in rows:
        if opcode in (13312, 13832, 13422) and (sequence, opcode) not in seen:
            frames.append(dict(sequence=sequence, opcode=opcode, body_hex=body.hex()))
    probe.receipt.setdefault("trace", []).extend(probe.peer.gameplay_trace(mark))
    probe.save()


def _wait(probe, predicate, label, *, timeout=20):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = predicate()
        if latest:
            return latest
        if probe.peer.closed.is_set():
            break
        time.sleep(0.05)
    raise AssertionError(("Native departure action did not settle", label, latest))


def _open(probe, placement):
    row = placement["row"]
    mark = probe.peer.mark()
    probe.peer.send(13222, struct.pack(">qq", row["actor_id"], row["action_ids"][0]))
    frame = probe.peer.matching(12969, mark, timeout=20)
    if len(frame) != 13:
        raise AssertionError(("Malformed native departure dialogue", len(frame)))
    node, _kind, speaker = struct.unpack(">ibq", frame)
    if speaker != row["actor_id"]:
        raise AssertionError(
            ("Native departure dialogue belongs to another actor", speaker)
        )
    return mark, node


def _move(probe, placement, move_to):
    row = placement["row"]
    anchor = placement.get("interaction_anchor", row)
    position = tuple(anchor[key] for key in ("x", "y", "z"))
    move_to(row["map_id"], position)
    actual = probe.current()
    if actual["map_id"] != row["map_id"] or actual.get("instance_id", 0) != 0:
        raise AssertionError(
            ("Departure greeting requires its actual public map", actual)
        )
    return position


def run_departure(probe, *, move_to, board=True):
    """Resume missing actual greetings, earn8335, then accept native7954.

    ``move_to(map_id, (x,y,z))`` belongs to the caller and may use normal walking
    or explicitly authorized public QA setup. Such setup earns no objective;
    every objective below still requires the native NPC action/accepted choice.
    """
    state = probe.progress()
    if QUEST not in set(state["running"]) | set(state["completed"]):
        raise ValueError("Quest2676 must already be naturally active or completed")
    if 8330 not in state["objectives"]:
        raise ValueError("Finish the actual Bossowl acknowledgement8330 first")
    publication = _publication(probe)
    journey = probe.receipt.setdefault("journey", [])
    for objective in POST_OBJECTIVES:
        if objective in probe.progress()["objectives"]:
            continue
        matches = [
            p
            for p in publication["placements"]
            if any(
                f.get("quest_id") == QUEST and f.get("objective_id") == objective
                for f in p.get("spoken_objectives", ())
            )
        ]
        if len(matches) != 1:
            raise ValueError(
                ("Departure post lacks one authentic published source", objective)
            )
        placement = matches[0]
        position = _move(probe, placement, move_to)
        mark = probe.peer.mark()
        try:
            _, node = _open(probe, placement)
            probe.peer.matching(
                13832,
                mark,
                predicate=lambda body: body
                == struct.pack(">qi", probe.character["id"], objective),
                timeout=20,
            )
            _wait(probe, lambda: objective in probe.progress()["objectives"], objective)
            journey.append(
                dict(
                    kind="native_post_greeting",
                    quest_id=QUEST,
                    objective_id=objective,
                    actor_id=placement["row"]["actor_id"],
                    action_id=placement["row"]["action_ids"][0],
                    actual_root=node,
                    public_approach=list(position),
                )
            )
        finally:
            _record(probe, mark)
    state = probe.progress()
    required = {8330, *POST_OBJECTIVES}
    if not required <= set(state["objectives"]):
        raise AssertionError(
            (
                "Native captain prerequisites are still missing",
                required - set(state["objectives"]),
            )
        )
    matches = [
        p
        for p in publication["placements"]
        if p["row"]["reference_id"] == CAPTAIN
        and any(r.get("route") == ROUTE for r in p.get("choice_routes", ()))
    ]
    if len(matches) != 1:
        raise ValueError("Captain lacks its exact published native owned route")
    captain = matches[0]
    position = _move(probe, captain, move_to)
    mark = probe.peer.mark()
    try:
        _, node = _open(probe, captain)
        if node != 1729:
            raise AssertionError(("Unexpected actual captain root", node))
        # 7990 is the actual final2676 acknowledgement;7991 is its completed
        # revisit counterpart. The live server retains the original level21 gate.
        choice = 7991 if QUEST in probe.progress()["completed"] else 7990
        probe.peer.send(12058, struct.pack(">ii", node, choice))
        response_opcode, opened = probe.peer.matching_any(
            (12218, 12969),
            mark,
            predicate=lambda opcode, body: (
                opcode == 12218
                and body == struct.pack(">i", 3206)
                or opcode == 12969
                and len(body) == 13
                and struct.unpack_from(">i", body)[0] == 3206
            ),
            timeout=20,
        )
        if (
            response_opcode == 12969
            and struct.unpack_from(">q", opened, 5)[0] != captain["row"]["actor_id"]
        ):
            raise AssertionError("Captain readiness response changed speaker")
        state = _wait(
            probe,
            lambda: probe.progress()
            if QUEST in probe.progress()["completed"]
            else None,
            "2676 captain acknowledgement",
        )
        if 8335 not in state["objectives"] or 2684 not in set(state["running"]) | set(
            state["completed"]
        ):
            raise AssertionError(("Captain did not earn8335 and unlock2684", state))
        journey.append(
            dict(
                kind="native_captain_acknowledgement",
                quest_id=QUEST,
                objective_id=8335,
                offered_root=node,
                accepted_choice=choice,
                response_root=3206,
                response_opcode=response_opcode,
                public_approach=list(position),
            )
        )
        _record(probe, mark)  # 2676 evidence must survive a later boarding failure.
        if not board:
            return state
        entry_mark = probe.peer.mark()
        probe.peer.send(12058, struct.pack(">ii", 3206, 7954))
        probe.peer.matching(13974, entry_mark, timeout=30)
        current = _wait(
            probe,
            lambda: probe.current()
            if probe.current()["map_id"] == 980
            and probe.current().get("instance_id", 0) > 0
            else None,
            "actual native captain boarding",
            timeout=30,
        )
        probe.peer.send(12449)
        journey.append(
            dict(
                kind="native_captain_owned_entry",
                route=ROUTE,
                node_id=3206,
                choice_id=7954,
                map_id=current["map_id"],
                instance_id=current["instance_id"],
                position=[current[key] for key in ("x", "y", "z")],
                map_change_opcode=13974,
            )
        )
        return current
    finally:
        _record(probe, mark)
