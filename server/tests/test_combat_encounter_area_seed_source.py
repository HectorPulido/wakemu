"""Granular PL operand guards; callback/304/listener caster stays unchanged."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_encounter_area_seed_source import seed_program_level_source
from wakfu_server import combat_encounter_seed_programs as manifests
from wakfu_server import combat_state_managers as managers


class EncounterAreaSeedSourceTests(unittest.TestCase):
    def fixture(self):
        row = dict(
            uid=132, reference=1650, effect_reference=324354, level=1, owner_id=-200
        )
        program = dict(
            area_reference=1650,
            creator_reference=324354,
            program_reference=324353,
            state_reference=7001,
            state_effect_reference=324355,
            level=1,
        )
        fight = SimpleNamespace(
            native_encounter_area_seed_policy={"boss_reference": 5306},
            native_effect_areas={132: row},
        )
        values = dict(parameters=[0, 0, 1, 0, 1, 0, 7001, 1, 1, 0])
        effect = dict(effect_class=844)
        area = SimpleNamespace(
            id=132,
            state_ledger=SimpleNamespace(
                entries=(SimpleNamespace(reference=7001, level=1),)
            ),
        )
        invocation = EffectInvocation(
            318816,
            1,
            -200,
            2,
            (-44, 11, -4),
            native_retained_container=dict(
                present=True, type=3, id=132, level=1, native_kind="effect_area"
            ),
        )
        return fight, row, program, effect, values, area, invocation

    def source(self, fixture):
        fight, _, program, effect, values, area, invocation = fixture
        with patch.object(
            manifests, "encounter_seed_programs", return_value=(program,)
        ), patch.object(managers, "registered_area_pv", return_value=area):
            return seed_program_level_source(fight, effect, values, invocation)

    def test_actual_area_pl_is_operand_and_caster_is_still_owner(self):
        fixture = self.fixture()
        self.assertIs(self.source(fixture), fixture[5])
        self.assertEqual((fixture[6].caster_id, fixture[6].target_id), (-200, 2))
        fixture[1]["uid"] = 999
        fixture[5].id = 999
        fixture[0].native_effect_areas = {999: fixture[1]}
        fixture[6].native_retained_container["id"] = 999
        self.assertIs(self.source(fixture), fixture[5])

    def test_wrong_constructor_owner_and_retained_state_do_not_opt_in(self):
        fixture = list(self.fixture())
        fixture[1]["effect_reference"] += 1
        self.assertIsNone(self.source(fixture))
        fixture[1]["effect_reference"] -= 1
        fixture[1]["owner_id"] = 33
        self.assertIsNone(self.source(fixture))
        fixture[1]["owner_id"] = -200
        fixture[6] = replace(fixture[6], state_uid=264)
        self.assertIsNone(self.source(fixture))

    def test_no_manifest_missing_pl_and_target_getter_preserve_default(self):
        fixture = list(self.fixture())
        fixture[0].native_encounter_area_seed_policy = None
        self.assertIsNone(self.source(fixture))
        fixture = list(self.fixture())
        fixture[6] = replace(fixture[6], native_retained_container=None)
        self.assertIsNone(self.source(fixture))
        fixture = self.fixture()
        fixture[4]["parameters"][7] = 0
        self.assertIsNone(self.source(fixture))

    def test_native_actor_rebind_and_absent_qq_state_are_not_overridden(self):
        fixture = self.fixture()
        for rebind in (1, 2):
            fixture[4]["parameters"][5] = rebind
            self.assertIsNone(self.source(fixture))
        fixture[4]["parameters"][5] = 0
        fixture[5].state_ledger.entries = ()
        self.assertIsNone(self.source(fixture))

    def test_real_registered_qq_ledger_binds_native_level_and_wire_without_rebinding(
        self,
    ):
        from wakfu_server.combat_state_level_group import runtime_child_level
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_state_ledger import StateLedger, RunningState
        from wakfu_server.combat_effect_removal import _identity_fields

        fixture = self.fixture()
        fight, row, program, _, values, _, invocation = fixture
        ledger = StateLedger(row["uid"])
        ledger._entries = (
            RunningState(
                301, 7001, 1, -200, row["uid"], -1, "target", False, (), 0, True, None
            ),
        )
        row.update(
            cell=invocation.cell,
            native_area_contract="faY",
            native_running_effect_manager=True,
            state_ledger=ledger,
        )
        fight.actors = {
            -200: SimpleNamespace(state_ledger=StateLedger(-200)),
            2: SimpleNamespace(state_ledger=StateLedger(2)),
        }
        definitions = {
            "1650": dict(type="GLYPH", native_area_properties=[12], entry_masks=[])
        }
        effect = dict(
            effect_class=844,
            native_effect_flags=[17],
            parameters=[0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 7001, 0, 1, 0, 1, 0, 0, 0],
        )
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight, runtime.plan = fight, {
            "native_retained_container": {"present": False}
        }
        with patch.object(
            manifests, "encounter_seed_programs", return_value=(program,)
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            self.assertEqual(runtime_child_level(effect, values, invocation, fight), 1)
            level, wire = runtime.child_level_context(
                effect, values, invocation, default_level=1
            )
            self.assertEqual(
                (level, _identity_fields(wire, integer_fields=(4,))[4]), (1, 1)
            )
            fight.native_encounter_area_seed_policy = None
            self.assertEqual(runtime_child_level(effect, values, invocation, fight), 0)
        self.assertEqual((invocation.caster_id, invocation.target_id), (-200, 2))
