"""Shared owned END dispatch; callers retain private transactions and authority."""


def deliver_end_boundary(dispatcher, *, actor_id):
    """Run the existing ordinary sequence on the caller's private dispatcher."""
    from .combat_turn_events import deliver_turn_end, deliver_turn_regeneration

    preview = dispatcher.native_retention.fight
    from .combat_npc_phase_controller import deliver_npc_score_result

    from .combat_encounter_turn_end_order import turn_end_event_order

    objective_terminal = None
    if getattr(preview, "native_encounter_objective_policy", None) is not None:
        from .combat_encounter_objective import deliver_objective_score_marker

        deliver_objective_score_marker(dispatcher, actor_id=actor_id)
    deliver_npc_score_result(dispatcher, actor_id=actor_id)
    order = turn_end_event_order(preview, actor_id=actor_id)
    early_regeneration = order[0] == 1037
    if early_regeneration:
        deliver_turn_regeneration(dispatcher, actor_id=actor_id)
    if not early_regeneration or (
        preview.phase == "active" and preview.current is not None
    ):
        deliver_turn_end(dispatcher, actor_id=actor_id)
    if (
        preview.phase == "active"
        and preview.current is not None
        and preview.current.id == actor_id
        and getattr(preview, "native_ogrest_phase_context", None) is not None
    ):
        from .combat_ogrest_phase_controller import finish_ogrest_player_turn

        finish_ogrest_player_turn(dispatcher, actor_id=actor_id)
    if getattr(preview, "native_encounter_objective_policy", None) is not None:
        from .combat_encounter_objective import deliver_owned_objective_boundary

        objective_terminal = deliver_owned_objective_boundary(
            dispatcher, actor_id=actor_id, boundary="owned_player_end"
        )
    if (
        not early_regeneration
        and objective_terminal is None
        and preview.phase == "active"
        and preview.current is not None
    ):
        deliver_turn_regeneration(dispatcher, actor_id=actor_id)
    from .combat_encounter_terminal_cleanup import deliver_terminal_helper_cleanup

    deliver_terminal_helper_cleanup(dispatcher)
    from wakfu_server.dungeon_optional_votes import observe_turn

    observe_turn(preview, actor_id)
