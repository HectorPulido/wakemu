"""Native turn messages and explicit interrupted-fight cleanup.

No spell effects, AI, rewards or ordinary victory-result protobuf are invented.
"""
import struct
import time
from .combat_wire import actor_state
from .combat_area_boundary import atomic_area_turn, adopt_fight
from .combat_native_action_ids import native_delivery_boundary


class RuntimeMessages:
    def __init__(
        self,
        fight,
        turn_duration_ms=30000,
        *,
        stats_serializer=None,
        turn_end_provider=None,
        turn_start_provider=None,
        clock=time.monotonic
    ):
        if type(turn_duration_ms) is not int or not 0 < turn_duration_ms < 2**63:
            raise ValueError("Invalid turn duration")
        if stats_serializer is not None and not callable(stats_serializer):
            raise ValueError("Stats serializer must be callable")
        if turn_end_provider is not None and not callable(turn_end_provider):
            raise ValueError("Turn-end provider must be callable")
        if turn_start_provider is not None and not callable(turn_start_provider):
            raise ValueError("Turn-start provider must be callable")
        self.turn_start_provider = turn_start_provider
        self.area_started_turn = None
        self.turn_end_provider = turn_end_provider
        self.stats_serializer = stats_serializer
        self.fight = fight
        self.duration = turn_duration_ms
        self.action_id = 0
        self.native_action_id = 0
        self.last_native_delivery = ()
        self.awaiting_ack = None
        self.pending = []
        self.round = 0
        self.clock = clock
        self.turn_deadline = None
        self.deadline_turn = None

    def prepare_delivery(self, packets):
        """Assign native cvB IDs once at the owning delivery boundary.

        Logical request/action counters and turn ACK13510 remain independent.
        The returned tuple carries mapping metadata for logs/client harnesses.
        """
        from .combat_native_action_ids import prepare_native_delivery

        delivery, last = prepare_native_delivery(
            packets, fight_id=self.fight.id, previous_id=self.native_action_id
        )
        self.native_action_id = last
        self.last_native_delivery = delivery.native_actions
        return delivery

    def _arm_turn(self):
        self.deadline_turn = self.fight.turn_id
        self.turn_deadline = self.clock() + self.duration / 1000

    def expire_current_once(self):
        """Call on the session's own thread; never synthesize a missing ACK.

        Only a delivered controlled turn can expire. Its successor remains
        behind the ordinary13510 barrier, even if that ACK never arrives.
        """
        actor = self.fight.current
        if (
            self.fight.phase != "active"
            or actor is None
            or not actor.controlled
            or actor.hp <= 0
            or self.awaiting_ack is not None
            or self.turn_deadline is None
            or self.deadline_turn != self.fight.turn_id
            or self.clock() < self.turn_deadline
        ):
            return []
        return self.end_turn(actor.owner_id, actor.id, actor.turn_count)

    def expire_current_or_recover(self, owner_id, *, now_ms):
        """Keep the world socket and owned turn when an end reaction rejects.

        Recovery publishes the unchanged current timeline and rearms its clock;
        no end event, turn advance or reward is fabricated after a rejection.
        """
        try:
            return self.expire_current_once(), None
        except ValueError as error:
            packets = self.recover(
                owner_id, struct.pack(">i", self.fight.id), now_ms=now_ms
            )
            return packets, str(error)

    def _prefix(self):
        self.action_id += 1
        if self.action_id >= 2**31:
            raise ValueError("Fight action sequence exhausted")
        return struct.pack(">iii", self.fight.id, self.action_id, -1)

    def _flush(self):
        return (13420, struct.pack(">i", self.fight.id))

    def _expire_owned(self, *, actor_id, round_number, phase, round_cleanup=False):
        if not (
            any(
                entry.timer is not None
                for actor in self.fight.actors.values()
                for entry in actor.state_ledger.entries
            )
            or any(
                entry.get("timer") is not None
                for entry in self.fight.owned_stat_effects.values()
            )
        ):
            return []
        from .combat_timed_expiration import expire_timed_effects

        next_action = self.action_id + 1
        if next_action >= 2**31:
            raise ValueError("Fight action sequence exhausted")
        packets = expire_timed_effects(
            self.fight,
            actor_id=actor_id,
            round_number=round_number,
            phase=phase,
            round_cleanup=round_cleanup,
            action_id=next_action,
        )
        if packets:
            self.action_id = next_action
        return packets + ([self._flush()] if packets else [])

    def _end_owned(self, actor):
        if self.turn_end_provider is None:
            return self._expire_owned(
                actor_id=actor.id, round_number=actor.turn_count, phase="end"
            )
        from .combat_timed_expiration import prepare_timed_expiration

        next_action = self.action_id + 1
        candidate, events = self.turn_end_provider(
            self.fight, actor_id=actor.id, action_id=next_action
        )
        # Keep event reactions and expiration in one unpublished transaction.
        expiry = ()
        if candidate.phase == "active":
            candidate, expiry = prepare_timed_expiration(
                candidate,
                actor_id=actor.id,
                round_number=actor.turn_count,
                phase="end",
                action_id=next_action,
            )
        if set(candidate.actors) != set(self.fight.actors):
            raise ValueError("Turn-end policy changed actor roster")
        for identity, updated in candidate.actors.items():
            self.fight.actors[identity].__dict__.clear()
            self.fight.actors[identity].__dict__.update(updated.__dict__)
        for key, value in candidate.__dict__.items():
            if key != "actors":
                setattr(self.fight, key, value)
        self.action_id = next_action
        packets = list(events) + list(expiry)
        return packets + ([self._flush()] if packets else [])

    @native_delivery_boundary
    @atomic_area_turn
    def turn_started(self, *, arm_deadline=True):
        actor = self.fight.current
        if actor is None:
            raise ValueError("No active actor turn")
        if self.awaiting_ack is not None:
            raise ValueError("Waiting for previous turn synchronization")
        boundary = (self.fight.turn_id, actor.id)
        if self.turn_start_provider is not None and self.area_started_turn == boundary:
            return []  # Already committed: neither timers nor callbacks repeat.
        packets = []
        # SU.bhO advances the round and enters BETWEEN_FIGHTER_TURNS.
        # Round boundaries follow complete timeline cycles, not individual actors.
        current_round = actor.turn_count
        new_round = current_round > self.round
        if new_round:
            if current_round >= 2**15:
                raise ValueError("Round sequence exhausted")
            packets.extend(
                self._expire_owned(
                    actor_id=actor.id,
                    round_number=current_round,
                    phase="start",
                    round_cleanup=True,
                )
            )
            self.round = current_round
        self.fight.native_table_turn = self.round
        packets.extend(
            self._expire_owned(
                actor_id=actor.id, round_number=current_round, phase="start"
            )
        )
        actor = self.fight.current
        if actor is None:
            self.turn_deadline = self.deadline_turn = None
            return packets
        boundary = (self.fight.turn_id, actor.id)
        if self.turn_start_provider is not None and self.area_started_turn != boundary:
            action_id = self.action_id + 1
            candidate, callbacks = self.turn_start_provider(
                self.fight, actor_id=actor.id, action_id=action_id
            )
            adopt_fight(self.fight, candidate)
            self.area_started_turn = boundary
            self.action_id = action_id
            packets.extend(callbacks)
            if callbacks:
                packets.append(self._flush())
            actor = self.fight.current
            if actor is None:
                self.turn_deadline = self.deadline_turn = None
                return packets
        if self.stats_serializer is not None:
            stats = self.stats_serializer(actor)
            packets.append((12873, actor_state(12873, self.fight.id, actor.id, stats)))
        if new_round:
            packets.extend(
                [
                    (13477, self._prefix() + struct.pack(">h", current_round)),
                    self._flush(),
                ]
            )
        for opcode in (13337, 13482):
            packets.append(
                (opcode, self._prefix() + struct.pack(">qq", actor.id, self.duration))
            )
            packets.append(self._flush())
        if arm_deadline:
            self._arm_turn()
        return packets

    @native_delivery_boundary
    def combat_started(self, actor_payloads, *, initialization_packets=()):
        """Own stats/effects, end placement12233, then native ACTION12514."""
        if (
            self.fight.phase != "active"
            or self.fight.turn_id != 1
            or set(actor_payloads) != set(self.fight.actors)
        ):
            raise ValueError("Invalid initial combat state")
        packets = []
        for identity, (stats, effects) in actor_payloads.items():
            packets.extend(
                [
                    (12873, actor_state(12873, self.fight.id, identity, stats)),
                    (13912, actor_state(13912, self.fight.id, identity, effects)),
                ]
            )
        packets.append((12233, struct.pack(">i", self.fight.id)))
        from .combat_phase import action_transition

        packets.append(action_transition(self.fight.id))
        if initialization_packets:
            packets.extend(initialization_packets)
            packets.append(self._flush())
        packets.extend(self.turn_started())
        return packets

    @native_delivery_boundary
    @atomic_area_turn
    def end_turn(self, owner_id, actor_id, actor_turn):
        """12502 client aUM ends actor, then emits13510 global turn ACK."""
        if self.awaiting_ack is not None:
            raise ValueError("Turn synchronization pending")
        actor = self.fight._current_owned(owner_id, actor_id)
        if actor_turn != actor.turn_count:
            raise ValueError("Stale turn identifier")
        expiry = self._end_owned(actor)
        if self.fight.phase != "active":
            self.turn_deadline = self.deadline_turn = None
            return expiry
        previous = self.fight.turn_id
        self.fight.end_turn(owner_id, actor_id, actor_turn)
        packets = expiry + [
            (12502, self._prefix() + struct.pack(">qii", actor_id, -1, 0)),
            self._flush(),
        ]
        self.pending = self.turn_started(arm_deadline=False)
        self.turn_deadline = self.deadline_turn = None
        self.awaiting_ack = previous
        return packets

    @native_delivery_boundary
    @atomic_area_turn
    def end_server_turn(self, actor_id, global_turn):
        if self.awaiting_ack is not None:
            raise ValueError("Turn synchronization pending")
        actor = self.fight.current
        if (
            actor is None
            or actor.id != actor_id
            or actor.controlled
            or global_turn != self.fight.turn_id
        ):
            raise ValueError("Invalid server controlled turn")
        expiry = self._end_owned(actor)
        if self.fight.phase != "active":
            self.turn_deadline = self.deadline_turn = None
            return expiry
        self.fight.end_server_turn(actor_id, global_turn)
        packets = expiry + [
            (12502, self._prefix() + struct.pack(">qii", actor_id, -1, 0)),
            self._flush(),
        ]
        self.pending = self.turn_started(arm_deadline=False)
        self.turn_deadline = self.deadline_turn = None
        self.awaiting_ack = global_turn
        return packets

    @native_delivery_boundary
    def acknowledge_turn(self, body):
        if (
            len(body) != 4
            or self.awaiting_ack is None
            or struct.unpack(">i", body)[0] != self.awaiting_ack
        ):
            raise ValueError("Invalid or stale turn synchronization")
        self.awaiting_ack = None
        packets = self.pending
        self.pending = []
        self._arm_turn()
        return packets

    @native_delivery_boundary
    def recover(self, owner_id, body, *, now_ms):
        """Native full timeline recovery, with a fresh explicit active-turn deadline.

        This supersedes outstanding presentation/ACK state; the next legitimate
        TURN_END still checks the authoritative turn's exact sequence number.
        """
        if not any(
            a.controlled and a.owner_id == owner_id for a in self.fight.actors.values()
        ):
            raise ValueError("Account does not participate in this fight")
        from .combat_recovery import recovery_packet

        packet = recovery_packet(self.fight, body, deadline_ms=now_ms + self.duration)
        stats = (
            None
            if self.stats_serializer is None
            else self.stats_serializer(self.fight.current)
        )
        self.awaiting_ack = None
        self.pending = []
        self.round = self.fight.current.turn_count
        self.fight.native_table_turn = self.round
        self._arm_turn()
        packets = [packet]
        if stats is not None:
            actor = self.fight.current
            packets.append((12873, actor_state(12873, self.fight.id, actor.id, stats)))
            packets.append(self._flush())
        # SU is already ON_FIGHTER_TURN: reannounce TURN_START only. A PRE_TURN
        # would incorrectly require BETWEEN_FIGHTER_TURNS and trigger recovery.
        packets.extend(
            [
                (
                    13482,
                    self._prefix()
                    + struct.pack(">qq", self.fight.current.id, self.duration),
                ),
                self._flush(),
            ]
        )
        return packets

    @native_delivery_boundary
    def interrupted_cleanup(self, player_id):
        """12238 huN=true executes aUH cleanup directly, no false victory result.

        Follow with own player's format17 outside-fight update. Caller restores
        world state and may resend own13974 map data after these notifications.
        """
        actor = self.fight.actors.get(player_id)
        if actor is None or not actor.controlled:
            raise ValueError("Player is not a fight participant")
        self.awaiting_ack = None
        self.pending = []
        self.turn_deadline = self.deadline_turn = None
        self.fight.phase = "finished"
        self.fight.winner = None
        from .combat_world_refresh import actor_refresh

        return [
            (12238, self._prefix() + b"\x01"),
            self._flush(),
            actor_refresh(player_id, b"\x11" + struct.pack(">i", -1)),
        ]
