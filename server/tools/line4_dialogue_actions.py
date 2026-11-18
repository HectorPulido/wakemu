"""Reviewed literal NPC paths for already-earned2690/2691/2692.

No dialogue edge or mission event is inferred at runtime; paths consist only
of the currently published reviewed graph and the live offered starting node.
"""
from collections import deque
import struct
from tools.line4_owned_actions import capture


def hand_in(probe, quest, objective_id=None):
    if quest in probe.progress()["completed"]:
        return
    if objective_id is not None and objective_id in probe.progress()["objectives"]:
        return
    if quest not in probe.progress()["running"]:
        raise ValueError(("Quest is not earned and running", quest))
    with probe.store.connection() as db:
        p = db.execute(
            "SELECT value FROM settings WHERE name='native_quest_conversation_contracts'"
        ).fetchone()["value"]
    bindings = [
        r
        for r in p["bindings"]
        if r.get("quest_id") == quest
        and (objective_id is None or r["objective_id"] == objective_id)
    ]
    if len(bindings) != 1:
        raise ValueError(("Expected one actual hand-in binding", quest))
    binding = bindings[0]
    from wakfu_server.achievements import conversation

    placements = [
        r
        for r in p["placements"]
        if r["row"]["reference_id"] == binding["reference_id"]
        and binding["action_id"] in r["row"]["action_ids"]
        and conversation.placement_signature(r["row"]) == binding["placement_sha256"]
    ]
    if len(placements) != 1:
        raise ValueError("Native speaker placement is not unique")
    source = placements[0]
    row = source["row"]
    anchor = source.get("interaction_anchor", row)
    probe.move_to(row["map_id"], tuple(anchor[k] for k in ("x", "y", "z")))
    mark = probe.peer.mark()
    try:
        probe.peer.send(
            13222, struct.pack(">qq", row["actor_id"], binding["action_id"])
        )
        body = probe.peer.matching(12969, mark, timeout=20)
        node, _kind, actor = struct.unpack(">ibq", body)
        if actor != row["actor_id"]:
            raise ValueError("Unexpected actual dialogue owner")
        pending = deque([(node, [])])
        seen = {node}
        path = None
        while pending:
            at, route = pending.popleft()
            if at == binding["node_id"]:
                path = route
                break
            for origin, choice, target in source["graph"]:
                if origin == at and target and target not in seen:
                    seen.add(target)
                    pending.append((target, route + [(origin, choice, target)]))
        if path is None:
            raise ValueError(
                (
                    "Reviewed graph cannot reach final hand-in",
                    quest,
                    node,
                    binding["node_id"],
                )
            )
        destinations = [
            target
            for origin, choice, target in source["graph"]
            if (origin, choice) == (binding["node_id"], binding["choice_id"])
        ]
        if len(destinations) != 1:
            raise ValueError(
                "Actual objective binding lacks its unique reviewed dialogue destination"
            )
        path.append((binding["node_id"], binding["choice_id"], destinations[0]))
        for origin, choice, target in path:
            start = probe.peer.mark()
            probe.peer.send(12058, struct.pack(">ii", origin, choice))
            probe.peer.matching(
                12218,
                start,
                lambda frame: len(frame) == 4
                and struct.unpack(">i", frame)[0] == target,
                timeout=20,
            )
        state = probe.progress()
        if binding["objective_id"] not in state["objectives"] or (
            objective_id is None and quest not in state["completed"]
        ):
            raise AssertionError(
                ("Actual hand-in did not settle", quest, binding["objective_id"])
            )
        probe.note(
            "actual story NPC hand-in",
            quest_id=quest,
            objective_id=binding["objective_id"],
            reference_id=binding["reference_id"],
            path=path,
        )
        return state
    finally:
        capture(probe, mark)
