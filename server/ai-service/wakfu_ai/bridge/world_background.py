"""Detached shared NPC turns; socket delivery stays with session readers."""

from copy import deepcopy
from threading import Event
import time

from .world_sources import bind_private_sources
from .world_shared import run_shared_turn
from ..native.native_control import effective_server_controlled


def admission(shared):
    """Older engine images remain on their existing foreground path."""
    try:
        from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
        from wakfu_server.combat_background_work import NATIVE_WORK
    except ModuleNotFoundError as error:
        if error.name not in {
            "wakfu_server.combat_expiration_provider",
            "wakfu_server.combat_background_work",
        }:
            raise
        return "server_capability_missing"
    if getattr(shared.fight, "rift_wave_state", None) is not None:
        return "rift_providers_unqualified"
    if getattr(shared.runtime, "clock", time.monotonic) is not time.monotonic:
        return "custom_clock_unqualified"
    provider = getattr(shared.runtime, "expiration_runtime_factory", None)
    if type(provider) is not OwnedExpirationFactory:
        return "legacy_lifecycle_providers"
    return None


class BackgroundTurn:
    def __init__(
        self, shared, adapter, session, runner, store, viewer, monsters, diagnostics
    ):
        self.shared, self.adapter, self.session = shared, adapter, session
        self.queued_at = time.monotonic()
        self.runner, self.store = runner, store
        self.viewer, self.monsters = deepcopy((viewer, monsters))
        self.diagnostics = diagnostics
        self.owner = (session.account_id, session.generation, session.character_id)
        self.cancelled = Event()
        self.claim = None
        self.actor_id = shared.fight.current.id
        self.turn_id = shared.fight.turn_id
        self.sequence = shared.sequence
        self.runtime = shared.runtime

    def cancel(self):
        self.cancelled.set()
        with self.shared.lock:
            if (
                self.claim is not None
                and getattr(self.shared, "native_ai_turn_claim", None) == self.claim
            ):
                self.shared.native_ai_turn_claim = None

    def prepare(self, runtime, session):
        if self.cancelled.is_set():
            raise ValueError("Background native work was cancelled")
        self.claim = getattr(self.shared, "native_ai_turn_claim", None)
        bind_private_sources(runtime, session)

    def __call__(self):
        from wakfu_server.performance_profiler import PROFILER

        wall, cpu = time.perf_counter(), time.thread_time()
        failed = True
        try:
            failed = self._execute()
        finally:
            PROFILER.observe(
                "combat.ai_turn.background",
                time.perf_counter() - wall,
                time.thread_time() - cpu,
                error=failed,
            )

    def _execute(self):
        from wakfu_server.performance_profiler import PROFILER

        started_at = time.monotonic()
        queue_wait_ms = max(0.0, (started_at - self.queued_at) * 1000)
        PROFILER.observe("combat.ai_turn.queue_wait", queue_wait_ms / 1000, 0.0)
        try:
            if self.cancelled.is_set():
                return False
            for _, diagnostic in run_shared_turn(
                self.runtime,
                self.adapter,
                self.session,
                lambda native: self.runner(
                    native,
                    store=self.store,
                    viewer_character=self.viewer,
                    monsters=self.monsters,
                    stats_serializer=None,
                ),
                prepare_candidate=self.prepare,
                expected_turn=(self.actor_id, self.turn_id),
                expected_sequence=self.sequence,
                started_at=started_at,
            ):
                self.diagnostics.put(
                    self.owner,
                    dict(
                        event="combat_monster_tactical_action",
                        fight_id=self.shared.fight.id,
                        decision=diagnostic,
                        background=True,
                        queue_wait_ms=queue_wait_ms,
                    ),
                )
            return False
        except Exception as error:
            with self.shared.lock:
                current = self.shared.fight.current
                if (
                    not self.cancelled.is_set()
                    and self.shared.fight.phase == "active"
                    and current is not None
                    and (current.id, self.shared.fight.turn_id)
                    == (self.actor_id, self.turn_id)
                ):
                    self.shared.native_npc_retry = (
                        (self.actor_id, self.turn_id),
                        time.monotonic() + 2.0,
                    )
            self.diagnostics.put(
                self.owner,
                dict(
                    event="combat_background_native_failed",
                    fight_id=self.shared.fight.id,
                    actor_id=self.actor_id,
                    turn_id=self.turn_id,
                    error_type=type(error).__name__,
                    reason=str(error)[:512],
                ),
            )
            return True


def schedule(shared, adapter, session, runner, store, viewer, monsters, diagnostics):
    from wakfu_server.combat_background_work import NATIVE_WORK

    with shared.lock:
        adapter.registry._member(shared, session)
        current = shared.fight.current
        if (
            shared.fight.phase != "active"
            or current is None
            or not effective_server_controlled(shared.fight, current)
            or shared.runtime.awaiting_ack is not None
            or shared.runtime.pending
        ):
            return "stale"
        previous = getattr(shared, "native_npc_retry", None)
        if (
            previous is not None
            and previous[0] == (current.id, shared.fight.turn_id)
            and time.monotonic() < previous[1]
        ):
            return "backoff"
        key = ("native-ai", id(shared))
        status = NATIVE_WORK.status(key)
        if status is not None:
            return status
        if getattr(shared, "native_ai_turn_claim", None) is not None:
            return "duplicate"
        job = BackgroundTurn(
            shared, adapter, session, runner, store, viewer, monsters, diagnostics
        )
        # The shared identity fences recycled IDs and limits even stale work
        # from a previous actor/turn to one outstanding job for this encounter.
        return NATIVE_WORK.submit(key, job)
