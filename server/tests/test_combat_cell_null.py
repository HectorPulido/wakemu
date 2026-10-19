import copy, unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_cell_null import NativeCellNullHandler, cell_null_payload
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_effect_removal import _identity_fields, running_effect_removal


class CellNullTests(unittest.TestCase):
    def setUp(self):
        self.fight = Fight(
            77,
            [
                Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
                Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.fight.ready(3)
        self.fight.native_effect_uid_next = 900
        self.packets = []
        self.effect = dict(
            effect_class=402,
            parameters=[],
            target_masks=[None] * 7,
            native_effect_flags=[17],
        )
        self.inv = EffectInvocation(123, 1, 7, None, (2, -3, 4))

    def handler(self, fight=None, *, retained=True, executable=True):
        fight = self.fight if fight is None else fight
        return NativeCellNullHandler(
            fight,
            self.packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda e, i: StatExecutionContext(
                executable, True, None, retained, native_time_payload()
            ),
        )

    def test_cell_identity_owner_retention_and_removal(self):
        self.assertTrue(self.handler()(self.effect, [], self.inv))
        row = self.fight.owned_stat_effects[900]
        fields = _identity_fields(bytes.fromhex(row["payload"]))
        self.assertEqual((fields[1], fields[2], fields[6]), (900, 900, 7))
        self.assertNotIn(7, fields)
        self.assertIsNone(row["payload_target_id"])
        stat = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=self.fight.allocate_effect_uid,
            context=None,
        )
        self.assertTrue(stat.remove(900))
        self.assertNotIn(900, self.fight.owned_stat_effects)
        self.assertEqual([opcode for opcode, _ in self.packets], [13497, 13560])
        self.assertEqual(self.fight.actors[7].hp, 60)

    def test_instant_cell_null_executes_without_fabricating_actor_target(self):
        self.assertTrue(self.handler(retained=False)(self.effect, [], self.inv))
        self.assertEqual(len(self.packets), 1)
        opcode, body = self.packets[0]
        self.assertEqual(opcode, 12613)
        self.assertEqual(body[12], 1)
        size = int.from_bytes(body[17:19], "big", signed=True)
        fields = _identity_fields(body[19 : 19 + size])
        self.assertEqual(fields[3], 123)
        self.assertEqual(fields[6], 7)
        self.assertNotIn(7, fields)
        self.assertEqual(self.fight.native_effect_uid_next, 901)
        self.assertFalse(self.fight.owned_stat_effects)
        self.assertEqual(self.fight.actors[7].hp, 60)

    def test_actor_target_or_clone_rejected_before_uid(self):
        from dataclasses import replace

        for invocation in (
            replace(self.inv, target_id=-7),
            replace(self.inv, native_running_uid=80),
        ):
            with self.assertRaises(ValueError):
                self.handler()(self.effect, [], invocation)
        self.assertEqual(self.fight.native_effect_uid_next, 900)
        self.assertEqual(self.packets, [])

    def test_guard_false_and_preview_discard_preserve_original(self):
        self.assertFalse(self.handler(executable=False)(self.effect, [], self.inv))
        preview = copy.deepcopy(self.fight)
        self.handler(preview)(self.effect, [], self.inv)
        self.assertEqual(self.fight.native_effect_uid_next, 900)
        self.assertFalse(self.fight.owned_stat_effects)
        self.assertEqual(preview.native_effect_uid_next, 901)

    def test_removal_rejects_wrong_owner(self):
        payload = cell_null_payload(
            uid=900,
            base_uid=None,
            reference=123,
            caster_id=7,
            cell=(2, -3, 4),
            status=-1,
            timing_payload=native_time_payload(),
        )
        with self.assertRaisesRegex(ValueError, "identity differs"):
            running_effect_removal(
                77,
                1,
                effect_class=402,
                target_id=-7,
                uid=900,
                running_effect_payload=payload,
            )

    def test_cell_resolution_is_one_application_without_actor_candidates(self):
        from wakfu_server.combat_effect_resolver import (
            NativeEffectResolver,
            EffectResolutionContext,
        )

        def forbidden(*args):
            raise AssertionError(
                "Cell-only runner must not select actor/area candidates"
            )

        resolver = NativeEffectResolver(
            actors=forbidden,
            native_context=forbidden,
            context=lambda e, i: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "cell", True
            ),
            cell_eligible=lambda e, i: True,
        )
        effect = dict(self.effect, variant=0)
        from dataclasses import replace

        selected = resolver(effect, replace(self.inv, target_id=-7))
        expected = replace(
            self.inv,
            target_id=None,
            native_target_cell_argument=True,
        )
        self.assertEqual(selected, (expected,))
        self.assertIsNone(selected[0].target_id)
        self.assertTrue(selected[0].native_target_cell_argument)
        self.assertTrue(self.handler()(effect, [], selected[0]))
        self.assertEqual(self.fight.native_effect_uid_next, 901)
        self.assertEqual(len(self.packets), 1)
