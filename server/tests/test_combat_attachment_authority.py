"""Persisted native slots are independently authorized before owned combat."""
import unittest
from copy import deepcopy

from wakfu_server.combat_attachment_authority import CombatAttachmentAuthority
from wakfu_server.items.sublimation_eligibility import CLIENT_JAR_SHA256
from wakfu_server.wire import proto_field


def pattern(reference, kind, colors=()):
    return dict(
        reference=reference,
        pattern_type=kind,
        slot_colors=list(colors),
        client_jar_sha256=CLIENT_JAR_SHA256,
        enabled=True,
    )


def target(reference, kind, rarity):
    return dict(
        reference=reference,
        pattern_type=kind,
        rarity_code=rarity,
        item_level=20,
        client_jar_sha256=CLIENT_JAR_SHA256,
        enabled=True,
    )


def shard(colors, basic=11, special=12):
    return (
        b"".join(
            proto_field(10, proto_field(80, index) + proto_field(96, color))
            for index, color in enumerate(colors)
        )
        + proto_field(24, basic)
        + proto_field(32, special)
    )


class CombatAttachmentAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.patterns = [
            pattern(11, "BASIC", [1, 2]),
            pattern(12, "EPIC"),
            pattern(13, "RELIC"),
        ]
        self.targets = [target(100, "EPIC", 7), target(101, "RELIC", 5)]
        self.authority = CombatAttachmentAuthority(self.patterns, self.targets)
        self.gear = dict(reference=100, quantity=1)

    def test_contiguous_order_and_native_white_socket(self):
        for colors, expected in (
            ([3, 1, 2], True),
            ([1, 3, 2], False),
            ([2, 1], False),
            ([1, 4], True),
            ([0, 2], False),
        ):
            with self.subTest(colors=colors):
                self.assertIs(
                    self.authority(self.gear, shard(colors), 11, 24), expected
                )

    def test_special_uses_rarity_without_sockets_and_coexists_with_basic(self):
        empty = shard([])
        self.assertTrue(self.authority(self.gear, empty, 12, 32))
        self.assertFalse(self.authority(self.gear, empty, 11, 24))
        both = shard([1, 2])
        self.assertTrue(self.authority(self.gear, both, 11, 24))
        self.assertTrue(self.authority(self.gear, both, 12, 32))
        self.assertFalse(self.authority(dict(reference=101, quantity=1), both, 12, 32))
        relic = shard([], special=13)
        self.assertTrue(self.authority(dict(reference=101, quantity=1), relic, 13, 32))

    def test_missing_disabled_mismatched_and_stacked_sources_cannot_activate(self):
        disabled = deepcopy(self.patterns)
        disabled[0]["enabled"] = False
        authority = CombatAttachmentAuthority(disabled, self.targets)
        self.assertFalse(authority(self.gear, shard([1, 2]), 11, 24))
        self.assertFalse(self.authority(self.gear, shard([], special=999), 999, 32))
        self.assertFalse(self.authority(dict(self.gear, quantity=2), shard([]), 12, 32))
        with self.assertRaisesRegex(ValueError, "persisted native slot"):
            self.authority(self.gear, shard([]), 13, 32)

    def test_snapshot_is_detached_and_corrupt_provenance_is_rejected(self):
        self.patterns[0]["slot_colors"][0] = 3
        self.targets[0]["pattern_type"] = "RELIC"
        self.assertTrue(self.authority(self.gear, shard([1, 2]), 11, 24))
        self.assertTrue(self.authority(self.gear, shard([]), 12, 32))
        with self.assertRaises(TypeError):
            self.authority.patterns[11]["tag"] = 32
        bad = pattern(20, "EPIC")
        bad["client_jar_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Malformed"):
            CombatAttachmentAuthority([bad], [])
        with self.assertRaisesRegex(ValueError, "identity"):
            CombatAttachmentAuthority([pattern(11, "EPIC"), pattern(11, "EPIC")], [])

    def test_ready_captures_one_detached_sql_authority_only_for_equipped_attachments(
        self,
    ):
        from contextlib import contextmanager
        from unittest.mock import patch
        from wakfu_server.combat_attachment_authority import for_characters

        item = dict(uid=500, reference=100, quantity=1, shard_state=shard([1, 2]))
        character = dict(
            active_build_index=0,
            inventory_items=[item],
            builds={
                0: dict(
                    equipment=(
                        proto_field(10, proto_field(8, 500) + proto_field(16, 10))
                    ).hex()
                )
            },
        )
        calls = []

        class Store:
            @contextmanager
            def connection(self):
                calls.append("connection")
                yield object()

        store = Store()
        with patch.object(
            CombatAttachmentAuthority, "from_database", return_value=self.authority
        ) as load:
            empty = dict(character, builds={0: dict(equipment="")})
            self.assertIsNone(for_characters(store, {1: empty}))
            load.assert_not_called()
            captured = for_characters(store, {1: character, 2: character})
            self.assertIs(captured, self.authority)
            load.assert_called_once()
        self.assertEqual(calls, ["connection"])
        self.assertTrue(captured(item, item["shard_state"], 11, 24))

    def test_noncontiguous_socket_positions_are_not_repaired(self):
        state = proto_field(10, proto_field(80, 1) + proto_field(96, 1)) + proto_field(
            24, 11
        )
        with self.assertRaisesRegex(ValueError, "positions"):
            self.authority(self.gear, state, 11, 24)
