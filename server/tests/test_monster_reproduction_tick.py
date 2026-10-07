import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_reproduction
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.monster_wander import edge_index


class MonsterReproductionTickTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.map_id, self.instance_id, self.group_id = 1134, 0, 78101
        self.location = (self.map_id, self.instance_id)
        self.groups = PersistentGroups(self.store)
        self.members = [self._member(-78101, 4, 0), self._member(-78102, 4, 4)]
        self.key = self.groups.register(*self.location, self.group_id, self.members)
        self.indexed = edge_index(
            [
                ((0, 0, 0), (1, 0, 0)),
                ((4, 0, 0), (5, 0, 0)),
            ]
        )
        self._set_policy()

    def _member(self, actor_id, reference, x):
        return owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            actor_id,
            map_id=self.map_id,
            x=x,
            y=0,
            z=0,
        )

    def _set_policy(
        self,
        *,
        birth=1.0,
        new_group=0.0,
        max_members=8,
        interval=60000,
        birth_stage_decay=0.5,
        max_zone_members=128,
        max_zone_groups=32
    ):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                (
                    Jsonb(
                        {
                            "interval_ms": interval,
                            "birth_probability": birth,
                            "birth_stage_decay": birth_stage_decay,
                            "new_group_probability": new_group,
                            "max_members": max_members,
                            "max_zone_members": max_zone_members,
                            "max_zone_groups": max_zone_groups,
                        }
                    ),
                ),
            )

    def _emit(self, packets):
        return lambda map_id, instance_id, opcode, body: packets.append(
            (map_id, instance_id, opcode, body)
        )

    def _tick(
        self,
        now,
        packets,
        *,
        locations=None,
        previous=(),
        excluded=(),
        emit=None,
        generation="reproduction-world"
    ):
        return monster_reproduction.tick(
            self.store,
            {self.location} if locations is None else locations,
            previous,
            generation=generation,
            now_ms=now,
            indexed_by_map={self.map_id: self.indexed},
            players=[],
            excluded_ids=set(excluded),
            emit=emit or self._emit(packets),
        )

    def _group(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s "
                "AND group_id=%s",
                self.key,
            ).fetchone()

    def _unpublished(self):
        return monster_reproduction.unpublished(self.store, *self.location)

    def _packet_ids(self, body, *, remove):
        if remove:
            count = body[2]
            self.assertEqual(3 + count * 9, len(body))
            return [
                struct.unpack_from(">Bq", body, 3 + index * 9)[1]
                for index in range(count)
            ]
        count = body[1]
        offset, ids = 2, []
        for _ in range(count):
            _actor_type, actor_id, size = struct.unpack_from(">BqH", body, offset)
            ids.append(actor_id)
            offset += 11 + size
        self.assertEqual(len(body), offset)
        return ids

    def test_tick_coalesces_births_and_publishes_remove_then_latest_roster(self):
        packets = []
        self._tick(0, packets)
        with patch.object(monster_reproduction.secrets, "randbelow", return_value=0):
            self._tick(60000, packets)
        self.assertEqual([12304, 12608], [packet[2] for packet in packets])
        ids_removed = self._packet_ids(packets[0][3], remove=True)
        ids_spawned = self._packet_ids(packets[1][3], remove=False)
        self.assertEqual(set(ids_removed), set(ids_spawned))
        self.assertEqual(4, len(ids_spawned))
        self.assertTrue({m["id"] for m in self.members}.issubset(ids_spawned))
        self.assertEqual(4, len(self._group()["members"]))
        self.assertEqual(2, self._group()["revision"])
        self.assertEqual([], self._unpublished())

    def test_stale_ack_does_not_mark_event_published(self):
        # Create an outbox event through the actual due-cycle transaction.
        packets = []
        self._tick(0, packets)

        def fail_emit(*_):
            raise OSError("hold publication for stale-ack test")

        with patch.object(monster_reproduction.secrets, "randbelow", return_value=0):
            with self.assertRaisesRegex(OSError, "hold publication"):
                self._tick(60000, packets, emit=fail_emit)
        event = self._unpublished()[0]
        current = self._group()
        moved = [dict(member) for member in current["members"]]
        moved[0]["x"] += 10
        self.assertTrue(self.groups.move_members(self.key, current["members"], moved))
        event["current_revision"] = current["revision"]
        self.assertFalse(monster_reproduction.acknowledge(self.store, event))
        self.assertEqual(2, len(self._unpublished()))

    def test_fighting_and_harvesting_defer_publication_and_retry(self):
        packets = []
        self._tick(0, packets)

        def fail_emit(*_):
            raise OSError("hold publication for lease test")

        with patch.object(monster_reproduction.secrets, "randbelow", return_value=0):
            with self.assertRaisesRegex(OSError, "hold publication"):
                self._tick(60000, packets, emit=fail_emit)
        self.assertEqual(2, len(self._unpublished()))

        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') " "RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(self.key, "reproduction-fight", fight_id)
        self._tick(61000, packets)
        self.assertEqual([], packets)
        self.assertEqual(2, len(self._unpublished()))
        self.assertTrue(self.groups.finish(lease, defeated=False))

        # A harvesting sibling also holds back the whole roster snapshot.
        self._tick(62000, packets, excluded={self.members[1]["id"]})
        self.assertEqual([], packets)
        self.assertEqual(2, len(self._unpublished()))
        self._tick(63000, packets)
        self.assertEqual([12304, 12608], [row[2] for row in packets])
        self.assertEqual([], self._unpublished())

    def test_active_clock_pauses_when_absent_or_restarted_and_babies_have_no_clock(
        self,
    ):
        packets = []
        self._tick(0, packets)
        self._tick(30000, packets)
        self._tick(90000, packets, locations=set(), previous={self.location})
        self._tick(500000, packets, generation="new-restart")
        self.assertEqual([], packets)
        with self.store.connection() as db:
            timers = db.execute(
                "SELECT monster_id,remaining_ms,last_active_ms,due FROM "
                "monster_reproduction_timers WHERE map_id=%s AND instance_id=%s",
                self.location,
            ).fetchall()
        self.assertEqual(2, len(timers))
        self.assertTrue(
            all(row["remaining_ms"] == 30000 and not row["due"] for row in timers)
        )
        self._tick(529999, packets, generation="new-restart")
        self.assertEqual([], packets)
        with patch.object(monster_reproduction.secrets, "randbelow", return_value=0):
            self._tick(530000, packets, generation="new-restart")
        self.assertEqual([12304, 12608], [row[2] for row in packets])

        # After birth, newborn tier-zero members are excluded from clock seeding.
        babies = [member for member in self._group()["members"] if member["ref"] == 6]
        self.assertTrue(babies)
        monster_reproduction.observe(
            self.store,
            *self.location,
            present=True,
            generation="new-restart",
            now_ms=590000
        )
        with self.store.connection() as db:
            baby_timers = db.execute(
                "SELECT count(*) AS count FROM monster_reproduction_timers "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=ANY(%s)",
                (*self.location, [baby["id"] for baby in babies]),
            ).fetchone()["count"]
        self.assertEqual(0, baby_timers)

    def test_emission_failure_retains_outbox_for_exact_packet_retry(self):
        packets = []
        self._tick(0, packets)

        def fail(*_):
            raise OSError("injected reproduction emit failure")

        with patch.object(monster_reproduction.secrets, "randbelow", return_value=0):
            with self.assertRaisesRegex(OSError, "injected reproduction emit failure"):
                self._tick(60000, packets, emit=fail)
        self.assertEqual(2, len(self._unpublished()))
        retry = []
        self._tick(70000, retry)
        self.assertEqual([12304, 12608], [row[2] for row in retry])
        self.assertEqual([], self._unpublished())


if __name__ == "__main__":
    unittest.main()
