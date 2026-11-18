"""Production mode factories using the ordinary durable combat services."""
import secrets
import time


def callbacks(app):
    """Return one request's transaction/start and postcommit publication pair."""
    runtime, state = app.runtime, app.state
    if not callable(getattr(app, "current_combat_stats", None)):
        raise ValueError("Native order actor serializers are unavailable")
    pending = {}

    def start(db, store, current, proof, capability):
        from wakfu_server import native_order_trial_context, native_order_trial_arena
        from wakfu_server import native_order_trial_encounter as encounter
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.spells import default_deck
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_server_spell import server_runtime

        if pending:
            raise ValueError("Order start already constructed its admitted attempt")
        scoped = native_order_trial_context.scope(db, store, current)
        arena = native_order_trial_arena.prepare(scoped, current, proof)
        # Reuse the ordinary scene START template; no border area is added.
        arena.setdefault("terrain_effect_id", 46)
        resources = combat_resources(current, wp=runtime.COMBAT_TEST_WP)
        selected = current.get("builds", {}).get(
            current.get("active_build_index", 0), {}
        )
        deck = (
            bytes.fromhex(selected["deck"])
            if selected.get("deck")
            else default_deck(current)
        )
        terrain_identity = secrets.randbelow(2**60) + 1024

        def initialize(fight):
            # This is the selected client's real native bootstrap authority,
            # not an invented original-instance publication or replay frame.
            if not state.connection.instance_publications.bind_encounter(
                fight,
                state.connection.native_instance_scope(),
                npc_ids=(),
                player_id=current["id"],
            ):
                raise ValueError(
                    "Order start requires its actually written instance publication"
                )
            initialize_fight_snapshots(
                fight,
                characters={current["id"]: current},
                monsters={},
                wp_resources={current["id"]: (resources["wp"], resources["wp"])},
                running_effects={current["id"]: ()},
                initial_effect_uid=1,
            )
            factory, _ = server_runtime(current, {}, deck, action_id=1, critical=False)
            dispatcher, _ = factory(
                fight, {"native_retained_container": {"present": False}}
            )
            return dispatcher

        prepared = encounter.create_durable(
            db,
            store,
            current,
            proof,
            capability=capability,
            arena=arena,
            initialize_runtime=initialize,
            resources=dict(
                player_ap=resources["ap"],
                player_mp=resources["mp"],
                player_wp=resources["wp"],
                player_initiative=resources["initiative"],
                terrain_effect_id=arena["terrain_effect_id"],
                terrain_instance_id=terrain_identity,
            ),
        )
        prepared.update(
            character=current,
            terrain_identity=terrain_identity,
            started_at=time.monotonic(),
        )
        pending.update(prepared)
        return True

    def publish(_app, accepted):
        if _app is not app or accepted is not True or not pending:
            raise ValueError("Order publication has no committed mode constructor")
        from wakfu_server.native_order_trial_checkpoint import validate_fight

        fight, proof, current = pending["fight"], pending["proof"], pending["character"]
        validate_fight(fight)
        from wakfu_server.native_order_trial_encounter import policy_for

        policy = policy_for(fight)
        session = runtime.COMBAT_SESSIONS.session(
            proof.account_id, proof.generation, current
        )
        runtime.COMBAT_SESSIONS.register(
            session,
            fight,
            runtime=None,
            join_context=dict(
                arena=pending["arena"],
                terrain_effect_id=pending["arena"]["terrain_effect_id"],
                terrain_instance_id=pending["terrain_identity"],
                leaders={policy.player_team: current["id"], policy.npc_team: 0},
                duration_ms=60000,
                monsters={},
                group_key=None,
                fight_started_at=pending["started_at"],
                world_marker_cells=((current["x"], current["y"]),),
                world_marker_origin=(current["x"], current["y"], current["z"]),
            ),
        )
        state.character, state.fight = current, fight
        state.combat_session = session
        state.TEST_MONSTERS, state.TEST_MONSTERS_BY_ID = (), {}
        state.TEST_GROUP_KEY = None
        state.fight_started_at = pending["started_at"]
        state.placement_deadline.start(fight.id, 60000, state.fight_started_at)
        runtime.send_batch(state.connection, state.service, pending["packets"])
        pending.clear()
        return True

    return start, publish
