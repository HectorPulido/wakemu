import struct
import unittest

from wakfu_server.combat.combat_state import Actor, Fight
from wakfu_server.combat.combat_instance_publication import (
    InstancePublicationTracker,
    PublicationLease,
)
from wakfu_server.combat.combat_geometry_snapshot import source_snapshot
from wakfu_server.maps.proto_dungeon import encode
from wakfu_server.combat.fight_checkpoint_store import snapshot


class FightCheckpointInstanceContextTests(unittest.TestCase):
    def test_published_actor_difficulty_is_saved_without_live_lease(self):
        actors = (
            Actor(24, 1, (1, 0, 0), 80, 6, 3, 90, 20),
            Actor(34, 0, (2, 0, 0), 100, 6, 3, 100, 20, 7, True),
        )
        fight = Fight(
            281,
            actors,
            {(1, 0, 0), (2, 0, 0)},
            {0: {(2, 0, 0)}, 1: {(1, 0, 0)}},
        )
        scope = (7, "generation", 34, 1385, 0)
        context = encode({"difficulty_level": 2})
        payload = b"".join(
            struct.pack(">H", len(block)) + block
            for block in (b"actor", b"", b"\0\0", context)
        )
        frame = struct.pack(">IH", 6 + len(payload), 13974) + payload
        tracker = InstancePublicationTracker()
        tracker.after_write(frame, scope)
        self.assertTrue(
            tracker.bind_encounter(fight, scope, npc_ids=(24,), player_id=34)
        )
        self.assertIsInstance(fight.native_instance_publication_lease, PublicationLease)

        state = snapshot(fight)

        self.assertEqual(
            state["native_instance_difficulty_snapshots"],
            {
                "24": {
                    "actor_id": 24,
                    "difficulty": 2,
                    "source": "fBg.drG.fBf.GN",
                },
                "34": {
                    "actor_id": 34,
                    "difficulty": None,
                    "source": "fBg.drG.Optional.empty",
                },
            },
        )
        self.assertNotIn("native_instance_publication_lease", state)

        # Tactical AI and transaction source guards use the same strict state
        # projection; a live publication lease cannot poison those previews.
        ai_state = source_snapshot(fight)
        self.assertNotIn("native_instance_publication_lease", ai_state)
        self.assertEqual(
            ai_state["native_instance_difficulty_snapshots"],
            state["native_instance_difficulty_snapshots"],
        )


if __name__ == "__main__":
    unittest.main()
