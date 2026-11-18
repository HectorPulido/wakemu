"""Battle-local native resource constructor for the selected order form.

Native eWG933 switches the book only. This reviewed encounter join applies the
original3217 resource profile after ordinary class/equipment initialization.
"""
from hashlib import sha256
import json

SCHEMA = "reviewed-native-order-resource-constructor-v1"


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def project(fight):
    from .native_order_trial_encounter import policy_for
    from .native_order_trial_checkpoint import validate
    from .combat_morph_spellbook import morph_record
    from .combat_actor_snapshot import (
        native_actor_catalog,
        install_native_profile_resource_pool,
    )

    policy = policy_for(fight)
    if policy is None:
        return False
    proof, _, _ = validate(
        fight.native_order_trial, encounter_id=fight.id, replay=False
    )
    actor = fight.actors[policy.owner_id]
    morph = morph_record(fight, actor.id)
    if (
        fight.phase != "active"
        or fight.turn_id != 1
        or proof.owner_id != actor.id
        or proof.instance_id != policy.instance_id
        or morph is None
        or morph.get("profile_id") != 3217
        or actor.id not in getattr(fight, "native_class_initializations", {})
    ):
        raise ValueError(
            "Order resource constructor requires completed ordinary Ready initialization"
        )
    existing = getattr(fight, "native_order_resource_constructor", None)
    if existing is not None:
        validate_projection(fight)
        return False
    catalog = native_actor_catalog()
    source = catalog["npc_profiles"].get("3217")
    if not isinstance(source, dict):
        raise ValueError("Order resource constructor lacks its original3217 profile")
    before = {
        str(stat): dict(
            current=actor.effect_stats[stat], maximum=actor.effect_maxima[stat]
        )
        for stat in (1, 2, 3, 4)
    }
    resources = install_native_profile_resource_pool(actor, 3217, 1, catalog=catalog)
    fight.native_order_resource_constructor = dict(
        schema=SCHEMA,
        owner_id=actor.id,
        encounter_id=fight.id,
        map_id=policy.map_id,
        instance_id=policy.instance_id,
        reference=3217,
        level=1,
        profile_sha256=_digest(source),
        resources=resources,
        before=before,
        initial_wound=resources["1"]["maximum"] - resources["1"]["current"],
        authority="reviewed controlled-form join using original bbo/ffx resource constructor",
    )
    return True


def validate_projection(fight):
    from .native_order_trial_encounter import policy_for
    from .combat_actor_snapshot import native_actor_catalog, native_npc_creation_values

    row = getattr(fight, "native_order_resource_constructor", None)
    if row is None:
        return None
    policy = policy_for(fight)
    catalog = native_actor_catalog()
    native = native_npc_creation_values(3217, 1, catalog=catalog)
    if (
        policy is None
        or not isinstance(row, dict)
        or row.get("schema") != SCHEMA
        or (
            row.get("owner_id"),
            row.get("encounter_id"),
            row.get("map_id"),
            row.get("instance_id"),
        )
        != (policy.owner_id, fight.id, policy.map_id, policy.instance_id)
        or row.get("reference") != 3217
        or row.get("level") != 1
        or row.get("profile_sha256") != _digest(catalog["npc_profiles"]["3217"])
        or row.get("resources") != {str(stat): native[stat] for stat in (1, 2, 3, 4)}
        or row.get("initial_wound") != native[1]["maximum"] - native[1]["current"]
    ):
        raise ValueError("Order resource constructor source changed")
    return row
