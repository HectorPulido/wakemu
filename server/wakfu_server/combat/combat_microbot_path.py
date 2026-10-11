"""Native fdq rail Sn(6,1,4) and QI.X projections, without mutable QI flags.

fdq.j temporarily sets QI.bf(true), resets it in finally, and calls Sn.c.
Sn.c calls a(start,end,false): physical columns come from inherited VE.aO/VB.a,
while the optional QI.Z mask branch is skipped. QI has no aO override. The pure
projection therefore keeps native terrain and surface masks, touches no live
flag, and cannot leak bf(true) into subsequent movement or casting queries.
"""
from dataclasses import dataclass
from .combat_qi_snapshot import NativeQISnapshot
from .combat_qi_surfaces import NativeQISurfaces
from .combat_sn_path import NativeSnColumns, NativeSnPathAuthority


@dataclass(frozen=True)
class NativeMicrobotPathProjection:
    qi: NativeQISnapshot
    surfaces: NativeQISurfaces
    columns: NativeSnColumns

    def __post_init__(self):
        if (
            not isinstance(self.qi, NativeQISnapshot)
            or not isinstance(self.surfaces, NativeQISurfaces)
            or not isinstance(self.columns, NativeSnColumns)
            or self.surfaces.map_id != self.columns.map_id
        ):
            raise ValueError("Missing matching native microbot path authority")

    def segment_is_passable(self, start, end):
        return NativeSnPathAuthority(
            source=start,
            target=end,
            height=6,
            radius=1,
            jump=4,
            physical_column=self.columns.column,
            qi_z=self.qi.Z,
            is_qi=True,
            target_obstacle_present=False,
        )(False)

    def surface_z(self, x, y):
        return self.surfaces.X(self.qi, x, y)


def microbot_path_projection(fight):
    from .combat_qi_fight import current_registry
    from .combat_qi_surface_catalog import (
        native_qi_surfaces,
        native_qi_surface_provenance,
    )

    provenance = getattr(fight, "native_qi_surface_provenance", None)
    if not isinstance(provenance, dict):
        raise ValueError("Missing native microbot map identity")
    map_id = provenance.get("map_id")
    if type(map_id) is not int or map_id <= 0:
        raise ValueError("Missing native microbot map identity")
    if provenance != native_qi_surface_provenance(map_id):
        raise ValueError("Native microbot selected-surface provenance mismatch")
    return NativeMicrobotPathProjection(
        current_registry(fight).snapshot(),
        native_qi_surfaces(map_id),
        NativeSnColumns.from_published(map_id),
    )


def segment_is_passable(fight, start, end):
    return microbot_path_projection(fight).segment_is_passable(start, end)


def native_surface_z(fight, x, y):
    return microbot_path_projection(fight).surface_z(x, y)
