"""Four-sack owned encounter and quest settlement with isolated PostgreSQL.

Area hit targets are supplied by this fixture. This does not substitute for a
real spell dispatcher or terrain/line-of-sight test.
"""
from threading import RLock
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import (
    rii_area_encounter as encounter,
    rii_area_runtime,
    rii_training_arena,
    storage,
)
from wakfu_server import npc_world, npc_objective_facts, rii_airyna_dialogue
from wakfu_server.combat_state import Actor, Fight


class AreaFlowPostgresTests(PostgresCase):
    def test_owned_four_sacks_settle_and_persist(self):
        account = self.store.register("area-owner", "test-password")["id"]
        character = self.store.create_character(account, "Area Flow")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
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
                (character["id"],),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,1)",
                ("c" * 64, Jsonb({}), b"fixture"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5143,%s)",
                ("c" * 64, Jsonb({"native": native})),
            )
            state = storage.load_locked(db, character["id"])
            state["running"], state["objectives"] = [5143], [
                10574,
                10575,
                10576,
                10608,
                10606,
            ]
            storage.store(db, character["id"], state)
            current = self.store.character(account, character["id"], db)
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
                return npc_objective_facts.load(db, account, character["id"])

        session, _ = rii_airyna_dialogue.begin(
            lambda: current, rows, facts, row["actor_id"], 1389
        )
        self.assertEqual(session.choose(5787, 13326)[0], 12218)
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
                10609,
                available=lambda position: True,
            )
        self.assertEqual((current["x"], current["y"], current["z"]), (0, -16, 0))
        current = dict(current, _rii_training_objective=10609)

        class Groups:
            lock = RLock()

            def available(self, *args):
                return []

            def register_transaction(self, db, map_id, instance_id, group_id, members):
                self.members = members

        groups = Groups()
        origin = (0, -16, 0)
        from wakfu_server.achievements.rii_lesson_layout import AREA

        cells = AREA
        geometry = type("Geometry", (), {"outgoing": {origin: cells}})()

        def instance(ref, level, identity, **location):
            return {"id": identity, "ref": ref, **location}

        with patch(
            "wakfu_server.combat_terrain.published_geometry", return_value=geometry
        ), patch.object(encounter, "formation", return_value=(origin, cells)), patch(
            "wakfu_server.monsters.owned_instance", side_effect=instance
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=30
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ):
            self.assertEqual(
                encounter.spawn(self.store, groups, account, generation, current),
                (12608, b"spawn"),
            )
        monsters = groups.members
        player = Actor(character["id"], 0, origin, 100, 6, 3, 10, 1, account, True)
        sacks = [
            Actor(
                monster["id"],
                1,
                (monster["x"], monster["y"], monster["z"]),
                100,
                6,
                3,
                5,
                1,
            )
            for monster in monsters
        ]
        from wakfu_server.combat_terrain import local_arena

        terrain = local_arena(1388, 0, origin, cells, relocate_monsters=False)
        fight = Fight(
            77,
            [player, *sacks],
            terrain["validated_cells"],
            {0: {origin}, 1: set(cells)},
            terrain["valid_edges"],
        )
        fight.native_effect_uid_next = 1000
        fight.ready(account)
        with self.store.connection() as db:
            fight.rii_area_lesson_contract = encounter.bind(
                db, character["id"], monsters
            )
        self.assertTrue(
            rii_training_arena.setup_is_ready(self.store, account, character["id"])
        )
        fight.rii_area_lesson_contract["initialized"] = True
        effects = (367142, 367142, 367103, 367145)
        for action, effect in enumerate(effects, 1):
            self.assertTrue(
                rii_area_runtime.begin(
                    fight,
                    source_id=player.id,
                    action_id=action,
                    spell_id=(7970, 7970, 7969, 7971)[action - 1],
                )
            )
            for sack in sacks:
                rii_area_runtime.defer(
                    fight,
                    action_id=action,
                    source_id=player.id,
                    target_id=sack.id,
                    effect_reference=effect,
                    damage=25,
                    uid=1000 + action * 10 - sack.id,
                    element=1,
                    cell=sack.position,
                    base_uid=None,
                )
            self.assertTrue(rii_area_runtime.finish(fight, []))
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status,fight_kind) OVERRIDING SYSTEM VALUE VALUES(77,'finished','pve')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(77,%s,%s,0)",
                (player.id, account),
            )
            packets = encounter.settle_participants(
                db,
                self.store,
                fight,
                [
                    {
                        "character_id": player.id,
                        "account_id": account,
                        "session_generation": generation,
                    }
                ],
                monsters,
            )
            self.assertIn(account, packets)
        with self.reopen().connection() as db:
            self.assertIn(10609, storage.load_locked(db, player.id)["objectives"])
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
            tuple(returned[key] for key in rii_training_arena.POSITION),
            tuple(source[key] for key in rii_training_arena.POSITION),
        )
        self.assertFalse(
            rii_training_arena.pending(self.store, account, character["id"])
        )
