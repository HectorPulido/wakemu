"""Exact eYZ inputs and explicit Wakemu server-triggered execution policy.

The shipped eGj.a(int,aBn,boolean) implementation is empty. This module
models its arguments. Runtime execution below is a declared server policy,
not a reconstruction of an unavailable original server implementation.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar

from .combat_parameters import _float32, parameter_value


def triggered_spell_owner_flags(parameters):
    """eYZ.bbA/bbB compare raw So(1), never its evaluated level value."""
    if len(parameters) % 2:
        raise ValueError("Incomplete native eYZ parameter pairs")
    cell_mode = len(parameters) >= 4 and _float32(parameters[2]) == 1
    return not cell_mode, cell_mode


@dataclass(frozen=True)
class NativeTriggeredSpellRequest:
    spell_id: int
    caster_id: int
    cell: tuple[int, int, int]
    native_rhe: bool


def native_triggered_spell_request(
    parameters, level, *, caster_id, target_cell, caster_is_native_fighter
):
    """Model C then c, after the caller's exact Qe guards and timing.

    target_cell must be the actual target PV coordinates when a PV is bound,
    otherwise bbd(). No target selection or coordinates are inferred here.
    None represents native mu(true) for a non-eGj caster, not spell success.
    """
    if len(parameters) % 2:
        raise ValueError("Incomplete native eYZ parameter pairs")
    spell_id = parameter_value(parameters, 0, 1)
    native_rhe = len(parameters) < 6 or parameter_value(parameters, 2, level) == 1
    if type(caster_is_native_fighter) is not bool:
        raise ValueError("Missing native eYZ caster type authority")
    if not caster_is_native_fighter:
        return None
    if type(caster_id) is not int:
        raise ValueError("Missing actual eYZ caster identity")
    cell = tuple(target_cell)
    if len(cell) != 3 or any(type(value) is not int for value in cell):
        raise ValueError("Missing actual eYZ target coordinates")
    if not -32768 <= cell[2] <= 32767:
        raise ValueError("Native eYZ target height must be a signed short")
    return NativeTriggeredSpellRequest(spell_id, caster_id, cell, native_rhe)


def execute_native_triggered_spell(request, *, server_executor=None):
    """Keep the missing server producer explicit; never accept a silent no-op."""
    if not isinstance(request, NativeTriggeredSpellRequest):
        raise ValueError("Missing native triggered spell request")
    if server_executor is None:
        raise ValueError("Missing source-proven native triggered spell server executor")
    return server_executor(request)


_trigger_stack = ContextVar("wakemu_triggered_spell_stack", default=())


@contextmanager
def triggered_spell_scope(request):
    """Explicit server policy: reject recursive cycles or depth beyond 32."""
    key = (request.caster_id, request.spell_id)
    stack = _trigger_stack.get()
    if key in stack or len(stack) >= 32:
        raise ValueError("Wakemu triggered-spell recursion policy rejected cycle/depth")
    token = _trigger_stack.set(stack + (key,))
    try:
        yield
    finally:
        _trigger_stack.reset(token)


@dataclass(frozen=True)
class InternalTriggeredAbility:
    """Declared dependency policy over an actual eYZ and native fyF table."""

    effect_reference: int
    spell_reference: int
    maximum_level: int

    def __post_init__(self):
        if any(
            type(v) is not int or v <= 0
            for v in (self.effect_reference, self.spell_reference, self.maximum_level)
        ):
            raise ValueError("Missing actual internal-triggered ability descriptor")


def triggered_spell_level(request, authority, internal_ability=None):
    """Bind actual owned book level and native ability table without user gates."""
    from .combat_spell_level import NativeSpellBook

    book = authority.native_spellbook
    if not isinstance(book, NativeSpellBook):
        raise ValueError("Missing actual triggered-spell owned ability book")
    level = book.level(request.spell_id)
    if level == 0 and isinstance(internal_ability, InternalTriggeredAbility):
        if internal_ability.spell_reference != request.spell_id:
            raise ValueError(
                "Internal triggered ability descriptor differs from request"
            )
        actual_level = authority.native_real_level
        if type(actual_level) is not int or not 0 < actual_level <= 32767:
            raise ValueError("Missing actual internal-triggered caster level")
        # Explicit Wakemu helper-ability policy: the source caster level is
        # capped by the actual fyF maximum. No parent runner level is borrowed.
        level = min(actual_level, internal_ability.maximum_level)
    if type(level) is not int or level <= 0:
        raise ValueError(
            "Triggered internal spell lacks an actual owned level descriptor"
        )
    return level


def triggered_spell_plan(
    request, *, actor, authority, condition, definition, internal_ability=None
):
    level = triggered_spell_level(request, authority, internal_ability)
    rule = definition(
        request.spell_id,
        level,
        condition,
        getattr(actor, "spell_ap_cost_modifiers", None),
        calculate_costs=request.native_rhe,
    )
    costs = rule["costs"] if request.native_rhe else dict(ap=0, mp=0, wp=0)
    if not isinstance(costs, dict) or any(
        type(costs.get(k)) is not int or costs[k] < 0 for k in ("ap", "mp", "wp")
    ):
        raise ValueError("Missing actual triggered-spell resource costs")
    stats = getattr(actor, "effect_stats", None)
    if not isinstance(stats, dict) or type(stats.get(4)) is not int:
        raise ValueError("Missing actual triggered-spell WP snapshot")
    for name, stat in (("ap", 2), ("mp", 3)):
        if type(stats.get(stat)) is not int or stats[stat] != getattr(actor, name):
            raise ValueError("Triggered-spell resource snapshot mismatch")
    if actor.ap < costs["ap"] or actor.mp < costs["mp"] or stats[4] < costs["wp"]:
        raise ValueError("Insufficient triggered-spell resources")
    from .combat_spell_resource_costs import extra_costs, validate_extra_resources

    costs["extra_resource_deltas"] = extra_costs(
        costs.get("extra_resource_values", {}), actor
    )
    validate_extra_resources(actor, costs["extra_resource_deltas"])
    return dict(
        actor_id=actor.id,
        spell_id=request.spell_id,
        spell_uid=request.spell_id,
        evaluation_level=level,
        target=request.cell,
        effect_ids=tuple(rule["roots"]),
        costs=costs,
        native_triggered_spell_policy="wakemu.eYZ.owned-ability-v1",
    )


def consume_triggered_costs(actor, plan, *, fight=None):
    from .combat_spell_resource_costs import pay_extra_resources

    plan["extra_resource_payment"] = pay_extra_resources(
        actor, plan["costs"]["extra_resource_deltas"], fight=fight
    )
    if getattr(actor, "effect_resource_raw_currents", None) is not None:
        if fight is None or fight.actors.get(actor.id) is not actor:
            raise ValueError("Missing actual triggered PA cost fight")
        from .combat_resource_pa_notifications import shift_resource_current

        for name, stat in (("ap", 2), ("mp", 3)):
            shift_resource_current(
                fight, actor, stat, plan["costs"][name], subtract=True
            )
        actor.effect_stats[4] -= plan["costs"]["wp"]
        return
    for name, stat in (("ap", 2), ("mp", 3)):
        setattr(actor, name, getattr(actor, name) - plan["costs"][name])
        actor.effect_stats[stat] = getattr(actor, name)
    actor.effect_stats[4] -= plan["costs"]["wp"]
