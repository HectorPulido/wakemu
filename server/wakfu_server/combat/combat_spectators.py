"""Lease-fenced, read-only subscriptions for live combat spectators.

The caller provides an authoritative current snapshot, including native 12044,
and only public post-snapshot packet batches. Spectators are never inserted
into combat actor/member collections and receive no action, turn, settlement,
or reward authority.
"""

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from .combat_spectator_wire import decode_spectator_bootstrap


@dataclass(frozen=True)
class ObserverSession:
    account_id: int
    character_id: int
    generation: str
    map_id: int
    instance_id: int

    def __post_init__(self):
        if (
            any(
                type(value) is not int or value <= 0
                for value in (self.account_id, self.character_id, self.map_id)
            )
            or type(self.instance_id) is not int
            or self.instance_id < 0
            or not isinstance(self.generation, str)
            or not self.generation
        ):
            raise ValueError("Invalid spectator session")


@dataclass(frozen=True)
class SpectatorDelivery:
    fight_id: int
    revision: int
    packets: tuple
    is_snapshot: bool


@dataclass(frozen=True)
class TerminalAck:
    """One lease-bound native cvF cleanup ACK expected from an observer."""

    session: ObserverSession
    fight_id: int

    def __post_init__(self):
        if (
            not isinstance(self.session, ObserverSession)
            or type(self.fight_id) is not int
            or self.fight_id <= 0
        ):
            raise ValueError("Invalid spectator terminal ACK identity")

    def validate(self, session, body):
        if session != self.session:
            raise ValueError("Spectator terminal ACK belongs to another lease")
        from .combat_results import continuation

        # A nonparticipant is absent from the native winner/loser roster and
        # therefore receives huO=true from aUH after its normal cvF cleanup.
        if continuation(self.fight_id, body) is not True:
            raise ValueError("Spectator terminal ACK must report nonparticipation")
        return True


@dataclass
class _Fight:
    fight_id: int
    map_id: int
    instance_id: int
    participants: frozenset
    visible: bool
    revision: int
    snapshot: tuple
    observers: dict = field(default_factory=dict)


@dataclass
class _Observer:
    session: ObserverSession
    cursor: int
    deliveries: deque = field(default_factory=deque)


class SpectatorRegistry:
    """In-process spectator index; packet construction and socket writes stay outside."""

    def __init__(self, live_session, *, max_pending_batches=128, live_location=None):
        if not callable(live_session):
            raise TypeError("Spectator registry requires a session lease validator")
        if live_location is not None and not callable(live_location):
            raise TypeError("Spectator registry location validator must be callable")
        if type(max_pending_batches) is not int or max_pending_batches < 1:
            raise ValueError("Invalid spectator queue bound")
        self.live_session = live_session
        self.live_location = live_location
        self.max_pending_batches = max_pending_batches
        self.lock = RLock()
        self.fights = {}
        self.by_session = {}
        # One lease-fenced deferred entry per observer. An active fight has no
        # authoritative action deadline between turn-end and the final 13510
        # acknowledgement, so entry is materialized only on the next snapshot.
        self.pending_entries = {}

    @staticmethod
    def _packets(packets):
        packets = tuple(packets)
        if any(
            not isinstance(packet, tuple)
            or len(packet) != 2
            or type(packet[0]) is not int
            or not 0 <= packet[0] <= 0xFFFF
            or not isinstance(packet[1], bytes)
            or len(packet[1]) > 0xFFFFFFFF - 6
            for packet in packets
        ):
            raise ValueError("Spectator delivery must contain native packet pairs")
        return packets

    @classmethod
    def _snapshot_packets(cls, fight_id, packets):
        packets = cls._packets(packets)
        native = [body for opcode, body in packets if opcode == 12044]
        if (
            len(native) != 1
            or decode_spectator_bootstrap(native[0])["fight_id"] != fight_id
        ):
            raise ValueError("A current matching cva/12044 snapshot is required")
        return packets

    def _live(self, session):
        if (
            not isinstance(session, ObserverSession)
            or self.live_session(session) is not True
        ):
            raise ValueError("Stale spectator session lease")

    @staticmethod
    def _identity(session):
        return (session.account_id, session.character_id, session.generation)

    def publish_fight(
        self,
        fight_id,
        *,
        map_id,
        instance_id,
        participant_sessions,
        revision,
        snapshot_packets,
        visible=False,
    ):
        """Publish/replace an authoritative snapshot; visibility defaults closed."""
        if (
            type(fight_id) is not int
            or fight_id <= 0
            or type(map_id) is not int
            or map_id <= 0
            or type(instance_id) is not int
            or instance_id < 0
            or type(revision) is not int
            or revision < 0
            or type(visible) is not bool
        ):
            raise ValueError("Invalid live spectator fight metadata")
        participants = frozenset(participant_sessions)
        if any(not isinstance(entry, ObserverSession) for entry in participants):
            raise ValueError("Invalid spectator participant identity")
        packets = self._snapshot_packets(fight_id, snapshot_packets)
        with self.lock:
            current = self.fights.get(fight_id)
            if current is not None and revision <= current.revision:
                if revision == current.revision and (
                    current.participants == participants
                    and current.visible == visible
                    and current.snapshot == packets
                ):
                    return
                raise ValueError("Spectator snapshot revision must increase")
            if current is None:
                self.fights[fight_id] = _Fight(
                    fight_id,
                    map_id,
                    instance_id,
                    participants,
                    visible,
                    revision,
                    packets,
                )
                return
            if (map_id, instance_id) != (current.map_id, current.instance_id):
                raise ValueError("Live fight location cannot change in place")
            current.participants = participants
            current.visible = visible
            current.revision = revision
            current.snapshot = packets
            participant_accounts = {entry.account_id for entry in participants}
            for identity, observer in tuple(current.observers.items()):
                if (
                    identity in participants
                    or observer.session.account_id in participant_accounts
                ):
                    self._remove_observer(current, identity)
            if not visible:
                self._remove_fight_observers(current)
                for identity, (_, pending_fight_id) in tuple(
                    self.pending_entries.items()
                ):
                    if pending_fight_id == fight_id:
                        self.pending_entries.pop(identity, None)
            else:
                self._materialize_pending(current)

    def _remove_observer(self, fight, identity):
        observer = fight.observers.pop(identity, None)
        if observer is not None:
            self.by_session.pop(identity, None)
        return observer

    def _remove_fight_observers(self, fight):
        for identity in tuple(fight.observers):
            self._remove_observer(fight, identity)

    def enter(self, session, fight_id, *, authorize=None):
        """Subscribe at the current snapshot, never replay from fight start.

        `authorize(session, fight_id)` is a server-owned access policy. It must
        return the literal True; truthy values do not grant access.
        """
        self._live(session)
        identity = self._identity(session)
        with self.lock:
            pending = self.pending_entries.get(identity)
            if pending is not None:
                if pending != (session, fight_id):
                    raise ValueError("Session has another pending spectator entry")
                self.pending_entries.pop(identity, None)
            fight = self.fights.get(fight_id)
            if fight is None or not fight.visible:
                raise ValueError("Fight is not published for spectators")
            if (session.map_id, session.instance_id) != (
                fight.map_id,
                fight.instance_id,
            ):
                raise ValueError("Spectator is outside the fight map instance")
            if identity in fight.participants or any(
                p.account_id == session.account_id for p in fight.participants
            ):
                raise ValueError("Combat participants cannot enter as spectators")
            if authorize is None or authorize(session, fight_id) is not True:
                raise ValueError("Spectator access denied")
            previous = self.by_session.get(identity)
            if previous is not None:
                if previous != fight_id:
                    raise ValueError("Session already observes another fight")
                observer = fight.observers.get(identity)
                if observer is None:
                    raise ValueError("Spectator subscription is inconsistent")
                # An explicit re-entry installs this current snapshot. Older
                # queued batches must not be applied afterward to roll the
                # client back behind the state it has just received.
                observer.deliveries.clear()
                observer.cursor = fight.revision
                return SpectatorDelivery(fight_id, fight.revision, fight.snapshot, True)
            for old_identity, old_fight_id in tuple(self.by_session.items()):
                if old_identity[:2] == identity[:2] and old_identity != identity:
                    old_fight = self.fights.get(old_fight_id)
                    if old_fight is not None:
                        self._remove_observer(old_fight, old_identity)
            observer = _Observer(session, fight.revision)
            fight.observers[identity] = observer
            self.by_session[identity] = fight_id
            return SpectatorDelivery(fight_id, fight.revision, fight.snapshot, True)

    def defer_enter(self, session, fight_id, *, authorize=None):
        """Queue entry until a fresh snapshot follows the native ACK barrier."""
        self._live(session)
        identity = self._identity(session)
        with self.lock:
            fight = self.fights.get(fight_id)
            if fight is None or not fight.visible:
                raise ValueError("Fight is not published for spectators")
            if (session.map_id, session.instance_id) != (
                fight.map_id,
                fight.instance_id,
            ):
                raise ValueError("Spectator is outside the fight map instance")
            if identity in fight.participants or any(
                participant.account_id == session.account_id
                for participant in fight.participants
            ):
                raise ValueError("Combat participants cannot enter as spectators")
            if authorize is None or authorize(session, fight_id) is not True:
                raise ValueError("Spectator access denied")
            existing = self.by_session.get(identity)
            if existing is not None:
                if existing != fight_id:
                    raise ValueError("Session already observes another fight")
                observer = fight.observers.get(identity)
                if observer is None or observer.session != session:
                    raise ValueError("Spectator subscription is inconsistent")
                return False
            previous = self.pending_entries.get(identity)
            if previous == (session, fight_id):
                return True
            if previous is not None:
                self.pending_entries.pop(identity, None)
            for old_identity, (old_session, _) in tuple(self.pending_entries.items()):
                if old_identity[:2] == identity[:2] and old_identity != identity:
                    self.pending_entries.pop(old_identity, None)
            for old_identity, old_fight_id in tuple(self.by_session.items()):
                if old_identity[:2] == identity[:2] and old_identity != identity:
                    old_fight = self.fights.get(old_fight_id)
                    if old_fight is not None:
                        self._remove_observer(old_fight, old_identity)
            if len(self.pending_entries) >= self.max_pending_batches:
                raise ValueError("Spectator entry queue is full")
            self.pending_entries[identity] = (session, fight_id)
            return True

    def _materialize_pending(self, fight):
        """Install queued leases at this exact current snapshot, never history."""
        snapshot = SpectatorDelivery(
            fight.fight_id, fight.revision, fight.snapshot, True
        )
        participant_accounts = {entry.account_id for entry in fight.participants}
        for identity, (session, fight_id) in tuple(self.pending_entries.items()):
            if fight_id != fight.fight_id:
                continue
            self.pending_entries.pop(identity, None)
            try:
                self._live(session)
            except ValueError:
                continue
            if self.live_location is not None:
                try:
                    if self.live_location(session) is not True:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
            if (
                (session.map_id, session.instance_id)
                != (fight.map_id, fight.instance_id)
                or identity in fight.participants
                or session.account_id in participant_accounts
                or not fight.visible
            ):
                continue
            observer = _Observer(
                session,
                fight.revision,
                deliveries=deque([snapshot]),
            )
            fight.observers[identity] = observer
            self.by_session[identity] = fight.fight_id

    def publish_events(self, fight_id, *, revision, event_packets):
        """Deliver public events while retaining the prior snapshot in an ACK gap."""
        event = self._packets(event_packets)
        if not event:
            return
        with self.lock:
            fight = self.fights.get(fight_id)
            if fight is None:
                return
            if type(revision) is not int or revision <= fight.revision:
                raise ValueError("Spectator revision must increase")
            fight.revision = revision
            delivery = SpectatorDelivery(fight_id, revision, event, False)
            for identity, observer in tuple(fight.observers.items()):
                if len(observer.deliveries) >= self.max_pending_batches:
                    self._remove_observer(fight, identity)
                else:
                    observer.deliveries.append(delivery)

    def publish_update(self, fight_id, *, revision, snapshot_packets, event_packets):
        """Atomically replace current state and queue only events after its cursor."""
        snapshot = self._snapshot_packets(fight_id, snapshot_packets)
        event = self._packets(event_packets)
        with self.lock:
            fight = self.fights.get(fight_id)
            if fight is None:
                raise ValueError("Unknown spectator fight")
            if type(revision) is not int or revision <= fight.revision:
                raise ValueError("Spectator revision must increase")
            fight.revision = revision
            fight.snapshot = snapshot
            if not fight.visible:
                self._remove_fight_observers(fight)
                return
            if event:
                delivery = SpectatorDelivery(fight_id, revision, event, False)
                for identity, observer in tuple(fight.observers.items()):
                    if len(observer.deliveries) >= self.max_pending_batches:
                        # A slow observer is detached; fight dispatch never waits on it.
                        self._remove_observer(fight, identity)
                        continue
                    observer.deliveries.append(delivery)
            self._materialize_pending(fight)

    def publish_terminal(self, fight_id, *, revision, event_packets):
        """Queue the final public batch and detach subscriptions from a closed fight."""
        event = self._packets(event_packets)
        if type(revision) is not int or revision <= 0:
            raise ValueError("Invalid terminal spectator revision")
        with self.lock:
            fight = self.fights.get(fight_id)
            if fight is None or revision <= fight.revision:
                raise ValueError("Terminal spectator revision must increase")
            delivery = SpectatorDelivery(fight_id, revision, event, False)
            observers = tuple(fight.observers.values())
            for observer in observers:
                if event:
                    if len(observer.deliveries) >= self.max_pending_batches:
                        self._remove_observer(fight, self._identity(observer.session))
                    else:
                        observer.deliveries.append(delivery)
            for identity, (_, pending_fight_id) in tuple(self.pending_entries.items()):
                if pending_fight_id == fight_id:
                    self.pending_entries.pop(identity, None)
            fight.visible = False
            if not fight.observers:
                self.fights.pop(fight_id, None)
            return tuple(observer.session for observer in observers)

    def poll(self, session):
        """Drain queued post-snapshot event batches for one live observer."""
        self._live(session)
        identity = self._identity(session)
        with self.lock:
            fight_id = self.by_session.get(identity)
            if fight_id is None:
                return ()
            fight = self.fights.get(fight_id)
            observer = fight.observers.get(identity) if fight is not None else None
            if observer is None or observer.session != session:
                self.by_session.pop(identity, None)
                return ()
            result = tuple(observer.deliveries)
            observer.deliveries.clear()
            if result:
                observer.cursor = result[-1].revision
            if not fight.visible:
                self._remove_observer(fight, identity)
                if not fight.observers:
                    self.fights.pop(fight_id, None)
            return result

    def leave(self, session, fight_id):
        """Remove only this exact session subscription; repeated leave is harmless."""
        self._live(session)
        identity = self._identity(session)
        with self.lock:
            pending = self.pending_entries.get(identity)
            if pending is not None:
                if pending[1] != fight_id:
                    raise ValueError(
                        "Leave fight ID does not match pending subscription"
                    )
                self.pending_entries.pop(identity, None)
                return True
            current = self.by_session.get(identity)
            if current is None:
                return False
            if current != fight_id:
                raise ValueError("Leave fight ID does not match subscription")
            fight = self.fights.get(current)
            if fight is not None:
                self._remove_observer(fight, identity)
            else:
                self.by_session.pop(identity, None)
            return True

    def disconnect(self, session):
        """Generation-specific cleanup; does not require a lease still be current."""
        if not isinstance(session, ObserverSession):
            raise ValueError("Invalid spectator disconnect identity")
        identity = self._identity(session)
        with self.lock:
            pending = self.pending_entries.pop(identity, None) is not None
            fight_id = self.by_session.get(identity)
            fight = self.fights.get(fight_id) if fight_id is not None else None
            if fight is not None:
                self._remove_observer(fight, identity)
                return True
            self.by_session.pop(identity, None)
            return pending

    def observing(self, session):
        """Return this exact generation's subscription, if one is still active."""
        if not isinstance(session, ObserverSession):
            raise ValueError("Invalid spectator session")
        with self.lock:
            identity = self._identity(session)
            current = self.by_session.get(identity)
            if current is not None:
                return current
            pending = self.pending_entries.get(identity)
            return None if pending is None else pending[1]

    def sessions(self, fight_id):
        """Return current observer leases without exposing mutable queues."""
        with self.lock:
            fight = self.fights.get(fight_id)
            if fight is None:
                return ()
            return tuple(observer.session for observer in fight.observers.values())

    def close_fight(self, fight_id):
        """Drop marker and subscriptions; caller restores observers to world."""
        with self.lock:
            for identity, (_, pending_fight_id) in tuple(self.pending_entries.items()):
                if pending_fight_id == fight_id:
                    self.pending_entries.pop(identity, None)
            fight = self.fights.pop(fight_id, None)
            if fight is None:
                return ()
            sessions = tuple(entry.session for entry in fight.observers.values())
            self._remove_fight_observers(fight)
            return sessions
