import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import monster_maturation
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonsterMaturationTickTests(PostgresCase):
    def setUp(self):
        super().setUp()
        # Keep publication tests short; the default interval itself is tested
        # against migration 035 in the clock suite.
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{interval_ms}','60000'::jsonb) "
                "WHERE name='monster_maturation'"
            )
        self.groups = PersistentGroups(self.store)
        self.map_id = 1134
        self.instance_id = 0
        self.group_id = 88201
        self.location = (self.map_id, self.instance_id)
        self.members = [
            self._member(2, -88201, 0),
            self._member(39, -88202, 1),
        ]
        self.key = self.groups.register(*self.location, self.group_id, self.members)

    def _member(self, reference, actor_id, x):
        return owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            actor_id,
            map_id=self.map_id,
            x=x,
            y=0,
            z=0,
        )

    def _emit_all(self, packets):
        return lambda map_id, instance_id, opcode, body: packets.append(
            (map_id, instance_id, opcode, body)
        )

    def _unpack_ids(self, body, *, remove):
        if remove:
            count = body[2]
            entries = body[3:]
            self.assertEqual(9 * count, len(entries))
            return [
                struct.unpack_from(">Bq", entries, index * 9)[1]
                for index in range(count)
            ]
        count = body[1]
        offset = 2
        actor_ids = []
        for _ in range(count):
            _actor_type, actor_id, size = struct.unpack_from(">BqH", body, offset)
            offset += 11
            actor_ids.append(actor_id)
            offset += size
        self.assertEqual(len(body), offset)
        return actor_ids

    def _tick(self, now_ms, packets, *, locations=None, previous=(), excluded_ids=()):
        if locations is None:
            locations = {self.location}
        return monster_maturation.tick(
            self.store,
            locations,
            previous,
            generation="maturation-world",
            now_ms=now_ms,
            excluded_ids=set(excluded_ids),
            emit=self._emit_all(packets),
        )

    def _group(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                self.key,
            ).fetchone()

    def test_active_growth_emits_remove_then_snapshot_once_for_whole_group(self):
        packets = []
        self._tick(0, packets)
        self.assertEqual([], packets)
        with patch.object(monster_maturation.secrets, "randbelow", return_value=0):
            self._tick(60000, packets)

        self.assertEqual([12304, 12608], [packet[2] for packet in packets])
        self.assertEqual(
            {self.location}, {(packet[0], packet[1]) for packet in packets}
        )
        removed_ids = self._unpack_ids(packets[0][3], remove=True)
        spawned_ids = self._unpack_ids(packets[1][3], remove=False)
        self.assertEqual({member["id"] for member in self.members}, set(removed_ids))
        self.assertEqual(set(removed_ids), set(spawned_ids))
        group = self._group()
        self.assertEqual(2, group["revision"])
        self.assertEqual({1}, {member["ref"] for member in group["members"]})
        self.assertEqual(
            [],
            monster_maturation.unpublished(self.store, self.map_id, self.instance_id),
        )

    def test_absent_location_pauses_clock_without_charging_offline_gap(self):
        packets = []
        self._tick(0, packets)
        self._tick(50000, packets, locations=set(), previous={self.location})
        self._tick(100000, packets)
        self.assertEqual([], packets)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT remaining_ms,last_active_ms FROM monster_maturation_timers "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (*self.location, self.members[0]["id"]),
            ).fetchone()
        self.assertEqual(60000, row["remaining_ms"])
        self.assertEqual(100000, row["last_active_ms"])
        with patch.object(monster_maturation.secrets, "randbelow", return_value=0):
            self._tick(160000, packets)
        self.assertEqual([12304, 12608], [packet[2] for packet in packets])

    def test_fighting_group_keeps_unpublished_outbox_for_later_retry(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-world",
            now_ms=0,
        )
        tickets = monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-world",
            now_ms=60000,
        )
        monster_maturation.attempt(
            self.store,
            tickets[0],
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(self.key, "fight-maturation", fight_id)
        packets = []
        self._tick(70000, packets)
        self.assertEqual([], packets)
        pending = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )
        self.assertEqual(
            [tickets[0]["monster_id"]], [row["monster_id"] for row in pending]
        )
        self.assertEqual("fighting", pending[0]["status"])

        self.assertTrue(self.groups.finish(lease, defeated=False))
        with patch.object(monster_maturation.secrets, "randbelow", return_value=0):
            self._tick(80000, packets)
        self.assertEqual([12304, 12608], [packet[2] for packet in packets])
        self.assertEqual(
            [],
            monster_maturation.unpublished(self.store, self.map_id, self.instance_id),
        )

    def test_sibling_harvest_defers_group_publication_until_member_is_free(self):
        packets = []
        self._tick(0, packets, excluded_ids={self.members[1]["id"]})
        with patch.object(monster_maturation.secrets, "randbelow", return_value=0):
            self._tick(60000, packets, excluded_ids={self.members[1]["id"]})
        self.assertEqual([], packets)
        pending = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )
        self.assertEqual(
            [self.members[0]["id"]], [event["monster_id"] for event in pending]
        )
        roster = {member["id"]: member for member in self._group()["members"]}
        self.assertEqual(1, roster[self.members[0]["id"]]["ref"])
        self.assertEqual(39, roster[self.members[1]["id"]]["ref"])

        # The committed growth waits while the sibling harvest remains active.
        self._tick(61000, packets, excluded_ids={self.members[1]["id"]})
        self.assertEqual([], packets)
        self.assertEqual(
            1,
            len(
                monster_maturation.unpublished(
                    self.store, self.map_id, self.instance_id
                )
            ),
        )

        # Once the occupation clears, publish the current complete roster and ack.
        self._tick(62000, packets)
        self.assertEqual([12304, 12608], [packet[2] for packet in packets])
        removed = self._unpack_ids(packets[0][3], remove=True)
        spawned = self._unpack_ids(packets[1][3], remove=False)
        self.assertEqual(set(removed), set(spawned))
        self.assertEqual({member["id"] for member in self.members}, set(removed))
        self.assertEqual(
            [],
            monster_maturation.unpublished(self.store, self.map_id, self.instance_id),
        )

    def test_emit_failure_preserves_outbox_and_retry_republishes(self):
        packets = []
        self._tick(0, packets)

        def fail_emit(*_packet):
            raise OSError("injected emitter failure")

        with patch.object(monster_maturation.secrets, "randbelow", return_value=0):
            with self.assertRaisesRegex(OSError, "injected emitter failure"):
                monster_maturation.tick(
                    self.store,
                    {self.location},
                    {self.location},
                    generation="maturation-world",
                    now_ms=60000,
                    excluded_ids=set(),
                    emit=fail_emit,
                )
        self.assertEqual(
            2,
            len(
                monster_maturation.unpublished(
                    self.store, self.map_id, self.instance_id
                )
            ),
        )
        retry = []
        self._tick(70000, retry)
        self.assertEqual([12304, 12608], [packet[2] for packet in retry])
        self.assertEqual(
            [],
            monster_maturation.unpublished(self.store, self.map_id, self.instance_id),
        )

    def test_register_seed_accepts_growth_and_movement_but_rejects_forged_stats(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-world",
            now_ms=0,
        )
        tickets = monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-world",
            now_ms=60000,
        )
        ticket = next(
            row for row in tickets if row["monster_id"] == self.members[0]["id"]
        )
        monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        current = self._group()["members"]
        moved = [dict(member) for member in current]
        moved[0]["x"] = 12
        self.assertTrue(self.groups.move_members(self.key, current, moved))
        self.assertEqual(self.key, self.groups.register_seed(*self.key, self.members))

        forged = [dict(member) for member in self._group()["members"]]
        forged[0]["hp"] -= 1
        with self.store.connection() as db:
            from psycopg.types.json import Jsonb

            db.execute(
                "UPDATE combat_groups SET members=%s WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (Jsonb(forged), *self.key),
            )
        with self.assertRaisesRegex(
            ValueError, "Conflicting existing group seed identity or stats"
        ):
            self.groups.register_seed(*self.key, self.members)


if __name__ == "__main__":
    unittest.main()
