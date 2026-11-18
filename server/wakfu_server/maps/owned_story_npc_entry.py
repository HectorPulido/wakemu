"""Actual accepted native NPC choices entering normal owned dungeon machinery.

No teleporter packet or map object is synthesized. The conversation adapter
supplies its frozen accepted-choice proof inside the same owner transaction.
"""

KIND = "native_npc_choice"


def validate_entry(entry, *, map_id=None, cells=None):
    from wakfu_server import npc_dialogue

    required = {
        "kind",
        "map_id",
        "reference_id",
        "action_id",
        "node_id",
        "choice_id",
        "position",
        "interaction_anchor",
        "interaction_range",
        "arrival",
        "direction",
        "evidence",
    }
    if (
        not isinstance(entry, dict)
        or set(entry) != required
        or entry["kind"] != KIND
        or any(
            type(entry.get(key)) is not int or entry[key] <= 0
            for key in ("map_id", "reference_id", "action_id", "node_id", "choice_id")
        )
        or type(entry["interaction_range"]) is not int
        or not 1 <= entry["interaction_range"] <= 12
        or type(entry["direction"]) is not int
        or not 0 <= entry["direction"] < 8
        or not entry["evidence"]
        or any(
            not isinstance(entry[key], list)
            or len(entry[key]) != 3
            or any(type(v) is not int for v in entry[key])
            for key in ("position", "interaction_anchor", "arrival")
        )
    ):
        raise ValueError("Malformed native NPC owned entrance")
    native = npc_dialogue.catalog()
    speaker = next(
        (row for row in native["speakers"] if row["ref"] == entry["reference_id"]), None
    )
    node = native["node_index"].get(entry["node_id"])
    if (
        speaker is None
        or entry["action_id"] not in {a["id"] for a in speaker["actions"]}
        or node is None
        or entry["choice_id"] not in {c["id"] for c in node["choices"]}
    ):
        raise ValueError("Owned entrance names a nonnative NPC/action/choice")
    if cells is not None and entry["arrival"] not in cells:
        raise ValueError("NPC owned arrival is outside its native floor")
    return entry


def validate_route(route):
    entry = validate_entry(route.get("native_npc_entry"))
    if (
        route.get("registration_policy") != KIND
        or route.get("entry_map_id") != entry["map_id"]
        or route.get("entry_object_id") != entry["reference_id"]
        or route.get("destination_id") != entry["choice_id"]
        or route.get("native_template_id") is not None
        or route.get("native_definition_id") is not None
    ):
        raise ValueError("Owned route differs from its native NPC choice")
    return entry


def enter_choice(
    db,
    store,
    character,
    proof,
    *,
    initialize_instance=None,
    resolve_destination=None,
    allowed_position_accounts=None
):
    from wakfu_server import (
        dungeon_instances,
        dungeon_runtime_config,
        dungeon_transport,
        quest_npc,
    )
    from wakfu_server.achievements import conversation
    from wakfu_server.dungeon_achievement_authority import queries_from_state
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_criteria import evaluate

    key = proof["route_key"]
    active = db.execute(
        "SELECT policy_version FROM dungeon_runtime_active_configurations WHERE route_key=%s",
        (key,),
    ).fetchone()
    if active is None:
        raise ValueError("NPC owned destination is not activated")
    configuration = dungeon_runtime_config.pinned_configuration(
        db, key, active["policy_version"]
    )
    entry = validate_route(configuration["route"])
    route = dungeon_instances.route(key)
    published = quest_npc.publication(db)
    if (
        published is None
        or conversation._digest(published[0]) != proof["publication_sha256"]
    ):
        raise ValueError("NPC owned entry conversation publication changed")
    row, item = quest_npc._row(db, proof["actor_id"], published)
    expected = dict(
        reference_id=entry["reference_id"],
        action_id=entry["action_id"],
        node_id=entry["node_id"],
        choice_id=entry["choice_id"],
        account_id=character["account_id"],
        char_id=character["id"],
    )
    if (
        any(proof.get(field) != value for field, value in expected.items())
        or conversation.placement_signature(row) != proof["placement_sha256"]
    ):
        raise ValueError("NPC owned entry escaped its actual accepted choice")
    if (
        row["map_id"] != entry["map_id"]
        or row["instance_id"] != 0
        or [row[k] for k in ("x", "y", "z")] != entry["position"]
        or row["interaction_range"] != entry["interaction_range"]
        or entry["action_id"] not in row["action_ids"]
        or item.get("interaction_anchor")
        != dict(zip(("x", "y", "z"), entry["interaction_anchor"]))
        or not quest_npc._nearby_placement(character, row, item)
        or any(
            proof["source_position"].get(k) != character[k]
            for k in ("map_id", "instance_id", "x", "y", "z")
        )
    ):
        raise ValueError("NPC owned entry lost its actual physical source")
    if not any(
        r.get("node_id") == entry["node_id"]
        and r.get("choice_id") == entry["choice_id"]
        and r.get("route") == key
        for r in item.get("choice_routes", [])
    ):
        raise ValueError("Native NPC choice has no published owned destination")
    state = storage.load_locked(db, character["id"])
    authority = queries_from_state(state)
    public_visit = (
        configuration.get("topology", {})
        .get("owned_story_controller", {})
        .get("npc_public_visit")
    )
    if public_visit is not None:
        from wakfu_server import owned_story_entry_variants

        selected = configuration["topology"]["owned_story_controller"]
        assigned = any(
            authority["IsAchievementRunning"](quest)
            for quest in owned_story_entry_variants.quest_ids(selected["admission"])
        )
        if not assigned:
            if (
                allowed_position_accounts is None
                or character["account_id"] not in allowed_position_accounts
            ):
                raise ValueError("Public NPC trip escaped its owned position fence")
            target = public_visit_destination(public_visit)
            from wakfu_server import mission_transport

            saved, packets = mission_transport.public_transition_locked(
                db,
                store,
                character["account_id"],
                proof["generation"],
                character,
                target,
            )
            return dict(
                public_arrival=saved,
                direction=public_visit["direction"],
                packets=packets,
            )

    def criterion_allowed(current, expression):
        return evaluate(
            store,
            expression,
            character=current,
            queries=authority,
            now_ms=int(store.now().timestamp() * 1000),
        )

    def source_allowed(current, source):
        return (
            current["id"] == character["id"]
            and source == row
            and quest_npc._nearby_placement(current, row, item)
        )

    destination = dict(
        map_id=route.start_map_id,
        **dict(zip(("x", "y", "z"), entry["arrival"])),
        direction=entry["direction"]
    )
    resolved = dict(
        route=route,
        source=row,
        difficulty_selection=None,
        native_destination=dict(cyW=0, item_reference=0),
        destination=destination,
    )
    return dungeon_transport.enter_resolved(
        store,
        character["account_id"],
        proof["generation"],
        character["id"],
        resolved,
        criterion_allowed=criterion_allowed,
        source_allowed=source_allowed,
        initialize_instance=initialize_instance,
        resolve_destination=resolve_destination,
        allowed_position_accounts=allowed_position_accounts,
        _db=db,
    )


def route_target_map(db, route_key):
    from wakfu_server import dungeon_instances

    return dungeon_instances.route(route_key).start_map_id


def public_visit_destination(value):
    """A questless trip approaches a proven native entrance without activating it."""
    from wakfu_server import generic_transports, quest_npc, dungeon_runtime_config

    required = {
        "schema",
        "source_map_id",
        "source_object_id",
        "source_sha256",
        "approach",
        "direction",
        "evidence",
    }
    if (
        type(value) is not dict
        or set(value) != required
        or value.get("schema") != "native-npc-public-visit-v1"
        or not value.get("evidence")
    ):
        raise ValueError("Public NPC visit lacks a native exterior declaration")
    source = generic_transports.source(
        value["source_map_id"], value["source_object_id"]
    )
    if (
        source is None
        or dungeon_runtime_config.canonical_hash(source) != value["source_sha256"]
    ):
        raise ValueError(
            "Public NPC visit source differs from its frozen native endpoint"
        )
    return quest_npc.qualify_approach_arrival(source, value)
