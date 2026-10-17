"""Owned weapon12889 -> native item-container12 effects on a private preview.

Costs and target validation are fcH/fcj; ordinary damage/areas/conditions are
executed by the same native dispatcher as spells. Critical branch is explicit.
Only direct damage roots are admitted; other item actions remain unsupported.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import struct
from copy import deepcopy
from .combat_entry_executor import (
    entry_route,
    execute_entry_roots,
    private_entry_preview,
    seal_entry_transaction,
)
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from wakfu_server.equipment import validate_sheet
from .combat_effect_dispatch import EffectInvocation
from .combat_geometry_snapshot import source_snapshot
from .combat_random_transaction import rollback_external_rng

from .combat_damage_healing import DAMAGE_FAMILIES


@lru_cache(maxsize=1)
def catalog():
    return {
        row["reference"]: row
        for row in protocol_catalog.load(DATA_ROOT / "weapon-combat-rules.json")[
            "items"
        ]
    }


@lru_cache(maxsize=1)
def weapon_runtime_catalog():
    from .combat_server_spell import compiled_runtime_catalog
    from .combat_static_catalogs import CompiledEffects
    from wakfu_server.spell_audit import states_catalog

    base = compiled_runtime_catalog()
    extra = protocol_catalog.load(DATA_ROOT / "weapon-combat-effects.json")["effects"]
    from .combat_effect_runtime import _merge_effects

    merged = _merge_effects(base.source_effects, {"effects": extra})
    return CompiledEffects(merged, states_catalog())


def decode_request(body):
    if len(body) != 27:
        raise ValueError("Invalid native weapon request length")
    actor, uid, slot, x, y, z = struct.unpack(">qqbiih", body)
    return dict(actor_id=actor, item_uid=uid, slot=slot, target=(x, y, z))


def owned_weapon(character, request):
    index = character.get("active_build_index", 0)
    saved = character.get("builds", {}).get(index, {})
    selected = validate_sheet(character, bytes.fromhex(saved.get("equipment", "")))
    if request["slot"] != 15 or not any(
        row["uid"] == request["item_uid"] and row["slot"] == 15 for row in selected
    ):
        raise ValueError("Weapon UID is not equipped in the owned active slot15")
    item = next(
        (
            row
            for row in character.get("inventory_items", ())
            if row["uid"] == request["item_uid"]
        ),
        None,
    )
    if item is None:
        raise ValueError("Weapon unit is unavailable")
    rule = catalog().get(item["reference"])
    if rule is None:
        raise ValueError("Missing native weapon definition")
    return item, rule


def animation(
    fight_id, action_id, actor_id, item_reference, item_level, target, critical
):
    # cvO.dp/cjz: optional spell absent, successful item action, explicit crit.
    return struct.pack(
        ">iiiqihBBB iih",
        fight_id,
        action_id,
        -1,
        actor_id,
        item_reference,
        item_level,
        0,
        0,
        int(critical),
        *target,
    )


@rollback_external_rng
def prepare_server_weapon(
    body,
    character,
    monsters,
    fight,
    owner_id,
    deck_blob,
    *,
    action_id,
    line_of_sight,
    critical,
    rng=None,
    player_characters=None,
    deck_blobs=None,
):
    if (
        (critical is not None and type(critical) is not bool)
        or type(action_id) is not int
        or not 0 < action_id < 2**31
    ):
        raise ValueError("Missing explicit weapon action/critical branch")
    request = decode_request(body)
    actor = fight.actors.get(request["actor_id"])
    if (
        fight.phase != "active"
        or actor is None
        or fight.current is not actor
        or not actor.controlled
        or actor.owner_id != owner_id
        or actor.id != character["id"]
        or actor.hp <= 0
    ):
        raise ValueError("Weapon caster is not the owned active actor")
    item, rule = owned_weapon(character, request)
    if "native_use_criteria" not in rule or not isinstance(
        rule["native_use_criteria"], str
    ):
        raise ValueError("Missing native weapon USE criterion metadata")
    if rule["native_use_criteria"]:
        raise ValueError("Native weapon USE criterion requires an audited evaluator")
    import random
    from .combat_critical import choose_critical

    transaction_rng = random.Random() if rng is None else rng
    from .combat_input_observation import observe_rng

    transaction_rng = observe_rng(
        "player_weapon.before_critical", transaction_rng, external=rng is not None
    )
    decision = choose_critical(
        actor,
        rng=transaction_rng,
        mode="auto" if critical is None else "critical" if critical else "normal",
        critical_available=any(root["variant"] == 1 for root in rule["roots"]),
    )
    critical = decision.critical
    if critical and not any(root["variant"] == 1 for root in rule["roots"]):
        raise ValueError("Weapon has no native critical action branch")
    compiled = weapon_runtime_catalog()
    roots = tuple(
        row["reference"]
        for row in rule["roots"]
        if row["active"] and row["execution_mode"] == 2
    )
    if not roots or any(
        compiled.effects[str(ref)]["effect_class"] not in DAMAGE_FAMILIES
        or compiled.effects[str(ref)].get("children")
        for ref in roots
    ):
        raise ValueError("Weapon contains actions beyond native direct damage")
    from .combat_server_spell import server_runtime

    factory, _ = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=critical,
        rng=transaction_rng,
        compiled=compiled,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    authority = factory.summon_authority(fight, actor)
    if authority.is_carrying is not False:
        raise ValueError("Native weapon casting while carrying is unavailable")
    properties = factory.summon_authority.properties(fight, actor)
    if 41 in properties:  # ffe.sel / fcH.a
        raise ValueError("Native actor property forbids item casting")
    costs = {key: rule[key + "_cost"] for key in ("ap", "mp", "wp")}
    from .combat_ap_property_cost import require_native_ap_cost

    require_native_ap_cost(costs["ap"], properties, weapon=True)
    if any(type(value) is not int or value < 0 for value in costs.values()):
        raise ValueError("Invalid native weapon costs")
    stats = actor.effect_stats
    if not isinstance(stats, dict) or 4 not in stats:
        raise ValueError("Missing authoritative weapon WP snapshot")
    if actor.ap < costs["ap"] or actor.mp < costs["mp"] or stats[4] < costs["wp"]:
        raise ValueError("Insufficient authoritative weapon resources")
    cell = request["target"]
    if cell not in fight.walkable:
        raise ValueError("Weapon target is outside verified terrain")
    dx, dy = cell[0] - actor.position[0], cell[1] - actor.position[1]
    maximum_range = (
        min(rule["native_cpG"], 1) if 2 in properties else rule["native_cpG"]
    )
    if not rule["native_cpF"] <= abs(dx) + abs(dy) <= maximum_range:
        raise ValueError("Weapon target is outside native range")
    if rule["native_gjn"] and dx and dy:
        raise ValueError("Weapon requires native straight-line targeting")
    target = next(
        (a for a in fight.actors.values() if a.hp > 0 and a.position == cell), None
    )
    if rule["native_gjj"] and target is not None:
        raise ValueError("Weapon requires an empty target cell")
    if rule["native_gjl"]:
        raise ValueError("Native weapon QI.P terrain gate is not audited")
    if (
        rule["native_gjk"]
        and cell != actor.position
        and not line_of_sight(actor.position, cell, fight)
    ):
        raise ValueError("Weapon target has no verified native line of sight")
    source, preview = private_entry_preview(
        fight, snapshot=source_snapshot, clone=deepcopy
    )
    caster = preview.actors[actor.id]
    start = len(preview.events)
    plan = dict(
        request,
        item_reference=item["reference"],
        evaluation_level=rule["item_level"],
        costs=costs,
        effect_ids=roots,
        target_id=None if target is None else target.id,
        native_retained_container=dict(
            present=True, type=12, id=item["reference"], is_spell=False, protected=None
        ),
    )
    if getattr(caster, "effect_resource_raw_currents", None) is not None:
        from .combat_resource_pa_notifications import shift_resource_current

        shift_resource_current(preview, caster, 2, costs["ap"], subtract=True)
        shift_resource_current(preview, caster, 3, costs["mp"], subtract=True)
    else:
        before_ap = caster.ap
        caster.ap -= costs["ap"]
        caster.effect_stats[2] = caster.ap
        from .combat_resource_pa_notifications import notify_resource_pa

        notify_resource_pa(preview, caster, 2, before_current=before_ap)
        caster.mp -= costs["mp"]
    caster.effect_stats.update({2: caster.ap, 3: caster.mp, 4: stats[4] - costs["wp"]})
    dispatcher, packets = factory(preview, plan)
    outcomes = execute_entry_roots(
        preview,
        plan,
        caster,
        dispatcher,
        roots,
        route="weapon",
        invocation_factory=EffectInvocation,
        native_level_source=lambda: rule["item_level"],
        native_cell=cell,
    )
    packet = animation(
        fight.id,
        action_id,
        caster.id,
        item["reference"],
        rule["item_level"],
        cell,
        critical,
    )
    plan["critical_decision"] = decision.diagnostic()
    return seal_entry_transaction(
        preview,
        plan,
        caster.effect_stats[4],
        outcomes,
        ((13509, packet), *packets),
        start,
        source,
        action_id,
    )
