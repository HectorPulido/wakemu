"""Original collaborative goals share physical progress, not personal eligibility."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import time
import unittest

from wakfu_server import heroes
from wakfu_server.achievements import combat_adapter
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.combat_state import Actor
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_native_variables as variables
from wakfu_server.progression import XP_BY_LEVEL


class CollaborativeGoalTests(unittest.TestCase):
    def test_original_personal_five_global_twenty_separates_main_hero_and_below_minimum_owner(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )

        fixture = EnvironmentalOwnedResourcePopulationTests(
            "test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        main = fixture.character["id"]
        account = fixture.account
        hero = store.create_character(account, "Shared Goal Hero")
        third_account = store.register("shared-goal-third", "test-password")["id"]
        third = store.create_character(third_account, "Shared Goal Third")
        third_generation = store.begin_session(third_account, ttl=1800)
        store.select_character(third_account, third_generation, third["id"])
        with store.connection() as db:
            for identity in (hero["id"], third["id"]):
                db.execute(
                    "UPDATE characters SET level=81,map_id=327,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (*fixture.points[-1], identity),
                )
                db.execute(
                    "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                    (XP_BY_LEVEL[81], identity),
                )
        heroes.add(store, account, fixture.generation, main, hero["id"])
        self.assertTrue(store.heartbeat(account, fixture.generation, ttl=1800))
        fixture.world.join(
            third_generation,
            SimpleNamespace(shutdown=lambda *_: None),
            store.character(third_account, third["id"]),
        )
        groups = PersistentGroups(store)
        key = "group-native-1329-327-56601"
        raw = (
            Path(__file__).resolve().parents[1]
            / "seeds/environmental_group_profiles.sql"
        ).read_text()
        statements = []
        for fragment in raw.split(";\n"):
            statement = fragment.strip()
            if "E'" + key + "'" in statement and (
                statement.startswith("INSERT INTO environmental_profile_")
                or statement.startswith("INSERT INTO environmental_runtime_profiles")
                or statement.startswith(
                    "UPDATE environmental_runtime_profiles SET sealed=TRUE"
                )
            ):
                statements.append(statement + ";")
        self.assertGreaterEqual(len(statements), 10)
        with store.connection() as db:
            for statement in statements:
                db.execute(statement, prepare=False)
            # A declared finite admission window avoids depending on the
            # original profile's wall-clock recurring window during a test.
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('abc-one-original-profile',1,327,56601,'wakemu_round_robin',"
                "'occupied_sequential_windows',0,'explicit finite source qualification schedule',%s)",
                ("0" * 64,),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_candidates VALUES "
                "('abc-one-original-profile',1,0,%s,1)",
                (key,),
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true "
                "WHERE policy_key='abc-one-original-profile'"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (key,),
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET enabled=true WHERE singleton"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
        initial = service.refresh(
            store,
            account,
            fixture.generation,
            main,
            location=fixture.location,
            now_ms=int(fixture.clock[0] * 1000),
            groups=groups,
        )
        self.assertTrue(
            initial["instances"],
            "Declared occupied source admission window produced no event",
        )
        event_id = initial["instances"][0]["instance_id"]
        service.refresh(
            store,
            third_account,
            third_generation,
            third["id"],
            location=fixture.location,
            now_ms=int(fixture.clock[0] * 1000),
            groups=groups,
        )
        identities = (main, hero["id"], third["id"])

        def views():
            with store.connection() as db:
                event = dict(
                    db.execute(
                        "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()
                )
                profile = storage._event_profile(db, event)
                result = {}
                for identity in identities:
                    participant = dict(
                        db.execute(
                            "SELECT * FROM environmental_participants "
                            "WHERE instance_id=%s AND character_id=%s",
                            (event_id, identity),
                        ).fetchone()
                    )
                    view = storage._view(
                        db, event, profile, participant, int(fixture.clock[0] * 1000)
                    )
                    projected = {
                        r["name"]: r["value"]
                        for r in variables.project(
                            db,
                            event,
                            profile,
                            participant,
                            int(fixture.clock[0] * 1000),
                        )
                    }
                    result[identity] = (participant, view, projected)
                objective = storage._objectives(db, profile)[0]
                entitlements = db.execute(
                    "SELECT character_id FROM environmental_reward_entitlements "
                    "WHERE instance_id=%s ORDER BY character_id",
                    (event_id,),
                ).fetchall()
                return (
                    event,
                    result,
                    objective,
                    [r["character_id"] for r in entitlements],
                )

        event, before, objective, entitled = views()
        self.assertEqual(objective["required_quantity"], 20)
        self.assertEqual(entitled, [])
        for _, _, projection in before.values():
            self.assertEqual(
                (
                    projection["nbMobForReward"],
                    projection["nbMobMin"],
                    projection["nbMobGlobal"],
                ),
                (5, 20, 0),
            )
        with store.connection() as db:
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT g.map_id,g.instance_id,g.group_id,g.members "
                    "FROM combat_groups g JOIN environmental_owned_groups o "
                    "ON (o.map_id,o.world_instance_id,o.group_id)=(g.map_id,g.instance_id,g.group_id) "
                    "WHERE o.instance_id=%s ORDER BY g.group_id",
                    (event_id,),
                ).fetchall()
            ]
        # Select complete actual native groups totalling exactly20 monsters.
        # One small first group includes C; only A/B join later victories.
        chosen = None
        for first in rows:
            if not 0 < len(first["members"]) < 5:
                continue
            paths = {len(first["members"]): [first]}
            for row in rows:
                if row["group_id"] == first["group_id"]:
                    continue
                for count, path in tuple(paths.items()):
                    total = count + len(row["members"])
                    if total <= 20:
                        paths.setdefault(total, path + [row])
            if 20 in paths:
                chosen = paths[20]
                break
        self.assertIsNotNone(
            chosen, "Original native groups cannot form the declared20-monster witness"
        )
        third_personal = len(chosen[0]["members"])
        self.assertLess(third_personal, 5)
        physical = 0
        final_fight = None
        final_scene = None
        final_participants = None
        for index, row in enumerate(chosen):
            participants = [(account, main), (account, hero["id"])]
            if index == 0:
                participants.append((third_account, third["id"]))
            with store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
                ).fetchone()["id"]
            group_key = (row["map_id"], row["instance_id"], row["group_id"])
            lease, members = groups.claim(group_key, fixture.generation, fight_id)
            groups.finish(lease, defeated=True)
            actors = {
                member["id"]: SimpleNamespace(controlled=False, team=1, hp=0)
                for member in members
            }
            durable = []
            with store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s",
                    (fight_id,),
                )
                for owner, identity in participants:
                    character = store.character(owner, identity, db)
                    actors[identity] = Actor(
                        identity,
                        0,
                        (character["x"], character["y"], character["z"]),
                        character["hp"],
                        6,
                        3,
                        0,
                        character["effective_level"],
                        owner_id=owner,
                        controlled=True,
                    )
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                        "VALUES(%s,%s,%s,0)",
                        (fight_id, identity, owner),
                    )
                    durable.append(dict(account_id=owner, character_id=identity))
                # This is an explicit terminal receipt component, not a paid
                # battle. Native population/UIDs, claimed lease and actual public
                # achievement/gameplay adapter provide progress authority.
                fight = SimpleNamespace(
                    id=fight_id,
                    phase="finished",
                    winner=0,
                    actors=actors,
                    native_summon_registrations={},
                )
                scene = dict(
                    fixture.location,
                    original_entities=deepcopy(members),
                    group_lease=lease,
                )
                combat_adapter.settle_participants(
                    db, store, fight, durable, members, environmental_scene=scene
                )
            physical += len(members)
            fixture.clock[0] = max(time.time() + 1, fixture.clock[0] + 1)
            event, current, objective, entitled = views()
            for identity in identities:
                self.assertEqual(current[identity][2]["nbMobGlobal"], physical)
                self.assertEqual(current[identity][2]["nbMobMin"], 20)
            self.assertEqual(current[main][2]["nbMobPlayer"], physical)
            self.assertEqual(current[hero["id"]][2]["nbMobPlayer"], physical)
            self.assertEqual(current[third["id"]][2]["nbMobPlayer"], third_personal)
            if physical < 20:
                self.assertEqual(entitled, [])
                self.assertTrue(
                    all(
                        participant["completed_at_ms"] is None
                        for participant, _, _ in current.values()
                    )
                )
            final_fight, final_scene, final_participants = fight, scene, durable
        self.assertEqual(physical, 20)
        self.assertEqual(event["state"], "completed")
        self.assertEqual(set(entitled), {main, hero["id"]})
        for identity in (main, hero["id"]):
            participant, view, projection = current[identity]
            self.assertIsNotNone(participant["completed_at_ms"])
            self.assertIsNotNone(view["native_result"])
        self.assertIsNone(current[third["id"]][0]["completed_at_ms"])
        self.assertIsNone(current[third["id"]][1]["native_result"])
        # A native terminal failure for C is legitimate; only an earned
        # native_result may close the client model as personal success.

        def balances():
            with store.connection() as db:
                return {
                    identity: (
                        db.execute(
                            "SELECT xp FROM character_progression WHERE character_id=%s",
                            (identity,),
                        ).fetchone()["xp"],
                        db.execute(
                            "SELECT coalesce(sum(quantity),0) AS n FROM inventory_items "
                            "WHERE character_id=%s AND reference=21118",
                            (identity,),
                        ).fetchone()["n"],
                    )
                    for identity in identities
                }

        before_claim = balances()
        with store.connection() as db:
            earned_xp = {
                row["character_id"]: row["awarded_xp"]
                for row in db.execute(
                    "SELECT character_id,awarded_xp FROM environmental_entitlement_xp_rates "
                    "WHERE character_id=ANY(%s)",
                    ([main, hero["id"]],),
                ).fetchall()
            }
        self.assertEqual(set(earned_xp), {main, hero["id"]})
        with store.connection() as db:
            for owner, identity in (
                (account, main),
                (account, hero["id"]),
                (third_account, third["id"]),
            ):
                storage.claim_pending(
                    db,
                    store,
                    account_id=owner,
                    character_id=identity,
                    now_ms=int(fixture.clock[0] * 1000),
                )
        after_claim = balances()
        for identity in (main, hero["id"]):
            self.assertEqual(
                after_claim[identity],
                (
                    before_claim[identity][0] + earned_xp[identity],
                    before_claim[identity][1] + 24,
                ),
            )
        self.assertEqual(after_claim[third["id"]], before_claim[third["id"]])
        with store.connection() as db:
            combat_adapter.settle_participants(
                db,
                store,
                final_fight,
                final_participants,
                final_scene["original_entities"],
                environmental_scene=final_scene,
            )
            for owner, identity in (
                (account, main),
                (account, hero["id"]),
                (third_account, third["id"]),
            ):
                storage.claim_pending(
                    db,
                    store,
                    account_id=owner,
                    character_id=identity,
                    now_ms=int(fixture.clock[0] * 1000),
                )
        self.assertEqual(balances(), after_claim)
