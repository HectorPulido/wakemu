"""Compact advisory books for observed actors; never native cast authority."""

from functools import lru_cache


@lru_cache(maxsize=2048)
def allied_healing_scope(spell, level):
    """Prove direct, unconditional healing can select another ally.

    This does not certify range, LOS, immunity, or a legal current cast.
    Nested state/group healing and zero-range allied area casts remain unknown
    until their routing and area geometry are described.
    """
    from wakfu_server.combat_native_spell_casting import native_casting_table
    from wakfu_server.combat_npc_attack import npc_runtime_catalog
    from wakfu_server.combat_damage_healing import HEAL_ELEMENTS
    from wakfu_server.combat_effect_targets import native_selector_policy

    try:
        table, index = native_casting_table(spell, level)
        compiled = npc_runtime_catalog()
        roots = table["levels"][index][2]
        supported = []
        self_healing = False
        for reference in roots:
            effect = compiled.effects.get(str(reference), {})
            if effect.get("effect_class") not in HEAL_ELEMENTS or effect.get(
                "criteria"
            ):
                continue
            policy = native_selector_policy(effect)
            if "ally" in policy["relations"] and table["levels"][index][1] > 0:
                supported.append(reference)
                self_healing = self_healing or (
                    "self" in policy["relations"] and bool(table.get("allow_self"))
                )
        if supported:
            return dict(
                allyTarget=True,
                selfTarget=self_healing,
                allyTargetEvidence=dict(
                    basis="native_direct_heal_recipient_relation",
                    effectIds=supported,
                    castLegalityVerified=False,
                ),
            )
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return {}


def actor_repertoires(oracle, fight, actors, *, source_state, capabilities):
    from .actor_casting_metadata import selected_cost_metadata

    result = {}
    ownership = getattr(oracle, "owned_spells", None)

    def owned_books():
        for actor in actors:
            if actor["hp"] <= 0:
                continue
            record = dict(
                actorId=actor["id"],
                sourceState=source_state,
                stateRevision=fight.sequence,
                spells=[],
                unknownDependencies=[],
            )
            result[str(actor["id"])] = record
            if not callable(ownership):
                record["unknownDependencies"].append("missing_owned_spell_provider")
                continue
            try:
                owned = ownership(fight, actor["id"])
            except (KeyError, TypeError, ValueError):
                record["unknownDependencies"].append("owned_spell_metadata_unavailable")
                continue
            yield actor, record, owned

    books = owned_books()
    prepare = getattr(capabilities, "prepare", None)
    if callable(prepare):
        books = list(books)
        pairs = tuple(
            (spell, level)
            for _, _, owned in books
            for spell, level in sorted(owned.items())
        )
        if pairs:
            prepare(pairs)
    for actor, record, owned in books:
        for spell, level in sorted(owned.items()):
            hint = capabilities(spell, level)
            if isinstance(hint, dict) and "heal" in hint.get("tags", ()):
                hint = dict(hint, **allied_healing_scope(spell, level))
            entry = dict(
                spellId=spell,
                level=level,
                advisoryCapabilities=hint,
                costOptions=[],
                conditionalCosts=False,
                costBasis="native_table_before_actor_modifiers",
                costUncertainties=[
                    "actor_cost_modifiers_and_extra_resources_unresolved"
                ],
            )
            record["spells"].append(entry)
            try:
                metadata = selected_cost_metadata(spell, level)
                options = metadata.options
                if any(
                    len(values) < 3
                    or any(type(value) is not int for value in values[:3])
                    for values in options
                ):
                    raise ValueError("Incomplete native cost metadata")
                from wakfu_server.combat_casting_range import int32

                native_actor = fight.actors.get(actor["id"])
                modifiers = getattr(native_actor, "spell_ap_cost_modifiers", None)
                categories = metadata.categories
                known_modifiers = not categories or (
                    isinstance(modifiers, dict)
                    and all(
                        type(k) is int and type(v) is int for k, v in modifiers.items()
                    )
                )
                if known_modifiers:
                    adjustment = (
                        int32(
                            sum(modifiers.get(category, 0) for category in categories)
                        )
                        if categories
                        else 0
                    )
                    options = [
                        [
                            max(0, int32(values[0] + adjustment)),
                            max(0, values[1]),
                            max(0, values[2]),
                        ]
                        for values in options
                    ]
                    entry["costBasis"] = "native_table_with_current_ap_modifiers"
                    entry["costUncertainties"] = ["extra_resource_costs_unresolved"]
                entry["costOptions"] = [
                    dict(ap=ap, mp=mp, wp=wp)
                    for ap, mp, wp in sorted({tuple(values[:3]) for values in options})
                ]
                entry["conditionalCosts"] = metadata.conditional
            except (KeyError, IndexError, TypeError, ValueError):
                entry["costUncertainties"].append("missing_native_cost_table")
    return result
