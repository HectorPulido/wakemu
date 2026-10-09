"""Plain, detached diagnostic facts after native casting-table selection."""
from copy import deepcopy


def casting_diagnostics(
    fight, actor, request, spell_id, level, rule, context, owner_deck
):
    selection = deepcopy(rule.get("native_casting_selection"))
    conditional = deepcopy((selection or {}).get("evaluated_rules", ()))
    states = []
    for identity, current in fight.actors.items():
        ledger = getattr(current, "state_ledger", None)
        entries = getattr(ledger, "entries", None)
        states.append(
            dict(
                actor_id=identity,
                states=None
                if entries is None
                else [
                    dict(
                        uid=entry.uid,
                        reference=entry.reference,
                        level=entry.level,
                        source_actor_id=entry.caster_id,
                        target_actor_id=entry.target_id,
                    )
                    for entry in entries
                ],
            )
        )
    caster = getattr(context, "actors", {}).get("caster")
    return dict(
        schema="native-cast-diagnostics-v1",
        fight_id=fight.id,
        caster_id=actor.id,
        spell_id=spell_id,
        evaluation_level=level,
        target_cell=list(request["target"]),
        selection=selection,
        conditional_rules=conditional,
        costs=deepcopy(rule.get("costs")),
        resolved_casting={
            key: deepcopy(rule.get(key))
            for key in (
                "minimum",
                "maximum",
                "range_modifiable",
                "line_of_sight",
                "linear",
                "diagonal",
                "linear_path",
                "path_option",
                "free_cell",
                "allow_self",
                "forbid_QI_P",
                "cast_criterion_raw",
                "categories",
            )
        },
        owner_deck=None
        if owner_deck is None
        else dict(
            active=list(owner_deck["active"]), passive=list(owner_deck["passive"])
        ),
        caster_condition_deck=None
        if getattr(caster, "deck_spell_ids", None) is None
        else sorted(caster.deck_spell_ids),
        live_range=None
        if getattr(caster, "characteristics", None) is None
        else caster.characteristics.get("RANGE"),
        carried=getattr(caster, "is_carried", None),
        caster_fight_properties=None
        if getattr(caster, "fight_properties", None) is None
        else sorted(caster.fight_properties),
        range_category_modifiers=deepcopy(
            getattr(actor, "spell_range_modifiers", None)
        ),
        actor_states=states,
    )
