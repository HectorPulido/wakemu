"""Actual big copied-appearance call to eGj.PJ(source.dsK())."""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache


@lru_cache(maxsize=1)
def native_copied_equipment_catalog():
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "protocol/native-copied-equipment-definitions.json"
    )
    return protocol_catalog.load(path)


def copied_equipment_source(authority, source_actor_id):
    from .combat_runtime_adapter import NativeActorAuthority

    if not isinstance(authority, NativeActorAuthority):
        raise ValueError("Missing typed copied source actor authority")
    if authority.native_npc_prototype_ref is not None:
        if (
            authority.native_actor_type != 1
            or authority.is_player is not False
            or authority.native_npc_prototype_ref != authority.breed_id
            or type(authority.native_copied_equipment_operand) is not int
            or authority.native_copied_equipment_operand != 0
        ):
            raise ValueError("Missing actual bje inherited eGj.dsK authority")
        # bje/big inherit eGj.dsK(): literal zero. This is independent of the
        # player eSU component and PJ(0) returns without installing equipment.
        return dict(
            producer="big.copy.eGj.PJ.zero_return",
            source_actor_id=source_actor_id,
            dsK=0,
        )
    selected = authority.native_selected_cosmetics
    if not isinstance(selected, dict) or type(selected.get(7)) is not int:
        raise ValueError("Missing actual copied source eSU.dzQ operand")
    operand = selected[7]
    if not -(1 << 31) <= operand < (1 << 31):
        raise ValueError("Invalid actual copied source eSU.dzQ operand")
    # PJ does not store a title. Nonzero calls foA.Wc -> fnR.k -> eVn.a;
    # copying the source cosmetic component would invent destination state.
    if operand != 0:
        from .combat_copied_equipment_plan import copied_equipment_plan

        plan = copied_equipment_plan(operand, native_copied_equipment_catalog())
        if plan["roots"]:
            from .combat_copied_equipment_execution import equipment_effect_definitions

            equipment_effect_definitions(plan)
        return dict(
            producer="big.copy.eGj.PJ.complete_definition_iterator",
            source_actor_id=source_actor_id,
            dsK=operand,
            native_plan=plan,
        )
    return dict(
        producer="big.copy.eGj.PJ.zero_return",
        source_actor_id=source_actor_id,
        dsK=operand,
    )
