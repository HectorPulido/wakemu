"""Durable independent bot work queues and external behavior scheduling."""
import hashlib
import json
import logging
import threading
import time
from pathlib import Path

from .behaviors import BehaviorRegistry
from .clients import RemoteError
from .config import atomic_json

LOG = logging.getLogger(__name__)
MAX_PENDING = 2048


class Worker:
    def __init__(
        self,
        profiles,
        world,
        *,
        shop=None,
        llm=None,
        state_path,
        registry=None,
        clock=time.time,
    ):
        self.profiles, self.world, self.shop, self.llm = profiles, world, shop, llm
        self.state_path, self.registry, self.clock = (
            Path(state_path),
            registry or BehaviorRegistry(),
            clock,
        )
        self.lock, self.stop = threading.RLock(), threading.Event()
        self.state = {
            "world_epoch": None,
            "cursor": 0,
            "announcements": {},
            "pending": [],
            "recover_exchanges": False,
        }
        self.status = {
            "connected": False,
            "last_success": None,
            "last_error": None,
            "bot_errors": {},
        }
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text())
            if (
                not isinstance(state, dict)
                or set(state)
                - {
                    "world_epoch",
                    "cursor",
                    "announcements",
                    "pending",
                    "recover_exchanges",
                }
                or type(state.get("cursor")) is not int
                or state["cursor"] < 0
                or not isinstance(state.get("announcements"), dict)
                or not isinstance(state.get("pending", []), list)
                or len(state.get("pending", [])) > MAX_PENDING
            ):
                raise ValueError("Invalid bot worker checkpoint")
            self.state = dict(
                state,
                pending=state.get("pending", []),
                recover_exchanges=state.get("recover_exchanges", False),
            )

    def checkpoint(self):
        atomic_json(self.state_path, self.state)

    def request_id(self, source, bot_id, suffix):
        value = f"{self.state['world_epoch']}:{source}:{bot_id}:{suffix}"
        return hashlib.sha256(value.encode()).hexdigest()

    def enqueue(self, event):
        key = (event["bot_id"], event["id"])
        if any(
            (entry["event"]["bot_id"], entry["event"]["id"]) == key
            for entry in self.state["pending"]
        ):
            return True
        if len(self.state["pending"]) >= MAX_PENDING:
            return False
        self.state["pending"].append(
            dict(
                event=event,
                actions=None,
                attempts=0,
                next_retry=0,
                error=None,
                queued_at=self.clock(),
            )
        )
        return True

    def recover(self, profiles, snapshot, *, advance_cursor=True, attempt=None):
        pending = snapshot.get("pending_events", [])
        if not isinstance(pending, list) or len(pending) > MAX_PENDING:
            raise ValueError("Invalid pending bot events")
        cursor = snapshot.get("cursor")
        if type(cursor) is not int or cursor < 0:
            raise ValueError("Invalid World snapshot cursor")
        for event in pending:
            profile = profiles.get(event["bot_id"])
            if profile is not None and profile["enabled"]:
                source = hashlib.sha256(
                    json.dumps(event, sort_keys=True).encode()
                ).hexdigest()
                if attempt is not None:
                    source += "-" + str(attempt)
                if not self.enqueue(dict(event, id="recovery-" + source)):
                    raise RuntimeError("Bot recovery capacity reached")
        if advance_cursor:
            self.state["cursor"] = cursor
        self.checkpoint()

    def execute(self, profile, entry):
        event = entry["event"]
        if entry["actions"] is None:
            actions = self.registry.decide(profile, event, shop=self.shop, llm=self.llm)
            # Persist both the selected action and its original issue time BEFORE
            # sending. A retry after a crash never invents a new quote or reply.
            entry["actions"] = [
                dict(
                    action=action,
                    args=args,
                    request_id=self.request_id(event["id"], profile["bot_id"], index),
                    issued_at=self.clock(),
                    done=False,
                )
                for index, (action, args) in enumerate(actions)
            ]
            self.checkpoint()
        for action in entry["actions"]:
            if action["done"]:
                continue
            if self.clock() - action["issued_at"] > 300:
                # An expired speech must not be sent again after World's dedup
                # receipt expires. Exchange recovery uses current SQL snapshots.
                entry["error"] = "command_expired"
                if action["action"].startswith("exchange."):
                    self.state["recover_exchanges"] = True
                return True
            try:
                self.world.command(
                    profile["bot_id"],
                    action["action"],
                    action["args"],
                    action["request_id"],
                    issued_at=action["issued_at"],
                )
            except RemoteError as error:
                if error.status != 409 or error.code not in {
                    "exchange_revision_changed",
                    "exchange_revision_stale",
                    "exchange_closed",
                    "command_expired",
                }:
                    raise
                if error.code == "command_expired" and action["action"].startswith(
                    "exchange."
                ):
                    self.state["recover_exchanges"] = True
            action["done"] = True
            self.checkpoint()
        return True

    def process_pending(self, profiles):
        blocked, completed, errors = set(), [], {}
        # LLM failures cannot hold up deterministic buyers and announcements.
        queue = sorted(
            self.state["pending"],
            key=lambda entry: "llm"
            in profiles.get(entry["event"]["bot_id"], {}).get("behaviors", {}),
        )
        for entry in queue:
            bot_id = entry["event"]["bot_id"]
            profile = profiles.get(bot_id)
            if profile is None or not profile["enabled"]:
                completed.append(entry)
                continue
            if (
                entry["event"]["type"]
                not in {"exchange.invited", "exchange.updated", "exchange.closed"}
                and self.clock() - entry["queued_at"] > 300
            ):
                completed.append(entry)
                errors[bot_id] = "event_expired"
                continue
            if bot_id in blocked:
                continue
            if self.clock() < entry["next_retry"]:
                blocked.add(bot_id)
                errors[bot_id] = entry["error"]
                continue
            try:
                if self.execute(profile, entry):
                    completed.append(entry)
                    if entry["error"]:
                        errors[bot_id] = entry["error"]
            except Exception as error:
                entry["attempts"] += 1
                entry["next_retry"] = self.clock() + min(
                    30, 2 ** min(entry["attempts"], 5)
                )
                entry["error"] = type(error).__name__
                errors[bot_id] = entry["error"]
                blocked.add(bot_id)
                self.checkpoint()
        self.state["pending"] = [
            entry for entry in self.state["pending"] if entry not in completed
        ]
        self.checkpoint()
        return errors

    def reconcile(self, profiles, snapshot):
        bots, errors = {bot["bot_id"]: bot for bot in snapshot["bots"]}, {}
        for bot_id, profile in profiles.items():
            try:
                bot = bots.get(bot_id)
                digest = hashlib.sha256(
                    json.dumps(profile, sort_keys=True).encode()
                ).hexdigest()[:16]
                if bot is None and profile["enabled"]:
                    args = dict(
                        profile["character"],
                        capabilities=self.registry.world_capabilities(profile),
                    )
                    self.world.command(
                        bot_id,
                        "create",
                        args,
                        self.request_id("profile", bot_id, "create-" + digest),
                    )
                    bot = {"active": False}
                elif bot is not None:
                    identity = bot.get("character", {})
                    if any(
                        key in identity and identity[key] != profile["character"][key]
                        for key in ("name", "breed", "sex")
                    ):
                        errors[bot_id] = "character_identity_is_immutable"
                        continue
                    desired = self.registry.world_capabilities(profile)
                    if sorted(bot.get("capabilities", desired)) != desired:
                        if bot["active"]:
                            self.world.command(
                                bot_id,
                                "deactivate",
                                {},
                                self.request_id(
                                    "profile",
                                    bot_id,
                                    "configure-stop-" + str(time.time_ns()),
                                ),
                            )
                            bot = dict(bot, active=False)
                        self.world.command(
                            bot_id,
                            "configure",
                            {"capabilities": desired},
                            self.request_id(
                                "profile", bot_id, "configure-" + str(time.time_ns())
                            ),
                        )
                if profile["enabled"] and bot is not None and not bot["active"]:
                    self.world.command(
                        bot_id,
                        "activate",
                        {},
                        self.request_id(
                            "profile", bot_id, "activate-" + str(time.time_ns())
                        ),
                    )
                elif not profile["enabled"] and bot is not None and bot["active"]:
                    self.world.command(
                        bot_id,
                        "deactivate",
                        {},
                        self.request_id(
                            "profile", bot_id, "deactivate-" + str(time.time_ns())
                        ),
                    )
            except Exception as error:
                errors[bot_id] = type(error).__name__
        for bot_id, bot in bots.items():
            if bot_id not in profiles and bot["active"]:
                try:
                    self.world.command(
                        bot_id,
                        "deactivate",
                        {},
                        self.request_id(
                            "profile", bot_id, "removed-" + str(time.time_ns())
                        ),
                    )
                except Exception as error:
                    errors[bot_id] = type(error).__name__
        return errors

    def tick(self):
        with self.lock:
            profiles = self.profiles.snapshot()
            snapshot = self.world.snapshot()
            epoch = snapshot.get("world_epoch")
            if not isinstance(epoch, str) or not epoch:
                raise ValueError("Invalid World snapshot epoch")
            if epoch != self.state["world_epoch"]:
                previous_state = self.state
                self.state = {
                    "world_epoch": epoch,
                    "cursor": 0,
                    "announcements": {},
                    "pending": [],
                    "recover_exchanges": False,
                }
                try:
                    self.recover(profiles, snapshot)
                except Exception:
                    self.state = previous_state
                    raise
            if self.state["recover_exchanges"]:
                # A fresh SQL snapshot is the only authority for replacing an
                # expired monetary intent. Keep the event cursor so concurrent
                # chats and other bot events remain replayable.
                self.recover(
                    profiles,
                    snapshot,
                    advance_cursor=False,
                    attempt=int(self.clock() // 300),
                )
                self.state["recover_exchanges"] = False
                self.checkpoint()
            errors = self.reconcile(profiles, snapshot)
            try:
                result = self.world.events(self.state["cursor"])
            except RemoteError as error:
                if error.status != 409 or error.code != "event_cursor_expired":
                    raise
                self.recover(profiles, snapshot)
                result = self.world.events(self.state["cursor"])
            if result.get("world_epoch") != epoch:
                raise RuntimeError("World restarted during event polling")
            events = result.get("events")
            if not isinstance(events, list) or len(events) > 4096:
                raise ValueError("Invalid bot event page")
            for event in events:
                if (
                    not isinstance(event, dict)
                    or type(event.get("id")) is not int
                    or event["id"] <= self.state["cursor"]
                    or not isinstance(event.get("payload"), dict)
                    or not isinstance(event.get("bot_id"), str)
                    or not isinstance(event.get("type"), str)
                ):
                    raise ValueError("Invalid or unordered bot event")
                profile = profiles.get(event["bot_id"])
                if (
                    profile is not None
                    and profile["enabled"]
                    and not self.enqueue(event)
                ):
                    break
                # Cursor acknowledges durable enqueue, independently of the
                # optional provider's availability. Each bot retries its queue.
                self.state["cursor"] = event["id"]
                self.checkpoint()
            for bot_id, profile in profiles.items():
                if not profile["enabled"] or "announcer" not in profile["behaviors"]:
                    continue
                interval = profile["behaviors"]["announcer"]["interval_seconds"]
                bucket = int(self.clock() // interval)
                if self.state["announcements"].get(bot_id) == bucket:
                    continue
                if self.enqueue(
                    {
                        "id": f"announcement-{bucket}",
                        "bot_id": bot_id,
                        "type": "timer.announcement",
                        "payload": {},
                    }
                ):
                    self.state["announcements"][bot_id] = bucket
                    self.checkpoint()
            errors.update(self.process_pending(profiles))
            self.status = {
                "connected": True,
                "last_success": self.clock(),
                "last_error": None,
                "bot_errors": errors,
            }

    def run(self, interval=0.5):
        while not self.stop.is_set():
            try:
                self.tick()
            except Exception as error:
                with self.lock:
                    self.status["connected"] = False
                    self.status["last_error"] = type(error).__name__
                LOG.warning("Bot worker cycle failed: %s", type(error).__name__)
            self.stop.wait(interval)

    def inspect(self):
        return {
            "bots": list(self.profiles.snapshot().values()),
            "worker": dict(self.status),
            "world_epoch": self.state["world_epoch"],
            "cursor": self.state["cursor"],
            "pending_count": len(self.state["pending"]),
        }
