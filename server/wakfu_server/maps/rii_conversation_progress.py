"""Progress Rii's initial talk objectives on accredited terminal choices.

The dialogue edges were captured from the original server. Associating their
terminal choices with the matching "talk to" objectives is a local gameplay
reconstruction: the original quest side effects were not captured.
"""
from wakfu_server import npc_observed_dialogue, npc_protectors, npc_world
from wakfu_server.achievements import mission_dependencies, mission_progress, storage


# Native reference, captured speaker, final node/choice, scene and objective.
TALKS = {
    (-1706442046308322, 5770, 13283): (5461, 1385, 10612),
    (424, 5774, 13290): (5459, 1385, 10613),
    (424, 5774, 13307): (5459, 1385, 10613),
    (-1706442046308339, 5755, 13258): (5460, 1388, 10614),
    (-1706442046308339, 5756, 13260): (5460, 1388, 10614),
    (-1706442046308328, 5786, 13318): (5467, 1385, 10615),
    (-1706442035962340, 5791, 13347): (5458, 1387, 10583),
}


def recognizes(session, request):
    return (
        session is not None
        and (session.speaker_id, request["node_id"], request["choice_id"]) in TALKS
    )


def choose(store, account_id, generation, character, session, request):
    """Choose and settle in one transaction; restore session on rollback."""
    key = (session.speaker_id, request["node_id"], request["choice_id"])
    if key not in TALKS:
        raise ValueError("Unrecognized Rii conversation")
    reference_id, map_id, objective_id = TALKS[key]
    previous = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            store.lock_character(
                db, account_id, generation, character["id"], selected=True
            )
            current = store.character(account_id, character["id"], db)
            if (current["map_id"], current["instance_id"]) != (map_id, 0):
                raise ValueError("Rii conversation is outside its original scene")
            rows = npc_world.load_scene(db, map_id, 0)
            matches = [
                row
                for row in rows
                if row["reference_id"] == reference_id
                and npc_protectors.speaker(row)[1] == key[0]
            ]
            if len(matches) != 1 or not npc_world.nearby(current, matches[0]):
                raise ValueError("Rii speaker is unavailable or out of range")
            row = matches[0]
            target = 5756 if key[1:] == (5755, 13258) else 0
            if key == (424, 5774, 13307) and session.graph.get(key[1:]) == 5775:
                pass  # Observed in the official Rii session.
            elif npc_observed_dialogue.graph(row, session.nodes).get(key[1:]) != target:
                raise ValueError("Rii dialogue edge is not captured")
            packet = session.choose(**request)
            before = storage.load_locked(db, current["id"])
            packets = []
            if (
                objective_id == 10583
                and 5146 in before["running"]
                and objective_id not in before["objectives"]
            ):
                row = db.execute(
                    "SELECT data FROM native_quest_metadata_definitions WHERE revision="
                    "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
                    "AND definition_id=%s",
                    (5146,),
                ).fetchone()
                if row is None:
                    raise ValueError("Missing native sanctuary mission definition")
                definition = row["data"]["native"]
                if definition.get("d") != 5146:
                    raise ValueError("Invalid native sanctuary mission definition")
                now_ms = int(store.now().timestamp() * 1000)
                planned = mission_progress.advance_objective(
                    before,
                    definition,
                    objective_id,
                    character=current,
                    store=store,
                    now_ms=now_ms,
                )
                if not storage.record_event(
                    db,
                    current["id"],
                    "rii-talk:10583",
                    {
                        "kind": "reconstructed_rii_talk",
                        "objective_id": objective_id,
                        "reference_id": reference_id,
                        "node_id": key[1],
                        "choice_id": key[2],
                    },
                ):
                    raise ValueError("Rii dialogue receipt exists without progress")
                result = mission_dependencies.settle(
                    db,
                    store,
                    current,
                    before,
                    planned,
                    {5146: definition},
                    (),
                    now_ms=now_ms,
                )
                packets.extend(result["packets"])
            if 5160 in before["running"]:
                if objective_id == 10583:
                    return {"packet": packet, "packets": packets}

                def definition_for(identity):
                    definition_row = db.execute(
                        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
                        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
                        "AND definition_id=%s",
                        (identity,),
                    ).fetchone()
                    if definition_row is None:
                        raise ValueError("Missing native Rii mission definition")
                    return definition_row["data"]["native"]

                now_ms = int(store.now().timestamp() * 1000)
                if objective_id not in before["objectives"]:
                    planned = mission_progress.advance_objective(
                        before,
                        definition_for(5160),
                        objective_id,
                        character=current,
                        store=store,
                        now_ms=now_ms,
                    )
                    if not storage.record_event(
                        db,
                        current["id"],
                        f"rii-talk:{objective_id}",
                        {
                            "kind": "reconstructed_rii_talk",
                            "objective_id": objective_id,
                            "reference_id": reference_id,
                            "node_id": key[1],
                            "choice_id": key[2],
                        },
                    ):
                        raise ValueError("Rii dialogue receipt exists without progress")
                else:
                    planned = (before, [], [], [])
                after, intents, objectives, completed = planned
                from wakfu_server.achievements import rii_introductions

                after, new_flags, hidden_completed = rii_introductions.apply(
                    db, current["id"], after, definition_for(5154), objective_id, now_ms
                )
                objectives = list(objectives) + new_flags
                completed = list(completed) + hidden_completed
                added = False
                if objective_id == 10614:
                    from wakfu_server.achievements import rii_lesson_activation

                    after, added = rii_lesson_activation.plan(
                        after, definition_for(5143)
                    )
                    if added and not storage.record_event(
                        db,
                        current["id"],
                        "rii-lesson-activation:5143",
                        {
                            "kind": "reconstructed_rii_lesson_activation",
                            "definition_id": 5143,
                        },
                    ):
                        raise ValueError(
                            "Rii lesson receipt exists without mission state"
                        )
                elif objective_id == 10615:
                    from wakfu_server.achievements import rii_ecosystem_activation

                    definitions = {
                        identity: definition_for(identity)
                        for identity in rii_ecosystem_activation.OBJECTIVES
                    }
                    after, started = rii_ecosystem_activation.plan(after, definitions)
                    added = bool(started)
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
                    if 5145 in started:
                        from wakfu_server import rii_scenario

                        packets.append(rii_scenario.packet(rii_scenario.ECOLOGY_GUIDE))
                    if 5155 in started:
                        from wakfu_server.achievements import rii_starter_seed

                        packets.extend(
                            rii_starter_seed.grant_if_missing(db, store, current)
                        )
                if objectives or completed or added or objective_id in (10614, 10615):
                    links = ()
                    definitions = {5160: definition_for(5160)}
                    if objective_id in (10614, 10615):
                        links = mission_dependencies.RII_LINKS
                        identities = {5160} | {child for _, _, child in links}
                        definitions = {
                            identity: definition_for(identity)
                            for identity in identities
                        }
                    result = mission_dependencies.settle(
                        db,
                        store,
                        current,
                        before,
                        (after, intents, objectives, completed),
                        definitions,
                        links,
                        now_ms=now_ms,
                    )
                    packets.extend(result["packets"])
            return {"packet": packet, "packets": packets}
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = previous
        raise
