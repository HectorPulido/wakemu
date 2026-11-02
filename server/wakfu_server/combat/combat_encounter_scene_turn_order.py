"""Source-sealed ordering for declared native queued phase transitions."""
from functools import lru_cache
from hashlib import sha256
import json

_FIELDS = frozenset(
    (
        "target_references",
        "constructor_state",
        "event_ids",
        "source_effect_chain",
        "authority",
        "source_sha256",
    )
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def native_order_source_digest(rule):
    """Prove regeneration -> queued spell -> state -> owned-END causality."""
    from .combat_npc_attack import npc_runtime_catalog, npc_spell_catalog
    from .combat_retained_runtime import native_retained_metadata
    from .spell_audit import states_catalog

    if type(rule) is not dict or set(rule) - _FIELDS:
        raise ValueError("Malformed declared native turn ordering")
    refs, state, chain = (
        rule.get(k)
        for k in ("target_references", "constructor_state", "source_effect_chain")
    )
    if (
        type(refs) is not list
        or not refs
        or any(type(v) is not int or v <= 0 for v in refs)
        or refs != sorted(set(refs))
        or type(state) is not int
        or state <= 0
        or rule.get("event_ids") != [1037, 1002]
        or type(chain) is not list
        or len(chain) != 4
        or any(type(v) is not int or v <= 0 for v in chain)
        or type(rule.get("authority")) is not str
        or not rule["authority"].strip()
    ):
        raise ValueError("Missing reviewed native turn ordering authority")
    runtime = npc_runtime_catalog()
    effects = runtime.source_effects
    rows = [effects[str(ref)] for ref in chain]
    first, queued, applied, last = rows
    metadata = native_retained_metadata()["effects"]
    states = states_catalog()["states"]
    queue_parameters, state_parameters = queued.get("parameters"), applied.get(
        "parameters"
    )
    if (
        first.get("effect_class") != 330
        or queued.get("effect_class") != 426
        or applied.get("effect_class") != 304
        or last.get("effect_class") != 330
        or chain[1] not in first.get("children", ())
        or chain[0] not in states[str(state)].get("effect_ids", ())
        or not isinstance(queue_parameters, list)
        or len(queue_parameters) != 2
        or queue_parameters[1] != 0
        or not isinstance(state_parameters, list)
        or len(state_parameters) < 2
        or state_parameters[1] != 0
    ):
        raise ValueError("Declared turn ordering lost its native phase chain")
    spell_id, next_state = int(queue_parameters[0]), int(state_parameters[0])
    if queue_parameters[0] != spell_id or state_parameters[0] != next_state:
        raise ValueError("Phase chain requires exact native references")
    spell = npc_spell_catalog()["spells"][str(spell_id)]
    roots = set(spell.get("level_zero_roots", ()))
    for level in spell.get("levels", ()):
        roots.update(level[2])
    if chain[2] not in roots or chain[3] not in states[str(next_state)]["effect_ids"]:
        raise ValueError("Queued transition does not own the declared END listener")
    for ref, row, event in ((chain[0], first, 1037), (chain[3], last, 1002)):
        native = metadata[str(ref)]
        masks = row.get("target_masks")
        if (
            not isinstance(masks, list)
            or len(masks) != 7
            or event not in (masks[5] or ())
            or native.get("subscription") is not True
            or native.get("event_global_subscription") is not False
            or native.get("event_reverse_subscription") is not True
            or native.get("event_caster_code") != 2
            or native.get("event_target_code") != 2
            or row.get("native_target_selector") != {"class": "fcE", "mask": 1}
        ):
            raise ValueError("Phase ordering requires actual owned SELF subscriptions")
    document = dict(
        chain=dict(zip(map(str, chain), rows)),
        spell=spell,
        constructor_state=states[str(state)],
        next_state=states[str(next_state)],
        metadata={str(ref): metadata[str(ref)] for ref in (chain[0], chain[3])},
    )
    return sha256(_canonical(document).encode()).hexdigest()


@lru_cache(maxsize=32)
def _qualified_rule(encoded):
    rule = json.loads(encoded)
    if set(rule) != _FIELDS or rule.get("source_sha256") != native_order_source_digest(
        rule
    ):
        raise ValueError("Declared phase ordering source changed")
    return (
        tuple(rule["target_references"]),
        rule["constructor_state"],
        tuple(rule["event_ids"]),
    )


def validate_declared_turn_order(rule):
    """Admission can fail before any participant or effect publication."""
    return _qualified_rule(_canonical(rule))


def declared_turn_end_order(fight, *, actor_id):
    """Return an opt-in order only for an actual owned constructor recipient."""
    from .combat_encounter_scene_policy import frozen_scene

    scene = frozen_scene(fight)
    if scene is None or scene.get("turn_end_order") is None:
        return None
    refs, state, events = validate_declared_turn_order(scene["turn_end_order"])
    actor = fight.actors.get(actor_id)
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor_id, {})
    if actor is None or actor.controlled or receipt.get("ref") not in refs:
        return None
    if (
        fight.phase != "active"
        or fight.current is not actor
        or getattr(actor, "native_summon_source", None) is not None
        or receipt.get("initialized") is not True
        or not any(
            row.get("state_id") == state for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Declared phase ordering lacks its actual owned constructor")
    return events
