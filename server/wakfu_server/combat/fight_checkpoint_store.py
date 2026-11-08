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
        "_native_retained_owner",
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


# Declaration order matches RunningState; each result remains caller-owned.
_STATE_FIELDS = (
    ("uid", int, False),
    ("reference", int, False),
    ("level", int, False),
    ("caster_id", int, False),
    ("target_id", int, False),
    ("duration", int, False),
    ("clock_actor", str, False),
    ("tick_at_turn_end", bool, False),
    ("effect_ids", tuple, False),
    ("realtime_duration", int, False),
    ("retained", bool, False),
    ("timer", object, True),
    ("protected", bool, True),
    ("realtime_deadline_ms", int, True),
    ("realtime_in_combat", bool, True),
)
_MISSING_STATE_FIELD = object()


def _plain_state_entry(entry):
    """Avoid asdict's recursive deepcopy for exact native scalar carriers."""
    from .combat_state_ledger import RunningState
    from .combat_state_timing import StateTimer

    if type(entry) is RunningState and len(vars(entry)) == len(_STATE_FIELDS):
        fields = vars(entry)
        result = {}
        for name, expected, optional in _STATE_FIELDS:
            value = fields.get(name, _MISSING_STATE_FIELD)
            if optional and value is None:
                result[name] = None
                continue
            if name == "timer":
                if type(value) is not StateTimer or len(vars(value)) != 3:
                    break
                timer = vars(value)
                actor = timer.get("actor_id", _MISSING_STATE_FIELD)
                round_number = timer.get("expiration_round", _MISSING_STATE_FIELD)
                phase = timer.get("phase", _MISSING_STATE_FIELD)
                if (
                    type(actor) is not int
                    or type(round_number) is not int
                    or type(phase) is not str
                ):
                    break
                value = dict(actor_id=actor, expiration_round=round_number, phase=phase)
            elif type(value) is not expected:
                break
            elif name == "effect_ids":
                if any(type(identity) is not int for identity in value):
                    break
                value = list(value)
            result[name] = value
        else:
            return result
    # Dataclass subclasses, mutable/custom values, extra fields and malformed
    # instances retain the exact legacy conversion and callback/error behavior.
    return _plain(asdict(entry))


def _plain(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    # Exact built-in containers cannot be typed native records. Recurse before
    # domain imports; subclasses retain the original dispatch and error order.
    exact = type(value)
    if exact is dict:
        return {str(k): _plain(v) for k, v in value.items()}
    if exact is list or exact is tuple:
        return [_plain(v) for v in value]
    if exact is set or exact is frozenset:
        return [_plain(v) for v in sorted(value)]
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
            entries=[_plain_state_entry(entry) for entry in value.entries],
        )
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_plain(v) for v in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    raise ValueError("Fight contains nonserializable state")


def snapshot(fight, *, runtime=None):
    from .rift_combat_adapter import creation_deliveries_snapshot

    state = {
        key: _plain(
            creation_deliveries_snapshot(value)
            if key == "native_rift_creation_deliveries"
            else value
        )
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


RECOVERY_SCHEMA = "wakemu.fight-checkpoint.v2"
_RECOVERY_FIGHT_FIELDS = (
    "id",
    "phase",
    "winner",
    "turn_id",
    "turn_index",
    "order",
    "native_timeline_round",
    "native_fight_model",
    "native_encounter_roles",
    "native_summon_registrations",
    "native_companion_sources",
    "native_consumable_initializations",
    "native_external_state_origins",
    "rift_monsters",
    "walkable",
    "edges",
    "native_qi_snapshot",
    "native_qi_slots",
    "native_qi_touched_cells",
    "native_qi_byte_topology",
    "native_qi_ignored_slots",
    "native_qi_movement_override",
    "native_los_ignored_affiliations",
    "native_ordinary_qi_retirements",
    "native_rift_birth_fence",
)
_RECOVERY_ACTOR_FIELDS = (
    "id",
    "controlled",
    "owner_id",
    "team",
    "hp",
    "max_hp",
    "effective_level",
    "position",
    "is_summon",
    "native_summon_source",
    "native_companion_source",
    "pve_withdrawn",
    "ap",
    "mp",
    "turn_count",
    "physical_radius",
    "native_obstacle_id",
    "native_los_height",
    "native_ordinary_qi_retirement",
    "native_death_status",
)
_RIFT_RECOVERY_FIELDS = (
    "instance_id",
    "wave",
    "outcome",
    "persisted_wave",
    "staged_receipts",
    "last_cleared_wave",
    "pending_wave",
    "wave_actor_ids",
    "wave_species_refs",
)
_REWARD_STATS = frozenset((33, 36, 118, 119))
_RECOVERY_ORB_FIELDS = (
    "uid",
    "reference",
    "cell",
    "native_area_contract",
    "native_qq_bhi",
    "native_qq_guard_source",
    "executing",
    "remaining_activations",
)


def recovery_snapshot(fight, *, runtime=None):
    """Build a versioned recovery/accounting projection for routine active saves.

    ``snapshot`` remains the full evidence/debug API. This projection is only
    safe because recovery aborts the fight; it never resumes the native graph.
    """
    if runtime is not None and runtime.fight is not fight:
        raise ValueError("Runtime belongs to another fight")
    state = {"checkpoint_schema": RECOVERY_SCHEMA}
    for key in _RECOVERY_FIGHT_FIELDS:
        if hasattr(fight, key):
            state[key] = _plain(getattr(fight, key))
    # These native consumers define the genuine uninitialized values as an
    # empty retirement ledger and no pending birth fence. Persist them
    # explicitly so compact QA readers can distinguish defaults from omission.
    state.setdefault("native_ordinary_qi_retirements", {})
    state.setdefault("native_rift_birth_fence", None)
    removed = getattr(fight, "native_timeline_removed", None)
    if removed is not None:
        state["native_timeline_removed_count"] = len(removed)
    areas = getattr(fight, "native_effect_areas", None)
    if isinstance(areas, dict):
        selected_areas = {}
        for identity, area in areas.items():
            if (
                area.get("reference") == 1574
                and area.get("native_area_contract") == "faY"
                and area.get("native_qq_bhi") is False
                and not area.get("executing")
                and area.get("remaining_activations", -1) != 0
            ):
                selected_areas[str(identity)] = {
                    key: _plain(area[key])
                    for key in _RECOVERY_ORB_FIELDS
                    if key in area
                }
        state["native_effect_areas"] = selected_areas
    collections = getattr(fight, "native_global_pv_collections", None)
    if isinstance(collections, dict) and "fighter_status" in collections:
        state["native_global_pv_collections"] = {
            "fighter_status": _plain(collections["fighter_status"])
        }

    state["actors"] = {
        str(identity): {
            key: _plain(actor.__dict__[key])
            for key in _RECOVERY_ACTOR_FIELDS
            if key in actor.__dict__
        }
        for identity, actor in fight.actors.items()
    }
    for identity, actor in fight.actors.items():
        stats = actor.__dict__.get("effect_stats")
        if stats is not None:
            # The reward and drop consumers use 33/36/118/119 only. Missing
            # authoritative keys remain missing so those consumers fail closed.
            state["actors"][str(identity)]["effect_stats"] = {
                str(key): _plain(stats[key]) for key in _REWARD_STATS if key in stats
            }

    wave = getattr(fight, "rift_wave_state", None)
    if isinstance(wave, dict):
        state["rift_wave_state"] = {
            key: _plain(wave[key]) for key in _RIFT_RECOVERY_FIELDS if key in wave
        }
        wave_entries = wave.get("native_wave_entries")
        if isinstance(wave_entries, dict):
            state["rift_wave_state"]["native_wave_entries"] = {
                str(identity): _plain(row)
                for identity, row in wave_entries.items()
                if isinstance(row, dict) and row.get("wave") == wave.get("wave")
            }

    if runtime is not None:
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

    # Keep only ledger rows named by durable world-consumable bindings or
    # external native-state origins. These are restored solely for health and
    # source accounting; no timer or action is resumed.
    bindings = getattr(fight, "native_consumable_initializations", {})
    external = getattr(fight, "native_external_state_origins", {})
    selected_by_actor = {}
    for raw_actor_id, rows in bindings.items():
        actor_id = int(raw_actor_id)
        selected = selected_by_actor.setdefault(actor_id, set())
        for binding in rows:
            selected.add(binding["combat_uid"])
    for raw_uid, origin in external.items():
        uid = int(raw_uid)
        selected_by_actor.setdefault(origin["character_id"], set()).add(uid)
    if bindings:
        state["native_consumable_initializations"] = _plain(bindings)
    if external:
        state["native_external_state_origins"] = _plain(external)
    payloads = getattr(fight, "state_wire_payloads", {})
    external_uids = {int(uid) for uid in external}
    selected_external = {
        uid
        for uids in selected_by_actor.values()
        for uid in uids
        if uid in external_uids
    }
    if selected_external:
        state["state_wire_payloads"] = {
            str(uid): _plain(
                payloads[str(uid)] if str(uid) in payloads else payloads[uid]
            )
            for uid in selected_external
            if str(uid) in payloads or uid in payloads
        }
    for actor_id, selected in selected_by_actor.items():
        if not selected:
            continue
        actor = fight.actors[actor_id]
        ledger = getattr(actor, "state_ledger", None)
        picked = []
        for entry in getattr(ledger, "entries", ()) if ledger is not None else ():
            if getattr(entry, "uid", None) in selected:
                picked.append(_plain_state_entry(entry))
        state["actors"][str(actor_id)]["state_ledger"] = {
            "actor_id": actor_id,
            "entries": picked,
        }
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
        # Terminal settlement and administrative snapshots remain complete
        # evidence. Only active, abort-on-restart recovery rows use v2.
        state = (
            snapshot(fight, runtime=runtime)
            if getattr(fight, "phase", None) != "active"
            else recovery_snapshot(fight, runtime=runtime)
        )
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
        serialized = json.dumps(state, allow_nan=False)
        encoded = Jsonb(state, dumps=lambda _: serialized)
        rift_receipts = ()
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
                "SELECT account_id,generation,revision,status,"
                "snapshot->>'phase' AS snapshot_phase "
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
            if (
                allow_terminal_receipt
                and row is not None
                and durable_fight["status"] == "finished"
                and row["status"] == "ended"
                and row["snapshot_phase"] == "finished"
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
                rift_receipts = persist_progress(db, fight)
        from wakfu_server.rift_runtime import mark_progress_committed

        mark_progress_committed(fight, rift_receipts)
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
        if isinstance(raw, dict) and "checkpoint_schema" in raw:
            if raw.get("checkpoint_schema") != RECOVERY_SCHEMA:
                raise ValueError("Unsupported fight checkpoint schema")
            actors = raw.get("actors")
            if (
                type(raw.get("id")) is not int
                or not isinstance(actors, dict)
                or not isinstance(raw.get("phase"), str)
            ):
                raise ValueError("Malformed versioned fight checkpoint")
            for identity, actor in actors.items():
                try:
                    parsed = int(identity)
                except (TypeError, ValueError):
                    raise ValueError(
                        "Malformed versioned checkpoint actor key"
                    ) from None
                if (
                    str(parsed) != str(identity)
                    or not isinstance(actor, dict)
                    or actor.get("id") != parsed
                    or type(actor.get("controlled")) is not bool
                    or type(actor.get("hp")) is not int
                    or type(actor.get("max_hp")) is not int
                    or not 0 <= actor["hp"] <= actor["max_hp"]
                    or type(actor.get("team")) is not int
                ):
                    raise ValueError("Malformed versioned checkpoint actor")
            return raw
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
            from wakfu_server.rift_interrupted_rewards import settle_startup

            settle_startup(self.store, db)
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
