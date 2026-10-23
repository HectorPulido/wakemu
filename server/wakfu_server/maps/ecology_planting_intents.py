"""Durable async planting preparation; only world accepts an occupation."""
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


def prepare_intents(store, snapshot, *, limit=4):
    """Resolve heavy native surface/terrain/probability outside world locks."""
    from wakfu_server.planting_cells import authorize
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.haven_bag_garden import (
        is_private_garden,
        authorize as garden_authorize,
    )
    from wakfu_server.planting_location import active_character
    from wakfu_server.planting_probability import resolver
    from wakfu_server.planting_bonus import resolver as bonus_resolver

    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("Invalid planting intent batch")
    started_at_ms = snapshot.get("started_at_ms")
    if type(started_at_ms) is not int or not 0 < started_at_ms < 2**53:
        raise ValueError("Missing or invalid planting snapshot start time")
    players = snapshot.get("players", ())
    open_policy = snapshot.get("open_planting", True)
    probability = resolver(
        store, profession_bonus=bonus_resolver(store), open_test_policy=open_policy
    )
    plans = []
    with store.connection() as db:
        rows = db.execute(
            "SELECT * FROM ecology_planting_intents WHERE world_epoch=%s AND status='pending' "
            "AND created_at < to_timestamp(%s / 1000.0) "
            "ORDER BY intent_version LIMIT %s",
            (snapshot["world_epoch"], started_at_ms, limit),
        ).fetchall()
    for row in rows:
        envelope = dict(
            world_epoch=row["world_epoch"],
            intent_id=row["id"],
            intent_version=row["intent_version"],
            account_id=row["account_id"],
            generation=row["generation"],
            character_id=row["character_id"],
            body_hex=bytes(row["body"]).hex(),
        )
        try:
            actor = dict(
                id=row["character_id"],
                account_id=row["account_id"],
                **row["actor_location"]
            )

            def authorize_cell(current_actor, request, seed, resource):
                if any(
                    current_actor[key] != row["actor_location"][key]
                    for key in LOCATION_KEYS
                ):
                    raise ValueError("Planting origin changed during preparation")
                if is_private_garden(current_actor):
                    return garden_authorize(
                        store, current_actor, request, seed, resource
                    )
                z = authorize(
                    store,
                    current_actor,
                    request,
                    seed,
                    resource,
                    open_test_policy=open_policy,
                )
                source = tuple(current_actor[k] for k in ("x", "y", "z"))
                if (request["x"], request["y"], z) not in published_geometry(
                    current_actor["map_id"]
                ).outgoing.get(source, ()):
                    raise ValueError("Move next to the planting cell")
                return z

            prepared = planting.prepare(
                store,
                row["account_id"],
                row["generation"],
                actor,
                bytes(row["body"]),
                authorize_cell=authorize_cell,
                open_test_policy=open_policy,
                location_context=lambda stored: active_character(
                    stored,
                    players,
                    store=store,
                    expected_location=row["actor_location"],
                ),
                read_only=True,
            )
            chance = probability(prepared)
            with store.connection() as db:
                policy = db.execute(
                    "SELECT value FROM settings WHERE name='planting_duration_ms'"
                ).fetchone()
            duration = None if policy is None else policy["value"]
            if type(duration) is not int or not 1 <= duration <= 300000:
                raise ValueError("Invalid PostgreSQL planting duration")
            prepared["character"] = {
                key: prepared["character"][key]
                for key in ("id", "account_id", *LOCATION_KEYS)
            }
            prepared.update(probability=chance, duration_ms=duration)
            plans.append(dict(envelope, kind="planting_begin", prepared=prepared))
        except ValueError as error:
            plans.append(dict(envelope, kind="planting_rejected", error=str(error)))
    return plans
