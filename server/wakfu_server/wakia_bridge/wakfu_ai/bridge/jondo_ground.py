"""Per-snapshot projection of the native, release-qualified ground policy."""
from wakfu_server import combat_ground_support as _ground
from wakfu_server import native_catalog as _native_catalog

_FIGHT_SUPPORTED = _ground.fight_supported
_SUPPORTED = _ground.supported
_MAP = _ground._map


def unsupported_ground(fight, *, catalog_revision):
    """Resolve the existing ground publication once for this current fight.

    Retain no fight or terrain across snapshots. If a caller substitutes the
    native policy, use that policy for every cell as the original bridge did.
    """
    if (
        getattr(_FIGHT_SUPPORTED, "__module__", None) != _ground.__name__
        or getattr(_SUPPORTED, "__module__", None) != _ground.__name__
        or getattr(_MAP, "__module__", None) != _ground.__name__
        or _ground.fight_supported is not _FIGHT_SUPPORTED
        or _ground.supported is not _SUPPORTED
        or _ground._map is not _MAP
    ):
        return {
            cell for cell in fight.walkable if not _ground.fight_supported(fight, cell)
        }
    provenance = getattr(fight, "native_qi_surface_provenance", None)
    if provenance is None:
        return set()
    if not isinstance(provenance, dict) or type(provenance.get("map_id")) is not int:
        raise ValueError("Missing ordinary combat floor provenance")
    if _native_catalog.release() != catalog_revision:
        raise ValueError("Native catalog changed during ground projection")
    supported = _MAP(
        provenance["map_id"], provenance.get("source_sha256"), catalog_revision
    )
    result = set() if supported is None else set(fight.walkable).difference(supported)
    if _native_catalog.release() != catalog_revision:
        raise ValueError("Native catalog changed during ground projection")
    return result
