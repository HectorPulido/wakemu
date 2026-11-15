"""Social operations for one lease-bound World session."""

import struct
import os
import time
from .dispatch_result import DispatchResult


class SocialSessionMixin:
    def handle_guild_request(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.runtime.GUILDS.handle(
                self.state.opcode,
                self.state.body,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
            self.runtime.GUILDS.drain_pending()
            self.state.live = self.runtime.WORLD.live_identity(
                character_id=self.state.character["id"]
            )
            if (
                self.state.live is not None
                and self.state.live[0] == self.state.generation
            ):
                for self.state.key in ("guild_native", "guild_moderation_factor"):
                    if self.state.key in self.state.live[1]:
                        self.state.character[self.state.key] = self.state.live[1][
                            self.state.key
                        ]
            if self.state.opcode in (13757, 12937, 12575):
                self.state.updated = self.runtime.STORE.character(
                    self.state.account_id, self.state.character["id"]
                )
                for self.state.key in (
                    "inventory_items",
                    "inventory_containers",
                    "guild_native",
                    "guild_moderation_factor",
                ):
                    if self.state.key in self.state.updated:
                        self.state.character[self.state.key] = self.state.updated[
                            self.state.key
                        ]
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.runtime.rich_inventory_packet(self.state.updated),
                )
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
                    13021,
                    struct.pack(
                        ">q", self.runtime.STORE.account_kamas(self.state.account_id)
                    ),
                )
        except (
            ValueError,
            UnicodeError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
            NotImplementedError,
        ) as error:
            self.state.text = (
                str(error)
                if isinstance(error, (ValueError, NotImplementedError))
                else "Guild service is temporarily unavailable."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="guild_request_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_chat_channel(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.state.request = self.runtime.decode_body(
                "out", self.state.opcode, self.state.body
            )
            self.state.now = time.monotonic()
            interval = self.runtime.CHANNELS.minimum_interval()
            if self.state.now - self.state.last_chat < interval:
                raise ValueError("Espera un momento antes de enviar otro mensaje.")
            self.state.last_chat = self.state.now
            self.state.delivered = self.runtime.CHANNELS.handle(
                self.state.opcode,
                self.state.request,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
            )
        except (
            ValueError,
            UnicodeError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
        ) as error:
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "El chat está temporalmente indisponible."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="channel_chat_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
        else:
            self.runtime.record(
                event="channel_chat",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                delivered=self.state.delivered,
            )
        return DispatchResult.FALLTHROUGH

    def handle_social_contact(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.state.packet = self.runtime.SOCIAL_ACTIONS.handle(
                self.state.opcode,
                self.state.body,
                self.state.account_id,
                self.state.generation,
            )
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
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "Los contactos están temporalmente indisponibles."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="social_request_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
        return DispatchResult.FALLTHROUGH

    def handle_exchange(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            self.runtime.EXCHANGES.handle(
                self.state.opcode,
                self.state.body,
                self.state.account_id,
                self.state.generation,
                self.state.character["id"],
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
                *self.state.information(self.state.failure_message("exchange", error)),
            )
            self.runtime.record(
                event="exchange_request_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
            )
        else:
            self.runtime.record(
                event="exchange_request",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
        return DispatchResult.FALLTHROUGH

    def handle_party(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.ecology_feedback import information

        self.state.information = information

        try:
            owned_hero_removal = False
            if self.state.opcode == 1074:
                from wakfu_server import party_wire
                from wakfu_server import heroes

                self.state.heroes = heroes

                self.state.request = party_wire.member_request(
                    self.state.body, allow_companions=True
                )
                if self.state.request["member_id"] < 0:
                    from wakfu_server import companions

                    self.state.companions = companions
                    from wakfu_server import hero_private_scene

                    self.state.hero_private_scene = hero_private_scene

                    self.state.hero_private_scene.authorize(
                        self.active_private_session(),
                        self.state.character,
                        self.state.generation,
                    )
                    with self.runtime.PARTIES._guard(self.state.character["id"]):
                        with self.runtime.STORE.connection() as self.state.companion_db:
                            self.state.selected = self.state.companion_db.execute(
                                "SELECT 1 FROM account_companion_slots s "
                                "JOIN player_party_members m ON m.character_id=s.owner_character_id "
                                "WHERE s.account_id=%s AND s.owner_character_id=%s "
                                "AND s.companion_id=%s AND m.party_id=%s",
                                (
                                    self.state.account_id,
                                    self.state.character["id"],
                                    -self.state.request["member_id"],
                                    self.state.request["group_id"],
                                ),
                            ).fetchone()
                        if self.state.selected is None:
                            raise ValueError(
                                "El compañero no pertenece a tu compañía actual"
                            )
                        self.state.companions.remove_from_party(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            -self.state.request["member_id"],
                        )
                        with self.runtime.STORE.connection() as self.state.companion_db:
                            recipients = self.state.companion_db.execute(
                                "SELECT character_id FROM player_party_members WHERE party_id=%s",
                                (self.state.request["group_id"],),
                            ).fetchall()
                        self.state.packet = party_wire.removed(
                            self.state.request["group_id"],
                            [self.state.request["member_id"]],
                            allow_companions=True,
                        )
                        for self.state.member in recipients:
                            self.state.live = self.runtime.WORLD.live_identity(
                                character_id=self.state.member["character_id"]
                            )
                            if self.state.live is not None:
                                self.runtime.WORLD.send_to(
                                    self.state.member["character_id"],
                                    self.state.live[0],
                                    *self.state.packet,
                                )
                        self.runtime.refresh_party(
                            self.state.generation, self.state.character
                        )
                    self.runtime.record(
                        event="companion_removed",
                        actor_id=self.state.character["id"],
                        companion_id=-self.state.request["member_id"],
                    )
                    return DispatchResult.CONTINUE
                with self.runtime.STORE.connection() as self.state.hero_db:
                    hero_slot = self.state.hero_db.execute(
                        "SELECT s.character_id FROM account_hero_slots s "
                        "JOIN player_party_members m ON m.character_id=%s "
                        "WHERE s.account_id=%s AND s.character_id=%s AND m.party_id=%s",
                        (
                            self.state.character["id"],
                            self.state.account_id,
                            self.state.request["member_id"],
                            self.state.request["group_id"],
                        ),
                    ).fetchone()
                if hero_slot is not None:
                    from wakfu_server import hero_private_scene

                    self.state.hero_private_scene = hero_private_scene

                    self.state.hero_private_scene.authorize(
                        self.active_private_session(),
                        self.state.character,
                        self.state.generation,
                    )
                    with self.runtime.PARTIES._guard(self.state.character["id"]):
                        with self.runtime.STORE.connection() as self.state.hero_db:
                            self.state.members = self.state.hero_db.execute(
                                "SELECT character_id FROM player_party_members "
                                "WHERE party_id=%s",
                                (self.state.request["group_id"],),
                            ).fetchall()
                        if self.state.character["id"] not in {
                            member["character_id"] for member in self.state.members
                        }:
                            raise ValueError("No perteneces a ese grupo.")
                        recipients = [
                            self.runtime.WORLD.live_identity(
                                character_id=member["character_id"]
                            )
                            for member in self.state.members
                        ]
                        with self.runtime.POSITIONS.account_barrier(
                            self.state.account_id
                        ):
                            self.runtime.flush_positions(
                                account_id=self.state.account_id
                            )
                            self.state.roster = self.state.heroes.remove(
                                self.runtime.STORE,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character["id"],
                                self.state.request["member_id"],
                            )
                        self.state.packet = party_wire.removed(
                            self.state.request["group_id"],
                            [self.state.request["member_id"]],
                        )
                        for self.state.live in recipients:
                            if self.state.live is not None:
                                self.runtime.WORLD.send_to(
                                    self.state.live[1]["id"],
                                    self.state.live[0],
                                    *self.state.packet,
                                )
                        self.publish_heroes(self.state.roster)
                    self.runtime.record(
                        event="hero_removed",
                        actor_id=self.state.character["id"],
                        hero_id=self.state.request["member_id"],
                        party_id=self.state.request["group_id"],
                    )
                    owned_hero_removal = True
            if not owned_hero_removal:
                self.runtime.PARTIES.handle(
                    self.state.opcode,
                    self.state.body,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
                if self.state.opcode == 1074:
                    self.runtime.refresh_party(
                        self.state.generation, self.state.character
                    )
        except (
            ValueError,
            UnicodeError,
            self.state.DatabaseError,
            self.state.PoolTimeout,
        ) as error:
            self.state.text = (
                str(error)
                if isinstance(error, ValueError)
                else "Le groupe est temporairement indisponible."
            )
            self.runtime.send(
                self.state.connection,
                self.state.service,
                *self.state.information(self.state.text),
            )
            self.runtime.record(
                event="party_request_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=type(error).__name__,
                sqlstate=getattr(error, "sqlstate", None),
                constraint=getattr(
                    getattr(error, "diag", None), "constraint_name", None
                ),
            )
        else:
            self.runtime.record(
                event="party_request",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
            )
        return DispatchResult.FALLTHROUGH

    def handle_private_chat(self):
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout

        self.state.request = self.runtime.decode_body(
            "out", self.state.opcode, self.state.body
        )
        self.state.text = self.state.request["text"].strip()
        self.state.now = time.monotonic()
        if (
            not self.state.text
            or len(self.state.text) > 512
            or self.state.now - self.state.last_chat < 0.2
        ):
            self.runtime.send(
                self.state.connection,
                self.state.service,
                349,
                self.runtime.wire.private_chat_error(140),
            )
            return DispatchResult.CONTINUE
        self.state.last_chat = self.state.now
        try:
            self.state.delivered = self.runtime.WORLD.private_chat(
                self.state.generation,
                self.state.character["id"],
                self.state.account_id,
                self.state.request["recipient"],
                self.state.text,
                block_reason=self.runtime.SOCIAL_CONTACTS.private_chat_block_reason,
                valid_session=lambda entry: self.runtime.STORE.current_character_session(
                    entry[2]["account_id"], entry[0], entry[2]["id"]
                ),
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
                349,
                self.runtime.wire.private_chat_error(140),
            )
            self.runtime.record(
                event="private_chat_rejected",
                actor_id=self.state.character["id"],
                reason=type(error).__name__,
            )
        else:
            if self.state.delivered:
                self.runtime.publish_bot_chat(
                    self.state.character,
                    self.state.text,
                    recipient=self.state.request["recipient"],
                )
            self.runtime.record(
                event="private_chat",
                actor_id=self.state.character["id"],
                delivered=self.state.delivered,
                characters=len(self.state.text),
            )
        return DispatchResult.FALLTHROUGH

    def handle_local_chat(self):
        self.state.text = self.runtime.decode_body(
            "out", self.state.opcode, self.state.body
        )["text"].strip()
        local_command = (
            self.state.text.split(None, 1)[0].lower() if self.state.text else ""
        )
        if local_command in ("!tasks", "!challenge", "!adventures"):
            self.execute_objectives_command(self.state.text)
            return DispatchResult.CONTINUE
        if local_command == "!nacion":
            from psycopg import Error as DatabaseError

            self.state.DatabaseError = DatabaseError
            from psycopg_pool import PoolTimeout

            self.state.PoolTimeout = PoolTimeout
            from wakfu_server import nation_state

            self.state.nation_state = nation_state
            from wakfu_server.ecology_feedback import information

            self.state.information = information

            try:
                self.state.nation_state.local_selection_request(self.state.text)
                if self.state.fight is not None:
                    raise ValueError("La inscripción requiere estar fuera de combate.")
                self.state.now = time.monotonic()
                if (
                    self.state.now - self.state.last_chat
                    < self.runtime.CHANNELS.minimum_interval()
                ):
                    raise ValueError("Espera un momento antes de enviar otro mensaje.")
                self.state.packet = self.state.nation_state.open_selection(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                )
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
                self.state.last_chat = self.state.now
            except (
                ValueError,
                UnicodeError,
                self.state.DatabaseError,
                self.state.PoolTimeout,
            ) as error:
                self.state.message = (
                    str(error)
                    if isinstance(error, ValueError)
                    else ("La selección de nación está temporalmente indisponible.")
                )
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    *self.state.information(self.state.message),
                )
                self.runtime.record(
                    event="nation_selection_rejected",
                    actor_id=self.state.character["id"],
                    reason=type(error).__name__,
                )
            return DispatchResult.CONTINUE
        if self.state.text.lower() in ("!exitdungeon", "!salirmazmorra"):
            self.execute_dungeon_exit_command()
            return DispatchResult.CONTINUE
        if (
            self.state.text.startswith("!")
            and os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
        ):
            try:
                self.execute_test_command(self.state.text)
            except (ValueError, PermissionError):
                pass  # Rejection was sent to the chat; keep the session alive.
            return DispatchResult.CONTINUE
        self.state.now = time.monotonic()
        if (
            self.state.text
            and len(self.state.text) <= 512
            and self.state.now - self.state.last_chat >= 0.2
        ):
            self.state.last_chat = self.state.now
            self.runtime.WORLD.broadcast(
                self.state.generation,
                self.state.character["id"],
                674,
                self.runtime.wire.chat(self.state.character, self.state.text),
            )
            self.runtime.publish_bot_chat(self.state.character, self.state.text)
            self.runtime.record(
                event="chat",
                actor_id=self.state.character["id"],
                characters=len(self.state.text),
            )
        return DispatchResult.FALLTHROUGH
