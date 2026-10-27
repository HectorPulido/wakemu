"""Bounded expiry work; socket readers only claim and consume its outcome."""
from threading import Event


def stamp(shared):
    runtime = shared.runtime
    return (
        shared.fight.turn_id,
        shared.sequence,
        getattr(runtime, "deadline_turn", None),
        getattr(runtime, "turn_deadline", None),
    )


class TurnExpiryWork:
    def __init__(self, registry, shared, session, now_ms):
        self.registry, self.shared, self.session = registry, shared, session
        self.now_ms = now_ms
        self.expected = stamp(shared)
        self.cancelled = Event()

    def cancel(self):
        self.cancelled.set()

    def __call__(self):
        shared, registry = self.shared, self.registry
        outcome = (False, None)
        with shared.lock:
            try:
                with registry.lock:
                    current = registry.fights.get(shared.fight.id)
                if (
                    not self.cancelled.is_set()
                    and current is shared
                    and shared.turn_expiry_work is self
                    and stamp(shared) == self.expected
                ):
                    try:
                        # A disconnected submitter cannot advance a live peer's
                        # turn. Another connected owner may claim a later poll.
                        registry._member(shared, self.session)
                    except ValueError:
                        pass
                    else:
                        outcome = registry.expire_current_turn(
                            shared.fight.id, self.session, now_ms=self.now_ms
                        )
            except Exception as error:
                # Preserve the existing reader error boundary without running
                # the expensive transition on that reader's thread.
                outcome = (False, error)
            if shared.turn_expiry_work is self:
                shared.turn_expiry_result = outcome
