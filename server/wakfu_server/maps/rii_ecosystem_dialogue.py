"""Kheperalia's returning ecosystem conversations.

The 5762 quest-return edges were captured from the original server. Alternate
population roots and the informational 5792–5794 chain are inferred from
native localized question/answer text; they were not captured in the session.
"""
from wakfu_server import npc_world, npc_protectors, npc_observed_dialogue
from wakfu_server.npc_dialogue import DialogueSession, catalog
from wakfu_server.dungeon_achievement_authority import queries_from_snapshot
from wakfu_server import dungeon_criteria

ACTOR = -1706442046308328
SPEAKER = ACTOR
ROOTS = {
    5762: (13337, 13339, 13319, 13350),
    5799: (13360, 13361, 13362, 13363),
    5800: (13364, 13365, 13366, 13367),
}
TERMINALS = {(5788, 13338): (5145, 10620, 10617), (5789, 13340): (5155, 10621, 10618)}


def _snapshot(store, account_id, character_id):
    with store.connection() as db:
        if (
            db.execute(
                "SELECT id FROM characters WHERE account_id=%s AND id=%s",
                (account_id, character_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Unknown character for Rii conversation")
        row = db.execute(
            "SELECT snapshot FROM character_achievement_authority WHERE character_id=%s",
            (character_id,),
        ).fetchone()
    if row is None:
        raise ValueError("Missing Rii quest authority")
    value = row["snapshot"]
    queries_from_snapshot(
        {key: value[key] for key in ("running", "completed", "objectives")}
    )
    return value


def _population(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT count(*) AS amount FROM combat_groups g "
            "CROSS JOIN LATERAL jsonb_array_elements(g.members) AS m "
            "WHERE g.map_id=1385 AND g.instance_id=0 AND g.status!='defeated' "
            "AND m->>'ref' IN ('5455','5456')"
        ).fetchone()
    amount = row["amount"]
    if type(amount) is not int or amount < 0:
        raise ValueError("Invalid Rii Wodent population")
    return amount


def begin(store, character_provider, rows_provider, account_id, actor_id, action_id):
    """Return a returning session or None when the intro remains applicable."""
    if actor_id != ACTOR:
        return None
    initial = character_provider()
    owner = (initial["id"], initial["account_id"])
    if initial["account_id"] != account_id:
        raise ValueError("Rii NPC owner mismatch")
    state = _snapshot(store, account_id, initial["id"])
    if 10607 not in state["objectives"]:
        return None
    rows = npc_world.validate_placements(rows_provider())
    row = next((r for r in rows if r["actor_id"] == ACTOR), None)
    if (
        row is None
        or row["reference_id"] != 5467
        or row["map_id"] != 1385
        or action_id not in row["action_ids"]
        or not npc_world.nearby(initial, row)
    ):
        raise ValueError("Rii NPC unavailable or out of range")
    count = _population(store)
    root = 5799 if count < 20 else 5800 if count > 80 else 5762
    choices = ROOTS[root]
    nodes = catalog()["node_index"]
    for node_id, expected in [
        (root, choices),
        (5788, (13338,)),
        (5789, (13340,)),
        (5792, (13351,)),
        (5793, (13352,)),
        (5794, (13353,)),
    ]:
        if node_id not in nodes or not set(expected) <= {
            c["id"] for c in nodes[node_id]["choices"]
        }:
            raise ValueError("Rii native dialogue differs from reconstructed contract")
    observed = npc_observed_dialogue.ledger()
    if observed["source_sha256"] != row["native_capture_contract"]["source_sha256"]:
        raise ValueError("Rii observed conversation source mismatch")
    expected_edges = {
        (5762, 13337): 5788,
        (5762, 13339): 5789,
        (5788, 13338): 0,
        (5789, 13340): 0,
    }
    edges = {
        (e["node_id"], e["choice_id"]): e["target_node_id"]
        for e in observed["edges"]
        if e["speaker_id"] == SPEAKER and e["initial_root"] == 5762
    }
    if any(edges.get(key) != target for key, target in expected_edges.items()):
        raise ValueError("Rii observed conversation edges unavailable")
    graph = {
        (root, choices[0]): 5788,
        (root, choices[1]): 5789,
        (root, choices[2]): 5792,
        (root, choices[3]): None,
        (5788, 13338): 0,
        (5789, 13340): 0,
        (5792, 13351): 5793,
        (5793, 13352): 5794,
        (5794, 13353): root,
    }

    def current_state():
        current = character_provider()
        if (current.get("id"), current.get("account_id")) != owner:
            raise ValueError("Rii dialogue owner changed")
        return current, _snapshot(store, account_id, owner[0])

    def criterion(entry):
        if entry["id"] == root:
            return 10607 in current_state()[1]["objectives"]
        expression = entry.get("criteria", "")
        if not expression:
            return True
        current, snapshot = current_state()
        queries = queries_from_snapshot(
            {key: snapshot[key] for key in ("running", "completed", "objectives")}
        )
        return dungeon_criteria.evaluate(
            store, expression, character=current, queries=queries
        )

    session = DialogueSession(
        nodes, graph, authorize_node=criterion, authorize_choice=criterion
    )
    kind, speaker = npc_protectors.speaker(row)

    def authorize(speaker_id, node_id):
        current = character_provider()
        latest = next((r for r in rows_provider() if r["actor_id"] == ACTOR), None)
        return (
            speaker_id == speaker
            and node_id in (root, 5788, 5789, 5792, 5793, 5794)
            and (current.get("id"), current.get("account_id")) == owner
            and latest == row
            and npc_world.nearby(current, row)
        )

    return session, session.open(root, speaker, authorize, speaker_type=kind)


def recognizes(session, request):
    return (
        session is not None
        and session.speaker_id == SPEAKER
        and (request["node_id"], request["choice_id"]) in TERMINALS
    )


def choose(store, account_id, generation, character, session, request):
    """Complete an eligible child and its matching parent in one transaction."""
    from wakfu_server.achievements import (
        mission_progress,
        mission_dependencies,
        storage,
    )
    from wakfu_server.achievements import rii_ecosystem_activation, rii_starter_seed

    key = request["node_id"], request["choice_id"]
    if not recognizes(session, request):
        raise ValueError("Not a Rii ecosystem return")
    quest_id, objective_id, parent_id = TERMINALS[key]
    previous = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            store.lock_character(
                db, account_id, generation, character["id"], selected=True
            )
            current = store.character(account_id, character["id"], db)
            rows = npc_world.load_scene(db, current["map_id"], current["instance_id"])
            row = next((r for r in rows if r["actor_id"] == ACTOR), None)
            if (
                row is None
                or row["reference_id"] != 5467
                or not npc_world.nearby(current, row)
            ):
                raise ValueError("Rii NPC unavailable or out of range")
            packet = session.choose(**request)
            before = storage.load_locked(db, current["id"])

            def definition(identity):
                value = db.execute(
                    "SELECT data FROM native_quest_metadata_definitions WHERE revision="
                    "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
                    "AND definition_id=%s",
                    (identity,),
                ).fetchone()
                if value is None:
                    raise ValueError("Missing Rii native mission definition")
                return value["data"]["native"]

            child, parent = definition(quest_id), definition(5160)
            now_ms = int(store.now().timestamp() * 1000)
            planned = mission_progress.advance_objective(
                before,
                child,
                objective_id,
                character=current,
                store=store,
                now_ms=now_ms,
            )
            if not planned[2]:
                return {"packet": packet, "packets": []}
            if not storage.record_event(
                db,
                current["id"],
                f"rii-ecosystem-return:{objective_id}",
                {"kind": "reconstructed_rii_return", "objective_id": objective_id},
            ):
                raise ValueError("Rii return receipt exists without progress")
            after, intents, objectives, completed = planned
            started = []
            if quest_id in completed:
                definitions = {
                    identity: definition(identity)
                    for identity in rii_ecosystem_activation.OBJECTIVES
                }
                after, started = rii_ecosystem_activation.plan(after, definitions)
                for identity in started:
                    if not storage.record_event(
                        db,
                        current["id"],
                        f"rii-ecosystem-activation:{identity}",
                        {
                            "kind": "reconstructed_rii_ecosystem_activation",
                            "definition_id": identity,
                        },
                    ):
                        raise ValueError(
                            "Rii ecosystem receipt exists without mission state"
                        )
            planned = (after, intents, objectives, completed)
            result = mission_dependencies.settle(
                db,
                store,
                current,
                before,
                planned,
                {quest_id: child, 5160: parent},
                ((5160, parent_id, quest_id),),
                now_ms=now_ms,
            )
            if 5155 in started:
                from wakfu_server import rii_scenario

                result["packets"].extend(
                    rii_starter_seed.grant_if_missing(db, store, current)
                )
                result["packets"].append(
                    rii_scenario.packet(rii_scenario.PLANTING_GUIDE)
                )
            return {"packet": packet, "packets": result["packets"]}
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = previous
        raise
