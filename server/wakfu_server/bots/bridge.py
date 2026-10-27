"""Authenticated, epoch-fenced commands and bounded semantic event delivery.

Only game authority lives here. Behavior selection, pricing and language model
calls belong to the bot service. No outbound HTTP runs on World gameplay paths.
"""
from collections import deque
from copy import deepcopy
import hashlib
import hmac
import json
import math
import re
import threading
import time
import uuid
from urllib.parse import parse_qs, urlsplit

MAX_BODY_BYTES = 65536
COMMAND_TTL = 300


class BotConflict(ValueError):
    """The caller must refresh authority before retrying an operation."""


class BotBusy(RuntimeError):
    pass


class BotWorldBridge:
    def __init__(
        self,
        runtime,
        token,
        *,
        clock=time.time,
        event_limit=2048,
        receipt_limit=8192,
        worker_timeout=60
    ):
        if not isinstance(token, str) or len(token.strip()) < 24:
            raise ValueError(
                "A dedicated bot credential of at least 24 characters is required"
            )
        if type(event_limit) is not int or event_limit < 1:
            raise ValueError("Invalid bot event capacity")
        self.runtime, self.token, self.clock = runtime, token, clock
        self.epoch = uuid.uuid4().hex
        self.lock = threading.RLock()
        self.event_lock = threading.Lock()
        self.events = deque(maxlen=event_limit)
        self.sequence = 0
        self.receipts = {}
        self.receipt_limit = receipt_limit
        self.worker_timeout = worker_timeout
        self.last_worker = None

    def authorized(self, header):
        return isinstance(header, str) and hmac.compare_digest(
            header.encode(), ("Bearer " + self.token).encode()
        )

    def emit(self, bot_id, event_type, payload):
        # Separate from command lock: gameplay outbox writers never wait for
        # a command holding an exchange guard to drain their own notifications.
        with self.event_lock:
            self.sequence += 1
            self.events.append(
                dict(
                    id=self.sequence,
                    bot_id=bot_id,
                    type=event_type,
                    payload=deepcopy(payload),
                )
            )

    def snapshot(self):
        with self.lock:
            self.last_worker = self.clock()
            # Capture the cursor first. Events produced during the snapshot
            # must remain replayable, even if the snapshot also contains them.
            with self.event_lock:
                cursor = self.sequence
            bots = self.runtime.snapshot()
            pending = []
            for bot in bots:
                for event in bot.pop("pending_events", []):
                    pending.append(dict(bot_id=bot["bot_id"], **event))
            return dict(
                world_epoch=self.epoch,
                cursor=cursor,
                bots=bots,
                pending_events=pending,
                supported_actions=list(self.runtime.supported_actions),
            )

    def poll(self, after, world_epoch):
        if world_epoch != self.epoch:
            raise BotConflict("world_epoch_changed")
        if type(after) is not int or after < 0:
            raise ValueError("Invalid event cursor")
        with self.event_lock:
            if after > self.sequence or (
                self.events and after < self.events[0]["id"] - 1
            ):
                raise BotConflict("event_cursor_expired")
            events = [deepcopy(event) for event in self.events if event["id"] > after][
                :128
            ]
            cursor = events[-1]["id"] if events else after
            self.last_worker = self.clock()
            return dict(world_epoch=self.epoch, events=events, cursor=cursor)

    def command(self, body):
        required = {
            "world_epoch",
            "request_id",
            "issued_at",
            "bot_id",
            "action",
            "args",
        }
        if type(body) is not dict or set(body) != required:
            raise ValueError("Invalid bot command envelope")
        if body["world_epoch"] != self.epoch:
            raise BotConflict("world_epoch_changed")
        for key in ("request_id", "bot_id"):
            if not isinstance(body[key], str) or not re.fullmatch(
                r"[A-Za-z0-9_.:-]{1,128}", body[key]
            ):
                raise ValueError("Invalid bot command identifier")
        if not isinstance(body["action"], str) or type(body["args"]) is not dict:
            raise ValueError("Invalid bot action")
        if type(body["issued_at"]) not in (int, float) or not math.isfinite(
            body["issued_at"]
        ):
            raise ValueError("Invalid bot command time")
        fingerprint = hashlib.sha256(
            json.dumps(
                {key: value for key, value in body.items() if key != "issued_at"},
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        with self.lock:
            now = self.clock()
            self.receipts = {
                key: receipt
                for key, receipt in self.receipts.items()
                if receipt[0] >= now
            }
            if not now - COMMAND_TTL <= body["issued_at"] <= now + 5:
                raise BotConflict("command_expired")
            prior = self.receipts.get(body["request_id"])
            if prior is not None:
                if prior[1] != fingerprint:
                    raise BotConflict("request_id_reused")
                return deepcopy(prior[2])
            if len(self.receipts) >= self.receipt_limit:
                raise BotBusy("Bot command capacity reached")
            self.last_worker = now
            result = self.runtime.execute(body["bot_id"], body["action"], body["args"])
            response = dict(
                world_epoch=self.epoch, request_id=body["request_id"], result=result
            )
            # Retain until the *latest* valid issue time for this request has
            # expired; stale requests are rejected before deduplication.
            self.receipts[body["request_id"]] = (
                now + COMMAND_TTL + 5,
                fingerprint,
                deepcopy(response),
            )
            return response

    def tick(self):
        with self.lock:
            if (
                self.last_worker is None
                or self.clock() - self.last_worker > self.worker_timeout
            ):
                self.runtime.deactivate_all()
                return
            self.runtime.heartbeat()

    def request(self, method, path, body=None):
        parsed = urlsplit(path)
        if (
            method == "GET"
            and parsed.path == "/internal/bots/snapshot"
            and not parsed.query
        ):
            return self.snapshot()
        if method == "GET" and parsed.path == "/internal/bots/events":
            query = parse_qs(parsed.query, keep_blank_values=True)
            if set(query) != {"after", "world_epoch"} or any(
                len(value) != 1 for value in query.values()
            ):
                raise ValueError("Invalid bot event query")
            return self.poll(int(query["after"][0]), query["world_epoch"][0])
        if method == "POST" and path == "/internal/bots/commands":
            return self.command(body)
        raise LookupError("Unknown bot endpoint")
