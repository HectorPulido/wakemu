"""Coalesced dirty intents with bounded asynchronous snapshot persistence."""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, replace
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
    source: object
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
        self.database_health_epoch = 0
        self.database_health_down = False
        self.renewal_receipts = {}
        self.failed_fights = set()
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
        # Pending work retains only the canonical fight, not another full FSM.
        # Workers acquire its lock before materializing a bounded snapshot.
        with shared.lock:
            fight_id = shared.fight.id
            initial_revision = shared.checkpoint_revision
            # Shared combat transitions are copy-on-write. Pin the accepted
            # terminal version so registry retirement/replacement cannot change
            # the receipt, without duplicating a full FSM on the input thread.
            source = (
                None
                if status is None
                else SimpleNamespace(
                    fight=shared.fight,
                    runtime=shared.runtime,
                    lock=shared.lock,
                    checkpoint_revision=initial_revision,
                )
            )
        with self.condition:
            if self.closed:
                raise ValueError("Checkpoint worker is closed")
            state = self.states.get(fight_id)
            if state is None:
                state = self.states[fight_id] = dict(
                    revision=initial_revision,
                    sequence=0,
                    committed=0,
                    terminal=False,
                    error=None,
                    recovery=None,
                    takeover=None,
                    takeover_attempts=set(),
                    takeover_previous={},
                    health_retry_epoch=None,
                    failure_health_epoch=None,
                    explicit_recovery_tokens=set(),
                    owners={account_id: generation},
                )
            if (
                account_id in state["owners"]
                and state["owners"][account_id] != generation
            ):
                raise ValueError("Checkpoint writer ownership changed")
            state["owners"][account_id] = generation
            self.renewal_receipts.setdefault((account_id, generation), None)
            if state["terminal"]:
                return dict(sequence=state["sequence"], terminal=True, replay=True)
            state["sequence"] += 1
            state["terminal"] = status is not None
            job = PreparedJob(
                shared,
                source,
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

    def retry_failed(self, fight_id, account_id, generation):
        """Explicit recovery request; workers reconcile the uncertain CAS first.

        This never runs SQL on the calling thread and never schedules an
        automatic endless retry after an exhausted attempt group.
        """
        with self.condition:
            state = self.states.get(fight_id)
            if state is None or state["error"] is None:
                return False
            if state["owners"].get(account_id) != generation:
                raise ValueError("Checkpoint recovery belongs to another writer")
            if not self._transient(state["error"]):
                raise ValueError(
                    "Checkpoint requires authoritative state repair"
                ) from state["error"]
            state["error"] = None
            self.condition.notify_all()
            return True

    @staticmethod
    def _transport_failure(error):
        from psycopg import InterfaceError, OperationalError

        if isinstance(error, (ConnectionError, TimeoutError, InterfaceError)):
            return True
        if not isinstance(error, OperationalError):
            return False
        code = getattr(error, "sqlstate", None)
        return (
            code is None or code.startswith("08") or code in ("57P01", "57P02", "57P03")
        )

    def observe_database_health(
        self, account_id, generation, *, renewed_until=None, error=None
    ):
        """Use existing authenticated lease writes as availability witnesses.

        A failed renewal followed by a successful new receipt defines a new
        epoch. Ordinary healthy idle calls never repeatedly reset a failed
        write's budget. Checkpoint transport failure seeds the first outage;
        after its recovery group fails, another failed renewal is required.
        """
        with self.condition:
            key = (account_id, generation)
            if key not in self.renewal_receipts:
                return dict(epoch=self.database_health_epoch, resumed=0)
            if error is not None:
                if self._transport_failure(error):
                    self.database_health_down = True
                return dict(epoch=self.database_health_epoch, resumed=0)
            if renewed_until is None or self.renewal_receipts[key] == renewed_until:
                return dict(epoch=self.database_health_epoch, resumed=0)
            self.renewal_receipts[key] = renewed_until
            if self.database_health_down:
                self.database_health_down = False
                self.database_health_epoch += 1
            resumed = 0
            for fight_id in tuple(self.failed_fights):
                state = self.states[fight_id]
                pending = self.pending.get(fight_id)
                if (
                    state["error"] is None
                    or not self._transport_failure(state["error"])
                    or state["recovery"] is None
                    or state["takeover"] is not None
                    or pending is None
                    or (pending.account_id, pending.generation) != key
                    or state["failure_health_epoch"] is None
                    or self.database_health_epoch <= state["failure_health_epoch"]
                ):
                    continue
                state["health_retry_epoch"] = self.database_health_epoch
                state["error"] = None
                self.failed_fights.discard(fight_id)
                resumed += 1
            if resumed:
                self.condition.notify_all()
            return dict(epoch=self.database_health_epoch, resumed=resumed)

    def recover_pending(self, fight_id, account_id, generation, *, request_token):
        """Retry one explicit owned recovery request, deduplicating its receipt."""
        with self.condition:
            state = self.states.get(fight_id)
            if state is None or state["error"] is None:
                return False
            if state["owners"].get(account_id) != generation:
                raise ValueError("Checkpoint recovery belongs to another writer")
            key = (account_id, generation, request_token)
            if key in state["explicit_recovery_tokens"]:
                return False
            if not self._transient(state["error"]) or state["takeover"] is not None:
                return False
            state["explicit_recovery_tokens"].add(key)
            state["error"] = None
            self.failed_fights.discard(fight_id)
            self.condition.notify_all()
            return True

    def flush_for_takeover(
        self, fight_id, account_id, previous_generation, generation, *, timeout=10
    ):
        """Drain, with one authenticated replacement recovery per new login.

        Called only before registry takeover, never under its fight lock. SQL
        remains on the worker; repeated idle probes cannot reset retry budgets.
        """
        deadline = time.monotonic() + timeout
        key = (account_id, generation)
        with self.condition:
            state = self.states.get(fight_id)
            if state is not None:
                current = state["owners"].get(account_id)
                lineage, cursor = set(), current
                while cursor is not None and cursor not in lineage:
                    lineage.add(cursor)
                    cursor = state["takeover_previous"].get((account_id, cursor))
                if previous_generation not in lineage:
                    raise ValueError("Checkpoint takeover belongs to another writer")
        try:
            return self.flush_fight(
                fight_id, timeout=max(0, deadline - time.monotonic())
            )
        except ValueError:
            with self.condition:
                state = self.states.get(fight_id)
                if (
                    state is None
                    or state["error"] is None
                    or not self._transient(state["error"])
                    or key in state["takeover_attempts"]
                    or generation == previous_generation
                    or state["recovery"] is None
                ):
                    raise
                state["takeover_attempts"].add(key)
                state["takeover_previous"][key] = previous_generation
                uncertain_takeover = state["takeover"]
                recovery_generations = set(lineage)
                if (
                    uncertain_takeover is not None
                    and uncertain_takeover["account_id"] == account_id
                ):
                    recovery_generations.add(uncertain_takeover["generation"])
                    recovery_generations.update(
                        uncertain_takeover.get("recovery_generations", ())
                    )
                state["takeover"] = dict(
                    account_id=account_id,
                    previous_generation=previous_generation,
                    generation=generation,
                    recovery_generations=tuple(sorted(recovery_generations)),
                )
                state["error"] = None
                self.condition.notify_all()
            return self.flush_fight(
                fight_id, timeout=max(0, deadline - time.monotonic())
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
            if previous not in (None, previous_generation) and not (
                previous == generation
                and state["takeover_previous"].get((account_id, generation))
                == previous_generation
            ):
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
        with self.condition:
            return not self.pending and not any(
                thread.is_alive() for thread in self.threads
            )

    @staticmethod
    def _transient(error):
        # Validation/CAS errors are never retried as transport failures.
        from psycopg import InterfaceError, OperationalError

        return isinstance(
            error, (ConnectionError, TimeoutError, OperationalError, InterfaceError)
        )

    def _write_with_recovery(self, job, frozen, prepared, revision, *, status=None):
        uncertain = False
        last_error = None
        for _ in range(3):
            try:
                if uncertain:
                    receipt = self.checkpoints.reconcile_write(
                        job.account_id,
                        job.generation,
                        frozen,
                        prepared,
                        expected_revision=revision,
                        status=status,
                    )
                    if receipt["committed"]:
                        return (
                            dict(revision=receipt["revision"], terminal=True)
                            if status is None and receipt["terminal"]
                            else receipt["revision"]
                        )
                    uncertain = False
                if status is None:
                    return self.checkpoints.save_prepared(
                        job.account_id,
                        job.generation,
                        frozen,
                        prepared,
                        expected_revision=revision,
                        trace=job.trace,
                        allow_terminal_receipt=True,
                    )
                return self.checkpoints.end(
                    job.account_id,
                    job.generation,
                    frozen.id,
                    expected_revision=revision,
                    status=status,
                    trace=job.trace,
                    allow_terminal_receipt=True,
                )
            except Exception as error:
                if not self._transient(error):
                    raise
                last_error, uncertain = error, True
        # A third lost commit response still deserves one read-only receipt
        # check. No fourth write attempt or unbounded retry is scheduled.
        receipt = self.checkpoints.reconcile_write(
            job.account_id,
            job.generation,
            frozen,
            prepared,
            expected_revision=revision,
            status=status,
        )
        if receipt["committed"]:
            return (
                dict(revision=receipt["revision"], terminal=True)
                if status is None and receipt["terminal"]
                else receipt["revision"]
            )
        raise last_error

    def _run(self):
        while True:
            with self.condition:
                while True:
                    eligible = next(
                        (
                            identity
                            for identity in self.order
                            if identity not in self.inflight
                            and self.states[identity]["error"] is None
                            and len(self.inflight) < self.capacity
                        ),
                        None,
                    )
                    if eligible is not None:
                        break
                    if self.closed and not self.inflight:
                        return
                    self.condition.wait()
                fight_id = eligible
                self.order.remove(fight_id)
                job = self.pending.pop(fight_id)
                self.inflight.add(fight_id)
                state = self.states[fight_id]
                revision = state["revision"]
            try:
                frozen, runtime, _ = detach(job.source or job.shared)
                prepared = self.serializer(frozen, runtime=runtime)
                if state["recovery"] is not None:
                    previous = state["recovery"]
                    takeover = state["takeover"]
                    if takeover is None:
                        receipt = self.checkpoints.reconcile_write(
                            job.account_id,
                            job.generation,
                            frozen,
                            None,
                            expected_revision=previous["revision"],
                            status=previous["status"],
                            snapshot_digest=previous["digest"],
                            receipt_writer=(
                                previous["account_id"],
                                previous["generation"],
                            ),
                        )
                    else:
                        # This transaction authenticates the replacement login;
                        # never try to authenticate SQL using the expired lease.
                        for attempt in range(3):
                            try:
                                receipt = self.checkpoints.recover_write_for_takeover(
                                    takeover["account_id"],
                                    takeover["previous_generation"],
                                    takeover["generation"],
                                    frozen,
                                    previous,
                                    recovery_generations=takeover[
                                        "recovery_generations"
                                    ],
                                )
                                break
                            except Exception as error:
                                if not self._transient(error) or attempt == 2:
                                    raise
                        with self.condition:
                            state["owners"][takeover["account_id"]] = takeover[
                                "generation"
                            ]
                            self.renewal_receipts.setdefault(
                                (takeover["account_id"], takeover["generation"]), None
                            )
                            if job.account_id == takeover["account_id"]:
                                job = replace(job, generation=takeover["generation"])
                            queued = self.pending.get(fight_id)
                            if (
                                queued is not None
                                and queued.account_id == takeover["account_id"]
                            ):
                                self.pending[fight_id] = replace(
                                    queued, generation=takeover["generation"]
                                )
                            state["takeover"] = None
                    if receipt["committed"]:
                        revision = receipt["revision"]
                        if receipt["terminal"]:
                            with job.shared.lock:
                                job.shared.checkpoint_revision = revision
                                job.shared.checkpoint_terminal = True
                            with self.condition:
                                state["revision"] = revision
                                state["committed"] = state["sequence"]
                                state["terminal"] = True
                                state["recovery"] = None
                                self.pending.pop(fight_id, None)
                                self.order = deque(
                                    i for i in self.order if i != fight_id
                                )
                            continue
                    else:
                        revision = previous["revision"]
                    state["recovery"] = None
                from .fight_checkpoint_store import checkpoint_digest

                digest = checkpoint_digest(prepared)
                state["recovery"] = dict(
                    revision=revision,
                    status=None,
                    digest=digest,
                    account_id=job.account_id,
                    generation=job.generation,
                )
                revision = self._write_with_recovery(job, frozen, prepared, revision)
                terminal_receipt = (
                    isinstance(revision, dict) and revision.get("terminal") is True
                )
                if terminal_receipt:
                    revision = revision["revision"]
                if job.status is not None and not terminal_receipt:
                    state["recovery"] = dict(
                        revision=revision,
                        status=job.status,
                        digest=digest,
                        account_id=job.account_id,
                        generation=job.generation,
                    )
                    revision = self._write_with_recovery(
                        job, frozen, prepared, revision, status=job.status
                    )
                with job.shared.lock:
                    job.shared.checkpoint_revision = revision
                    if job.status is not None or terminal_receipt:
                        job.shared.checkpoint_terminal = True
                with self.condition:
                    state["revision"] = revision
                    state["recovery"] = None
                    self.failed_fights.discard(fight_id)
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
                    # Traceback frames retain the detached FSM; failure state
                    # stores only the exception and compact reconciliation facts.
                    seen, current = set(), error
                    while current is not None and id(current) not in seen:
                        seen.add(id(current))
                        current.__traceback__ = None
                        current = current.__cause__ or current.__context__
                    state["error"] = error
                    self.failed_fights.add(fight_id)
                    state["failure_health_epoch"] = self.database_health_epoch
                    if (
                        self._transport_failure(error)
                        and state["health_retry_epoch"] != self.database_health_epoch
                    ):
                        self.database_health_down = True
                    # Retain the latest intent for explicit recovery; exhausted
                    # retries must neither loop forever nor silently drop work.
                    if fight_id not in self.pending:
                        self.pending[fight_id] = job
                        self.order.append(fight_id)
                if self.failed is not None:
                    try:
                        self.failed(fight_id=fight_id, error=error)
                    except Exception:
                        pass
            finally:
                frozen = runtime = prepared = None
                with self.condition:
                    self.inflight.discard(fight_id)
                    self.condition.notify_all()
