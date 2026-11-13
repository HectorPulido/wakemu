"""Owned LOS receipts and four-hit quest settlement in isolated PostgreSQL."""
from types import SimpleNamespace
from threading import RLock
from unittest.mock import Mock, patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import (
    rii_los_encounter as los,
    rii_owned_lesson,
    rii_training_arena,
    storage,
)
from wakfu_server import npc_world, npc_objective_facts, rii_airyna_dialogue


class LosFlowPostgresTests(PostgresCase):
    def test_owned_receipts_and_four_hit_settlement_survive_reconnect(self):
        account = self.store.register("los-owner", "test-password")["id"]
        character = self.store.create_character(account, "Los Flow")
        owner = character["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, owner)
        native = {
            "d": 5143,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjK": [],
            "cjJ": [
                {"d": objective, "ckc": "", "cke": ""}
                for objective in (10574, 10575, 10576, 10608, 10609, 10610, 10611)
            ],
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1388,instance_id=0,x=1,y=-19,z=3 WHERE id=%s",
                (owner,),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,1)",
                ("c" * 64, Jsonb({}), b"fixture"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5143,%s)",
                ("c" * 64, Jsonb({"native": native})),
            )
            state = storage.load_locked(db, owner)
            state["running"], state["objectives"] = [5143], [10574, 10575, 10576, 10606]
            storage.store(db, owner, state)
            current = self.store.character(account, owner, db)
            row = next(
                r
                for r in npc_world.load_scene(db, 1388, 0)
                if r["reference_id"] == 5460
            )

        def rows():
            with self.store.connection() as db:
                return npc_world.load_scene(db, 1388, 0)

        def facts():
            with self.store.connection() as db:
                return npc_objective_facts.load(db, account, owner)

        session, _ = rii_airyna_dialogue.begin(
            lambda: current, rows, facts, row["actor_id"], 1389
        )
        self.assertEqual(session.choose(5787, 13325)[0], 12218)
        source = current
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            current = rii_training_arena.enter(
                self.store,
                account,
                generation,
                source,
                10608,
                available=lambda position: True,
            )
        self.assertEqual((current["x"], current["y"], current["z"]), (0, -16, 0))
        current = dict(current, _rii_training_objective=10608)

        class Groups:
            lock = RLock()

            def available(self, *args):
                return []

            def register_transaction(self, db, map_id, instance_id, group_id, members):
                self.members = members

        groups = Groups()
        cells = ((1, -16, 0), (2, -16, 0), (2, -15, 0), (2, -17, 0))

        def instance(ref, level, identity, **location):
            return {"id": identity, "ref": ref, **location}

        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value={
                "default_actor_los_height": 6,
                "npc_profiles": {"5466": {"native_los_height": 4}},
            },
        ), patch(
            "wakfu_server.combat_terrain.published_geometry",
            return_value=SimpleNamespace(outgoing={}),
        ), patch.object(
            los, "scene_cells", return_value=cells
        ), patch(
            "wakfu_server.monsters.owned_instance", side_effect=instance
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block",
            side_effect=(20, 21, 22, 23),
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ):
            # Exercise compatibility for historical three-actor receipts;
            # new encounters use the native one-sack producer.
            self.assertEqual(
                los._spawn_legacy(self.store, groups, account, generation, current),
                (12608, b"spawn"),
            )
        monsters = groups.members
        self.assertTrue(rii_training_arena.setup_is_ready(self.store, account, owner))
        with self.store.connection() as db:
            self.assertTrue(los.admit(db, owner, monsters))
            contract = los.bind(db, owner, monsters)
            db.execute(
                "INSERT INTO combat_fights(id,status,fight_kind) OVERRIDING SYSTEM VALUE VALUES(77,'finished','pve')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(77,%s,%s,0)",
                (owner, account),
            )
            contract["hits"] = 0
            fight = SimpleNamespace(
                id=77,
                phase="active",
                winner=None,
                actors={
                    owner: SimpleNamespace(team=0, hp=100, position=(0, 0, 0)),
                    -20: SimpleNamespace(team=1, hp=100, position=(4, 0, 0)),
                },
                rii_los_lesson_contract=contract,
                _event=Mock(),
            )
            with patch(
                "wakfu_server.combat_casting_los.native_casting_los", return_value=True
            ):
                for _ in range(4):
                    self.assertEqual(
                        los.hit(
                            fight,
                            source_id=owner,
                            target_id=-20,
                            effect_reference=361213,
                            damage=25,
                            actor_authority=object(),
                            spell_id=7968,
                        ),
                        25,
                    )
            self.assertTrue(los.finish_if_qualified(fight))
            members = [
                {
                    "character_id": owner,
                    "account_id": account,
                    "session_generation": generation,
                }
            ]
            result = rii_owned_lesson.settle_participants(
                db,
                self.store,
                los.LOS,
                fight,
                members,
                monsters,
                contract_name="rii_los_lesson_contract",
            )
            self.assertIn(account, result)
            self.assertEqual(
                rii_owned_lesson.settle_participants(
                    db,
                    self.store,
                    los.LOS,
                    fight,
                    members,
                    monsters,
                    contract_name="rii_los_lesson_contract",
                ),
                {},
            )
        with self.reopen().connection() as db:
            self.assertIn(10608, storage.load_locked(db, owner)["objectives"])
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            returned = rii_training_arena.return_to_source(
                self.store,
                account,
                generation,
                current,
                available=lambda position: True,
                only_completed=True,
            )
        self.assertEqual(
            tuple(returned[k] for k in rii_training_arena.POSITION),
            tuple(source[k] for k in rii_training_arena.POSITION),
        )

    def test_native_victory_settlement_survives_reconnect(self):
        account = self.store.register("los-owner", "test-password")["id"]
        character = self.store.create_character(account, "Los Flow")
        owner = character["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, owner)
        native = {
            "d": 5143,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjK": [],
            "cjJ": [
                {"d": objective, "ckc": "", "cke": ""}
                for objective in (10574, 10575, 10576, 10608, 10609, 10610, 10611)
            ],
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1388,instance_id=0,x=1,y=-19,z=3 WHERE id=%s",
                (owner,),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,1)",
                ("c" * 64, Jsonb({}), b"fixture"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5143,%s)",
                ("c" * 64, Jsonb({"native": native})),
            )
            state = storage.load_locked(db, owner)
            state["running"], state["objectives"] = [5143], [10574, 10575, 10576, 10606]
            storage.store(db, owner, state)
            current = self.store.character(account, owner, db)
            row = next(
                r
                for r in npc_world.load_scene(db, 1388, 0)
                if r["reference_id"] == 5460
            )

        def rows():
            with self.store.connection() as db:
                return npc_world.load_scene(db, 1388, 0)

        def facts():
            with self.store.connection() as db:
                return npc_objective_facts.load(db, account, owner)

        session, _ = rii_airyna_dialogue.begin(
            lambda: current, rows, facts, row["actor_id"], 1389
        )
        self.assertEqual(session.choose(5787, 13325)[0], 12218)
        source = current
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            current = rii_training_arena.enter(
                self.store,
                account,
                generation,
                source,
                10608,
                available=lambda position: True,
            )
        self.assertEqual((current["x"], current["y"], current["z"]), (0, -16, 0))
        current = dict(current, _rii_training_objective=10608)

        class Groups:
            lock = RLock()

            def available(self, *args):
                return []

            def register_transaction(self, db, map_id, instance_id, group_id, members):
                self.members = members

        groups = Groups()
        cells = ((1, -16, 0), (2, -16, 0), (2, -15, 0), (2, -17, 0))

        def instance(ref, level, identity, **location):
            return {"id": identity, "ref": ref, **location}

        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value={
                "default_actor_los_height": 6,
                "npc_profiles": {"5466": {"native_los_height": 4}},
            },
        ), patch(
            "wakfu_server.combat_terrain.published_geometry",
            return_value=SimpleNamespace(outgoing={(0, -16, 0): ((1, -16, 0),)}),
        ), patch.object(
            los, "scene_cells", return_value=cells
        ), patch(
            "wakfu_server.monsters.owned_instance", side_effect=instance
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=20
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ):
            self.assertEqual(
                __import__(
                    "wakfu_server.achievements.rii_los_native", fromlist=["spawn"]
                ).spawn(self.store, groups, account, generation, current),
                (12608, b"spawn"),
            )
        monsters = groups.members
        self.assertTrue(rii_training_arena.setup_is_ready(self.store, account, owner))
        with self.store.connection() as db:
            self.assertTrue(los.admit(db, owner, monsters))
            contract = los.bind(db, owner, monsters)
            db.execute(
                "INSERT INTO combat_fights(id,status,fight_kind) OVERRIDING SYSTEM VALUE VALUES(77,'finished','pve')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(77,%s,%s,0)",
                (owner, account),
            )
            self.assertTrue(contract["native_los_areas"])
            fight = SimpleNamespace(
                id=77,
                phase="finished",
                winner=0,
                actors={
                    owner: SimpleNamespace(team=0, hp=100, position=(0, 0, 0)),
                    -20: SimpleNamespace(team=1, hp=0, position=(4, 0, 0)),
                },
                rii_los_lesson_contract=contract,
                _event=Mock(),
            )
            members = [
                {
                    "character_id": owner,
                    "account_id": account,
                    "session_generation": generation,
                }
            ]
            result = rii_owned_lesson.settle_participants(
                db,
                self.store,
                los.LOS,
                fight,
                members,
                monsters,
                contract_name="rii_los_lesson_contract",
            )
            self.assertIn(account, result)
            self.assertEqual(
                rii_owned_lesson.settle_participants(
                    db,
                    self.store,
                    los.LOS,
                    fight,
                    members,
                    monsters,
                    contract_name="rii_los_lesson_contract",
                ),
                {},
            )
        with self.reopen().connection() as db:
            self.assertIn(10608, storage.load_locked(db, owner)["objectives"])
        # Lost combat-return ACK: the prior completed transit may still hold
        # its original source when the next floor lesson is requested.
        resumed = rii_training_arena.enter(
            self.reopen(),
            account,
            generation,
            current,
            10609,
            available=lambda position: False,
        )
        with self.reopen().connection() as db:
            transit = db.execute(
                "SELECT * FROM rii_training_transits WHERE character_id=%s", (owner,)
            ).fetchone()
            self.assertEqual(transit["lesson_objective"], 10609)
            self.assertTrue(transit["setup_failed"])
            self.assertEqual(
                (transit["source_x"], transit["source_y"], transit["source_z"]),
                (source["x"], source["y"], source["z"]),
            )
            rii_training_arena.mark_setup_ready_in_transaction(
                db, dict(resumed, _rii_training_objective=10609), 10609
            )
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            returned = rii_training_arena.return_to_source(
                self.store,
                account,
                generation,
                resumed,
                available=lambda position: True,
            )
        self.assertEqual(
            tuple(returned[k] for k in rii_training_arena.POSITION),
            tuple(source[k] for k in rii_training_arena.POSITION),
        )
