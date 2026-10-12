"""Local task schema and authoritative-fact rules without DB or native UI."""
from custom_task_fixtures import task_definitions
import copy
import unittest
from wakfu_server.custom_tasks import catalog, engine


class CustomTaskCoreTests(unittest.TestCase):
    def test_defaults_match_reviewed_gobball_and_seed_bindings(self):
        definitions = catalog.validate(task_definitions())
        self.assertEqual(set(definitions), {"gobball-kills-20", "gobball-seeds-20"})
        self.assertEqual(
            definitions["gobball-seeds-20"]["predicate"],
            {
                "kind": "monster_seed_planted",
                "family_id": 68,
                "seed_reference": 7361,
                "resource_reference": 192,
            },
        )
        self.assertTrue(all(not row["rewards"] for row in definitions.values()))
        rule = definitions["gobball-kills-20"]
        payload = engine.event_payload(
            {
                "kind": "original_monster_killed",
                "fight_id": 1,
                "actors": [
                    {"actor_id": -7, "reference": 1},
                    {"actor_id": -3, "reference": 4086},
                    {"actor_id": -1, "reference": 99999},
                ],
            }
        )
        self.assertEqual(engine.increment(rule, payload), 2)

    def test_event_signature_is_order_independent_but_fact_sensitive(self):
        event = {
            "kind": "original_monster_killed",
            "fight_id": 1,
            "actors": [
                {"actor_id": 2, "reference": 1},
                {"actor_id": 1, "reference": 2},
            ],
        }
        reordered = copy.deepcopy(event)
        reordered["actors"].reverse()
        self.assertEqual(
            engine.event_signature(event), engine.event_signature(reordered)
        )
        reordered["actors"][0]["reference"] = 3
        self.assertNotEqual(
            engine.event_signature(event)[1], engine.event_signature(reordered)[1]
        )

    def test_duplicates_failed_status_and_client_count_are_rejected(self):
        actor = {"actor_id": 1, "reference": 1}
        invalid = [
            {
                "kind": "original_monster_killed",
                "fight_id": 1,
                "actors": [actor, actor],
            },
            {
                "kind": "original_monster_killed",
                "fight_id": 1,
                "actors": [],
                "count": 20,
            },
            {
                "kind": "monster_seed_planted",
                "family_ids": [68],
                "seed_reference": 7361,
                "resource_reference": 192,
                "operation_id": "x",
                "success": False,
            },
            {
                "kind": "original_monster_killed",
                "fight_id": 1,
                "actors": [{"actor_id": True, "reference": 1}],
            },
        ]
        for event in invalid:
            with self.subTest(event=event), self.assertRaises(ValueError):
                engine.event_payload(event)

    def test_plant_requires_exact_family_seed_and_resource(self):
        rule = catalog.validate(task_definitions())["gobball-seeds-20"]
        event = {
            "kind": "monster_seed_planted",
            "family_ids": [68],
            "seed_reference": 7361,
            "resource_reference": 192,
            "operation_id": "12345678123456789234123456789abc",
        }
        self.assertEqual(engine.increment(rule, engine.event_payload(event)), 1)
        self.assertEqual(
            engine.increment(rule, engine.event_payload(dict(event, family_ids=[69]))),
            0,
        )
        for field in ("seed_reference", "resource_reference"):
            changed = dict(event, **{field: event[field] + 1})
            self.assertEqual(engine.increment(rule, engine.event_payload(changed)), 0)
        rule["enabled"] = False
        self.assertEqual(engine.increment(rule, engine.event_payload(event)), 0)

    def test_definition_semantics_immutable_but_presentation_and_enable_mutable(self):
        rule = catalog.validate(task_definitions())["gobball-kills-20"]
        original = catalog.signature(rule)
        for field, value in [
            ("enabled", False),
            ("title", "Other title"),
            ("description", "Other text"),
        ]:
            changed = copy.deepcopy(rule)
            changed[field] = value
            self.assertEqual(catalog.signature(changed), original)
        changed = copy.deepcopy(rule)
        changed["target"] = 21
        self.assertNotEqual(catalog.signature(changed), original)

    def test_strict_definition_and_reward_shapes(self):
        for field, value in [
            ("target", True),
            ("enabled", 1),
            ("key", "Bad key"),
            ("title", "\ud800"),
            ("rewards", [{"aeV": 17, "ckl": [1]}]),
        ]:
            source = copy.deepcopy(task_definitions())
            source[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                catalog.validate(source)
        source = copy.deepcopy(task_definitions())
        source[0]["rewards"] = [
            {"aeV": 5, "ckl": [12686, 20]},
            {"aeV": 6, "ckl": [100]},
        ]
        self.assertEqual(
            len(catalog.validate(source)["gobball-kills-20"]["rewards"]), 2
        )

    def test_canonical_source_keys_and_strict_operation_uuid(self):
        fight = engine.event_payload(
            {
                "kind": "original_monster_killed",
                "fight_id": 27,
                "actors": [{"actor_id": -1, "reference": 1}],
            }
        )
        self.assertEqual(engine.canonical_event_key(fight), "fight:27")
        seed = {
            "kind": "monster_seed_planted",
            "family_ids": [68],
            "seed_reference": 7361,
            "resource_reference": 192,
            "operation_id": "12345678123456789234123456789abc",
        }
        self.assertEqual(
            engine.canonical_event_key(engine.event_payload(seed)),
            "planting:12345678123456789234123456789abc",
        )
        for invalid in (
            "free-string",
            "12345678-1234-5678-9234-123456789abc",
            "12345678123456789234123456789ABC",
            "00000000-0000-0000-0000-000000000000",
            "0" * 32,
            123,
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                engine.event_payload(dict(seed, operation_id=invalid))
        for invalid in (True, 0, -1, 2**63):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                engine.event_payload(dict(fight, fight_id=invalid))

    def test_multi_family_binding_preserved_and_canonicalized(self):
        event = {
            "kind": "monster_seed_planted",
            "family_ids": [69, 68],
            "seed_reference": 7361,
            "resource_reference": 192,
            "operation_id": "12345678123456789234123456789abc",
        }
        payload, signature = engine.event_signature(event)
        self.assertEqual(payload["family_ids"], [68, 69])
        self.assertEqual(
            signature, engine.event_signature(dict(event, family_ids=[68, 69]))[1]
        )
        self.assertNotEqual(
            signature, engine.event_signature(dict(event, family_ids=[68]))[1]
        )
        rule = catalog.validate(task_definitions())["gobball-seeds-20"]
        self.assertEqual(engine.increment(rule, payload), 1)
        for families in ([], [68, 68], [True], [0], "68"):
            with self.subTest(families=families), self.assertRaises(ValueError):
                engine.event_payload(dict(event, family_ids=families))


class DatabaseTaskCatalogTests(unittest.TestCase):
    def test_sql_authority_is_required_and_no_python_default_exists(self):
        from unittest.mock import Mock

        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        with self.assertRaises(ValueError):
            catalog.validate(db=db)
        db.execute.assert_called_once_with(
            "SELECT value FROM settings WHERE name=%s", ("custom_task_definitions",)
        )
        self.assertFalse(hasattr(catalog, "DEFAULT_DEFINITIONS"))
        db.execute.return_value.fetchone.return_value = {"value": task_definitions()}
        self.assertEqual(catalog.validate(db=db), catalog.validate(task_definitions()))
