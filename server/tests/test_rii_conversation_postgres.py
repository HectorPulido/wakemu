"""Transactional persistence for an actual captured Rii dialogue."""
import unittest
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import npc_world, npc_objective_facts, rii_conversation_progress
from wakfu_server.achievements import storage


class RiiConversationPostgresTests(PostgresCase):
    def test_huly_talk_persists_once_and_survives_reconnection(self):
        account = self.store.register("rii-talk-owner", "test-password")["id"]
        character = self.store.create_character(account, "Rii Talk")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        definition = {
            "d": 5160,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [{"d": i, "ckc": "", "cke": ""} for i in (10612, 10613)],
            "cjK": [],
        }
        with self.store.connection() as db:
            row = next(
                r
                for r in npc_world.load_scene(db, 1385, 0)
                if r["reference_id"] == 5461
            )
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    row["map_id"],
                    row["instance_id"],
                    row["x"],
                    row["y"],
                    row["z"],
                    character["id"],
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,1)",
                ("a" * 64, Jsonb({}), b"fixture"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5160,%s)",
                ("a" * 64, Jsonb({"native": definition})),
            )
            hidden = {
                "d": 5154,
                "native_class": "aJM",
                "aqb": True,
                "isVisible": False,
                "cjK": [],
                "cjJ": [
                    {"d": objective, "ckc": "", "cke": "", "ckf": []}
                    for objective in (10595, 10596, 10606, 10607)
                ],
            }
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5154,%s)",
                ("a" * 64, Jsonb({"native": hidden})),
            )
            state = storage.load_locked(db, character["id"])
            state["running"] = [5160]
            storage.store(db, character["id"], state)
        with self.store.connection() as db:
            current = self.store.character(account, character["id"], db)

        def rows():
            with self.store.connection() as db:
                return npc_world.load_scene(db, 1385, 0)

        def facts():
            with self.store.connection() as db:
                return npc_objective_facts.load(db, account, character["id"])

        def talk():
            session, _ = npc_world.begin(
                lambda: current,
                rows,
                row["actor_id"],
                row["action_ids"][0],
                facts_provider=facts,
            )
            for node, choice in (
                (5765, 13275),
                (5766, 13278),
                (5767, 13280),
                (5768, 13281),
                (5769, 13282),
                (5783, 13306),
            ):
                session.choose(node, choice)
            return rii_conversation_progress.choose(
                self.store,
                account,
                generation,
                current,
                session,
                {"node_id": 5770, "choice_id": 13283},
            )

        self.assertTrue(talk()["packets"])
        # Native action criteria close this conversation after objective 10612;
        # a fresh open must be rejected without changing the existing receipt.
        with self.assertRaisesRegex(
            ValueError, "Unavailable native NPC action criteria"
        ):
            talk()
        reopened = self.reopen()
        with reopened.connection() as db:
            persisted = storage.load_locked(db, character["id"])
            self.assertEqual(persisted["objectives"], [10595, 10612])
            self.assertTrue(
                npc_objective_facts.load(db, account, character["id"])[10612]
            )

        # Airyna and Kheperalia start their curricula in the same transaction
        # as their own talk objective; inspect fresh database state afterward.
        from wakfu_server.achievements.rii_ecosystem_activation import OBJECTIVES

        definitions = {
            5143: (10574, 10575, 10576, 10608, 10609, 10610, 10611),
            5146: (10582, 10583, 10584),
            **OBJECTIVES,
        }
        definition["cjJ"] = [
            {"d": i, "ckc": "", "cke": ""}
            for i in (10612, 10613, 10614, 10615, 10616, 10617, 10618, 10619, 10622)
        ]
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_quest_metadata_definitions SET data=%s WHERE definition_id=5160",
                (Jsonb({"native": definition}),),
            )
            for identity, objectives in definitions.items():
                native = {
                    "d": identity,
                    "native_class": "aJM",
                    "aqb": False,
                    "cjI": "",
                    "cjU": 0,
                    "getDuration": 0,
                    "cjJ": [{"d": i} for i in objectives],
                }
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,%s,%s)",
                    ("a" * 64, identity, Jsonb({"native": native})),
                )

        for map_id, reference, edges, objective in (
            (1388, 5460, ((5755, 13258), (5756, 13260)), 10614),
            (1385, 5467, ((5782, 13305), (5786, 13318)), 10615),
        ):
            with self.store.connection() as db:
                npc = next(
                    r
                    for r in npc_world.load_scene(db, map_id, 0)
                    if r["reference_id"] == reference
                )
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (map_id, npc["x"], npc["y"], npc["z"], character["id"]),
                )
                current = self.store.character(account, character["id"], db)

            def scene():
                with self.store.connection() as db:
                    return npc_world.load_scene(db, map_id, 0)

            session, _ = npc_world.begin(
                lambda: current,
                scene,
                npc["actor_id"],
                npc["action_ids"][0],
                facts_provider=facts,
            )
            for node, choice in edges[:-1]:
                session.choose(node, choice)
            node, choice = edges[-1]
            result = rii_conversation_progress.choose(
                self.store,
                account,
                generation,
                current,
                session,
                {"node_id": node, "choice_id": choice},
            )
            self.assertTrue(result["packets"])
            with reopened.connection() as db:
                persisted = storage.load_locked(db, character["id"])
                self.assertIn(objective, persisted["objectives"])
        self.assertTrue({5143, 5145}.issubset(persisted["running"]))
        self.assertTrue({5143, 5145}.issubset(persisted["tracking"]))
        self.assertFalse({5155, 5156} & set(persisted["running"]))
        self.assertIn(10607, persisted["objectives"])
        with reopened.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COALESCE(sum(quantity),0) AS quantity FROM inventory_items "
                    "WHERE character_id=%s AND reference=31007",
                    (character["id"],),
                ).fetchone()["quantity"],
                0,
            )

        # Both return choices complete their child mission and its parent
        # objective atomically, including after a fresh connection.
        from wakfu_server import rii_ecosystem_dialogue

        prerequisite_rows = {
            5145: (10597, 10579, 10578, 10620),
            5155: (10598, 10599, 10600, 10621),
        }
        with self.store.connection() as db:
            for identity, ids in prerequisite_rows.items():
                native = {
                    "d": identity,
                    "native_class": "aJM",
                    "aqb": False,
                    "cjI": "",
                    "cjU": 0,
                    "getDuration": 0,
                    "cjJ": [{"d": i, "ckc": "", "cke": ""} for i in ids],
                    "cjK": [],
                }
                db.execute(
                    "UPDATE native_quest_metadata_definitions SET data=%s WHERE definition_id=%s",
                    (Jsonb({"native": native}), identity),
                )
            state = storage.load_locked(db, character["id"])
            state["objectives"] = sorted(
                set(state["objectives"]) | {10597, 10579, 10578, 10598, 10599, 10600}
            )
            storage.store(db, character["id"], state)

        for root_choice, node, terminal in ((13360, 5788, 13338), (13361, 5789, 13340)):
            with self.store.connection() as db:
                current = self.store.character(account, character["id"], db)
            session, _ = rii_ecosystem_dialogue.begin(
                self.store,
                lambda: current,
                scene,
                account,
                npc["actor_id"],
                npc["action_ids"][0],
            )
            self.assertEqual(
                session.node_id, 5799
            )  # isolated database has no live Wodents
            session.choose(5799, root_choice)
            outcome = rii_ecosystem_dialogue.choose(
                self.store,
                account,
                generation,
                current,
                session,
                {"node_id": node, "choice_id": terminal},
            )
            self.assertTrue(outcome["packets"])
        with reopened.connection() as db:
            persisted = storage.load_locked(db, character["id"])
        self.assertTrue({5145, 5155}.issubset(persisted["completed"]))
        self.assertIn(5156, persisted["running"])
        self.assertTrue({10620, 10621, 10617, 10618}.issubset(persisted["objectives"]))


if __name__ == "__main__":
    unittest.main()
