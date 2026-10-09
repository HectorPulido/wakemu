"""Execute native parent spell trees for mechanic-only summon reaction audits.

This entry point does not attest cast permission, spend resources, or send
packets. The ordinary request transaction remains responsible for those steps.
It preserves that transaction's ordered root dispatch and active spell scope,
instead of promoting a descendant damage runner to a standalone spell root.
"""
from wakfu_server.combat_active_spell import active_spell_scope
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_native_spell_casting import catalog


def execute_native_parent_roots(
    fight,
    runtime_factory,
    *,
    spell_id,
    level,
    caster_id,
    cell,
    observe_factory=None,
):
    """Run an actual cell-targeted parent tree on the caller's isolated fight.

    Native cell requests supply no explicit PV, even when a fighter occupies
    the cell. The shared resolver selects targets and inherited group geometry.
    A failing parent leaves this isolated preview available for diagnostic
    traces; callers must discard it rather than commit a partial audit.
    """
    if (
        type(spell_id) is not int
        or type(level) is not int
        or level < 1
        or type(caster_id) is not int
        or caster_id not in fight.actors
    ):
        raise ValueError("Missing actual native parent spell/caster")
    if (
        not isinstance(cell, tuple)
        or len(cell) != 3
        or any(type(value) is not int for value in cell)
    ):
        raise ValueError("Missing exact native parent target cell")
    record = catalog().get(str(spell_id))
    if record is None or level > len(record["levels"]):
        raise ValueError("Native parent spell level unavailable")
    # definition() resolves conditional costs/range, but returns this same
    # level's roots unconditionally. We select no cost/range branch here.
    roots = tuple(record["levels"][level - 1][2])
    if any(type(reference) is not int for reference in roots):
        raise ValueError("Malformed native parent root sequence")
    factory = observe_factory(runtime_factory) if observe_factory else runtime_factory
    dispatcher, packets = factory(
        fight, dict(spell_id=spell_id, evaluation_level=level)
    )
    if not isinstance(dispatcher, EffectDispatcher) or not isinstance(packets, list):
        raise ValueError("Missing shared native parent effect runtime")
    with active_spell_scope(fight, spell_id, level=level), fight.effect_resolution():
        outcomes = tuple(
            dispatcher.execute(
                EffectInvocation(reference, level, caster_id, None, cell)
            )
            for reference in roots
        )
    return dict(
        roots=roots,
        outcomes=outcomes,
        packets=tuple(packets),
        scope="native_parent_roots_without_cast_permission",
    )
