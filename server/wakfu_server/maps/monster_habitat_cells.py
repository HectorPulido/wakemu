"""Pinned native habitat-source adapter; admission is owned by Rust."""

from wakfu_server.spatial_geometry import habitats, surfaces


def habitat_destination_allowed(
    map_id, instance_id, destination, *, parent=None, family_id=None
):
    if not habitats().call(
        "geometry.habitat_tracked", map_id=map_id, instance_id=instance_id
    ):
        return True
    try:
        return surfaces(map_id).call("geometry.surface_exists", point=destination)
    except (ValueError, KeyError, TypeError):
        return False
