"""Audit executable effect closure for internally triggered native spell tables.

Casting-table presence alone does not establish that executable effect trees
were imported. Policy/retained metadata rows are not effect definitions.
"""
from pathlib import Path
import sys
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.combat_operation_registry import dependency_specs
from combat_operation_sources import operation_source_paths


def executable_effect(row):
    return (
        isinstance(row, dict)
        and type(row.get("effect_class")) is int
        and isinstance(row.get("children"), (list, tuple))
        and "native_target_selector" in row
        and isinstance(row.get("parameters"), (list, tuple))
        and type(row.get("minimum_level")) is int
        and type(row.get("maximum_level")) is int
    )


def callback_effect_closure(casting, effects, seed_spell_ids):
    """Follow all native level roots, child effects, and constant 426 links.

    No spell is added to an actor's book. This is a catalog dependency audit;
    it does not infer callback conditions, resources, targets, or execution.
    """
    pending_spells = list(map(int, seed_spell_ids))
    pending_effects = []
    spell_ids, effect_ids, missing_spells, missing_effects = set(), set(), set(), set()
    dynamic_callbacks = set()
    while pending_spells or pending_effects:
        while pending_spells:
            identity = pending_spells.pop()
            if identity in spell_ids:
                continue
            spell_ids.add(identity)
            spell = casting.get(str(identity))
            if not isinstance(spell, dict) or not isinstance(
                spell.get("levels"), (list, tuple)
            ):
                missing_spells.add(identity)
                continue
            for level in spell["levels"]:
                if not isinstance(level, (list, tuple)) or len(level) != 3:
                    raise ValueError("Malformed native casting level roots")
                pending_effects.extend(level[2])
            pending_effects.extend(spell.get("level_zero_roots", ()))
        if not pending_effects:
            continue
        identity = pending_effects.pop()
        if type(identity) is not int or identity <= 0:
            raise ValueError("Invalid native effect root identity")
        if identity in effect_ids:
            continue
        effect_ids.add(identity)
        effect = effects.get(str(identity))
        if not executable_effect(effect):
            missing_effects.add(identity)
            continue
        pending_effects.extend(effect["children"])
        if effect["effect_class"] == 426:
            spec = next(spec for spec in dependency_specs(426) if spec.kind == "spell")
            raw = effect["parameters"]
            index = 2 * spec.parameter_index
            if len(raw) < index + 2:
                raise ValueError("Incomplete native callback spell parameters")
            if raw[index + 1] != 0:
                dynamic_callbacks.add(identity)
            elif raw[index] > 0 and int(raw[index]) == raw[index]:
                pending_spells.append(int(raw[index]))
    return dict(
        operation_sources_sha256={
            str(path.relative_to(Path(__file__).resolve().parents[2])): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in operation_source_paths()
        },
        spell_ids=sorted(spell_ids),
        effect_ids=sorted(effect_ids),
        missing_casting_ids=sorted(missing_spells),
        missing_effect_ids=sorted(missing_effects),
        dynamic_callback_effect_ids=sorted(dynamic_callbacks),
    )


def validate_additions(existing, additions, casting, seed_spell_ids):
    """Require exact additive definitions and complete seeded callback closure."""
    if set(existing) & set(additions):
        raise ValueError("Callback recovery must not replace an existing effect")
    if any(not executable_effect(row) for row in additions.values()):
        raise ValueError("Callback recovery requires full executable definitions")
    result = callback_effect_closure(casting, {**existing, **additions}, seed_spell_ids)
    if (
        result["missing_casting_ids"]
        or result["missing_effect_ids"]
        or result["dynamic_callback_effect_ids"]
    ):
        raise ValueError("Incomplete native callback effect closure: " + str(result))
    return result
