"""Combat admission operations for one lease-bound World session."""

import secrets
import struct
import os
import time
from .dispatch_result import DispatchResult


class CombatAdmissionMixin:
    def handle_duel_invite(self):
        from wakfu_server.friendly_duel_wire import cancellation

        self.state.cancellation = cancellation

        try:
            if (
                not self.runtime.COMBAT_TEST
                or self.state.fight is not None
                or self.state.bag_session is not None
                or self.state.spectator_session is not None
            ):
                raise ValueError("Duel invitations are unavailable in this session")
            from wakfu_server.friendly_duel_wire import (
                decode_challenge,
            )
            from wakfu_server.friendly_duels import (
                cancel_undelivered_invitation,
                invite_challenge,
                owned_duel_target,
            )

            self.state.request = decode_challenge(self.state.body)
            self.state.identity = self.runtime.WORLD.live_identity(
                character_id=self.state.request["target_character_id"]
            )
            challenger_session = self.runtime.COMBAT_SESSIONS.session(
                self.state.account_id, self.state.generation, self.state.character
            )
            own_target = (
                owned_duel_target(
                    self.runtime.STORE,
                    challenger_session,
                    self.state.request["target_character_id"],
                )
                if self.state.identity is None
                or self.state.identity[1]["account_id"] == self.state.account_id
                else None
            )
            if self.state.identity is None and own_target is None:
                raise ValueError("Duel target is offline")
            if own_target is not None:
                from wakfu_server.combat_shared import Session

                target_generation, self.state.target_character = (
                    self.state.generation,
                    own_target,
                )
                target_session = Session(
                    self.state.account_id,
                    own_target["id"],
                    self.state.generation,
                    own_target["map_id"],
                    own_target.get("instance_id", 0),
                )
                delivery_character_id = self.state.character["id"]
            else:
                target_generation, self.state.target_character = self.state.identity
                target_session = self.runtime.COMBAT_SESSIONS.session(
                    self.state.target_character["account_id"],
                    target_generation,
                    self.state.target_character,
                )
                delivery_character_id = self.state.target_character["id"]
            self.runtime.flush_positions(
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
            )
            self.runtime.flush_positions(
                account_id=self.state.target_character["account_id"],
                generation=target_generation,
                character_id=delivery_character_id,
            )
            self.state.result = invite_challenge(
                self.runtime.STORE, challenger_session, target_session, self.state.body
            )
            bot_runtime = (
                None
                if self.runtime.BOTS_BRIDGE is None
                else self.runtime.BOTS_BRIDGE.runtime
            )
            bot_target = False
            if bot_runtime is not None:
                with bot_runtime.lock:
                    bot_target = any(
                        lease["character_id"] == self.state.target_character["id"]
                        for lease in bot_runtime.active.values()
                    )
            if bot_target:
                from wakfu_server.bots.friendly_duel import (
                    accept as accept_bot_duel,
                )

                try:
                    accepted = accept_bot_duel(
                        bot_runtime,
                        self.runtime.COMBAT_SESSIONS,
                        target_session,
                        self.state.character["id"],
                        self.runtime.flush_positions,
                    )
                except Exception:
                    cancel_undelivered_invitation(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.character["id"],
                        self.state.result["invitation_id"],
                    )
                    raise
                if not accepted.get("accepted"):
                    raise ValueError("Bot challenge was not accepted")
                self.adopt_shared_duel()
                self.drain_shared_combat()
                self.apply_readiness(True, acting_session=target_session)
                self.checkpoint_fight()
            elif not self.runtime.WORLD.send_to(
                delivery_character_id,
                target_generation,
                *self.state.result["packet"],
            ):
                cancel_undelivered_invitation(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                    self.state.result["invitation_id"],
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.cancellation(6),
                )
            self.runtime.record(
                event="friendly_duel_invitation",
                actor_id=self.state.character["id"],
                target_id=self.state.target_character["id"],
                delivered=bool(self.state.result),
            )
        except ValueError as error:
            self.runtime.record(
                event="friendly_duel_invitation_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection, self.state.service, *self.state.cancellation(7)
            )
        return DispatchResult.FALLTHROUGH

    def handle_duel_accept(self):
        from wakfu_server.friendly_duel_wire import cancellation

        self.state.cancellation = cancellation

        try:
            if (
                not self.runtime.COMBAT_TEST
                or self.state.fight is not None
                or self.state.bag_session is not None
            ):
                raise ValueError("Duel answer is unavailable in this session")
            from wakfu_server.friendly_duel_runtime import (
                prepare_and_register,
            )

            self.state.prepare_and_register = prepare_and_register
            from wakfu_server.friendly_duels import (
                answer_challenge,
                flush_answer_positions,
            )

            # Checkpoint only these duel owners, never the world.
            flush_answer_positions(
                self.runtime.STORE,
                self.runtime.COMBAT_SESSIONS.session(
                    self.state.account_id, self.state.generation, self.state.character
                ),
                self.state.body,
                self.runtime.flush_positions,
            )

            from wakfu_server.combat_terrain import prepare_terrain

            def prepare_duel(
                db,
                fight_id,
                invitation,
                challenger,
                target,
                *,
                prepared_terrain=None,
            ):
                prepared = self.state.prepare_and_register(
                    self.runtime.STORE,
                    self.runtime.COMBAT_SESSIONS,
                    db,
                    fight_id,
                    invitation,
                    challenger,
                    target,
                    auto_locked=bool(invitation["auto_lock"]),
                    prepared_terrain=prepared_terrain,
                )
                rollback = prepared.pop("rollback")
                return prepared, rollback

            self.state.result = answer_challenge(
                self.runtime.STORE,
                self.runtime.COMBAT_SESSIONS.session(
                    self.state.account_id, self.state.generation, self.state.character
                ),
                self.state.body,
                prepare_duel=prepare_duel,
                prewarm_duel=prepare_terrain,
            )
            if self.state.result.get("accepted"):
                self.adopt_shared_duel()
                self.drain_shared_combat()
                self.checkpoint_fight()
                self.runtime.record(
                    event="friendly_duel_accepted",
                    actor_id=self.state.character["id"],
                    fight_id=self.state.result["fight_id"],
                )
            else:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.result["packet"],
                )
                if self.state.result.get("notify_character_id") is not None:
                    self.runtime.WORLD.send_to(
                        self.state.result["notify_character_id"],
                        self.state.result["notify_generation"],
                        *self.state.result["packet"],
                    )
                self.runtime.record(
                    event="friendly_duel_declined_or_stale",
                    actor_id=self.state.character["id"],
                    fight_id=self.state.result.get("fight_id"),
                )
        except ValueError as error:
            self.runtime.record(
                event="friendly_duel_answer_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection, self.state.service, *self.state.cancellation(6)
            )
        return DispatchResult.FALLTHROUGH

    def handle_fight_join(self):
        from wakfu_server.combat_multiplayer_wire import decode_join

        try:
            if (
                self.state.fight is not None
                or self.state.combat_session is not None
                or self.state.bag_session is not None
            ):
                raise ValueError("Already in a fight or inventory session")
            self.state.request = decode_join(self.state.body)
            self.state.fight_id = (
                self.runtime.COMBAT_SESSIONS.registry.resolve_join_target(
                    self.state.request["target_id"]
                )
            )
            self.state.shared = self.runtime.COMBAT_SESSIONS.registry.lookup(
                self.state.fight_id
            )
            self.state.context = self.state.shared.join_context
            if not isinstance(self.state.context, dict):
                raise ValueError("Placement bootstrap context is unavailable")
            self.state.target = self.state.shared.fight.actors.get(
                self.state.request["target_id"]
            )
            if self.state.target is None:
                raise ValueError("Join target disappeared")
            candidate_session = self.runtime.COMBAT_SESSIONS.session(
                self.state.account_id, self.state.generation, self.state.character
            )
            joined_actor = self.runtime.COMBAT_SESSIONS.player_actor(
                candidate_session, team=self.state.target.team
            )
            self.state.shared = self.runtime.COMBAT_SESSIONS.join(
                candidate_session,
                self.state.body,
                joined_actor,
                expected_fight_id=self.state.fight_id,
                native_publication=(
                    self.state.connection.instance_publications,
                    self.state.connection.native_instance_scope(),
                ),
            )
            from wakfu_server.objectives.environmental_gameplay import (
                remember_admission,
            )

            remember_admission(
                self.state.shared, self.state.account_id, self.state.character
            )
            self.state.combat_session = candidate_session
            self.state.fight = self.state.shared.fight
            self.state.fight_messages = self.state.shared.runtime
            self.state.group_lease = getattr(self.state.shared, "group_lease", None)
            self.state.TEST_MONSTERS_BY_ID = self.state.context["monsters"]
            self.state.TEST_MONSTERS = tuple(self.state.TEST_MONSTERS_BY_ID.values())
            self.state.TEST_GROUP_KEY = self.state.context["group_key"]
            self.state.fight_started_at = self.state.context["fight_started_at"]
            self.state.placement_deadline.start(
                self.state.fight.id,
                self.state.context["duration_ms"],
                self.state.fight_started_at,
                native=self.state.is_owned_guardian_fight(
                    self.state.fight, self.state.character["id"]
                ),
            )
            self.checkpoint_fight()
            self.drain_shared_combat()
            self.runtime.record(
                event="combat_test_joined",
                actor_id=self.state.character["id"],
                fight_id=self.state.fight.id,
                target_id=self.state.request["target_id"],
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_test_join_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"), str(error)
                ),
            )
        return DispatchResult.FALLTHROUGH

    def handle_spectator_join(self):
        from wakfu_server.combat_spectator_wire import (
            decode_spectator_request,
        )

        self.state.decode_spectator_request = decode_spectator_request

        try:
            if self.state.fight is not None or self.state.combat_session is not None:
                raise ValueError("Combat participants cannot observe another fight")
            if self.state.bag_session is not None:
                raise ValueError("Close the inventory session first")
            self.runtime.flush_positions(
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
            )
            self.state.character = self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"]
            )
            self.state.fight_id = self.state.decode_spectator_request(self.state.body)
            self.state.shared = self.runtime.COMBAT_SESSIONS.registry.lookup(
                self.state.fight_id
            )
            self.state.observer = self.spectator_session_for_current_character()
            if (self.state.observer.map_id, self.state.observer.instance_id) != (
                self.state.shared.map_id,
                self.state.shared.instance_id,
            ):
                raise ValueError("Fight is outside this map instance")
            if self.spectator_waiting_for_ack(self.state.shared):
                self.runtime.SPECTATORS.defer_enter(
                    self.state.observer,
                    self.state.fight_id,
                    authorize=lambda _session, _fight_id: True,
                )
                self.state.spectator_session = self.state.observer
                self.state.spectator_fight_id = self.state.fight_id
                # Close the check/register race: if the last ACK
                # arrived just before defer_enter, this publishes
                # the current snapshot and materializes the request.
                self.publish_spectator_state(self.state.shared, force_snapshot=True)
                self.runtime.record(
                    event="combat_spectator_entry_deferred",
                    actor_id=self.state.character["id"],
                    fight_id=self.state.fight_id,
                    revision=self.state.shared.sequence,
                )
                return DispatchResult.CONTINUE
            if (
                self.state.shared.fight.phase == "active"
                and getattr(self.state.shared.runtime, "turn_deadline", None) is None
            ):
                raise ValueError("Fight has no current native action deadline")
            # Keep refresh and subscription atomic against an owner
            # action invalidating an otherwise unobserved snapshot.
            with self.state.shared.lock:
                self.publish_spectator_state(self.state.shared, force_snapshot=True)
                self.state.delivery = self.runtime.SPECTATORS.enter(
                    self.state.observer,
                    self.state.fight_id,
                    authorize=lambda _session, _fight_id: True,
                )
            self.state.spectator_session = self.state.observer
            self.state.spectator_fight_id = self.state.fight_id
            for (
                self.state.message_id,
                self.state.message_body,
            ) in self.state.delivery.packets:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            self.runtime.record(
                event="combat_spectator_entered",
                actor_id=self.state.character["id"],
                fight_id=self.state.fight_id,
                revision=self.state.delivery.revision,
            )
        except (KeyError, ValueError) as error:
            self.runtime.record(
                event="combat_spectator_entry_rejected",
                actor_id=(
                    None if self.state.character is None else self.state.character["id"]
                ),
                reason=str(error),
            )
            if self.state.character is not None:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"), str(error)
                    ),
                )
        return DispatchResult.FALLTHROUGH

    def handle_spectator_leave(self):
        from wakfu_server.combat_spectator_wire import (
            decode_spectator_request,
        )

        self.state.decode_spectator_request = decode_spectator_request

        try:
            # Native bvU clears spectator mode and restores the
            # world before sending cpg/12154; this is a no-ACK
            # server cleanup notification, not a new world bootstrap.
            self.state.fight_id = self.state.decode_spectator_request(self.state.body)
            self.state.observer = self.spectator_session_for_current_character()
            left = self.runtime.SPECTATORS.leave(
                self.state.observer, self.state.fight_id
            )
            self.state.spectator_session = None
            self.state.spectator_fight_id = None
            terminal_return = False
            if (
                self.state.spectator_terminal_pending is not None
                and self.state.spectator_terminal_pending.fight_id
                == self.state.fight_id
            ):
                if self.state.spectator_terminal_pending.session != self.state.observer:
                    raise ValueError(
                        "Spectator terminal return belongs to another lease"
                    )
                terminal_return = True
                self.state.spectator_terminal_pending = None
            if left or terminal_return:
                self.refresh_owned_world_after_spectating()
            self.runtime.record(
                event="combat_spectator_left",
                actor_id=self.state.character["id"],
                fight_id=self.state.fight_id,
                world_refreshed=left or terminal_return,
            )
        except (KeyError, ValueError) as error:
            self.runtime.record(
                event="combat_spectator_leave_rejected",
                actor_id=(
                    None if self.state.character is None else self.state.character["id"]
                ),
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_encounter_start(self):
        if (
            self.state.rift_start_run is False
            or self.state.encounter_world_action is False
        ):
            return DispatchResult.CONTINUE
        self.runtime.PLANTINGS.cancel(self.state.character["id"], self.state.generation)
        self.runtime.HARVESTS.cancel(
            self.state.character["id"], generation=self.state.generation
        )
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_terrain import local_arena

        if self.state.encounter_world_action is not None:
            self.state.target = self.state.encounter_world_action["target_id"]
            (
                self.state.x,
                self.state.y,
                self.state.z,
            ) = self.state.encounter_world_action["position"]
            auto_lock = 0
        elif self.state.rift_start_run is None:
            (
                self.state.target,
                self.state.x,
                self.state.y,
                self.state.z,
                auto_lock,
            ) = struct.unpack(">qiihB", self.state.body)
        else:
            self.state.target = self.state.x = self.state.y = self.state.z = (
                auto_lock
            ) = None
        if (
            self.state.fight is not None
            or (self.state.bag_session is not None and self.state.ranch_session is None)
            or (
                self.state.ranch_session is not None
                and not self.state.ranch_session.owns(self.state.character)
            )
            or self.state.spectator_session is not None
        ):
            self.runtime.record(
                event="combat_test_attack_rejected",
                actor_id=self.state.character["id"],
                reason="Fight or inventory session is already active",
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    "No puedes iniciar otro combate con una sesión de combate o inventario activa.",
                ),
            )
            return DispatchResult.CONTINUE
        self.state.durable_fight_id = None
        self.state.entry_stage_started = time.monotonic()
        self.state.entry_stage_cpu = time.thread_time()

        def entry_stage(stage):
            now, cpu = time.monotonic(), time.thread_time()
            self.runtime.record(
                event="combat_entry_stage",
                stage=stage,
                fight_id=self.state.durable_fight_id,
                map_id=self.state.character["map_id"],
                elapsed_ms=round((now - self.state.entry_stage_started) * 1000, 3),
                thread_cpu_ms=round((cpu - self.state.entry_stage_cpu) * 1000, 3),
            )
            self.state.entry_stage_started, self.state.entry_stage_cpu = now, cpu

        try:
            if self.state.rift_start_run is None:
                with self.runtime.COMBAT_GROUPS.lock:
                    self.state.selected_group = self.runtime.combat_group_for_target(
                        self.runtime.COMBAT_GROUPS,
                        self.state.character,
                        self.state.target,
                    )
            else:
                from wakfu_server.rift_dispatch_lifecycle import (
                    initial_members,
                )
                from wakfu_server.combat_terrain import map_geometry

                self.state.map_geometry = map_geometry

                with self.runtime.STORE.connection() as rift_db:
                    self.state.members = initial_members(
                        rift_db,
                        self.state.rift_start_run,
                        self.state.map_geometry(self.state.character["map_id"]),
                        (
                            self.state.character["x"],
                            self.state.character["y"],
                            self.state.character["z"],
                        ),
                    )
                self.state.selected_group = {
                    "key": (
                        self.state.character["map_id"],
                        self.state.character["instance_id"],
                        self.state.rift_start_run["instance_id"],
                    ),
                    "members": self.state.members,
                }
            self.state.TEST_GROUP_KEY = self.state.selected_group["key"]
            self.state.TEST_MONSTERS = tuple(self.state.selected_group["members"])
            rii_orientation_owned = False
            rii_lesson_objective = None
            rii_guardian_owned = None
            world_scene_owner = None
            if self.state.character["map_id"] == 1388:
                from wakfu_server.achievements import (
                    rii_orientation,
                    rii_element_encounter,
                    rii_owned_lesson,
                    rii_free_practice,
                )

                self.state.rii_orientation = rii_orientation
                self.state.rii_element_encounter = rii_element_encounter
                self.state.rii_owned_lesson = rii_owned_lesson
                self.state.rii_free_practice = rii_free_practice

                with self.runtime.STORE.connection() as self.state.lesson_db:
                    from wakfu_server.achievements import rii_lesson_layout
                    from wakfu_server.achievements.rii_lesson_visibility import (
                        group_owners,
                    )

                    world_scene_owner = group_owners(
                        self.state.lesson_db, [self.state.selected_group]
                    ).get(self.state.TEST_GROUP_KEY)
                    rii_lesson_objective = rii_lesson_layout.identify(
                        self.state.lesson_db,
                        self.state.character,
                        self.state.TEST_MONSTERS,
                    )
                    self.state.rii_free_practice.admit(
                        self.state.lesson_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    self.state.rii_orientation.admit(
                        self.state.lesson_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    rii_orientation_owned = (
                        len(self.state.TEST_MONSTERS) == 1
                        and self.state.rii_orientation.owned_target(
                            self.state.lesson_db,
                            self.state.character["id"],
                            self.state.TEST_MONSTERS,
                        )
                        is not None
                    )
                    self.state.rii_element_encounter.admit(
                        self.state.lesson_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    self.state.rii_owned_lesson.admit(
                        self.state.lesson_db,
                        self.state.rii_owned_lesson.DISTANCE,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    from wakfu_server.achievements import rii_area_encounter

                    self.state.rii_area_encounter = rii_area_encounter

                    self.state.rii_area_encounter.admit(
                        self.state.lesson_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    from wakfu_server.achievements import rii_los_encounter

                    self.state.rii_los_encounter = rii_los_encounter

                    self.state.rii_los_encounter.admit(
                        self.state.lesson_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    self.state.rii_owned_lesson.admit(
                        self.state.lesson_db,
                        self.state.rii_owned_lesson.MOVEMENT,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    self.state.rii_owned_lesson.admit(
                        self.state.lesson_db,
                        self.state.rii_owned_lesson.STATES,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
            if self.state.character["map_id"] == 1387:
                from wakfu_server.achievements import (
                    rii_guardian_battle,
                    rii_guardian_contract,
                )

                self.state.rii_guardian_battle = rii_guardian_battle

                with self.runtime.STORE.connection() as self.state.guardian_db:
                    self.state.rii_guardian_battle.admit(
                        self.state.guardian_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    rii_guardian_owned = rii_guardian_contract.identify(
                        self.state.guardian_db,
                        self.state.character,
                        self.state.TEST_MONSTERS,
                    )
                    if rii_guardian_owned is not None:
                        world_scene_owner = self.state.character["id"]
            scene_helper_manifest = None
            if self.state.rift_start_run is None:
                from wakfu_server.combat_encounter_scene_helpers import (
                    prepare_scene_roster,
                )

                mission_helper_options = {}
                if self.state.character.get(
                    "map_id"
                ) == 312 and self.runtime.is_dungeon_run(
                    self.state.character.get("instance_id", 0)
                ):
                    from wakfu_server.achievements.astrub_cat_story import (
                        combat_helper_admission,
                    )

                    mission_allies = combat_helper_admission(
                        self.runtime.STORE,
                        self.state.character,
                        self.state.TEST_MONSTERS,
                    )
                    if mission_allies is not None:
                        mission_helper_options["mission_allies"] = mission_allies
                self.state.TEST_MONSTERS, scene_helper_manifest = prepare_scene_roster(
                    self.runtime.STORE,
                    self.state.character,
                    self.state.TEST_MONSTERS,
                    **mission_helper_options,
                )
            from wakfu_server.combat_operational_admission import (
                require_operational_encounter,
            )

            try:
                require_operational_encounter(self.state.TEST_MONSTERS)
            except ValueError as error:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"),
                        str(error),
                    ),
                )
                return DispatchResult.CONTINUE
            self.state.TEST_MONSTERS_BY_ID = {
                m["id"]: m for m in self.state.TEST_MONSTERS
            }
            entry_stage("group_selected")
            from wakfu_server.combat_arena_policy import (
                cell_budget,
                size_range,
            )

            with self.runtime.STORE.connection() as arena_policy_db:
                arena_cell_budget = cell_budget(arena_policy_db)
                arena_size_range = size_range(arena_policy_db)
                arena_room_cells = None
                arena_room_scene = None
                arena_room_obstacles = ()
                if (
                    self.state.rift_start_run is None
                    and self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                    and self.runtime.is_dungeon_run(
                        self.state.character.get("instance_id", 0)
                    )
                ):
                    from wakfu_server.dungeon_runtime import (
                        combat_room_cells,
                        combat_room_scene,
                    )

                    arena_room_cells = combat_room_cells(
                        arena_policy_db,
                        self.state.TEST_GROUP_KEY,
                        (
                            self.state.character["x"],
                            self.state.character["y"],
                            self.state.character["z"],
                        ),
                        [(m["x"], m["y"], m["z"]) for m in self.state.TEST_MONSTERS],
                    )
                    arena_room_scene = combat_room_scene(
                        arena_policy_db, self.state.TEST_GROUP_KEY
                    )
                    if arena_room_scene is not None:
                        arena_room_cells = arena_room_scene["room_cells"]
                        from wakfu_server.combat_encounter_glyph_bootstrap import (
                            declared_environment_blockers,
                        )

                        arena_room_obstacles = declared_environment_blockers(
                            arena_room_scene["descriptor"].get(
                                "native_initial_glyphs", ()
                            )
                        )
                        from wakfu_server.combat_encounter_scene_policy import (
                            declared_spawn_cells,
                        )

                        arena_room_obstacles = (
                            arena_room_obstacles
                            | declared_spawn_cells(arena_room_scene["descriptor"])
                        )
            from wakfu_server.combat_actor_snapshot import (
                native_actor_catalog,
            )

            self.state.formation_catalog = native_actor_catalog()
            from wakfu_server.combat_fixed_actor_placement import (
                member_positions,
            )

            fixed_actor_positions = (
                {}
                if arena_room_scene is None
                else member_positions(
                    arena_room_scene["descriptor"],
                    self.state.TEST_MONSTERS,
                    room_cells=arena_room_scene["room_cells"],
                )
            )
            tutorial_arena = None
            if self.state.character["map_id"] == 1361:
                from wakfu_server.achievements import incarnam_encounters

                self.state.incarnam_encounters = incarnam_encounters
                from wakfu_server.combat_terrain import map_geometry

                self.state.map_geometry = map_geometry

                with self.runtime.STORE.connection() as self.state.tutorial_db:
                    tutorial_arena = self.state.incarnam_encounters.arena_policy(
                        self.state.tutorial_db,
                        self.state.character,
                        self.state.TEST_MONSTERS,
                        self.state.map_geometry(1361),
                    )
            self.state.arena = (
                rii_guardian_contract.arena(
                    self.state.character,
                    self.state.TEST_MONSTERS,
                    rii_guardian_owned,
                    cell_budget=arena_cell_budget,
                    size_range=arena_size_range,
                )
                if rii_guardian_owned is not None
                else local_arena(
                    self.state.character["map_id"],
                    self.state.character["id"],
                    (
                        self.state.character["x"],
                        self.state.character["y"],
                        self.state.character["z"],
                    ),
                    [(m["x"], m["y"], m["z"]) for m in self.state.TEST_MONSTERS],
                    automatic_cell_budget=arena_cell_budget,
                    size_range=arena_size_range,
                    allowed_cells=(
                        tutorial_arena["allowed_cells"]
                        if tutorial_arena
                        else arena_room_cells
                    ),
                    relocate_monsters=(
                        tutorial_arena["relocate_monsters"]
                        if tutorial_arena
                        else not rii_orientation_owned
                    ),
                    full_room_scope=(
                        arena_room_scene is not None
                        and arena_room_scene["descriptor"]["full_room_scope"]
                    ),
                    initial_obstacle_cells=arena_room_obstacles,
                    fixed_member_positions=fixed_actor_positions,
                    ordinary_npc_placement=(
                        tutorial_arena["ordinary_npc_placement"]
                        if tutorial_arena
                        else True
                    ),
                    member_radii=tuple(
                        self.state.formation_catalog["npc_profiles"][str(m["ref"])][
                            "physical_radius"
                        ]
                        for m in self.state.TEST_MONSTERS
                    ),
                    player_radius=self.state.formation_catalog["default_actor_radius"],
                    stage_callback=lambda stage, elapsed_ms, thread_cpu_ms: self.runtime.record(
                        event="combat_arena_stage",
                        stage=stage,
                        map_id=self.state.character["map_id"],
                        elapsed_ms=round(elapsed_ms, 3),
                        thread_cpu_ms=round(thread_cpu_ms, 3),
                    ),
                )
            )
            if rii_lesson_objective is not None:
                self.state.arena = rii_lesson_layout.arena(
                    self.state.character,
                    self.state.TEST_MONSTERS,
                    rii_lesson_objective,
                    cell_budget=arena_cell_budget,
                    size_range=arena_size_range,
                )
            from wakfu_server.combat_encounter_scene_layout import (
                prepare_encounter_scene,
            )

            if scene_helper_manifest is not None:
                from wakfu_server.combat_encounter_scene_helpers import (
                    adapt_helper_placement,
                )

                self.state.arena["native_encounter_scene_helpers"] = (
                    scene_helper_manifest
                )
                self.state.arena = adapt_helper_placement(
                    self.state.character, self.state.TEST_MONSTERS, self.state.arena
                )

            if self.state.rift_start_run is not None:
                from wakfu_server.rift_encounter_roles import (
                    prepare_rift_arena,
                )

                self.state.arena = prepare_rift_arena(
                    self.state.character,
                    self.state.TEST_MONSTERS,
                    self.state.arena,
                    self.state.rift_start_run["catalog"],
                    self.state.rift_start_run["policy"],
                )
            self.state.arena = prepare_encounter_scene(
                self.state.character, self.state.TEST_MONSTERS, self.state.arena
            )
            if arena_room_scene is not None:
                from wakfu_server.combat_encounter_scene_policy import (
                    arena_scene,
                )

                self.state.arena = arena_scene(
                    arena_room_scene,
                    self.state.arena,
                    self.state.character,
                    self.state.TEST_MONSTERS,
                )
            entry_stage("arena_selected")
            from wakfu_server import territory_bonuses

            with self.runtime.STORE.connection() as territory_db:
                self.state.character = territory_bonuses.reconcile_owned(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    db=territory_db,
                )
                self.state.character = territory_bonuses.attach_character(
                    territory_db, self.state.character
                )
            from wakfu_server.equipment_stats import combat_resources

            resources = combat_resources(
                self.state.character, wp=self.runtime.COMBAT_TEST_WP
            )
            entry_stage("resources_built")
            from wakfu_server.fight_store import (
                create as create_fight_identity,
            )

            from wakfu_server.placement_deadline import duration

            placement_duration = (
                rii_guardian_contract.PLACEMENT_DURATION_MS
                if rii_guardian_owned is not None
                else duration(self.runtime.STORE)
            )
            terrain_instance_id = secrets.randbelow(2**60) + 1
            self.state.dungeon_binding = None
            if (
                self.state.rift_start_run is None
                and self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                and self.runtime.is_dungeon_run(
                    self.state.character.get("instance_id", 0)
                )
            ):
                from wakfu_server.dungeon_fight_binding import (
                    bind_room_group,
                )

                self.state.bind_room_group = bind_room_group

                def dungeon_binding(db, fight_id):
                    from wakfu_server.dungeon_difficulty import (
                        encounter_scaling,
                    )

                    profile = encounter_scaling(db, self.state.character["instance_id"])
                    return self.state.bind_room_group(
                        db,
                        self.state.TEST_GROUP_KEY,
                        self.state.character["id"],
                        fight_id,
                        player_team=(
                            0
                            if self.state.arena.get("native_encounter_roles") is None
                            else self.state.arena["native_encounter_roles"][
                                "player_team"
                            ]
                        ),
                        expected_selection_revision=(
                            None if profile is None else profile["selection_revision"]
                        ),
                    )

                self.state.dungeon_binding = dungeon_binding

            self.state.entry_boundary = {}

            def capture_entry_boundary(db, identity):
                from types import SimpleNamespace
                from wakfu_server.neo_regeneration import (
                    freeze_fight_configuration,
                )

                if self.state.dungeon_binding is not None:
                    self.state.dungeon_binding(db, identity)
                    from wakfu_server.dungeon_optional_votes import (
                        freeze_challenge,
                        scene_enabled,
                    )

                    if scene_enabled(self.state.character["map_id"]):
                        self.state.entry_boundary["optional_ballot_challenge"] = (
                            freeze_challenge(db, identity)
                        )
                self.state.entry_boundary["health"] = db.execute(
                    "SELECT id,account_id,hp,max_hp,hp_damage,health_dead,hp_zero_valid "
                    "FROM characters WHERE id=%s AND account_id=%s",
                    (self.state.character["id"], self.state.account_id),
                ).fetchone()
                configuration = SimpleNamespace()
                freeze_fight_configuration(db, configuration)
                self.state.entry_boundary["configuration"] = (
                    configuration.native_system_configuration
                )
                from wakfu_server.combat_protector_fight_condition import (
                    capture_world_registry_record,
                )

                self.state.entry_boundary["protector_registry"] = (
                    capture_world_registry_record(db, self.state.character, identity)
                )

            from wakfu_server.combat_encounter_roles import (
                assigned_roles,
                roles_from_record,
            )

            entry_role_record = self.state.arena.get("native_encounter_roles")
            entry_roles = (
                assigned_roles(None)
                if entry_role_record is None
                else roles_from_record(
                    entry_role_record,
                    map_id=self.state.arena["map_id"],
                    monster_references=[m["ref"] for m in self.state.TEST_MONSTERS],
                )
            )
            optional_owner_preflight = None
            from wakfu_server import (
                dungeon_optional_ground_items,
                dungeon_optional_votes,
            )

            self.state.dungeon_optional_ground_items = dungeon_optional_ground_items

            if self.state.dungeon_binding is not None:
                from wakfu_server import (
                    dungeon_optional_encounters,
                    dungeon_postboss_nodes,
                )

                self.state.dungeon_optional_encounters = dungeon_optional_encounters
                self.state.dungeon_postboss_nodes = dungeon_postboss_nodes

                def optional_owner_preflight(db):
                    from psycopg.errors import LockNotAvailable

                    try:
                        # A first-fight bind must not own the account
                        # while waiting for a stair choice's run lock.
                        db.execute(
                            "SELECT instance_id FROM dungeon_room_runs "
                            "WHERE instance_id=%s FOR UPDATE NOWAIT",
                            (self.state.TEST_GROUP_KEY[1],),
                        ).fetchone()
                        from wakfu_server.dungeon_entry_paths import (
                            prelock_combat_owner_nowait,
                        )

                        prelock_combat_owner_nowait(
                            db,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            self.runtime.STORE.now(),
                        )
                        self.state.dungeon_postboss_nodes.lock_group_run(
                            db, self.state.TEST_GROUP_KEY
                        )
                        self.state.dungeon_optional_encounters.lock_group_run(
                            db, self.state.TEST_GROUP_KEY
                        )
                    except LockNotAvailable as error:
                        raise ValueError(
                            "Dungeon encounter is busy; retry selection"
                        ) from error

            self.state.durable_fight_id = create_fight_identity(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                team=entry_roles.player_team,
                on_created=capture_entry_boundary,
                before_owner_lock=optional_owner_preflight,
            )
            from wakfu_server.neo_regeneration import (
                project_entry_character,
            )

            self.state.character = project_entry_character(
                self.state.character, self.state.entry_boundary["health"]
            )
            from wakfu_server.combat_placement_policy import (
                freeze as freeze_placement,
            )

            self.state.arena = freeze_placement(
                self.runtime.STORE,
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
                fight_id=self.state.durable_fight_id,
                map_id=self.state.character["map_id"],
                instance_id=self.state.character["instance_id"],
                selected_arena=self.state.arena,
                seeds={
                    0: [
                        (
                            self.state.character["x"],
                            self.state.character["y"],
                            self.state.character["z"],
                        )
                    ],
                    1: [(m["x"], m["y"], m["z"]) for m in self.state.TEST_MONSTERS],
                },
            )
            entry_stage("durable_placement_frozen")
            self.state.candidate, self.state.packets = create_placement(
                self.state.character,
                self.state.TEST_MONSTERS,
                self.state.arena,
                fight_id=self.state.durable_fight_id,
                player_ap=resources["ap"],
                player_mp=resources["mp"],
                player_wp=resources["wp"],
                player_initiative=resources["initiative"],
                terrain_effect_id=self.state.arena["terrain_effect_id"],
                terrain_instance_id=terrain_instance_id,
                duration_ms=placement_duration,
            )
            if rii_guardian_owned is not None:
                rii_guardian_contract.bind(self.state.candidate, rii_guardian_owned)
            if self.state.character["map_id"] == 1388:
                from wakfu_server.achievements import (
                    rii_orientation,
                    rii_element_encounter,
                    rii_owned_lesson,
                )

                self.state.rii_orientation = rii_orientation
                self.state.rii_element_encounter = rii_element_encounter
                self.state.rii_owned_lesson = rii_owned_lesson

                with self.runtime.STORE.connection() as self.state.lesson_db:
                    self.state.rii_orientation.bind(
                        self.state.lesson_db,
                        self.state.candidate,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    self.state.rii_element_encounter.bind(
                        self.state.lesson_db,
                        self.state.candidate,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    distance_contract = self.state.rii_owned_lesson.bind(
                        self.state.lesson_db,
                        self.state.rii_owned_lesson.DISTANCE,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    if distance_contract is not None:
                        self.state.candidate.rii_distance_lesson_contract = (
                            distance_contract
                        )
                    from wakfu_server.achievements import rii_area_encounter

                    self.state.rii_area_encounter = rii_area_encounter

                    area_contract = self.state.rii_area_encounter.bind(
                        self.state.lesson_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    if area_contract is not None:
                        self.state.candidate.rii_area_lesson_contract = area_contract
                    from wakfu_server.achievements import rii_los_encounter

                    self.state.rii_los_encounter = rii_los_encounter

                    los_contract = self.state.rii_los_encounter.bind(
                        self.state.lesson_db,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    if los_contract is not None:
                        self.state.candidate.rii_los_lesson_contract = los_contract
                    movement_contract = self.state.rii_owned_lesson.bind(
                        self.state.lesson_db,
                        self.state.rii_owned_lesson.MOVEMENT,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    if movement_contract is not None:
                        self.state.candidate.rii_movement_lesson_contract = (
                            movement_contract
                        )
                    states_contract = self.state.rii_owned_lesson.bind(
                        self.state.lesson_db,
                        self.state.rii_owned_lesson.STATES,
                        self.state.character["id"],
                        self.state.TEST_MONSTERS,
                    )
                    if states_contract is not None:
                        self.state.candidate.rii_states_lesson_contract = (
                            states_contract
                        )
            self.state.candidate.native_system_configuration = (
                self.state.entry_boundary["configuration"]
            )
            self.state.candidate.native_protector_registry = self.state.entry_boundary[
                "protector_registry"
            ]
            with self.state.connection.write_lock:
                self.state.connection.instance_publications.bind_encounter(
                    self.state.candidate,
                    self.state.connection.native_instance_scope(),
                    npc_ids=tuple(m["id"] for m in self.state.TEST_MONSTERS),
                    player_id=self.state.character["id"],
                )
            entry_stage("placement_created")
            from wakfu_server.combat_actor_snapshot import (
                initialize_fight_snapshots,
            )

            from wakfu_server.combat_encounter_scene_policy import (
                bind_scene,
                scene_state_declarations,
            )

            bind_scene(
                self.state.candidate, self.state.arena, self.state.TEST_MONSTERS_BY_ID
            )
            initialization_warnings = []
            initialize_fight_snapshots(
                self.state.candidate,
                characters={self.state.character["id"]: self.state.character},
                monsters=self.state.TEST_MONSTERS_BY_ID,
                wp_resources={
                    self.state.character["id"]: (resources["wp"], resources["wp"]),
                    **{
                        m["id"]: (m["wp"], m.get("max_wp", m["wp"]))
                        for m in self.state.TEST_MONSTERS
                    },
                },
                running_effects={
                    identity: () for identity in self.state.candidate.actors
                },
                initial_effect_uid=1,
                dev_skip_unsupported=os.environ.get(
                    "WAKFU_DEV_SKIP_UNSUPPORTED_INITIALIZATION", "0"
                )
                == "1",
                initialization_warnings=initialization_warnings,
                scene_state_declarations=scene_state_declarations(
                    self.state.candidate, self.state.TEST_MONSTERS_BY_ID
                ),
            )
            if self.state.entry_boundary.get("optional_ballot_challenge") is not None:
                self.state.candidate.native_optional_ballot_challenge = (
                    self.state.entry_boundary["optional_ballot_challenge"]
                )
            entry_stage("actor_snapshots_initialized")
            if scene_helper_manifest is not None:
                from wakfu_server.combat_encounter_objective_spirit import (
                    authorize_spirit_scene,
                )

                with self.runtime.STORE.connection() as scene_db:
                    authorize_spirit_scene(
                        self.runtime.STORE,
                        scene_db,
                        self.state.candidate,
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                        monster_references=tuple(
                            monster["ref"] for monster in self.state.TEST_MONSTERS
                        ),
                    )
            if tuple(m["ref"] for m in self.state.TEST_MONSTERS) == (1723,):
                from wakfu_server.combat_aguabrial_scene import (
                    authorize_aguabrial_scene,
                )

                with self.runtime.STORE.connection() as scene_db:
                    authorize_aguabrial_scene(
                        self.runtime.STORE,
                        scene_db,
                        self.state.candidate,
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                        monster_references=(1723,),
                    )
            if tuple(m["ref"] for m in self.state.TEST_MONSTERS) == (2880,):
                from wakfu_server.combat_abomination_scene import (
                    authorize_admission as authorize_abomination_scene,
                )

                with self.runtime.STORE.connection() as scene_db:
                    authorize_abomination_scene(
                        self.runtime.STORE,
                        scene_db,
                        self.state.candidate,
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                        monster_references=(2880,),
                    )
            if self.state.dungeon_binding is not None:
                from wakfu_server.dungeon_scaling_entry import (
                    initialize as initialize_dungeon_scaling,
                )

                with self.runtime.STORE.connection() as scaling_db:
                    self.state.candidate, scaling_receipt = initialize_dungeon_scaling(
                        scaling_db, self.state.candidate, self.state.TEST_MONSTERS_BY_ID
                    )
                entry_stage("dungeon_scaling_initialized")
            from wakfu_server.combat_forced_terrain import prewarm_map

            warm_started = time.monotonic()
            warm_thread_cpu = time.thread_time()
            warm_process_cpu = time.process_time()
            forced_terrain_loaded = prewarm_map(self.state.character["map_id"])
            self.runtime.record(
                event="combat_forced_terrain_ready",
                fight_id=self.state.candidate.id,
                map_id=self.state.character["map_id"],
                available=forced_terrain_loaded,
                thread_cpu_ms=round((time.thread_time() - warm_thread_cpu) * 1000, 3),
                process_cpu_ms=round(
                    (time.process_time() - warm_process_cpu) * 1000, 3
                ),
                elapsed_ms=round((time.monotonic() - warm_started) * 1000, 3),
            )
            # Placement serializers publish each actor's initialized facing.
            # Preserve it: resetting controlled actors to EAST also makes
            # inherited summon appearances request unavailable 0_ clips.
            from wakfu_server.combat_monster_world import remove_message

            self.state.remove_message = remove_message

            if self.state.rift_start_run is None:
                with self.runtime.COMBAT_GROUPS.lock:
                    (
                        self.state.group_lease,
                        self.state.members,
                    ) = self.runtime.COMBAT_GROUPS.claim(
                        self.state.TEST_GROUP_KEY,
                        self.state.generation,
                        self.state.candidate.id,
                    )
                    from wakfu_server.item_test_spawns import (
                        is_fight as is_developer_test_fight,
                    )

                    with self.runtime.STORE.connection() as test_group_db:
                        developer_test_encounter = is_developer_test_fight(
                            test_group_db, self.state.candidate.id
                        )
                    from wakfu_server.custom_tasks import (
                        external as objectives_mode,
                    )

                    if objectives_mode.enabled() and not developer_test_encounter:
                        from wakfu_server.objectives.challenges import (
                            bind_fight,
                        )

                        with self.runtime.STORE.connection() as challenge_db:
                            bind_fight(
                                challenge_db,
                                *self.state.TEST_GROUP_KEY,
                                self.state.candidate.id,
                            )
                    self.runtime.WORLD.emit_location(
                        self.state.TEST_GROUP_KEY[0],
                        self.state.TEST_GROUP_KEY[1],
                        *self.state.remove_message(
                            [m["id"] for m in self.state.members]
                        ),
                        exclude_generation=self.state.generation,
                    )
            else:
                self.state.group_lease = None
                from wakfu_server.rift_dispatch_lifecycle import (
                    reserve_actor_ids,
                )

                with self.runtime.STORE.connection() as rift_db:
                    reserved_ids = reserve_actor_ids(rift_db, 128)
                self.state.candidate.rift_wave_state = {
                    "instance_id": self.state.rift_start_run["instance_id"],
                    "world_group_id": self.state.candidate.id,
                    "wave": self.state.rift_start_run["wave"],
                    "turn_budget": self.state.rift_start_run["policy"]["turn_budget"],
                    "wave_actor_ids": [
                        monster["id"] for monster in self.state.TEST_MONSTERS
                    ],
                    "wave_species_refs": [
                        monster["ref"] for monster in self.state.TEST_MONSTERS
                    ],
                    "catalog": self.state.rift_start_run["catalog"],
                    "policy": self.state.rift_start_run["policy"],
                    "seed": self.state.rift_start_run["seed"],
                    "actor_id_pool": list(reserved_ids),
                }
                self.state.candidate.rift_monsters = dict(
                    self.state.TEST_MONSTERS_BY_ID
                )
            self.state.saved = self.runtime.health_store.sync(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.character["hp"],
                self.state.character["hp"],
                coefficient=0,
            )
            self.state.character.update(
                hp=self.state.saved["hp"],
                max_hp=self.state.saved["max_hp"],
                hp_damage=self.state.saved["hp_damage"],
                health_dead=self.state.saved["health_dead"],
            )
            self.state.fight_started_at = time.monotonic()
            self.state.combat_session = self.runtime.COMBAT_SESSIONS.session(
                self.state.account_id, self.state.generation, self.state.character
            )
            from wakfu_server.combat_heroes import admit_owned_heroes
            from wakfu_server.combat_bootstrap import (
                placement_messages,
                player_payload,
            )
            from wakfu_server.combat_actor import (
                monster_actor_stats,
                actor_effects,
            )

            with self.runtime.STORE.connection() as self.state.hero_db:
                if rii_guardian_owned is not None:
                    # Model71 is the captured solo story encounter;
                    # the selected company stays in exploration.
                    self.state.hero_admission = dict(
                        fight=self.state.candidate, characters={}, actors=()
                    )
                else:
                    self.state.hero_admission = admit_owned_heroes(
                        self.state.hero_db,
                        self.runtime.STORE,
                        self.state.combat_session,
                        self.state.candidate,
                        private_scene=self.state.ranch_session,
                        frozen_members=(
                            self.state.rift_start_run["members"]
                            if self.state.rift_start_run is not None
                            else None
                        ),
                    )
                self.state.candidate = self.state.hero_admission["fight"]
                from wakfu_server.combat_instance_publication import (
                    refresh_owned_encounter,
                )

                refresh_owned_encounter(self.state.candidate)
                from wakfu_server.combat_companions import (
                    admit_owned_companions,
                )

                if rii_guardian_owned is not None:
                    self.state.companion_admission = dict(
                        fight=self.state.candidate,
                        companions=(),
                        sources={},
                        actors=(),
                        packets=(),
                    )
                else:
                    self.state.companion_admission = admit_owned_companions(
                        self.state.hero_db,
                        self.runtime.STORE,
                        self.state.combat_session,
                        self.state.candidate,
                        owner_character=self.state.character,
                    )
                self.state.candidate = self.state.companion_admission["fight"]
                hero_packets = (
                    tuple(
                        (
                            12608,
                            self.runtime.wire.spawn_player(
                                self.runtime.PLAYER_TEMPLATE, source
                            ),
                        )
                        for source in self.state.hero_admission["characters"].values()
                    )
                    + self.state.companion_admission["packets"]
                )
                from wakfu_server.combat_bootstrap import (
                    should_rebuild_placement,
                )

                if should_rebuild_placement(
                    self.state.candidate,
                    (
                        *self.state.hero_admission["actors"],
                        *self.state.companion_admission["actors"],
                    ),
                ):
                    sources = {
                        self.state.character["id"]: self.state.character,
                        **self.state.hero_admission["characters"],
                    }
                    actor_payloads = {}
                    for placement_actor in self.state.candidate.actors.values():
                        wp_current, wp_maximum = self.runtime.live_wp(
                            self.state.candidate, placement_actor.id
                        )
                        if (
                            placement_actor.controlled
                            and placement_actor.id
                            not in self.state.companion_admission["sources"]
                        ):
                            actor_payloads[placement_actor.id] = player_payload(
                                sources[placement_actor.id],
                                placement_actor,
                                self.state.candidate.id,
                                wp=wp_current,
                            )
                        else:
                            self.state.source = {
                                **self.state.TEST_MONSTERS_BY_ID,
                                **self.state.companion_admission["sources"],
                            }[placement_actor.id]
                            if (
                                placement_actor.id
                                not in self.state.companion_admission["sources"]
                            ):
                                self.state.source = dict(
                                    self.state.source,
                                    **dict(
                                        zip(
                                            ("x", "y", "z"),
                                            placement_actor.position,
                                        )
                                    ),
                                )
                            if (
                                placement_actor.id
                                in self.state.companion_admission["sources"]
                                or placement_actor.id
                                in getattr(
                                    self.state.candidate,
                                    "native_npc_initialization_receipts",
                                    {},
                                )
                                or placement_actor.id
                                in getattr(
                                    self.state.candidate,
                                    "native_npc_ai_actors",
                                    frozenset(),
                                )
                                or placement_actor.id
                                in getattr(
                                    self.state.candidate,
                                    "native_dungeon_scaling_receipt",
                                    {},
                                ).get("actor_ids", ())
                            ):
                                from wakfu_server.combat_actor import (
                                    actual_monster_actor_stats,
                                )

                                wp = self.runtime.live_wp(
                                    self.state.candidate, placement_actor.id
                                )
                                stats = actual_monster_actor_stats(
                                    self.state.source,
                                    placement_actor,
                                    self.state.candidate.id,
                                    wp_current=wp[0],
                                    wp_maximum=wp[1],
                                    fight=self.state.candidate,
                                )
                            else:
                                stats = monster_actor_stats(
                                    self.state.source,
                                    self.state.candidate.id,
                                    direction=3,
                                    obstacle_id=placement_actor.native_obstacle_id,
                                    native_controlled_by_ai=(
                                        placement_actor.native_controlled_by_ai
                                    ),
                                )
                            effects = actor_effects()
                            if (
                                placement_actor.id
                                in self.state.companion_admission["sources"]
                                or placement_actor.id
                                in getattr(
                                    self.state.candidate,
                                    "native_dungeon_scaling_receipt",
                                    {},
                                ).get("actor_ids", ())
                                or (
                                    rii_guardian_owned is not None
                                    and placement_actor.id
                                    == rii_guardian_owned["target"]
                                )
                            ):
                                from wakfu_server.combat_remote_effects import (
                                    initial_npc_actor_effects,
                                )

                                effects = initial_npc_actor_effects(
                                    self.state.candidate, placement_actor.id
                                )
                            actor_payloads[placement_actor.id] = (
                                stats,
                                effects,
                            )
                    self.state.packets = placement_messages(
                        self.state.candidate,
                        self.state.arena,
                        actor_payloads,
                        kind=getattr(self.state.candidate, "native_fight_model", 2),
                        terrain_effect_id=self.state.arena["terrain_effect_id"],
                        terrain_instance_id=terrain_instance_id,
                        leaders={
                            self.state.candidate.actors[
                                self.state.character["id"]
                            ].team: self.state.character["id"],
                            self.state.candidate.actors[
                                self.state.TEST_MONSTERS[0]["id"]
                            ].team: self.state.TEST_MONSTERS[0]["id"],
                        },
                        duration_ms=placement_duration,
                        viewer_id=self.state.character["id"],
                    )
            from wakfu_server.objectives.environmental_gameplay import (
                admission_origin,
            )

            self.runtime.COMBAT_SESSIONS.register(
                self.state.combat_session,
                self.state.candidate,
                runtime=None,
                group_lease=self.state.group_lease,
                join_context={
                    **(
                        {
                            "rift_accepted_action": self.checkpoint_accepted_rift,
                            "rift_checkpoint_action": self.checkpoint_final_rift,
                        }
                        if self.state.rift_start_run is not None
                        else {}
                    ),
                    "arena": self.state.arena,
                    "terrain_effect_id": self.state.arena["terrain_effect_id"],
                    "terrain_instance_id": terrain_instance_id,
                    "leaders": {
                        self.state.candidate.actors[
                            self.state.character["id"]
                        ].team: self.state.character["id"],
                        self.state.candidate.actors[
                            self.state.TEST_MONSTERS[0]["id"]
                        ].team: self.state.TEST_MONSTERS[0]["id"],
                    },
                    "duration_ms": placement_duration,
                    "hero_appearance": lambda source: (
                        12608,
                        self.runtime.wire.spawn_player(
                            self.runtime.PLAYER_TEMPLATE, source
                        ),
                    ),
                    "frozen_company_members": (
                        self.state.rift_start_run["members"]
                        if self.state.rift_start_run is not None
                        else None
                    ),
                    "monsters": self.state.TEST_MONSTERS_BY_ID,
                    "group_key": self.state.TEST_GROUP_KEY,
                    "world_scene_owner": world_scene_owner,
                    "fight_started_at": self.state.fight_started_at,
                    "world_marker_cells": (
                        (self.state.character["x"], self.state.character["y"]),
                    ),
                    "environmental_admission_origins": {
                        self.state.account_id: admission_origin(self.state.character),
                    },
                    "world_marker_origin": (
                        self.state.character["x"],
                        self.state.character["y"],
                        self.state.character["z"],
                    ),
                },
            )
            if self.state.rift_start_run is not None:
                from wakfu_server import rift_runtime
                from wakfu_server.combat_monster_world import spawn_group

                self.state.shared_rift = self.runtime.COMBAT_SESSIONS.registry.lookup(
                    self.state.candidate.id
                )
                with self.state.shared_rift.lock, self.runtime.COMBAT_SESSIONS.registry.lock:
                    if (
                        self.runtime.COMBAT_SESSIONS.registry.fights.get(
                            self.state.candidate.id
                        )
                        is not self.state.shared_rift
                    ):
                        raise ValueError(
                            "Rift company registration changed before assembly"
                        )
                    with self.runtime.STORE.connection() as rift_db:
                        from wakfu_server.combat_heroes import (
                            frozen_main_sessions,
                        )

                        party_rows = frozen_main_sessions(
                            rift_db,
                            self.runtime.STORE,
                            self.state.rift_start_run["members"],
                        )
                    for self.state.member in party_rows:
                        if self.state.member["id"] == self.state.character["id"]:
                            continue
                        member_character = self.runtime.STORE.character(
                            self.state.member["account_id"], self.state.member["id"]
                        )
                        member_session = self.runtime.COMBAT_SESSIONS.session(
                            self.state.member["account_id"],
                            self.state.member["generation"],
                            member_character,
                        )
                        from wakfu_server.combat_owner_publication import (
                            publication_for_world_member,
                        )

                        from wakfu_server.combat_encounter_roles import (
                            assigned_roles,
                        )

                        player_team = assigned_roles(
                            self.state.shared_rift.fight
                        ).player_team
                        self.runtime.COMBAT_SESSIONS.join(
                            member_session,
                            # coU's trailing byte is autoLock, not
                            # the actor's team. Initial company
                            # assembly must admit the full frozen
                            # roster before applying any join lock.
                            struct.pack(">qB", self.state.character["id"], 0),
                            self.runtime.COMBAT_SESSIONS.player_actor(
                                member_session, team=player_team
                            ),
                            expected_fight_id=self.state.candidate.id,
                            native_publication=publication_for_world_member(
                                self.runtime.WORLD,
                                self.state.member,
                                map_id=member_character["map_id"],
                                instance_id=member_character["instance_id"],
                            ),
                        )
                    self.state.candidate = self.state.shared_rift.fight
                    if {
                        actor.id
                        for actor in self.state.candidate.actors.values()
                        if actor.controlled
                        and str(actor.id)
                        not in getattr(
                            self.state.candidate, "native_companion_sources", {}
                        )
                    } != set(self.state.rift_start_run["members"]):
                        raise ValueError(
                            "Rift combat differs from the frozen real company"
                        )
                    with self.runtime.STORE.connection() as rift_db:
                        rift_runtime.start(
                            rift_db,
                            self.state.rift_start_run["instance_id"],
                            self.state.character["id"],
                            self.state.candidate.id,
                        )
                        rift_runtime.bind_wave(
                            rift_db,
                            self.state.rift_start_run["instance_id"],
                            self.state.rift_start_run["wave"],
                            [
                                (monster["id"], monster["ref"])
                                for monster in self.state.TEST_MONSTERS
                            ],
                        )
                        from wakfu_server.rift_key_admission import (
                            contract as rift_key_contract,
                            publication as rift_key_publication,
                        )

                        key_packets = (
                            rift_key_publication(
                                rift_db,
                                self.runtime.STORE,
                                self.state.account_id,
                                self.state.character["id"],
                            )
                            if rift_key_contract(self.state.rift_start_run["catalog"])
                            else ()
                        )
                    if key_packets:
                        from wakfu_server.inventory_move import (
                            reload_inventory,
                        )

                        self.state.reload_inventory = reload_inventory

                        self.state.character = self.state.reload_inventory(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.character,
                        )
                    for key_packet in key_packets:
                        self.runtime.send(
                            self.state.connection, self.state.service, *key_packet
                        )
                    # Initial joins have already expanded the shared
                    # roster. Bootstrap the starter from that exact
                    # final state, using the same native path as peers.
                    self.state.packets = (
                        self.runtime.COMBAT_SESSIONS.placement_bootstrap(
                            self.state.candidate,
                            self.state.shared_rift,
                            self.state.combat_session,
                        )
                    )
            self.state.fight = self.state.candidate
            for hero_packet in hero_packets:
                self.runtime.send(
                    self.state.connection, self.state.service, *hero_packet
                )
            for hero_actor in self.state.hero_admission["actors"]:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12436,
                    self.runtime.health.packet(hero_actor.id, hero_actor.hp, 0),
                )
            self.publish_external_marker(
                self.runtime.COMBAT_SESSIONS.registry.lookup(self.state.candidate.id)
            )
            self.state.placement_deadline.start(
                self.state.fight.id,
                placement_duration,
                self.state.fight_started_at,
                native=rii_guardian_owned is not None,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                12436,
                self.runtime.health.packet(
                    self.state.character["id"], self.state.character["hp"], 0
                ),
            )
            for m in self.state.TEST_MONSTERS:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    13249,
                    struct.pack(">qiih", m["id"], m["x"], m["y"], m["z"]),
                )
            if self.state.encounter_world_action is not None:
                # The actual group and durable placement already exist.
                # Preserve original cyl12421 completion. aNq197/FightStart
                # has an empty script; no second client attack is emitted.
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.encounter_world_action["native_response"],
                )
                self.runtime.record(
                    event="native_encounter_world_action_started",
                    actor_id=self.state.character["id"],
                    fight_id=self.state.fight.id,
                    target_id=self.state.encounter_world_action["target_id"],
                    action_id=self.state.encounter_world_action["action_id"],
                    source_sha256=self.state.encounter_world_action["source_sha256"],
                    authority=self.state.encounter_world_action["authority"],
                )
            if (
                self.state.encounter_world_action is not None
                and self.state.encounter_world_action.get("incarnam_stage")
            ):
                from wakfu_server.intro_cinematic import scenario_event

                self.state.scenario_event = scenario_event

                from wakfu_server.achievements.incarnam_encounters import (
                    CombatGuides,
                )

                stage = self.state.encounter_world_action["incarnam_stage"]
                self.state.connection.incarnam_combat_guides = CombatGuides(
                    self.state.fight.id, self.state.character["id"], stage
                )
                self.state.packets = list(self.state.packets)
                self.state.packets.append(
                    self.state.scenario_event(
                        22512 if stage == 1 else 22523, 2500, self.state.fight.id
                    )
                )
            starter_delivery = None
            if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                try:
                    from wakfu_server.combat_delivery_observation import (
                        begin_direct_bootstrap,
                        finish_direct_bootstrap,
                    )

                    starter_delivery = begin_direct_bootstrap(
                        self.state.fight.id,
                        self.state.combat_session,
                        self.state.packets,
                    )
                except Exception:
                    pass
            try:
                for self.state.message_id, self.state.payload in self.state.packets:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.payload,
                    )
            except BaseException as error:
                if starter_delivery is not None:
                    try:
                        finish_direct_bootstrap(starter_delivery, error=error)
                    except Exception:
                        pass
                raise
            else:
                if starter_delivery is not None:
                    try:
                        finish_direct_bootstrap(starter_delivery)
                    except Exception:
                        pass
            if any(message_id == 13652 for message_id, _ in self.state.packets):
                self.publish_admitted_rii_lesson_guide()
            from wakfu_server.combat_initialization_policy import (
                warning_text,
            )

            for warning in initialization_warnings:
                self.runtime.record(
                    event="combat_initialization_effect_skipped",
                    fight_id=self.state.fight.id,
                    development_fallback=True,
                    **warning,
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"),
                        warning_text(warning),
                    ),
                )
            from wakfu_server.combat_party_prompt import (
                notify as notify_party_combat,
            )

            notify_party_combat(
                self.runtime.STORE,
                self.runtime.WORLD,
                self.runtime.COMBAT_SESSIONS,
                self.runtime.COMBAT_SESSIONS.registry.lookup(self.state.fight.id),
                self.state.character["id"],
            )
            self.runtime.record(
                event="combat_test_placement_started",
                actor_id=self.state.character["id"],
                fight_id=self.state.fight.id,
            )
        except ValueError as error:
            if self.state.fight is None:
                self.state.combat_session = None
            if self.state.fight is None and self.state.group_lease is not None:
                self.runtime.release_groups(self.state.generation)
                self.state.group_lease = None
            if self.state.fight is None and self.state.durable_fight_id is not None:
                from wakfu_server.fight_store import abort
                from wakfu_server.dungeon_fight_binding import (
                    abort_room_encounter,
                )

                abort(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                    self.state.durable_fight_id,
                    on_aborted=(
                        abort_room_encounter
                        if self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                        and self.state.rift_start_run is None
                        else None
                    ),
                )
                if self.state.rift_start_run is not None:
                    self.runtime.COMBAT_SESSIONS.registry.retire_unpublished_rift(
                        self.state.durable_fight_id
                    )
            self.runtime.record(
                event="combat_test_attack_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.combat_initialization_policy import (
                safe_rejection_text,
            )

            self.state.safe_rejection_text = safe_rejection_text

            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    self.state.safe_rejection_text(error),
                ),
            )
        except Exception:
            # Durable identity may exist before bootstrap produces a Fight.
            if self.state.fight is None:
                self.state.combat_session = None
            if self.state.fight is None and self.state.group_lease is not None:
                self.runtime.release_groups(self.state.generation)
                self.state.group_lease = None
            if self.state.fight is None and self.state.durable_fight_id is not None:
                from wakfu_server.fight_store import abort
                from wakfu_server.dungeon_fight_binding import (
                    abort_room_encounter,
                )

                abort(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                    self.state.durable_fight_id,
                    on_aborted=(
                        abort_room_encounter
                        if self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                        and self.state.rift_start_run is None
                        else None
                    ),
                )
                if self.state.rift_start_run is not None:
                    self.runtime.COMBAT_SESSIONS.registry.retire_unpublished_rift(
                        self.state.durable_fight_id
                    )
            raise
        return DispatchResult.FALLTHROUGH

    def handle_fight_roster(self):
        try:
            if self.state.combat_session is None or self.state.fight is None:
                raise ValueError("Tactical signaling requires owned fight membership")
            from wakfu_server import combat_tactical_markers
            from wakfu_server.combat_terminal_metadata import (
                registered_summon_actor_ids,
            )

            self.refresh_shared_combat()
            selected_actor = self.state.fight.actors[
                self.state.combat_session.character_id
            ]
            current_actor = self.state.fight.current
            if (
                current_actor is not None
                and current_actor.controlled
                and current_actor.owner_id == self.state.combat_session.account_id
                and current_actor.id
                not in registered_summon_actor_ids(self.state.fight)
            ):
                selected_actor = current_actor
            self.state.result = combat_tactical_markers.handle(
                self.runtime.COMBAT_SESSIONS.registry,
                self.state.combat_session,
                self.state.fight.id,
                selected_actor.id,
                self.state.opcode,
                self.state.body,
            )
            if self.state.result["accepted"]:
                self.checkpoint_fight()
                self.drain_shared_combat()
            self.runtime.record(
                event="combat_tactical_signal",
                fight_id=self.state.fight.id,
                actor_id=selected_actor.id,
                opcode=self.state.opcode,
                accepted=self.state.result["accepted"],
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_tactical_signal_rejected",
                opcode=self.state.opcode,
                actor_id=(
                    None if self.state.character is None else self.state.character["id"]
                ),
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_fight_placement(self):
        from wakfu_server.combat_bootstrap import placement_positions

        self.state.placement_positions = placement_positions

        self.state.actor_id, self.state.x, self.state.y, self.state.z = struct.unpack(
            ">qiih", self.state.body
        )
        try:
            if self.state.combat_session is not None:
                from wakfu_server.combat_shared import Transition

                self.state.Transition = Transition

                self.runtime.COMBAT_SESSIONS.execute(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.actor_id,
                    lambda candidate, runtime: (
                        candidate.place(
                            self.state.account_id,
                            self.state.actor_id,
                            (self.state.x, self.state.y, self.state.z),
                        ),
                        self.state.Transition(
                            candidate,
                            runtime,
                            ((13652, self.state.placement_positions(candidate)),),
                        ),
                    )[1],
                    require_turn=False,
                )
                self.refresh_shared_combat()
                self.drain_shared_combat()
            else:
                self.state.fight.place(
                    self.state.account_id,
                    self.state.actor_id,
                    (self.state.x, self.state.y, self.state.z),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    13652,
                    self.state.placement_positions(self.state.fight),
                )
        except ValueError as error:
            self.runtime.record(
                event="combat_test_placement_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.combat_initialization_policy import (
                safe_rejection_text,
            )

            self.state.safe_rejection_text = safe_rejection_text

            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    self.state.safe_rejection_text(error),
                ),
            )
        return DispatchResult.FALLTHROUGH

    def handle_fight_placement_validate(self):
        try:
            if len(self.state.body) != 1 or self.state.body[0] not in (0, 1):
                raise ValueError("Invalid placement readiness")
            self.apply_readiness(bool(self.state.body[0]))
        except ValueError as error:
            self.runtime.record(
                event="combat_test_ready_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.combat_initialization_policy import (
                safe_rejection_text,
            )

            self.state.safe_rejection_text = safe_rejection_text

            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    self.state.safe_rejection_text(error),
                ),
            )
        return DispatchResult.FALLTHROUGH
