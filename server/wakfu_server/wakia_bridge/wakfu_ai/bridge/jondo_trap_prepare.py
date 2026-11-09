"""Bounded asynchronous preparation of static native trap metadata.

Only catalogue identifiers cross the queue. A miss never waits for I/O or
asserts that the trap can be cast or will activate in the current fight.
"""
from collections import OrderedDict
from queue import Empty, Full, Queue
from threading import Lock, Thread
import json
import math
import time

_LOCK = Lock()
_QUEUE = Queue(maxsize=32)
_READY = OrderedDict()
_PENDING = set()
_FAILED_UNTIL = {}
_STARTED = False
_MAX_RESULTS = 128


def _prepare(revision, generation, collection, reference, level):
    from wakfu_server import native_catalog
    from wakfu_server.combat_effect_area import native_effect_areas
    from wakfu_server.combat_definitions import effect_profile
    from wakfu_server.combat_effect_targets import native_selector_policy
    from wakfu_server.combat_published_catalogs import resolve_static_catalog_descriptor
    from wakfu_server.native_compiled_catalog import resolve_publication, descriptor_for

    if native_catalog.release() != revision:
        return None
    publication = resolve_publication(source_revision=revision)
    descriptor = descriptor_for(publication, collection)
    if descriptor["revision"] != generation:
        return None
    effects = resolve_static_catalog_descriptor(descriptor)
    # Bypass the area helper's unkeyed one-entry cache: protocol_catalog.load
    # below it is keyed by the native release and runs only in this worker.
    definition = native_effect_areas.__wrapped__().get(str(reference))
    if not isinstance(definition, dict) or definition.get("type") != "TRAP":
        return None
    roots = definition.get("effect_ids")
    entries = definition.get("entry_masks")
    exits = definition.get("exit_masks")
    area_properties = definition.get("native_area_properties")
    shape = definition.get("native_shape_description")
    parameters = definition.get("shape_parameters")
    if (
        not isinstance(roots, (list, tuple))
        or not 1 <= len(roots) <= 16
        or any(type(v) is not int or v <= 0 for v in roots)
        or not isinstance(entries, (list, tuple))
        or len(entries) > 32
        or not all(type(v) is int for v in entries)
        or not isinstance(exits, (list, tuple))
        or len(exits) > 32
        or any(type(v) is not int for v in exits)
        or not isinstance(area_properties, (list, tuple))
        or len(area_properties) > 32
        or any(type(v) is not int for v in area_properties)
        or not isinstance(shape, str)
        or len(shape) > 128
        or not isinstance(parameters, (list, tuple))
        or len(parameters) > 16
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in parameters)
    ):
        return None
    pending = [(int(root), 0) for root in roots]
    seen, rows = set(), []
    while pending:
        ref, depth = pending.pop()
        if ref in seen:
            continue
        if depth > 4 or len(seen) >= 32:
            return None
        seen.add(ref)
        effect = effects.get(str(ref))
        if effect is None:
            return None
        children = effect.get("children")
        if (
            not isinstance(children, (tuple, list))
            or len(children) > 32
            or any(type(x) is not int or x <= 0 for x in children)
        ):
            return None
        pending.extend((child, depth + 1) for child in children)
        selector = effect.get("native_target_selector")
        try:
            policy = native_selector_policy(effect)
            relations, in_area = sorted(policy["relations"]), policy["in_area"]
        except (ValueError, TypeError, KeyError):
            relations, in_area = [], None
        parameter_count = effect.get("parameter_count")
        if type(parameter_count) is not int or not 0 <= parameter_count <= 32:
            return None
        profile = effect_profile(effect, level)
        probability = profile["probability"]
        if not math.isfinite(probability):
            return None
        criteria = effect.get("criteria")
        if not isinstance(criteria, str) or len(criteria) > 512:
            return None
        masks = effect.get("target_masks")
        timing = effect.get("native_timing_definition")
        if (
            not isinstance(masks, (tuple, list))
            or len(masks) != 7
            or not hasattr(timing, "items")
        ):
            return None
        # Preserve event/retention metadata; no consumer may infer immediate
        # execution merely from the existence of a damage-family row.
        target_masks = [None if part is None else list(part) for part in masks]
        timing = dict(timing)
        flags = effect.get("native_effect_flags", ())
        if (
            not isinstance(flags, (tuple, list))
            or len(flags) > 32
            or any(type(v) is not int for v in flags)
        ):
            return None
        rows.append(
            dict(
                reference=ref,
                family=effect.get("effect_class"),
                children=list(children),
                criteria=criteria,
                probability=probability,
                targets=relations,
                inArea=in_area,
                selector=dict(selector) if selector is not None else None,
                flags=list(flags),
                parameters=profile["parameters"],
                variant=effect.get("variant"),
                minimumLevel=effect.get("minimum_level"),
                maximumLevel=effect.get("maximum_level"),
                executionMode=effect.get("native_execution_mode"),
                targetMasks=target_masks,
                timing=timing,
            )
        )
    if native_catalog.release() != revision:
        return None
    current = resolve_publication(source_revision=revision)
    if descriptor_for(current, collection) != descriptor:
        return None
    return dict(
        version=1,
        reference=reference,
        level=level,
        shape=shape,
        shapeParameters=list(parameters),
        entryMasks=list(entries),
        exitMasks=list(exits),
        areaProperties=list(area_properties),
        roots=list(roots),
        effects=rows,
        certainty="advisory_static_only",
    )


def _work():
    while True:
        key = _QUEUE.get()
        try:
            value = _prepare(*key)
            encoded = (
                None
                if value is None
                else json.dumps(value, separators=(",", ":"), allow_nan=False)
            )
            if encoded is not None and len(encoded) > 32768:
                encoded = None
            with _LOCK:
                if encoded is not None:
                    _READY[key] = encoded
                    _READY.move_to_end(key)
                    while len(_READY) > _MAX_RESULTS:
                        _READY.popitem(last=False)
                else:
                    _FAILED_UNTIL[key] = time.monotonic() + 30
        except Exception:
            with _LOCK:
                _FAILED_UNTIL[key] = time.monotonic() + 30
        finally:
            with _LOCK:
                _PENDING.discard(key)
                # Keep error throttling bounded even under adversarial IDs.
                while len(_FAILED_UNTIL) > _MAX_RESULTS:
                    _FAILED_UNTIL.pop(next(iter(_FAILED_UNTIL)))
            _QUEUE.task_done()


def start_worker():
    """Start once during World startup; a failed start leaves the feature off."""
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
        Thread(target=_work, name="wakia-trap-catalog", daemon=True).start()
        return True
    except Exception:
        with _LOCK:
            _STARTED = False
            while True:
                try:
                    pending = _QUEUE.get_nowait()
                except Empty:
                    break
                _PENDING.discard(pending)
                _QUEUE.task_done()
        return False


def get_or_schedule(revision, descriptor, reference, level):
    """Return prepared metadata or enqueue without waiting on a worker or I/O."""
    if (
        not isinstance(revision, str)
        or len(revision) != 64
        or not isinstance(descriptor, dict)
        or type(descriptor.get("revision")) is not str
        or type(descriptor.get("collection")) is not str
        or type(reference) is not int
        or reference <= 0
        or type(level) is not int
        or not 0 <= level <= 32767
    ):
        return None
    key = (revision, descriptor["revision"], descriptor["collection"], reference, level)
    if not _LOCK.acquire(blocking=False):
        return None
    try:
        encoded = _READY.get(key)
        if encoded is not None:
            _READY.move_to_end(key)
        elif (
            _STARTED
            and key not in _PENDING
            and _FAILED_UNTIL.get(key, 0) <= time.monotonic()
        ):
            try:
                _QUEUE.put_nowait(key)
            except Full:
                pass
            else:
                _PENDING.add(key)
    finally:
        _LOCK.release()
    return None if encoded is None else json.loads(encoded)
