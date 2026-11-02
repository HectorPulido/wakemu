"""Shared ordinary/native-AI START dispatch; callers own transactions and RNG."""


def deliver_start_boundary(
    dispatcher, *, actor_id, native_events=True, area_callbacks=False
):
    """Run the ordinary committed boundary on the caller's actual dispatcher."""
    from .combat_turn_events import deliver_turn_start

    preview = dispatcher.native_retention.fight
    objective_terminal = None
    if native_events:
        from .combat_periodic_aptitude import renew_periodic_aptitudes
        from .combat_npc_phase_controller import (
            deliver_npc_score_result,
            deliver_npc_table_phase,
        )

        from .combat_equipment_external_events import deliver_completed_round

        if getattr(preview, "native_encounter_objective_policy", None) is not None:
            from .combat_encounter_objective import deliver_objective_score_marker

            deliver_objective_score_marker(dispatcher, actor_id=actor_id)
        deliver_completed_round(dispatcher)
        if getattr(preview, "native_encounter_objective_policy", None) is not None:
            from .combat_encounter_objective import deliver_owned_objective_boundary

            objective_terminal = deliver_owned_objective_boundary(
                dispatcher, actor_id=actor_id, boundary="completed_round"
            )
        if objective_terminal is None:
            renew_periodic_aptitudes(dispatcher, actor_id=actor_id)
            deliver_npc_score_result(dispatcher, actor_id=actor_id)
            if getattr(preview, "native_encounter_objective_policy", None) is not None:
                from .combat_encounter_objective import (
                    deliver_owned_objective_boundary,
                )

                objective_terminal = deliver_owned_objective_boundary(
                    dispatcher, actor_id=actor_id, boundary="owned_boss_start"
                )
            deliver_npc_table_phase(dispatcher, actor_id=actor_id)
            if preview.phase == "active" and objective_terminal is None:
                deliver_turn_start(dispatcher, actor_id=actor_id)
                if preview.phase == "active":
                    from .combat_ogrest_phase_controller import (
                        deliver_ogrest_post_turn_start,
                    )

                    deliver_ogrest_post_turn_start(dispatcher, actor_id=actor_id)
                if preview.phase == "active" and preview.current is not None:
                    from .combat_encounter_table_listeners import (
                        deliver_owned_post_start_listeners,
                    )

                    deliver_owned_post_start_listeners(dispatcher, actor_id=actor_id)
    if area_callbacks and preview.phase == "active" and objective_terminal is None:
        dispatcher.native_area_events.turn_start(actor_id)
