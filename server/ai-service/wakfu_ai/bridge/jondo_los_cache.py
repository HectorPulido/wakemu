"""Bounded content reuse of advisory LOS, never a native casting certificate."""
from collections import OrderedDict
from threading import RLock
from time import perf_counter
from weakref import WeakKeyDictionary
from types import FunctionType

from wakfu_server import combat_los as _world_los
from wakfu_server import combat_native_los_ray as _native_ray
from wakfu_server import native_catalog as _catalog


_OWNERS = WeakKeyDictionary()
_OWNERS_LOCK = RLock()
_MISSING = object()


def cache_for_oracle(oracle, source):
    """One private cache per verified owner/turn; never attach to native state."""
    instance = source.get("fightInstanceId")
    if (
        type(instance) is not str
        or not instance
        or any(
            type(source.get(key)) is not int for key in ("fightId", "actorId", "turnId")
        )
        or type(source.get("catalogRevision")) is not str
    ):
        return None
    scope = tuple(
        source[key]
        for key in (
            "fightInstanceId",
            "fightId",
            "actorId",
            "turnId",
            "catalogRevision",
        )
    )
    try:
        with _OWNERS_LOCK:
            existing = _OWNERS.get(oracle)
            if existing is None or existing[0] != scope:
                existing = scope, AdvisoryLosCache(
                    catalog_revision=source["catalogRevision"]
                )
                _OWNERS[oracle] = existing
            return existing[1]
    except TypeError:
        # Unhashable/nonweak fixture owners cannot grant a persistent lifetime.
        return None


class AdvisoryLosCache:
    """Immutable scalar facts only; weak owner lifetime and bounded scene/rays."""

    def __init__(
        self, *, catalog_revision, max_rays=512, max_contexts=32, max_units=250_000
    ):
        if (
            type(catalog_revision) is not str
            or not catalog_revision
            or any(
                type(value) is not int or value < 1
                for value in (max_rays, max_contexts, max_units)
            )
        ):
            raise ValueError("Bounded advisory LOS cache scope required")
        self.catalog_revision = catalog_revision
        self.max_rays, self.max_contexts, self.max_units = (
            max_rays,
            max_contexts,
            max_units,
        )
        self._contexts = OrderedDict()
        self._ray_order = OrderedDict()
        self._terrain_last = None
        self._rays = self._units = 0
        self._lock = RLock()
        self._reader = _world_los.authoritative_visible
        self._reader_functions = (
            _native_ray.cast_rays,
            _native_ray.static_ray,
            _catalog.exists,
        )
        self._readers_known = (
            type(self._reader) is FunctionType
            and self._reader.__module__ == _world_los.__name__
            and type(_native_ray.cast_rays) is FunctionType
            and _native_ray.cast_rays.__module__ == _native_ray.__name__
            and type(_catalog.exists) is FunctionType
            and _catalog.exists.__module__ == _catalog.__name__
        )
        self.hits = self.misses = self.bypasses = 0
        self.key_ms = self.read_ms = self.publish_ms = 0.0

    def metrics(self):
        with self._lock:
            return dict(
                hits=self.hits,
                misses=self.misses,
                bypasses=self.bypasses,
                keyMs=self.key_ms,
                readMs=self.read_ms,
                publishMs=self.publish_ms,
                rays=self._rays,
                contexts=len(self._contexts),
                units=self._units,
            )

    def snapshot_session(self):
        """Unpublished observations cannot escape a rejected native snapshot."""
        return _AdvisoryLosSession(self)

    def _find(self, scene, query):
        with self._lock:
            entry = self._contexts.get(scene)
            if entry is None or query not in entry[1]:
                self.misses += 1
                return _MISSING
            self._contexts.move_to_end(scene)
            entry[1].move_to_end(query)
            self._ray_order.move_to_end((scene, query))
            self.hits += 1
            return entry[1][query][0]

    def _canonical_terrain(self, permitted):
        """Intern only exact immutable XY values, once per new prepared value.

        The opaque source terrain proof was checked BEFORE this call. Strong
        immutable references make this an equality shortcut, not an ID cache.
        """
        with self._lock:
            if self._terrain_last is not None and self._terrain_last[0] is permitted:
                return self._terrain_last[1]
            canonical, inspected = permitted, set()
            for scene in self._contexts:
                known = scene[1]
                if id(known) in inspected:
                    continue
                inspected.add(id(known))
                if known == permitted:
                    canonical = known
                    break
            self._terrain_last = permitted, canonical
            return canonical

    def _store(self, scene, query, value, units, query_units):
        if units + query_units > self.max_units or type(value) is not bool:
            return
        with self._lock:
            entry = self._contexts.get(scene)
            if entry is None:
                entry = units, OrderedDict()
                self._contexts[scene] = entry
                self._units += units
            if query not in entry[1]:
                self._rays += 1
                self._units += query_units
            else:
                self._units += query_units - entry[1][query][1]
            entry[1][query] = value, query_units
            self._ray_order[scene, query] = None
            self._ray_order.move_to_end((scene, query))
            self._contexts.move_to_end(scene)
            while (
                len(self._contexts) > self.max_contexts
                or self._rays > self.max_rays
                or self._units > self.max_units
            ):
                if len(self._contexts) > self.max_contexts:
                    retired_scene, retired = self._contexts.popitem(last=False)
                    self._units -= retired[0] + sum(
                        value[1] for value in retired[1].values()
                    )
                    self._rays -= len(retired[1])
                    for retired_query in retired[1]:
                        self._ray_order.pop((retired_scene, retired_query), None)
                else:
                    (retired_scene, retired_query), _ = self._ray_order.popitem(
                        last=False
                    )
                    retired = self._contexts[retired_scene]
                    self._units -= retired[1].pop(retired_query)[1]
                    self._rays -= 1
                    if not retired[1]:
                        del self._contexts[retired_scene]
                        self._units -= retired[0]


class _AdvisoryLosSession(AdvisoryLosCache):
    def __init__(self, parent):
        super().__init__(
            catalog_revision=parent.catalog_revision,
            max_rays=parent.max_rays,
            max_contexts=parent.max_contexts,
            max_units=parent.max_units,
        )
        self._parent = parent
        self._reader, self._reader_functions = parent._reader, parent._reader_functions
        self._readers_known = parent._readers_known
        self._published = False
        self._prepared_keys = []

    def _key_permitted(self, map_id, walkable, prepared):
        """Key construction only: MISS uses the original fresh World reader.

        HITs separately validate the opaque proof on EVERY use. New facts are
        unpublished until the complete native source guard succeeds, so an
        invalidated snapshot cannot publish observations under this key.
        """
        from wakfu_server.combat_los_geometry import prepared_permitted_xy

        for token, terrain, map_value, permitted in self._prepared_keys:
            if token is prepared and terrain is walkable and map_value == map_id:
                return permitted
        permitted = prepared_permitted_xy(prepared, map_id=map_id, walkable=walkable)
        if permitted is not None and len(self._prepared_keys) < 4:
            self._prepared_keys.append((prepared, walkable, map_id, permitted))
        return permitted

    def _reject_hit(self):
        self._parent.hits -= 1

    def _canonical_terrain(self, permitted):
        return self._parent._canonical_terrain(permitted)

    def _find(self, scene, query):
        known = self._parent._find(scene, query)
        if known is not _MISSING:
            return known
        pending = super()._find(scene, query)
        if pending is not _MISSING:
            # A repeated ray within one snapshot is one actual cache hit.
            self._parent.misses -= 1
            self._parent.hits += 1
        return pending

    def publish(self):
        """Called only AFTER the existing complete native identity guard."""
        if self._published:
            return
        started = perf_counter()
        self._published = True
        for scene, (units, values) in self._contexts.items():
            for query, (value, query_units) in values.items():
                self._parent._store(scene, query, value, units, query_units)
        self._parent.key_ms += self.key_ms
        self._parent.read_ms += self.read_ms
        self._parent.bypasses += self.bypasses
        self._parent.publish_ms += (perf_counter() - started) * 1000


def _xyz(value):
    return (
        type(value) is tuple
        and len(value) == 3
        and all(type(number) is int for number in value)
        and all(-(1 << 31) <= number < (1 << 31) for number in value[:2])
        and -32768 <= value[2] < 32768
    )


def _world_scene(
    map_id, fight, footprints, prepared_geometry, cast_exclusions, *, permitted=_MISSING
):
    """Capture EVERY actual World reader field after fresh SDK validation."""
    from wakfu_server.combat_los_geometry import prepared_permitted_xy

    if permitted is _MISSING:
        permitted = prepared_permitted_xy(
            prepared_geometry, map_id=map_id, walkable=fight.walkable
        )
    if (
        permitted is None
        or type(footprints) is not dict
        or type(fight.actors) is not dict
    ):
        return None
    if type(cast_exclusions) is not frozenset or any(
        type(value) is not int or not 0 <= value <= 126 for value in cast_exclusions
    ):
        return None
    ignored = getattr(fight, "native_los_ignored_affiliations", frozenset())
    if type(ignored) is not frozenset or any(
        type(value) is not int or not -128 <= value <= 127 for value in ignored
    ):
        return None
    actors = []
    for identity, actor in fight.actors.items():
        if (
            type(identity) is not int
            or actor.id != identity
            or type(actor.hp) is not int
        ):
            return None
        if actor.hp <= 0:
            continue
        position = actor.position
        height, slot = getattr(actor, "native_los_height", _MISSING), getattr(
            actor, "native_obstacle_id", _MISSING
        )
        if (
            not _xyz(position)
            or not (height is None or type(height) is int and -128 <= height <= 127)
            or not (slot is None or type(slot) is int and -128 <= slot <= 127)
        ):
            return None
        actors.append((identity, position, height, slot))
    if set(footprints) != {row[0] for row in actors}:
        return None
    bodies, count = [], 0
    for identity, cells in footprints.items():
        if type(identity) is not int or type(cells) not in (
            tuple,
            list,
            set,
            frozenset,
        ):
            return None
        count += len(cells)
        if count > 4096:
            return None
        if any(
            type(cell) not in (tuple, list)
            or len(cell) != 2
            or any(type(value) is not int for value in cell)
            for cell in cells
        ):
            return None
        bodies.append((identity, frozenset(tuple(cell) for cell in cells)))
    # Source exclusions/projected footprints vary by directed ray. Keep those
    # in its query key so reverse rays share one immutable per-origin scene.
    return (
        (permitted, tuple(sorted(actors)), ignored),
        (frozenset(bodies), cast_exclusions),
        len(permitted) + len(actors),
        count,
    )


def read_advisory(
    cache,
    map_id,
    source,
    target,
    fight,
    *,
    blocking_footprints,
    prepared_geometry,
    cast_exclusions,
    reader,
):
    """Reuse only a verified identical advisory scene, keeping errors unknown."""
    kwargs = dict(blocking_footprints=blocking_footprints)
    if prepared_geometry is not None:
        kwargs["prepared_geometry"] = prepared_geometry
    if type(cache) not in (AdvisoryLosCache, _AdvisoryLosSession):
        return reader(map_id, source, target, fight, **kwargs)
    started = perf_counter()
    candidate = None
    from wakfu_server import combat_input_observation as observation

    if (
        reader is cache._reader
        and cache._readers_known
        and cache._reader_functions
        == (_native_ray.cast_rays, _native_ray.static_ray, _catalog.exists)
        and observation._active.get() is None
        and observation._replaying.get() is None
        and type(map_id) is int
        and _xyz(tuple(source))
        and _xyz(tuple(target))
    ):
        try:
            prepared_value = (
                cache._key_permitted(map_id, fight.walkable, prepared_geometry)
                if type(cache) is _AdvisoryLosSession
                else _MISSING
            )
            context = _world_scene(
                map_id,
                fight,
                blocking_footprints,
                prepared_geometry,
                cast_exclusions,
                permitted=prepared_value,
            )
            generation_reader = getattr(_native_ray, "sealed_generation", None)
            generation = (
                generation_reader(map_id)
                if context is not None and callable(generation_reader)
                else None
            )
            if generation is not None and generation.release == cache.catalog_revision:
                scene, dynamic_query, units, query_units = context
                if units + query_units <= cache.max_units:
                    scene = (cache._canonical_terrain(scene[0]), *scene[1:])
                    candidate = (
                        (generation, *scene),
                        (tuple(source), tuple(target), *dynamic_query),
                        units,
                        query_units,
                    )
        except (ValueError, TypeError, KeyError, AttributeError):
            # Unknown/custom inputs keep the unchanged strict reader path.
            candidate = None
    if candidate is not None:
        scene, query, units, query_units = candidate
        known = cache._find(scene, query)
        if known is not _MISSING:
            if type(cache) is _AdvisoryLosSession:
                from wakfu_server.combat_los_geometry import prepared_permitted_xy

                fresh = prepared_permitted_xy(
                    prepared_geometry, map_id=map_id, walkable=fight.walkable
                )
                if fresh is not prepared_value:
                    cache._reject_hit()
                    cache.bypasses += 1
                    candidate = None
                else:
                    cache.key_ms += (perf_counter() - started) * 1000
                    return known
            else:
                cache.key_ms += (perf_counter() - started) * 1000
                return known
    else:
        cache.bypasses += 1
    cache.key_ms += (perf_counter() - started) * 1000
    started = perf_counter()
    try:
        value = reader(map_id, source, target, fight, **kwargs)
    finally:
        cache.read_ms += (perf_counter() - started) * 1000
    if candidate is not None:
        cache._store(scene, query, value, units, query_units)
    return value
