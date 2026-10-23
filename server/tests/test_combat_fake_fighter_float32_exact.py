"""Exact faW binary32 fast paths retain original IEEE and failure behavior."""
import math
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_fake_fighter import _float32


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


if __name__ == "__main__":
    unittest.main()
