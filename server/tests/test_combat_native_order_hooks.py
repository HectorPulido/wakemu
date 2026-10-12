"""Real factory, registered authority, owned wire and rollback for native hooks."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from wakfu_server import combat_native_order_hooks as module
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_effect_dispatch import EffectInvocation, run_effect_transaction
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_runner_callbacks import runner_value_scope
import test_combat_random_earth_damage as damage_fixture

FIXTURE = json.loads(
    (Path(__file__).resolve().parent / "fixtures/native_order_hooks.json").read_text()
)


class NativeOrderHookRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        damage_fixture.RealRuntimeTests.setUpClass()

    def setUp(self):
        base = damage_fixture.RealRuntimeTests()
        base.setUp()
        self.fight, self.adapter = base.fight, base.fixture.adapter
        effects = deepcopy(base.fixture.f.effects)
        effects.update(deepcopy(FIXTURE["effects"]))
        metadata = deepcopy(base.fixture.f.fixture["retained_metadata"])
        metadata["effects"].update(deepcopy(FIXTURE["metadata"]))
        self.factory = NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog={"effects": {}, "states": []},
            characteristic_registry={"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            contexts=self.adapter.contexts(),
            summon_authority=self.adapter.actor_authority,
        )
        self.plan = {"spell_id": 6266, "evaluation_level": 1}
        self.metadata = metadata
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value=metadata,
        ):
            self.dispatcher, self.packets = self.factory(self.fight, self.plan)
        self.seen = []

    def invocation(self, reference):
        return EffectInvocation(
            reference, 1, 7, -7, (1, 0, 0), native_preselected_target=True
        )

    def execute(self, reference):
        original = type(self.dispatcher.replay_event).__call__

        def capture(replay, source, **kwargs):
            self.seen.append(
                (
                    source.channel,
                    source.uid,
                    source.effect_action_id,
                    source.value,
                    source.event_ids,
                )
            )
            return original(replay, source, **kwargs)

        with patch.object(type(self.dispatcher.replay_event), "__call__", capture):
            return self.dispatcher.execute(self.invocation(reference))

    def owned(self):
        rows = [
            row
            for row in self.fight.owned_stat_effects.values()
            if row["effect_class"] in module.FAMILIES
        ]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test327_real_factory_keeps_order_amount_long_zero_and_exact_lifecycle(self):
        before = [a.hp for a in self.fight.actors.values()]
        self.assertTrue(self.execute(187816))
        row = self.owned()
        fields, messages = {}, {}
        fields = _identity_fields(bytes.fromhex(row["payload"]), messages=messages)
        self.assertEqual(fields[4], 14)
        self.assertEqual(messages[8], bytes.fromhex("6800"))
        self.assertEqual([x[0] for x in self.seen], [10, 1, 20, 2, 30, 3, 40, 4])
        self.assertEqual({x[1] for x in self.seen}, {901})
        self.assertEqual([a.hp for a in self.fight.actors.values()], before)
        self.assertEqual(row["family"], "eVX")
        self.assertEqual({x[4] for x in self.seen}, {(0,)})
        self.assertEqual(set(self.fight.native_retained_records), {900, 901})

    def test328_real_retained_packet_owns_cell15_and_original_container(self):
        self.assertTrue(self.execute(175181))
        row = self.owned()
        messages = {}
        fields = _identity_fields(bytes.fromhex(row["payload"]), messages=messages)
        self.assertEqual(fields[4], 3)
        self.assertEqual(
            messages[8],
            module.order_additional(328, cell=module.NativeOrderCell(1, 0, 0)),
        )
        self.assertEqual(_identity_fields(messages[8], integer_fields=()), {})
        self.assertIn(
            9, _identity_fields(bytes.fromhex(row["payload"]), integer_fields=(9, 10))
        )
        self.assertEqual([x[0] for x in self.seen], [10, 1, 20, 2, 30, 3, 40, 4])

    def test342_actual_factory_publishes_once_and_preserves_no_additional(self):
        self.assertTrue(self.execute(152407))
        self.assertEqual(len(self.packets), 1)
        messages = {}
        fields = _identity_fields(self.packets[0][1][18:], messages=messages)
        self.assertEqual(fields[4], 0)
        self.assertNotIn(8, messages)
        self.assertEqual({x[4] for x in self.seen}, {()})
        self.assertEqual([x[0] for x in self.seen], [10, 1, 20, 2, 30, 3, 40, 4])
        self.assertFalse(
            any(
                row["effect_class"] == 342
                for row in self.fight.owned_stat_effects.values()
            )
        )

    def test_owned_removal_real_central_callback_preserves_wire_and_hp(self):
        self.assertTrue(self.execute(175181))
        row = deepcopy(self.owned())
        retention = self.dispatcher.group_retention
        retention.removal(retention.view()).remove([row["uid"]])
        self.assertNotIn(row["uid"], self.fight.owned_stat_effects)
        self.assertEqual(self.packets[-1][0], 13560)
        self.assertEqual(struct.unpack(">q", self.packets[-1][1][-8:])[0], row["uid"])
        self.assertEqual(self.fight.actors[-7].hp, 12000)

    def test_actual_value_observer_sees_order_amount_after_lifecycle(self):
        seen = []
        with runner_value_scope(lambda inv, value: seen.append(value)) as observer:
            inv = replace(self.invocation(187816), native_value_scope=observer)
            self.assertTrue(self.dispatcher.execute(inv))
        self.assertEqual(seen, [14])

    def test_optional_three_parameter_definition_rejected_before_packets(self):
        effect = (
            self.dispatcher.effects[175181]
            if 175181 in self.dispatcher.effects
            else self.dispatcher.effects["175181"]
        )
        effect["parameters"] = [3, 0, 1, 0, 2, 0]
        effect["parameter_count"] = 3
        with self.assertRaisesRegex(ValueError, "parameter schema|definition|metadata"):
            self.execute(175181)
        self.assertEqual(self.packets, [])

    def test_missing_registered_actor_authority_rejects_before_mutation(self):
        self.adapter.actor_authority.ordinary.characters.clear()
        with self.assertRaises(ValueError):
            self.execute(187816)
        self.assertEqual(self.packets, [])
        self.assertFalse(
            any(
                row["effect_class"] == 327
                for row in self.fight.owned_stat_effects.values()
            )
        )

    def test_actual_fight_transaction_rolls_back_owned_hook_and_publication_failure(
        self,
    ):
        before = deepcopy(
            (
                self.fight.owned_stat_effects,
                self.fight.native_retained_records,
                self.fight.native_retained_order,
                self.fight.events,
            )
        )

        def factory(preview):
            with patch(
                "wakfu_server.combat_retained_runtime.native_retained_metadata",
                return_value=self.metadata,
            ):
                dispatcher, packets = self.factory(preview, self.plan)
            original = dispatcher.execute

            def fail(inv):
                original(inv)
                raise RuntimeError("publication rejected")

            dispatcher.execute = fail
            return dispatcher

        with self.assertRaisesRegex(RuntimeError, "publication rejected"):
            run_effect_transaction(self.fight, [self.invocation(187816)], factory)
        self.assertEqual(
            (
                self.fight.owned_stat_effects,
                self.fight.native_retained_records,
                self.fight.native_retained_order,
                self.fight.events,
            ),
            before,
        )

    def test_installed_java_additional_bytes_match_encoders(self):
        native = {
            row["family"]: row["additional_hex"]
            for row in FIXTURE["native_probe"]
            if "additional_hex" in row
        }
        self.assertEqual(module.order_additional(327).hex(), native[327])
        self.assertEqual(
            module.order_additional(328, cell=module.NativeOrderCell(2, 3, 4)).hex(),
            native[328],
        )
        self.assertEqual(module.order_additional(342), b"")

    def test_owned_hook_checkpoint_contains_only_serializable_wire_and_native_timer(
        self,
    ):
        from wakfu_server.fight_checkpoint_store import snapshot

        self.assertTrue(self.execute(175181))
        row = self.owned()
        saved = json.loads(json.dumps(snapshot(self.fight)))
        owned = saved["owned_stat_effects"][str(row["uid"])]
        self.assertEqual(owned["payload"], row["payload"])
        self.assertEqual(owned["timer"], row["timer"])
        self.assertEqual(
            saved["native_retained_records"][str(row["uid"])]["effect_class"], 328
        )

    def test_restored_runner_identity_rejected_without_recalculation_or_packets(self):
        inv = replace(self.invocation(187816), native_running_uid=901)
        with self.assertRaisesRegex(ValueError, "restored"):
            self.dispatcher.execute(inv)
        self.assertEqual(self.packets, [])

    def test_native_cell_copies_input_values_and_rejects_nonshort_altitude(self):
        source = [2, 3, 4]
        cell = module.NativeOrderCell(*source)
        source[0] = 999
        self.assertEqual(cell.payload(), bytes.fromhex("080210031804"))
        with self.assertRaises(ValueError):
            module.NativeOrderCell(2, 3, 32768)
