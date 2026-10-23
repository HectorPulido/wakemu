"""Native passive eXx modifiers owned by selected, eligible equipment.

These effects mutate the profession manager, never combat characteristics.
The generic/action-kind bindings come from original eVi/eXx/eRJ/eRM.
"""
from functools import lru_cache

KINDS = {
    2000: "plant_probability",
    2001: "collect_quantity",
    2002: "craft_speed",
    2003: "plant_speed",
    2004: "collect_speed",
    2006: "craft_xp",
    2007: "plant_xp",
    2008: "collect_xp",
}
SOURCE_SHA256 = "5c4e45905718939b067c456162e46137abc45a93b4e203cc10cf32603c5bcff8"


@lru_cache(maxsize=1)
def definitions():
    import json
    from hashlib import sha256
    from pathlib import Path

    raw = Path(__file__).with_name("profession_equipment_effects.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native equipment profession definitions")
    return json.loads(raw)["items"]


def passive_profession_effect(effect, reference=None):
    """Recognize the unconditional native profession leaf, with no PC bonus."""
    import math

    definition = definitions().get(str(reference), {}).get(str(effect.get("id")))
    if definition is None:
        return False
    expected = definition["equipment_effect"]
    if {key: value for key, value in effect.items() if key != "values"} != {
        key: value for key, value in expected.items() if key != "values"
    }:
        return False
    criterion = definition["native_root"]["criterion_raw"]
    count = effect.get("parameter_count")
    params, values = effect.get("params"), effect.get("values")
    return (
        effect.get("generic") in KINDS
        and effect.get("runner") == "eXx"
        and effect.get("stat_id") == -1
        and effect.get("native_variant") == 0
        and effect.get("native_active_effect") is False
        and criterion in ("", "IsNeoServer()")
        and effect.get("effect_criteria") is bool(criterion)
        and effect.get("has_triggers") is False
        and effect.get("target_mask") == 0
        and type(count) is int
        and count in (1, 2)
        and isinstance(params, list)
        and len(params) == count * 2
        and all(
            type(value) in (int, float) and math.isfinite(value) for value in params
        )
        and isinstance(values, list)
        and len(values) == count
        and all(type(value) is int for value in values)
        and (count == 1 or values[1] >= 0)
    )


def aggregate(character, profession_id, *, criterion_context=None, is_neo_server=None):
    """Resolve active sheet ownership, eligibility and native profession scope."""
    if type(profession_id) is not int or profession_id <= 0:
        raise ValueError("Invalid equipment profession identity")
    if is_neo_server is not None and type(is_neo_server) is not bool:
        raise ValueError("Invalid equipment profession server context")
    from wakfu_server.equipment import resolve_sheet
    from wakfu_server.equipment_stats import CATALOG
    from wakfu_server.builds import valid_index
    from wakfu_server.combat_parameters import parameter_value

    index = character.get("active_build_index", 0)
    if not valid_index(index):
        raise ValueError("Invalid equipment profession sheet")
    saved = character.get("builds", {}).get(index, {})
    selected = resolve_sheet(
        character,
        bytes.fromhex(saved.get("equipment", "")),
        criterion_context=criterion_context,
        build_index=index,
    )["entries"]
    owned = {item["uid"]: item for item in character.get("inventory_items", ())}
    result = dict.fromkeys(KINDS.values(), 0)
    for entry in selected:
        item = owned[entry["uid"]]
        template = CATALOG.get(item["reference"])
        if template is None:
            continue
        pet_level = None
        if "pet" in item:
            from wakfu_server.pet_hibernation import active

            pet = item["pet"]
            if not active(pet):
                continue
            if (
                type(pet.get("xp")) is not int
                or pet["xp"] < 0
                or type(pet.get("xp_per_level")) is not int
                or pet["xp_per_level"] <= 0
                or type(pet.get("maximum_level")) is not int
                or pet["maximum_level"] < 0
            ):
                raise ValueError("Missing native equipment profession pet level")
            pet_level = min(pet["maximum_level"], pet["xp"] // pet["xp_per_level"])
        elif "mount" in item:
            from wakfu_server import native_catalog
            from wakfu_server.paths import DATA_ROOT

            mount = item["mount"]
            model_id = mount.get("model_id", mount.get("definition_id"))
            model = next(
                (
                    row
                    for row in native_catalog.load(DATA_ROOT / "mount-models.json")[
                        "models"
                    ]
                    if row["model_id"] == model_id
                ),
                None,
            )
            if model is None or model["xp_per_level"] <= 0:
                raise ValueError("Missing native equipment profession mount level")
            pet_level = min(model["max_level"], mount["xp"] // model["xp_per_level"])
        for effect in template["effects"]:
            if not passive_profession_effect(effect, item["reference"]):
                continue
            definition = definitions()[str(item["reference"])][str(effect["id"])]
            if definition["native_root"]["criterion_raw"]:
                if is_neo_server is None:
                    raise ValueError("Missing equipment profession Neo context")
                if not is_neo_server:
                    continue
            values = (
                effect["values"]
                if pet_level is None
                else [
                    parameter_value(effect["params"], parameter, pet_level)
                    for parameter in range(effect["parameter_count"])
                ]
            )
            scope = 0 if effect["parameter_count"] == 1 else values[1]
            if scope in (0, profession_id):
                result[KINDS[effect["generic"]]] += values[0]
    return result


def modifiers(store, db, character_id, profession_id):
    """Read equipment and criteria from the caller's fenced transaction."""
    if type(profession_id) is not int or profession_id <= 0:
        raise ValueError("Invalid equipment profession identity")
    from wakfu_server.equipment_persisted_context import load
    from wakfu_server.neo_regeneration import mode_from_database
    from wakfu_server.wire import proto_fields

    owner = db.execute(
        "SELECT c.account_id,b.equipment FROM characters c "
        "LEFT JOIN character_build_selection s ON s.character_id=c.id "
        "LEFT JOIN character_builds b ON b.character_id=c.id "
        "AND b.build_index=COALESCE(s.active_index,0) "
        "WHERE c.id=%s AND c.deleted_at IS NULL",
        (character_id,),
    ).fetchone()
    if owner is None:
        raise ValueError("Unavailable equipment profession owner")
    # Most action actors have no profession equipment. Avoid hydrating their
    # complete inventory/account aggregate on every gather/craft checkpoint.
    selected_uids = []
    for tag, value in proto_fields(bytes(owner["equipment"] or b"")):
        if tag == 10 and isinstance(value, bytes):
            uid = dict(proto_fields(value)).get(8)
            if type(uid) is int and uid > 0:
                selected_uids.append(uid)
    if (
        not selected_uids
        or db.execute(
            "SELECT 1 FROM inventory_items WHERE character_id=%s AND uid=ANY(%s) "
            "AND reference=ANY(%s) LIMIT 1",
            (
                character_id,
                selected_uids,
                [int(reference) for reference in definitions()],
            ),
        ).fetchone()
        is None
    ):
        return dict.fromkeys(KINDS.values(), 0)
    character = store.character(owner["account_id"], character_id, db)
    return aggregate(
        character,
        profession_id,
        criterion_context=load(db, character),
        is_neo_server=mode_from_database(db),
    )
