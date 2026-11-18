"""Reviewed public journeys between actual qualified native NPC counterparts."""


def validate_paired_arrival(placements, source_item, declaration, *, check_floor=False):
    from wakfu_server.achievements import conversation

    required = {
        "node_id",
        "choice_id",
        "target_actor_id",
        "target_placement_sha256",
        "direction",
        "evidence",
    }
    if (
        not isinstance(declaration, dict)
        or set(declaration) != required
        or any(
            type(declaration.get(key)) is not int or declaration[key] <= 0
            for key in ("node_id", "choice_id")
        )
        or type(declaration.get("target_actor_id")) is not int
        or declaration["target_actor_id"] >= 0
        or type(declaration.get("direction")) is not int
        or not 0 <= declaration["direction"] < 8
        or not isinstance(declaration.get("evidence"), str)
        or not declaration["evidence"].strip()
    ):
        raise ValueError("Paired NPC journey lacks its exact reviewed native choice")
    targets = [
        item
        for item in placements
        if item["row"]["actor_id"] == declaration["target_actor_id"]
    ]
    if len(targets) != 1:
        raise ValueError("Paired NPC journey has no unique published counterpart")
    target = targets[0]
    source_row, target_row = source_item["row"], target["row"]
    if (
        source_row["actor_id"] == target_row["actor_id"]
        or source_row["reference_id"] != target_row["reference_id"]
        or not set(source_row["action_ids"]) & set(target_row["action_ids"])
        or source_row["instance_id"] != 0
        or target_row["instance_id"] != 0
        or conversation.placement_signature(target_row)
        != declaration["target_placement_sha256"]
    ):
        raise ValueError(
            "Paired NPC journey differs from its qualified native counterpart"
        )
    if not any(
        (node, choice) == (declaration["node_id"], declaration["choice_id"])
        for node, choice, _ in source_item["graph"]
    ):
        raise ValueError("Paired NPC journey is not an actual published dialogue edge")
    anchor = target.get("interaction_anchor")
    if (
        not isinstance(anchor, dict)
        or set(anchor) != {"x", "y", "z"}
        or any(type(anchor[k]) is not int for k in anchor)
    ):
        raise ValueError(
            "Paired NPC counterpart has no reviewed physical arrival anchor"
        )
    if check_floor:
        from wakfu_server.combat_geometry import published_geometry

        if (
            tuple(anchor[k] for k in ("x", "y", "z"))
            not in published_geometry(target_row["map_id"]).cells
        ):
            raise ValueError(
                "Paired NPC arrival is outside actual native walking terrain"
            )
    return dict(map_id=target_row["map_id"], instance_id=0, **anchor)


def qualify(db, store, character, published, row, item, declaration, *, action_id):
    """Check late native predicates and both physical actors before mutation."""
    from wakfu_server import quest_npc, npc_dialogue
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    destination = validate_paired_arrival(
        published[0]["placements"], item, declaration, check_floor=True
    )
    target_row, target_item = quest_npc._row(
        db, declaration["target_actor_id"], published
    )
    # _row checks the live enabled projection/overlay against this publication.
    if (
        target_item is None
        or action_id not in target_row["action_ids"]
        or not quest_npc._nearby_placement(character, row, item)
        or character.get("instance_id", 0) != 0
        or character["map_id"] != row["map_id"]
    ):
        raise ValueError("Paired NPC journey lost its actual source or counterpart")
    authority = queries_from_state(storage.load_locked(db, character["id"]))
    node = npc_dialogue.catalog()["node_index"][declaration["node_id"]]
    choice = next(
        (c for c in node["choices"] if c["id"] == declaration["choice_id"]), None
    )
    if choice is None:
        raise ValueError("Paired NPC journey names no actual native choice")
    predicates = [node.get("criteria", ""), choice.get("criteria", "")]
    predicates.extend(
        entry["criterion"]
        for entry in item.get("choice_criteria", ())
        if (entry["node_id"], entry["choice_id"])
        == (declaration["node_id"], declaration["choice_id"])
    )
    if not all(
        quest_npc._criterion(store, character, expression, authority)
        for expression in predicates
    ):
        raise ValueError("Paired NPC journey's current native prerequisite is not met")
    return destination
