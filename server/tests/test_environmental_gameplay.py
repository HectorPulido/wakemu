import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from wakfu_server.objectives import environmental_gameplay as gameplay
from wakfu_server.objectives.environmental_runtime import objective_increment


class EnvironmentalGameplayTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.world import World

        world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        world.join(
            "live",
            object(),
            dict(id=5, account_id=4, map_id=7, instance_id=19, x=0, y=0, z=0),
        )
        live = patch.object(gameplay.presence, "_world", world)
        live.start()
        self.addCleanup(live.stop)

    def test_owned_winning_roster_keeps_each_entity_and_frozen_scene_on_replay(self):
        receipt = {"fight_id": 12, "original_monsters": [[-81, 92], [-82, 92]]}
        db = Mock()
        db.execute.return_value.fetchone.return_value = {
            "payload": receipt,
            "created_at": datetime(2026, 10, 22, tzinfo=timezone.utc),
        }
        admitted = {"map_id": 7, "instance_id": 19, "region_id": 3}
        batches = []
        with patch.object(
            gameplay,
            "consume",
            side_effect=lambda db, facts: batches.append(facts) or (),
        ):
            for _ in range(2):
                gameplay.settled_fight(
                    db,
                    account_id=4,
                    character_id=5,
                    fight_id=12,
                    source_scene=admitted,
                )
        self.assertEqual(batches[0], batches[1])
        self.assertEqual([f.entity_id for f in batches[0]], [-81, -82])
        self.assertEqual({f.receipt_key for f in batches[0]}, {"fight:12"})
        self.assertEqual(
            {(f.map_id, f.instance_id, f.region_id) for f in batches[0]}, {(7, 19, 3)}
        )
        self.assertEqual(batches[0][0].occurred_at_ms, 1792627200000)
        # A later selected-character move is not a source query or a new scene.
        self.assertNotIn("SELECT map_id", db.execute.call_args.args[0])
        self.assertEqual(db.execute.call_args.args[1], (5, "fight:12", 4))
        receipt["original_monsters"][0][0] = -99
        self.assertEqual(batches[0][0].entity_id, -81)
        with self.assertRaises(FrozenInstanceError):
            batches[0][0].entity_id = -99

    def test_resource_stage_membership_and_yield_are_distinct_from_planting(self):
        resource = dict(
            resource_uid=90, resource_reference=15, stage=2, map_id=7, instance_id=19
        )
        receipt = dict(
            token="harvest-token",
            account_id=4,
            character_id=5,
            resource_uid=90,
            action_id=6,
            result=dict(stage=1, quantity=9),
        )
        fact = gameplay.resource_fact(
            account_id=4,
            character_id=5,
            token="harvest-token",
            receipt=receipt,
            resource=resource,
            occurred_at_ms=1000,
        )
        member = dict(entity_kind="resource", entity_id=90, reference=15)
        objective = dict(
            family="resource_collect",
            required_quantity=10,
            target_reference=15,
            resource_step=2,
            action_id=6,
        )
        self.assertEqual((fact.quantity, fact.interaction_count), (9, 1))
        self.assertEqual(objective_increment(objective, fact, membership=member), 1)
        self.assertEqual(
            objective_increment(
                dict(objective, unit="quantity"), fact, membership=member
            ),
            9,
        )
        self.assertEqual(
            objective_increment(objective, fact, membership=dict(member, entity_id=91)),
            0,
        )
        self.assertEqual(
            objective_increment(
                dict(objective, resource_step=1), fact, membership=member
            ),
            0,
        )
        self.assertEqual(
            objective_increment(
                dict(objective, family="resource_plant"), fact, membership=member
            ),
            0,
        )
        self.assertEqual(objective_increment(objective, fact, membership=None), 0)

    def test_planting_authentication_precedes_contribution_and_failure_is_empty(self):
        db = Mock()
        db.execute.return_value.fetchall.return_value = []
        db.execute.return_value.fetchone.return_value = None
        with patch.object(gameplay, "consume") as consumed:
            with self.assertRaisesRegex(ValueError, "owned"):
                gameplay.committed_planting(
                    db, account_id=44, character_id=5, operation_id="op"
                )
            consumed.assert_not_called()
        query, parameters = db.execute.call_args.args
        self.assertIn("c.account_id=%s", query)
        self.assertEqual(parameters, ("op", 5, 44))
        db.execute.return_value.fetchone.return_value = dict(success=False)
        with patch.object(gameplay, "consume") as consumed:
            self.assertEqual(
                gameplay.committed_planting(
                    db, account_id=4, character_id=5, operation_id="op"
                ),
                (),
            )
            consumed.assert_not_called()
        row = dict(
            operation_id="op",
            character_id=5,
            success=True,
            request=dict(action_id=8),
            resource=dict(
                resource_uid=20,
                resource_reference=15,
                map_id=7,
                instance_id=19,
                stage=1,
                creation_time=1000,
            ),
        )
        db.execute.return_value.fetchone.return_value = row
        with patch.object(gameplay, "consume", side_effect=lambda db, facts: facts):
            facts = gameplay.committed_planting(
                db, account_id=4, character_id=5, operation_id="op"
            )
        self.assertEqual(
            (facts[0].kind, facts[0].occurred_at_ms, facts[0].after_step),
            ("resource_planted", 1000, 1),
        )

    def test_destroy_requires_actual_action3_and_never_matches_a_fight(self):
        monster = dict(id=-81, ref=92, map_id=7, instance_id=19)
        receipt = dict(
            token="destroy",
            character_id=5,
            monster_id=-81,
            map_id=7,
            instance_id=19,
            action_id=8,
            quantity=1,
            action_kind="destroy",
            monster_action_type=3,
            destroyed=True,
        )
        fact = gameplay.monster_action_fact(
            account_id=4,
            character_id=5,
            token="destroy",
            receipt=receipt,
            monster=monster,
            occurred_at_ms=1000,
        )
        member = dict(entity_kind="monster", entity_id=-81, reference=92)
        objective = dict(family="monster_destroy", required_quantity=5)
        self.assertEqual(objective_increment(objective, fact, membership=member), 1)
        won = gameplay.fight_facts(
            account_id=4,
            character_id=5,
            map_id=7,
            instance_id=19,
            fight_id=12,
            occurred_at_ms=1000,
            receipt=dict(fight_id=12, original_monsters=[[-81, 92]]),
        )[0]
        self.assertEqual(objective_increment(objective, won, membership=member), 0)
        for wrong in (
            dict(receipt, destroyed=False),
            dict(receipt, monster_action_type=1),
        ):
            with self.assertRaises(ValueError):
                gameplay.monster_action_fact(
                    account_id=4,
                    character_id=5,
                    token="destroy",
                    receipt=wrong,
                    monster=monster,
                    occurred_at_ms=1000,
                )
        with self.assertRaises(ValueError):
            replace(fact, character_id=True)
        with self.assertRaises(ValueError):
            gameplay.fight_facts(
                account_id=4,
                character_id=5,
                map_id=7,
                instance_id=19,
                fight_id=12,
                occurred_at_ms=1000,
                receipt=dict(fight_id=12, original_monsters=[[-81, 92], [-81, 92]]),
            )

    def test_real_resource_and_fight_bridges_resolve_frozen_source_regions(self):
        db = Mock()
        db.execute.return_value.fetchall.return_value = []
        resource = dict(
            resource_uid=90,
            resource_reference=15,
            stage=2,
            map_id=7,
            instance_id=19,
            x=12,
            y=13,
            z=0,
        )
        db.execute.return_value.fetchone.return_value = dict(
            token="real",
            account_id=4,
            character_id=5,
            resource_uid=90,
            action_id=6,
            result=dict(stage=1, quantity=9),
            completed_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
        )
        with patch(
            "wakfu_server.territory_cells.region_at", return_value=3
        ) as locate, patch.object(
            gameplay, "consume", side_effect=lambda db, facts: facts
        ):
            facts = gameplay.committed_resource(
                db, account_id=4, character_id=5, token="real", resource=resource
            )
            self.assertEqual(facts[0].region_id, 3)
            locate.assert_called_once_with(7, 12, 13)
        db.execute.return_value.fetchone.return_value = dict(
            payload=dict(fight_id=12, original_monsters=[[-81, 92], [-82, 93]]),
            created_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
        )
        original = [dict(id=-81, ref=92, x=12, y=13), dict(id=-82, ref=93, x=22, y=23)]
        with patch(
            "wakfu_server.territory_cells.region_at", side_effect=[3, 4]
        ), patch.object(gameplay, "consume", side_effect=lambda db, facts: facts):
            facts = gameplay.settled_fight(
                db,
                account_id=4,
                character_id=5,
                fight_id=12,
                source_scene=dict(map_id=7, instance_id=19, original_entities=original),
            )
            self.assertEqual(
                [(f.entity_id, f.region_id) for f in facts], [(-81, 3), (-82, 4)]
            )
        original[1]["ref"] = 999
        with patch(
            "wakfu_server.territory_cells.region_at", return_value=3
        ), self.assertRaisesRegex(ValueError, "original scene roster"):
            gameplay.settled_fight(
                db,
                account_id=4,
                character_id=5,
                fight_id=12,
                source_scene=dict(map_id=7, instance_id=19, original_entities=original),
            )

    def test_combat_adapter_freezes_original_generator_and_preserves_existing_packet_contract(
        self,
    ):
        from types import SimpleNamespace
        from wakfu_server.achievements import combat_adapter, service

        actor = lambda controlled, team: SimpleNamespace(
            controlled=controlled, team=team, hp=0
        )
        fight = SimpleNamespace(
            id=12,
            phase="finished",
            winner=0,
            native_summon_registrations={},
            actors={5: actor(True, 0), -81: actor(False, 1)},
        )
        store = Mock()
        store.character.return_value = dict(id=5, account_id=4)
        originals = [dict(id=-81, ref=92, x=12, y=13, z=0)]
        scene = dict(map_id=7, instance_id=19)
        with patch.object(
            service, "settle", return_value=dict(packets=[(13295, b"owned")])
        ) as settled, patch(
            "wakfu_server.custom_tasks.adapters.original_kills",
            return_value=dict(updated=[], completed=[]),
        ), patch.object(
            gameplay, "settled_fight", return_value=("progress",)
        ) as environmental:
            delivery = combat_adapter.settle_participants(
                object(),
                store,
                fight,
                [dict(account_id=4, character_id=5)],
                (row for row in originals),
                environmental_scene=scene,
            )
        self.assertEqual(delivery["packets_by_owner"], {4: [(13295, b"owned")]})
        self.assertEqual(delivery["environmental_updates"], ("progress",))
        self.assertEqual(settled.call_args.args[-1], [dict(id=-81, ref=92)])
        frozen = environmental.call_args.kwargs["source_scene"]
        self.assertEqual(frozen, dict(scene, original_entities=tuple(originals)))
        originals[0]["x"] = 999
        self.assertEqual(frozen["original_entities"][0]["x"], 12)
