import unittest
from wakfu_server.combat_subscription_runners import deferred_payload
from wakfu_server.combat_effect_removal import _identity_fields, _read_varint


def fields(data):
    result = {}
    offset = 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        key = tag >> 3
        value, offset = _read_varint(data, offset)
        if tag & 7 == 2:
            value, data_end = data[offset : offset + value], offset + value
            offset = data_end
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


class DeferredRunnerTests(unittest.TestCase):
    def test_state_decurse_subscription_has_only_original_fresh_base_payload(self):
        from wakfu_server.combat_subscription_runners import (
            DEFERRED_RUNNERS,
            SUBSCRIPTION_FAMILIES,
        )

        self.assertEqual(DEFERRED_RUNNERS.get(321), "eZi")
        self.assertIn(321, SUBSCRIPTION_FAMILIES)
        args = dict(
            uid=91,
            base_uid=90,
            generic_effect=242089,
            caster_id=7,
            target_id=7,
            cell=(1, 2, 0),
            timing_payload=b"",
            container_type=1,
            container_id=842,
        )
        payload = deferred_payload(family=321, **args)
        # eZi inherits eZR.b(iP); its private rHq/rHr are not wire fields.
        self.assertEqual(payload, deferred_payload(family=421, **args))
        parsed = fields(payload)
        self.assertEqual(parsed[4], 0)
        self.assertNotIn(8, parsed)
        self.assertEqual((parsed[9], parsed[10]), (1, 842))

    def test_fresh_native_constructors_do_not_apply_or_calculate(self):
        clock = bytes.fromhex(
            "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
        )
        native = {
            421: "08850710a00618d8b21520002a06080410051800300738f9ffffffffffffffff015a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800",
            1001: "08850710a00618d8b21520002a06080410051800300738f9ffffffffffffffff01420d500060ffffffffffffffffff015a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800",
        }
        for family, captured in native.items():
            with self.subTest(family=family):
                actual = deferred_payload(
                    family=family,
                    uid=901,
                    base_uid=800,
                    generic_effect=350552,
                    caster_id=7,
                    target_id=-7,
                    cell=(4, 5, 0),
                    timing_payload=clock,
                    container_type=None,
                    container_id=None,
                )
                expected = fields(bytes.fromhex(captured))
                got = fields(actual)
                self.assertEqual(
                    {k: v for k, v in got.items() if k not in (8, 11)},
                    {k: v for k, v in expected.items() if k not in (8, 11)},
                )
                self.assertEqual(fields(got[11]), fields(expected[11]))
                if family == 1001:
                    self.assertEqual(fields(got[8]), fields(expected[8]))
                self.assertEqual(got[4], 0)
                self.assertEqual(fields(got[11])[5], 0)

    def test_unknown_runner_and_partial_container_reject(self):
        args = dict(
            uid=1,
            base_uid=1,
            generic_effect=10,
            caster_id=1,
            target_id=2,
            cell=(0, 0, 0),
            timing_payload=b"",
            container_type=None,
            container_id=None,
        )
        with self.assertRaises(ValueError):
            deferred_payload(family=99999, **args)
        args["container_type"] = 3
        with self.assertRaises(ValueError):
            deferred_payload(family=421, **args)

    def test_deferred_decurse_disappearance_and_copy_do_not_run_handlers_or_guards(
        self,
    ):
        from types import SimpleNamespace
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        effects = {
            str(kind): dict(
                effect_class=kind,
                parameters=[],
                parameter_count=0,
                probability_base=100,
                probability_per_level=0,
                minimum_level=1,
                maximum_level=200,
                children=[],
                criteria="UnsupportedCriterion()",
                target_masks=[[1003], [], [], [], [], [], []],
            )
            for kind in (321, 421, 1001)
        }
        retention = object.__new__(NativeRetainedRuntime)
        retention.definition = lambda effect, inv: dict(subscription=True)
        saved = []
        retention.begin_group = lambda effect, values, inv: dict(
            family=effect["effect_class"]
        )
        retention.finish_group = lambda row: saved.append(row)

        def unexpected(*args):
            raise AssertionError("Deferred listener evaluated before event")

        dispatcher = EffectDispatcher(
            effects,
            {321: unexpected, 421: unexpected, 1001: unexpected},
            resolve=lambda effect, inv: (inv,),
            condition_context=unexpected,
            probability_accepts=unexpected,
            group_cells=unexpected,
            actor_position=unexpected,
            group_retention=retention,
        )
        for kind in (321, 421, 1001):
            self.assertTrue(
                dispatcher.execute(EffectInvocation(kind, 1, 1, 2, (0, 0, 0)))
            )
        self.assertEqual(saved, [{"family": 321}, {"family": 421}, {"family": 1001}])
