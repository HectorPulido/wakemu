"""Durable planting intents; World alone accepts the prepared occupation."""

import uuid
import threading

from psycopg.types.json import Jsonb
from wakfu_server import planting

LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")


class EcologyPlantingIntents:
    def __init__(self, store, world_epoch):
        self.store, self.world_epoch = store, world_epoch
        self.active = {}
        self.lock = threading.Lock()

    def enqueue(self, account, generation, character, body):
        planting.decode(body)
        if not isinstance(self.world_epoch, str) or not self.world_epoch:
            raise ValueError("Missing planting world epoch")
        identity = uuid.uuid4().hex
        cancelled = [False]
        active = (generation, identity, cancelled)
        with self.lock:
            self.active[character["id"]] = active
        try:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE ecology_planting_intents SET status='cancelled' "
                    "WHERE character_id=%s AND status='pending'",
                    (character["id"],),
                )
                db.execute(
                    "INSERT INTO ecology_planting_intents(id,world_epoch,account_id,generation,"
                    "character_id,body,actor_location,created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,clock_timestamp())",
                    (
                        identity,
                        self.world_epoch,
                        account,
                        generation,
                        character["id"],
                        body,
                        Jsonb({key: character[key] for key in LOCATION_KEYS}),
                    ),
                )
        except Exception:
            with self.lock:
                if self.active.get(character["id"]) == active:
                    self.active.pop(character["id"], None)
            raise
        # Cancellation may run before INSERT becomes visible. Its scalar flag
        # closes that visibility gap without holding a mutex across SQL.
        if cancelled[0]:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE ecology_planting_intents SET status='cancelled' "
                    "WHERE id=%s AND status='pending'",
                    (identity,),
                )
        return identity

    def cancel(self, character_id, generation=None):
        # Most movement cancellations have no async intent. Keep this hot path
        # in memory; SQL remains authoritative for the indexed pending intent.
        with self.lock:
            current = self.active.get(character_id)
            if current is None or (generation is not None and current[0] != generation):
                return
            current[2][0] = True
        with self.store.connection() as db:
            db.execute(
                "UPDATE ecology_planting_intents SET status='cancelled' "
                "WHERE character_id=%s AND status='pending' "
                + ("AND generation=%s" if generation is not None else ""),
                (character_id,) + (() if generation is None else (generation,)),
            )
        with self.lock:
            if self.active.get(character_id) == current:
                self.active.pop(character_id, None)

    def apply(self, proposal, begin_callback):
        """Serialize cancel versus accept; callback reuses this transaction."""
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM ecology_planting_intents WHERE id=%s FOR UPDATE",
                (proposal["intent_id"],),
            ).fetchone()
            if (
                row is None
                or row["status"] != "pending"
                or row["world_epoch"] != self.world_epoch
                or proposal.get("world_epoch") != self.world_epoch
                or row["intent_version"] != proposal.get("intent_version")
                or any(
                    row[key] != proposal.get(key)
                    for key in ("account_id", "generation", "character_id")
                )
                or bytes(row["body"]).hex() != proposal.get("body_hex")
            ):
                return dict(applied=False, reason="stale_intent")
            db.execute(
                "UPDATE ecology_planting_intents SET status='applying' WHERE id=%s",
                (row["id"],),
            )
            if proposal["kind"] == "planting_rejected":
                result = dict(applied=True, rejected=True, error=proposal["error"])
            elif proposal["kind"] == "planting_begin":
                result = dict(applied=True, packet=begin_callback(db, proposal))
            else:
                raise ValueError("Unknown planting intent proposal")
            db.execute(
                "UPDATE ecology_planting_intents SET status='applied' WHERE id=%s",
                (row["id"],),
            )
        with self.lock:
            current = self.active.get(proposal["character_id"])
            if current is not None and current[:2] == (
                proposal["generation"],
                proposal["intent_id"],
            ):
                self.active.pop(proposal["character_id"], None)
        return result
