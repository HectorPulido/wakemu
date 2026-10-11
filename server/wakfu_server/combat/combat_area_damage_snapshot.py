"""eYW308 post-creation PC guard, without inventing damage PCs on plain faV."""
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS


def area_has_damage_characteristic(row, definition):
    contract = row.get("native_area_contract")
    if contract not in SUPPORTED_AREA_CONTRACTS:
        raise ValueError("Missing native area characteristic constructor")
    if contract == "fbc":
        from .combat_trap_area import (
            verified_trap_characteristics,
            trap_characteristics,
        )

        return trap_characteristics()["fields"]["sgQ"] in verified_trap_characteristics(
            row, definition
        )
    if contract == "faW":
        from .combat_fake_fighter import verified_fake_fighter

        constructor = verified_fake_fighter(row, definition)
        if constructor["characteristic_ids"]:
            from .combat_fake_fighter_resources import fake_fighter_characteristics

            return 20 in fake_fighter_characteristics(row, definition)
    elif contract == "fbd":
        from .combat_wall_area import wall_constructor

        level = row.get("level")
        if type(level) is not int:
            raise ValueError("Missing native fbd constructor level")
        if row.get("native_wall_constructor") != wall_constructor(definition, level):
            raise ValueError("Missing native fbd characteristic constructor")
        # Actual fbd constructor installs HP only, never ffw.sgQ.
    # Other supported subtypes inherit faV.a(PC)=false and b(PC)=null.
    return False


def copy_area_damage_snapshot(
    row,
    definition,
    *,
    source_stats=None,
    container_type=None,
    spell_element_stat=None,
    spell_element_provider=None,
):
    if not area_has_damage_characteristic(row, definition):
        row["native_eyw_damage_copy"] = "eYW.fQG.skipped_no_sgQ"
        return False
    if row.get("native_area_contract") == "faW":
        # Unlike ordinary eYQ315, eYW308 copies additional source/spell PCs.
        # Its actual source/PL authority is not produced for faW yet.
        raise ValueError("Native faW eYW copy authority unavailable")
    if not isinstance(source_stats, dict) or any(
        type(k) is not int or type(v) is not int for k, v in source_stats.items()
    ):
        raise ValueError("Missing native eYW source PC authority")
    from .combat_trap_area import verified_trap_characteristics, trap_characteristics
    from .combat_area_property import area_properties

    target = verified_trap_characteristics(row, definition)
    catalog = trap_characteristics()
    fields = catalog["fields"]

    def add(target_id, source_id, *, reset=False):
        if target_id not in target or source_id not in source_stats:
            return
        bounds = catalog["characteristics"][str(target_id)]
        before = bounds["current"] if reset else target[target_id]
        target[target_id] = max(
            bounds["minimum"], min(bounds["maximum"], before + source_stats[source_id])
        )

    add(fields["sgQ"], fields["sgQ"])
    add(fields["sgP"], fields["sgP"])
    add(fields["sgP"], fields["sgS"])  # nG is an ordered delta, not assignment.
    if catalog["copy_all_property"] in area_properties(row, definition):
        for name in ("sgR", "sgS", "sgU", "sgT", "shY", "shX", "shV", "shW"):
            add(fields[name], fields[name], reset=True)
    elif container_type == 11:
        if spell_element_provider is not None:
            from .combat_spell_element_pc import NativeSpellElementPC

            operand = spell_element_provider()
            if not isinstance(operand, NativeSpellElementPC):
                raise ValueError("Missing actual native fyG spell element operand")
            spell_element_stat = operand.characteristic_id
            if spell_element_stat is None:
                row["native_eyw_damage_copy"] = "eYW.fQG.ordered_PA_nG"
                return True  # Actual PV.a(null) is false, not a missing PC ID.
        if type(spell_element_stat) is not int:
            raise ValueError("Missing actual native fyG spell element PC")
        add(fields["sgQ"], spell_element_stat)
    elif type(container_type) is not int:
        raise ValueError("Missing native eVo area PL type")
    row["native_eyw_damage_copy"] = "eYW.fQG.ordered_PA_nG"
    return True
