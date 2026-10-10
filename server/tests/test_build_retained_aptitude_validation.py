"""Partial build updates validate retained aptitude data before persistence."""
import copy
import unittest

from wakfu_server import builds
from wakfu_server.wire import proto_field


def metadata(level):
    return b"".join(
        proto_field(t, v)
        for t, v in [(8, 0), (18, b"Default"), (24, level), (56, 1), (64, 1)]
    )


class BuildRetainedAptitudeValidationTests(unittest.TestCase):
    def character(self):
        aptitude = proto_field(24, (1 << 64) - 1) + proto_field(
            34, proto_field(8, 1) + proto_field(16, 10)
        )
        return {
            "level": 200,
            "breed": 8,
            "builds": {
                0: {
                    "sheet": metadata(50).hex(),
                    "equipment": "",
                    "deck": "",
                    "aptitudes": aptitude.hex(),
                }
            },
        }

    def test_lowered_cap_rejects_retained_allocation_without_mutating_source(self):
        character = self.character()
        before = copy.deepcopy(character)
        with self.assertRaisesRegex(ValueError, "budget"):
            builds.validated_saved_blobs(
                character,
                0,
                dict(sheet=metadata(20), equipment=b"", deck=b"", aptitudes=b""),
            )
        self.assertEqual(character, before)

    def test_partial_update_preserves_valid_allocation(self):
        character = self.character()
        merged = builds.validated_saved_blobs(
            character,
            0,
            dict(sheet=metadata(60), equipment=b"", deck=b"", aptitudes=b""),
        )
        self.assertEqual(
            merged["aptitudes"], bytes.fromhex(character["builds"][0]["aptitudes"])
        )

    def test_lowered_cap_accepts_explicit_reset_in_same_update(self):
        character = self.character()
        merged = builds.validated_saved_blobs(
            character,
            0,
            dict(
                sheet=metadata(20),
                equipment=b"",
                deck=b"",
                aptitudes=builds.EMPTY_APTITUDES,
            ),
        )
        self.assertEqual(merged["aptitudes"], builds.EMPTY_APTITUDES)
