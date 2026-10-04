"""Durable own-fight checkpoints for evidence and authoritative actor HP.

Recovery marks interrupted fights aborted; it never reconstructs a client fight
or silently resumes a timeline. Runtime callbacks and network peers are omitted.
"""
import json
from dataclasses import asdict
from .combat_state_ledger import StateLedger


def _plain(value):
    if isinstance(value, StateLedger):
        return dict(
            actor_id=value.actor_id,
            entries=[_plain(asdict(entry)) for entry in value.entries],
        )
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_plain(v) for v in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    raise ValueError("Fight contains nonserializable state")


def snapshot(fight, *, runtime=None):
    state = {
        key: _plain(value) for key, value in fight.__dict__.items() if key != "actors"
    }
    state["actors"] = {
        str(identity): _plain(actor.__dict__)
        for identity, actor in fight.actors.items()
    }
    if runtime is not None:
        if runtime.fight is not fight:
            raise ValueError("Runtime belongs to another fight")
        state["runtime"] = {
            key: _plain(getattr(runtime, key))
            for key in ("action_id", "awaiting_ack", "round", "duration")
        }
        # Pending wire packets are derived presentation, not checkpoint gameplay state.
    return state


class Checkpoints:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS fight_checkpoints (
                fight_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
                generation TEXT NOT NULL, revision INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','ended','aborted')),
                snapshot TEXT NOT NULL, updated_at REAL NOT NULL)"""
            )

    def _session(self, db, account_id, generation):
        row = db.execute(
            "SELECT * FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
            (account_id, generation, self.store.clock()),
        ).fetchone()
        if row is None:
            raise ValueError("Fight checkpoint session is stale")
        return row

    def save(
        self, account_id, generation, fight, *, expected_revision=None, runtime=None
    ):
        if not any(
            a.controlled and a.owner_id == account_id for a in fight.actors.values()
        ):
            raise ValueError("Account does not own a fight participant")
        state = snapshot(fight, runtime=runtime)
        encoded = json.dumps(state, separators=(",", ":"), allow_nan=False)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = self._session(db, account_id, generation)
            actor = fight.actors.get(session["character_id"])
            if actor is None or not actor.controlled or actor.owner_id != account_id:
                raise ValueError(
                    "Selected character does not participate in this fight"
                )
            row = db.execute(
                "SELECT * FROM fight_checkpoints WHERE fight_id=?", (fight.id,)
            ).fetchone()
            if row is None:
                if expected_revision is not None:
                    raise ValueError("Fight checkpoint revision does not exist")
                db.execute(
                    "INSERT INTO fight_checkpoints VALUES(?,?,?,?,?,?,?)",
                    (
                        fight.id,
                        account_id,
                        generation,
                        1,
                        "active",
                        encoded,
                        self.store.clock(),
                    ),
                )
                return 1
            if (
                row["account_id"] != account_id
                or row["generation"] != generation
                or row["status"] != "active"
                or row["revision"] != expected_revision
            ):
                raise ValueError("Stale or foreign fight checkpoint")
            revision = row["revision"] + 1
            db.execute(
                "UPDATE fight_checkpoints SET revision=?,snapshot=?,updated_at=? WHERE fight_id=?",
                (revision, encoded, self.store.clock(), fight.id),
            )
            return revision

    def read(self, account_id, fight_id):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM fight_checkpoints WHERE fight_id=? AND account_id=?",
                (fight_id, account_id),
            ).fetchone()
            if row is None:
                raise ValueError("Fight checkpoint does not belong to this account")
            return dict(
                fight_id=fight_id,
                generation=row["generation"],
                revision=row["revision"],
                status=row["status"],
                updated_at=row["updated_at"],
                snapshot=json.loads(row["snapshot"]),
            )

    def end(
        self, account_id, generation, fight_id, *, expected_revision, status="ended"
    ):
        if status not in ("ended", "aborted"):
            raise ValueError("Invalid checkpoint terminal status")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._session(db, account_id, generation)
            cursor = db.execute(
                "UPDATE fight_checkpoints SET status=?,revision=revision+1,updated_at=? WHERE fight_id=? AND account_id=? AND generation=? AND revision=? AND status='active'",
                (
                    status,
                    self.store.clock(),
                    fight_id,
                    account_id,
                    generation,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Stale or foreign fight checkpoint")
            return expected_revision + 1

    def recover_interrupted(self):
        """Startup-only; preserve last actor HP/resources while marking lost fights."""
        with self.store.connection() as db:
            cursor = db.execute(
                "UPDATE fight_checkpoints SET status='aborted',revision=revision+1,updated_at=? WHERE status='active'",
                (self.store.clock(),),
            )
            return cursor.rowcount
