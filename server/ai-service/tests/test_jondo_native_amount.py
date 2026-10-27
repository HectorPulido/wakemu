"""Staged generic native amount metadata; actual World AST arithmetic oracle."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.bridge.jondo_native_amount import (
    project_native_amount as _project_native_amount,
    advisory_area_row,
    source_binding_proof,
)
from wakfu_ai.bridge.jondo_snapshot import semantic_rows, summarize
from wakfu_ai.bridge.jondo_capabilities import project_support
from wakfu_ai.bridge.jondo_native_hp import (
    readonly_hp_projection,
    readonly_healing_projection,
)


ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".runtime/jondo-generic-percent-ai-20261025").is_dir()
)
EVIDENCE = ROOT / ".runtime/jondo-generic-percent-ai-20261025"
NEXT = ROOT / ".runtime/jondo-general-effects-next-20261026"
spec = importlib.util.spec_from_file_location(
    "world_native_amount_oracle", EVIDENCE / "pure_native_loader.py"
)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
WORLD, SOURCE_HASHES = loader.native_namespace()
GOLDENS = json.loads((EVIDENCE / "native-percent-goldens.json").read_text())
FIXTURES = json.loads((NEXT / "native-small-amount-fixtures.json").read_text())


def effect(*, family=2, parameters=None):
    return dict(
        effect_class=family,
        parameters=parameters or [30, 0, 2, 0, 4, 0],
        parameter_count=len(parameters or [30, 0, 2, 0, 4, 0]) // 2,
        variant=0,
        minimum_level=0,
        maximum_level=32767,
        probability_base=100,
        probability_per_level=0,
        children=[],
        application_flag="NONE",
        target_masks=[None] * 7,
        native_target_selector={"class": "fcE", "mask": 9},
        native_effect_flags=[4, 22, 34],
        native_localization_enabled=True,
        area_class="anD",
        area_native="point",
    )


def project_native_amount(native, level):
    return _project_native_amount(native, level, source_binding_known=True)


class NativeAmountProjectionTests(unittest.TestCase):
    def setUp(self):
        self.modules = patch.dict(
            "sys.modules",
            {
                "wakfu_server.combat_damage_parameters": SimpleNamespace(
                    damage_parameter_specification=WORLD[
                        "damage_parameter_specification"
                    ]
                ),
                "wakfu_server.combat_effect_resolver": SimpleNamespace(
                    variant_accepts=lambda row, mode: row.get("variant", 0) == 0
                ),
                "wakfu_server.combat_summon": SimpleNamespace(
                    summon_specification=lambda *args, **kwargs: None
                ),
                "wakfu_server.monsters": SimpleNamespace(reference=lambda *args: None),
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)
        registry = patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value={"effects": {}},
        )
        registry.start()
        self.addCleanup(registry.stop)

    def test_all_six_native_hp_modes_preserve_evaluated_percent_not_target_amount(self):
        for case in GOLDENS["percentCases"]:
            native = effect(parameters=case["parameters"])
            metadata = project_native_amount(native, case["level"])
            specification = WORLD["damage_parameter_specification"](
                native["parameters"], case["level"]
            )
            self.assertEqual(
                metadata["nativeBase"],
                dict(
                    version=1,
                    kind=specification["base_kind"],
                    value=specification["base"],
                    sourceBindingKnown=True,
                ),
            )
            self.assertEqual(metadata["amount"], 0)
            self.assertEqual(
                metadata["nativeCoefficientMask"], specification["coefficient_mask"]
            )
            # Reconstruct evaluated parameters, then ask the unchanged World
            # interpreter. This tests descriptor fidelity including overflow,
            # fractional outcomes and fresh simulated current/max HP changes.
            descriptor = metadata["nativeBase"]
            parameters = [
                descriptor["value"],
                0,
                metadata["nativeCoefficientMask"],
                0,
                descriptor["kind"],
                0,
            ]
            if "error" in case:
                with self.assertRaises(ValueError):
                    WORLD["interpret_damage_parameters"](
                        parameters,
                        0,
                        hp_context=case["hpContext"],
                        rng=lambda: case["rngSample"],
                        allow_signed_base=case["allowSignedBase"],
                    )
            else:
                actual = WORLD["interpret_damage_parameters"](
                    parameters,
                    0,
                    hp_context=case["hpContext"],
                    rng=lambda: case["rngSample"],
                    allow_signed_base=case["allowSignedBase"],
                )
                self.assertEqual(actual["base"], case["result"]["base"])
        self.assertEqual(len(GOLDENS["percentCases"]), 182)

    def test_heals_preserve_all_native_coefficients_flags_and_elements_fail_closed_flat(
        self,
    ):
        for family, element in (
            (25, 1),
            (259, 2),
            (253, 3),
            (258, 4),
            (251, 5),
            (1084, 6),
        ):
            for mask in range(4):
                native = effect(family=family, parameters=[100, 0, mask, 0])
                metadata = project_native_amount(native, 100)
                self.assertEqual(
                    metadata["nativeHealing"], dict(version=1, element=element)
                )
                self.assertEqual(
                    metadata["nativeBase"],
                    dict(version=1, kind=0, value=100, sourceBindingKnown=True),
                )
                self.assertEqual(metadata["nativeCoefficientMask"], mask)
                self.assertEqual(metadata["nativeDamageFlags"], [4, 22, 34])
                self.assertTrue(metadata["nativeLocalization"])
                self.assertEqual(metadata["amount"], 0)
        classic = project_native_amount(effect(parameters=[17, 0]), 1)
        self.assertEqual(classic["amount"], 17)
        self.assertNotIn("nativeHealing", classic)

    def test_actual_duna1535_target_maximum_heal_and_light_books_in_both_real_branches(
        self,
    ):
        actor = SimpleNamespace(
            id=1, team=0, effective_level=100, direction=1, position=(0, 0, 0)
        )
        fight = SimpleNamespace(actors={1: actor})
        expected = {
            "167897": (4, 30, 2, 1),
            "371791": (0, 36, 3, 6),
            "107737": (0, 24, 3, 6),
        }
        for reference, (kind, value, mask, element) in expected.items():
            native = deepcopy(FIXTURES["effects"][reference])
            before = deepcopy(native)
            compiled = SimpleNamespace(effects={reference: native})
            rows, unknown = semantic_rows(compiled, [int(reference)], 100)
            self.assertFalse(unknown, (reference, unknown))
            self.assertTrue(rows)
            support = project_support(
                compiled,
                [int(reference)],
                100,
                fight=fight,
                actor=actor,
                actors=[dict(id=1, hp=100, team=0)],
            )
            self.assertTrue(support["effects"])
            for row in (*rows, *support["effects"]):
                self.assertEqual(row["kind"], "heal")
                self.assertEqual(row["amount"], 0)
                self.assertEqual(
                    row["nativeBase"],
                    dict(version=1, kind=kind, value=value, sourceBindingKnown=True),
                )
                self.assertEqual(row["nativeCoefficientMask"], mask)
                self.assertEqual(row["nativeHealing"], dict(version=1, element=element))
                self.assertEqual(
                    row["nativeDamageFlags"], native["native_effect_flags"]
                )
            self.assertEqual(native, before)
            if reference == "167897":
                self.assertEqual({row["target"] for row in rows}, {"ally"})
                self.assertEqual(support["aimKinds"], ["ally"])
                self.assertEqual(rows[0]["nativeBase"]["value"], 30)
                self.assertNotIn("percent_hp_requires_target_context", unknown)

    def test_light_heal_descriptor_routes_to_actual_world_healing_goldens(self):
        for case in GOLDENS["lightHealingCases"]:
            native = effect(
                family=1084, parameters=[case["base"], 0, case["coefficientMask"], 0]
            )
            metadata = project_native_amount(native, 100)
            self.assertEqual(metadata["nativeHealing"]["element"], 6)
            actual = WORLD["healing_amount"](
                metadata["nativeBase"]["value"],
                metadata["nativeHealing"]["element"],
                {int(key): value for key, value in case["sourceStats"].items()},
                {int(key): value for key, value in case["targetStats"].items()},
                coefficient_mask=metadata["nativeCoefficientMask"],
                rng=lambda: case["rngSample"],
                **GOLDENS["lightHealingContext"]
            )
            self.assertEqual(actual, case["result"])
        self.assertEqual(len(GOLDENS["lightHealingCases"]), 36)

    def test_life_steal_bad_masks_and_unknown_damage_stay_explicit(self):
        for native in (
            effect(family=24),
            effect(parameters=[30, 0, 7, 0, 4, 0]),
            effect(parameters=[-1, 0]),
        ):
            with self.assertRaises(ValueError):
                project_native_amount(native, 1)
            rows, unknown = semantic_rows(
                SimpleNamespace(effects={"1": native}), [1], 1
            )
            self.assertFalse(rows)
            self.assertTrue(unknown)
            self.assertEqual(summarize(rows, unknown)["damage"], 0)
        normalized = project_native_amount(effect(parameters=[10, 0, 3, 0, 255, 0]), 1)
        self.assertEqual(
            normalized["nativeBase"],
            dict(version=1, kind=0, value=10, sourceBindingKnown=True),
        )

    def test_hp_bounds_unknown_floors_and_frozen_are_not_inferred_from_states(self):
        actor = SimpleNamespace(
            id=1,
            hp=5,
            max_hp=5,
            effect_stats={1: 5},
            effect_minima={1: 1},
            effect_maxima={1: 5},
            effect_frozen=frozenset({1}),
        )
        before = deepcopy(vars(actor))
        self.assertEqual(
            readonly_hp_projection(
                actor,
                hp_definition=dict(over_max_current=True, hard_maximum=2147483647),
            ),
            dict(
                version=1,
                minimum=1,
                frozen=True,
                rawCurrentMode="bounded",
                rawCurrent=None,
                hardMaximum=2147483647,
            ),
        )
        self.assertEqual(vars(actor), before)
        del actor.effect_minima
        self.assertIsNone(readonly_hp_projection(actor))

    def test_snapshot_all_actor_hp_floors_and_undead_use_actual_existing_authority(
        self,
    ):
        import test_jondo_bridge as bridge_tests

        producer = bridge_tests.JondoSnapshotLosTests()
        oracle, _, _ = producer.fixture()
        fight = oracle.runtime.fight
        for actor in fight.actors.values():
            actor.effect_stats[1] = actor.hp
            actor.effect_maxima[1] = actor.max_hp
            actor.effect_minima = {1: 1 if actor.id == 2 else 0}
            actor.effect_frozen = frozenset({1}) if actor.id == 2 else frozenset()
        original_factory = oracle.factory
        calls = []

        def factory(*args):
            native, adapter = original_factory(*args)
            original = adapter.actor_authority.properties

            def properties(fight, actor):
                calls.append(actor.id)
                return original(fight, actor) | ({20} if actor.id == 2 else set())

            adapter.actor_authority.properties = properties
            return native, adapter

        oracle.factory = factory
        definition = dict(
            fresh_characteristics={
                "1": dict(over_max_current=True, hard_maximum=2147483647)
            }
        )
        with patch(
            "wakfu_server.combat_character_copy_metadata.native_copy_characteristics",
            return_value=definition,
        ) as loaded:
            snapshot = producer.build(oracle, lambda *args, **kwargs: True)
        rows = {row["id"]: row for row in snapshot["board"]["actors"]}
        self.assertEqual(
            rows[2]["nativeHp"],
            dict(
                version=1,
                minimum=1,
                frozen=True,
                rawCurrentMode="bounded",
                rawCurrent=None,
                hardMaximum=2147483647,
            ),
        )
        self.assertTrue(rows[2]["nativeUndead"])
        self.assertFalse(rows[1]["nativeUndead"])
        self.assertNotIn(
            "nativeUndead", rows[4]
        )  # No living-property authority for a corpse.
        self.assertNotIn(5, rows)  # Hidden enemy remains excluded.
        self.assertEqual(loaded.call_count, 1)
        self.assertEqual(
            calls, [actor.id for actor in fight.actors.values() if actor.hp > 0]
        )
        self.assertNotIn("nativeHealingResistanceEnabled", rows[1])

    def test_raw_hp_operand_is_separate_from_effective_percent_base_and_invalid_is_unknown(
        self,
    ):
        from wakfu_server.combat_hp_raw import SOURCE

        actor = SimpleNamespace(
            id=1,
            hp=5,
            max_hp=5,
            effect_stats={1: 5},
            effect_minima={1: 0},
            effect_maxima={1: 5},
            effect_frozen=frozenset(),
            effect_hp_raw_current=10,
            native_hp_raw_current_source=SOURCE,
        )
        self.assertEqual(readonly_hp_projection(actor)["rawCurrent"], 10)
        for kind, expected in ((2, 5), (3, 0), (5, 5), (6, 0)):
            base = WORLD["interpret_damage_parameters"](
                [100, 0, 0, 0, kind, 0],
                1,
                hp_context=dict(
                    source_hp=5, source_max_hp=5, target_hp=5, target_max_hp=5
                ),
                rng=lambda: 0.5,
            )
            self.assertEqual(base["base"], expected)
        actor.native_hp_raw_current_source = "unverified"
        self.assertIsNone(readonly_hp_projection(actor))

    def test_condition_projection_reuses_actual_actor_type_world122_and_resource32_bounds(
        self,
    ):
        import test_jondo_bridge as bridge_tests

        for missing_world in (False, True):
            producer = bridge_tests.JondoSnapshotLosTests()
            oracle, _, _ = producer.fixture()
            fight = oracle.runtime.fight
            for actor in fight.actors.values():
                actor.effect_stats.update({1: actor.hp, 32: 45})
                actor.effect_maxima.update({1: actor.max_hp, 32: 1000})
                actor.effect_minima = {1: 0, 32: 0}
                actor.effect_frozen = (
                    frozenset({32}) if actor.id == 2 else frozenset({92})
                )
            projected, legacy = [], []

            def properties(fight, actor):
                legacy.append(actor.id)
                return frozenset({5}) if actor.id == 5 else frozenset()

            def projection(fight, actor):
                projected.append(actor.id)
                if missing_world:
                    raise ValueError("Optional world-property source unavailable")
                return (
                    SimpleNamespace(
                        native_actor_type=0 if actor.id == 1 else 2,
                        is_carried=actor.id == 2,
                    ),
                    frozenset({122}) if actor.id == 3 else frozenset(),
                    frozenset({5}) if actor.id == 5 else frozenset(),
                )

            oracle.factory = lambda *args: (
                SimpleNamespace(native_rail_movement_authority=object()),
                SimpleNamespace(
                    actor_authority=SimpleNamespace(
                        properties=properties, condition_projection=projection
                    )
                ),
            )
            with patch(
                "wakfu_server.combat_character_copy_metadata.native_copy_characteristics",
                return_value=dict(
                    fresh_characteristics={
                        "1": dict(over_max_current=True, hard_maximum=2147483647)
                    }
                ),
            ):
                snapshot = producer.build(oracle, lambda *args, **kwargs: True)
            rows = {row["id"]: row for row in snapshot["board"]["actors"]}
            alive = [actor.id for actor in fight.actors.values() if actor.hp > 0]
            self.assertEqual(projected, alive)
            self.assertEqual(legacy, alive if missing_world else [])
            if missing_world:
                self.assertNotIn("nativeHealingResistance", rows[1])
            else:
                self.assertTrue(
                    rows[1]["nativeHealingResistanceEnabled"]
                )  # Actual type0.
                self.assertFalse(rows[2]["nativeHealingResistanceEnabled"])
                self.assertTrue(
                    rows[3]["nativeHealingResistanceEnabled"]
                )  # Actual world122.
                self.assertEqual(
                    rows[2]["nativeHealingResistance"],
                    dict(
                        version=1, enabled=False, minimum=0, maximum=1000, frozen=True
                    ),
                )
                self.assertTrue(rows[1]["nativeVirtualHpFrozen"])
                self.assertFalse(rows[2]["nativeVirtualHpFrozen"])
                self.assertFalse(rows[1]["nativeIsCarried"])
                self.assertTrue(rows[2]["nativeIsCarried"])
        unknown = SimpleNamespace(effect_frozen=None)
        self.assertEqual(readonly_healing_projection(unknown), {})

    def test_health_geometry_hides_directional_and_global_recipients_from_old_readers(
        self,
    ):
        from wakfu_ai.bridge.jondo_area import area_projection

        for directional in (False, True):
            native = effect(parameters=[30, 0, 2, 0, 4, 0])
            if directional:
                native.update(area_class="anv", area_native="cone-3")
            native["native_target_selector"][
                "mask"
            ] = 8  # Actual global non-area selector.
            rows, unknown = semantic_rows(
                SimpleNamespace(effects={"1": native}), [1], 1
            )
            self.assertFalse(unknown)
            row = rows[0]
            self.assertEqual(row["fixedCells"], [])
            self.assertTrue(row["nativeInArea"])
            self.assertNotIn("nativeDirectionalArea", row)
            self.assertNotIn("nativeAreaCenterOnCaster", row)
            self.assertNotIn("nativeAreaUseTargetRadius", row)
            restored = advisory_area_row(row)
            self.assertIsNotNone(restored)
            self.assertFalse(restored["nativeInArea"])
            for key, value in area_projection(native).items():
                self.assertEqual(restored[key], value)
            invalid = deepcopy(row)
            invalid["nativeBase"]["version"] = 2
            self.assertIsNone(advisory_area_row(invalid))
            invalid = deepcopy(row)
            invalid["nativeHealthGeometry"]["version"] = True
            self.assertIsNone(advisory_area_row(invalid))
        native = effect(family=1084, parameters=[10, 0])
        rows, _ = semantic_rows(SimpleNamespace(effects={"1": native}), [1], 1)
        invalid = deepcopy(rows[0])
        del invalid["nativeHealing"]
        self.assertIsNone(advisory_area_row(invalid))

    def test_actual_book_source_binding_and_exact_1533_recipient_guard(self):
        closure = json.loads(
            (NEXT / "native-binding-closure-fixtures.json").read_text()
        )["effects"]
        healer = json.loads((NEXT / "1533-binding-fixtures.json").read_text())[
            "effects"
        ]
        for roots, effects, reference, binding, guard in (
            ([166893], closure, 167897, True, False),
            ([143554], closure, 371791, False, False),
            ([107737], closure, 107737, True, False),
            ([367641, 367662], healer, 166935, True, True),
        ):
            rows, unknown = semantic_rows(SimpleNamespace(effects=effects), roots, 100)
            selected = [row for row in rows if row["nativeReference"] == reference]
            self.assertTrue(selected)
            for row in selected:
                self.assertIs(row["nativeBase"]["sourceBindingKnown"], binding)
                self.assertIs("nativeHealthEligibility" in row, guard)
                if guard:
                    self.assertTrue(row["conditional"])
                    self.assertEqual(
                        row["nativeHealthEligibility"],
                        dict(version=1, targetNotCarried=True),
                    )
                if not binding:
                    self.assertTrue(row["conditional"])
            if reference == 167897:
                self.assertTrue(
                    all(row["conditional"] for row in selected)
                )  # Resurrection predicate remains unknown.
        leaf = effect()
        parent = effect(family=330, parameters=[0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0])
        parent["children"] = [2]  # Native actor_rebind1 changes child caster.
        graph = {"1": parent, "2": leaf}
        self.assertFalse(
            source_binding_proof(graph, [1, 2], 1)[2]
        )  # AND across direct+rebound paths.
        parent["application_flag"] = "EFFECT_CARRIER"
        self.assertFalse(source_binding_proof(graph, [1], 1)[2])

    def test_unknown_classic_heal_keeps_exact_baseline_without_widening_percent_or_light(
        self,
    ):
        import ast
        import wakfu_ai.bridge.jondo_snapshot as snapshot

        # Compile the unchanged current G5 producer, rather than mirroring its
        # legacy fields in the regression expectation.
        tree = ast.parse(
            (ROOT / "server/ai-service/wakfu_ai/bridge/jondo_snapshot.py").read_text()
        )
        definition = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "semantic_rows"
        )
        namespace = dict(vars(snapshot))
        exec(
            compile(
                ast.Module(body=[definition], type_ignores=[]),
                "<G5-semantic-baseline>",
                "exec",
            ),
            namespace,
        )
        baseline = namespace["semantic_rows"]
        actor = SimpleNamespace(
            id=1, team=0, effective_level=10, direction=1, position=(0, 0, 0)
        )
        for family in (25, 259, 253, 258, 251):
            for criterion, application in (
                ("", "EFFECT_CARRIER"),
                ("UnprovedTargetPredicate()", "NONE"),
            ):
                native = effect(family=family, parameters=[37, 0, 3, 0])
                native.update(criteria=criterion, application_flag=application)
                compiled = SimpleNamespace(effects={"1": native})
                expected = baseline(compiled, [1], 10)
                actual = semantic_rows(compiled, [1], 10)
                self.assertEqual(actual, expected)
                for row in actual[0]:
                    self.assertEqual(row["amount"], 37)
                    self.assertNotIn("nativeBase", row)
                    self.assertNotIn("nativeHealing", row)
                    self.assertNotIn("nativeHealthGeometry", row)
                support = project_support(
                    compiled,
                    [1],
                    10,
                    fight=SimpleNamespace(actors={1: actor}),
                    actor=actor,
                    actors=[dict(id=1, hp=50, team=0)],
                )
                self.assertFalse(
                    support["effects"]
                )  # Original support supplied intent only.
                self.assertIn("heal", support["intents"])
        for family, parameters in ((258, [30, 0, 2, 0, 4, 0]), (1084, [37, 0, 3, 0])):
            native = effect(family=family, parameters=parameters)
            native.update(
                criteria="UnprovedTargetPredicate()", application_flag="EFFECT_CARRIER"
            )
            rows, _ = semantic_rows(SimpleNamespace(effects={"1": native}), [1], 10)
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(row["amount"], 0)
                self.assertFalse(row["nativeBase"]["sourceBindingKnown"])
                self.assertEqual(row["fixedCells"], [])
                self.assertIn("nativeHealthGeometry", row)

    def test_absorber_pool_bounds_are_actual_or_omitted_not_defaulted(self):
        actor = SimpleNamespace(
            effect_frozen=frozenset({97}),
            effect_stats={97: 11, 100: 8, 92: 7},
            effect_minima={97: 0, 100: 1, 92: 0},
            effect_maxima={97: 50, 100: 20, 92: 10},
        )
        projected = readonly_healing_projection(actor)
        self.assertEqual(
            projected["nativeArmor"],
            dict(version=1, minimum=0, maximum=50, frozen=True),
        )
        self.assertEqual(
            projected["nativeBarrier"],
            dict(version=1, minimum=1, maximum=20, frozen=False),
        )
        self.assertEqual(
            projected["nativeVirtualHp"],
            dict(version=1, minimum=0, maximum=10, frozen=False),
        )
        del actor.effect_minima[97]
        self.assertNotIn("nativeArmor", readonly_healing_projection(actor))


if __name__ == "__main__":
    unittest.main()
