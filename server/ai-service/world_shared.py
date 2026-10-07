"""Publish AI commits through the existing shared fight authority and ACKs."""

if __package__:
    from .native_context import encode
    from .team_blackboard import observe, confirm
else:
    from native_context import encode
    from team_blackboard import observe, confirm


class _NoPublication(Exception):
    """Abort Registry adoption when the runner produced no public outcome."""


def run_shared_turn(runtime, adapter, session, runner):
    from wakfu_server.combat_shared import Transition

    registry = adapter.registry
    shared = registry.lookup(runtime.fight.id)
    diagnostics = []
    with shared.lock:
        registry._member(shared, session)
        current = shared.fight.current
        if (
            shared.runtime is None
            or current is None
            or current.controlled
            or shared.runtime.awaiting_ack is not None
            or shared.runtime.pending
        ):
            return
        actor_id, turn_id = current.id, shared.fight.turn_id
        before = observe(shared.fight)

        def operation(candidate, native):
            if native is None or native.fight is not candidate:
                raise ValueError("Shared native encounter/runtime identity differs")
            # Freeze every coordinator data field, including future fields,
            # participant leases, ACK receipts, outboxes and join context.
            # The lock is execution authority rather than a transferable
            # object; the encounter/runtime themselves already form the root.
            metadata = dict(vars(shared))
            metadata["fight"] = dict(nativeReference="runtime.fight")
            metadata["runtime"] = dict(nativeReference="runtime")
            metadata["lock"] = dict(
                module=type(shared.lock).__module__,
                name=type(shared.lock).__qualname__,
                ownerThread=True,
            )
            native.native_ai_shared_context = encode(metadata)
            packets = []
            for deliveries, diagnostic in runner(native):
                packets.extend(deliveries)
                diagnostics.append(diagnostic)
            if not packets:
                raise _NoPublication()
            return Transition(native.fight, native, tuple(packets))

        # Registry stages a private pair, adopts it once and broadcasts the
        # exact ordered packets to every connected participant. No live ACK
        # is consumed by AI and no owning socket gets a duplicate direct send.
        try:
            registry.execute_server(
                shared.fight.id, actor_id, operation, expected_sequence=shared.sequence
            )
        except _NoPublication:
            return
        if shared.runtime.awaiting_ack is not None:
            registry.arm_ack(shared.fight.id, shared.runtime.awaiting_ack)
        confirm(shared.runtime, before, diagnostics)
    for diagnostic in diagnostics:
        yield [], dict(diagnostic, shared=True, actorId=actor_id, turnId=turn_id)
