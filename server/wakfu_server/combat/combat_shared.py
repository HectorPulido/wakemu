"""Shared fight dispatcher and fenced participant outboxes.

Network adapter drains each session mailbox through its single socket writer.
Every combat command must enter execute/ready/join; connection-local FSMs must
not remain authoritative. Runtime/codec factories never send or persist inside
these transactions: they produce owned packet batches before the FSM commits.
"""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
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


@dataclass
class SharedFight:
    fight: object
    map_id: int
    instance_id: int
    runtime: object
    participants: dict = field(default_factory=dict)
    connected: set = field(default_factory=set)
    outboxes: dict = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock)
    sequence: int = 0
    auto_locked: bool = False
    ack: AckBarrier = field(default_factory=AckBarrier)


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
        ):
            raise ValueError("Session does not own this fight membership")

    @staticmethod
    def _packets(packets):
        packets = tuple(packets)
        if any(
            not isinstance(p, tuple)
            or len(p) != 2
            or type(p[0]) is not int
            or not isinstance(p[1], bytes)
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

    def register(self, fight, starter, *, runtime=None, group_lease=None):
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
            shared.participants[starter.account_id] = starter
            shared.connected.add(starter.account_id)
            shared.outboxes[starter.account_id] = deque()
            self.fights[fight.id] = shared
            self.by_character[starter.character_id] = fight.id
            self.by_actor.update((actor_id, fight.id) for actor_id in fight.actors)
            return shared

    def lookup(self, fight_id):
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                raise ValueError("Unknown shared fight")
            return shared

    def join(self, session, body, actor, *, actor_payload, bootstrap_packets):
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
                # All validators/serializers completed: atomic membership commit.
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
        require_turn=True
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
            packets = self._packets(operation(candidate, runtime))
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
            packets = self._packets(operation(candidate, runtime))
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
        """RedisGroups.lease_active accepts a generation, not a group lease tuple."""
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
            packets = self._packets(release_packets(candidate, runtime, body))
            shared.fight = candidate
            shared.runtime = runtime
            shared.ack.release()
            self._broadcast(shared, packets)
            return True

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

    def takeover(self, fight_id, session, bootstrap_packets):
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
            if previous.generation == session.generation:
                raise ValueError("Session already current")
            if self.live_session(previous):
                raise ValueError("Previous combat owner lease still live")
            packets = self._packets(bootstrap_packets(shared.fight, shared, session))
            shared.participants[session.account_id] = session
            shared.connected.add(session.account_id)
            shared.outboxes[session.account_id] = deque(
                [Batch(shared.sequence, packets)]
            )
            return shared

    def disconnect(self, session):
        """Fence old finalizers; never release starter's group behind other owners."""
        with self.lock:
            affected = []
            for shared in self.fights.values():
                with shared.lock:
                    if shared.participants.get(session.account_id) == session:
                        shared.connected.discard(session.account_id)
                        shared.outboxes[session.account_id].clear()
                        affected.append(shared.fight.id)
            return affected

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
                settle(shared)
                del self.fights[fight_id]
                for actor_id in shared.fight.actors:
                    self.by_actor.pop(actor_id, None)
                for session in shared.participants.values():
                    self.by_character.pop(session.character_id, None)
                return True
