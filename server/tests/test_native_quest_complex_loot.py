"""Exact native quest rows need a reviewed source-bound permission."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server import combat_drops
from wakfu_server import native_quest_complex_loot as policy

ROW = {
    "complex_criteria": True,
    "conditions": [],
    "is_loot_table": False,
    "native_csE": 1,
    "native_csF": 0,
    "probability": 1.0,
    "quantity_max": 1,
    "quantity_min": 1,
    "reference_id": 18747,
    "roll_count": -1,
}


class NativeQuestComplexLootTests(unittest.TestCase):
    def setUp(self):
        contract = policy.contracts()[0]
        self.permission = dict(
            schema=policy.SCHEMA,
            fight_id=696,
            character_id=369,
            instance_id=144115188075855919,
            route_key="owned-native-source",
            policy_version=1,
            rows=[
                dict(
                    contract=contract["id"],
                    contract_sha256=policy.digest(contract),
                    monster_reference=contract["monster_reference"],
                    item_reference=contract["item_reference"],
                    native_row_sha256=contract["native_row_sha256"],
                )
            ],
        )

    def plan(self, *, permission=True, reference=3249, rows=None):
        return combat_drops.plan_player_drops(
            monsters=[dict(actor_id=-1, reference=reference)],
            character_id=369,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={"quest_complex_loot": self.permission} if permission else {},
            catalog={"monsters": {reference: rows or [deepcopy(ROW)]}},
            rng=lambda upper: 0,
        )

    def test_exact_native_key_row_uses_native_chance_quantity_and_attempt(self):
        self.assertEqual(
            policy.digest(ROW), self.permission["rows"][0]["native_row_sha256"]
        )
        decisions = self.plan()
        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0].success)
        self.assertEqual(
            (
                decisions[0].item_reference,
                decisions[0].quantity,
                decisions[0].attempt_index,
            ),
            (18747, 1, 0),
        )

    def test_missing_permission_and_other_creature_cannot_unlock_complex_row(self):
        self.assertEqual(self.plan(permission=False), ())
        self.assertEqual(self.plan(reference=3250), ())

    def test_changed_native_row_and_unrelated_complex_items_remain_closed(self):
        for mutation in (
            {"probability": 0.5},
            {"quantity_max": 2},
            {"reference_id": 18021},
        ):
            with self.subTest(mutation=mutation):
                self.assertEqual(self.plan(rows=[dict(ROW, **mutation)]), ())
        ordinary = dict(ROW, reference_id=99, complex_criteria=False)
        decisions = self.plan(rows=[ordinary])
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].item_reference, 99)

    def test_forged_contract_and_malformed_context_fail_closed(self):
        self.permission["rows"][0]["contract_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "reviewed contract"):
            self.plan()
        with self.assertRaises(ValueError):
            policy.validate_context({})

    def test_cook_actual_type7_dialogue_payment_consumer_is_exact_and_pinned(self):
        root = Path(__file__).resolve().parents[2]
        with gzip.open(
            root / "database/protocol/npc-dialogues.json.gz", "rt"
        ) as stream:
            native = json.load(stream)
        consumer = dict(
            kind="native_dialogue_payment",
            reference_id=2800,
            action_id=439,
            node_id=2320,
            choice_id=5619,
            objective_id=3085,
            quantity=10,
            native_source_sha256="",
        )
        actual_source = policy.dialogue_consumer_source(consumer, native)
        consumer["native_source_sha256"] = policy.digest(actual_source)
        row = dict(quest_id=1640, item_reference=17829, consumer=consumer)

        node = next(row for row in native["nodes"] if row["id"] == 2320)
        choice = next(row for row in node["choices"] if row["id"] == 5619)
        self.assertEqual(
            (choice["type"], choice["criteria"]),
            (
                7,
                "IsAchievementRunning(1640)&&IsAchievementObjectiveComplete(3085)&&GetItemQuantity(17829)>=10",
            ),
        )
        self.assertEqual(
            consumer["native_source_sha256"],
            "dbb24188ee05cb3908af0a43bb04f576777c898af93f076394fe71c4b33cb905",
        )
        policy.validate_dialogue_consumer(row, native)

        tampered = deepcopy(native)
        tampered_node = next(row for row in tampered["nodes"] if row["id"] == 2320)
        next(row for row in tampered_node["choices"] if row["id"] == 5619)["type"] = 0
        with self.assertRaisesRegex(ValueError, "source changed"):
            policy.validate_dialogue_consumer(row, tampered)

        tampered_criterion = deepcopy(native)
        tampered_node = next(
            row for row in tampered_criterion["nodes"] if row["id"] == 2320
        )
        next(row for row in tampered_node["choices"] if row["id"] == 5619)[
            "criteria"
        ] = "GetItemQuantity(17829)>=9"
        with self.assertRaisesRegex(ValueError, "source changed"):
            policy.validate_dialogue_consumer(row, tampered_criterion)

    def _settlement_context(self, monster_reference):
        from wakfu_server import combat_reward_context
        from wakfu_server.maps import boss_score

        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        fight = SimpleNamespace(
            id=696,
            actors={369: SimpleNamespace(effective_level=11)},
            winner=0,
        )
        character = dict(id=369, account_id=313)
        monsters = [dict(id=-1, ref=monster_reference)]
        reward = {"reward": "native snapshot"}
        drops = {"base": "native drop snapshot"}
        permission = {"authorized": "only native quest row"}
        with (
            patch.object(combat_reward_context, "build_context", return_value=reward),
            patch.object(
                combat_reward_context, "build_drop_context", return_value=drops
            ),
            patch.object(boss_score, "drop_context", return_value={}),
            patch.object(policy, "monster_references", return_value={3249}),
            patch.object(policy, "permission", return_value=permission) as authorize,
        ):
            actual = combat_reward_context.settlement_contexts(
                db, fight, character, monsters, encounter_kind=None
            )
        return actual, authorize, db, fight, character, monsters, permission

    def test_settlement_context_adds_reviewed_permission_only_for_native_3249(self):
        (
            (reward, drops),
            authorize,
            db,
            fight,
            character,
            monsters,
            permission,
        ) = self._settlement_context(3249)
        self.assertEqual(reward, {"reward": "native snapshot"})
        self.assertEqual(
            drops,
            {"base": "native drop snapshot", "quest_complex_loot": permission},
        )
        authorize.assert_called_once_with(
            db, 696, 369, fight=fight, original_monsters=monsters
        )
        self.assertEqual(db.execute.call_count, 2)

    def test_settlement_context_skips_quest_permission_for_ordinary_monsters(self):
        (
            (reward, drops),
            authorize,
            db,
            _fight,
            _character,
            _monsters,
            _permission,
        ) = self._settlement_context(1259)
        self.assertEqual(reward, {"reward": "native snapshot"})
        self.assertEqual(drops, {"base": "native drop snapshot"})
        authorize.assert_not_called()
        self.assertEqual(db.execute.call_count, 2)

    def test_owned_content_loot_does_not_read_absent_or_completed_mission_state(self):
        from wakfu_server import dungeon_runtime_config
        from wakfu_server.achievements import owned_quest_encounters, storage

        encounter = dict(
            encounter_scope="main",
            room_order=1,
            team=0,
            player_team=0,
            context_route_key="quest-map-747-21367-1460",
            context_policy_version=1,
            start_map_id=747,
            instance_id=144115188075855919,
        )
        member = dict(character_id=369)
        originals = [dict(id=-1, ref=3249)]

        def execute(sql, parameters):
            cursor = Mock()
            if "FROM dungeon_room_encounters e" in sql:
                cursor.fetchone.return_value = encounter
            elif (
                "FROM combat_fight_participants" in sql
                or "FROM dungeon_instance_members" in sql
            ):
                cursor.fetchall.return_value = [member]
            elif "FROM dungeon_room_spawn_receipts" in sql:
                cursor.fetchone.return_value = {"members": originals}
            elif "FROM fight_reward_policy_receipts" in sql:
                cursor.fetchone.return_value = {
                    "snapshot": {"context": {"winner_team": 0}}
                }
            else:
                raise AssertionError("Unexpected mission-state query: " + sql)
            return cursor

        db = Mock()
        db.execute.side_effect = execute
        for state in (
            dict(running=[], completed=[]),
            dict(running=[], completed=[2165]),
        ):
            with (
                self.subTest(state=state),
                patch.object(
                    dungeon_runtime_config, "pinned_configuration", return_value={}
                ),
                patch.object(
                    owned_quest_encounters,
                    "policy",
                    return_value={
                        "quest_id": 2165,
                        "roster": [{"reference": 3249, "count": len(originals)}],
                    },
                ),
                patch.object(owned_quest_encounters, "admission_phase") as mission_gate,
                patch.object(
                    storage, "load_locked", return_value=state
                ) as mission_state,
                patch.object(
                    combat_drops,
                    "native_drop_catalog",
                    return_value={"monsters": {3249: [ROW]}},
                ),
                patch.object(policy, "validate_native") as native_guard,
            ):
                permission = policy.permission(db, 696, 369)
            self.assertEqual(permission["character_id"], 369)
            self.assertEqual(permission["rows"][0]["item_reference"], 18747)
            mission_gate.assert_not_called()
            mission_state.assert_not_called()
            native_guard.assert_called_once_with(policy.contracts()[0], [ROW])

    def test_actual_frigost_owned_story_profiles_keep_their_pinned_native_rosters(self):
        root = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
        for slug, quest, expected in (
            ("frigost-hunters-528", 1226, [2402, 2403, 2404, 2405]),
            ("frigost-pirates-529", 1110, [2398, 2400, 2401]),
        ):
            with self.subTest(slug=slug):
                config = json.loads((root / f"{slug}.configuration.json").read_text())
                selected = policy.encounter_policy(config)
                self.assertEqual(selected["quest_id"], quest)
                self.assertEqual(
                    [entry["reference"] for entry in selected["roster"]], expected
                )
                changed_map = deepcopy(config)
                changed_map["compiled_plan"]["asset_map_id"] += 1
                with self.assertRaisesRegex(ValueError, "asset differs"):
                    policy.encounter_policy(changed_map)
                changed_roster = deepcopy(config)
                changed_roster["compiled_plan"]["rooms"][0]["monsters"][0][
                    "role"
                ] = "boss"
                self.assertIsNone(policy.encounter_policy(changed_roster))


if __name__ == "__main__":
    unittest.main()
