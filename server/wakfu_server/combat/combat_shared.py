"""Shared fight dispatcher and fenced participant outboxes.

Network adapter drains each session mailbox through its serialized socket writer.
Every combat command must enter execute/ready/join; connection-local FSMs must
not remain authoritative. Runtime/codec factories never send or persist inside
these transactions: they produce owned packet batches before the FSM commits.
"""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock, RLock
from .combat_multiplayer_wire import decode_join, added
from .combat_bootstrap import placement_positions
from .combat_ack_barrier import AckBarrier


@dataclass(frozen=True)
class Session:
    account_id: int
    character_id: int
    generation: str
    map_id: int
    instance_id: int

    def __post_init__(self):
        if (
            any(
                type(n) is not int or n <= 0
                for n in (self.account_id, self.character_id, self.map_id)
            )
            or type(self.instance_id) is not int
            or self.instance_id < 0
            or not self.generation
        ):
            raise ValueError("Invalid combat participant session")


@dataclass
class Batch:
    sequence: int
    packets: tuple


@dataclass(frozen=True)
class Transition:
    """A candidate state replacement and its ordered public packet batch."""

    fight: object
    runtime: object
    packets: tuple


@dataclass
class SharedFight:
    fight: object
    map_id: int
    instance_id: int
    runtime: object
    group_lease: object = None
    participants: dict = field(default_factory=dict)
    connected: set = field(default_factory=set)
    outboxes: dict = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock)
    sequence: int = 0
    auto_locked: bool = False
    ack: AckBarrier = field(default_factory=AckBarrier)
    join_context: object = None
    settlement_ready: bool = False
    settlement_batches: dict = field(default_factory=dict)
    returned: set = field(default_factory=set)
    dispatch_lock: object = field(default_factory=Lock)
    checkpoint_revision: object = None
    checkpoint_terminal: bool = False
    disconnect_abort_pending: bool = False
    withdrawals: dict = field(default_factory=dict)

    def seed_checkpoint_revision(self, revision):
        """Initialize from a socket read without regressing a newer revision."""
        if revision is not None and (type(revision) is not int or revision < 1):
            raise ValueError("Invalid shared fight checkpoint revision")
        with self.lock:
            if self.checkpoint_revision is None:
                self.checkpoint_revision = revision
            return self.checkpoint_revision


class Registry:
    def __init__(self, live_session):
        """live_session(Session)->bool must verify current Store lease/selection."""
        self.live_session = live_session
        self.lock = RLock()
        self.fights = {}
        self.by_actor = {}
        self.by_character = {}

    def _live(self, session):
        if not isinstance(session, Session) or not self.live_session(session):
            raise ValueError("Stale combat session lease")

    def _member(self, shared, session):
        self._live(session)
        if (
            shared.participants.get(session.account_id) != session
            or session.account_id not in shared.connected
            or session.account_id in shared.withdrawals
        ):
            raise ValueError("Session does not own this fight membership")

    @staticmethod
    def _packets(packets):
        packets = tuple(packets)
        if any(
            not isinstance(p, tuple)
            or len(p) != 2
            or type(p[0]) is not int
            or not 0 <= p[0] <= 0xFFFF
            or not isinstance(p[1], bytes)
            or len(p[1]) > 0xFFFFFFFF - 6
            for p in packets
        ):
            raise ValueError("Combat batch must contain native opcode/body pairs")
        return packets

    def _broadcast(self, shared, packets, *, exclude=()):
        packets = self._packets(packets)
        shared.sequence += 1
        for account in shared.connected - set(exclude):
            shared.outboxes[account].append(Batch(shared.sequence, packets))
        return shared.sequence

    @classmethod
    def _transition(cls, result, fight, runtime):
        if isinstance(result, Transition):
            return result.fight, result.runtime, cls._packets(result.packets)
        return fight, runtime, cls._packets(result)

    def register(
        self, fight, starter, *, runtime=None, group_lease=None, join_context=None
    ):
        self._live(starter)
        owners = {a.owner_id for a in fight.actors.values() if a.controlled}
        if owners != {starter.account_id} or starter.character_id not in fight.actors:
            raise ValueError("Initial fight requires its owned starter")
        with self.lock:
            if (
                fight.id in self.fights
                or starter.character_id in self.by_character
                or any(a in self.by_actor for a in fight.actors)
            ):
                raise ValueError("Fight/actor already registered")
            shared = SharedFight(fight, starter.map_id, starter.instance_id, runtime)
            shared.group_lease = group_lease
            shared.join_context = join_context
            shared.participants[starter.account_id] = starter
            shared.connected.add(starter.account_id)
            shared.outboxes[starter.account_id] = deque()
            self.fights[fight.id] = shared
            self.by_character[starter.character_id] = fight.id
            self.by_actor.update((actor_id, fight.id) for actor_id in fight.actors)
            return shared

    def register_duel(
        self,
        fight,
        sessions,
        *,
        runtime=None,
        auto_locked=False,
        initial_packets=None,
        leases_validated=False,
        join_context=None,
    ):
        """Register a consented two-owner duel created by durable invitation flow.

        This is intentionally separate from ``register`` (one starter owner)
        and ``join`` (same-team late admission). The caller must have inserted
        both participant rows and prepared every native bootstrap before
        calling; it publishes no packets itself.
        """
        if (
            getattr(fight, "phase", None) != "placement"
            or type(getattr(fight, "id", None)) is not int
            or not 0 < fight.id < 2**31
            or type(auto_locked) is not bool
        ):
            raise ValueError("Invalid shared duel placement")
        sessions = tuple(sessions)
        controlled = {
            actor.id: actor for actor in fight.actors.values() if actor.controlled
        }
        if len(sessions) != 2 or set(controlled) != {
            session.character_id for session in sessions
        }:
            raise ValueError("A duel requires exactly two controlled owners")
        if len({session.account_id for session in sessions}) != 2:
            raise ValueError("Duel owners must be distinct accounts")
        if {controlled[session.character_id].team for session in sessions} != {0, 1}:
            raise ValueError("A duel requires opposing owner teams")
        map_instances = {(session.map_id, session.instance_id) for session in sessions}
        if len(map_instances) != 1:
            raise ValueError("Duel sessions must share map and instance")
        if initial_packets is None:
            initial_packets = {}
        if not isinstance(initial_packets, dict) or set(initial_packets) != {
            session.account_id for session in sessions
        }:
            raise ValueError("Duel bootstrap packets must cover both owners")
        initial_packets = {
            account: self._packets(packets)
            for account, packets in initial_packets.items()
        }
        if type(leases_validated) is not bool:
            raise ValueError("Invalid duel lease validation flag")
        for session in sessions:
            if not leases_validated:
                self._live(session)
            actor = controlled[session.character_id]
            if actor.owner_id != session.account_id or actor.hp <= 0:
                raise ValueError("Duel actor does not match its live owner")
        map_id, instance_id = next(iter(map_instances))
        with self.lock:
            if (
                fight.id in self.fights
                or any(actor_id in self.by_actor for actor_id in fight.actors)
                or any(
                    session.character_id in self.by_character for session in sessions
                )
            ):
                raise ValueError("Duel fight or actor already registered")
            shared = SharedFight(fight, map_id, instance_id, runtime)
            shared.auto_locked = auto_locked
            shared.join_context = join_context
            shared.is_duel = True
            shared.sequence = 1
            for session in sessions:
                shared.participants[session.account_id] = session
                shared.connected.add(session.account_id)
                shared.outboxes[session.account_id] = deque(
                    [Batch(shared.sequence, initial_packets[session.account_id])]
                )
                self.by_character[session.character_id] = fight.id
            self.fights[fight.id] = shared
            self.by_actor.update((actor_id, fight.id) for actor_id in fight.actors)
            return shared

    def unregister_unpublished(self, fight_id):
        """Compensate a duel reservation before its first outbox is drained."""
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                if (
                    shared.sequence != 1
                    or shared.settlement_ready
                    or shared.returned
                    or any(len(box) != 1 for box in shared.outboxes.values())
                ):
                    raise ValueError("Cannot roll back a published duel registry")
                self._remove_locked(self, shared)
                return True

    def lookup(self, fight_id):
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                raise ValueError("Unknown shared fight")
            return shared

    def lookup_character(self, character_id):
        """Return the registered fight for a character without exposing maps."""
        with self.lock:
            fight_id = self.by_character.get(character_id)
            if fight_id is None:
                return None
            return self.fights.get(fight_id)

    def join(
        self,
        session,
        body,
        actor,
        *,
        actor_payload,
        bootstrap_packets,
        persist_member=None,
    ):
        """bootstrap_packets(candidateFSM,shared,session)->own native packets.

        Joined actor appears in the world before this call. Factory must build
        the joiner's full owned placement bootstrap. Existing owners get13091.
        """
        request = decode_join(body)
        self._live(session)
        with self.lock:
            fight_id = self.by_actor.get(request["target_id"])
            if fight_id is None:
                raise ValueError("Target has no registered fight")
            shared = self.fights[fight_id]
            with shared.lock:
                fight = shared.fight
                target = fight.actors.get(request["target_id"])
                if getattr(shared, "is_duel", False):
                    raise ValueError(
                        "Friendly duel roster cannot admit another fighter"
                    )
                if fight.phase != "placement" or shared.auto_locked:
                    raise ValueError("Fight is no longer joinable")
                if (session.map_id, session.instance_id) != (
                    shared.map_id,
                    shared.instance_id,
                ):
                    raise ValueError("Foreign fight map/instance")
                if target is None or target.hp <= 0 or not target.controlled:
                    raise ValueError("Join target is not an allied player")
                if (
                    session.character_id in self.by_character
                    or session.account_id in shared.participants
                ):
                    raise ValueError("Owner already participating")
                if (
                    actor.id != session.character_id
                    or not actor.controlled
                    or actor.owner_id != session.account_id
                    or actor.team != target.team
                    or actor.hp <= 0
                ):
                    raise ValueError("Joined actor ownership/team invalid")
                occupied = {a.position for a in fight.actors.values() if a.hp > 0}
                cells = sorted(fight.placement[target.team] - occupied)
                if not cells:
                    raise ValueError("Native team placement capacity exhausted")
                candidate, runtime = deepcopy((fight, shared.runtime))
                new_actor = deepcopy(actor)
                new_actor.position = cells[0]
                candidate.actors[new_actor.id] = new_actor
                candidate._check_positions()
                candidate._event(
                    "joined",
                    actor_id=new_actor.id,
                    owner_id=session.account_id,
                    team=new_actor.team,
                    position=new_actor.position,
                )
                stats, effects = actor_payload(candidate, new_actor, session)
                notification = added(
                    candidate.id,
                    new_actor.id,
                    actor_type=0,
                    team=new_actor.team,
                    stats=stats,
                    effects=effects,
                )
                own_packets = self._packets(
                    bootstrap_packets(candidate, shared, session)
                )
                # Persistence runs only after all validators and serializers
                # succeed, while the registry lock still reserves the chosen
                # cell. A dispatcher can persist the participant row here in
                # its own short transaction before publishing the in-memory
                # membership and its outboxes.
                if persist_member is not None:
                    if not callable(persist_member):
                        raise ValueError(
                            "Participant persistence hook must be callable"
                        )
                    persist_member(candidate, new_actor, shared, session)
                # All validators/serializers/persistence completed: commit the
                # shared FSM, durable identity and ordered outboxes.
                shared.fight = candidate
                shared.runtime = runtime
                shared.participants[session.account_id] = session
                shared.connected.add(session.account_id)
                shared.outboxes[session.account_id] = deque()
                self.by_character[session.character_id] = candidate.id
                self.by_actor[new_actor.id] = candidate.id
                shared.auto_locked = request["auto_lock"]
                sequence = self._broadcast(
                    shared,
                    [notification, (13026, placement_positions(candidate))],
                    exclude=(session.account_id,),
                )
                shared.outboxes[session.account_id].append(Batch(sequence, own_packets))
                return shared

    def execute(
        self,
        fight_id,
        session,
        actor_id,
        operation,
        *,
        expected_sequence=None,
        require_turn=True,
    ):
        """operation(candidateFSM,runtime)->packets; mutation commits once.

        Serialized socket requests get server sequence checks; no callbacks may
        bypass this dispatcher for casts/move/ready/end-turn/ack. Runtime objects
        are immutable inputs here; action callbacks cannot mutate runtime caches.
        """
        shared = self.lookup(fight_id)
        with shared.lock:
            self._member(shared, session)
            if expected_sequence is not None and expected_sequence != shared.sequence:
                raise ValueError("Stale shared combat sequence")
            actor = shared.fight.actors.get(actor_id)
            if (
                actor is None
                or not actor.controlled
                or actor.owner_id != session.account_id
                or actor.hp <= 0
            ):
                raise ValueError("Foreign/dead combat actor")
            if require_turn and (
                shared.fight.current is None or shared.fight.current.id != actor_id
            ):
                raise ValueError("Not current owned turn")
            candidate, runtime = deepcopy((shared.fight, shared.runtime))
            candidate, runtime, packets = self._transition(
                operation(candidate, runtime), candidate, runtime
            )
            shared.fight = candidate
            shared.runtime = runtime
            return self._broadcast(shared, packets)

    def execute_server(self, fight_id, actor_id, operation, *, expected_sequence):
        """Internal AI only; no route accepts this method from a player packet."""
        shared = self.lookup(fight_id)
        with shared.lock:
            if expected_sequence != shared.sequence:
                raise ValueError("Stale server combat sequence")
            actor = shared.fight.current
            if actor is None or actor.id != actor_id or actor.controlled:
                raise ValueError("Not current server-controlled turn")
            candidate, runtime = deepcopy((shared.fight, shared.runtime))
            candidate, runtime, packets = self._transition(
                operation(candidate, runtime), candidate, runtime
            )
            shared.fight = candidate
            shared.runtime = runtime
            return self._broadcast(shared, packets)

    def lease_active(self, group_lease):
        """Group recovery callback: shared lifecycle, not starter socket lifetime.

        All disconnected fights remain reserved until explicit timeout/abort
        settlement. The network adapter must settle before deleting the registry.
        """
        with self.lock:
            return any(
                shared.group_lease == group_lease for shared in self.fights.values()
            )

    def lease_generation_active(self, generation):
        """Match the generation component of a persistent group lease."""
        with self.lock:
            return any(
                shared.group_lease is not None
                and len(shared.group_lease) == 4
                and shared.group_lease[1] == generation
                for shared in self.fights.values()
            )

    def arm_ack(self, fight_id, turn):
        shared = self.lookup(fight_id)
        with shared.lock:
            sessions = [
                s
                for a, s in shared.participants.items()
                if a in shared.connected and self.live_session(s)
            ]
            shared.ack.arm(turn, sessions)

    def acknowledge(self, fight_id, session, body, release_packets):
        """All recipients ACK; no current-actor ownership check applies here.

        release_packets(candidateFSM,runtime,body) consumes native pending
        acknowledge_turn once after all clients have processed12502.
        """
        shared = self.lookup(fight_id)
        with shared.lock:
            self._member(shared, session)
            if not shared.ack.accept(session, body):
                return False
            candidate, runtime = deepcopy((shared.fight, shared.runtime))
            candidate, runtime, packets = self._transition(
                release_packets(candidate, runtime, body), candidate, runtime
            )
            shared.fight = candidate
            shared.runtime = runtime
            shared.ack.release()
            self._broadcast(shared, packets)
            return True

    def expire_current_turn(self, fight_id, session, *, now_ms):
        """Run a timed shared turn end once and publish it to the whole roster.

        Every connected participant has an idle loop. The shared fight lock is
        the claim for the common deadline; without it, both socket loops could
        independently end/recover the same turn and send each owner a
        different native action sequence.
        """
        self._live(session)
        shared = self.lookup(fight_id)
        with shared.lock:
            self._member(shared, session)
            if shared.fight.phase != "active":
                return False, None
            # An outstanding barrier means another transition has already
            # published its turn boundary. Never replace its state or packets.
            if shared.ack.turn is not None:
                return False, None
            candidate, runtime = deepcopy((shared.fight, shared.runtime))
            if runtime is None or runtime.fight is not candidate:
                raise ValueError("Shared fight runtime is missing or stale")
            actor = candidate.current
            if actor is None or not actor.controlled:
                return False, None
            packets, error = runtime.expire_current_or_recover(
                actor.owner_id, now_ms=now_ms
            )
            if not packets:
                return False, error
            packets = self._packets(packets)
            next_ack = deepcopy(shared.ack)
            if runtime.awaiting_ack is not None:
                sessions = [
                    participant
                    for account, participant in shared.participants.items()
                    if account in shared.connected and self.live_session(participant)
                ]
                next_ack.arm(runtime.awaiting_ack, sessions)
            shared.fight = candidate
            shared.runtime = runtime
            shared.ack = next_ack
            self._broadcast(shared, packets)
            return True, error

    def ready(self, fight_id, session, ready, packets):
        def change(fight, runtime):
            if fight.phase != "placement":
                raise ValueError("Placement finished")
            fight.ready(session.account_id, ready)
            return packets(fight, runtime)

        return self.execute(
            fight_id, session, session.character_id, change, require_turn=False
        )

    def drain(self, fight_id, session):
        shared = self.lookup(fight_id)
        with shared.lock:
            self._member(shared, session)
            queue = shared.outboxes[session.account_id]
            batches = list(queue)
            queue.clear()
            return batches

    def dispatch_connected(self, fight_id, deliver):
        """Drain and deliver every connected owner's batches in sequence order.

        The per-fight dispatch lock serializes socket batches, while the fight
        and Registry locks are released before ``deliver`` performs I/O.
        """
        shared = self.lookup(fight_id)
        with shared.dispatch_lock:
            with shared.lock:
                recipients = []
                for account in sorted(shared.connected):
                    session = shared.participants.get(account)
                    queue = shared.outboxes.get(account)
                    if session is None or queue is None or not queue:
                        continue
                    batches = tuple(queue)
                    queue.clear()
                    recipients.append((session, batches))
            failure = None
            for session, batches in recipients:
                try:
                    deliver(session, batches)
                except Exception as error:
                    # One broken peer must not prevent the other connected
                    # owners from receiving their already-drained batches.
                    if failure is None:
                        failure = error
            if failure is not None:
                raise failure
            return tuple(session for session, _ in recipients)

    def publish(self, fight_id, session, packets):
        """Append one public ordered batch for every connected participant."""
        shared = self.lookup(fight_id)
        with shared.lock:
            self._member(shared, session)
            return self._broadcast(shared, packets)

    def takeover(self, fight_id, session, bootstrap_packets, *, persist_takeover=None):
        self._live(session)
        shared = self.lookup(fight_id)
        with shared.lock:
            previous = shared.participants.get(session.account_id)
            if (
                previous is None
                or previous.character_id != session.character_id
                or (session.map_id, session.instance_id)
                != (shared.map_id, shared.instance_id)
            ):
                raise ValueError("Foreign combat takeover")
            if session.account_id in shared.returned:
                raise ValueError("Combat participant already returned")
            if session.account_id in shared.withdrawals:
                raise ValueError("PvE participant already withdrew")
            if shared.disconnect_abort_pending:
                raise ValueError(
                    "Combat is being closed after its last owner disconnected"
                )
            if previous.generation == session.generation:
                raise ValueError("Session already current")
            if self.live_session(previous):
                raise ValueError("Previous combat owner lease still live")
            if shared.settlement_ready:
                packets = shared.settlement_batches.get(session.account_id)
                if packets is None:
                    raise ValueError("Settled owner packets are unavailable")
                packets = self._packets(packets)
            else:
                packets = self._packets(
                    bootstrap_packets(shared.fight, shared, session)
                )
            if persist_takeover is not None:
                persist_takeover(previous)
            shared.participants[session.account_id] = session
            shared.connected.add(session.account_id)
            shared.outboxes[session.account_id] = deque(
                [Batch(shared.sequence, packets)]
            )
            return shared

    def disconnect(self, session):
        """Fence old finalizers; never release starter's group behind other owners."""
        with self.lock:
            shared_fights = tuple(self.fights.values())
        affected = []
        for shared in shared_fights:
            with shared.lock:
                if shared.participants.get(session.account_id) == session:
                    shared.connected.discard(session.account_id)
                    shared.outboxes[session.account_id].clear()
                    if (
                        not shared.connected
                        and not getattr(shared, "is_duel", False)
                        and not shared.settlement_ready
                        and shared.fight.phase in ("placement", "active")
                    ):
                        # Claim last-owner cleanup before the caller releases
                        # the socket lease. A racing reconnect must not revive
                        # a fight whose abort transaction is about to commit.
                        shared.disconnect_abort_pending = True
                    affected.append(shared.fight.id)
        return affected

    @staticmethod
    def _remove_locked(registry, shared):
        del registry.fights[shared.fight.id]
        for actor_id in shared.fight.actors:
            if registry.by_actor.get(actor_id) == shared.fight.id:
                registry.by_actor.pop(actor_id, None)
        for participant in shared.participants.values():
            if registry.by_character.get(participant.character_id) == shared.fight.id:
                registry.by_character.pop(participant.character_id, None)

    def withdraw_pve(self, session, *, persist, placement_ready=None):
        """Commit one owner's private exit without ending its teammates' fight.

        Persistence receives the unchanged authoritative fight for HP. All
        public/private encodings are validated first; failure retains original
        state and outboxes. The caller sends private_packets to this owner and
        keeps private_runtime until its native12925 callback.
        """
        self._live(session)
        with self.lock:
            fight_id = self.by_character.get(session.character_id)
            shared = self.fights.get(fight_id)
            if shared is None:
                raise ValueError("Unknown shared PvE membership")
            shared.lock.acquire()
        try:
            if shared.participants.get(session.account_id) != session:
                raise ValueError("Foreign PvE withdrawal membership")
            if session.account_id in shared.withdrawals:
                return shared.withdrawals[session.account_id]
            self._member(shared, session)
            if getattr(shared, "is_duel", False) or shared.settlement_ready:
                raise ValueError("Individual withdrawal requires unresolved PvE")
            from .combat_pve_withdraw import plan

            withdrawal = plan(session, shared.fight, shared.runtime)
            public = self._packets(withdrawal.public_packets)
            self._packets(withdrawal.private_packets)
            if withdrawal.fight.phase == "placement":
                remaining_owners = {
                    actor.owner_id
                    for actor in withdrawal.fight.actors.values()
                    if actor.controlled and not getattr(actor, "pve_withdrawn", False)
                }
                if remaining_owners <= withdrawal.fight.ready_owners:
                    if not callable(placement_ready):
                        raise ValueError(
                            "Withdrawal Ready requires native initialization authority"
                        )
                    from dataclasses import replace

                    transition = placement_ready(
                        shared, withdrawal.fight, withdrawal.runtime
                    )
                    if not isinstance(transition, Transition):
                        raise ValueError("Invalid withdrawal Ready transition")
                    public += self._packets(transition.packets)
                    withdrawal = replace(
                        withdrawal, fight=transition.fight, runtime=transition.runtime
                    )
            barrier = deepcopy(shared.ack)
            barrier.expected.pop(session.account_id, None)
            barrier.received.discard(session.account_id)
            if barrier.complete:
                import struct

                counter = barrier.release()
                public += self._packets(
                    withdrawal.runtime.acknowledge_turn(struct.pack(">i", counter))
                )
            saved = persist(shared.fight)
            if not isinstance(saved, dict) or "character" not in saved:
                raise ValueError("Invalid durable PvE withdrawal result")
            shared.fight, shared.runtime, shared.ack = (
                withdrawal.fight,
                withdrawal.runtime,
                barrier,
            )
            shared.withdrawals[session.account_id] = dict(
                session=session,
                withdrawal=withdrawal,
                character=saved["character"],
            )
            shared.connected.discard(session.account_id)
            shared.outboxes[session.account_id].clear()
            self._broadcast(shared, public)
            return shared.withdrawals[session.account_id]
        finally:
            shared.lock.release()

    def return_withdrawn_pve(self, fight_id, session, *, persist):
        """Free only this participant's indexes after its durable native ACK."""
        self._live(session)
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                raise ValueError("Unknown withdrawn PvE encounter")
            with shared.lock:
                receipt = shared.withdrawals.get(session.account_id)
                if receipt is None or receipt["session"] != session:
                    raise ValueError("Foreign or stale PvE withdrawal return")
                saved = persist()
                shared.returned.add(session.account_id)
                for identity in receipt["withdrawal"].removed_actor_ids:
                    if self.by_actor.get(identity) == fight_id:
                        self.by_actor.pop(identity)
                if self.by_character.get(session.character_id) == fight_id:
                    self.by_character.pop(session.character_id)
                if (
                    shared.fight.phase == "finished"
                    and shared.fight.winner is None
                    and shared.returned == set(shared.participants)
                ):
                    self._remove_locked(self, shared)
                return saved

    def recover_withdrawn_pve(self, session, *, persist):
        """A replacement selected lease returns to world, never to combat."""
        self._live(session)
        with self.lock:
            fight_id = self.by_character.get(session.character_id)
            shared = self.fights.get(fight_id)
            if shared is None:
                return None
            with shared.lock:
                receipt = shared.withdrawals.get(session.account_id)
                if (
                    receipt is None
                    or receipt["session"].character_id != session.character_id
                ):
                    return None
                previous = receipt["session"]
                if previous.generation != session.generation and self.live_session(
                    previous
                ):
                    raise ValueError("Previous PvE withdrawal lease is still active")
                saved = persist(fight_id, previous.generation)
                receipt["session"] = session
                shared.participants[session.account_id] = session
                shared.returned.add(session.account_id)
                for identity in receipt["withdrawal"].removed_actor_ids:
                    if self.by_actor.get(identity) == fight_id:
                        self.by_actor.pop(identity)
                if self.by_character.get(session.character_id) == fight_id:
                    self.by_character.pop(session.character_id)
                if (
                    shared.fight.phase == "finished"
                    and shared.fight.winner is None
                    and shared.returned == set(shared.participants)
                ):
                    self._remove_locked(self, shared)
                return saved

    def clear_disconnect_abort(self, fight_id):
        """Allow recovery after a failed last-owner abort persistence attempt."""
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                if shared.connected or not shared.disconnect_abort_pending:
                    return False
                shared.disconnect_abort_pending = False
                return True

    def retire_disconnected_pve(self, fight_id, session):
        """Forget a PvE registry entry only after its durable abort succeeded."""
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                if (
                    getattr(shared, "is_duel", False)
                    or shared.participants.get(session.account_id) != session
                    or shared.connected
                    or not shared.disconnect_abort_pending
                    or shared.settlement_ready
                    or shared.fight.phase not in ("placement", "active")
                ):
                    return False
                self._remove_locked(self, shared)
                return True

    def retire_abandoned_single_owner(self, fight_id, session):
        """Retire the native abandon continuation for a one-owner shared PvE fight."""
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                runtime = shared.runtime
                if (
                    getattr(shared, "is_duel", False)
                    or set(shared.participants) - set(shared.withdrawals)
                    != {session.account_id}
                    or shared.participants.get(session.account_id) != session
                    or runtime is None
                    or getattr(runtime, "abandon_owner", None)
                    != (session.account_id, session.character_id)
                    or not getattr(runtime, "abandon_returned", False)
                    or shared.fight.phase != "finished"
                    or shared.fight.winner is not None
                    or shared.settlement_ready
                ):
                    return False
                shared.returned.add(session.account_id)
                shared.connected.discard(session.account_id)
                for identity in shared.fight.actors:
                    if self.by_actor.get(identity) == fight_id:
                        self.by_actor.pop(identity)
                if self.by_character.get(session.character_id) == fight_id:
                    self.by_character.pop(session.character_id)
                if shared.returned == set(shared.participants):
                    self._remove_locked(self, shared)
                return True

    def retire_disconnected_abandon(self, fight_id, session):
        """Release an already-durable singleton abandon if its ACK socket closes."""
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                runtime = shared.runtime
                if (
                    getattr(shared, "is_duel", False)
                    or set(shared.participants) - set(shared.withdrawals)
                    != {session.account_id}
                    or shared.participants.get(session.account_id) != session
                    or session.account_id in shared.connected
                    or runtime is None
                    or getattr(runtime, "abandon_owner", None)
                    != (session.account_id, session.character_id)
                    or shared.fight.phase != "finished"
                    or shared.fight.winner is not None
                    or shared.settlement_ready
                ):
                    return False
                shared.returned.add(session.account_id)
                for identity in shared.fight.actors:
                    if self.by_actor.get(identity) == fight_id:
                        self.by_actor.pop(identity)
                if self.by_character.get(session.character_id) == fight_id:
                    self.by_character.pop(session.character_id)
                if shared.returned == set(shared.participants):
                    self._remove_locked(self, shared)
                return True

    def forfeit_duel(self, session, *, reason="disconnect"):
        """Resolve a disconnected duel owner as the loser without a turn/action."""
        if reason not in ("disconnect", "defeat"):
            raise ValueError("Invalid friendly duel forfeit reason")
        self._live(session)
        with self.lock:
            fight_id = self.by_character.get(session.character_id)
            shared = None if fight_id is None else self.fights.get(fight_id)
        if shared is None:
            return False
        with shared.lock:
            if (
                not getattr(shared, "is_duel", False)
                or shared.participants.get(session.account_id) != session
                or shared.fight.phase not in ("placement", "active")
                or shared.settlement_ready
            ):
                return False
            actor = shared.fight.actors.get(session.character_id)
            if (
                actor is None
                or not actor.controlled
                or actor.owner_id != session.account_id
            ):
                raise ValueError("Disconnected duel actor is not owned by its lease")
            opponents = [
                current
                for current in shared.fight.actors.values()
                if current.controlled and current.team != actor.team
            ]
            if len(opponents) != 1:
                raise ValueError("Duel disconnect does not match the two-owner roster")
            shared.fight.phase = "finished"
            shared.fight.winner = opponents[0].team
            shared.fight._event(
                "duel_forfeit", character_id=session.character_id, reason=reason
            )
            shared.duel_disconnected_character_id = (
                session.character_id if reason == "disconnect" else None
            )
            shared.duel_finish_reason = reason
            if shared.runtime is not None:
                shared.ack.cancel_for_recovery()
                shared.runtime.awaiting_ack = None
                shared.runtime.pending = []
                shared.runtime.turn_deadline = None
                shared.runtime.deadline_turn = None
            return True

    def remove_finished(self, fight_id, settle):
        """settle(shared) persists every owner + group outcome idempotently.

        If settling fails, retain registry/lease for retry. Never settle on one
        connection's finally or release groups while other players remain.
        """
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                if shared.fight.phase != "finished":
                    raise ValueError("Fight has not finished")
                if shared.settlement_ready and shared.returned != set(
                    shared.participants
                ):
                    raise ValueError("Shared owners have not all returned")
                settle(shared)
                self._remove_locked(self, shared)
                return True

    def settle_finished(self, fight_id, session, prepare_packets):
        """Persist one roster outcome, then queue a private result per owner.

        ``prepare_packets(shared)`` must commit the complete durable roster
        settlement before returning a mapping of account IDs to native packet
        sequences. Queuing is all-or-nothing in memory after that commit. The
        registry remains authoritative until every participant returns through
        the native continuation callback.
        """
        if not callable(prepare_packets):
            raise ValueError("Shared settlement requires a packet builder")
        self._live(session)
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                raise ValueError("Unknown shared fight")
            # Acquire the per-fight lock while the registry membership is
            # pinned, then drop the global lock before any SQL/encoding work.
            shared.lock.acquire()
        try:
            with shared.lock:
                # A friendly-duel forfeit is settled from the disconnect
                # barrier after the owner has been removed from `connected`.
                # The SQL lease remains current until the barrier finishes, so
                # that exact durable duel participant may finalize the roster
                # outcome without gaining socket/action authority. PvE retains
                # the ordinary connected-member requirement.
                if not (
                    getattr(shared, "is_duel", False)
                    and shared.participants.get(session.account_id) == session
                ):
                    self._member(shared, session)
                if shared.fight.phase != "finished":
                    raise ValueError("Fight has not finished")
                if shared.settlement_ready:
                    return False
                batches = prepare_packets(shared)
                if not isinstance(batches, dict) or set(batches) != set(
                    shared.participants
                ):
                    raise ValueError("Shared settlement did not cover its roster")
                checked = {
                    account: self._packets(packets)
                    for account, packets in batches.items()
                }
                # Only enqueue after the callback has completed its durable
                # transaction and every owner payload has passed validation.
                for account in sorted(shared.participants):
                    shared.sequence += 1
                    shared.settlement_batches[account] = checked[account]
                    shared.outboxes[account].append(
                        Batch(shared.sequence, checked[account])
                    )
                shared.settlement_ready = True
                return True
        finally:
            shared.lock.release()

    def mark_returned(self, fight_id, session):
        """Retire the shared registry only after each owner returns from UI."""
        self._live(session)
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                self._member(shared, session)
                if not shared.settlement_ready:
                    raise ValueError("Fight settlement has not been published")
                shared.returned.add(session.account_id)
                if shared.returned != set(shared.participants):
                    return False
                self._remove_locked(self, shared)
                return True
