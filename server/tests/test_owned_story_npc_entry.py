"""Native accepted NPC choices share owned entry without forged portal packets."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_npc_entry as entry
from wakfu_server import dungeon_instances, dungeon_transport
from wakfu_server.achievements import conversation

ROOT = Path(__file__).parents[1]


class OwnedStoryNPCEntryTests(unittest.TestCase):
    def setUp(self):
        self.configuration = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/zinit-reef-980.configuration.json"
            ).read_text()
        )
        self.metadata = self.configuration["route"]["native_npc_entry"]
        self.route = SimpleNamespace(
            key=self.configuration["route"]["key"], start_map_id=980
        )
        self.character = dict(
            id=7, account_id=2, map_id=527, instance_id=0, x=108, y=-20, z=0
        )
        self.row = dict(
            actor_id=-2251799934981740,
            reference_id=1740,
            map_id=527,
            instance_id=0,
            x=109,
            y=-20,
            z=0,
            direction=3,
            dialogue_root=1729,
            action_ids=[158],
            interaction_range=4,
        )
        self.item = dict(
            row=self.row,
            interaction_anchor=dict(x=108, y=-20, z=0),
            choice_routes=[dict(node_id=3206, choice_id=7954, route=self.route.key)],
        )
        self.published = (dict(placements=[self.item]), {}, {})
        self.proof = dict(
            route_key=self.route.key,
            actor_id=self.row["actor_id"],
            reference_id=1740,
            action_id=158,
            node_id=3206,
            choice_id=7954,
            account_id=2,
            char_id=7,
            generation="lease",
            publication_sha256=conversation._digest(self.published[0]),
            placement_sha256=conversation.placement_signature(self.row),
            source_position={
                k: self.character[k] for k in ("map_id", "instance_id", "x", "y", "z")
            },
        )
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = dict(policy_version=1)
        self.store = Mock()
        self.native = dict(
            speakers=[dict(ref=1740, actions=[dict(id=158)])],
            node_index={3206: dict(choices=[dict(id=7954)])},
        )

    def test_explicit_npc_route_loads_without_claiming_a_native_teleporter(self):
        with patch(
            "wakfu_server.npc_dialogue.catalog", return_value=self.native
        ), patch.object(dungeon_instances.protocol_catalog, "load", return_value=[]):
            routes = dungeon_instances._load_routes([self.configuration["route"]])
        route = routes[self.route.key]
        self.assertEqual((route.entry_object_id, route.destination_id), (1740, 7954))
        self.assertIsNone(route.native_template_id)
        malformed = deepcopy(self.configuration["route"])
        malformed["destination_id"] = 123
        with patch(
            "wakfu_server.npc_dialogue.catalog", return_value=self.native
        ), self.assertRaises(ValueError):
            entry.validate_route(malformed)

    def test_source_bound_accepted_choice_uses_the_same_owned_entry_transaction(self):
        from wakfu_server import quest_npc

        with patch(
            "wakfu_server.npc_dialogue.catalog", return_value=self.native
        ), patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration",
            return_value=self.configuration,
        ), patch.object(
            dungeon_instances, "route", return_value=self.route
        ), patch.object(
            quest_npc, "publication", return_value=self.published
        ), patch.object(
            quest_npc, "_row", return_value=(self.row, self.item)
        ), patch.object(
            quest_npc, "_nearby_placement", return_value=True
        ), patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value=dict(running=[], completed=[], objectives=[]),
        ), patch.object(
            dungeon_transport,
            "enter_resolved",
            return_value=dict(instance_id=99, destination=dict(map_id=980)),
        ) as enter:
            result = entry.enter_choice(
                self.db,
                self.store,
                self.character,
                self.proof,
                allowed_position_accounts=frozenset([2]),
            )
            self.assertEqual(result["instance_id"], 99)
            resolved = enter.call_args.args[4]
            self.assertEqual(resolved["source"], self.row)
            self.assertEqual(
                resolved["destination"], dict(map_id=980, x=0, y=-3, z=0, direction=5)
            )
            self.assertIs(enter.call_args.kwargs["_db"], self.db)
            self.assertEqual(
                enter.call_args.kwargs["allowed_position_accounts"], frozenset([2])
            )
            self.assertTrue(
                enter.call_args.kwargs["source_allowed"](self.character, self.row)
            )
            self.assertFalse(
                enter.call_args.kwargs["source_allowed"](
                    dict(self.character, id=8), self.row
                )
            )
            for changed in (
                dict(self.proof, choice_id=7955),
                dict(self.proof, publication_sha256="changed"),
                dict(
                    self.proof,
                    source_position=dict(self.proof["source_position"], x=10),
                ),
            ):
                with self.subTest(proof=changed), self.assertRaises(ValueError):
                    entry.enter_choice(self.db, self.store, self.character, changed)
            self.assertEqual(enter.call_count, 1)

    def test_school_npc_visit_dispatches_by_effective_running_admission(self):
        school = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.json"
            ).read_text()
        )
        configuration = deepcopy(self.configuration)
        configuration["topology"]["owned_story_controller"] = school
        arrived = {
            "id": 7,
            "account_id": 2,
            "map_id": 1017,
            "instance_id": 0,
            "x": 0,
            "y": -59,
            "z": -44,
        }
        cases = (
            (
                "questless",
                dict(running=[], completed=[], objectives=[], active=[]),
                True,
            ),
            (
                "completed",
                dict(running=[], completed=[2773], objectives=[], active=[]),
                True,
            ),
            (
                "expired",
                dict(
                    running=[2773],
                    completed=[],
                    objectives=[],
                    active=[2773],
                    active_periods={
                        "2773": {
                            "anchor_ms": 1_000_000,
                            "period_seconds": 60,
                            "accepted_at_ms": 1_000_000,
                        }
                    },
                ),
                True,
            ),
            (
                "running",
                dict(running=[2773], completed=[], objectives=[], active=[2773]),
                False,
            ),
        )
        for label, progress, expect_public in cases:
            with self.subTest(state=label):
                store = Mock()
                store.transition_map_in_transaction.return_value = arrived
                store.character.return_value = arrived
                with patch(
                    "wakfu_server.npc_dialogue.catalog", return_value=self.native
                ), patch(
                    "wakfu_server.dungeon_runtime_config.pinned_configuration",
                    return_value=configuration,
                ), patch.object(
                    dungeon_instances, "route", return_value=self.route
                ), patch(
                    "wakfu_server.quest_npc.publication", return_value=self.published
                ), patch(
                    "wakfu_server.quest_npc._row",
                    return_value=(self.row, self.item),
                ), patch(
                    "wakfu_server.quest_npc._nearby_placement", return_value=True
                ), patch(
                    "wakfu_server.achievements.storage.load_locked",
                    return_value=progress,
                ), patch(
                    "wakfu_server.achievements.mission_toolkit.settle",
                    return_value=[],
                ), patch.object(
                    dungeon_transport,
                    "enter_resolved",
                    return_value=dict(instance_id=99, destination=dict(map_id=980)),
                ) as enter:
                    result = entry.enter_choice(
                        self.db,
                        store,
                        self.character,
                        self.proof,
                        allowed_position_accounts=frozenset([2]),
                    )
                if expect_public:
                    self.assertEqual(result["public_arrival"], arrived)
                    self.assertEqual(result["direction"], 7)
                    store.transition_map_in_transaction.assert_called_once_with(
                        self.db,
                        2,
                        "lease",
                        7,
                        self.character,
                        dict(map_id=1017, instance_id=0, x=0, y=-59, z=-44),
                    )
                    enter.assert_not_called()
                else:
                    self.assertEqual(result["instance_id"], 99)
                    store.transition_map_in_transaction.assert_not_called()
                    enter.assert_called_once()

    def test_school_public_visit_rejects_changed_native_source_or_approach(self):
        from wakfu_server import generic_transports
        from wakfu_server import owned_story_npc_entry

        declaration = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.json"
            ).read_text()
        )["npc_public_visit"]
        source = generic_transports.source(
            declaration["source_map_id"], declaration["source_object_id"]
        )
        self.assertIsNotNone(source)
        self.assertEqual(
            owned_story_npc_entry.public_visit_destination(declaration),
            dict(map_id=1017, instance_id=0, x=0, y=-59, z=-44),
        )
        with self.assertRaisesRegex(ValueError, "frozen native endpoint"):
            owned_story_npc_entry.public_visit_destination(
                dict(declaration, source_sha256="0" * 64)
            )
        with self.assertRaisesRegex(ValueError, "native exterior approach"):
            owned_story_npc_entry.public_visit_destination(
                dict(declaration, approach=dict(x=1, y=-59, z=-44))
            )
