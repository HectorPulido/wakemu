import struct
from types import SimpleNamespace
import unittest
from wakfu_server.combat_original_controller_area import (
    original_controller_area_creator,
)
from wakfu_server.combat_effect_area import (
    NativeEffectAreaHandler,
    remove_owned_hour_area,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.wire import proto_fields


class OriginalControllerAreaTests(unittest.TestCase):
    def fixture(self, controller=8):
        actors = {
            7: SimpleNamespace(id=7, direction=2, position=(0, 0, 0)),
            8: SimpleNamespace(id=8, direction=6, position=(9, 9, 0)),
        }
        fight = SimpleNamespace(id=77, actors=actors, native_effect_areas={})
        allocated, packets, affiliations, created = [], [], [], []

        def allocate():
            uid = 901 + len(allocated)
            allocated.append(uid)
            return uid

        authority = lambda f, a: SimpleNamespace(
            targeting=dict(is_eGj=True, dpr_id=controller)
        )

        def affiliation(f, source):
            affiliations.append(source)
            return 1

        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda i: (dict(container_type=None), None),
            actor_authority=authority,
            area_affiliation=affiliation,
        )
        handler.on_created = created.append
        return fight, handler, allocated, packets, affiliations, created

    def test_all_native_hours_use_original_controller_and_original_source_orientation(
        self,
    ):
        for reference in range(1546, 1558):
            for level in (1, 200):
                with self.subTest(reference=reference, level=level):
                    (
                        fight,
                        handler,
                        allocated,
                        packets,
                        affiliations,
                        created,
                    ) = self.fixture()
                    self.assertTrue(
                        handler(
                            dict(effect_class=1008),
                            dict(parameters=[reference, 1, 1]),
                            EffectInvocation(314085, level, 7, None, (2, 3, 0)),
                        )
                    )
                    area = fight.native_effect_areas[901]
                    self.assertEqual(
                        (area["owner_id"], area["direction"], area["level"]), (8, 2, 1)
                    )
                    self.assertEqual(affiliations, [8])
                    self.assertEqual(created, [area])
                    self.assertEqual(allocated, [901, 902])
                    opcode, payload = packets[0]
                    self.assertIn(opcode, (12613, 13497))
                    offset = 13 if opcode == 12613 else 12
                    self.assertEqual(struct.unpack_from(">i", payload, offset)[0], 1008)
                    fields = dict(proto_fields(payload[offset + 6 :]))
                    self.assertEqual(
                        fields[48], 7
                    )  # Original bfr wire caster, not redirected area creator.
                    self.assertNotIn(56, fields)  # Cell recipient has no bfs target.
                    self.assertTrue(area["keep_after"])
                    remove_owned_hour_area(fight, 901)
                    self.assertFalse(fight.native_effect_areas)

    def test_inherited_context_redirects_area_reference_without_changing_creator(self):
        from wakfu_server.combat_value_transfer import transfer_value_context

        fight, handler, allocated, packets, affiliations, created = self.fixture()
        invocation = EffectInvocation(
            314085,
            200,
            7,
            None,
            (2, 3, 0),
            native_context_hex=transfer_value_context(b"", 1547).hex(),
        )
        self.assertTrue(
            handler(dict(effect_class=1008), dict(parameters=[1546, 1, 1]), invocation)
        )
        self.assertEqual(fight.native_effect_areas[901]["reference"], 1547)
        self.assertEqual(fight.native_effect_areas[901]["owner_id"], 8)

    def test_ordinary_self_controller_and_explicit_nonfighter_or_null(self):
        fight, handler, allocated, packets, affiliations, created = self.fixture(
            controller=7
        )
        self.assertEqual(
            original_controller_area_creator(fight, 7, handler.actor_authority), 7
        )
        self.assertIsNone(original_controller_area_creator(fight, None, None))
        authority = lambda f, a: SimpleNamespace(targeting=dict(is_eGj=False))
        self.assertEqual(original_controller_area_creator(fight, 7, authority), 7)

    def test_unknown_controller_rejects_before_allocation_and_registration(self):
        for controller in (None, 0, 99, True):
            fight, handler, allocated, packets, affiliations, created = self.fixture(
                controller
            )
            with self.assertRaises(ValueError):
                handler(
                    dict(effect_class=1008),
                    dict(parameters=[1546, 1, 1]),
                    EffectInvocation(314085, 1, 7, None, (2, 3, 0)),
                )
            self.assertFalse(allocated)
            self.assertFalse(packets)
            self.assertFalse(created)
            self.assertFalse(fight.native_effect_areas)


if __name__ == "__main__":
    unittest.main()
