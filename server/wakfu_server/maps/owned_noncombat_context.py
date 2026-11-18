"""Qualify explicit owned content without inventing combat rooms."""

NARRATIVE = "owned-story-narrative-v1"


def selected(topology):
    from wakfu_server import owned_object_trials

    mode = topology.get("policy")
    if mode not in (owned_object_trials.SCHEMA, NARRATIVE):
        return None
    if mode == NARRATIVE:
        from wakfu_server import owned_story_controller

        result = owned_story_controller.policy(dict(topology=topology))
        if result is None or any(
            step["kind"] in ("room_admission", "room_available", "room_victory")
            for step in result["steps"]
        ):
            raise ValueError("Narrative owned content cannot declare combat producers")
        other_policy = "owned_object_trials"
    else:
        result = owned_object_trials.policy(dict(topology=topology))
        other_policy = "owned_story_controller"
    if (
        result is None
        or result["map_id"] != topology.get("asset_map_id")
        or topology.get("rooms") != []
        or any(
            topology.get(key)
            for key in (
                "doors",
                "physical_doors",
                "auto_edges",
                "branch_routes",
                "optional_room_policy",
                "entry_path_policy",
                other_policy,
                "owned_quest_encounter",
            )
        )
    ):
        raise ValueError("Noncombat owned content cannot declare encounter progression")
    return result


def authenticate_bootstrap(db, store, character, configuration):
    """Qualify a roomless baseline using its actual pinned owner membership."""
    topology = configuration["topology"]
    expected = selected(topology)
    if expected is None:
        return False
    if topology["policy"] == NARRATIVE:
        from wakfu_server import owned_story_controller

        actual, _ = owned_story_controller._scope(
            db, store, character, check_position=False, lock=False
        )
    else:
        from wakfu_server import owned_object_trials

        actual, _ = owned_object_trials._scope(
            db, store, character, check_position=False, lock=False
        )
    if actual != expected:
        raise ValueError("Noncombat bootstrap differs from its pinned owner scope")
    return True
