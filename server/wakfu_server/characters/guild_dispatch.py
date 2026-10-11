"""Session-bound native guild request routing and full-state publication.

No socket write occurs inside a database transaction. Unknown shared-storage
contexts and unverified native requests never gain guild authority here.
"""
import hashlib
import threading
import time
from contextlib import contextmanager

from . import guild_model, guild_wire
from .guild_service import GuildService


REQUEST_OPCODES = guild_wire.REQUEST_OPCODES | frozenset((15877,))


class Guilds:
    def __init__(
        self,
        store,
        world,
        local_entity,
        *,
        service=None,
        remote_publish=None,
        company_packet=None
    ):
        self.store = store
        self.world = world
        self.service = service or GuildService(store)
        self.local_entity = local_entity
        self.remote_publish = remote_publish
        self.company_packet = company_packet
        self.locks = [threading.RLock() for _ in range(256)]
        self.chat_times = [None] * 4096

    def _identity(self, account, generation, character):
        live = self.world.live_identity(character_id=character)
        if live is None or live[0] != generation or live[1]["account_id"] != account:
            raise ValueError("Guild sender session is stale")
        return live[1]

    def _key(self, character):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT guild_id FROM guild_members WHERE character_id=%s", (character,)
            ).fetchone()
        return ("guild", row["guild_id"]) if row else ("character", character)

    @contextmanager
    def _guard(self, character):
        while True:
            key = self._key(character)
            lock = self.locks[hash(key) % len(self.locks)]
            lock.acquire()
            try:
                if self._key(character) == key:
                    break
            except BaseException:
                lock.release()
                raise
            lock.release()
        try:
            yield
        finally:
            lock.release()

    def _packet(self, character, snapshot):
        from .nation_state import nation_id, synchro
        import struct

        entity = guild_wire.replace_local_entity(
            self.local_entity(),
            guild_model.native_model(snapshot),
            guild_model.moderation_factor(snapshot),
        )
        live = self.world.live_identity(character_id=character)
        if live is None:
            raise ValueError("Guild actor session is stale")
        entity = (
            entity[:1]
            + struct.pack(">i", nation_id(live[1]))
            + synchro(live[1])
            + entity[32:]
        )
        return guild_wire.local_actor_update(character, entity)

    def refresh(self, account, generation, character):
        """Reconnect uses a fresh snapshot, never historic outbox payloads."""
        if not self.service.native_enabled():
            return False
        self.drain_pending()
        self._identity(account, generation, character)
        with self._guard(character):
            snapshot = self.service.snapshot(account, generation, character)
            self._projection(character, generation, snapshot)
            return self.world.send_to(
                character, generation, *self._packet(character, snapshot)
            )

    def _projection(self, character, generation, snapshot):
        model = guild_model.native_model(snapshot)
        self.world.set_guild_projection(
            character, generation, model, guild_model.moderation_factor(snapshot)
        )
        if self.company_packet is not None:
            live = self.world.live_identity(character_id=character)
            if live is not None and live[0] == generation:
                self.world.send_to(
                    character, generation, *self.company_packet(live[1], model)
                )
        if self.remote_publish is not None:
            live = self.world.live_identity(character_id=character)
            if live is not None and live[0] == generation:
                from .nation_state import nation_id, synchro

                packet = guild_wire.remote_actor_update(
                    character,
                    model["guildId"] if model else 0,
                    model["blazon"] if model else 0,
                    model["level"] if model else 0,
                    model["name"] if model else "",
                    nation_id=nation_id(live[1]),
                    nation_synchro=synchro(live[1]),
                )
                self.remote_publish(live[1], packet)

    def _publish(self, previous, current, actor):
        identities = {actor} if actor is not None else set()
        for snapshot in (previous, current):
            if snapshot is not None:
                identities.update(row["character_id"] for row in snapshot["members"])
        delivered = 0
        failed = False
        for identity in sorted(identities):
            live = self.world.live_identity(character_id=identity)
            if live is None:
                continue
            generation, character = live
            # Removed members receive an empty model. Read under their own
            # current session rather than reusing another member's authority.
            snapshot = self.service.snapshot(
                character["account_id"], generation, identity
            )
            self._projection(identity, generation, snapshot)
            sent = self.world.send_to(
                identity, generation, *self._packet(identity, snapshot)
            )
            delivered += bool(sent)
            failed |= not sent
        from .guild_chest_dispatch import GuildChestSession

        guild_ids = {
            snapshot["guild"]["id"]
            for snapshot in (previous, current)
            if snapshot is not None and "guild" in snapshot
        }
        for guild_id in sorted(guild_ids):
            GuildChestSession.refresh_guild(guild_id)
        if failed:
            raise ValueError("Guild changes are committed; synchronization is pending")
        return delivered

    def drain_pending(self, *, limit=64):
        """Retry committed changes using current models and current leases."""
        from .guild_outbox import drain

        if not self.service.native_enabled():
            return 0

        def publish(guild_id, revision, affected):
            with self.locks[hash(("guild", guild_id)) % len(self.locks)]:
                with self.store.connection() as db:
                    row = db.execute(
                        "SELECT id FROM guilds WHERE id=%s FOR UPDATE", (guild_id,)
                    ).fetchone()
                    if row is None:
                        return
                    snapshot = self.service._snapshot(db, guild_id)
                previous = {
                    "members": [dict(character_id=identity) for identity in affected]
                }
                self._publish(previous, snapshot, None)

        return drain(self.store, publish, limit=limit)

    def handle(self, opcode, body, account, generation, character):
        self._identity(account, generation, character)
        if not self.service.native_enabled():
            raise ValueError("Guild system is disabled")
        if opcode == 15877:
            if body:
                raise ValueError("Guild management request must be empty")
            return self.refresh(account, generation, character)
        request = guild_wire.decode_request(opcode, body)
        with self._guard(character):
            previous = self.service.snapshot(account, generation, character)
            args = (account, generation, character)
            key = (
                "native-guild:"
                + generation
                + ":"
                + hashlib.sha256(opcode.to_bytes(2, "big") + body).hexdigest()
            )
            if opcode == 13757:
                current = self.service.create(
                    *args,
                    request["name"],
                    request["blazon"],
                    request["best_rank_name"],
                    request["worst_rank_name"],
                    operation_key=key,
                )
            elif opcode == 15194:
                current = self.service.rank_create(
                    *args, request["name"], request["authorizations"]
                )
            elif opcode == 14088:
                current = self.service.rank_remove(*args, request["rank_id"])
            elif opcode == 14815:
                current = self.service.rank_edit(
                    *args,
                    request["rank_id"],
                    request["name"],
                    request["authorizations"],
                )
            elif opcode == 15429:
                current = self.service.rank_move(
                    *args, request["rank_id"], request["position"]
                )
            elif opcode == 15627:
                current = self.service.remove_member(*args, request["character_id"])
            elif opcode == 14230:
                current = self.service.member_rank(
                    *args, request["character_id"], request["rank_id"]
                )
            elif opcode == 15481:
                current = self.service.dissolve(*args)
            elif opcode in (15511, 14890):
                current = self.service.metadata_set(
                    *args,
                    "description" if opcode == 15511 else "message",
                    request["text"],
                )
            elif opcode == 15542:
                invitation = self.service.invite(*args, request["name"])
                notice = guild_wire.invitation_notice(
                    invitation["inviter_name"], invitation["guild_name"]
                )
                self.world.send_to(
                    invitation["target_id"], invitation["target_generation"], *notice
                )
                return invitation
            elif opcode == 14995:
                current = self.service.respond_invitation(*args, request["accepted"])
            elif opcode in (15613, 14447):
                from . import guild_economy

                if previous is None:
                    raise ValueError("Character is not a guild member")
                guild_economy.bonus_operation(
                    self.store,
                    *args,
                    previous["guild"]["id"],
                    request["bonus_id"],
                    activate=opcode == 14447,
                    operation_key=key,
                )
                current = self.service.snapshot(*args)
            elif opcode in (12937, 12575):
                field = "name" if opcode == 12937 else "blazon"
                current = self.service.change_identity(
                    *args, field, request[field], operation_key=key
                )
            elif opcode == 13744:
                return self.chat(*args, request)
            else:
                raise ValueError("Guild request contract is not integrated")
            self._publish(previous, current, character)
            if opcode == 13757:
                self.world.send_to(
                    character,
                    generation,
                    *guild_wire.creation_ack(current["guild"]["name"]),
                )
            return current

    def chat(self, account, generation, character, request):
        """Native NV/743 goes only to current members, across map boundaries."""
        from wakfu_server.chat_channels import payload

        text = request["text"]
        if type(text) is not str or not text.strip() or "\x00" in text:
            raise ValueError("Invalid guild chat text")
        text = text.strip()
        recipients = []
        with self.store.connection() as db:
            self.service._start(db, account, generation, character)
            guild = self.service._guild(db, character)
            if request["guild_id"] != guild["id"]:
                raise ValueError("Guild chat identity does not match membership")
            row = db.execute(
                "SELECT value FROM settings WHERE name='chat_channel_policy'"
            ).fetchone()
            policy = row["value"] if row else {}
            maximum = policy.get("maximum_bytes")
            interval = policy.get("minimum_interval_ms")
            if (
                type(maximum) is not int
                or not 1 <= maximum <= 2048
                or type(interval) is not int
                or not 1 <= interval <= 60000
            ):
                raise ValueError("Invalid guild chat policy")
            if len(text.encode("utf-8")) > maximum:
                raise ValueError("Guild chat message is too long")
            now = time.monotonic()
            slot = character % len(self.chat_times)
            previous = self.chat_times[slot]
            if (
                previous is not None
                and previous[0] == character
                and now - previous[1] < interval / 1000
            ):
                raise ValueError("Guild chat rate limit exceeded")
            sender = db.execute(
                "SELECT c.name,p.language_mask,p.community FROM characters c "
                "JOIN account_chat_preferences p ON p.account_id=c.account_id WHERE c.id=%s",
                (character,),
            ).fetchone()
            if sender is None:
                sender = dict(
                    name=self._identity(account, generation, character)["name"],
                    language_mask=policy["language_mask"],
                    community=policy["community"],
                )
            body = payload(
                account,
                sender,
                text,
                language_mask=sender["language_mask"],
                community=sender["community"],
            )
            for row in db.execute(
                "SELECT m.character_id,c.account_id,s.generation FROM guild_members m "
                "JOIN characters c ON c.id=m.character_id AND c.deleted_at IS NULL "
                "JOIN sessions s ON s.account_id=c.account_id AND s.character_id=c.id "
                "WHERE m.guild_id=%s AND s.expires_at>%s",
                (guild["id"], self.store.now()),
            ):
                live = self.world.live_identity(character_id=row["character_id"])
                if (
                    live is not None
                    and live[0] == row["generation"]
                    and live[1]["account_id"] == row["account_id"]
                ):
                    recipients.append((row["character_id"], row["generation"]))
        self.chat_times[slot] = (character, now)
        return sum(
            bool(self.world.send_to(identity, lease, 743, body))
            for identity, lease in recipients
        )
