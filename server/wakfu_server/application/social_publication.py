"""Application domain helpers extracted from the World bootstrap."""

import struct


class SocialPublication:
    def __init__(self, runtime):
        self.runtime = runtime

    def publish_bot_chat(self, sender, text, *, recipient=None):
        if self.runtime.BOTS_BRIDGE is None:
            return
        try:
            self.runtime.BOTS_BRIDGE.runtime.observe_chat(
                sender, text, recipient=recipient
            )
        except Exception as error:
            # Bot observers cannot interrupt successful human chat delivery.
            self.runtime.record(
                event="bot_chat_observation_failed", reason=type(error).__name__
            )

    def deliver_bot_whisper(self, generation, character, recipient, text):
        delivered = self.runtime.WORLD.private_chat(
            generation,
            character["id"],
            character["account_id"],
            recipient,
            text,
            block_reason=self.runtime.SOCIAL_CONTACTS.private_chat_block_reason,
            valid_session=lambda entry: self.runtime.STORE.current_character_session(
                entry[2]["account_id"], entry[0], entry[2]["id"]
            ),
        )
        if not delivered:
            raise ValueError("Bot whisper recipient is unavailable")

    def guild_local_entity(self):
        captured = self.runtime.fixture(15548)
        if (
            len(captured) < 11
            or len(captured) != 10 + struct.unpack_from(">H", captured, 8)[0]
        ):
            raise ValueError("Invalid native guild synchronization fixture")
        return self.runtime.wire.minimal_entity(captured[10:], {"level": 1})

    def guild_company_packet(self, character, model):
        from wakfu_server.hero_wire import company
        from wakfu_server.nation_state import nation_id

        return company(
            character["account_id"],
            character["id"],
            guild_id=model["guildId"] if model else 0,
            nation_id=nation_id(character),
            company_snapshot=character["equipment_criterion_context"][
                "company_snapshot"
            ],
        )

    def refresh_guild(self, generation, character):
        from psycopg import Error as DatabaseError
        from psycopg_pool import PoolTimeout

        try:
            self.runtime.GUILDS.refresh(
                character["account_id"], generation, character["id"]
            )
        except (ValueError, DatabaseError, PoolTimeout) as error:
            self.runtime.record(
                event="guild_refresh_failed",
                actor_id=character["id"],
                reason=str(error),
            )

    def refresh_party(self, generation, character):
        """Social publication failures must not disconnect a playable character."""
        from psycopg import Error as DatabaseError
        from psycopg_pool import PoolTimeout

        try:
            self.runtime.PARTIES.refresh(
                character["account_id"], generation, character["id"]
            )
        except (ValueError, DatabaseError, PoolTimeout) as error:
            self.runtime.record(
                event="party_refresh_failed",
                actor_id=character["id"],
                reason=str(error),
            )
