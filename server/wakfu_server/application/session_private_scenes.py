"""Private scenes operations for one lease-bound World session."""

import struct
import time
import uuid
from wakfu_server.performance_profiler import PROFILER
from .dispatch_result import DispatchResult


class PrivateScenesMixin:
    def notify_owned_story_refresh(self):
        if (
            self.state.character is None
            or not self.runtime.is_dungeon_run(
                self.state.character.get("instance_id", 0)
            )
            or self.state.fight is not None
            or self.state.combat_session is not None
        ):
            return
        from wakfu_server import owned_story_refresh

        owned_story_refresh.notify_pending(
            self.runtime.STORE, self.state.character, self.state.generation
        )

    def active_private_session(self):
        return self.state.ranch_session or self.state.bag_session

    def refresh_owned_character(self, saved):
        """Merge durable rewards/health without persisting a private scene location."""
        session = self.active_private_session()
        if session is None:
            return saved
        if not session.owns(self.state.character):
            raise ValueError("Combat return requires its current private scene")
        if self.state.ranch_session is not None:
            self.state.ranch_session.validate_lease(self.state.generation)
        return session.refresh(self.state.character, saved)

    def training_occupancy_snapshot(self, *, returning=False):
        """Capture occupancy before SQL locks to avoid world/group lock inversion."""
        from wakfu_server.achievements import rii_training_arena

        peers = self.runtime.WORLD.ecology_snapshot()
        groups = self.runtime.COMBAT_GROUPS.available(1388, 0)
        if returning:
            from wakfu_server.achievements.rii_lesson_visibility import visible_groups

            with self.runtime.STORE.connection() as db:
                groups = visible_groups(db, groups, self.state.character["id"])
        occupied = rii_training_arena.occupied_positions(
            peers, groups, self.state.character["id"], returning=returning
        )

        def available(destination):
            return (
                tuple(
                    destination[key] for key in ("map_id", "instance_id", "x", "y", "z")
                )
                not in occupied
            )

        return available

    def publish_training_relocation(self, saved):
        """Publish the same complete owned scene used for normal map travel."""
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
        for message_id, payload in self.runtime.owned_native_bootstrap(
            self.state.character
        ):
            self.runtime.send(
                self.state.connection, self.state.service, message_id, payload
            )
        self.runtime.join_world(
            self.state.generation, self.state.connection, self.state.character
        )
        self.mark_static_sync_pending()

    def begin_floor_training(self, objective_id, producer):
        """Stage a Rii lesson on the native floor and publish its encounter."""
        from wakfu_server.achievements import rii_training_arena

        if (
            self.active_private_session() is not None
            or self.state.fight is not None
            or self.state.combat_session is not None
        ):
            raise ValueError("Training requires the public dojo outside combat")
        with self.runtime.POSITIONS.account_barrier(self.state.account_id):
            self.runtime.flush_positions(account_id=self.state.account_id)
            if not rii_training_arena.requires_transit(
                self.state.character,
                has_pending=rii_training_arena.pending(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                ),
            ):
                scene = producer(
                    self.runtime.STORE,
                    self.runtime.COMBAT_GROUPS,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                )
                if scene is None:
                    raise ValueError("Training encounter could not be prepared")
                self.state.training_transit_active = False
                return scene
            available = self.training_occupancy_snapshot()
            return_available = self.training_occupancy_snapshot(returning=True)
            try:
                return rii_training_arena.stage(
                    lambda: rii_training_arena.enter(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        objective_id,
                        available=available,
                    ),
                    lambda moved: producer(
                        self.runtime.STORE,
                        self.runtime.COMBAT_GROUPS,
                        self.state.account_id,
                        self.state.generation,
                        dict(moved, _rii_training_objective=objective_id),
                    ),
                    lambda moved: rii_training_arena.return_to_source(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        moved,
                        available=return_available,
                    ),
                    self.publish_training_relocation,
                    lambda returned: self.runtime.POSITIONS.attach(
                        self.state.account_id, self.state.generation, returned
                    ),
                    lambda moved: rii_training_arena.mark_setup_failed(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        moved,
                    ),
                    lambda moved: rii_training_arena.setup_is_ready(
                        self.runtime.STORE, self.state.account_id, moved["id"]
                    ),
                )
            finally:
                self.state.training_transit_active = rii_training_arena.pending(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                )

    def queue_rii_lesson_attack(self, objective_id):
        """Reuse normal combat admission for an owner-receipted lesson group."""
        from wakfu_server.achievements import rii_lesson_auto_start

        if self.state.pending_guardian_attack is not None:
            raise ValueError("A tutorial combat is already pending")
        with self.runtime.STORE.connection() as db:
            target = rii_lesson_auto_start.target(
                db, self.runtime.COMBAT_GROUPS, self.state.character["id"], objective_id
            )
        self.state.pending_guardian_attack = struct.pack(
            ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
        )

    def deliver_ranch_cycle_rewards(self):
        """Settle an idle owner's herd independently of combat and visitor scenes."""
        if (
            not self.state.loaded
            or self.state.ranch_session is None
            or not self.state.ranch_session.parent.is_owner
            or self.state.fight is not None
            or self.state.combat_session is not None
            or self.state.spectator_session is not None
            or self.state.hero_switch_pending is not None
            or time.monotonic() - self.state.last_ranch_cycle_tick < 60
        ):
            return
        self.state.last_ranch_cycle_tick = time.monotonic()
        from wakfu_server import ranch_cycle_rewards

        try:
            packets = ranch_cycle_rewards.tick(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                session=self.state.ranch_session,
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.record(
                event="haven_ranch_cycle_deferred",
                actor_id=self.state.character["id"],
                reason=(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Ranch cycle unavailable"
                ),
            )
            return
        for packet in packets:
            self.runtime.send(self.state.connection, self.state.service, *packet)
        if packets:
            from wakfu_server.haven_ranch_building_knowledge import scene_packet

            self.runtime.WORLD.emit_location(
                self.state.character["map_id"],
                self.state.character["instance_id"],
                *scene_packet(
                    self.runtime.STORE,
                    self.state.account_id,
                    biome_id=self.state.ranch_session.biome_id,
                ),
            )

    def deliver_ranch_scene_refresh(self):
        """Rebuild this recipient's native Ranch scene without changing ownership."""
        pending = self.state.connection.ranch_scene_refresh
        if pending is None:
            return
        scope = (
            self.state.character["id"],
            self.state.generation,
            self.state.character["map_id"],
            self.state.character["instance_id"],
        )
        if (
            pending[:4] != scope
            or self.state.ranch_session is None
            or not self.state.ranch_session.owns(self.state.character)
        ):
            with self.runtime.WORLD.lock:
                if self.state.connection.ranch_scene_refresh == pending:
                    self.state.connection.ranch_scene_refresh = None
            return
        if (
            self.state.fight is not None
            or self.state.combat_session is not None
            or self.state.spectator_session is not None
            or self.state.pending_combat_return is not None
        ):
            return
        # 13864 replaces the model; recipient-specific 13974 invokes ceK.nc and
        # rebuilds its actors. Reuse the qualified same-scene return sequence.
        for packet in self.combat_return_bootstrap():
            self.runtime.send(self.state.connection, self.state.service, *packet)
        self.mark_static_sync_pending()
        with self.runtime.WORLD.lock:
            if self.state.connection.ranch_scene_refresh == pending:
                self.state.connection.ranch_scene_refresh = None
        self.runtime.record(
            event="haven_ranch_scene_refreshed",
            actor_id=self.state.character["id"],
            revision=pending[4],
        )

    def validate_ranch_lease(self):
        if not self.runtime.STORE.current_character_session(
            self.state.account_id, self.state.generation, self.state.character["id"]
        ):
            raise ValueError("Expired ranch actor lease")

    def validate_ranch_entitlement(self):
        from wakfu_server.haven_ranch_authority import require_owned_entitlement

        require_owned_entitlement(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character,
        )

    def cancel_private_scene_activity(self):
        self.runtime.PLANTINGS.cancel(self.state.character["id"], self.state.generation)
        self.runtime.HARVESTS.cancel(
            self.state.character["id"], generation=self.state.generation
        )
        self.cancel_flora()
        self.cancel_crafting()
        if self.state.chest_opening is not None:
            from wakfu_server.haven_chest_wire import close_packet as close_chest

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *close_chest(self.state.character["id"]),
            )
            self.state.chest_opening = None
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)

    def handle_haven_bag_enter(self):
        from wakfu_server.haven_bag import (
            HavenBagSession,
            entry_result,
            entry_messages,
        )

        if len(self.state.body) != 8:
            raise ValueError("Invalid haven bag entry request")
        self.state.target_id = struct.unpack(">q", self.state.body)[0]
        if self.state.character["map_id"] == 9 or self.state.ranch_session is not None:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                13307,
                entry_result(success=False, own=self.state.target_id == 0),
            )
            return DispatchResult.CONTINUE
        if self.state.fight is not None:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                13307,
                entry_result(success=False),
            )
            return DispatchResult.CONTINUE
        self.state.owner = None
        if self.state.target_id != 0:
            from wakfu_server.haven_bag_exterior import can_visit

            try:
                exterior_owner = self.runtime.HAVEN_BAG_EXTERIORS.resolve(
                    self.state.character, self.state.target_id
                )
                self.state.owner = self.runtime.STORE.character(
                    exterior_owner["account_id"], self.state.target_id
                )
                if not can_visit(self.state.character, self.state.owner):
                    raise ValueError("Haven Bag access denied")
            except ValueError as error:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    13307,
                    entry_result(success=False, own=False),
                )
                self.runtime.record(
                    event="haven_bag_visit_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
                return DispatchResult.CONTINUE
        self.runtime.PLANTINGS.cancel(self.state.character["id"], self.state.generation)
        self.runtime.HARVESTS.cancel(
            self.state.character["id"], generation=self.state.generation
        )
        self.cancel_flora()
        self.cancel_crafting()
        if self.state.owner is None:
            self.state.packet = self.runtime.HAVEN_BAG_EXTERIORS.publish(
                self.state.generation, self.state.character
            )
            self.runtime.WORLD.emit_location(
                self.state.character["map_id"],
                self.state.character["instance_id"],
                *self.state.packet,
            )
        self.state.bag_session = HavenBagSession(
            self.state.character, owner=self.state.owner
        )
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        self.state.character = dict(self.state.bag_session.inside)
        self.state.position = {
            key: self.state.character[key] for key in ("x", "y", "z")
        }
        self.state.movement_state = self.runtime.Movement(self.state.position)
        from copy import deepcopy

        self.state.deepcopy = deepcopy
        from wakfu_server.haven_bag import own_bag

        self.state.own_bag = own_bag
        from wakfu_server.haven_bag_furniture_world import (
            packets as bag_furniture_packets,
        )

        self.state.bag_furniture_packets = bag_furniture_packets

        self.state.render_owner = {
            **self.state.bag_session.owner,
            "haven_bag": self.state.character["haven_bag"],
        }
        self.state.layout_owner = self.state.deepcopy(self.state.render_owner)
        self.state.layout_owner["haven_bag"]["furniture"] = []
        for self.state.message_id, self.state.message_body in entry_messages(
            self.runtime.fixture(13974),
            self.state.character,
            owner=self.state.layout_owner if self.state.owner is not None else None,
        ):
            self.runtime.send(
                self.state.connection,
                self.state.service,
                self.state.message_id,
                self.state.message_body,
            )
        if self.state.owner is None:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                12187,
                self.state.own_bag(self.state.layout_owner),
            )
        self.runtime.join_world(
            self.state.generation, self.state.connection, self.state.character
        )
        for self.state.packet in self.state.bag_furniture_packets(
            self.state.render_owner
        ):
            self.runtime.send(
                self.state.connection, self.state.service, *self.state.packet
            )
        self.mark_static_sync_pending()
        self.runtime.record(
            event="haven_bag_entered",
            actor_id=self.state.character["id"],
            position=self.state.position,
        )
        return DispatchResult.FALLTHROUGH

    def handle_haven_furniture(self):
        from wakfu_server.ecology_feedback import information

        self.state.information = information
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout

        try:
            if self.state.guild_chest_session is None:
                raise ValueError("No active guild chest")
            (
                self.state.result,
                self.state.packets,
            ) = self.state.guild_chest_session.handle(
                self.state.opcode,
                self.state.body,
                self.state.character,
                self.runtime.world_static.objects(self.state.character["map_id"]),
                blocked=self.state.fight is not None
                or self.state.spectator_session is not None
                or self.state.bag_session is not None,
            )
            if "character" in self.state.result:
                self.state.updated = self.state.result["character"]
                for self.state.key in (
                    "inventory_items",
                    "inventory_containers",
                    "kamas",
                ):
                    if self.state.key in self.state.updated:
                        self.state.character[self.state.key] = self.state.updated[
                            self.state.key
                        ]
                from wakfu_server.inventory_move import synchronization

                self.state.synchronization = synchronization

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.synchronization(self.state.updated),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.runtime.rich_inventory_packet(self.state.updated),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12753,
                    self.runtime.wire.account_kamas_update(self.state.updated["kamas"]),
                )
            for self.state.packet in self.state.packets:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.record(
                event="guild_chest_request",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                applied=self.state.result.get("applied", False),
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            if self.state.guild_chest_session is not None:
                self.state.guild_chest_session.close(clear=True)
            self.state.guild_chest_session = None
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "Guild chest is temporarily unavailable."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="guild_chest_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_haven_chest(self):
        from wakfu_server.haven_chest import transfer as transfer_chest
        from wakfu_server.haven_chest_wire import (
            action_result as chest_action_result,
            bootstrap as chest_bootstrap,
        )

        self.state.chest_bootstrap = chest_bootstrap
        from wakfu_server.inventory_move import (
            synchronization as sync_chest_inventory,
        )
        from wakfu_server.inventory_items import (
            equipment_inventory as chest_registry,
        )

        try:
            if self.state.chest_opening is None or self.state.fight is not None:
                raise ValueError("No active account chest")
            self.state.result = transfer_chest(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.opcode,
                self.state.body,
                opening_token=self.state.chest_opening,
                location=self.state.character,
                ranch_session=self.state.ranch_session,
            )
            self.state.character = self.active_private_session().refresh(
                self.state.character, self.state.result["character"]
            )
            # 318/ciH replaces existing bmM slots (including empty
            # cells) and refreshes cYz; rich state uses item_proto.
            # BAGS + registry reconcile the client's pending move
            # from authoritative state without entity rebuilds.
            for self.state.owner in self.state.result.get(
                "inventory_characters", (self.state.character,)
            ):
                for self.state.packet in (
                    sync_chest_inventory(self.state.owner),
                    chest_registry(self.state.owner),
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
            for self.state.packet in (
                self.state.chest_bootstrap(self.state.result["chest"]),
                chest_action_result(),
            ):
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.record(
                event="account_chest_transferred",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                applied=self.state.result["applied"],
                revision=self.state.result["chest"]["revision"],
            )
        except ValueError as error:
            self.runtime.record(
                event="account_chest_transfer_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *chest_action_result(rejected=True),
            )
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
            if self.state.chest_opening is not None:
                from wakfu_server.haven_chest import load as load_chest

                self.state.load_chest = load_chest

                self.state.current_chest = self.state.load_chest(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
                from wakfu_server import heroes

                self.state.heroes = heroes

                with self.runtime.STORE.connection() as self.state.db:
                    self.state.roster = self.state.heroes.load_roster(
                        self.state.db,
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.character["id"],
                    )
                for self.state.owner in (
                    self.state.character,
                    *self.state.roster["heroes"],
                ):
                    for self.state.packet in (
                        sync_chest_inventory(self.state.owner),
                        chest_registry(self.state.owner),
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.chest_bootstrap(self.state.current_chest),
                )
        return DispatchResult.FALLTHROUGH

    def handle_haven_permissions(self):
        from wakfu_server import dungeon_stele

        self.state.dungeon_stele = dungeon_stele
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if (
                self.state.fight is not None
                or self.state.spectator_session is not None
                or self.state.bag_session is not None
            ):
                raise ValueError(
                    "Stele selection is unavailable during combat or a bag visit"
                )
            self.state.packets = self.state.dungeon_stele.activate(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.character = self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"]
            )
            for self.state.packet in self.state.packets:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
        except ValueError as error:
            self.runtime.record(
                event="dungeon_stele_selection_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
        return DispatchResult.FALLTHROUGH

    def handle_ranch_travel(self):
        from wakfu_server.haven_ranch import (
            RanchSession,
            leave_messages as ranch_leave_messages,
        )
        from wakfu_server.haven_ranch_authority import (
            portal_target,
            biome_target,
            validate_return,
        )
        from wakfu_server.combat_terrain import map_geometry

        self.state.map_geometry = map_geometry
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if self.state.fight is not None or self.state.spectator_session is not None:
                raise ValueError("Ranch travel is unavailable during combat")
            if self.state.opcode == 13982 or (
                self.state.opcode == 12870
                and struct.unpack_from(">H", self.state.body, 8)[0] == 18
            ):
                if self.state.opcode == 13982:
                    validate_return(
                        self.state.character,
                        self.state.ranch_session,
                        self.state.body,
                        validate_lease=self.validate_ranch_lease,
                    )
                else:
                    from wakfu_server.haven_ranch_portal import (
                        validate_exit,
                    )

                    validate_exit(
                        self.state.character,
                        self.state.ranch_session,
                        self.state.body,
                        validate_lease=self.validate_ranch_lease,
                    )
                self.cancel_private_scene_activity()
                self.state.character = self.state.ranch_session.leave(
                    self.state.character
                )
                self.state.ranch_session = None
                self.state.packets = ranch_leave_messages(
                    self.runtime.fixture(13974),
                    self.state.character,
                    self.state.bag_session,
                )
            else:
                if self.state.opcode == 12870:
                    if self.state.ranch_session is not None:
                        raise ValueError("Nested ranch entry is unavailable")
                    self.state.target = portal_target(
                        self.state.character,
                        self.state.bag_session,
                        self.state.body,
                        validate_lease=self.validate_ranch_lease,
                        validate_entitlement=self.validate_ranch_entitlement,
                        geometry=self.state.map_geometry(9),
                    )
                    child = RanchSession(
                        self.state.bag_session,
                        self.state.character,
                        self.state.target,
                        lease=self.state.generation,
                        now_ms=int(time.time() * 1000),
                    )
                else:
                    self.state.target = biome_target(
                        self.state.character,
                        self.state.ranch_session,
                        self.state.body,
                        validate_lease=self.validate_ranch_lease,
                        validate_entitlement=self.validate_ranch_entitlement,
                    )
                    child = RanchSession(
                        self.state.bag_session,
                        self.state.ranch_session.return_point,
                        self.state.target,
                        lease=self.state.generation,
                        now_ms=int(time.time() * 1000),
                    )
                self.cancel_private_scene_activity()
                clear_bag_role = self.state.ranch_session is None
                self.state.ranch_session = child
                self.state.character = dict(child.inside)
                self.state.packets = child.entry_messages(
                    self.runtime.fixture(13974),
                    self.state.character,
                    clear_bag_role=clear_bag_role,
                )
                if self.state.character["map_id"] == 1440:
                    from wakfu_server.haven_ranch_furniture import (
                        snapshot as ranch_furniture_snapshot,
                    )

                    self.state.initial_ranch = ranch_furniture_snapshot(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        session=child,
                        now_ms=int(time.time() * 1000),
                    )
                    # Native scene geometry is built during map transition.
                    self.state.packets = [
                        (
                            self.state.initial_ranch["packet"]
                            if packet[0] == 13864
                            else packet
                        )
                        for packet in self.state.packets
                    ]
            self.state.position = {
                key: self.state.character[key] for key in ("x", "y", "z")
            }
            self.state.movement_state = self.runtime.Movement(self.state.position)
            for self.state.packet in self.state.packets:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.join_world(
                self.state.generation,
                self.state.connection,
                self.state.character,
                hydrate_heroes=self.state.ranch_session is None,
            )
            if self.state.ranch_session is None:
                from wakfu_server.haven_bag import own_bag

                self.state.own_bag = own_bag
                from wakfu_server.haven_bag_furniture_world import (
                    packets as bag_furniture_packets,
                )

                self.state.bag_furniture_packets = bag_furniture_packets

                self.state.render_owner = {
                    **self.state.bag_session.owner,
                    "haven_bag": self.state.character["haven_bag"],
                }
                from copy import deepcopy

                self.state.deepcopy = deepcopy

                self.state.layout_owner = self.state.deepcopy(self.state.render_owner)
                self.state.layout_owner["haven_bag"]["furniture"] = []
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12187,
                    self.state.own_bag(self.state.layout_owner),
                )
                for self.state.packet in self.state.bag_furniture_packets(
                    self.state.render_owner
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
            self.mark_static_sync_pending()
        except ValueError as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
            self.runtime.record(
                event="ranch_travel_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_ranch_bridge(self):
        from wakfu_server.haven_ranch_bridges import (
            activate as activate_ranch_bridge,
        )
        from wakfu_server.inventory_move import synchronization

        self.state.synchronization = synchronization
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if self.state.fight is not None or self.state.spectator_session is not None:
                raise ValueError("Ranch bridges are unavailable during combat")
            self.state.result = activate_ranch_bridge(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.body,
                session=self.state.ranch_session,
            )
            self.state.character = self.state.ranch_session.refresh(
                self.state.character, self.state.result["character"]
            )
            for self.state.packet in self.state.result.get("private_packets", []):
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            for self.state.packet in (
                self.state.synchronization(self.state.character),
                self.state.equipment_inventory(self.state.character),
            ):
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            for self.state.packet in self.state.result["scene_packets"]:
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.character["instance_id"],
                    *self.state.packet,
                )
            self.runtime.record(
                event="haven_ranch_bridge_activated",
                actor_id=self.state.character["id"],
                applied=self.state.result["applied"],
            )
        except ValueError as error:
            self.runtime.record(
                event="haven_ranch_bridge_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
        return DispatchResult.FALLTHROUGH

    def handle_ranch_building(self):
        from wakfu_server import ranch_reward_retrieval
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if (
                self.state.fight is not None
                or self.state.combat_session is not None
                or self.state.spectator_session is not None
            ):
                raise ValueError("Ranch rewards are unavailable during combat")
            self.cancel_crafting()
            self.state.result = ranch_reward_retrieval.retrieve(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.opcode,
                self.state.body,
                session=self.state.ranch_session,
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.state.reason = (
                str(error)
                if isinstance(error, ValueError)
                else "Ranch rewards unavailable; retry"
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.reason),
            )
            self.runtime.record(
                event="haven_ranch_rewards_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=self.state.reason,
            )
        else:
            if (
                self.state.result["recipient_character_id"]
                == self.state.character["id"]
            ):
                self.state.character = self.refresh_owned_character(
                    self.state.result["character"]
                )
            for self.state.packet in self.state.result["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            from wakfu_server.haven_ranch_building_knowledge import (
                scene_packet,
            )

            self.state.scene_packet = scene_packet

            self.runtime.WORLD.emit_location(
                self.state.character["map_id"],
                self.state.character["instance_id"],
                *self.state.scene_packet(
                    self.runtime.STORE,
                    self.state.account_id,
                    biome_id=self.state.ranch_session.biome_id,
                ),
            )
            self.runtime.record(
                event="haven_ranch_rewards_retrieved",
                actor_id=self.state.character["id"],
                recipient_character_id=self.state.result["recipient_character_id"],
                opcode=self.state.opcode,
                applied=self.state.result["applied"],
                reward_uids=self.state.result["reward_uids"],
            )
        return DispatchResult.FALLTHROUGH

    def handle_ranch_construction(self):
        from wakfu_server import haven_ranch_herd

        self.state.haven_ranch_herd = haven_ranch_herd
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if (
                self.state.fight is not None
                or self.state.combat_session is not None
                or self.state.spectator_session is not None
            ):
                raise ValueError("Ranch creatures are unavailable during combat")
            self.cancel_crafting()
            if self.state.opcode == 13017:
                self.state.result = self.state.haven_ranch_herd.rename(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                )
            elif self.state.opcode == 13961:
                self.state.result = self.state.haven_ranch_herd.release(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                    session=self.state.ranch_session,
                )
            elif self.state.opcode == 13541:
                self.state.result = self.state.haven_ranch_herd.deploy(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                    session=self.state.ranch_session,
                    geometry=self.state.map_geometry(1440),
                )
            else:
                self.state.result = self.state.haven_ranch_herd.repack(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                    session=self.state.ranch_session,
                )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            if self.state.opcode == 13541:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12391,
                    struct.pack(">qB", 1440, False),
                )
            elif self.state.opcode == 12617:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12657,
                    struct.pack(">qh", 1440, 99),
                )
            self.state.reason = (
                str(error)
                if isinstance(error, ValueError)
                else "Ranch creature operation failed; retry"
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.reason),
            )
            self.runtime.record(
                event="haven_ranch_creature_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=self.state.reason,
            )
        else:
            # Native deltas update the current account's fxS library;
            # visitors receive only the actual host-tagged scene model.
            for self.state.packet in self.state.result["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            scope = (
                self.state.result.get("scene_scope")
                if self.state.opcode in (13017, 13961)
                else (
                    self.state.character["map_id"],
                    self.state.character["instance_id"],
                )
            )
            if scope is not None:
                from wakfu_server.haven_ranch_building_knowledge import (
                    scene_packet,
                )

                self.state.scene_packet = scene_packet

                self.state.packet = self.state.scene_packet(
                    self.runtime.STORE, self.state.account_id, biome_id=1
                )
                self.runtime.WORLD.emit_location(*scope, *self.state.packet)
                self.runtime.WORLD.request_ranch_scene_refresh(
                    *scope,
                    exclude_generation=(
                        None
                        if self.state.result.get("refresh_scene")
                        else self.state.generation
                    ),
                )
            self.runtime.record(
                event="haven_ranch_creature_changed",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                applied=self.state.result.get("applied", True),
            )
        return DispatchResult.FALLTHROUGH

    def handle_ranch_production(self):
        from wakfu_server import (
            haven_ranch_buildings,
            haven_ranch_building_wire,
        )
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        rejected_uid = None
        if self.state.opcode == 12662 and len(self.state.body) >= 8:
            rejected_uid = struct.unpack_from(">q", self.state.body)[0]
            if rejected_uid <= 0:
                rejected_uid = None
        try:
            if (
                self.state.fight is not None
                or self.state.combat_session is not None
                or self.state.spectator_session is not None
            ):
                raise ValueError("Ranch buildings are unavailable during combat")
            self.cancel_crafting()
            self.state.result = haven_ranch_buildings.operate(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.opcode,
                self.state.body,
                session=self.state.ranch_session,
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            if self.state.opcode != 12662 or rejected_uid is not None:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *haven_ranch_building_wire.rejected(
                        self.state.opcode,
                        self.state.character["map_id"],
                        uid=rejected_uid,
                    ),
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Ranch buildings are temporarily unavailable."
                ),
            )
            self.runtime.record(
                event="haven_ranch_building_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
        else:
            for self.state.packet in self.state.result["packets"]:
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.character["instance_id"],
                    *self.state.packet,
                )
            if self.state.result["changed"]:
                from wakfu_server import haven_ranch_building_knowledge

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *haven_ranch_building_knowledge.packet(
                        self.runtime.STORE, self.state.account_id
                    ),
                )
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.character["instance_id"],
                    *haven_ranch_building_knowledge.scene_packet(
                        self.runtime.STORE, self.state.account_id, biome_id=1
                    ),
                )
            self.runtime.record(
                event="haven_ranch_building_changed",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                changed=self.state.result["changed"],
            )
        return DispatchResult.FALLTHROUGH

    def handle_ranch_interaction(self):
        from wakfu_server import haven_ranch_furniture
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if self.state.fight is not None or self.state.spectator_session is not None:
                raise ValueError("Ranch furniture is unavailable during combat")
            self.cancel_crafting()
            if self.state.opcode == 12766:
                self.state.result = haven_ranch_furniture.deploy(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                    session=self.state.ranch_session,
                    geometry=self.state.map_geometry(1440),
                )
            else:
                self.state.result = haven_ranch_furniture.edit(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.opcode,
                    self.state.body,
                    session=self.state.ranch_session,
                    geometry=self.state.map_geometry(1440),
                )
            for self.state.packet in self.state.result["packets"]:
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.character["instance_id"],
                    *self.state.packet,
                )
            self.runtime.record(
                event="haven_ranch_furniture_changed",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
        except ValueError as error:
            self.runtime.record(
                event="haven_ranch_furniture_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
        return DispatchResult.FALLTHROUGH

    def handle_world_interaction(self):
        from . import native_order_trial_dispatch

        order_trial_result = native_order_trial_dispatch.handle(self)
        if order_trial_result is not None:
            return order_trial_result
        from . import owned_story_dispatch

        if owned_story_dispatch.handle_interaction(self):
            return DispatchResult.CONTINUE
        from .mercenary_board_dispatch import dispatch as dispatch_mercenary_board

        mercenary_result = dispatch_mercenary_board(self)
        if mercenary_result is not None:
            return mercenary_result
        from . import source_quest_encounter_dispatch

        if self.state.opcode == 12870 and source_quest_encounter_dispatch.handle(self):
            return DispatchResult.CONTINUE
        from psycopg import Error as ItemDatabaseError

        self.state.ItemDatabaseError = ItemDatabaseError
        from psycopg_pool import PoolTimeout as ItemPoolTimeout

        self.state.ItemPoolTimeout = ItemPoolTimeout
        from wakfu_server import (
            dungeon_excavation_rules,
            dungeon_excavation_provider,
        )

        self.state.dungeon_excavation_rules = dungeon_excavation_rules
        self.state.dungeon_excavation_provider = dungeon_excavation_provider

        excavation_rule = None
        if (
            self.state.opcode == 12870
            and len(self.state.body) == 12
            and self.runtime.is_dungeon_run(self.state.character.get("instance_id", 0))
            and self.state.dungeon_excavation_rules.scene_enabled(
                self.state.character["map_id"]
            )
        ):
            candidate_rule = next(
                (
                    r
                    for r in self.state.dungeon_excavation_rules.rules()
                    if r.get("enabled") is True
                    and r["ground_authority"]["map_id"]
                    == self.state.character["map_id"]
                    and struct.unpack_from(">q", self.state.body)[0]
                    in {d["source_id"] for d in r["door_authority"]}
                ),
                None,
            )
            if candidate_rule is not None:
                from wakfu_server import dungeon_runtime

                self.state.dungeon_runtime = dungeon_runtime

                with self.runtime.STORE.connection() as self.state.db:
                    (
                        self.state._,
                        rule_config,
                    ) = self.state.dungeon_runtime.configuration_for_instance(
                        self.state.db, self.state.character["instance_id"]
                    )
                if (
                    rule_config["topology"].get("excavation_access", {}).get("key")
                    == candidate_rule["key"]
                ):
                    excavation_rule = candidate_rule
        if excavation_rule is not None:
            try:
                self.state.chosen = self.state.dungeon_excavation_provider.choose(
                    self.runtime.STORE,
                    self.runtime.COMBAT_GROUPS,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    rule=excavation_rule,
                    positions=self.runtime.POSITIONS,
                    in_fight=self.state.fight is not None
                    or self.state.combat_session is not None
                    or self.state.spectator_session is not None,
                )
            except (
                ValueError,
                self.state.ItemDatabaseError,
                self.state.ItemPoolTimeout,
            ) as error:
                self.runtime.record(
                    event="native_excavation_choice_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(
                        str(error)
                        if isinstance(error, ValueError)
                        else "No se pudo abrir la puerta; inténtalo de nuevo"
                    ),
                )
                return DispatchResult.CONTINUE
            self.state.character = self.refresh_owned_character(
                self.state.chosen["character"]
            )
            for self.state.packet in self.state.chosen["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            for self.state.packet in self.state.chosen["scene_packets"]:
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.chosen["instance_id"],
                    *self.state.packet,
                )
            group = self.state.chosen["group"]
            if group is not None and group["status"] == "available":
                self.runtime.WORLD.emit_location(
                    self.state.character["map_id"],
                    self.state.chosen["instance_id"],
                    12608,
                    self.runtime.owned_scene_spawn_group(
                        group["members"], group_id=group["group_id"]
                    ),
                )
            self.runtime.record(
                event="native_excavation_choice",
                actor_id=self.state.character["id"],
                source_id=self.state.chosen["selected_source_id"],
                replay=self.state.chosen["replay"],
            )
            return DispatchResult.CONTINUE
        from wakfu_server import dungeon_optional_votes, native_scene_start

        self.state.native_scene_start = native_scene_start

        if self.state.opcode == 12870 and self.state.native_scene_start.handles(
            self.runtime.STORE, self.state.character, self.state.body
        ):
            from psycopg import Error as SceneStartDatabaseError
            from psycopg_pool import PoolTimeout as SceneStartPoolTimeout
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            try:
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    prior_scene_inventory = self.state.character
                    started_scene = self.state.native_scene_start.start(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        groups=self.runtime.COMBAT_GROUPS,
                        geometry=self.state.map_geometry(
                            self.state.character["map_id"]
                        ),
                        blocked=self.environment_blocked(),
                        is_hero=self.environment_actor_is_hero(),
                    )
                    self.state.character = started_scene["character"]
                    if started_scene["payment"]:
                        self.publish_entry_inventory(prior_scene_inventory)
                    for self.state.packet in started_scene["packets"]:
                        self.runtime.WORLD.emit_location(
                            self.state.character["map_id"],
                            self.state.character["instance_id"],
                            *self.state.packet,
                        )
                    if (
                        not started_scene["replay"]
                        and started_scene["group"] is not None
                    ):
                        group = started_scene["group"]
                        self.runtime.WORLD.emit_location(
                            self.state.character["map_id"],
                            self.state.character["instance_id"],
                            12608,
                            self.runtime.owned_scene_spawn_group(
                                group["members"], group_id=group["group_id"]
                            ),
                        )
                self.runtime.record(
                    event="native_scene_started",
                    actor_id=self.state.character["id"],
                    instance_id=self.state.character["instance_id"],
                    replay=started_scene["replay"],
                )
            except (
                ValueError,
                SceneStartDatabaseError,
                SceneStartPoolTimeout,
            ) as error:
                self.runtime.record(
                    event="native_scene_start_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(
                        str(error)
                        if isinstance(error, ValueError)
                        else "No se pudo iniciar la escena; inténtalo de nuevo."
                    ),
                )
            return DispatchResult.CONTINUE

        if self.state.opcode == 12870 and dungeon_optional_votes.handles(
            self.state.character["map_id"], self.state.body
        ):
            try:
                voted = dungeon_optional_votes.cast_vote(
                    self.runtime.STORE,
                    self.runtime.COMBAT_GROUPS,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    positions=self.runtime.POSITIONS,
                    in_fight=self.state.fight is not None
                    or self.state.combat_session is not None
                    or self.state.spectator_session is not None,
                )
            except (
                ValueError,
                self.state.ItemDatabaseError,
                self.state.ItemPoolTimeout,
            ) as error:
                self.runtime.record(
                    event="optional_vote_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"),
                        (
                            str(error)
                            if isinstance(error, ValueError)
                            else "No se pudo votar; inténtalo de nuevo"
                        ),
                    ),
                )
                return DispatchResult.CONTINUE
            self.state.character = self.refresh_owned_character(voted["character"])
            for self.state.packet in voted["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            try:
                from wakfu_server import dungeon_optional_encounters

                self.state.dungeon_optional_encounters = dungeon_optional_encounters

                dungeon_optional_votes.publish_pending(
                    self.runtime.STORE,
                    self.runtime.COMBAT_GROUPS,
                    instance_id=voted["instance_id"],
                    publish=lambda *packet: self.state.dungeon_optional_encounters.publish_native_scene(
                        self.runtime.WORLD, *packet
                    ),
                )
            except Exception as error:
                self.runtime.record(
                    event="optional_vote_publication_deferred",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
            self.runtime.record(
                event="optional_vote_cast",
                actor_id=self.state.character["id"],
                consumed=voted["consumed"],
                winner=voted["winner"],
            )
            return DispatchResult.CONTINUE
        from wakfu_server.haven_bag_furniture_transfer import (
            edit as edit_bag_furniture,
        )
        from wakfu_server.haven_bag import own_bag

        self.state.own_bag = own_bag

        if (
            self.state.opcode == 12870
            and len(self.state.body) == 12
            and struct.unpack_from(">H", self.state.body, 8)[0] == 11
        ):
            from wakfu_server import rift_transition_delivery
            from wakfu_server.rift_dispatch_lifecycle import (
                resolve_destination,
            )

            self.state.resolve_destination = resolve_destination
            from wakfu_server.combat_terrain import map_geometry

            self.state.map_geometry = map_geometry

            try:
                if (
                    self.state.spectator_session is not None
                    or self.state.bag_session is not None
                ):
                    raise ValueError(
                        "A fight or inventory session blocks rift admission"
                    )
                if (
                    self.state.fight is not None
                    or self.state.combat_session is not None
                ):
                    if not self.native_exterior_rift_request():
                        raise ValueError("A live fight blocks native rift admission")
                entered = rift_transition_delivery.enter(
                    self.runtime.STORE,
                    self.runtime.POSITIONS,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.character["map_id"],
                    self.state.body,
                    world=self.runtime.WORLD,
                    combat_registry=self.runtime.COMBAT_SESSIONS.registry,
                    groups=self.runtime.COMBAT_GROUPS,
                    checkpoint_writer=self.runtime.CHECKPOINT_WRITER,
                    source_allowed=lambda actor, source: (
                        actor["map_id"] == source["map_id"]
                        and max(
                            abs(actor["x"] - source["x"]),
                            abs(actor["y"] - source["y"]),
                        )
                        <= 3
                        and abs(actor["z"] - source["z"]) <= 2
                    ),
                    resolve_destination=lambda db, catalog, members: self.state.resolve_destination(
                        db,
                        catalog,
                        members,
                        self.state.map_geometry(catalog["map_id"]),
                    ),
                )
                if entered is not None:
                    self.deliver_rift_transition()
                    self.runtime.record(
                        event="rift_entered",
                        actor_id=self.state.character["id"],
                        instance_id=entered["run"]["instance_id"],
                        wave_id=entered["run"]["wave_definition_id"],
                        member_ids=list(entered["run"]["members"]),
                    )
                    return DispatchResult.CONTINUE
            except ValueError as error:
                self.runtime.record(
                    event="rift_entry_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
                from wakfu_server.ecology_feedback import information

                self.state.information = information
                from wakfu_server.player_action_feedback import (
                    failure_message,
                )

                self.state.failure_message = failure_message

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(
                        self.state.failure_message("rift_entry", error)
                    ),
                )
                return DispatchResult.CONTINUE
        if self.state.opcode == 12870 and len(self.state.body) == 12:
            self.state.target_id, target_action, target_parameter = struct.unpack(
                ">qHH", self.state.body
            )
            if target_action in (12, 13) and any(
                row["id"] == self.state.target_id and row["type"] == "Stele"
                for row in self.runtime.world_static.objects(
                    self.state.character["map_id"]
                )
            ):
                from wakfu_server import dungeon_stele

                self.state.dungeon_stele = dungeon_stele
                from wakfu_server.ecology_feedback import information

                self.state.information = information

                try:
                    if target_parameter != 0:
                        raise ValueError("Invalid stele interaction parameter")
                    if (
                        self.state.fight is not None
                        or self.state.spectator_session is not None
                        or self.state.bag_session is not None
                    ):
                        raise ValueError(
                            "Stele interaction is unavailable during combat or a bag visit"
                        )
                    if (
                        self.state.dungeon_stele.definition(
                            self.runtime.STORE,
                            self.state.character["map_id"],
                            self.state.target_id,
                        )
                        is None
                    ):
                        raise ValueError("Unknown native stele placement")
                    if target_action == 12:
                        self.cancel_environment()
                        self.cancel_crafting()
                        self.state.packets = self.state.dungeon_stele.browse(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            self.state.target_id,
                        )
                    else:
                        self.state.packets = self.state.dungeon_stele.close(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            self.state.target_id,
                        )
                    for self.state.packet in self.state.packets:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                except ValueError as error:
                    self.runtime.record(
                        event="dungeon_stele_interaction_rejected",
                        actor_id=self.state.character["id"],
                        reason=str(error),
                    )
                    if target_action == 12:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.dungeon_stele.cancel_packet(
                                self.state.character["id"]
                            ),
                        )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.information(str(error)),
                    )
                return DispatchResult.CONTINUE
            self.state.target = next(
                (
                    row
                    for row in self.runtime.world_static.objects(
                        self.state.character["map_id"]
                    )
                    if row["id"] == self.state.target_id
                    and row["type"] == "GuildStorageBox"
                ),
                None,
            )
            if self.state.target is not None and target_action in (12, 13):
                if self.state.guild_chest_session is not None:
                    self.state.guild_chest_session.close()
                self.state.guild_chest_session = None
                if target_action == 12:
                    from wakfu_server.guild_chest_dispatch import (
                        GuildChestSession,
                    )
                    from wakfu_server.ecology_feedback import information

                    self.state.information = information
                    from psycopg import Error as DatabaseError

                    self.state.DatabaseError = DatabaseError
                    from psycopg_pool import PoolTimeout

                    self.state.PoolTimeout = PoolTimeout

                    try:
                        self.state.guild_chest_session = GuildChestSession(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                            self.runtime.world_static.objects(
                                self.state.character["map_id"]
                            ),
                            blocked=self.state.fight is not None
                            or self.state.spectator_session is not None
                            or self.state.bag_session is not None,
                            world=self.runtime.WORLD,
                            objects_for=self.runtime.world_static.objects,
                            blocked_now=lambda: self.state.fight is not None
                            or self.state.spectator_session is not None
                            or self.state.bag_session is not None,
                        )
                        self.cancel_crafting()
                        for (
                            self.state.packet
                        ) in self.state.guild_chest_session.publish_current():
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                        self.runtime.record(
                            event="guild_chest_opened",
                            actor_id=self.state.character["id"],
                            object_id=self.state.target_id,
                            guild_id=self.state.guild_chest_session.guild_id,
                        )
                    except (
                        ValueError,
                        self.state.DatabaseError,
                        self.state.PoolTimeout,
                    ) as error:
                        self.state.guild_chest_session = None
                        self.state.text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Guild chest is temporarily unavailable."
                        )
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.information(self.state.text),
                        )
                        self.runtime.record(
                            event="guild_chest_open_rejected",
                            actor_id=self.state.character["id"],
                            reason=type(error).__name__,
                        )
                return DispatchResult.CONTINUE
        if (
            self.state.opcode == 12870
            and len(self.state.body) == 12
            and struct.unpack_from(">H", self.state.body, 8)[0] == 12
        ):
            from wakfu_server.haven_chest import (
                load as load_chest,
                validate_open as validate_chest_open,
            )

            self.state.load_chest = load_chest
            from wakfu_server.haven_chest_wire import (
                bootstrap as chest_bootstrap,
                open_packet as chest_open_packet,
                close_packet as chest_close_packet,
            )

            self.state.chest_bootstrap = chest_bootstrap

            from psycopg import Error as DatabaseError

            self.state.DatabaseError = DatabaseError
            from psycopg_pool import PoolTimeout

            self.state.PoolTimeout = PoolTimeout
            from wakfu_server.travel_storage_feedback import rejection

            self.state.rejection = rejection

            self.state.chest_opening = None
            try:
                with PROFILER.span("storage.chest.open.validate"):
                    self.state.identity = validate_chest_open(
                        self.state.character,
                        self.state.bag_session,
                        self.state.body,
                        self.runtime.world_static.objects(
                            self.state.character["map_id"]
                        ),
                        fight_active=self.state.fight is not None
                        or self.state.spectator_session is not None,
                        ranch_session=self.state.ranch_session,
                    )
                self.cancel_crafting()
                with PROFILER.span("storage.chest.open.load"):
                    self.state.current_chest = self.state.load_chest(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                    )
                with PROFILER.span("storage.chest.open.publish"):
                    self.state.chest_opening = uuid.uuid4()
                    for self.state.packet in (
                        self.state.chest_bootstrap(self.state.current_chest),
                        (12401, struct.pack(">qB", self.state.character["id"], 7)),
                        (
                            12344,
                            struct.pack(">qh", self.state.identity, 19)
                            + bytes.fromhex("01020000000602000201010001010000000000"),
                        ),
                        chest_open_packet(self.state.character["id"]),
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                self.runtime.record(
                    event="account_chest_opened",
                    actor_id=self.state.character["id"],
                    capacity=self.state.current_chest["capacity"],
                )
            except (
                ValueError,
                self.state.DatabaseError,
                self.state.PoolTimeout,
            ) as error:
                self.state.chest_opening = None
                self.runtime.record(
                    event="account_chest_open_rejected",
                    actor_id=self.state.character["id"],
                    reason=(
                        str(error)
                        if isinstance(error, ValueError)
                        else type(error).__name__
                    ),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *chest_close_packet(self.state.character["id"]),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.rejection("chest_open", error),
                )
            return DispatchResult.CONTINUE
        if self.state.opcode == 12870 and len(self.state.body) == 12:
            self.state.stool_id, stool_action, stool_parameter = struct.unpack(
                ">qHH", self.state.body
            )
            stool = next(
                (
                    row
                    for row in self.runtime.world_static.objects(
                        self.state.character["map_id"]
                    )
                    if row["id"] == self.state.stool_id and row["type"] == "Stool"
                ),
                None,
            )
            if stool is not None:
                try:
                    from wakfu_server import (
                        environment_seats,
                        environment_seat_animations,
                    )

                    # This proximity limit is server policy, not bDV.am geometry.
                    in_range = (
                        abs(self.state.character["x"] - stool["x"])
                        + abs(self.state.character["y"] - stool["y"])
                        <= 4
                        and abs(self.state.character["z"] - stool["z"]) <= 1
                    )
                    self.state.result = environment_seats.sit(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        in_range=in_range,
                        animation_verified=environment_seat_animations.supported(
                            self.state.character, ordinary_actor=True
                        ),
                        blocked=self.environment_blocked(allow_seated=True)
                        or self.state.environment_ticket is not None,
                    )
                    self.state.environment_seat = (
                        self.state.result if stool_action == 6 else None
                    )
                    for self.state.packet in self.state.result["packets"]:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    self.publish_environment_scene(force=True)
                except ValueError as error:
                    self.runtime.record(
                        event="stool_interaction_rejected",
                        actor_id=self.state.character["id"],
                        object_id=self.state.stool_id,
                        reason=str(error),
                    )
                return DispatchResult.CONTINUE
        if self.state.opcode == 12870 and len(self.state.body) == 12:
            from wakfu_server import nation_board

            board_id = struct.unpack_from(">q", self.state.body)[0]
            if (
                nation_board.definition(self.state.character["map_id"], board_id)
                is not None
            ):
                try:
                    self.state.packet = nation_board.open_selection(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        blocked=self.environment_blocked(),
                    )
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
                except ValueError as error:
                    self.runtime.record(
                        event="nation_board_rejected",
                        actor_id=self.state.character["id"],
                        object_id=board_id,
                        reason=str(error),
                    )
                return DispatchResult.CONTINUE
        if self.state.opcode == 12870 and len(self.state.body) == 12:
            self.state.door_id = struct.unpack_from(">q", self.state.body)[0]
            door = next(
                (
                    row
                    for row in self.runtime.world_static.objects(
                        self.state.character["map_id"]
                    )
                    if row["id"] == self.state.door_id and row["type"] == "Door"
                ),
                None,
            )
            if door is not None and not self.runtime.is_dungeon_run(
                self.state.character.get("instance_id", 0)
            ):
                from wakfu_server import environment_doors

                self.state.environment_doors = environment_doors

                if (
                    self.state.environment_doors.definition(
                        self.runtime.STORE,
                        self.state.character["map_id"],
                        self.state.door_id,
                    )
                    is not None
                ):
                    try:
                        self.state.result = self.state.environment_doors.interact(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                            blocked=self.environment_blocked(),
                        )
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.result["packet"],
                        )
                        self.publish_environment_scene(force=True)
                    except ValueError as error:
                        self.runtime.record(
                            event="ordinary_door_rejected",
                            actor_id=self.state.character["id"],
                            object_id=self.state.door_id,
                            reason=str(error),
                        )
                    return DispatchResult.CONTINUE
        if self.state.opcode == 12870 and self.state.character["map_id"] != 9:
            try:
                from wakfu_server import environment_interactions

                if len(self.state.body) != 12:
                    raise ValueError("Invalid native environment interaction length")
                environment_id = struct.unpack_from(">q", self.state.body)[0]
                if self.state.character["map_id"] == 1361 and (
                    environment_id,
                    self.state.body[8:],
                ) == (34658, b"\x00\x05\x00\x00"):
                    from wakfu_server.achievements import incarnam_tutorial

                    self.state.incarnam_tutorial = incarnam_tutorial

                    if (
                        self.environment_blocked()
                        or self.state.environment_ticket is not None
                    ):
                        raise ValueError("Incarnam tutorial trigger unavailable")
                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(
                            account_id=self.state.account_id,
                            generation=self.state.generation,
                            character_id=self.state.character["id"],
                        )
                        if getattr(
                            self.state.connection, "pending_incarnam_seed_guide", None
                        ) != self.state.character[
                            "id"
                        ] and self.state.incarnam_tutorial.blocked_path(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                        ):
                            self.state.connection.pending_incarnam_seed_guide = (
                                self.state.character["id"]
                            )
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.incarnam_tutorial.scenario_packet(22525),
                            )
                    return DispatchResult.CONTINUE
                from wakfu_server.achievements import incarnam_resources

                if incarnam_resources.is_gate_request(
                    self.state.character, self.state.body
                ):
                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(
                            account_id=self.state.account_id,
                            generation=self.state.generation,
                            character_id=self.state.character["id"],
                        )
                        self.state.result = incarnam_resources.interact_gate(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                            loaded=self.state.loaded,
                            blocked=self.environment_blocked()
                            or self.state.environment_ticket is not None,
                        )
                        self.state.character = self.state.result["character"]
                        for self.state.packet in self.state.result["packets"]:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                    return DispatchResult.CONTINUE
                from wakfu_server.achievements import ruel_story

                if ruel_story.recognizes_trace(
                    self.state.character["map_id"], self.state.body
                ):
                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(
                            account_id=self.state.account_id,
                            generation=self.state.generation,
                            character_id=self.state.character["id"],
                        )
                        trace_result = ruel_story.interact_trace(
                            self.runtime.STORE,
                            self.runtime.COMBAT_GROUPS,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                            loaded=self.state.loaded,
                            blocked=self.environment_blocked()
                            or self.state.environment_ticket is not None,
                        )
                        for self.state.trace_update in trace_result["packets"]:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.trace_update,
                            )
                        if trace_result["scene_packet"] is not None:
                            self.runtime.WORLD.emit_location(
                                self.state.character["map_id"],
                                0,
                                *trace_result["scene_packet"],
                            )
                    return DispatchResult.CONTINUE
                from wakfu_server.achievements import ground_quest_pickups
                from .quest_interaction_dispatch import settle_interaction

                if ground_quest_pickups.recognizes(
                    self.state.character["map_id"], self.state.body
                ) and settle_interaction(
                    self,
                    ground_quest_pickups.interact,
                    event="native_quest_ground_pickup",
                    object_id=environment_id,
                ):
                    return DispatchResult.CONTINUE
                from wakfu_server.application import owned_story_generic_entry_dispatch

                if owned_story_generic_entry_dispatch.handle(self):
                    return DispatchResult.CONTINUE
                from wakfu_server.achievements import interactive_missions

                if interactive_missions.binding_exists(
                    self.runtime.STORE, self.state.character["map_id"], self.state.body
                ):
                    if settle_interaction(
                        self,
                        interactive_missions.interact,
                        event="configured_quest_interaction",
                        object_id=environment_id,
                    ):
                        return DispatchResult.CONTINUE
                from wakfu_server import paid_containers

                self.state.paid_containers = paid_containers

                if (
                    self.state.paid_containers.definition(
                        self.runtime.STORE,
                        self.state.character["map_id"],
                        environment_id,
                    )
                    is not None
                ):
                    self.runtime.flush_positions(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                    )
                    self.state.result = self.state.paid_containers.begin(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        loaded=self.state.loaded,
                        blocked=self.environment_blocked(allow_paid=True)
                        or self.state.environment_ticket is not None,
                        is_hero=self.environment_actor_is_hero(),
                    )
                    self.state.paid_container_ticket = self.state.result["token"]
                    self.state.character = self.state.result["character"]
                    for self.state.packet in self.state.result["packets"]:
                        if self.state.packet[0] == 12344 and not self.state.result.get(
                            "personal_state", False
                        ):
                            self.runtime.WORLD.emit_location(
                                *self.state.result["location"], *self.state.packet
                            )
                        else:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                    self.publish_environment_scene(force=True)
                    self.runtime.record(
                        event="paid_container_started",
                        actor_id=self.state.character["id"],
                        object_id=environment_id,
                        replay=self.state.result["replay"],
                    )
                    return DispatchResult.CONTINUE
                from wakfu_server import native_generic_rewards

                if (
                    native_generic_rewards.definition(
                        self.runtime.STORE,
                        self.state.character["map_id"],
                        environment_id,
                    )
                    is not None
                ):
                    self.runtime.flush_positions(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                    )
                    self.state.result = native_generic_rewards.claim(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        loaded=self.state.loaded,
                        blocked=self.environment_blocked()
                        or self.state.environment_ticket is not None,
                    )
                    self.state.character = self.state.result["character"]
                    for self.state.packet in (
                        *self.state.result["visual_packets"],
                        *self.state.result["packets"],
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    if self.state.result["notification_key"]:
                        from wakfu_server.achievements.service import (
                            acknowledge_notifications,
                        )

                        with self.runtime.STORE.connection() as notification_db:
                            acknowledge_notifications(
                                notification_db,
                                self.state.character,
                                [self.state.result["notification_key"]],
                            )
                    self.runtime.record(
                        event="native_generic_reward_claim",
                        actor_id=self.state.character["id"],
                        object_id=environment_id,
                        replay=self.state.result["replay"],
                    )
                    return DispatchResult.CONTINUE
                from wakfu_server import treasure_chests

                if (
                    treasure_chests.definition(
                        self.runtime.STORE,
                        self.state.character["map_id"],
                        environment_id,
                    )
                    is not None
                ):
                    self.runtime.flush_positions(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                    )
                    previous_level = self.state.character["level"]
                    self.state.result = treasure_chests.claim(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                        loaded=self.state.loaded,
                        blocked=self.environment_blocked()
                        or self.state.environment_ticket is not None,
                        is_hero=self.environment_actor_is_hero(),
                    )
                    self.state.character = self.state.result["character"]
                    for self.state.packet in self.state.result.get(
                        "visual_packets", ()
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    for self.state.packet in self.state.result["packets"]:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    if any(
                        packet[0] == 13613 for packet in self.state.result["packets"]
                    ):
                        from wakfu_server.combat_lifecycle import (
                            outside_progression,
                        )

                        self.state.outside_progression = outside_progression

                        if self.state.character["level"] != previous_level:
                            self.state.character = self.runtime.health_store.initialize(
                                self.runtime.STORE,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character["id"],
                                exploration=True,
                            )
                            self.runtime.WORLD.update(
                                self.state.generation,
                                self.state.character,
                                *self.runtime.wire.refresh_player(
                                    self.runtime.PLAYER_TEMPLATE, self.state.character
                                ),
                            )
                            from wakfu_server.level_publication import (
                                refresh,
                            )

                            self.state.refresh = refresh

                            self.runtime.send_batch(
                                self.state.connection,
                                self.state.service,
                                self.state.refresh(
                                    self.state.character,
                                    self.runtime.STORE.characters(
                                        self.state.account_id
                                    ),
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
                            *self.state.outside_progression(
                                self.state.character, wp=self.runtime.COMBAT_TEST_WP
                            ),
                        )
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.runtime.rich_inventory_packet(self.state.character),
                        )
                    if self.state.result.get("notification_key"):
                        from wakfu_server.achievements.service import (
                            acknowledge_notifications,
                        )

                        with self.runtime.STORE.connection() as achievement_db:
                            acknowledge_notifications(
                                achievement_db,
                                self.state.character,
                                [self.state.result["notification_key"]],
                            )
                    self.publish_environment_scene(force=True)
                    self.runtime.record(
                        event="treasure_claim",
                        actor_id=self.state.character["id"],
                        object_id=environment_id,
                        replay=self.state.result["replay"],
                        content_id=self.state.result.get("receipt", {}).get(
                            "content_id"
                        ),
                        native_bindings=self.state.result.get("opened", []),
                    )
                    return DispatchResult.CONTINUE
                environment_rule = environment_interactions.definition(
                    self.runtime.STORE, self.state.character["map_id"], environment_id
                )
                if environment_rule is not None:
                    blocked = self.environment_blocked()
                    if environment_rule["kind"] == "well":
                        self.state.environment_ticket = environment_interactions.begin(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                            blocked=blocked,
                            is_hero=self.environment_actor_is_hero(),
                        )
                        self.runtime.record(
                            event="environment_well_started",
                            actor_id=self.state.character["id"],
                            object_id=environment_id,
                            due_at=str(self.state.environment_ticket["due_at"]),
                        )
                    else:
                        self.state.result = environment_interactions.toggle(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                            blocked=blocked
                            or self.state.environment_ticket is not None,
                        )
                        # Each observer publishes only its loaded native
                        # neighborhood; other peers observe this on idle.
                        self.publish_environment_scene(force=True)
                    return DispatchResult.CONTINUE
                interaction = self.runtime.world_static.interaction(
                    self.state.character, self.state.body
                )
                if (
                    interaction["type"] == "PositionTrigger"
                    and interaction["action"] == "WALKON"
                ):
                    from wakfu_server import quest_ground_entry

                    with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                        self.runtime.flush_positions(account_id=self.state.account_id)
                        quest_entrance = quest_ground_entry.handle(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                            blocked=self.environment_blocked()
                            or self.state.environment_ticket is not None,
                        )
                        if quest_entrance is not None:
                            if "saved" in quest_entrance:
                                self.publish_public_transport(
                                    quest_entrance["transport"],
                                    quest_entrance["saved"],
                                    generic_route=True,
                                )
                            else:
                                for quest_packet in quest_entrance["packets"]:
                                    self.runtime.send(
                                        self.state.connection,
                                        self.state.service,
                                        *quest_packet,
                                    )
                            self.runtime.record(
                                event="qualified_quest_entrance",
                                actor_id=self.state.character["id"],
                                object_id=environment_id,
                                blocked_by_quest=quest_entrance["blocked_by_quest"],
                            )
                            return DispatchResult.CONTINUE
                # An accepted action only proves this target was
                # registered. Keep the map-wide retry armed so
                # other interactives can arrive after lazy loading.
                self.sync_static_world(force=True)
                if interaction["route"] != "transport_registration":
                    if interaction["route"] == "transport_menu":
                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id
                            )
                            transport_action = (
                                self.runtime.TRANSPORT_DISCOVERIES.activate_character(
                                    self.state.account_id,
                                    self.state.generation,
                                    self.state.character,
                                    self.state.body,
                                )
                            )
                        self.publish_settled_quest_packets(transport_action["packets"])
                    self.runtime.record(
                        event="world_interactive_action",
                        actor_id=self.state.character["id"],
                        interaction=interaction,
                        implemented=interaction["route"] == "transport_menu",
                    )
                    return DispatchResult.CONTINUE
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    registration = (
                        self.runtime.TRANSPORT_DISCOVERIES.register_character(
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.body,
                        )
                    )
                kind = registration["kind"]
                self.state.identity = registration["identity"]
                (
                    self.state.message_id,
                    self.state.message_body,
                ) = self.runtime.transport_discovery.discovery_packet(
                    kind, self.state.identity
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
                self.publish_settled_quest_packets(registration["packets"])
                self.runtime.record(
                    event="transport_discovered",
                    account_id=self.state.account_id,
                    kind=kind,
                    transport_id=self.state.identity,
                )
            except ValueError as error:
                self.runtime.record(
                    event="transport_registration_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
            return DispatchResult.CONTINUE
        if (
            self.state.bag_session is None
            or not self.state.bag_session.is_owner
            or not self.state.bag_session.owns(self.state.character)
        ):
            return DispatchResult.CONTINUE
        try:
            self.cancel_crafting()
            previous_furniture = list(
                self.state.character["haven_bag"].get("furniture", [])
            )
            self.state.result = edit_bag_furniture(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.opcode,
                self.state.body,
                location=self.state.character,
            )
            self.state.character = self.active_private_session().refresh(
                self.state.character, self.state.result["character"]
            )
            for self.state.message_id, self.state.message_body in self.state.result[
                "packets"
            ]:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            from wakfu_server.haven_bag_furniture_world import (
                remove as remove_furniture_scene,
                upsert as publish_furniture_scene,
            )

            self.state.publish_furniture_scene = publish_furniture_scene

            current_furniture = {
                item["item_uid"]: item
                for item in self.state.character["haven_bag"].get("furniture", [])
            }
            for old_item in previous_furniture:
                new_item = current_furniture.get(old_item["item_uid"])
                if old_item != new_item:
                    self.runtime.WORLD.emit_location(
                        self.state.character["map_id"],
                        self.state.character["instance_id"],
                        *remove_furniture_scene(old_item),
                    )
                    if new_item is not None and new_item.get("deployed"):
                        self.runtime.WORLD.emit_location(
                            self.state.character["map_id"],
                            self.state.character["instance_id"],
                            *self.state.publish_furniture_scene(
                                self.state.character, new_item
                            ),
                        )
            self.runtime.record(
                event="haven_bag_furniture_edited",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
        except ValueError as error:
            self.runtime.record(
                event="haven_bag_furniture_edit_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.ecology_feedback import information

            self.state.information = information
            from wakfu_server.player_action_feedback import failure_message

            self.state.failure_message = failure_message

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.failure_message("furniture", error)),
            )
        return DispatchResult.FALLTHROUGH

    def handle_haven_furniture_move(self):
        from wakfu_server.haven_bag_furniture_transfer import (
            deploy as deploy_bag_furniture,
        )
        from wakfu_server.haven_bag import own_bag

        self.state.own_bag = own_bag

        if (
            self.state.bag_session is None
            or not self.state.bag_session.is_owner
            or not self.state.bag_session.owns(self.state.character)
        ):
            return DispatchResult.CONTINUE
        try:
            self.cancel_crafting()
            previous_furniture_uids = {
                item["item_uid"]
                for item in self.state.character["haven_bag"].get("furniture", [])
                if item.get("deployed")
            }
            self.state.result = deploy_bag_furniture(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                location=self.state.character,
            )
            self.state.character = self.active_private_session().refresh(
                self.state.character, self.state.result["character"]
            )
            for self.state.message_id, self.state.message_body in self.state.result[
                "packets"
            ]:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            from wakfu_server.haven_bag_furniture_world import (
                upsert as publish_furniture_scene,
            )

            self.state.publish_furniture_scene = publish_furniture_scene

            for item in self.state.character["haven_bag"].get("furniture", []):
                if (
                    item.get("deployed")
                    and item["item_uid"] not in previous_furniture_uids
                ):
                    self.runtime.WORLD.emit_location(
                        self.state.character["map_id"],
                        self.state.character["instance_id"],
                        *self.state.publish_furniture_scene(self.state.character, item),
                    )
            self.runtime.record(
                event="haven_bag_furniture_saved", actor_id=self.state.character["id"]
            )
        except ValueError as error:
            self.runtime.record(
                event="haven_bag_furniture_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_haven_bag_settings(self):
        from wakfu_server.haven_bag_store import save as save_haven_bag

        self.state.save_haven_bag = save_haven_bag
        from wakfu_server.haven_bag import (
            decode_permissions,
            visit_permission_payload,
        )

        if (
            self.state.bag_session is None
            or not self.state.bag_session.is_owner
            or not self.state.bag_session.owns(self.state.character)
        ):
            return DispatchResult.CONTINUE
        try:
            locked, self.state.access = decode_permissions(self.state.body)
            self.state.saved = self.state.save_haven_bag(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                locked=locked,
                access=self.state.access,
            )
            self.state.character = self.active_private_session().refresh(
                self.state.character, self.state.saved
            )
            self.runtime.record(
                event="haven_bag_permissions_saved",
                actor_id=self.state.character["id"],
            )
        except ValueError as error:
            self.runtime.record(
                event="haven_bag_permissions_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        self.state.payload = visit_permission_payload(self.state.character["haven_bag"])
        self.runtime.WORLD.emit_location(
            9,
            self.state.bag_session.bag_instance_id,
            13522,
            struct.pack(">qI", self.state.character["id"], len(self.state.payload))
            + self.state.payload,
        )
        return DispatchResult.FALLTHROUGH

    def handle_haven_bag_transfer(self):
        from wakfu_server.haven_bag_transfer import (
            can_transfer,
            insert,
            remove,
        )

        self.state.remove = remove
        from wakfu_server.haven_bag import own_bag

        self.state.own_bag = own_bag

        # Gem transfers are owner-only. A visitor can be on map 9,
        # but only this connection's active private-bag owner may
        # mutate its inventory or layout.
        if not can_transfer(
            self.state.bag_session,
            self.state.character,
            fight_active=self.state.fight is not None,
        ):
            return DispatchResult.CONTINUE
        try:
            if self.state.opcode == 12177:
                self.state.result = insert(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    location=self.state.character,
                )
            else:
                occupied_by_others = any(
                    player["id"] != self.state.character["id"]
                    and player["map_id"] == 9
                    and player["instance_id"] == self.state.character["instance_id"]
                    for player in self.runtime.WORLD.snapshot()
                )
                self.state.result = self.state.remove(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    location={
                        **self.state.character,
                        "other_occupants": occupied_by_others,
                    },
                )
            self.state.character = self.active_private_session().refresh(
                self.state.character, self.state.result["character"]
            )
            if self.runtime.STORE.current_session(
                self.state.account_id, self.state.generation
            ):
                for self.state.message_id, self.state.message_body in self.state.result[
                    "packets"
                ]:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.message_body,
                    )
            self.runtime.record(
                event="haven_bag_gem_transfer_applied",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                uid=self.state.result["uid"],
                room=self.state.result["room"],
                replayed=self.state.result.get("replayed", False),
            )
        except ValueError as error:
            self.runtime.record(
                event="haven_bag_gem_transfer_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=str(error),
            )
            # Refresh the authoritative room state after an invalid
            # native request; never fabricate a success delta.
            if self.runtime.STORE.current_session(
                self.state.account_id, self.state.generation
            ):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12187,
                    self.state.own_bag(self.state.character),
                )
        return DispatchResult.FALLTHROUGH

    def handle_haven_bag_permission(self):
        from wakfu_server.haven_bag_store import (
            save as save_haven_bag,
            rearrange_rooms,
        )

        self.state.save_haven_bag = save_haven_bag
        from wakfu_server.haven_bag import own_bag

        self.state.own_bag = own_bag

        if (
            self.state.bag_session is None
            or not self.state.bag_session.is_owner
            or not self.state.bag_session.owns(self.state.character)
        ):
            return DispatchResult.CONTINUE
        try:
            rooms = rearrange_rooms(self.state.character["haven_bag"], self.state.body)
            self.state.saved = self.state.save_haven_bag(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                rooms=rooms,
            )
            self.state.character = self.active_private_session().refresh(
                self.state.character, self.state.saved
            )
            self.runtime.record(
                event="haven_bag_rooms_saved", actor_id=self.state.character["id"]
            )
        except ValueError as error:
            self.runtime.record(
                event="haven_bag_rooms_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        # cyX12187 reloads the authoritative tR configuration even
        # after a rejected edit, rather than inventing partial ACKs.
        self.runtime.send(
            self.state.connection,
            self.state.service,
            12187,
            self.state.own_bag(self.state.character),
        )
        return DispatchResult.FALLTHROUGH

    def handle_haven_bag_access(self):
        from wakfu_server.haven_bag_store import save as save_haven_bag

        self.state.save_haven_bag = save_haven_bag

        if len(self.state.body) != 4:
            raise ValueError("Invalid haven bag appearance request")
        appearance_id = struct.unpack(">i", self.state.body)[0]
        self.state.saved = self.state.save_haven_bag(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            appearance_id=appearance_id,
        )
        self.state.character = (
            self.active_private_session().refresh(
                self.state.character, self.state.saved
            )
            if self.active_private_session() is not None
            and self.active_private_session().owns(self.state.character)
            else self.state.saved
        )
        self.runtime.record(
            event="haven_bag_appearance_saved",
            actor_id=self.state.character["id"],
            appearance_id=appearance_id,
        )
        return DispatchResult.FALLTHROUGH

    def handle_haven_bag_leave(self):
        from wakfu_server.haven_bag import leave_messages
        from wakfu_server.haven_bag import validate_leave_request

        validate_leave_request(self.state.body)
        if self.state.ranch_session is not None:
            self.validate_ranch_lease()
            self.state.character = self.state.ranch_session.leave(self.state.character)
            self.state.ranch_session = None
        if self.state.bag_session is None or not self.state.bag_session.owns(
            self.state.character
        ):
            # A missing cyV13019 notification could leave bag UI
            # active after the exterior map was already restored.
            for (
                self.state.message_id,
                self.state.message_body,
            ) in self.runtime.owned_haven_leave(
                self.runtime.fixture(13974), self.state.character
            ):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            self.runtime.record(
                event="haven_bag_leave_repaired", actor_id=self.state.character["id"]
            )
            return DispatchResult.CONTINUE
        self.runtime.PLANTINGS.cancel(self.state.character["id"], self.state.generation)
        self.runtime.HARVESTS.cancel(
            self.state.character["id"], generation=self.state.generation
        )
        self.cancel_flora()
        self.cancel_crafting()
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
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
        self.state.character = self.state.bag_session.leave(self.state.character)
        self.state.bag_session = None
        self.state.ranch_session = None
        self.state.position = {
            key: self.state.character[key] for key in ("x", "y", "z")
        }
        self.state.movement_state = self.runtime.Movement(self.state.position)
        for (
            self.state.message_id,
            self.state.message_body,
        ) in self.runtime.owned_haven_leave(
            self.runtime.fixture(13974), self.state.character
        ):
            self.runtime.send(
                self.state.connection,
                self.state.service,
                self.state.message_id,
                self.state.message_body,
            )
        self.runtime.join_world(
            self.state.generation, self.state.connection, self.state.character
        )
        self.mark_static_sync_pending()
        self.runtime.record(
            event="haven_bag_left",
            actor_id=self.state.character["id"],
            position=self.state.position,
        )
        return DispatchResult.FALLTHROUGH
