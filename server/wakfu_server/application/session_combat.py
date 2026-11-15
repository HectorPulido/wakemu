"""Combat operations for one lease-bound World session."""

from contextlib import contextmanager, nullcontext
import struct
import threading
import os
import time
from wakfu_server.performance_profiler import PROFILER
from .dispatch_result import DispatchResult


class CombatSessionMixin:
    def attach_combat_return_position(self):
        # Private coordinates never replace the durable exterior position.
        saved = (
            self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"]
            )
            if self.active_private_session() is not None
            else self.state.character
        )
        return self.runtime.POSITIONS.attach(
            self.state.account_id, self.state.generation, saved
        )

    def combat_return_bootstrap(self):
        session = self.active_private_session()
        if session is None:
            return self.runtime.owned_native_bootstrap(self.state.character)
        if not session.owns(self.state.character):
            raise ValueError("Combat return lost its private scene capability")
        if self.state.ranch_session is not None:
            packets = self.state.ranch_session.entry_messages(
                self.runtime.fixture(13974), self.state.character, clear_bag_role=False
            )
            if self.state.character["map_id"] == 1440:
                from wakfu_server.haven_ranch_furniture import snapshot

                restored = snapshot(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    session=self.state.ranch_session,
                    now_ms=int(time.time() * 1000),
                )
                packets = [restored["packet"] if p[0] == 13864 else p for p in packets]
            return packets
        from wakfu_server.haven_bag import entry_messages

        return entry_messages(
            self.runtime.fixture(13974),
            self.state.character,
            owner=(
                None
                if self.state.bag_session.is_owner
                else self.state.bag_session.owner
            ),
        )

    def consume_rift_entry_combat_retirement(self):
        """Drop only a durably retired encounter; native entry owns its bootstrap."""
        from wakfu_server.combat_entry_recovery import take_entry_recovery

        old_fight_id = take_entry_recovery(
            self.runtime.COMBAT_SESSIONS.registry,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
        )
        if old_fight_id is None or (
            self.state.fight is not None and self.state.fight.id != old_fight_id
        ):
            return False
        self.state.fight = self.state.fight_messages = self.state.combat_session = (
            self.state.group_lease
        ) = None
        if self.state.checkpoint_id == old_fight_id:
            self.state.checkpoint_id = self.state.checkpoint_revision = None
            self.state.checkpoint_terminal = True
        if (
            isinstance(self.state.pending_combat_return, dict)
            and self.state.pending_combat_return.get("fight_id") == old_fight_id
        ):
            self.state.pending_combat_return = None
            self.state.pending_return_command.clear()
        if (
            isinstance(self.state.pending_terminal_world_recovery, dict)
            and self.state.pending_terminal_world_recovery.get("fight_id")
            == old_fight_id
        ):
            self.state.pending_terminal_world_recovery = None
        if (
            self.state.publication_recovery_shared is not None
            and self.state.publication_recovery_shared.fight.id == old_fight_id
        ):
            self.state.publication_recovery_shared = None
            self.state.publication_recovery_attempt_token = (
                self.state.publication_recovery_notice_token
            ) = None
        self.state.TEST_MONSTERS = ()
        self.state.TEST_MONSTERS_BY_ID = {}
        self.state.TEST_GROUP_KEY = None
        self.state.fight_started_at = None
        self.state.placement_deadline.take_expired(None, time.monotonic())
        self.runtime.record(
            event="rift_entry_obsolete_combat_retired",
            actor_id=self.state.character["id"],
            fight_id=old_fight_id,
        )
        return True

    def publish_entry_inventory(self, before):
        """Publish committed bag, personal and account entrance-item quantities."""
        from wakfu_server.inventory_move import synchronization
        from wakfu_server.quest_inventory import changes as quest_changes
        from wakfu_server.exploration_secrets import account_packet

        self.runtime.send(
            self.state.connection,
            self.state.service,
            *synchronization(self.state.character),
        )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *self.runtime.rich_inventory_packet(self.state.character),
        )
        for packet in quest_changes(before, self.state.character):
            self.runtime.send(self.state.connection, self.state.service, *packet)
        with self.runtime.STORE.connection() as db:
            packet = account_packet(db, self.state.account_id)
        self.runtime.send(self.state.connection, self.state.service, *packet)

    def publish_heroes(self, roster):
        self.state.pet_hibernation_due = 0.0
        # A newly added hero may have expired cycles even if the main owner's
        # previous session checkpoint was already cached.
        self.state.recurring_hunter_boundary = (None, None)
        from wakfu_server import hero_wire, hero_private_scene

        roster = hero_private_scene.project(
            roster,
            self.active_private_session(),
            self.state.character,
            self.state.generation,
        )
        for hero in roster["heroes"]:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *hero_wire.activate(self.runtime.OWNED_HERO_TEMPLATE, hero),
            )
            self.runtime.send(
                self.state.connection, self.state.service, *hero_wire.statistics(hero)
            )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *hero_wire.company(
                self.state.account_id,
                roster["leader"]["id"],
                guild_id=(roster["leader"].get("guild_native") or {}).get("guildId", 0),
                nation_id=roster["leader"].get("nation_id", 0),
                company_snapshot=roster["leader"]["equipment_criterion_context"][
                    "company_snapshot"
                ],
            ),
        )
        self.runtime.refresh_party(self.state.generation, roster["leader"])

    def prepare_rift_start(self, body):
        """Return None if unrelated, a startable run, or False after refusal."""
        if self.state.character is None or not (1 << 58) < self.state.character.get(
            "instance_id", 0
        ) < (1 << 59):
            return None
        from wakfu_server import rift_entry_adapter

        loading_member = None
        try:
            with self.runtime.STORE.connection() as db:
                run = rift_entry_adapter.authorize_start(
                    db,
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    body,
                    source_allowed=lambda actor, source: (
                        actor["map_id"] == source["map_id"]
                        and max(
                            abs(actor["x"] - source["x"]), abs(actor["y"] - source["y"])
                        )
                        <= 3
                        and abs(actor["z"] - source["z"]) <= 2
                    ),
                )
                if run is not None:
                    from wakfu_server import rift_transition_delivery

                    frozen_members = db.execute(
                        "SELECT c.id,c.account_id,c.name,s.generation,"
                        "s.character_id AS selected_character_id FROM characters c "
                        "JOIN sessions s ON s.account_id=c.account_id WHERE c.id=ANY(%s)",
                        (run["members"],),
                    ).fetchall()
                    # Heroes share their selected main's transport. Durable
                    # authorization above still checks every frozen member.
                    members = [
                        row
                        for row in frozen_members
                        if row["id"] == row["selected_character_id"]
                    ]
                    if {row["id"] for row in frozen_members} != set(run["members"]) or {
                        row["account_id"] for row in members
                    } != {row["account_id"] for row in frozen_members}:
                        raise ValueError(
                            "Every frozen rift owner must have a selected participant"
                        )
                    for row in members:
                        if (
                            rift_transition_delivery.pending(
                                row["account_id"], row["generation"], row["id"]
                            )
                            is not None
                        ):
                            loading_member = row["name"]
                            raise ValueError(
                                "Wait for every frozen rift member to load the interior"
                            )
            if run is not None:
                with self.runtime.WORLD.lock:
                    for row in members:
                        visible = self.runtime.WORLD.players.get(row["id"])
                        if (
                            visible is None
                            or visible[0] != row["generation"]
                            or self.runtime.WORLD.location(visible[2])
                            != (self.state.character["map_id"], run["instance_id"])
                        ):
                            loading_member = row["name"]
                            raise ValueError(
                                "Every frozen rift member must finish loading the interior"
                            )
            return run
        except ValueError as error:
            self.runtime.record(
                event="rift_start_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.ecology_feedback import information

            loading_name = "".join(
                char for char in str(loading_member or "") if char.isprintable()
            )[:64]
            loading_message = (
                "No se puede iniciar la brecha: espera a que "
                + loading_name
                + " termine de cargar la brecha."
                if loading_name
                else (
                    "No se puede iniciar la brecha: espera a que todos los "
                    "integrantes terminen de cargar el interior."
                )
            )
            message = {
                "Wait for every frozen rift member to load the interior": loading_message,
                "Every frozen rift member must finish loading the interior": loading_message,
                "Every frozen rift owner must have a selected participant": (
                    "No se puede iniciar la brecha: cada cuenta debe tener "
                    "seleccionado un integrante de la compañía."
                ),
                "Frozen rift members left the instance": (
                    "No se puede iniciar la brecha: todos los integrantes "
                    "deben estar dentro de la misma brecha."
                ),
                "Missing native ultimate rift key": (
                    "No se puede iniciar la brecha: falta la llave necesaria."
                ),
            }.get(
                str(error),
                "No se pudo iniciar la brecha. Revisa la compañía y vuelve a usar el altar.",
            )
            self.runtime.send(
                self.state.connection, self.state.service, *information(message)
            )
            return False

    def checkpoint_accepted_rift(self, shared, candidate, runtime, packets):
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.rift_dispatch_lifecycle import (
            actor_reservation_shortfall,
            replenish_actor_ids,
        )

        # A wave count is not an actor-ID budget. Reserve only when this
        # private accepted preview actually needs another native ID block.
        if actor_reservation_shortfall(candidate):
            with self.runtime.STORE.connection() as rift_db:
                replenish_actor_ids(rift_db, candidate)

        def initialize_equipment_wave(current, actors, monsters):
            from wakfu_server.combat_server_spell import server_runtime
            from wakfu_server.rift_wave_initialization import initialize_registered_wave

            characters, decks = self.runtime.COMBAT_SESSIONS.player_sources(current)
            source_id = min(characters)
            factory, _ = server_runtime(
                characters[source_id],
                current.rift_monsters,
                decks[source_id],
                action_id=runtime.action_id,
                critical=False,
                player_characters=characters,
                deck_blobs=decks,
            )
            dispatcher, outbox = factory(
                current, {"native_retained_container": {"present": False}}
            )
            with current.effect_resolution():
                initialize_registered_wave(
                    dispatcher,
                    actors=actors,
                    monsters=monsters,
                    player_ids=tuple(characters),
                )
            return tuple(outbox)

        prepared = finish_accepted_action(
            candidate,
            runtime,
            packets,
            initialize_actor=lambda current, actor, monster: (),
            initialize_wave=initialize_equipment_wave,
        )
        return prepared

    def checkpoint_final_rift(self, shared, candidate, runtime, packets):
        # Registry calls this only after death/turn synchronization and packet
        # validation, while the final private state is still unpublished.
        owner = next(
            (
                owner
                for owner in sorted(
                    shared.participants.values(), key=lambda entry: entry.character_id
                )
                if self.runtime.STORE.current_character_session(
                    owner.account_id, owner.generation, owner.character_id
                )
            ),
            None,
        )
        if owner is None:
            raise ValueError("Rift checkpoint requires a current participant lease")
        shared.checkpoint_revision = self.runtime.CHECKPOINTS.save(
            owner.account_id,
            owner.generation,
            candidate,
            expected_revision=shared.checkpoint_revision,
            runtime=runtime,
        )

    @PROFILER.profile("combat.checkpoint")
    def checkpoint_fight(
        self, status=None, *, deliver=True, accepted_publication=False
    ):
        if self.state.fight is None:
            return
        if self.state.checkpoint_id != self.state.fight.id:
            self.state.checkpoint_id = self.state.fight.id
            self.state.checkpoint_revision = None
            self.state.checkpoint_terminal = False
        if self.state.checkpoint_terminal:
            return
        checkpoint_started = time.monotonic()
        captured_checkpoint_id = self.state.fight.id

        def checkpoint_trace(stage, **details):
            details.setdefault("fight_id", captured_checkpoint_id)
            self.runtime.record(
                event="persistence_stage",
                domain="fight_checkpoint",
                stage=stage,
                **details,
            )

        try:
            if self.state.combat_session is not None:
                shared_checkpoint = self.runtime.COMBAT_SESSIONS.registry.lookup(
                    self.state.fight.id
                )
            else:
                from types import SimpleNamespace

                if (
                    self.state.checkpoint_local_shared is None
                    or self.state.checkpoint_local_shared.fight.id
                    != self.state.fight.id
                ):
                    self.state.checkpoint_local_shared = SimpleNamespace(
                        fight=self.state.fight,
                        runtime=self.state.fight_messages,
                        lock=threading.RLock(),
                        checkpoint_revision=self.state.checkpoint_revision,
                        checkpoint_terminal=False,
                    )
                shared_checkpoint = self.state.checkpoint_local_shared
            if (
                shared_checkpoint.checkpoint_terminal
                or self.runtime.CHECKPOINT_WRITER.terminal_pending(self.state.fight.id)
            ):
                return
            if self.state.combat_session is not None and deliver:
                # Live presentation retains its existing ordered drain. Logout
                # checkpoints the canonical state independently of a dead socket;
                # other owners' outboxes and the native ACK remain untouched.
                self.drain_shared_combat()
            if (
                accepted_publication
                and status is None
                and self.state.combat_session is not None
            ):
                from wakfu_server.combat_checkpoint_publication import (
                    is_checkpointed_publication,
                )

                # Only explicitly audited Registry callers opt into this.
                # In-place mutations and terminal/logout saves never do.
                with shared_checkpoint.lock:
                    if is_checkpointed_publication(shared_checkpoint):
                        return
            self.runtime.record(
                event="persistence_stage",
                domain="fight_checkpoint",
                stage="save_started",
                fight_id=self.state.fight.id,
            )
            if getattr(self.state.fight, "rift_wave_state", None) is not None:
                with shared_checkpoint.lock:
                    shared_checkpoint.checkpoint_revision = (
                        self.runtime.CHECKPOINTS.save(
                            self.state.account_id,
                            self.state.generation,
                            shared_checkpoint.fight,
                            expected_revision=shared_checkpoint.checkpoint_revision,
                            runtime=shared_checkpoint.runtime,
                            trace=checkpoint_trace,
                        )
                    )
                    if status is not None:
                        shared_checkpoint.checkpoint_revision = (
                            self.runtime.CHECKPOINTS.end(
                                self.state.account_id,
                                self.state.generation,
                                self.state.fight.id,
                                expected_revision=shared_checkpoint.checkpoint_revision,
                                status=status,
                                trace=checkpoint_trace,
                            )
                        )
                        shared_checkpoint.checkpoint_terminal = True
                return
            queued = self.runtime.CHECKPOINT_WRITER.submit(
                shared_checkpoint,
                self.state.account_id,
                self.state.generation,
                status=status,
                trace=checkpoint_trace,
            )
            self.runtime.record(
                event="combat_checkpoint_queued",
                fight_id=self.state.fight.id,
                sequence=queued["sequence"],
                terminal=queued["terminal"],
            )
            self.runtime.record(
                event="combat_checkpoint_timing",
                fight_id=self.state.fight.id,
                elapsed_ms=round((time.monotonic() - checkpoint_started) * 1000, 3),
            )
        except ValueError as error:
            # A replaced login cannot overwrite the current generation's state.
            self.runtime.record(
                event="combat_checkpoint_rejected",
                fight_id=self.state.fight.id,
                reason=str(error),
            )

    @PROFILER.profile("combat.settlement")
    def complete_test_fight(self):
        from wakfu_server.combat_death import death_messages
        from wakfu_server.combat_lifecycle import prepare_finish
        from wakfu_server.combat_encounter_scene_helpers import reward_eligible_members
        from wakfu_server.item_test_spawns import (
            is_fight as is_developer_test_fight,
            finish as finish_developer_test_group,
        )

        committed_task_candidates = []
        reward_monsters = reward_eligible_members(
            self.state.fight, self.state.TEST_MONSTERS
        )

        def mark_committed_custom_tasks():
            self.state.custom_task_cards.changed(
                self.state.character["id"],
                tuple(
                    update["character_id"]
                    for update in committed_task_candidates
                    if update["account_id"] == self.state.account_id
                    and update["result"]["updated"]
                ),
            )

        def settle_achievements(db, members, candidate):
            if (getattr(candidate, "rift_wave_state", None) or {}).get(
                "outcome"
            ) == "administrative_victory":
                return {}
            if is_developer_test_fight(db, candidate.id):
                return {}
            from wakfu_server.achievements.combat_adapter import settle_participants

            try:
                admitted = self.runtime.COMBAT_SESSIONS.registry.lookup(candidate.id)
            except ValueError:
                # Legacy non-registry settlement has no environmental origin.
                admitted = None
            from wakfu_server.objectives.environmental_gameplay import (
                scene_from_admission,
            )

            environmental_scene = (
                scene_from_admission(admitted) if admitted is not None else None
            )
            from wakfu_server.combat_aguabrial_story import settle_aguabrial_story

            story_packets = settle_aguabrial_story(
                self.runtime.STORE, db, candidate, members
            )
            delivery = settle_participants(
                db,
                self.runtime.STORE,
                candidate,
                members,
                reward_eligible_members(candidate, self.state.TEST_MONSTERS),
                environmental_scene=environmental_scene,
            )
            # Collect metadata only; mark dirty after the enclosing commit.
            committed_task_candidates.extend(delivery.get("custom_task_updates", ()))
            # Durable notification keys remain pending until a complete native
            # bootstrap covers their state; disconnect never loses progress.
            packets_by_owner = {
                owner: list(packets)
                for owner, packets in delivery["packets_by_owner"].items()
            }
            for owner, packets in story_packets.items():
                packets_by_owner.setdefault(owner, []).extend(packets)
            if any(
                monster.get("map_id") == 1361 for monster in self.state.TEST_MONSTERS
            ):
                from wakfu_server.achievements import incarnam_encounters

                for owner, packets in incarnam_encounters.settle(
                    db, self.runtime.STORE, candidate, members, self.state.TEST_MONSTERS
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            if getattr(candidate, "rii_orientation_contract", None):
                from wakfu_server.achievements import rii_orientation

                # Keep the lesson receipt and fight result in one transaction.
                # A failure must roll back the final result and remain retryable.
                for owner, packets in rii_orientation.settle_participants(
                    db, self.runtime.STORE, candidate, members, self.state.TEST_MONSTERS
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            if getattr(candidate, "rii_element_lesson_contract", None):
                from wakfu_server.achievements import rii_element_encounter

                for owner, packets in rii_element_encounter.settle_participants(
                    db, self.runtime.STORE, candidate, members, self.state.TEST_MONSTERS
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            if getattr(candidate, "rii_distance_lesson_contract", None):
                from wakfu_server.achievements import rii_owned_lesson

                for owner, packets in rii_owned_lesson.settle_participants(
                    db,
                    self.runtime.STORE,
                    rii_owned_lesson.DISTANCE,
                    candidate,
                    members,
                    self.state.TEST_MONSTERS,
                    contract_name="rii_distance_lesson_contract",
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            if getattr(candidate, "rii_area_lesson_contract", None):
                from wakfu_server.achievements import rii_area_encounter

                for owner, packets in rii_area_encounter.settle_participants(
                    db, self.runtime.STORE, candidate, members, self.state.TEST_MONSTERS
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            if getattr(candidate, "rii_los_lesson_contract", None):
                from wakfu_server.achievements import (
                    rii_owned_lesson,
                    rii_los_encounter,
                )

                for owner, packets in rii_owned_lesson.settle_participants(
                    db,
                    self.runtime.STORE,
                    rii_los_encounter.LOS,
                    candidate,
                    members,
                    self.state.TEST_MONSTERS,
                    contract_name="rii_los_lesson_contract",
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            if getattr(candidate, "rii_movement_lesson_contract", None):
                from wakfu_server.achievements import rii_owned_lesson

                for owner, packets in rii_owned_lesson.settle_participants(
                    db,
                    self.runtime.STORE,
                    rii_owned_lesson.MOVEMENT,
                    candidate,
                    members,
                    self.state.TEST_MONSTERS,
                    contract_name="rii_movement_lesson_contract",
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            if getattr(candidate, "rii_states_lesson_contract", None):
                from wakfu_server.achievements import rii_owned_lesson

                for owner, packets in rii_owned_lesson.settle_participants(
                    db,
                    self.runtime.STORE,
                    rii_owned_lesson.STATES,
                    candidate,
                    members,
                    self.state.TEST_MONSTERS,
                    contract_name="rii_states_lesson_contract",
                ).items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            from wakfu_server.achievements import rii_lesson_presentation

            for packets in packets_by_owner.values():
                presentation = rii_lesson_presentation.finish(candidate, packets)
                if presentation is not None:
                    packets.append(presentation)
            if any(monster.get("ref") == 5458 for monster in self.state.TEST_MONSTERS):
                from wakfu_server.achievements import rii_guardian_battle

                # A guardian attempt and its combat result must commit together.
                # Propagate failures so the existing settlement retry can recover.
                guardian_packets = rii_guardian_battle.settle(
                    db, self.runtime.STORE, candidate, members, self.state.TEST_MONSTERS
                )
                for owner, packets in guardian_packets.items():
                    packets_by_owner.setdefault(owner, []).extend(packets)
            return packets_by_owner

        if self.state.combat_session is not None:
            from wakfu_server.combat_lifecycle import prepare_finish_shared
            from wakfu_server.monster_removal_ecology import (
                finish as finish_world_group,
            )
            from wakfu_server import combat_reward_context, reward_policy
            from wakfu_server import combat_drops, combat_drop_delivery
            from wakfu_server.inventory_move import synchronization
            from wakfu_server.inventory_items import equipment_inventory

            shared = self.refresh_shared_combat()
            if shared is None:
                raise ValueError("Shared fight registry entry is unavailable")
            owner_characters, _ = self.runtime.COMBAT_SESSIONS.player_sources(
                self.state.fight
            )
            from wakfu_server.combat_terminal_metadata import (
                owner_characters_for_finish,
                registered_summon_actor_ids,
                registered_summon_metadata,
            )

            owner_characters = owner_characters_for_finish(
                self.runtime.STORE, shared, self.state.fight, owner_characters
            )
            summon_actor_ids = registered_summon_actor_ids(self.state.fight)
            from wakfu_server.combat_companions import registered_companion_ids

            companion_actor_ids = registered_companion_ids(self.state.fight)
            if getattr(shared, "is_duel", False):
                from wakfu_server.combat_results import finish_messages
                from wakfu_server.friendly_duels import settle as settle_duel

                duel_metadata = {
                    actor.id: dict(
                        kind="player",
                        account_id=actor.owner_id,
                        name=owner_characters[actor.id]["name"],
                        breed=owner_characters[actor.id]["breed"],
                        is_male=owner_characters[actor.id]["sex"] == 0,
                    )
                    for actor in self.state.fight.actors.values()
                    if actor.controlled
                    and actor.id not in summon_actor_ids
                    and actor.id not in companion_actor_ids
                }
                duel_metadata.update(registered_summon_metadata(self.state.fight))

                def prepare_duel_packets(current_shared):
                    reason = getattr(current_shared, "duel_finish_reason", "defeat")
                    disconnected_id = getattr(
                        current_shared, "duel_disconnected_character_id", None
                    )
                    settle_duel(
                        self.runtime.STORE,
                        self.state.combat_session.account_id,
                        self.state.combat_session.generation,
                        self.state.combat_session.character_id,
                        current_shared.fight,
                        reason=reason,
                        disconnected_character_id=disconnected_id,
                    )
                    batches = {}
                    for owner, participant in current_shared.participants.items():
                        packets = finish_messages(
                            current_shared.runtime,
                            duel_metadata,
                            duration_ms=int(
                                (time.monotonic() - self.state.fight_started_at) * 1000
                            ),
                            fight_instance_id=current_shared.fight.id,
                            initiator_id=participant.character_id,
                        )
                        packets.append(
                            (13420, struct.pack(">i", current_shared.fight.id))
                        )
                        batches[owner] = tuple(packets)
                    return batches

                self.runtime.COMBAT_SESSIONS.settle_finished(
                    self.state.combat_session, self.state.fight.id, prepare_duel_packets
                )
                self.refresh_shared_combat()
                self.drain_shared_combat()
                self.checkpoint_fight("ended")
                from wakfu_server.friendly_duel_bot_ack import return_settled

                return_settled(self.runtime.COMBAT_SESSIONS, shared)
                self.state.character.update(
                    self.refresh_owned_character(
                        self.runtime.STORE.character(
                            self.state.account_id, self.state.character["id"]
                        )
                    )
                )
                self.runtime.record(
                    event="friendly_duel_finished",
                    actor_id=self.state.combat_session.character_id,
                    fight_id=self.state.fight.id,
                    winner=self.state.fight.winner,
                    reason=getattr(shared, "duel_finish_reason", "defeat"),
                )
                return
            metadata = {
                actor.id: dict(
                    kind="player",
                    account_id=actor.owner_id,
                    name=owner_characters[actor.id]["name"],
                    breed=owner_characters[actor.id]["breed"],
                    is_male=owner_characters[actor.id]["sex"] == 0,
                )
                for actor in self.state.fight.actors.values()
                if actor.controlled
                and actor.id not in summon_actor_ids
                and actor.id not in companion_actor_ids
            }
            metadata.update(registered_summon_metadata(self.state.fight))
            metadata.update(
                {
                    identity: dict(kind="monster", ref=source["ref"])
                    for identity in companion_actor_ids
                    for source in (
                        self.state.fight.native_companion_sources[str(identity)],
                    )
                }
            )
            metadata.update(
                {
                    monster_id: dict(kind="monster", ref=monster["ref"])
                    for monster_id, monster in self.state.TEST_MONSTERS_BY_ID.items()
                }
            )
            frozen_contexts = {}

            def settle_rift_rewards(db):
                from wakfu_server import rift_runtime
                from wakfu_server import rift_rewards
                from wakfu_server.combat_encounter_roles import assigned_roles

                rift_roles = assigned_roles(self.state.fight)

                eligible = tuple(
                    actor.id
                    for actor in self.state.fight.actors.values()
                    if actor.id in owner_characters
                    and actor.team == rift_roles.player_team
                    and not getattr(actor, "pve_withdrawn", False)
                )
                return rift_runtime.settle(
                    db,
                    self.state.fight.rift_wave_state["instance_id"],
                    self.state.fight.id,
                    outcome=(
                        "closed"
                        if self.state.fight.rift_wave_state.get("outcome")
                        in ("capacity_exhausted", "administrative_victory")
                        else (
                            "won"
                            if self.state.fight.winner == rift_roles.player_team
                            else (
                                "lost"
                                if self.state.fight.winner == rift_roles.npc_team
                                else "closed"
                            )
                        )
                    ),
                    turn=self.state.fight.native_timeline_round,
                    reconcile_earned_rewards=True,
                    apply_rewards=lambda reward_db, run, result: rift_rewards.apply(
                        reward_db,
                        run,
                        result,
                        store=self.runtime.STORE,
                        eligible_character_ids=eligible,
                        fight=self.state.fight,
                    ),
                )

            def shared_policy(db, member, source):
                from wakfu_server.rii_training_rewards import is_owned_training
                from wakfu_server.achievements.rii_guardian_contract import (
                    is_owned as is_owned_guardian,
                )

                if (
                    is_developer_test_fight(db, self.state.fight.id)
                    or is_owned_training(self.state.fight, member["character_id"])
                    or is_owned_guardian(self.state.fight, member["character_id"])
                ):
                    from wakfu_server.combat_rewards import Policy

                    return Policy()
                if getattr(self.state.fight, "rift_wave_state", None) is not None:
                    from wakfu_server import rift_currency_rewards
                    from wakfu_server.combat_encounter_roles import assigned_roles

                    # Loot receipts must exist before per-member native reports are built.
                    settle_rift_rewards(db)
                    return rift_currency_rewards.resolve(
                        self.runtime.STORE,
                        db,
                        account_id=member["account_id"],
                        generation=member["session_generation"],
                        character_id=member["character_id"],
                        fight=self.state.fight,
                        character=source,
                        eligible_character_ids=tuple(
                            actor.id
                            for actor in self.state.fight.actors.values()
                            if actor.id in owner_characters
                            and actor.team
                            == assigned_roles(self.state.fight).player_team
                            and not getattr(actor, "pve_withdrawn", False)
                        ),
                    )
                context, drop_context = combat_reward_context.settlement_contexts(
                    db,
                    self.state.fight,
                    source,
                    reward_monsters,
                    encounter_kind=combat_reward_context.authoritative_encounter_kind(
                        db,
                        self.state.fight.id,
                        (
                            None
                            if self.state.group_lease is None
                            else self.state.group_lease[0]
                        ),
                        dungeon_runtime_available=self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE,
                    ),
                )
                frozen_contexts[member["character_id"]] = (context, drop_context)
                return reward_policy.resolve(
                    self.runtime.STORE,
                    db,
                    account_id=member["account_id"],
                    generation=member["session_generation"],
                    character_id=member["character_id"],
                    fight_id=self.state.fight.id,
                    context=context,
                ).policy

            def shared_loot(db, member, reward):
                from wakfu_server.rii_training_rewards import is_owned_training
                from wakfu_server.achievements.rii_guardian_contract import (
                    is_owned as is_owned_guardian,
                )

                if (
                    is_developer_test_fight(db, self.state.fight.id)
                    or is_owned_training(self.state.fight, member["character_id"])
                    or is_owned_guardian(self.state.fight, member["character_id"])
                ):
                    return {"loots": [], "packets": []}
                if getattr(self.state.fight, "rift_wave_state", None) is not None:
                    from wakfu_server import rift_rewards

                    settle_rift_rewards(db)
                    return rift_rewards.delivery(
                        db,
                        self.runtime.STORE,
                        self.state.fight.rift_wave_state["instance_id"],
                        member["character_id"],
                    )
                actor = self.state.fight.actors[member["character_id"]]
                frozen = frozen_contexts.get(member["character_id"])
                if frozen is None:
                    raise ValueError("Shared loot has no pre-award context snapshot")
                _, drop_context = frozen
                from wakfu_server.combat_companions import loot_profiles

                batch = combat_drops.resolve(
                    self.runtime.STORE,
                    db,
                    account_id=member["account_id"],
                    generation=member["session_generation"],
                    character_id=member["character_id"],
                    fight_id=self.state.fight.id,
                    monsters=[
                        {"actor_id": monster["id"], "reference": monster["ref"]}
                        for monster in reward_monsters
                    ],
                    prospecting_bonus=combat_drops.native_prospection_bonus(actor),
                    shop_consumable_factor=combat_drops.native_shop_drop_factor(actor),
                    can_loot=True,
                    fight_context=drop_context,
                    companion_rolls=loot_profiles(
                        self.state.fight, member["character_id"]
                    ),
                )
                from wakfu_server.quest_inventory import changes as quest_changes

                before_loot = self.runtime.STORE.character(
                    member["account_id"], member["character_id"], db
                )
                combat_drop_delivery.apply(self.runtime.STORE, db, batch)
                saved = self.runtime.STORE.character(
                    member["account_id"], member["character_id"], db
                )
                return {
                    "loots": combat_drops.report_loots(
                        batch, loot_actor_id=member["character_id"]
                    ),
                    "packets": [
                        *quest_changes(before_loot, saved),
                        synchronization(saved),
                        equipment_inventory(saved),
                        *combat_drop_delivery.temporary_updates(
                            db, member["character_id"]
                        ),
                    ],
                }

            def shared_group_settlement(db, owner_account, owner_character, defeated):
                if self.state.group_lease is not None:
                    developer_result = finish_developer_test_group(
                        db, self.runtime.COMBAT_GROUPS, self.state.group_lease
                    )
                    if developer_result is not None:
                        return developer_result
                if getattr(self.state.fight, "rift_wave_state", None) is not None:
                    settle_rift_rewards(db)
                    return {"applied": True, "packets": []}
                if self.state.group_lease is None:
                    return {"applied": True, "packets": []}
                if (
                    self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                    and self.state.group_lease[0][1] > 0
                ):
                    from wakfu_server import dungeon_progression

                    # Hydration takes the run before the population/group locks.
                    # Settlement must use the same order before finishing a group.
                    dungeon_progression.lock_encounter_run(db, self.state.fight.id)
                outcome = finish_world_group(
                    self.runtime.STORE,
                    self.runtime.COMBAT_GROUPS,
                    self.state.group_lease,
                    character_id=owner_character,
                    defeated=defeated,
                    db=db,
                )
                if outcome["applied"] and defeated:
                    from wakfu_server.monster_corpses import retain

                    retain(db, self.state.fight, reward_monsters)
                if (
                    outcome["applied"]
                    and self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                    and self.state.group_lease[0][1] > 0
                ):
                    from wakfu_server import dungeon_progression, dungeon_runtime
                    from wakfu_server.combat_terrain import map_geometry

                    room_result = dungeon_progression.settle_encounter(
                        db, self.state.fight
                    )
                    if room_result is not None:
                        if (
                            room_result.get("victory")
                            and room_result.get("encounter_scope", "main") == "main"
                        ):
                            from wakfu_server import dungeon_room_handoff

                            dungeon_room_handoff.prepare(
                                db,
                                self.runtime.COMBAT_GROUPS,
                                instance_id=room_result["instance_id"],
                                fight_id=self.state.fight.id,
                                map_id=self.state.group_lease[0][0],
                                geometry_provider=map_geometry,
                            )
                        else:
                            dungeon_runtime.ensure_current_room(
                                db,
                                self.runtime.COMBAT_GROUPS,
                                room_result["instance_id"],
                                map_geometry(self.state.group_lease[0][0]),
                            )
                return outcome

            def prepare_shared_packets(current_shared):
                prepared = prepare_finish_shared(
                    self.runtime.STORE,
                    self.state.combat_session.account_id,
                    self.state.combat_session.generation,
                    self.state.combat_session.character_id,
                    current_shared.runtime,
                    metadata,
                    duration_ms=int(
                        (time.monotonic() - self.state.fight_started_at) * 1000
                    ),
                    fight_instance_id=self.state.fight.id,
                    policy_resolver=shared_policy,
                    loot_resolver=shared_loot,
                    progression_resolver=settle_achievements,
                    expected_accounts=set(current_shared.participants),
                    owner_character_ids={
                        owner: session.character_id
                        for owner, session in current_shared.participants.items()
                    },
                    trace=lambda stage, **fields: self.runtime.record(
                        event="persistence_stage",
                        domain="fight_settlement",
                        stage=stage,
                        **fields,
                    ),
                    group_settlement=(
                        shared_group_settlement
                        if self.state.group_lease is not None
                        or getattr(self.state.fight, "rift_wave_state", None)
                        is not None
                        else None
                    ),
                )

                mark_committed_custom_tasks()
                return prepared

            if self.state.group_lease is None:
                self.runtime.COMBAT_SESSIONS.settle_finished(
                    self.state.combat_session,
                    self.state.fight.id,
                    prepare_shared_packets,
                )
            else:

                def prepare_grouped_shared_packets(current_shared):
                    # settle_finished already owns the frozen fight. Acquire
                    # groups here, in the same order as terminal marker
                    # publication, and retain them through the SQL commit.
                    settlement_lock_started = time.monotonic()
                    self.runtime.record(
                        event="persistence_stage",
                        domain="fight_settlement",
                        stage="group_lock_wait",
                        fight_id=self.state.fight.id,
                    )
                    with self.runtime.COMBAT_GROUPS.lock:
                        self.runtime.record(
                            event="persistence_stage",
                            domain="fight_settlement",
                            stage="group_lock_acquired",
                            fight_id=self.state.fight.id,
                            elapsed_ms=round(
                                (time.monotonic() - settlement_lock_started) * 1000, 3
                            ),
                        )
                        return prepare_shared_packets(current_shared)

                self.runtime.COMBAT_SESSIONS.settle_finished(
                    self.state.combat_session,
                    self.state.fight.id,
                    prepare_grouped_shared_packets,
                )
            self.refresh_shared_combat()
            self.drain_shared_combat()
            self.checkpoint_fight("ended")
            self.state.character.update(
                self.refresh_owned_character(
                    self.runtime.STORE.character(
                        self.state.account_id, self.state.character["id"]
                    )
                )
            )
            self.runtime.record(
                event="combat_shared_finished",
                actor_id=self.state.combat_session.character_id,
                fight_id=self.state.fight.id,
                participants=len(shared.participants),
                winner=self.state.fight.winner,
            )
            return

        for actor in self.state.fight.actors.values():
            if actor.hp == 0 and actor.id not in getattr(
                self.state.fight_messages, "_reported_deaths", set()
            ):
                for message_id, payload in self.state.fight_messages.prepare_delivery(
                    death_messages(self.state.fight_messages, actor.id)
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, message_id, payload
                    )
        metadata = {
            self.state.character["id"]: dict(
                kind="player",
                account_id=self.state.account_id,
                name=self.state.character["name"],
                breed=self.state.character["breed"],
                is_male=self.state.character["sex"] == 0,
            ),
        }
        metadata.update(
            {
                m["id"]: dict(kind="monster", ref=m["ref"])
                for m in self.state.TEST_MONSTERS
            }
        )
        from wakfu_server.monster_removal_ecology import finish as finish_world_group
        from wakfu_server import combat_reward_context, reward_policy

        def resolve_fight_reward(db):
            from wakfu_server.rii_training_rewards import is_owned_training
            from wakfu_server.achievements.rii_guardian_contract import (
                is_owned as is_owned_guardian,
            )

            if (
                is_developer_test_fight(db, self.state.fight.id)
                or is_owned_training(self.state.fight, self.state.character["id"])
                or is_owned_guardian(self.state.fight, self.state.character["id"])
            ):
                from wakfu_server.combat_rewards import Policy

                return Policy()
            context = combat_reward_context.build_context(
                self.state.fight, self.state.character, reward_monsters
            )
            return reward_policy.resolve(
                self.runtime.STORE,
                db,
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
                fight_id=self.state.fight.id,
                context=context,
            ).policy

        def resolve_fight_loot(db, reward):
            from wakfu_server.rii_training_rewards import is_owned_training
            from wakfu_server.achievements.rii_guardian_contract import (
                is_owned as is_owned_guardian,
            )

            if (
                is_developer_test_fight(db, self.state.fight.id)
                or is_owned_training(self.state.fight, self.state.character["id"])
                or is_owned_guardian(self.state.fight, self.state.character["id"])
            ):
                return {"loots": [], "packets": []}
            from wakfu_server import combat_drops, combat_drop_delivery
            from wakfu_server.inventory_move import synchronization
            from wakfu_server.inventory_items import equipment_inventory

            actor = self.state.fight.actors[self.state.character["id"]]
            batch = combat_drops.resolve(
                self.runtime.STORE,
                db,
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
                fight_id=self.state.fight.id,
                monsters=[
                    {"actor_id": m["id"], "reference": m["ref"]}
                    for m in reward_monsters
                ],
                prospecting_bonus=combat_drops.native_prospection_bonus(actor),
                shop_consumable_factor=combat_drops.native_shop_drop_factor(actor),
                can_loot=True,
                fight_context=combat_reward_context.build_drop_context(
                    self.state.fight, self.state.character, reward_monsters
                ),
            )
            from wakfu_server.quest_inventory import changes as quest_changes

            before_loot = self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"], db
            )
            combat_drop_delivery.apply(self.runtime.STORE, db, batch)
            saved = self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"], db
            )
            return {
                "loots": combat_drops.report_loots(batch),
                "packets": [
                    *quest_changes(before_loot, saved),
                    synchronization(saved),
                    equipment_inventory(saved),
                    *combat_drop_delivery.temporary_updates(
                        db, self.state.character["id"]
                    ),
                ],
            }

        def settle_individual_group(db, lease, defeated):
            developer_result = finish_developer_test_group(
                db, self.runtime.COMBAT_GROUPS, lease
            )
            if developer_result is not None:
                return developer_result
            outcome = finish_world_group(
                self.runtime.STORE,
                self.runtime.COMBAT_GROUPS,
                lease,
                character_id=self.state.character["id"],
                defeated=defeated,
                db=db,
            )
            if outcome["applied"] and defeated:
                from wakfu_server.monster_corpses import retain

                retain(db, self.state.fight, reward_monsters)
            return outcome

        with self.runtime.COMBAT_GROUPS.lock:
            result = prepare_finish(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.fight_messages,
                metadata,
                duration_ms=int(
                    (time.monotonic() - self.state.fight_started_at) * 1000
                ),
                fight_instance_id=self.state.fight.id,
                policy_resolver=resolve_fight_reward,
                loot_resolver=resolve_fight_loot,
                progression_resolver=settle_achievements,
                groups=self.runtime.COMBAT_GROUPS,
                group_lease=self.state.group_lease,
                group_settlement=settle_individual_group,
            )
        mark_committed_custom_tasks()
        # A terminal checkpoint must not precede the reward transaction.
        self.checkpoint_fight("ended")
        self.state.character.update(
            {
                key: result["character"][key]
                for key in (
                    "xp",
                    "kamas",
                    "level",
                    "hp",
                    "max_hp",
                    "hp_damage",
                    "health_dead",
                    "ecology_value",
                    "ecology_revision",
                    "captured_roster",
                )
            }
        )
        if result["reward"] is not None:
            # Update the existing wallet model, including an already-open UI.
            # Bootstrap wallet packets alone replace rather than refresh it.
            self.runtime.send(
                self.state.connection,
                self.state.service,
                12753,
                self.runtime.wire.account_kamas_update(self.state.character["kamas"]),
            )
        for message_id, payload in self.state.fight_messages.prepare_delivery(
            result["packets"]
        ):
            self.runtime.send(
                self.state.connection, self.state.service, message_id, payload
            )
        if result["reward"] is not None:
            self.runtime.record(
                event="combat_reward_committed",
                actor_id=self.state.character["id"],
                fight_id=self.state.fight.id,
                xp=result["reward"]["xp"],
                kamas=result["reward"]["kamas"],
                awarded=result["reward"]["awarded"],
            )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *self.state.fight_messages._flush(),
        )
        self.runtime.record(
            event="combat_finished",
            fight_id=self.state.fight.id,
            winner=self.state.fight.winner,
        )

    def area_boundary_provider(self, preview, **boundary):
        from wakfu_server.combat_server_spell import prepare_server_turn_start
        from wakfu_server.spells import default_deck

        if self.state.combat_session is not None:
            characters, decks = self.runtime.COMBAT_SESSIONS.player_sources(preview)
            source = characters.get(
                boundary.get("actor_id"), next(iter(characters.values()))
            )
            deck = decks[source["id"]]
        else:
            source = self.state.character
            stored = (
                self.state.character.get("builds", {})
                .get(self.state.character.get("active_build_index", 0), {})
                .get("deck")
            )
            deck = (
                bytes.fromhex(stored) if stored else default_deck(self.state.character)
            )
        return prepare_server_turn_start(
            source,
            self.state.TEST_MONSTERS_BY_ID,
            preview,
            deck,
            player_characters=(
                characters if self.state.combat_session is not None else None
            ),
            deck_blobs=decks if self.state.combat_session is not None else None,
            native_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
            area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1",
            **boundary,
        )

    def area_movement_provider(self, preview, **boundary):
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.spells import default_deck

        if self.state.combat_session is not None:
            characters, decks = self.runtime.COMBAT_SESSIONS.player_sources(preview)
            source = characters.get(
                boundary.get("actor_id"), next(iter(characters.values()))
            )
            deck = decks[source["id"]]
        else:
            source = self.state.character
            stored = (
                self.state.character.get("builds", {})
                .get(self.state.character.get("active_build_index", 0), {})
                .get("deck")
            )
            deck = (
                bytes.fromhex(stored) if stored else default_deck(self.state.character)
            )
        return prepare_area_movement(
            source,
            self.state.TEST_MONSTERS_BY_ID,
            preview,
            deck,
            player_characters=(
                characters if self.state.combat_session is not None else None
            ),
            deck_blobs=decks if self.state.combat_session is not None else None,
            **boundary,
        )

    def pass_test_monster_turn(self):
        if self.state.combat_session is None or self.state.fight is None:
            return self.run_test_monster_turn()
        from wakfu_server.combat_turn_guard import run_shared_npc_attempt

        shared = self.runtime.COMBAT_SESSIONS.registry.lookup(self.state.fight.id)
        return run_shared_npc_attempt(
            shared,
            self.run_test_monster_turn,
            lambda identity, error: self.runtime.record(
                event="combat_npc_turn_retry_pending",
                fight_id=shared.fight.id,
                actor_id=identity[0],
                turn_id=identity[1],
                exception_type=type(error).__name__,
                reason=self.runtime.redact(str(error)),
                retry_delay_seconds=2,
            ),
        )

    @PROFILER.profile("combat.ai_turn")
    def run_test_monster_turn(self):
        import hashlib
        import pathlib
        import sys
        import types

        directory = self.runtime.ROOT / "wakfu_server" / "wakia_bridge"
        path = directory / "world_loader.py"
        source = path.read_bytes()
        name = "_wakfu_world_ai_loader_" + hashlib.sha256(source).hexdigest()
        loader = sys.modules.get(name)
        if loader is None:
            candidate = types.ModuleType(name)
            candidate.__file__ = str(path)
            exec(compile(source, str(path), "exec"), candidate.__dict__)
            loader = sys.modules.setdefault(name, candidate)
        entry = loader.load_entry(directory)
        for _ in entry(
            self.state.fight_messages, world_context=self.ai_world_context()
        ):
            pass

    def consume_command_combat_recovery(self, *, bootstrap=True):
        """Consume cancellation only at a socket action/idle boundary."""
        if self.state.character is None:
            return False
        from wakfu_server.combat_command_recovery import take_cancelled
        from wakfu_server.combat_shared import Session

        owner = self.state.combat_session or Session(
            self.state.account_id,
            self.state.character["id"],
            self.state.generation,
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
        )
        pending = take_cancelled(self.runtime.COMBAT_SESSIONS.registry, owner)
        if pending is None:
            return False
        self.state.publication_recovery_shared = pending
        if bootstrap:
            return self.continue_aborted_publication_recovery()
        return self.recover_aborted_publication_cohort(bootstrap=False)

    def command_recovery_holds_request(self, opcode, body=None):
        """Drop stale combat actions but keep chat after completed world recovery."""
        recovering = self.consume_command_combat_recovery()
        if not recovering:
            recovering = self.continue_aborted_publication_recovery()
        if not recovering:
            return False
        if opcode == 12925 and self.state.aborted_native_return is not None:
            return False
        if (
            opcode == 12366
            and body is not None
            and self.state.aborted_native_return is not None
            and self.state.aborted_native_return.command is None
        ):
            from wakfu_server.combat_return_command import PendingEmergencyCommand

            self.state.aborted_native_return.require(
                self.state.account_id, self.state.generation, self.state.character["id"]
            )
            command = PendingEmergencyCommand()
            identity = (
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
            if command.retain(opcode, body, identity):
                self.state.aborted_native_return.command = command.take(
                    identity,
                    valid_session=lambda: self.runtime.STORE.current_character_session(
                        *identity
                    ),
                )
        return not (
            opcode == 12366
            and self.state.fight is None
            and self.state.combat_session is None
            and self.state.publication_recovery_shared is None
        )

    def attach_command_combat(self):
        """Bind selected emergency custody without publishing a fight constructor."""
        from wakfu_server.combat_command_recovery import bind_selected
        from wakfu_server.combat_shared import Session

        shared = self.runtime.COMBAT_SESSIONS.lookup_character(
            self.state.character["id"]
        )
        if shared is None:
            return None
        owner = Session(
            self.state.account_id,
            self.state.character["id"],
            self.state.generation,
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
        )
        shared = bind_selected(
            self.runtime.STORE,
            self.runtime.COMBAT_SESSIONS.registry,
            owner,
            self.runtime.CHECKPOINT_WRITER,
        )
        self.state.combat_session, self.state.fight, self.state.fight_messages = (
            owner,
            shared.fight,
            shared.runtime,
        )
        self.state.group_lease = shared.group_lease
        context = shared.join_context or {}
        self.state.TEST_MONSTERS_BY_ID = getattr(
            self.state.fight, "rift_monsters", context.get("monsters", {})
        )
        self.state.TEST_MONSTERS = tuple(self.state.TEST_MONSTERS_BY_ID.values())
        self.state.TEST_GROUP_KEY = context.get("group_key")
        self.state.fight_started_at = context.get("fight_started_at", time.monotonic())
        self.state.checkpoint_id, self.state.checkpoint_revision = (
            self.state.fight.id,
            shared.checkpoint_revision,
        )
        self.state.checkpoint_terminal = shared.checkpoint_terminal
        return shared

    def recover_expired_combat_presentation(self, *, blocking=True):
        """Return an exhausted owned reconnect through durable native cleanup."""
        if (
            self.state.reconnect_expiry_recovery["running"]
            or self.state.combat_session is None
            or self.state.fight is None
        ):
            return False
        try:
            shared = self.runtime.COMBAT_SESSIONS.registry.lookup(
                self.state.fight.id, blocking=blocking
            )
        except ValueError:
            return False  # Existing retired-fight recovery owns this branch.
        if shared is None or not shared.lock.acquire(blocking=blocking):
            return False
        try:
            pending = shared.reconnect_presentations.get(self.state.account_id)
            if (
                pending is None
                or pending.session != self.state.combat_session
                or shared.participants.get(self.state.account_id)
                != self.state.combat_session
                or self.state.combat_session.generation != self.state.generation
                or self.state.character is None
                or self.state.combat_session.character_id != self.state.character["id"]
            ):
                return False
            reason = pending.recovery_reason()
            if reason is None:
                return False
        finally:
            shared.lock.release()
        now = time.monotonic()
        token = (shared.fight.id, self.state.generation)
        if (
            token == self.state.reconnect_expiry_recovery["notice"]
            and now < self.state.reconnect_expiry_recovery["due"]
        ):
            return True
        self.state.reconnect_expiry_recovery["due"] = now + 1.0
        if self.state.reconnect_expiry_recovery["notice"] != token:
            self.state.reconnect_expiry_recovery["notice"] = token
            self.runtime.record(
                event="combat_reconnect_automatic_recovery",
                fight_id=shared.fight.id,
                actor_id=self.state.character["id"],
                reason=reason,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    "La sincronización del combate no pudo recuperarse. "
                    "Estamos cerrando el combate para regresar al mapa; "
                    "el progreso guardado se conserva."
                ),
            )
        self.state.reconnect_expiry_recovery["running"] = True
        try:
            self.emergency_exit_current_combat(expired_presentation=pending)
            self.continue_aborted_publication_recovery()
        except (
            ValueError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
            TimeoutError,
        ) as error:
            # Keep the selected socket and exact recovery pending when the
            # durable cancellation or return-position fence needs another try.
            self.runtime.record(
                event="combat_reconnect_automatic_recovery_pending",
                fight_id=shared.fight.id,
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        finally:
            self.state.reconnect_expiry_recovery["running"] = False
        return True

    def combat_reconnect_expiry_boundary(self, operation):
        """Recover only an expiry that raced the socket's preceding check."""
        from functools import wraps
        from wakfu_server.combat_reconnect_birth_stage import (
            ReconnectPresentationExpired,
        )

        @wraps(operation)
        def invoke(*args, **kwargs):
            try:
                return operation(*args, **kwargs)
            except ReconnectPresentationExpired:
                if self.recover_expired_combat_presentation(
                    blocking=kwargs.get("blocking", True)
                ):
                    return False
                raise

        return invoke

    def emergency_exit_current_combat(self, *, expired_presentation=None):
        """Commit an explicit escape before travel, independently of native ACKs."""
        from wakfu_server.combat_command_recovery import (
            bind_selected,
            cancel,
            release_settled,
            take_cancelled,
        )

        if self.state.combat_session is not None:
            pending = take_cancelled(
                self.runtime.COMBAT_SESSIONS.registry, self.state.combat_session
            )
            if pending is not None:
                self.state.publication_recovery_shared = pending
                self.recover_aborted_publication_cohort(bootstrap=False)
                return True
        shared = self.runtime.COMBAT_SESSIONS.lookup_character(
            self.state.character["id"]
        )
        if shared is None:
            shared = self.deferred_native_combat_attachment()
        if shared is None:
            return False
        if expired_presentation is not None:
            with shared.lock:
                if (
                    shared.reconnect_presentations.get(self.state.account_id)
                    is not expired_presentation
                    or expired_presentation.session
                    != shared.participants.get(self.state.account_id)
                    or expired_presentation.recovery_reason() is None
                ):
                    return False
        owner = shared.participants.get(self.state.account_id)
        if owner is None or owner.character_id != self.state.character["id"]:
            raise ValueError("La sesión seleccionada cambió antes de salir del combate")
        if owner.generation != self.state.generation:
            from wakfu_server.combat_shared import Session

            owner = Session(
                self.state.account_id,
                self.state.character["id"],
                self.state.generation,
                self.state.character["map_id"],
                self.state.character.get("instance_id", 0),
            )
            shared = bind_selected(
                self.runtime.STORE,
                self.runtime.COMBAT_SESSIONS.registry,
                owner,
                self.runtime.CHECKPOINT_WRITER,
            )
        if self.state.character["id"] in (
            getattr(shared, "publication_recovery_aborted", None) or {}
        ):
            self.state.publication_recovery_shared = shared
            return self.recover_aborted_publication_cohort(bootstrap=False)
        if not self.runtime.CHECKPOINT_WRITER.flush_fight(shared.fight.id, timeout=10):
            raise ValueError(
                "La escritura del combate sigue pendiente; vuelve a intentar salir"
            )
        if getattr(shared, "is_duel", False):
            if self.state.combat_session is None:
                self.attach_command_combat()
            if shared.fight.phase != "finished":
                self.runtime.COMBAT_SESSIONS.registry.forfeit_duel(
                    owner, reason="defeat"
                )
            if expired_presentation is not None and shared.fight.phase == "finished":
                # The ordinary duel forfeit is terminal now. Its abandoned
                # private birth queue must not gate the committed result path.
                with shared.lock:
                    if (
                        shared.reconnect_presentations.get(self.state.account_id)
                        is expired_presentation
                    ):
                        shared.reconnect_presentations.pop(self.state.account_id)
            if not shared.settlement_ready:
                self.refresh_shared_combat()
                self.complete_test_fight()
        if shared.settlement_ready:
            result = release_settled(
                self.runtime.STORE, self.runtime.COMBAT_SESSIONS.registry, owner
            )
        else:
            result = cancel(
                self.runtime.STORE,
                self.runtime.COMBAT_SESSIONS.registry,
                owner,
                groups=self.runtime.COMBAT_GROUPS,
                checkpoint_writer=self.runtime.CHECKPOINT_WRITER,
            )
            marker = self.runtime.EXTERNAL_FIGHT_MARKERS.remove(shared.fight.id)
            if marker is not None:
                self.runtime.WORLD.emit_location(
                    shared.map_id,
                    shared.instance_id,
                    *marker,
                    exclude_sessions=tuple(
                        (participant.character_id, participant.generation)
                        for participant in shared.participants.values()
                    ),
                )
            if shared.group_lease is not None:
                self.publish_full_abandon_group(shared, {"group_restored": True})
        if result is None:
            return False
        take_cancelled(self.runtime.COMBAT_SESSIONS.registry, owner)
        self.state.publication_recovery_shared = result["shared"]
        return self.recover_aborted_publication_cohort(bootstrap=False)

    def shared_action_incident(
        self,
        runtime,
        action_type,
        body,
        source,
        owner_deck,
        characters,
        decks,
        *,
        actor_id=None,
        turn_id=None,
    ):
        if not os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
            return nullcontext()
        try:
            from wakfu_server.combat_shared_incident_capture import (
                current_shared_incident,
                shared_incidents_suppressed,
            )

            if shared_incidents_suppressed():
                return nullcontext()
            from wakfu_server.combat_incident_capture import (
                incident_enabled,
                incident_scope,
            )

            if not incident_enabled():
                return nullcontext()
            # End-turn obtains authority through its actual runtime providers.
            # Do not add a diagnostic Store read that gameplay never performs;
            # those providers record their consumed sources when invoked.
            action = dict(
                type=action_type, owner_id=self.state.combat_session.account_id
            )
            if action_type == "end_turn":
                action.update(actor_id=actor_id, turn_id=turn_id)
            else:
                action["body"] = body
                if action_type != "move":
                    action["critical"] = (
                        False
                        if action_type == "player_unarmed"
                        else (
                            None
                            if self.runtime.COMBAT_TEST_CRITICAL_BRANCH == "auto"
                            else self.runtime.COMBAT_TEST_CRITICAL_BRANCH == "critical"
                        )
                    )
            # This records the actual connected operation. Its providers are not
            # accredited as equivalent to the isolated offline authority recipe.
            inputs = dict(
                authority_recipe="observed-live-server-v1",
                map_id=(
                    self.state.combat_session.map_id
                    if source is None
                    else source["map_id"]
                ),
                native_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
                area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1")
                == "1",
                recipient_evidence="intended-participant-accounts-not-confirmed-routing",
                client_request_body=body,
            )
            if characters is not None:
                inputs.update(
                    character=source,
                    monsters=self.state.TEST_MONSTERS_BY_ID,
                    deck_blob=owner_deck,
                    player_characters=characters,
                    deck_blobs=decks,
                )
            outer = current_shared_incident()
            if outer is not None:
                outer.attach(
                    runtime,
                    action,
                    inputs,
                    session=dict(requester=self.state.combat_session),
                )
                return nullcontext(outer)
            return incident_scope(
                runtime,
                action,
                inputs,
                session=dict(requester=self.state.combat_session),
                recipients=tuple(
                    sorted(
                        {
                            actor.owner_id
                            for actor in runtime.fight.actors.values()
                            if actor.owner_id is not None
                        }
                    )
                ),
            )
        except Exception as error:
            # Diagnostics must never replace the gameplay result or exception.
            try:
                self.runtime.record(
                    event="combat_incident_setup_failed",
                    error_type=type(error).__name__,
                )
            except Exception:
                pass
            return nullcontext()

    def current_combat_stats(self, actor, state=None):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_input_observation import observe_fact

        current_fight = self.state.fight if state is None else state
        if actor.id in getattr(current_fight, "native_summon_registrations", {}):
            from wakfu_server.combat_summon_stats import registered_summon_stats

            stats = registered_summon_stats(
                actor, current_fight, self.state.character["map_id"]
            )
            observe_fact("current_combat_stats.summon_actor", actor.id)
            observe_fact("current_combat_stats.summon", stats)
            return stats
        if getattr(actor, "native_summon_source", None) is not None:
            raise ValueError("Summon stats require current native registration")
        if actor.effect_stats is not None:
            if (
                actor.effect_maxima is None
                or 4 not in actor.effect_stats
                or 4 not in actor.effect_maxima
            ):
                raise ValueError("Missing authoritative combat WP snapshot")
            wp_current = actor.effect_stats[4]
            wp_maximum = actor.effect_maxima[4]
        else:
            raise ValueError("Missing authoritative combat WP snapshot")
        companion_source = getattr(current_fight, "native_companion_sources", {}).get(
            str(actor.id)
        )
        if companion_source is not None:
            from wakfu_server.combat_companions import registered_source

            registered_source(current_fight, actor, companion_source)
            return actual_monster_actor_stats(
                companion_source,
                actor,
                current_fight.id,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
                fight=current_fight,
            )
        if actor.controlled:
            source = (
                self.runtime.STORE.character(actor.owner_id, actor.id)
                if self.runtime.COMBAT_TEST
                else self.state.character
            )
            observe_fact("current_combat_stats.player_source", source)
            stats = actual_actor_stats(
                source,
                actor,
                self.state.fight.id,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
            )
            observe_fact("current_combat_stats.player", stats)
            return stats
        source = self.state.TEST_MONSTERS_BY_ID[actor.id]
        observe_fact("current_combat_stats.monster_source", source)
        stats = actual_monster_actor_stats(
            source,
            actor,
            self.state.fight.id,
            wp_current=wp_current,
            wp_maximum=wp_maximum,
            direction=3,
        )
        observe_fact("current_combat_stats.monster", stats)
        return stats

    @PROFILER.profile("combat.refresh")
    def refresh_shared_combat(self, *, blocking=True):
        if self.state.combat_session is None or self.state.fight is None:
            return None
        if self.recover_expired_combat_presentation(blocking=blocking):
            return False
        try:
            shared = self.runtime.COMBAT_SESSIONS.registry.lookup(
                self.state.fight.id, blocking=blocking
            )
        except ValueError:
            retired = self.state.publication_recovery_shared
            if self.continue_aborted_publication_recovery():
                return retired
            raise
        if shared is None:
            return False
        self.state.fight = shared.fight
        self.state.fight_messages = shared.runtime
        receipt = shared.withdrawals.get(self.state.combat_session.account_id)
        if (
            getattr(shared, "full_abandon_owner", None) is not None
            and receipt is not None
            and receipt["session"] == self.state.combat_session
            and not receipt.get("full_abort_requester", False)
            and self.state.combat_session.account_id not in shared.returned
        ):
            self.state.pve_withdrawal_pending = receipt
            self.state.fight = self.state.fight_messages = None
            self.state.combat_session = self.state.group_lease = None
            self.state.loaded = False
            return shared  # Native12925 now selects the existing private-return branch.
        self.state.group_lease = getattr(shared, "group_lease", self.state.group_lease)
        context = shared.join_context or {}
        placement_origin = context.get("fight_started_at")
        if (
            self.state.fight.phase == "placement"
            and not shared.disconnect_abort_pending
            and placement_origin is not None
            and placement_origin != self.state.fight_started_at
        ):
            # Another owner may have completed the paused cohort. Every socket
            # must use the same resumed placement origin, including early waiters.
            self.state.fight_started_at = placement_origin
            self.state.placement_deadline.start(
                self.state.fight.id,
                context.get("duration_ms"),
                placement_origin,
                native=self.state.is_owned_guardian_fight(
                    self.state.fight, self.state.character["id"]
                ),
            )
        monsters = getattr(self.state.fight, "rift_monsters", context.get("monsters"))
        if monsters is not None:
            if getattr(self.state.fight, "rift_wave_state", None) is not None:
                context["monsters"] = monsters
            self.state.TEST_MONSTERS_BY_ID = monsters
            self.state.TEST_MONSTERS = tuple(monsters.values())
        return shared

    def publish_full_abandon_group(self, shared, result):
        if not result.get("group_restored") or shared.group_lease is None:
            return
        from wakfu_server.ecology_admin import current_available
        from wakfu_server.combat_monster_world import spawn_group

        key = shared.group_lease[0]
        members = current_available(self.runtime.STORE, key)
        if members:
            self.runtime.publish_available_group(
                key, members, exclude_generation=self.state.generation
            )

    def publish_external_marker(self, shared):
        if shared is None:
            return
        with shared.lock:
            return self._publish_external_marker_locked(shared)

    def _publish_external_marker_locked(self, shared):
        """Publish public-world marker deltas, never to fight participants."""
        if (
            not self.runtime.COMBAT_TEST
            or shared is None
            or getattr(shared, "is_duel", False)
        ):
            return
        fight = getattr(shared, "fight", None)
        if fight is None:
            return

        def public_member_packet(actor, source_fight):
            from wakfu_server.combat_multiplayer_wire import added
            from wakfu_server.combat_public_fighter_stats import (
                public_player_fighter_stats,
            )

            from wakfu_server.combat_actor import actual_actor_stats, actor_effects
            from wakfu_server.breed_resources import live_wp

            companion_source = getattr(
                source_fight, "native_companion_sources", {}
            ).get(str(actor.id))
            if companion_source is not None:
                from wakfu_server.combat_companions import registered_source
                from wakfu_server.combat_actor import actual_monster_actor_stats

                registered_source(source_fight, actor, companion_source)
                wp_current, wp_maximum = live_wp(source_fight, actor.id)
                return added(
                    source_fight.id,
                    actor.id,
                    actor_type=5,
                    team=actor.team,
                    stats=actual_monster_actor_stats(
                        companion_source,
                        actor,
                        source_fight.id,
                        wp_current=wp_current,
                        wp_maximum=wp_maximum,
                        fight=source_fight,
                    ),
                    effects=actor_effects(),
                )

            # A complete native snapshot already owns current gear/resources.
            # Legacy actors without it retain the full character reducer.
            source = (
                self.runtime.STORE.combat_public_character(actor.owner_id, actor.id)
                if getattr(actor, "effect_stats", None) is not None
                else self.runtime.STORE.character(actor.owner_id, actor.id)
            )
            wp_current, wp_maximum = live_wp(source_fight, actor.id)
            stats = actual_actor_stats(
                source,
                actor,
                source_fight.id,
                fight=source_fight,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
            )
            public = public_player_fighter_stats(
                stats, actor_id=actor.id, fight_id=source_fight.id
            )
            # Native ckT uses fighter stats for external membership; it does
            # not replay cvg effects or SQ. Preserve the existing canonical
            # empty effect descriptor instead of exposing owned retained rows.
            return added(
                source_fight.id,
                actor.id,
                actor_type=0,
                team=actor.team,
                stats=public,
                effects=actor_effects(),
            )

        previous_location = self.runtime.EXTERNAL_FIGHT_MARKERS.location(fight.id)
        if fight.phase == "finished":
            committed_abandon = (
                getattr(getattr(shared, "runtime", None), "abandon_owner", None)
                is not None
                and fight.winner is None
            )
            # A lethal action can drain before the group tombstone commits.
            # Keep the marker until settlement so terminal world removal is
            # derived from durable state rather than an uncommitted preview.
            # Abandonment commits its own durable abort before setting
            # abandon_owner; it deliberately has no reward settlement.
            if not getattr(shared, "settlement_ready", False) and not committed_abandon:
                return
            packet = self.runtime.EXTERNAL_FIGHT_MARKERS.remove(fight.id)
        else:
            try:
                packet = self.runtime.EXTERNAL_FIGHT_MARKERS.update(
                    shared, member_packet=public_member_packet
                )
            except (KeyError, TypeError, ValueError) as error:
                self.runtime.record(
                    event="combat_external_marker_publish_failed",
                    fight_id=fight.id,
                    reason=str(error),
                )
                return
        if packet is None or packet[0] == 12233:
            # Existing native contexts need an incremental member add; a
            # second13753 would replace their retained external model.
            exclusions = frozenset(
                (owner.character_id, owner.generation)
                for owner in (
                    *getattr(shared, "participants", {}).values(),
                    *self.runtime.SPECTATORS.sessions(fight.id),
                )
            )
            with self.runtime.WORLD.lock:
                peers = tuple(
                    peer
                    for lease, peer, owner in self.runtime.WORLD.players.values()
                    if not getattr(peer, "is_bot_peer", False)
                    and (owner["map_id"], owner.get("instance_id", 0))
                    == (shared.map_id, shared.instance_id)
                    and (owner["id"], lease) not in exclusions
                )
            for peer in peers:
                try:
                    with peer.write_lock:
                        scope = peer.native_instance_scope()
                        phases = peer.marker_publications.snapshot(scope)
                        if fight.id not in phases:
                            continue
                        delta = self.runtime.EXTERNAL_FIGHT_MARKERS.world_snapshots(
                            shared.map_id,
                            shared.instance_id,
                            known_phases=phases,
                            known_rosters=peer.marker_publications.roster_snapshot(
                                scope
                            ),
                            unbound_members=peer.marker_publications.unbound_snapshot(
                                scope
                            ),
                            only_fight_id=fight.id,
                        )
                        if packet is not None:
                            # The existing uniform transition below follows this
                            # roster repair in the SAME publication pass.
                            delta = tuple(row for row in delta if row[0] != 12233)
                        self.runtime.WORLD._send_batch(peer, delta)
                except (KeyError, TypeError, ValueError) as error:
                    self.runtime.record(
                        event="combat_external_marker_recipient_failed",
                        fight_id=fight.id,
                        target_connection_id=getattr(peer, "trace_id", None),
                        reason=str(error),
                    )
            if packet is None:
                return
        if packet[0] == 12238 and previous_location is not None:
            map_id, instance_id = previous_location
        else:
            map_id, instance_id = shared.map_id, shared.instance_id
        participant_sessions = frozenset(
            (session.character_id, session.generation)
            for session in getattr(shared, "participants", {}).values()
        )
        observer_sessions = frozenset(
            (session.character_id, session.generation)
            for session in self.runtime.SPECTATORS.sessions(fight.id)
        )
        try:
            # The native marker resolves its NPC leader in the world actor
            # registry. A claimed group is absent from available() snapshots.
            # Publish its authoritative descriptor before announcing the fight.
            if packet[0] == 13753:
                actor_packet = self.runtime.EXTERNAL_FIGHT_MARKERS.actor_packet(
                    fight.id
                )
                if actor_packet is None:
                    raise ValueError("External fight marker lacks its NPC snapshot")
                packets = (actor_packet, packet)
            else:
                packets = (packet,)
            # Live markers only enqueue an already-owned actor/marker batch;
            # they neither inspect nor modify world groups. Do not wait behind
            # unrelated ecology transactions. Terminal snapshots still require
            # the group fence through their final ordered publication.
            from contextlib import nullcontext

            marker_fence = (
                self.runtime.COMBAT_GROUPS.lock
                if fight.phase == "finished"
                else nullcontext()
            )
            with marker_fence:
                if (
                    fight.phase == "finished"
                    and getattr(shared, "settlement_ready", False)
                    and getattr(shared, "group_lease", None)
                ):
                    from wakfu_server.combat_world_group_cleanup import (
                        defeated_snapshot,
                    )

                    with self.runtime.STORE.connection() as db:
                        packets += defeated_snapshot(
                            db, map_id, instance_id, lease=shared.group_lease
                        )
                    with self.runtime.WORLD.lock:
                        corpse_peers = tuple(
                            peer
                            for session_generation, peer, owner in self.runtime.WORLD.players.values()
                            if (owner["map_id"], owner.get("instance_id", 0))
                            == (map_id, instance_id)
                            and (owner["id"], session_generation)
                            not in participant_sessions | observer_sessions
                        )
                    packets += self.runtime.monster_corpse_snapshot(
                        map_id, instance_id, peers=corpse_peers
                    )
                delivered_recipients = self.runtime.WORLD.emit_location_batch(
                    map_id,
                    instance_id,
                    packets,
                    exclude_sessions=participant_sessions | observer_sessions,
                )
            self.runtime.record(
                event="combat_external_marker_published",
                fight_id=fight.id,
                map_id=map_id,
                instance_id=instance_id,
                opcode=packet[0],
                delivered_recipients=delivered_recipients,
            )
        except (KeyError, TypeError, ValueError) as error:
            self.runtime.record(
                event="combat_external_marker_publish_failed",
                fight_id=fight.id,
                reason=str(error),
            )

    @PROFILER.profile("combat.event_delivery")
    def drain_shared_combat(self, *, blocking=True):
        if self.state.combat_session is None or self.state.fight is None:
            return
        if self.recover_expired_combat_presentation(blocking=blocking):
            return False

        delivered_batches = {}

        def deliver(owner, batches):
            for batch in batches:
                if batch.public_events:
                    delivered_batches.setdefault(batch.sequence, []).append(
                        batch.packets
                    )
            packets = tuple(packet for batch in batches for packet in batch.packets)
            if not packets:
                return
            if any(packet[0] == 12847 for packet in packets):
                # Membership is committed before outboxes drain. Replay icons
                # after the native fight constructor for late join/reconnect.
                from wakfu_server.combat_tactical_markers import snapshots

                packets += snapshots(
                    self.runtime.COMBAT_SESSIONS.registry, owner, self.state.fight.id
                )
            if (
                owner.account_id == self.state.combat_session.account_id
                and owner.generation == self.state.combat_session.generation
                and owner.character_id == self.state.combat_session.character_id
            ):
                self.runtime.send_batch(
                    self.state.connection, self.state.service, packets
                )
                if any(opcode == 13652 for opcode, _ in packets):
                    self.publish_admitted_rii_lesson_guide()
            else:
                self.runtime.WORLD.send_batch_to(
                    owner.character_id, owner.generation, packets
                )

        if (
            self.runtime.COMBAT_SESSIONS.dispatch_connected(
                self.state.fight.id, deliver, blocking=blocking
            )
            is None
        ):
            return False
        shared = self.runtime.COMBAT_SESSIONS.registry.lookup(self.state.fight.id)
        self.publish_external_marker(shared)
        if delivered_batches:
            from wakfu_server.combat_spectator_events import public_combat_events

            self.publish_spectator_state(
                shared,
                tuple(
                    packet
                    for sequence in sorted(delivered_batches)
                    for packet in public_combat_events(delivered_batches[sequence])
                ),
            )
        from wakfu_server.friendly_duel_bot_ack import acknowledge_delivered

        # A headless duel bot has no client to acknowledge its delivered
        # presentation. Human participants still ACK their own packets.
        if acknowledge_delivered(self.runtime.COMBAT_SESSIONS, shared):
            self.refresh_shared_combat()
            return self.drain_shared_combat(blocking=blocking)
        return True

    def spectator_session_for_current_character(self):
        if (
            self.state.account_id is None
            or self.state.generation is None
            or self.state.character is None
        ):
            raise ValueError("A loaded character session is required")
        return self.runtime.ObserverSession(
            self.state.account_id,
            self.state.character["id"],
            self.state.generation,
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
        )

    def spectator_snapshot(self, shared):
        from wakfu_server.combat_spectator_snapshot import current_snapshot

        owner_session = self.spectator_session_for_current_character()
        deadline_ms = None
        if shared.fight.phase == "active":
            deadline = getattr(shared.runtime, "turn_deadline", None)
            if deadline is None:
                raise ValueError("Active fight has no current native turn deadline")
            deadline_ms = int(
                time.time() * 1000 + max(0.0, deadline - time.monotonic()) * 1000
            )
        packets = current_snapshot(
            shared.fight,
            shared,
            actor_payload=lambda current_fight, actor: self.runtime.COMBAT_SESSIONS.actor_payload(
                current_fight, actor, owner_session
            ),
            deadline_ms=deadline_ms,
            public_pvp_duel=self.public_objectives_duel(shared),
        )
        if getattr(shared.fight, "rift_wave_state", None) is not None:
            from wakfu_server.rift_combat_adapter import world_snapshot

            return tuple(world_snapshot(shared.fight)) + tuple(packets)
        return packets

    def public_objectives_duel(self, shared):
        if not getattr(shared, "is_duel", False):
            return False
        from wakfu_server.custom_tasks.external import enabled

        if not enabled():
            return False
        with self.runtime.STORE.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM objectives_pvp_events WHERE fight_id=%s "
                    "AND status IN ('in_fight','completed','expired')",
                    (shared.fight.id,),
                ).fetchone()
                is not None
            )

    def spectator_waiting_for_ack(self, shared):
        runtime = getattr(shared, "runtime", None)
        awaiting = getattr(runtime, "awaiting_ack", None)
        return (
            shared.fight.phase == "active"
            and awaiting is not None
            and getattr(runtime, "turn_deadline", None) is None
            and getattr(getattr(shared, "ack", None), "turn", None) == awaiting
        )

    @PROFILER.profile("combat.spectator_publish")
    def publish_spectator_state(
        self, shared, event_packets=(), *, force_snapshot=False
    ):
        """Publish current state plus only the shared batches after its cursor."""
        if (
            not self.runtime.COMBAT_TEST
            or shared is None
            or (
                getattr(shared, "is_duel", False)
                and not self.public_objectives_duel(shared)
            )
        ):
            return
        if (getattr(shared, "join_context", None) or {}).get(
            "world_scene_owner"
        ) is not None:
            return
        try:
            # Owners may drain concurrently; snapshot and cursor share the FSM lock.
            with shared.lock:
                from wakfu_server.combat_abandon import (
                    committed_abandon_team,
                    aborted_terminal_packets,
                )

                abandon_team = (
                    committed_abandon_team(getattr(shared, "runtime", None))
                    if shared.fight.phase == "finished"
                    else None
                )
                if (
                    shared.fight.phase == "finished"
                    and not getattr(shared, "settlement_ready", False)
                    and abandon_team is None
                ):
                    # Preserve lethal action/death delivery, but do not let the
                    # client return before the durable NPC tombstone is committed.
                    current = self.runtime.SPECTATORS.fights.get(shared.fight.id)
                    pending_events = tuple(
                        packet for packet in event_packets if packet[0] != 12238
                    )
                    if current is not None and pending_events:
                        self.runtime.SPECTATORS.publish_events(
                            shared.fight.id,
                            revision=max(shared.sequence, current.revision + 1),
                            event_packets=pending_events,
                        )
                    return
                if shared.fight.phase == "finished":
                    from copy import copy
                    from wakfu_server.combat_results import terminal_event
                    from wakfu_server.combat_spectator_events import terminal_batch

                    event_packets = terminal_batch(
                        event_packets,
                        fight_id=shared.fight.id,
                        fallback_packet=lambda: (
                            aborted_terminal_packets(
                                shared.fight, shared.runtime, losing_team=abandon_team
                            )[0]
                            if abandon_team is not None
                            else terminal_event(copy(shared.runtime))
                        ),
                    )
                participants = tuple(
                    self.runtime.ObserverSession(
                        entry.account_id,
                        entry.character_id,
                        entry.generation,
                        entry.map_id,
                        entry.instance_id,
                    )
                    for entry in shared.participants.values()
                )
                current = self.runtime.SPECTATORS.fights.get(shared.fight.id)
                if self.spectator_waiting_for_ack(shared):
                    if current is not None and event_packets:
                        self.runtime.SPECTATORS.publish_events(
                            shared.fight.id,
                            revision=max(shared.sequence, current.revision + 1),
                            event_packets=event_packets,
                        )
                    return
                if current is None:
                    if shared.fight.phase == "finished":
                        return
                    packets = self.spectator_snapshot(shared)
                    self.runtime.SPECTATORS.publish_fight(
                        shared.fight.id,
                        map_id=shared.map_id,
                        instance_id=shared.instance_id,
                        participant_sessions=participants,
                        revision=max(1, shared.sequence),
                        snapshot_packets=packets,
                        visible=not getattr(shared, "is_duel", False)
                        or self.public_objectives_duel(shared),
                    )
                elif shared.fight.phase == "finished":
                    revision = max(shared.sequence, current.revision + 1)
                    observers = self.runtime.SPECTATORS.publish_terminal(
                        shared.fight.id,
                        revision=revision,
                        event_packets=event_packets,
                    )
                else:
                    if (
                        not force_snapshot
                        and not self.runtime.SPECTATORS.has_subscribers(shared.fight.id)
                    ):
                        # Current viewers consume public actions; an empty audience
                        # needs no repeated actor/DB serialization. Keep the initial
                        # registry entry for deferred admission, but fence its stale
                        # snapshot until an explicit entry refreshes it under this lock.
                        self.runtime.SPECTATORS.invalidate_snapshot(shared.fight.id)
                        return
                    try:
                        packets = self.spectator_snapshot(shared)
                    except (KeyError, TypeError, ValueError):
                        # Existing observers already own a native bootstrap. A
                        # rejected replacement must not discard their committed
                        # action stream or admit newcomers at a stale snapshot.
                        self.runtime.SPECTATORS.invalidate_snapshot(shared.fight.id)
                        if event_packets:
                            self.runtime.SPECTATORS.publish_events(
                                shared.fight.id,
                                revision=max(shared.sequence, current.revision + 1),
                                event_packets=event_packets,
                            )
                        raise
                    self.runtime.SPECTATORS.publish_update(
                        shared.fight.id,
                        revision=max(shared.sequence, current.revision + 1),
                        snapshot_packets=packets,
                        event_packets=event_packets,
                    )
        except (KeyError, TypeError, ValueError) as error:
            self.runtime.record(
                event="combat_spectator_snapshot_rejected",
                fight_id=getattr(getattr(shared, "fight", None), "id", None),
                reason=str(error),
            )

    def resume_settled_shared_combat(self):
        if (
            not self.runtime.COMBAT_TEST
            or self.state.character is None
            or self.state.combat_session is not None
            or self.state.fight is not None
        ):
            return False
        shared = self.runtime.COMBAT_SESSIONS.lookup_character(
            self.state.character["id"]
        )
        if shared is not None and getattr(shared, "is_duel", False):
            if not shared.settlement_ready or self.state.account_id in shared.returned:
                return False
            fight_id = shared.fight.id
            session_entry = self.runtime.COMBAT_SESSIONS.session(
                self.state.account_id, self.state.generation, self.state.character
            )
            try:
                shared = self.runtime.COMBAT_SESSIONS.takeover_settled(
                    session_entry, fight_id
                )
            except ValueError as error:
                self.runtime.record(
                    event="combat_settlement_takeover_rejected",
                    actor_id=self.state.character["id"],
                    fight_id=fight_id,
                    reason=str(error),
                )
                return False
            self.state.combat_session = session_entry
            self.state.fight = shared.fight
            self.state.fight_messages = shared.runtime
            self.state.group_lease = getattr(shared, "group_lease", None)
            context = shared.join_context or {}
            self.state.TEST_MONSTERS_BY_ID = context.get("monsters", {})
            self.state.TEST_MONSTERS = tuple(self.state.TEST_MONSTERS_BY_ID.values())
            self.state.TEST_GROUP_KEY = context.get("group_key")
            checkpoint = self.runtime.CHECKPOINTS.read(self.state.account_id, fight_id)
            self.state.checkpoint_id = fight_id
            self.state.checkpoint_revision = checkpoint["revision"]
            self.state.checkpoint_terminal = True
            self.drain_shared_combat()
            self.runtime.record(
                event="combat_settlement_taken_over",
                actor_id=self.state.character["id"],
                fight_id=fight_id,
            )
            return True
        if shared is not None and (
            not shared.settlement_ready or self.state.account_id in shared.returned
        ):
            return False
        session_entry = self.runtime.COMBAT_SESSIONS.session(
            self.state.account_id, self.state.generation, self.state.character
        )
        try:
            recovered = self.runtime.COMBAT_SESSIONS.recover_settled_world(
                session_entry,
                self.state.character,
                wp=self.runtime.COMBAT_TEST_WP,
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_settled_world_recovery_rejected",
                actor_id=self.state.character["id"],
                fight_id=None if shared is None else shared.fight.id,
                reason=str(error),
            )
            return False
        if recovered is None:
            return False
        self.state.character.update(recovered["character"])
        for message_id, payload in recovered["packets"]:
            self.runtime.send(
                self.state.connection, self.state.service, message_id, payload
            )
        self.state.group_lease = None
        self.runtime.record(
            event="combat_settled_world_recovered",
            actor_id=self.state.character["id"],
            fight_id=recovered["fight_id"],
            health_applied=recovered["applied"],
            native_fight_attached=False,
        )
        return True

    def recover_pending_terminal_world(self):
        """Return a fresh login after its deferred terminal settlement commits."""
        if (
            self.state.pending_terminal_world_recovery is None
            or self.state.combat_session is None
        ):
            return False
        shared = self.runtime.COMBAT_SESSIONS.registry.lookup(self.state.fight.id)
        if not shared.settlement_ready:
            return False
        recovered = self.runtime.COMBAT_SESSIONS.recover_settled_world(
            self.state.combat_session,
            self.state.character,
            wp=self.runtime.COMBAT_TEST_WP,
            pending_world_recovery=self.state.pending_terminal_world_recovery,
        )
        if recovered is None:
            raise ValueError("Pending terminal world recovery was not completed")
        self.state.character.update(recovered["character"])
        self.runtime.send_batch(
            self.state.connection, self.state.service, recovered["packets"]
        )
        self.runtime.record(
            event="combat_pending_terminal_world_recovered",
            actor_id=self.state.character["id"],
            fight_id=self.state.fight.id,
            health_applied=recovered["applied"],
            native_fight_attached=False,
        )
        self.state.pending_terminal_world_recovery = None
        self.state.combat_session = self.state.fight = self.state.fight_messages = (
            self.state.group_lease
        ) = None
        self.state.checkpoint_id = self.state.checkpoint_revision = None
        self.state.checkpoint_terminal = False
        return True

    def adopt_shared_duel(self):
        """Attach a loaded owner to its existing shared combat FSM/outbox."""
        if (
            not self.runtime.COMBAT_TEST
            or not self.state.loaded
            or self.state.character is None
            or (
                (self.state.combat_session is not None or self.state.fight is not None)
                and self.deferred_native_combat_attachment() is None
            )
        ):
            return False
        shared = self.runtime.COMBAT_SESSIONS.lookup_character(
            self.state.character["id"]
        )
        if shared is None:
            return False
        owner = shared.participants.get(self.state.account_id)
        if owner is None or not self.runtime.COMBAT_SESSIONS.reconnect_owner_matches(
            shared,
            self.runtime.COMBAT_SESSIONS.session(
                self.state.account_id, self.state.generation, self.state.character
            ),
        ):
            return False
        # A participant who has completed native12925 is back in the world
        # even while the other owner is still viewing the settled result.
        # Never let an idle/reconnect callback reattach that returned socket.
        if (
            self.state.account_id in shared.returned
            or self.state.account_id in shared.withdrawals
        ):
            return False
        staged_entry = getattr(shared, "pending_publication_recoveries", {}).get(
            self.state.account_id
        )
        resume_staged = (
            staged_entry is not None
            and staged_entry.session == owner
            and owner.generation == self.state.generation
            and self.state.account_id not in shared.connected
        )
        if owner.generation != self.state.generation or resume_staged:
            if shared.settlement_ready:
                return self.resume_settled_shared_combat()
            from wakfu_server.combat_shared import Session
            from wakfu_server.fight_store import takeover_participant

            replacement = Session(
                self.state.account_id,
                self.state.character["id"],
                self.state.generation,
                shared.map_id,
                shared.instance_id,
            )

            # The worker publishes its revision under shared.lock. Drain before
            # Registry.takeover acquires that lock, never from its callback.
            if (
                not resume_staged
                and not self.runtime.CHECKPOINT_WRITER.flush_for_takeover(
                    shared.fight.id,
                    self.state.account_id,
                    owner.generation,
                    self.state.generation,
                    timeout=10,
                )
            ):
                raise ValueError("Checkpoint takeover drain timed out")

            def persist_takeover(previous):
                self.runtime.CHECKPOINT_WRITER.takeover_writer(
                    shared.fight.id,
                    self.state.account_id,
                    previous.generation,
                    self.state.generation,
                    persist=lambda: takeover_participant(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        fight_id=shared.fight.id,
                        previous_generation=previous.generation,
                    ),
                )

            from wakfu_server.combat_instance_publication_recovery import (
                rebind_recovered_owner,
                requires_publication_recovery,
            )

            publication_recovery = (
                (
                    self.state.connection.instance_publications,
                    self.state.connection.native_instance_scope(),
                )
                if requires_publication_recovery(shared.fight)
                else None
            )
            self.runtime.COMBAT_SESSIONS.registry.takeover(
                shared.fight.id,
                replacement,
                lambda current_fight, current_shared, current_session: (
                    ()
                    if current_fight.phase == "finished"
                    else self.runtime.COMBAT_SESSIONS.owned_reconnect_bootstrap(
                        current_fight, current_shared, current_session
                    )
                ),
                persist_takeover=persist_takeover,
                recover_disconnected=True,
                prepare_authority=(
                    (
                        lambda current_fight, current_shared, current_session: rebind_recovered_owner(
                            current_fight,
                            current_shared,
                            current_session,
                            publication_recovery,
                            session_live=self.runtime.COMBAT_SESSIONS.registry._lease_live,
                            owner_matches=self.runtime.COMBAT_SESSIONS.reconnect_owner_matches,
                        )
                    )
                    if publication_recovery is not None
                    else None
                ),
                fresh_world=(
                    shared.fight.phase == "finished"
                    and not getattr(shared, "is_duel", False)
                    and getattr(shared.runtime, "abandon_owner", None) is None
                ),
            )
            shared = self.runtime.COMBAT_SESSIONS.registry.lookup(shared.fight.id)
            self.state.pending_terminal_world_recovery = (
                shared.pending_world_recoveries.get(self.state.account_id)
            )
            owner = replacement
        if owner.generation != self.state.generation:
            return False
        self.state.combat_session = owner
        self.state.fight = shared.fight
        self.state.fight_messages = shared.runtime
        self.state.group_lease = shared.group_lease
        context = shared.join_context or {}
        self.state.TEST_MONSTERS_BY_ID = context.get("monsters", {})
        self.state.TEST_MONSTERS = tuple(self.state.TEST_MONSTERS_BY_ID.values())
        self.state.TEST_GROUP_KEY = context.get("group_key")
        self.state.fight_started_at = context.get("fight_started_at", time.monotonic())
        from wakfu_server.combat_instance_publication_recovery import (
            publication_recovery_waiting,
        )

        if publication_recovery_waiting(shared):
            # Durable membership is attached, but native gameplay and transport
            # bootstrap remain paused until every required real owner returns.
            return True
        self.state.placement_deadline.start(
            self.state.fight.id,
            context.get("duration_ms"),
            self.state.fight_started_at,
            native=self.state.is_owned_guardian_fight(
                self.state.fight, self.state.character["id"]
            ),
        )
        try:
            checkpoint = self.runtime.CHECKPOINTS.read(
                self.state.account_id, self.state.fight.id
            )
        except ValueError:
            checkpoint = None
        self.state.checkpoint_id = self.state.fight.id
        self.state.checkpoint_revision = (
            None if checkpoint is None else checkpoint["revision"]
        )
        self.state.checkpoint_terminal = False
        # Another peer can adopt/checkpoint this shared duel concurrently.
        # Seed once; a delayed SQL read on this socket must not roll back a
        # newer fight-wide revision observed by another socket.
        self.state.checkpoint_revision = shared.seed_checkpoint_revision(
            self.state.checkpoint_revision
        )
        self.drain_shared_combat()
        if checkpoint is None:
            self.checkpoint_fight()
        self.runtime.record(
            event="shared_combat_owner_attached",
            actor_id=self.state.character["id"],
            fight_id=self.state.fight.id,
        )
        return True

    def deferred_native_combat_attachment(self):
        """Keep selected owners in their retained fight while peers reattach."""
        if (
            not self.runtime.COMBAT_TEST
            or not self.state.loaded
            or self.state.character is None
        ):
            return None
        shared = self.runtime.COMBAT_SESSIONS.lookup_character(
            self.state.character["id"]
        )
        if shared is None:
            shared = self.state.publication_recovery_shared
            if not getattr(shared, "publication_recovery_aborted", None):
                return None
        owner = shared.participants.get(self.state.account_id)
        if owner is None or owner.character_id != self.state.character["id"]:
            return None
        if (
            self.state.account_id in shared.returned
            or self.state.account_id in shared.withdrawals
        ):
            return None
        from wakfu_server.combat_instance_publication_recovery import (
            publication_recovery_waiting,
            requires_publication_recovery,
        )

        if getattr(shared, "publication_recovery_aborted", None):
            return shared
        if not requires_publication_recovery(shared.fight):
            return None
        if owner.generation != self.state.generation or publication_recovery_waiting(
            shared
        ):
            return shared
        return None

    def recover_aborted_publication_cohort(self, *, bootstrap=True):
        """Return every waiting socket after a complete durable cohort abort."""
        shared = self.state.publication_recovery_shared
        exits = getattr(shared, "publication_recovery_aborted", None)
        if not exits or self.state.character is None:
            return False
        previous = shared.participants.get(self.state.account_id)
        if (
            previous is None
            or previous.generation != self.state.generation
            or previous.character_id != self.state.character["id"]
            or self.state.character["id"] not in exits
        ):
            return False
        if not self.runtime.STORE.current_character_session(
            self.state.account_id, self.state.generation, self.state.character["id"]
        ):
            raise ValueError("Aborted native return has a stale selected session")
        if getattr(self.state.connection, "native_fight_id", None) == shared.fight.id:
            if self.state.aborted_native_return is None:
                pending = self.runtime.AbortedNativeReturn(previous, shared)
                pending.require(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
                packets = pending.packets()
                self.runtime.send_batch(
                    self.state.connection, self.state.service, packets
                )
                self.state.aborted_native_return = pending
                self.runtime.record(
                    event="combat_aborted_native_cleanup_sent",
                    actor_id=self.state.character["id"],
                    fight_id=shared.fight.id,
                )
                return True
            self.state.aborted_native_return.require(
                self.state.account_id, self.state.generation, self.state.character["id"]
            )
            if not self.state.aborted_native_return.acknowledged:
                return True
        # Reload rather than replaying the exit's character snapshot: an
        # explicit console relocation may already have committed its new map.
        saved = self.runtime.STORE.character(
            self.state.account_id, self.state.character["id"]
        )
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        self.state.character.update(self.refresh_owned_character(saved))
        self.attach_combat_return_position()
        self.state.position = {
            key: self.state.character[key] for key in ("x", "y", "z")
        }
        self.state.movement_state = self.runtime.Movement(self.state.position)
        self.state.fight = self.state.fight_messages = self.state.combat_session = (
            self.state.group_lease
        ) = None
        self.state.checkpoint_id = self.state.checkpoint_revision = None
        self.state.checkpoint_terminal = False
        self.state.pending_terminal_world_recovery = None
        self.state.TEST_MONSTERS = ()
        self.state.TEST_MONSTERS_BY_ID = {}
        self.state.TEST_GROUP_KEY = None
        self.state.fight_started_at = None
        self.state.placement_deadline.take_expired(None, time.monotonic())
        self.state.publication_recovery_shared = None
        self.state.publication_recovery_attempt_token = (
            self.state.publication_recovery_notice_token
        ) = None
        if self.state.aborted_native_return is not None:
            self.state.aborted_native_return.world_returned = True
            if self.state.aborted_native_return.command is None:
                self.state.aborted_native_return = None
        if bootstrap:
            self.runtime.send_batch(
                self.state.connection,
                self.state.service,
                self.combat_return_bootstrap(),
            )
            self.runtime.join_world(
                self.state.generation, self.state.connection, self.state.character
            )
            self.mark_static_sync_pending()
        self.runtime.record(
            event="combat_publication_recovery_aborted_world_return",
            actor_id=self.state.character["id"],
            fight_id=shared.fight.id,
        )
        if bootstrap:
            self.release_completed_combat_return_aliases()
        return True

    def finish_aborted_native_return(self, body):
        """Consume the original12925 only after this socket's native cleanup."""
        pending = self.state.aborted_native_return
        if pending is None or self.state.character is None:
            raise ValueError("No aborted native cleanup awaits this callback")
        pending.require(
            self.state.account_id, self.state.generation, self.state.character["id"]
        )
        if not self.runtime.STORE.current_character_session(
            self.state.account_id, self.state.generation, self.state.character["id"]
        ):
            raise ValueError("Aborted native return has a stale selected session")
        pending.acknowledge(body)
        self.state.publication_recovery_return_due = 0.0
        return self.continue_aborted_publication_recovery()

    def complete_aborted_native_return(self):
        """Retry a recorded native completion without manufacturing its ACK."""
        pending = self.state.aborted_native_return
        if pending is None or not pending.acknowledged or self.state.character is None:
            raise ValueError("Aborted native cleanup has not completed")
        pending.require(
            self.state.account_id, self.state.generation, self.state.character["id"]
        )
        if not self.runtime.STORE.current_character_session(
            self.state.account_id, self.state.generation, self.state.character["id"]
        ):
            raise ValueError("Aborted native return has a stale selected session")
        command = pending.command
        self.state.connection.native_fight_id = None
        if not pending.world_returned:
            self.recover_aborted_publication_cohort(bootstrap=command is None)
        if command is not None:
            if command.lower() in ("!exitdungeon", "!salirmazmorra"):
                self.execute_dungeon_exit_command(_native_return_retry=True)
            else:
                self.execute_test_command(command)
        self.runtime.record(
            event="combat_aborted_native_cleanup_completed",
            actor_id=self.state.character["id"],
            fight_id=pending.shared.fight.id,
            native_return_ack=True,
        )
        self.state.aborted_native_return = None
        self.release_completed_combat_return_aliases()
        return True

    def continue_aborted_publication_recovery(self):
        """Keep an already committed abort retryable during transient DB contention."""
        if (
            self.state.aborted_native_return is not None
            and self.state.aborted_native_return.world_returned
        ):
            try:
                self.complete_aborted_native_return()
            except (self.state.DatabaseError, self.state.PoolTimeout, TimeoutError):
                pass  # The exact command remains attached to this native ACK.
            return True
        shared = self.state.publication_recovery_shared
        if not getattr(shared, "publication_recovery_aborted", None):
            return False
        owner = shared.participants.get(self.state.account_id)
        if (
            self.state.character is None
            or owner is None
            or (owner.generation, owner.character_id)
            != (self.state.generation, self.state.character["id"])
        ):
            self.state.publication_recovery_shared = None
            return False
        now = time.monotonic()
        if now < self.state.publication_recovery_return_due:
            return True
        self.state.publication_recovery_return_due = now + 1.0
        from wakfu_server.position_buffer import PositionOwnerBusy

        try:
            if (
                self.state.aborted_native_return is not None
                and self.state.aborted_native_return.acknowledged
            ):
                self.complete_aborted_native_return()
            else:
                self.recover_aborted_publication_cohort()
        except (
            ValueError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
            PositionOwnerBusy,
        ) as error:
            token = ("world_return", shared.fight.id, self.state.generation)
            if self.state.publication_recovery_notice_token != token:
                self.state.publication_recovery_notice_token = token
                self.runtime.record(
                    event="combat_publication_recovery_world_return_pending",
                    actor_id=self.state.character["id"],
                    fight_id=shared.fight.id,
                    reason=type(error).__name__,
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(
                        "El combate ya se abandonó y el progreso está guardado. "
                        "El regreso al mapa está pendiente; espera un momento."
                    ),
                )
        return True

    def attempt_shared_combat_attachment(self, *, blocking=False):
        """Poll in idle; retain an explicit request until attachment can proceed."""
        from wakfu_server.combat_instance_publication_recovery import (
            publication_recovery_token,
            requires_publication_recovery,
        )

        if self.continue_aborted_publication_recovery():
            return True
        shared = (
            None
            if self.state.character is None
            else self.runtime.COMBAT_SESSIONS.lookup_character(
                self.state.character["id"]
            )
        )
        if shared is None or not requires_publication_recovery(shared.fight):
            return self.adopt_shared_duel()
        self.state.publication_recovery_shared = shared
        if not shared.lock.acquire(blocking=blocking):
            return False
        try:
            token = (
                publication_recovery_token(shared),
                self.state.connection.instance_publications.lease.current,
            )
        finally:
            shared.lock.release()
        now = time.monotonic()
        if (
            not blocking
            and token == self.state.publication_recovery_attempt_token
            and now < self.state.publication_recovery_attempt_due
        ):
            return False
        self.state.publication_recovery_attempt_token = token
        self.state.publication_recovery_attempt_due = now + 1.0
        error = None
        try:
            result = self.adopt_shared_duel()
        except (ValueError, KeyError) as rejected:
            error = rejected
            result = False
        waiting = self.deferred_native_combat_attachment() is not None
        if waiting and token != self.state.publication_recovery_notice_token:
            self.state.publication_recovery_notice_token = token
            self.runtime.record(
                event="combat_publication_recovery_waiting",
                actor_id=self.state.character["id"],
                fight_id=shared.fight.id,
                reason=(
                    "participant_publications_pending"
                    if error is None
                    else type(error).__name__
                ),
            )
            current_owner = shared.participants.get(self.state.account_id)
            can_abandon = (
                not shared.connected
                and shared.disconnect_abort_pending
                and current_owner is not None
                and current_owner.generation == self.state.generation
                and self.state.account_id in shared.pending_publication_recoveries
            )
            message = (
                "El combate está pausado mientras se recupera la conexión del grupo. "
                "Los participantes que se desconectaron deben volver a entrar. "
            )
            message += (
                "Puedes abandonar el combate para volver al mapa."
                if can_abandon
                else "Espera a que termine la recuperación; si persiste, vuelve a conectar."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(message),
            )
        if not waiting and error is not None:
            raise error
        if not waiting:
            self.state.publication_recovery_attempt_token = (
                self.state.publication_recovery_notice_token
            ) = None
            self.state.publication_recovery_shared = None
        return result

    def abort_waiting_publication_cohort(self):
        """Explicitly abandon an unbootstrapped, fully paused owner cohort."""
        shared = self.deferred_native_combat_attachment()
        if shared is None:
            return False
        self.state.publication_recovery_shared = shared
        owner = shared.participants.get(self.state.account_id)
        if owner is None or owner.generation != self.state.generation:
            self.attempt_shared_combat_attachment()
            owner = shared.participants.get(self.state.account_id)
        if owner is None or owner.generation != self.state.generation:
            raise ValueError(
                "La recuperación aún no permite abandonar. Vuelve a conectar e inténtalo otra vez."
            )
        from wakfu_server.combat_health import persist_aborted_shared_fight

        result = (
            self.runtime.COMBAT_SESSIONS.registry.abort_pending_publication_recovery(
                owner,
                persist=lambda current: persist_aborted_shared_fight(
                    self.runtime.STORE, current, groups=self.runtime.COMBAT_GROUPS
                ),
            )
        )
        # Waiting peers retain this same shared object even after index
        # retirement. Their next idle returns them through the same world path.
        shared.publication_recovery_aborted = result["exits"]
        marker = self.runtime.EXTERNAL_FIGHT_MARKERS.remove(shared.fight.id)
        if marker is not None:
            self.runtime.WORLD.emit_location(
                shared.map_id,
                shared.instance_id,
                *marker,
                exclude_sessions=tuple(
                    (participant.character_id, participant.generation)
                    for participant in shared.participants.values()
                ),
            )
        if shared.group_lease is not None:
            self.publish_full_abandon_group(shared, {"group_restored": True})
        self.continue_aborted_publication_recovery()
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *self.state.information(
                "Se abandonó el combate pausado del grupo. Se guardaron la vida y "
                "las heridas de todos. Puedes continuar cuando termine de cargar el mapa."
            ),
        )
        return True

    @PROFILER.profile("combat.readiness")
    def apply_readiness(self, ready, *, acting_session=None):
        if self.state.fight is None or self.state.fight.phase != "placement":
            return False
        from wakfu_server.combat_actor import actor_effects
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.spells import default_deck

        def initialize_encounter_states(
            preview, action_id, characters, decks, monsters
        ):
            from wakfu_server.combat_consumable_lifecycle import refresh_participants

            characters.update(
                refresh_participants(self.runtime.STORE, characters, preview.id)
            )
            source_id = next(iter(characters))
            source = characters[source_id]
            from wakfu_server import boss_score, boss_score_runtime

            if getattr(preview, "rift_wave_state", None) is None:
                with self.runtime.STORE.connection() as score_db:
                    score_snapshot = boss_score.prepare_snapshot(
                        score_db,
                        preview.id,
                        monsters={
                            identity: {
                                "ref": monster["ref"],
                                "team": preview.actors[identity].team,
                            }
                            for identity, monster in monsters.items()
                            if identity in preview.actors
                        },
                        player_ids=tuple(characters),
                        player_team=preview.actors[source_id].team,
                    )
                    boss_score_runtime.install(preview, score_snapshot)
            if not self.runtime.is_dungeon_run(source.get("instance_id", 0)):
                return preview, ()
            from wakfu_server.dungeon_stele_states import (
                initialize as initialize_stele_states,
            )

            def native_factory(state, boss_id):
                factory, _ = server_runtime(
                    source,
                    monsters,
                    decks[source_id],
                    action_id=action_id,
                    critical=False,
                    player_characters=characters,
                    deck_blobs=decks,
                )
                return factory

            with self.runtime.STORE.connection() as db:
                preview, receipt, packets = initialize_stele_states(
                    db, preview, monsters, runtime_factory=native_factory
                )
            return preview, tuple(packets)

        if self.state.combat_session is not None:
            from wakfu_server.fight_store import activate

            shared = self.refresh_shared_combat()
            ready_session = (
                self.state.combat_session if acting_session is None else acting_session
            )

            @PROFILER.profile("combat.readiness.prepare")
            def ready_operation(candidate, runtime):
                bot_id = (shared.join_context or {}).get("ai_bot_character_id")
                if (
                    getattr(shared, "is_duel", False)
                    and ready_session.character_id == bot_id
                    and ready
                ):
                    from wakfu_server.friendly_duel_runtime import (
                        enable_friendly_bot_ai,
                    )

                    enable_friendly_bot_ai(
                        candidate, tuple(shared.duel_leaders.values()), bot_id
                    )
                prepared = self.runtime.COMBAT_SESSIONS.ready_transition(
                    ready_session,
                    candidate,
                    runtime,
                    ready,
                    shared.join_context["monsters"],
                    previous_native_action_id=(
                        0 if runtime is None else runtime.native_action_id
                    ),
                    fight_start=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
                    area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1")
                    == "1",
                    encounter_initializer=lambda preview, action_id, characters, decks: (
                        initialize_encounter_states(
                            preview,
                            action_id,
                            characters,
                            decks,
                            shared.join_context["monsters"],
                        )
                    ),
                )
                if candidate.phase == "placement" and prepared.fight.phase == "active":
                    activate(
                        self.runtime.STORE,
                        ready_session.account_id,
                        ready_session.generation,
                        ready_session.character_id,
                        candidate.id,
                    )
                return prepared

            self.runtime.COMBAT_SESSIONS.execute(
                ready_session,
                self.state.fight.id,
                ready_session.character_id,
                ready_operation,
                require_turn=False,
            )
            self.refresh_shared_combat()
            self.drain_shared_combat()
            self.checkpoint_fight(accepted_publication=True)
            if self.state.fight.phase == "finished":
                self.complete_test_fight()
            else:
                self.pass_test_monster_turn()
            return True

        stored_deck = (
            self.state.character.get("builds", {})
            .get(self.state.character.get("active_build_index", 0), {})
            .get("deck")
        )
        deck = (
            bytes.fromhex(stored_deck)
            if stored_deck
            else default_deck(self.state.character)
        )

        def initialize_legacy(preview, action_id):
            legacy_characters = {self.state.character["id"]: self.state.character}
            preview, encounter_packets = initialize_encounter_states(
                preview,
                action_id,
                legacy_characters,
                {self.state.character["id"]: deck},
                self.state.TEST_MONSTERS_BY_ID,
            )
            from wakfu_server.combat_attachment_authority import for_characters

            attachments = for_characters(self.runtime.STORE, legacy_characters)
            preview, owned_packets = prepare_server_initialization(
                legacy_characters[self.state.character["id"]],
                self.state.TEST_MONSTERS_BY_ID,
                preview,
                self.state.account_id,
                deck,
                action_id=action_id,
                attachment_authority=attachments,
                fight_start=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
            )
            initial_packets = [*encounter_packets, *owned_packets]
            if getattr(preview, "rii_element_lesson_contract", None) is not None:
                from wakfu_server.achievements.rii_element_contract import initialize

                initialize(preview, initial_packets, action_id=action_id)
            if getattr(preview, "rii_distance_lesson_contract", None) is not None:
                from wakfu_server.achievements.rii_distance_contract import initialize

                initialize(preview, initial_packets, action_id=action_id)
            if getattr(preview, "rii_area_lesson_contract", None) is not None:
                from wakfu_server.achievements.rii_area_contract import initialize

                initialize(preview, initial_packets, action_id=action_id)
            if getattr(preview, "rii_los_lesson_contract", None) is not None:
                from wakfu_server.achievements.rii_los_encounter import initialize

                initialize(preview, initial_packets, action_id=action_id)
            if getattr(preview, "rii_movement_lesson_contract", None) is not None:
                from wakfu_server.achievements.rii_movement_contract import initialize

                initialize(preview, initial_packets, action_id=action_id)
            if getattr(preview, "rii_states_lesson_contract", None) is not None:
                from wakfu_server.achievements.rii_states_contract import initialize

                initialize(preview, initial_packets, action_id=action_id)
            return preview, tuple(initial_packets)

        candidate, candidate_messages, packets = prepare_ready(
            self.state.fight,
            self.state.account_id,
            ready,
            initialize=initialize_legacy,
            stats_serializer=self.current_combat_stats,
            runtime_stats_serializer=self.current_combat_stats,
            effects_serializer=actor_effects,
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                self.state.character,
                self.state.TEST_MONSTERS_BY_ID,
                deck,
                action_id=action_id,
                critical=False,
            )[0],
            turn_start_provider=(
                self.area_boundary_provider
                if (
                    os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1"
                    or os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1"
                )
                else None
            ),
            previous_native_action_id=(
                self.state.fight_messages.native_action_id
                if self.state.fight_messages is not None
                else 0
            ),
            turn_end_provider=(
                (
                    lambda preview, **boundary: prepare_server_turn_end(
                        self.state.character,
                        self.state.TEST_MONSTERS_BY_ID,
                        preview,
                        deck,
                        **boundary,
                    )
                )
                if os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1"
                else None
            ),
        )
        if candidate_messages is None:
            self.state.fight = candidate
            return False
        from wakfu_server.fight_store import activate

        activate(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            candidate.id,
        )
        self.state.fight = candidate
        self.state.fight_messages = candidate_messages
        for message_id, payload in packets:
            self.runtime.send(
                self.state.connection, self.state.service, message_id, payload
            )
        self.runtime.record(
            event="combat_test_active",
            actor_id=self.state.character["id"],
            fight_id=self.state.fight.id,
        )
        if self.state.fight.phase == "finished":
            self.complete_test_fight()
        else:
            self.pass_test_monster_turn()
        return True

    def release_completed_combat_action_results(self):
        """Drop synchronous action receipts after request diagnostics finish."""
        self.state.transaction = self.state.action_results = self.state.delivery = (
            self.state.shared_cast
        ) = self.state.shared_weapon = None

    def release_completed_combat_return_aliases(self):
        """Release socket-frame battle aliases after successful world delivery."""
        self.state.shared_state = self.state.shared = self.state.shared_selection = (
            self.state.shared_rift
        ) = None
        self.state.candidate = self.state.hero_admission = (
            self.state.companion_admission
        ) = None
        self.state.selection_runtime = self.state.orientation_runtime = (
            self.state.checkpoint_local_shared
        ) = None
        self.state.pending = self.state.returned = None
        self.state.finish_return = self.state.abandon_messages = None

    def finish_combat_return_after_position_flush(
        self, *, abandoned, shared_return, shared_state
    ):
        """Resume a consumed12925 only after its position fence succeeds."""
        self.state.connection.native_fight_id = None

        if (
            self.state.character["map_id"] == 1388
            and self.state.character["instance_id"] == 0
        ):
            from wakfu_server.achievements import rii_training_arena

            try:
                # A shared-fight withdrawal removes the lesson contract from
                # the combat preview. The durable transit receipt remains the
                # authority for returning its owner after any combat exit.
                if rii_training_arena.pending(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                ):
                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(
                            account_id=self.state.account_id,
                            generation=self.state.generation,
                            character_id=self.state.character["id"],
                        )
                        available = self.training_occupancy_snapshot(returning=True)
                        returned = rii_training_arena.return_to_source(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            available=available,
                        )
                        if returned is not None:
                            self.state.character = returned
                            self.state.training_transit_active = False
            except ValueError as error:
                # Keep the return receipt for a later recovery; never break
                # the normal combat exit or send a fabricated position.
                self.runtime.record(
                    event="rii_training_return_deferred",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
        self.attach_combat_return_position()
        self.state.position = {
            key: self.state.character[key] for key in ("x", "y", "z")
        }
        self.state.movement_state = self.runtime.Movement(self.state.position)
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        return_packets = self.combat_return_bootstrap()
        if self.state.character["map_id"] == 1361:
            from wakfu_server.achievements import incarnam_encounters

            return_packets = incarnam_encounters.return_bootstrap(
                self.state.character, return_packets, abandoned=abandoned
            )
        for message_id, payload in return_packets:
            self.runtime.send(
                self.state.connection, self.state.service, message_id, payload
            )
        from wakfu_server.level_publication import (
            combat_return as refresh_return_spells,
        )

        self.runtime.send_batch(
            self.state.connection,
            self.state.service,
            refresh_return_spells(
                self.state.character,
                self.runtime.STORE.characters(self.state.account_id),
                participant_ids=tuple(
                    actor.id
                    for actor in self.state.fight.actors.values()
                    if actor.controlled
                    and actor.owner_id == self.state.account_id
                    and str(actor.id)
                    not in getattr(self.state.fight, "native_companion_sources", {})
                ),
                entity_template=self.runtime.OWNED_HERO_TEMPLATE,
                roster_template=self.runtime.CHARACTERS,
                retained_state_packets=self.runtime.consumable_state_packets,
            ),
        )
        from wakfu_server import companions

        with self.runtime.STORE.connection() as companion_db:
            companion_collection = companions.collection(
                companion_db, self.state.account_id
            )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *companions.refresh_packet(companion_collection),
        )
        from wakfu_server.combat_monster_world import spawn_group

        if self.state.group_lease is not None and (not shared_return or abandoned):
            with self.runtime.COMBAT_GROUPS.lock:
                defeated = (
                    not abandoned
                    and self.state.fight.winner
                    == self.state.fight.actors[self.state.character["id"]].team
                )
                restored = self.runtime.COMBAT_GROUPS.finish(
                    self.state.group_lease, defeated=defeated
                )
                if restored and not defeated:
                    from wakfu_server.ecology_admin import current_available

                    map_id, instance_id, group_id = self.state.group_lease[0]
                    restored_members = current_available(
                        self.runtime.STORE, self.state.group_lease[0]
                    )
                    if restored_members:
                        self.runtime.publish_available_group(
                            self.state.group_lease[0],
                            restored_members,
                            exclude_generation=self.state.generation,
                        )
                        for packet in self.runtime.HARVESTS.availability_for(
                            map_id,
                            instance_id,
                            [member["id"] for member in restored_members],
                        ):
                            self.runtime.WORLD.emit_location(
                                map_id,
                                instance_id,
                                *packet,
                                exclude_generation=self.state.generation,
                            )
        self.runtime.join_world(
            self.state.generation, self.state.connection, self.state.character
        )
        self.mark_static_sync_pending()
        if shared_return and abandoned:
            if getattr(shared_state, "full_abandon_owner", None) is None:
                if not self.runtime.COMBAT_SESSIONS.registry.retire_abandoned_single_owner(
                    self.state.fight.id, self.state.combat_session
                ):
                    raise ValueError("Shared PvE abandon was not safely retired")
        elif shared_return:
            # Persist the terminal checkpoint while the shared registry entry
            # exists. mark_returned may retire it when this is the last owner.
            self.checkpoint_fight("ended")
            self.runtime.COMBAT_SESSIONS.mark_returned(
                self.state.combat_session, self.state.fight.id
            )
            self.runtime.COMBAT_SESSIONS.disconnect(self.state.combat_session)
        else:
            self.checkpoint_fight("aborted" if abandoned else "ended")
        self.runtime.record(
            event="combat_return_to_world",
            actor_id=self.state.character["id"],
            fight_id=self.state.fight.id,
            abandoned=abandoned,
        )
        self.state.group_lease = None
        self.state.fight = self.state.fight_messages = None
        self.state.combat_session = None
        if not abandoned and self.state.character["map_id"] == 1361:
            from wakfu_server.achievements import incarnam_encounters
            from wakfu_server.intro_cinematic import scenario_event

            from wakfu_server.achievements import storage as tutorial_storage
            from wakfu_server.achievements import incarnam_tutorial

            with self.runtime.STORE.connection() as tutorial_db:
                ending_pending = incarnam_encounters.pending_final(
                    tutorial_db, self.state.character
                )
                tutorial_state = tutorial_storage.load_locked(
                    tutorial_db, self.state.character["id"]
                )
                first_scene = (
                    not ending_pending
                    and 5136 in tutorial_state["running"]
                    and incarnam_tutorial.claim_presentation(
                        tutorial_db, self.state.character["id"], 22354
                    )
                )
            if ending_pending:
                self.state.connection.pending_incarnam_outro = self.state.character[
                    "id"
                ]
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *scenario_event(22359, 2500),
                )
            elif first_scene:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *scenario_event(22354, 2500),
                )
        if not abandoned and self.state.character["map_id"] == 1387:
            from wakfu_server.achievements import rii_guardian_battle

            with self.runtime.STORE.connection() as guardian_db:
                ending_pending = rii_guardian_battle.pending_cinematic(
                    guardian_db, self.state.character
                )
            if ending_pending:
                for packet in rii_guardian_battle.cinematic_packets():
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
        self.deliver_custom_task_rewards()
        self.state.custom_task_cards.changed(
            self.state.character["id"], (self.state.character["id"],)
        )
        self.publish_custom_task_cards()
