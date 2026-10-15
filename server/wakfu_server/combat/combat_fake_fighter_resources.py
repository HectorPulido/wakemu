"""Source-qualified faW HP and zero-owner-copy PA constructors.

faW.aQc builds eRF([ffw.sgC]), initializes native defaults, sets maximum
from two float32 operations and resets current through PA.aZf. Optional
characteristics and nonzero owner damage copying remain unsupported.
"""
from .combat_fake_fighter import _float32, _int

SOURCE = "faW.aQc.eRF.sgC.hp_only.v1"
HP_CHARACTERISTIC = 1


def fake_fighter_hp_resources(definition, level):
    if (
        definition.get("type") != "FAKE_FIGHTER"
        or definition.get("native_type_id") != 15
        or definition.get("native_class") != "bcQ"
    ):
        raise ValueError("Missing native faW HP constructor prototype")
    if type(level) is not int or not 0 <= level <= 32767:
        raise ValueError("Missing actual native faW container level")
    raw = definition.get("raw_bdh")
    if not isinstance(raw, (tuple, list)) or len(raw) != 10:
        raise ValueError("Unaudited native faW characteristic parameter layout")
    parameters = tuple(_float32(value) for value in raw)
    if parameters[1] == -1 or parameters[9] != -1:
        raise ValueError("Native faW HP-only characteristic branch required")
    # Native fmul then fadd round separately before Java f2i. ffw.sgC
    # defaults min0, absolute max INT_MAX; fff.or clamps max to min0.
    scaled = _float32(level * parameters[2])
    maximum = max(0, _int(_float32(parameters[1] + scaled)))
    return {
        "source": SOURCE,
        "level": level,
        "characteristics": {
            HP_CHARACTERISTIC: {
                "current": maximum,
                "maximum": maximum,
                "minimum": 0,
                "absolute_minimum": 0,
                "absolute_maximum": (1 << 31) - 1,
            }
        },
    }


def install_fake_fighter_hp(row, definition):
    """Persist native constructor authority separately from mutable PA current."""
    resources = _owned_resources_constructor(definition, row.get("level"))
    row["native_faw_hp_constructor"] = {
        "source": resources["source"],
        "level": resources["level"],
        "hp": dict(resources["characteristics"][HP_CHARACTERISTIC]),
    }
    row["native_faw_hp_current"] = resources["characteristics"][HP_CHARACTERISTIC][
        "current"
    ]
    row["native_faw_hp_source"] = "faW.PA.sgC.aYS"
    if 20 in resources["characteristics"]:
        row["native_faw_hp_constructor"]["damage"] = dict(
            resources["characteristics"][20]
        )
        row["native_faw_damage_current"] = resources["characteristics"][20]["current"]
        row["native_faw_damage_source"] = "faW.PA.sgQ.aYS"
    return fake_fighter_hp_state(row, definition)


def fake_fighter_hp_state(row, definition):
    """Validate actual owned PA presence, including restored JSON snapshots."""
    if row.get("native_area_contract") != "faW":
        raise ValueError("Missing actual native faW area resource owner")
    resources = _owned_resources_constructor(definition, row.get("level"))
    hp = resources["characteristics"][HP_CHARACTERISTIC]
    expected = {"source": resources["source"], "level": resources["level"], "hp": hp}
    if 20 in resources["characteristics"]:
        expected["damage"] = resources["characteristics"][20]
    current = row.get("native_faw_hp_current")
    if (
        row.get("native_faw_hp_constructor") != expected
        or row.get("native_faw_hp_source") != "faW.PA.sgC.aYS"
        or type(current) is not int
    ):
        raise ValueError("Missing actual native faW HP PA authority")
    from .combat_area_hp_pa import area_hp_pa

    return area_hp_pa(row, hp, current, "faW")


def update_fake_fighter_hp(row, definition, current):
    hp = fake_fighter_hp_state(row, definition)
    if type(current) is not int or not hp["minimum"] <= current <= hp["maximum"]:
        raise ValueError("Invalid native faW current HP update")
    from .combat_area_hp_pa import set_area_hp_current

    set_area_hp_current(row, hp, current, "native_faw_hp_current")
    return fake_fighter_hp_state(row, definition)


def fake_fighter_damage_snapshot(row, definition):
    hp = fake_fighter_hp_state(row, definition)
    characteristics = fake_fighter_characteristics(row, definition)
    return dict(
        stats={
            identity: value["current"] for identity, value in characteristics.items()
        },
        maxima={
            identity: value["maximum"] for identity, value in characteristics.items()
        },
        minima={
            identity: value["minimum"] for identity, value in characteristics.items()
        },
        frozen=frozenset((1,)) if hp["frozen"] else frozenset(),
        current_hp=hp["current"],
        maximum_hp=hp["maximum"],
        characteristics_source=_owned_resources_constructor(
            definition, row.get("level")
        )["source"],
        absent_actor_absorption_stats=(92, 97, 100),
    )


def fake_fighter_hp_wire(row, definition):
    """faW serialized HP suffix: maximum then current, both signed int32."""
    import struct

    hp = fake_fighter_hp_state(row, definition)
    return struct.pack(">ii", hp["maximum"], hp["current"])


DAMAGE_CHARACTERISTIC = 20
DAMAGE_SOURCE = "faW.aQc.eRF.sgC_sgQ.owner_mask0.v1"


def fake_fighter_zero_copy_resources(definition, level):
    """Actual p9=0 installs sgQ without reading any owner characteristic."""
    raw = definition.get("raw_bdh")
    if not isinstance(raw, (tuple, list)) or len(raw) != 10 or _float32(raw[9]) != 0:
        raise ValueError("Native faW zero owner-copy mask required")
    # The HP producer owns the identical sgC constructor arithmetic. Substitute
    # only its branch selector in this private validated constructor input;
    # the real definition and admitted PC population remain unchanged.
    hp_definition = dict(definition, raw_bdh=list(raw[:9]) + [-1])
    resources = fake_fighter_hp_resources(hp_definition, level)
    resources["source"] = DAMAGE_SOURCE
    resources["characteristics"][DAMAGE_CHARACTERISTIC] = dict(
        current=0,
        maximum=50000,
        minimum=-5000,
        absolute_minimum=-5000,
        absolute_maximum=50000,
    )
    return resources


def _owned_resources_constructor(definition, level):
    raw = definition.get("raw_bdh")
    if isinstance(raw, (tuple, list)) and len(raw) == 10 and _float32(raw[9]) == 0:
        return fake_fighter_zero_copy_resources(definition, level)
    return fake_fighter_hp_resources(definition, level)


def fake_fighter_characteristics(row, definition):
    """Return the complete actual faW PC population, never fighter defaults."""
    from .combat_fake_fighter_owner_copy import damage_only_mask, characteristics

    if damage_only_mask(definition) is not None:
        return characteristics(row, definition)
    hp = fake_fighter_hp_state(row, definition)
    resources = _owned_resources_constructor(definition, row.get("level"))
    result = {HP_CHARACTERISTIC: hp}
    if DAMAGE_CHARACTERISTIC in resources["characteristics"]:
        damage = resources["characteristics"][DAMAGE_CHARACTERISTIC]
        current = row.get("native_faw_damage_current")
        if (
            row.get("native_faw_damage_source") != "faW.PA.sgQ.aYS"
            or type(current) is not int
            or not damage["minimum"] <= current <= damage["maximum"]
        ):
            raise ValueError("Missing actual native faW sgQ PA authority")
        result[DAMAGE_CHARACTERISTIC] = dict(damage, current=current)
    elif "native_faw_damage_current" in row or "native_faw_damage_source" in row:
        raise ValueError("Absent native faW sgQ has invented PA authority")
    return result
