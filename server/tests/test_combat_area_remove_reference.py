import unittest
from types import SimpleNamespace
from wakfu_server.combat_area_remove_reference import NativeAreaReferenceRemovalHandler
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class AreaReferenceRemovalTests(unittest.TestCase):
    def fixture(self):
        rows = {
            uid: dict(
                uid=uid,
                reference=ref,
                native_area_contract="faY",
                child_effect_uids={},
                owner_id=owner,
                cell=(99, 99, 9),
            )
            for uid, ref, owner in ((901, 781, 7), (902, 781, 8), (903, 999, 7))
        }
        fight = SimpleNamespace(
            id=11,
            actors={7: SimpleNamespace(id=7)},
            native_effect_areas=rows,
            native_retained_records={},
        )
        packets = []
        seen = []
        handler = NativeAreaReferenceRemovalHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 999,
            context=lambda *a: StatExecutionContext(True, True, None, False, b""),
            container=lambda *a: ({"container_type": None}, None),
        )
        handler.events = SimpleNamespace(
            removed=lambda row, **kw: seen.append(
                (row["uid"], kw["target_id"], row["uid"] in fight.native_effect_areas)
            )
        )
        return fight, handler, packets, seen

    def test_removes_all_exact_references_across_owners_and_coordinates(self):
        fight, handler, packets, seen = self.fixture()
        self.assertTrue(
            handler(
                {"effect_class": 935},
                {"parameters": [781]},
                EffectInvocation(300001, 1, 7, None, (0, 0, 0)),
            )
        )
        self.assertEqual(seen, [(901, 7, False), (902, 7, False)])
        self.assertEqual(set(fight.native_effect_areas), {903})
        self.assertEqual([opcode for opcode, _ in packets], [13497])

    def test_negative_reference_is_not_wildcard_and_empty_match_still_executes(self):
        fight, handler, packets, seen = self.fixture()
        self.assertTrue(
            handler(
                {"effect_class": 935},
                {"parameters": [-1]},
                EffectInvocation(300001, 1, 7, None, (0, 0, 0)),
            )
        )
        self.assertEqual(seen, [])
        self.assertEqual(set(fight.native_effect_areas), {901, 902, 903})
        self.assertEqual(len(packets), 1)

    def test_missing_callback_rejects_before_notification_or_mutation(self):
        fight, handler, packets, seen = self.fixture()
        handler.events = None
        with self.assertRaisesRegex(ValueError, "callback authority"):
            handler(
                {"effect_class": 935},
                {"parameters": [781]},
                EffectInvocation(300001, 1, 7, None, (0, 0, 0)),
            )
        self.assertEqual(packets, [])
        self.assertEqual(set(fight.native_effect_areas), {901, 902, 903})

    def test_payload_matches_original_exs_serializer_byte_for_byte(self):
        from wakfu_server.combat_retained_runtime import group_payload
        from wakfu_server.wire import proto_fields

        native = bytes.fromhex(
            "08e70710e70718e1a712208d062a0608001000180030075a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012801"
        )
        clock = dict(proto_fields(native))[90]
        payload = group_payload(
            uid=999,
            base_uid=999,
            generic_effect=300001,
            caster_id=7,
            target_id=None,
            cell=(0, 0, 0),
            container_type=None,
            container_id=None,
            timing_payload=clock,
            initial_value=781,
        )
        self.assertEqual(payload, native)
