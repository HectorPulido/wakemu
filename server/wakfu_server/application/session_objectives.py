"""Objectives operations for one lease-bound World session."""

import time
from .dispatch_result import DispatchResult


class ObjectivesSessionMixin:
    def choose_toolkit_dialogue(self, request):
        """Commit a plain native choice and its declared mission events together."""
        from uuid import uuid4
        from wakfu_server.achievements import mission_toolkit

        session = self.state.npc_dialogue_session
        previous = (
            session.node_id,
            session.speaker_id,
            session.authorize_speaker,
            session.previous_choice_id,
        )
        try:
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                with self.runtime.STORE.connection() as db:
                    db.execute(
                        "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                        (self.state.account_id,),
                    )
                    self.runtime.STORE.lock_character(
                        db,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        selected=True,
                    )
                    packet = session.choose(request["node_id"], request["choice_id"])
                    packets = (
                        []
                        if packet is None
                        else mission_toolkit.settle(
                            db,
                            self.runtime.STORE,
                            self.state.character,
                            token="dialogue:" + uuid4().hex,
                            kind="dialogue",
                            reference=request["choice_id"],
                        )
                    )
        except BaseException:
            (
                session.node_id,
                session.speaker_id,
                session.authorize_speaker,
                session.previous_choice_id,
            ) = previous
            raise
        self.publish_settled_quest_packets(packets)
        return packet

    def publish_settled_quest_packets(self, packets):
        """Refresh committed reward state before publishing quest notifications."""
        if packets:
            current = self.state.character
            saved = self.runtime.STORE.character(self.state.account_id, current["id"])
            updated = self.refresh_owned_character(dict(current, **saved))
            updated.update(
                map_id=current["map_id"],
                instance_id=current["instance_id"],
                direction=current["direction"],
                **self.state.position,
            )
            self.state.character = updated
            self.runtime.POSITIONS.merge(
                self.state.account_id, self.state.generation, updated
            )
        self.runtime.send_batch(self.state.connection, self.state.service, packets)

    def publish_nation_character(self, updated):
        from wakfu_server import guild_wire, nation_state

        updated = dict(updated)
        updated.update(
            map_id=self.state.character["map_id"],
            instance_id=self.state.character["instance_id"],
            direction=self.state.character["direction"],
            **self.state.position,
        )
        selected = updated["id"] == self.state.character["id"]
        if selected:
            self.state.character = updated
            self.runtime.send(
                self.state.connection,
                self.state.service,
                15548,
                self.runtime.wire.adapt(
                    15548,
                    self.runtime.fixture(15548),
                    self.state.account_id,
                    self.state.character,
                ),
            )
            for packet in self.runtime.consumable_state_packets(self.state.character):
                self.runtime.send(self.state.connection, self.state.service, *packet)
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.guild_company_packet(
                    self.state.character, self.state.character.get("guild_native")
                ),
            )
        else:
            from wakfu_server.hero_wire import refresh

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *refresh(self.runtime.OWNED_HERO_TEMPLATE, updated),
            )
        guild = updated.get("guild_native")
        packet = guild_wire.remote_actor_update(
            updated["id"],
            guild["guildId"] if guild else 0,
            guild["blazon"] if guild else 0,
            guild["level"] if guild else 0,
            guild["name"] if guild else "",
            nation_id=nation_state.nation_id(updated),
            nation_synchro=nation_state.synchro(updated),
        )
        if selected:
            self.runtime.WORLD.update(
                self.state.generation, updated, *packet, include_sender=False
            )
        else:
            self.runtime.WORLD.broadcast(
                self.state.generation,
                self.state.character["id"],
                *packet,
                include_sender=False,
            )
        return updated

    def deliver_custom_task_rewards(self, *, bootstrap=False):
        """Separate committed selected-character grant; never inside gameplay TX."""
        from wakfu_server.custom_tasks.reward_delivery import deliver
        from psycopg.errors import DeadlockDetected, LockNotAvailable

        if bootstrap:
            with self.runtime.STORE.connection() as db:
                active = db.execute(
                    "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f "
                    "ON f.id=p.fight_id WHERE p.account_id=%s AND p.character_id=%s "
                    "AND f.status IN ('placement','active') LIMIT 1",
                    (self.state.account_id, self.state.character["id"]),
                ).fetchone()
            if active is not None:
                return {
                    "deferred": True,
                    "packets": [],
                    "delivered": [],
                    "capacity_pending": [],
                    "character": self.state.character,
                }
        previous_level = self.state.character.get("level")
        try:
            result = deliver(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
        except (ValueError, DeadlockDetected, LockNotAvailable) as error:
            # Delivery owns its transaction: these lock errors reach here only
            # after rollback. Keep earned rows pending for the ordinary poll;
            # do not retry inline or publish packets for uncommitted grants.
            if not self.runtime.STORE.current_character_session(
                self.state.account_id, self.state.generation, self.state.character["id"]
            ):
                raise
            self.runtime.record(
                event="custom_task_rewards_pending",
                actor_id=self.state.character["id"],
                reason=str(error),
                sqlstate=getattr(error, "sqlstate", None),
                deferred=True,
            )
            return {
                "deferred": True,
                "packets": [],
                "delivered": [],
                "capacity_pending": [],
                "character": self.state.character,
            }
        saved = result["character"]
        if not bootstrap and saved.get("level") != previous_level:
            # Durable XP reconciliation pauses regeneration; resume world policy.
            # initialize itself keeps coefficient zero for a dead character.
            saved = self.runtime.health_store.initialize(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                saved["id"],
                exploration=True,
            )
            result["character"] = saved
        private = self.active_private_session()
        self.state.character = (
            private.refresh(self.state.character, saved)
            if private is not None and private.owns(self.state.character)
            else saved
        )
        if bootstrap:
            # Only absolute account unlock snapshots are safe before bootstrap.
            # Suppress additive XP, item insertions and unlock notifications.
            for packet in result["packets"]:
                if packet[0] == 13873:
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
            return result
        if result["delivered"]:
            from wakfu_server.combat_lifecycle import outside_progression

            self.runtime.send_batch(
                self.state.connection, self.state.service, result["packets"]
            )
            if self.state.character.get("level") != previous_level:
                self.runtime.WORLD.update(
                    self.state.generation,
                    self.state.character,
                    *self.runtime.wire.refresh_player(
                        self.runtime.PLAYER_TEMPLATE, self.state.character
                    ),
                )
                from wakfu_server.level_publication import refresh

                # Refresh owned spellbook and roster level/build availability.
                self.runtime.send_batch(
                    self.state.connection,
                    self.state.service,
                    refresh(
                        self.state.character,
                        self.runtime.STORE.characters(self.state.account_id),
                        entity_template=self.runtime.OWNED_HERO_TEMPLATE,
                        roster_template=self.runtime.CHARACTERS,
                        retained_state_packets=self.runtime.consumable_state_packets,
                    ),
                )
                self.runtime.send_native_planting_bonus(
                    self.state.connection, self.state.character
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *outside_progression(
                    self.state.character, wp=self.runtime.COMBAT_TEST_WP
                ),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.rich_inventory_packet(self.state.character),
            )
        return result

    def publish_custom_task_cards(self):
        ready = (
            self.state.loaded
            and self.state.fight is None
            and self.state.combat_session is None
            and self.state.hero_switch_pending is None
            and self.state.spectator_session is None
        )
        if not ready or not self.state.custom_task_cards.needs_refresh(
            self.state.account_id, self.state.generation, self.state.character["id"]
        ):
            return False
        gifts = self.state.current_local_gifts()
        return self.state.custom_task_cards.refresh(
            self.runtime.STORE,
            self.runtime.WORLD,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            ready=ready,
            existing_packages=gifts.packages,
            cap_reached=gifts.cap_reached,
        )

    def poll_national_progression(self):
        if not (
            self.state.loaded
            and self.state.character is not None
            and self.state.fight is None
            and self.state.combat_session is None
            and self.state.spectator_session is None
            and self.state.hero_switch_pending is None
        ):
            return
        now = time.monotonic()
        if now < self.state.national_poll_at:
            return
        self.state.national_poll_at = now + 1.0
        self.state.national_publication.refresh(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            publish=self.publish_nation_character,
        )

    def poll_environmental_events(self):
        """Recover committed environmental state independently of custom tasks."""
        if not (
            self.state.loaded
            and self.state.character is not None
            and self.state.fight is None
            and self.state.combat_session is None
            and self.state.spectator_session is None
            and self.state.hero_switch_pending is None
            and self.state.bag_session is None
        ):
            return
        now = time.monotonic()
        if now < self.state.environmental_poll_at:
            return
        self.state.environmental_poll_at = now + 1.0
        from wakfu_server.territory_cells import region_at

        try:
            region_id = region_at(
                self.state.character["map_id"],
                self.state.character["x"],
                self.state.character["y"],
            )
        except ValueError:
            # Unknown territory forbids new admission but does not hide already
            # earned entitlements or prevent reconnect delivery.
            region_id = None
        location = {
            key: self.state.character.get(key, 0)
            for key in ("map_id", "instance_id", "x", "y", "z")
        }
        location["region_id"] = region_id
        try:
            from wakfu_server.objectives.environmental_archmonster_runtime import (
                poll as poll_archmonsters,
            )

            try:
                poll_archmonsters(
                    self.runtime.STORE,
                    self.runtime.WORLD,
                    self.runtime.COMBAT_GROUPS,
                    location=location,
                    now_ms=int(self.runtime.STORE.now().timestamp() * 1000),
                )
            except OSError as error:
                self.runtime.record(
                    event="archmonster_publication_pending",
                    map_id=location["map_id"],
                    instance_id=location["instance_id"],
                    reason=type(error).__name__,
                )
            self.publish_native_monster_destructions(location)
            self.state.environmental_events.refresh(
                self.runtime.STORE,
                self.runtime.WORLD,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                location=location,
                ready=True,
                checkpoint=lambda: self.runtime.flush_positions(
                    account_id=self.state.account_id,
                    generation=self.state.generation,
                    character_id=self.state.character["id"],
                ),
            )
            saved = self.state.environmental_events.claimed_character
            if saved is not None:
                previous_level = self.state.character.get("level")
                # Live movement belongs to the position registry; an earned
                # inventory/XP refresh must not copy an older persisted tile.
                saved = dict(
                    saved,
                    **{
                        key: self.state.character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                    },
                )
                if saved.get("level") != previous_level:
                    initialized = self.runtime.health_store.initialize(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        saved["id"],
                        exploration=True,
                    )
                    saved = dict(
                        initialized,
                        **{
                            key: saved[key]
                            for key in ("map_id", "instance_id", "x", "y", "z")
                        },
                    )
                self.state.character = saved
                if self.state.character.get("level") != previous_level:
                    self.runtime.WORLD.update(
                        self.state.generation,
                        self.state.character,
                        *self.runtime.wire.refresh_player(
                            self.runtime.PLAYER_TEMPLATE, self.state.character
                        ),
                    )
                    from wakfu_server.level_publication import refresh as refresh_level

                    self.runtime.send_batch(
                        self.state.connection,
                        self.state.service,
                        refresh_level(
                            self.state.character,
                            self.runtime.STORE.characters(self.state.account_id),
                            entity_template=self.runtime.OWNED_HERO_TEMPLATE,
                            roster_template=self.runtime.CHARACTERS,
                            retained_state_packets=self.runtime.consumable_state_packets,
                        ),
                    )
                    self.runtime.send_native_planting_bonus(
                        self.state.connection, self.state.character
                    )
        except ValueError as error:
            reason = str(error)
            if self.state.environmental_publication_error != reason:
                self.runtime.record(
                    event="environmental_publication_rejected",
                    actor_id=self.state.character["id"],
                    reason=reason,
                )
            self.state.environmental_publication_error = reason
            return
        self.state.environmental_publication_error = None

    def poll_external_objectives(self):
        """Consume asynchronous objective changes only in a ready world scene."""
        from wakfu_server.custom_tasks import external

        if not external.enabled():
            return
        now = time.monotonic()
        if self.state.loaded and now >= self.state.objectives_hunt_poll_at:
            from wakfu_server.objectives import hunts

            self.state.objectives_hunt_poll_at = now + 1.0
            hunts.publish(
                self.runtime.STORE, self.runtime.COMBAT_GROUPS, self.runtime.WORLD
            )
        if not (
            self.state.loaded
            and self.state.character is not None
            and self.state.fight is None
            and self.state.combat_session is None
            and self.state.hero_switch_pending is None
            and self.state.spectator_session is None
        ):
            return
        updates = getattr(self.state.connection, "objectives_updates", None)
        if updates is not None:
            updates.character_id = self.state.character["id"]
        notified = updates is not None and updates.dirty.is_set()
        if now < self.state.objectives_poll_at and not notified:
            return
        if updates is not None:
            updates.dirty.clear()
        self.state.objectives_poll_at = now + 1.0
        self.drain_objectives_player_actions()
        if self.state.pending_travel_resume is not None:
            return
        from wakfu_server.custom_tasks import service as task_service

        from wakfu_server.custom_tasks.exploration import observe
        from wakfu_server.objectives.progression import (
            observe as observe_account_progression,
        )

        observe(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
        )
        observe_account_progression(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
        )
        with self.runtime.STORE.connection() as db:
            snapshot = task_service.snapshot(
                db,
                self.state.account_id,
                self.state.character["id"],
                section=self.state.custom_task_cards.section,
                page=self.state.custom_task_cards.page,
            )
            pending = external.pending_rewards(db, self.state.character["id"])
        identity = (
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            snapshot,
        )
        if pending:
            self.deliver_custom_task_rewards()
        from wakfu_server.objectives.notices import deliver as deliver_objective_notices
        from wakfu_server.ecology_feedback import information

        with self.runtime.STORE.connection() as db:
            deliver_objective_notices(
                db,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                lambda text: self.runtime.send(
                    self.state.connection, self.state.service, *information(text)
                ),
            )
        if notified or identity != self.state.objectives_projection:
            self.state.custom_task_cards.changed(
                self.state.character["id"], (self.state.character["id"],)
            )
            self.publish_custom_task_cards()
            self.state.objectives_projection = identity

    def execute_objectives_command(self, text, *, browser_action=None):
        """Public objective navigation and fenced private weekly challenge entry."""
        from wakfu_server.command_permissions import authorize_command
        from wakfu_server.custom_tasks import external
        from wakfu_server.ecology_feedback import information

        arguments = text.split()
        command = arguments[0].lower() if arguments else ""
        try:
            authorize_command(self.runtime.STORE, self.state.account_id, text)
            if not external.enabled():
                raise ValueError("The objectives service is not enabled.")
            if not (
                self.state.loaded
                and self.state.character is not None
                and self.state.fight is None
                and self.state.combat_session is None
                and self.state.hero_switch_pending is None
                and self.state.spectator_session is None
            ):
                raise ValueError("Objectives require a ready scene outside combat.")
            if command == "!adventures":
                if len(arguments) != 1:
                    raise ValueError("Usage: !adventures")
                from wakfu_server.custom_tasks.player_actions import launch_url

                with self.runtime.STORE.connection() as db:
                    url = launch_url(
                        db,
                        self.state.account_id,
                        self.state.character["id"],
                        self.state.generation,
                    )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *information("Open your adventures: " + url),
                )
                return {"success": True, "message": "Adventures link created."}
            if command == "!tasks":
                from wakfu_server.custom_tasks.sections import parse

                section, page = parse(arguments[1:])
                self.state.custom_task_cards.select_view(section, page)
                self.publish_custom_task_cards()
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *information(
                        "Gifts window updated. Use !tasks <section> <page> to browse objectives."
                    ),
                )
                return {"success": True, "message": "Objectives view updated."}
            if (
                command != "!challenge"
                or len(arguments) != 2
                or arguments[1].lower() not in ("weekly", "return", "abandon")
            ):
                raise ValueError("Usage: !challenge weekly | return | abandon")
            if (
                self.state.bag_session is not None
                or self.state.ranch_session is not None
            ):
                raise ValueError(
                    "Leave your private scene before entering a weekly challenge."
                )
            from wakfu_server.objectives import challenges
            from wakfu_server.combat_terrain import map_geometry

            action = arguments[1].lower()
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                with self.runtime.COMBAT_GROUPS.lock:
                    with self.runtime.STORE.connection() as db:
                        db.execute(
                            "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                            (self.state.account_id,),
                        )
                        self.runtime.STORE.lock_character(
                            db,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            selected=True,
                        )
                        if browser_action is not None:
                            from wakfu_server.custom_tasks.player_actions import (
                                lock_running,
                            )

                            lock_running(db, browser_action)
                        if action == "weekly":
                            run = challenges.enter_weekly(
                                db,
                                self.runtime.COMBAT_GROUPS,
                                self.state.account_id,
                                self.state.character["id"],
                                geometry_loader=map_geometry,
                            )
                        else:
                            run = challenges.current_run(
                                db, self.state.account_id, self.state.character["id"]
                            )
                            challenges.return_from_challenge(
                                db,
                                self.state.account_id,
                                self.state.character["id"],
                                abandon=action == "abandon",
                            )
                        moved_ids = tuple(
                            row["character_id"]
                            for row in db.execute(
                                "SELECT character_id FROM objectives_challenge_members WHERE attempt_id=%s",
                                (run["attempt_id"],),
                            ).fetchall()
                        )
                        saved = self.runtime.STORE.character(
                            self.state.account_id, self.state.character["id"], db
                        )
                        if browser_action is not None:
                            from wakfu_server.custom_tasks.player_actions import finish

                            if not finish(
                                db,
                                browser_action,
                                {
                                    "success": True,
                                    "message": "Weekly challenge action completed.",
                                    "map_id": saved["map_id"],
                                    "instance_id": saved.get("instance_id", 0),
                                },
                            ):
                                raise ValueError(
                                    "Adventures action is no longer executable."
                                )
                for member_id in moved_ids:
                    self.runtime.POSITIONS.release(
                        self.state.account_id, self.state.generation, member_id
                    )
            self.cancel_crafting()
            self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
            self.state.character = saved
            self.runtime.POSITIONS.attach(
                self.state.account_id, self.state.generation, self.state.character
            )
            self.state.position = {
                key: self.state.character[key] for key in ("x", "y", "z")
            }
            self.state.movement_state = self.runtime.Movement(self.state.position)
            for packet in self.runtime.owned_native_bootstrap(self.state.character):
                self.runtime.send(self.state.connection, self.state.service, *packet)
            self.runtime.join_world(
                self.state.generation, self.state.connection, self.state.character
            )
            self.mark_static_sync_pending()
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *information(
                    "Weekly challenge ready. Defeat the private group, then use !challenge return."
                    if action == "weekly"
                    else "Returned from the weekly challenge."
                ),
            )
            return {
                "success": True,
                "message": "Weekly challenge action completed.",
                "map_id": self.state.character["map_id"],
                "instance_id": self.state.character.get("instance_id", 0),
            }
        except (ValueError, PermissionError) as error:
            self.runtime.send(
                self.state.connection, self.state.service, *information(str(error))
            )
            self.runtime.record(
                event="objectives_command_rejected",
                actor_id=self.state.character["id"],
                command=command,
                reason=str(error),
            )
            return {"success": False, "error": str(error)}

    def drain_objectives_player_actions(self):
        """Browser requests run on this socket's scene-owning dispatcher only."""
        from wakfu_server.custom_tasks import player_actions

        if not (
            self.state.loaded
            and self.state.character is not None
            and self.state.fight is None
            and self.state.combat_session is None
            and self.state.hero_switch_pending is None
            and self.state.spectator_session is None
            and not self.state.static_sync_pending
            and not self.state.world_snapshot_pending
            and self.state.pending_travel_resume is None
        ):
            return
        identity = {
            "account_id": self.state.account_id,
            "character_id": self.state.character["id"],
            "generation": self.state.generation,
        }
        with self.runtime.STORE.connection() as db:
            action = player_actions.claim(db, identity)
        if action is None:
            return
        target = action["target"]
        if target.get("kind") == "weekly" and target.get("action") in (
            "weekly",
            "return",
            "abandon",
        ):
            result = self.execute_objectives_command(
                "!challenge " + target["action"], browser_action=action
            )
        elif target.get("kind") == "travel":
            result = self.execute_objectives_travel(action)
        elif target.get("kind") == "seasonal_entry":
            result = self.execute_objectives_seasonal_entry(action)
        elif target.get("kind") == "pvp":
            result = self.execute_objectives_pvp(action)
        else:
            result = {"success": False, "error": "Unsupported adventures action."}
        with self.runtime.STORE.connection() as db:
            player_actions.finish(db, action, result)

    def handle_tutorial(self):
        from wakfu_server.tutorials import update as update_tutorials

        update_tutorials(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.body,
        )
        self.runtime.record(
            event="tutorial_state_saved", account_id=self.state.account_id
        )
        return DispatchResult.FALLTHROUGH

    def handle_world_dialogue(self):
        from wakfu_server import npc_dialogue, npc_world

        self.state.npc_dialogue = npc_dialogue
        self.state.npc_world = npc_world

        from wakfu_server import quest_npc
        from psycopg import Error as QuestDatabaseError
        from psycopg_pool import PoolTimeout as QuestPoolTimeout

        try:
            from . import (
                npc_owned_entry_dispatch,
                owned_story_npc_dispatch,
                owned_physical_offer_dispatch,
            )

            if owned_physical_offer_dispatch.handle(self):
                return DispatchResult.CONTINUE
            if npc_owned_entry_dispatch.handle(self) or owned_story_npc_dispatch.handle(
                self
            ):
                return DispatchResult.CONTINUE
            if (
                self.state.fight is None
                and self.state.spectator_session is None
                and self.state.bag_session is None
            ):
                from wakfu_server.npc_approach_target import approach_cells, resolve

                target = resolve(
                    self.runtime.STORE,
                    self.state.character,
                    self.state.opcode,
                    self.state.body,
                )
                if target is not None:
                    from wakfu_server.combat_geometry import prepare_geometry
                    from wakfu_server.combat_terrain import map_geometry

                    geometry = prepare_geometry(map_geometry(target["map_id"]))
                    goals = approach_cells(geometry, target)
                    if self.approach_actor(goals.__contains__, geometry=geometry):
                        return DispatchResult.CONTINUE
            from wakfu_server import ruel_investigation_npc

            if ruel_investigation_npc.recognizes(
                self.state.opcode, self.state.body, self.state.npc_dialogue_session
            ):
                if (
                    self.state.fight is not None
                    or self.state.spectator_session is not None
                ):
                    raise ValueError("Investigation requires being out of combat")
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    if self.state.opcode == 12058:
                        suspect_result = ruel_investigation_npc.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.body,
                        )
                        suspect_packets = suspect_result["packets"]
                    else:
                        if self.state.opcode == 13222:
                            (
                                self.state.actor_id,
                                self.state._,
                            ) = self.state.npc_world.decode_interaction(self.state.body)
                        else:
                            self.state.actor_id = (
                                self.state.npc_dialogue.decode_request(
                                    self.state.opcode, self.state.body
                                )["speaker_id"]
                            )
                        (
                            self.state.npc_dialogue_session,
                            suspect_packets,
                        ) = ruel_investigation_npc.begin(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.actor_id,
                            character_provider=lambda: self.state.character,
                        )
                    self.publish_settled_quest_packets(suspect_packets)
                return DispatchResult.CONTINUE
            from wakfu_server import ruel_hunt_npc

            if ruel_hunt_npc.recognizes(
                self.runtime.STORE,
                self.state.opcode,
                self.state.body,
                self.state.npc_dialogue_session,
            ):
                if (
                    self.state.fight is not None
                    or self.state.spectator_session is not None
                ):
                    raise ValueError("Ruel requiere estar fuera de combate")
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    if self.state.opcode == 12058:
                        self.state.result = ruel_hunt_npc.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.body,
                        )
                        ruel_packets = self.state.result["packets"]
                    else:
                        if self.state.opcode == 13222:
                            (
                                self.state.actor_id,
                                self.state.action_id,
                            ) = self.state.npc_world.decode_interaction(self.state.body)
                        else:
                            self.state.request = self.state.npc_dialogue.decode_request(
                                self.state.opcode, self.state.body
                            )
                            self.state.actor_id, self.state.action_id = (
                                self.state.request["speaker_id"],
                                ruel_hunt_npc.ACTION,
                            )
                        (
                            self.state.npc_dialogue_session,
                            ruel_packets,
                        ) = ruel_hunt_npc.begin(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.actor_id,
                            self.state.action_id,
                            character_provider=lambda: self.state.character,
                        )
                    self.publish_settled_quest_packets(ruel_packets)
                return DispatchResult.CONTINUE
            from wakfu_server import modulox_npc

            if modulox_npc.recognizes(
                self.runtime.STORE,
                self.state.opcode,
                self.state.body,
                self.state.npc_dialogue_session,
            ):
                if (
                    self.state.fight is not None
                    or self.state.spectator_session is not None
                ):
                    raise ValueError("Mod'Ulo requiere estar fuera de combate")
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    if self.state.opcode == 12058:
                        self.state.outcome = modulox_npc.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.body,
                            bag_session=self.state.bag_session,
                        )
                        modulox_packets = self.state.outcome["packets"]
                    else:
                        if self.state.opcode == 13222:
                            (
                                self.state.actor_id,
                                self.state.action_id,
                            ) = self.state.npc_world.decode_interaction(self.state.body)
                        else:
                            self.state.request = self.state.npc_dialogue.decode_request(
                                self.state.opcode, self.state.body
                            )
                            self.state.actor_id, self.state.action_id = (
                                self.state.request["speaker_id"],
                                modulox_npc.ACTION,
                            )
                        (
                            self.state.npc_dialogue_session,
                            modulox_packets,
                        ) = modulox_npc.begin(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.actor_id,
                            self.state.action_id,
                            bag_session=self.state.bag_session,
                            character_provider=lambda: self.state.character,
                        )
                    for modulox_packet in modulox_packets:
                        self.runtime.send(
                            self.state.connection, self.state.service, *modulox_packet
                        )
                return DispatchResult.CONTINUE
            from wakfu_server import weekly_hunter_npc

            if weekly_hunter_npc.recognizes(
                self.runtime.STORE,
                self.state.opcode,
                self.state.body,
                self.state.npc_dialogue_session,
            ):
                if (
                    self.state.fight is not None
                    or self.state.spectator_session is not None
                ):
                    raise ValueError(
                        "Hunter conversations require a ready scene outside combat"
                    )
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    if self.state.opcode == 12058:
                        self.state.outcome = weekly_hunter_npc.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.body,
                        )
                        hunter_packets = self.state.outcome["packets"]
                    else:
                        (
                            self.state.actor_id,
                            self.state.action_id,
                        ) = self.state.npc_world.decode_interaction(self.state.body)
                        (
                            self.state.npc_dialogue_session,
                            hunter_packets,
                        ) = weekly_hunter_npc.begin(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.actor_id,
                            self.state.action_id,
                            character_provider=lambda: self.state.character,
                        )
                    for hunter_packet in hunter_packets:
                        self.runtime.send(
                            self.state.connection, self.state.service, *hunter_packet
                        )
                return DispatchResult.CONTINUE
            if (
                self.state.opcode == 13222
                and self.state.loaded
                and self.state.fight is None
                and self.state.spectator_session is None
            ):
                # A captured ordinary NPC may retain its base provider while
                # one explicitly guarded, published story branch is active.
                actor_id, action_id = self.state.npc_world.decode_interaction(
                    self.state.body
                )
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    overlay = quest_npc.try_native_overlay(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        actor_id,
                        action_id,
                        character_provider=lambda: self.state.character,
                        provider_field="existing_dialogue_actor",
                    )
                if overlay is not None:
                    if self.state.npc_dialogue_session is not None:
                        self.state.npc_dialogue_session.close()
                    self.state.npc_dialogue_session, overlay_packets = overlay
                    self.publish_settled_quest_packets(overlay_packets)
                    return DispatchResult.CONTINUE
            qualified_quest = quest_npc.recognizes(
                self.runtime.STORE,
                self.state.opcode,
                self.state.body,
                self.state.npc_dialogue_session,
            )
            if qualified_quest:
                if (
                    self.state.fight is not None
                    or self.state.spectator_session is not None
                ):
                    raise ValueError(
                        "Quest conversations require a ready scene outside combat"
                    )
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    if self.state.opcode == 12058:
                        self.state.outcome = quest_npc.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.body,
                        )
                    else:

                        def quest_rows():
                            with self.runtime.STORE.connection() as quest_db:
                                return self.state.npc_world.load_scene(
                                    quest_db,
                                    self.state.character["map_id"],
                                    self.state.character["instance_id"],
                                )

                        if self.state.opcode == 13222:
                            (
                                self.state.actor_id,
                                self.state.action_id,
                            ) = self.state.npc_world.decode_interaction(self.state.body)
                        else:
                            self.state.request = self.state.npc_dialogue.decode_request(
                                self.state.opcode, self.state.body
                            )
                            row = next(
                                (
                                    row
                                    for row in quest_rows()
                                    if self.state.npc_world.matches_open_request(
                                        row, self.state.request
                                    )
                                ),
                                None,
                            )
                            if row is None:
                                raise ValueError(
                                    "Unavailable qualified quest dialogue root"
                                )
                            self.state.actor_id, self.state.action_id = (
                                row["actor_id"],
                                row["action_ids"][0],
                            )
                        (
                            self.state.npc_dialogue_session,
                            quest_packets,
                        ) = quest_npc.begin(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.actor_id,
                            self.state.action_id,
                            character_provider=lambda: self.state.character,
                            rows_provider=quest_rows,
                        )
                        self.state.outcome = dict(packets=quest_packets)

                    def publish_quest_packets():
                        self.publish_settled_quest_packets(
                            self.state.outcome["packets"]
                        )

                    if "saved" in self.state.outcome:
                        self.publish_public_transport(
                            self.state.outcome["transport"],
                            self.state.outcome["saved"],
                            generic_route=True,
                            before_bootstrap=publish_quest_packets,
                        )
                    else:
                        publish_quest_packets()
                return DispatchResult.CONTINUE
        except (
            ValueError,
            UnicodeError,
            QuestDatabaseError,
            QuestPoolTimeout,
        ) as error:
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Quest conversation is temporarily unavailable."
                ),
            )
            self.runtime.record(
                event="qualified_quest_conversation_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
            return DispatchResult.CONTINUE

        from wakfu_server import rii_dialogue_gate

        if (
            not self.state.npc_dialogue.interactions_enabled()
            and not rii_dialogue_gate.allow(
                self.state.opcode,
                self.state.body,
                self.state.character,
                self.state.npc_dialogue_session,
            )
        ):
            if self.state.npc_dialogue_session is not None or self.state.opcode in (
                12058,
                12535,
            ):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.npc_dialogue.disabled_response(
                        self.state.npc_dialogue_session
                    ),
                )
            self.state.npc_dialogue_session = None
            return DispatchResult.CONTINUE

        from wakfu_server import npc_objective_facts

        self.state.npc_objective_facts = npc_objective_facts
        from wakfu_server.ecology_feedback import information

        self.state.information = information
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout

        from wakfu_server.achievements import rii_free_practice

        self.state.rii_free_practice = rii_free_practice

        if (
            self.state.opcode == 13222
            and len(self.state.body) == 16
            and self.state.npc_world.decode_interaction(self.state.body)
            == (self.state.rii_free_practice.ACTOR, self.state.rii_free_practice.ACTION)
        ):
            try:
                if (
                    not self.runtime.COMBAT_TEST
                    or self.state.fight is not None
                    or self.state.spectator_session is not None
                ):
                    raise ValueError("Practice is unavailable during combat")
                if self.state.pending_guardian_attack is not None:
                    raise ValueError("A tutorial combat is already pending")

                def practice_rows():
                    with self.runtime.STORE.connection() as db:
                        return self.state.npc_world.load_scene(
                            db,
                            self.state.character["map_id"],
                            self.state.character["instance_id"],
                        )

                if self.state.npc_dialogue_session is not None:
                    self.state.npc_dialogue_session.close()
                (
                    self.state.npc_dialogue_session,
                    self.state.packet,
                ) = self.state.rii_free_practice.begin_menu(
                    lambda: self.state.character,
                    practice_rows,
                    self.state.rii_free_practice.ACTOR,
                    self.state.rii_free_practice.ACTION,
                )
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            except (
                ValueError,
                self.state.DatabaseError,
                self.state.PoolTimeout,
            ) as error:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(str(error)),
                )
            return DispatchResult.CONTINUE

        try:
            if self.state.fight is not None or self.state.spectator_session is not None:
                if self.state.npc_dialogue_session is not None:
                    self.state.npc_dialogue_session.close()
                self.state.npc_dialogue_session = None
                raise ValueError("NPC dialogue is unavailable during combat")

            def dialogue_rows():
                with self.runtime.STORE.connection() as db:
                    return self.state.npc_world.load_scene(
                        db,
                        self.state.character["map_id"],
                        self.state.character["instance_id"],
                    )

            def dialogue_facts():
                # Keep the current leased scene position. Reading
                # owned objective facts must not reload SQL exterior
                # coordinates while inside a private scene.
                with self.runtime.STORE.connection() as db:
                    return self.state.npc_objective_facts.load(
                        db, self.state.account_id, self.state.character["id"]
                    )

            if self.state.opcode == 12058:
                if self.state.npc_dialogue_session is None:
                    raise ValueError("No NPC conversation is active")
                self.state.request = self.state.npc_dialogue.decode_request(
                    self.state.opcode, self.state.body
                )
                from wakfu_server import rii_conversation_progress
                from wakfu_server import rii_ecosystem_dialogue
                from wakfu_server import rii_otomai_fresco

                if getattr(
                    self.state.npc_dialogue_session, "rii_free_practice_menu", False
                ):
                    (
                        self.state.packet,
                        start_practice,
                    ) = self.state.rii_free_practice.choose_menu(
                        self.state.npc_dialogue_session, self.state.request
                    )
                    if start_practice:
                        if (
                            not self.runtime.COMBAT_TEST
                            or self.state.pending_guardian_attack is not None
                        ):
                            raise ValueError("Practice is currently unavailable")
                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id
                            )
                            scene, sack = self.state.rii_free_practice.spawn(
                                self.runtime.STORE,
                                self.runtime.COMBAT_GROUPS,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character,
                                **start_practice,
                            )
                        if self.state.packet is not None:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                            self.state.packet = None
                        self.runtime.send(
                            self.state.connection, self.state.service, *scene
                        )
                        self.state.pending_guardian_attack = (
                            self.state.rii_free_practice.start_request(sack)
                        )
                elif rii_otomai_fresco.recognizes(
                    self.state.npc_dialogue_session, self.state.request
                ):
                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(account_id=self.state.account_id)
                        self.state.outcome = rii_otomai_fresco.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.request,
                        )
                        self.publish_settled_quest_packets(
                            self.state.outcome["packets"]
                        )
                        self.state.packet = self.state.outcome["packet"]
                elif rii_ecosystem_dialogue.recognizes(
                    self.state.npc_dialogue_session, self.state.request
                ):
                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(account_id=self.state.account_id)
                        self.state.outcome = rii_ecosystem_dialogue.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.request,
                        )
                        self.publish_settled_quest_packets(
                            self.state.outcome["packets"]
                        )
                        self.state.packet = self.state.outcome["packet"]
                elif rii_conversation_progress.recognizes(
                    self.state.npc_dialogue_session, self.state.request
                ):
                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(account_id=self.state.account_id)
                        self.state.outcome = rii_conversation_progress.choose(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.npc_dialogue_session,
                            self.state.request,
                        )
                        self.publish_settled_quest_packets(
                            self.state.outcome["packets"]
                        )
                        self.state.packet = self.state.outcome["packet"]
                        if (
                            self.state.request["node_id"],
                            self.state.request["choice_id"],
                        ) == (
                            5756,
                            13260,
                        ):
                            from wakfu_server.achievements import (
                                rii_orientation,
                            )

                            self.state.rii_orientation = rii_orientation

                            self.publish_rii_lesson_guide(
                                self.state.request["node_id"],
                                self.state.request["choice_id"],
                            )

                            try:
                                lesson_scene = self.state.rii_orientation.spawn(
                                    self.runtime.STORE,
                                    self.runtime.COMBAT_GROUPS,
                                    self.state.account_id,
                                    self.state.generation,
                                    self.state.character,
                                )
                                if lesson_scene:
                                    self.runtime.send(
                                        self.state.connection,
                                        self.state.service,
                                        *lesson_scene,
                                    )
                                self.queue_rii_lesson_attack(10574)
                            except Exception as error:
                                self.runtime.record(
                                    event="rii_orientation_spawn_error",
                                    reason=str(error),
                                )
                        if (
                            self.state.request["node_id"],
                            self.state.request["choice_id"],
                        ) == (
                            5791,
                            13347,
                        ):
                            from wakfu_server.achievements import (
                                rii_guardian_battle,
                            )

                            self.state.rii_guardian_battle = rii_guardian_battle

                            try:
                                guardian_scene = self.state.rii_guardian_battle.spawn(
                                    self.runtime.STORE,
                                    self.runtime.COMBAT_GROUPS,
                                    self.state.account_id,
                                    self.state.generation,
                                    self.state.character,
                                )
                                if guardian_scene:
                                    self.state.scene_packet, guardian = guardian_scene
                                    if self.state.scene_packet:
                                        self.runtime.send(
                                            self.state.connection,
                                            self.state.service,
                                            *self.state.scene_packet,
                                        )
                                    self.state.pending_guardian_attack = (
                                        self.state.rii_guardian_battle.start_request(
                                            guardian
                                        )
                                    )
                            except Exception as error:
                                self.runtime.record(
                                    event="rii_guardian_spawn_error",
                                    reason=str(error),
                                )
                else:
                    self.state.packet = self.choose_toolkit_dialogue(self.state.request)
                    from wakfu_server import rii_airyna_dialogue

                    self.state.airyna_repeat = (
                        self.state.request["node_id"] == rii_airyna_dialogue.ROOT
                        and self.state.request["choice_id"]
                        in rii_airyna_dialogue.REPEAT_OPTIONS
                    )
                    if self.state.airyna_repeat:
                        # The native "already done" entry re-runs the
                        # same exercise: settle it as its own lesson.
                        self.state.request["choice_id"] -= 8
                    if (
                        self.state.request["node_id"] == 5787
                        and 13322 <= self.state.request["choice_id"] <= 13328
                    ):
                        self.publish_rii_lesson_guide(
                            self.state.request["node_id"],
                            self.state.request["choice_id"],
                        )
                    if (
                        self.state.request["node_id"],
                        self.state.request["choice_id"],
                    ) == (
                        5787,
                        13322,
                    ):
                        from wakfu_server.achievements import (
                            rii_orientation,
                        )

                        self.state.rii_orientation = rii_orientation

                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id
                            )
                            lesson_scene = self.state.rii_orientation.spawn(
                                self.runtime.STORE,
                                self.runtime.COMBAT_GROUPS,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character,
                                repeat=self.state.airyna_repeat,
                            )
                        if lesson_scene:
                            self.runtime.send(
                                self.state.connection, self.state.service, *lesson_scene
                            )
                    if (
                        self.state.request["node_id"],
                        self.state.request["choice_id"],
                    ) == (
                        5787,
                        13323,
                    ):
                        from wakfu_server.achievements import (
                            rii_element_encounter,
                        )

                        self.state.rii_element_encounter = rii_element_encounter

                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id
                            )
                            lesson_scene = self.state.rii_element_encounter.spawn(
                                self.runtime.STORE,
                                self.runtime.COMBAT_GROUPS,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character,
                                repeat=self.state.airyna_repeat,
                            )
                        if lesson_scene:
                            self.runtime.send(
                                self.state.connection, self.state.service, *lesson_scene
                            )
                    if (
                        self.state.request["node_id"],
                        self.state.request["choice_id"],
                    ) == (
                        5787,
                        13324,
                    ):
                        from wakfu_server.achievements import (
                            rii_owned_lesson,
                        )

                        self.state.rii_owned_lesson = rii_owned_lesson

                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id
                            )
                            lesson_scene = self.state.rii_owned_lesson.spawn(
                                self.runtime.STORE,
                                self.runtime.COMBAT_GROUPS,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character,
                                self.state.rii_owned_lesson.DISTANCE,
                            )
                        if lesson_scene:
                            self.runtime.send(
                                self.state.connection, self.state.service, *lesson_scene
                            )
                    if (
                        self.state.request["node_id"],
                        self.state.request["choice_id"],
                    ) in (
                        (5787, 13325),
                        (5787, 13326),
                    ):
                        # Close the dialogue before replacing the owned map scene.
                        if self.state.packet is not None:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                            self.state.packet = None
                        if self.state.request["choice_id"] == 13325:
                            from wakfu_server.achievements import (
                                rii_los_encounter,
                            )

                            self.state.rii_los_encounter = rii_los_encounter

                            lesson_scene = self.begin_floor_training(
                                10608,
                                lambda store, groups, account, gen, actor: self.state.rii_los_encounter.spawn(
                                    store,
                                    groups,
                                    account,
                                    gen,
                                    actor,
                                    repeat=self.state.airyna_repeat,
                                ),
                            )
                        else:
                            from wakfu_server.achievements import (
                                rii_area_encounter,
                            )

                            self.state.rii_area_encounter = rii_area_encounter

                            lesson_scene = self.begin_floor_training(
                                10609,
                                lambda store, groups, account, gen, actor: self.state.rii_area_encounter.spawn(
                                    store,
                                    groups,
                                    account,
                                    gen,
                                    actor,
                                    repeat=self.state.airyna_repeat,
                                ),
                            )
                        # Private groups are omitted from exploration
                        # snapshots; admission publishes the owner's
                        # actors before combat references their IDs.
                        self.runtime.send(
                            self.state.connection, self.state.service, *lesson_scene
                        )
                    if (
                        self.state.request["node_id"],
                        self.state.request["choice_id"],
                    ) == (
                        5787,
                        13327,
                    ):
                        from wakfu_server.achievements import (
                            rii_owned_lesson,
                        )

                        self.state.rii_owned_lesson = rii_owned_lesson

                        if self.state.packet is not None:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                            self.state.packet = None
                        lesson_scene = self.begin_floor_training(
                            10610,
                            lambda store, groups, account, gen, actor: self.state.rii_owned_lesson.spawn(
                                store,
                                groups,
                                account,
                                gen,
                                actor,
                                self.state.rii_owned_lesson.MOVEMENT,
                                repeat=self.state.airyna_repeat,
                            ),
                        )
                        self.runtime.send(
                            self.state.connection, self.state.service, *lesson_scene
                        )
                    if (
                        self.state.request["node_id"],
                        self.state.request["choice_id"],
                    ) == (
                        5787,
                        13328,
                    ):
                        from wakfu_server.achievements import (
                            rii_owned_lesson,
                        )

                        self.state.rii_owned_lesson = rii_owned_lesson

                        if self.state.packet is not None:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                            self.state.packet = None
                        lesson_scene = self.begin_floor_training(
                            10611,
                            lambda store, groups, account, gen, actor: self.state.rii_owned_lesson.spawn(
                                store,
                                groups,
                                account,
                                gen,
                                actor,
                                self.state.rii_owned_lesson.STATES,
                                repeat=self.state.airyna_repeat,
                            ),
                        )
                        self.runtime.send(
                            self.state.connection, self.state.service, *lesson_scene
                        )
                    if (
                        self.state.request["node_id"] == 5787
                        and 13322 <= self.state.request["choice_id"] <= 13328
                    ):
                        objective = (
                            10574,
                            10575,
                            10576,
                            10608,
                            10609,
                            10610,
                            10611,
                        )[self.state.request["choice_id"] - 13322]
                        self.queue_rii_lesson_attack(objective)
            else:
                if self.state.opcode == 13222:
                    (
                        self.state.actor_id,
                        self.state.action_id,
                    ) = self.state.npc_world.decode_interaction(self.state.body)
                else:
                    self.state.request = self.state.npc_dialogue.decode_request(
                        self.state.opcode, self.state.body
                    )
                    from wakfu_server import rii_airyna_dialogue

                    if (
                        self.state.request["speaker_type"] == 2
                        and self.state.request["speaker_id"]
                        == rii_airyna_dialogue.ACTOR
                        and self.state.request["node_id"] == rii_airyna_dialogue.ROOT
                    ):
                        self.state.actor_id, self.state.action_id = (
                            rii_airyna_dialogue.ACTOR,
                            rii_airyna_dialogue.ACTION,
                        )
                    else:
                        self.state.actor_id, self.state.action_id = None, None
                    row = next(
                        (
                            npc
                            for npc in dialogue_rows()
                            if self.state.npc_world.matches_open_request(
                                npc, self.state.request
                            )
                        ),
                        None,
                    )
                    if row is None and self.state.actor_id is None:
                        raise ValueError("Unavailable NPC dialogue root")
                    if row is not None:
                        self.state.actor_id, self.state.action_id = (
                            row["actor_id"],
                            row["action_ids"][0],
                        )
                if self.state.npc_dialogue_session is not None:
                    self.state.npc_dialogue_session.close()
                from wakfu_server import rii_ecosystem_dialogue
                from wakfu_server import rii_airyna_dialogue

                returning = rii_airyna_dialogue.begin(
                    lambda: self.state.character,
                    dialogue_rows,
                    dialogue_facts,
                    self.state.actor_id,
                    self.state.action_id,
                )
                if returning is None:
                    returning = rii_ecosystem_dialogue.begin(
                        self.runtime.STORE,
                        lambda: self.state.character,
                        dialogue_rows,
                        self.state.account_id,
                        self.state.actor_id,
                        self.state.action_id,
                    )
                if returning is None:
                    (
                        self.state.npc_dialogue_session,
                        self.state.packet,
                    ) = self.state.npc_world.begin(
                        lambda: self.state.character,
                        dialogue_rows,
                        self.state.actor_id,
                        self.state.action_id,
                        facts_provider=dialogue_facts,
                    )
                else:
                    self.state.npc_dialogue_session, self.state.packet = returning
            if self.state.packet is not None:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
        except (
            ValueError,
            UnicodeError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
        ) as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    str(error)
                    if isinstance(error, ValueError)
                    else "NPC dialogue is temporarily unavailable."
                ),
            )
            self.runtime.record(
                event="npc_dialogue_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=(
                    str(error)
                    if isinstance(error, ValueError)
                    else type(error).__name__
                ),
                reason_type=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_guild_daily_quest(self):
        from wakfu_server.guild_daily_quests import activate
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.state.result = activate(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            for self.state.packet in self.state.result["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.record(
                event="guild_daily_quest_activated",
                actor_id=self.state.character["id"],
                definition_id=self.state.result["definition_id"],
                applied=self.state.result["applied"],
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Guild quests are temporarily unavailable."
                ),
            )
            self.runtime.record(
                event="guild_daily_quest_rejected",
                actor_id=self.state.character["id"],
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH
