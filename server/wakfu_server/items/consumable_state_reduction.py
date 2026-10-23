"""Descriptor-attested native eZi321 reduction of a retained world state."""
from psycopg.types.json import Jsonb


def reduce_states(store, db, character_id, reductions, *, generation):
    """Preserve the existing clock and canonical owner across level reduction."""
    from .consumable_buffs import active_states

    if not isinstance(reductions, (list, tuple)):
        raise ValueError("Invalid native retained-state reductions")
    states = {
        state["state_id"]: state
        for state in active_states(store, db, character_id, generation=generation)
    }
    for reduction in reductions:
        if not isinstance(reduction, dict):
            raise ValueError("Invalid native retained-state reduction")
        effect, model = reduction.get("effect", {}), reduction.get("native_state", {})
        identity, amount = reduction.get("state_id"), reduction.get("levels")
        if (
            identity != 981
            or amount != 1
            or effect.get("id") != 45983
            or effect.get("generic") != 321
            or effect.get("runner") != "eZi"
            or effect.get("values") != [981, 1]
            or effect.get("criteria")
            or effect.get("subscription") is not False
            or model.get("state_id") != identity
            or model.get("maximum_level") != 100
            or model.get("duration_ms") != 240000
        ):
            raise ValueError("Unattested native retained-state reduction")
        state = states.get(identity)
        if state is None:
            raise ValueError("El estado que elimina este consumible ya no está activo")
        if (
            state["clock"] != "online"
            or state["duration_ms"] != model["duration_ms"]
            or state["combat_id"] is not None
            or not 1 <= state["level"] <= model["maximum_level"]
        ):
            raise ValueError("Invalid retained native state ownership or clock")
        level = state["level"] - amount
        if level <= 0:
            db.execute(
                "DELETE FROM character_consumable_buffs WHERE uid=%s AND character_id=%s",
                (state["uid"], character_id),
            )
            states.pop(identity)
            continue
        roots = model.get("effect_ids_by_level", {}).get(str(level))
        definitions = model.get("native_effects")
        if (
            not isinstance(roots, list)
            or not roots
            or not isinstance(definitions, dict)
            or any(str(root) not in definitions for root in roots)
        ):
            raise ValueError("Missing native reduced-level state effect graph")
        stored = db.execute(
            "SELECT metadata FROM character_consumable_buffs WHERE uid=%s AND character_id=%s FOR UPDATE",
            (state["uid"], character_id),
        ).fetchone()
        if stored is None:
            raise ValueError("Retained native state disappeared")
        metadata = dict(stored["metadata"])
        detail = dict(metadata.get("metadata", {}))
        detail.update(
            native_effects=definitions,
            combat_only_effect_ids=[254574],
            native_state_flags=model["native_state_flags"],
        )
        metadata.update(level=level, effect_ids=roots, metadata=detail)
        # No deadline, online anchor or remaining-time column is renewed.
        db.execute(
            "UPDATE character_consumable_buffs SET level=%s,metadata=%s "
            "WHERE uid=%s AND character_id=%s",
            (level, Jsonb(metadata), state["uid"], character_id),
        )
        states[identity] = dict(state, level=level)
