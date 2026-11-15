"""Characters operations for one lease-bound World session."""

import struct
from .dispatch_result import DispatchResult


class CharacterSessionMixin:
    def handle_character_list(self):
        try:
            self.state.request = self.runtime.decode_body(
                "out", self.state.opcode, self.state.body
            )
            self.runtime.send_shop_authentication(
                self.state.connection,
                self.state.service,
                self.state.account_id,
                self.state.generation,
                language=self.state.request["language"],
            )
        except (
            ValueError,
            UnicodeError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
        ) as error:
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    "No se pudo conectar con la tienda. Cierra y vuelve "
                    "a abrir la tienda; si persiste, reconecta al juego."
                ),
            )
            self.runtime.record(
                event="shop_authentication_rejected",
                account_id=self.state.account_id,
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_character_selection_prepare(self):
        if self.state.account_id is None or self.state.body != b"\x00":
            raise ValueError("Invalid character selection request")
        self.state.spectator_terminal_pending = None
        if self.state.combat_session is not None and self.state.fight is not None:
            self.state.shared_selection = self.refresh_shared_combat()
            if (
                not getattr(self.state.shared_selection, "is_duel", False)
                and getattr(self.state.shared_selection.fight, "phase", None)
                == "finished"
            ):
                terminal_selection_fight_id = self.state.fight.id
                terminal_selection_error = None
                try:
                    if not self.state.shared_selection.settlement_ready:
                        self.complete_test_fight()
                    if self.state.pending_terminal_world_recovery is not None:
                        self.recover_pending_terminal_world()
                    else:
                        self.drain_shared_combat()
                except (
                    ValueError,
                    self.state.DatabaseError,
                    self.state.PoolTimeout,
                ) as error:
                    terminal_selection_error = str(error)
                if self.state.combat_session is not None:
                    # A selector request is not a native12925 ACK.
                    # Keep attached terminal ownership until the
                    # real return, or an already-proven fresh-login
                    # world recovery, completes its durable return.
                    self.runtime.record(
                        event="combat_terminal_character_selection_deferred",
                        actor_id=self.state.character["id"],
                        fight_id=terminal_selection_fight_id,
                        settlement_ready=self.state.shared_selection.settlement_ready,
                        reason=terminal_selection_error,
                        native_return_ack=False,
                    )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        674,
                        self.runtime.wire.chat(
                            dict(self.state.character, name="Consola local"),
                            "Cierra el resultado del combate antes de cambiar de personaje.",
                        ),
                    )
                    return DispatchResult.CONTINUE
        if self.state.combat_session is not None and self.state.fight is not None:
            from wakfu_server.combat_pve_withdraw import (
                has_other_live_owner,
            )

            self.state.has_other_live_owner = has_other_live_owner

            if not getattr(
                self.state.shared_selection, "is_duel", False
            ) and self.state.has_other_live_owner(
                self.state.shared_selection.fight, self.state.combat_session
            ):
                try:
                    self.state.pve_withdrawal_pending = (
                        self.runtime.COMBAT_SESSIONS.withdraw_pve(
                            self.state.combat_session, self.state.character, b""
                        )
                    )
                except ValueError as error:
                    self.state.shared_selection = self.refresh_shared_combat()
                    if (
                        getattr(self.state.shared_selection, "is_duel", False)
                        or getattr(self.state.shared_selection.fight, "phase", None)
                        != "finished"
                    ):
                        raise
                    # The authoritative withdrawal rejects before
                    # writes if another owner just ended the fight.
                    # Preserve the terminal session for its real ACK.
                    self.runtime.record(
                        event="combat_terminal_character_selection_deferred",
                        actor_id=self.state.character["id"],
                        fight_id=self.state.shared_selection.fight.id,
                        settlement_ready=self.state.shared_selection.settlement_ready,
                        reason=str(error),
                        native_return_ack=False,
                    )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        674,
                        self.runtime.wire.chat(
                            dict(self.state.character, name="Consola local"),
                            "Cierra el resultado del combate antes de cambiar de personaje.",
                        ),
                    )
                    return DispatchResult.CONTINUE
                self.publish_external_marker(self.state.shared_selection)
                self.state.character.update(
                    self.refresh_owned_character(
                        self.state.pve_withdrawal_pending["character"]
                    )
                )
                self.state.fight = self.state.fight_messages = None
                self.state.combat_session = self.state.group_lease = None
            elif (
                not getattr(self.state.shared_selection, "is_duel", False)
                and not self.state.shared_selection.settlement_ready
            ):
                from wakfu_server.combat_abandon import (
                    prepare as prepare_selection_abandon,
                    placement_runtime as selection_abandon_runtime,
                    return_to_world as return_selection_abandon,
                )

                with self.state.shared_selection.lock:
                    self.state.selection_runtime = selection_abandon_runtime(
                        self.state.fight, self.state.shared_selection.runtime
                    )
                    from wakfu_server.combat_shared_abandon import (
                        requires_shared_abort,
                    )

                    self.state.requires_shared_abort = requires_shared_abort

                    if self.state.requires_shared_abort(
                        self.state.shared_selection.fight, self.state.combat_session
                    ):
                        abandoned_selection = (
                            self.runtime.COMBAT_SESSIONS.abandon_shared_pve(
                                self.state.combat_session,
                                self.state.character,
                                b"",
                                groups=self.runtime.COMBAT_GROUPS,
                                shared=self.state.shared_selection,
                            )
                        )
                        self.state.fight = self.state.shared_selection.fight
                        self.state.selection_runtime = (
                            self.state.shared_selection.runtime
                        )
                    else:
                        abandoned_selection = prepare_selection_abandon(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.selection_runtime,
                            b"",
                        )
                        self.state.shared_selection.runtime = (
                            self.state.selection_runtime
                        )
                    self.state.character.update(
                        self.refresh_owned_character(abandoned_selection["character"])
                    )
                    if not abandoned_selection.get("shared_full_abort"):
                        return_selection_abandon(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.selection_runtime,
                            struct.pack(">iB", self.state.fight.id, 1),
                            wp=self.runtime.COMBAT_TEST_WP,
                        )
                self.publish_external_marker(self.state.shared_selection)
                self.publish_spectator_state(
                    self.state.shared_selection, abandoned_selection["packets"]
                )
                if abandoned_selection.get("shared_full_abort"):
                    self.publish_full_abandon_group(
                        self.state.shared_selection, abandoned_selection
                    )
                    self.drain_shared_combat()
                    returned_selection = (
                        self.runtime.COMBAT_SESSIONS.return_withdrawn_pve(
                            self.state.combat_session,
                            self.state.fight.id,
                            self.state.character,
                            struct.pack(">iB", self.state.fight.id, 1),
                            wp=self.runtime.COMBAT_TEST_WP,
                            pending=self.state.shared_selection.withdrawals[
                                self.state.account_id
                            ],
                        )
                    )
                    self.state.character.update(
                        self.refresh_owned_character(returned_selection["character"])
                    )
                else:
                    if not self.runtime.COMBAT_SESSIONS.registry.retire_abandoned_single_owner(
                        self.state.fight.id, self.state.combat_session
                    ):
                        raise ValueError("Selector PvE abandon was not safely retired")
                if self.state.shared_selection.group_lease is not None:
                    self.runtime.COMBAT_GROUPS.finish(
                        self.state.shared_selection.group_lease, defeated=False
                    )
                self.state.fight = self.state.fight_messages = None
                self.state.combat_session = self.state.group_lease = None
        if self.state.pve_withdrawal_pending is not None:
            from wakfu_server.combat_pve_withdraw_store import (
                WithdrawalRecoveryDeferred,
            )

            self.state.WithdrawalRecoveryDeferred = WithdrawalRecoveryDeferred

            try:
                self.state.recovered = (
                    self.runtime.COMBAT_SESSIONS.recover_withdrawn_pve(
                        self.runtime.COMBAT_SESSIONS.session(
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                        )
                    )
                )
            except self.state.WithdrawalRecoveryDeferred as error:
                self.runtime.record(
                    event="withdrawal_selection_return_deferred",
                    character_id=self.state.character["id"],
                    reason=str(error),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"),
                        "Tu progreso está guardado. La recuperación del personaje sigue pendiente; "
                        "la conexión permanece abierta.",
                    ),
                )
                return DispatchResult.CONTINUE
            if self.state.recovered is not None:
                self.state.character.update(self.state.recovered)
            self.state.pve_withdrawal_pending = None
        from wakfu_server.combat_health import persist_aborted_fight

        self.state.persist_aborted_fight = persist_aborted_fight

        self.checkpoint_fight(
            "ended"
            if self.state.fight is not None and self.state.fight.phase == "finished"
            else "aborted"
        )
        self.state.persist_aborted_fight(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character,
            self.state.fight,
        )
        if not self.runtime.COMBAT_SESSIONS.registry.lease_generation_active(
            self.state.generation
        ):
            self.runtime.release_groups(self.state.generation)
        self.state.group_lease = None
        self.state.fight = self.state.fight_messages = None
        if self.state.character is not None:
            self.runtime.POSITIONS.release(
                self.state.account_id, self.state.generation, self.state.character["id"]
            )
        self.runtime.STORE.clear_character(self.state.account_id, self.state.generation)
        if self.state.character is not None:
            self.state.exterior = self.runtime.HAVEN_BAG_EXTERIORS.discard(
                self.state.generation,
                (
                    self.state.bag_session.exterior_actor_id
                    if self.state.bag_session is not None
                    else self.state.character["id"]
                ),
            )
            if self.state.exterior is not None:
                self.state.outside, self.state.packet = self.state.exterior
                self.runtime.WORLD.emit_location(
                    self.state.outside["map_id"],
                    self.state.outside["instance_id"],
                    *self.state.packet,
                )
            self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        self.state.selected = self.state.loaded = False
        self.state.hero_switch_pending = None
        self.state.character = None
        self.state.movement_state = None
        self.state.bag_session = None
        self.state.ranch_session = None
        self.runtime.replay(
            self.state.connection,
            31,
            44,
            self.state.account_id,
            generation=self.state.generation,
        )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            13873,
            self.runtime.wire.account_kamas(
                self.runtime.STORE.account_kamas(self.state.account_id)
            ),
        )
        self.runtime.record(
            event="returned_to_character_selection", account_id=self.state.account_id
        )
        return DispatchResult.FALLTHROUGH

    def handle_character_create(self):
        if self.state.account_id is None or self.state.selected:
            raise ValueError("Authentication required or character already selected")
        self.state.status, created = self.runtime.create_character_request(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.body,
        )
        self.runtime.send(
            self.state.connection, self.state.service, 22025, bytes([self.state.status])
        )
        if created is not None:
            if not created.get("recustomized"):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    13078,
                    self.runtime.wire.adapt(
                        13078,
                        self.runtime.fixture(13078),
                        self.state.account_id,
                        created,
                    ),
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                12393,
                self.runtime.wire.attribute_sheets(
                    self.runtime.fixture(12393),
                    self.runtime.STORE.characters(self.state.account_id),
                ),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                23548,
                self.runtime.wire.character_list(
                    self.runtime.CHARACTERS,
                    self.state.account_id,
                    self.runtime.STORE.characters(self.state.account_id),
                ),
            )
            self.runtime.record(
                event="character_created",
                account_id=self.state.account_id,
                character_id=created["id"],
                breed=created["breed"],
            )
            # Official creation selects the new character server-side;
            # it sends 23082/bootstrap without waiting for 23664.
            self.state.character = self.runtime.select_created_character(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                created["id"],
            )
            self.deliver_custom_task_rewards(bootstrap=True)
            self.state.character = self.runtime.health_store.initialize(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                exploration=True,
            )
            self.runtime.POSITIONS.attach(
                self.state.account_id, self.state.generation, self.state.character
            )
            self.state.position = {k: self.state.character[k] for k in ("x", "y", "z")}
            self.state.movement_state = self.runtime.Movement(self.state.position)
            self.state.selected = True
            self.runtime.replay(
                self.state.connection,
                45,
                114,
                self.state.account_id,
                self.state.character,
                generation=self.state.generation,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.rich_inventory_packet(self.state.character),
            )
            from wakfu_server.inventory_uids import initialize_pool

            self.state.initialize_pool = initialize_pool

            self.state.message_id, self.state.message_body = self.state.initialize_pool(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )["packet"]
            self.runtime.send(
                self.state.connection,
                self.state.service,
                self.state.message_id,
                self.state.message_body,
            )
            self.runtime.record(
                event="character_selected_after_creation",
                account_id=self.state.account_id,
                character_id=self.state.character["id"],
            )
        return DispatchResult.FALLTHROUGH

    def handle_created_character_select(self):
        character_id = None
        deleted = False
        if self.state.account_id is None:
            error = ValueError("Authentication required")
        elif self.state.selected:
            error = ValueError("Return to character selection before deletion")
        else:
            try:
                self.state.request = self.runtime.decode_body(
                    "out", self.state.opcode, self.state.body
                )
                character_id = self.state.request["character_id"]
                with self.runtime.PARTIES._guard(character_id):
                    self.state.result = self.runtime.STORE.delete_character(
                        self.state.account_id, self.state.generation, character_id
                    )
                    deleted = True
                    try:
                        self.runtime.PARTIES.publish_character_deletion(
                            self.state.result["party_change"]
                        )
                    except Exception as failure:
                        self.runtime.record(
                            event="character_deletion_party_publish_failed",
                            character_id=character_id,
                            reason=str(failure),
                        )
            except (ValueError, UnicodeError) as failure:
                error = failure
        if not deleted:
            self.runtime.record(
                event="character_deletion_rejected",
                account_id=self.state.account_id,
                reason=str(error),
            )
        else:
            self.runtime.record(
                event="character_deleted",
                account_id=self.state.account_id,
                character_id=character_id,
            )
        if self.state.account_id is not None and not self.state.selected:
            owned = self.runtime.STORE.characters(self.state.account_id)
            self.runtime.send(
                self.state.connection,
                self.state.service,
                12393,
                self.runtime.wire.attribute_sheets(self.runtime.fixture(12393), owned),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                23548,
                self.runtime.wire.character_list(
                    self.runtime.CHARACTERS, self.state.account_id, owned
                ),
            )
        return DispatchResult.FALLTHROUGH

    def handle_character_select(self):
        self.state.request = self.runtime.decode_body(
            "out", self.state.opcode, self.state.body
        )
        if self.state.selected:
            from wakfu_server.character_selection_retry import (
                already_selected_owned_character,
            )

            if already_selected_owned_character(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.request,
            ):
                self.runtime.record(
                    event="character_selection_retry_ignored",
                    character_id=self.state.character["id"],
                )
                return DispatchResult.CONTINUE
        if self.state.account_id is None or self.state.selected:
            raise ValueError("Authentication required or character already selected")
        from wakfu_server.heroes import CompanySelectionRejected

        pending_character = self.runtime.STORE.character(
            self.state.account_id, self.state.request["character_id"]
        )
        if pending_character.get("recustomization"):
            if self.state.request["character_name"] != pending_character["name"]:
                raise ValueError("Character name mismatch")
            from wakfu_server.character_recustomization import (
                transition_packets,
            )

            for self.state.packet in transition_packets(pending_character):
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            return DispatchResult.CONTINUE
        try:
            self.state.character = self.runtime.STORE.select_character(
                self.state.account_id,
                self.state.generation,
                self.state.request["character_id"],
            )
        except CompanySelectionRejected as error:
            from wakfu_server.ecology_feedback import information

            self.state.information = information
            from wakfu_server.player_action_feedback import failure_message

            self.state.failure_message = failure_message

            self.runtime.send(self.state.connection, self.state.service, 23082, b"\x01")
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    self.state.failure_message("hero_selection", error)
                ),
            )
            self.runtime.record(
                event="character_selection_rejected",
                account_id=self.state.account_id,
                character_id=self.state.request["character_id"],
                reason=str(error),
            )
            return DispatchResult.CONTINUE
        from wakfu_server.achievements import rii_training_arena

        self.state.training_transit_active = rii_training_arena.pending(
            self.runtime.STORE, self.state.account_id, self.state.character["id"]
        )
        if self.state.training_transit_active:
            # Recover a completed training return if the connection
            # was lost after settlement but before the world exit.
            # An unfinished or active fight stays on the floor.
            try:
                available = (
                    self.training_occupancy_snapshot(returning=True)
                    if self.state.character["map_id"] == 1388
                    and self.state.character["instance_id"] == 0
                    else lambda destination: True
                )
                self.state.recovered = rii_training_arena.return_to_source(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    available=available,
                    only_completed=True,
                )
                if self.state.recovered is not None:
                    self.state.character = self.state.recovered
                self.state.training_transit_active = rii_training_arena.pending(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                )
            except ValueError as error:
                self.runtime.record(
                    event="rii_training_recovery_deferred",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
        # The native Otomai dialogue promises that prior boss
        # victories are reconciled on reconnect. Keep failures
        # isolated from character selection and normal gameplay.
        try:
            from wakfu_server.achievements.otomai_hunter_retroactive import (
                reconcile as reconcile_otomai_hunts,
            )

            with self.runtime.STORE.connection() as quest_db:
                quest_db.execute(
                    "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                    (self.state.account_id,),
                )
                self.runtime.STORE.lock_character(
                    quest_db,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    selected=True,
                )
                with quest_db.transaction():
                    reconciled = reconcile_otomai_hunts(
                        quest_db,
                        self.runtime.STORE,
                        self.state.character,
                        now_ms=int(self.runtime.STORE.now().timestamp() * 1000),
                    )
            if reconciled:
                self.state.character = self.runtime.STORE.character(
                    self.state.account_id, self.state.character["id"]
                )
        except Exception as error:
            self.runtime.record(
                event="otomai_hunter_reconcile_failed",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        from wakfu_server import dungeon_recovery

        try:
            if dungeon_recovery.has_persisted_context(
                self.runtime.STORE, self.state.character
            ):
                from wakfu_server import dungeon_runtime

                self.state.dungeon_runtime = dungeon_runtime
                from wakfu_server.combat_terrain import map_geometry

                self.state.map_geometry = map_geometry

                recovery = dungeon_recovery.resume_member(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.character["instance_id"],
                    positions=self.runtime.POSITIONS,
                    in_fight=lambda actor_id: self.runtime.COMBAT_SESSIONS.lookup_character(
                        actor_id
                    )
                    is not None,
                )
                self.state.character = dungeon_recovery.prepare_selected_room(
                    self.runtime.STORE,
                    self.runtime.COMBAT_GROUPS,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    positions=self.runtime.POSITIONS,
                    in_fight=lambda actor_id: self.runtime.COMBAT_SESSIONS.lookup_character(
                        actor_id
                    )
                    is not None,
                    geometry_provider=self.state.map_geometry,
                )
        except dungeon_recovery.DungeonLoginRecoveryDeferred as error:
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            self.runtime.record(
                event="character_dungeon_recovery_deferred",
                character_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.STORE.clear_character(
                self.state.account_id, self.state.generation
            )
            self.state.character = None
            self.runtime.send(self.state.connection, self.state.service, 23082, b"\x01")
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    "Tu progreso está guardado, pero aún no podemos recuperar una posición segura. "
                    "La conexión sigue abierta; puedes volver a intentarlo."
                ),
            )
            return DispatchResult.CONTINUE
        from wakfu_server import heroes

        self.state.heroes = heroes

        self.state.heroes.select_main(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
        )
        from wakfu_server import companions

        self.state.companions = companions

        with self.runtime.STORE.connection() as self.state.companion_db:
            self.state.companion_db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                (self.state.account_id,),
            )
            self.runtime.STORE.lock_character(
                self.state.companion_db,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
            self.state.companions.select_main(
                self.state.companion_db,
                self.state.account_id,
                self.state.character["id"],
            )
        if self.state.request["character_name"] != self.state.character["name"]:
            raise ValueError("Character name mismatch")
        reconnect_session = self.runtime.COMBAT_SESSIONS.session(
            self.state.account_id, self.state.generation, self.state.character
        )
        live_reconnect = self.runtime.COMBAT_SESSIONS.live_reconnect_available(
            reconnect_session
        )
        reconciliation = (
            None
            if live_reconnect
            else self.runtime.COMBAT_SESSIONS.reconcile_disconnected_pve(
                reconnect_session, groups=self.runtime.COMBAT_GROUPS
            )
        )
        if reconciliation is not None:
            orphan = reconciliation["shared"]
            # Durable health/abort committed before registry removal.
            # Refresh before regeneration, position attachment and
            # world bootstrap; never initialize from stale login HP.
            self.state.character = self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"]
            )
            with orphan.lock:
                orphan.fight.phase = "finished"
                orphan.fight.winner = None
            self.publish_external_marker(orphan)
            self.runtime.record(
                event="shared_pve_reconnect_reconciled",
                actor_id=self.state.character["id"],
                fight_id=orphan.fight.id,
                registry_retired=True,
                durable_abort=True,
            )
        from wakfu_server.combat_pve_withdraw_store import (
            WithdrawalRecoveryDeferred,
        )

        self.state.WithdrawalRecoveryDeferred = WithdrawalRecoveryDeferred

        try:
            self.state.recovered = self.runtime.COMBAT_SESSIONS.recover_withdrawn_pve(
                self.runtime.COMBAT_SESSIONS.session(
                    self.state.account_id, self.state.generation, self.state.character
                )
            )
        except self.state.WithdrawalRecoveryDeferred as error:
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            self.runtime.record(
                event="withdrawal_character_selection_deferred",
                character_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.STORE.clear_character(
                self.state.account_id, self.state.generation
            )
            self.state.character = None
            self.runtime.send(self.state.connection, self.state.service, 23082, b"\x01")
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    "Tu progreso está guardado. La recuperación del personaje sigue pendiente; "
                    "la conexión permanece abierta."
                ),
            )
            return DispatchResult.CONTINUE
        if self.state.recovered is not None:
            self.state.character.update(self.state.recovered)
        recovered_rift = self.runtime.reconcile_closed_rift_login(
            self.runtime.STORE,
            self.runtime.POSITIONS,
            self.state.account_id,
            self.state.generation,
            self.state.character,
            live_reconnect=live_reconnect,
            fighting=lambda identity: self.runtime.COMBAT_SESSIONS.lookup_character(
                identity
            )
            is not None,
        )
        if recovered_rift is not None:
            self.state.character = recovered_rift
            self.runtime.record(
                event="closed_rift_login_recovered",
                actor_id=self.state.character["id"],
                map_id=self.state.character["map_id"],
                instance_id=self.state.character["instance_id"],
            )
        self.deliver_custom_task_rewards(bootstrap=True)
        self.state.character = self.runtime.health_store.initialize(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            exploration=not live_reconnect,
        )
        self.runtime.POSITIONS.attach(
            self.state.account_id, self.state.generation, self.state.character
        )
        self.state.position = {k: self.state.character[k] for k in ("x", "y", "z")}
        self.state.movement_state = self.runtime.Movement(self.state.position)
        self.state.selected = True
        self.runtime.replay(
            self.state.connection,
            45,
            114,
            self.state.account_id,
            self.state.character,
            generation=self.state.generation,
        )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *self.runtime.builds.selection_message(self.state.character),
        )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *self.runtime.rich_inventory_packet(self.state.character),
        )
        from wakfu_server.inventory_uids import initialize_pool

        self.state.initialize_pool = initialize_pool

        self.state.message_id, self.state.message_body = self.state.initialize_pool(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
        )["packet"]
        self.runtime.send(
            self.state.connection,
            self.state.service,
            self.state.message_id,
            self.state.message_body,
        )
        self.runtime.record(
            event="character_selected",
            account_id=self.state.account_id,
            character_id=self.state.character["id"],
            name=self.state.character["name"],
        )
        return DispatchResult.FALLTHROUGH
