"""Durable own-fight checkpoints for evidence and authoritative actor HP.

Recovery marks interrupted fights aborted; it never reconstructs a client fight
or silently resumes a timeline. Runtime callbacks and network peers are omitted.
"""
import json
import hashlib
import time
from psycopg.types.json import Jsonb
from dataclasses import asdict
from .combat_state_ledger import StateLedger
from .combat_character_copy_book import CopyBookAction

EPHEMERAL_FIGHT_FIELDS = frozenset(
    {
        "actors",
        "native_rail_movement_authority",
        # Post-commit query-elision cache; the durable row is the real fence.
        "native_consumable_handoff_committed",
        # A live session fence, invalidated on disconnect; interrupted fights
        # are aborted rather than resumed with this authority.
        "native_instance_publication_lease",
    }
)


def checkpoint_digest(state):
    """Stable identity for reconciling an uncertain write without retaining its FSM."""
    return hashlib.sha256(
        json.dumps(
            state, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _trace_stage(
    trace, stage, fight_id, *, elapsed_ms=None, count=None, operation="save"
):
    if trace is None:
        return
    event = {"fight_id": fight_id, "operation": operation}
    if elapsed_ms is not None:
        event["elapsed_ms"] = round(max(0.0, elapsed_ms), 3)
    if count is not None:
        event["count"] = count
    try:
        trace(stage, **event)
    except Exception:
        # Instrumentation is strictly observational.
        pass


def _plain(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    from wakfu_server.characters.owned_social_context import OwnedSocialContext

    if type(value) is OwnedSocialContext:
        return value.to_record()
    from .combat_carrying import NativeCarryPair
    from .combat_instance_level_group import InstanceDifficultySnapshot

    if isinstance(value, NativeCarryPair):
        # Persistent reciprocal carry authority is a typed immutable record,
        # not a runtime callback. Preserve every field in the checkpoint.
        return _plain(asdict(value))
    if isinstance(value, CopyBookAction):
        # eZd publishes immutable owned UI actions. Keep every exact UID and
        # native field in both durable evidence and transaction source guards.
        value.validate()
        return _plain(asdict(value))
    if isinstance(value, InstanceDifficultySnapshot):
        # The published instance difficulty is authoritative gameplay input.
        # Keep its exact actor/source binding in the durable snapshot.
        return _plain(asdict(value))
    if isinstance(value, StateLedger):
        return dict(
            actor_id=value.actor_id,
            entries=[_plain(asdict(entry)) for entry in value.entries],
        )
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_plain(v) for v in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    raise ValueError("Fight contains nonserializable state")


def snapshot(fight, *, runtime=None):
    state = {
        key: _plain(value)
        for key, value in fight.__dict__.items()
        if key not in EPHEMERAL_FIGHT_FIELDS
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
            for key in (
                "action_id",
                "native_action_id",
                "awaiting_ack",
                "round",
                "duration",
            )
        }
        # Pending wire packets are derived presentation, not checkpoint gameplay state.
    return state


class Checkpoints:
    def __init__(self, store):
        self.store = store

    def save_shared(self, shared, account_id, generation, *, status=None, trace=None):
        """Checkpoint one canonical shared FSM with a fight-wide revision.

        Each owner has a socket-local dispatcher closure, but all those
        closures refer to the same fight. Keep snapshot selection and CAS
        revision advancement under the shared fight lock so a joiner or the
        other owner cannot race a stale per-socket revision into storage.
        """
        lock_started = time.monotonic()
        _trace_stage(trace, "lock_wait", shared.fight.id)
        with shared.lock:
            _trace_stage(
                trace,
                "lock_acquired",
                shared.fight.id,
                elapsed_ms=(time.monotonic() - lock_started) * 1000,
            )
            if shared.checkpoint_terminal:
                return shared.checkpoint_revision, True
            fight = shared.fight
            revision = self.save(
                account_id,
                generation,
                fight,
                expected_revision=shared.checkpoint_revision,
                runtime=shared.runtime,
                trace=trace,
            )
            shared.checkpoint_revision = revision
            if status is not None:
                revision = self.end(
                    account_id,
                    generation,
                    fight.id,
                    expected_revision=revision,
                    status=status,
                    trace=trace,
                )
                shared.checkpoint_revision = revision
                shared.checkpoint_terminal = True
            return revision, shared.checkpoint_terminal

    def _session(self, db, account_id, generation):
        row = db.execute(
            "SELECT * FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
            (account_id, generation, self.store.now()),
        ).fetchone()
        if row is None:
            raise ValueError("Fight checkpoint session is stale")
        return row

    @staticmethod
    def _participant(db, account_id, generation, character_id, fight_id):
        row = db.execute(
            "SELECT p.team,p.session_generation,f.status,"
            "EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE "
            "w.fight_id=p.fight_id AND w.character_id=p.character_id) AS withdrawn "
            "FROM combat_fights f "
            "JOIN combat_fight_participants p ON p.fight_id=f.id "
            "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s "
            "FOR UPDATE OF f,p",
            (fight_id, character_id, account_id),
        ).fetchone()
        if (
            row is None
            or row["session_generation"] not in (None, generation)
            or row["withdrawn"]
        ):
            raise ValueError("Missing or stale shared fight participant")
        return row

    @staticmethod
    def _validate_roster(db, fight):
        rows = tuple(
            db.execute(
                "SELECT character_id,account_id,team FROM combat_fight_participants "
                "WHERE fight_id=%s ORDER BY character_id",
                (fight.id,),
            )
        )
        durable = {row["character_id"]: row["account_id"] for row in rows}
        from .combat_terminal_metadata import registered_summon_actor_ids

        from .combat_companions import registered_companion_ids

        summon_ids = registered_summon_actor_ids(fight) | registered_companion_ids(
            fight
        )
        controlled = {
            actor.id: actor.owner_id
            for actor in fight.actors.values()
            if actor.controlled and actor.id not in summon_ids
        }
        if not durable or durable != controlled:
            raise ValueError("Checkpoint fight roster differs from durable members")
        from .combat_companions import validate_durable_roster

        validate_durable_roster(db, fight)
        if any(fight.actors[row["character_id"]].team != row["team"] for row in rows):
            raise ValueError("Checkpoint participant team differs from durable member")

    def save(
        self,
        account_id,
        generation,
        fight,
        *,
        expected_revision=None,
        runtime=None,
        trace=None,
    ):
        if not any(
            a.controlled and a.owner_id == account_id for a in fight.actors.values()
        ):
            raise ValueError("Account does not own a fight participant")
        snapshot_started = time.monotonic()
        _trace_stage(trace, "snapshot_started", fight.id, count=len(fight.actors))
        state = snapshot(fight, runtime=runtime)
        _trace_stage(
            trace,
            "snapshot_finished",
            fight.id,
            elapsed_ms=(time.monotonic() - snapshot_started) * 1000,
            count=len(fight.actors),
        )
        return self.save_prepared(
            account_id,
            generation,
            fight,
            state,
            expected_revision=expected_revision,
            trace=trace,
        )

    def save_prepared(
        self,
        account_id,
        generation,
        fight,
        state,
        *,
        expected_revision=None,
        trace=None,
        allow_terminal_receipt=False,
    ):
        """Persist a detached immutable checkpoint through the same ownership CAS."""
        if not any(
            a.controlled and a.owner_id == account_id for a in fight.actors.values()
        ):
            raise ValueError("Account does not own a fight participant")
        json.dumps(state, allow_nan=False)
        encoded = Jsonb(state)
        pool_started = time.monotonic()
        _trace_stage(trace, "pool_wait", fight.id, count=len(fight.actors))
        with self.store.connection() as db:
            _trace_stage(
                trace,
                "pool_acquired",
                fight.id,
                elapsed_ms=(time.monotonic() - pool_started) * 1000,
                count=len(fight.actors),
            )
            _trace_stage(trace, "fight_query_started", fight.id)
            try:
                durable_fight = db.execute(
                    "SELECT id,status FROM combat_fights WHERE id=%s FOR UPDATE",
                    (fight.id,),
                ).fetchone()
            finally:
                _trace_stage(trace, "fight_query_finished", fight.id)
            if durable_fight is None:
                raise ValueError("Missing durable fight")
            session_started = time.monotonic()
            _trace_stage(trace, "session_query_started", fight.id)
            try:
                session = self._session(db, account_id, generation)
            finally:
                _trace_stage(
                    trace,
                    "session_query_finished",
                    fight.id,
                    elapsed_ms=(time.monotonic() - session_started) * 1000,
                )
            actor = fight.actors.get(session["character_id"])
            if actor is None or not actor.controlled or actor.owner_id != account_id:
                raise ValueError(
                    "Selected character does not participate in this fight"
                )
            self._participant(
                db, account_id, generation, session["character_id"], fight.id
            )
            self._validate_roster(db, fight)
            row = db.execute(
                "SELECT * FROM fight_checkpoints WHERE fight_id=%s", (fight.id,)
            ).fetchone()
            if (
                row is not None
                and self._participant_generation_is_legacy(
                    db, account_id, fight.id, session["character_id"]
                )
                and (row["account_id"] != account_id or row["generation"] != generation)
            ):
                raise ValueError("Stale shared fight writer generation")
            if (
                allow_terminal_receipt
                and row is not None
                and durable_fight["status"] == "finished"
                and row["status"] == "ended"
                and row["snapshot"].get("phase") == "finished"
                and (expected_revision is None or row["revision"] >= expected_revision)
            ):
                return dict(revision=row["revision"], terminal=True)
            if row is None:
                if expected_revision is not None:
                    raise ValueError("Fight checkpoint revision does not exist")
                db.execute(
                    "INSERT INTO fight_checkpoints VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        fight.id,
                        account_id,
                        generation,
                        1,
                        "active",
                        encoded,
                        self.store.now(),
                    ),
                )
                revision = 1
            else:
                if row["status"] != "active" or row["revision"] != expected_revision:
                    raise ValueError("Stale or foreign fight checkpoint")
                revision = row["revision"] + 1
                db.execute(
                    "UPDATE fight_checkpoints SET account_id=%s,generation=%s,revision=%s,snapshot=%s,updated_at=%s WHERE fight_id=%s",
                    (
                        account_id,
                        generation,
                        revision,
                        encoded,
                        self.store.now(),
                        fight.id,
                    ),
                )
            from .combat_captured_roster_checkpoint import (
                persist_captured_roster_updates,
            )

            persist_captured_roster_updates(db, fight)
            from .combat_consumable_handoff import persist as persist_consumable_handoff

            consumable_handoffs = persist_consumable_handoff(self.store, db, fight)
            if getattr(fight, "boss_score_profile", None) is not None:
                from wakfu_server.maps.boss_score_runtime import persist

                persist(db, fight)
            if getattr(fight, "rift_wave_state", None) is not None:
                from wakfu_server.rift_runtime import persist_progress

                # Accepted wave receipts and this immutable fight snapshot
                # commit together; a rejected checkpoint rolls both back.
                persist_progress(db, fight)
        from .combat_consumable_handoff import mark_committed

        mark_committed(fight, consumable_handoffs)
        _trace_stage(
            trace,
            "committed",
            fight.id,
            elapsed_ms=(time.monotonic() - pool_started) * 1000,
            count=len(fight.actors),
        )
        return revision

    @staticmethod
    def _read_snapshot(raw):
        from .combat_checkpoint_containers import reconstruct_state_containers

        return reconstruct_state_containers(raw)

    @staticmethod
    def _participant_generation_is_legacy(db, account_id, fight_id, character_id):
        row = db.execute(
            "SELECT session_generation FROM combat_fight_participants "
            "WHERE fight_id=%s AND character_id=%s AND account_id=%s",
            (fight_id, character_id, account_id),
        ).fetchone()
        return row is not None and row["session_generation"] is None

    def read(self, account_id, fight_id):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT c.* FROM fight_checkpoints c JOIN combat_fight_participants p "
                "ON p.fight_id=c.fight_id WHERE c.fight_id=%s AND p.account_id=%s",
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
                snapshot=self._read_snapshot(row["snapshot"]),
            )

    def reconcile_write(
        self,
        account_id,
        generation,
        fight,
        state,
        *,
        expected_revision,
        status=None,
        snapshot_digest=None,
        receipt_writer=None,
    ):
        """Resolve a lost write response without relaxing session or revision CAS.

        Only an identical next revision owned by this writer is our receipt.
        An unchanged revision means the write did not commit and can be retried.
        A separately settled finished fight may supersede an obsolete snapshot.
        """
        expected_digest = snapshot_digest or checkpoint_digest(state)
        with self.store.connection() as db:
            durable = db.execute(
                "SELECT id,status FROM combat_fights WHERE id=%s FOR UPDATE",
                (fight.id,),
            ).fetchone()
            if durable is None:
                raise ValueError("Missing durable fight")
            session = self._session(db, account_id, generation)
            self._participant(
                db, account_id, generation, session["character_id"], fight.id
            )
            actor = fight.actors.get(session["character_id"])
            if actor is None or not actor.controlled or actor.owner_id != account_id:
                raise ValueError(
                    "Selected character does not participate in this fight"
                )
            row = db.execute(
                "SELECT account_id,generation,status,revision,snapshot "
                "FROM fight_checkpoints WHERE fight_id=%s",
                (fight.id,),
            ).fetchone()
            if (
                row is not None
                and self._participant_generation_is_legacy(
                    db, account_id, fight.id, session["character_id"]
                )
                and (row["account_id"] != account_id or row["generation"] != generation)
            ):
                raise ValueError("Stale shared fight writer generation")
            writer_account, writer_generation = receipt_writer or (
                account_id,
                generation,
            )
            return self._reconcile_receipt(
                row,
                durable,
                writer_account,
                writer_generation,
                expected_revision,
                status,
                expected_digest,
            )

    @staticmethod
    def _reconcile_receipt(
        row, durable, account_id, generation, expected_revision, status, expected_digest
    ):
        if row is None:
            if expected_revision is None and status is None:
                return dict(committed=False, revision=None, terminal=False)
            raise ValueError("Fight checkpoint revision does not exist")
        if (
            status in (None, "ended")
            and durable["status"] == "finished"
            and row["status"] == "ended"
            and row["snapshot"].get("phase") == "finished"
            and row["revision"] >= (expected_revision or 0)
        ):
            return dict(committed=True, revision=row["revision"], terminal=True)
        if row["revision"] == expected_revision and row["status"] == "active":
            return dict(committed=False, revision=row["revision"], terminal=False)
        if (
            row["revision"] == (expected_revision or 0) + 1
            and row["account_id"] == account_id
            and row["generation"] == generation
            and row["status"] == (status or "active")
            and checkpoint_digest(Checkpoints._read_snapshot(row["snapshot"]))
            == expected_digest
        ):
            return dict(
                committed=True, revision=row["revision"], terminal=status is not None
            )
        raise ValueError("Checkpoint response cannot be reconciled with owned write")

    def recover_write_for_takeover(
        self,
        account_id,
        previous_generation,
        generation,
        fight,
        recovery,
        *,
        recovery_generations=(),
    ):
        """Authenticate the replacement before reconciling and fencing old work.

        The old login is no longer valid in sessions. It identifies the expected
        participant lease and lost-write receipt; it never authenticates a new
        write. All receipt checks and membership fencing share this transaction.
        """
        from .fight_store import _takeover_account_memberships

        with self.store.connection() as db:
            durable = db.execute(
                "SELECT id,status FROM combat_fights WHERE id=%s FOR UPDATE",
                (fight.id,),
            ).fetchone()
            if durable is None:
                raise ValueError("Missing durable fight")
            session = self._session(db, account_id, generation)
            actor = fight.actors.get(session["character_id"])
            if actor is None or not actor.controlled or actor.owner_id != account_id:
                raise ValueError(
                    "Selected character does not participate in this fight"
                )
            member = db.execute(
                "SELECT p.session_generation, EXISTS(SELECT 1 FROM fight_health_exits e "
                "WHERE e.fight_id=p.fight_id AND e.character_id=p.character_id "
                "AND e.return_acknowledged_at IS NOT NULL) AS returned "
                "FROM combat_fight_participants p WHERE p.fight_id=%s "
                "AND p.character_id=%s AND p.account_id=%s FOR UPDATE",
                (fight.id, session["character_id"], account_id),
            ).fetchone()
            if (
                member is None
                or member["returned"]
                or member["session_generation"]
                not in (previous_generation, generation, *recovery_generations)
            ):
                raise ValueError("Stale durable combat participant generation")
            row = db.execute(
                "SELECT account_id,generation,status,revision,snapshot "
                "FROM fight_checkpoints WHERE fight_id=%s",
                (fight.id,),
            ).fetchone()
            receipt = self._reconcile_receipt(
                row,
                durable,
                recovery["account_id"],
                recovery["generation"],
                recovery["revision"],
                recovery["status"],
                recovery["digest"],
            )
            _takeover_account_memberships(
                db, fight.id, account_id, generation, member["session_generation"]
            )
            return receipt

    def end(
        self,
        account_id,
        generation,
        fight_id,
        *,
        expected_revision,
        status="ended",
        trace=None,
        allow_terminal_receipt=False,
    ):
        if status not in ("ended", "aborted"):
            raise ValueError("Invalid checkpoint terminal status")
        pool_started = time.monotonic()
        _trace_stage(trace, "pool_wait", fight_id, operation="end")
        with self.store.connection() as db:
            _trace_stage(
                trace,
                "pool_acquired",
                fight_id,
                elapsed_ms=(time.monotonic() - pool_started) * 1000,
                operation="end",
            )
            durable_fight = db.execute(
                "SELECT id,status FROM combat_fights WHERE id=%s FOR UPDATE",
                (fight_id,),
            ).fetchone()
            if durable_fight is None:
                raise ValueError("Missing durable fight")
            self._session(db, account_id, generation)
            member = db.execute(
                "SELECT session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s AND character_id=(SELECT character_id FROM sessions "
                "WHERE account_id=%s AND generation=%s) AND account_id=%s FOR UPDATE",
                (fight_id, account_id, generation, account_id),
            ).fetchone()
            if member is None or member["session_generation"] not in (None, generation):
                raise ValueError("Missing or stale shared fight participant")
            checkpoint = db.execute(
                "SELECT account_id,generation,status,revision,snapshot FROM fight_checkpoints WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()
            if checkpoint is None:
                raise ValueError("Fight checkpoint does not exist")
            if member["session_generation"] is None and (
                checkpoint["account_id"] != account_id
                or checkpoint["generation"] != generation
            ):
                raise ValueError("Stale shared fight writer generation")
            if (
                allow_terminal_receipt
                and status == "ended"
                and durable_fight["status"] == "finished"
                and checkpoint["status"] == "ended"
                and checkpoint["snapshot"].get("phase") == "finished"
                and checkpoint["revision"] >= expected_revision
            ):
                return checkpoint["revision"]
            cursor = db.execute(
                "UPDATE fight_checkpoints SET account_id=%s,generation=%s,status=%s,revision=revision+1,updated_at=%s WHERE fight_id=%s AND revision=%s AND status='active'",
                (
                    account_id,
                    generation,
                    status,
                    self.store.now(),
                    fight_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Stale or foreign fight checkpoint")
            if status == "aborted":
                db.execute(
                    "UPDATE combat_fights SET status='aborted' WHERE id=%s AND status IN ('placement','active')",
                    (fight_id,),
                )
                from wakfu_server.rift_runtime import abort_bound_fight

                abort_bound_fight(db, fight_id)
            revision = expected_revision + 1
        _trace_stage(
            trace,
            "committed",
            fight_id,
            elapsed_ms=(time.monotonic() - pool_started) * 1000,
            operation="end",
        )
        return revision

    def recover_interrupted(self):
        """Startup-only; preserve last actor HP/resources while marking lost fights."""
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE status IN ('placement','active')"
            )
            cursor = db.execute(
                "UPDATE fight_checkpoints c SET status='aborted',"
                "revision=revision+1,updated_at=%s WHERE c.status='active' "
                "AND NOT EXISTS(SELECT 1 FROM combat_fights f "
                "WHERE f.id=c.fight_id AND f.status='finished')",
                (self.store.now(),),
            )
            return cursor.rowcount
