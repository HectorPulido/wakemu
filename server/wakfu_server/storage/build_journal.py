"""Owned build snapshots durable in Redis, checkpointed to SQLite in batches.

HP, inventory, session leases and rewards remain independent SQL domains.
All mutations validate the SQL lease and owned units while holding its write
lock; Redis failure never acknowledges or falls back to immediate build SQL.
"""
import math
import time
from copy import deepcopy
from threading import RLock
from wakfu_server.state_journal import StateJournal, StateJournalError
from wakfu_server.builds import KEYS, validate


def _sql(db, character_id):
    return {
        str(row["build_index"]): {key: row[key].hex() for key in KEYS}
        for row in db.execute(
            "SELECT * FROM character_builds WHERE character_id=?", (character_id,)
        )
    }


def _checked(state):
    if not isinstance(state, dict):
        raise StateJournalError("Invalid build journal state")
    for index, build in state.items():
        if (
            index not in ("0", "1", "2")
            or not isinstance(build, dict)
            or set(build) != set(KEYS)
        ):
            raise StateJournalError("Invalid build journal sheet")
        for value in build.values():
            if not isinstance(value, str):
                raise StateJournalError("Invalid build journal bytes")
            try:
                raw = bytes.fromhex(value)
            except ValueError as error:
                raise StateJournalError("Invalid build journal bytes") from error
            if len(raw) > 65536:
                raise StateJournalError("Oversized build journal section")
    return state


def _units(db, character_id, state):
    """Recheck unit ownership for every sheet, including inactive builds.

    Do not revalidate captured build levels after a legitimate XP level-up.
    Slot/catalog eligibility was validated when the edit was accepted.
    """
    from wakfu_server.wire import proto_fields

    owned = {
        row["uid"]: row["quantity"]
        for row in db.execute(
            "SELECT uid,quantity FROM inventory_items WHERE character_id=?",
            (character_id,),
        )
    }
    for build in state.values():
        for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
            if tag == 424:
                continue
            if tag != 10 or not isinstance(value, bytes):
                raise StateJournalError("Invalid journal equipment selection")
            fields = list(proto_fields(value))
            selected = dict(fields)
            if (
                len(fields) != 2
                or set(selected) != {8, 16}
                or owned.get(selected[8]) != 1
            ):
                raise StateJournalError("Journal equipment unit unavailable or foreign")


class BuildJournal:
    def __init__(
        self,
        store,
        client,
        *,
        namespace="wakfu:builds:v1",
        flush_interval=1200,
        clock=time.time
    ):
        if (
            type(flush_interval) not in (int, float)
            or not math.isfinite(flush_interval)
            or flush_interval <= 0
        ):
            raise ValueError("Invalid build flush interval")
        self.store = store
        self.clock = clock
        self.interval = flush_interval
        self.last_flush = clock()
        self.lock = RLock()
        self.journal = StateJournal(client, namespace)
        # Reconcile only completed checkpoints; never overwrite pending Redis.
        with store.connection() as db:
            for key, value, encoded in list(self.journal.records()):
                self._key(key)
                _checked(value["current"])
                _checked(value["baseline"])
                row = db.execute(
                    "SELECT account_id FROM characters WHERE id=?", (key[1],)
                ).fetchone()
                if row is None or row["account_id"] != key[0]:
                    raise StateJournalError("Foreign build journal character")
                saved = _sql(db, key[1])
                if saved == value["current"] and saved != value["baseline"]:
                    self.journal.checkpoint(key, encoded)
                elif saved != value["baseline"]:
                    raise StateJournalError(
                        "SQLite build baseline conflicts with Redis recovery"
                    )

    @staticmethod
    def _key(key):
        if len(key) != 2 or any(type(n) is not int or n <= 0 for n in key):
            raise StateJournalError("Invalid build journal identity")

    def overlay(self, character, db):
        """Hydrate under the caller's DB handle; never call Store.character here."""
        key = (character["account_id"], character["id"])
        value, _ = self.journal.read(key)
        if value is None:
            return character
        state = _checked(value["current"])
        _units(db, character["id"], state)
        updated = dict(
            character,
            builds={int(index): deepcopy(build) for index, build in state.items()},
        )
        from wakfu_server.equipment_stats import effective_character

        # Keep current SQL HP, including damage/death; do not replay old health
        # captured during an equipment edit over a later fight or reward.
        return effective_character(updated)

    def save(self, account_id, generation, character_id, index, blobs):
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            lease = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, self.store.clock()),
            ).fetchone()
            if lease is None or lease["character_id"] != character_id:
                raise ValueError("Sesión o personaje inválidos.")
            character = self.store.character(account_id, character_id, db)
            validate(character, index, blobs)
            key = (account_id, character_id)
            value, encoded = self.journal.read(key)
            state = deepcopy(
                _sql(db, character_id) if value is None else _checked(value["current"])
            )
            previous = state.get(str(index), {})
            state[str(index)] = {
                name: (blobs[name] or bytes.fromhex(previous.get(name, ""))).hex()
                for name in KEYS
            }
            updated = dict(character, builds={int(i): b for i, b in state.items()})
            from wakfu_server.equipment_stats import effective_character

            effective = effective_character(updated)
            maximum = effective["max_hp"]
            hp = (
                maximum
                if character["hp"] > 0 and character["hp"] == character["max_hp"]
                else min(character["hp"], maximum)
            )
            # Redis CAS is durable before returning to the dispatcher/ACK.
            self.journal.put(
                key, state, expected=encoded, baseline=_sql(db, character_id)
            )
            # Health is a separate immediate domain; no build rows are written.
            db.execute(
                "UPDATE characters SET hp=?,max_hp=? WHERE account_id=? AND id=?",
                (hp, maximum, account_id, character_id),
            )
            from wakfu_server import health_store

            health_store.schema(db)
            now_ms = int(self.store.clock() * 1000)
            db.execute(
                "UPDATE character_regeneration SET initial_hp=?,started_ms=?,last_ms=? WHERE character_id=?",
                (hp, now_ms, now_ms, character_id),
            )
            return self.store.character(account_id, character_id, db)

    def flush(self):
        with self.lock:
            with self.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                dirty = [
                    (key, value, encoded)
                    for key, value, encoded in self.journal.records()
                    if value["current"] != value["baseline"]
                ]
                for key, value, _ in dirty:
                    self._key(key)
                    current = _checked(value["current"])
                    owner = db.execute(
                        "SELECT account_id FROM characters WHERE id=?", (key[1],)
                    ).fetchone()
                    if owner is None or owner["account_id"] != key[0]:
                        raise StateJournalError("Foreign build journal character")
                    _units(db, key[1], current)
                    saved = _sql(db, key[1])
                    if saved == current:
                        continue  # SQL commit succeeded before checkpoint outage.
                    if saved != value["baseline"]:
                        raise StateJournalError("SQLite build revision conflict")
                    # Never delete unrelated inventory/HP/progression state.
                    for index, build in current.items():
                        db.execute(
                            "INSERT INTO character_builds VALUES(?,?,?,?,?,?) ON CONFLICT(character_id,build_index) "
                            "DO UPDATE SET sheet=excluded.sheet,equipment=excluded.equipment,deck=excluded.deck,aptitudes=excluded.aptitudes",
                            (
                                key[1],
                                int(index),
                                *(bytes.fromhex(build[name]) for name in KEYS),
                            ),
                        )
            for key, _, encoded in dirty:
                self.journal.checkpoint(key, encoded)
            self.last_flush = self.clock()
            return len(dirty)

    def flush_due(self):
        return self.flush() if self.clock() - self.last_flush >= self.interval else 0

    def close(self):
        return self.flush()
