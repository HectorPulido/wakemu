from prepared_mob_fixtures import prepared_birth
from wakfu_server.npc_actor_identity import MINIMUM
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_reproduction, ecology_mobs
from types import SimpleNamespace
import threading
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.monster_wander import edge_index


class MonsterReproductionTickTests(PostgresCase):
    def setUp(self):
        super().setUp()
        # These tests exercise World commits/publication on explicit synthetic cells.
        # Autonomous clock pacing lives in Rust lifecycle_contract/clock_cases.rs.
        habitat = patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=True,
        )
        habitat.start()
        self.addCleanup(habitat.stop)
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

    def _commit_due_birth_fixtures(self):
        """Apply two explicit Rust due tickets through the real World authority."""
        for parent in self.members:
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO monster_reproduction_timers"
                    "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                    "VALUES(%s,%s,%s,%s,0,true,1)",
                    (self.map_id, self.instance_id, parent["id"], parent["ref"]),
                )
            ticket = dict(
                map_id=self.map_id,
                instance_id=self.instance_id,
                group_id=self.group_id,
                monster_id=parent["id"],
                reference=parent["ref"],
                cycle=1,
            )
            result = monster_reproduction.attempt(
                self.store,
                ticket,
                present=True,
                indexed=self.indexed,
                players=[],
                excluded_ids=[],
                draw=0.0,
                group_draw=0.99,
                prepared=prepared_birth(
                    self.store,
                    ticket,
                    destination=(1, 0, 0) if parent["id"] == -78101 else (5, 0, 0),
                    actor_id=-(MINIMUM + abs(parent["id"])),
                ),
            )
            self.assertIsNotNone(result)
            self.assertFalse(result["duplicate"])

    def _publish(self, packets, *, excluded=(), emit=None):
        world = SimpleNamespace(
            snapshot=lambda: [
                dict(
                    id=7,
                    map_id=self.map_id,
                    instance_id=self.instance_id,
                    x=99,
                    y=99,
                    z=0,
                )
            ],
            emit_location=emit or self._emit(packets),
        )
        return ecology_mobs.apply(
            self.store,
            self.groups,
            SimpleNamespace(lock=threading.RLock(), targets=set(excluded)),
            world,
            dict(
                kind="publish_reproduction",
                scope=list(self.location),
                world_epoch="reproduction-world",
                group_id=self.group_id,
                expected_members=self._group()["members"],
            ),
            world_epoch="reproduction-world",
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

    def test_world_coalesces_births_and_publishes_remove_then_latest_roster(self):
        self._commit_due_birth_fixtures()
        packets = []
        self._publish(packets)
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
        self._commit_due_birth_fixtures()
        event = self._unpublished()[0]
        current = self._group()
        moved = [dict(member) for member in current["members"]]
        moved[0]["x"] += 10
        self.assertTrue(self.groups.move_members(self.key, current["members"], moved))
        event["current_revision"] = current["revision"]
        self.assertFalse(monster_reproduction.acknowledge(self.store, event))
        self.assertEqual(2, len(self._unpublished()))

    def test_fighting_and_harvesting_defer_publication_and_retry(self):
        self._commit_due_birth_fixtures()
        packets = []
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(self.key, "reproduction-fight", fight_id)
        self._publish(packets)
        self.assertEqual([], packets)
        self.assertEqual(2, len(self._unpublished()))
        self.assertTrue(self.groups.finish(lease, defeated=False))
        self.assertEqual(
            self._publish(packets, excluded={self.members[1]["id"]}),
            dict(status="harvesting"),
        )
        self.assertEqual([], packets)
        self.assertEqual(2, len(self._unpublished()))
        self._publish(packets)
        self.assertEqual([12304, 12608], [row[2] for row in packets])
        self.assertEqual([], self._unpublished())

    def test_emission_failure_retains_outbox_for_exact_packet_retry(self):
        self._commit_due_birth_fixtures()
        attempted = []

        def fail(*packet):
            attempted.append(packet)
            raise OSError("injected reproduction emit failure")

        with self.assertRaisesRegex(OSError, "injected reproduction emit failure"):
            self._publish([], emit=fail)
        self.assertEqual(2, len(self._unpublished()))
        retry = []
        self._publish(retry)
        self.assertEqual(retry[0], attempted[0])
        self.assertEqual([12304, 12608], [row[2] for row in retry])
        self.assertEqual([], self._unpublished())


if __name__ == "__main__":
    unittest.main()
