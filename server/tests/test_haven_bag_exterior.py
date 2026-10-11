"""Exterior lifecycle, native coordinates and visitor policy regressions."""
import struct
import unittest

from wakfu_server.haven_bag_exterior import ExteriorBags, can_visit, entity_id, spawn
from wakfu_server.haven_bag import HavenBagSession, entry_result
from wakfu_server.wire import captured_haven_bag_records


def actor(identity=10, account=5):
    return dict(
        id=identity,
        account_id=account,
        name="Owner",
        map_id=1134,
        instance_id=0,
        x=-9,
        y=-15,
        z=0,
        haven_bag=dict(
            owner_id=7,
            appearance_id=408,
            locked=False,
            access=dict(groups=[dict(group=0, rights=1)], characters=[]),
        ),
    )


class ExteriorBagTests(unittest.TestCase):
    def test_native_record_world_and_packed_position_agree(self):
        owner = actor()
        opcode, body = spawn(owner)
        self.assertEqual(opcode, 13664)
        uid, template, record = captured_haven_bag_records(body)[0]
        self.assertEqual((uid, template), (entity_id(owner), 3700))
        size = struct.unpack_from(">H", record, 16)[0]
        blob = record[18 : 18 + size]
        self.assertEqual(blob[:11], bytes.fromhex("02020000000b0300000018"))
        world, x, y, z, _, _ = struct.unpack_from(">qiihBB", blob, 25)
        self.assertEqual((world, x, y, z), (1134, -9, -15, 0))
        pos = struct.unpack_from(">q", record, 18 + size)[0]
        decoded = (
            (pos >> 28 & 262143) - 131071,
            (pos >> 10 & 262143) - 131071,
            (pos & 1023) - 511,
        )
        self.assertEqual(decoded, (x, y, z))
        self.assertNotIn(b"Manama", blob)

    def test_registry_scopes_entry_and_removal_to_current_lease(self):
        bags = ExteriorBags()
        owner, visitor = actor(), actor(11, 6)
        bags.publish("old", owner)
        bags.publish("current", owner)
        self.assertIsNone(bags.discard("old", owner["id"]))
        self.assertEqual(bags.resolve(visitor, owner["id"]), owner)
        self.assertEqual(len(bags.snapshots(visitor)), 1)
        visitor["map_id"] = 527
        self.assertEqual(bags.snapshots(visitor), [])
        with self.assertRaises(ValueError):
            bags.resolve(visitor, owner["id"])
        self.assertEqual(bags.discard("current", owner["id"])[1][0], 13082)
        self.assertEqual(bags.snapshots(owner), [])

    def test_public_visits_ignore_historical_room_restrictions(self):
        owner, visitor = actor(), actor(11, 6)
        self.assertTrue(can_visit(visitor, owner))
        owner["haven_bag"]["access"]["characters"] = [dict(id=11, rights=0)]
        self.assertTrue(can_visit(visitor, owner))
        owner["haven_bag"]["locked"] = True
        self.assertTrue(can_visit(visitor, owner))
        self.assertTrue(can_visit(actor(12, 5), owner))

    def test_shared_account_and_foreign_session_return_restore_own_state(self):
        owner, visitor = actor(), actor(11, 6)
        visitor["haven_bag"]["owner_id"] = 11
        session = HavenBagSession(visitor, owner=owner)
        self.assertFalse(session.is_owner)
        self.assertEqual(session.inside["instance_id"], 7)
        self.assertTrue(session.inside["haven_bag_visitor"])
        self.assertTrue(session.owns(session.inside))
        from wakfu_server.haven_bag_transfer import can_transfer

        self.assertFalse(can_transfer(session, session.inside, fight_active=False))
        self.assertEqual(session.leave(session.inside), visitor)
        own = HavenBagSession(owner)
        self.assertEqual(own.inside["instance_id"], 7)
        self.assertTrue(own.is_owner)

    def test_foreign_success_requires_native_owner_serialization(self):
        with self.assertRaises(ValueError):
            entry_result(success=True, own=False)
        self.assertEqual(entry_result(success=False, own=False), b"\x00" * 6)


if __name__ == "__main__":
    unittest.main()
