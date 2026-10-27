"""Production settlement recovers frozen regional credit for every winning owner."""
import ast
from copy import deepcopy
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

from wakfu_server import heroes
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.objectives import environmental_gameplay as gameplay
from wakfu_server.objectives import environmental_storage as storage
from test_environmental_group_wins import EnvironmentalGroupWinTests


class EnvironmentalAdmissionCreditTests(EnvironmentalGroupWinTests):
    def test_real_world_settlement_four_kills_legacy_origin_hero_and_replay(self):
        hero = self.store.create_character(self.account, "Regional Hero")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (self.map_id, self.world_instance, *self.points[0], hero["id"]),
            )
        heroes.add(
            self.store, self.account, self.generation, self.character["id"], hero["id"]
        )
        originals = [
            owned_instance(
                5008,
                REFERENCES[5008]["min_level"],
                -990000 - index,
                map_id=self.map_id,
                instance_id=self.world_instance,
                x=point[0],
                y=point[1],
                z=point[2],
            )
            for index, point in enumerate(self.points[:4])
        ]
        self.assertEqual(len(originals), 4)
        self.registry.register(self.map_id, self.world_instance, 779, originals)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,"
                "level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision) "
                "VALUES('regional-four',1,'monster_defeat','collaborative',%s,%s,60000,%s,"
                "1,245,5,'bounded declared group',%s,%s)",
                (self.map_id, self.region, self.now_ms - 1000, "0" * 64, "1" * 64),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES "
                "('regional-four',1,'kill','monster_defeat',5008,NULL,NULL,'interaction',20)"
            )
            db.execute(
                "INSERT INTO environmental_profile_group_composition VALUES "
                "('regional-four',1,2643,5008,4,'bounded declared group')"
            )
            db.execute(
                "INSERT INTO environmental_profile_bindings VALUES "
                "('regional-four',1,'existing_declared_groups','bounded declared group')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true "
                "WHERE profile_key='regional-four'"
            )
        event = self.refresh()["instances"][0]["instance_id"]
        with self.store.connection() as db:
            participants = db.execute(
                "SELECT character_id FROM environmental_participants "
                "WHERE instance_id=%s ORDER BY character_id",
                (event,),
            ).fetchall()
            self.assertEqual(
                {r["character_id"] for r in participants},
                {self.character["id"], hero["id"]},
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES "
                "('active','pve') RETURNING id"
            ).fetchone()["id"]
            for identity in (self.character["id"], hero["id"]):
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                    "VALUES(%s,%s,%s,0)",
                    (fight_id, identity, self.account),
                )
        lease, _ = self.registry.claim(
            (self.map_id, self.world_instance, 779), self.generation, fight_id
        )
        actor = lambda controlled, team, hp: SimpleNamespace(
            controlled=controlled,
            team=team,
            hp=hp,
            owner_id=self.account if controlled else 0,
        )
        actors = {
            identity: actor(True, 0, 1)
            for identity in (self.character["id"], hero["id"])
        }
        actors.update({m["id"]: actor(False, 1, 0) for m in originals})
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            actors=actors,
            native_summon_registrations={},
        )
        # This is the context already held by real in-flight fights before the
        # new admission field exists. Only its original leader may use it.
        shared = SimpleNamespace(
            map_id=self.map_id,
            instance_id=self.world_instance,
            group_lease=lease,
            lock=RLock(),
            participants={
                self.account: SimpleNamespace(character_id=self.character["id"])
            },
            join_context={
                "world_marker_origin": tuple(self.points[0]),
                "leaders": {0: self.character["id"], 1: originals[0]["id"]},
            },
        )
        scene = gameplay.scene_from_admission(shared)
        self.assertEqual(scene["admission_regions"], {self.account: self.region})
        # A changed selection location must never replace frozen admission.
        moved = dict(self.character, x=999999, y=999999)
        self.assertIsNone(gameplay.admission_origin(moved)["region_id"])
        self.assertEqual(gameplay.scene_from_admission(shared), scene)
        gameplay.remember_admission(shared, self.account, self.character)
        gameplay.remember_admission(shared, self.account, moved)
        self.assertEqual(gameplay.scene_from_admission(shared), scene)

        source = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        method = next(
            n
            for n in ast.walk(source)
            if isinstance(n, ast.FunctionDef) and n.name == "settle_achievements"
        )
        namespace = dict(
            COMBAT_SESSIONS=SimpleNamespace(
                registry=SimpleNamespace(lookup=lambda _: shared)
            ),
            STORE=self.store,
            TEST_MONSTERS=originals,
            is_developer_test_fight=lambda *_: False,
            committed_task_candidates=[],
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                "<actual World settle_achievements>",
                "exec",
            ),
            namespace,
        )
        settle = namespace["settle_achievements"]
        members = [
            dict(account_id=self.account, character_id=i)
            for i in (self.character["id"], hero["id"])
        ]
        with self.store.connection() as db:
            self.store.lock_character(
                db, self.account, self.generation, self.character["id"]
            )
            self.assertTrue(self.registry.finish(lease, defeated=True, db=db))
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            # Wrong admitted region still creates no objective progress.
            wrong = deepcopy(shared.join_context)
            shared.join_context["environmental_admission_origins"][self.account][
                "region_id"
            ] = (self.region + 1)
            settle(db, members, fight)
            self.assertEqual(storage._progress(db, dict(instance_id=event)), {})
            shared.join_context = wrong
            settle(db, members, fight)
            self.assertEqual(
                storage._progress(db, dict(instance_id=event)), {"kill": 4}
            )
            for identity in (self.character["id"], hero["id"]):
                self.assertEqual(
                    storage._progress(db, dict(instance_id=event), identity),
                    {"kill": 4},
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions "
                    "WHERE instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts "
                    "WHERE instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                8,
            )
            settle(db, members, fight)
            self.assertEqual(
                storage._progress(db, dict(instance_id=event)), {"kill": 4}
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts "
                    "WHERE instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                8,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements "
                    "WHERE instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                0,
            )
