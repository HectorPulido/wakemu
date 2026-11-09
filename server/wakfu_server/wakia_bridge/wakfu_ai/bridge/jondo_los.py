"""Advisory cast rays with the native source-QK visibility exclusion."""
from copy import copy
from wakfu_server.combat_los import authoritative_visible as _KNOWN_READER
from wakfu_server import (
    combat_native_los_ray as _native_ray,
    native_catalog as _catalog,
)

_KNOWN_RAY = _native_ray.cast_rays
_KNOWN_STATIC_RAY = _native_ray.static_ray
_KNOWN_CATALOG_EXISTS = _catalog.exists


def casting_visible(
    map_id,
    source,
    target,
    fight,
    *,
    blocking_footprints,
    prepared_geometry=None,
    advisory_cache=None,
    static_rays_observer=None,
):
    """Project fcr's source exclusion without changing the live QI registry.

    The ordinary coordinate-ray reader deliberately excludes no actor body.
    Native cast LOS additionally ignores its source's complete QK obstacle and
    the already owned QI visibility exclusions. Keep that distinction for each
    hypothetical origin, including enemy-to-caster rays used for retreat.
    """
    from wakfu_server.combat_los import authoritative_visible

    # A substituted/custom reader keeps the old call contract and cannot
    # certify native static rays merely by returning an advisory boolean.
    if (
        authoritative_visible is not _KNOWN_READER
        or getattr(authoritative_visible, "__module__", None)
        != "wakfu_server.combat_los"
        or (
            _native_ray.cast_rays is not _KNOWN_RAY
            or _native_ray.static_ray is not _KNOWN_STATIC_RAY
            or _catalog.exists is not _KNOWN_CATALOG_EXISTS
            or getattr(_KNOWN_RAY, "__module__", None)
            != "wakfu_server.combat_native_los_ray"
            or getattr(_KNOWN_STATIC_RAY, "__module__", None)
            != "wakfu_server.combat_native_los_ray"
            or getattr(_KNOWN_CATALOG_EXISTS, "__module__", None)
            != "wakfu_server.native_catalog"
        )
    ):
        static_rays_observer = None

    alive = {actor.id for actor in fight.actors.values() if actor.hp > 0}
    if set(blocking_footprints) != alive:
        raise ValueError("Cast LOS requires every living actor footprint")
    sources = [
        actor
        for actor in fight.actors.values()
        if actor.hp > 0 and tuple(actor.position) == tuple(source)
    ]
    if len(sources) != 1:
        raise ValueError("Advisory cast LOS requires one actual source actor")
    # Native fcr receives the actual QI-selected target's height even when the
    # aimed cell is an outer part of its body. Resolve identity before removing
    # any visibility-excluded body; LOS exclusions do not remove target identity.
    targets = [
        fight.actors[identity]
        for identity, cells in blocking_footprints.items()
        if tuple(target[:2]) in cells
    ]
    if len(targets) > 1:
        raise ValueError("Advisory cast LOS requires an unambiguous target body")
    height_view = fight
    if targets and tuple(targets[0].position) != tuple(target):
        if targets[0].id == sources[0].id:
            raise ValueError("Source-body side aims require separate height authority")
        # This private endpoint view changes only the coordinate-reader's height
        # lookup. Actual blockers retain the original target body, and no QI,
        # movement, registration or casting certificate is constructed here.
        height_view = copy(fight)
        height_view.actors = dict(fight.actors)
        endpoint = copy(targets[0])
        endpoint.position = tuple(target)
        height_view.actors[endpoint.id] = endpoint
    excluded = getattr(fight, "native_qi_visibility_ignored_slots", None)
    source_slot = getattr(sources[0], "native_obstacle_id", None)
    if (
        not isinstance(excluded, list)
        or any(type(slot) is not int or not 0 <= slot <= 126 for slot in excluded)
        or type(source_slot) is not int
        or not 0 <= source_slot <= 126
    ):
        raise ValueError("Missing native cast LOS source-QK exclusions")
    ignored_slots = frozenset((*excluded, source_slot))
    projected = {
        identity: (
            ()
            if getattr(fight.actors[identity], "native_obstacle_id", None)
            in ignored_slots
            else cells
        )
        for identity, cells in blocking_footprints.items()
    }
    kwargs = dict(blocking_footprints=projected)
    if prepared_geometry is not None:
        kwargs["prepared_geometry"] = prepared_geometry
    if advisory_cache is not None:
        from .jondo_los_cache import read_advisory

        return read_advisory(
            advisory_cache,
            map_id,
            source,
            target,
            height_view,
            blocking_footprints=projected,
            prepared_geometry=prepared_geometry,
            cast_exclusions=ignored_slots,
            reader=authoritative_visible,
            static_rays_observer=static_rays_observer,
        )
    if static_rays_observer is not None:
        kwargs["static_rays_observer"] = static_rays_observer
    return authoritative_visible(map_id, source, target, height_view, **kwargs)
