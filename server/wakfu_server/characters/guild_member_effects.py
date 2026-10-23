"""Original member-effect leaves, projected from current owned guild membership.

These are guild effects, not consumable states or retained combat carriers.
Scalar/resource arithmetic is shared with the native equipment interpreter.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from types import SimpleNamespace


CRITERION = 'not GetBooleanSystemConfiguration("beta.mode")'


@lru_cache(maxsize=1)
def effects():
    document = json.loads(
        Path(__file__).with_name("native_guild_member_effects.json").read_text()
    )
    if document.get("schema_version") != 1:
        raise ValueError("Invalid native guild member effect catalog")
    result = document["effects"]
    if len(result) != 49:
        raise ValueError("Incomplete native guild member effect catalog")
    for key, node in result.items():
        if (
            str(node["id"]) != key
            or node["criteria"] != CRITERION
            or node["children"] != []
            or node["subscription"] is not False
            or node["variant"] != 0
            or node["native_metadata"]["native_target_selector"]
            != {"class": "fcE", "mask": 0}
            or node["native_metadata"]["target_masks"] != [None] * 7
            or any(value != 0 for value in node["params"][1::2])
        ):
            raise ValueError("Unsupported native guild member effect contract")
    return result


def qualified_descriptor(native, *, include_temporary=False):
    """Admit only complete member effects; activation policy owns temporary use."""
    if native.get("effect_type") != "MEMBER_EFFECT":
        return None
    identity = native["effect_parameters"]["smu"]
    if str(identity) not in effects() or (
        native["has_effect_duration"] and not include_temporary
    ):
        return None
    duration = native["effect_duration_ms"] if native["has_effect_duration"] else -1
    return dict(
        cost=native["cost"],
        learning_duration_ms=native["learning_duration_ms"],
        minimum_guild_level=native["minimum_guild_level"],
        prerequisites=[],
        native_category=native["category"],
        effect=dict(kind="member_effect", reference=identity, duration_ms=duration),
    )


def projection(character, records, now_ms, *, system_configuration=None):
    """Pure current-membership projection for reloads and owned World deltas."""
    from .guild_progression import catalog
    from wakfu_server.combat_system_conditions import (
        boolean_system_configuration,
        fresh_system_configuration,
    )

    if type(now_ms) is not int or now_ms < 0 or not isinstance(records, dict):
        raise ValueError("Invalid guild member effect snapshot")
    guild = character.get("guild_native")
    if guild is None:
        return ()
    beta = boolean_system_configuration(
        SimpleNamespace(
            native_system_configuration=(
                fresh_system_configuration()
                if system_configuration is None
                else system_configuration
            )
        ),
        "beta.mode",
    )
    if beta:
        return ()
    native = {
        row["id"]: row
        for row in catalog()["bonuses"]
        if row["effect_type"] == "MEMBER_EFFECT"
    }
    now = now_ms
    selected = []
    seen = set()
    for key, record in records.items():
        identity, activation = int(key), record.get("activated_at_ms", 0)
        if type(identity) is not int or identity in seen:
            raise ValueError("Invalid owned guild bonus identity")
        seen.add(identity)
        definition = native.get(identity)
        if definition is None:
            continue
        if record.get("active") is not True:
            continue
        if type(activation) is not int or activation < 0:
            raise ValueError("Invalid owned guild bonus activation clock")
        if activation == 0 or activation > now:
            continue
        duration = (
            definition["effect_duration_ms"]
            if definition["has_effect_duration"]
            else None
        )
        if duration is not None and activation + duration <= now:
            continue
        effect = effects().get(str(definition["effect_parameters"]["smu"]))
        if effect is None:
            raise ValueError("Missing native guild member effect")
        selected.append(
            dict(
                guild_id=guild["guildId"],
                bonus_id=identity,
                activated_at_ms=activation,
                expires_at_ms=None if duration is None else activation + duration,
                effect=deepcopy(effect),
            )
        )
    return tuple(selected)


def load_from_records(character, records, now_ms):
    """Attach a trusted current raw snapshot; never hydrate or mutate SQL."""
    character["guild_member_effects"] = projection(character, records, now_ms)
    return character


def load(db, store, character):
    """Attach the just-hydrated guild record without additional SQL or writes."""
    return load_from_records(
        character,
        character.get("guild_member_bonus_records", {}),
        int(store.now().timestamp() * 1000),
    )


def bonuses(character):
    """Return the same ordered characteristic contribution contract as equipment."""
    from wakfu_server.equipment_stats import _flat

    stats, operations, unsupported = {}, [], []
    for source in character.get("guild_member_effects", ()):
        node = source["effect"]
        if node["runner"] == "eXx":
            continue
        effect = dict(
            node,
            effect_criteria=False,
            has_triggers=False,
            target_mask=0,
            native_variant=node["variant"],
            native_active_effect=False,
            stat_limit=-1,
        )
        value = _flat(effect)
        if value is None:
            unsupported.append(dict(bonus_id=source["bonus_id"], effect_id=node["id"]))
            continue
        stat, delta = value
        stats[stat] = stats.get(stat, 0) + delta
        operations.append((stat, abs(delta), delta < 0))
    return dict(
        stats=stats,
        percentages={},
        stat_operations=tuple(operations),
        resource_kinds={},
        unsupported=unsupported,
    )


def profession_bonuses(character, profession_id):
    from wakfu_server.profession_consumable_modifiers import KINDS, effect_modifiers

    result = dict.fromkeys(KINDS.values(), 0)
    for source in character.get("guild_member_effects", ()):
        node = source["effect"]
        if node["runner"] != "eXx":
            continue
        effect = dict(node, effect_class=node["generic"], parameters=node["params"])
        values = effect_modifiers(effect, 1, profession_id, beta_mode=False)
        for kind, amount in values.items():
            result[kind] += amount
    return result


def profession_modifiers(store, db, character_id, profession_id):
    """Read only the member aggregate, without hydrating an inventory per action."""
    from wakfu_server.profession_consumable_modifiers import KINDS

    row = db.execute(
        "SELECT g.id,COALESCE(s.record,'{}'::jsonb) AS record FROM guild_members m "
        "JOIN guilds g ON g.id=m.guild_id AND g.dissolved_at IS NULL "
        "LEFT JOIN guild_service_state s ON s.guild_id=g.id AND s.service='economy' "
        "JOIN settings p ON p.name='guild_policy' "
        "WHERE m.character_id=%s AND p.value->>'enabled'='true' "
        "AND p.value->>'native_sync_enabled'='true'",
        (character_id,),
    ).fetchone()
    if row is None:
        return dict.fromkeys(KINDS.values(), 0)
    character = dict(
        guild_native=dict(guildId=row["id"]),
        guild_member_bonus_records=row["record"].get("bonuses", {}),
    )
    load(db, store, character)
    return profession_bonuses(character, profession_id)
