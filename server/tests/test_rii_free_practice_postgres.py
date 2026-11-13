"""Owned Rii practice sacks retire without touching public groups."""
from postgres_case import PostgresCase
from unittest.mock import patch
from wakfu_server.achievements import rii_free_practice as practice
from wakfu_server.achievements import storage
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import owned_instance


class RiiFreePracticePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("rii-practice-cleanup", "test-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Practice Cleanup")
        self.groups = PersistentGroups(self.store)
        self.generation = "practice-cleanup-generation"

    def _actor(self, reference, actor_id, x):
        return owned_instance(
            reference, 1, actor_id, map_id=1388, instance_id=0, x=x, y=-15, z=0
        )

    def _register_receipted_group(
        self, group_id, actor_id, x, *, reference, event_key, event_kind
    ):
        actor = self._actor(reference, actor_id, x)
        with self.store.connection() as db:
            self.assertTrue(
                storage.record_event(
                    db,
                    self.character["id"],
                    event_key + str(-actor_id),
                    {
                        "kind": event_kind,
                        "owner": self.character["id"],
                        "actor_id": actor_id,
                        "ref": reference,
                    },
                )
            )
        key = self.groups.register(1388, 0, group_id, [actor])
        return key

    def _claim(self, key, fight_status="active"):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES(%s) RETURNING id",
                (fight_status,),
            ).fetchone()["id"]
        lease, _ = self.groups.claim(key, self.generation, fight_id)
        return lease

    def _assert_group_absent(self, key):
        with self.reopen().connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    key,
                ).fetchone()
            )

    def test_multi_sack_spawn_receipts_group_and_cleanup(self):
        from wakfu_server import npc_world
        from types import SimpleNamespace

        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.character["id"])
        with self.store.connection() as db:
            row = next(
                r
                for r in npc_world.load_scene(db, 1388, 0)
                if r["actor_id"] == practice.ACTOR and r["reference_id"] == 5460
            )
            db.execute(
                "UPDATE characters SET map_id=1388,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (row["x"], row["y"], row["z"], self.character["id"]),
            )
            current = self.store.character(self.account, self.character["id"], db)
        origin = tuple(current[k] for k in ("x", "y", "z"))
        cells = [(origin[0] + dx, origin[1], origin[2]) for dx in (1, 2, 3)]
        geometry = SimpleNamespace(outgoing={origin: cells})
        with patch(
            "wakfu_server.combat_terrain.published_geometry", return_value=geometry
        ):
            packet, lead = practice.spawn(
                self.store, self.groups, self.account, generation, current, count=3
            )
            self.assertEqual(packet[0], 12608)
            group = next(
                g
                for g in self.groups.available(1388, 0)
                if any(a["id"] == lead["id"] for a in g["members"])
            )
            self.assertEqual(len(group["members"]), 3)
            with self.store.connection() as db:
                practice.admit(db, self.character["id"], group["members"])
                for actor in group["members"]:
                    row = db.execute(
                        "SELECT payload FROM character_achievement_events "
                        "WHERE character_id=%s AND event_key=%s",
                        (self.character["id"], practice.KEY + str(-actor["id"])),
                    ).fetchone()
                    self.assertEqual(
                        row["payload"],
                        practice.payload(self.character["id"], actor["id"]),
                    )
            same_packet, same_lead = practice.spawn(
                self.store, self.groups, self.account, generation, current, count=3
            )
            self.assertEqual(same_lead["id"], lead["id"])
            self.assertEqual(same_packet, packet)
        lease = self._claim(group["key"])
        with self.groups.lock, self.store.connection() as db, db.transaction():
            self.assertTrue(self.groups.finish(lease, defeated=False, db=db))
        self._assert_group_absent(group["key"])

    def test_finish_outcomes_and_disconnect_retire_only_receipted_practice_sacks(self):
        public_key = self.groups.register(
            1388,
            0,
            71001,
            [self._actor(practice.REF, -870001, -20)],
        )
        for index, defeated in enumerate((False, True), start=1):
            actor_id = -870001 - index
            key = self._register_receipted_group(
                71001 + index,
                actor_id,
                -18 + index,
                reference=practice.REF,
                event_key=practice.KEY,
                event_kind=practice.KIND,
            )
            lease = self._claim(key)
            with self.groups.lock, self.store.connection() as db, db.transaction():
                self.assertTrue(self.groups.finish(lease, defeated=defeated, db=db))
            self._assert_group_absent(key)

        disconnected = self._register_receipted_group(
            71004,
            -870004,
            -14,
            reference=practice.REF,
            event_key=practice.KEY,
            event_kind=practice.KIND,
        )
        self._claim(disconnected)
        self.assertEqual(self.groups.release_session(self.generation), [])
        self._assert_group_absent(disconnected)

        public_lesson_key = self.groups.register(
            1388,
            0,
            71005,
            [self._actor(5466, -870005, -12)],
        )
        for index, defeated in enumerate((True, False), start=6):
            actor_id = -870000 - index
            owned_lesson = self._register_receipted_group(
                71000 + index,
                actor_id,
                -12 + index,
                reference=5466,
                event_key="rii-orientation-sack:",
                event_kind="reconstructed_rii_orientation_sack",
            )
            lease = self._claim(owned_lesson)
            with self.groups.lock, self.store.connection() as db, db.transaction():
                self.assertTrue(self.groups.finish(lease, defeated=defeated, db=db))
            self._assert_group_absent(owned_lesson)

        disconnected_lesson = self._register_receipted_group(
            71008,
            -870008,
            -8,
            reference=5466,
            event_key="rii-orientation-sack:",
            event_kind="reconstructed_rii_orientation_sack",
        )
        self._claim(disconnected_lesson)
        self.assertEqual(self.groups.release_session(self.generation), [])
        self._assert_group_absent(disconnected_lesson)

        with self.reopen().connection() as db:
            public = db.execute(
                "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                public_key,
            ).fetchone()
            self.assertIsNotNone(public)
            self.assertEqual(public["status"], "available")
            self.assertEqual(public["members"][0]["ref"], practice.REF)
            public_lesson = db.execute(
                "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                public_lesson_key,
            ).fetchone()
            self.assertIsNotNone(public_lesson)
            self.assertEqual(public_lesson["status"], "available")
            self.assertEqual(public_lesson["members"][0]["ref"], 5466)


if __name__ == "__main__":
    import unittest

    unittest.main()
