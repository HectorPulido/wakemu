"""Construct the declared native ball form's battle-local resource pool.

The original933 effect owns its spellbook. This reviewed controlled-form join
uses the existing native bbo/ffx constructor after ordinary Ready initialization.
"""
from hashlib import sha256
import json

SCHEMA = "owned-native-ball-resource-constructor-v1"
FIELD = "native_ball_resource_constructor"


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _scope(fight):
    from .combat_scene_ball_goals import _scene

    scene, selected = _scene(fight)
    if scene is None:
        return None
    receipt = getattr(fight, "native_controlled_scene_state_receipt", None)
    if not isinstance(receipt, dict) or receipt.get("scene_sha256") != scene["sha256"]:
        raise ValueError(
            "Ball resources require their actual controlled-state publisher"
        )
    actor = fight.actors.get(receipt.get("actor_id"))
    if (
        actor is None
        or actor.controlled is not True
        or receipt.get("programs") != scene["descriptor"]["controlled_state_programs"]
    ):
        raise ValueError("Ball resources lost their original controlled owner")
    return scene, selected, actor


def project(fight, *, catalog=None):
    from .combat_actor_snapshot import (
        native_actor_catalog,
        install_native_profile_resource_pool,
    )
    from .combat_morph_spellbook import morph_record

    scope = _scope(fight)
    if scope is None:
        return False
    scene, selected, actor = scope
    morph = morph_record(fight, actor.id)
    reference = selected["player_form_reference"]
    if (
        fight.phase != "active"
        or fight.turn_id != 1
        or actor.id not in getattr(fight, "native_class_initializations", {})
        or morph is None
        or morph.get("profile_id") != reference
    ):
        raise ValueError(
            "Ball resources require completed ordinary Ready and original933 form"
        )
    if getattr(fight, FIELD, None) is not None:
        validate_projection(fight, catalog=catalog)
        return False
    catalog = native_actor_catalog() if catalog is None else catalog
    source = catalog["npc_profiles"].get(str(reference))
    if not isinstance(source, dict) or type(source.get("base_level")) is not int:
        raise ValueError("Ball resources lack their original native form profile")
    level = source["base_level"]
    before = {
        str(stat): dict(
            current=actor.effect_stats[stat], maximum=actor.effect_maxima[stat]
        )
        for stat in (1, 2, 3, 4)
    }
    resources = install_native_profile_resource_pool(
        actor, reference, level, catalog=catalog
    )
    setattr(
        fight,
        FIELD,
        dict(
            schema=SCHEMA,
            owner_id=actor.id,
            encounter_id=fight.id,
            instance_id=scene["scope"]["instance_id"],
            scene_sha256=scene["sha256"],
            reference=reference,
            level=level,
            profile_sha256=_digest(source),
            resources=resources,
            before=before,
            initial_wound=resources["1"]["maximum"] - resources["1"]["current"],
        ),
    )
    return True


def validate_projection(fight, *, catalog=None):
    from .combat_actor_snapshot import native_actor_catalog, native_npc_creation_values

    row = getattr(fight, FIELD, None)
    if row is None:
        return None
    scope = _scope(fight)
    if scope is None:
        raise ValueError("Ball resource receipt lost its admitted scene")
    scene, selected, actor = scope
    catalog = native_actor_catalog() if catalog is None else catalog
    reference = selected["player_form_reference"]
    source = catalog["npc_profiles"].get(str(reference))
    if not isinstance(source, dict):
        raise ValueError("Ball resource receipt lost its original profile")
    level = source["base_level"]
    native = native_npc_creation_values(reference, level, catalog=catalog)
    if (
        not isinstance(row, dict)
        or row.get("schema") != SCHEMA
        or (
            row.get("owner_id"),
            row.get("encounter_id"),
            row.get("instance_id"),
            row.get("scene_sha256"),
        )
        != (actor.id, fight.id, scene["scope"]["instance_id"], scene["sha256"])
        or row.get("reference") != reference
        or row.get("level") != level
        or row.get("profile_sha256") != _digest(source)
        or row.get("resources") != {str(stat): native[stat] for stat in (1, 2, 3, 4)}
        or row.get("initial_wound") != native[1]["maximum"] - native[1]["current"]
    ):
        raise ValueError("Ball resource constructor authority changed")
    return row
