"""Explicit server renewal policy for finite, turn-clock aptitude listeners.

Installed content.33.165201 specifies a point-scaled number of reductions per
turn. Native eZR.bbj supplies the count and the child constructor supplies its
target-clock window. No original server renewal caller has been recovered.
Renewal constructs the same owned listener after its removal; it emits no
fabricated external event and never resets a still-live listener's budget.
"""
from copy import deepcopy

from .combat_effect_dispatch import EffectInvocation
from .combat_conditions import evaluate_condition


def _source_effects():
    from .combat_aptitude_initialization import effect_catalog

    return effect_catalog()["effects"]


def _validate_recipe(state, invocation, container, root):
    if (
        invocation.caster_id != invocation.target_id
        or invocation.state_uid is not None
        or container.get("native_kind") != "aptitude"
        or container.get("type") != 36
        or not any(
            item[2] == root
            and item[3] == container.get("id")
            and item[1] == invocation.level
            for item in state.get("aptitudes", ())
        )
    ):
        raise ValueError("Periodic aptitude recipe lost its owned source")
    effects = _source_effects()
    pending, seen = [root], set()
    while pending:
        reference = pending.pop()
        if reference in seen:
            continue
        seen.add(reference)
        effect = effects.get(str(reference))
        if effect is None:
            raise ValueError("Periodic aptitude closure is incomplete")
        pending.extend(effect["children"])
    if invocation.reference not in seen:
        raise ValueError("Periodic aptitude listener is outside its original closure")


def remember_periodic_aptitude(fight, row, effect, definition):
    container = row.get("native_retained_container")
    timing = effect.get("native_timing_definition", {})
    invocation = row["invocation"]
    if (
        not isinstance(container, dict)
        or container.get("native_kind") != "aptitude"
        or container.get("type") != 36
        or definition.get("subscription") is not True
        or definition.get("event_execution_count", -1) < 0
        or not definition.get("event_execution_count_per_level")
        or timing.get("ryE") != 1
        or timing.get("ryF") != 0
        or timing.get("clock_on_target") is not True
        or timing.get("clock_on_caster") is not False
        or invocation["caster_id"] != invocation["target_id"]
        or invocation["state_uid"] is not None
    ):
        return
    identity = invocation["target_id"]
    state = fight.native_class_initializations.get(identity)
    timer = row.get("timer")
    allocation = (
        None
        if state is None
        else next(
            (
                item
                for item in state.get("aptitudes", ())
                if item[3] == container.get("id") and item[1] == invocation["level"]
            ),
            None,
        )
    )
    if (
        state is None
        or not isinstance(timer, dict)
        or timer.get("actor_id") != identity
        or allocation is None
    ):
        raise ValueError("Periodic aptitude lacks its owned initialization source")
    key = str(invocation["reference"])
    recipes = state.setdefault("aptitude_periodic_recipes", {})
    recipe = {
        "invocation": deepcopy(invocation),
        "container": deepcopy(container),
        "root_reference": allocation[2],
    }
    _validate_recipe(state, EffectInvocation(**invocation), container, allocation[2])
    previous = recipes.get(key)
    if previous is not None:
        for field in ("reference", "level", "caster_id", "target_id"):
            if previous["invocation"][field] != invocation[field]:
                raise ValueError("Periodic aptitude constructor identity changed")
        if previous["container"] != container:
            raise ValueError("Periodic aptitude container changed")
    else:
        recipes[key] = recipe


def renew_periodic_aptitudes(dispatcher, *, actor_id):
    fight = dispatcher.native_retention.fight
    if fight.current is None or fight.current.id != actor_id or fight.phase != "active":
        raise ValueError("Periodic aptitude renewal requires the actual owner turn")
    state = fight.native_class_initializations.get(actor_id)
    if state is None or not state.get("aptitude_periodic_recipes"):
        return ()
    if state.get("aptitude_periodic_turn") == fight.turn_id:
        return ()
    outcomes = []
    for recipe in tuple(state["aptitude_periodic_recipes"].values()):
        original = recipe["invocation"]
        _validate_recipe(
            state,
            EffectInvocation(**original),
            recipe["container"],
            recipe["root_reference"],
        )
        invocation = dict(
            original,
            cell=fight.actors[actor_id].position,
            base_uid=None,
            native_running_uid=None,
            native_value_scope=None,
            native_retained_container=deepcopy(recipe["container"]),
        )
        parent = EffectInvocation(
            **dict(invocation, reference=recipe["root_reference"])
        )
        definition = dispatcher.effects.get(str(parent.reference))
        if definition is None:
            raise ValueError("Periodic aptitude lost its original root definition")
        if not evaluate_condition(
            definition["criteria"], dispatcher.condition_context(parent)
        ):
            continue
        # Expiration precedes the production turn-start provider. A surviving
        # listener retains its budget; no second copy can be installed.
        if any(
            row["invocation"]["reference"] == original["reference"]
            and row["invocation"]["target_id"] == actor_id
            and row.get("native_retained_container") == recipe["container"]
            for row in fight.native_owned_group_effects.values()
        ):
            continue
        outcomes.append(dispatcher.execute(EffectInvocation(**invocation)))
    state["aptitude_periodic_turn"] = fight.turn_id
    return tuple(outcomes)
