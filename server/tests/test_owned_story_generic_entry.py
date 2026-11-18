"""Native coordinate effects admit the exact owned-story entrance only."""

from copy import deepcopy
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from wakfu_server import (
    dungeon_instances,
    dungeon_transport,
    owned_story_controller,
    owned_story_generic_entry as entry,
    owned_story_auto_start,
    owned_story_item_gates,
    owned_story_mechanics,
)

ROOT = Path(__file__).parents[1]


class OwnedStoryGenericEntryTests(unittest.TestCase):
    def setUp(self):
        self.configuration = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/wild-estate-excavation-713.configuration.json"
            ).read_text()
        )
        self.instance = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/wild-estate-excavation-713.instance.json"
            ).read_text()
        )
        self.declaration = self.instance["entry"]
        self.source = self.declaration["source"]
        self.character = dict(
            id=77,
            account_id=8,
            map_id=711,
            instance_id=0,
            x=44,
            y=-24,
            z=-81,
        )
        self.floors = {tuple(point) for point in self.declaration["approaches"]}

    def _native_source(self, source=None):
        return [deepcopy(source or self.source)]

    def _native_geometry(self):
        return SimpleNamespace(cells=self.floors)

    def test_exact_native_effect_and_floor_are_required(self):
        with patch(
            "wakfu_server.world_static.objects",
            side_effect=lambda _map_id: self._native_source(),
        ), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=self._native_geometry(),
        ):
            proof = entry.validate_entry(self.declaration)
            self.assertEqual(proof[0]["id"], 20378)
            self.assertEqual(proof[3]["action_reference"], 443)
            self.assertEqual(proof[4]["map_id"], 713)

            changed = deepcopy(self.declaration)
            changed["effect_reference"] = 444
            with self.assertRaisesRegex(ValueError, "one literal native coordinate"):
                entry.validate_entry(changed)

            changed = deepcopy(self.declaration)
            changed["source"]["payload_hex"] = "00" * 48
            with self.assertRaisesRegex(ValueError, "actual native source"):
                entry.validate_entry(changed)

            changed = deepcopy(self.declaration)
            changed["approaches"][0] = [1, 2, 3]
            with self.assertRaisesRegex(ValueError, "actual native floor"):
                entry.validate_entry(changed)

    def test_loaded_owner_action_and_approach_share_the_existing_entry_transaction(
        self,
    ):
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        store = MagicMock()
        store.connection.return_value.__enter__.return_value = db
        store.character.return_value = dict(self.character)
        route = SimpleNamespace(key=self.configuration["route"]["key"])
        resolved_result = {"instance_id": 901, "destination": {"map_id": 713}}

        with patch.object(
            entry, "configuration", return_value=self.configuration
        ), patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value={"running": [], "completed": [], "objectives": []},
        ), patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=True
        ), patch(
            "wakfu_server.simple_item_actions._idle"
        ), patch.object(
            entry,
            "validate_route",
            return_value=(
                self.source,
                {"cod": 0, "coe": 0, "cof": False},
                {"wire_action": 0, "criterion": ""},
                {"action_reference": 443, "criterion": ""},
                {"map_id": 713, "x": 0, "y": 0, "z": 0},
                1,
            ),
        ), patch.object(
            dungeon_instances, "route", return_value=route
        ), patch.object(
            dungeon_transport, "enter_resolved", return_value=resolved_result
        ) as enter_resolved:
            result = entry.enter(
                store,
                8,
                "lease-8",
                self.character,
                struct.pack(">qHH", 20378, 0, 0),
                loaded=True,
                blocked=False,
                allowed_position_accounts=frozenset({8}),
            )
            self.assertIs(result, resolved_result)
            self.assertIs(enter_resolved.call_args.kwargs["_db"], db)
            self.assertEqual(enter_resolved.call_args.args[1:4], (8, "lease-8", 77))
            self.assertEqual(
                enter_resolved.call_args.kwargs["allowed_position_accounts"],
                frozenset({8}),
            )

            for bad_body, bad_character in (
                (struct.pack(">qHH", 20378, 1, 0), self.character),
                (struct.pack(">qHH", 20378, 0, 1), self.character),
                (struct.pack(">qHH", 20378, 0, 0), dict(self.character, x=45)),
            ):
                with self.subTest(body=bad_body, position=bad_character):
                    with self.assertRaises(ValueError):
                        entry.enter(
                            store,
                            8,
                            "lease-8",
                            bad_character,
                            bad_body,
                            loaded=True,
                            blocked=False,
                            allowed_position_accounts=frozenset({8}),
                        )
            self.assertEqual(enter_resolved.call_count, 1)

    def test_multistage_autostart_keeps_durable_room_prerequisites_and_v1_compatibility(
        self,
    ):
        controller = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/wild-estate-excavation-713.json"
            ).read_text()
        )
        self.assertEqual(
            [
                owned_story_auto_start.requirements(controller, order)["requires"]
                for order in (1, 2, 3)
            ],
            [
                ["excavation-equipment"],
                ["excavation-first-victory"],
                ["excavation-bomb"],
            ],
        )
        self.assertIsNone(owned_story_auto_start.requirements(controller, 4))

        legacy = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.json"
            ).read_text()
        )
        self.assertEqual(
            owned_story_auto_start.requirements(legacy, 1),
            legacy["automatic_room_start"],
        )
        self.assertIsNone(owned_story_auto_start.requirements(legacy, 2))

    def test_item_gate_checks_real_native_output_and_debits_only_declared_bomb(self):
        from wakfu_server.combat_inventory_date_conditions import (
            complete_owned_item_quantity,
        )

        selected = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/wild-estate-excavation-713.json"
            ).read_text()
        )
        native = owned_story_mechanics.sources(selected)
        equipment = dict(
            kind="native_item_gate", reference=17797, quantity=1, consume=False
        )
        bomb = dict(kind="native_item_gate", reference=17799, quantity=1, consume=True)
        db, store = Mock(), Mock()
        with patch(
            "wakfu_server.combat_inventory_date_conditions.complete_owned_item_quantity",
            return_value=1,
        ) as quantity, patch(
            "wakfu_server.native_generic_rewards._payment",
            return_value=(None, [(1, b"paid")], None),
        ) as payment:
            self.assertEqual(
                owned_story_item_gates.apply(
                    db, store, self.character, selected, equipment
                ),
                [],
            )
            quantity.assert_called_with(self.character, (17797,))
            payment.assert_not_called()

            with patch(
                "wakfu_server.combat_inventory_date_conditions.complete_owned_item_quantity",
                return_value=0,
            ):
                with self.assertRaisesRegex(ValueError, "actual native equipment"):
                    owned_story_item_gates.apply(
                        db, store, self.character, selected, bomb
                    )
            payment.assert_not_called()

            self.assertEqual(
                owned_story_item_gates.apply(db, store, self.character, selected, bomb),
                [(1, b"paid")],
            )
            payment.assert_called_once_with(
                db,
                store,
                self.character,
                {"group_cod": 17799, "group_coe": 1},
            )
        self.assertIsNotNone(
            owned_story_item_gates.validate(selected, equipment, native)
        )
        self.assertIsNotNone(owned_story_item_gates.validate(selected, bomb, native))
        altered_native = deepcopy(native)
        altered_native["loot_tables"]["2350"]["gBN"] = []
        with self.assertRaisesRegex(ValueError, "native loot output"):
            owned_story_item_gates.validate(selected, bomb, altered_native)

    def test_native_loot_requires_its_source_effect_and_auto_start_requires_room_progress(
        self,
    ):
        selected = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/wild-estate-excavation-713.json"
            ).read_text()
        )
        loot = next(
            effect
            for step in selected["steps"]
            for effect in step["effects"]
            if effect["kind"] == "native_loot" and effect["source_id"] == 20404
        )
        db, store = Mock(), Mock()
        with patch.object(
            owned_story_mechanics, "allowed", return_value=False
        ), patch.object(owned_story_mechanics, "_loot") as grant:
            owned_story_mechanics.executor(selected)(db, store, self.character, [loot])
            grant.assert_not_called()

        with patch.object(
            owned_story_mechanics, "allowed", return_value=True
        ), patch.object(owned_story_mechanics, "_loot", return_value=[]) as grant:
            owned_story_mechanics.executor(selected)(db, store, self.character, [loot])
            grant.assert_called_once_with(db, store, self.character, selected, 2350)
            grant.reset_mock()
            changed = dict(loot, effect_reference=467)
            with self.assertRaisesRegex(ValueError, "actual source's native table"):
                owned_story_mechanics.executor(selected)(
                    db, store, self.character, [changed]
                )
            grant.assert_not_called()

        def queue_result(progress, room_order, group_id=15):
            actor = {"id": -20378001, "x": 0, "y": 0, "z": 0}
            group = {"group_id": group_id, "members": [actor]}
            db = MagicMock()
            db.execute.return_value.fetchone.return_value = {
                "group_id": group_id,
                "asset_map_id": selected["map_id"],
                "members": [actor],
                "status": "available",
                "room_order": room_order,
            }
            store = MagicMock()
            store.connection.return_value.__enter__.return_value = db
            state = SimpleNamespace(
                loaded=True,
                character=dict(
                    self.character,
                    map_id=selected["map_id"],
                    instance_id=741,
                    x=12,
                    y=6,
                    z=0,
                ),
                fight=None,
                combat_session=None,
                spectator_session=None,
                pending_guardian_attack=None,
            )
            session = SimpleNamespace(state=state, runtime=SimpleNamespace(STORE=store))
            with patch(
                "wakfu_server.owned_story_controller._scope",
                return_value=(selected, set(progress)),
            ):
                result = owned_story_auto_start.queue(
                    session, group, configuration=self.configuration
                )
            return result, state, group

        # The second room's authentic spawn can be attacked only after its
        # preceding victory; the v1 School declaration retains its old path.
        result, state, group = queue_result(["excavation-first-victory"], 2)
        self.assertTrue(result)
        self.assertEqual(
            state.pending_guardian_attack,
            struct.pack(">qiihB", group["members"][0]["id"], 0, 0, 0, 0),
        )
        result, state, _ = queue_result([], 2)
        self.assertFalse(result)
        self.assertIsNone(state.pending_guardian_attack)

        school = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.json"
            ).read_text()
        )
        actor = {"id": -1030001, "x": 1, "y": 2, "z": 0}
        group = {"group_id": 16, "members": [actor]}
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = {
            "group_id": 16,
            "asset_map_id": school["map_id"],
            "members": [actor],
            "status": "available",
            "room_order": 1,
        }
        store = MagicMock()
        store.connection.return_value.__enter__.return_value = db
        state = SimpleNamespace(
            loaded=True,
            character=dict(
                self.character,
                map_id=school["map_id"],
                instance_id=742,
                x=128,
                y=-15,
                z=0,
            ),
            fight=None,
            combat_session=None,
            spectator_session=None,
            pending_guardian_attack=None,
        )
        school_configuration = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.configuration.json"
            ).read_text()
        )
        with patch(
            "wakfu_server.owned_story_controller._scope",
            return_value=(school, {"platform-ready"}),
        ):
            self.assertTrue(
                owned_story_auto_start.queue(
                    SimpleNamespace(state=state, runtime=SimpleNamespace(STORE=store)),
                    group,
                    configuration=school_configuration,
                )
            )

    def test_pinned_native_qv_interaction_accepts_only_declared_diagonal_floor(self):
        selected = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/wild-estate-excavation-713.json"
            ).read_text()
        )
        self.assertEqual(selected["interaction_approach_policy"], "pinned_native_qv")
        character = dict(
            id=77,
            account_id=8,
            map_id=713,
            instance_id=741,
            x=7,
            y=-3,
            z=0,
        )
        db, store = Mock(), Mock()
        with patch.object(
            owned_story_controller,
            "_scope",
            return_value=(selected, {"excavation-equipment"}),
        ), patch.object(
            owned_story_controller, "_settle", return_value="settled"
        ) as settle:
            self.assertEqual(
                owned_story_controller.interact(
                    db,
                    store,
                    character,
                    struct.pack(">qHH", 20405, 0, 0),
                    apply_effects=Mock(),
                ),
                "settled",
            )
            evidence = settle.call_args.kwargs["evidence"]
            self.assertEqual(
                evidence, {"object_id": 20405, "action": 0, "parameter": 0}
            )
            settle.reset_mock()

            with self.assertRaisesRegex(ValueError, "native interaction range"):
                owned_story_controller.interact(
                    db,
                    store,
                    dict(character, x=8, y=-5),
                    struct.pack(">qHH", 20405, 0, 0),
                    apply_effects=Mock(),
                )
            settle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
