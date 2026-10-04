"""Redis-authoritative NPC groups, batched to SQLite without duplicate leases.

Startup recover=True aborts lost fights only; never use on a second live worker.
No fallback occurs if Redis is configured but unavailable. Group mutations are
CAS durable in Redis before a result is returned, not deferred memory-only work.
"""
import json
import math
import time
from copy import deepcopy
from threading import RLock
from wakfu_server.state_journal import StateJournal, StateJournalError
from wakfu_server.combat_groups import Groups
from wakfu_server.combat_group_store import PersistentGroups


def _state(row):
    if row is None:
        return None
    return dict(
        members=json.loads(row["members"]),
        status=row["status"],
        generation=row["generation"],
        fight_id=row["fight_id"],
        revision=row["revision"],
        defeated_at=row["defeated_at"],
    )


class RedisGroups:
    def __init__(
        self,
        store,
        client,
        *,
        recover=False,
        clock=time.time,
        lease_active=None,
        namespace="wakfu:groups:v1",
        flush_interval=1200
    ):
        if (
            type(flush_interval) not in (int, float)
            or not math.isfinite(flush_interval)
            or flush_interval <= 0
        ):
            raise ValueError("Invalid group flush interval")
        self.store = store
        self.clock = clock
        self.lock = RLock()
        self.lease_active = lease_active
        self.interval = flush_interval
        self.last_flush = clock()
        self.journal = StateJournal(client, namespace)
        PersistentGroups(store, recover=False)  # Schema only; no state writes.
        with store.connection() as db:
            rows = list(db.execute("SELECT * FROM combat_groups"))
            existing = {
                (r["map_id"], r["instance_id"], r["group_id"]): _state(r) for r in rows
            }
        for key, dbstate in existing.items():
            value, encoded = self.journal.read(key)
            if value is None:
                self.journal.put(key, dbstate, baseline=dbstate)
        for key, value, encoded in list(self.journal.records()):
            self._validate(key, value["current"])
            dbstate = existing.get(key)
            if dbstate == value["current"] and dbstate != value["baseline"]:
                self.journal.checkpoint(key, encoded)
            elif dbstate != value["baseline"]:
                raise StateJournalError(
                    "SQLite group baseline conflicts with Redis recovery"
                )
        if recover:
            self.recover_reservations()

    @staticmethod
    def _validate(key, state):
        if len(key) != 3 or any(type(n) is not int for n in key):
            raise StateJournalError("Invalid group key")
        validator = Groups()
        validator.register(*key, state["members"])
        if (
            state["status"] not in ("available", "fighting", "defeated")
            or type(state["revision"]) is not int
            or state["revision"] < 0
        ):
            raise StateJournalError("Invalid group state")
        if state["status"] == "fighting":
            if (
                not isinstance(state["generation"], str)
                or not state["generation"]
                or type(state["fight_id"]) is not int
                or not 0 < state["fight_id"] < 2**31
            ):
                raise StateJournalError("Invalid group fight reservation")
        elif state["generation"] is not None or state["fight_id"] is not None:
            raise StateJournalError("Invalid released group lease")
        if state["defeated_at"] is not None and (
            type(state["defeated_at"]) not in (int, float)
            or not math.isfinite(state["defeated_at"])
        ):
            raise StateJournalError("Invalid group defeat timestamp")

    def _read(self, key):
        value, encoded = self.journal.read(key)
        if value is None:
            raise ValueError("Unknown group")
        self._validate(key, value["current"])
        return deepcopy(value["current"]), encoded

    def _write(self, key, state, encoded):
        self._validate(key, state)
        self.journal.put(key, state, expected=encoded)

    def register(self, map_id, instance_id, group_id, members):
        validator = Groups()
        key = validator.register(map_id, instance_id, group_id, members)
        canonical = list(validator.groups[key]["members"])
        with self.lock:
            value, encoded = self.journal.read(key)
            if value is not None:
                if value["current"]["members"] != canonical:
                    raise ValueError("Conflicting existing group")
                return key
            identities = {m["id"] for m in canonical}
            for other, state, _ in self.journal.records():
                if other[:2] == key[:2] and identities & {
                    m["id"] for m in state["current"]["members"]
                }:
                    raise ValueError("NPC identity already exists in this map instance")
            state = dict(
                members=canonical,
                status="available",
                generation=None,
                fight_id=None,
                revision=0,
                defeated_at=None,
            )
            self._write(key, state, None)
            return key

    def register_seed(self, map_id, instance_id, group_id, members):
        """Validate fixed seed identity/stats while retaining persisted positions."""
        key = (map_id, instance_id, group_id)
        validator = Groups()
        validator.register(*key, members)
        with self.lock:
            value, _ = self.journal.read(key)
            if value is None:
                return self.register(*key, members)
            state = value["current"]
            self._validate(key, state)
            strip = lambda m: {k: v for k, v in m.items() if k not in ("x", "y", "z")}
            if [strip(m) for m in state["members"]] != [strip(m) for m in members]:
                raise ValueError("Conflicting existing group seed identity or stats")
            return key

    def snapshot(self):
        """Detached all-state groups for occupancy and lifecycle policies."""
        with self.lock:
            return [
                dict(
                    key=key,
                    status=value["current"]["status"],
                    members=deepcopy(value["current"]["members"]),
                )
                for key, value, _ in self.journal.records()
            ]

    def available(self, map_id, instance_id):
        with self.lock:
            rows = [
                dict(key=key, members=tuple(deepcopy(value["current"]["members"])))
                for key, value, _ in self.journal.records()
                if key[:2] == (map_id, instance_id)
                and value["current"]["status"] == "available"
            ]
            return sorted(rows, key=lambda row: row["key"])

    def claim(self, key, generation, fight_id):
        if (
            not isinstance(generation, str)
            or not generation
            or type(fight_id) is not int
            or not 0 < fight_id < 2**31
        ):
            raise ValueError("Invalid fight lease")
        with self.lock:
            if self.lease_active is not None and not self.lease_active(generation):
                raise ValueError("Expired fight owner lease")
            state, encoded = self._read(key)
            if state["status"] != "available":
                raise ValueError("Group is unavailable")
            state.update(
                status="fighting",
                generation=generation,
                fight_id=fight_id,
                revision=state["revision"] + 1,
            )
            self._write(key, state, encoded)
            return (key, generation, fight_id, state["revision"]), tuple(
                state["members"]
            )

    def move_members(self, key, expected_members, moved_members):
        """CAS an available group's positions; preserve identity and all stats."""
        expected_members, moved_members = list(expected_members), list(moved_members)
        if len(expected_members) != len(moved_members) or not moved_members:
            raise ValueError("Invalid group movement roster")
        for old, new in zip(expected_members, moved_members):
            if {k: v for k, v in old.items() if k not in ("x", "y", "z")} != {
                k: v for k, v in new.items() if k not in ("x", "y", "z")
            }:
                raise ValueError("Wandering may only change positions")
        with self.lock:
            state, encoded = self._read(key)
            if state["status"] != "available" or state["members"] != expected_members:
                return False
            state.update(members=moved_members, revision=state["revision"] + 1)
            self._write(key, state, encoded)
            return True

    def finish(self, lease, *, defeated):
        if type(defeated) is not bool:
            raise ValueError("Outcome must be explicit")
        key, generation, fight_id, revision = lease
        with self.lock:
            state, encoded = self._read(key)
            if state["status"] != "fighting" or (
                state["generation"],
                state["fight_id"],
                state["revision"],
            ) != (generation, fight_id, revision):
                return False
            if self.lease_active is not None and not self.lease_active(generation):
                raise ValueError("Expired fight owner lease")
            state.update(
                status="defeated" if defeated else "available",
                generation=None,
                fight_id=None,
                revision=revision + 1,
                defeated_at=self.clock() if defeated else None,
            )
            self._write(key, state, encoded)
            return True

    def release_session(self, generation):
        with self.lock:
            restored = []
            for key, value, encoded in list(self.journal.records()):
                state = value["current"]
                if state["status"] == "fighting" and state["generation"] == generation:
                    state.update(
                        status="available",
                        generation=None,
                        fight_id=None,
                        revision=state["revision"] + 1,
                        defeated_at=None,
                    )
                    self._write(key, state, encoded)
                    restored.append(dict(key=key, members=tuple(state["members"])))
            return restored

    def respawn(self, key):
        with self.lock:
            state, encoded = self._read(key)
            if state["status"] != "defeated":
                raise ValueError("Only defeated groups can respawn")
            state.update(
                status="available",
                generation=None,
                fight_id=None,
                revision=state["revision"] + 1,
                defeated_at=None,
            )
            self._write(key, state, encoded)
            return tuple(state["members"])

    def respawn_due(self, delay_seconds):
        if (
            type(delay_seconds) not in (int, float)
            or not math.isfinite(delay_seconds)
            or delay_seconds < 0
        ):
            raise ValueError("Invalid group respawn delay")
        with self.lock:
            result = []
            for key, value, _ in list(self.journal.records()):
                state = value["current"]
                if (
                    state["status"] == "defeated"
                    and state["defeated_at"] is not None
                    and state["defeated_at"] <= self.clock() - delay_seconds
                ):
                    result.append(dict(key=key, members=self.respawn(key)))
            return result

    def recover_reservations(self):
        with self.lock:
            generations = {
                v["current"]["generation"]
                for _, v, _ in self.journal.records()
                if v["current"]["status"] == "fighting"
            }
            return sum(
                len(self.release_session(generation)) for generation in generations
            )

    def flush(self):
        with self.lock:
            dirty = [
                (key, value, encoded)
                for key, value, encoded in self.journal.records()
                if value["baseline"] != value["current"]
            ]
            with self.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                for key, value, _ in dirty:
                    current = value["current"]
                    self._validate(key, current)
                    saved = _state(
                        db.execute(
                            "SELECT * FROM combat_groups WHERE map_id=? AND instance_id=? AND group_id=?",
                            key,
                        ).fetchone()
                    )
                    if saved == current:
                        continue  # Previous SQL commit succeeded before Redis checkpoint failed.
                    if saved != value["baseline"]:
                        raise StateJournalError("SQLite group revision conflict")
                    db.execute(
                        """INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,generation,fight_id,revision,defeated_at)
                        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(map_id,instance_id,group_id) DO UPDATE SET
                        members=excluded.members,status=excluded.status,generation=excluded.generation,
                        fight_id=excluded.fight_id,revision=excluded.revision,defeated_at=excluded.defeated_at""",
                        (
                            *key,
                            json.dumps(current["members"], separators=(",", ":")),
                            current["status"],
                            current["generation"],
                            current["fight_id"],
                            current["revision"],
                            current["defeated_at"],
                        ),
                    )
            # SQLite commits first; preserve newer Redis current revisions during checkpoint.
            for key, _, encoded in dirty:
                self.journal.checkpoint(key, encoded)
            self.last_flush = self.clock()
            return len(dirty)

    def flush_due(self):
        return self.flush() if self.clock() - self.last_flush >= self.interval else 0

    def close(self):
        return self.flush()
