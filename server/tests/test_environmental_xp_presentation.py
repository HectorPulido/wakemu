"""Completion-frozen native XP ratio precedes the selected owned result."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from wakfu_server import heroes, wire
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents


class EnvironmentalXpPresentationTests(unittest.TestCase):
    def test_native_single_key_rate_and_owned_result_order_preserve_frozen_amount(self):
        from test_environmental_durable_lifecycle import (
            EnvironmentalDurableLifecycleTests,
        )
        from test_environmental_reward_bands import (
            EnvironmentalRewardBandPostgresTests,
            SOURCE,
        )

        fixture = EnvironmentalDurableLifecycleTests(
            "test_shared_progress_rewards_only_real_contributors"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        store = fixture.store
        main = fixture.character["id"]
        hero = store.create_character(fixture.account, "Rate Hero")
        heroes.add(store, fixture.account, fixture.generation, main, hero["id"])
        with store.connection() as db:
            self.native = [
                dict(row)
                for row in db.execute(
                    "SELECT r.reward_id,d.primary_result_index,d.primary_reward_list,r.native_text "
                    "FROM environmental_native_rewards_raw r JOIN environmental_native_reward_display d "
                    "USING(source_key,scenario_id,reward_id) WHERE r.source_key=%s AND r.scenario_id=-2247 "
                    "AND d.primary_reward_list ORDER BY d.primary_result_index",
                    (SOURCE,),
                ).fetchall()
            ]
            EnvironmentalRewardBandPostgresTests._profile(
                self, db, "rate-ui", seal=False
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET map_id=527,region_id=17,level_min=1,duration_ms=60000,anchor_ms=%s WHERE profile_key='rate-ui'",
                (fixture.now_ms - 1000,),
            )
            db.execute(
                "UPDATE environmental_profile_objectives SET target_reference=1337,action_id=3,resource_step=1,unit='quantity' WHERE profile_key='rate-ui'"
            )
            db.execute(
                "INSERT INTO environmental_profile_evaluation VALUES('rate-ui',1,'score_at_deadline',1,'character_id','test-declared evaluator')"
            )
            for state, ordinal in (
                ("proposed", 0),
                ("active", 1),
                ("completed", 2),
                ("expired", 3),
                ("cancelled", 3),
            ):
                db.execute(
                    "INSERT INTO environmental_profile_publication_states VALUES('rate-ui',1,%s,%s)",
                    (state, ordinal),
                )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='rate-ui'"
            )
        admitted = fixture.admit()
        event = admitted["instances"][0]["instance_id"]
        fixture.roster(event, [8801, 8802])
        for identity, entity, quantity in ((main, 8801, 30), (hero["id"], 8802, 20)):
            fixture.consume(
                replace(
                    fixture.fact(entity, character=dict(id=identity)), quantity=quantity
                )
            )
        now = fixture.now_ms + 60000
        with store.connection() as db:
            storage.refresh(
                db,
                account_id=fixture.account,
                character_id=main,
                location=fixture.location,
                now_ms=now,
            )
            frozen = db.execute(
                "SELECT character_id,base_xp,awarded_xp FROM environmental_entitlement_xp_rates ORDER BY character_id"
            ).fetchall()
            self.assertEqual(
                {row["character_id"] for row in frozen}, {main, hero["id"]}
            )
            self.assertTrue(
                all(row["awarded_xp"] == row["base_xp"] * 10 for row in frozen)
            )
            before = {
                row["character_id"]: row["xp"]
                for row in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    ([main, hero["id"]],),
                ).fetchall()
            }
            db.execute(
                "INSERT INTO combat_reward_policy_versions(version,xp_rate_bp,kamas_rate_bp,conquest_rate_bp) VALUES(999,20000,10000,10000)"
            )
            db.execute(
                "UPDATE combat_reward_policy_active SET version=999 WHERE singleton"
            )
        snapshot = service.refresh(
            store,
            fixture.account,
            fixture.generation,
            main,
            location=fixture.location,
            now_ms=now,
        )
        main_result = next(
            row
            for row in snapshot["deliveries"]
            if row["kind"] == "completed" and row["character_id"] == main
        )
        hero_result = next(
            row
            for row in snapshot["deliveries"]
            if row["kind"] == "completed" and row["character_id"] == hero["id"]
        )
        self.assertTrue(hero_result["deferred_selected_result"])
        self.assertNotIn(13263, [op for op, _ in hero_result["packets"]])
        result_ops = [op for op, _ in main_result["packets"]]
        self.assertEqual(result_ops[result_ops.index(13263) - 1], 22318)
        self.assertEqual(main_result["result_view"]["xp_rate_bp"], 100000)
        self.assertIn(wire.native_xp_rate_packet(100000), main_result["packets"])
        with store.connection() as db:
            after = {
                row["character_id"]: row["xp"]
                for row in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    ([main, hero["id"]],),
                ).fetchall()
            }
        self.assertEqual(
            after,
            {
                row["character_id"]: before[row["character_id"]] + row["awarded_xp"]
                for row in frozen
            },
        )
        batches = []
        world = SimpleNamespace(
            scope_presence=fixture.presence_world.scope_presence,
            send_batch_to=lambda *args: batches.append(args[-1]) or False,
        )
        from test_environmental_company import EnvironmentalCompanyPostgresTests

        template, roster = EnvironmentalCompanyPostgresTests.native_template(self)
        cursor = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster
        )
        with patch.object(service, "refresh", return_value=snapshot), patch.object(
            service, "acknowledge"
        ) as ack:
            self.assertFalse(
                cursor.refresh(
                    store,
                    world,
                    fixture.account,
                    fixture.generation,
                    main,
                    location=fixture.location,
                    ready=True,
                    checkpoint=lambda: None,
                    now_ms=now,
                )
            )
            ack.assert_not_called()
            opcodes = [op for op, _ in batches[-1]]
            self.assertEqual(opcodes.count(22318), 1)
            self.assertEqual(opcodes[opcodes.index(13263) - 1], 22318)
            self.assertNotIn(22318, opcodes[opcodes.index(13263) + 1 :])
            self.assertEqual(
                next(body for op, body in batches[-1] if op == 22318),
                wire.native_xp_rate_packet(100000)[1],
            )
        # Startup hooks must publish after full23053 and before selected UI.
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        replay = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "replay"
        )
        initial = next(
            node
            for node in replay.body
            if isinstance(node, ast.If) and "start == 45" in ast.unparse(node.test)
        )
        self.assertIn("native_current_xp_rate()", ast.unparse(initial))
        config = next(
            node
            for node in ast.walk(replay)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "frame['opcode'] == 23053"
        )
        self.assertLess(
            ast.unparse(config).index("hero_configuration(original)"),
            ast.unparse(config).index("native_current_xp_rate()"),
        )
        vectors = Path(
            ".runtime/parallel-readiness-20261021/repro-084dc694/xp-rate-native-vectors.bin"
        )
        vectors.parent.mkdir(parents=True, exist_ok=True)
        with vectors.open("wb") as stream:
            for rate in (100000, 20000):
                opcode, body = wire.native_xp_rate_packet(rate)
                self.assertEqual(opcode, 22318)
                stream.write(struct.pack(">I", len(body)) + body)
