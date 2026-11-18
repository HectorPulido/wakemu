"""Unique source-qualified private NPC targets with any-order group completion."""


def validate(selected, profile):
    groups = selected.get("npc_target_groups", ())
    targets = {
        row.get("controller_target_id"): row
        for row in profile["npcs"]
        if row.get("controller_target_id") is not None
    }
    if len(targets) != sum(
        row.get("controller_target_id") is not None for row in profile["npcs"]
    ):
        raise ValueError("Owned NPC target identities are not unique")
    steps = selected["steps"]
    ids = set()
    for group in groups:
        if (
            set(group) != {"id", "targets", "evidence"}
            or type(group["id"]) is not int
            or group["id"] <= 0
            or group["id"] in ids
            or not group["evidence"]
            or not isinstance(group["targets"], list)
            or not group["targets"]
            or len(set(group["targets"])) != len(group["targets"])
        ):
            raise ValueError("Malformed owned NPC target group")
        ids.add(group["id"])
        required = set()
        for identity in group["targets"]:
            row = targets.get(identity)
            candidates = [
                s
                for s in steps
                if s["kind"] == "npc_target" and s["reference"] == identity
            ]
            if row is None or len(candidates) != 1 or row["template_id"] != identity:
                raise ValueError(
                    "Owned NPC group lacks its exact source-qualified target"
                )
            required.add(candidates[0]["id"])
        final = [
            s
            for s in steps
            if s["kind"] == "npc_targets_completed" and s["reference"] == group["id"]
        ]
        if len(final) != 1 or not required <= set(final[0]["requires"]):
            raise ValueError("Owned NPC group completion omits a unique target")
    if set(targets) != {target for group in groups for target in group["targets"]}:
        raise ValueError("Owned NPC target lacks its declared group")
    return groups


def settle(
    db,
    store,
    character,
    selected,
    completed,
    profile,
    row,
    *,
    actor_id,
    action_id,
    executor
):
    from wakfu_server import owned_story_controller as controller, owned_story_npcs

    groups = validate(selected, profile)
    identity = row["controller_target_id"]
    if actor_id != owned_story_npcs.actor_id(character["instance_id"], identity):
        raise ValueError("Owned NPC target aliases another scoped actor")
    outcome = controller._settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="npc_target",
        reference=identity,
        evidence=dict(
            actor_id=actor_id,
            template_id=identity,
            native_reference=row["reference_id"],
            action_id=action_id,
        ),
        apply_effects=executor,
    )
    if not outcome["applied"]:
        return outcome["packets"]
    completed = set(completed) | {outcome["step"]}
    packets = list(outcome["packets"])
    for group in groups:
        if identity not in group["targets"]:
            continue
        follow = controller._settle(
            db,
            store,
            character,
            selected,
            completed,
            kind="npc_targets_completed",
            reference=group["id"],
            evidence=dict(target_ids=group["targets"], source_actor_id=actor_id),
            apply_effects=executor,
        )
        packets.extend(follow["packets"])
        if follow["applied"]:
            completed.add(follow["step"])
    return packets
