"""eNn/eIG IsBackstabbed against the current eGj locator and opposite PV.

Evidence: ProbeNativeBackstabbed, original eNn/eIG/Sl/eGj bytecode.
An explicit cell aBn is not PV. Qq is PV but is not a selectable eGj.
"""
from types import SimpleNamespace


def native_backstabbed(fight, selected_id, opposite_id, selected_authority):
    from .combat_ordinary_authority import native_facing

    selected = fight.actors.get(selected_id)
    if selected is None:
        return False
    if (
        selected_authority is None
        or type(selected_authority.is_native_fighter) is not bool
    ):
        raise ValueError("Missing native facing eGj actor authority")
    if not selected_authority.is_native_fighter:
        return False
    properties = selected_authority.fight_properties
    if not isinstance(properties, frozenset):
        raise ValueError("Missing native facing fight property authority")
    if 47 in properties:  # ffe.ser: eGj.baB is explicitly null.
        return False
    opposite = fight.actors.get(opposite_id)
    if opposite is None:
        area = getattr(fight, "native_effect_areas", {}).get(opposite_id)
        if area is None:
            return False
        opposite = SimpleNamespace(position=tuple(area["cell"]))
    return native_facing(opposite, selected) == "BACK"
