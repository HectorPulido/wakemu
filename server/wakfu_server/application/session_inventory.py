"""Inventory operations for one lease-bound World session."""

import struct
import time
from wakfu_server.performance_profiler import PROFILER
from .dispatch_result import DispatchResult


class InventorySessionMixin:
    def refresh_item_mutation_character(self, owner_id=None):
        from wakfu_server.combat_lifecycle import outside_progression

        owner_id = self.state.character["id"] if owner_id is None else owner_id
        updated = self.runtime.STORE.character(self.state.account_id, owner_id)
        if owner_id == self.state.character["id"]:
            updated = self.refresh_owned_character(updated)
        self.runtime.send(
            self.state.connection,
            self.state.service,
            *outside_progression(updated, wp=self.runtime.COMBAT_TEST_WP),
        )
        return updated

    def publish_consumable_character(self, updated):
        from wakfu_server.consumable_world_publication import publish

        publish(
            self.runtime.WORLD,
            self.state.generation,
            updated,
            send=lambda opcode, body: self.runtime.send(
                self.state.connection, self.state.service, opcode, body
            ),
        )

    def spawn_inventory_test_actor(self, body):
        from wakfu_server import item_test_spawns

        if item_test_spawns.action_class(body) is None:
            return False
        if self.state.bag_session is not None or self.state.ranch_session is not None:
            raise ValueError("Developer test actors require ordinary public ground")
        location = dict(self.state.character, **self.state.position)
        with self.runtime.COMBAT_GROUPS.lock:
            occupied = [
                tuple(row[key] for key in ("x", "y", "z"))
                for row in self.runtime.WORLD.ecology_snapshot()
                if (row["map_id"], row["instance_id"])
                == (location["map_id"], location["instance_id"])
            ]
            result = item_test_spawns.use(
                self.runtime.STORE,
                self.runtime.COMBAT_GROUPS,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                body,
                in_fight=self.state.fight is not None
                or self.state.combat_session is not None,
                location=location,
                occupied_cells=occupied,
            )
            if result["applied"]:
                for packet in result["world_packets"]:
                    self.runtime.WORLD.emit_location(*result["key"][:2], *packet)
        self.runtime.record(
            event="developer_item_test_actor",
            actor_id=self.state.character["id"],
            group_key=result["key"],
            created=result["applied"],
            consumed=0,
        )
        return True

    def publish_account_item_spells(self, *, seed=False):
        if (
            not self.state.loaded
            or self.state.character is None
            or self.state.fight is not None
            or self.state.combat_session is not None
        ):
            return
        from wakfu_server.item_spell_publication import account_inventory_packets

        with self.state.connection.write_lock:
            try:
                packets = account_inventory_packets(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
            except ValueError:
                return  # An obsolete socket cannot publish a replacement lease's book.
            for opcode, payload in packets:
                entries = []
                for offset in range(8, len(payload), 14):
                    uid = struct.unpack_from(">q", payload, offset + 4)[0]
                    if seed:
                        self.state.connection.item_spell_uids.add(uid)
                    elif uid not in self.state.connection.item_spell_uids:
                        entries.append(payload[offset : offset + 14])
                if entries:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        opcode,
                        payload[:8] + b"".join(entries),
                    )

    def refresh_pet_hibernation(self):
        from wakfu_server import pet_hibernation
        from wakfu_server.mount_publication import pet_packet

        deadlines = []
        with self.runtime.STORE.connection() as db:
            heroes = db.execute(
                "SELECT character_id FROM account_hero_slots WHERE account_id=%s",
                (self.state.account_id,),
            ).fetchall()
        for owner_id in (
            self.state.character["id"],
            *(row["character_id"] for row in heroes),
        ):
            result = pet_hibernation.refresh(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                owner_id,
            )
            if result["next_deadline_ms"] is not None:
                deadlines.append(result["next_deadline_ms"])
            if not result["changed"]:
                continue
            saved = result["character"]
            saved.update(
                {
                    key: self.state.character[key]
                    for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                }
            )
            for packet in result["packets"]:
                self.runtime.send(self.state.connection, self.state.service, *packet)
            if owner_id == self.state.character["id"]:
                self.state.character = self.refresh_owned_character(saved)
                self.runtime.WORLD.update(
                    self.state.generation,
                    self.state.character,
                    *pet_packet(self.state.character),
                )
                self.publish_consumable_character(self.state.character)
            else:
                from wakfu_server.hero_wire import statistics

                self.runtime.send(
                    self.state.connection, self.state.service, *pet_packet(saved)
                )
                self.runtime.send(
                    self.state.connection, self.state.service, *statistics(saved)
                )
        self.state.pet_hibernation_due = (
            time.monotonic()
            + max(0.1, (min(deadlines) - int(time.time() * 1000)) / 1000)
            if deadlines
            else time.monotonic() + 60
        )

    def play_inventory_emote(self, body):
        from wakfu_server.emote_item_actions import action_class, play

        if action_class(body) is None:
            return False

        def target(actor_id):
            identity = self.runtime.WORLD.live_identity(character_id=actor_id)
            return None if identity is None else identity[1]

        outcome = play(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character,
            body,
            resolve_target=target,
            in_fight=lambda actor_id: (
                actor_id == self.state.character["id"]
                and (
                    self.state.fight is not None
                    or self.state.combat_session is not None
                )
            )
            or self.runtime.COMBAT_SESSIONS.lookup_character(actor_id) is not None,
            occupied=lambda actor_id: actor_id in self.runtime.HARVESTS.pending
            or actor_id in self.runtime.PLANTINGS.pending,
        )
        saved = self.refresh_owned_character(outcome["character"])
        saved.update(
            {
                key: self.state.character[key]
                for key in ("map_id", "instance_id", "x", "y", "z", "direction")
            }
        )
        for packet in outcome["packets"]:
            self.runtime.send(self.state.connection, self.state.service, *packet)
        saved["_emote_packet"] = outcome["packet"]
        saved["_emote_until"] = (
            float("inf")
            if outcome["duration_ms"] < 0
            else time.monotonic() + outcome["duration_ms"] / 1000
        )
        self.state.character = saved
        self.runtime.WORLD.update(
            self.state.generation, self.state.character, *outcome["packet"]
        )
        self.runtime.record(
            event="emote_item_used", actor_id=self.state.character["id"], consumed=1
        )
        return True

    def play_inventory_script(self, body):
        from wakfu_server.script_item_actions import action_class, descriptors, use

        if action_class(body) is None:
            return False
        source_uid = struct.unpack_from(">q", body, 4)[0]
        with self.runtime.STORE.connection() as db:
            owner = db.execute(
                "SELECT character_id FROM inventory_items WHERE uid=%s",
                (source_uid,),
            ).fetchone()
        if owner is None:
            raise ValueError("The visual item is unavailable")
        if owner["character_id"] != self.state.character["id"]:
            raise ValueError(
                "Select the character carrying this visual item before using it"
            )
        # Following heroes share their selected main's visible scene. The
        # consuming transaction independently fences the actual item's owner.
        location = dict(self.state.character, id=owner["character_id"])
        target = (
            struct.unpack_from(">iih", body, 13)
            if body[12]
            else tuple(location[key] for key in ("x", "y", "z"))
        )
        scene = (location["map_id"], location["instance_id"])
        action_id = struct.unpack_from(">i", body)[0]
        plan = next(
            row for row in descriptors()["items"] if row["action_id"] == action_id
        )
        present = False
        if plan["requires_mobile_target"]:
            present = any(
                (actor["map_id"], actor["instance_id"]) == scene
                and tuple(actor[key] for key in ("x", "y", "z")) == target
                and self.runtime.COMBAT_SESSIONS.lookup_character(actor["id"]) is None
                for actor in self.runtime.WORLD.ecology_snapshot()
            )
            if not present:
                present = any(
                    any(
                        tuple(actor[key] for key in ("x", "y", "z")) == target
                        for actor in group["members"]
                    )
                    for group in self.runtime.COMBAT_GROUPS.available(*scene)
                )
        outcome = use(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            body,
            in_fight=self.state.fight is not None
            or self.state.combat_session is not None,
            location=location,
            native_map_id=self.state.character["map_id"],
            target_present=present,
        )
        for packet in outcome["packets"]:
            self.runtime.send(self.state.connection, self.state.service, *packet)
        if outcome["character"]["id"] == self.state.character["id"]:
            saved = self.refresh_owned_character(outcome["character"])
            saved.update(
                {
                    key: self.state.character[key]
                    for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                }
            )
            self.state.character = saved
        # Publish only after the inventory transaction commits. This packet is
        # a scene visual and does not refresh actor characteristics or gear.
        self.runtime.WORLD.emit_location(*scene, *outcome["script_packet"])
        self.runtime.record(
            event="script_item_used",
            actor_id=outcome["character"]["id"],
            script_id=outcome["script_id"],
            consumed=outcome["consumed"],
        )
        return True

    def mark_inventory_destination(self, body):
        from wakfu_server.world_marker_item_actions import action_class, use

        if action_class(body) is None:
            return False
        result = use(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            body,
            in_fight=self.state.fight is not None
            or self.state.combat_session is not None,
            native_map_id=self.runtime.native_item_world_identity(self.state.character),
            private_context=self.active_private_session() is not None,
        )
        self.runtime.record(
            event="inventory_destination_marked",
            actor_id=result["actor_id"],
            source_reference=result["source_reference"],
            consumed=result["consumed"],
            marker=result["marker"],
        )
        return True

    def open_item_recustomization(self, body):
        from wakfu_server.simple_item_actions import _action_classes

        action_id = struct.unpack_from(">i", body)[0]
        if "bIb" not in _action_classes().get(action_id, ()):
            return False
        if (
            self.state.fight is not None
            or self.state.combat_session is not None
            or self.active_private_session() is not None
            or self.state.chest_opening is not None
            or self.state.guild_chest_session is not None
            or self.state.hero_switch_pending is not None
        ):
            raise ValueError(
                "Termina la actividad actual antes de cambiar tu personaje"
            )
        from wakfu_server.character_recustomization import request, transition_packets

        self.runtime.flush_positions(
            account_id=self.state.account_id,
            generation=self.state.generation,
            character_id=self.state.character["id"],
        )
        outcome = request(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            body,
        )
        for packet in outcome["packets"]:
            self.runtime.send(self.state.connection, self.state.service, *packet)
        self.runtime.POSITIONS.release(
            self.state.account_id, self.state.generation, self.state.character["id"]
        )
        self.runtime.STORE.clear_character(self.state.account_id, self.state.generation)
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        self.state.selected = self.state.loaded = False
        self.state.hero_switch_pending = self.state.movement_state = None
        for packet in transition_packets(outcome["character"]):
            self.runtime.send(self.state.connection, self.state.service, *packet)
        self.runtime.record(
            event="item_recustomization_opened",
            actor_id=self.state.character["id"],
            mode=outcome["pending"]["mode"],
        )
        self.state.character = None
        return True

    def cancel_crafting(self):
        self.cancel_environment()
        if (
            self.state.account_id is None
            or self.state.generation is None
            or self.state.character is None
        ):
            return
        from wakfu_server.crafting import current as current_crafting
        from wakfu_server.crafting import cancel as cancel_crafting_occupation

        occupation = current_crafting(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
        )
        if occupation is not None:
            cancel_crafting_occupation(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                occupation["token"],
                occupation["version"],
                b"\x03\x00\x08",
            )

    @PROFILER.profile("inventory.mount_publish")
    def publish_mount_equipment(self, previous, current):
        # Build transactions already reconcile riding when the equipped UID
        # changes. Publish that committed state only outside combat.
        if self.state.fight is not None:
            return
        from wakfu_server.mount_publication import equipment_changes

        for packet in equipment_changes(
            self.runtime.PLAYER_TEMPLATE, previous, current
        ):
            if current["id"] == self.state.character["id"]:
                self.runtime.WORLD.update(self.state.generation, current, *packet)
            else:
                # Heroes share the leader's world subscription, rather than
                # owning a separate registered world connection.
                self.runtime.send(self.state.connection, self.state.service, *packet)
                self.runtime.WORLD.broadcast(
                    self.state.generation,
                    self.state.character["id"],
                    *packet,
                    include_sender=False,
                )
        self.runtime.send_native_planting_bonus(self.state.connection, current)

    def handle_inventory_move(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.mount_feeding_dispatch import (
            prepare as prepare_mount_feeding,
            publish_result as publish_mount_feeding,
        )
        from wakfu_server.inventory_move import (
            reload_inventory,
            synchronization,
        )

        self.state.reload_inventory = reload_inventory
        self.state.synchronization = synchronization
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.state.result = prepare_mount_feeding(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                in_fight=self.state.fight is not None,
            )
        except ValueError as error:
            self.state.character = self.state.reload_inventory(
                self.runtime.STORE, self.state.account_id, self.state.character
            )
            self.runtime.send_batch(
                self.state.connection,
                self.state.service,
                [
                    self.state.synchronization(self.state.character),
                    self.runtime.rich_inventory_packet(self.state.character),
                ],
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
            self.runtime.record(
                event="mount_food_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        except (self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    "La alimentación está temporalmente indisponible."
                ),
            )
            self.runtime.record(
                event="mount_food_unavailable",
                actor_id=self.state.character["id"],
                reason=type(error).__name__,
            )
        else:
            # This is deliberately outside the domain-error catch:
            # publication happens after commit. Any send/encoding
            # failure must disconnect so the next bootstrap repairs
            # the client's inventory without replaying additive deltas.
            publish_mount_feeding(
                self.state.result,
                lambda packets: self.runtime.send_batch(
                    self.state.connection, self.state.service, packets
                ),
            )
            self.state.pet_hibernation_due = 0.0
            self.state.saved = self.state.result["character"]
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.updated = self.refresh_owned_character(self.state.saved)
                self.state.updated.update(
                    {
                        key: self.state.character[key]
                        for key in (
                            "map_id",
                            "instance_id",
                            "x",
                            "y",
                            "z",
                            "direction",
                        )
                    }
                )
                self.state.character = self.state.updated
                self.state.saved = self.state.character
            if self.state.result["applied"]:
                # PET attaches the actor observer to the refreshed
                # rich item model. XP itself belongs to ProtoPet.
                from wakfu_server.mount_publication import pet_packet

                if self.state.saved["id"] == self.state.character["id"]:
                    self.runtime.WORLD.update(
                        self.state.generation,
                        self.state.character,
                        *pet_packet(self.state.character),
                    )
                    self.publish_consumable_character(self.state.character)
                else:
                    from wakfu_server.territory_bonuses import world_packet

                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *pet_packet(self.state.saved),
                    )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *world_packet(self.state.saved),
                    )
                for self.state.packet in self.runtime.mount_snapshot(self.state.saved):
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
            self.runtime.record(
                event="mount_food_fed",
                actor_id=self.state.saved["id"],
                applied=self.state.result["applied"],
                replayed=self.state.result["replayed"],
                xp_delta=self.state.result["xp_delta"],
                health_delta=self.state.result["health_delta"],
            )
        return DispatchResult.FALLTHROUGH

    def handle_mount_state(self):
        from wakfu_server.mount_state import toggle
        from wakfu_server.mount_codec import ride_result, dismounted

        if self.state.body:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *ride_result(self.state.character["id"], 7),
            )
            self.runtime.record(
                event="mount_request_rejected",
                actor_id=self.state.character["id"],
                reason="Mount requests require an empty body",
            )
            return DispatchResult.CONTINUE
        wants_mount = self.state.opcode == 12634
        if self.state.fight is not None or self.state.bag_session is not None:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *ride_result(self.state.character["id"], 3),
            )
            return DispatchResult.CONTINUE
        if wants_mount:
            self.cancel_flora()
            self.runtime.PLANTINGS.cancel(
                self.state.character["id"], self.state.generation
            )
            self.runtime.HARVESTS.cancel(
                self.state.character["id"], generation=self.state.generation
            )
        try:
            code, self.state.saved = toggle(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                mounted=wants_mount,
                in_fight=False,
                location_allowed=True,
                occupation_cancelable=True,
            )
        except ValueError as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *ride_result(self.state.character["id"], 7),
            )
            self.runtime.record(
                event="mount_request_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            return DispatchResult.CONTINUE
        self.state.character = self.state.saved
        if code:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *ride_result(self.state.character["id"], code),
            )
        else:
            self.state.packet = (
                ride_result(self.state.character["id"], 0)
                if wants_mount
                else dismounted(self.state.character["id"])
            )
            self.runtime.WORLD.update(
                self.state.generation, self.state.character, *self.state.packet
            )
        self.runtime.record(
            event="mount_toggle",
            actor_id=self.state.character["id"],
            requested_mounted=wants_mount,
            result=code,
        )
        return DispatchResult.FALLTHROUGH

    def handle_craft(self):
        from wakfu_server.crafting import begin as begin_crafting
        from wakfu_server.craft_station import (
            native_catalog as craft_catalog,
            resolve_current as resolve_craft_station,
        )

        self.state.craft_catalog = craft_catalog
        self.state.resolve_craft_station = resolve_craft_station
        from wakfu_server.craft_wire import request as craft_request
        from wakfu_server.craft_wire import (
            occupation_request as craft_occupation_request,
        )
        from wakfu_server.craft_wire import result as craft_result

        self.state.craft_result = craft_result

        try:
            if self.state.fight is not None:
                raise ValueError("Crafting is unavailable in this session state")
            if (
                self.state.character["id"] in self.runtime.PLANTINGS.pending
                or self.state.character["id"] in self.runtime.HARVESTS.pending
            ):
                raise ValueError("Finish or cancel the current occupation first")
            self.state.request = (
                craft_request(self.state.opcode, self.state.body)
                if self.state.opcode == 12231
                else craft_occupation_request(self.state.body)
            )
            self.state.station = self.state.resolve_craft_station(
                self.state.character, self.state.request["table_id"]
            )
            self.state.result = begin_crafting(
                self.runtime.STORE,
                self.state.craft_catalog(),
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.opcode,
                self.state.body,
                station=self.state.station,
                # Character-level CRAFT_SPEED is not persisted in
                # the world snapshot yet; zero is the explicit
                # local baseline, while the recipe timer still
                # uses the native percentage formula.
                craft_speed_modifier=0,
                location_resolver=(
                    (
                        lambda saved: self.active_private_session().refresh(
                            self.state.character, saved
                        )
                    )
                    if self.active_private_session() is not None
                    else None
                ),
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
            self.runtime.record(
                event="craft_occupation_started",
                actor_id=self.state.character["id"],
                table_uid=self.state.request["table_id"],
                recipe_id=self.state.request["recipe_id"],
                request_opcode=self.state.opcode,
                duration_ms=self.state.result["duration_ms"],
                duplicate=self.state.result["duplicate"],
            )
        except ValueError as error:
            self.state.message = str(error)
            self.state.status = (
                7
                if "reachable" in self.state.message
                or "current map" in self.state.message
                else (
                    8
                    if "not allowed" in self.state.message
                    or "table" in self.state.message
                    else (
                        9
                        if "criterion" in self.state.message
                        or "flags" in self.state.message
                        else (
                            10
                            if "ingredient" in self.state.message
                            or "batch" in self.state.message
                            else (
                                3
                                if "Unknown native crafting recipe"
                                in self.state.message
                                else 1
                            )
                        )
                    )
                )
            )
            try:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.craft_result(self.state.status, 0, 0),
                )
            except ValueError:
                pass
            self.runtime.record(
                event="craft_occupation_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.message,
                native_status=self.state.status,
            )
        return DispatchResult.FALLTHROUGH

    def handle_craft_station(self):
        from wakfu_server.crafting import (
            cancel as cancel_crafting_occupation,
            complete as complete_crafting,
            current as current_crafting,
            completion_target as craft_completion_target,
        )
        from wakfu_server.craft_station import (
            native_catalog as craft_catalog,
            resolve_current as resolve_craft_station,
        )

        self.state.craft_catalog = craft_catalog
        self.state.resolve_craft_station = resolve_craft_station
        from wakfu_server.craft_wire import result as craft_result

        self.state.craft_result = craft_result

        try:
            if self.state.fight is not None:
                raise ValueError("Crafting is unavailable in this session state")
            occupation = (
                craft_completion_target(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
                if self.state.body[0] == 2
                else current_crafting(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
            )
            if occupation is None:
                raise ValueError("Crafting occupation is no longer active")
            if self.state.body[0] == 3:
                cancel_crafting_occupation(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    occupation["token"],
                    occupation["version"],
                    self.state.body,
                )
                self.runtime.record(
                    event="craft_occupation_canceled",
                    actor_id=self.state.character["id"],
                    recipe_id=occupation["recipe_id"],
                )
                return DispatchResult.CONTINUE
            self.state.station = (
                None
                if occupation.get("state") == "completed"
                else self.state.resolve_craft_station(
                    self.state.character, occupation["table_uid"]
                )
            )
            self.state.result = complete_crafting(
                self.runtime.STORE,
                self.state.craft_catalog(),
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                occupation["token"],
                occupation["version"],
                self.state.body,
                station=self.state.station,
                location_resolver=(
                    (
                        lambda saved: self.active_private_session().refresh(
                            self.state.character, saved
                        )
                    )
                    if self.active_private_session() is not None
                    else None
                ),
            )
            if self.state.result["replay"]:
                from wakfu_server.inventory_move import synchronization

                self.state.synchronization = synchronization
                from wakfu_server.inventory_items import equipment_inventory

                self.state.equipment_inventory = equipment_inventory
                from wakfu_server.profession_store import account_packet

                self.state.saved = self.runtime.STORE.character(
                    self.state.account_id, self.state.character["id"]
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.synchronization(self.state.saved),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.equipment_inventory(self.state.saved),
                )
                with self.runtime.STORE.connection() as self.state.db:
                    self.state.progress_packet = account_packet(
                        self.state.db, self.state.account_id
                    )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.progress_packet,
                )
            else:
                for self.state.message_id, self.state.message_body in self.state.result[
                    "packets"
                ]:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.message_body,
                    )
            self.state.saved = self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"]
            )
            self.state.character = (
                self.active_private_session().refresh(
                    self.state.character, self.state.saved
                )
                if self.active_private_session() is not None
                and self.active_private_session().owns(self.state.character)
                else self.state.saved
            )
            self.runtime.send_native_planting_bonus(
                self.state.connection, self.state.character
            )
            self.runtime.record(
                event="craft_occupation_completed",
                actor_id=self.state.character["id"],
                recipe_id=occupation["recipe_id"],
                applied_xp=self.state.result.get("applied_xp", 0),
                replay=self.state.result["replay"],
            )
        except ValueError as error:
            self.state.message = str(error)
            self.state.status = (
                12
                if "before its duration" in self.state.message
                else (
                    7
                    if "reachable" in self.state.message
                    or "current map" in self.state.message
                    else 10 if "ingredient" in self.state.message else 1
                )
            )
            try:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.craft_result(self.state.status, 0, 0),
                )
            except ValueError:
                pass
            self.runtime.record(
                event="craft_occupation_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.message,
                native_status=self.state.status,
            )
        return DispatchResult.FALLTHROUGH

    def handle_appearance_fusion(self):
        from wakfu_server.item_appearance_fusion import (
            use as fuse_item_appearance,
        )
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            fusion = fuse_item_appearance(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                in_fight=self.state.fight is not None
                or self.state.combat_session is not None,
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.state.reason = (
                str(error)
                if isinstance(error, ValueError)
                else "No se pudo fusionar la apariencia; inténtalo de nuevo"
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.reason),
            )
            self.runtime.record(
                event="item_appearance_fusion_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.reason,
            )
            return DispatchResult.CONTINUE
        self.state.saved = fusion["character"]
        if self.state.saved["id"] == self.state.character["id"]:
            self.state.updated = self.refresh_owned_character(self.state.saved)
            self.state.updated.update(
                {
                    key: self.state.character[key]
                    for key in (
                        "map_id",
                        "instance_id",
                        "x",
                        "y",
                        "z",
                        "direction",
                    )
                }
            )
            self.state.character = self.state.saved = self.state.updated
        for self.state.packet in fusion["packets"]:
            self.runtime.send(
                self.state.connection, self.state.service, *self.state.packet
            )
        from wakfu_server.equipment_appearance import snapshot_packet

        if self.state.saved["id"] == self.state.character["id"]:
            self.runtime.WORLD.update(
                self.state.generation,
                self.state.character,
                *snapshot_packet(self.state.saved),
            )
        else:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *snapshot_packet(self.state.saved),
            )
            self.runtime.WORLD.broadcast(
                self.state.generation,
                self.state.character["id"],
                *snapshot_packet(self.state.saved),
                include_sender=False,
            )
        self.runtime.record(
            event="item_appearance_fused",
            actor_id=self.state.saved["id"],
            stat_uid=fusion["stat_uid"],
            appearance_ref=fusion["appearance_ref"],
            consumed=fusion["consumed"],
        )
        return DispatchResult.FALLTHROUGH

    def handle_inventory_journal(self):
        if (
            self.state.account_id is None
            or self.state.generation is None
            or not self.state.selected
            or self.state.character is None
        ):
            raise ValueError("Inventory journal requires a selected character")
        from wakfu_server.inventory_deferred_journal import query

        self.runtime.send(
            self.state.connection,
            self.state.service,
            *query(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.body,
            ),
        )
        return DispatchResult.FALLTHROUGH

    def handle_item_action(self):
        from psycopg import Error as ItemDatabaseError

        self.state.ItemDatabaseError = ItemDatabaseError
        from psycopg_pool import PoolTimeout as ItemPoolTimeout

        self.state.ItemPoolTimeout = ItemPoolTimeout
        from wakfu_server.simple_item_actions import (
            action_class as simple_item_action_class,
            use as use_simple_item_action,
        )

        from wakfu_server import haven_world_bombs

        if (
            len(self.state.body) >= 4
            and struct.unpack_from(">i", self.state.body)[0]
            in haven_world_bombs.ACTIONS
        ):
            try:
                bombing = haven_world_bombs.use(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    in_fight=self.state.fight is not None
                    or self.state.combat_session is not None,
                    context=dict(self.state.character, **self.state.position),
                )
            except (
                ValueError,
                self.state.ItemDatabaseError,
                self.state.ItemPoolTimeout,
            ) as error:
                self.state.reason = (
                    str(error)
                    if isinstance(error, ValueError)
                    else "No se pudo utilizar la bomba; inténtalo de nuevo"
                )
                self.runtime.record(
                    event="haven_world_bomb_rejected",
                    actor_id=self.state.character["id"],
                    reason=self.state.reason,
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"),
                        self.state.reason,
                    ),
                )
                return DispatchResult.CONTINUE
            # Source/population committed; delivery failure must not
            # re-enter the consuming transaction or roll it back.
            self.state.character = self.refresh_owned_character(bombing["character"])
            self.state.character.update(self.state.position)
            for self.state.packet in bombing["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            for self.state.packet in bombing["scene_packets"]:
                self.runtime.WORLD.emit_location(*bombing["scene"], *self.state.packet)
            self.runtime.record(
                event="haven_world_bomb_used",
                actor_id=self.state.character["id"],
                removed=bombing["removed_count"],
                receipt_id=bombing["receipt_id"],
            )
            return DispatchResult.CONTINUE
        from wakfu_server import (
            dungeon_optional_ground_items,
            dungeon_ground_outcomes,
        )

        self.state.dungeon_optional_ground_items = dungeon_optional_ground_items
        from wakfu_server import (
            dungeon_excavation_provider,
            dungeon_excavation_rules,
        )

        self.state.dungeon_excavation_provider = dungeon_excavation_provider
        self.state.dungeon_excavation_rules = dungeon_excavation_rules

        try:
            used_ground = dungeon_ground_outcomes.dispatch(
                self.state.body,
                [
                    *self.state.dungeon_optional_ground_items.rules(),
                    *self.state.dungeon_excavation_rules.rules(),
                ],
                optional_group=lambda request, rule: dict(
                    self.state.dungeon_optional_ground_items.use(
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
                    ),
                    outcome="optional_group",
                ),
                excavation_state=lambda request, rule: dict(
                    self.state.dungeon_excavation_provider.attempt(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        rule=rule,
                        positions=self.runtime.POSITIONS,
                        in_fight=self.state.fight is not None
                        or self.state.combat_session is not None
                        or self.state.spectator_session is not None,
                    ),
                    outcome="excavation_state",
                ),
                context={},
            )
        except (
            ValueError,
            self.state.ItemDatabaseError,
            self.state.ItemPoolTimeout,
        ) as error:
            self.runtime.record(
                event="native_ground_item_rejected",
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
                        else "No se pudo utilizar el objeto; inténtalo de nuevo"
                    ),
                ),
            )
            return DispatchResult.CONTINUE
        if used_ground is not None:
            self.state.character = self.refresh_owned_character(
                used_ground["character"]
            )
            for self.state.packet in used_ground["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            if used_ground["outcome"] == "optional_group":
                try:
                    from wakfu_server import dungeon_optional_encounters

                    self.state.dungeon_optional_encounters = dungeon_optional_encounters

                    self.state.dungeon_optional_encounters.publish_pending(
                        self.runtime.STORE,
                        self.runtime.COMBAT_GROUPS,
                        instance_id=used_ground["instance_id"],
                        publish=lambda *packet: self.state.dungeon_optional_encounters.publish_native_scene(
                            self.runtime.WORLD, *packet
                        ),
                    )
                except Exception as error:
                    self.runtime.record(
                        event="optional_ground_publication_deferred",
                        actor_id=self.state.character["id"],
                        reason=str(error),
                    )
            self.runtime.record(
                event="native_ground_item_used",
                actor_id=self.state.character["id"],
                outcome=used_ground["outcome"],
                consumed=used_ground["consumed"],
                replay=used_ground["replay"],
            )
            return DispatchResult.CONTINUE
        simple_item_result = None
        try:
            simple_class = simple_item_action_class(self.state.body)
            if simple_class is None:
                from wakfu_server import companions, haven_ranch_herd

                self.state.companions = companions
                self.state.haven_ranch_herd = haven_ranch_herd

                if (
                    self.state.haven_ranch_herd.action_class(self.state.body)
                    is not None
                ):
                    simple_class = "bHz"
                    simple_item_result = self.state.haven_ranch_herd.use(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        in_fight=(
                            self.state.fight is not None
                            or self.state.combat_session is not None
                            or self.state.spectator_session is not None
                        ),
                    )
                elif self.state.companions.action_class(self.state.body) is not None:
                    simple_class = "bHE"
                    simple_item_result = self.state.companions.use(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        in_fight=self.state.fight is not None
                        or self.state.combat_session is not None,
                    )
                elif self.open_item_recustomization(self.state.body):
                    return DispatchResult.CONTINUE
                if simple_item_result is None and self.play_inventory_emote(
                    self.state.body
                ):
                    return DispatchResult.CONTINUE
                if simple_item_result is None and self.use_inventory_teleport(
                    self.state.body
                ):
                    return DispatchResult.CONTINUE
                if simple_item_result is None and self.play_inventory_script(
                    self.state.body
                ):
                    return DispatchResult.CONTINUE
                if simple_item_result is None and self.spawn_inventory_test_actor(
                    self.state.body
                ):
                    return DispatchResult.CONTINUE
                if simple_item_result is None and self.mark_inventory_destination(
                    self.state.body
                ):
                    return DispatchResult.CONTINUE
                if simple_item_result is None:
                    from wakfu_server import (
                        conversion_item_actions,
                        restat_item_actions,
                        neutrality_item_actions,
                        captain_map_item_actions,
                        journal_part_item_actions,
                        achievement_item_actions,
                        binding_kit_item_actions,
                    )

                    for actions in (
                        conversion_item_actions,
                        restat_item_actions,
                        neutrality_item_actions,
                        captain_map_item_actions,
                        journal_part_item_actions,
                        achievement_item_actions,
                        binding_kit_item_actions,
                    ):
                        handled = actions.action_class(self.state.body)
                        if handled is not None:
                            simple_class = handled
                            simple_item_result = actions.use(
                                self.runtime.STORE,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character["id"],
                                self.state.body,
                                in_fight=self.state.fight is not None
                                or self.state.combat_session is not None,
                            )
                            break
                from wakfu_server.scenario_item_actions import (
                    action_class as scenario_item_action_class,
                    use as read_scenario_item,
                )

                if (
                    simple_item_result is None
                    and scenario_item_action_class(self.state.body) is not None
                ):
                    reading = read_scenario_item(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        in_fight=self.state.fight is not None
                        or self.state.combat_session is not None,
                    )
                    for self.state.packet in reading["packets"]:
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
                    self.runtime.record(
                        event="scenario_item_read",
                        actor_id=self.state.character["id"],
                        scenario_id=reading["scenario_id"],
                        consumed=reading["consumed"],
                    )
                    return DispatchResult.CONTINUE
                from wakfu_server.book_item_actions import (
                    action_class as book_action_class,
                    use as read_book_item,
                )

                if (
                    simple_item_result is None
                    and book_action_class(self.state.body) is not None
                ):
                    book_result = read_book_item(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        in_fight=self.state.fight is not None,
                        native_map_id=self.runtime.native_item_world_identity(
                            self.state.character
                        ),
                    )
                    self.runtime.record(
                        event="book_item_read",
                        actor_id=book_result["character"]["id"],
                        background_id=book_result["background_id"],
                        consumed=book_result["consumed"],
                    )
                    return DispatchResult.CONTINUE
                from wakfu_server.random_item_actions import (
                    action_class as random_item_action_class,
                    use as use_random_item_action,
                )

                if simple_item_result is None:
                    simple_class = random_item_action_class(self.state.body)
                if simple_item_result is None and simple_class is not None:
                    simple_item_result = use_random_item_action(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        in_fight=self.state.fight is not None,
                        native_map_id=self.runtime.native_item_world_identity(
                            self.state.character
                        ),
                    )
            elif simple_class is not None:
                simple_item_result = use_simple_item_action(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    in_fight=self.state.fight is not None,
                    native_map_id=self.runtime.native_item_world_identity(
                        self.state.character
                    ),
                )
        except (
            ValueError,
            self.state.ItemDatabaseError,
            self.state.ItemPoolTimeout,
        ) as error:
            self.state.reason = (
                str(error)
                if isinstance(error, ValueError)
                else "No se pudo utilizar el objeto; inténtalo de nuevo"
            )
            self.runtime.record(
                event="simple_item_action_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.reason,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"), self.state.reason
                ),
            )
            return DispatchResult.CONTINUE
        if simple_item_result is not None:
            # Publication is outside the consuming transaction and
            # its error catch. Reconnect repairs a failed delivery;
            # it must never repeat an already committed grant.
            self.state.saved = simple_item_result["character"]
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.saved = self.refresh_owned_character(self.state.saved)
            else:
                self.state.saved = dict(self.state.saved)
            # Buffered movement and private scene coordinates are
            # live authority. Item/XP hydration must not move either
            # the selected actor or its following hero to SQL's
            # durable exterior/previous position.
            self.state.saved.update(
                map_id=self.state.character["map_id"],
                instance_id=self.state.character["instance_id"],
                direction=self.state.character["direction"],
                **self.state.position,
            )
            simple_packets = list(simple_item_result["packets"])
            if simple_class == "bHK":
                from wakfu_server.combat_lifecycle import (
                    outside_progression,
                )

                self.state.outside_progression = outside_progression

                simple_packets[-1] = self.state.outside_progression(
                    self.state.saved, wp=self.runtime.COMBAT_TEST_WP
                )
            elif simple_item_result.get("xp_changed"):
                from wakfu_server.combat_lifecycle import (
                    outside_progression,
                )

                self.state.outside_progression = outside_progression

                # Earned mission XP notifications precede the final
                # absolute progression and level snapshot.
                simple_packets.append(
                    self.state.outside_progression(
                        self.state.saved, wp=self.runtime.COMBAT_TEST_WP
                    )
                )
            if simple_item_result.get("nation_changed"):
                # The original passport scenario reads the updated
                # nation. Publish identity before its private UI event.
                self.state.saved = self.publish_nation_character(self.state.saved)
            for self.state.message_id, self.state.message_body in simple_packets:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            if simple_item_result.get("feedback"):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.saved, name="Información"),
                        simple_item_result["feedback"],
                    ),
                )
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.character = self.state.saved
                if simple_class == "bHK" or simple_item_result.get("xp_changed"):
                    self.runtime.WORLD.update(
                        self.state.generation,
                        self.state.character,
                        *self.runtime.wire.refresh_player(
                            self.runtime.PLAYER_TEMPLATE, self.state.character
                        ),
                    )
                    self.publish_consumable_character(self.state.character)
                elif simple_item_result.get("characteristics_changed"):
                    self.publish_consumable_character(self.state.character)
            else:
                from wakfu_server.hero_wire import refresh

                self.state.refresh = refresh

                if not simple_item_result.get("characteristics_changed"):
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.refresh(
                            self.runtime.OWNED_HERO_TEMPLATE, self.state.saved
                        ),
                    )
                from wakfu_server.hero_wire import statistics

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *statistics(self.state.saved),
                )
            self.runtime.record(
                event="simple_item_action_used",
                actor_id=self.state.saved["id"],
                native_class=simple_class,
                consumed=simple_item_result["consumed"],
            )
            return DispatchResult.CONTINUE
        item_action_class = None
        try:
            from wakfu_server.cosmetic_learning import (
                learn_item,
                request_action_class,
            )

            item_action_class = request_action_class(self.state.body)
            if item_action_class != "bIi":
                if self.state.fight is not None:
                    raise ValueError("Item learning is unavailable during combat")
                self.state.result = learn_item(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                )
                self.state.saved = self.state.result["character"]
                if self.state.saved["id"] == self.state.character["id"]:
                    self.state.character = self.refresh_owned_character(
                        self.state.saved
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
                self.runtime.record(
                    event="item_learned", actor_id=self.state.saved["id"]
                )
                return DispatchResult.CONTINUE
            if self.state.fight is not None:
                raise ValueError("Sal del combate para plantar")

            self.state.character = self.runtime.owned_planting_character(
                self.state.character,
                self.runtime.WORLD,
                self.runtime.POSITIONS,
                store=self.runtime.STORE,
                generation=self.state.generation,
            )
            self.runtime.WORLD.refresh_location(
                self.state.generation, self.state.character
            )

            if self.runtime.ECOLOGY_MODE == "external":
                self.runtime.HARVESTS.cancel(
                    self.state.character["id"], generation=self.state.generation
                )
                self.runtime.PLANTINGS.cancel(
                    self.state.character["id"], self.state.generation
                )
                intent_id = self.runtime.PLANTINGS.ecology_intents.enqueue(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                )
                self.runtime.record(
                    event="planting_preparation_enqueued",
                    actor_id=self.state.character["id"],
                    intent_id=intent_id,
                )
                return DispatchResult.CONTINUE

            raise ValueError("Planting requires the external ecology service")
        except ValueError as error:
            self.runtime.record(
                event=(
                    "planting_rejected"
                    if item_action_class == "bIi"
                    else "item_learning_rejected"
                ),
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

    def handle_shard_identify(self):
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.shard_identification import identify
        from wakfu_server.shard_identification_wire import response

        self.state.response = response
        from wakfu_server.inventory_move import (
            reload_inventory,
            synchronization,
        )

        self.state.reload_inventory = reload_inventory
        self.state.synchronization = synchronization
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if self.state.fight is not None:
                raise ValueError("No puedes identificar objetos durante un combate.")
            self.state.result = identify(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.updated_owner = self.refresh_item_mutation_character(
                self.state.result["character_id"]
            )
            if self.state.updated_owner["id"] == self.state.character["id"]:
                self.state.character = self.state.updated_owner
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.synchronization(self.state.updated_owner),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.response(self.state.result),
            )
            if self.state.result["status"] == 0:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.equipment_inventory(self.state.updated_owner),
                )
            if self.state.result["cost_kamas"] > 0 and self.state.result["status"] == 0:
                with self.runtime.STORE.connection() as self.state.db:
                    balance = self.state.db.execute(
                        "SELECT kamas FROM account_wallets WHERE account_id=%s",
                        (self.state.account_id,),
                    ).fetchone()["kamas"]
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12753,
                    struct.pack(">q", balance),
                )
            self.runtime.record(
                event="inventory_socket_identification",
                actor_id=self.state.result["character_id"],
                uid=self.state.result["uid"],
                status=self.state.result["status"],
                applied=self.state.result["applied"],
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "La identificación está temporalmente indisponible."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="inventory_socket_identification_rejected",
                actor_id=self.state.character["id"],
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_element_select(self):
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.element_selection import select as select_elements
        from wakfu_server.inventory_move import (
            reload_inventory,
            synchronization,
        )

        self.state.reload_inventory = reload_inventory
        self.state.synchronization = synchronization
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if self.state.fight is not None:
                raise ValueError("No puedes seleccionar elementos durante un combate.")
            self.state.result = select_elements(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.updated_owner = self.refresh_item_mutation_character(
                self.state.result["character_id"]
            )
            if self.state.updated_owner["id"] == self.state.character["id"]:
                self.state.character = self.state.updated_owner
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.synchronization(self.state.updated_owner),
            )
            self.runtime.send(
                self.state.connection, self.state.service, *self.state.result["packet"]
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.equipment_inventory(self.state.updated_owner),
            )
            if self.state.result.get("cost_kamas", 0) > 0:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    12753,
                    struct.pack(">q", self.state.result["wallet_kamas"]),
                )
            self.runtime.record(
                event="inventory_elements_selected",
                actor_id=self.state.result["character_id"],
                uid=self.state.result["uid"],
                applied=self.state.result["applied"],
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "La selección de elementos está temporalmente indisponible."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="inventory_elements_rejected",
                actor_id=self.state.character["id"],
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_socket_enchant(self):
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.socket_enchantment import install_bonus, mutate
        from wakfu_server.socket_enchantment_wire import (
            bonus_installation_packets,
            packets,
        )

        self.state.packets = packets
        from wakfu_server.inventory_move import reload_inventory

        self.state.reload_inventory = reload_inventory
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if self.state.fight is not None:
                raise ValueError("No puedes modificar objetos durante un combate.")
            if self.state.opcode == 13269:
                self.state.result = install_bonus(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                )
            else:
                self.state.result = mutate(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.opcode,
                    self.state.body,
                )
            self.state.updated_owner = self.refresh_item_mutation_character(
                self.state.result["character_id"]
            )
            if self.state.updated_owner["id"] == self.state.character["id"]:
                self.state.character = self.state.updated_owner
            response_packets = (
                bonus_installation_packets(
                    self.state.updated_owner["id"], self.state.result
                )
                if self.state.opcode == 13269
                else self.state.packets(
                    self.state.updated_owner["id"], self.state.result
                )
            )
            for self.state.message_id, self.state.message_body in response_packets:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.result["equipment_packet"],
            )
            self.runtime.record(
                event="inventory_socket_enchantment_changed",
                actor_id=self.state.updated_owner["id"],
                uid=self.state.result["uid"],
                operation=self.state.result["operation"],
                applied=self.state.result["applied"],
                consumed_uid=self.state.result.get("consumed_uid"),
                consumed=self.state.result.get("consumed", []),
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "La modificación de ranuras está temporalmente indisponible."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="inventory_socket_enchantment_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_inventory_uid(self):
        from wakfu_server.inventory_uids import replenish

        self.state.message_id, self.state.message_body = replenish(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            self.state.body,
        )["packet"]
        self.runtime.send(
            self.state.connection,
            self.state.service,
            self.state.message_id,
            self.state.message_body,
        )
        self.runtime.record(
            event="inventory_uids_reserved", actor_id=self.state.character["id"]
        )
        return DispatchResult.FALLTHROUGH

    def handle_inventory_bag(self):
        from wakfu_server.inventory_bags import equip, remove

        self.state.remove = remove
        from wakfu_server.inventory_move import (
            synchronization,
            reload_inventory,
        )

        self.state.synchronization = synchronization
        self.state.reload_inventory = reload_inventory

        try:
            operation = equip if self.state.opcode == 12656 else self.state.remove
            self.state.result = operation(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.saved = self.state.result["character"]
            self.state.character = (
                self.active_private_session().refresh(
                    self.state.character, self.state.saved
                )
                if self.active_private_session() is not None
                and self.active_private_session().owns(self.state.character)
                else self.state.saved
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
            self.runtime.record(
                event="inventory_bag_changed",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
        except ValueError as error:
            self.state.character = self.state.reload_inventory(
                self.runtime.STORE, self.state.account_id, self.state.character
            )
            self.state.message_id, self.state.message_body = self.state.synchronization(
                self.state.character
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                self.state.message_id,
                self.state.message_body,
            )
            self.runtime.record(
                event="inventory_bag_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_consumable(self):
        from wakfu_server.inventory_consumable_effects import use
        from wakfu_server.inventory_move import (
            synchronization,
            reload_inventory,
        )

        self.state.synchronization = synchronization
        self.state.reload_inventory = reload_inventory
        from psycopg import Error as ConsumableDatabaseError
        from psycopg_pool import PoolTimeout as ConsumablePoolTimeout

        try:
            self.state.result = use(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                expected_hp=self.state.character["hp"],
                in_fight=self.state.fight is not None,
                native_map_id=self.runtime.native_item_world_identity(
                    self.state.character
                ),
            )
        except (
            ValueError,
            ConsumableDatabaseError,
            ConsumablePoolTimeout,
        ) as error:
            self.state.character = self.state.reload_inventory(
                self.runtime.STORE, self.state.account_id, self.state.character
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.synchronization(self.state.character),
            )
            self.state.reason = (
                str(error)
                if isinstance(error, ValueError)
                else "No se pudo utilizar el consumible; inténtalo de nuevo"
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"), self.state.reason
                ),
            )
            self.runtime.record(
                event="inventory_food_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.reason,
            )
            return DispatchResult.CONTINUE
        # The transaction is committed. Publication failures must
        # never be mistaken for an uncommitted consumable action.
        self.state.saved = self.state.result["character"]
        main_owner = self.state.saved["id"] == self.state.character["id"]
        if main_owner:
            self.state.saved = self.refresh_owned_character(self.state.saved)
            self.state.saved.update(
                map_id=self.state.character["map_id"],
                instance_id=self.state.character["instance_id"],
                direction=self.state.character["direction"],
                **self.state.position,
            )
        else:
            self.state.saved = dict(self.state.saved)
        for self.state.packet in self.state.result["packets"]:
            self.runtime.send(
                self.state.connection, self.state.service, *self.state.packet
            )
        from wakfu_server.inventory_animation import consumable_emote

        for self.state.emote in self.state.result.get("emotes", ()):
            self.state.action_id = next(self.runtime.LOCAL_WORLD_ACTIONS)
            animation = consumable_emote(
                actor_id=self.state.saved["id"],
                action_id=self.state.action_id,
                effect_uid=(1 << 48) + self.state.action_id,
                effect_id=self.state.emote["effect_id"],
                emote_id=self.state.emote["emote_id"],
            )
            if main_owner:
                self.runtime.WORLD.broadcast(
                    self.state.generation, self.state.saved["id"], *animation
                )
            else:
                self.runtime.send(self.state.connection, self.state.service, *animation)
        if self.state.result.get("native_consumable"):
            from wakfu_server.consumable_buff_wire import delta

            for self.state.packet in delta(
                self.state.result["previous_character"],
                self.state.saved,
                allocate_action=lambda: next(self.runtime.LOCAL_WORLD_ACTIONS),
            ):
                if main_owner:
                    self.runtime.WORLD.broadcast(
                        self.state.generation,
                        self.state.saved["id"],
                        *self.state.packet,
                    )
                else:
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
            if main_owner:
                self.publish_consumable_character(self.state.saved)
            else:
                from wakfu_server import hero_wire

                self.state.hero_wire = hero_wire

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.hero_wire.refresh(
                        self.runtime.OWNED_HERO_TEMPLATE, self.state.saved
                    ),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.hero_wire.statistics(self.state.saved),
                )
                for self.state.packet in self.runtime.consumable_state_packets(
                    self.state.saved
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
        if main_owner:
            self.state.character = self.state.saved
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory

        self.runtime.send(
            self.state.connection,
            self.state.service,
            *self.state.equipment_inventory(self.state.saved),
        )
        self.runtime.record(
            event="inventory_food_used",
            actor_id=self.state.saved["id"],
            hp=self.state.saved["hp"],
        )
        return DispatchResult.FALLTHROUGH

    def handle_item_unpack(self):
        from wakfu_server import combat_drop_delivery

        self.state.combat_drop_delivery = combat_drop_delivery
        from wakfu_server.inventory_move import reload_inventory

        self.state.reload_inventory = reload_inventory

        try:
            self.state.action = (
                self.state.combat_drop_delivery.claim
                if self.state.opcode == 13993
                else self.state.combat_drop_delivery.bulk_transfer
            )
            self.state.result = self.state.action(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.saved = (
                self.state.result["character"]
                if self.state.opcode == 13993
                else self.state.result["source"]
            )
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.character = (
                    self.active_private_session().refresh(
                        self.state.character, self.state.saved
                    )
                    if self.active_private_session() is not None
                    and self.active_private_session().owns(self.state.character)
                    else self.state.saved
                )
            for self.state.packet in self.state.result["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
        except ValueError as error:
            self.state.character = self.state.reload_inventory(
                self.runtime.STORE, self.state.account_id, self.state.character
            )
            with self.runtime.STORE.connection() as self.state.db:
                self.state.packets = self.state.combat_drop_delivery.temporary_updates(
                    self.state.db, self.state.character["id"]
                )
            for self.state.packet in self.state.packets:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.record(
                event="combat_loot_claim_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_item_inspect(self):
        from wakfu_server import combat_drop_delivery

        self.state.combat_drop_delivery = combat_drop_delivery

        try:
            self.state.result = self.state.combat_drop_delivery.discard(
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
                event="combat_loot_discarded",
                actor_id=self.state.character["id"],
                applied=self.state.result["applied"],
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_loot_discard_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_recycle_preview(self):
        from wakfu_server.temporary_recycling import recycle

        self.state.recycle = recycle
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.state.result = self.state.recycle(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.saved = self.state.result["character"]
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.character = (
                    self.active_private_session().refresh(
                        self.state.character, self.state.saved
                    )
                    if self.active_private_session() is not None
                    and self.active_private_session().owns(self.state.character)
                    else self.state.saved
                )
            for self.state.packet in self.state.result["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.record(
                event="temporary_inventory_recycled",
                actor_id=self.state.saved["id"],
                applied=self.state.result["applied"],
            )
        except ValueError as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
            self.runtime.record(
                event="temporary_inventory_recycling_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_recycle(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.recycling import recycle

        self.state.recycle = recycle
        from wakfu_server.inventory_move import (
            synchronization,
            reload_inventory,
        )

        self.state.synchronization = synchronization
        self.state.reload_inventory = reload_inventory
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.state.result = self.state.recycle(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                fight=self.state.fight,
            )
            self.state.saved = self.state.result["character"]
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.character = (
                    self.active_private_session().refresh(
                        self.state.character, self.state.saved
                    )
                    if self.active_private_session() is not None
                    and self.active_private_session().owns(self.state.character)
                    else self.state.saved
                )
                self.state.saved = self.state.character
            # The UID-only request may target a loaded owned hero.
            # Preserve the selected main and publish the actual owner.
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.synchronization(self.state.saved),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.equipment_inventory(self.state.saved),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.result["packets"][-1],
            )
            self.runtime.record(
                event="inventory_recycled",
                actor_id=self.state.saved["id"],
                applied=self.state.result["applied"],
            )
        except (
            ValueError,
            UnicodeError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
        ) as error:
            from wakfu_server.player_action_feedback import failure_message

            self.state.failure_message = failure_message

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.failure_message("recycling", error)),
            )
            self.runtime.record(
                event="inventory_recycling_rejected",
                actor_id=self.state.character["id"],
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_item_upgrade(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server import exchange_machine
        from wakfu_server.inventory_move import synchronization

        self.state.synchronization = synchronization
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.state.request = exchange_machine.decode(self.state.body)
            self.runtime.POSITIONS.flush(
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
            )
            self.state.station = exchange_machine.station(
                self.state.character, self.state.request
            )
            self.state.result = exchange_machine.purchase(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                location=self.state.character,
                station=self.state.station,
                blocked=self.environment_blocked(),
            )
            self.state.saved = self.state.result["character"]
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.character = self.refresh_owned_character(self.state.saved)
                self.state.saved = self.state.character
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.synchronization(self.state.saved),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.equipment_inventory(self.state.saved),
            )
            for self.state.packet in self.state.result["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.record(
                event="exchange_machine_purchased",
                **self.state.request,
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
                    "Esta respuesta aún no está disponible."
                    if isinstance(
                        error, self.state.npc_dialogue.UnavailableDialogueChoice
                    )
                    else (
                        str(error)
                        if isinstance(error, ValueError)
                        else "Exchange purchase is temporarily unavailable."
                    )
                ),
            )
            self.runtime.record(
                event="exchange_machine_purchase_rejected",
                actor_id=self.state.character["id"],
                reason=(
                    str(error)
                    if isinstance(error, ValueError)
                    else type(error).__name__
                ),
            )
        return DispatchResult.FALLTHROUGH

    def handle_inventory_action(self):
        from wakfu_server.inventory_actions import destroy
        from wakfu_server.inventory_move import (
            synchronization,
            reload_inventory,
        )

        self.state.synchronization = synchronization
        self.state.reload_inventory = reload_inventory

        try:
            self.state.result = destroy(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.saved = self.state.result["character"]
            if self.state.saved["id"] == self.state.character["id"]:
                self.state.character = self.refresh_owned_character(self.state.saved)
                self.state.saved = self.state.character
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
                event="inventory_item_destroyed", actor_id=self.state.saved["id"]
            )
            from wakfu_server.inventory_items import equipment_inventory

            self.state.equipment_inventory = equipment_inventory

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.equipment_inventory(self.state.saved),
            )
        except ValueError as error:
            self.state.character = self.state.reload_inventory(
                self.runtime.STORE, self.state.account_id, self.state.character
            )
            self.state.message_id, self.state.message_body = self.state.synchronization(
                self.state.character
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                self.state.message_id,
                self.state.message_body,
            )
            self.runtime.record(
                event="inventory_destroy_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_equipment_action(self):
        from wakfu_server.inventory_move import (
            transfer,
            synchronization,
            reload_inventory,
        )

        self.state.synchronization = synchronization
        self.state.reload_inventory = reload_inventory

        try:
            self.state.result = transfer(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.saved = self.state.result["character"]
            self.state.character = (
                self.active_private_session().refresh(
                    self.state.character, self.state.saved
                )
                if self.active_private_session() is not None
                and self.active_private_session().owns(self.state.character)
                else self.state.saved
            )
            self.runtime.record(
                event="inventory_item_moved", actor_id=self.state.character["id"]
            )
            from wakfu_server.inventory_items import equipment_inventory

            self.state.equipment_inventory = equipment_inventory

            for owner_id in self.state.result.get(
                "affected_characters", (self.state.character["id"],)
            ):
                self.state.owner = (
                    self.state.character
                    if owner_id == self.state.character["id"]
                    else self.runtime.STORE.character(self.state.account_id, owner_id)
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.equipment_inventory(self.state.owner),
                )
        except ValueError as error:
            from wakfu_server.ecology_feedback import information

            self.state.information = information
            from wakfu_server.player_action_feedback import failure_message

            self.state.failure_message = failure_message

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    self.state.failure_message("inventory_move", error)
                ),
            )
            self.state.character = self.state.reload_inventory(
                self.runtime.STORE, self.state.account_id, self.state.character
            )
            self.state.message_id, self.state.message_body = self.state.synchronization(
                self.state.character
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                self.state.message_id,
                self.state.message_body,
            )
            from wakfu_server import (
                heroes,
                hero_wire,
                hero_private_scene,
            )

            self.state.heroes = heroes
            self.state.hero_wire = hero_wire
            self.state.hero_private_scene = hero_private_scene
            from wakfu_server.inventory_items import equipment_inventory

            self.state.equipment_inventory = equipment_inventory

            with self.runtime.STORE.connection() as self.state.db:
                self.state.roster = self.state.heroes.load_roster(
                    self.state.db,
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character["id"],
                )
            self.state.roster = self.state.hero_private_scene.project(
                self.state.roster,
                self.active_private_session(),
                self.state.character,
                self.state.generation,
            )
            for hero in self.state.roster["heroes"]:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.hero_wire.refresh(
                        self.runtime.OWNED_HERO_TEMPLATE, hero
                    ),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.equipment_inventory(hero),
                )
            self.runtime.record(
                event="inventory_move_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_build_view(self):
        from wakfu_server import world_shortcuts

        try:
            self.state.saved = world_shortcuts.apply(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
        except (ValueError, UnicodeError) as error:
            self.runtime.record(
                event="world_shortcuts_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        else:
            self.state.character = (
                self.active_private_session().refresh(
                    self.state.character, self.state.saved
                )
                if self.active_private_session() is not None
                and self.active_private_session().owns(self.state.character)
                else self.state.saved
            )
            self.runtime.record(
                event="world_shortcuts_saved", actor_id=self.state.character["id"]
            )
        return DispatchResult.FALLTHROUGH

    def handle_build_select(self):
        self.state.previous_mount_character = self.state.character
        self.state.index = self.state.character["active_build_index"]
        try:
            (
                self.state.requested_actor,
                self.state.index,
            ) = self.runtime.builds.decode_deletion(self.state.body)
            if self.state.requested_actor != self.state.character["id"]:
                raise ValueError("Build deletion belongs to another character")
            self.state.saved = self.runtime.STORE.delete_build(
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.index,
                in_fight=self.state.fight is not None,
            )
            self.state.character = (
                self.active_private_session().refresh(
                    self.state.character, self.state.saved
                )
                if self.active_private_session() is not None
                and self.active_private_session().owns(self.state.character)
                else self.state.saved
            )
        except (ValueError, UnicodeError) as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.builds.deletion_message(
                    self.state.character["id"],
                    self.state.index,
                    failed=True,
                ),
            )
            self.runtime.record(
                event="build_deletion_rejected",
                actor_id=self.state.character["id"],
                build_index=self.state.index,
                reason=str(error),
            )
        else:
            # cEN removes the sheet and releases heroBuildLock first.
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.builds.deletion_message(
                    self.state.character["id"],
                    self.state.index,
                    failed=False,
                ),
            )
            if (
                self.state.index
                == self.state.previous_mount_character["active_build_index"]
            ):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.runtime.builds.selection_message(self.state.character),
                )
                self.publish_mount_equipment(
                    self.state.previous_mount_character, self.state.character
                )
                from wakfu_server.combat_lifecycle import (
                    outside_progression,
                )

                self.state.outside_progression = outside_progression

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.outside_progression(
                        self.state.character, wp=self.runtime.COMBAT_TEST_WP
                    ),
                )
            self.runtime.record(
                event="build_deleted",
                actor_id=self.state.character["id"],
                build_index=self.state.index,
                active_build_index=self.state.character["active_build_index"],
            )
        return DispatchResult.FALLTHROUGH

    def handle_build_reset(self):
        self.state.previous_mount_character = self.state.character
        try:
            (
                self.state.requested_actor,
                self.state.index,
            ) = self.runtime.builds.decode_activation(self.state.body)
            if self.state.requested_actor != self.state.character["id"]:
                raise ValueError("Build activation belongs to another character")
            self.state.saved = self.runtime.STORE.activate_build(
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.index,
                in_fight=self.state.fight is not None,
            )
            self.state.character = (
                self.active_private_session().refresh(
                    self.state.character, self.state.saved
                )
                if self.active_private_session() is not None
                and self.active_private_session().owns(self.state.character)
                else self.state.saved
            )
        except (ValueError, UnicodeError) as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.builds.selection_message(self.state.character),
            )
            self.runtime.record(
                event="build_activation_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        else:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.builds.selection_message(self.state.character),
            )
            self.publish_mount_equipment(
                self.state.previous_mount_character, self.state.character
            )
            from wakfu_server.combat_lifecycle import outside_progression

            self.state.outside_progression = outside_progression

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.outside_progression(
                    self.state.character, wp=self.runtime.COMBAT_TEST_WP
                ),
            )
            self.runtime.record(
                event="build_activated",
                actor_id=self.state.character["id"],
                build_index=self.state.index,
                revision=self.state.character["build_selection_revision"],
            )
        return DispatchResult.FALLTHROUGH

    def handle_build_save(self):
        self.state.previous_mount_character = self.state.character
        try:
            request_id, self.state.index, blobs = self.runtime.builds.decode(
                self.state.body
            )
            if request_id <= 0:
                raise ValueError("Invalid build character identity")
            if not self.runtime.builds.valid_index(self.state.index):
                raise ValueError("Invalid build index")
        except (ValueError, UnicodeError) as error:
            # A stale hero editor must not terminate the world session.
            from wakfu_server.ecology_feedback import information

            self.state.information = information
            from wakfu_server.player_action_feedback import failure_message

            self.state.failure_message = failure_message

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    self.state.failure_message("build_save", error)
                ),
            )
            self.runtime.record(
                event="build_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.builds.capacity_message(self.state.character),
            )
            messages = (
                [
                    (
                        12284,
                        self.runtime.builds.rejection_response(
                            self.state.character,
                            self.state.character["active_build_index"],
                            status=2,
                        ),
                    )
                ]
                if self.state.fight is not None
                else self.runtime.builds.rejection_messages(
                    self.state.character,
                    self.state.character["active_build_index"],
                    wp=self.runtime.COMBAT_TEST_WP,
                    status=2,
                )
            )
            for self.state.message_id, self.state.message_body in messages:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            return DispatchResult.CONTINUE
        build_character = self.state.character
        try:
            build_character = self.runtime.STORE.character(
                self.state.account_id, request_id
            )
            previous_build_character = build_character
            if (
                self.state.fight is not None
                and self.state.index == build_character["active_build_index"]
            ):
                raise self.runtime.builds.BuildOccupationError(
                    "Active build cannot be saved during combat"
                )
            self.runtime.record(
                event="persistence_stage",
                domain="build",
                stage="save_started",
                build_index=self.state.index,
                backend="postgresql",
            )
            self.state.saved = self.runtime.STORE.save_build(
                self.state.account_id,
                self.state.generation,
                request_id,
                self.state.index,
                blobs,
            )
            self.runtime.record(
                event="persistence_stage",
                domain="build",
                stage="postgresql_committed",
                build_index=self.state.index,
            )
            build_character = self.state.saved
            if request_id == self.state.character["id"]:
                self.state.character = (
                    self.active_private_session().refresh(
                        self.state.character, self.state.saved
                    )
                    if self.active_private_session() is not None
                    and self.active_private_session().owns(self.state.character)
                    else self.state.saved
                )
                build_character = self.state.character
        except (ValueError, UnicodeError) as error:
            self.state.reason = str(error)
            self.state.status = self.runtime.builds.rejection_status(error)
            from wakfu_server.ecology_feedback import information

            self.state.information = information
            from wakfu_server.player_action_feedback import failure_message

            self.state.failure_message = failure_message

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    self.state.failure_message("build_save", error)
                ),
            )
            self.state.saved = self.runtime.STORE.character(
                self.state.account_id, build_character["id"]
            )
            build_character = self.state.saved
            if request_id == self.state.character["id"]:
                self.state.character = (
                    self.active_private_session().refresh(
                        self.state.character, self.state.saved
                    )
                    if self.active_private_session() is not None
                    and self.active_private_session().owns(self.state.character)
                    else self.state.saved
                )
                build_character = self.state.character
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.builds.capacity_message(build_character),
            )
            messages = (
                self.runtime.builds.rejection_messages(
                    build_character,
                    self.state.index,
                    wp=self.runtime.COMBAT_TEST_WP,
                    status=self.state.status,
                )
                if request_id == self.state.character["id"] and self.state.fight is None
                else [
                    (
                        12284,
                        self.runtime.builds.rejection_response(
                            build_character, self.state.index, status=self.state.status
                        ),
                    )
                ]
            )
            for self.state.message_id, self.state.message_body in messages:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            self.runtime.record(
                event="build_rejected",
                actor_id=request_id,
                build_index=self.state.index,
                reason=str(error),
            )
        else:
            if previous_build_character.get("inventory_items") != build_character.get(
                "inventory_items"
            ):
                from wakfu_server.inventory_move import synchronization

                self.state.synchronization = synchronization
                from wakfu_server.inventory_items import equipment_inventory

                self.state.equipment_inventory = equipment_inventory

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.synchronization(build_character),
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.equipment_inventory(build_character),
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.builds.capacity_message(build_character),
            )
            if self.state.index != build_character["active_build_index"]:
                # cER acknowledges all sheet fields without replacing
                # the live actor's combat resources or selected gear.
                messages = [
                    (
                        12284,
                        self.runtime.builds.response(build_character, self.state.index),
                    )
                ]
            elif request_id == self.state.character["id"]:
                messages = self.runtime.builds.response_messages(
                    build_character, self.state.index, wp=self.runtime.COMBAT_TEST_WP
                )
            else:
                from wakfu_server import hero_wire

                self.state.hero_wire = hero_wire

                messages = [
                    (
                        12284,
                        self.runtime.builds.response(build_character, self.state.index),
                    ),
                    self.state.hero_wire.refresh(
                        self.runtime.OWNED_HERO_TEMPLATE, build_character
                    ),
                    self.state.hero_wire.statistics(build_character),
                ]
            for self.state.message_id, self.state.message_body in messages:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
            if self.state.index == build_character["active_build_index"]:
                self.publish_mount_equipment(previous_build_character, build_character)
            self.runtime.record(
                event="build_saved", actor_id=request_id, build_index=self.state.index
            )
        return DispatchResult.FALLTHROUGH

    def handle_companion_equipment(self):
        from wakfu_server import companion_equipment
        from wakfu_server.ecology_feedback import information

        self.state.information = information
        from psycopg import Error as CompanionDatabaseError

        self.state.CompanionDatabaseError = CompanionDatabaseError
        from psycopg_pool import PoolTimeout as CompanionPoolTimeout

        self.state.CompanionPoolTimeout = CompanionPoolTimeout

        companion_identity = None
        try:
            companion_identity = (
                companion_equipment.decode_save(self.state.body)[0]
                if self.state.opcode == 13191
                else companion_equipment.identity_request(self.state.body)
            )
            handler = {
                13191: companion_equipment.save,
                13345: companion_equipment.retrieve_all,
                12019: companion_equipment.unlink,
            }[self.state.opcode]
            handler_options = {}
            if self.state.opcode == 13191:
                from wakfu_server.combat_companion_owned_equipment_adapter import (
                    preflight_custody,
                )

                self.state.preflight_custody = preflight_custody

                # The command's locked Store snapshot and NPC row
                # are the only sources for this side-effect-free
                # factory preflight. The active Ready path repeats
                # it against the actual companion Actor and pin.
                handler_options["native_admission"] = (
                    lambda companion, owner, entries, level: self.state.preflight_custody(
                        owner, companion, entries, level
                    )
                )
            self.state.result = handler(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                in_fight=self.state.fight is not None
                or self.state.combat_session is not None,
                **handler_options,
            )
            self.state.saved = self.state.result["character"]
            self.state.character = dict(
                self.state.character,
                inventory_items=self.state.saved["inventory_items"],
                inventory_containers=self.state.saved["inventory_containers"],
            )
            for self.state.packet in self.state.result["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.refresh_party(self.state.generation, self.state.character)
            self.runtime.record(
                event="companion_inventory_action",
                actor_id=self.state.character["id"],
                companion_id=companion_identity,
                opcode=self.state.opcode,
            )
        except (
            ValueError,
            self.state.CompanionDatabaseError,
            self.state.CompanionPoolTimeout,
        ) as error:
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "No se pudo modificar el compañero"
            )
            if self.state.opcode in (13191, 13345) and companion_identity is not None:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *companion_equipment.response(companion_identity, error=True),
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="companion_inventory_action_rejected",
                actor_id=self.state.character["id"],
                companion_id=companion_identity,
                opcode=self.state.opcode,
                reason=self.state.text,
            )
        return DispatchResult.FALLTHROUGH

    def handle_companion_action(self):
        from wakfu_server import companions

        self.state.companions = companions
        from wakfu_server import hero_private_scene

        self.state.hero_private_scene = hero_private_scene
        from wakfu_server.ecology_feedback import information

        self.state.information = information
        from psycopg import Error as CompanionDatabaseError

        self.state.CompanionDatabaseError = CompanionDatabaseError
        from psycopg_pool import PoolTimeout as CompanionPoolTimeout

        self.state.CompanionPoolTimeout = CompanionPoolTimeout

        try:
            if self.state.fight is not None or self.state.combat_session is not None:
                raise ValueError("Companion roster cannot change during combat")
            self.state.hero_private_scene.authorize(
                self.active_private_session(),
                self.state.character,
                self.state.generation,
            )
            with self.runtime.PARTIES._guard(self.state.character["id"]):
                with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                    self.runtime.flush_positions(account_id=self.state.account_id)
                    self.state.companions.add_to_party(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                    )
                self.runtime.refresh_party(self.state.generation, self.state.character)
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.companions.added_result(),
            )
            self.runtime.record(
                event="companion_added", actor_id=self.state.character["id"]
            )
        except (
            ValueError,
            self.state.CompanionDatabaseError,
            self.state.CompanionPoolTimeout,
        ) as error:
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "No se pudo añadir el compañero"
            )
            self.state.result = (
                14
                if "combat" in self.state.text
                else (
                    11
                    if "full" in self.state.text
                    else 13 if "Dead" in self.state.text else 15
                )
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.companions.added_result(self.state.result),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="companion_add_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.text,
            )
        return DispatchResult.FALLTHROUGH

    def handle_companion_view(self):
        from wakfu_server import heroes, hero_wire

        self.state.heroes = heroes
        self.state.hero_wire = hero_wire
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            if self.state.fight is not None or self.state.combat_session is not None:
                raise ValueError("Hero roster cannot change during combat")
            self.state.target = self.state.hero_wire.add_request(self.state.body)
            from wakfu_server import hero_private_scene

            self.state.hero_private_scene = hero_private_scene

            self.state.hero_private_scene.authorize(
                self.active_private_session(),
                self.state.character,
                self.state.generation,
            )
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                self.state.roster = self.state.heroes.add(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.target,
                )
            self.publish_heroes(self.state.roster)
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.hero_wire.added_success(),
            )
            self.runtime.record(
                event="hero_added",
                actor_id=self.state.character["id"],
                hero_id=self.state.target,
            )
        except ValueError as error:
            self.state.text = str(error)
            self.state.result = (
                14
                if "combat" in self.state.text
                else (
                    11
                    if "full" in self.state.text
                    else 13 if "Dead" in self.state.text else 15
                )
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.hero_wire.added_result(self.state.result),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="hero_add_rejected",
                actor_id=self.state.character["id"],
                reason=self.state.text,
            )
        return DispatchResult.FALLTHROUGH

    def handle_hero_switch(self):
        from wakfu_server import heroes, hero_wire

        self.state.heroes = heroes
        self.state.hero_wire = hero_wire
        from wakfu_server.ecology_feedback import information

        self.state.information = information
        from wakfu_server.player_action_feedback import failure_message

        self.state.failure_message = failure_message
        from wakfu_server.position_buffer import PositionOwnerBusy

        self.state.PositionOwnerBusy = PositionOwnerBusy

        switch_target = None
        try:
            switch_target = self.state.hero_wire.switch_request(self.state.body)
            if self.state.hero_switch_pending is not None:
                raise ValueError("A native hero switch is already pending")
            if self.state.fight is not None or self.state.combat_session is not None:
                raise ValueError("Native hero switching is unavailable during combat")
            if self.state.training_transit_active:
                raise ValueError(
                    "Finish or leave the current Rii training before switching the company leader"
                )
            self.state.target = switch_target
            private_session = self.active_private_session()
            if private_session is not None and not private_session.owns(
                self.state.character
            ):
                raise ValueError(
                    "Hero switch requires the current private scene session"
                )
            if self.state.npc_dialogue_session is not None:
                self.state.npc_dialogue_session.close()
                self.state.npc_dialogue_session = None
            previous_character = self.state.character
            self.runtime.PLANTINGS.cancel(
                self.state.character["id"], self.state.generation
            )
            self.runtime.HARVESTS.cancel(
                self.state.character["id"], generation=self.state.generation
            )
            self.cancel_flora()
            self.cancel_crafting()
            if self.state.chest_opening is not None:
                from wakfu_server.haven_chest_wire import (
                    close_packet as close_chest,
                )

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *close_chest(self.state.character["id"]),
                )
            self.state.chest_opening = None
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                self.state.roster = self.state.heroes.switch_main(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.target,
                )
                previous_character_id = self.state.character["id"]
                self.runtime.WORLD.leave(previous_character_id, self.state.generation)
                self.runtime.POSITIONS.release(
                    self.state.account_id, self.state.generation, previous_character_id
                )
                self.state.character = self.state.roster["leader"]
                self.runtime.POSITIONS.attach(
                    self.state.account_id, self.state.generation, self.state.character
                )
                if private_session is not None:
                    self.state.character = private_session.rebind(
                        previous_character, self.state.character
                    )
            self.state.position = {
                key: self.state.character[key] for key in ("x", "y", "z")
            }
            self.state.movement_state = self.runtime.Movement(self.state.position)
            # cwE must hand off the native master before the full
            # owned component refresh. An open class dialog still
            # resolves the old master until its csF completion.
            self.state.hero_switch_pending = self.state.character["id"]
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.hero_wire.switched_result(self.state.character["id"]),
            )
            self.runtime.record(
                event="hero_main_switch_pending",
                actor_id=self.state.character["id"],
                previous_id=previous_character_id,
            )
        except (ValueError, self.state.PositionOwnerBusy) as error:
            if switch_target is not None:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.hero_wire.switched_result(
                        switch_target,
                        (
                            2
                            if self.state.fight is not None
                            or self.state.combat_session is not None
                            else 6
                        ),
                    ),
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    self.state.failure_message("hero_switch", error)
                ),
            )
            self.runtime.record(
                event="hero_switch_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_hero_roster(self):
        from wakfu_server import hero_wire

        self.state.hero_wire = hero_wire
        from wakfu_server.ecology_feedback import information

        self.state.information = information
        from wakfu_server.player_action_feedback import failure_message

        self.state.failure_message = failure_message

        try:
            self.state.target = self.state.hero_wire.switch_request(self.state.body)
            if self.state.hero_switch_pending is None:
                if self.state.target != self.state.character["id"]:
                    raise ValueError(
                        "Native hero switch completion has no pending target"
                    )
                return DispatchResult.CONTINUE
            if (
                self.state.target != self.state.hero_switch_pending
                or self.state.target != self.state.character["id"]
            ):
                raise ValueError(
                    "Native hero switch completion targets another character"
                )
            if not self.runtime.STORE.current_character_session(
                self.state.account_id, self.state.generation, self.state.target
            ):
                raise ValueError(
                    "Native hero switch completion belongs to a replaced session"
                )
            if self.runtime.is_dungeon_run(self.state.character.get("instance_id", 0)):
                from wakfu_server import dungeon_context

                self.state.dungeon_context = dungeon_context

                # The same native scene now belongs to the new main.
                # Publish its actual context under that actor's scope
                # before later combat admission consumes the receipt.
                with self.runtime.STORE.connection() as self.state.db:
                    fighting = self.state.db.execute(
                        "SELECT EXISTS(SELECT 1 FROM combat_fights f "
                        "JOIN dungeon_room_encounters e ON e.fight_id=f.id "
                        "WHERE e.instance_id=%s AND e.status='active' "
                        "AND f.status IN ('placement','active')) AS fighting",
                        (self.state.character["instance_id"],),
                    ).fetchone()["fighting"]
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.dungeon_context.update_packet(
                        self.runtime.STORE,
                        self.state.character["instance_id"],
                        fight_in_progress=fighting,
                    ),
                )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.hero_wire.refresh(
                    self.runtime.OWNED_HERO_TEMPLATE, self.state.character
                ),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.hero_wire.statistics(self.state.character),
            )
            # The native post-swap cinematic waits for the selected
            # actor's format22 GUILD_LOCAL_INFO consumer, even when
            # the character has no guild. Format10 lacks this section.
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
            from wakfu_server.private_scene_heroes import (
                messages as private_hero_messages,
            )

            for self.state.packet in private_hero_messages(
                self.active_private_session(),
                self.state.character,
                generation=self.state.generation,
            ):
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.join_world(
                self.state.generation,
                self.state.connection,
                self.state.character,
                hydrate_heroes=False,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.runtime.rich_inventory_packet(self.state.character),
            )
            from wakfu_server.inventory_move import synchronization

            self.state.synchronization = synchronization

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.synchronization(self.state.character),
            )
            self.state.hero_switch_pending = None
            self.publish_custom_task_cards()
            self.runtime.record(
                event="hero_main_switched", actor_id=self.state.character["id"]
            )
        except ValueError as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    self.state.failure_message("hero_switch", error)
                ),
            )
            self.runtime.record(
                event="hero_switch_completion_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        else:
            self.deliver_custom_task_rewards()
        return DispatchResult.FALLTHROUGH

    def handle_cosmetic(self):
        from wakfu_server.cosmetics import (
            OwnedCosmetics,
            actor_update,
        )

        try:
            previous_cosmetic_character = self.state.character
            self.state.saved = self.runtime.STORE.equip_owned_finishers(
                self.state.account_id,
                self.state.character["id"],
                self.state.opcode,
                self.state.body,
            )
            self.state.character = (
                dict(
                    self.state.character,
                    owned_cosmetics=self.state.saved["owned_cosmetics"],
                )
                if self.state.fight is not None
                else (
                    self.active_private_session().refresh(
                        self.state.character, self.state.saved
                    )
                    if self.active_private_session() is not None
                    and self.active_private_session().owns(self.state.character)
                    else self.state.saved
                )
            )
            cosmetics = OwnedCosmetics.from_record(
                self.state.character["owned_cosmetics"],
                account_id=self.state.account_id,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                13873,
                struct.pack(">II", 2, 8)
                + cosmetics.inventory_component()
                + struct.pack(">I", 9)
                + cosmetics.preset_component(),
            )
            # Combat keeps its actor/resource snapshots; publish appearance on return.
            if self.state.fight is None:
                cosmetic_opcode, cosmetic_body = actor_update(self.state.character)
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    cosmetic_opcode,
                    cosmetic_body,
                )
                self.runtime.WORLD.update(
                    self.state.generation,
                    self.state.character,
                    cosmetic_opcode,
                    cosmetic_body,
                    include_sender=False,
                )
                self.publish_mount_equipment(
                    previous_cosmetic_character, self.state.character
                )
            self.runtime.record(
                event="owned_finishers_selected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
        except ValueError as error:
            self.runtime.record(
                event="owned_finishers_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH
