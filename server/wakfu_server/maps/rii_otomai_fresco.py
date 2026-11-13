"""Reconstructed Otomai lore branch and the accompanying fresco mission.

Native dialogue text connects the question on the World of Twelve to the
frescoes. Its continuation and quest side effect were not captured, so these
are explicit local reconstructions, not claims about original server scripts.
"""
from copy import deepcopy

from wakfu_server import npc_observed_dialogue, npc_protectors, npc_world
from wakfu_server.achievements import mission_dependencies, mission_progress, storage

EDGES = {
    (5774, 13307): 5775,
    (5775, 13292): 5776,
    (5775, 13294): 5779,
    (5775, 13295): 5781,
    (5775, 13293): 0,
    (5776, 13296): 5777,
    (5777, 13297): 5778,
    (5778, 13298): 5775,
    (5778, 13299): 0,
    (5779, 13300): 5780,
    (5780, 13301): 5775,
    (5780, 13302): 0,
    (5781, 13303): 5775,
    (5781, 13304): 0,
}


def lore_graph(nodes):
    for (node, choice), target in EDGES.items():
        if (
            node not in nodes
            or choice not in {row["id"] for row in nodes[node]["choices"]}
            or (target and target not in nodes)
        ):
            raise ValueError("Otomai lore graph differs from native dialogue catalog")
    return dict(EDGES)


def recognizes(session, request):
    return (
        session is not None
        and session.speaker_id == 424
        and (request["node_id"], request["choice_id"]) == (5775, 13295)
    )


def choose(store, account_id, generation, character, session, request):
    """Enter Otomai's fresco explanation and start 5163 once, atomically."""
    if not recognizes(session, request):
        raise ValueError("Not the Otomai fresco conversation")
    previous = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            store.lock_character(
                db, account_id, generation, character["id"], selected=True
            )
            current = store.character(account_id, character["id"], db)
            if (current["map_id"], current["instance_id"]) != (1385, 0):
                raise ValueError("Otomai is outside the original Rii scene")
            rows = npc_world.load_scene(db, 1385, 0)
            matches = [
                row
                for row in rows
                if row["reference_id"] == 5459 and npc_protectors.speaker(row)[1] == 424
            ]
            if len(matches) != 1 or not npc_world.nearby(current, matches[0]):
                raise ValueError("Otomai is unavailable or out of range")
            row = matches[0]
            observed = npc_observed_dialogue.graph(row, session.nodes)
            if (
                observed.get((5772, 13288)) != 5773
                or observed.get((5773, 13289)) != 5774
                or session.graph.get((5775, 13295)) != 5781
            ):
                raise ValueError("Otomai dialogue provenance does not match")
            packet = session.choose(**request)
            before = storage.load_locked(db, current["id"])
            now_ms = int(store.now().timestamp() * 1000)
            planned = (before, [], [], [])
            if 5160 in before["running"] and 10613 not in before["objectives"]:
                parent_row = db.execute(
                    "SELECT data FROM native_quest_metadata_definitions WHERE revision="
                    "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
                    "AND definition_id=%s",
                    (5160,),
                ).fetchone()
                if parent_row is None:
                    raise ValueError("Missing native Rii main mission")
                planned = mission_progress.advance_objective(
                    before,
                    parent_row["data"]["native"],
                    10613,
                    character=current,
                    store=store,
                    now_ms=now_ms,
                )
                if not storage.record_event(
                    db,
                    current["id"],
                    "rii-talk:10613",
                    {
                        "kind": "reconstructed_rii_talk",
                        "objective_id": 10613,
                        "reference_id": 5459,
                        "node_id": 5775,
                        "choice_id": 13295,
                    },
                ):
                    raise ValueError("Otomai dialogue receipt exists without progress")
            after, intents, objectives, completed = planned
            if 5163 in after["running"] or 5163 in after["completed"]:
                if not objectives:
                    return {"packet": packet, "packets": []}
                result = mission_dependencies.settle(
                    db, store, current, before, planned, {}, (), now_ms=now_ms
                )
                return {"packet": packet, "packets": result["packets"]}
            definition_row = db.execute(
                "SELECT data FROM native_quest_metadata_definitions WHERE revision="
                "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
                "AND definition_id=%s",
                (5163,),
            ).fetchone()
            if definition_row is None:
                raise ValueError("Missing native fresco mission definition")
            definition = definition_row["data"]["native"]
            if (
                definition.get("d") != 5163
                or definition.get("native_class") != "aJM"
                or definition.get("aqb") is not False
                or definition.get("cjI") != ""
                or definition.get("cjU") != 0
                or definition.get("getDuration") != 0
                or [item.get("d") for item in definition.get("cjJ", ())]
                != [10628, 10629, 10630]
            ):
                raise ValueError("Native fresco mission differs from reconstruction")
            if not storage.record_event(
                db,
                current["id"],
                "rii-fresco-activation:5163",
                {
                    "kind": "reconstructed_rii_fresco_activation",
                    "definition_id": 5163,
                    "accepted_at_ms": now_ms,
                },
            ):
                raise ValueError(
                    "Fresco activation receipt exists without mission state"
                )
            after = deepcopy(after)
            after["running"] = sorted(set(after["running"]) | {5163})
            mission_progress.auto_track(after, 5163)
            result = mission_dependencies.settle(
                db,
                store,
                current,
                before,
                (after, intents, objectives, completed),
                {},
                (),
                now_ms=now_ms,
            )
            return {"packet": packet, "packets": result["packets"]}
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = previous
        raise
