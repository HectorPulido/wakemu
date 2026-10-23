"""Adapter contracts only; real native349/Qq pickup is qualified separately."""
from contextlib import nullcontext
from types import SimpleNamespace
import unittest

from wakfu_server.combat_encounter_area_seeds import (
    NativeEncounterAreaSeed,
    install_native_area_seeds,
)


class EncounterAreaSeedProgramTests(unittest.TestCase):
    def fixture(self):
        cell = (2, 3, 0)
        seed = NativeEncounterAreaSeed(100, 200, 1, cell, 199, 10, 201)
        creator = dict(
            effect_class=315,
            criteria="",
            children=[],
            parameters=[100, 0, 1, 0, 1, 0],
            parameter_count=3,
            probability_base=100,
            probability_per_level=0,
        )
        state = dict(creator, effect_class=304, parameters=[10, 0, 0, 1, -1, 0])
        parent = dict(
            creator, effect_class=349, children=[200, 201], native_effect_flags=[16]
        )
        actor = SimpleNamespace(position=(0, 0, 0), physical_radius=0, hp=10)
        fight = SimpleNamespace(
            phase="active",
            actors={7: actor},
            walkable={cell},
            native_effect_areas={},
            effect_resolution=nullcontext,
        )
        original_cells = lambda effect, invocation: ((99, 99, 0),)
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        retention = object.__new__(NativeRetainedRuntime)
        retention.fight = fight
        retention.plan = {"native_retained_container": {"present": False}}
        dispatcher = SimpleNamespace(
            native_retention=retention,
            effects={"199": parent, "200": creator, "201": state},
            group_cells=original_cells,
        )
        return seed, fight, dispatcher, original_cells

    def install(self, dispatcher, seed):
        return install_native_area_seeds(
            dispatcher,
            policy="fixture-program-v1",
            creator_id=7,
            seeds=(seed,),
            provenance={"scope": "adapter_fixture"},
        )

    def test_scoped_population_is_restored_on_native_program_exception(self):
        seed, fight, dispatcher, original_cells = self.fixture()

        def execute(invocation):
            self.assertEqual(invocation.reference, seed.program_reference)
            self.assertFalse(invocation.native_preselected_target)
            self.assertEqual(dispatcher.group_cells({}, invocation), (seed.cell,))
            raise RuntimeError("native child failure")

        dispatcher.execute = execute
        with self.assertRaisesRegex(RuntimeError, "native child failure"):
            self.install(dispatcher, seed)
        self.assertIs(dispatcher.group_cells, original_cells)
        self.assertFalse(hasattr(fight, "native_encounter_area_setups"))

    def test_reordered_native_children_are_rejected_before_execution(self):
        seed, _, dispatcher, _ = self.fixture()
        dispatcher.effects["199"]["children"].reverse()
        dispatcher.execute = lambda invocation: self.fail("Changed program executed")
        with self.assertRaisesRegex(ValueError, "ordered program changed"):
            self.install(dispatcher, seed)

    def test_created_area_without_native_state_is_rejected(self):
        seed, fight, dispatcher, original_cells = self.fixture()

        def execute(invocation):
            fight.native_effect_areas[91] = dict(reference=100, cell=seed.cell)
            return True

        dispatcher.execute = execute
        with self.assertRaisesRegex(
            ValueError, "did not initialize its created Qq state"
        ):
            self.install(dispatcher, seed)
        self.assertIs(dispatcher.group_cells, original_cells)
        self.assertFalse(hasattr(fight, "native_encounter_area_setups"))

    def test_committed_leaf315_receipt_replays_without_manifest_or_upgrade(self):
        import hashlib
        import json
        from unittest.mock import patch
        from wakfu_server.combat_rushu_encounter_setup import (
            install_rushu_encounter_setup,
        )
        from wakfu_server import combat_encounter_seed_programs as programs

        cells = [(index, 0, 0) for index in range(16)]
        seeds = [
            NativeEncounterAreaSeed(100 + index, 200 + index, 1, cell).plain()
            for index, cell in enumerate(cells)
        ]
        provenance = dict(layout_seed=78, layout_policy="fixture-layout-v1")
        payload = dict(
            policy="wakemu.rushu.initial-vestiges.v1",
            creator_id=-200,
            seeds=seeds,
            provenance=provenance,
        )
        checksum = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        receipt = dict(
            schema="wakemu-native-area-setup-v1",
            sha256=checksum,
            plan=payload,
            created_area_uids=list(range(16)),
        )
        fight = SimpleNamespace(
            id=78,
            phase="active",
            native_start_event_delivered=True,
            actors={-200: SimpleNamespace()},
            native_encounter_area_setups={payload["policy"]: receipt},
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        with patch.object(
            programs, "_database", side_effect=AssertionError("late active pointer")
        ):
            self.assertFalse(
                install_rushu_encounter_setup(
                    dispatcher,
                    map_id=1332,
                    monsters={-200: {"ref": 5306}},
                    layout=dict(
                        map_id=1332, glyph_cells=cells, policy="fixture-layout-v1"
                    ),
                )
            )
        self.assertFalse(hasattr(fight, "native_encounter_area_seed_policy"))
        self.assertEqual(receipt["plan"], payload)
        self.assertTrue(
            all(
                set(row) == {"area_reference", "effect_reference", "level", "cell"}
                for row in receipt["plan"]["seeds"]
            )
        )

    def test_root_initial_level_uses_native_sp_transmission_without_fake_container(
        self,
    ):
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        seed, _, dispatcher, _ = self.fixture()
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.plan = {"native_retained_container": {"present": False}}

        def execute(invocation):
            level, _ = runtime.child_level_context(
                {"effect_class": 349, "native_effect_flags": [16]},
                {},
                invocation,
                default_level=invocation.level,
            )
            self.assertEqual(level, seed.level)
            self.assertFalse(runtime.probability_bypassed(invocation))
            self.assertEqual(invocation.native_retained_container, {"present": False})
            raise RuntimeError("transmission observed before constructor")

        dispatcher.execute = execute
        with self.assertRaisesRegex(RuntimeError, "transmission observed"):
            self.install(dispatcher, seed)
