"""Selected equipment/aptitude bonuses and explicit temporary server profiles.

Only native passive equipment effects (eHi.a: aZD==0, fKP==false) feed
characteristics. Active item actions remain separately reported; unconditional
eWN maximum+current and scalar eWQ passives are evaluated.
Other effects remain explicitly reported, never converted to invented bonuses.
Competitive dungeon profile bonuses are separately authorized local policy.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from wakfu_server.equipment import validate_sheet
from wakfu_server.health import maximum

CATALOG = {
    item["reference"]: item
    for item in protocol_catalog.load(DATA_ROOT / "item-equipment-effects.json")[
        "items"
    ]
}


@lru_cache(maxsize=None)
def _inactive_passive_roots(reference):
    from wakfu_server.combat_character_copy_equipment import (
        native_copied_equipment_catalog,
    )
    from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan

    plan = copied_equipment_plan(reference, native_copied_equipment_catalog())
    return {
        root["reference"]: root
        for root in plan["roots"]
        if root.get("criterion_raw") == "False"
        and root.get("children") == []
        and root.get("child_definitions") == []
    }


def inactive_passive_root(reference, effect):
    """Recognize original constant-false leaf roots without granting bonuses."""
    if not (
        effect.get("effect_criteria") is True
        and effect.get("has_triggers") is False
        and type(effect.get("native_variant")) is int
        and effect["native_variant"] == 0
        and effect.get("native_active_effect") is False
        and type(effect.get("target_mask")) is int
        and effect["target_mask"] == 0
    ):
        return False
    root = _inactive_passive_roots(reference).get(effect.get("id"))
    if root is None:
        return False
    metadata = root["metadata"]
    return (
        root["effect_class"] == effect.get("generic")
        and root["parameters"] == effect.get("params")
        and root["parameter_count"] == effect.get("parameter_count")
        and root["variant"] == 0
        and metadata.get("native_execution_mode") == 0
        and metadata.get("native_active_effect") is False
        and metadata.get("native_effect_flags") == []
        and metadata.get("native_target_selector") == {"class": "fcE", "mask": 0}
    )


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
    from .equipment_resource_bonuses import reduction

    reduced = reduction(effect)
    if reduced is not None:
        return reduced[0], -reduced[1]
    if scalar_reduction(effect):
        parsed = _scalar_parameters(effect)
        return parsed["stat_id"], -parsed["requested"]
    dynamic = dynamic_scalar_bonus(effect)
    if dynamic is not None:
        return dynamic
    if (
        effect.get("generic") == 192
        and effect["runner"] == "eWO"
        and effect["parameter_count"] == 1
        and len(values) == 1
        and type(values[0]) is int
        and values[0] >= 0
        and effect.get("native_variant") == 0
        and effect.get("native_active_effect") is False
    ):
        # Original fNI binds192/eWO to WP(4). Its standard equipment
        # calculation subtracts the amount from current/maximum; bbR restores
        # it. The exported stat_id=-1 means the exporter omitted that binding.
        return 4, -values[0]
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
    scalar = _scalar_parameters(effect)
    if scalar is not None and effect["runner"] == "eWQ":
        return scalar["stat_id"], scalar["requested"]
    if (
        effect["runner"] == "eWQ"
        and effect["parameter_count"] == 1
        and len(values) == 1
        and values[0] != -1
    ):
        return effect["stat_id"], values[0]
    if (
        effect["runner"] == "eWQ"
        and effect["parameter_count"] == 1
        and len(values) == 1
        and values[0] == -1
    ):
        return effect["stat_id"], 0  # Native fresh equipment context has no fLP source.
    return None


def _scalar_parameters(effect):
    """Use native eWW's deterministic parser for evaluated equipment values.

    The export already evaluates each parameter at its actual item/pet level.
    Constant pairs preserve those exact integers while sharing native percent,
    fixed/dynamic-PC and fresh-equipment triggering-value interpretation.
    Native fKJ, not backing-array length, determines which values are consumed.
    """
    values = effect.get("values")
    count = effect.get("parameter_count")
    if not (
        effect.get("runner") in ("eWQ", "eWR")
        and type(effect.get("generic")) is int
        and type(count) is int
        and count in (1, 2, 3)
        and isinstance(values, list)
        and len(values) >= count
        and all(
            type(value) is int and -(1 << 31) <= value < (1 << 31) for value in values
        )
        and effect.get("stat_limit") == -1
        and type(effect.get("stat_id")) is int
        and effect.get("effect_criteria") is False
        and effect.get("has_triggers") is False
        and type(effect.get("target_mask")) is int
        and effect["target_mask"] == 0
        and type(effect.get("native_variant")) is int
        and effect["native_variant"] == 0
        and effect.get("native_active_effect") is False
    ):
        return None
    from .combat_static_catalogs import characteristic_registry
    from .combat_current_stat_parameters import stat_parameters
    from .equipment_characteristics import native_rows

    native = characteristic_registry()["effects"].get(str(effect["generic"]))
    if native is None or native["runner"] != effect["runner"]:
        return None
    # Preserve the existing one-parameter resistance reduction projection.
    # New parameter shapes do not acquire an unqualified owned-stack policy.
    if native["limit_policy"] != "NORMAL" and not (
        native["limit_policy"] == "RESISTANCE_CAP"
        and effect["runner"] == "eWR"
        and count == 1
    ):
        return None
    fixed = native["fixed_stat_id"]
    if (fixed is None and effect["stat_id"] != -1) or (
        fixed is not None and effect["stat_id"] != fixed
    ):
        return None
    # Dynamic equipment effects and subtraction keep their existing nonnegative
    # amount contract; trigger copies/negative reductions require another source.
    if (fixed is None or effect["runner"] == "eWR") and values[0] < 0:
        return None
    if fixed is None and count < 3:
        return None
    parsed = stat_parameters(
        [part for value in values[:count] for part in (value, 0)],
        0,
        registered_stat_id=fixed,
        percent_default=native["percent_default"],
        trigger_value=0,
    )
    row = native_rows().get(parsed["stat_id"])
    if parsed["percent"] or row is None or row["expandable"] or row["frozen"]:
        return None
    return parsed


def dynamic_scalar_bonus(effect):
    """Resolve native dynamic eWQ gain without treating a missing PC as null."""
    if effect.get("generic") != 39 or effect.get("runner") != "eWQ":
        return None
    parsed = _scalar_parameters(effect)
    return None if parsed is None else (parsed["stat_id"], parsed["requested"])


def scalar_reduction(effect):
    """Recognize deterministic native scalar eWR roots in application order."""
    return effect.get("runner") == "eWR" and _scalar_parameters(effect) is not None


def bonuses(
    character,
    *,
    build_index=None,
    include_consumable_buffs=False,
    criterion_context=None,
    ignore_ineligible=False,
    native_baseline=None,
    _selected_entries=None
):
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
    character = dict(
        character,
        real_level=character.get("real_level", character["level"]),
        level=level,
        effective_level=level,
    )
    saved = character.get("builds", {}).get(index, {})
    blob = bytes.fromhex(saved.get("equipment", ""))
    scalar_overrides = {}
    resource_overrides = None
    if _selected_entries is None:
        from .equipment import resolve_sheet

        resolution = resolve_sheet(
            character,
            blob,
            criterion_context=criterion_context,
            ignore_ineligible=ignore_ineligible,
            native_baseline=native_baseline,
            build_index=index,
            include_consumable_buffs=include_consumable_buffs,
        )
        selected = resolution["entries"]
        scalar_overrides = resolution["scalar_overrides"]
        resource_overrides = resolution.get("resource_states")
    else:
        # Only the structural/ownership-validated eligibility adapter supplies
        # these rows while constructing its pre-application native context.
        selected = _selected_entries
    owned = {item["uid"]: item for item in character.get("inventory_items", [])}
    stats, unsupported, uids, active_effects = {}, [], [], []
    operations, ordered_ids, gear_ranges = [], set(), {}
    resource_kinds = {}
    hp_operations = []

    def contribute(stat, amount, *, subtract=False, resource_kind=None):
        stats[stat] = stats.get(stat, 0) + (-amount if subtract else amount)
        if stat in (2, 3, 4):
            resource_kinds[len(operations)] = resource_kind or dict(
                family="eWN", stat=stat, apply_current=True, remove_current=False
            )
        operations.append((stat, amount, subtract))

    # Original selected-build eUJ applies the category-36 aptitude effects
    # before eHi.doT registers equipment in native slot/effect order.
    from .aptitudes import bonuses as aptitude_bonuses

    aptitudes = aptitude_bonuses(character, build_index=index)
    for stat, delta in aptitudes["stats"].items():
        contribute(stat, delta)

    for entry in sorted(selected, key=lambda row: row["slot"]):
        operation_start = len(operations)
        item = owned[entry["uid"]]
        uids.append(item["uid"])
        template = CATALOG.get(item["reference"])
        if template is None:
            from .empty_equipment_effects import template as empty_template

            template = empty_template(item["reference"])
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
        elif "pet" in item:
            state = item["pet"]
            from wakfu_server.pet_hibernation import active as pet_active

            if not pet_active(state):
                continue
            if (
                type(state.get("xp")) is not int
                or state["xp"] < 0
                or type(state.get("xp_per_level")) is not int
                or state["xp_per_level"] <= 0
                or type(state.get("maximum_level")) is not int
                or state["maximum_level"] < 0
            ):
                raise ValueError("Missing native equipped companion level model")
            pet_level = min(
                state["maximum_level"], state["xp"] // state["xp_per_level"]
            )
        effects = () if template is None else template["effects"]
        if template is not None:
            from .equipment_level_groups import (
                project as project_level_groups,
                qualified_source,
            )

            if qualified_source(item["reference"]) is not None:
                from .equipment_context import for_character

                effects = project_level_groups(
                    item["reference"],
                    actor_level=level,
                    container_level=pet_level,
                    criterion_context=for_character(character, criterion_context),
                )
        for effect_index, effect in enumerate(effects):
            if pet_level is not None and not effect.get("_native_level_group"):
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
            if inactive_passive_root(item["reference"], effect):
                continue  # Original literal False cannot contribute a bonus.
            from wakfu_server.profession_equipment_modifiers import (
                passive_profession_effect,
            )

            if passive_profession_effect(effect, item["reference"]):
                continue  # The selected profession manager owns these modifiers.
            # eWO exposes stat_id=-1 for multiple native resource families;
            # their generic selects distinct HP versus AP/MP/WP semantics.
            # Only generic 21 is the HP PA lifecycle. Generics 56/57/192
            # are deterministic resource reductions handled by `reduction`
            # below and must not be sent through the HP descriptor parser.
            if effect.get("generic") == 21 and effect.get("runner") == "eWO":
                from .equipment_hp_bonuses import descriptor as hp_descriptor

                parsed_hp = hp_descriptor(effect)
                if parsed_hp is None:
                    unsupported.append(
                        dict(
                            uid=item["uid"],
                            reference=item["reference"],
                            effect_id=effect.get("id"),
                            generic=effect.get("generic"),
                            reason="unsupported-native-hp-eWO-shape-or-context",
                        )
                    )
                    continue
                hp_operations.append(
                    dict(
                        source_uid=item["uid"],
                        slot=entry["slot"],
                        effect_index=effect_index,
                        effect_id=effect["id"],
                        **parsed_hp,
                    )
                )
                continue
            if effect["generic"] in (1068, 1069):
                from .inventory_elements import bonuses as selected_bonuses

                elemental = selected_bonuses(item, effect)
                if elemental is not None:
                    for stat, delta in elemental.items():
                        contribute(stat, delta)
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
            from .equipment_resource_bonuses import reduction, kind as resource_kind

            resource = (
                resource_kind(item["reference"], effect, stat)
                if stat in (2, 3, 4)
                else None
            )
            if reduction(effect) is not None:
                contribute(stat, -delta, subtract=True, resource_kind=resource)
            elif scalar_reduction(effect):
                ordered_ids.add(stat)
                contribute(stat, effect["values"][0], subtract=True)
            else:
                if (
                    dynamic_scalar_bonus(effect) is not None
                    or effect.get("parameter_count", 0) > 1
                    and _scalar_parameters(effect) is not None
                ):
                    ordered_ids.add(stat)
                contribute(stat, delta, resource_kind=resource)
        from .shard_bonuses import bonuses as shard_bonuses

        socketed = shard_bonuses(item, entry["slot"], include_operations=True)
        for stat, delta in socketed["stats"].items():
            stats[stat] = stats.get(stat, 0) + delta
        operations.extend(socketed["stat_operations"])
        for operation_index in range(
            len(operations) - len(socketed["stat_operations"]), len(operations)
        ):
            stat = operations[operation_index][0]
            if stat in (2, 3, 4):
                resource_kinds[operation_index] = dict(
                    family="eWN", stat=stat, apply_current=True, remove_current=False
                )
        gear_ranges[item["uid"]] = (operation_start, len(operations))
        unsupported.extend(socketed["unsupported"])
    from wakfu_server.characters.dungeon_modulation import bonus_stats

    for stat, delta in bonus_stats(character, index).items():
        contribute(stat, delta)
    territory_stats = character.get("territory_stat_bonuses", {})
    if not isinstance(territory_stats, dict) or any(
        type(stat) is not int
        or stat not in (1, 33, 36)
        or type(delta) is not int
        or not -1000 <= delta <= 1000
        for stat, delta in territory_stats.items()
    ):
        raise ValueError("Invalid derived territory characteristic bonuses")
    territory_stats = dict(territory_stats)
    if "territory_health_projection" in character:
        # An owned character uses the committed maximum contribution. Fresh
        # ecological observations may change Wisdom/Prospection, but cannot
        # change HP before the canonical health transaction commits.
        projection = character["territory_health_projection"]
        if projection is None:
            applied = 0
        elif (
            not isinstance(projection, dict)
            or type(projection.get("applied_flat")) is not int
            or not -1000 <= projection["applied_flat"] <= 1000
        ):
            raise ValueError("Invalid applied territorial health projection")
        else:
            applied = projection["applied_flat"]
        territory_stats[1] = applied
    for stat, delta in territory_stats.items():
        contribute(stat, abs(delta), subtract=delta < 0)
    if type(include_consumable_buffs) is not bool:
        raise ValueError("Invalid exploration consumable characteristic policy")
    percentages = dict(aptitudes["percentages"])
    if include_consumable_buffs:
        from wakfu_server.consumable_characteristics import (
            bonuses as consumable_bonuses,
        )

        consumables = consumable_bonuses(character, include_operations=True)
        for stat, delta in consumables["stats"].items():
            stats[stat] = stats.get(stat, 0) + delta
        operations.extend(consumables["stat_operations"])
        for operation_index in range(
            len(operations) - len(consumables["stat_operations"]), len(operations)
        ):
            stat = operations[operation_index][0]
            if stat in (2, 3, 4):
                source_index = operation_index - (
                    len(operations) - len(consumables["stat_operations"])
                )
                resource_kinds[operation_index] = consumables["resource_kinds"][
                    source_index
                ]
        for stat, delta in consumables.get("percentages", {}).items():
            percentages[stat] = percentages.get(stat, 0) + delta
        unsupported.extend(consumables["unsupported"])
    if ordered_ids:
        from .equipment_characteristics import replay

        stats.update(replay(operations, ordered_ids, baseline=native_baseline))
    stats.update(scalar_overrides)
    from wakfu_server.guild_member_effects import bonuses as guild_bonuses

    guild = guild_bonuses(character)
    for stat, delta in guild["stats"].items():
        stats[stat] = stats.get(stat, 0) + delta
    guild_operation_start = len(operations)
    operations.extend(guild["stat_operations"])
    for operation_index, resource in guild["resource_kinds"].items():
        resource_kinds[guild_operation_start + operation_index] = resource
    for stat, delta in guild["percentages"].items():
        percentages[stat] = percentages.get(stat, 0) + delta
    unsupported.extend(guild["unsupported"])
    from .equipment_resource_bonuses import (
        baseline as resource_baseline,
        project as resource_project,
    )

    resource_base = resource_baseline(character, criterion_context)
    resource_projection = resource_project(operations, resource_kinds, resource_base)
    final_resources = (
        resource_projection["final"]
        if resource_overrides is None
        else resource_overrides
    )
    if resource_overrides is not None:
        resource_projection["final"] = resource_overrides
    for stat, state in final_resources.items():
        if (
            stat in stats
            or state["maximum"] != resource_projection["initial"][stat]["maximum"]
        ):
            stats[stat] = (
                state["maximum"] - resource_projection["initial"][stat]["maximum"]
            )
    return dict(
        stats=stats,
        percentages=percentages,
        unsupported=unsupported + aptitudes["unsupported"],
        equipped_uids=uids,
        active_effects=active_effects,
        stat_operations=tuple(operations),
        ordered_stat_ids=frozenset(ordered_ids),
        gear_operation_ranges=gear_ranges,
        resource_projection=resource_projection,
        resource_baseline=resource_base,
        resource_kinds=resource_kinds,
        hp_operations=tuple(hp_operations),
        build_index=index,
    )


def effective_character(character, *, build_index=None, include_consumable_buffs=False):
    result = dict(character)
    evaluated = bonuses(
        character,
        build_index=build_index,
        include_consumable_buffs=include_consumable_buffs,
    )
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
    hp_projection = character.get("equipment_hp_projection")
    projected_hp_stale = False
    projected_current = None
    if hp_projection is not None and index == character.get("active_build_index", 0):
        from wakfu_server.equipment_hp_lifecycle import (
            NativeHPActor,
            OwnedEwoHPReplay,
        )

        if not isinstance(hp_projection, dict) or not isinstance(
            hp_projection.get("actor"), dict
        ):
            raise ValueError("Malformed persisted native equipment HP projection")
        persisted_actor = NativeHPActor(**hp_projection["actor"])
        replay = OwnedEwoHPReplay(persisted_actor, hp_projection.get("receipts", ()))
        if replay.matches(evaluated["hp_operations"]):
            base_replay = OwnedEwoHPReplay.restore(replay.checkpoint())
            for key in sorted(
                tuple(base_replay.receipts),
                key=lambda item: (base_replay._order(base_replay.receipts[item]), item),
                reverse=True,
            ):
                base_replay.remove(key)
            base_raw = base_replay.actor.effect_base_maxima[1]
            equipment_delta = persisted_actor.effect_base_maxima[1] - base_raw
            # Apply the saved eWO raw maximum delta to the ordinary equipment
            # reducer before the current percentage phase. This keeps food and
            # other late maximum modifiers in their existing pipeline.
            flat += equipment_delta
            effective = max(
                1,
                flat
                + (abs(flat * percentage) // 100)
                * (1 if flat * percentage >= 0 else -1),
            )
            if not include_consumable_buffs:
                if persisted_actor.max_hp == effective and (
                    persisted_actor.hp == character.get("hp")
                    or character.get("consumable_states")
                ):
                    # The pre-food PA owns its actual raw/effective current.
                    # Food restores the canonical wound at its own native
                    # import boundary, after increasing this actor's maximum.
                    projected_current = persisted_actor.hp
                elif "hp_damage" in character and "health_dead" in character:
                    from wakfu_server.health_policy import visible

                    hp = visible(
                        effective,
                        character["hp_damage"],
                        character["health_dead"],
                        character.get("hp_zero_valid", False),
                    )
                    projected_hp_stale = True
    hp = (
        projected_current
        if projected_current is not None
        else min(effective, max(0, character.get("hp", base)))
    )
    if (
        projected_current is None
        and (
            projected_hp_stale
            or character.get("consumable_states")
            or character.get("guild_member_effects")
            or character.get("pet_hibernation_projection")
        )
        and "hp_damage" in character
        and "health_dead" in character
    ):
        from wakfu_server.health_policy import visible

        # Native combat imports food maxima/current later. Start from the
        # canonical wounds at this reducer's selected maximum, not world HP
        # that already includes a food maximum contribution.
        hp = visible(
            effective,
            character["hp_damage"],
            character["health_dead"],
            character.get("hp_zero_valid", False),
        )
    result.update(
        base_max_hp=base,
        effective_level=effective_level,
        max_hp=effective,
        hp=hp,
        equipment_stats=evaluated["stats"],
        equipment_unsupported=evaluated["unsupported"],
    )
    return result


def native_hp_baseline(character, *, build_index=None):
    """Return the authoritative pre-eWO HP PA state for the selected build."""
    from wakfu_server.builds import effective_sheet_level
    from wakfu_server.health_policy import visible
    from wakfu_server.equipment_hp_lifecycle import NativeHPActor

    index = (
        character.get("active_build_index", 0) if build_index is None else build_index
    )
    evaluated = bonuses(character, build_index=index)
    level = effective_sheet_level(character, index)
    raw_maximum = maximum(character["breed"], level) + evaluated["stats"].get(1, 0)
    percentage = evaluated["percentages"].get(1, 0)
    # The non-eWO build maximum changes with ordinary gear/level; preserve the
    # canonical wound and independent death state while constructing its PA.
    seed = NativeHPActor(
        raw_current=0,
        raw_maximum=raw_maximum,
        raw_minimum=0,
        percentage=percentage,
    )
    raw_current = visible(
        seed.max_hp,
        character["hp_damage"],
        character["health_dead"],
        character.get("hp_zero_valid", False),
    )
    baseline = dict(seed.plain(), raw_current=raw_current)
    actor = NativeHPActor(**baseline)
    if actor.max_hp != max(1, seed.max_hp):
        raise ValueError("Native eWO baseline differs from ordinary health reducer")
    return baseline


def combat_resources(
    character,
    *,
    wp=None,
    base_ap=None,
    base_mp=None,
    base_initiative=0,
    build_index=None,
    include_consumable_buffs=False
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
    evaluated = bonuses(
        character,
        build_index=build_index,
        include_consumable_buffs=include_consumable_buffs,
    )
    stats = evaluated["stats"]
    return dict(
        ap=max(0, base_ap + stats.get(2, 0)),
        mp=max(0, base_mp + stats.get(3, 0)),
        wp=max(0, wp + stats.get(4, 0)),
        initiative=base_initiative + stats.get(35, 0),
        stats=stats,
        unsupported=evaluated["unsupported"],
    )
