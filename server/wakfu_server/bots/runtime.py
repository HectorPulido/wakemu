"""Headless character leases and validated game actions; no bot decisions."""
import threading
import time
import re

from .repository import (
    BotsRepository,
    public_character,
    validate_bot_id,
    validate_capabilities,
)


class BotPeer:
    """A World peer without a native game socket or a second protocol engine."""

    is_bot_peer = True

    def __init__(self, bot_id):
        self.trace_id = "bot:" + bot_id
        self.closed = False
        self.write_lock = threading.RLock()

    def sendall(self, data):
        if self.closed:
            raise OSError("Bot peer is closed")

    def shutdown(self, how):
        self.closed = True


def exchange_event(row, *, bot_kamas=None):
    """Project a durable exchange outbox row into the public bot contract."""
    source = row["payload"]
    state = source["state"]
    payload = dict(
        exchange_id=row["exchange_id"],
        revision=row["revision"],
        delivery_id=row["id"],
        state=state,
        bot_character_id=row["character_id"],
        inviter_id=source["inviter_id"],
        invitee_id=source["invitee_id"],
        members=[
            {
                key: member.get(key)
                for key in ("character_id", "offered_kamas", "confirmed_revision")
            }
            for member in source.get("members", [])
        ],
        items=[
            dict(
                character_id=item["character_id"],
                uid=item["uid"],
                reference=item.get("unit", {}).get("reference"),
                quantity=item["quantity"],
            )
            for item in source.get("items", [])
        ],
    )
    if bot_kamas is not None:
        if type(bot_kamas) is not int or not 0 <= bot_kamas < 2**63:
            raise ValueError("Invalid bot account balance")
        payload["bot_kamas"] = bot_kamas
    if state == "invitation":
        kind = "exchange.invited"
    elif state == "active":
        kind = "exchange.updated"
    else:
        kind = "exchange.closed"
    return dict(type=kind, payload=payload)


class BotsRuntime:
    supported_actions = (
        "create",
        "configure",
        "activate",
        "deactivate",
        "say",
        "whisper",
        "exchange.accept",
        "exchange.cancel",
        "exchange.offer_kamas",
        "exchange.ready",
    )

    def __init__(
        self,
        store,
        world,
        exchanges,
        positions,
        *,
        say,
        emit,
        whisper=None,
        repository=None,
        clock=time.monotonic
    ):
        self.store, self.world, self.exchanges, self.positions = (
            store,
            world,
            exchanges,
            positions,
        )
        self.repository = (
            repository if repository is not None else BotsRepository(store)
        )
        self.say, self.emit, self.clock = say, emit, clock
        self.whisper = whisper
        self.lock = threading.RLock()
        self.active = {}
        self.last_chat = {}

    def execute(self, bot_id, action, args):
        validate_bot_id(bot_id)
        if not isinstance(args, dict) or not isinstance(action, str):
            raise ValueError("Invalid bot action")
        with self.lock:
            if action == "create":
                row = self.repository.create(bot_id, args)
                return self._summary(row)
            row = self.repository.get(bot_id)
            if action == "configure":
                if set(args) != {"capabilities"}:
                    raise ValueError("Only bot capabilities can be configured")
                validate_capabilities(args["capabilities"])
                if bot_id in self.active:
                    from .bridge import BotConflict

                    raise BotConflict("bot_is_active")
                row = self.repository.configure(bot_id, args["capabilities"])
                return self._summary(row)
            if action == "activate":
                if args:
                    raise ValueError("Activation takes no arguments")
                return self._activate(row)
            if action == "deactivate":
                if args:
                    raise ValueError("Deactivation takes no arguments")
                self._deactivate(bot_id)
                return self._summary(row)
            lease = self._lease(bot_id)
            if action in ("say", "whisper"):
                self._require(row, "chat")
                fields = {"text", "recipient"} if action == "whisper" else {"text"}
                if set(args) != fields or not isinstance(args["text"], str):
                    raise ValueError("Invalid bot chat message")
                if action == "whisper" and (
                    self.whisper is None
                    or not isinstance(args["recipient"], str)
                    or not 3 <= len(args["recipient"]) <= 24
                    or "\x00" in args["recipient"]
                ):
                    raise ValueError("Invalid bot private chat recipient")
                text = args["text"].strip()
                if (
                    not text
                    or "\x00" in text
                    or len(text.encode("utf-8")) > 1024
                    or text.startswith("!")
                ):
                    raise ValueError("Invalid bot chat message")
                now = self.clock()
                if now - self.last_chat.get(bot_id, float("-inf")) < 1:
                    raise ValueError("Bot chat is rate limited")
                character = self.world.live_identity(character_id=row["character_id"])
                if character is None or character[0] != lease["generation"]:
                    raise ValueError("Bot is no longer in World")
                if action == "whisper":
                    self.whisper(
                        lease["generation"], character[1], args["recipient"], text
                    )
                else:
                    self.say(lease["generation"], character[1], text)
                self.last_chat[bot_id] = now
                return dict(spoken=True)
            if action.startswith("exchange."):
                self._require(row, "exchange")
                result = self.exchanges.bot_command(
                    action,
                    args,
                    row["account_id"],
                    lease["generation"],
                    row["character_id"],
                )
                return {key: result[key] for key in ("id", "state", "revision")}
            raise ValueError("Unsupported bot action")

    @staticmethod
    def _require(row, capability):
        if capability not in row["capabilities"]:
            raise PermissionError("Bot lacks required capability")

    def _lease(self, bot_id):
        lease = self.active.get(bot_id)
        if lease is None or not self.store.current_character_session(
            lease["account_id"], lease["generation"], lease["character_id"]
        ):
            raise ValueError("Bot is not active")
        return lease

    def _summary(self, row):
        character = self.store.character(row["account_id"], row["character_id"])
        return dict(
            bot_id=row["bot_id"],
            account_id=row["account_id"],
            character_id=row["character_id"],
            capabilities=list(row["capabilities"]),
            active=row["bot_id"] in self.active,
            character=public_character(character),
        )

    def _activate(self, row):
        bot_id = row["bot_id"]
        if bot_id in self.active:
            previous = self.active[bot_id]
            if self.store.current_character_session(
                previous["account_id"], previous["generation"], previous["character_id"]
            ):
                return self._summary(row)
            self._deactivate(bot_id)
        generation = self.store.begin_session(row["account_id"])
        peer = BotPeer(bot_id)
        attached = False
        try:
            character = self.store.select_character(
                row["account_id"], generation, row["character_id"]
            )
            self.positions.attach(row["account_id"], generation, character)
            attached = True
            self.active[bot_id] = dict(row, generation=generation, peer=peer)
            self.world.join(generation, peer, character)
            # Bot presence must not keep player-driven ecology jobs running.
            self.world.deactivate_ecology(row["character_id"], generation)
        except BaseException:
            self.active.pop(bot_id, None)
            self.world.leave(row["character_id"], generation)
            if attached:
                self.positions.release(
                    row["account_id"], generation, row["character_id"]
                )
            self.store.end_session(row["account_id"], generation)
            peer.shutdown(2)
            raise
        return self._summary(row)

    def _deactivate(self, bot_id):
        lease = self.active.get(bot_id)
        if lease is None:
            return
        account, generation, character = (
            lease["account_id"],
            lease["generation"],
            lease["character_id"],
        )
        current = self.store.current_character_session(account, generation, character)
        if current:
            with self.store.connection() as db:
                pending = db.execute(
                    "SELECT exchange_id FROM player_exchange_members WHERE character_id=%s",
                    (character,),
                ).fetchall()
            for row in pending:
                self.exchanges.bot_command(
                    "exchange.cancel",
                    {"exchange_id": row["exchange_id"]},
                    account,
                    generation,
                    character,
                )
            self.positions.flush(
                account_id=account, generation=generation, character_id=character
            )
        self.world.leave(character, generation)
        self.positions.release(
            account, generation, character, discard_stale=not current
        )
        if current:
            self.store.clear_character(account, generation)
        self.store.end_session(account, generation)
        lease["peer"].shutdown(2)
        self.active.pop(bot_id, None)
        self.last_chat.pop(bot_id, None)

    def heartbeat(self):
        with self.lock:
            errors = []
            for bot_id, lease in tuple(self.active.items()):
                try:
                    if not self.store.heartbeat(
                        lease["account_id"], lease["generation"]
                    ):
                        self._deactivate(bot_id)
                except Exception as error:
                    errors.append(error)
            if errors:
                raise errors[0]

    def deactivate_all(self):
        with self.lock:
            errors = []
            for bot_id in tuple(self.active):
                try:
                    self._deactivate(bot_id)
                except Exception as error:
                    errors.append(error)
            if errors:
                raise errors[0]

    def handle_exchange(self, row):
        # Exchanges owns its per-exchange lock here. Do not acquire the runtime
        # lock: bot commands hold runtime -> exchange and must not deadlock.
        lease = next(
            (
                entry
                for entry in tuple(self.active.values())
                if entry["character_id"] == row["character_id"]
                and entry["generation"] == row["generation"]
            ),
            None,
        )
        if lease is None:
            return False
        event = exchange_event(
            row, bot_kamas=self.store.account_kamas(lease["account_id"])
        )
        self.emit(lease["bot_id"], event["type"], event["payload"])
        return True

    def observe_chat(self, sender, text, recipient=None):
        """Publish explicitly addressed messages without deciding any reply."""
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text.encode("utf-8")) > 2048
        ):
            return
        leases = tuple(self.active.values())
        if any(lease["character_id"] == sender.get("id") for lease in leases):
            return
        for lease in leases:
            if "chat" not in lease["capabilities"]:
                continue
            current = self.world.live_identity(character_id=lease["character_id"])
            if current is None or current[0] != lease["generation"]:
                continue
            character = current[1]
            if recipient is not None:
                addressed = (
                    recipient == character["id"]
                    or isinstance(recipient, str)
                    and recipient.casefold() == character["name"].casefold()
                )
            else:
                addressed = (
                    self.world.location(sender) == self.world.location(character)
                    and re.search(
                        r"(?<!\w)@" + re.escape(character["name"]) + r"(?![A-Za-z])",
                        text,
                        re.IGNORECASE,
                    )
                    is not None
                )
            if addressed:
                self.emit(
                    lease["bot_id"],
                    "chat.message",
                    dict(
                        sender_id=sender["id"],
                        sender_name=sender["name"],
                        text=text.strip(),
                        channel="private" if recipient is not None else "local",
                        addressed=True,
                    ),
                )

    def snapshot(self):
        with self.lock:
            result = []
            for row in self.repository.list():
                value = self._summary(row)
                value["pending_events"] = []
                lease = self.active.get(row["bot_id"])
                if lease is not None:
                    with self.store.connection() as db:
                        pending = db.execute(
                            "SELECT DISTINCT ON (o.exchange_id) o.* FROM player_exchange_outbox o "
                            "JOIN player_exchanges e ON e.id=o.exchange_id "
                            "WHERE o.character_id=%s AND o.generation=%s AND o.revision=e.revision "
                            "AND e.state IN ('invitation','active') "
                            "ORDER BY o.exchange_id,o.delivery_sequence DESC,o.id DESC",
                            (row["character_id"], lease["generation"]),
                        ).fetchall()
                    balance = self.store.account_kamas(row["account_id"])
                    value["pending_events"] = [
                        exchange_event(dict(event), bot_kamas=balance)
                        for event in pending
                    ]
                result.append(value)
            return result
