"""Ecology operations for one lease-bound World session."""

import itertools
import struct
import time
from .dispatch_result import DispatchResult


class EcologySessionMixin:
    def cancel_artifact_action(self, reason):
        if self.state.pending_artifact_action is not None:
            self.runtime.record(
                event="exploration_artifact_cancelled",
                actor_id=self.state.pending_artifact_action["owner"][2],
                reason=reason,
            )
            self.state.pending_artifact_action = None

    def artifact_owner_identity(self, owner):
        return (
            self.state.account_id,
            self.state.generation,
            owner["id"],
            owner["map_id"],
            owner.get("instance_id", 0),
            owner["x"],
            owner["y"],
            owner["z"],
        )

    def artifact_failure_message(self, error):
        messages = {
            "hammer_unavailable": "El martillo todavía no puede despejar estas rocas.",
            "position": "Acércate al punto de uso del artefacto.",
        }
        return messages.get(
            getattr(error, "public_code", None),
            "No se pudo usar el artefacto. Inténtalo de nuevo.",
        )

    def artifact_position_allowed(self, owner):
        """Bind zero-mask native branches to accepted owned movement only."""
        if owner["map_id"] != self.state.character["map_id"] or owner.get(
            "instance_id", 0
        ) != self.state.character.get("instance_id", 0):
            return False
        current = tuple(owner[key] for key in ("x", "y", "z"))
        approved = tuple(self.state.movement_state.approved)
        return (
            current in approved
            if approved
            else current == tuple(self.state.character[key] for key in ("x", "y", "z"))
        )

    def admit_artifact_action(self, route, request_body, owner):
        """Publish admitted native scripts and retain only a delayed transition."""
        for visual in route.get("script_packets", ()):
            if visual["broadcast"]:
                self.runtime.WORLD.broadcast(
                    self.state.generation, owner["id"], *visual["packet"]
                )
            else:
                self.runtime.send(
                    self.state.connection, self.state.service, *visual["packet"]
                )
        delay_ms = route["delay_ms"]
        if delay_ms == 0:
            return False
        self.state.pending_artifact_action = dict(
            owner=self.artifact_owner_identity(owner),
            body=bytes(request_body),
            route=route,
            due_at=time.monotonic() + delay_ms / 1000,
        )
        self.runtime.record(
            event="exploration_artifact_waiting",
            actor_id=owner["id"],
            object_id=route["interactive_element_id"],
            delay_ms=delay_ms,
        )
        return True

    def complete_artifact_action(self):
        """Revalidate delayed native travel on idle without blocking the reader."""
        pending = self.state.pending_artifact_action
        if pending is None:
            return
        if (
            not self.state.loaded
            or self.state.character is None
            or self.artifact_owner_identity(self.state.character) != pending["owner"]
            or self.environment_blocked()
            or self.state.environment_ticket is not None
        ):
            self.cancel_artifact_action("Owner, source or occupation changed")
            return
        if time.monotonic() < pending["due_at"]:
            return
        from wakfu_server import exploration_artifact_actions, teleporter_approach
        from wakfu_server.position_buffer import PositionOwnerBusy

        try:
            if not self.runtime.STORE.current_character_session(
                self.state.account_id, self.state.generation, self.state.character["id"]
            ):
                raise ValueError("Exploration action session expired")
            self.runtime.flush_positions(
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
            )
            route = pending["route"]
            saved = exploration_artifact_actions.transition(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                pending["body"],
                expected_plan=route,
                source_allowed=teleporter_approach.callback(
                    self.state.movement_state,
                    map_id=self.state.character["map_id"],
                    instance_id=self.state.character.get("instance_id", 0),
                ),
                position_allowed=self.artifact_position_allowed,
                blocked=self.environment_blocked(),
            )
        except PositionOwnerBusy:
            return
        except ValueError as error:
            self.cancel_artifact_action(str(error))
            from wakfu_server.ecology_feedback import information

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *information(self.artifact_failure_message(error)),
            )
            return
        self.state.pending_artifact_action = None
        self.publish_public_transport(route, saved, generic_route=True)

    def cancel_environment(self, *, publish=True):
        self.cancel_artifact_action("Environment action cancelled")
        if self.state.paid_container_ticket is not None:
            from wakfu_server.paid_containers import cancel

            result = cancel(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.paid_container_ticket,
            )
            self.state.paid_container_ticket = None
            if publish:
                for packet in result["packets"]:
                    if result.get("personal_state", False):
                        self.runtime.send(
                            self.state.connection, self.state.service, *packet
                        )
                    else:
                        self.runtime.WORLD.emit_location(*result["location"], *packet)
                self.publish_environment_scene(force=True)
        if self.state.environment_ticket is not None:
            from wakfu_server.environment_interactions import cancel

            cancel(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.environment_ticket["character_id"],
            )
            self.state.environment_ticket = None
        if self.state.environment_seat is not None:
            from wakfu_server.environment_seats import release

            occupied = self.state.environment_seat
            result = release(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                occupied["character_id"],
            )
            self.state.environment_seat = None
            if publish:
                for packet in result["packets"]:
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
                self.publish_environment_scene(force=True)

    def environment_actor_is_hero(self):
        from wakfu_server.heroes import ensure_company_party

        roster = ensure_company_party(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
        )
        if roster["leader"]["id"] == self.state.character["id"]:
            return False
        if any(hero["id"] == self.state.character["id"] for hero in roster["heroes"]):
            return True
        raise ValueError("Environment actor is outside the owned company")

    def environment_blocked(
        self, *, allow_seated=False, allow_paid=False, allow_source=False
    ):
        if (
            self.state.fight is not None
            or (
                getattr(self.state, "quest_source_ticket", None) is not None
                and not allow_source
            )
            or self.state.combat_session is not None
            or self.state.spectator_session is not None
            or self.state.bag_session is not None
            or self.state.flora_ticket is not None
            or (self.state.paid_container_ticket is not None and not allow_paid)
            or (self.state.environment_seat is not None and not allow_seated)
        ):
            return True
        with self.runtime.PLANTINGS.lock:
            planting = self.state.character["id"] in self.runtime.PLANTINGS.pending
        with self.runtime.HARVESTS.lock:
            harvesting = self.state.character["id"] in self.runtime.HARVESTS.pending
        if planting or harvesting:
            return True
        from wakfu_server.crafting import current

        return (
            current(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
            is not None
        )

    def publish_environment_scene(self, *, force=False):
        import itertools

        if (
            not self.state.loaded
            or self.state.character is None
            or self.state.fight is not None
            or self.state.combat_session is not None
            or self.state.spectator_session is not None
            or self.state.character.get("instance_id", 0) != 0
        ):
            return
        now = time.monotonic()
        if not force and now - self.state.last_environment_refresh < 1:
            return
        from wakfu_server.environment_interactions import snapshots
        from wakfu_server.world_scene_sync import chunk, neighborhood

        selected = neighborhood(chunk(self.state.character))
        nearby = {
            row["id"]
            for row in self.runtime.world_static.objects(self.state.character["map_id"])
            if chunk((row["x"], row["y"])) in selected
        }
        identity = (
            self.state.character["map_id"],
            self.state.character.get("instance_id", 0),
            chunk(self.state.character),
        )
        previous = (
            self.state.environment_scene_states
            if self.state.environment_scene_identity == identity
            else {}
        )
        current = {}
        from wakfu_server.environment_seats import snapshots as seat_snapshots

        from wakfu_server.environment_doors import snapshots as door_snapshots
        from wakfu_server.treasure_chests import snapshots as treasure_snapshots
        from wakfu_server.paid_containers import snapshots as paid_container_snapshots

        for packet in itertools.chain(
            snapshots(self.runtime.STORE, self.state.character["map_id"]),
            seat_snapshots(self.runtime.STORE, self.state.character["map_id"]),
            door_snapshots(
                self.runtime.STORE,
                self.state.character["map_id"],
                self.state.character.get("instance_id", 0),
                nearby,
            ),
            treasure_snapshots(
                self.runtime.STORE,
                self.state.account_id,
                self.state.character["map_id"],
                character_id=self.state.character["id"],
            ),
            paid_container_snapshots(
                self.runtime.STORE,
                self.state.character["map_id"],
                self.state.character.get("instance_id", 0),
            ),
        ):
            object_id = struct.unpack_from(">q", packet[1])[0]
            if object_id not in nearby:
                continue
            if force or previous.get(object_id) != packet:
                self.runtime.send(self.state.connection, self.state.service, *packet)
            current[object_id] = packet
        self.state.environment_scene_identity, self.state.environment_scene_states = (
            identity,
            current,
        )
        self.state.last_environment_refresh = now

    def complete_environment_occupation(self):
        if self.state.environment_ticket is None:
            return
        if (
            not self.state.loaded
            or self.state.character is None
            or self.environment_blocked()
            or any(
                self.state.character.get(key) != self.state.environment_ticket[key]
                for key in ("map_id", "x", "y", "z")
            )
        ):
            self.cancel_environment()
            return
        if self.runtime.STORE.now() < self.state.environment_ticket["due_at"]:
            return
        from wakfu_server.environment_interactions import complete

        try:
            result = complete(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.environment_ticket["token"],
                location=self.state.character,
                is_hero=self.environment_actor_is_hero(),
            )
        except ValueError as error:
            self.cancel_environment()
            self.runtime.record(
                event="environment_occupation_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            return
        for packet in result["packets"]:
            self.runtime.send(self.state.connection, self.state.service, *packet)
        if result.get("character") is not None:
            saved = result["character"]
            self.state.character.update(
                {key: saved[key] for key in ("inventory_items", "inventory_containers")}
            )
        self.state.environment_ticket = None

    def publish_native_monster_destructions(self, location):
        """Retry committed removals; socket failure never reverses their receipt."""
        from wakfu_server.objectives.environmental_destroy_publication import publish

        try:
            return publish(
                self.runtime.STORE,
                self.runtime.WORLD,
                self.runtime.COMBAT_GROUPS,
                map_id=location["map_id"],
                instance_id=location["instance_id"],
                now_ms=int(self.runtime.STORE.now().timestamp() * 1000),
            )
        except OSError as error:
            self.runtime.record(
                event="environmental_monster_destroy_publication_pending",
                map_id=location["map_id"],
                instance_id=location["instance_id"],
                reason=type(error).__name__,
            )
            return 0

    def prepare_native_encounter_world_action(self, body):
        """Admit only an authored original NPC action; preserve other cnT uses."""
        from wakfu_server.combat_encounter_world_action_start import prepare
        from wakfu_server.ecology_feedback import information

        if type(body) is not bytes or len(body) != 16:
            return None
        target_id, action_id = struct.unpack(">qq", body)
        if target_id >= 0 or not self.state.character.get("instance_id"):
            return None
        try:
            current = self.runtime.owned_planting_character(
                self.state.character,
                self.runtime.WORLD,
                self.runtime.POSITIONS,
                store=self.runtime.STORE,
            )
            from copy import deepcopy

            with self.runtime.COMBAT_GROUPS.lock:
                try:
                    group = deepcopy(
                        self.runtime.combat_group_for_target(
                            self.runtime.COMBAT_GROUPS, current, target_id
                        )
                    )
                except ValueError:
                    return None
            # Read SQL and native source outside the registry lock. The common
            # combat path revalidates and claims this exact group afterward.
            if current.get("map_id") == 1361:
                from wakfu_server.achievements import incarnam_encounters

                with self.runtime.STORE.connection() as tutorial_db:
                    result = incarnam_encounters.prepare(
                        tutorial_db, current, body, group
                    )
            else:
                result = prepare(self.runtime.STORE, current, body, group)
            if result is not None and not self.runtime.STORE.current_character_session(
                self.state.account_id, self.state.generation, current["id"]
            ):
                raise ValueError("Native encounter action has a stale selected session")
            return result
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.record(
                event="native_encounter_world_action_rejected",
                actor_id=self.state.character["id"],
                target_id=target_id,
                action_id=action_id,
                reason=str(error),
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *information(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Native encounter interaction is temporarily unavailable."
                ),
            )
            return False

    def publish_incarnam_combat_guides(self, actor_id, action):
        guides = getattr(self.state.connection, "incarnam_combat_guides", None)
        if (
            guides is None
            and self.state.fight is not None
            and self.state.character.get("map_id") == 1361
        ):
            from wakfu_server.achievements import incarnam_encounters

            with self.runtime.STORE.connection() as tutorial_db:
                guides = incarnam_encounters.recover_guides(
                    tutorial_db, self.state.character, self.state.fight
                )
            self.state.connection.incarnam_combat_guides = guides
        if guides is not None and self.state.fight is not None:
            from wakfu_server.achievements import tutorial_presentation_once

            guide_packets = guides.observe(self.state.fight, actor_id, action)
            if guide_packets:
                with self.runtime.STORE.connection() as tutorial_db:
                    guide_packets = tutorial_presentation_once.filter_packets(
                        tutorial_db, self.state.character["id"], guide_packets
                    )
            for guide_packet in guide_packets:
                self.runtime.send(
                    self.state.connection, self.state.service, *guide_packet
                )

    def publish_rii_lesson_guide(self, node_id, choice_id):
        """Queue presentation until its owned placement survives scene bootstrap."""
        from wakfu_server.achievements import rii_lesson_presentation

        if rii_lesson_presentation.begin(node_id, choice_id) is not None:
            self.state.pending_rii_lesson_guide = (node_id, choice_id)

    def publish_admitted_rii_lesson_guide(self):
        if self.state.pending_rii_lesson_guide is None:
            return
        from wakfu_server.achievements import (
            rii_lesson_presentation,
        )

        try:
            with self.runtime.STORE.connection() as tutorial_db:
                packets = rii_lesson_presentation.claim_admission(
                    tutorial_db,
                    self.state.fight,
                    self.state.character["id"],
                    *self.state.pending_rii_lesson_guide,
                )
        except ValueError as error:
            # A rejected lesson request must not decorate a later encounter.
            self.state.pending_rii_lesson_guide = None
            self.runtime.record(
                event="rii_lesson_guide_admission_rejected", reason=str(error)
            )
            return
        for guide_packet in packets:
            self.runtime.send(self.state.connection, self.state.service, *guide_packet)
        self.state.pending_rii_lesson_guide = None

    def try_native_monster_destroy(self, body):
        """Handle only durable event-owned targets; leave NPC cnT requests alone."""
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.ecology_feedback import information

        if type(body) is not bytes or len(body) != 16:
            return False
        target_id, action_id = struct.unpack(">qq", body)
        try:
            current = self.runtime.owned_planting_character(
                self.state.character,
                self.runtime.WORLD,
                self.runtime.POSITIONS,
                store=self.runtime.STORE,
            )

            def reachable(owner, monster):
                source = tuple(owner[key] for key in ("x", "y", "z"))
                target = tuple(monster[key] for key in ("x", "y", "z"))
                return any(
                    tuple(a) == source and tuple(b) == target
                    for a, b in map_geometry(owner["map_id"])["edges"]
                )

            with self.runtime.COMBAT_GROUPS.lock:
                with self.runtime.STORE.connection() as db:
                    owned = db.execute(
                        "SELECT 1 FROM environmental_owned_groups g "
                        "JOIN environmental_owned_group_members m USING(instance_id,group_ordinal) "
                        "WHERE g.map_id=%s AND g.world_instance_id=%s AND m.monster_id=%s",
                        (current["map_id"], current["instance_id"], target_id),
                    ).fetchone()
                    if owned is None:
                        return False
                    from wakfu_server.objectives import environmental_monster_actions
                    from wakfu_server.objectives import environmental_monster_destroy
                    from wakfu_server.objectives.environmental_gameplay import (
                        committed_monster_destroy,
                    )

                    environmental_monster_actions.decode_request(body)
                    now_ms = int(self.runtime.STORE.now().timestamp() * 1000)
                    receipt = environmental_monster_destroy.commit(
                        self.runtime.STORE,
                        db,
                        self.state.account_id,
                        self.state.generation,
                        current,
                        body,
                        groups=self.runtime.COMBAT_GROUPS,
                        reachable=reachable,
                        loaded=self.state.loaded,
                        blocked=(
                            self.state.fight is not None
                            or self.state.combat_session is not None
                            or self.state.spectator_session is not None
                            or self.state.hero_switch_pending is not None
                            or self.state.bag_session is not None
                            or self.state.ranch_session is not None
                        ),
                        location_context=lambda stored: self.runtime.owned_planting_character(
                            stored,
                            self.runtime.WORLD,
                            self.runtime.POSITIONS,
                            store=self.runtime.STORE,
                        ),
                        now_ms=now_ms,
                    )
                    if not receipt["replayed"]:
                        committed_monster_destroy(db, receipt)
            self.publish_native_monster_destructions(receipt)
            self.poll_environmental_events()
            self.runtime.record(
                event="environmental_monster_destroyed",
                actor_id=receipt["character_id"],
                monster_id=receipt["monster_id"],
                action_id=receipt["action_id"],
                replayed=receipt["replayed"],
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.record(
                event="environmental_monster_destroy_rejected",
                actor_id=self.state.character["id"],
                target_id=target_id,
                action_id=action_id,
                reason=type(error).__name__,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *information(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Native monster destruction is temporarily unavailable."
                ),
            )
        return True

    def cancel_flora(self):
        self.state.flora_retry_body = None
        self.cancel_environment()
        if self.state.flora_ticket is not None:
            from wakfu_server.resource_collect import cancel

            cancel(self.runtime.STORE, self.state.flora_ticket)
            self.state.flora_ticket = None

    def complete_flora_occupation(self, body):
        from wakfu_server.resource_collect import (
            complete,
            acknowledge_publication,
            HarvestNotReady,
        )

        if self.state.flora_ticket is None:
            return
        try:
            if self.state.fight is not None:
                raise ValueError("La cosecha requiere estar fuera del combate")

            def resume_dungeon_resource_group(db, instance_id):
                from wakfu_server import dungeon_runtime
                from wakfu_server.combat_terrain import map_geometry

                return dungeon_runtime.ensure_current_room(
                    db,
                    self.runtime.COMBAT_GROUPS,
                    instance_id,
                    map_geometry(self.state.character["map_id"]),
                )

            with self.runtime.PLANTINGS.publisher_lock:
                result = complete(
                    self.runtime.STORE,
                    self.state.flora_ticket,
                    body,
                    location_context=lambda stored: self.runtime.owned_planting_character(
                        stored,
                        self.runtime.WORLD,
                        self.runtime.POSITIONS,
                        store=self.runtime.STORE,
                    ),
                    on_dungeon_unlocked=resume_dungeon_resource_group,
                )
                for message_id, payload in result["world_packets"]:
                    self.runtime.WORLD.emit_location(
                        result["map_id"], result["instance_id"], message_id, payload
                    )
                acknowledge_publication(self.runtime.STORE, result)
                dungeon_group = result.get("dungeon_group")
                if dungeon_group is not None and not dungeon_group.get("replay", False):
                    self.runtime.WORLD.emit_location(
                        result["map_id"],
                        result["instance_id"],
                        12608,
                        self.runtime.owned_scene_spawn_group(
                            dungeon_group["members"], group_id=dungeon_group["group_id"]
                        ),
                    )
            self.state.flora_ticket = None
            self.state.flora_retry_body = None
            if result["applied"]:
                saved = self.runtime.STORE.character(
                    self.state.account_id, self.state.character["id"]
                )
                self.state.character = (
                    self.active_private_session().refresh(self.state.character, saved)
                    if self.active_private_session() is not None
                    else saved
                )
            for message_id, payload in result["packets"]:
                if message_id == 13574:
                    self.runtime.WORLD.update(
                        self.state.generation,
                        self.state.character,
                        message_id,
                        payload,
                        include_sender=False,
                    )
            self.runtime.send_batch(
                self.state.connection, self.state.service, result["packets"]
            )
            if result["applied"]:
                self.runtime.send_native_planting_bonus(
                    self.state.connection, self.state.character
                )
            self.runtime.record(
                event="resource_harvest_completed",
                actor_id=self.state.character["id"],
                applied=result["applied"],
                ecology=result.get("outcome", {}).get("ecology", {}).get("reason"),
            )
        except HarvestNotReady:
            # Keep the owned operation; the idle poll finishes it at its deadline.
            self.state.flora_retry_body = body
        except ValueError as error:
            self.cancel_flora()
            self.runtime.record(
                event="resource_harvest_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.ecology_feedback import information
            from wakfu_server.player_action_feedback import failure_message

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *information(failure_message("harvest", error)),
            )

    def handle_resource_collect(self):
        from wakfu_server.resource_collect import (
            prepare,
            reserve,
            start_packet,
        )
        from wakfu_server.combat_terrain import map_geometry

        self.state.map_geometry = map_geometry

        try:
            if self.state.fight is not None:
                raise ValueError("Sal del combate para recolectar")
            self.cancel_flora()

            def reachable_flora(current, resource):
                from wakfu_server.resource_domains import (
                    is_mineral,
                    is_fish,
                )

                if is_mineral(resource["resource_reference"]):
                    from wakfu_server.mining_navigation import reachable

                    return reachable(current, resource)
                if is_fish(resource["resource_reference"]):
                    from wakfu_server.fishing_navigation import reachable

                    return reachable(current, resource)
                from wakfu_server.haven_bag_garden import is_private_garden

                if is_private_garden(current):
                    from wakfu_server.haven_bag_garden import reachable

                    return reachable(current, resource)
                source = tuple(current[k] for k in ("x", "y", "z"))
                destination = tuple(resource[k] for k in ("x", "y", "z"))
                return any(
                    tuple(a) == source and tuple(b) == destination
                    for a, b in self.state.map_geometry(current["map_id"])["edges"]
                )

            prepared = prepare(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
                reachable=reachable_flora,
                location_context=lambda stored: self.runtime.owned_planting_character(
                    stored,
                    self.runtime.WORLD,
                    self.runtime.POSITIONS,
                    store=self.runtime.STORE,
                ),
            )
            self.runtime.PLANTINGS.cancel(
                self.state.character["id"], self.state.generation
            )
            self.runtime.HARVESTS.cancel(
                self.state.character["id"], generation=self.state.generation
            )
            self.state.flora_ticket = reserve(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                prepared,
                location_context=lambda stored: self.runtime.owned_planting_character(
                    stored,
                    self.runtime.WORLD,
                    self.runtime.POSITIONS,
                    store=self.runtime.STORE,
                ),
            )
            self.runtime.WORLD.emit_location(
                prepared["character"]["map_id"],
                prepared["character"]["instance_id"],
                *start_packet(
                    prepared["character"],
                    prepared["resource"],
                    dict(
                        prepared["rule"],
                        duration_ms=self.state.flora_ticket["duration_ms"],
                    ),
                ),
            )
            self.runtime.record(
                event="resource_harvest_started",
                actor_id=self.state.character["id"],
                resource_uid=self.state.flora_ticket["resource_uid"],
                action_id=self.state.flora_ticket["action_id"],
            )
        except ValueError as error:
            self.cancel_flora()
            self.runtime.record(
                event="resource_harvest_rejected",
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
                *self.state.information(self.state.failure_message("harvest", error)),
            )
        return DispatchResult.FALLTHROUGH

    def handle_resource_complete(self):
        self.complete_flora_occupation(self.state.body)
        return DispatchResult.FALLTHROUGH

    def handle_monster_collect(self):
        self.runtime.PLANTINGS.cancel(self.state.character["id"], self.state.generation)
        from wakfu_server.monster_collect import (
            decode_request,
            action,
            Regenerating,
            availability_packet,
        )

        self.state.decode_request = decode_request
        self.state.action = action
        from wakfu_server.profession_store import level as profession_level

        self.state.profession_level = profession_level
        from wakfu_server.combat_terrain import map_geometry

        self.state.map_geometry = map_geometry

        try:
            if self.state.fight is not None or (
                self.state.bag_session is not None and self.state.ranch_session is None
            ):
                raise ValueError(
                    "La recolección requiere estar fuera del combate y del merkasaco"
                )
            if self.state.ranch_session is not None:
                self.state.ranch_session.validate_lease(self.state.generation)
            self.state.request = self.state.decode_request(self.state.body)
            with self.runtime.COMBAT_GROUPS.lock:
                self.state.monster = self.runtime.harvest_target(
                    self.state.character, self.state.request["monster_id"]
                )
                rule = self.state.action(
                    self.state.monster["ref"], self.state.request["action_id"]
                )
                self.state.source = tuple(
                    self.state.character[k] for k in ("x", "y", "z")
                )
                self.state.target = tuple(
                    self.state.monster[k] for k in ("x", "y", "z")
                )
                reachable = any(
                    tuple(a) == self.state.source and tuple(b) == self.state.target
                    for a, b in self.state.map_geometry(self.state.character["map_id"])[
                        "edges"
                    ]
                )
                self.state.packet = self.runtime.HARVESTS.begin(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    self.state.monster,
                    profession_level=self.state.profession_level(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        rule["profession_id"],
                    ),
                    reachable=reachable,
                    location_context=self.refresh_owned_character,
                )
            self.runtime.send(
                self.state.connection, self.state.service, *self.state.packet
            )
            self.runtime.record(
                event="monster_harvest_started",
                actor_id=self.state.character["id"],
                monster_id=self.state.monster["id"],
                action_id=rule["action_id"],
            )
        except Regenerating as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *availability_packet(
                    error.monster_id,
                    error.action_id,
                    False,
                ),
            )
            self.runtime.record(
                event="monster_harvest_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
                monster_id=error.monster_id,
                action_id=error.action_id,
            )
        except ValueError as error:
            self.runtime.record(
                event="monster_harvest_rejected",
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

    def handle_harvest_complete(self):
        from wakfu_server.profession_store import level as profession_level

        self.state.profession_level = profession_level
        from wakfu_server.inventory_items import equipment_inventory

        self.state.equipment_inventory = equipment_inventory

        try:
            if (
                len(self.state.body) == 3
                and struct.unpack(">Bh", self.state.body)[1] == 2
            ):
                with self.runtime.POSITIONS.account_barrier(
                    self.state.account_id
                ), self.runtime.COMBAT_GROUPS.lock:
                    self.state.result = self.runtime.PLANTINGS.complete(
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.body,
                    )
                private_packets = []
                for self.state.message_id, self.state.payload in self.state.result[
                    "packets"
                ]:
                    if self.state.message_id == 13135:
                        self.runtime.send_batch(
                            self.state.connection, self.state.service, private_packets
                        )
                        private_packets.clear()
                        self.runtime.WORLD.emit_location(
                            self.state.character["map_id"],
                            self.state.character["instance_id"],
                            self.state.message_id,
                            self.state.payload,
                        )
                    else:
                        if self.state.message_id == 13574:
                            self.runtime.WORLD.update(
                                self.state.generation,
                                self.state.result["character"],
                                self.state.message_id,
                                self.state.payload,
                                include_sender=False,
                            )
                        private_packets.append(
                            (self.state.message_id, self.state.payload)
                        )
                self.runtime.send_batch(
                    self.state.connection, self.state.service, private_packets
                )
                if self.state.result["applied"]:
                    self.state.saved = self.runtime.STORE.character(
                        self.state.account_id, self.state.character["id"]
                    )
                    self.state.character = self.runtime.owned_planting_character(
                        self.state.saved,
                        self.runtime.WORLD,
                        self.runtime.POSITIONS,
                        store=self.runtime.STORE,
                        generation=self.state.generation,
                    )
                    self.runtime.send_planting_context(
                        self.state.connection, self.state.character
                    )
                custom_tasks = self.state.result.get("custom_task_update") or {}
                if custom_tasks.get("updated"):
                    self.deliver_custom_task_rewards()
                    self.state.custom_task_cards.changed(
                        self.state.character["id"], (self.state.character["id"],)
                    )
                    self.publish_custom_task_cards()
                self.runtime.record(
                    event="planting_completed",
                    actor_id=self.state.character["id"],
                    applied=self.state.result["applied"],
                    success=self.state.result.get("success"),
                    probability=self.state.result.get("probability"),
                    ecology=self.state.result.get("ecology", {}).get("reason"),
                )
                return DispatchResult.CONTINUE
            with self.runtime.COMBAT_GROUPS.lock, self.runtime.HARVESTS.lock:
                self.state.ticket = self.runtime.HARVESTS.pending.get(
                    self.state.character["id"]
                )
                if self.state.ticket is None:
                    return DispatchResult.CONTINUE
                self.state.monster = self.runtime.harvest_target(
                    self.state.character, self.state.ticket["monster_id"]
                )
                self.state.result = self.runtime.HARVESTS.complete(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    monster=self.state.monster,
                    location_context=self.refresh_owned_character,
                    profession_level=self.state.profession_level(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.ticket["rule"]["profession_id"],
                    ),
                )
            if (
                self.state.result["applied"]
                and self.state.result.get("availability") is not None
            ):
                (
                    self.state.map_id,
                    self.state.instance_id,
                    self.state.packet,
                ) = self.state.result["availability"]
                self.runtime.WORLD.emit_location(
                    self.state.map_id, self.state.instance_id, *self.state.packet
                )
            self.runtime.send_batch(
                self.state.connection, self.state.service, self.state.result["packets"]
            )
            if self.state.result["applied"]:
                self.state.character = self.refresh_owned_character(
                    self.runtime.STORE.character(
                        self.state.account_id, self.state.character["id"]
                    )
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.equipment_inventory(self.state.character),
                )
                self.runtime.send_native_planting_bonus(
                    self.state.connection, self.state.character
                )
            self.runtime.record(
                event="monster_harvest_completed",
                actor_id=self.state.character["id"],
                applied=self.state.result["applied"],
            )
        except ValueError as error:
            self.runtime.PLANTINGS.cancel(
                self.state.character["id"], self.state.generation
            )
            self.runtime.HARVESTS.cancel(
                self.state.character["id"], generation=self.state.generation
            )
            self.runtime.record(
                event="monster_harvest_rejected",
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

    def handle_monster_destroy(self):
        pass
        return DispatchResult.FALLTHROUGH
