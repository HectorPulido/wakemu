"""Reviewed special-instance admission composed with the ordinary run transaction.

Native entry identity and modulation remain authoritative. External scene fees
are explicitly reconstructed policy, never hidden catalog edits or free keys.
"""


def initialize(db, session, resolved):
    from wakfu_server.native_scene_policy_authority import admission_policy
    from wakfu_server.dungeon_instances import canonical_context_key

    route = resolved["route"]
    policy = admission_policy(
        db,
        canonical_context_key(route),
        configuration_version=session["context_policy_version"],
    )
    if policy is None:
        return
    if session["context_policy_version"] < policy["minimum_configuration_version"]:
        return
    expected = policy["route"]
    for key in (
        "template_id",
        "definition_id",
        "entry_map_id",
        "entry_object_id",
        "destination_id",
        "start_map_id",
    ):
        if getattr(route, key) != expected[key] or type(expected[key]) is not int:
            raise ValueError("Special-instance admission differs from its native route")
    from wakfu_server import companions

    # Dungeon members already contain heroes. Sidekicks occupy additional
    # controlled seats and are fenced by the existing company/entry locks.
    controlled = len(session["members"]) + companions.controlled_count(
        db, session["members"]
    )
    if (
        policy.get("authority") != "reconstructed_wakemu_native_scene_v1"
        or type(policy.get("maximum_members")) is not int
        or policy["maximum_members"] <= 0
        or controlled > policy["maximum_members"]
    ):
        raise ValueError("This native special instance permits fewer participants")
    from wakfu_server import dungeon_difficulty

    native = dungeon_difficulty.definition(db, route.definition_id)
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_snapshot
    from wakfu_server.instance_entry_level import enforced

    minimum_enforced = enforced(db)

    members = db.execute(
        "SELECT c.id,c.level,a.snapshot FROM characters c "
        "JOIN character_achievement_authority a ON a.character_id=c.id "
        "WHERE c.id=ANY(%s) AND c.deleted_at IS NULL ORDER BY c.id",
        (list(session["members"]),),
    ).fetchall()
    if len(members) != len(session["members"]):
        raise ValueError("Special-instance native member authority is missing")
    for member in members:
        if not dungeon_criteria.evaluate(
            None,
            route.criterion,
            character=member,
            queries=queries_from_snapshot(member["snapshot"]),
            bypass_minimum_level=not minimum_enforced,
        ):
            raise ValueError(
                "Every special-instance participant must meet its native entry criterion"
            )
    selection = dungeon_difficulty.selection(db, session["instance_id"])
    if (
        native.get("forced_competitive") is not True
        or selection["competitive"] is not True
        or selection["competitive_max_level"] != policy["competitive_ceiling"]
        or dungeon_difficulty.ceiling_band(native["native_level"])
        != policy["competitive_ceiling"]
    ):
        raise ValueError("Special-instance native competitive profile is unavailable")
    native_destination = resolved["native_destination"]
    if native_destination.get("cyW", 0) != 0 or native_destination.get("cyX", 0) != 0:
        raise ValueError("External scene payment conflicts with a native entrance fee")
    # Native item payment belongs to the inside scene-start action, not this
    # free native teleporter. Keep only native participant/modulation checks.
    session["special_instance_admission"] = {
        "policy_id": policy["policy_id"],
        "maximum_members": policy["maximum_members"],
        "competitive_ceiling": selection["competitive_max_level"],
        "reused": session["reused"],
    }
