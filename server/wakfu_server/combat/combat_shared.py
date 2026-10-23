"""Shared fight dispatcher and fenced participant outboxes.

Network adapter drains each session mailbox through its serialized socket writer.
Every combat command must enter execute/ready/join; connection-local FSMs must
not remain authoritative. Runtime/codec factories never send or persist inside
these transactions: they produce owned packet batches before the FSM commits.
"""
import struct
import time
import os
from collections import deque
from contextlib import nullcontext
from copy import copy, deepcopy
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
    # Owned constructors and recovery carriers rehydrate only their recipient.
    # Genuine runtime broadcasts retain the public event stream by default.
    public_events: bool = True


@dataclass(frozen=True)
class Transition:
    """A candidate state replacement and its ordered public packet batch."""

    fight: object
    runtime: object
    packets: tuple


@dataclass(frozen=True, eq=False)
class PendingWorldRecovery:
    """In-memory provenance for a fresh world login taking over terminal PvE."""

    session: object
    fight_id: int


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
    # The native external-fight marker keeps its original team leader id for
    # the lifetime of placement. If that owner withdraws, this narrowly-scoped
    # alias lets another teammate use the still-visible marker.
    join_aliases: dict = field(default_factory=dict)
    settlement_ready: bool = False
    settlement_batches: dict = field(default_factory=dict)
    returned: set = field(default_factory=set)
    dispatch_lock: object = field(default_factory=Lock)
    checkpoint_revision: object = None
    checkpoint_terminal: bool = False
    disconnect_abort_pending: bool = False
    withdrawals: dict = field(default_factory=dict)
    pending_world_recoveries: dict = field(default_factory=dict)
    pending_publication_recoveries: dict = field(default_factory=dict)
    publication_recovery_origins: dict = field(default_factory=dict)
    reconnect_placement_paused_at: object = None

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
        # Historical marker targets are kept separately: a withdrawn actor
        # must not reserve its character ID against a later encounter.
        self.join_aliases = {}

    def _lease_live(self, session):
        if not os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
            return self.live_session(session)
        try:
            from .combat_shared_incident_capture import observe_shared_lease
        except Exception:
            return self.live_session(session)

        try:
            result = self.live_session(session)
        except BaseException as error:
            observe_shared_lease(session, error=error)
            self._observe_npc_lease(session, error=error)
            raise
        observe_shared_lease(session, result=result)
        self._observe_npc_lease(session, result=result)
        return result

    @staticmethod
    def _observe_npc_lease(session, **observation):
        try:
            from .combat_npc_publication import observe_npc_publication_lease

            observe_npc_publication_lease(session, **observation)
        except Exception:
            pass

    def _live(self, session):
        if not isinstance(session, Session) or not self._lease_live(session):
            raise ValueError("Stale combat session lease")

    def _member(self, shared, session):
        self._live(session)
        if getattr(shared, "pending_publication_recoveries", {}) or getattr(
            shared, "publication_recovery_origins", {}
        ):
            raise ValueError("Native combat recovery awaits participant publications")
        if (
            shared.participants.get(session.account_id) != session
            or session.account_id not in shared.connected
            or session.account_id in shared.withdrawals
        ):
            raise ValueError("Session does not own this fight membership")

    @staticmethod
    def _observe_delivery(method, *args, **kwargs):
        if not os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
            return None
        try:
            from . import combat_delivery_observation

            return getattr(combat_delivery_observation, method)(*args, **kwargs)
        except Exception:
            return None

    @staticmethod
    def _packets(packets):
        from .combat_delivery_boundary import native_packets

        return native_packets(packets)

    def _broadcast(self, shared, packets, *, exclude=()):
        packets = self._packets(packets)
        # Preserve only the original turn-end presentation for reconnect ACK;
        # never replay damage, state application or other gameplay deliveries.
        turn_end = tuple(packet for packet in packets if packet[0] == 12502)
        if turn_end:
            shared.reconnect_turn_end_packets = turn_end + (
                (13420, struct.pack(">i", shared.fight.id)),
            )
        shared.sequence += 1
        for account in shared.connected - set(exclude):
            shared.outboxes[account].append(Batch(shared.sequence, packets))
            if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                self._observe_delivery(
                    "record_enqueue",
                    shared.fight.id,
                    shared.participants.get(account),
                    shared.outboxes[account][-1],
                )
        return shared.sequence

    def _retire_join_aliases_locked(self, shared):
        """Drop withdrawn-leader aliases once the native marker is no longer joinable."""
        if shared.fight.phase == "placement" and not shared.auto_locked:
            return
        # This helper runs under the fight lock alone on normal FSM paths.
        # Keep the registry index immutable here; resolution checks this
        # per-fight set under registry->fight lock order, and terminal removal
        # prunes the registry index while holding both locks.
        shared.join_aliases.clear()

    def resolve_join_target(self, actor_id):
        """Resolve a native13241 target, preferring a currently registered actor.

        Native13241 carries only an actor ID, not a fight ID. A historical
        placement alias is therefore usable only when no current actor owns
        that ID and exactly one joinable alias remains.
        """
        if type(actor_id) is not int or actor_id == 0:
            raise ValueError("Invalid shared fight join target")
        with self.lock:
            current = self.by_actor.get(actor_id)
            if current is not None:
                return current
            candidates = set()
            for fight_id in self.join_aliases.get(actor_id, ()):
                shared = self.fights.get(fight_id)
                if shared is None:
                    continue
                with shared.lock:
                    if (
                        actor_id in shared.join_aliases
                        and shared.fight.phase == "placement"
                        and not shared.auto_locked
                    ):
                        candidates.add(fight_id)
            if len(candidates) == 1:
                return next(iter(candidates))
            if len(candidates) > 1:
                raise ValueError("Ambiguous historical fight join target")
            raise ValueError("Target has no registered fight")

    def _has_live_team_member_locked(self, shared, team):
        for owner in shared.connected:
            participant = shared.participants.get(owner)
            if participant is None or not self._lease_live(participant):
                continue
            if any(
                actor.controlled
                and actor.owner_id == owner
                and actor.team == team
                and actor.hp > 0
                and not getattr(actor, "pve_withdrawn", False)
                for actor in shared.fight.actors.values()
            ):
                return True
        return False

    @classmethod
    def _transition(cls, result, fight, runtime):
        if isinstance(result, Transition):
            return result.fight, result.runtime, cls._packets(result.packets)
        return fight, runtime, cls._packets(result)

    def _prepare_accepted(self, shared, candidate, runtime, packets):
        if getattr(candidate, "rift_wave_state", None) is None:
            return candidate, runtime, packets
        context = shared.join_context
        provider = (
            context.get("rift_accepted_action") if isinstance(context, dict) else None
        )
        if not callable(provider):
            raise ValueError("Rift accepted action provider is missing")
        return self._transition(
            provider(shared, candidate, runtime, packets), candidate, runtime
        )

    def _accepted_ack(self, shared, runtime):
        """Stage the presentation barrier before adopting any accepted action."""
        from .combat_delivery_boundary import accepted_ack

        return accepted_ack(shared, runtime, self._lease_live)

    def _prepare_publication(self, shared, candidate, runtime, packets, *, operation):
        """Complete native preparation before publishing any candidate state."""
        from .combat_delivery_boundary import PreparedPublication
        from .combat_invariant_observation import observe_prepared_boundary

        candidate, runtime, packets = self._prepare_accepted(
            shared, candidate, runtime, packets
        )
        packets = self._synchronize_defeated_current(
            shared, candidate, runtime, packets
        )
        ack = self._accepted_ack(shared, runtime)
        observe_prepared_boundary(candidate, runtime, operation=operation, ack=ack)
        return PreparedPublication(candidate, runtime, self._packets(packets), ack)

    @staticmethod
    def _synchronize_defeated_current(shared, candidate, runtime, packets):
        if (
            shared.fight.phase != "active"
            or candidate.phase != "active"
            or not shared.fight.order
            or not candidate.order
        ):
            return packets
        previous = shared.fight.current
        current = candidate.current
        defeated = candidate.actors.get(previous.id) if previous is not None else None
        if (
            shared.fight.phase == "active"
            and candidate.phase == "active"
            and previous is not None
            and previous.hp > 0
            and defeated is not None
            and defeated.hp <= 0
            and current is not None
            and current.id != previous.id
            and candidate.turn_id > shared.fight.turn_id
            and getattr(runtime, "awaiting_ack", None) is None
        ):
            packets += tuple(
                runtime.synchronize_defeated_turn(previous.id, shared.fight.turn_id)
            )
        return packets

    def register(
        self, fight, starter, *, runtime=None, group_lease=None, join_context=None
    ):
        self._live(starter)
        owners = {a.owner_id for a in fight.actors.values() if a.controlled}
        if owners != {starter.account_id} or starter.character_id not in fight.actors:
            raise ValueError("Initial fight requires its owned starter")
        from .combat_encounter_roles import assigned_roles

        player_team = assigned_roles(fight).player_team
        with self.lock:
            if (
                fight.id in self.fights
                or any(
                    a.controlled and a.id in self.by_character
                    for a in fight.actors.values()
                )
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
            self.by_character.update(
                (actor.id, fight.id)
                for actor in fight.actors.values()
                if actor.controlled
            )
            self.by_actor.update((actor_id, fight.id) for actor_id in fight.actors)
            leaders = (
                join_context.get("leaders") if isinstance(join_context, dict) else None
            )
            marker = (
                join_context.get("world_marker_cells")
                if isinstance(join_context, dict)
                else None
            )
            leader_id = leaders.get(player_team) if isinstance(leaders, dict) else None
            leader = fight.actors.get(leader_id)
            # Only the originally advertised player leader in an ordinary
            # world marker can become an alias. Duel markers and arena/private
            # instances do not participate in this recovery path.
            if (
                not getattr(shared, "is_duel", False)
                and fight.phase == "placement"
                and starter.instance_id == 0
                and marker
                and leader_id == starter.character_id
                and leader is not None
                and leader.controlled
                and leader.owner_id == starter.account_id
                and leader.team == player_team
            ):
                shared.join_aliases[leader_id] = leader.team
                self.join_aliases.setdefault(leader_id, set()).add(fight.id)
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
        owners = {session.account_id: session for session in sessions}
        nominated = (
            None if not isinstance(join_context, dict) else join_context.get("leaders")
        )
        if nominated is None:
            nominated = {
                controlled[session.character_id].team: session.character_id
                for session in sessions
                if session.character_id in controlled
            }
        if (
            not sessions
            or len(owners) != len(sessions)
            or not isinstance(nominated, dict)
            or set(nominated) != {0, 1}
            or len(set(nominated.values())) != 2
            or not set(nominated.values()) <= set(controlled)
        ):
            raise ValueError("A duel requires both consenting team leaders")
        for team, identity in nominated.items():
            if (
                controlled[identity].team != team
                or controlled[identity].owner_id not in owners
            ):
                raise ValueError("Duel leader is outside its consenting session")
        for actor in controlled.values():
            leader = (
                controlled[nominated[actor.team]] if actor.team in nominated else None
            )
            if leader is None or actor.owner_id != leader.owner_id:
                raise ValueError("Duel actor is outside its consenting owner's team")
        if not {session.character_id for session in sessions} <= set(controlled):
            raise ValueError("Duel omitted its selected session actor")
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
            shared.duel_leaders = dict(nominated)
            shared.sequence = 1
            for session in sessions:
                shared.participants[session.account_id] = session
                shared.connected.add(session.account_id)
                shared.outboxes[session.account_id] = deque(
                    [
                        Batch(
                            shared.sequence,
                            initial_packets[session.account_id],
                            public_events=False,
                        )
                    ]
                )
                if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                    self._observe_delivery(
                        "record_bootstrap",
                        fight.id,
                        session,
                        initial_packets[session.account_id],
                        sequence=shared.sequence,
                        producer="register_duel",
                    )
                    self._observe_delivery(
                        "record_enqueue",
                        fight.id,
                        session,
                        shared.outboxes[session.account_id][-1],
                    )
                self.by_character[session.character_id] = fight.id
            for actor in controlled.values():
                self.by_character[actor.id] = fight.id
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

    def lookup(self, fight_id, *, blocking=True):
        if not self.lock.acquire(blocking=blocking):
            return None
        try:
            shared = self.fights.get(fight_id)
            if shared is None:
                raise ValueError("Unknown shared fight")
            return shared
        finally:
            self.lock.release()

    def retire_unpublished_rift(self, fight_id):
        """Forget a failed initial party setup after its durable abort.

        Caller holds registration and publication fenced until all joins and
        native setup succeed. This is not a cleanup path for an active fight.
        """
        with self.lock:
            shared = self.fights.get(fight_id)
            if shared is None:
                return False
            with shared.lock:
                if (
                    getattr(shared.fight, "rift_wave_state", None) is None
                    or shared.fight.phase != "placement"
                    or shared.runtime is not None
                    or shared.settlement_ready
                ):
                    raise ValueError("Cannot retire a published or active rift setup")
                self._remove_locked(self, shared)
                return True

    def lookup_character(self, character_id):
        """Return the registered fight for a character without exposing maps."""
        with self.lock:
            fight_id = self.by_character.get(character_id)
            if fight_id is None:
                return None
            return self.fights.get(fight_id)

    def reconcile_disconnected_pve(self, session, persist):
        """Retire an orphaned PvE lease after a fenced durable abort on login."""
        self._live(session)
        with self.lock:
            fight_id = self.by_character.get(session.character_id)
            shared = self.fights.get(fight_id)
            if shared is None:
                return None
            with shared.lock:
                previous = shared.participants.get(session.account_id)
                if (
                    previous is None
                    or previous.character_id != session.character_id
                    or previous.generation == session.generation
                    or getattr(shared, "is_duel", False)
                    or shared.settlement_ready
                    or shared.fight.phase not in ("placement", "active")
                    or any(
                        self._lease_live(owner)
                        for owner in shared.participants.values()
                    )
                ):
                    return None
                # A failed finalizer can leave stale connected bits. Actual
                # lease validity above, rather than those bits, fences recovery.
                connected = set(shared.connected)
                abort_pending = shared.disconnect_abort_pending
                shared.connected.clear()
                shared.disconnect_abort_pending = True
                try:
                    exits = persist(previous, shared)
                    if (
                        not isinstance(exits, dict)
                        or set(exits)
                        != {
                            owner.character_id for owner in shared.participants.values()
                        }
                        or any(
                            not isinstance(exit_result, dict)
                            or type(exit_result.get("applied")) is not bool
                            for exit_result in exits.values()
                        )
                    ):
                        raise ValueError("Missing complete durable PvE abort receipts")
                except Exception:
                    shared.connected.update(connected)
                    shared.disconnect_abort_pending = abort_pending
                    raise
                self._remove_locked(self, shared)
                return dict(shared=shared, exits=exits)

    def join(
        self,
        session,
        body,
        actor,
        *,
        actor_payload,
        bootstrap_packets,
        persist_member=None,
        prepare_members=None,
        member_packets=None,
        expected_fight_id=None,
    ):
        """bootstrap_packets(candidateFSM,shared,session)->own native packets.

        Joined actor appears in the world before this call. Factory must build
        the joiner's full owned placement bootstrap. Existing owners get13091.
        """
        request = decode_join(body)
        self._live(session)
        with self.lock:
            fight_id = self.resolve_join_target(request["target_id"])
            if expected_fight_id is not None and fight_id != expected_fight_id:
                raise ValueError("Join target changed during admission")
            shared = self.fights[fight_id]
            with shared.lock:
                fight = shared.fight
                target = fight.actors.get(request["target_id"])
                if getattr(shared, "is_duel", False):
                    raise ValueError(
                        "Friendly duel roster cannot admit another fighter"
                    )
                if (
                    fight.phase != "placement"
                    or shared.auto_locked
                    or getattr(shared, "pending_publication_recoveries", {})
                    or getattr(shared, "publication_recovery_origins", {})
                ):
                    raise ValueError("Fight is no longer joinable")
                if (session.map_id, session.instance_id) != (
                    shared.map_id,
                    shared.instance_id,
                ):
                    raise ValueError("Foreign fight map/instance")
                from .combat_encounter_roles import assigned_roles

                alias_team = shared.join_aliases.get(request["target_id"])
                alias_target = (
                    alias_team is not None
                    and target is not None
                    and getattr(target, "pve_withdrawn", False)
                    and target.controlled
                    and target.team == alias_team
                    and alias_team == assigned_roles(fight).player_team
                    and self._has_live_team_member_locked(shared, alias_team)
                )
                if (
                    target is None
                    or not target.controlled
                    or (target.hp <= 0 and not alias_target)
                ):
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
                    or actor.team != (alias_team if alias_target else target.team)
                    or actor.hp <= 0
                ):
                    raise ValueError("Joined actor ownership/team invalid")
                occupied = {a.position for a in fight.actors.values() if a.hp > 0}
                cells = sorted(fight.placement[target.team] - occupied)
                if not cells:
                    raise ValueError("Native team placement capacity exhausted")
                candidate, runtime = deepcopy((fight, shared.runtime))
                new_actor = deepcopy(actor)
                from .combat_join_registration import register_joined_fighter

                register_joined_fighter(candidate, new_actor, cells[0])
                candidate._check_positions()
                candidate._event(
                    "joined",
                    actor_id=new_actor.id,
                    owner_id=session.account_id,
                    team=new_actor.team,
                    position=new_actor.position,
                )
                if prepare_members is not None:
                    candidate = prepare_members(candidate, new_actor, shared, session)
                    if candidate is fight or candidate.id != fight.id:
                        raise ValueError(
                            "Joined roster preparation requires detached same fight"
                        )
                    new_actor = candidate.actors[actor.id]
                    if runtime is not None and hasattr(runtime, "fight"):
                        runtime.fight = candidate
                newcomers = [
                    member
                    for identity, member in candidate.actors.items()
                    if identity not in fight.actors
                ]
                if any(
                    not member.controlled
                    or member.owner_id != session.account_id
                    or member.team != new_actor.team
                    or member.hp <= 0
                    or member.id in self.by_character
                    or member.id in self.by_actor
                    for member in newcomers
                ):
                    raise ValueError(
                        "Joined roster contains foreign or reserved actors"
                    )
                candidate._check_positions()
                notifications = (
                    list(self._packets(member_packets(candidate, shared, session)))
                    if member_packets is not None
                    else []
                )
                for member in newcomers:
                    stats, effects = actor_payload(candidate, member, session)
                    notifications.append(
                        added(
                            candidate.id,
                            member.id,
                            actor_type=0,
                            team=member.team,
                            stats=stats,
                            effects=effects,
                        )
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
                for member in newcomers:
                    self.by_character[member.id] = candidate.id
                    self.by_actor[member.id] = candidate.id
                shared.auto_locked = request["auto_lock"]
                self._retire_join_aliases_locked(shared)
                sequence = self._broadcast(
                    shared,
                    [*notifications, (13652, placement_positions(candidate))],
                    exclude=(session.account_id,),
                )
                shared.outboxes[session.account_id].append(
                    Batch(sequence, own_packets, public_events=False)
                )
                if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                    self._observe_delivery(
                        "record_bootstrap",
                        candidate.id,
                        session,
                        own_packets,
                        sequence=sequence,
                        producer="join",
                    )
                    self._observe_delivery(
                        "record_enqueue",
                        candidate.id,
                        session,
                        shared.outboxes[session.account_id][-1],
                    )
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
        incident_request=None,
    ):
        """operation(candidateFSM,runtime)->packets; mutation commits once.

        Serialized socket requests get server sequence checks; no callbacks may
        bypass this dispatcher for casts/move/ready/end-turn/ack. Runtime objects
        are immutable inputs here; action callbacks cannot mutate runtime caches.
        """
        shared = self.lookup(fight_id)
        with shared.lock:
            incident_context = nullcontext()
            if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                try:
                    from .combat_shared_incident_capture import shared_incident_scope

                    incident_context = shared_incident_scope(
                        shared,
                        self,
                        dict(
                            type="execute",
                            session=session,
                            actor_id=actor_id,
                            expected_sequence=expected_sequence,
                            require_turn=require_turn,
                            wire_request=incident_request,
                        ),
                    )
                except Exception:
                    pass
            with incident_context as incident:
                self._member(shared, session)
                if (
                    expected_sequence is not None
                    and expected_sequence != shared.sequence
                ):
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
                if incident is not None:
                    incident.packets(packets)
                prepared = self._prepare_publication(
                    shared, candidate, runtime, packets, operation="Registry.execute"
                )
                shared.fight = prepared.fight
                shared.runtime = prepared.runtime
                shared.ack = prepared.ack
                packets = prepared.packets
                self._retire_join_aliases_locked(shared)
                sequence = self._broadcast(shared, packets)
                if incident is not None:
                    incident.result(sequence)
                return sequence

    def execute_server(
        self,
        fight_id,
        actor_id,
        operation,
        *,
        expected_sequence,
        incident_runtime=None,
        incident_packets=(),
        incident_session=None,
        incident_recipe="chosen-native-commit",
        incident_turn_id=None,
    ):
        """Internal AI only; no route accepts this method from a player packet."""
        shared = self.lookup(fight_id)
        with shared.lock:
            incident_context = nullcontext()
            if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                try:
                    from .combat_npc_publication import npc_publication_scope

                    incident_context = npc_publication_scope(
                        shared,
                        self,
                        actor_id,
                        expected_sequence,
                        prepared_runtime=incident_runtime,
                        prepared_packets=incident_packets,
                        initiating_session=incident_session,
                        recipe=incident_recipe,
                        turn_id=incident_turn_id,
                    )
                except Exception:
                    pass
            with incident_context as incident:
                if expected_sequence != shared.sequence:
                    raise ValueError("Stale server combat sequence")
                actor = shared.fight.current
                if actor is None or actor.id != actor_id or actor.controlled:
                    raise ValueError("Not current server-controlled turn")
                candidate, runtime = deepcopy((shared.fight, shared.runtime))
                candidate, runtime, packets = self._transition(
                    operation(candidate, runtime), candidate, runtime
                )
                if incident is not None:
                    incident.transition(candidate, runtime, packets)
                prepared = self._prepare_publication(
                    shared,
                    candidate,
                    runtime,
                    packets,
                    operation="Registry.execute_server",
                )
                shared.fight = prepared.fight
                shared.runtime = prepared.runtime
                shared.ack = prepared.ack
                packets = prepared.packets
                self._retire_join_aliases_locked(shared)
                sequence = self._broadcast(shared, packets)
                if incident is not None:
                    incident.result(sequence)
                return sequence

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
            if shared.ack.turn == turn:
                # Legacy socket adapters may announce the accepted barrier.
                # They must not reset a participant's already received ACK.
                return
            sessions = [
                s
                for a, s in shared.participants.items()
                if a in shared.connected and self._lease_live(s)
            ]
            shared.ack.arm(turn, sessions)

    def acknowledge(self, fight_id, session, body, release_packets):
        """All recipients ACK; no current-actor ownership check applies here.

        release_packets(candidateFSM,runtime,body) consumes native pending
        acknowledge_turn once after all clients have processed12502.
        """
        shared = self.lookup(fight_id)
        with shared.lock:
            incident_context = nullcontext()
            if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                try:
                    from .combat_shared_incident_capture import shared_incident_scope

                    incident_context = shared_incident_scope(
                        shared,
                        self,
                        dict(type="shared_ack", session=session, body=body),
                    )
                except Exception:
                    pass
            with incident_context as incident:
                self._member(shared, session)
                prior_rift_ack = (
                    deepcopy(shared.ack)
                    if getattr(shared.fight, "rift_wave_state", None) is not None
                    else None
                )
                if not shared.ack.accept(session, body):
                    if incident is not None:
                        incident.result(False)
                    return False
                candidate, runtime = deepcopy((shared.fight, shared.runtime))
                try:
                    candidate, runtime, packets = self._transition(
                        release_packets(candidate, runtime, body), candidate, runtime
                    )
                    if incident is not None:
                        incident.packets(packets)
                    candidate, runtime, packets = self._prepare_accepted(
                        shared, candidate, runtime, packets
                    )
                except Exception:
                    if prior_rift_ack is not None:
                        shared.ack = prior_rift_ack
                    raise
                shared.fight = candidate
                shared.runtime = runtime
                shared.ack.release()
                self._retire_join_aliases_locked(shared)
                self._broadcast(shared, packets)
                if incident is not None:
                    incident.result(True)
                return True

    def recover_timeline(self, fight_id, session, body, *, now_ms):
        """Publish one explicit native coX recovery consistently to all owners.

        A private socket must not clear shared presentation or advance shared
        native action IDs without giving every peer the replacement timeline.
        This supersedes ACK presentation explicitly; it never fabricates13510.
        """
        shared = self.lookup(fight_id)
        with shared.lock:
            self._member(shared, session)
            candidate, runtime = deepcopy((shared.fight, shared.runtime))
            packets = runtime.recover(
                session.account_id,
                body,
                now_ms=now_ms,
                preserve_armed_deadline=True,
            )
            if not packets:
                return False
            view = copy(shared)
            view.ack = deepcopy(shared.ack)
            view.ack.cancel_for_recovery()
            prepared = self._prepare_publication(
                view,
                candidate,
                runtime,
                packets,
                operation="Registry.recover_timeline",
            )
            shared.fight = prepared.fight
            shared.runtime = prepared.runtime
            shared.ack = prepared.ack
            self._retire_join_aliases_locked(shared)
            self._broadcast(shared, prepared.packets)
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
            if shared.runtime is None or shared.runtime.fight is not shared.fight:
                raise ValueError("Shared fight runtime is missing or stale")
            if not shared.runtime.expiration_due():
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
            candidate, runtime, packets = self._prepare_accepted(
                shared, candidate, runtime, packets
            )
            from .combat_delivery_boundary import accepted_ack

            next_ack = accepted_ack(shared, runtime, self._lease_live)
            shared.fight = candidate
            shared.runtime = runtime
            shared.ack = next_ack
            self._retire_join_aliases_locked(shared)
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
            if session.account_id in shared.pending_world_recoveries:
                return []
            queue = shared.outboxes[session.account_id]
            batches = list(queue)
            queue.clear()
            if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                self._observe_delivery("record_drain", fight_id, session, batches)
            return batches

    def dispatch_connected(self, fight_id, deliver, *, blocking=True):
        """Drain and deliver every connected owner's batches in sequence order.

        The per-fight dispatch lock serializes socket batches, while the fight
        and Registry locks are released before ``deliver`` performs I/O.
        Nonblocking idle polls return None when busy and leave queues intact.
        """
        shared = self.lookup(fight_id, blocking=blocking)
        if shared is None or not shared.dispatch_lock.acquire(blocking=blocking):
            return None
        try:
            dispatch_observation = None
            if not shared.lock.acquire(blocking=blocking):
                return None
            try:
                recipients = []
                for account in sorted(shared.connected):
                    if account in shared.pending_world_recoveries:
                        continue
                    session = shared.participants.get(account)
                    queue = shared.outboxes.get(account)
                    if session is None or queue is None or not queue:
                        continue
                    batches = tuple(queue)
                    queue.clear()
                    recipients.append((session, batches))
                if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                    dispatch_observation = self._observe_delivery(
                        "begin_dispatch", fight_id, recipients
                    )
            finally:
                shared.lock.release()
            failure = None
            for session, batches in recipients:
                try:
                    deliver(session, batches)
                except Exception as error:
                    if dispatch_observation is not None:
                        self._observe_delivery(
                            "record_dispatch_attempt",
                            dispatch_observation,
                            session,
                            batches,
                            error=error,
                        )
                    # One broken peer must not prevent the other connected
                    # owners from receiving their already-drained batches.
                    if failure is None:
                        failure = error
                else:
                    if dispatch_observation is not None:
                        self._observe_delivery(
                            "record_dispatch_attempt",
                            dispatch_observation,
                            session,
                            batches,
                        )
            if dispatch_observation is not None:
                self._observe_delivery("finish_dispatch", dispatch_observation)
            if failure is not None:
                raise failure
            return tuple(session for session, _ in recipients)
        finally:
            shared.dispatch_lock.release()

    def publish(self, fight_id, session, packets):
        """Append one public ordered batch for every connected participant."""
        shared = self.lookup(fight_id)
        with shared.lock:
            self._member(shared, session)
            return self._broadcast(shared, packets)

    def takeover(
        self,
        fight_id,
        session,
        bootstrap_packets,
        *,
        persist_takeover=None,
        recover_disconnected=False,
        fresh_world=False,
        prepare_authority=None,
    ):
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
            if recover_disconnected and not callable(persist_takeover):
                raise ValueError("Disconnected takeover requires a durable lease fence")
            if prepare_authority is not None and not callable(persist_takeover):
                raise ValueError(
                    "Native authority takeover requires a durable lease fence"
                )
            if shared.disconnect_abort_pending and not recover_disconnected:
                raise ValueError(
                    "Combat is being closed after its last owner disconnected"
                )
            staged_entry = getattr(shared, "pending_publication_recoveries", {}).get(
                session.account_id
            )
            resume_staged = (
                staged_entry is not None
                and staged_entry.session == session
                and previous == session
                and session.account_id not in shared.connected
            )
            if previous.generation == session.generation and not resume_staged:
                raise ValueError("Session already current")
            if self._lease_live(previous) and not resume_staged:
                raise ValueError("Previous combat owner lease still live")
            if fresh_world and (
                shared.fight.phase != "finished"
                or shared.settlement_ready
                or getattr(shared, "is_duel", False)
                or getattr(shared.runtime, "abandon_owner", None) is not None
            ):
                raise ValueError("Fresh world recovery requires unsettled terminal PvE")
            from .combat_delivery_boundary import prepare_reconnect

            from .combat_instance_publication_recovery import (
                OwnerPublicationsPending,
                PendingPublicationRecovery,
            )

            def stage_owner(entry):
                origins = dict(getattr(shared, "publication_recovery_origins", {}))
                origins.setdefault(session.account_id, entry.original_session)
                staged_owners = dict(
                    getattr(shared, "pending_publication_recoveries", {})
                )
                staged_owners[session.account_id] = entry
                shared.publication_recovery_origins = origins
                shared.pending_publication_recoveries = staged_owners
                shared.participants[session.account_id] = session
                shared.outboxes[session.account_id] = deque()
                return shared

            original_fight = shared.fight
            try:
                prepared = prepare_reconnect(
                    shared,
                    session,
                    bootstrap_packets,
                    recover_disconnected=recover_disconnected,
                    now_ms=int(time.time() * 1000),
                    prepare_authority=prepare_authority,
                )
            except OwnerPublicationsPending as pending:
                if os.environ.get("WAKFU_NATIVE_PARTY_STAGED_RECOVERY", "0") != "1":
                    raise
                if shared.connected or not shared.disconnect_abort_pending:
                    raise ValueError(
                        "Partial native publication recovery cannot resume a live party"
                    )
                if pending.entry.session != session or not callable(persist_takeover):
                    raise ValueError(
                        "Staged recovery requires its durable authorized owner"
                    )
                origins = dict(getattr(shared, "publication_recovery_origins", {}))
                if pending.entry.original_session != origins.get(
                    session.account_id, previous
                ):
                    raise ValueError(
                        "Staged recovery changed the original owner identity"
                    )
                if not resume_staged:
                    persist_takeover(previous)
                return stage_owner(pending.entry)
            packets = prepared.packets
            if fresh_world and packets:
                raise ValueError("Fresh world recovery cannot bootstrap native combat")
            recover_pending_turn = prepared.recovered_pending_turn
            candidate, candidate_runtime, candidate_ack = (
                prepared.fight,
                prepared.runtime,
                prepared.ack,
            )
            staged = dict(getattr(shared, "pending_publication_recoveries", {}))
            staged_packets = {}
            if staged:
                view = copy(shared)
                view.fight, view.runtime, view.ack = (
                    candidate,
                    candidate_runtime,
                    candidate_ack,
                )
                for account, entry in staged.items():
                    if account == session.account_id:
                        continue
                    self._live(entry.session)
                    if shared.participants.get(account) != entry.session:
                        raise ValueError(
                            "Staged recovery participant changed before final adoption"
                        )
                    staged_packets[account] = self._packets(
                        bootstrap_packets(candidate, view, entry.session)
                    )
                from .combat_instance_publication import require_current_publication

                require_current_publication(candidate)
            if (
                shared.ack is not None
                and session.account_id in shared.ack.expected
                and shared.ack.expected[session.account_id]
                != (
                    getattr(shared, "publication_recovery_origins", {})
                    .get(session.account_id, previous)
                    .generation
                )
            ):
                raise ValueError("Combat ACK owner differs from takeover lease")
            if persist_takeover is not None and not resume_staged:
                persist_takeover(previous)
            if staged:
                # SQL may release the GIL while a real source/socket is lost.
                # Membership is already durable; retain it privately and retry
                # with real publications instead of adopting the stale preview.
                source_live = (
                    candidate.native_instance_publication_lease.current
                    == candidate.native_instance_publication_receipt
                )
                owners_live = self._lease_live(session) and all(
                    self._lease_live(entry.session)
                    and shared.participants.get(account) == entry.session
                    for account, entry in staged.items()
                    if account != session.account_id
                )
                if (
                    not source_live
                    or not owners_live
                    or shared.fight is not original_fight
                ):
                    bindings = (
                        candidate.native_instance_publication_lease.owner_bindings
                    )
                    publication = next(
                        (source, scope)
                        for source, scope in bindings
                        if scope[0] == session.account_id
                    )
                    origin = getattr(shared, "publication_recovery_origins", {}).get(
                        session.account_id, previous
                    )
                    return stage_owner(
                        PendingPublicationRecovery(origin, session, publication)
                    )
            if prepared.fight is not None:
                shared.fight, shared.runtime, shared.ack = (
                    candidate,
                    candidate_runtime,
                    candidate_ack,
                )
            if recover_pending_turn:
                shared.reconnect_turn_end_packets = None
                shared.reconnect_remaining_turn_seconds = None
            shared.participants[session.account_id] = session
            if fresh_world:
                shared.pending_world_recoveries[
                    session.account_id
                ] = PendingWorldRecovery(session, fight_id)
            if recover_disconnected:
                paused_at = getattr(shared, "reconnect_placement_paused_at", None)
                if paused_at is not None:
                    if (
                        shared.fight.phase == "placement"
                        and shared.join_context is not None
                        and "fight_started_at" in shared.join_context
                    ):
                        shared.join_context = dict(shared.join_context)
                        shared.join_context["fight_started_at"] += max(
                            0.0, time.monotonic() - paused_at
                        )
                    shared.reconnect_placement_paused_at = None
                remaining = getattr(shared, "reconnect_remaining_turn_seconds", None)
                if remaining is not None:
                    shared.runtime.turn_deadline = shared.runtime.clock() + remaining
                    shared.reconnect_remaining_turn_seconds = None
                shared.disconnect_abort_pending = False
            if shared.ack is not None and session.account_id in shared.ack.expected:
                shared.ack.expected[session.account_id] = session.generation
            shared.connected.add(session.account_id)
            shared.outboxes[session.account_id] = deque(
                [Batch(shared.sequence, packets, public_events=False)]
            )
            for account, owner_packets in staged_packets.items():
                shared.connected.add(account)
                shared.outboxes[account] = deque(
                    [Batch(shared.sequence, owner_packets, public_events=False)]
                )
            if staged:
                shared.pending_publication_recoveries = {}
                shared.publication_recovery_origins = {}
            if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                self._observe_delivery(
                    "record_bootstrap",
                    fight_id,
                    session,
                    packets,
                    sequence=shared.sequence,
                    producer="takeover",
                    previous_generation=previous.generation,
                )
                self._observe_delivery(
                    "record_enqueue",
                    fight_id,
                    session,
                    shared.outboxes[session.account_id][-1],
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
                    staged = dict(getattr(shared, "pending_publication_recoveries", {}))
                    if (
                        session.account_id in staged
                        and staged[session.account_id].session == session
                    ):
                        del staged[session.account_id]
                        shared.pending_publication_recoveries = staged
                    shared.connected.discard(session.account_id)
                    shared.outboxes[session.account_id].clear()
                    if shared.connected and shared.ack.turn is not None:
                        # The departed transport cannot finish presentation.
                        # Retain every remaining recipient's real ACK; never
                        # synthesize one or clear a last-owner reconnect pause.
                        barrier = deepcopy(shared.ack)
                        if (
                            barrier.expected.get(session.account_id)
                            == session.generation
                        ):
                            barrier.expected.pop(session.account_id)
                            barrier.received.discard(session.account_id)
                            # Transport departure is already committed. Keep
                            # its membership fence even if private turn release
                            # fails, so a remaining owner's real ACK can retry.
                            shared.ack = barrier
                            if barrier.complete:
                                import struct

                                candidate, runtime = deepcopy(
                                    (shared.fight, shared.runtime)
                                )
                                counter = barrier.turn
                                packets = self._packets(
                                    runtime.acknowledge_turn(struct.pack(">i", counter))
                                )
                                barrier.release()
                                shared.fight, shared.runtime = candidate, runtime
                                self._retire_join_aliases_locked(shared)
                                self._broadcast(shared, packets)
                    if (
                        not shared.connected
                        and not getattr(shared, "is_duel", False)
                        and not shared.settlement_ready
                        and shared.fight.phase in ("placement", "active")
                    ):
                        # Claim last-owner cleanup before the caller releases
                        # the socket lease. A racing reconnect must not revive
                        # a fight whose abort transaction is about to commit.
                        already_paused = shared.disconnect_abort_pending
                        shared.disconnect_abort_pending = True
                        if not already_paused and shared.fight.phase == "placement":
                            shared.reconnect_placement_paused_at = time.monotonic()
                        runtime = shared.runtime
                        if (
                            not already_paused
                            and runtime is not None
                            and getattr(runtime, "turn_deadline", None) is not None
                            and runtime.awaiting_ack is None
                        ):
                            shared.reconnect_remaining_turn_seconds = max(
                                0.0, runtime.turn_deadline - runtime.clock()
                            )
                    affected.append(shared.fight.id)
        return affected

    @staticmethod
    def _remove_locked(registry, shared):
        del registry.fights[shared.fight.id]
        for actor_id in shared.fight.actors:
            if registry.by_actor.get(actor_id) == shared.fight.id:
                registry.by_actor.pop(actor_id, None)
            if registry.by_character.get(actor_id) == shared.fight.id:
                registry.by_character.pop(actor_id, None)
        for participant in shared.participants.values():
            if registry.by_character.get(participant.character_id) == shared.fight.id:
                registry.by_character.pop(participant.character_id, None)
        for actor_id in tuple(shared.join_aliases):
            fights = registry.join_aliases.get(actor_id)
            if fights is not None:
                fights.discard(shared.fight.id)
                if not fights:
                    registry.join_aliases.pop(actor_id, None)
        shared.join_aliases.clear()

    def withdraw_pve(
        self, session, *, persist, placement_ready=None, owned_teardown=None
    ):
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
            from .combat_instance_publication_withdrawal import (
                retire_withdrawn_publication,
            )

            retire_withdrawn_publication(withdrawal.fight, session.account_id)
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
            if owned_teardown is not None:
                if not callable(owned_teardown):
                    raise ValueError("Missing owned teardown callback")
                owned_teardown(withdrawal.fight)
            saved = persist(shared.fight)
            if not isinstance(saved, dict) or "character" not in saved:
                raise ValueError("Invalid durable PvE withdrawal result")
            shared.fight, shared.runtime, shared.ack = (
                withdrawal.fight,
                withdrawal.runtime,
                barrier,
            )
            self._retire_join_aliases_locked(shared)
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
                    if self.by_character.get(identity) == fight_id:
                        self.by_character.pop(identity)
                if self.by_character.get(session.character_id) == fight_id:
                    self.by_character.pop(session.character_id)
                self._retire_join_aliases_locked(shared)
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
                if previous.generation != session.generation and self._lease_live(
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
                    if self.by_character.get(identity) == fight_id:
                        self.by_character.pop(identity)
                if self.by_character.get(session.character_id) == fight_id:
                    self.by_character.pop(session.character_id)
                self._retire_join_aliases_locked(shared)
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
                from .combat_pve_withdraw import live_owner_accounts

                if (
                    getattr(shared, "is_duel", False)
                    or live_owner_accounts(shared.fight) - {session.account_id}
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
                from .combat_pve_withdraw import live_owner_accounts

                if (
                    getattr(shared, "is_duel", False)
                    or live_owner_accounts(shared.fight) - {session.account_id}
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
            if not opponents or len({other.team for other in opponents}) != 1:
                raise ValueError("Duel disconnect has no single opposing team")
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
                from .combat_delivery_boundary import settlement_batches

                checked = settlement_batches(batches, shared.participants)
                # Only enqueue after the callback has completed its durable
                # transaction and every owner payload has passed validation.
                for account in sorted(shared.participants):
                    shared.sequence += 1
                    shared.settlement_batches[account] = checked[account]
                    shared.outboxes[account].append(
                        Batch(shared.sequence, checked[account])
                    )
                shared.settlement_ready = True
                # Settlement commits the terminal checkpoint in the same
                # durable transaction. Socket callbacks must not save an
                # active checkpoint against its previous revision afterward.
                shared.checkpoint_terminal = True
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
                if (
                    shared.participants.get(session.account_id) == session
                    and session.account_id in shared.returned
                ):
                    return False
                self._member(shared, session)
                if not shared.settlement_ready:
                    raise ValueError("Fight settlement has not been published")
                shared.returned.add(session.account_id)
                shared.connected.discard(session.account_id)
                shared.outboxes[session.account_id].clear()
                self._release_owner_actor_indices_locked(shared, session)
                if shared.returned != set(shared.participants):
                    return False
                self._remove_locked(self, shared)
        return True

    def _release_owner_actor_indices_locked(self, shared, session):
        """Release this owner's combat actor IDs without touching newer fights.

        ``register`` indexes every actor, including controlled heroes/summons,
        while return/recovery used to clear only the primary character. Keep the
        registry -> shared lock order at call sites and fence every deletion by
        the old fight ID so an actor re-registered elsewhere is preserved.
        """
        fight_id = shared.fight.id
        if self.by_character.get(session.character_id) == fight_id:
            self.by_character.pop(session.character_id, None)
        for actor in shared.fight.actors.values():
            if not actor.controlled or actor.owner_id != session.account_id:
                continue
            if self.by_actor.get(actor.id) == fight_id:
                self.by_actor.pop(actor.id, None)

    def recover_settled_world(self, session, persist, *, pending_world_recovery=None):
        """Complete one settled PvE owner directly into a freshly loaded world.

        A new world login has no native fight model to consume cached terminal
        frames. Persist its idempotent health return first, then retire only
        this owner's Registry indexes while leaving other owners' results and
        membership intact.
        """
        self._live(session)
        if not callable(persist):
            raise ValueError("Settled world recovery requires durable persistence")
        with self.lock:
            fight_id = self.by_character.get(session.character_id)
            shared = self.fights.get(fight_id)
            if shared is None:
                return None
            shared.lock.acquire()
        try:
            previous = shared.participants.get(session.account_id)
            current_recovery = (
                pending_world_recovery is not None
                and shared.pending_world_recoveries.get(session.account_id)
                is pending_world_recovery
                and previous == session
                and session.account_id in shared.connected
            )
            if pending_world_recovery is not None and not current_recovery:
                raise ValueError("Stale or foreign pending world recovery")
            if (
                previous is None
                or previous.character_id != session.character_id
                or previous.generation == session.generation
                and not current_recovery
                or session.account_id in shared.returned
                or not shared.settlement_ready
                or shared.fight.phase != "finished"
                or getattr(shared, "is_duel", False)
            ):
                return None
            if not current_recovery and self._lease_live(previous):
                raise ValueError("Previous settled owner lease is still live")
            result = persist(previous, shared)
            shared.participants[session.account_id] = session
            shared.returned.add(session.account_id)
            shared.connected.discard(session.account_id)
            shared.outboxes[session.account_id].clear()
            shared.pending_world_recoveries.pop(session.account_id, None)
        finally:
            shared.lock.release()

        # Keep Registry->fight lock order. If the other owner returned during
        # persistence, it may already have retired the entire terminal fight.
        with self.lock:
            current = self.fights.get(fight_id)
            if current is shared:
                with shared.lock:
                    if shared.participants.get(session.account_id) == session:
                        self._release_owner_actor_indices_locked(shared, session)
                    if shared.returned == set(shared.participants):
                        self._remove_locked(self, shared)
        return result
