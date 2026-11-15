"""Travel operations for one lease-bound World session."""

import struct
import time
from wakfu_server.performance_profiler import PROFILER
from .dispatch_result import DispatchResult


class TravelSessionMixin:
    def handle_rii_zaap_scene(self):
        from wakfu_server import rii_zaap_scene

        try:
            if self.environment_blocked():
                raise ValueError("Finish the current action before entering the portal")
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                result = rii_zaap_scene.begin(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                    approved_positions=tuple(
                        getattr(self.state.movement_state, "approved", ())
                    ),
                )
                if result["started"]:
                    self.state.character = result["character"]
                    self.runtime.POSITIONS.attach(
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                    )
                    self.state.position = {
                        key: self.state.character[key] for key in ("x", "y", "z")
                    }
                    self.state.movement_state = self.runtime.Movement(
                        self.state.position
                    )
                    self.state.connection.pending_rii_zaap_scene = self.state.character[
                        "id"
                    ]
                    self.runtime.WORLD.update(
                        self.state.generation,
                        self.state.character,
                        *result["packets"][0],
                        include_sender=False,
                    )
                    self.runtime.send_batch(
                        self.state.connection, self.state.service, result["packets"]
                    )
        except ValueError as error:
            self.runtime.record(event="rii_zaap_scene_rejected", reason=str(error))
        return DispatchResult.CONTINUE

    def handle_astrub_house_exit(self):
        from wakfu_server import astrub_house_exit

        try:
            if self.environment_blocked():
                raise ValueError("Finish the current action before leaving the house")
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                result = astrub_house_exit.begin(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.body,
                    approved_positions=tuple(
                        getattr(self.state.movement_state, "approved", ())
                    ),
                )
                self.publish_public_transport(
                    result["route"],
                    result["character"],
                    generic_route=True,
                    before_bootstrap=lambda: self.publish_settled_quest_packets(
                        result["packets"]
                    ),
                )
        except ValueError as error:
            self.runtime.record(event="astrub_house_exit_rejected", reason=str(error))
        return DispatchResult.CONTINUE

    def activate_world_phoenix(self, body):
        from wakfu_server.phoenix_points import activate

        if (
            self.active_private_session() is not None
            or self.state.spectator_session is not None
        ):
            raise ValueError("Activa el fénix desde su mapa público")
        live = dict(self.state.character, **self.state.position)
        result = activate(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            body,
            in_fight=self.state.fight is not None
            or self.state.combat_session is not None,
            location=live,
        )
        self.state.character = dict(
            result["character"],
            **{
                key: live[key]
                for key in ("map_id", "instance_id", "x", "y", "z", "direction")
            },
        )
        self.runtime.WORLD.refresh_projection(
            self.state.generation, self.state.character
        )
        # Original bDB already sets the owned point and displays soulLinked
        # before12870. Persist without reconstructing the actor or its effects.
        self.runtime.record(
            event="phoenix_bound",
            actor_id=self.state.character["id"],
            phoenix_id=result["saved_phoenix_id"],
            changed=result["applied"],
        )

    def request_world_respawn(self, body):
        from wakfu_server.world_respawn import request

        if (
            self.state.fight is not None
            or self.state.combat_session is not None
            or self.state.pending_combat_return is not None
            or self.state.pending_terminal_world_recovery is not None
            or self.state.publication_recovery_shared is not None
            or self.state.hero_switch_pending is not None
            or self.active_private_session() is not None
            or self.state.spectator_session is not None
            or self.runtime.COMBAT_SESSIONS.lookup_character(self.state.character["id"])
            is not None
        ):
            raise ValueError("Completa el regreso al mundo antes de volver al fénix")
        source = dict(self.state.character, **self.state.position)

        def live():
            identity = self.runtime.WORLD.live_identity(
                character_id=self.state.character["id"]
            )
            return bool(
                identity is not None
                and identity[0] == self.state.generation
                and identity[1]["account_id"] == self.state.account_id
                and all(
                    identity[1][key] == source[key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                )
            )

        result = request(
            self.runtime.STORE,
            self.runtime.POSITIONS,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            body,
            source=source,
            validate_live=live,
        )
        self.runtime.record(
            event="world_respawn_committed",
            actor_id=self.state.character["id"],
            replayed=result["replayed"],
            policy=result["destination"]["world_respawn"]["policy"],
        )
        return self.deliver_rift_transition()

    def prepare_world_respawn_delivery(self, destination, saved, *, attach=None):
        from wakfu_server.world_respawn import release_position, publication
        from wakfu_server.position_buffer import (
            PositionBaselineChanged,
            PositionOwnerBusy,
        )
        from wakfu_server.position_redis import PositionJournalError

        metadata = destination.get("world_respawn")
        if metadata is None:
            if attach is not None:
                attach()
            return True
        if time.monotonic() < self.state.world_respawn_retry_at:
            return False
        try:
            with self.runtime.POSITIONS.account_barrier(
                self.state.account_id, blocking=False
            ):
                if not metadata["position_released"]:
                    release_position(
                        self.runtime.STORE,
                        self.runtime.POSITIONS,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        destination,
                    )
                    metadata["position_released"] = True
                # Keep completed position release truthful across retries, but
                # do not publish native resurrection before attachment succeeds.
                if attach is not None:
                    attach()
                if not metadata["occupation_published"]:
                    self.runtime.send_batch(
                        self.state.connection, self.state.service, publication(saved)
                    )
                    metadata["occupation_published"] = True
        except (
            PositionBaselineChanged,
            PositionOwnerBusy,
            PositionJournalError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
        ) as error:
            self.state.world_respawn_retry_at = time.monotonic() + 0.25
            self.runtime.record(
                event="world_respawn_delivery_pending",
                actor_id=self.state.character["id"],
                error_type=type(error).__name__,
            )
            return False
        self.state.world_respawn_retry_at = 0.0
        return True

    def resurrect_world_character(self, body):
        from contextlib import ExitStack
        from wakfu_server.world_resurrection import resurrect

        if not isinstance(body, bytes) or len(body) != 8:
            raise ValueError("Invalid native BenKO target packet")
        target_id = struct.unpack(">q", body)[0]
        if (
            target_id <= 0
            or self.state.fight is not None
            or self.state.combat_session is not None
        ):
            raise ValueError("BenKO requires an exploration target")
        with self.runtime.STORE.connection() as db:
            row = db.execute(
                "SELECT c.account_id,s.character_id AS leader_id FROM characters c "
                "JOIN sessions s ON s.account_id=c.account_id "
                "WHERE c.id=%s AND c.deleted_at IS NULL AND s.expires_at>%s",
                (target_id, self.runtime.STORE.now()),
            ).fetchone()
        if row is None:
            raise ValueError("Resurrection target is not connected")
        with ExitStack() as barriers:
            for owner in sorted({self.state.account_id, row["account_id"]}):
                barriers.enter_context(
                    self.runtime.POSITIONS.account_barrier(owner, blocking=False)
                )
            # Account barriers fence position I/O. Each registry lookup captures
            # the Rust owner's current lease without a global Python World lock.
            source_entry = self.runtime.WORLD.players.get(self.state.character["id"])
            target_entry = self.runtime.WORLD.players.get(row["leader_id"])
            if (
                source_entry is None
                or source_entry[0] != self.state.generation
                or target_entry is None
                or target_entry[2]["account_id"] != row["account_id"]
            ):
                raise ValueError("Resurrection target left the world")
            target_generation = target_entry[0]
            target_leader = dict(target_entry[2])
            live = {
                target_id: dict(target_leader, generation=target_generation),
                self.state.character["id"]: dict(
                    self.state.character,
                    **self.state.position,
                    generation=self.state.generation,
                ),
            }
            result = resurrect(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                body,
                target_generation=target_generation,
                live_locations=live,
            )
            for packet in result["donor_packets"]:
                self.runtime.send(self.state.connection, self.state.service, *packet)
            target = result["target"]
            if result["donor"]["id"] == self.state.character["id"]:
                updated = self.refresh_owned_character(result["donor"])
                self.state.character = dict(
                    updated,
                    **{
                        key: self.state.character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                    },
                )
            if target_id == self.state.character["id"]:
                self.state.character = dict(
                    target,
                    **{
                        key: self.state.character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                    },
                )
            current_target = self.runtime.WORLD.players.get(target_leader["id"])
            if current_target is not None and current_target[0] == target_generation:
                for packet in result["target_packets"]:
                    self.runtime.WORLD.send_to(
                        target_leader["id"], target_generation, *packet
                    )
                if target_id == target_leader["id"]:
                    target = dict(
                        target,
                        **{
                            key: current_target[2][key]
                            for key in (
                                "map_id",
                                "instance_id",
                                "x",
                                "y",
                                "z",
                                "direction",
                            )
                        },
                    )
                    for packet in result["world_packets"]:
                        self.runtime.WORLD.update(target_generation, target, *packet)
                else:
                    for packet in result["world_packets"]:
                        self.runtime.WORLD.broadcast(
                            target_generation, target_leader["id"], *packet
                        )
            self.runtime.record(
                event="world_character_resurrected",
                actor_id=self.state.character["id"],
                target_id=target_id,
                donor_id=result["donor"]["id"],
                hp=target["hp"],
            )

    def publish_haven_world_travel(self, outcome):
        from wakfu_server.haven_world_travel import acknowledge

        self.cancel_crafting()
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        self.state.character = outcome["character"]
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
        if not acknowledge(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            outcome["transition"]["token"],
        ):
            self.deliver_rift_transition()
        self.runtime.record(
            event="haven_world_travel",
            actor_id=self.state.character["id"],
            kind=outcome["transition"]["kind"],
        )

    def use_inventory_teleport(self, body):
        from wakfu_server import item_teleports

        if item_teleports.action_class(body) is None:
            return False
        private = self.active_private_session()
        if private is not None and not private.owns(self.state.character):
            raise ValueError("El traslado requiere la sesión privada actual")
        physical = None
        if private is not None:
            physical = self.runtime.STORE.character(
                self.state.account_id, self.state.character["id"]
            )
        outcome = item_teleports.use(
            self.runtime.STORE,
            self.runtime.POSITIONS,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            body,
            in_fight=self.state.fight is not None
            or self.state.combat_session is not None,
            physical_source=physical,
            native_map_id=self.runtime.native_item_world_identity(self.state.character),
        )
        for packet in outcome["packets"]:
            self.runtime.send(self.state.connection, self.state.service, *packet)
        # SQL movement and debit have committed. Private capabilities and native
        # scene publication retire only after that owned transaction succeeds.
        leaving_ranch = self.state.ranch_session is not None
        leaving_bag = self.state.bag_session is not None
        if private is not None:
            self.cancel_private_scene_activity()
            if self.state.bag_session is not None:
                exterior = self.runtime.HAVEN_BAG_EXTERIORS.discard(
                    self.state.generation, self.state.bag_session.exterior_actor_id
                )
                if exterior is not None:
                    outside, packet = exterior
                    self.runtime.WORLD.emit_location(
                        outside["map_id"], outside["instance_id"], *packet
                    )
            if self.state.ranch_session is not None:
                self.state.ranch_session.leave(self.state.character)
            self.state.bag_session = self.state.ranch_session = None
        else:
            self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        self.state.character = outcome["character"]
        self.runtime.POSITIONS.attach(
            self.state.account_id, self.state.generation, self.state.character
        )
        self.state.position = {
            key: self.state.character[key] for key in ("x", "y", "z")
        }
        self.state.movement_state = self.runtime.Movement(self.state.position)
        bootstrap = (
            self.runtime.owned_haven_leave(
                self.runtime.fixture(13974), self.state.character
            )
            if leaving_bag
            else self.runtime.owned_native_bootstrap(self.state.character)
        )
        for opcode, payload in bootstrap:
            if leaving_ranch and opcode == 13019:
                continue
            self.runtime.send(
                self.state.connection, self.state.service, opcode, payload
            )
        self.runtime.join_world(
            self.state.generation, self.state.connection, self.state.character
        )
        self.mark_static_sync_pending()
        if not item_teleports.acknowledge(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            outcome["transition"]["token"],
        ):
            self.deliver_rift_transition()
        self.runtime.record(
            event="inventory_item_teleported",
            actor_id=self.state.character["id"],
            native_class=outcome["native_class"],
            consumed=outcome["consumed"],
        )
        return True

    def native_exterior_rift_request(self):
        """Recognize the same real exterior request at both combat guards."""
        if (
            self.state.opcode != 12870
            or not self.state.loaded
            or self.state.character is None
            or self.state.account_id is None
            or self.state.generation is None
            or len(self.state.body) != 12
            or struct.unpack_from(">H", self.state.body, 8)[0] != 11
        ):
            return False
        from wakfu_server.rift_entry_recovery import matches_loaded_source

        try:
            return matches_loaded_source(
                self.runtime.STORE,
                self.runtime.WORLD,
                self.runtime.POSITIONS,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
        except ValueError:
            return False

    def deliver_rift_transition(self):
        if (
            not self.state.loaded
            or self.state.character is None
            or self.state.account_id is None
            or self.state.generation is None
        ):
            return False
        self.consume_rift_entry_combat_retirement()
        if self.state.fight is not None or self.state.combat_session is not None:
            return False
        from wakfu_server import rift_transition_delivery
        from wakfu_server.position_buffer import (
            PositionBaselineChanged,
            PositionOwnerBusy,
        )

        if (
            rift_transition_delivery.pending(
                self.state.account_id, self.state.generation, self.state.character["id"]
            )
            is None
        ):
            return False
        try:
            # Match native entry/exit account-to-position lock order. The wakeup
            # is a delivery hint; the current selected lease and storage own it.
            with self.runtime.POSITIONS.account_barrier(
                self.state.account_id, blocking=False
            ):
                destination = rift_transition_delivery.pending(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
                if destination is None:
                    return False
                if not self.runtime.STORE.current_character_session(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                ):
                    raise ValueError("Rift transition belongs to a replaced session")
                saved = self.runtime.STORE.character(
                    self.state.account_id, self.state.character["id"]
                )
                wakeup = destination
                if destination.get("refresh_current_owned_position") is True:
                    if self.runtime.POSITIONS.has_dirty(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.character["id"],
                    ):
                        return False
                    destination = {
                        key: saved[key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                    }
                if any(
                    saved[key] != destination[key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ):
                    self.runtime.record(
                        event="rift_map_transition_pending",
                        actor_id=self.state.character["id"],
                        reason="committed_destination_changed",
                    )
                    return False
                if "world_respawn" in destination:
                    if not self.prepare_world_respawn_delivery(
                        destination,
                        saved,
                        attach=lambda: self.runtime.POSITIONS.attach(
                            self.state.account_id, self.state.generation, saved
                        ),
                    ):
                        return False
                else:
                    self.runtime.POSITIONS.attach(
                        self.state.account_id, self.state.generation, saved
                    )
        except (PositionBaselineChanged, PositionOwnerBusy) as error:
            self.runtime.record(
                event="rift_map_transition_pending",
                actor_id=self.state.character["id"],
                reason=type(error).__name__,
            )
            return False
        self.cancel_crafting()
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        self.state.character = saved
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
        rift_transition_delivery.acknowledge(
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            wakeup,
        )
        self.runtime.record(
            event="rift_map_transition",
            actor_id=self.state.character["id"],
            **destination,
        )
        return True

    def publish_public_transport(
        self, destination_route, saved, *, generic_route, before_bootstrap=None
    ):
        """Publish one committed native public transition through its usual path."""
        self.cancel_crafting()
        self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
        prior_inventory = self.state.character
        self.state.character = saved
        self.runtime.POSITIONS.attach(
            self.state.account_id, self.state.generation, self.state.character
        )
        self.state.position = {
            key: self.state.character[key] for key in ("x", "y", "z")
        }
        self.state.movement_state = self.runtime.Movement(self.state.position)
        if before_bootstrap is not None:
            # Earned XP deltas precede the final absolute snapshot; the position
            # lease already reflects the committed destination if delivery fails.
            before_bootstrap()
        messages = (
            self.runtime.owned_native_bootstrap(
                self.state.character, direction=destination_route["direction"]
            )
            if generic_route
            else self.runtime.transports.bootstrap(
                self.state.character, destination_route
            )
        )
        for message_id, message_body in messages:
            self.runtime.send(
                self.state.connection, self.state.service, message_id, message_body
            )
        if destination_route.get("item_payment") is not None:
            self.publish_entry_inventory(prior_inventory)
        # Publish heavy dynamic entities once, after map-ready.
        self.runtime.join_world(
            self.state.generation,
            self.state.connection,
            self.state.character,
            defer_scene_snapshot=self.state.character["map_id"] != 9,
        )
        self.mark_static_sync_pending()
        self.runtime.record(
            event="map_transition",
            actor_id=self.state.character["id"],
            map_id=self.state.character["map_id"],
            position=self.state.position,
        )

    def queue_committed_travel_resume(self, saved, complete, action_id):
        """Retry only post-commit attachment; payment and travel never replay."""
        from psycopg.errors import LockNotAvailable
        from wakfu_server.position_buffer import PositionOwnerBusy
        from wakfu_server.position_lifecycle import PendingPositionReturn

        if self.state.pending_travel_resume is not None:
            raise ValueError("A committed travel is already awaiting attachment")
        scope = (self.state.account_id, self.state.generation, saved["id"])

        def attach():
            if scope != (
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            ):
                raise ValueError("Committed travel selection changed before attachment")
            try:
                self.runtime.POSITIONS.attach(*scope[:2], saved)
            except LockNotAvailable as error:
                # The failed attachment transaction has already unwound.
                raise PositionOwnerBusy(
                    "Committed travel position is contended"
                ) from error

        self.state.pending_travel_resume = dict(
            retry=PendingPositionReturn(now=time.monotonic()),
            attach=attach,
            complete=complete,
            actor_id=saved["id"],
            action_id=str(action_id),
            started_at=time.monotonic(),
            held_requests=0,
        )

    def continue_committed_travel(self):
        """Run after valid session health and before further World publication."""
        if self.state.pending_travel_resume is None:
            return False
        pending = self.state.pending_travel_resume
        completed = pending["retry"].attempt(
            now=time.monotonic(),
            flush=pending["attach"],
            complete=pending["complete"],
            busy=lambda error, attempt: (
                self.runtime.record(
                    event="travel_position_resume_pending",
                    actor_id=pending["actor_id"],
                    action_id=pending["action_id"],
                    attempt=attempt,
                    pending_seconds=round(time.monotonic() - pending["started_at"], 3),
                    reason=self.runtime.redact(str(error)),
                )
                if attempt == 1 or attempt % 30 == 0
                else None
            ),
        )
        if completed:
            self.state.pending_travel_resume = None
        return True

    def committed_travel_holds_request(self, opcode):
        """Keep native ping/clock traffic while the durable scene resumes."""
        if self.state.pending_travel_resume is None or opcode in (314, 23354):
            return False
        pending = self.state.pending_travel_resume
        pending["held_requests"] += 1
        if pending["held_requests"] == 1 or pending["held_requests"] % 100 == 0:
            self.runtime.record(
                event="travel_position_request_held",
                actor_id=pending["actor_id"],
                action_id=pending["action_id"],
                opcode=opcode,
                held_requests=pending["held_requests"],
            )
        return True

    def execute_objectives_travel(
        self,
        action,
        *,
        resolve_destination=None,
        related_accounts=(),
        defer_receipt=False
    ):
        """Resolve curated public arrivals again and commit receipt with travel."""
        from wakfu_server.custom_tasks import player_actions
        from wakfu_server.objectives import player_travel
        from wakfu_server.ecology_feedback import information
        from contextlib import ExitStack

        try:
            if (
                self.state.pending_travel_resume is not None
                or self.state.bag_session is not None
                or self.state.ranch_session is not None
                or self.state.character.get("instance_id", 0)
            ):
                raise ValueError(
                    "Leave your private instance before using adventures travel."
                )
            accounts = sorted(set((self.state.account_id, *related_accounts)))
            with ExitStack() as barriers:
                for owner_id in accounts:
                    barriers.enter_context(
                        self.runtime.POSITIONS.account_barrier(owner_id)
                    )
                    self.runtime.flush_positions(account_id=owner_id)
                with self.runtime.STORE.connection() as db:
                    db.execute(
                        "SELECT id FROM accounts WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                        (accounts,),
                    )
                    self.runtime.STORE.lock_character(
                        db,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        selected=True,
                    )
                    player_actions.lock_running(db, action)
                    if (
                        db.execute(
                            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                            "WHERE p.character_id=%s AND f.status IN ('placement','active') "
                            "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE w.fight_id=p.fight_id "
                            "AND w.character_id=p.character_id) LIMIT 1",
                            (self.state.character["id"],),
                        ).fetchone()
                        is not None
                    ):
                        raise ValueError(
                            "Finish your current combat before travelling."
                        )
                    cost = 0
                    if resolve_destination is None:
                        spec = player_travel.resolve(db, action, action["action_key"])
                        destination, cost = spec["target"], spec["cost_kamas"]
                        if action["target"] != {
                            "kind": "travel",
                            "destination": destination,
                            "cost_kamas": cost,
                        }:
                            raise ValueError(
                                "This destination or price changed; refresh adventures before travelling."
                            )
                        remaining_kamas = player_actions.charge_travel(db, action, cost)
                    else:
                        destination = resolve_destination(db, action)
                    saved = self.runtime.STORE.transition_map_in_transaction(
                        db,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.character,
                        destination,
                    )
                    result = {
                        "success": True,
                        "message": "Travel completed.",
                        "map_id": saved["map_id"],
                        "instance_id": saved.get("instance_id", 0),
                        "cost_kamas": cost,
                    }
                    if defer_receipt:
                        db.execute(
                            "UPDATE objectives_player_actions SET status='pending' "
                            "WHERE id=%s AND status='running'",
                            (action["id"],),
                        )
                    elif not player_actions.finish(db, action, result):
                        raise ValueError("Adventures action is no longer executable.")
                    moved_ids = (self.state.character["id"],) + tuple(
                        row["character_id"]
                        for row in db.execute(
                            "SELECT character_id FROM account_hero_slots WHERE account_id=%s",
                            (self.state.account_id,),
                        ).fetchall()
                    )
                for member_id in moved_ids:
                    self.runtime.POSITIONS.release(
                        self.state.account_id, self.state.generation, member_id
                    )
            prior_inventory = self.state.character
            self.state.character = saved

            def publish_committed_travel():
                self.cancel_crafting()
                self.runtime.WORLD.leave(
                    self.state.character["id"], self.state.generation
                )
                self.state.position = {
                    key: self.state.character[key] for key in ("x", "y", "z")
                }
                self.state.movement_state = self.runtime.Movement(self.state.position)
                for packet in self.runtime.owned_native_bootstrap(self.state.character):
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
                self.runtime.join_world(
                    self.state.generation,
                    self.state.connection,
                    self.state.character,
                    defer_scene_snapshot=self.state.character["map_id"] != 9,
                )
                self.mark_static_sync_pending()
                if (
                    action["target"].get("kind") == "seasonal_entry"
                    and action["target"].get("route_kind") == "public"
                ):
                    self.publish_entry_inventory(prior_inventory)
                if cost:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        12753,
                        self.runtime.wire.account_kamas_update(remaining_kamas),
                    )

            self.queue_committed_travel_resume(
                saved, publish_committed_travel, action["id"]
            )
            return result
        except (ValueError, PermissionError) as error:
            self.runtime.send(
                self.state.connection, self.state.service, *information(str(error))
            )
            self.runtime.record(
                event="objectives_travel_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            return {"success": False, "error": str(error)}

    def execute_objectives_seasonal_entry(self, action):
        """Enter a reviewed native seasonal route with an atomic action receipt."""
        from wakfu_server.custom_tasks import player_actions
        from wakfu_server.objectives import seasonal_entry
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server import (
            dungeon_transport,
            dungeon_entry_access,
            teleporter_approach,
        )
        from wakfu_server.ecology_feedback import information

        try:
            if action["target"].get("route_kind") == "public":
                from wakfu_server import generic_transports
                from wakfu_server import seasonal_transport
                from wakfu_server.dungeon_entry_payment import consume

                def public_destination(db, queued):
                    target = seasonal_entry.resolve(db, queued)
                    actor = self.runtime.STORE.character(
                        self.state.account_id, self.state.character["id"], db
                    )
                    source = generic_transports.source(
                        target["entry_map_id"], target["source_id"]
                    )
                    native = next(
                        (
                            item
                            for item in (source or {}).get("destinations", ())
                            if item["destination_id"] == target["destination_id"]
                        ),
                        None,
                    )
                    if native is None or native["criterion"] != target["criterion"]:
                        raise ValueError(
                            "Seasonal island route changed; refresh Adventures."
                        )
                    resolved = generic_transports.resolve(
                        actor,
                        seasonal_entry.request(target),
                        source_allowed=teleporter_approach.callback(
                            self.state.movement_state,
                            map_id=target["entry_map_id"],
                            instance_id=0,
                        ),
                        criterion_evaluator=seasonal_transport.evaluator(
                            self.runtime.STORE, actor
                        ),
                        allow_item_payment=True,
                    )
                    if (
                        resolved["destination"]["map_id"]
                        != target["destination_map_id"]
                    ):
                        raise ValueError(
                            "Seasonal island route changed; refresh Adventures."
                        )
                    price = resolved.get("item_payment")
                    if price:
                        consume(
                            db,
                            (self.state.character["id"],),
                            price["reference"],
                            price["quantity"],
                        )
                    return resolved["destination"]

                return self.execute_objectives_travel(
                    action, resolve_destination=public_destination
                )
            if (
                self.state.bag_session is not None
                or self.state.ranch_session is not None
            ):
                raise ValueError(
                    "Leave your private instance before entering a dungeon."
                )
            with self.runtime.STORE.connection() as db:
                target = seasonal_entry.resolve(db, action)
            body = seasonal_entry.request(target)
            resolved = dungeon_transport.resolve_request(target["entry_map_id"], body)
            if resolved is None or (
                resolved["route"].key != target["route_key"]
                or resolved["route"].criterion != target["criterion"]
                or resolved["route"].start_map_id != target["destination_map_id"]
            ):
                raise ValueError("Seasonal dungeon route changed; refresh Adventures.")
            geometry = map_geometry(resolved["route"].start_map_id)

            def initialize(db, session):
                player_actions.lock_running(db, action)
                # Recheck the published route fence in the entry transaction.
                active = db.execute(
                    "SELECT revision FROM native_catalog_active WHERE id=1"
                ).fetchone()
                if active is None or active["revision"] != target["catalog_revision"]:
                    raise ValueError("Seasonal catalog changed; refresh Adventures.")
                if not player_actions.finish(
                    db,
                    action,
                    {
                        "success": True,
                        "message": "Dungeon entered.",
                        "instance_id": session["instance_id"],
                    },
                ):
                    raise ValueError("Adventures action is no longer executable.")
                self.state.dungeon_runtime.initialize_instance(
                    db,
                    session,
                    groups=self.runtime.COMBAT_GROUPS,
                    geometry=geometry,
                    store=self.runtime.STORE,
                )

            dungeon_transport.enter(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                target["entry_map_id"],
                body,
                criterion_allowed=lambda actor, criterion: dungeon_entry_access.evaluate(
                    self.runtime.STORE,
                    criterion,
                    character=actor,
                    destination_map_id=target["destination_map_id"],
                ),
                source_allowed=teleporter_approach.callback(
                    self.state.movement_state,
                    map_id=target["entry_map_id"],
                    instance_id=0,
                ),
                resolve_destination=self.state.dungeon_runtime.entry_destination,
                initialize_instance=initialize,
                positions=self.runtime.POSITIONS,
            )
            self.deliver_dungeon_transitions(before_action=True)
            return {"success": True, "message": "Dungeon entered."}
        except (ValueError, PermissionError) as error:
            self.runtime.send(
                self.state.connection, self.state.service, *information(str(error))
            )
            return {"success": False, "error": str(error)}

    def execute_objectives_pvp(self, action):
        """Meet selected opponents or observe the real event-bound native duel."""
        from wakfu_server.custom_tasks import player_actions
        from wakfu_server.objectives import pvp
        from wakfu_server.combat_terrain import map_geometry

        def destination(db, queued):
            current = pvp.resolve(db, queued, queued["action_key"])["target"]
            if current["event_id"] != queued["target"]["event_id"]:
                raise ValueError("Hourly PvP event changed.")
            if current["action"] == "meet":
                opponent = db.execute(
                    "SELECT c.* FROM sessions s JOIN characters c ON c.id=s.character_id "
                    "AND c.account_id=s.account_id WHERE s.account_id=%s AND s.character_id=%s "
                    "AND s.generation=%s AND s.expires_at>CURRENT_TIMESTAMP FOR UPDATE OF s,c",
                    (
                        current["opponent_account_id"],
                        current["opponent_character_id"],
                        current["opponent_generation"],
                    ),
                ).fetchone()
                if opponent is None:
                    raise ValueError("The PvP opponent is no longer available.")
                if (
                    db.execute(
                        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                        "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                        (opponent["id"],),
                    ).fetchone()
                    is not None
                ):
                    raise ValueError("The PvP opponent is currently fighting.")
            else:
                invitation = db.execute(
                    "SELECT map_id,instance_id,challenger_x AS x,challenger_y AS y,challenger_z AS z "
                    "FROM friendly_duel_invitations WHERE fight_id=%s AND status='accepted'",
                    (current["fight_id"],),
                ).fetchone()
                if invitation is None:
                    raise ValueError("The hourly PvP fight is no longer available.")
                opponent = invitation
            occupied = [
                tuple(row[key] for key in ("x", "y", "z"))
                for row in db.execute(
                    "SELECT c.x,c.y,c.z FROM sessions s JOIN characters c ON c.id=s.character_id "
                    "WHERE s.expires_at>CURRENT_TIMESTAMP AND c.map_id=%s AND c.instance_id=0",
                    (opponent["map_id"],),
                ).fetchall()
            ]
            return player_actions.nearby_public_floor(
                map_geometry(opponent["map_id"]), opponent, occupied=occupied
            )

        try:
            with self.runtime.STORE.connection() as db:
                current = pvp.resolve(db, action, action["action_key"])["target"]
            if current["action"] == "meet":
                return self.execute_objectives_travel(
                    action,
                    resolve_destination=destination,
                    related_accounts=(current["opponent_account_id"],),
                )
            if (
                self.state.character["map_id"],
                self.state.character.get("instance_id", 0),
            ) != (
                current["map_id"],
                current["instance_id"],
            ):
                return self.execute_objectives_travel(
                    action, resolve_destination=destination, defer_receipt=True
                )
            shared = self.runtime.COMBAT_SESSIONS.registry.lookup(current["fight_id"])
            if not self.public_objectives_duel(shared):
                raise ValueError("This fight is not a public hourly PvP challenge.")
            with self.runtime.STORE.connection() as db:
                player_actions.lock_running(db, action)
                pvp.resolve(db, action, action["action_key"])
                observer = self.spectator_session_for_current_character()
                if self.spectator_waiting_for_ack(shared):
                    db.execute(
                        "UPDATE objectives_player_actions SET status='pending' WHERE id=%s "
                        "AND status='running'",
                        (action["id"],),
                    )
                    return {
                        "success": True,
                        "message": "Waiting for the current native action.",
                    }
                with shared.lock:
                    self.publish_spectator_state(shared, force_snapshot=True)
                    delivery = self.runtime.SPECTATORS.enter(
                        observer,
                        current["fight_id"],
                        authorize=lambda _session, _fight_id: True,
                    )
                result = {
                    "success": True,
                    "message": "Watching hourly PvP.",
                    "fight_id": current["fight_id"],
                }
                if not player_actions.finish(db, action, result):
                    self.runtime.SPECTATORS.disconnect(observer)
                    raise ValueError("Adventures action is no longer executable.")
            self.state.spectator_session = observer
            self.state.spectator_fight_id = current["fight_id"]
            for packet in delivery.packets:
                self.runtime.send(self.state.connection, self.state.service, *packet)
            return result
        except (ValueError, PermissionError, KeyError) as error:
            return {"success": False, "error": str(error)}

    @PROFILER.profile("dungeon.transition")
    def publish_astrub_cat_story(self, result):
        """Publish one committed owned-story projection through shared state paths."""
        saved = result["character"]
        previous = self.state.character
        self.state.character = saved
        moved = any(
            previous.get(key) != saved.get(key)
            for key in ("map_id", "instance_id", "x", "y", "z")
        )
        if moved:
            self.state.position = {key: saved[key] for key in ("x", "y", "z")}
            self.state.movement_state = self.runtime.Movement(self.state.position)
            self.runtime.POSITIONS.attach(
                self.state.account_id, self.state.generation, saved
            )
            for packet in result["packets"]:
                if packet[0] in (13530, 13259):
                    self.runtime.WORLD.update(
                        self.state.generation, saved, *packet, include_sender=False
                    )
            self.mark_static_sync_pending()
        self.state.connection.pending_astrub_cat_story = result["pending_event"]
        self.state.connection.pending_astrub_cat_story_bootstrap = False
        self.publish_settled_quest_packets(result["packets"])

    def poll_astrub_cat_story(self):
        if self.state.character.get("map_id") != 312 or not self.runtime.is_dungeon_run(
            self.state.character.get("instance_id", 0)
        ):
            return None
        from wakfu_server.achievements import astrub_cat_story
        from wakfu_server import dungeon_runtime
        from wakfu_server.combat_terrain import map_geometry

        with self.runtime.COMBAT_GROUPS.lock, self.runtime.STORE.connection() as story_db:
            scope = astrub_cat_story.context(
                story_db, self.state.character, allow_finished=True
            )
            if scope is not None:
                dungeon_runtime.ensure_current_room(
                    story_db,
                    self.runtime.COMBAT_GROUPS,
                    self.state.character["instance_id"],
                    map_geometry(312),
                )
        with self.runtime.POSITIONS.account_barrier(self.state.account_id):
            self.runtime.flush_positions(account_id=self.state.account_id)
            result = astrub_cat_story.poll(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                pending_event=getattr(
                    self.state.connection, "pending_astrub_cat_story", None
                ),
                bootstrap=getattr(
                    self.state.connection, "pending_astrub_cat_story_bootstrap", False
                ),
            )
            if result is not None:
                self.publish_astrub_cat_story(result)
        return result

    def deliver_dungeon_transitions(self, *, before_action=False):
        """Poll this worker's durable transition without crossing combat/context.

        Prepare the authoritative destination and pinned context before any
        runtime mutation. Acknowledge only after complete bootstrap delivery.
        """
        if (
            not self.runtime.DUNGEON_TRANSITION_OUTBOX_AVAILABLE
            or not self.state.selected
            or not self.state.loaded
            or self.state.character is None
            or self.state.account_id is None
            or self.state.generation is None
        ):
            return None
        if self.state.fight is not None or self.state.combat_session is not None:
            return {"state": "deferred_combat", "pending_event_ids": ()}
        now = time.monotonic()
        if not before_action and now - self.state.last_dungeon_transition_poll < 1.0:
            return None
        self.state.last_dungeon_transition_poll = now
        story = self.poll_astrub_cat_story()
        if story is not None and story["blocks_travel"]:
            return {"state": "astrub_cat_story", "pending_event_ids": ()}
        if self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE and self.runtime.is_dungeon_run(
            self.state.character.get("instance_id", 0)
        ):
            from wakfu_server import (
                dungeon_auto_transition,
                dungeon_auto_exit,
                dungeon_runtime,
            )

            from wakfu_server import (
                dungeon_optional_encounters,
                dungeon_optional_ground_items,
                dungeon_optional_votes,
                dungeon_optional_continuations,
            )

            try:
                from wakfu_server import dungeon_postboss_nodes

                dungeon_postboss_nodes.publish_pending(
                    self.runtime.STORE,
                    self.runtime.COMBAT_GROUPS,
                    instance_id=self.state.character["instance_id"],
                    publish=lambda *packet: dungeon_optional_encounters.publish_native_scene(
                        self.runtime.WORLD, *packet
                    ),
                )
                if dungeon_optional_ground_items.scene_enabled(
                    self.state.character["map_id"]
                ) or dungeon_optional_votes.scene_enabled(
                    self.state.character["map_id"]
                ):
                    dungeon_optional_encounters.publish_pending(
                        self.runtime.STORE,
                        self.runtime.COMBAT_GROUPS,
                        instance_id=self.state.character["instance_id"],
                        publish=lambda *packet: dungeon_optional_encounters.publish_native_scene(
                            self.runtime.WORLD, *packet
                        ),
                    )
                    if dungeon_optional_votes.scene_enabled(
                        self.state.character["map_id"]
                    ):
                        dungeon_optional_votes.publish_pending(
                            self.runtime.STORE,
                            self.runtime.COMBAT_GROUPS,
                            instance_id=self.state.character["instance_id"],
                            publish=lambda *packet: dungeon_optional_encounters.publish_native_scene(
                                self.runtime.WORLD, *packet
                            ),
                        )
                if dungeon_optional_continuations.scene_enabled(
                    self.state.character["map_id"]
                ):
                    dungeon_optional_continuations.publish_pending(
                        self.runtime.STORE,
                        instance_id=self.state.character["instance_id"],
                        publish=lambda *packet: dungeon_optional_encounters.publish_native_scene(
                            self.runtime.WORLD, *packet
                        ),
                    )
            except Exception as error:
                # Post-commit delivery is retried by the existing idle/action
                # poll, including after reconnect or World recovery.
                self.runtime.record(
                    event="optional_ground_publication_deferred",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
            with self.runtime.COMBAT_GROUPS.lock, self.runtime.STORE.connection() as db:
                pending = db.execute(
                    "SELECT e.fight_id,COALESCE((e.result->>'completed')::boolean,false) AS completed "
                    "FROM dungeon_room_encounters e "
                    "JOIN dungeon_room_runs r ON r.instance_id=e.instance_id "
                    "WHERE e.instance_id=%s AND e.status='victory' AND e.encounter_scope='main' "
                    "AND e.result_revision=r.revision "
                    "AND EXISTS (SELECT 1 FROM dungeon_instance_members own "
                    "WHERE own.instance_id=e.instance_id AND own.character_id=%s AND own.status='active') "
                    "AND e.result->>'physical_publication_revision' IS NULL "
                    "AND ((e.result->>'auto_transition_revision' IS NULL "
                    "AND NOT COALESCE((e.result->>'completed')::boolean,false)) "
                    "OR (e.result->>'auto_exit_revision' IS NULL "
                    "AND COALESCE((e.result->>'completed')::boolean,false))) "
                    "ORDER BY e.fight_id DESC LIMIT 1",
                    (self.state.character["instance_id"], self.state.character["id"]),
                ).fetchone()
                if pending is not None:
                    from wakfu_server import dungeon_room_handoff
                    from wakfu_server.combat_terrain import map_geometry

                    hydration = dungeon_room_handoff.prepare(
                        db,
                        self.runtime.COMBAT_GROUPS,
                        instance_id=self.state.character["instance_id"],
                        fight_id=pending["fight_id"],
                        map_id=self.state.character["map_id"],
                        geometry_provider=map_geometry,
                    )
                    if hydration["ready"]:
                        _, configuration = dungeon_runtime.configuration_for_instance(
                            db, self.state.character["instance_id"]
                        )
            if pending is not None and not hydration["ready"]:
                if not hydration.get("recovery_required"):
                    return {"state": "room_hydration_deferred", "pending_event_ids": ()}
                from wakfu_server import dungeon_exit
                from wakfu_server.dungeon_transition_recovery import DungeonExitDeferred
                from wakfu_server.position_buffer import PositionOwnerBusy
                from psycopg.errors import LockNotAvailable

                try:
                    dungeon_exit.leave_recovery(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        positions=self.runtime.POSITIONS,
                        in_fight=lambda identity: self.runtime.COMBAT_SESSIONS.lookup_character(
                            identity
                        )
                        is not None,
                    )
                except (DungeonExitDeferred, PositionOwnerBusy, LockNotAvailable):
                    return {
                        "state": "room_hydration_exit_deferred",
                        "pending_event_ids": (),
                    }
                self.runtime.record(
                    event="dungeon_room_hydration_safe_exit",
                    actor_id=self.state.character["id"],
                    instance_id=self.state.character["instance_id"],
                    fight_id=pending["fight_id"],
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Información"),
                        "Tu victoria está guardada. Te estamos devolviendo a la entrada para recuperar la mazmorra.",
                    ),
                )
                pending = None
            if pending is not None:
                from wakfu_server import dungeon_native_flow

                if dungeon_native_flow.enabled(configuration["topology"]):
                    # Native room progress is committed by settlement; publish without automatic travel.
                    from wakfu_server.combat_monster_world import spawn_group

                    with self.runtime.COMBAT_GROUPS.lock:
                        physical_groups = tuple(
                            self.runtime.COMBAT_GROUPS.available(
                                self.state.character["map_id"],
                                self.state.character["instance_id"],
                            )
                        )
                    with self.runtime.STORE.connection() as db:
                        progress = db.execute(
                            "SELECT current_room,status,revision FROM dungeon_room_runs "
                            "WHERE instance_id=%s FOR UPDATE",
                            (self.state.character["instance_id"],),
                        ).fetchone()
                        physical_packets = dungeon_native_flow.packets(
                            configuration["topology"],
                            map_id=self.state.character["map_id"],
                            instance_id=self.state.character["instance_id"],
                            unlocked_room=progress["current_room"],
                            completed=progress["status"] == "completed",
                        )
                        for packet in physical_packets:
                            self.runtime.WORLD.emit_location(
                                self.state.character["map_id"],
                                self.state.character["instance_id"],
                                *packet,
                            )
                        for group in physical_groups:
                            self.runtime.WORLD.emit_location(
                                self.state.character["map_id"],
                                self.state.character["instance_id"],
                                12608,
                                self.runtime.owned_scene_spawn_group(
                                    group["members"], group_id=group["key"][2]
                                ),
                            )
                        db.execute(
                            "UPDATE dungeon_room_encounters SET result=result || "
                            "jsonb_build_object('physical_publication_revision',%s) "
                            "WHERE instance_id=%s AND fight_id=%s AND result_revision=%s",
                            (
                                progress["revision"],
                                self.state.character["instance_id"],
                                pending["fight_id"],
                                progress["revision"],
                            ),
                        )
                    return {"state": "physical_room_published", "pending_event_ids": ()}
                transition = (
                    dungeon_auto_exit.complete
                    if pending.get("completed")
                    else dungeon_auto_transition.advance
                )
                from wakfu_server.dungeon_position_barrier import (
                    run_auto_transition,
                )

                from wakfu_server.position_buffer import PositionOwnerBusy
                from psycopg.errors import LockNotAvailable

                try:
                    automatic_result = run_auto_transition(
                        self.runtime.STORE,
                        self.runtime.POSITIONS,
                        self.state.character["instance_id"],
                        pending["fight_id"],
                        transition=transition,
                        topology=configuration["topology"],
                        in_fight=lambda character_id: self.runtime.COMBAT_SESSIONS.lookup_character(
                            character_id
                        )
                        is not None,
                    )
                except (PositionOwnerBusy, LockNotAvailable):
                    return {"state": "transition_owner_busy", "pending_event_ids": ()}

                def recovery_notice(state):
                    identity = (
                        self.state.character["id"],
                        automatic_result["instance_id"],
                        automatic_result["fight_id"],
                        automatic_result["code"],
                    )
                    if identity != self.state.last_dungeon_recovery_identity:
                        self.state.dungeon_recovery_notice_states.clear()
                        self.state.last_dungeon_recovery_identity = identity
                    if state not in self.state.dungeon_recovery_notice_states:
                        message = (
                            "Tu progreso está a salvo. Te estamos devolviendo a una posición segura."
                            if state == "recovery_exit_queued"
                            else "Tu progreso está a salvo. Estamos recuperando tu posición para que puedas continuar."
                        )
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            674,
                            self.runtime.wire.chat(
                                dict(self.state.character, name="Información"), message
                            ),
                        )
                        self.state.dungeon_recovery_notice_states.add(state)

                if automatic_result is not None and automatic_result.get(
                    "recovery_waiting"
                ):
                    recovery_notice("recovery_retrying")
                    return {"state": "recovery_backoff", "pending_event_ids": ()}
                if automatic_result is not None and automatic_result.get(
                    "recovery_required"
                ):
                    from wakfu_server.dungeon_transition_recovery import (
                        DungeonExitDeferred,
                    )
                    from wakfu_server.position_buffer import PositionOwnerBusy
                    from psycopg.errors import LockNotAvailable
                    from wakfu_server import dungeon_exit

                    recovery_state = "recovery_held_at_last_scene"
                    if automatic_result["exit_authorized"]:
                        try:
                            dungeon_exit.leave_automatic(
                                self.runtime.STORE,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character["id"],
                                positions=self.runtime.POSITIONS,
                                in_fight=lambda identity: self.runtime.COMBAT_SESSIONS.lookup_character(
                                    identity
                                )
                                is not None,
                            )
                        except (
                            DungeonExitDeferred,
                            PositionOwnerBusy,
                            LockNotAvailable,
                        ) as error:
                            recovery_state = "recovery_exit_deferred"
                            recovery_reason = str(error)
                        else:
                            recovery_state = "recovery_exit_queued"
                            recovery_reason = automatic_result["code"]
                    else:
                        recovery_reason = automatic_result["code"]
                    recovery_notice(recovery_state)
                    report_key = (
                        recovery_state,
                        automatic_result["instance_id"],
                        automatic_result["fight_id"],
                        automatic_result["code"],
                    )
                    if report_key != self.state.last_dungeon_transition_report:
                        self.runtime.record(
                            event="dungeon_transition_recovery",
                            actor_id=self.state.character["id"],
                            state=recovery_state,
                            instance_id=automatic_result["instance_id"],
                            fight_id=automatic_result["fight_id"],
                            code=automatic_result["code"],
                            attempts=automatic_result["attempts"],
                            reason=recovery_reason,
                        )
                    self.state.last_dungeon_transition_report = report_key
                    if recovery_state != "recovery_exit_queued":
                        return {"state": recovery_state, "pending_event_ids": ()}
                elif automatic_result is not None and automatic_result.get("recovery"):
                    self.runtime.record(
                        event="dungeon_transition_repaired",
                        actor_id=self.state.character["id"],
                        instance_id=self.state.character["instance_id"],
                        fight_id=pending["fight_id"],
                        revision=automatic_result["revision"],
                        recovery=automatic_result["recovery"],
                    )

        def current_location():
            return {
                key: self.state.character.get(key, 0)
                for key in ("map_id", "instance_id", "x", "y", "z")
            }

        def bootstrap_dungeon_event(event):
            plan = self.runtime.dungeon_hydration.prepare_transition(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                event,
                fixture_provider=self.runtime.fixture,
            )
            from wakfu_server.position_buffer import (
                PositionBaselineChanged,
                PositionOwnerBusy,
            )
            from psycopg.errors import LockNotAvailable

            try:
                self.runtime.POSITIONS.attach(
                    self.state.account_id, self.state.generation, plan.character
                )
            except (PositionBaselineChanged, PositionOwnerBusy, LockNotAvailable):
                # The durable outbox remains pending; retry before changing
                # this worker's scene or acknowledging delivery.
                return False
            self.cancel_crafting()
            self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
            prior_inventory = self.state.character
            self.state.character = plan.character
            self.state.position = {
                key: self.state.character[key] for key in ("x", "y", "z")
            }
            self.state.movement_state = self.runtime.Movement(self.state.position)
            for message_id, message_body in plan.packets:
                self.runtime.send(
                    self.state.connection, self.state.service, message_id, message_body
                )
            from wakfu_server import dungeon_excavation_rules

            excavation_exit = event.get(
                "transition_kind"
            ) == "exit" and dungeon_excavation_rules.scene_enabled(
                prior_inventory["map_id"]
            )
            if event.get("transition_kind") == "entry" or excavation_exit:
                self.publish_entry_inventory(prior_inventory)
            if excavation_exit:
                from wakfu_server import consumable_buff_wire

                for packet in consumable_buff_wire.delta(
                    prior_inventory, self.state.character
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *packet
                    )
            self.runtime.join_world(
                self.state.generation, self.state.connection, self.state.character
            )
            self.mark_static_sync_pending()
            return True

        result = self.runtime.dungeon_transition_delivery.deliver_pending_transitions(
            self.runtime.STORE,
            self.state.account_id,
            self.state.generation,
            self.state.character["id"],
            worker_generation=self.state.generation,
            current_location=current_location,
            in_fight=lambda: self.state.fight is not None
            or self.state.combat_session is not None,
            bootstrap=bootstrap_dungeon_event,
        )
        report_key = (
            result["state"],
            tuple(result["pending_event_ids"]),
        )
        if (
            result["state"] != "idle"
            and report_key != self.state.last_dungeon_transition_report
        ):
            self.runtime.record(
                event="dungeon_transition_deferred",
                actor_id=self.state.character["id"],
                state=result["state"],
                pending_event_ids=list(result["pending_event_ids"]),
                reason=(
                    "destination bootstrap did not complete"
                    if result["state"] == "bootstrap_incomplete"
                    else None
                ),
            )
        self.state.last_dungeon_transition_report = report_key
        return result

    def execute_dungeon_exit_command(self, *, _native_return_retry=False):
        try:
            from wakfu_server import dungeon_exit

            self.emergency_exit_current_combat()
            if (
                self.state.aborted_native_return is not None
                and not self.state.aborted_native_return.world_returned
            ):
                self.state.aborted_native_return.command = "!exitdungeon"
                return
            with self.runtime.STORE.connection() as exit_db:
                has_dungeon = (
                    exit_db.execute(
                        "SELECT 1 FROM dungeon_instances WHERE instance_id=%s",
                        (self.state.character.get("instance_id", 0),),
                    ).fetchone()
                    is not None
                )
            if not has_dungeon:
                self.execute_test_command("!astrub")
                return

            def exit_member_in_fight(actor_id):
                if actor_id == self.state.character["id"] and (
                    self.state.fight is not None
                    or self.state.combat_session is not None
                ):
                    return True
                return (
                    self.runtime.COMBAT_SESSIONS.lookup_character(actor_id) is not None
                )

            self.runtime.record(
                event="dungeon_exit_requested",
                actor_id=self.state.character["id"],
                instance_id=self.state.character.get("instance_id", 0),
            )
            try:
                dungeon_exit.leave_automatic(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    in_fight=exit_member_in_fight,
                    positions=self.runtime.POSITIONS,
                )
            except ValueError:
                # Administrative relocation closes company membership
                # even when this dungeon has no reviewed native exit.
                self.execute_test_command("!astrub")
                return
            self.deliver_dungeon_transitions(before_action=True)
            answer = "Has salido de la mazmorra."
        except (
            ValueError,
            PermissionError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
        ) as error:
            if _native_return_retry and isinstance(
                error, (self.state.DatabaseError, self.state.PoolTimeout)
            ):
                raise
            answer = str(error)
            self.runtime.record(
                event="dungeon_exit_rejected",
                actor_id=self.state.character["id"],
                reason=answer,
            )
        self.runtime.send(
            self.state.connection,
            self.state.service,
            674,
            self.runtime.wire.chat(
                dict(self.state.character, name="Información"), answer
            ),
        )
        return

    def handle_storage_travel(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.travel_storage_feedback import rejection

        self.state.rejection = rejection

        try:
            from wakfu_server import native_boats

            self.state.native_boats = native_boats
            from wakfu_server import transport_criteria

            with PROFILER.span("transport.native.resolve"):
                native_zaap = (
                    self.state.native_boats.source(
                        self.state.character, self.state.body
                    )
                    is None
                )
                if not native_zaap:
                    from wakfu_server.combat_terrain import map_geometry

                    self.state.map_geometry = map_geometry

                    self.state.destination_route = self.state.native_boats.resolve(
                        self.state.character,
                        self.state.body,
                        source_allowed=lambda actor, origin: self.state.native_boats.admit_source(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            actor,
                            origin,
                            blocked=self.environment_blocked(),
                        ),
                        geometry=self.state.map_geometry,
                        criterion_evaluator=transport_criteria.evaluator(
                            self.runtime.STORE, self.state.character
                        ),
                    )
                else:
                    self.state.destination_route = (
                        self.runtime.native_transports.resolve(
                            self.state.character,
                            self.state.body,
                            known_ids=self.runtime.known_transports(
                                self.state.account_id
                            ),
                            waive_criteria=self.runtime.ALL_ZAAPS,
                        )
                    )
            with PROFILER.span("transport.native.commit"):
                from wakfu_server import mission_transport

                self.state.mission_transport = mission_transport

                (
                    self.state.saved,
                    self.state.mission_packets,
                ) = self.state.mission_transport.transition(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.destination_route,
                    native_zaap=native_zaap,
                )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.record(
                event="native_transport_rejected",
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
                *self.state.rejection("transport", error),
            )
        else:
            with PROFILER.span("transport.native.publish"):
                self.cancel_crafting()
                self.runtime.WORLD.leave(
                    self.state.character["id"], self.state.generation
                )
                self.state.character = self.state.saved
                self.runtime.POSITIONS.attach(
                    self.state.account_id, self.state.generation, self.state.character
                )
                self.state.position = {
                    key: self.state.character[key] for key in ("x", "y", "z")
                }
                self.state.movement_state = self.runtime.Movement(self.state.position)
                for (
                    self.state.message_id,
                    self.state.message_body,
                ) in self.runtime.owned_native_bootstrap(self.state.character):
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.message_body,
                    )
                # Publish heavy dynamic entities once, after map-ready.
                self.runtime.join_world(
                    self.state.generation,
                    self.state.connection,
                    self.state.character,
                    defer_scene_snapshot=self.state.character["map_id"] != 9,
                )
                self.mark_static_sync_pending()
                for (
                    self.state.message_id,
                    self.state.message_body,
                ) in self.state.mission_packets:
                    from wakfu_server import rii_scenario

                    self.state.rii_scenario = rii_scenario

                    if (
                        self.state.message_id,
                        self.state.message_body,
                    ) == self.state.rii_scenario.packet(self.state.rii_scenario.INTRO):
                        self.state.connection.pending_rii_intro = self.state.character[
                            "id"
                        ]
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.message_body,
                    )
            self.runtime.record(
                event="native_map_transition",
                actor_id=self.state.character["id"],
                source_id=self.state.destination_route["source_id"],
                destination_id=self.state.destination_route["destination_id"],
                map_id=self.state.character["map_id"],
                position=self.state.position,
            )
        return DispatchResult.FALLTHROUGH

    def handle_transport_list(self):
        from wakfu_server import nation_state, guild_wire

        self.state.nation_state = nation_state

        try:
            if self.state.fight is not None:
                raise ValueError("La inscripción requiere estar fuera de combate.")
            self.state.saved = self.state.nation_state.enroll(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                self.state.body,
            )
            self.state.character = (
                self.active_private_session().refresh(
                    self.state.character, self.state.saved
                )
                if self.active_private_session() is not None
                and self.active_private_session().owns(self.state.character)
                else self.state.saved
            )
            self.state.character = self.publish_nation_character(self.state.character)
            self.runtime.record(
                event="nation_enrolled",
                actor_id=self.state.character["id"],
                nation_id=self.state.nation_state.nation_id(self.state.character),
            )
        except ValueError as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
            self.runtime.record(
                event="nation_enrollment_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_transport_select(self):
        from wakfu_server import dungeon_context, dungeon_difficulty

        self.state.dungeon_context = dungeon_context

        try:
            if self.state.fight is not None:
                raise ValueError("Dungeon difficulty cannot change during combat")
            self.state.request = dungeon_difficulty.decode_request(self.state.body)
            if self.state.request["character_id"] != self.state.character["id"]:
                raise ValueError("Dungeon request targets another character")
            self.state.chosen = dungeon_difficulty.select(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
                stasis_level=self.state.request["stasis_level"],
                expected_instance_id=self.state.request["instance_id"],
            )
            self.state.instance_id = self.state.chosen["instance_id"]
            self.state.packet = self.state.dungeon_context.update_packet(
                self.runtime.STORE, self.state.instance_id, fight_in_progress=False
            )
            maps = {
                player["map_id"]
                for player in self.runtime.WORLD.snapshot()
                if player["instance_id"] == self.state.instance_id
            }
            for self.state.map_id in maps:
                self.runtime.WORLD.emit_location(
                    self.state.map_id, self.state.instance_id, *self.state.packet
                )
            self.runtime.record(
                event="dungeon_difficulty_selected",
                actor_id=self.state.character["id"],
                instance_id=self.state.instance_id,
                stasis_level=self.state.chosen["stasis_level"],
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(str(error)),
            )
            self.runtime.record(
                event="dungeon_difficulty_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_transport_travel(self):
        from wakfu_server import generic_transports, teleporter_approach
        from wakfu_server.position_buffer import PositionOwnerBusy

        self.state.PositionOwnerBusy = PositionOwnerBusy

        generic_route = False
        transport_committed = False
        mission_transport_packets = []
        try:
            if self.state.artifact_action_request:
                from wakfu_server import exploration_artifact_actions

                self.state.exploration_artifact_actions = exploration_artifact_actions

                if (
                    self.environment_blocked()
                    or self.state.environment_ticket is not None
                ):
                    raise ValueError(
                        "Exploration action is blocked by the current activity"
                    )
                if not self.runtime.STORE.current_character_session(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                ):
                    raise ValueError("Exploration action session expired")
                self.runtime.flush_positions(
                    account_id=self.state.account_id,
                    generation=self.state.generation,
                    character_id=self.state.character["id"],
                )
                self.state.destination_route = (
                    self.state.exploration_artifact_actions.admit(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        source_allowed=teleporter_approach.callback(
                            self.state.movement_state,
                            map_id=self.state.character["map_id"],
                            instance_id=self.state.character.get("instance_id", 0),
                        ),
                        position_allowed=self.artifact_position_allowed,
                        blocked=self.environment_blocked(),
                    )
                )
                artifact_owner = dict(
                    self.state.character, **self.state.destination_route["origin"]
                )
                if self.admit_artifact_action(
                    self.state.destination_route, self.state.body, artifact_owner
                ):
                    return DispatchResult.CONTINUE
                generic_route = True
            if (1 << 58) < self.state.character.get("instance_id", 0) < (1 << 59):
                from wakfu_server import rift_exit

                from wakfu_server.position_buffer import PositionOwnerBusy

                self.state.PositionOwnerBusy = PositionOwnerBusy

                try:
                    self.state.exited = rift_exit.leave(
                        self.runtime.STORE,
                        self.runtime.POSITIONS,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.body,
                        source_allowed=teleporter_approach.callback(
                            self.state.movement_state,
                            map_id=self.state.character["map_id"],
                            instance_id=self.state.character["instance_id"],
                        ),
                        fighting=lambda actor_id: self.runtime.COMBAT_SESSIONS.lookup_character(
                            actor_id
                        )
                        is not None,
                    )
                except self.state.PositionOwnerBusy:
                    self.runtime.record(
                        event="request_position_busy",
                        actor_id=self.state.character["id"],
                        opcode=self.state.opcode,
                    )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        674,
                        self.runtime.wire.chat(
                            dict(self.state.character, name="Consola local"),
                            "Guardado de posición en curso. Reintenta la acción.",
                        ),
                    )
                    return DispatchResult.CONTINUE
                if self.state.exited is not None:
                    self.deliver_rift_transition()
                    return DispatchResult.CONTINUE
            if (
                not self.state.artifact_action_request
                and self.runtime.DUNGEON_TRANSITION_OUTBOX_AVAILABLE
                and self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
            ):
                from wakfu_server import (
                    dungeon_transport,
                    dungeon_criteria,
                    dungeon_runtime,
                )

                self.state.dungeon_runtime = dungeon_runtime
                from wakfu_server.combat_terrain import map_geometry

                self.state.map_geometry = map_geometry

                if self.runtime.is_dungeon_run(
                    self.state.character.get("instance_id", 0)
                ):
                    from wakfu_server import (
                        dungeon_doors,
                        dungeon_exit,
                    )

                    with self.runtime.STORE.connection() as dungeon_db:
                        (
                            self.state._,
                            self.state.dungeon_config,
                        ) = self.state.dungeon_runtime.configuration_for_instance(
                            dungeon_db, self.state.character["instance_id"]
                        )
                    if (
                        self.state.dungeon_config["topology"].get("policy")
                        == "local_accessible_anchor_policy"
                    ):
                        raise ValueError("This dungeon uses automatic party travel")
                    (
                        self.state.source_id,
                        self.state.destination_id,
                        self.state._,
                        self.state._,
                    ) = struct.unpack(">qiBi", self.state.body)
                    self.state.source = generic_transports.source(
                        self.state.character["map_id"], self.state.source_id
                    )
                    destination = next(
                        (
                            row
                            for row in (self.state.source or {}).get("destinations", ())
                            if row["destination_id"] == self.state.destination_id
                        ),
                        None,
                    )
                    if destination is None:
                        raise ValueError("Dungeon teleporter destination is absent")
                    from wakfu_server import dungeon_native_flow

                    self.state.dungeon_native_flow = dungeon_native_flow

                    if self.state.source_id in {
                        r["source_id"]
                        for r in self.state.dungeon_config["topology"].get(
                            "held_optional_sources", ()
                        )
                    }:
                        raise ValueError(
                            "Native optional access requires its separate qualified quest mechanism"
                        )
                    if (
                        self.state.source_id
                        in self.state.dungeon_native_flow.disabled_source_ids(
                            self.state.dungeon_config["topology"],
                            generic_transports._CATALOG,
                        )
                    ):
                        raise ValueError(
                            "Native source is explicitly excluded by the local dungeon policy"
                        )
                    approach = teleporter_approach.callback(
                        self.state.movement_state,
                        map_id=self.state.character["map_id"],
                        instance_id=self.state.character["instance_id"],
                    )

                    def dungeon_member_in_fight(actor_id):
                        if actor_id == self.state.character["id"] and (
                            self.state.fight is not None
                            or self.state.combat_session is not None
                        ):
                            return True
                        return (
                            self.runtime.COMBAT_SESSIONS.lookup_character(actor_id)
                            is not None
                        )

                    if destination["map_id"] != self.state.character["map_id"]:
                        from wakfu_server import dungeon_native_flow

                        self.state.dungeon_native_flow = dungeon_native_flow

                        if self.state.dungeon_native_flow.enabled(
                            self.state.dungeon_config["topology"]
                        ):
                            physical_exit = next(
                                (
                                    row
                                    for row in self.state.dungeon_config["topology"][
                                        "physical_exit_objects"
                                    ]
                                    if row["source_id"] == self.state.source_id
                                ),
                                None,
                            )
                            with self.runtime.STORE.connection() as exit_db:
                                exit_progress = exit_db.execute(
                                    "SELECT status FROM dungeon_room_runs WHERE instance_id=%s",
                                    (self.state.character["instance_id"],),
                                ).fetchone()
                            if not self.state.dungeon_native_flow.exit_available(
                                self.state.dungeon_config["topology"],
                                physical_exit,
                                completed=exit_progress["status"] == "completed",
                            ):
                                raise ValueError("Native dungeon exit is locked")
                        dungeon_exit.leave(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            self.state.body,
                            source_allowed=approach,
                            in_fight=dungeon_member_in_fight,
                            positions=self.runtime.POSITIONS,
                        )
                    else:
                        dungeon_doors.advance(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            self.state.body,
                            source_allowed=approach,
                            in_fight=dungeon_member_in_fight,
                            topology=self.state.dungeon_config["topology"],
                            positions=self.runtime.POSITIONS,
                            on_arrival=(
                                (
                                    lambda db, instance_id: self.state.dungeon_runtime.ensure_current_room(
                                        db,
                                        self.runtime.COMBAT_GROUPS,
                                        instance_id,
                                        self.state.map_geometry(
                                            self.state.character["map_id"]
                                        ),
                                    )
                                )
                                if (
                                    self.state.dungeon_config["topology"].get(
                                        "branch_routes"
                                    )
                                    or self.state.dungeon_config["topology"].get(
                                        "entry_path_policy"
                                    )
                                )
                                else None
                            ),
                            room_for_position=lambda map_id, x, y, z: self.state.dungeon_runtime.room_for_position(
                                self.state.dungeon_config, map_id, x, y, z
                            ),
                        )
                    self.deliver_dungeon_transitions(before_action=True)
                    return DispatchResult.CONTINUE
                self.state.configured_entry = dungeon_transport.resolve_request(
                    self.state.character["map_id"], self.state.body
                )
                if self.state.configured_entry is not None:
                    from wakfu_server import (
                        dungeon_entry_access,
                    )

                    self.state.dungeon_entry_access = dungeon_entry_access

                    self.state.geometry = self.state.map_geometry(
                        self.state.configured_entry["route"].start_map_id
                    )
                    dungeon_transport.enter(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.character["map_id"],
                        self.state.body,
                        criterion_allowed=lambda actor, criterion: self.state.dungeon_entry_access.evaluate(
                            self.runtime.STORE,
                            criterion,
                            character=actor,
                            destination_map_id=self.state.configured_entry[
                                "route"
                            ].start_map_id,
                        ),
                        source_allowed=teleporter_approach.callback(
                            self.state.movement_state,
                            map_id=self.state.character["map_id"],
                            instance_id=self.state.character.get("instance_id", 0),
                        ),
                        resolve_destination=self.state.dungeon_runtime.entry_destination,
                        positions=self.runtime.POSITIONS,
                        initialize_instance=lambda db, session: self.state.dungeon_runtime.initialize_instance(
                            db,
                            session,
                            groups=self.runtime.COMBAT_GROUPS,
                            geometry=self.state.geometry,
                            store=self.runtime.STORE,
                        ),
                    )
                    transport_committed = True
                    self.deliver_dungeon_transitions(before_action=True)
                    return DispatchResult.CONTINUE
            self.state.identity = (
                struct.unpack_from(">q", self.state.body)[0]
                if len(self.state.body) == 17
                else None
            )
            verified_tutorial = any(
                route["source_map"] == self.state.character["map_id"]
                and route["interactive_element_id"] == self.state.identity
                for route in self.runtime.transports.CATALOG["routes"]
            )
            if not self.state.artifact_action_request and (
                not verified_tutorial
                and self.state.identity is not None
                and generic_transports.source(
                    self.state.character["map_id"], self.state.identity
                )
                is not None
            ):
                from wakfu_server import seasonal_transport

                self.state.destination_route = generic_transports.resolve(
                    self.state.character,
                    self.state.body,
                    source_allowed=teleporter_approach.callback(
                        self.state.movement_state,
                        map_id=self.state.character["map_id"],
                        instance_id=self.state.character.get("instance_id", 0),
                    ),
                    criterion_evaluator=seasonal_transport.evaluator(
                        self.runtime.STORE, self.state.character
                    ),
                    allow_item_payment=True,
                )
                generic_route = True
            elif not self.state.artifact_action_request:
                self.state.destination_route = self.runtime.transports.resolve(
                    self.state.character, self.state.body
                )
            if self.state.artifact_action_request:
                self.state.saved = self.state.exploration_artifact_actions.transition(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                    expected_plan=self.state.destination_route,
                    source_allowed=teleporter_approach.callback(
                        self.state.movement_state,
                        map_id=self.state.character["map_id"],
                        instance_id=self.state.character.get("instance_id", 0),
                    ),
                    position_allowed=self.artifact_position_allowed,
                    blocked=self.environment_blocked(),
                )
            elif self.state.destination_route.get("item_payment") is not None:
                from wakfu_server import seasonal_transport

                self.state.saved = seasonal_transport.transition(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.destination_route,
                )
            else:
                # Every native teleporter shares the mission journal
                # boundary; each hook is destination-scoped inside
                # (Rii arrival, dojo script bootstrap, sanctuary,
                # guardian ending, Zaap departure).
                from wakfu_server import mission_transport

                self.state.mission_transport = mission_transport

                (
                    self.state.saved,
                    mission_transport_packets,
                ) = self.state.mission_transport.transition(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.destination_route,
                    native_zaap=False,
                )
            transport_committed = True
        except self.state.PositionOwnerBusy:
            # Pre-commit contention leaves the source playable;
            # committed dungeon travel retries its durable outbox.
            self.runtime.record(
                event="request_position_busy",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(
                    "Guardado de posición en curso. Reintenta la acción."
                ),
            )
        except ValueError as error:
            self.runtime.record(
                event="transport_rejected",
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
                *self.state.information(
                    self.artifact_failure_message(error)
                    if self.state.artifact_action_request
                    else self.state.failure_message("transport", error)
                ),
            )
            from wakfu_server.transport_rejection import (
                requires_scene_recovery,
            )

            if requires_scene_recovery(error, transition_committed=transport_committed):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    13974,
                    (
                        next(
                            payload
                            for message_id, payload in self.runtime.owned_native_bootstrap(
                                self.state.character
                            )
                            if message_id == 13974
                        )
                        if self.runtime.is_dungeon_run(
                            self.state.character.get("instance_id", 0)
                        )
                        else self.runtime.wire.adapt(
                            13974,
                            self.runtime.fixture(13974),
                            self.state.account_id,
                            self.state.character,
                        )
                    ),
                )
        else:
            self.publish_public_transport(
                self.state.destination_route,
                self.state.saved,
                generic_route=generic_route,
            )
            for (
                self.state.message_id,
                self.state.message_body,
            ) in mission_transport_packets:
                from wakfu_server import rii_scenario

                self.state.rii_scenario = rii_scenario

                if (
                    self.state.message_id,
                    self.state.message_body,
                ) == self.state.rii_scenario.packet(self.state.rii_scenario.INTRO):
                    self.state.connection.pending_rii_intro = self.state.character["id"]
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.message_body,
                )
        return DispatchResult.FALLTHROUGH
