"""Owned Airyna choice through four distance hits and durable quest progress.

Map geometry/group emission and spell catalog lookups are bounded fixtures;
the NPC session, fight damage handler and PostgreSQL progress are real.
"""
from threading import RLock
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import (
    npc_world,
    npc_objective_facts,
    rii_airyna_dialogue,
    rii_lesson_grants,
)
from wakfu_server.achievements import (
    rii_owned_lesson as encounter,
    rii_distance_contract,
    storage,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation


class DistanceFlowPostgresTests(PostgresCase):
    def test_choice_owned_sack_four_hits_and_reconnect_progress(self):
        account = self.store.register("distance-owner", "test-password")["id"]
        character = self.store.create_character(account, "Distance Flow")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        native = {
            "d": 5143,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjK": [],
            "cjJ": [
                {"d": 10574, "ckc": "", "cke": ""},
                {"d": 10575, "ckc": "IsAchievementObjectiveComplete(10574)", "cke": ""},
                {"d": 10576, "ckc": "IsAchievementObjectiveComplete(10575)", "cke": ""},
                *[
                    {"d": objective, "ckc": "", "cke": ""}
                    for objective in (10608, 10609, 10610, 10611)
                ],
            ],
        }
        with self.store.connection() as db:
            row = next(
                r
                for r in npc_world.load_scene(db, 1388, 0)
                if r["reference_id"] == 5460
            )
            db.execute(
                "UPDATE characters SET map_id=1388,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (row["x"], row["y"], row["z"], character["id"]),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,1)",
                ("b" * 64, Jsonb({}), b"fixture"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5143,%s)",
                ("b" * 64, Jsonb({"native": native})),
            )
            state = storage.load_locked(db, character["id"])
            state["running"], state["objectives"] = [5143], [10574, 10575, 10606]
            storage.store(db, character["id"], state)
            current = self.store.character(account, character["id"], db)

        def rows():
            with self.store.connection() as db:
                return npc_world.load_scene(db, 1388, 0)

        def facts():
            with self.store.connection() as db:
                return npc_objective_facts.load(db, account, character["id"])

        session, _ = rii_airyna_dialogue.begin(
            lambda: current, rows, facts, row["actor_id"], 1389
        )
        self.assertEqual(session.choose(5787, 13324)[0], 12218)

        class Groups:
            lock = RLock()

            def available(self, *args):
                return []

            def register_transaction(self, db, map_id, instance_id, group_id, members):
                self.members = members

        groups = Groups()
        origin = (current["x"], current["y"], current["z"])
        target_cell = (origin[0] + 1, origin[1], origin[2])
        geometry = type("Geometry", (), {"outgoing": {origin: [target_cell]}})()

        def instance(ref, level, identity, **location):
            return {"id": identity, "ref": ref, **location}

        with patch(
            "wakfu_server.combat_terrain.published_geometry", return_value=geometry
        ), patch("wakfu_server.monsters.owned_instance", side_effect=instance), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=30
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ):
            self.assertEqual(
                encounter.spawn(
                    self.store, groups, account, generation, current, encounter.DISTANCE
                ),
                (12608, b"spawn"),
            )
        monsters = groups.members
        player = Actor(character["id"], 0, (0, 0, 0), 100, 6, 3, 10, 1, account, True)
        sack = Actor(-30, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            77,
            [player, sack],
            {player.position, sack.position},
            {0: {player.position}, 1: {sack.position}},
        )
        fight.ready(account)
        for actor in (player, sack):
            actor.effect_stats = {92: 0, 97: 0, 100: 0, 28: 0, 29: 0, 30: 0, 31: 0}
            actor.effect_minima = {k: -2147483648 for k in actor.effect_stats}
            actor.effect_maxima = {k: 2147483647 for k in actor.effect_stats}
            actor.effect_maxima[92] = 0
            actor.effect_frozen, actor.physical_radius = frozenset(), 0
        with self.store.connection() as db:
            fight.rii_distance_lesson_contract = encounter.bind(
                db, encounter.DISTANCE, character["id"], monsters
            )
            self.assertIsNotNone(fight.rii_distance_lesson_contract)
        fight.native_effect_uid_next = 1000
        with patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset({7967}),
        ), patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"7967": {"maximum_level": 200}},
        ):
            initial = []
            self.assertTrue(
                rii_distance_contract.initialize(fight, initial, action_id=1)
            )
            self.assertEqual([op for op, _ in initial], [12613, 349])
        handler = NativeDamageHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            rng=lambda: 0.99,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False
            ),
        )
        for distance in (1, 3, 2, 4):
            sack.position = (distance, 0, 0)
            self.assertTrue(
                handler(
                    {
                        "effect_class": 1,
                        "parameters": [25, 0],
                        "native_effect_flags": [],
                        "native_localization_enabled": True,
                    },
                    {},
                    EffectInvocation(361204, 1, player.id, sack.id, sack.position),
                )
            )
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
                encounter.DISTANCE,
                fight,
                [
                    {
                        "character_id": player.id,
                        "account_id": account,
                        "session_generation": generation,
                    }
                ],
                monsters,
                contract_name="rii_distance_lesson_contract",
            )
            self.assertIn(account, packets)
        with self.reopen().connection() as db:
            self.assertIn(10576, storage.load_locked(db, player.id)["objectives"])
