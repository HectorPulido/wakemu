import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.combat.combat_world_group_cleanup import defeated_snapshot


class WorldGroupCleanupTests(PostgresCase):
    def add(
        self,
        db,
        group,
        identities,
        *,
        map_id=527,
        instance=0,
        status="defeated",
        revision=8
    ):
        members = [
            dict(id=identity, map_id=map_id, instance_id=instance)
            for identity in identities
        ]
        db.execute(
            "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,revision) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (map_id, instance, group, Jsonb(members), status, revision),
        )

    @staticmethod
    def identities(packets):
        found = []
        for opcode, body in packets:
            assert opcode == 12304 and body[:2] == bytes(2)
            for offset in range(body[2]):
                kind, identity = struct.unpack_from(">Bq", body, 3 + offset * 9)
                assert kind == 1
                found.append(identity)
        return found

    def test_additive_world_replay_removes_only_current_scoped_tombstones(self):
        with self.store.connection() as db:
            self.add(db, 1, [-100, -101])
            self.add(db, 2, [-102], status="available")
            self.add(db, 3, [-103], instance=900)
            self.add(db, 4, [-104], map_id=528)
            self.assertEqual(
                self.identities(defeated_snapshot(db, 527, 0)), [-100, -101]
            )
            self.assertEqual(self.identities(defeated_snapshot(db, 527, 900)), [-103])
            reopened = self.reopen()
            with reopened.connection() as persisted:
                self.assertEqual(defeated_snapshot(persisted, 527, 0), ())
        with self.reopen().connection() as persisted:
            self.assertEqual(
                self.identities(defeated_snapshot(persisted, 527, 0)), [-100, -101]
            )

    def test_terminal_lease_revision_fence_does_not_delete_respawn_or_replacement(self):
        lease = ((527, 0, 1), "original-generation", 106, 7)
        with self.store.connection() as db:
            self.add(db, 1, [-100])
            self.assertEqual(
                self.identities(defeated_snapshot(db, 527, 0, lease=lease)), [-100]
            )
            db.execute("UPDATE combat_groups SET revision=10")
            self.assertEqual(defeated_snapshot(db, 527, 0, lease=lease), ())
            db.execute("UPDATE combat_groups SET revision=8,status='available'")
            self.assertEqual(defeated_snapshot(db, 527, 0, lease=lease), ())
            with self.assertRaises(ValueError):
                defeated_snapshot(db, 527, 900, lease=lease)

    def test_native_limit_splits_large_world_cleanup_without_player_removal(self):
        with self.store.connection() as db:
            self.add(db, 1, list(range(-1, -258, -1)))
            packets = defeated_snapshot(db, 527, 0)
            self.assertEqual([body[2] for _, body in packets], [255, 2])
            self.assertEqual(self.identities(packets), list(range(-1, -258, -1)))
            self.add(db, 2, [100])
            with self.assertRaises(ValueError):
                defeated_snapshot(db, 527, 0)
