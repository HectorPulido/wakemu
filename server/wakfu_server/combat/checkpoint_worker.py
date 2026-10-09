"""Bounded asynchronous checkpoint persistence with detached per-fight snapshots."""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from threading import Condition, Thread
from types import SimpleNamespace
import time


def serialize_detached(fight, *, runtime):
    from .fight_checkpoint_store import snapshot

    return snapshot(fight, runtime=runtime)


def checkpoint_cleanup_barrier(operation, *, failed):
    """Report checkpoint failure without skipping durable disconnect cleanup.

    This is only for socket finalization. Normal requests still propagate
    checkpoint failures. The caller must persist the fight abort/health before
    retiring a shared registry entry; a checkpoint error never authorizes that
    retirement by itself.
    """
    try:
        return operation()
    except Exception as error:
        failed(error)
        return False


@dataclass(frozen=True)
class PreparedJob:
    shared: object
    fight: object
    runtime: object
    account_id: int
    generation: str
    status: object
    trace: object
    sequence: int


def detach(shared):
    """Copy supported gameplay fields under ownership; workers never read live FSMs."""
    with shared.lock:
        fight = shared.fight
        fields = deepcopy(
            {
                key: value
                for key, value in fight.__dict__.items()
                if key not in ("actors", "native_rail_movement_authority")
            }
        )
        fields["actors"] = {
            identity: SimpleNamespace(**deepcopy(actor.__dict__))
            for identity, actor in fight.actors.items()
        }
        frozen = SimpleNamespace(**fields)
        runtime = None
        if shared.runtime is not None:
            runtime = SimpleNamespace(
                fight=frozen,
                **{
                    key: deepcopy(getattr(shared.runtime, key))
                    for key in (
                        "action_id",
                        "native_action_id",
                        "awaiting_ack",
                        "round",
                        "duration",
                    )
                },
            )
        return frozen, runtime, shared.checkpoint_revision


class CheckpointWorker:
    """Bounded SQL pool, per-fight ordered revisions and terminal barriers."""

    def __init__(
        self,
        checkpoints,
        *,
        capacity=128,
        workers=4,
        failed=None,
        serializer=serialize_detached,
    ):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Checkpoint queue capacity must be positive")
        self.checkpoints, self.capacity, self.failed = checkpoints, capacity, failed
        self.serializer = serializer
        self.condition = Condition()
        self.pending, self.order, self.states = {}, deque(), {}
        self.inflight = set()
        self.closed = False
        if type(workers) is not int or not 1 <= workers <= 8:
            raise ValueError("Checkpoint worker count must be between one and eight")
        self.threads = [
            Thread(
                target=self._run, name=f"wakfu-checkpoint-writer-{index}", daemon=True
            )
            for index in range(workers)
        ]
        for thread in self.threads:
            thread.start()

    def submit(self, shared, account_id, generation, *, status=None, trace=None):
        frozen, runtime, initial_revision = detach(shared)
        fight_id = frozen.id
        with self.condition:
            if self.closed:
                raise ValueError("Checkpoint worker is closed")
            state = self.states.get(fight_id)
            if (
                fight_id not in self.pending
                and fight_id not in self.inflight
                and len(set(self.pending) | self.inflight) >= self.capacity
            ):
                raise ValueError("Checkpoint queue capacity exhausted")
            if state is None:
                state = self.states[fight_id] = dict(
                    revision=initial_revision,
                    sequence=0,
                    committed=0,
                    terminal=False,
                    error=None,
                    owners={account_id: generation},
                )
            if (
                account_id in state["owners"]
                and state["owners"][account_id] != generation
            ):
                raise ValueError("Checkpoint writer ownership changed")
            state["owners"][account_id] = generation
            if state["error"] is not None:
                raise ValueError(
                    "Asynchronous checkpoint previously failed"
                ) from state["error"]
            if state["terminal"]:
                return dict(sequence=state["sequence"], terminal=True, replay=True)
            state["sequence"] += 1
            state["terminal"] = status is not None
            job = PreparedJob(
                shared,
                frozen,
                runtime,
                account_id,
                generation,
                status,
                trace,
                state["sequence"],
            )
            if fight_id not in self.pending:
                self.order.append(fight_id)
            self.pending[fight_id] = job
            self.condition.notify_all()
            return dict(
                sequence=job.sequence, terminal=status is not None, replay=False
            )

    def terminal_pending(self, fight_id):
        """Report accepted terminal work before duplicate notices or submissions."""
        with self.condition:
            state = self.states.get(fight_id)
            return state is not None and state["terminal"]

    def takeover_writer(
        self, fight_id, account_id, previous_generation, generation, *, persist=None
    ):
        """Advance a drained writer only after durable participant takeover."""
        with self.condition:
            state = self.states.get(fight_id)
            if state is None:
                if persist is not None:
                    persist()
                return
            if fight_id in self.pending or fight_id in self.inflight:
                raise ValueError("Checkpoint takeover requires a drained writer")
            previous = state["owners"].get(account_id)
            if previous not in (None, previous_generation):
                raise ValueError("Stale checkpoint writer takeover")
            if state["error"] is not None:
                raise ValueError("Asynchronous checkpoint failed") from state["error"]
            if persist is not None:
                persist()
            state["owners"][account_id] = generation

    def flush_fight(self, fight_id, *, timeout=10):
        """Wait only at ownership cleanup boundaries; gameplay ACKs never wait here."""
        deadline = time.monotonic() + timeout
        with self.condition:
            state = self.states.get(fight_id)
            if state is None:
                return True
            target = state["sequence"]
            while state["committed"] < target and state["error"] is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
            if state["error"] is not None:
                raise ValueError("Asynchronous checkpoint failed") from state["error"]
            return True

    def close(self, *, timeout=10):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        deadline = time.monotonic() + timeout
        for thread in self.threads:
            thread.join(max(0, deadline - time.monotonic()))
        return not any(thread.is_alive() for thread in self.threads)

    def _run(self):
        while True:
            with self.condition:
                while True:
                    eligible = next(
                        (
                            identity
                            for identity in self.order
                            if identity not in self.inflight
                        ),
                        None,
                    )
                    if eligible is not None:
                        break
                    if self.closed and not self.order and not self.inflight:
                        return
                    self.condition.wait()
                fight_id = eligible
                self.order.remove(fight_id)
                job = self.pending.pop(fight_id)
                self.inflight.add(fight_id)
                state = self.states[fight_id]
                revision = state["revision"]
            try:
                prepared = self.serializer(job.fight, runtime=job.runtime)
                revision = self.checkpoints.save_prepared(
                    job.account_id,
                    job.generation,
                    job.fight,
                    prepared,
                    expected_revision=revision,
                    trace=job.trace,
                    allow_terminal_receipt=True,
                )
                terminal_receipt = (
                    isinstance(revision, dict) and revision.get("terminal") is True
                )
                if terminal_receipt:
                    revision = revision["revision"]
                if job.status is not None and not terminal_receipt:
                    revision = self.checkpoints.end(
                        job.account_id,
                        job.generation,
                        job.fight.id,
                        expected_revision=revision,
                        status=job.status,
                        trace=job.trace,
                        allow_terminal_receipt=True,
                    )
                with job.shared.lock:
                    job.shared.checkpoint_revision = revision
                    if job.status is not None or terminal_receipt:
                        job.shared.checkpoint_terminal = True
                with self.condition:
                    state["revision"] = revision
                    state["committed"] = job.sequence
                    if terminal_receipt:
                        state["terminal"] = True
                        state["committed"] = state["sequence"]
                        self.pending.pop(fight_id, None)
                        self.order = deque(
                            identity for identity in self.order if identity != fight_id
                        )
            except Exception as error:
                with self.condition:
                    state["error"] = error
                    # Failed earlier writes cannot permit a later stale CAS or terminal write.
                    self.pending.pop(fight_id, None)
                    self.order = deque(
                        identity for identity in self.order if identity != fight_id
                    )
                if self.failed is not None:
                    try:
                        self.failed(fight_id=fight_id, error=error)
                    except Exception:
                        pass
            finally:
                with self.condition:
                    self.inflight.discard(fight_id)
                    self.condition.notify_all()
