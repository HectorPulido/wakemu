"""Full native QI registration footprints for ordinary initial formations.

This local formation policy does not govern native summon/carry constructors.
"""
from .combat_obstacle_condition import footprint


def radii_for(members, member_radii, player_radius):
    radii = (0,) * len(members) if member_radii is None else tuple(member_radii)
    if len(radii) != len(members) or any(
        type(radius) is not int or not 0 <= radius <= 127
        for radius in (player_radius, *radii)
    ):
        raise ValueError("Invalid ordinary formation physical radii")
    return radii


def covered_cells(position, radius, cells, *, by_xy=None):
    """Resolve the complete inclusive QI footprint on selected native columns."""
    if by_xy is None:
        by_xy = {cell[:2]: cell for cell in cells}
    points = footprint(position, radius)
    if any(point not in by_xy for point in points):
        raise ValueError("Ordinary actor footprint exceeds selected native terrain")
    return frozenset(by_xy[point] for point in points)
