"""Actual fcb.b(III) usage population: bak PVs at an XY footprint."""
from dataclasses import dataclass
from .combat_casting_eligibility import native_pv_cell_distance


@dataclass(frozen=True)
class NativeUsageTarget:
    identity: int
    consume: bool


def usage_targets(fight, cell):
    from .combat_global_pv_collections import global_pv_iterator

    output = []
    for identity in global_pv_iterator(fight, caster_id=None, caster_only=False):
        actor = fight.actors.get(identity)
        if actor is not None:
            position, radius, consume = actor.position, actor.physical_radius, True
        else:
            from .combat_effect_area import native_effect_areas
            from .combat_area_contracts import AREA_CONTRACTS

            row = getattr(fight, "native_effect_areas", {}).get(identity)
            if not isinstance(row, dict) or row.get("uid") != identity:
                raise ValueError("Missing registered usage PV authority")
            definition = native_effect_areas().get(str(row.get("reference")))
            if (
                not isinstance(definition, dict)
                or definition.get("type") not in AREA_CONTRACTS
                or row.get("native_area_contract")
                != AREA_CONTRACTS.get(definition.get("type"))
                or type(definition.get("raw_bcR")) is not bool
            ):
                raise ValueError("Missing actual native usage area authority")
            position, radius, consume = row.get("cell"), 0, definition["raw_bcR"]
        if not isinstance(position, (tuple, list)) or len(position) != 3:
            raise ValueError("Missing actual native usage PV position")
        if native_pv_cell_distance(position, radius, cell) == 0:
            output.append(NativeUsageTarget(identity, consume))
    return tuple(output)
