"""Exact faW binary32 fast paths retain original IEEE and failure behavior."""
import math
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_fake_fighter import (
    _fake_fighter_constructor_plan,
    _cached_float_constructor,
    _float32,
    _plain_float_constructor,
    fake_fighter_constructor,
)


def reference(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing finite native faW constructor parameter")
    try:
        return struct.unpack(">f", struct.pack(">f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("Invalid native faW float parameter") from error


def outcome(call, value):
    try:
        result = call(value)
        return ("return", type(result), struct.pack(">d", result))
    except Exception as error:
        return ("error", type(error), str(error))


def boundary_cases():
    yield from range(-65536, 65537)
    for sign in (-1, 1):
        for value in range((1 << 24) - 8192, (1 << 24) + 8193):
            yield sign * value
        for exponent in range(0, 1101):
            value = 1 << exponent
            for delta in (-1, 0, 1):
                yield sign * (value + delta)
    # Every binary32 exponent, both signs, subnormal/normal mantissa edges and
    # midpoint tie rounding immediately above/below each sampled adjacent pair.
    for sign in (0, 1 << 31):
        for exponent in range(255):
            for mantissa in (0, 1, 2, 0x3FFFFF, 0x400000, 0x7FFFFE, 0x7FFFFF):
                bits = sign | (exponent << 23) | mantissa
                current = struct.unpack(">f", struct.pack(">I", bits))[0]
                yield current
                if exponent == 254 and mantissa == 0x7FFFFF:
                    continue
                following = struct.unpack(">f", struct.pack(">I", bits + 1))[0]
                middle = (current + following) / 2
                yield middle
                yield math.nextafter(middle, -math.inf)
                yield math.nextafter(middle, math.inf)
    for sign in (-1, 1):
        max_finite = float.fromhex("0x1.fffffep127")
        overflow_tie = max_finite + 2.0**103
        for value in (
            max_finite,
            overflow_tie,
            math.nextafter(overflow_tie, -math.inf),
            math.nextafter(overflow_tie, math.inf),
            1e300,
        ):
            yield sign * value

    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    yield from (
        0.0,
        -0.0,
        float("nan"),
        float("inf"),
        -float("inf"),
        True,
        False,
        None,
        "0",
        [],
        {},
        IntSubclass(1),
        FloatSubclass(1.0),
    )


class FakeFighterFloat32ExactTests(unittest.TestCase):
    def setUp(self):
        _cached_float_constructor.cache_clear()

    def test_ieee_boundaries_and_exact_integer_domain_match_original_codec(self):
        count = 0
        for value in boundary_cases():
            expected, actual = outcome(reference, value), outcome(_float32, value)
            if expected != actual:
                self.fail(
                    f"IEEE conversion differs for {value!r}: {expected!r} != {actual!r}"
                )
            count += 1
        self.assertEqual(count, 184746)

    def test_proven_exact_values_avoid_codec_and_keep_negative_zero(self):
        values = (-16777216, -1, 0, 1, 16777216, 0.0, -0.0, 1.0, -1.0)
        with patch(
            "wakfu_server.combat_fake_fighter.struct.pack", wraps=struct.pack
        ) as packed:
            results = tuple(_float32(value) for value in values)
            self.assertEqual(packed.call_count, 0)
        self.assertTrue(all(type(value) is float for value in results))
        self.assertEqual(results, tuple(float(value) for value in values))
        self.assertEqual(math.copysign(1.0, results[6]), -1.0)

    def test_nonexact_rounding_and_overflow_keep_original_codec_guards(self):
        values = (
            16777217,
            -16777217,
            1.0 + 2.0**-24,
            math.nextafter(1.0 + 2.0**-24, math.inf),
            2.0**-150,
            1e300,
        )
        expected = tuple(outcome(reference, value) for value in values)
        with patch(
            "wakfu_server.combat_fake_fighter.struct.pack", wraps=struct.pack
        ) as packed:
            actual = tuple(outcome(_float32, value) for value in values)
            self.assertGreaterEqual(packed.call_count, len(values))
        self.assertEqual(actual, expected)

    def test_cached_plan_uses_content_and_returns_fresh_mutable_constructor(self):
        definition = {
            "type": "FAKE_FIGHTER",
            "native_type_id": 15,
            "native_class": "bcQ",
            "raw_bdh": [-1.0, -1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 6.0, -1.0],
        }
        cached_plan = _fake_fighter_constructor_plan(definition)
        with patch(
            "wakfu_server.combat_fake_fighter._plain_float_constructor",
            return_value=None,
        ):
            reference_plan = _fake_fighter_constructor_plan(definition)
        self.assertEqual(cached_plan, reference_plan)
        first = fake_fighter_constructor(definition)
        self.assertEqual(_cached_float_constructor.cache_info().misses, 1)
        first["kind"] = 123
        first["characteristic_ids"] = (20,)

        second = fake_fighter_constructor(definition)
        self.assertIsNot(first, second)
        self.assertEqual(second["kind"], -1)
        self.assertEqual(second["characteristic_ids"], ())
        self.assertEqual(_cached_float_constructor.cache_info().hits, 2)

        # In-place prototype mutation changes the packed content key.
        definition["raw_bdh"][0] = 3.0
        changed = fake_fighter_constructor(definition)
        self.assertEqual(changed["kind"], 3)
        self.assertEqual(_cached_float_constructor.cache_info().misses, 2)

    def test_binary64_cache_key_keeps_signed_zero_and_native_prototype_guards(self):
        definition = {
            "type": "FAKE_FIGHTER",
            "native_type_id": 15,
            "native_class": "bcQ",
            "raw_bdh": [-1.0, -1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 6.0, -1.0],
        }
        positive = _plain_float_constructor(definition, definition["raw_bdh"])
        definition["raw_bdh"][2] = -0.0
        negative = _plain_float_constructor(definition, definition["raw_bdh"])
        self.assertEqual(math.copysign(1.0, positive[0][2]), 1.0)
        self.assertEqual(math.copysign(1.0, negative[0][2]), -1.0)
        self.assertEqual(_cached_float_constructor.cache_info().misses, 2)

        definition["native_class"] = "not-the-native-prototype"
        with self.assertRaisesRegex(ValueError, "prototype"):
            fake_fighter_constructor(definition)

    def test_custom_mappings_and_sequences_keep_legacy_callback_path(self):
        class CustomList(list):
            def __init__(self, values):
                super().__init__(values)
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                return super().__iter__()

        class CustomMapping(dict):
            def __init__(self, values):
                super().__init__(values)
                self.reads = []

            def get(self, key, *args):
                self.reads.append(key)
                return super().get(key, *args)

        raw = CustomList([-1.0, -1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 6.0, -1.0])
        definition = CustomMapping(
            {
                "type": "FAKE_FIGHTER",
                "native_type_id": 15,
                "native_class": "bcQ",
                "raw_bdh": raw,
            }
        )
        result = fake_fighter_constructor(definition)
        self.assertEqual(result["kind"], -1)
        self.assertGreater(raw.iterations, 0)
        self.assertTrue(definition.reads)
        self.assertEqual(_cached_float_constructor.cache_info().currsize, 0)

        class IntSubclass(int):
            pass

        typed_flag = {
            "type": "FAKE_FIGHTER",
            "native_type_id": IntSubclass(15),
            "native_class": "bcQ",
            "raw_bdh": [-1.0, -1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 6.0, -1.0],
        }
        self.assertEqual(fake_fighter_constructor(typed_flag)["kind"], -1)
        self.assertEqual(_cached_float_constructor.cache_info().currsize, 0)

    def test_invalid_float_constructor_inputs_fail_without_cache_entries(self):
        base = {
            "type": "FAKE_FIGHTER",
            "native_type_id": 15,
            "native_class": "bcQ",
            "raw_bdh": [-1.0, -1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 6.0, -1.0],
        }
        for value in (float("nan"), float("inf"), -float("inf"), 1e300):
            with self.subTest(value=value), self.assertRaises(ValueError):
                raw = list(base["raw_bdh"])
                raw[0] = value
                fake_fighter_constructor({**base, "raw_bdh": raw})
        self.assertEqual(_cached_float_constructor.cache_info().currsize, 0)


if __name__ == "__main__":
    unittest.main()
