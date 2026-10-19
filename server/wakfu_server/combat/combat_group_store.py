"""Durable group availability and generation-safe fight reservations.

Instantiate once at server startup with recover=True to release reservations
whose in-memory fights were lost. Defeated groups are never revived by recovery.
PostgreSQL migrations own tables; no DDL is issued during runtime.
"""
from psycopg.types.json import Jsonb
from psycopg.pq import TransactionStatus
from datetime import datetime, timezone
import time
from copy import deepcopy
from threading import RLock
from .combat_groups import Groups


class PersistentGroups:
    def __init__(self, store, *, recover=False, clock=time.time):
        self.store = store
        self.lock = RLock()
        self.clock = clock
        if recover:
            self.recover_reservations()

    @staticmethod
    def _members(row):
        from .monster_minigame_policy import ordinary_group_members

        return ordinary_group_members(
            row["members"], instance_id=row.get("instance_id", 0)
        )

    def register(self, map_id, instance_id, group_id, members):
        with self.lock, self.store.connection() as db, db.transaction():
            return self.register_transaction(db, map_id, instance_id, group_id, members)

    def register_transaction(self, db, map_id, instance_id, group_id, members):
        """Register in the caller's transaction; caller owns locking and commit.

        This permits durable world births and their receipts to commit together.
        It never publishes packets or starts a fight.
        """
        if db.info.transaction_status != TransactionStatus.INTRANS:
            raise ValueError("Group registration requires an active transaction")
        from .npc_actor_identity_repair import actor_aliases, aliased_members

        members = aliased_members(
            members, actor_aliases(db, (map_id, instance_id, group_id))
        )
        validator = Groups()
        key = validator.register(map_id, instance_id, group_id, members)
        canonical = validator.groups[key]["members"]
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("monster-population:" + ":".join(map(str, key[:2])),),
        )
        inserted = db.execute(
            "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
            "VALUES(%s,%s,%s,%s,'available') ON CONFLICT(map_id,instance_id,group_id) "
            "DO NOTHING RETURNING group_id",
            (*key, Jsonb(canonical)),
        ).fetchone()
        if inserted is None:
            row = db.execute(
                "SELECT members,instance_id FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone()
            if self._members(row) != canonical:
                raise ValueError("Conflicting existing group")
            return key
        for member in canonical:
            claimed = db.execute(
                "INSERT INTO combat_group_members(map_id,instance_id,monster_id,group_id) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT(map_id,instance_id,monster_id) "
                "DO NOTHING RETURNING monster_id",
                (map_id, instance_id, member["id"], group_id),
            ).fetchone()
            if claimed is None:
                raise ValueError("NPC identity already exists in this map instance")
        return key

    def register_seed(self, map_id, instance_id, group_id, members):
        """Keep persisted positions while checking the seed identity and stats."""
        validator = Groups()
        key = validator.register(map_id, instance_id, group_id, members)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT members,ecology_admin_removed_ids FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone()
        if row is None:
            return self.register(*key, members)

        persisted = row["members"]
        removed = set(row.get("ecology_admin_removed_ids", ()))
        if removed:
            from wakfu_server.npc_actor_identity_repair import (
                actor_aliases,
                aliased_members,
            )

            with self.store.connection() as db:
                members = aliased_members(members, actor_aliases(db, key))
            # Administrative tombstones authorize omissions, while surviving
            # seeds and offspring still require their original native receipts.
            members = [member for member in members if member["id"] not in removed]
            persisted = [member for member in persisted if member["id"] not in removed]

        def identity(member):
            return {k: v for k, v in member.items() if k not in ("x", "y", "z")}

        from .monster_minigame_policy import ordinary_group_members

        visible_persisted = ordinary_group_members(persisted, instance_id=instance_id)
        visible_seeds = ordinary_group_members(members, instance_id=instance_id)
        if [identity(m) for m in visible_persisted] != [
            identity(m) for m in visible_seeds
        ]:
            from wakfu_server.monster_maturation import reconcile_seed

            # Old durable groups can retain excluded roots; new groups never
            # stored them. Keep a historical seed when its ID still exists,
            # including a former excluded root matured through real receipts.
            persisted_ids = {member["id"] for member in persisted}
            visible_seed_ids = {member["id"] for member in visible_seeds}
            reconciliation_seeds = [
                member
                for member in members
                if member["id"] in persisted_ids | visible_seed_ids
            ]
            return reconcile_seed(self.store, key, reconciliation_seeds, persisted)
        return key

    def move_members(self, key, expected_members, moved_members):
        """Persist positions only when the available roster still matches."""
        expected_members, moved_members = list(expected_members), list(moved_members)
        if not moved_members or len(expected_members) != len(moved_members):
            raise ValueError("Invalid group movement roster")
        for old, new in zip(expected_members, moved_members):
            if {k: v for k, v in old.items() if k not in ("x", "y", "z")} != {
                k: v for k, v in new.items() if k not in ("x", "y", "z")
            }:
                raise ValueError("Wandering may only change positions")
        validator = Groups()
        validator.register(*key, moved_members)
        with self.store.connection() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("monster-population:" + ":".join(map(str, key[:2])),),
            )
            row = db.execute(
                "SELECT members,instance_id FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND group_id=%s AND status='available' FOR UPDATE",
                key,
            ).fetchone()
            if row is None or list(self._members(row)) != expected_members:
                return False
            moved_by_id = {member["id"]: member for member in moved_members}
            durable_members = [
                moved_by_id.get(member["id"], member) for member in row["members"]
            ]
            return (
                db.execute(
                    "UPDATE combat_groups SET members=%s,revision=revision+1 "
                    "WHERE map_id=%s AND instance_id=%s AND group_id=%s "
                    "AND status='available' AND members=%s RETURNING group_id",
                    (Jsonb(durable_members), *key, Jsonb(row["members"])),
                ).fetchone()
                is not None
            )

    def snapshot(self, map_id=None, instance_id=None):
        if (map_id is None) != (instance_id is None):
            raise ValueError("Group snapshot requires map and instance together")
        with self.store.connection() as db:
            return [
                dict(
                    key=(row["map_id"], row["instance_id"], row["group_id"]),
                    status=row["status"],
                    members=deepcopy(self._members(row)),
                )
                for row in db.execute(
                    "SELECT * FROM combat_groups"
                    if map_id is None
                    else "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s",
                    () if map_id is None else (map_id, instance_id),
                )
                if self._members(row)
            ]

    def available(self, map_id, instance_id):
        with self.store.connection() as db:
            return [
                dict(
                    key=(r["map_id"], r["instance_id"], r["group_id"]),
                    members=deepcopy(self._members(r)),
                )
                for r in db.execute(
                    "SELECT g.* FROM combat_groups g WHERE g.map_id=%s "
                    "AND g.instance_id=%s AND g.status='available' AND ("
                    "NOT EXISTS (SELECT 1 FROM dungeon_room_runs r "
                    "WHERE r.instance_id=g.instance_id) OR EXISTS ("
                    "SELECT 1 FROM dungeon_room_runs r "
                    "JOIN dungeon_room_spawn_receipts s ON s.instance_id=r.instance_id "
                    "AND s.room_order=r.current_room WHERE r.instance_id=g.instance_id "
                    "AND r.status='active' AND s.asset_map_id=g.map_id "
                    "AND s.group_id=g.group_id)) AND ("
                    "NOT EXISTS (SELECT 1 FROM objectives_challenge_runs c WHERE c.instance_id=g.instance_id) "
                    "OR EXISTS (SELECT 1 FROM objectives_challenge_runs c WHERE c.instance_id=g.instance_id "
                    "AND c.map_id=g.map_id AND c.group_id=g.group_id AND c.status='available' "
                    "AND c.returned_at IS NULL)) ORDER BY g.group_id",
                    (map_id, instance_id),
                )
                if self._members(r)
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
            row = db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s AND status='available' FOR UPDATE",
                key,
            ).fetchone()
            if row is None:
                raise ValueError("Group is unavailable")
            members = self._members(row)
            if not members:
                raise ValueError("Group has no eligible ordinary monsters")
            revision = row["revision"] + 1
            db.execute(
                "UPDATE combat_groups SET status='fighting',generation=%s,fight_id=%s,revision=%s WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (generation, fight_id, revision, *key),
            )
            return (key, generation, fight_id, revision), members

    def finish(self, lease, *, defeated, db=None):
        if type(defeated) is not bool:
            raise ValueError("Outcome must be explicit")
        key, generation, fight_id, revision = lease
        if db is None:
            with self.lock, self.store.connection() as connection:
                return self.finish(lease, defeated=defeated, db=connection)
        if db.info.transaction_status != TransactionStatus.INTRANS:
            raise ValueError("Group settlement requires an active transaction")
        cursor = db.execute(
            "UPDATE combat_groups SET status=%s,generation=NULL,fight_id=NULL,revision=revision+1,defeated_at=%s WHERE map_id=%s AND instance_id=%s AND group_id=%s AND status='fighting' AND generation=%s AND fight_id=%s AND revision=%s",
            (
                "defeated" if defeated else "available",
                datetime.fromtimestamp(self.clock(), timezone.utc)
                if defeated
                else None,
                *key,
                generation,
                fight_id,
                revision,
            ),
        )
        return cursor.rowcount == 1

    def release_session(self, generation):
        with self.lock, self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT * FROM combat_groups WHERE status='fighting' AND generation=%s FOR UPDATE",
                    (generation,),
                )
            )
            db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL,revision=revision+1 WHERE status='fighting' AND generation=%s",
                (generation,),
            )
            released = []
            for prior in rows:
                key = (prior["map_id"], prior["instance_id"], prior["group_id"])
                current = db.execute(
                    "SELECT members,status,instance_id FROM combat_groups WHERE map_id=%s "
                    "AND instance_id=%s AND group_id=%s",
                    key,
                ).fetchone()
                members = self._members(current)
                if current["status"] == "available" and members:
                    released.append(dict(key=key, members=members))
            return released

    def respawn(self, key):
        with self.lock, self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s AND status='defeated' FOR UPDATE",
                key,
            ).fetchone()
            if row is None:
                raise ValueError("Only defeated groups can respawn")
            members = self._members(row)
            if not members:
                raise ValueError("Group has no eligible ordinary monsters")
            if row.get("ecology_admin_removed_ids"):
                raise ValueError("Administratively removed groups cannot respawn")
            if db.execute(
                "SELECT 1 FROM objectives_challenge_runs WHERE map_id=%s "
                "AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone():
                raise ValueError("Finite challenge groups cannot respawn")
            from wakfu_server.objectives.hunts import is_hunt

            if is_hunt(db, key):
                raise ValueError("Finite public hunt groups cannot respawn")
            db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL,revision=revision+1,defeated_at=NULL WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            )
            return members

    def recover_reservations(self):
        """Startup-only abort of lost fights. Never call on a live second worker."""
        with self.lock, self.store.connection() as db:
            cursor = db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL,revision=revision+1 WHERE status='fighting'"
            )
            return cursor.rowcount
