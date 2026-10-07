"""Adapt the complete embedding session context without another world patch."""
from ..planning.team_blackboard import observe, confirm


def _outcomes(runtime, deliveries):
    iterator = iter(deliveries)
    while True:
        before = observe(runtime.fight)
        try:
            packets, diagnostic = next(iterator)
        except StopIteration:
            return
        yield packets, diagnostic, before


def execute(runtime, world_context, runner):
    if (
        not isinstance(world_context, dict)
        or set(world_context) != {"globals", "scopes"}
        or not isinstance(world_context["globals"], dict)
        or not isinstance(world_context["scopes"], list)
        or any(not isinstance(scope, dict) for scope in world_context["scopes"])
    ):
        raise ValueError("Incomplete embedding world context")
    bindings = dict(world_context["globals"])
    # The outer socket session owns viewer/account/connection identity.
    # Helpers may contain temporary characters while preparing other actors.
    for scope in world_context["scopes"]:
        bindings.update(scope)
    if runtime is None or runtime.fight is None:
        return
    session = bindings.get("combat_session")
    adapter = bindings.get("COMBAT_SESSIONS")
    if session is not None:
        bindings["refresh_shared_combat"]()
        shared = adapter.registry.lookup(runtime.fight.id)
        runtime = shared.runtime
    if (
        runtime is None
        or runtime.fight is None
        or runtime.fight.current is None
        or runtime.fight.current.controlled
        or runtime.awaiting_ack is not None
        or runtime.pending
    ):
        return
    for packets, diagnostic, before in _outcomes(
        runtime,
        runner(
            runtime,
            store=bindings["STORE"],
            viewer_character=bindings["character"],
            monsters=bindings["TEST_MONSTERS_BY_ID"],
            stats_serializer=bindings.get("current_combat_stats"),
            shared_adapter=adapter,
            session=session,
        ),
    ):
        if session is not None:
            bindings["refresh_shared_combat"]()
            bindings["drain_shared_combat"]()
            fight = adapter.registry.lookup(runtime.fight.id).fight
        else:
            for opcode, body in packets:
                bindings["send"](
                    bindings["connection"], bindings["service"], opcode, body
                )
            if packets:
                confirm(runtime, before, [diagnostic])
            fight = runtime.fight
        bindings["record"](
            event="combat_monster_tactical_action",
            fight_id=fight.id,
            decision=diagnostic,
        )
        yield [], diagnostic
        if fight.phase == "finished":
            if session is None:
                bindings["complete_test_fight"]()
            else:
                bindings["record"](
                    event="combat_shared_finished_pending_settlement", fight_id=fight.id
                )
            return
