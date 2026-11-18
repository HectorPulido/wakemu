"""Scoped native5622 candidate over unchanged published catalog components.

The fixture overlays only two original roots and their original casting/cost
records. It does not rebuild the unrelated combat inventory or mutate runtime
publication. A production release must publish the matching derived documents.
"""

from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
from unittest.mock import patch


@contextmanager
def school_spell_domain(*, runtime=True):
    from wakfu_server import native_catalog, spells, spell_audit
    from wakfu_server import combat_common_spell_catalog as common
    from wakfu_server import combat_server_spell as server
    from wakfu_server import combat_npc_attack
    from wakfu_server import combat_spells, combat_casting_context
    from wakfu_server import combat_conditional_costs, combat_event_costs

    original_load = native_catalog.load
    original_book = spell_audit.catalog()
    if runtime:
        original_compiled = server.compiled_runtime_catalog()
        original_npc_compiled = combat_npc_attack.npc_runtime_catalog()
        original_roots = combat_casting_context.casting_root_catalog()
    root = Path(__file__).resolve().parents[2] / "database" / "protocol"
    names = {
        "native-common-spell-effect-trees.json",
        "native-common-spell-casting-roots.json",
    }

    def candidate_source(path):
        path = Path(path)
        return (
            json.loads((root / path.name).read_text())
            if path.name in names
            else original_load(path)
        )

    caches = (
        common.effects,
        common.casting_roots,
        spells.published_item_spell_references,
        combat_conditional_costs.native_catalog,
        combat_event_costs.cost_catalog,
    )
    for cached in caches:
        cached.cache_clear()
    try:
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(native_catalog, "load", side_effect=candidate_source)
            )
            document = common.effects()
            book = common.merge_effect_catalog(original_book)
            costs = common.merge_cost_records(combat_spells._COSTS)
            if runtime:
                roots = dict(
                    original_roots,
                    roots=dict(
                        original_roots["roots"], **common.casting_roots()["roots"]
                    ),
                )
                compiled = original_compiled.with_effect_sources(document["effects"])
                npc_compiled = original_npc_compiled.with_effect_sources(
                    document["effects"]
                )
                stack.enter_context(
                    patch.object(
                        combat_npc_attack,
                        "npc_runtime_catalog",
                        return_value=npc_compiled,
                    )
                )
            stack.enter_context(patch.object(spell_audit, "catalog", return_value=book))
            stack.enter_context(patch.object(server, "catalog", return_value=book))
            if runtime:
                stack.enter_context(
                    patch.object(
                        server, "compiled_runtime_catalog", return_value=compiled
                    )
                )
                stack.enter_context(patch.object(combat_spells, "_COSTS", costs))
                stack.enter_context(
                    patch.object(
                        combat_casting_context,
                        "casting_root_catalog",
                        return_value=roots,
                    )
                )
            yield document
    finally:
        for cached in caches:
            cached.cache_clear()
