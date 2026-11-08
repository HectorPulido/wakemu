"""Canonical summon codec coverage; no invented summon lifetime operation."""
import unittest
from copy import deepcopy
from wakfu_server.combat_summon import SummonSpecification
from wakfu_server.combat_summon_codec import summon_payload
from wakfu_server.combat_retained_summon import retained_summon_actor
from wakfu_server.combat_retained_gc import (
    _fields,
    _wire_references,
    plan_retired_effects,
)
from test_retained_gc_graph import fixture, scalar, varint


def encoded(fields):
    return b"".join(
        scalar(number, value)
        if wire == 0
        else varint(number << 3 | 2) + varint(len(value)) + value
        for number, (wire, value) in fields.items()
    )


def payload(*, properties=(), caster=1, actor=202, controlled=False):
    return summon_payload(
        uid=201,
        base_uid=201,
        effect_reference=313167,
        caster_id=caster,
        cell=(0, 0, 0),
        specification=SummonSpecification(999, 10, controlled, 7, 1, "caster", -2),
        actor_id=actor,
        obstacle_index=-1,
        properties=properties,
        timing_payload=b"",
    )


class RetainedGCSummonSchemaTests(unittest.TestCase):
    def test_real_encoder_actor_and_caster_roots_are_distinct_from_running_uid(self):
        for properties, caster, controlled in (
            ((), 1, False),
            ((0, 19, 127), -100, True),
        ):
            with self.subTest(properties=properties, caster=caster):
                raw = payload(
                    properties=properties, caster=caster, controlled=controlled
                )
                self.assertEqual(retained_summon_actor(raw), 202)
                actors, uids, areas = _wire_references(raw.hex(), 307)
                self.assertEqual(actors, {caster, 202})
                self.assertEqual(uids, {201})
                self.assertFalse(areas)

    def test_unknown_or_mismatched_descriptor_still_rejects_whole_gc_plan(self):
        raw = payload()
        outer = _fields(raw)
        variants = []
        for identity in (0, 203, 1 << 63):
            changed = dict(outer)
            changed[12] = (2, scalar(4, identity))
            variants.append(encoded(changed))
        changed = dict(outer)
        changed[12] = (2, scalar(4, 202) + scalar(5, 1))
        variants.append(encoded(changed))
        changed = dict(outer)
        changed[6] = (0, 2)
        variants.append(encoded(changed))
        changed = dict(outer)
        changed[7] = (0, 1)
        variants.append(encoded(changed))
        changed = dict(outer)
        del changed[12]
        variants.append(encoded(changed))
        descriptor = _fields(outer[8][1])[1][1]
        for blob in (descriptor[:-1], descriptor + b"\0", b"\x02" + descriptor[1:]):
            changed = dict(outer)
            changed[8] = (2, encoded({1: (2, blob)}))
            variants.append(encoded(changed))
        variants.append(raw + scalar(99, 1))
        for bad in variants:
            with self.subTest(payload_length=len(bad)):
                with self.assertRaises(ValueError):
                    _wire_references(bad.hex(), 307)
                snapshot = fixture()
                snapshot["native_retained_records"]["201"] = dict(
                    uid=201,
                    manager_id=1,
                    target_id=None,
                    effect_class=307,
                    owner_uid=None,
                )
                snapshot["native_owned_group_effects"]["201"] = dict(
                    uid=201, target_id=None, payload=bad.hex(), timer=None
                )
                plan = plan_retired_effects(snapshot, {-100, -200}, pending_roots=())
                self.assertFalse(plan.effect_uids)
                self.assertTrue(plan.opaque_sources)

    def test_supported_summon_does_not_disable_unrelated_terminal_cleanup(self):
        snapshot = fixture()
        snapshot["actors"]["202"] = dict(id=202, state_ledger={"entries": []})
        snapshot["native_retained_records"]["201"] = dict(
            uid=201, manager_id=1, target_id=None, effect_class=307, owner_uid=None
        )
        snapshot["native_owned_group_effects"]["201"] = dict(
            uid=201, target_id=None, payload=payload().hex(), timer=None
        )
        before = deepcopy(snapshot)
        plan = plan_retired_effects(snapshot, {-100, -200}, pending_roots=())
        self.assertEqual(plan.effect_uids, {21, 22, 31})
        self.assertFalse(plan.opaque_sources)
        self.assertEqual(snapshot, before)
        # The same bytes are not an authority for captured family324.
        with self.assertRaises(ValueError):
            _wire_references(payload().hex(), 324)


if __name__ == "__main__":
    unittest.main()
