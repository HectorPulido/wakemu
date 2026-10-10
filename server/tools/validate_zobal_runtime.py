"""Run Zobal and shared prior-class regressions without operating services.

Requires WAKFU_TEST_GRANTEDCAST=1 and the normal PostgreSQL test settings.
An optional complete staged catalog can be selected for this process only.
"""
import argparse
from contextlib import nullcontext
import gc, os, unittest
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--catalog-release", help="Complete staged catalog revision; never activates it"
)
args = parser.parse_args()
gc.disable()
from wakfu_server import native_catalog

modules = [
    "test_aniripsa_allied_healing_runtime",
    "test_combat_area_captured_activation",
    "test_combat_conditions",
    "test_combat_cra_beacon_reaction",
    "test_combat_effect_area_entry",
    "test_combat_effect_area_events",
    "test_combat_effect_area_queries",
    "test_combat_effect_area_targets",
    "test_combat_effect_dispatch",
    "test_combat_effect_resolver",
    "test_combat_effect_target_condition",
    "test_combat_iop_cast",
    "test_combat_osa_dragon_aoe_runtime",
    "test_combat_state_handler",
    "test_sacrier_sacrifice_pipeline",
    "test_combat_snapshot_wire",
    "test_combat_stat_handler",
    "test_combat_character_copy_runtime_book",
    "test_stage_native_copy_book_flags",
    "test_combat_zobal_mask_runtime",
    "test_combat_zobal_runtime",
    "test_combat_uginak_wauwau_lifecycle",
    "test_combat_iop_preparation_movement_runtime",
    "test_combat_aptitude_healing_runtime",
    "test_combat_resurrection_runtime",
    "test_class_passive_mechanics_audit",
]
modules += [
    "test_combat_hud_producers.NativeHudProducerTests." + name
    for name in (
        "test_zobal_acrobatism_uses_exact_range_six_empty_native_cell",
        "test_ouginak_cazador_hits_native_obstacle_at_legal_range",
        "test_ouginak_persecucion_grants_and_casts_perseguidor_on_other_obstacle",
        "test_ouginak_native_ally_gain_then_amain_consumes_resource",
        "test_ouginak_manada_form_lifecycle_uses_native_resource_and_removes_visual",
    )
]
catalog_scope = (
    patch.object(native_catalog, "release", return_value=args.catalog_release)
    if args.catalog_release
    else nullcontext()
)
with catalog_scope:
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(
        "GATE",
        result.testsRun,
        "FAIL",
        len(result.failures),
        "ERROR",
        len(result.errors),
        "SKIP",
        len(result.skipped),
        flush=True,
    )
    os._exit(0 if result.wasSuccessful() else 1)
