"""Demand-only challenger/table contexts over verified selected native PVs.

Kind attestations match the original adapter. No affiliation, ledger snapshot,
area population, spatial result or RNG value is cached or invented here.
"""
import ast
from functools import lru_cache

from .combat_conditions import ConditionActor, ConditionContext, _condition_root


@lru_cache(maxsize=512)
def challenger_table_only(criteria):
    try:
        root = _condition_root(criteria.strip())
    except ValueError:
        return False
    calls = [node for node in ast.walk(root) if isinstance(node, ast.Call)]
    if not any(
        isinstance(node.func, ast.Name) and node.func.id == "IsChallenger"
        for node in calls
    ):
        return False
    for node in calls:
        if not isinstance(node.func, ast.Name) or node.keywords:
            return False
        if node.func.id == "GetFightCurrentTableTurn":
            if node.args:
                return False
        elif node.func.id == "IsChallenger":
            if (
                len(node.args) > 1
                or node.args
                and (
                    not isinstance(node.args[0], ast.Constant)
                    or type(node.args[0].value) is not str
                    or node.args[0].value.lower() not in ("caster", "target")
                )
            ):
                return False
        else:
            return False
    return all(
        node.id in ("IsChallenger", "GetFightCurrentTableTurn")
        for node in ast.walk(root)
        if isinstance(node, ast.Name)
    )


def _selected_area(preview, identity):
    """Keep the original selected prototype, owner and lifecycle authority."""
    from .combat_state_managers import registered_area_pv

    area = registered_area_pv(preview, identity)
    if area is None:
        return None
    row = getattr(preview, "native_effect_areas", {}).get(identity)
    # Retired/scoped pointers and special null-owner environment/border PVs
    # retain the original full path rather than approximating their guards.
    if (
        not isinstance(row, dict)
        or identity in getattr(preview, "native_retired_area_managers", {})
        or row.get("owner_id") not in preview.actors
        or row.get("native_environment_source") is not None
        or row.get("native_border_source") is not None
    ):
        return None
    from .combat_area_authority import area_guards
    from .combat_area_affiliation import area_affiliation
    from .combat_effect_area_targets import native_area_targeting_bcR

    area_guards(preview, identity)
    area_affiliation(preview, row)
    native_area_targeting_bcR(row)
    return area


def challenger_condition_context(preview, effect, invocation, authority_for):
    if (
        not isinstance(effect, dict)
        or not isinstance(effect.get("criteria"), str)
        or not challenger_table_only(effect["criteria"])
        or getattr(invocation, "native_target_cell_argument", False)
        or getattr(invocation, "native_trigger_context", None) is not None
        or invocation.caster_id is None
        or invocation.target_id is None
    ):
        return None
    from .combat_native_actor_lookup import native_actor

    aliases = {}
    by_identity = {}
    for name, identity in (
        ("caster", invocation.caster_id),
        ("target", invocation.target_id),
    ):
        if identity in by_identity:
            aliases[name] = by_identity[identity]
            continue
        actor = preview.actors.get(identity)
        if actor is not None:
            authority = authority_for(actor)
            if name == "caster" and authority.native_controller_id not in (
                None,
                invocation.caster_id,
                invocation.target_id,
            ):
                return None
            affiliation = getattr(actor, "native_fight_affiliation", actor.team)
            if type(affiliation) is not int or not -128 <= affiliation < 128:
                raise ValueError("Missing native signed-byte bcM affiliation")
            selected = ConditionActor(
                actor_id=identity,
                is_challenger=authority.is_challenger,
                is_native_ehg=authority.targeting.get("is_eGj"),
            )
        else:
            if native_actor(preview, identity) is not None:
                return None  # Exact detached constructor keeps the full path.
            area = _selected_area(preview, identity)
            if area is None:
                return None
            # Exact faV alias fields in the original adapter, not a kind guess.
            selected = ConditionActor(
                actor_id=identity, is_challenger=False, is_native_ehg=True
            )
        aliases[name] = by_identity[identity] = selected
    return ConditionContext(
        aliases, fight_current_table_turn=getattr(preview, "native_table_turn", None)
    )
