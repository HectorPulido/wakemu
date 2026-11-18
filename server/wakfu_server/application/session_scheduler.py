"""Scheduler operations for one lease-bound World session."""

import os
import time
from wakfu_server.performance_profiler import PROFILER
from .dispatch_result import DispatchResult


class SessionSchedulerMixin:
    @PROFILER.profile("session.idle")
    def idle(self):
        if self.runtime.STOPPING.is_set():
            return False
        self.resume_actor_approach()
        from . import source_quest_encounter_dispatch

        source_quest_encounter_dispatch.poll(self)
        if (
            self.state.loaded
            and self.state.character is not None
            and self.state.training_transit_active
            and (self.state.character["map_id"], self.state.character["instance_id"])
            != (1388, 0)
        ):
            from wakfu_server.achievements import rii_training_arena

            try:
                rii_training_arena.return_to_source(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    available=lambda destination: True,
                    only_completed=True,
                )
                self.state.training_transit_active = rii_training_arena.pending(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                )
            except (ValueError, DatabaseError, PoolTimeout) as error:
                self.runtime.record(
                    event="rii_training_departure_cleanup_deferred",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
        if (
            self.state.loaded
            and self.state.character is not None
            and self.state.hero_switch_pending is None
            and self.state.pending_travel_resume is None
        ):
            from wakfu_server.guild_member_lifecycle import (
                synchronize as synchronize_guild,
            )

            self.state.character.update(
                self.runtime.WORLD.guild_projection(
                    self.state.character["id"], self.state.generation
                )
            )
            try:
                guild_in_combat = (
                    self.state.fight is not None
                    or self.state.combat_session is not None
                    or self.state.spectator_session is not None
                    or self.state.pending_combat_return is not None
                )
                guild_publication_pending = self.state.character.get(
                    "_guild_member_publication_pending", False
                )
                updated, guild_changed = synchronize_guild(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    in_combat=guild_in_combat,
                )
                self.state.character = (
                    self.refresh_owned_character(updated) if guild_changed else updated
                )
                if (guild_changed or guild_publication_pending) and not guild_in_combat:
                    self.state.character["_guild_member_publication_pending"] = True
                    self.publish_consumable_character(self.state.character)
                    self.state.character.pop("_guild_member_publication_pending", None)
            except (ValueError, DatabaseError, PoolTimeout) as error:
                self.runtime.record(
                    event="guild_member_refresh_retry",
                    actor_id=self.state.character["id"],
                    reason=type(error).__name__,
                )
            from wakfu_server.guild_daily_quests import synchronize_owned

            try:
                boundary, packets = synchronize_owned(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    next_boundary_ms=(
                        self.state.guild_daily_boundary[1]
                        if self.state.guild_daily_boundary[0]
                        == self.state.character["id"]
                        else None
                    ),
                )
                for packet in packets:
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
                self.state.guild_daily_boundary = (self.state.character["id"], boundary)
            except (ValueError, DatabaseError, PoolTimeout) as error:
                self.runtime.record(
                    event="guild_daily_refresh_retry",
                    actor_id=self.state.character["id"],
                    reason=type(error).__name__,
                )
            from wakfu_server.objectives.environmental_recurring_storage import (
                synchronize_owned as synchronize_recurring_hunters,
            )

            try:
                boundary, packets = synchronize_recurring_hunters(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    next_boundary_ms=(
                        self.state.recurring_hunter_boundary[1]
                        if self.state.recurring_hunter_boundary[0]
                        == self.state.character["id"]
                        else None
                    ),
                    include_company=True,
                )
                for packet in packets:
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
                self.state.recurring_hunter_boundary = (
                    self.state.character["id"],
                    boundary,
                )
                self.state.recurring_hunter_refresh_pending |= bool(packets)
                if self.state.recurring_hunter_refresh_pending:
                    # Subsequent map bootstraps reuse this cached character.
                    # Preserve private-scene location while refreshing its
                    # authoritative achievement section after resets.
                    self.state.character = self.refresh_owned_character(
                        self.runtime.STORE.character(
                            self.state.account_id, self.state.character["id"]
                        )
                    )
                    self.state.recurring_hunter_refresh_pending = False
            except (ValueError, DatabaseError, PoolTimeout) as error:
                self.runtime.record(
                    event="recurring_hunter_refresh_retry",
                    actor_id=self.state.character["id"],
                    reason=type(error).__name__,
                )
        mailbox = getattr(self.state.connection, "native_ai_diagnostics", None)
        if mailbox is not None:
            owner = (
                self.state.account_id,
                self.state.generation,
                None if self.state.character is None else self.state.character["id"],
            )
            diagnostics, dropped = mailbox.drain(owner)
            for fields in diagnostics:
                self.runtime.record(**fields)
            if dropped:
                self.runtime.record(
                    event="combat_background_diagnostics_dropped", count=dropped
                )
        if self.state.character is not None and not self.state.loaded:
            self.state.character.update(
                self.runtime.WORLD.guild_projection(
                    self.state.character["id"], self.state.generation
                )
            )
        if self.state.account_id is not None:
            now = time.monotonic()
            renew = now - self.state.last_session_renewal >= 10
            health_started = time.monotonic()
            try:
                session_health = self.runtime.STORE.session_health(
                    self.state.account_id, self.state.generation, renew=renew
                )
            except Exception as error:
                self.runtime.CHECKPOINT_WRITER.observe_database_health(
                    self.state.account_id, self.state.generation, error=error
                )
                raise
            if renew and session_health["valid"]:
                checkpoint_recovery = (
                    self.runtime.CHECKPOINT_WRITER.observe_database_health(
                        self.state.account_id,
                        self.state.generation,
                        renewed_until=session_health["renewed_until"],
                    )
                )
                if checkpoint_recovery["resumed"]:
                    self.runtime.record(
                        event="combat_checkpoint_health_recovery", **checkpoint_recovery
                    )
            health_elapsed_ms = (time.monotonic() - health_started) * 1000
            if not session_health["valid"] or health_elapsed_ms >= 1000:
                self.runtime.record(
                    event=(
                        "session_failure"
                        if not session_health["valid"]
                        else "session_renewal_slow"
                    ),
                    account_id=self.state.account_id,
                    actor_id=(
                        None
                        if self.state.character is None
                        else self.state.character["id"]
                    ),
                    fight_id=None if self.state.fight is None else self.state.fight.id,
                    turn_id=(
                        None if self.state.fight is None else self.state.fight.turn_id
                    ),
                    renewal_requested=renew,
                    health_elapsed_ms=round(health_elapsed_ms, 3),
                    last_successful_renewal_age_seconds=(
                        None
                        if self.state.last_session_renewal == 0
                        else round(now - self.state.last_session_renewal, 3)
                    ),
                    **session_health,
                )
            if not session_health["valid"]:
                return False
            if renew:
                self.state.last_session_renewal = time.monotonic()
            if self.state.hero_switch_pending is not None:
                # The selected hero joins World only after its native ACK.
                # Keep the account lease alive while deferring all actor
                # publication and timers until that registration completes.
                return True
            if self.continue_committed_travel():
                return True
            if self.state.pending_combat_return is not None:
                pending = self.state.pending_combat_return
                try:
                    completed = pending["retry"].attempt(
                        now=time.monotonic(),
                        flush=lambda: self.runtime.flush_positions(**pending["scope"]),
                        complete=pending["complete"],
                        busy=lambda error, attempt: (
                            self.runtime.record(
                                event="combat_return_position_pending",
                                actor_id=self.state.character["id"],
                                fight_id=pending["fight_id"],
                                attempt=attempt,
                                pending_seconds=round(
                                    time.monotonic() - pending["started_at"], 3
                                ),
                                reason=self.runtime.redact(str(error)),
                            )
                            if attempt == 1 or attempt % 30 == 0
                            else None
                        ),
                    )
                except ValueError as error:
                    self.runtime.record(
                        event="combat_return_rejected",
                        actor_id=self.state.character["id"],
                        fight_id=pending["fight_id"],
                        reason=str(error),
                    )
                    self.state.pending_combat_return = None
                    self.state.pending_return_command.clear()
                    return True
                if completed:
                    self.state.pending_combat_return = None
                    command = self.state.pending_return_command.take(
                        (
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                        ),
                        valid_session=lambda: self.runtime.STORE.current_character_session(
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                        ),
                    )
                    if command is not None:
                        # The real return callback has completed its durable
                        # position fence and retired membership. Run the same
                        # command handlers once; never replay native 12925.
                        if command.lower() in ("!exitdungeon", "!salirmazmorra"):
                            self.execute_dungeon_exit_command()
                        else:
                            try:
                                self.execute_test_command(command)
                            except (ValueError, PermissionError):
                                pass  # The normal command handler sent its rejection.
                else:
                    return True
            if self.consume_command_combat_recovery():
                return True
            if self.continue_aborted_publication_recovery():
                return True
            self.notify_owned_story_refresh()
            self.deliver_rift_transition()
            if (
                self.state.combat_session is None
                or self.deferred_native_combat_attachment() is not None
            ):
                try:
                    self.attempt_shared_combat_attachment()
                except (ValueError, KeyError) as error:
                    self.runtime.record(
                        event="friendly_duel_attach_rejected",
                        actor_id=(
                            None
                            if self.state.character is None
                            else self.state.character["id"]
                        ),
                        reason=str(error),
                    )
            if self.deferred_native_combat_attachment() is not None:
                # No world movement, deadline, ACK or native callback may run
                # against a partially reattached publication cohort.
                return True
            if self.state.combat_session is not None:
                # This runs on the socket reader before reading its next frame.
                # Leave reliable outboxes queued while another combat operation
                # owns the locks, so unrelated chat/input can still be read.
                if self.refresh_shared_combat(blocking=False) is False:
                    return True
                if self.drain_shared_combat(blocking=False) is False:
                    return True
                if (
                    self.state.fight is not None
                    and self.state.fight.phase == "finished"
                ):
                    try:
                        shared_state = self.runtime.COMBAT_SESSIONS.registry.lookup(
                            self.state.fight.id
                        )
                        from wakfu_server.combat_terminal_retry import (
                            pending_terminal_settlement,
                        )

                        if pending_terminal_settlement(shared_state):
                            self.complete_test_fight()
                        self.recover_pending_terminal_world()
                    except ValueError as error:
                        self.runtime.record(
                            event="combat_terminal_settlement_retry",
                            actor_id=self.state.character["id"],
                            fight_id=self.state.fight.id,
                            reason=str(error),
                        )
            self.deliver_rift_transition()
            self.deliver_dungeon_transitions()
            self.deliver_ranch_scene_refresh()
            self.deliver_ranch_cycle_rewards()
            if not self.sync_loaded_world_snapshot():
                self.sync_static_world()
            self.sync_scene_world()
            if self.state.environment_seat is not None and (
                self.state.fight is not None
                or self.state.combat_session is not None
                or self.state.spectator_session is not None
            ):
                self.cancel_environment()
            self.complete_environment_occupation()
            self.complete_artifact_action()
            if (
                self.state.flora_retry_body is not None
                and self.state.flora_ticket is not None
                and self.runtime.STORE.now() >= self.state.flora_ticket["completes_at"]
            ):
                self.complete_flora_occupation(self.state.flora_retry_body)
            self.publish_environment_scene()
            self.poll_national_progression()
            self.poll_environmental_events()
            from psycopg.errors import DeadlockDetected, SerializationFailure

            try:
                self.poll_external_objectives()
            except (DeadlockDetected, SerializationFailure) as error:
                # Poll-owned connection contexts already rolled back. Retry on
                # the next scheduled poll without retiring the selected session.
                self.runtime.record(
                    event="objectives_poll_transaction_retry",
                    account_id=self.state.account_id,
                    actor_id=(
                        self.state.character["id"]
                        if self.state.character is not None
                        else None
                    ),
                    reason=str(error),
                )
            if self.state.pending_travel_resume is not None:
                return True
            if (
                self.state.spectator_session is not None
                and self.state.spectator_fight_id is not None
            ):
                try:
                    if self.state.character is None or (
                        self.state.character["map_id"],
                        self.state.character.get("instance_id", 0),
                    ) != (
                        self.state.spectator_session.map_id,
                        self.state.spectator_session.instance_id,
                    ):
                        self.runtime.SPECTATORS.disconnect(self.state.spectator_session)
                        self.runtime.record(
                            event="combat_spectator_left_location",
                            actor_id=self.state.spectator_session.character_id,
                            fight_id=self.state.spectator_fight_id,
                        )
                        self.state.spectator_session = None
                        self.state.spectator_fight_id = None
                        return True
                    for delivery in self.runtime.SPECTATORS.poll(
                        self.state.spectator_session
                    ):
                        for message_id, payload in delivery.packets:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                message_id,
                                payload,
                            )
                            if message_id == 12238:
                                from wakfu_server.combat_spectator_events import (
                                    is_normal_finish_packet,
                                )

                                if is_normal_finish_packet(
                                    (message_id, payload), self.state.spectator_fight_id
                                ):
                                    from wakfu_server.combat_spectators import (
                                        TerminalAck,
                                    )

                                    self.state.spectator_terminal_pending = TerminalAck(
                                        self.state.spectator_session,
                                        self.state.spectator_fight_id,
                                    )
                    if (
                        self.runtime.SPECTATORS.observing(self.state.spectator_session)
                        is None
                    ):
                        self.runtime.record(
                            event="combat_spectator_subscription_closed",
                            actor_id=self.state.spectator_session.character_id,
                            fight_id=self.state.spectator_fight_id,
                        )
                        self.state.spectator_session = None
                        self.state.spectator_fight_id = None
                except ValueError as error:
                    self.runtime.SPECTATORS.disconnect(self.state.spectator_session)
                    self.runtime.record(
                        event="combat_spectator_lease_expired",
                        actor_id=self.state.spectator_session.character_id,
                        fight_id=self.state.spectator_fight_id,
                        reason=str(error),
                    )
                    return False
            if time.monotonic() - now >= 10:
                self.runtime.record(
                    event="session_idle_slow",
                    account_id=self.state.account_id,
                    actor_id=(
                        None
                        if self.state.character is None
                        else self.state.character["id"]
                    ),
                    fight_id=None if self.state.fight is None else self.state.fight.id,
                    elapsed_ms=round((time.monotonic() - now) * 1000, 3),
                )
            for map_id, instance_id, packet in self.runtime.HARVESTS.due_availability(
                blocking=False
            ):
                self.runtime.WORLD.emit_location(map_id, instance_id, *packet)
            if self.state.placement_deadline.take_expired(self.state.fight, now):
                try:
                    self.apply_readiness(True)
                    self.checkpoint_fight()
                    self.runtime.record(
                        event="combat_placement_expired",
                        fight_id=self.state.fight.id,
                        actor_id=self.state.character["id"],
                    )
                except ValueError as error:
                    self.runtime.record(
                        event="combat_placement_expiry_rejected",
                        fight_id=self.state.fight.id,
                        actor_id=self.state.character["id"],
                        reason=str(error),
                    )
            if self.state.fight_messages is not None and self.state.fight is not None:
                if self.state.combat_session is not None:
                    # A failed Ready/ACK callback can leave an unpublished NPC
                    # action pending. Any remaining owner may retry it; the AI
                    # bridge claims the actual shared actor/turn under its lock.
                    from wakfu_server.combat_effective_control import (
                        effective_server_controlled,
                    )
                    from wakfu_server.combat_automatic_npc_turn import (
                        requires_automatic_npc_turn_end,
                    )

                    if (
                        self.state.fight.phase == "active"
                        and self.state.fight.current is not None
                        and (
                            effective_server_controlled(
                                self.state.fight, self.state.fight.current
                            )
                            or requires_automatic_npc_turn_end(
                                self.state.fight, self.state.fight.current
                            )
                        )
                        and self.state.fight_messages.awaiting_ack is None
                        and not self.state.fight_messages.pending
                    ):
                        self.pass_test_monster_turn()
                        self.refresh_shared_combat()
                        self.drain_shared_combat()
                    (
                        expired,
                        expiry_error,
                    ) = self.runtime.COMBAT_SESSIONS.expire_current_turn(
                        self.state.fight.id,
                        self.state.combat_session,
                        now_ms=int(time.time() * 1000),
                    )
                    if expired:
                        self.refresh_shared_combat()
                        self.drain_shared_combat()
                        self.checkpoint_fight()
                        self.runtime.record(
                            event=(
                                "combat_turn_expiry_recovered"
                                if expiry_error is not None
                                else "combat_turn_expired"
                            ),
                            fight_id=self.state.fight.id,
                            actor_id=self.state.character["id"],
                        )
                        if self.state.fight.phase == "finished":
                            self.complete_test_fight()
                else:
                    (
                        expired_packets,
                        expiry_error,
                    ) = self.state.fight_messages.expire_current_or_recover(
                        self.state.account_id, now_ms=int(time.time() * 1000)
                    )
                    if expiry_error is not None:
                        self.runtime.record(
                            event="combat_turn_expiry_rejected",
                            fight_id=self.state.fight.id,
                            actor_id=self.state.character["id"],
                            reason=expiry_error,
                        )
                    for message_id, payload in expired_packets:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            message_id,
                            payload,
                        )
                    if expired_packets:
                        self.checkpoint_fight()
                        self.runtime.record(
                            event=(
                                "combat_turn_expiry_recovered"
                                if expiry_error is not None
                                else "combat_turn_expired"
                            ),
                            fight_id=self.state.fight.id,
                            actor_id=self.state.character["id"],
                        )
                    if self.state.fight.phase == "finished":
                        self.complete_test_fight()
            if (
                self.state.loaded
                and self.state.character is not None
                and self.state.fight is None
                and self.state.combat_session is None
                and time.monotonic() >= self.state.pet_hibernation_due
            ):
                self.refresh_pet_hibernation()
            if (
                self.state.loaded
                and self.state.character is not None
                and time.monotonic() - self.state.last_consumable_tick >= 5
            ):
                from wakfu_server.consumable_world_publication import (
                    synchronize_and_publish,
                )

                self.state.last_consumable_tick = time.monotonic()
                self.state.character = synchronize_and_publish(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    in_combat=self.state.fight is not None
                    or self.state.combat_session is not None,
                    allocate_action=lambda: next(self.runtime.LOCAL_WORLD_ACTIONS),
                    send=lambda opcode, body: self.runtime.send(
                        self.state.connection, self.state.service, opcode, body
                    ),
                    broadcast_main=lambda opcode, body: self.runtime.WORLD.broadcast(
                        self.state.generation,
                        self.state.character["id"],
                        opcode,
                        body,
                    ),
                    publish_main=self.publish_consumable_character,
                )
            if (
                self.state.loaded
                and self.state.character is not None
                and self.state.fight is None
                and self.state.combat_session is None
                and self.state.spectator_session is None
            ):
                bonus_packets = self.runtime.REGIONAL_BONUSES.packets_for(
                    self.state.character, self.state.generation, self.state.connection
                )
                for bonus_packet in bonus_packets:
                    self.runtime.send(self.state.connection, "world", *bonus_packet)
                if bonus_packets:
                    self.runtime.REGIONAL_BONUSES.acknowledge(
                        self.state.character,
                        self.state.generation,
                        self.state.connection,
                        bonus_packets,
                    )
            if (
                self.state.loaded
                and self.state.character is not None
                and self.state.fight is None
                and self.state.combat_session is None
                and time.monotonic() - self.state.last_shop_refresh >= 1
            ):
                from psycopg import Error as DatabaseError
                from psycopg_pool import PoolTimeout
                from wakfu_server import shop_refresh

                self.state.last_shop_refresh = time.monotonic()
                try:
                    purchase = shop_refresh.pending(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.character,
                        self.state.generation,
                    )
                    if purchase is not None:
                        for message_id, payload in purchase["packets"]:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                message_id,
                                payload,
                            )
                        self.state.character = purchase["character"]
                        shop_refresh.acknowledge(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.character["id"],
                            purchase["order_ids"],
                            self.state.generation,
                            purchase.get("feedback_revision"),
                        )
                        self.runtime.record(
                            event="shop_purchase_delivered",
                            actor_id=self.state.character["id"],
                            order_ids=purchase["order_ids"],
                        )
                except (ValueError, DatabaseError, PoolTimeout) as error:
                    self.runtime.record(
                        event="shop_purchase_delivery_retry",
                        actor_id=self.state.character["id"],
                        reason=type(error).__name__,
                    )
            if (
                self.state.loaded
                and self.state.character is not None
                and self.state.fight is None
                and self.state.combat_session is None
                and time.monotonic() - self.state.last_health_tick >= 1
            ):
                self.state.last_health_tick = time.monotonic()
                updates = self.runtime.health_store.tick_company(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.character["hp"],
                )
                for saved in updates:
                    is_main = saved["id"] == self.state.character["id"]
                    if is_main:
                        self.state.character.update(
                            hp=saved["hp"],
                            max_hp=saved["max_hp"],
                            hp_damage=saved["hp_damage"],
                            health_dead=saved["health_dead"],
                        )
                    if not saved["health_changed"]:
                        continue
                    packet = self.runtime.health.packet(
                        saved["id"], saved["hp"], saved["regeneration_coefficient"]
                    )
                    if is_main:
                        self.runtime.WORLD.update(
                            self.state.generation, self.state.character, 12436, packet
                        )
                    else:
                        # Heroes share their main's audience, not a world presence row.
                        self.runtime.WORLD.broadcast(
                            self.state.generation,
                            self.state.character["id"],
                            12436,
                            packet,
                        )
                    self.runtime.record(
                        event="health_regenerated",
                        actor_id=saved["id"],
                        previous_hp=saved["previous_hp"],
                        hp=saved["hp"],
                        max_hp=saved["max_hp"],
                    )
            if (
                self.state.loaded
                and self.state.character is not None
                and os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
            ):
                current_console = (self.state.character["id"], self.state.generation)
                if self.state.console_session != current_console:
                    if self.state.console_session is not None:
                        self.runtime.TEST_CONSOLE.unregister(
                            *self.state.console_session
                        )
                    self.runtime.TEST_CONSOLE.register(
                        self.state.character["id"],
                        self.state.generation,
                        name=self.state.character["name"],
                        account_id=self.state.account_id,
                    )
                    self.state.console_session = current_console
                self.runtime.TEST_CONSOLE.drain(
                    self.state.character["id"],
                    self.state.generation,
                    self.execute_test_command,
                )
            return True
        return time.monotonic() - self.state.connected_at < 30
