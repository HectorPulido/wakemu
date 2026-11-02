"""Stage one durable movement without publishing an uncommitted position."""
from contextlib import contextmanager
import copy

from wakfu_server.position_buffer import Positions, PositionOwnerBusy

_KEYS = ("map_id", "instance_id", "x", "y", "z", "direction")


class StagedMove:
    def __init__(self, positions, account_id, generation, character_id, start, end):
        self.positions = positions
        self.key = (account_id, generation, character_id)
        entry = positions.entries.get(self.key)
        if entry is None or not positions.lease_active(*self.key):
            raise ValueError("Stale buffered movement session")
        if (
            entry["dirty"]
            or self.key in getattr(positions, "mirrors", {})
            or self.key in getattr(positions, "pending_acks", {})
        ):
            raise PositionOwnerBusy("Checkpoint movement before a durable choice")
        self.entry = entry
        self.current = dict(entry["current"])
        self.persisted = dict(entry["persisted"])
        if any(self.current[k] != start[k] for k in ("x", "y", "z")):
            raise ValueError("Position origin is desynchronized")
        for axis, bits in (("x", 32), ("y", 32), ("z", 16)):
            if type(end.get(axis)) is not int or not -(1 << (bits - 1)) <= end[axis] < (
                1 << (bits - 1)
            ):
                raise ValueError("Invalid buffered position coordinate")
        direction = end.get("direction", self.current["direction"])
        if type(direction) is not int or not 0 <= direction <= 7:
            raise ValueError("Invalid buffered position direction")
        self.end = dict(end, direction=direction)
        # Validate with the ordinary algorithm before any durable choice write.
        # RedisPositions.move writes a journal; it must never run after COMMIT.
        candidate = Positions(positions.store, lease_active=positions.lease_active)
        candidate.entries[self.key] = copy.deepcopy(entry)
        self.result = candidate.move(*self.key, self.current, self.end)
        self.candidate = candidate.entries[self.key]
        self.candidate["persisted"] = {k: self.result[k] for k in _KEYS}
        self.candidate["dirty"] = False
        self.prepared = False
        self.accepted = False

    def persist(self, db):
        """Join the choice transaction using the normal persisted-position CAS."""
        if self.prepared:
            raise ValueError("Buffered movement already persisted in this transaction")
        if self.positions.entries.get(
            self.key
        ) is not self.entry or not self.positions.lease_active(*self.key):
            raise ValueError("Buffered movement lease changed before persistence")
        account, _generation, character = self.key
        row = db.execute(
            "UPDATE characters SET x=%s,y=%s,z=%s,direction=%s WHERE id=%s AND account_id=%s "
            "AND map_id=%s AND instance_id=%s AND x=%s AND y=%s AND z=%s AND direction=%s",
            (
                *[self.end[k] for k in ("x", "y", "z", "direction")],
                character,
                account,
                *[self.persisted[k] for k in _KEYS],
            ),
        )
        if row.rowcount != 1:
            raise ValueError("Buffered movement storage CAS conflict")
        self.prepared = True

    def commit(self, commit_transaction):
        """Commit only a prevalidated clean baseline, then adopt without I/O."""
        if not self.prepared or self.accepted or not callable(commit_transaction):
            raise ValueError("Buffered movement commit is not adoptable")
        if (
            self.positions.entries.get(self.key) is not self.entry
            or self.entry["dirty"]
            or self.key in getattr(self.positions, "mirrors", {})
            or self.key in getattr(self.positions, "pending_acks", {})
            or not self.positions.lease_active(*self.key)
        ):
            raise PositionOwnerBusy("Durable movement lost its clean owner")
        commit_transaction()
        return self._accept()

    def _accept(self):
        """The caller retains the account barrier through successful adoption."""
        # The account barrier remains held. No Redis, lease query, conversion,
        # or movement validation is allowed after the SQL commit callback.
        with self.positions.lock:
            self.positions.entries[self.key] = self.candidate
        self.accepted = True
        return self.result


@contextmanager
def stage_move(positions, account_id, generation, character_id, start, end):
    """Keep the ordinary account barrier through validation, SQL and adoption."""
    with positions.account_barrier(account_id, blocking=False):
        yield StagedMove(positions, account_id, generation, character_id, start, end)
