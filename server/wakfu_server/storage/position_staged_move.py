"""SQL transaction orchestration for a prevalidated native movement token."""

from contextlib import contextmanager

from wakfu_server.position_buffer import PositionOwnerBusy

_KEYS = ("map_id", "instance_id", "x", "y", "z", "direction")


class StagedMove:
    def __init__(self, positions, account_id, generation, character_id, start, end):
        self.positions = positions
        self.key = (account_id, generation, character_id)
        state = positions.entry_state(self.key)
        plan = positions._call(
            "stage_prepare",
            key=list(self.key),
            start={k: start[k] for k in ("x", "y", "z")},
            end={k: end[k] for k in ("x", "y", "z", "direction") if k in end},
            lease_active=state is not None and bool(positions.lease_active(*self.key)),
        )
        self.token = plan["token"]
        self.revision = plan["revision"]
        self.current = positions._character(self.key, plan["current"])
        self.persisted = plan["persisted"]
        self.end = plan["result"]
        self.result = positions._character(self.key, plan["result"])
        self.prepared = False
        self.accepted = False

    def _validate(self, phase):
        self.positions._call(
            "stage_validate",
            token=self.token,
            lease_active=bool(self.positions.lease_active(*self.key)),
            phase=phase,
        )

    def persist(self, db):
        """Join the caller's SQL choice transaction using the native CAS plan."""
        if self.prepared:
            raise ValueError("Buffered movement already persisted in this transaction")
        self._validate("persist")
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
        if not self.prepared or self.accepted or not callable(commit_transaction):
            raise ValueError("Buffered movement commit is not adoptable")
        self._validate("commit")
        commit_transaction()
        return self._accept()

    def _accept(self):
        # The account I/O guard retains this already validated native token.
        # Adopting it performs no Redis/SQL I/O or new lease validation.
        self.positions._call("stage_commit", token=self.token)
        self.accepted = True
        return self.result

    def abort(self):
        if not self.accepted:
            self.positions._call("abort", token=self.token)


@contextmanager
def stage_move(positions, account_id, generation, character_id, start, end):
    with positions.account_barrier(account_id, blocking=False):
        staged = StagedMove(positions, account_id, generation, character_id, start, end)
        try:
            yield staged
        finally:
            staged.abort()
