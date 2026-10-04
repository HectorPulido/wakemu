"""Durable group availability and generation-safe fight reservations.

Instantiate once at server startup with recover=True to release reservations
whose in-memory fights were lost. Defeated groups are never revived by recovery.
Tables belong to this module; it does not alter the character Store schema.
"""
import json
import time
from copy import deepcopy
from threading import RLock
from .combat_groups import Groups


class PersistentGroups:
    def __init__(self, store, *, recover=False, clock=time.time):
        self.store = store
        self.lock = RLock()
        self.clock = clock
        with store.connection() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS combat_groups (
                map_id INTEGER NOT NULL, instance_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL, members TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('available','fighting','defeated')),
                generation TEXT, fight_id INTEGER, revision INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(map_id,instance_id,group_id))"""
            )
        with store.connection() as db:
            columns = {
                r["name"] for r in db.execute("PRAGMA table_info(combat_groups)")
            }
            if "defeated_at" not in columns:
                db.execute("ALTER TABLE combat_groups ADD COLUMN defeated_at REAL")
        if recover:
            self.recover_reservations()

    @staticmethod
    def _members(row):
        return tuple(json.loads(row["members"]))

    def register(self, map_id, instance_id, group_id, members):
        # Reuse the complete native ownership/roster validation.
        validator = Groups()
        key = validator.register(map_id, instance_id, group_id, members)
        canonical = validator.groups[key]["members"]
        with self.lock, self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM combat_groups WHERE map_id=? AND instance_id=? AND group_id=?",
                key,
            ).fetchone()
            if row:
                if self._members(row) != canonical:
                    raise ValueError("Conflicting existing group")
                return key
            identities = {m["id"] for m in canonical}
            for other in db.execute(
                "SELECT members FROM combat_groups WHERE map_id=? AND instance_id=?",
                key[:2],
            ):
                if identities & {m["id"] for m in self._members(other)}:
                    raise ValueError("NPC identity already exists in this map instance")
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) VALUES(?,?,?,?,?)",
                (*key, json.dumps(canonical, separators=(",", ":")), "available"),
            )
        return key

    def snapshot(self):
        with self.lock, self.store.connection() as db:
            return [
                dict(
                    key=(row["map_id"], row["instance_id"], row["group_id"]),
                    status=row["status"],
                    members=deepcopy(self._members(row)),
                )
                for row in db.execute("SELECT * FROM combat_groups")
            ]

    def available(self, map_id, instance_id):
        with self.lock, self.store.connection() as db:
            return [
                dict(
                    key=(r["map_id"], r["instance_id"], r["group_id"]),
                    members=self._members(r),
                )
                for r in db.execute(
                    "SELECT * FROM combat_groups WHERE map_id=? AND instance_id=? AND status='available' ORDER BY group_id",
                    (map_id, instance_id),
                )
            ]

    def claim(self, key, generation, fight_id):
        if (
            not isinstance(generation, str)
            or not generation
            or type(fight_id) is not int
            or not 0 < fight_id < 2**31
        ):
            raise ValueError("Invalid fight lease")
        with self.lock, self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM combat_groups WHERE map_id=? AND instance_id=? AND group_id=? AND status='available'",
                key,
            ).fetchone()
            if row is None:
                raise ValueError("Group is unavailable")
            revision = row["revision"] + 1
            db.execute(
                "UPDATE combat_groups SET status='fighting',generation=?,fight_id=?,revision=? WHERE map_id=? AND instance_id=? AND group_id=?",
                (generation, fight_id, revision, *key),
            )
            return (key, generation, fight_id, revision), self._members(row)

    def finish(self, lease, *, defeated):
        if type(defeated) is not bool:
            raise ValueError("Outcome must be explicit")
        key, generation, fight_id, revision = lease
        with self.lock, self.store.connection() as db:
            cursor = db.execute(
                "UPDATE combat_groups SET status=?,generation=NULL,fight_id=NULL,revision=revision+1,defeated_at=? WHERE map_id=? AND instance_id=? AND group_id=? AND status='fighting' AND generation=? AND fight_id=? AND revision=?",
                (
                    "defeated" if defeated else "available",
                    self.clock() if defeated else None,
                    *key,
                    generation,
                    fight_id,
                    revision,
                ),
            )
            return cursor.rowcount == 1

    def release_session(self, generation):
        with self.lock, self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = list(
                db.execute(
                    "SELECT * FROM combat_groups WHERE status='fighting' AND generation=?",
                    (generation,),
                )
            )
            db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL,revision=revision+1 WHERE status='fighting' AND generation=?",
                (generation,),
            )
            return [
                dict(
                    key=(r["map_id"], r["instance_id"], r["group_id"]),
                    members=self._members(r),
                )
                for r in rows
            ]

    def respawn(self, key):
        with self.lock, self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM combat_groups WHERE map_id=? AND instance_id=? AND group_id=? AND status='defeated'",
                key,
            ).fetchone()
            if row is None:
                raise ValueError("Only defeated groups can respawn")
            db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL,revision=revision+1,defeated_at=NULL WHERE map_id=? AND instance_id=? AND group_id=?",
                key,
            )
            return self._members(row)

    def recover_reservations(self):
        """Startup-only abort of lost fights. Never call on a live second worker."""
        with self.lock, self.store.connection() as db:
            cursor = db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL,revision=revision+1 WHERE status='fighting'"
            )
            return cursor.rowcount

    def respawn_due(self, delay_seconds):
        """Atomically restore due groups; returned entries require world broadcast.

        Legacy defeated rows with no timestamp remain defeated until explicit
        respawn. Recovery never assigns a fabricated defeat time to those rows.
        """
        if type(delay_seconds) not in (int, float) or not 0 <= delay_seconds < float(
            "inf"
        ):
            raise ValueError("Respawn delay must be finite and nonnegative")
        cutoff = self.clock() - delay_seconds
        with self.lock, self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = list(
                db.execute(
                    "SELECT * FROM combat_groups WHERE status='defeated' AND defeated_at IS NOT NULL AND defeated_at<=? ORDER BY map_id,instance_id,group_id",
                    (cutoff,),
                )
            )
            for row in rows:
                db.execute(
                    "UPDATE combat_groups SET status='available',defeated_at=NULL,generation=NULL,fight_id=NULL,revision=revision+1 WHERE map_id=? AND instance_id=? AND group_id=?",
                    (row["map_id"], row["instance_id"], row["group_id"]),
                )
            return [
                dict(
                    key=(r["map_id"], r["instance_id"], r["group_id"]),
                    members=self._members(r),
                )
                for r in rows
            ]
