"""Bounded, optional native counterfactual trap forecasts.

The queue contains only a detached oracle and scalar job data. A caller must
start the daemon outside an actor turn, reserve its sole slot before copying,
and treat any missing, stale or unsupported result as unknown.
"""
from queue import Queue
from threading import BoundedSemaphore, Event, Lock, Thread
from copy import deepcopy
import random
import time

from .jondo_trap_observation import compare_area_movement, detached_oracle

_QUEUE = Queue(maxsize=1)
_SLOT = BoundedSemaphore(1)
_LOCK = Lock()
_READY = {}
_STARTED = False
_INFLIGHT = None
_DONE = Event()


def _forecast(oracle, job):
    """Forecast one real cast, next turn and one paid movement on private state."""
    from ..native.native_control import (
        effective_input_owner,
        effective_server_controlled,
    )
    from wakfu_server.combat_additional_turn import timeline_round
    from wakfu_server import native_catalog
    from wakfu_server.native_compiled_catalog import resolve_publication, descriptor_for

    def publication_current():
        revision = job["catalogRevision"]
        if native_catalog.release() != revision:
            return False
        publication = resolve_publication(source_revision=revision)
        descriptor = descriptor_for(publication, job["catalogCollection"])
        return descriptor["revision"] == job["catalogGeneration"]

    if not publication_current():
        return None

    actor = oracle.runtime.fight.current
    if actor.id != job["actorId"] or tuple(actor.position) != tuple(job["origin"]):
        return None
    if oracle.runtime.fight.native_effect_areas:
        return None
    preview, _, _ = oracle.preview(
        oracle.runtime,
        dict(
            type="cast", spellId=job["spellId"], level=job["grade"], target=job["aim"]
        ),
    )
    areas = preview.fight.native_effect_areas
    if len(areas) != 1:
        return None
    area_uid, area = next(iter(areas.items()))
    if (
        area.get("native_area_contract") != "fbc"
        or area.get("owner_id") != actor.id
        or area.get("reference") != job["areaReference"]
    ):
        return None
    preview, _, _ = oracle.preview(preview, {"type": "end_turn"})
    fight, target = preview.fight, preview.fight.current
    if (
        target.id != job["triggerActorId"]
        or effective_server_controlled(fight, target)
        or tuple(target.position) != tuple(job["triggerOrigin"])
        or target.mp <= 0
    ):
        return None
    if set(job["livingActorIds"]) != {
        i for i, row in fight.actors.items() if row.hp > 0
    }:
        return None
    before_mp = target.mp
    seed = random.Random(0).getstate()
    captured = []

    def movement(current, moving, before, after):
        captured.append(
            compare_area_movement(
                oracle,
                current,
                area_uid,
                moving.id,
                before,
                after,
                action_id=preview.action_id + 1,
                rng_state=seed,
            )
        )

    fight.move(
        effective_input_owner(fight, target),
        target.id,
        [tuple(job["triggerCellXYZ"])],
        step_callback=movement,
    )
    if len(captured) != 1:
        return None
    result = captured[0]
    observed, control = result["observed"], result["control"]
    actual_round = timeline_round(fight)
    if any(
        branch["timelineRoundBefore"] != actual_round
        or branch["timelineRoundAfter"] != actual_round
        for branch in (observed, control)
    ):
        return None
    if (
        observed["movedActorIds"]
        or control["movedActorIds"]
        or observed["changedStateActorIds"]
        or control["changedStateActorIds"]
        or control["changedStatEffects"]
        or control["newRetainedIds"]
        or control["removedRetainedIds"]
        or control["removedStatEffects"]
        or observed["removedStatEffects"]
        or observed["changedRetainedIds"]
        or control["changedRetainedIds"]
    ):
        return None
    for uid in observed["removedRetainedIds"]:
        owner = observed["removedAreaEffects"].get(uid)
        if (
            not isinstance(owner, dict)
            or owner.get("area_uid") != area_uid
            or area.get("effect_uid") != uid
            or owner.get("effect_class") != area.get("effect_class")
            or owner.get("caster_id") != area.get("owner_id")
        ):
            return None
    stats = observed["changedStatEffects"]
    if set(stats) != set(observed["newRetainedIds"]):
        return None
    durations = {}
    current_round = actual_round
    for row in stats.values():
        if not isinstance(row, dict):
            return None
        identity, stat, timer = (
            row.get("target_id"),
            row.get("stat_id"),
            row.get("timer"),
        )
        if (
            identity not in job["livingActorIds"]
            or stat not in (2, 3)
            or not isinstance(timer, dict)
            or timer.get("actor_id") != identity
            or timer.get("expiration_round") != current_round
            or timer.get("phase") != "end"
        ):
            return None
        key = (identity, stat)
        if key in durations:
            return None
        durations[key] = 1
    changes = {row["actorId"]: row for row in result["deltas"]}
    deltas = []
    for identity in job["livingActorIds"]:
        row = changes.get(identity, {})
        max_ap, max_mp = row.get("maxAp", 0), row.get("maxMp", 0)
        if (
            max_ap
            and (identity, 2) not in durations
            or max_mp
            and (identity, 3) not in durations
        ):
            return None
        deltas.append(
            dict(
                actorId=identity,
                hp=row.get("hp", 0),
                armor=row.get("armor", 0),
                ap=row.get("ap", 0),
                mp=row.get("mp", 0),
                maxApDelta=max_ap,
                maxMpDelta=max_mp,
                apMaxDuration=durations.get((identity, 2), 0),
                mpMaxDuration=durations.get((identity, 3), 0),
            )
        )
    if not publication_current():
        return None
    return dict(
        version=1,
        complete=False,
        recipientsComplete=True,
        unrepresentedHarmsDetected=False,
        certainty="one_native_counterfactual_route",
        nativeIdentity=job["nativeIdentity"],
        fightInstanceId=job["fightInstanceId"],
        turnId=job["turnId"],
        spellId=job["spellId"],
        grade=job["grade"],
        fromCell=job["fromCell"],
        aimCell=job["aimCell"],
        triggerActorId=target.id,
        triggerMpBefore=before_mp,
        triggerCell=job["triggerCell"],
        triggerPath=[job["triggerCell"]],
        deltas=deltas,
    )


def _work():
    global _INFLIGHT
    while True:
        key, oracle, job = _QUEUE.get()
        try:
            result = _forecast(oracle, job)
            if result is not None:
                with _LOCK:
                    _READY.clear()
                    _READY[key] = (time.monotonic(), result)
        except Exception:
            pass  # Optional preview never affects World.
        finally:
            with _LOCK:
                if _INFLIGHT == key:
                    _INFLIGHT = None
                    _DONE.set()
            _SLOT.release()
            _QUEUE.task_done()


def start_worker():
    global _STARTED
    if not _LOCK.acquire(blocking=False):
        return False
    try:
        if _STARTED:
            return True
        _STARTED = True
    finally:
        _LOCK.release()
    try:
        Thread(target=_work, name="wakia-trap-preview", daemon=True).start()
    except Exception:
        with _LOCK:
            _STARTED = False
        return False
    return True


def _key(job):
    return (
        job["fightInstanceId"],
        job["turnId"],
        job["actorId"],
        job["nativeIdentity"],
        job["catalogRevision"],
        job["catalogGeneration"],
        job["catalogCollection"],
        job["areaReference"],
        job["spellId"],
        job["grade"],
        job["fromCell"],
        job["aimCell"],
        job["triggerActorId"],
        job["triggerCell"],
        tuple(job["origin"]),
        tuple(job["aim"]),
        tuple(job["triggerOrigin"]),
        tuple(job["triggerCellXYZ"]),
    )


def get_ready(job, *, wait_ms=0):
    """Poll only; do not start or enqueue work on a cache miss."""
    try:
        key = _key(job)
        hash(key)
    except (TypeError, KeyError):
        return None
    if not _LOCK.acquire(blocking=False):
        return None
    try:
        cached = _READY.get(key)
        if cached is not None and time.monotonic() - cached[0] < 5:
            return deepcopy(cached[1])
        wait = _INFLIGHT == key and type(wait_ms) is int and 0 < wait_ms <= 50
    finally:
        _LOCK.release()
    if wait:
        _DONE.wait(wait_ms / 1000)
        return get_ready(job)
    return None


def get_or_schedule(oracle, job):
    """Read/enqueue without waiting for the worker; copy is synchronous."""
    global _INFLIGHT
    try:
        key = _key(job)
        hash(key)
        runtime, fight = oracle.runtime, oracle.runtime.fight
        if (
            fight.current.id != job["actorId"]
            or fight.turn_id != job["turnId"]
            or runtime.tactical_encounter_id != job["fightInstanceId"]
            or tuple(fight.current.position) != tuple(job["origin"])
        ):
            return None
    except (TypeError, KeyError, AttributeError):
        return None
    if not _STARTED or not _LOCK.acquire(blocking=False):
        return None
    try:
        cached = _READY.get(key)
        if cached is not None and time.monotonic() - cached[0] < 5:
            return cached[1]
    finally:
        _LOCK.release()
    if not _SLOT.acquire(blocking=False):
        return None
    try:
        private = detached_oracle(oracle)
        with _LOCK:
            _INFLIGHT = key
            _DONE.clear()
        _QUEUE.put_nowait((key, private, deepcopy(job)))
    except Exception:
        with _LOCK:
            _INFLIGHT = None
            _DONE.set()
        _SLOT.release()
    return None
