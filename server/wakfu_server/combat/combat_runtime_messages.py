"""Native turn messages and explicit interrupted-fight cleanup.

No spell effects, AI, rewards or ordinary victory-result protobuf are invented.
"""
from .combat_effective_control import effective_server_controlled, effective_input_owner
import struct
import time
from copy import deepcopy
from .combat_wire import actor_state
from .combat_area_boundary import atomic_area_turn, adopt_fight
from .combat_native_action_ids import native_delivery_boundary
from .combat_additional_turn import timeline_round
from .combat_input_observation import observe_clock, wall_time


class RuntimeMessages:
    def __deepcopy__(self, memo):
        """Clone transaction state without cloning service callback owners.

        These providers receive the candidate fight explicitly. They are
        injected services, not owned combat state; copying bound methods also
        copies their entire service/catalog graph. All other fields, including
        future mutable runtime fields, remain isolated through the shared memo.
        """
        clone = type(self).__new__(type(self))
        memo[id(self)] = clone
        providers = {
            "stats_serializer",
            "runtime_stats_serializer",
            "turn_end_provider",
            "turn_start_provider",
            "expiration_runtime_factory",
            "clock",
        }
        for name, value in vars(self).items():
            setattr(clone, name, value if name in providers else deepcopy(value, memo))
        return clone

    def __init__(
        self,
        fight,
        turn_duration_ms=30000,
        *,
        stats_serializer=None,
        runtime_stats_serializer=None,
        turn_end_provider=None,
        turn_start_provider=None,
        expiration_runtime_factory=None,
        clock=time.monotonic
    ):
        if type(turn_duration_ms) is not int or not 0 < turn_duration_ms < 2**63:
            raise ValueError("Invalid turn duration")
        if stats_serializer is not None and not callable(stats_serializer):
            raise ValueError("Stats serializer must be callable")
        if runtime_stats_serializer is not None and not callable(
            runtime_stats_serializer
        ):
            raise ValueError("Runtime stats serializer must be callable")
        if turn_end_provider is not None and not callable(turn_end_provider):
            raise ValueError("Turn-end provider must be callable")
        if turn_start_provider is not None and not callable(turn_start_provider):
            raise ValueError("Turn-start provider must be callable")
        if expiration_runtime_factory is not None and not callable(
            expiration_runtime_factory
        ):
            raise ValueError("Expiration runtime factory must be callable")
        self.expiration_runtime_factory = expiration_runtime_factory
        self.turn_start_provider = turn_start_provider
        self.area_started_turn = None
        self.turn_end_provider = turn_end_provider
        self.stats_serializer = stats_serializer
        self.runtime_stats_serializer = runtime_stats_serializer
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
        """Prepare new native actions without renumbering an owned prefix."""
        from .combat_native_action_ids import NativeDelivery, prepare_native_delivery
        from .combat_pending_restoration import settle_pending_restoration_deaths

        prepared = isinstance(packets, NativeDelivery)
        if prepared:
            # Validate ownership/counter before any lifecycle work. A previous
            # owned prefix remains legal after this allocator has advanced.
            prepare_native_delivery(
                packets, fight_id=self.fight.id, previous_id=self.native_action_id
            )
        else:
            packets = tuple(packets)
        pending = any(
            isinstance(getattr(actor, "native_death_status", None), dict)
            and actor.native_death_status.get("pending_restoration") is not None
            for actor in self.fight.actors.values()
        )
        if pending:
            from .combat_area_boundary import adopt_runtime

            candidate = deepcopy(self)
            tail = settle_pending_restoration_deaths(candidate)
            if prepared and not tail:
                # Positive-HP marker cleanup can mutate state with no packets.
                # Adopt that cleanup while retaining the exact sealed batch.
                adopt_runtime(self, candidate)
                return packets
            fresh, last = prepare_native_delivery(
                tail if prepared else packets + tail,
                fight_id=candidate.fight.id,
                previous_id=candidate.native_action_id,
            )
            delivery = (
                NativeDelivery(
                    tuple(packets) + tuple(fresh),
                    fight_id=candidate.fight.id,
                    actions=packets.native_actions + fresh.native_actions,
                )
                if prepared
                else fresh
            )
            candidate.native_action_id = last
            candidate.last_native_delivery = delivery.native_actions
            candidate._record_prepared_revivals(fresh)
            adopt_runtime(self, candidate)
            return delivery
        if prepared:
            return packets
        # Preserve ordinary raw preparation, including restoration validation.
        packets = packets + settle_pending_restoration_deaths(self)
        delivery, last = prepare_native_delivery(
            packets, fight_id=self.fight.id, previous_id=self.native_action_id
        )
        self.native_action_id = last
        self.last_native_delivery = delivery.native_actions
        self._record_prepared_revivals(delivery)
        return delivery

    def prepare_fight_delivery(self, packets, fight, *, action_id, operation):
        """Prepare and adopt one preview without discarding lifecycle cleanup.

        The caller has validated and serialized this preview. Delivery may
        finalize pending deaths, so it must use the same fight that is adopted.
        Keep both the source and the supplied preview unchanged on rejection.
        """
        from .combat_area_boundary import adopt_fight
        from .combat_invariant_observation import observe_prepared_boundary

        if fight.id != self.fight.id:
            raise ValueError("Delivery preview belongs to another fight")
        candidate_fight = deepcopy(fight)
        candidate = deepcopy(self, {id(self.fight): candidate_fight})
        candidate.fight = candidate_fight
        candidate.action_id = action_id
        delivery = candidate.prepare_delivery(packets)
        observe_prepared_boundary(candidate.fight, candidate, operation=operation)
        # Preserve the caller's preview identity, including existing actors.
        # adopt_fight performs pointer/characteristic preflight before mutation.
        adopt_fight(fight, candidate.fight)
        candidate.fight = fight
        self.__dict__.clear()
        self.__dict__.update(candidate.__dict__)
        return delivery

    def _record_prepared_revivals(self, delivery):
        # aTS1 revives the same identity; a subsequent real death must be
        # delivered again instead of being suppressed by its previous report.
        for opcode, payload in delivery:
            if opcode == 12727 and len(payload) == 21 and payload[-1] == 1:
                identity = struct.unpack_from(">q", payload, 12)[0]
                self._reported_deaths = getattr(self, "_reported_deaths", set()) - {
                    identity
                }

    def _arm_turn(self):
        from .combat_turn_duration import current_turn_duration

        self.deadline_turn = self.fight.turn_id
        self.turn_deadline = (
            observe_clock("runtime.arm_turn.monotonic", self.clock())
            + current_turn_duration(self.fight, self.duration) / 1000
        )

    def expiration_due(self):
        """Read the same owned turn/deadline gate without copying or mutation."""
        actor = self.fight.current
        return not (
            self.fight.phase != "active"
            or actor is None
            or effective_input_owner(self.fight, actor) is None
            or actor.hp <= 0
            or self.awaiting_ack is not None
            or self.turn_deadline is None
            or self.deadline_turn != self.fight.turn_id
            or observe_clock("runtime.expire_turn.monotonic", self.clock())
            < self.turn_deadline
        )

    def expire_current_once(self):
        """Expire a delivered controlled turn without synthesizing its ACK."""
        if not self.expiration_due():
            return []
        actor = self.fight.current
        from .combat_timeline_snapshot import current_wire_turn

        return self.end_turn(
            effective_input_owner(self.fight, actor),
            actor.id,
            current_wire_turn(self.fight),
        )

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

    def _changed_stat_packets(self, before, *, state=None, exclude=()):
        from .combat_characteristic_reconciliation import changed_characteristic_packets

        serialize = self.runtime_stats_serializer
        if serialize is None and self.stats_serializer is not None:
            serialize = lambda actor, fight: self.stats_serializer(actor)
        return changed_characteristic_packets(
            self.fight if state is None else state,
            before,
            serialize,
            exclude=exclude,
        )

    def _expire_owned(self, *, actor_id, round_number, phase, round_cleanup=False):
        from .combat_state_managers import state_managers

        if not (
            bool(getattr(self.fight, "native_delay_queue", {}).get("entries"))
            or any(
                entry.timer is not None
                for actor in state_managers(self.fight)
                for entry in actor.state_ledger.entries
            )
            or any(
                entry.get("timer") is not None
                for entry in self.fight.owned_stat_effects.values()
            )
            or any(
                entry.get("timer") is not None
                for entry in self.fight.native_owned_group_effects.values()
            )
            or any(
                entry.get("timer") is not None
                for entry in getattr(
                    self.fight, "native_owned_area_effects", {}
                ).values()
            )
        ):
            return []
        from .combat_timed_expiration import expire_timed_effects
        from .combat_characteristic_reconciliation import characteristic_signatures

        before = characteristic_signatures(self.fight)
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
            runtime_factory=self.expiration_runtime_factory,
        )
        packets = list(packets) + self._changed_stat_packets(before)
        if packets:
            self.action_id = next_action
        return packets + ([self._flush()] if packets else [])

    def _end_owned(self, actor):
        if self.turn_end_provider is None:
            return self._expire_owned(
                actor_id=actor.id, round_number=timeline_round(self.fight), phase="end"
            )
        from .combat_timed_expiration import prepare_timed_expiration
        from .combat_characteristic_reconciliation import characteristic_signatures

        before = characteristic_signatures(self.fight)
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
                round_number=timeline_round(candidate),
                phase="end",
                action_id=next_action,
                runtime_factory=self.expiration_runtime_factory,
            )
        previous_ids = set(self.fight.actors)
        candidate_ids = set(candidate.actors)
        if previous_ids - candidate_ids:
            raise ValueError("Turn-end policy removed an actor")
        # Native end callbacks may summon a replacement. Accept only births
        # registered by the native factory and introduced in this transaction;
        # arbitrary provider roster edits must still fail before publication.
        deliveries = getattr(candidate, "native_summon_creation_deliveries", {})
        registrations = getattr(candidate, "native_summon_registrations", {})
        packets = list(events) + list(expiry)
        for identity in candidate_ids - previous_ids:
            evidence = deliveries.get(identity)
            if (
                identity not in registrations
                or not isinstance(evidence, dict)
                or type(evidence.get("opcode")) is not int
                or not isinstance(evidence.get("payload_hex"), str)
            ):
                raise ValueError("Missing native turn-end actor creation delivery")
            try:
                packet = (evidence["opcode"], bytes.fromhex(evidence["payload_hex"]))
            except ValueError as error:
                raise ValueError(
                    "Malformed native turn-end actor creation delivery"
                ) from error
            if packet not in packets:
                raise ValueError("Missing native turn-end actor creation delivery")
        from .combat_area_boundary import adopt_fight

        packets.extend(self._changed_stat_packets(before, state=candidate))
        adopt_fight(self.fight, candidate)
        self.action_id = next_action
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
        restore_initial = getattr(
            self, "native_initial_timeline_restore_pending", False
        )
        initial_recovery = restore_initial and self.fight.turn_id == 1
        # SU.bhO advances the round and enters BETWEEN_FIGHTER_TURNS.
        # Round boundaries follow complete timeline cycles, not individual actors.
        current_round = timeline_round(self.fight)
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
            from .combat_characteristic_reconciliation import characteristic_signatures

            before_callbacks = characteristic_signatures(self.fight)
            action_id = self.action_id + 1
            candidate, callbacks = self.turn_start_provider(
                self.fight, actor_id=actor.id, action_id=action_id
            )
            adopt_fight(self.fight, candidate)
            self.area_started_turn = boundary
            self.action_id = action_id
            packets.extend(callbacks)
            # The current actor receives its existing full snapshot below.
            # Reconcile other actors changed by the same callback transaction.
            callbacks_sync = self._changed_stat_packets(
                before_callbacks,
                exclude=() if self.fight.current is None else (self.fight.current.id,),
            )
            packets.extend(callbacks_sync)
            if callbacks or callbacks_sync:
                packets.append(self._flush())
            actor = self.fight.current
            if actor is None:
                self.turn_deadline = self.deadline_turn = None
                return packets
        from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

        if (
            self.stats_serializer is not None
            or self.runtime_stats_serializer is not None
        ) and actor.id not in hidden_snapshot_actor_ids(self.fight):
            stats = (
                self.runtime_stats_serializer(actor, self.fight)
                if self.runtime_stats_serializer is not None
                else self.stats_serializer(actor)
            )
            packets.append((12873, actor_state(12873, self.fight.id, actor.id, stats)))
        # A first-turn 12053 below carries the current round and replaces SU.
        # Sending 13477 beside it queues a separate asynchronous SU.bhO advance;
        # its completion can run after recovery has already set ON_FIGHTER_TURN.
        if new_round and not initial_recovery:
            packets.extend(
                [
                    (13477, self._prefix() + struct.pack(">h", current_round)),
                    self._flush(),
                ]
            )
        removed = getattr(self.fight, "native_timeline_removed", ())
        delivered_count = getattr(self, "native_timeline_removal_delivery_count", 0)
        if len(removed) > delivered_count or restore_initial:
            # Native aTS overlaps death animation: its queue resumes after
            # 250ms, while SU removal waits for the full animation callback.
            # Restore the authoritative current SU instead of incrementing a
            # client timeline that may still contain those defeated actors.
            from .combat_recovery import recovery_packet
            from .combat_phase import action_transition
            from .combat_turn_duration import current_turn_duration

            packets.extend(
                [
                    recovery_packet(
                        self.fight,
                        struct.pack(">i", self.fight.id),
                        deadline_ms=int(wall_time("runtime.turn_started.wall") * 1000)
                        + current_turn_duration(self.fight, self.duration),
                        excluded_actor_ids=(
                            getattr(
                                self,
                                "native_initial_timeline_restore_excluded_actor_ids",
                                (),
                            )
                            if initial_recovery
                            else ()
                        ),
                    ),
                    action_transition(self.fight.id),
                    self._flush(),
                ]
            )
            self.native_timeline_removal_delivery_count = len(removed)
            self.native_initial_timeline_restore_pending = False
            self.native_initial_timeline_restore_excluded_actor_ids = ()
            if not arm_deadline:
                self.native_timeline_restore_pending_turn = self.fight.turn_id
            if arm_deadline:
                from .combat_skip_turn import skip_turn_packets

                skipped = skip_turn_packets(self)
                if skipped is not None:
                    return packets + skipped
                self._arm_turn()
            return packets
        for opcode in (13337, 13482):
            from .combat_turn_duration import current_turn_duration

            packets.append(
                (
                    opcode,
                    self._prefix()
                    + struct.pack(
                        ">qq",
                        actor.id,
                        current_turn_duration(self.fight, self.duration),
                    ),
                )
            )
            packets.append(self._flush())
        if arm_deadline:
            from .combat_skip_turn import skip_turn_packets

            skipped = skip_turn_packets(self)
            if skipped is not None:
                return packets + skipped
            self._arm_turn()
        return packets

    @native_delivery_boundary
    def combat_started(self, actor_payloads, *, initialization_packets=()):
        """Own stats/effects, end placement12233, then native ACTION12514."""
        if (
            self.fight.phase != "active"
            or self.fight.turn_id != 1
            or not set(actor_payloads).issubset(self.fight.actors)
        ):
            raise ValueError("Invalid initial combat state")
        # Innates execute after baseline capture and may create actual summons.
        # Only their exact registered 307 delivery can account for added PVs;
        # arbitrary missing actor snapshots remain an invalid initial state.
        added = set(self.fight.actors) - set(actor_payloads)
        deliveries = getattr(self.fight, "native_summon_creation_deliveries", {})
        registrations = getattr(self.fight, "native_summon_registrations", {})
        for identity in added:
            evidence = deliveries.get(identity)
            if (
                not isinstance(evidence, dict)
                or type(evidence.get("opcode")) is not int
                or not isinstance(evidence.get("payload_hex"), str)
            ):
                raise ValueError("Missing native initial actor creation delivery")
            try:
                packet = (evidence["opcode"], bytes.fromhex(evidence["payload_hex"]))
            except ValueError as error:
                raise ValueError(
                    "Malformed native initial actor creation delivery"
                ) from error
            if identity not in registrations or packet not in initialization_packets:
                raise ValueError("Missing native initial actor creation delivery")
        packets = []
        for identity, (stats, effects) in actor_payloads.items():
            packets.extend(
                [
                    (13912, actor_state(13912, self.fight.id, identity, effects)),
                    # big.a(buH,stats,effects) applies effects before stats:
                    # dU/13912 resets frm before replay, including gear RANGE.
                    (12873, actor_state(12873, self.fight.id, identity, stats)),
                ]
            )
        packets.append((12233, struct.pack(">i", self.fight.id)))
        from .combat_phase import action_transition

        packets.append(action_transition(self.fight.id))
        # Joining PCs may have equal INIT but different effective levels. The
        # client recomputes placement order as actor snapshots arrive; publish
        # the owned Ready timeline before its first actor advance.
        # Recovery/ACTION restores the existing turn, never begins another one.
        baseline_players = {
            actor.id
            for actor in self.fight.actors.values()
            if actor.controlled
            and actor.id in actor_payloads
            and not getattr(actor, "native_summon_source", None)
        }
        self.native_initial_timeline_restore_pending = len(baseline_players) > 1
        self.native_initial_timeline_restore_excluded_actor_ids = (
            tuple(sorted(added)) if self.native_initial_timeline_restore_pending else ()
        )
        if self.native_initial_timeline_restore_pending:
            # 12053 must install the baseline before client-side 307 creation
            # observers enroll these newborn actors in Tc/SU. Its projection
            # excludes only the exact registered initial birth deliveries.
            turn_packets = tuple(self.turn_started())
            recovery_indices = [
                index
                for index, (opcode, _) in enumerate(turn_packets)
                if opcode == 12053
            ]
            if len(recovery_indices) != 1:
                raise ValueError("Initial timeline restore did not emit one recovery")
            recovery_index = recovery_indices[0]
            action_index = next(
                (
                    index
                    for index in range(recovery_index + 1, len(turn_packets))
                    if turn_packets[index][0] == 12514
                ),
                None,
            )
            if action_index is None:
                raise ValueError(
                    "Initial timeline restore omitted its native action barrier"
                )
            flush_index = next(
                (
                    index
                    for index in range(action_index + 1, len(turn_packets))
                    if turn_packets[index][0] == 13420
                ),
                None,
            )
            if flush_index is None:
                raise ValueError(
                    "Initial timeline restore omitted its native action barrier"
                )
            if action_index != recovery_index + 1 or flush_index != action_index + 1:
                raise ValueError(
                    "Initial timeline restore changed its native action barrier"
                )
            # Install the baseline before 307, then keep initialization and
            # turn-start callbacks/stats ahead of the original ACTION binding.
            # Any skip-turn packets remain after that binding as usual.
            packets.extend(turn_packets[recovery_index : recovery_index + 1])
            if initialization_packets:
                packets.extend(initialization_packets)
                packets.append(self._flush())
            packets.extend(turn_packets[:recovery_index])
            packets.extend(turn_packets[action_index : flush_index + 1])
            packets.extend(turn_packets[flush_index + 1 :])
        else:
            if initialization_packets:
                packets.extend(initialization_packets)
                packets.append(self._flush())
            packets.extend(self.turn_started())
        return packets

    def _synchronize_pre_end_death(self, actor_id, previous_turn):
        """End callbacks may already settle the current actor and advance once."""
        current = self.fight.current
        if (
            current is not None
            and current.id == actor_id
            and self.fight.turn_id == previous_turn
        ):
            return None
        actor = self.fight.actors.get(actor_id)
        if (
            actor is None
            or actor.hp != 0
            or self.fight._in_play(actor)
            or self.fight.turn_id != previous_turn + 1
        ):
            raise ValueError("Unsupported turn transition during end callbacks")
        return self.synchronize_defeated_turn(actor_id, previous_turn)

    @native_delivery_boundary
    @atomic_area_turn
    def end_turn(self, owner_id, actor_id, actor_turn):
        """12502 client aUM ends actor, then emits13510 global turn ACK."""
        if self.awaiting_ack is not None:
            raise ValueError("Turn synchronization pending")
        actor = self.fight._current_owned(owner_id, actor_id)
        from .combat_timeline_snapshot import current_wire_turn

        if actor_turn != current_wire_turn(self.fight):
            raise ValueError("Stale turn identifier")
        previous = self.fight.turn_id
        expiry = self._end_owned(actor)
        if self.fight.phase != "active":
            self.turn_deadline = self.deadline_turn = None
            return expiry
        synchronized = self._synchronize_pre_end_death(actor_id, previous)
        if synchronized is not None:
            return expiry + synchronized
        self.fight.end_turn(owner_id, actor_id, actor.turn_count)
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
    def synchronize_defeated_turn(self, actor_id, global_turn):
        """Close an already advanced lethal action before publishing its successor."""
        actor = self.fight.actors.get(actor_id)
        if (
            self.fight.phase != "active"
            or actor is None
            or actor.hp > 0
            or self.fight.current is None
            or self.fight.current.id == actor_id
            or self.fight.turn_id <= global_turn
            or self.awaiting_ack is not None
            or self.pending
        ):
            raise ValueError("Invalid defeated current turn synchronization")
        # The authoritative lethal action already ran death/turn lifecycle.
        # Do not end or advance that actor again. The client must finish its
        # existing actor turn before either a successor action or AI can run.
        packets = [
            (12502, self._prefix() + struct.pack(">qii", actor_id, -1, 0)),
            self._flush(),
        ]
        self.pending = self.turn_started(arm_deadline=False)
        self.turn_deadline = self.deadline_turn = None
        self.awaiting_ack = global_turn
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
            or not effective_server_controlled(self.fight, actor)
            or global_turn != self.fight.turn_id
        ):
            raise ValueError("Invalid server controlled turn")
        previous = self.fight.turn_id
        expiry = self._end_owned(actor)
        if self.fight.phase != "active":
            self.turn_deadline = self.deadline_turn = None
            return expiry
        synchronized = self._synchronize_pre_end_death(actor_id, previous)
        if synchronized is not None:
            return expiry + synchronized
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
        # Start-of-turn reactions can finish the fight behind this ACK.
        # Deliver their committed packets without restoring/arming a turn
        # that no longer has an authoritative owner.
        if self.fight.phase != "active" or self.fight.current is None:
            self.native_timeline_restore_pending_turn = None
            self.turn_deadline = self.deadline_turn = None
            return packets
        if (
            getattr(self, "native_timeline_restore_pending_turn", None)
            == self.fight.turn_id
        ):
            from .combat_recovery import recovery_packet
            from .combat_turn_duration import current_turn_duration

            restored = recovery_packet(
                self.fight,
                struct.pack(">i", self.fight.id),
                deadline_ms=int(wall_time("runtime.acknowledge_turn.wall") * 1000)
                + current_turn_duration(self.fight, self.duration),
            )
            packets = [
                restored if opcode == 12053 else (opcode, payload)
                for opcode, payload in packets
            ]
            self.native_timeline_restore_pending_turn = None
        from .combat_skip_turn import skip_turn_packets

        skipped = skip_turn_packets(self)
        if skipped is not None:
            return packets + skipped
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
        if len(body) != 4 or struct.unpack(">i", body)[0] != self.fight.id:
            raise ValueError("Recovery request belongs to another fight")
        # A delayed coX can cross placement or the terminal notification. Neither
        # phase owns an active SU/deadline. Preserve its existing presentation
        # and ACK queue instead of constructing an invalid active-turn recovery.
        if self.fight.phase in ("placement", "finished"):
            return []
        from .combat_recovery import recovery_packet

        from .combat_turn_duration import current_turn_duration

        duration = current_turn_duration(self.fight, self.duration)
        packet = recovery_packet(self.fight, body, deadline_ms=now_ms + duration)
        stats = (
            None
            if self.stats_serializer is None and self.runtime_stats_serializer is None
            else (
                self.runtime_stats_serializer(self.fight.current, self.fight)
                if self.runtime_stats_serializer is not None
                else self.stats_serializer(self.fight.current)
            )
        )
        self.awaiting_ack = None
        self.pending = []
        self.round = timeline_round(self.fight)
        self.fight.native_table_turn = self.round
        self._arm_turn()
        packets = [packet]
        if stats is not None:
            actor = self.fight.current
            packets.append((12873, actor_state(12873, self.fight.id, actor.id, stats)))
            packets.append(self._flush())
        # A restored SU already identifies the current actor. ACTION installs
        # its controller without replaying buH.bp's turn-begin lifecycle.
        from .combat_phase import action_transition

        packets.extend([action_transition(self.fight.id), self._flush()])
        self.native_timeline_removal_delivery_count = len(
            getattr(self.fight, "native_timeline_removed", ())
        )
        self.native_timeline_restore_pending_turn = None
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
