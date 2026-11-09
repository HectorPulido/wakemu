"""Complete native SDK entry point loaded by the final stable world shim."""
from ..native.native_control import effective_server_controlled
import time


def run_npc_turn(
    runtime,
    *,
    store=None,
    viewer_character=None,
    monsters=None,
    stats_serializer=None,
    shared_adapter=None,
    session=None,
    world_context=None,
    _selection_error=None,
    _expected_turn=None,
):
    """Receive complete live dependencies once; return native FIFO deliveries."""
    if world_context is not None:
        selected_turn = None
        if (
            not isinstance(world_context, dict)
            or set(world_context) != {"globals", "scopes"}
            or not isinstance(world_context["globals"], dict)
            or not isinstance(world_context["scopes"], list)
            or any(not isinstance(scope, dict) for scope in world_context["scopes"])
        ):
            raise ValueError("Incomplete embedding world context")
        # Capture the selected turn before entering its shared coordinator.
        bindings = dict(world_context["globals"])
        for scope in world_context["scopes"]:
            bindings.update(scope)
        session = bindings.get("combat_session")
        shared = None
        if session is not None and runtime is not None and runtime.fight is not None:
            bindings["refresh_shared_combat"]()
            shared = bindings["COMBAT_SESSIONS"].registry.lookup(runtime.fight.id)
            runtime = shared.runtime
        if (
            runtime is not None
            and runtime.fight is not None
            and runtime.fight.phase == "active"
            and runtime.fight.current is not None
            and runtime.awaiting_ack is None
            and not runtime.pending
            and effective_server_controlled(runtime.fight, runtime.fight.current)
        ):
            from .backend_selection import pin_backend

            try:
                if shared is None:
                    selected_turn = (runtime.fight.current.id, runtime.fight.turn_id)
                    pin_backend(runtime)
                else:
                    with shared.lock:
                        live = shared.runtime
                        if live is None or live.fight is None:
                            return
                        current = live.fight.current
                        if (
                            live.fight.phase != "active"
                            or current is None
                            or live.awaiting_ack is not None
                            or live.pending
                            or not effective_server_controlled(live.fight, current)
                        ):
                            return
                        selected_turn = (current.id, live.fight.turn_id)
                        pin_backend(live)
            except (ValueError, TypeError, OSError) as error:
                # Leave failure handling to the runner inside the ordinary
                # shared-turn transaction; never mutate its live runtime here.
                _selection_error = error
            if selected_turn is not None:
                world_context = dict(
                    world_context,
                    scopes=[
                        *world_context["scopes"],
                        {"_wakia_expected_turn": selected_turn},
                    ],
                )
        from .world_host import execute

        from functools import partial

        yield from execute(
            runtime,
            world_context,
            partial(run_npc_turn, _selection_error=_selection_error),
        )
        return
    if session is not None:
        if shared_adapter is None:
            raise ValueError("Shared native AI requires its encounter coordinator")
        from .backend_selection import pin_backend

        try:
            if (
                _selection_error is None
                and runtime.fight.phase == "active"
                and runtime.fight.current is not None
                and runtime.awaiting_ack is None
                and not runtime.pending
                and effective_server_controlled(runtime.fight, runtime.fight.current)
            ):
                pin_backend(runtime)
        except (ValueError, TypeError, OSError) as error:
            _selection_error = error
        from .world_shared import run_shared_turn
        from ..native.native_commit_capability import _WORLD_NATIVE_RUNNER

        yield from run_shared_turn(
            runtime,
            shared_adapter,
            session,
            lambda candidate: run_npc_turn(
                candidate,
                store=store,
                viewer_character=viewer_character,
                monsters=monsters,
                stats_serializer=stats_serializer,
                _selection_error=_selection_error,
            ),
            native_runner_authority=_WORLD_NATIVE_RUNNER,
            expected_turn=_expected_turn,
        )
        return
    if runtime.awaiting_ack is not None or runtime.pending:
        return
    from wakfu_server.combat_automatic_npc_turn import requires_automatic_npc_turn_end

    if requires_automatic_npc_turn_end(runtime.fight, runtime.fight.current):
        yield runtime.end_automatic_npc_turn(
            runtime.fight.current.id, runtime.fight.turn_id
        ), dict(
            action={"type": "end_turn"},
            reason="ordinary_root_without_action_controller",
        )
        return
    # The preparation phase must fail as a turn outcome, not disconnect the
    # owning game session before the turn driver can apply its fallback.
    from psycopg import Error as DatabaseError

    bridge_started = time.monotonic()
    try:
        from .backend_selection import pin_backend

        if _selection_error is not None:
            raise _selection_error
        pin_backend(runtime)
        from .jondo_entry import run_npc_turn as runner

        yield from runner(
            runtime,
            store=store,
            viewer_character=viewer_character,
            monsters=monsters,
            stats_serializer=stats_serializer,
        )
    except (ValueError, TypeError, OSError, DatabaseError) as error:
        diagnostic = dict(
            action={"type": "end_turn"},
            reason="complete_native_bridge_rejected",
            detail=str(error),
            error=type(error).__name__,
            stage="bridge_preparation",
            bridgeElapsedMs=(time.monotonic() - bridge_started) * 1000,
        )
        yield [], diagnostic
        fight = runtime.fight
        if (
            fight.phase == "active"
            and fight.current is not None
            and effective_server_controlled(fight, fight.current)
            and runtime.awaiting_ack is None
            and not runtime.pending
        ):
            yield runtime.end_server_turn(fight.current.id, fight.turn_id), diagnostic
