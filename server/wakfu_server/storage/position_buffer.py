"""Single-process authoritative positions with generation-safe PostgreSQL batches.

A crash may lose the unflushed interval. Graceful lifecycle barriers must flush
successfully before logout, map transition, character switch or process exit.
The caller owns the live-session registry and validated movement paths.
"""
import threading

_KEYS = ("map_id", "instance_id", "x", "y", "z")


class Positions:
    def __init__(self, store, *, lease_active):
        self.store = store
        self.lease_active = lease_active
        self.lock = threading.RLock()
        self.entries = {}
        self.evictions = []

    def attach(self, account_id, generation, character):
        key = (account_id, generation, character["id"])
        with self.lock, self.store.connection() as db:
            row = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
                (account_id, generation, self.store.now()),
            ).fetchone()
            if row is None or row["character_id"] != character["id"]:
                raise ValueError("Invalid buffered position session")
            saved = self.store.character(account_id, character["id"], db)
            if any(saved[k] != character[k] for k in _KEYS):
                raise ValueError("Buffered position baseline does not match storage")
            if key in self.entries and self.entries[key]["dirty"]:
                raise ValueError("Flush buffered position before attaching again")
            self.entries[key] = {
                "current": dict(character),
                "persisted": {k: saved[k] for k in _KEYS},
                "dirty": False,
            }
            return dict(character)

    def move(self, account_id, generation, character_id, start, end):
        key = (account_id, generation, character_id)
        with self.lock:
            entry = self.entries.get(key)
            if entry is None or not self.lease_active(*key):
                raise ValueError("Stale buffered position session")
            current = entry["current"]
            if any(current[k] != start[k] for k in ("x", "y", "z")):
                raise ValueError("Position origin is desynchronized")
            for axis, bits in (("x", 32), ("y", 32), ("z", 16)):
                if type(end.get(axis)) is not int or not -(1 << (bits - 1)) <= end[
                    axis
                ] < (1 << (bits - 1)):
                    raise ValueError("Invalid buffered position coordinate")
            current.update({k: end[k] for k in ("x", "y", "z")})
            entry["dirty"] = any(current[k] != entry["persisted"][k] for k in _KEYS)
            return dict(current)

    def merge(self, account_id, generation, character):
        """Merge refreshed HP/build fields without restoring an old DB position."""
        key = (account_id, generation, character["id"])
        with self.lock:
            entry = self.entries.get(key)
            if entry is None or not self.lease_active(*key):
                raise ValueError("Stale buffered position session")
            entry["current"] = {**character, **{k: entry["current"][k] for k in _KEYS}}
            return dict(entry["current"])

    def flush(self, *, account_id=None, generation=None, character_id=None):
        """One transaction; failure preserves all pending entries for retry.

        Stale stored generations are evicted without writing and reported via
        evictions; they cannot poison live entries. CAS conflicts abort the batch;
        callers must resolve/release that entry rather than silently losing data.
        """
        with self.lock:
            selected = [
                (key, e)
                for key, e in self.entries.items()
                if e["dirty"]
                and (account_id is None or key[0] == account_id)
                and (generation is None or key[1] == generation)
                and (character_id is None or key[2] == character_id)
            ]
            if not selected:
                return 0
            committed = []
            stale = []
            with self.store.connection() as db:
                for (account, gen, cid), entry in sorted(selected):
                    session = db.execute(
                        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
                        (account, gen, self.store.now()),
                    ).fetchone()
                    if session is None or session["character_id"] != cid:
                        stale.append((account, gen, cid))
                        continue
                    if not self.lease_active(account, gen, cid):
                        raise ValueError("Live lease unavailable for buffered position")
                    old = entry["persisted"]
                    new = entry["current"]
                    result = db.execute(
                        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s "
                        "AND map_id=%s AND instance_id=%s AND x=%s AND y=%s AND z=%s",
                        (
                            new["x"],
                            new["y"],
                            new["z"],
                            cid,
                            account,
                            *[old[k] for k in _KEYS],
                        ),
                    )
                    if result.rowcount != 1:
                        raise ValueError("Buffered position storage CAS conflict")
                    committed.append(((account, gen, cid), entry))
            for key in stale:
                self.entries.pop(key, None)
                self.evictions.append(key)
            for key, entry in committed:
                entry["persisted"] = {k: entry["current"][k] for k in _KEYS}
                entry["dirty"] = False
            return len(committed)

    def release(self, account_id, generation, character_id, *, discard_stale=False):
        key = (account_id, generation, character_id)
        with self.lock:
            entry = self.entries.get(key)
            if entry is not None and entry["dirty"] and not discard_stale:
                raise ValueError("Flush position before release")
            if discard_stale and self.lease_active(*key):
                raise ValueError("Cannot discard a live authoritative position")
            self.entries.pop(key, None)
