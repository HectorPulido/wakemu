"""Real resource actions, loaded hero eligibility and durable native publication."""
import base64
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from protocol_codec import Reader
from wakfu_server.characters import heroes
from wakfu_server.objectives import environmental_company as company
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives.environmental_gameplay import GameplayFact
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents
from test_environmental_planting_binding import EnvironmentalPlantingBindingTests


class EnvironmentalCompanyPresenceTests(unittest.TestCase):
    def test_empty_map_projects_no_company_and_never_queries_sql(self):
        fact = GameplayFact(
            "resource_planted",
            "planting:real",
            1,
            1,
            1134,
            17,
            "resource",
            10,
            60,
            100,
            region_id=79001,
            action_id=8,
            after_step=2,
        )
        db = Mock()
        with patch.object(presence, "_world", None):
            self.assertEqual(company.project_interaction(db, fact), ())
        db.execute.assert_not_called()


class EnvironmentalCompanyPostgresTests(unittest.TestCase):
    def setUp(self):
        self.environment = EnvironmentalPlantingBindingTests(
            methodName="test_real_planting_binds_only_declared_matches_and_never_owns_player_crops"
        )
        self.environment.setUp()
        self.addCleanup(self.environment.doCleanups)
        self.flora = self.environment.flora
        self.store = self.flora.store
        self.hero = self.store.create_character(
            self.flora.account, "Environmental Hero"
        )
        self.low = self.store.create_character(self.flora.account, "Environmental Low")
        self.unloaded = self.store.create_character(
            self.flora.account, "Environmental Unloaded"
        )
        from wakfu_server.progression import XP_BY_LEVEL

        self.hero_start_xp = XP_BY_LEVEL[10]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=10 WHERE id=ANY(%s)",
                ([self.hero["id"], self.unloaded["id"]],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=ANY(%s)",
                (self.hero_start_xp, [self.hero["id"], self.unloaded["id"]]),
            )
        for hero in (self.hero, self.low):
            heroes.add(
                self.store,
                self.flora.account,
                self.flora.generation,
                self.flora.character["id"],
                hero["id"],
            )

    def profile(
        self,
        *,
        family="resource_plant",
        mode="collaborative",
        required=1,
        minimum_level=10
    ):
        from wakfu_server.planting import SEEDS

        f = self.flora
        action = SEEDS[4275]["action_id"] if family == "resource_plant" else 100
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('company-real',1,%s,%s,%s,%s,60000,%s,%s,245,'test-only',%s,%s)",
                (
                    family,
                    mode,
                    f.map_id,
                    f.region_id,
                    int(f.clock[0] * 1000) - 1000,
                    minimum_level,
                    "0" * 64,
                    "1" * 64,
                ),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES "
                "('company-real',1,'interact',%s,60,%s,%s,'interaction',%s)",
                (family, action, 2 if family == "resource_plant" else 3, required),
            )
            if family == "resource_plant":
                db.execute(
                    "INSERT INTO environmental_profile_bindings VALUES('company-real',1,'committed_planting','test-only')"
                )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES "
                "('company-real',1,0,'xp',NULL,100,'test-only'),"
                "('company-real',1,1,'item',11423,1,'test-only'),"
                "('company-real',1,2,'kamas',NULL,7,'test-only')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='company-real'"
            )

    def refresh(self):
        f = self.flora
        return service.refresh(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            location=self.environment.location,
            now_ms=int(f.clock[0] * 1000),
        )

    def plant(self, operation="company-plant"):
        f = self.flora
        prepared = f._prepare_plant(f.region_cells[0])
        return prepared, f._plant(prepared, operation)

    def native_template(self):
        from wakfu_server import native_catalog
        from wakfu_server.storage.bootstrap_capture import load

        with native_catalog._database().connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            frames = load(db)
        original = base64.b64decode(
            next(
                r["body_base64"]
                for r in frames
                if r["direction"] == "in" and r["opcode"] == 12666
            )
        )
        reader = Reader(original)
        reader.take(reader.number("H") * 8)
        template = reader.take(reader.number("I"))
        self.assertEqual(template[0], 10)
        roster = base64.b64decode(
            next(
                r["body_base64"]
                for r in frames
                if r["direction"] == "in" and r["opcode"] == 23548
            )
        )
        # Execute only the actual server's pure captured-roster selector. The
        # unfiltered first captured character has a different layout digest.
        import ast
        from pathlib import Path

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        selector = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "character_list_local"
        )
        from wakfu_server import wire

        namespace = dict(Reader=Reader, struct=struct, wire=wire)
        exec(
            compile(ast.Module(body=[selector], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        return template, namespace["character_list_local"](roster)

    def test_native_plant_enrolls_only_loaded_level_eligible_hero_and_retries_owned_publication(
        self,
    ):
        from wakfu_server.progression import XP_BY_LEVEL

        self.hero_start_xp = XP_BY_LEVEL[11] - 50
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (self.hero_start_xp, self.hero["id"]),
            )
        self.profile()
        initial = self.refresh()
        self.assertEqual(initial["instances"], [])  # Main is below level10.
        with self.store.connection() as db:
            enrolled = db.execute(
                "SELECT character_id FROM environmental_participants"
            ).fetchall()
            self.assertEqual([r["character_id"] for r in enrolled], [self.hero["id"]])
        prepared, result = self.plant()
        self.assertEqual(len(result["environmental_updates"]), 1)
        self.assertTrue(self.flora._plant(prepared, "company-plant")["duplicate"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions"
                ).fetchone()["n"],
                1,
            )
            before = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (self.flora.account,),
            ).fetchone()["kamas"]
        template, roster = self.native_template()
        connection = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster
        )
        batches = []
        world = SimpleNamespace(
            scope_presence=self.environment.world.scope_presence,
            send_batch_to=lambda *args: batches.append(args[-1]) or False,
        )
        f = self.flora
        location = dict(self.environment.location, x=71, y=72, z=0)
        self.assertFalse(
            connection.refresh(
                self.store,
                world,
                f.account,
                f.generation,
                f.character["id"],
                location=location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=int(f.clock[0] * 1000),
            )
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (self.hero["id"],),
                ).fetchone()["xp"],
                self.hero_start_xp + 100,
            )
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (f.account,),
                ).fetchone()["kamas"],
                before + 7,
            )
            pending = db.execute(
                "SELECT count(*) AS n FROM environmental_publication_outbox WHERE acknowledged_at_ms IS NULL"
            ).fetchone()["n"]
            self.assertGreater(pending, 0)
        world.send_batch_to = lambda *args: batches.append(args[-1]) or True
        self.assertTrue(
            connection.refresh(
                self.store,
                world,
                f.account,
                f.generation,
                f.character["id"],
                location=location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=int(f.clock[0] * 1000),
            )
        )
        updates = [body for opcode, body in batches[-1] if opcode == 13046]
        self.assertEqual(
            len(updates), 2
        )  # Owned format10 followed by absolute format3 statistics.
        self.assertTrue(
            all(struct.unpack(">q", body[:8])[0] == self.hero["id"] for body in updates)
        )
        self.assertEqual([body[10] for body in updates], [10, 3])
        roster_packets = [body for opcode, body in batches[-1] if opcode == 23548]
        self.assertEqual(len(roster_packets), 1)
        self.assertEqual(roster_packets[0][0], 4)
        self.assertNotIn(13613, [opcode for opcode, _ in batches[-1]])
        self.assertIsNone(connection.claimed_character)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox WHERE acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
        main = self.store.character(f.account, f.character["id"])
        hero = self.store.character(f.account, self.hero["id"])
        self.assertEqual(hero["level"], 11)
        self.assertEqual(
            sum(
                r["quantity"]
                for r in hero["inventory_items"]
                if r["reference"] == 11423
            ),
            1,
        )
        self.assertEqual(
            sum(
                r["quantity"]
                for r in main["inventory_items"]
                if r["reference"] == 11423
            ),
            0,
        )

    def test_actual_harvest_credits_loaded_players_once_globally_and_never_replays(
        self,
    ):
        from wakfu_server import resource_collect

        self.profile(family="resource_collect", required=2, minimum_level=1)
        event = self.refresh()["instances"][0]["instance_id"]
        f = self.flora
        resource = f._insert_resource(f.region_cells[0], resource_uid=700099, stage=3)
        with self.store.connection() as db:
            storage.register_memberships(
                db,
                event,
                [
                    dict(
                        entity_kind="resource",
                        entity_id=resource["resource_uid"],
                        reference=60,
                        source_key="test-real-harvest",
                    )
                ],
            )
        ticket = f._resource_ticket(resource, 100)
        f._advance_harvest()
        result = resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertEqual(len(result["environmental_updates"]), 3)
        with self.store.connection() as db:
            self.assertEqual(
                storage._progress(db, dict(instance_id=event)), {"interact": 1}
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts"
                ).fetchone()["n"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
        self.assertFalse(
            resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )

    def test_removed_hero_receipt_cannot_be_acknowledged_by_another_loaded_character(
        self,
    ):
        self.profile()
        self.refresh()
        self.plant()
        claimed = self.refresh()
        hero_keys = [
            r["delivery_key"]
            for r in claimed["deliveries"]
            if r["character_id"] == self.hero["id"]
        ]
        self.assertTrue(hero_keys)
        f = self.flora
        heroes.remove(
            self.store, f.account, f.generation, f.character["id"], self.hero["id"]
        )
        self.assertEqual(
            service.acknowledge(
                self.store, f.account, f.generation, f.character["id"], hero_keys
            ),
            0,
        )
        self.assertFalse(
            any(
                r["character_id"] == self.hero["id"]
                for r in self.refresh()["deliveries"]
            )
        )
        heroes.add(
            self.store, f.account, f.generation, f.character["id"], self.hero["id"]
        )
        resumed = self.refresh()
        self.assertEqual(resumed["hero_rewards"][self.hero["id"]]["delivered"], [])
        self.assertTrue(
            any(r["character_id"] == self.hero["id"] for r in resumed["deliveries"])
        )
        self.assertEqual(
            service.acknowledge(
                self.store, f.account, f.generation, f.character["id"], hero_keys
            ),
            len(hero_keys),
        )
