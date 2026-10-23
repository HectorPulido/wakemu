"""Native item-use descriptor boundary and representative catalog contracts."""
import json
from pathlib import Path
import unittest

from wakfu_server.consumable_catalog import load_plan
from wakfu_server.combat_local_criteria import parse_local_criterion


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Database:
    def __init__(self, row):
        self.row = row
        self.parameters = None

    def execute(self, statement, parameters):
        self.parameters = parameters
        return Cursor(self.row)


class ConsumableCatalogTests(unittest.TestCase):
    def test_reader_is_parameterized_and_returns_detached_plan(self):
        source = dict(
            states=[dict(state_id=1206, metadata=dict(removal_event_ids=[2164]))]
        )
        db = Database(dict(available=True, unsupported_reason="", plan=source))
        plan = load_plan(db, 3745)
        plan["states"][0]["metadata"]["removal_event_ids"].append(9999)
        self.assertEqual(db.parameters, (3745,))
        self.assertEqual(source["states"][0]["metadata"]["removal_event_ids"], [2164])

    def test_malformed_postcommit_emotes_are_rejected_before_use(self):
        for emotes in ([20019], [dict(emote_id=20019, forced=True)], None):
            db = Database(
                dict(
                    available=True,
                    unsupported_reason="",
                    plan=dict(states=[], emotes=emotes),
                )
            )
            with self.assertRaisesRegex(ValueError, "emote"):
                load_plan(db, 3745)

    def test_missing_and_explicitly_unsupported_are_distinct(self):
        self.assertIsNone(load_plan(Database(None), 1))
        with self.assertRaisesRegex(ValueError, "no_native_action_or_effect"):
            load_plan(
                Database(
                    dict(
                        available=False, unsupported_reason="no_native_action_or_effect"
                    )
                ),
                9247,
            )
        for reference in (True, 0, -1, "3745"):
            with self.assertRaises(ValueError):
                load_plan(Database(None), reference)

    def test_native_catalog_preserves_duration_events_and_percentage_heals(self):
        path = Path(__file__).parents[1] / "protocol" / "native-consumable-actions.json"
        rows = json.loads(path.read_text())["items"]
        by_ref = {row["item_ref"]: row for row in rows}
        base = [row for row in rows if row["native_type"] != 738]
        transformations = [row for row in rows if row["native_type"] == 738]
        self.assertEqual(len(base), 239)
        self.assertEqual(len(transformations), 36)
        # Migration221 qualifies the four native anti-KO effects in the base partition.
        self.assertEqual(sum(row["available"] is True for row in base), 232)
        self.assertEqual(sum(row["available"] is True for row in transformations), 36)
        self.assertEqual(len(rows), len(by_ref))
        for row in rows:
            for emote in row["plan"]["emotes"]:
                self.assertEqual(set(emote), {"emote_id", "effect_id", "forced"})
                self.assertIs(type(emote["emote_id"]), int)
                self.assertGreater(emote["emote_id"], 0)
                self.assertIs(type(emote["effect_id"]), int)
                self.assertGreater(emote["effect_id"], 0)
                self.assertIs(emote["forced"], True)
        # Mea Culpable scales duration by the applied state level, not its base.
        mea = by_ref[13551]["plan"]["states"][0]
        self.assertEqual(
            (mea["state_id"], mea["level"], mea["duration_ms"]), (1295, 12, 43200000)
        )
        # A combat-only heal is not executed or treated as a static World stat.
        first_aid = by_ref[13858]
        self.assertTrue(first_aid["available"])
        first_aid_state = first_aid["plan"]["states"][0]
        self.assertEqual(first_aid_state["clock"], "event")
        self.assertEqual(
            first_aid_state["metadata"]["combat_only_effect_ids"], [282786]
        )
        self.assertNotIn(1335, first_aid_state["removes"])
        self.assertEqual(
            first_aid_state["metadata"]["native_effects"]["68563"]["timing"]["delay"][
                0
            ],
            10,
        )
        halloween = by_ref[10374]["plan"]["states"][0]
        self.assertEqual(halloween["clock"], "event")
        self.assertEqual(halloween["metadata"]["removal_event_ids"], [1010, 1030])
        # Subscribed cancellation events do not turn timed food into event-only food.
        self.assertEqual(by_ref[3663]["plan"]["states"][0]["clock"], "online")
        self.assertEqual(by_ref[3663]["plan"]["states"][0]["duration_ms"], 900000)
        # Native three food cancellation families remain separate.
        food = by_ref[3745]["plan"]
        self.assertIn(2164, food["emitted_events"])
        self.assertIn(2164, food["states"][0]["metadata"]["removal_event_ids"])
        self.assertNotIn(2165, food["states"][0]["metadata"]["removal_event_ids"])
        # fnE.sGD is USE; fnE.sGH is EXCHANGE and must never gate eating.
        self.assertEqual(
            by_ref[9811]["plan"]["criterion"], 'GetRealLevel("caster") < 35'
        )
        self.assertEqual(by_ref[14055]["plan"]["criterion"], "")
        self.assertEqual(
            by_ref[14055]["plan"]["native_item_criteria"]["EXCHANGE"], "Faux"
        )
        self.assertEqual(by_ref[19313]["plan"]["heal"]["values"], [10, 2, 4])
        self.assertEqual(by_ref[20416]["plan"]["heal"]["values"], [8, 2, 4])
        # No inferred effect is assigned to the empty legacy consumable.
        self.assertFalse(by_ref[9247]["available"])
        self.assertEqual(
            by_ref[9247]["unsupported_reason"], "no_native_action_or_effect"
        )

    def test_all_native_use_criteria_parse_with_the_shared_restricted_parser(self):
        path = Path(__file__).parents[1] / "protocol" / "native-consumable-actions.json"
        rows = json.loads(path.read_text())["items"]
        criteria = [
            (row["item_ref"], row["plan"]["criterion"])
            for row in rows
            if row.get("plan") and row["plan"].get("criterion")
        ]
        self.assertEqual(
            sum(
                bool(row["plan"].get("criterion"))
                for row in rows
                if row["native_type"] != 738
            ),
            44,
        )
        self.assertEqual(
            sum(
                bool(row["plan"].get("criterion"))
                for row in rows
                if row["native_type"] == 738
            ),
            34,
        )
        for item_ref, criterion in criteria:
            with self.subTest(item_ref=item_ref, criterion=criterion):
                self.assertIsNotNone(parse_local_criterion(criterion))

    def test_outcome_expansion_preserves_native_contextual_children(self):
        path = Path(__file__).parents[1] / "protocol" / "native-consumable-actions.json"
        rows = {row["item_ref"]: row for row in json.loads(path.read_text())["items"]}
        for reference in (18351, 18355, 18401, 18406):
            self.assertTrue(rows[reference]["available"])
            state = rows[reference]["plan"]["states"][0]
            metadata = state["metadata"]
            self.assertEqual((state["clock"], state["duration_ms"]), ("event", 0))
            self.assertEqual(metadata["counter"]["fight_models"], [2, 24, 73, 76])
            root = metadata["native_effects"][
                str(metadata["combat_only_effect_ids"][0])
            ]
            self.assertEqual(root["native_metadata"]["target_masks"][5], [1026])
            self.assertEqual(root["criteria"], metadata["counter"]["criteria"])
        regeneration = rows[22491]["plan"]["states"][0]
        self.assertEqual(regeneration["duration_ms"], 43200000)
        root = regeneration["metadata"]["native_effects"]["205959"]
        self.assertEqual(root["native_metadata"]["target_masks"][5], [1026, 1028])
        self.assertEqual(root["criteria"], "(not IsBattleground())")
        self.assertEqual(rows[18357]["plan"]["states"][0]["duration_ms"], 604800000)

    def test_xp_handoff_preserves_the_new_native_state_descriptor(self):
        path = Path(__file__).parents[1] / "protocol" / "native-consumable-actions.json"
        row = next(
            row
            for row in json.loads(path.read_text())["items"]
            if row["item_ref"] == 22146
        )
        self.assertTrue(row["available"])
        source = row["plan"]["states"][0]
        self.assertEqual(source["state_id"], 4872)
        self.assertEqual(source["metadata"]["combat_only_effect_ids"], [203486])
        target = source["metadata"]["native_handoff_target"]
        self.assertEqual(
            (target["state_id"], target["level"], target["duration_ms"]),
            (6874, 100, 7200000),
        )
        self.assertEqual(target["effect_ids"], [316696, 316698])
        self.assertNotIn("native_handoff_target", target["metadata"])
        self.assertEqual(
            target["metadata"]["native_effects"]["316698"]["values"], [100]
        )


if __name__ == "__main__":
    unittest.main()
