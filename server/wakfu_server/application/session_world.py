"""World operations for one lease-bound World session."""

import struct
import time
from wakfu_server.performance_profiler import PROFILER
from .dispatch_result import DispatchResult


class WorldSessionMixin:
    @PROFILER.profile("world.static_sync")
    def sync_static_world(self, *, force=False, validated=False):
        if (
            self.state.character is None
            or self.state.fight is not None
            or (not self.state.static_sync_pending and not force)
        ):
            return
        if not force and time.monotonic() < self.state.static_sync_due:
            return
        if (
            self.state.account_id is None
            or self.state.generation is None
            or not self.runtime.STORE.current_session(
                self.state.account_id, self.state.generation
            )
        ):
            return
        if self.active_private_session() is not None:
            from wakfu_server.haven_ranch_portal import (
                config_message as ranch_portal_config,
            )

            self.runtime.send(
                self.state.connection, self.state.service, *ranch_portal_config()
            )
        ranch_furniture_scene = []
        if self.state.ranch_session is not None and self.state.ranch_session.owns(
            self.state.character
        ):
            from wakfu_server.haven_ranch_furniture import (
                snapshot as ranch_furniture_snapshot,
            )

            furniture_snapshot = ranch_furniture_snapshot(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                session=self.state.ranch_session,
                now_ms=int(self.runtime.STORE.now().timestamp() * 1000),
            )
            self.runtime.send(
                self.state.connection, self.state.service, *furniture_snapshot["packet"]
            )
            ranch_furniture_scene = furniture_snapshot["scene_packets"]
        if self.state.character["map_id"] != 9:
            from wakfu_server.treasure_definition_projections import (
                project_snapshot_bodies,
            )

            for message_body in project_snapshot_bodies(
                self.runtime.STORE,
                self.state.character["map_id"],
                self.runtime.world_static.snapshots(
                    self.state.character["map_id"], position=self.state.character
                ),
            ):
                self.runtime.send(
                    self.state.connection, self.state.service, 13984, message_body
                )
            for packet in ranch_furniture_scene:
                self.runtime.send(self.state.connection, self.state.service, *packet)
            self.publish_environment_scene(force=True)
            # Ruel's locally reconstructed assignment actor is sent after the
            # map scene so the client does not discard its native sprite.
            if self.state.character["map_id"] == 527:
                from wakfu_server import ruel_hunt_npc

                with self.runtime.STORE.connection() as db:
                    ruel_packet = ruel_hunt_npc.scene_packet(db, self.state.character)
                    from wakfu_server import ruel_investigation_npc

                    suspect_packets = ruel_investigation_npc.scene_packets(
                        db, self.state.character
                    )
                if ruel_packet is not None:
                    self.runtime.send(
                        self.state.connection, self.state.service, *ruel_packet
                    )
                for suspect_packet in suspect_packets:
                    self.runtime.send(
                        self.state.connection, self.state.service, *suspect_packet
                    )
            # The asset baseline also belongs to private dungeon scenes. Replay
            # its dynamic state first, then restore the run-owned door policy;
            # native default states must never reopen progression exits.
            if self.runtime.is_dungeon_run(self.state.character.get("instance_id", 0)):
                for message_id, message_body in self.runtime.owned_native_bootstrap(
                    self.state.character
                ):
                    if message_id == 12344:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            message_id,
                            message_body,
                        )
        elif self.state.bag_session is not None and self.state.bag_session.owns(
            self.state.character
        ):
            from wakfu_server.haven_bag_native_scene import packets as bag_scene_packets

            for message_id, message_body in bag_scene_packets(
                self.state.bag_session, self.state.character
            ):
                self.runtime.send(
                    self.state.connection, self.state.service, message_id, message_body
                )
            if self.state.bag_session.is_owner:
                # The client has loaded the private map by scene hydration.
                # An actor sent during the transition can be discarded before
                # the map exists, so publish it alongside the other bag actors.
                from wakfu_server import modulox_npc

                with self.runtime.STORE.connection() as npc_db:
                    modulox_scene = modulox_npc.scene_packet(
                        npc_db, self.state.bag_session, self.state.character
                    )
                if modulox_scene is not None:
                    self.runtime.send(
                        self.state.connection, self.state.service, *modulox_scene
                    )
                from wakfu_server.haven_chest_wire import (
                    scene_packet as chest_scene_packet,
                )

                for chest_object in self.runtime.world_static.objects(9):
                    if chest_object["type"] == "AccountChest":
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *chest_scene_packet(chest_object["id"]),
                        )
        from . import owned_story_dispatch

        owned_story_dispatch.hydrate(self)
        if validated:
            self.state.static_sync_pending = False
            self.state.static_sync_attempts = 0
        elif not force:
            # Only a due timer consumes the retry budget or moves its deadline.
            # Movement, interaction and 14689 can request an immediate resend
            # without starving the scheduled map-load retries.
            self.state.static_sync_attempts += 1
            self.state.static_sync_pending = self.state.static_sync_attempts < 3
            self.state.static_sync_due = time.monotonic() + 0.75
        self.runtime.record(
            event="static_map_state_synchronized",
            actor_id=self.state.character["id"],
            map_id=self.state.character["map_id"],
            instance_id=self.state.character.get("instance_id", 0),
            forced=force,
            validated=validated,
        )

    @PROFILER.profile("world.scene_sync")
    def sync_scene_world(self):
        """Hydrate newly loaded native scene partitions after local travel."""
        from . import owned_story_dispatch

        owned_story_dispatch.poll(self)
        if (
            not self.state.loaded
            or self.state.character is None
            or self.state.fight is not None
            or self.state.spectator_session is not None
        ):
            return
        if self.state.character["map_id"] == 9:
            return
        packets = self.state.scene_sync.poll(
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
            time.monotonic(),
        )
        if packets:
            from wakfu_server.treasure_definition_projections import (
                project_snapshot_bodies,
            )

            packets = project_snapshot_bodies(
                self.runtime.STORE, self.state.character["map_id"], packets
            )
        if not packets and not self.state.scene_sync.last_regions:
            return
        # csV/cgN shifts the native interactive registry independently of the
        # terrain camera. Raw assets must be registered before state hydration.
        self.runtime.send_batch(
            self.state.connection,
            self.state.service,
            (
                (
                    12318,
                    struct.pack(
                        ">ii", self.state.character["x"], self.state.character["y"]
                    ),
                ),
                *((13984, payload) for payload in packets),
            ),
        )
        # The connection publishes each native attachment once and converts
        # retained-object hydration to in-place state updates.
        # Replay the same animated-path partitions as the static hydration.
        # Character coordinates already name the endpoint while the client is
        # still walking; selecting only that endpoint loses intermediate flora.
        resource_packets = self.runtime.PLANTINGS.snapshots(
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
            position=self.state.character,
            chunks=self.state.scene_sync.last_regions,
        )
        self.runtime.send_batch(
            self.state.connection, self.state.service, resource_packets
        )
        self.publish_environment_scene(force=True)
        if self.state.character["map_id"] == 1361:
            from wakfu_server.achievements import incarnam_resources, storage

            if incarnam_resources.owned_scene(self.state.character):
                with self.runtime.STORE.connection() as tutorial_db:
                    tutorial_state = storage.load_locked(
                        tutorial_db, self.state.character["id"]
                    )
                for tutorial_packet in incarnam_resources.first_barrier_packets(
                    self.state.character, tutorial_state
                ) + incarnam_resources.gate_state_packets(
                    self.state.character, tutorial_state
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *tutorial_packet
                    )
        if self.runtime.is_dungeon_run(self.state.character.get("instance_id", 0)):
            for message_id, payload in self.runtime.owned_native_bootstrap(
                self.state.character
            ):
                if message_id == 12344:
                    self.runtime.send(
                        self.state.connection, self.state.service, message_id, payload
                    )
        if self.runtime.is_dungeon_run(self.state.character.get("instance_id", 0)):
            owned_story_dispatch.hydrate(
                self, chunks=self.state.scene_sync.last_regions
            )
        self.runtime.record(
            event="scene_objects_synchronized",
            actor_id=self.state.character["id"],
            map_id=self.state.character["map_id"],
            instance_id=self.state.character.get("instance_id", 0),
            packets=len(packets),
            bytes=sum(map(len, packets)),
            object_ids=self.runtime.snapshot_ids(packets),
        )

    @PROFILER.profile("world.snapshot")
    def send_loaded_world_snapshot(self, *, reconcile_markers=True):
        """Rebuild the current loaded map for this peer after scene transitions."""
        if (
            self.state.character is None
            or not self.state.loaded
            or self.state.account_id is None
            or self.state.generation is None
        ):
            raise ValueError("Loaded world session is required")
        if self.state.fight is not None or self.state.combat_session is not None:
            raise ValueError("Cannot rebuild an exploration snapshot during combat")
        if self.state.character.get("map_id") == 9:
            raise ValueError("Private haven-bag maps do not use world replay")
        if not self.runtime.STORE.current_session(
            self.state.account_id, self.state.generation
        ):
            raise ValueError("World snapshot session is stale")
        if not self.runtime.WORLD.resynchronize(
            self.state.generation, self.state.connection, self.state.character
        ):
            raise ValueError("Player snapshot delivery failed")
        for packet in self.runtime.HAVEN_BAG_EXTERIORS.snapshots(self.state.character):
            self.runtime.send(self.state.connection, self.state.service, *packet)
        # This is a complete current-map snapshot, so it also validates the
        # static-object load. Do not leave the independent retry timer armed
        # to resend the same 13984 packets after the world replay.
        self.sync_static_world(force=True, validated=True)
        self.runtime.send_planting_context(self.state.connection, self.state.character)
        for packet in self.runtime.PLANTINGS.snapshots(
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
            position=self.state.character,
        ):
            self.runtime.send(self.state.connection, self.state.service, *packet)
        if self.runtime.COMBAT_TEST:
            from wakfu_server.combat_monster_world import spawn_group
            from wakfu_server.combat_world_group_cleanup import defeated_snapshot

            with self.runtime.COMBAT_GROUPS.lock:
                with self.runtime.STORE.connection() as db:
                    from wakfu_server.achievements.rii_lesson_visibility import (
                        scene_cleanup,
                    )

                    for packet in scene_cleanup(
                        db,
                        self.state.character["map_id"],
                        self.state.character.get("instance_id", 0),
                    ):
                        self.runtime.send(
                            self.state.connection, self.state.service, *packet
                        )
                    for packet in defeated_snapshot(
                        db,
                        self.state.character["map_id"],
                        self.state.character.get("instance_id", 0),
                    ):
                        self.runtime.send(
                            self.state.connection, self.state.service, *packet
                        )
                for packet in self.runtime.monster_corpse_snapshot(
                    self.state.character["map_id"],
                    self.state.character.get("instance_id", 0),
                    peer=self.state.connection,
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
                groups = self.runtime.COMBAT_GROUPS.available(
                    self.state.character["map_id"],
                    self.state.character.get("instance_id", 0),
                )
                if self.state.character["map_id"] in (1387, 1388):
                    from wakfu_server.achievements.rii_lesson_visibility import (
                        visible_groups,
                    )

                    with self.runtime.STORE.connection() as db:
                        groups = visible_groups(db, groups, self.state.character["id"])
                from wakfu_server.achievements import source_quest_encounters

                if any(
                    source_quest_encounters.candidate_monsters(group["members"])
                    for group in groups
                ):
                    with self.runtime.STORE.connection() as db:
                        groups = source_quest_encounters.visible_groups(
                            db, groups, self.state.character["id"]
                        )
                for group in groups:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        12608,
                        self.runtime.owned_scene_spawn_group(
                            group["members"], group_id=group["key"][2]
                        ),
                    )
        for packet in self.runtime.HARVESTS.availability_snapshot(
            self.state.character["map_id"], self.state.character.get("instance_id", 0)
        ):
            self.runtime.send(self.state.connection, self.state.service, *packet)
        if self.runtime.COMBAT_TEST:
            # bvU restores retained external contexts before sending 12154.
            # Serialize selection with actual writes so concurrent new markers
            # cannot be created twice for the same native recipient scene.
            with self.state.connection.write_lock:
                known = (
                    self.state.connection.marker_publications.snapshot(
                        self.state.connection.native_instance_scope()
                    )
                    if reconcile_markers
                    else None
                )
                packets = self.runtime.EXTERNAL_FIGHT_MARKERS.world_snapshots(
                    self.state.character["map_id"],
                    self.state.character.get("instance_id", 0),
                    exclude_character_id=self.state.character["id"],
                    known_phases=known,
                    known_rosters=(
                        self.state.connection.marker_publications.roster_snapshot(
                            self.state.connection.native_instance_scope()
                        )
                        if reconcile_markers
                        else None
                    ),
                    unbound_members=(
                        self.state.connection.marker_publications.unbound_snapshot(
                            self.state.connection.native_instance_scope()
                        )
                        if reconcile_markers
                        else None
                    ),
                )
                self.runtime.send_batch(
                    self.state.connection, self.state.service, packets
                )

    def sync_loaded_world_snapshot(self, *, force=False):
        if (
            not self.state.world_snapshot_pending
            or not self.state.loaded
            or self.state.character is None
        ):
            return False
        if self.state.fight is not None or self.state.combat_session is not None:
            return False
        if self.state.character.get("map_id") == 9:
            # Each haven bag is a private instance; the normal join already
            # supplied its scoped state and must not trigger public replay.
            self.state.world_snapshot_pending = False
            return False
        identity = (
            self.state.character["id"],
            self.state.generation,
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
        )
        if identity != self.state.world_snapshot_identity:
            self.state.world_snapshot_pending = False
            return False
        if not force and time.monotonic() < self.state.world_snapshot_due:
            return False
        try:
            self.send_loaded_world_snapshot()
        except ValueError as error:
            self.runtime.record(
                event="world_snapshot_resynchronization_failed",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.state.world_snapshot_pending = False
            return False
        self.state.world_snapshot_pending = False
        self.runtime.record(
            event="world_snapshot_resynchronized",
            actor_id=self.state.character["id"],
            map_id=self.state.character["map_id"],
            instance_id=self.state.character.get("instance_id", 0),
            trigger="ready" if force else "fallback",
        )
        return True

    def refresh_owned_world_after_spectating(self):
        """Restore the loaded observer's current world snapshot after 12154."""
        if (
            self.state.character is None
            or self.state.account_id is None
            or self.state.generation is None
        ):
            raise ValueError("Loaded observer session is required")
        self.send_loaded_world_snapshot(reconcile_markers=True)
        self.state.world_snapshot_pending = False

    def mark_static_sync_pending(self, *, world_ready=False):
        self.state.scene_sync.arm(
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
            [self.state.character],
            time.monotonic(),
        )
        self.state.static_sync_pending = True
        self.state.static_sync_attempts = 0
        self.state.static_sync_due = time.monotonic() + 0.75
        self.state.world_snapshot_pending = (
            not world_ready and self.state.character.get("map_id") != 9
        )
        self.state.world_snapshot_due = self.state.static_sync_due
        self.state.world_snapshot_identity = (
            self.state.character["id"],
            self.state.generation,
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
        )

    def handle_position_save(self):
        from wakfu_server.position_buffer import PositionOwnerBusy

        self.state.PositionOwnerBusy = PositionOwnerBusy
        from wakfu_server.position_redis import PositionJournalError

        try:
            self.request_world_respawn(self.state.body)
        except (
            ValueError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
            self.state.PositionOwnerBusy,
            PositionJournalError,
        ) as error:
            self.state.reason = (
                str(error)
                if isinstance(error, ValueError)
                else "Reintenta el regreso al fénix"
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.reason),
            )
            self.runtime.record(
                event="world_respawn_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.reason,
            )
        return DispatchResult.FALLTHROUGH

    def handle_position_checkpoint(self):
        from psycopg import Error as ResurrectionDatabaseError
        from psycopg_pool import PoolTimeout as ResurrectionPoolTimeout
        from wakfu_server.position_buffer import PositionOwnerBusy

        self.state.PositionOwnerBusy = PositionOwnerBusy

        try:
            self.resurrect_world_character(self.state.body)
        except (
            ValueError,
            ResurrectionDatabaseError,
            ResurrectionPoolTimeout,
            self.state.PositionOwnerBusy,
        ) as error:
            self.state.reason = (
                str(error)
                if isinstance(error, ValueError)
                else "Reintenta la resurrección"
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.reason),
            )
            self.runtime.record(
                event="world_resurrection_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.reason,
            )
        return DispatchResult.FALLTHROUGH

    def handle_world_loaded(self):
        from wakfu_server.achievements import rii_dojo_arrival
        from wakfu_server.intro_cinematic import callback_id

        try:
            scenario_callback = callback_id(self.state.body)
            from . import source_quest_encounter_dispatch

            if source_quest_encounter_dispatch.handle_callback(self, scenario_callback):
                return DispatchResult.CONTINUE
            from . import owned_story_dispatch

            if owned_story_dispatch.handle_callback(self):
                return DispatchResult.CONTINUE
            if (
                scenario_callback in (23908, 23909, 23910, 23912)
                and self.state.intro_cinematic_scene is not None
            ):
                self.state.action = self.state.intro_cinematic_scene.receive(
                    self.state.body, map_id=self.state.character["map_id"]
                )
                if (
                    self.state.action is not None
                    and self.state.action[0] == "enter_incarnam"
                ):
                    from wakfu_server import (
                        intro_cinematic,
                        mission_transport,
                    )

                    self.state.intro_cinematic = intro_cinematic
                    self.state.mission_transport = mission_transport

                    try:
                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id,
                                generation=self.state.generation,
                                character_id=self.state.character["id"],
                            )
                            self.state.source = self.runtime.STORE.character(
                                self.state.account_id, self.state.character["id"]
                            )
                            if self.state.source["map_id"] != 1465:
                                raise ValueError(
                                    "Introductory scene is no longer active"
                                )
                            self.state.route = {
                                "direction": 0,
                                "destination": {
                                    "map_id": 1361,
                                    "instance_id": self.state.intro_cinematic.private_instance_id(
                                        self.state.source["id"]
                                    ),
                                    "x": 0,
                                    "y": 0,
                                    "z": 0,
                                },
                            }
                            (
                                self.state.saved,
                                self.state.packets,
                            ) = self.state.mission_transport.transition(
                                self.runtime.STORE,
                                self.state.account_id,
                                self.state.generation,
                                self.state.source,
                                self.state.route,
                                native_zaap=False,
                            )
                            self.publish_public_transport(
                                self.state.route, self.state.saved, generic_route=True
                            )
                            for self.state.packet in self.state.packets:
                                self.runtime.send(
                                    self.state.connection,
                                    self.state.service,
                                    *self.state.packet,
                                )
                            from wakfu_server.achievements import (
                                incarnam_tutorial,
                                storage,
                            )

                            self.state.incarnam_tutorial = incarnam_tutorial
                            self.state.storage = storage

                            with self.runtime.STORE.connection() as self.state.db:
                                self.state.tutorial_state = (
                                    self.state.storage.load_locked(
                                        self.state.db, self.state.saved["id"]
                                    )
                                )
                            self.state.connection.pending_incarnam_arrival = (
                                self.state.saved["id"],
                                21800,
                            )
                            for (
                                self.state.packet
                            ) in self.state.incarnam_tutorial.initial_packets(
                                self.state.tutorial_state
                            ):
                                self.runtime.send(
                                    self.state.connection,
                                    self.state.service,
                                    *self.state.packet,
                                )
                    except Exception:
                        self.state.intro_cinematic_scene.retry_completion()
                        raise
                    self.state.intro_cinematic_scene = None
                elif self.state.action is not None:
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.action
                    )
            elif scenario_callback in (21800, 22519, 22521):
                from wakfu_server.achievements import incarnam_tutorial

                self.state.incarnam_tutorial = incarnam_tutorial

                self.state.pending = getattr(
                    self.state.connection, "pending_incarnam_arrival", None
                )
                if scenario_callback == 21800 and self.state.pending is None:
                    from wakfu_server.achievements import storage

                    with self.runtime.STORE.connection() as tutorial_db:
                        resumed_state = storage.load_locked(
                            tutorial_db, self.state.character["id"]
                        )
                    if incarnam_tutorial.is_resumed_scene_ready(
                        self.state.character,
                        resumed_state,
                        scenario_callback,
                        self.state.pending,
                    ):
                        return DispatchResult.FALLTHROUGH
                if self.state.character["map_id"] != 1361 or self.state.pending != (
                    self.state.character["id"],
                    scenario_callback,
                ):
                    raise ValueError("Incarnam arrival scene is not pending")
                next_event = {21800: 22519, 22519: 22521, 22521: 22522}[
                    scenario_callback
                ]
                self.state.connection.pending_incarnam_arrival = (
                    (self.state.character["id"], next_event)
                    if next_event != 22522
                    else None
                )
                if scenario_callback in (22519, 22521):
                    # The tree cinematic is far from the real spawn.
                    # Relocate the client camera and hydrate that
                    # region before starting the corresponding Lua.
                    from wakfu_server.treasure_definition_projections import (
                        project_snapshot_bodies,
                    )

                    self.state.packets = (
                        self.state.incarnam_tutorial.cinematic_camera_travel(
                            self.state.character["id"], scenario_callback
                        )
                    )
                    for self.state.packet in self.state.packets:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    self.state.x, self.state.y = struct.unpack(
                        ">ii", self.state.packets[-1][1]
                    )
                    scene_position = {
                        **self.state.character,
                        "x": self.state.x,
                        "y": self.state.y,
                    }
                    for self.state.payload in project_snapshot_bodies(
                        self.runtime.STORE,
                        self.state.character["map_id"],
                        self.runtime.world_static.snapshots(
                            self.state.character["map_id"], position=scene_position
                        ),
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            13984,
                            self.state.payload,
                        )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.incarnam_tutorial.scenario_packet(next_event),
                )
            elif scenario_callback == 22525:
                from wakfu_server.achievements import incarnam_tutorial

                self.state.incarnam_tutorial = incarnam_tutorial

                if (
                    self.state.character["map_id"] != 1361
                    or getattr(
                        self.state.connection, "pending_incarnam_seed_guide", None
                    )
                    != self.state.character["id"]
                ):
                    raise ValueError("Incarnam planting guide is not pending")
                self.state.incarnam_tutorial.finish_planting_guide(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
                self.state.connection.pending_incarnam_seed_guide = None
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.incarnam_tutorial.scenario_packet(22566),
                )
            elif scenario_callback == 22359:
                from wakfu_server import intro_cinematic, mission_transport

                self.state.intro_cinematic = intro_cinematic
                self.state.mission_transport = mission_transport

                if (
                    self.state.fight is not None
                    or self.state.combat_session is not None
                ):
                    raise ValueError("Incarnam cinematic cannot finish during combat")
                if (
                    getattr(self.state.connection, "pending_incarnam_outro", None)
                    != self.state.character["id"]
                ):
                    raise ValueError("Incarnam cinematic is not pending")
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                    )
                    self.state.source = self.runtime.STORE.character(
                        self.state.account_id, self.state.character["id"]
                    )
                    if self.state.source.get("map_id") != 1361 or self.state.source.get(
                        "instance_id"
                    ) != self.state.intro_cinematic.private_instance_id(
                        self.state.source["id"]
                    ):
                        raise ValueError("Incarnam scene is no longer active")
                    self.state.route = {
                        "direction": 0,
                        "destination": {
                            "map_id": 1385,
                            "instance_id": 0,
                            "x": 27,
                            "y": 1,
                            "z": 1,
                        },
                    }
                    (
                        self.state.saved,
                        self.state.packets,
                    ) = self.state.mission_transport.transition(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.source,
                        self.state.route,
                        native_zaap=False,
                        incarnam_exit=True,
                    )
                    self.state.connection.pending_incarnam_outro = None
                    self.state.connection.pending_rii_intro = self.state.saved["id"]
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.incarnam_tutorial.scenario_packet(22500),
                    )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.incarnam_tutorial.interface_recovery_packet(),
                    )
                    self.publish_public_transport(
                        self.state.route, self.state.saved, generic_route=True
                    )
                    for self.state.packet in self.state.packets:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
            elif scenario_callback == 22532:
                from wakfu_server.achievements import rii_guardian_battle

                self.state.rii_guardian_battle = rii_guardian_battle

                if (
                    self.state.fight is not None
                    or self.state.combat_session is not None
                ):
                    raise ValueError("Guardian cinematic cannot finish during combat")
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                    )
                    self.state.source = self.runtime.STORE.character(
                        self.state.account_id, self.state.character["id"]
                    )
                    (
                        self.state.saved,
                        self.state.mission_packets,
                    ) = self.state.rii_guardian_battle.finish_cinematic(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.source,
                    )
                    for self.state.packet in self.state.mission_packets:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    self.publish_public_transport(
                        {"direction": 0}, self.state.saved, generic_route=True
                    )
            elif scenario_callback == rii_dojo_arrival.READY:
                # The installed dojo script reports its ready event.
                # The original server completes the hidden dojo
                # carrier from exactly this callback.
                if self.state.character["map_id"] != rii_dojo_arrival.DOJO_MAP:
                    raise ValueError("Dojo arrival is not the active scene")
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                    )
                    for self.state.packet in rii_dojo_arrival.deliver_callback(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.runtime.STORE.character(
                            self.state.account_id, self.state.character["id"]
                        ),
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
            elif scenario_callback in (23920, 23922, 23924, 23926, 23927, 23928):
                from wakfu_server.achievements import astrub_cat_story

                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    result = astrub_cat_story.callback(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        pending_event=getattr(
                            self.state.connection, "pending_astrub_cat_story", None
                        ),
                        in_combat=self.state.fight is not None
                        or self.state.combat_session is not None,
                    )
                    self.publish_astrub_cat_story(result)
            elif scenario_callback in (17029, 23936, 17022):
                from wakfu_server import astrub_arrival_scene

                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    result = astrub_arrival_scene.callback(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        pending_character_id=getattr(
                            self.state.connection, "pending_astrub_arrival", None
                        ),
                        expected_event=getattr(
                            self.state.connection, "pending_astrub_arrival_callback", -1
                        ),
                        in_combat=self.state.fight is not None
                        or self.state.combat_session is not None,
                    )
                    self.state.character = result["character"]
                    self.state.position = {
                        key: self.state.character[key] for key in ("x", "y", "z")
                    }
                    self.state.movement_state = self.runtime.Movement(
                        self.state.position
                    )
                    self.runtime.POSITIONS.attach(
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                    )
                    if result["finished"]:
                        self.state.connection.pending_astrub_arrival = None
                        self.state.connection.pending_astrub_arrival_callback = None
                        for packet in result["packets"]:
                            self.runtime.WORLD.update(
                                self.state.generation,
                                self.state.character,
                                *packet,
                                include_sender=False,
                            )
                    for packet in result["packets"]:
                        if packet[0] == 13411:
                            self.state.connection.pending_astrub_arrival_callback = (
                                struct.unpack_from(">i", packet[1], 1)[0]
                            )
                    self.runtime.send_batch(
                        self.state.connection, self.state.service, result["packets"]
                    )
            elif scenario_callback == 22534:
                from wakfu_server import rii_zaap_scene

                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    saved, packets, route = rii_zaap_scene.finish(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        pending_character_id=getattr(
                            self.state.connection, "pending_rii_zaap_scene", None
                        ),
                        in_combat=self.state.fight is not None
                        or self.state.combat_session is not None,
                    )
                    self.state.connection.pending_rii_zaap_scene = None
                    self.state.connection.pending_astrub_arrival = saved["id"]
                    self.state.connection.pending_astrub_arrival_callback = 17029
                    progress_packets = [
                        packet for packet in packets if packet[0] != 13411
                    ]
                    scene_packets = [packet for packet in packets if packet[0] == 13411]
                    self.publish_public_transport(
                        route,
                        saved,
                        generic_route=True,
                        before_bootstrap=lambda: self.publish_settled_quest_packets(
                            progress_packets
                        ),
                    )
                    self.runtime.send_batch(
                        self.state.connection, self.state.service, scene_packets
                    )
            elif scenario_callback == 22360:
                from wakfu_server import rii_scenario

                self.state.rii_scenario = rii_scenario

                for self.state.packet in self.state.rii_scenario.finish_intro(
                    self.state.connection,
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    in_combat=self.state.fight is not None
                    or self.state.combat_session is not None,
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
        except ValueError as error:
            self.runtime.record(event="scenario_callback_rejected", reason=str(error))
        return DispatchResult.FALLTHROUGH

    def handle_world_orientation(self):
        from wakfu_server.world_orientation import apply_exploration

        try:
            self.state.character = apply_exploration(
                self.runtime.STORE,
                self.runtime.POSITIONS,
                self.runtime.WORLD,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.body,
                loaded=self.state.loaded,
                fight=self.state.fight,
            )
            self.runtime.record(
                event="world_orientation",
                actor_id=self.state.character["id"],
                direction=self.state.character["direction"],
            )
        except ValueError as error:
            self.runtime.record(
                event="world_orientation_rejected",
                actor_id=(
                    self.state.character["id"]
                    if self.state.character is not None
                    else None
                ),
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_world_direction(self):
        from wakfu_server.combat_orientation import decode_request

        self.state.decode_request = decode_request
        from wakfu_server.world_orientation import save as save_orientation

        self.state.save_orientation = save_orientation

        try:
            self.state.actor_id, direction = self.state.decode_request(self.state.body)
            if self.state.actor_id != self.state.character["id"]:
                raise ValueError("Orientation actor is not the selected character")
            self.runtime.POSITIONS.flush(
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.actor_id,
            )
            self.state.changed = self.state.save_orientation(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.actor_id,
                direction,
                outside=True,
            )
            self.state.character = dict(
                self.state.character, direction=self.state.changed["direction"]
            )
            self.runtime.POSITIONS.attach(
                self.state.account_id, self.state.generation, self.state.character
            )
            self.runtime.WORLD.update(
                self.state.generation,
                self.state.character,
                *self.state.changed["packet"],
            )
            self.runtime.record(
                event="world_orientation",
                actor_id=self.state.actor_id,
                direction=direction,
            )
        except ValueError as error:
            self.runtime.record(
                event="world_orientation_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_emote(self):
        from wakfu_server.emotes import prepare_play

        def visible_emote_target(actor_id):
            identity = self.runtime.WORLD.live_identity(character_id=actor_id)
            return None if identity is None else identity[1]

        try:
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(
                    account_id=self.state.account_id,
                    generation=self.state.generation,
                    character_id=self.state.character["id"],
                )
                self.state.emote = prepare_play(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                    resolve_target=visible_emote_target,
                    in_fight=lambda actor_id: (
                        actor_id == self.state.character["id"]
                        and (
                            self.state.fight is not None
                            or self.state.combat_session is not None
                        )
                    )
                    or self.runtime.COMBAT_SESSIONS.lookup_character(actor_id)
                    is not None,
                    occupied=lambda actor_id: actor_id in self.runtime.HARVESTS.pending
                    or actor_id in self.runtime.PLANTINGS.pending,
                )
            self.state.character["_emote_packet"] = self.state.emote["packet"]
            self.state.character["_emote_until"] = (
                float("inf")
                if self.state.emote["duration_ms"] < 0
                else time.monotonic() + self.state.emote["duration_ms"] / 1000
            )
            self.runtime.WORLD.update(
                self.state.generation, self.state.character, *self.state.emote["packet"]
            )
            from wakfu_server import simultaneous_party_pads

            emote_id = struct.unpack(">i", self.state.body[:4])[0]
            aggro = simultaneous_party_pads.prepare_aggro(
                self.runtime, self.state.character, emote_id, self.state.generation
            )
            if aggro is not None and self.state.pending_guardian_attack is None:
                self.state.pending_guardian_attack = aggro["attack_body"]
                self.runtime.send(
                    self.state.connection, self.state.service, *aggro["packet"]
                )
            for actor_id, generation, packets in simultaneous_party_pads.performed(
                self.runtime, self.state.character, emote_id
            ):
                for packet in packets:
                    self.runtime.WORLD.send_to(actor_id, generation, *packet)
            if self.state.emote.get("mission_packets"):
                self.publish_settled_quest_packets(self.state.emote["mission_packets"])
        except ValueError as error:
            from wakfu_server.emotes import (
                packet as emote_account_packet,
            )

            self.runtime.record(
                event="emote_play_rejected",
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
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *emote_account_packet(self.runtime.STORE, self.state.account_id),
            )
        return DispatchResult.FALLTHROUGH

    def handle_world_movement(self):
        movement_started = time.monotonic()
        movement_timings = {}
        self.runtime.PLANTINGS.cancel(self.state.character["id"], self.state.generation)
        self.runtime.HARVESTS.cancel(
            self.state.character["id"], generation=self.state.generation
        )
        movement_timings["cancel_occupations_ms"] = round(
            (time.monotonic() - movement_started) * 1000, 3
        )
        movement = self.runtime.decode_body("out", self.state.opcode, self.state.body)
        if not movement["steps"]:
            self.runtime.record(
                event="movement_zero_step_ignored",
                actor_id=self.state.character["id"],
                mode_id=movement["mode_id"],
                start=movement["start_position"],
                authoritative_position=self.state.position,
            )
            return DispatchResult.CONTINUE
        start = movement["start_position"]
        end = movement["end_position"]
        try:
            approved = self.state.movement_state.validate(movement)
            from wakfu_server import native_boat_arrivals
            from wakfu_server.combat_terrain import map_geometry

            self.state.map_geometry = map_geometry

            native_boat_arrivals.validate_movement(
                self.state.character, movement, geometry=self.state.map_geometry
            )
            if self.state.ranch_session is not None and self.state.ranch_session.owns(
                self.state.character
            ):
                from wakfu_server.haven_ranch_bridges import validate_movement

                with self.runtime.STORE.connection() as bridge_db:
                    validate_movement(
                        bridge_db, self.state.character["instance_id"], movement
                    )
            from wakfu_server import environment_doors

            self.state.environment_doors = environment_doors

            self.state.environment_doors.validate_movement(
                self.runtime.STORE, self.state.character, movement
            )
            if (
                self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                and self.runtime.is_dungeon_run(
                    self.state.character.get("instance_id", 0)
                )
            ):
                from wakfu_server import (
                    dungeon_native_flow,
                    dungeon_runtime,
                )

                self.state.dungeon_native_flow = dungeon_native_flow
                self.state.dungeon_runtime = dungeon_runtime

                with self.runtime.STORE.connection() as movement_db:
                    (
                        self.state._,
                        walking_config,
                    ) = self.state.dungeon_runtime.configuration_for_instance(
                        movement_db, self.state.character["instance_id"]
                    )
                    from wakfu_server import dungeon_optional_rooms

                    dungeon_optional_rooms.validate_movement(
                        walking_config["topology"], movement
                    )
                    from wakfu_server import (
                        native_scene_start,
                        dungeon_resource_obstacles,
                    )

                    self.state.native_scene_start = native_scene_start

                    dungeon_resource_obstacles.validate_movement(
                        movement_db,
                        walking_config,
                        self.state.character["instance_id"],
                        movement,
                    )
                    self.state.native_scene_start.validate_movement(
                        walking_config["topology"], movement
                    )
                    from wakfu_server import owned_story_controller

                    story_movement = owned_story_controller.validate_movement(
                        movement_db,
                        self.runtime.STORE,
                        self.state.character,
                        movement,
                        walking_config,
                    )
                    if not story_movement and self.state.dungeon_native_flow.enabled(
                        walking_config["topology"]
                    ):
                        walking_progress = movement_db.execute(
                            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
                            (self.state.character["instance_id"],),
                        ).fetchone()
                        self.state.dungeon_native_flow.validate_movement(
                            walking_config["topology"],
                            movement,
                            unlocked_room=walking_progress["current_room"],
                            completed=walking_progress["status"] == "completed",
                        )
        except ValueError as error:
            self.runtime.record(
                event="movement_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                "world",
                13530,
                struct.pack(
                    ">qiihBi",
                    self.state.character["id"],
                    self.state.position["x"],
                    self.state.position["y"],
                    self.state.position["z"],
                    0,
                    movement["mode_id"],
                ),
            )
            return DispatchResult.CONTINUE
        if start != self.state.position:
            self.runtime.record(
                event="movement_redirected",
                actor_id=self.state.character["id"],
                previous_destination=self.state.position,
                start=start,
            )
        if end != self.state.position:
            crafting_cancel_started = time.monotonic()
            self.cancel_crafting()
            movement_timings["cancel_crafting_ms"] = round(
                (time.monotonic() - crafting_cancel_started) * 1000, 3
            )
        position_update_started = time.monotonic()
        physical_choice = None
        if (
            self.active_private_session() is not None
            and self.active_private_session().owns(self.state.character)
        ):
            try:
                self.state.character = self.active_private_session().move(
                    self.state.character, end
                )
            except ValueError as error:
                self.runtime.record(
                    event="movement_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
                self.runtime.send(
                    self.state.connection,
                    "world",
                    13530,
                    struct.pack(
                        ">qiihBi",
                        self.state.character["id"],
                        self.state.position["x"],
                        self.state.position["y"],
                        self.state.position["z"],
                        0,
                        movement["mode_id"],
                    ),
                )
                return DispatchResult.CONTINUE
        else:
            if (
                self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
                and self.runtime.is_dungeon_run(
                    self.state.character.get("instance_id", 0)
                )
                and walking_config["topology"].get("branch_selection_checkpoint")
                is not None
            ):
                from wakfu_server.dungeon_physical_choice import (
                    commit_movement,
                )
                from wakfu_server.position_buffer import (
                    PositionOwnerBusy as PhysicalChoiceBusy,
                )

                try:
                    physical_choice = commit_movement(
                        self.runtime.STORE,
                        self.runtime.POSITIONS,
                        self.runtime.COMBAT_GROUPS,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        movement,
                        self.state.position,
                        geometry=lambda: self.state.map_geometry(
                            self.state.character["map_id"]
                        ),
                        preview_configuration=walking_config,
                        unlocked_room=walking_progress["current_room"],
                    )
                except (ValueError, PhysicalChoiceBusy) as error:
                    self.runtime.record(
                        event="movement_rejected",
                        actor_id=self.state.character["id"],
                        reason=str(error),
                    )
                    self.runtime.send(
                        self.state.connection,
                        "world",
                        13530,
                        struct.pack(
                            ">qiihBi",
                            self.state.character["id"],
                            self.state.position["x"],
                            self.state.position["y"],
                            self.state.position["z"],
                            0,
                            movement["mode_id"],
                        ),
                    )
                    return DispatchResult.CONTINUE
            if physical_choice is None:
                self.runtime.POSITIONS.merge(
                    self.state.account_id, self.state.generation, self.state.character
                )
                self.state.buffered = self.runtime.POSITIONS.move(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.position,
                    dict(end, direction=movement["steps"][-1]["direction"]),
                )
            else:
                self.state.buffered = physical_choice["character"]
            self.state.character.update(
                {key: self.state.buffered[key] for key in ("x", "y", "z", "direction")}
            )
        self.state.movement_state.commit(approved)
        self.state.position = end
        if (
            self.state.character["map_id"] == 1094
            and self.state.character.get("instance_id", 0) == 0
        ):
            from wakfu_server.achievements.ruel_story import (
                matching_trace,
                visit_trace,
            )

            if matching_trace(self.state.character) == 8535:
                try:
                    for self.state.trace_update in visit_trace(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.trace_update,
                        )
                except Exception:
                    import logging

                    logging.getLogger(__name__).exception(
                        "Ruel trace movement settlement failed"
                    )
        if physical_choice is not None:
            for self.state.packet in physical_choice["scene_packets"]:
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.character["instance_id"],
                    *self.state.packet,
                )
            self.state.selected_group = physical_choice["group_receipt"]
            if not self.state.selected_group.get("replay", False):
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.character["instance_id"],
                    12608,
                    self.runtime.owned_scene_spawn_group(
                        self.state.selected_group["members"],
                        group_id=self.state.selected_group["group_id"],
                    ),
                )
        movement_timings["position_update_ms"] = round(
            (time.monotonic() - position_update_started) * 1000, 3
        )
        world_publish_started = time.monotonic()
        # The client loads/unloads scene partitions during its local
        # walk. Queue their dynamic states after loading, not a full
        # map reconstruction before the first walking frame.
        scene_path = [dict(start)]
        for self.state.step in movement["steps"]:
            self.state.previous = scene_path[-1]
            scene_path.append(
                {
                    axis: self.state.previous[axis] + self.state.step["d" + axis]
                    for axis in ("x", "y", "z")
                }
            )
        if self.state.character["map_id"] == 1361 and any(
            (cell["x"], cell["y"], cell["z"])
            in ((5, 0, -4), (12, 0, -16), (12, -9, -16))
            for cell in scene_path[1:]
        ):
            from wakfu_server.achievements import (
                incarnam_tutorial,
                storage as tutorial_storage,
            )

            self.state.incarnam_tutorial = incarnam_tutorial

            with self.runtime.STORE.connection() as self.state.tutorial_db:
                self.state.tutorial_state = tutorial_storage.load_locked(
                    self.state.tutorial_db, self.state.character["id"]
                )
            for guide_packet in self.state.incarnam_tutorial.walking_guide_packets(
                self.state.character, self.state.tutorial_state, scene_path
            ):
                self.runtime.send(
                    self.state.connection, self.state.service, *guide_packet
                )
        from . import owned_story_dispatch

        owned_story_dispatch.arm_movement(self, scene_path)
        self.state.scene_sync.arm(
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
            scene_path,
            time.monotonic(),
        )
        # The owner already follows this path locally. Rebuilding
        # an endpoint path on it interrupts redirects and stairs.
        # Other clients receive every packed step and its height.
        self.state.response = self.runtime.wire.movement_path(
            self.state.character["id"], self.state.body
        )
        if self.state.character.pop("_emote_packet", None) is not None:
            from wakfu_server.emotes import stopped

            self.state.character.pop("_emote_until", None)
            self.runtime.WORLD.broadcast(
                self.state.generation,
                self.state.character["id"],
                *stopped(self.state.character["id"]),
            )
        self.runtime.WORLD.update(
            self.state.generation,
            self.state.character,
            13852,
            self.state.response,
            include_sender=False,
        )
        movement_timings["world_publish_ms"] = round(
            (time.monotonic() - world_publish_started) * 1000, 3
        )
        ecology_context_started = time.monotonic()
        if self.state.bag_session is None:
            self.runtime.send_planting_context(
                self.state.connection,
                self.state.character,
                include_weather=self.runtime.territory_weather_region_changed(
                    self.state.character["map_id"], start, end
                ),
            )
        self.runtime.record(
            event="movement",
            actor_id=self.state.character["id"],
            account_id=self.state.account_id,
            start=start,
            end=end,
            steps=movement["step_count"],
            mode_id=movement["mode_id"],
            final_direction=movement["steps"][-1]["direction"],
            approved_path_points=len(approved),
            animation_owner="local_client",
            path_echo_to_owner=False,
            elapsed_ms=round((time.monotonic() - movement_started) * 1000, 3),
            ecology_context_ms=round(
                (time.monotonic() - ecology_context_started) * 1000, 3
            ),
            **movement_timings,
        )
        from wakfu_server import dungeon_optional_ground_items

        self.state.dungeon_optional_ground_items = dungeon_optional_ground_items

        if (
            self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
            and self.state.dungeon_optional_ground_items.scene_enabled(
                self.state.character["map_id"]
            )
            and self.runtime.is_dungeon_run(self.state.character.get("instance_id", 0))
        ):
            from wakfu_server import dungeon_optional_encounters

            self.state.dungeon_optional_encounters = dungeon_optional_encounters
            from psycopg import Error as OptionalGroundDatabaseError
            from psycopg_pool import (
                PoolTimeout as OptionalGroundPoolTimeout,
            )

            try:
                stepped_ground = (
                    self.state.dungeon_optional_ground_items.step_on_target(
                        self.runtime.STORE,
                        self.runtime.COMBAT_GROUPS,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        dict(self.state.character, **self.state.position),
                        positions=self.runtime.POSITIONS,
                        in_fight=self.state.fight is not None
                        or self.state.combat_session is not None
                        or self.state.spectator_session is not None,
                    )
                )
                if stepped_ground is not None:
                    self.state.character = self.refresh_owned_character(
                        stepped_ground["character"]
                    )
                    for self.state.packet in stepped_ground["packets"]:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    self.state.dungeon_optional_encounters.publish_pending(
                        self.runtime.STORE,
                        self.runtime.COMBAT_GROUPS,
                        instance_id=stepped_ground["instance_id"],
                        publish=lambda *packet: self.state.dungeon_optional_encounters.publish_native_scene(
                            self.runtime.WORLD, *packet
                        ),
                    )
                    self.runtime.record(
                        event="optional_ground_step_activated",
                        actor_id=self.state.character["id"],
                        consumed=stepped_ground["consumed"],
                        replay=stepped_ground["replay"],
                    )
            except (
                ValueError,
                OptionalGroundDatabaseError,
                OptionalGroundPoolTimeout,
            ) as error:
                # Access failure never rolls back an already accepted walk.
                self.runtime.record(
                    event="optional_ground_step_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
            except OSError as error:
                self.runtime.record(
                    event="optional_ground_publication_deferred",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
        return DispatchResult.FALLTHROUGH
