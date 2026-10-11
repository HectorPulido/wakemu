"""Selected equipment/aptitude bonuses and explicit temporary server profiles.

Only native passive equipment effects (eHi.a: aZD==0, fKP==false) feed
characteristics. Active item actions remain separately reported; unconditional
eWN maximum+current and scalar eWQ passives are evaluated.
Other effects remain explicitly reported, never converted to invented bonuses.
Competitive dungeon profile bonuses are separately authorized local policy.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from wakfu_server.paths import DATA_ROOT
from wakfu_server.equipment import validate_sheet
from wakfu_server.health import maximum

CATALOG = {
    item["reference"]: item
    for item in protocol_catalog.load(DATA_ROOT / "item-equipment-effects.json")[
        "items"
    ]
}


def passive_null_marker(effect):
    """Native standard eXE400 has no calculation or characteristic mutation.

    Conditional/subscribed/status variants still need their own execution
    context. This recognizes the unconditional zero-parameter equipment root
    without inventing a characteristic bonus or another execution path.
    """
    return (
        effect.get("generic") == 400
        and effect.get("runner") == "eXE"
        and effect.get("parameter_count") == 0
        and effect.get("params") == []
        and effect.get("values") == []
        and effect.get("stat_id") == -1
        and effect.get("has_triggers") is False
        and effect.get("effect_criteria") is False
        and effect.get("target_mask") == 0
        and effect.get("native_variant") == 0
        and effect.get("native_active_effect") is False
    )


def _flat(effect):
    values = effect["values"]
    if (
        effect["effect_criteria"]
        or effect["has_triggers"]
        or effect["target_mask"] != 0
    ):
        return None
    if (
        effect["stat_id"] < 0
        or not values
        or (values[0] == -2 and effect["runner"] != "eWQ")
    ):
        return None  # native triggering-effect copy sentinel
    if (
        effect["runner"] == "eWN"
        and effect["parameter_count"] == 3
        and values[1:] == [1, 0]
    ):
        return effect["stat_id"], values[0]
    if effect["runner"] == "eWQ" and effect["parameter_count"] == 1 and values[0] != -1:
        return effect["stat_id"], values[0]
    if effect["runner"] == "eWQ" and effect["parameter_count"] == 1 and values[0] == -1:
        return effect["stat_id"], 0  # Native fresh equipment context has no fLP source.
    return None


def bonuses(character, *, build_index=None):
    # Current runtime has no persisted sheet activation; default sheet0 is
    # explicit. A future activation caller must supply its authoritative index.
    index = (
        character.get("active_build_index", 0) if build_index is None else build_index
    )
    from wakfu_server.builds import valid_index

    if not valid_index(index):
        raise ValueError("Invalid active equipment sheet")
    from wakfu_server.builds import effective_sheet_level

    level = effective_sheet_level(character, index)
    character = dict(character, level=level)
    saved = character.get("builds", {}).get(index, {})
    blob = bytes.fromhex(saved.get("equipment", ""))
    selected = validate_sheet(character, blob)
    owned = {item["uid"]: item for item in character.get("inventory_items", [])}
    stats, unsupported, uids, active_effects = {}, [], [], []
    for entry in selected:
        item = owned[entry["uid"]]
        uids.append(item["uid"])
        template = CATALOG.get(item["reference"])
        if template is None:
            unsupported.append(
                dict(
                    uid=item["uid"],
                    reference=item["reference"],
                    reason="missing-effect-template",
                )
            )
        pet_level = None
        if "mount" in item:
            models = protocol_catalog.load(DATA_ROOT / "mount-models.json")["models"]
            model = next(
                (
                    model
                    for model in models
                    if model["model_id"]
                    == item["mount"].get("model_id", item["mount"].get("definition_id"))
                ),
                None,
            )
            if model is None or model["xp_per_level"] <= 0:
                raise ValueError("Missing native equipped pet level model")
            pet_level = min(
                model["max_level"], item["mount"]["xp"] // model["xp_per_level"]
            )
        for effect in () if template is None else template["effects"]:
            if pet_level is not None:
                from wakfu_server.combat.combat_parameters import parameter_value

                effect = dict(
                    effect,
                    values=[
                        parameter_value(effect["params"], index, pet_level)
                        for index in range(effect["parameter_count"])
                    ],
                )
            # eHi.a never registers these in the actor's passive equipment
            # context. Keep identity for the separate item action executor;
            # do not turn weapon attacks into bonuses or unsupported passives.
            variant = effect.get("native_variant")
            active = effect.get("native_active_effect")
            if (
                type(variant) is int
                and type(active) is bool
                and (variant != 0 or active)
            ):
                active_effects.append(
                    dict(
                        uid=item["uid"],
                        reference=item["reference"],
                        effect_id=effect["id"],
                        generic=effect["generic"],
                        native_variant=variant,
                        native_active_effect=active,
                    )
                )
                continue
            if passive_null_marker(effect):
                continue  # Standard eXE has no characteristic contribution.
            if effect["generic"] in (1068, 1069):
                from .inventory_elements import bonuses as selected_bonuses

                elemental = selected_bonuses(item, effect)
                if elemental is not None:
                    for stat, delta in elemental.items():
                        stats[stat] = stats.get(stat, 0) + delta
                    continue
            flat = _flat(effect)
            if flat is None:
                unsupported.append(
                    dict(
                        uid=item["uid"],
                        reference=item["reference"],
                        effect_id=effect["id"],
                        generic=effect["generic"],
                        reason="unsupported-native-effect",
                    )
                )
                continue
            stat, delta = flat
            stats[stat] = stats.get(stat, 0) + delta
        from .shard_bonuses import bonuses as shard_bonuses

        socketed = shard_bonuses(item, entry["slot"])
        for stat, delta in socketed["stats"].items():
            stats[stat] = stats.get(stat, 0) + delta
        unsupported.extend(socketed["unsupported"])
    from .aptitudes import bonuses as aptitude_bonuses

    aptitudes = aptitude_bonuses(character, build_index=index)
    for stat, delta in aptitudes["stats"].items():
        stats[stat] = stats.get(stat, 0) + delta
    from wakfu_server.characters.dungeon_modulation import bonus_stats

    for stat, delta in bonus_stats(character, index).items():
        stats[stat] = stats.get(stat, 0) + delta
    territory_stats = character.get("territory_stat_bonuses", {})
    if not isinstance(territory_stats, dict) or any(
        type(stat) is not int
        or stat not in (33, 36)
        or type(delta) is not int
        or not -1000 <= delta <= 1000
        for stat, delta in territory_stats.items()
    ):
        raise ValueError("Invalid derived territory characteristic bonuses")
    for stat, delta in territory_stats.items():
        stats[stat] = stats.get(stat, 0) + delta
    return dict(
        stats=stats,
        percentages=aptitudes["percentages"],
        unsupported=unsupported + aptitudes["unsupported"],
        equipped_uids=uids,
        active_effects=active_effects,
        build_index=index,
    )


def effective_character(character, *, build_index=None):
    result = dict(character)
    evaluated = bonuses(character, build_index=build_index)
    from wakfu_server.builds import effective_sheet_level

    index = (
        character.get("active_build_index", 0) if build_index is None else build_index
    )
    effective_level = effective_sheet_level(character, index)
    base = maximum(character["breed"], effective_level)
    flat = base + evaluated["stats"].get(1, 0)
    percentage = evaluated["percentages"].get(1, 0)
    # fff.aYU uses Java integer division toward zero.
    effective = max(
        1,
        flat + (abs(flat * percentage) // 100) * (1 if flat * percentage >= 0 else -1),
    )
    result.update(
        base_max_hp=base,
        effective_level=effective_level,
        max_hp=effective,
        hp=min(effective, max(0, character.get("hp", base))),
        equipment_stats=evaluated["stats"],
        equipment_unsupported=evaluated["unsupported"],
    )
    return result


def combat_resources(
    character,
    *,
    wp=None,
    base_ap=None,
    base_mp=None,
    base_initiative=0,
    build_index=None
):
    from .breed_resources import base_resources

    native = base_resources(character)
    wp = native["WP"] if wp is None else wp
    base_ap = native["AP"] if base_ap is None else base_ap
    base_mp = native["MP"] if base_mp is None else base_mp
    if any(type(value) is not int or value < 0 for value in (wp, base_ap, base_mp)):
        raise ValueError("Invalid base combat resources")
    if type(base_initiative) is not int:
        raise ValueError("Invalid base initiative")
    evaluated = bonuses(character, build_index=build_index)
    stats = evaluated["stats"]
    return dict(
        ap=max(0, base_ap + stats.get(2, 0)),
        mp=max(0, base_mp + stats.get(3, 0)),
        wp=max(0, wp + stats.get(4, 0)),
        initiative=base_initiative + stats.get(35, 0),
        stats=stats,
        unsupported=evaluated["unsupported"],
    )
