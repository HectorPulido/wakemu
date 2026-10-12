"""Native-session binding regressions; no game engine or DB."""
import json
from pathlib import Path
import unittest
from wakfu_server.combat_instance_context import (
    PublishedInstanceContext,
    npc_snapshot,
    bind_fight_npc_snapshots,
    capture_publication,
)
from types import SimpleNamespace
from wakfu_server.maps.proto_dungeon import encode


class PublishedContextTests(unittest.TestCase):
    def published(self, level=2):
        return PublishedInstanceContext(17, 1385, encode({"difficulty_level": level}))

    def snapshot(self, published, **kwargs):
        return npc_snapshot(
            99,
            native_actor_class=kwargs.get("native_actor_class", "bje"),
            actor_instance_id=kwargs.get("actor_instance_id", 1385),
            session_actor_id=kwargs.get("session_actor_id", 17),
            published=published,
        )

    def test_real_native_GN_levels_one_to_ten(self):
        rows = [
            json.loads(s)
            for s in (
                Path(__file__).parent
                / "fixtures/native_monster_recovery/native-producer-oracle.jsonl"
            )
            .read_text()
            .splitlines()
        ][1:]
        self.assertEqual(len(rows), 10)
        for row in rows:
            self.assertEqual(
                self.snapshot(self.published(row["difficulty_level"])).difficulty,
                row["native_GN"],
            )

    def test_actual_clean_bootstrap_has_two_not_zero(self):
        p = PublishedInstanceContext(
            17, 1385, bytes.fromhex("0800100218002001280030004000")
        )
        self.assertEqual(self.snapshot(p).difficulty, 2)

    def test_missing_context_never_loads_default(self):
        with self.assertRaises(ValueError):
            self.snapshot(None)

    def test_cross_session_and_instance_are_rejected(self):
        for kw in ({"session_actor_id": 18}, {"actor_instance_id": 527}):
            with self.assertRaises(ValueError):
                self.snapshot(self.published(), **kw)

    def test_unknown_actor_class_is_not_assumed_bje(self):
        for name in ("big", "bjo", "subclass", ""):
            with self.assertRaises(ValueError):
                self.snapshot(self.published(), native_actor_class=name)

    def test_mutable_payload_is_not_accepted_as_frozen_authority(self):
        with self.assertRaises(ValueError):
            PublishedInstanceContext(17, 1385, bytearray(self.published().payload))

    def test_atomic_fight_binding_requires_unanimous_published_contexts(self):
        fight = SimpleNamespace(actors={99: SimpleNamespace(id=99)})
        kw = dict(native_actor_classes={99: "bje"}, actor_instance_ids={99: 1385})
        with self.assertRaises(ValueError):
            bind_fight_npc_snapshots(
                fight, **kw, published_contexts=(self.published(2), self.published(3))
            )
        self.assertFalse(hasattr(fight, "native_instance_difficulty_snapshots"))
        returned = bind_fight_npc_snapshots(
            fight, **kw, published_contexts=(self.published(2),)
        )
        self.assertEqual(fight.native_instance_difficulty_snapshots[99].difficulty, 2)
        returned.clear()
        self.assertIn(99, fight.native_instance_difficulty_snapshots)

    def test_capture_actual_bootstrap_and_update_context(self):
        import struct

        context = self.published(7).payload
        bootstrap = b"".join(
            struct.pack(">H", len(b)) + b for b in (b"entity", b"", b"\0\0", context)
        )
        for mid, raw in (
            (13974, bootstrap),
            (13339, struct.pack(">qi", 1385, len(context)) + context),
        ):
            record = capture_publication(
                mid, raw, session_actor_id=17, instance_id=1385
            )
            self.assertEqual(self.snapshot(record).difficulty, 7)

    def test_invalid_publications_fail_without_default(self):
        import struct

        for mid, raw in (
            (13974, b""),
            (13974, b"\0\0" * 4 + b"x"),
            (13339, struct.pack(">qi", 527, 0)),
            (13339, struct.pack(">qi", 1385, -1)),
            (1, b""),
        ):
            with self.assertRaises(ValueError):
                capture_publication(mid, raw, session_actor_id=17, instance_id=1385)


if __name__ == "__main__":
    unittest.main()
