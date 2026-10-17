"""Optional primitive identity graphs survive real JSON transport exactly."""
import json
import unittest

from wakfu_server.combat_reproduction_state import (
    SCHEMA,
    encode_state,
    decode_state,
    UnsupportedReproductionState,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_npc_reproduction import after_state_projection


class ScalarIdentityReproductionTests(unittest.TestCase):
    def roundtrip(self, value):
        return decode_state(
            json.loads(json.dumps(encode_state(value, preserve_scalars=True)))
        )

    def test_shared_and_distinct_equal_strings_and_bytes_survive_json(self):
        for value in (
            "x",
            "long scalar string " * 80,
            b"x",
            b"long scalar bytes " * 80,
        ):
            with self.subTest(kind=type(value).__name__, length=len(value)):
                join = "".join if type(value) is str else b"".join
                empty = "" if type(value) is str else b""
                one, two = join((value, empty)), join((value, empty))
                self.assertIsNot(
                    one, two, "Fixture must contain distinct actual primitive objects"
                )
                result = self.roundtrip([one, one, two, two])
                self.assertEqual(result, [value] * 4)
                self.assertTrue(all(type(item) is type(value) for item in result))
                self.assertIs(result[0], result[1])
                self.assertIs(result[2], result[3])
                self.assertIsNot(result[0], result[2])

    def test_actor_attribute_keys_preserve_aliases_to_external_facts(self):
        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 1, 1, 9, True)
        key = next(key for key in vars(actor) if key == "id")
        restored = self.roundtrip(dict(actor=actor, key=key))
        actual = next(key for key in vars(restored["actor"]) if key == "id")
        self.assertIs(actual, restored["key"])
        self.assertEqual(list(vars(restored["actor"])), list(vars(actor)))

    def test_runtime_service_key_alias_and_original_attribute_order_are_preserved(self):
        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 1, 1, 9, True)
        target = Actor(-7, 1, (1, 0, 0), 60, 6, 3, 1, 1, 9, False)
        fight = Fight(
            99,
            [actor, target],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        runtime = RuntimeMessages(fight)
        key = next(key for key in vars(runtime) if key == "clock")
        result = self.roundtrip(dict(runtime=runtime, service_key=key))
        self.assertEqual(list(vars(result["runtime"])), list(vars(runtime)))
        restored_key = next(key for key in vars(result["runtime"]) if key == "clock")
        self.assertIs(restored_key, result["service_key"])
        self.assertIsNone(result["runtime"].clock)

    def test_legacy_default_encoding_and_reading_are_unchanged(self):
        payload = encode_state(["x", b"x"])
        self.assertFalse(
            any(node["kind"] in ("str", "bytes") for node in payload["nodes"])
        )
        self.assertEqual(decode_state(json.loads(json.dumps(payload))), ["x", b"x"])

    def test_after_projection_ignores_only_immutable_scalar_aliases(self):
        scalar = "".join(("event key repeated", ""))
        other = "".join((scalar, ""))
        self.assertIsNot(scalar, other)
        exact = encode_state([scalar, scalar, b"packet"], preserve_scalars=True)
        separate = encode_state([scalar, other, b"packet"], preserve_scalars=True)
        self.assertNotEqual(exact, separate)
        self.assertEqual(
            after_state_projection(exact), after_state_projection(separate)
        )
        self.assertIsNone(after_state_projection(None))
        envelope = dict(schema="shared", graph=exact)
        self.assertEqual(
            after_state_projection(envelope)["graph"], after_state_projection(exact)
        )

    def test_after_projection_rejects_domain_container_value_order_and_byte_corruption(
        self,
    ):
        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 1, 1, 9, True)
        other = Actor(7, 0, (0, 0, 0), 60, 6, 3, 1, 1, 9, True)
        container = [actor]

        def projected(value):
            return after_state_projection(encode_state(value, preserve_scalars=True))

        cases = (
            ([actor, actor], [actor, other]),
            ([container, container], [container, [actor]]),
            (dict(first=1, second=2), dict(second=2, first=1)),
            ([1, 2], [2, 1]),
            (b"packet", b"packeT"),
        )
        for before, corrupted in cases:
            with self.subTest(kind=type(before).__name__):
                self.assertNotEqual(projected(before), projected(corrupted))
        original = projected(actor)
        actor.hp -= 1
        self.assertNotEqual(original, projected(actor))

    def test_distinct_empty_scalar_claim_rejects_instead_of_collapsing_identity(self):
        for kind in ("str", "bytes"):
            payload = dict(
                schema=SCHEMA,
                root={"ref": 2},
                services=[],
                nodes=[
                    dict(kind=kind, value=""),
                    dict(kind=kind, value=""),
                    dict(kind="tuple", items=[{"ref": 0}, {"ref": 1}]),
                ],
            )
            with self.subTest(kind=kind), self.assertRaises(
                UnsupportedReproductionState
            ):
                decode_state(payload)

    def test_invalid_scalar_data_and_service_key_shape_reject(self):
        malformed = dict(
            schema=SCHEMA,
            root={"ref": 0},
            services=[],
            nodes=[dict(kind="bytes", value="not-base64!")],
        )
        with self.assertRaises(UnsupportedReproductionState):
            decode_state(malformed)
        malformed["nodes"][0] = dict(kind="str", value=123)
        with self.assertRaises(UnsupportedReproductionState):
            decode_state(malformed)
