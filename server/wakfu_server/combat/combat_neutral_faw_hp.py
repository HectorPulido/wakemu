"""Explicit prototype-pinned neutral HP-only faW scene construction."""
from hashlib import sha256
import json

SCHEMA = "native-neutral-hp-faw-v1"
REMOVAL_SCHEMA = "native-neutral-removal-hp-faw-v1"


def prototype_digest(definition):
    return sha256(
        json.dumps(
            definition, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def validate(definition, level, declaration):
    from .combat_fake_fighter import fake_fighter_constructor
    from .combat_fake_fighter_resources import fake_fighter_hp_resources

    if (
        not isinstance(declaration, dict)
        or set(declaration) != {"schema", "prototype_sha256"}
        or declaration["schema"] not in (SCHEMA, REMOVAL_SCHEMA)
        or declaration["prototype_sha256"] != prototype_digest(definition)
    ):
        raise ValueError("Neutral HP faW lacks its reviewed original prototype pin")
    constructor = fake_fighter_constructor(definition, level, allow_hp=True)
    resources = fake_fighter_hp_resources(definition, level)
    removal = declaration["schema"] == REMOVAL_SCHEMA
    if (
        constructor["kind"] != 0
        or constructor["characteristic_ids"] != (1,)
        or constructor["running_effect_manager"] is not (not removal)
        or not constructor["owner_activation"]
        or not constructor["other_activation"]
        or resources["characteristics"][1]["maximum"] <= 0
        or definition.get("native_container_type") != 3
        or definition.get("native_hour_contract") is not False
        or definition.get("native_shape_class") != "anD"
        or definition.get("native_shape_description") != "point"
        or definition.get("shape_parameters") != []
        or definition.get("entry_masks") != ([10011] if removal else [])
        or definition.get("exit_masks") != []
        or definition.get("native_fight_properties") != []
        or definition.get("native_area_properties") != []
        or definition.get("raw_bde") != (1 if removal else -1)
        or definition.get("raw_bdf") != 0
        or definition.get("raw_bdg") != []
        or type(level) is not int
        or level != 0
        or definition.get("maximum_level") != 0
        or not isinstance(definition.get("effect_ids"), (list, tuple))
        or not definition["effect_ids"]
        or any(type(ref) is not int or ref <= 0 for ref in definition["effect_ids"])
    ):
        raise ValueError("Unsupported reviewed neutral HP-only faW constructor")
    return constructor
