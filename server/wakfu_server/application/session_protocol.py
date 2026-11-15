"""Protocol operations for one lease-bound World session."""

import socket
import struct
import subprocess
from .dispatch_result import DispatchResult


class ProtocolSessionMixin:
    def handle_handshake(self):
        self.runtime.send(
            self.state.connection,
            self.state.service,
            400,
            struct.pack(">q", 123456789)
            + (self.runtime.RUNTIME / "public-key.der").read_bytes(),
        )
        return DispatchResult.FALLTHROUGH

    def handle_dispatcher(self):
        if self.state.opcode == 584:
            r = self.runtime.Reader(self.state.body)
            encrypted = r.take(r.number("I"))
            r.finish()
            self.state.result = subprocess.run(
                [
                    "openssl",
                    "pkeyutl",
                    "-decrypt",
                    "-inkey",
                    str(self.runtime.RUNTIME / "server.key"),
                    "-pkeyopt",
                    "rsa_padding_mode:pkcs1",
                ],
                input=encrypted,
                capture_output=True,
                timeout=5,
            )
            if self.state.result.returncode:
                raise ValueError("Invalid RSA authentication")
            r = self.runtime.Reader(self.state.result.stdout)
            if r.number("q") != 123456789:
                raise ValueError("Invalid challenge")
            token = r.text("B")
            r.finish()
            self.state.access = self.runtime.STORE.token(token, "game", consume=True)
            self.state.account_id = self.state.access["account_id"]
            # Hold the buffer across takeover so the old worker
            # cannot enqueue another move between flush and CAS.
            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                with self.runtime.LOCK:
                    self.state.previous = self.runtime.LIVE.get(self.state.account_id)
                self.state.generation = self.runtime.STORE.begin_session(
                    self.state.account_id,
                    previous_generation=(
                        None if self.state.previous is None else self.state.previous[0]
                    ),
                )
                with self.runtime.LOCK:
                    self.state.previous = self.runtime.LIVE.pop(
                        self.state.account_id, None
                    )
            if self.state.previous:
                self.runtime.record(
                    event="session_replaced_before_shutdown",
                    account_id=self.state.account_id,
                    target_connection_id=getattr(
                        self.state.previous[1], "trace_id", None
                    ),
                    replacement_connection_id=self.state.connection_trace_id,
                )
                try:
                    self.state.previous[1].shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            self.runtime.send(
                self.state.connection,
                self.state.service,
                472,
                self.runtime.wire.adapt(
                    472, self.runtime.fixture(472), self.state.account_id
                ),
            )
            self.runtime.record(
                event="account_authenticated", account_id=self.state.account_id
            )
        elif self.state.opcode == 402:
            if self.state.account_id is None:
                raise ValueError("Authentication required")
            from wakfu_server.server_identity import (
                configured_server_name,
                rename_realm,
            )

            self.runtime.send(
                self.state.connection,
                self.state.service,
                453,
                rename_realm(
                    self.runtime.REALMS, configured_server_name(self.runtime.STORE)
                ),
            )
        elif self.state.opcode == 575:
            self.state.request = self.runtime.decode_body(
                "out", self.state.opcode, self.state.body
            )
            if self.state.request["server_id"] != 10:
                raise ValueError("Unknown local realm")
            if self.state.account_id is None:
                raise ValueError("Authentication required")
            self.state.ticket = self.runtime.STORE.issue_token(
                self.state.account_id,
                "ticket",
                generation=self.state.generation,
                realm_id=10,
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                466,
                b"\x00" + self.runtime.pack_text(self.state.ticket),
            )
        return DispatchResult.FALLTHROUGH

    def handle_realm_ticket(self):
        self.state.request = self.runtime.decode_body(
            "out", self.state.opcode, self.state.body
        )
        self.state.access = self.runtime.STORE.token(
            self.state.request["ticket"], "ticket", consume=True
        )
        self.state.account_id, self.state.generation = (
            self.state.access["account_id"],
            self.state.access["generation"],
        )
        if self.state.access[
            "realm_id"
        ] != 10 or not self.runtime.STORE.current_session(
            self.state.account_id, self.state.generation
        ):
            raise ValueError("Invalid local ticket session")
        with self.runtime.LOCK:
            self.runtime.LIVE[self.state.account_id] = (
                self.state.generation,
                self.state.connection,
            )
        self.runtime.replay(
            self.state.connection,
            24,
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
        self.runtime.send_shop_authentication(
            self.state.connection,
            self.state.service,
            self.state.account_id,
            self.state.generation,
        )
        return DispatchResult.FALLTHROUGH

    def prepare_request(self):
        if self.state.opcode == 33:
            # Keepalive has no gameplay mutation. Reply before shared
            # fight locks, transitions or synchronous Rift checkpoints.
            self.runtime.send(
                self.state.connection, self.state.service, 23, b"\x01" + self.state.body
            )
            self.runtime.send(
                self.state.connection, self.state.service, 309, struct.pack(">I", 12345)
            )
            self.state.active_request.finish()
            self.state.active_request = None
            return DispatchResult.CONTINUE
        if self.committed_travel_holds_request(self.state.opcode):
            return DispatchResult.CONTINUE
        if self.state.pending_combat_return is not None and self.state.opcode not in (
            314,
            23354,
        ):
            if self.state.pending_return_command.retain(
                self.state.opcode,
                self.state.body,
                (
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                ),
            ):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(
                        "Comando guardado; se ejecutará al completar el regreso del combate."
                    ),
                )
            # The terminal return packets are already published. Hold
            # follow-up gameplay until the position fence completes.
            # Native ping replies and server-clock synchronization still
            # pass through; the ACK and return side effects never replay.
            self.state.pending_combat_return["held_requests"] += 1
            if (
                self.state.pending_combat_return["held_requests"] == 1
                or self.state.pending_combat_return["held_requests"] % 100 == 0
            ):
                self.runtime.record(
                    event="combat_return_request_held",
                    actor_id=self.state.character["id"],
                    fight_id=self.state.pending_combat_return["fight_id"],
                    opcode=self.state.opcode,
                    held_requests=self.state.pending_combat_return["held_requests"],
                )
            return DispatchResult.CONTINUE
        if self.state.loaded:
            # A frozen rift party must hydrate its committed asset map
            # before adopting a placement already registered by its leader.
            self.deliver_rift_transition()
        # The accepted challenger can receive its placement batch on
        # WORLD before its own idle callback runs. Bind that socket to
        # the shared duel before dispatching an immediate readiness or
        # action packet; otherwise the first 12523 can be rejected as
        # having no fight handler even though the client saw placement.
        if (
            self.runtime.COMBAT_TEST
            and self.state.loaded
            and self.state.character is not None
            and self.state.combat_session is None
            and self.state.fight is None
        ):
            try:
                self.attempt_shared_combat_attachment(blocking=True)
            except (ValueError, KeyError) as error:
                self.runtime.record(
                    event="friendly_duel_attach_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
        if self.command_recovery_holds_request(self.state.opcode, self.state.body):
            return DispatchResult.CONTINUE
        if self.state.combat_session is not None and self.state.fight is not None:
            if self.refresh_shared_combat() is False and self.state.opcode not in (
                314,
                23354,
                13952,
                12366,
                12925,
            ):
                return DispatchResult.CONTINUE
        if (
            self.state.opcode not in (314, 23354, 13952, 12366)
            and not (
                self.state.opcode == 12925
                and self.state.aborted_native_return is not None
            )
            and self.deferred_native_combat_attachment() is not None
        ):
            self.runtime.record(
                event="combat_publication_recovery_action_deferred",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
            return DispatchResult.CONTINUE
        if self.state.loaded:
            self.deliver_rift_transition()
            dungeon_delivery = self.deliver_dungeon_transitions(before_action=True)
            if (
                dungeon_delivery is not None
                and dungeon_delivery.get("state") == "astrub_cat_story"
                and self.state.opcode
                in (
                    13331,
                    12870,
                    12363,
                    12296,
                    13578,
                    13686,
                    13130,
                    13222,
                    12006,
                    12054,
                )
            ):
                return DispatchResult.CONTINUE
            if (
                dungeon_delivery is not None
                and (
                    dungeon_delivery.get("pending_event_ids")
                    or dungeon_delivery.get("state") == "transition_owner_busy"
                )
                and self.state.opcode not in (314, 23354, 13952, 12366)
            ):
                # A committed destination must replace the source scene
                # before another movement or gameplay request can run.
                self.runtime.record(
                    event="dungeon_transition_action_deferred",
                    actor_id=self.state.character["id"],
                    opcode=self.state.opcode,
                )
                return DispatchResult.CONTINUE
        if self.state.guild_chest_session is not None and (
            self.state.fight is not None
            or self.state.spectator_session is not None
            or self.state.bag_session is not None
            or self.state.character is None
            or self.state.character["id"] != self.state.guild_chest_session.character_id
            or self.state.opcode == 13331
        ):
            self.state.guild_chest_session.close(clear=True)
            self.state.guild_chest_session = None
        from wakfu_server.haven_chest import (
            can_access_location as chest_location_allowed,
        )

        if self.state.chest_opening is not None and (
            self.state.fight is not None
            or self.state.spectator_session is not None
            or self.state.bag_session is None
            or not chest_location_allowed(
                self.state.character, self.state.bag_session, self.state.ranch_session
            )
            or self.state.opcode == 13331
        ):
            self.state.chest_opening = None
        # All transactional actions/DB refreshes see the last approved
        # outside-world position; own-bag moves remain session-only.
        if self.state.character is not None and self.state.opcode != 13331:
            from wakfu_server.position_buffer import PositionOwnerBusy

            self.state.PositionOwnerBusy = PositionOwnerBusy

            try:
                self.runtime.flush_positions(
                    account_id=self.state.account_id,
                    generation=self.state.generation,
                    character_id=self.state.character["id"],
                )
            except self.state.PositionOwnerBusy:
                # Reject this action before any mutation; another
                # writer retains the dirty authoritative position.
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
        self.state.artifact_action_request = False
        if (
            self.state.pending_artifact_action is not None
            and self.state.opcode == 12870
        ):
            self.cancel_artifact_action("Another interactive action started")
        if (
            self.state.loaded
            and self.state.character is not None
            and self.state.opcode == 12870
        ):
            from wakfu_server.phoenix_points import (
                recognizes as phoenix_activation,
            )

            if phoenix_activation(self.state.body):
                from psycopg import Error as PhoenixDatabaseError
                from psycopg_pool import PoolTimeout as PhoenixPoolTimeout

                try:
                    self.activate_world_phoenix(self.state.body)
                except (
                    ValueError,
                    PhoenixDatabaseError,
                    PhoenixPoolTimeout,
                ) as error:
                    self.state.reason = (
                        str(error)
                        if isinstance(error, ValueError)
                        else "Reintenta la vinculación con el fénix"
                    )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.information(self.state.reason),
                    )
                    self.runtime.record(
                        event="phoenix_binding_rejected",
                        actor_id=self.state.character["id"],
                        reason=self.state.reason,
                    )
                return DispatchResult.CONTINUE
            from wakfu_server import exploration_artifact_actions

            self.state.exploration_artifact_actions = exploration_artifact_actions
            from wakfu_server.seasonal_native_gateway import activation

            self.state.artifact_action_request = (
                self.state.exploration_artifact_actions.recognizes(
                    self.state.character, self.state.body
                )
                or (
                    len(self.state.body) == 12
                    and self.state.exploration_artifact_actions.projection_required(
                        self.state.character["map_id"],
                        struct.unpack_from(">q", self.state.body)[0],
                    )
                )
            )
            try:
                artifact_body = self.state.exploration_artifact_actions.activation(
                    self.state.character, self.state.body
                )
                if artifact_body is not None:
                    self.state.body = artifact_body
                self.state.artifact_action_request = (
                    self.state.exploration_artifact_actions.recognizes(
                        self.state.character, self.state.body
                    )
                )
                gateway = activation(self.state.character, self.state.body)
            except ValueError as error:
                self.runtime.record(
                    event="seasonal_gateway_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                    original_opcode=12870,
                )
                from wakfu_server.ecology_feedback import information

                self.state.information = information

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(
                        self.artifact_failure_message(error)
                        if self.state.artifact_action_request
                        else str(error)
                    ),
                )
                return DispatchResult.CONTINUE
            if gateway is not None:
                self.runtime.record(
                    event="seasonal_gateway_activated",
                    actor_id=self.state.character["id"],
                    original_opcode=12870,
                    resolved_opcode=12296,
                    route_key=gateway["route_key"],
                    source_id=gateway["source_id"],
                    destination_map_id=gateway["destination_map_id"],
                )
                self.state.opcode, self.state.body = 12296, gateway["body"]
        if (
            self.state.opcode == 13429
            and self.state.paid_container_ticket is not None
            and len(self.state.body) == 3
            and struct.unpack_from(">h", self.state.body, 1)[0] in (13, 28)
        ):
            from wakfu_server import paid_containers

            self.state.paid_containers = paid_containers

            try:
                self.runtime.flush_positions(
                    account_id=self.state.account_id,
                    generation=self.state.generation,
                    character_id=self.state.character["id"],
                )
                self.state.result = self.state.paid_containers.finish(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.paid_container_ticket,
                    self.state.body,
                    loaded=self.state.loaded,
                    blocked=self.environment_blocked(allow_paid=True),
                    is_hero=self.environment_actor_is_hero(),
                )
                self.state.character = self.state.result["character"]
                self.state.paid_container_ticket = None
                for self.state.packet in self.state.result["packets"]:
                    if self.state.packet[0] == 12344:
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
                    event="paid_container_finished",
                    actor_id=self.state.character["id"],
                    state=self.state.result["state"],
                    replay=self.state.result["replay"],
                )
            except ValueError as error:
                from wakfu_server.ecology_feedback import information

                self.state.information = information

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(str(error)),
                )
                self.runtime.record(
                    event="paid_container_finish_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
            return DispatchResult.CONTINUE
        if (
            self.state.opcode == 13429
            and self.state.environment_seat is not None
            and len(self.state.body) == 3
        ):
            seat_phase, seat_occupation = struct.unpack(">Bh", self.state.body)
            if seat_occupation == 16:
                if seat_phase == 3:
                    self.cancel_environment()
                # Phase2 completes the sitting animation; occupancy remains.
                return DispatchResult.CONTINUE
        if self.state.flora_ticket is not None and self.state.opcode in (
            13331,
            13686,
            12296,
            13578,
            12247,
            13130,
            13220,
            13284,
            13481,
        ):
            self.cancel_flora()
        if (
            self.state.environment_ticket is not None
            or self.state.environment_seat is not None
            or self.state.paid_container_ticket is not None
            or self.state.pending_artifact_action is not None
        ) and self.state.opcode in (
            12117,
            13520,
            13241,
            13413,
            13331,
            13686,
            12296,
            13578,
            12247,
            13130,
            13220,
            13284,
            13481,
            12219,
            12006,
            12054,
        ):
            self.cancel_environment()
        if self.state.character is not None and self.state.opcode in (
            13686,
            12296,
            13578,
            12247,
        ):
            self.runtime.HARVESTS.cancel(
                self.state.character["id"], generation=self.state.generation
            )
            self.runtime.PLANTINGS.cancel(
                self.state.character["id"], self.state.generation
            )
        if (
            self.state.fight is not None
            and self.state.opcode
            in (
                13686,
                12296,
                13578,
                12247,
                13331,
                13434,
                12580,
                13210,
                13826,
                12870,
                12363,
            )
            and not self.native_exterior_rift_request()
        ):
            self.runtime.record(
                event="combat_world_action_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason="World action is unavailable during combat",
            )
            from wakfu_server.travel_storage_feedback import (
                blocked_world_rejection,
            )

            blocked_feedback = blocked_world_rejection(
                self.state.opcode, self.state.body
            )
            if blocked_feedback is not None:
                self.runtime.send(
                    self.state.connection, self.state.service, *blocked_feedback
                )
            return DispatchResult.CONTINUE
        # 14689 is an auxiliary request, not a mandatory world-ready
        # acknowledgement. A cached map after character switching can
        # omit it; the first world action must still join the session.
        if (
            self.state.selected
            and not self.state.loaded
            and self.state.opcode
            in (
                14689,
                13331,
                12366,
                13578,
                12772,
                12296,
                13686,
                12870,
                13220,
                13284,
                13481,
                1156,
                1031,
                1074,
                1066,
                13074,
                13224,
                13188,
                13831,
                13140,
                12997,
                13037,
                12510,
                12593,
                12203,
                12781,
                13406,
                12027,
                13113,
                784,
                657,
                672,
                799,
                12449,
                12787,
                13993,
                12294,
            )
        ):
            from wakfu_server import astrub_arrival_scene

            with self.runtime.POSITIONS.account_barrier(self.state.account_id):
                self.runtime.flush_positions(account_id=self.state.account_id)
                recovered_arrival = astrub_arrival_scene.recover_login(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                )
                if recovered_arrival is not None:
                    self.state.character = recovered_arrival[0]
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
            self.state.loaded = True
            self.publish_account_item_spells(seed=True)
            self.state.destination_route = self.runtime.transports.for_map(
                self.state.character["map_id"]
            )
            if self.state.destination_route:
                for (
                    self.state.message_id,
                    self.state.message_body,
                ) in self.runtime.transports.bootstrap(
                    self.state.character, self.state.destination_route
                ):
                    if (
                        recovered_arrival is not None
                        or self.state.opcode != 14689
                        or self.state.message_id != 13256
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            self.state.message_id,
                            self.state.message_body,
                        )
            elif self.state.character["map_id"] != 1134:
                for (
                    self.state.message_id,
                    self.state.message_body,
                ) in self.runtime.owned_native_bootstrap(self.state.character):
                    if (
                        recovered_arrival is not None
                        or self.state.opcode != 14689
                        or self.state.message_id != 13256
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            self.state.message_id,
                            self.state.message_body,
                        )
            else:
                self.runtime.replay(
                    self.state.connection,
                    119,
                    131,
                    self.state.account_id,
                    self.state.character,
                    generation=self.state.generation,
                )
            self.runtime.join_world(
                self.state.generation, self.state.connection, self.state.character
            )
            self.runtime.acknowledge_rift_login_bootstrap(
                self.state.account_id, self.state.generation, self.state.character
            )
            from wakfu_server import item_teleports

            recovered_travel = item_teleports.pending(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
            if recovered_travel is not None:
                item_teleports.acknowledge(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    recovered_travel["transition"]["token"],
                )
            from wakfu_server import haven_world_travel

            recovered_haven_world = haven_world_travel.pending(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
            if recovered_haven_world is not None:
                haven_world_travel.acknowledge(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    recovered_haven_world["transition"]["token"],
                )
            self.deliver_rift_transition()
            self.resume_settled_shared_combat()
            self.publish_custom_task_cards()
            if (
                self.state.character["map_id"] == 1465
                and self.state.fight is None
                and self.state.combat_session is None
            ):
                from wakfu_server import intro_cinematic

                self.state.intro_cinematic = intro_cinematic

                ogrest_id, actor_packet = self.state.intro_cinematic.ogrest_actor(
                    self.state.character["id"]
                )
                self.state.intro_cinematic_scene = (
                    self.state.intro_cinematic.IntroCinematic(ogrest_id)
                )
                self.runtime.send(
                    self.state.connection, self.state.service, *actor_packet
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.intro_cinematic_scene.start(),
                )
            if (
                self.state.character["map_id"] == 1361
                and self.state.fight is None
                and self.state.combat_session is None
            ):
                from wakfu_server.achievements import incarnam_tutorial, storage

                self.state.incarnam_tutorial = incarnam_tutorial
                self.state.storage = storage

                with self.runtime.STORE.connection() as self.state.db:
                    self.state.tutorial_state = self.state.storage.load_locked(
                        self.state.db, self.state.character["id"]
                    )
                    planting_seen = self.state.incarnam_tutorial.planting_guide_seen(
                        self.state.db, self.state.character["id"]
                    )
                for self.state.packet in self.state.incarnam_tutorial.initial_packets(
                    self.state.tutorial_state, planting_guide_seen=planting_seen
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
                walk_guide = self.state.incarnam_tutorial.resume_walk_guide(
                    self.state.character, self.state.tutorial_state
                )
                if walk_guide is not None:
                    self.runtime.send(
                        self.state.connection, self.state.service, *walk_guide
                    )
            if (
                self.state.character["map_id"] == 1385
                and self.state.fight is None
                and self.state.combat_session is None
            ):
                from wakfu_server import rii_scenario

                self.state.rii_scenario = rii_scenario
                from wakfu_server.achievements import (
                    storage as achievement_storage,
                )

                with self.runtime.STORE.connection() as rii_db:
                    rii_state = achievement_storage.load_locked(
                        rii_db, self.state.character["id"]
                    )
                    from wakfu_server import rii_zaap_scene

                    zaap_scene_packets = rii_zaap_scene.login_packets(
                        rii_db, self.state.character
                    )
                for event_packet in self.state.rii_scenario.login_packets(
                    self.state.character, rii_state
                ):
                    if event_packet == self.state.rii_scenario.packet(
                        self.state.rii_scenario.INTRO
                    ):
                        self.state.connection.pending_rii_intro = self.state.character[
                            "id"
                        ]
                    self.runtime.send(
                        self.state.connection, self.state.service, *event_packet
                    )
                if zaap_scene_packets:
                    self.state.connection.pending_rii_zaap_scene = self.state.character[
                        "id"
                    ]
                    self.runtime.send_batch(
                        self.state.connection, self.state.service, zaap_scene_packets
                    )
            if (
                self.state.character["map_id"] == astrub_arrival_scene.MAP_ID
                and self.state.fight is None
                and self.state.combat_session is None
            ):
                with self.runtime.STORE.connection() as arrival_db:
                    arrival_packets = astrub_arrival_scene.login_packets(
                        arrival_db, self.state.character
                    )
                if arrival_packets:
                    self.state.connection.pending_astrub_arrival = self.state.character[
                        "id"
                    ]
                    self.state.connection.pending_astrub_arrival_callback = 17029
                    self.runtime.send_batch(
                        self.state.connection, self.state.service, arrival_packets
                    )
            # Bootstrap can arrive before the client finishes loading its
            # scene. Initial login needs the same complete post-load replay
            # as map transitions, even when no movement request follows.
            self.mark_static_sync_pending()
            if (
                self.state.character["map_id"] == 1361
                and self.state.fight is None
                and self.state.combat_session is None
            ):
                from wakfu_server.achievements import incarnam_encounters

                self.state.incarnam_encounters = incarnam_encounters
                from wakfu_server.intro_cinematic import scenario_event

                self.state.scenario_event = scenario_event

                with self.runtime.STORE.connection() as self.state.tutorial_db:
                    ending_pending = self.state.incarnam_encounters.pending_final(
                        self.state.tutorial_db, self.state.character
                    )
                if ending_pending:
                    self.state.connection.pending_incarnam_outro = self.state.character[
                        "id"
                    ]
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.scenario_event(22359, 2500),
                    )
            if (
                self.state.character["map_id"] == 1387
                and self.state.fight is None
                and self.state.combat_session is None
            ):
                from wakfu_server.achievements import rii_guardian_battle

                self.state.rii_guardian_battle = rii_guardian_battle

                with self.runtime.STORE.connection() as self.state.guardian_db:
                    ending_pending = self.state.rii_guardian_battle.pending_cinematic(
                        self.state.guardian_db, self.state.character
                    )
                if ending_pending:
                    for (
                        self.state.packet
                    ) in self.state.rii_guardian_battle.cinematic_packets():
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            *self.state.packet,
                        )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                12436,
                self.runtime.health.packet(
                    self.state.character["id"],
                    self.state.character["hp"],
                    (
                        0
                        if self.state.fight is not None
                        or self.state.combat_session is not None
                        else self.runtime.health.exploration_coefficient(
                            self.state.character["max_hp"], self.state.character["hp"]
                        )
                    ),
                ),
            )
            self.runtime.record(
                event="world_bootstrap_sent", position=self.state.position
            )
        if (
            self.state.loaded
            and self.state.world_snapshot_pending
            and self.state.opcode
            in (
                13331,
                12366,
                13578,
                12772,
                12296,
                13686,
                12870,
                13220,
                13284,
                13481,
                1156,
                1031,
                1074,
                1066,
                13074,
                13224,
                13188,
                13831,
                13140,
                12997,
                13037,
                12510,
                12593,
                12203,
                12781,
                13406,
                12027,
                13113,
                784,
                657,
                672,
                799,
                12449,
                12787,
                13993,
                12294,
            )
        ):
            self.sync_loaded_world_snapshot(force=True)
        self.state.rift_start_run = None
        self.state.encounter_world_action = None
        if (
            self.state.opcode == 12197
            and self.state.loaded
            and self.runtime.COMBAT_TEST
        ):
            from wakfu_server.combat_party_prompt import (
                accepted_join_request,
            )

            try:
                accepted_body = accepted_join_request(self.state.body)
            except ValueError as error:
                self.runtime.record(
                    event="party_combat_answer_rejected", reason=str(error)
                )
                return DispatchResult.CONTINUE
            if accepted_body is None:
                return DispatchResult.CONTINUE
            # coK's boolean is acceptance; coU's boolean is autoLock.
            self.state.opcode, self.state.body = 13241, accepted_body
        if (
            self.state.opcode == 13175
            and self.state.loaded
            and self.state.character is not None
        ):
            from wakfu_server.achievements.service import tracking_request

            try:
                self.state.packets = tracking_request(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                    self.state.body,
                )
            except ValueError as error:
                self.runtime.record(
                    event="achievement_tracking_rejected", reason=str(error)
                )
                return DispatchResult.CONTINUE
            self.runtime.send_batch(
                self.state.connection, self.state.service, self.state.packets
            )
            return DispatchResult.CONTINUE
        return DispatchResult.FALLTHROUGH
