"""Native model-71 admission stays tied to the exact owned guardian receipt."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wakfu_server.achievements import rii_guardian_contract as contract


class RiiGuardianContractTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 7,
            "map_id": 1387,
            "instance_id": 0,
            "x": -12,
            "y": 0,
            "z": 2,
        }
        self.monster = {
            "id": -8,
            "ref": contract.REFERENCE,
            "level": contract.LEVEL,
            "x": -12,
            "y": 1,
            "z": 2,
        }
        self.receipt = {
            "kind": "reconstructed_rii_guardian_actor",
            "owner": 7,
            "actor_id": -8,
            "ref": contract.REFERENCE,
        }
        self.db = MagicMock()
        self.db.execute.return_value.fetchone.return_value = {"payload": self.receipt}

    def test_exact_receipt_selects_level_300_native_model_contract(self):
        identified = contract.identify(self.db, self.character, [self.monster])
        self.assertEqual(
            identified,
            {"schema": contract.SCHEMA, "owner": 7, "target": -8},
        )
        self.assertEqual(self.db.execute.call_args.args[1], (7, "rii-guardian-actor:8"))

    def test_missing_foreign_or_malformed_receipt_cannot_select_special_fight(self):
        self.db.execute.return_value.fetchone.return_value = None
        self.assertIsNone(contract.identify(self.db, self.character, [self.monster]))

        for payload in (
            {**self.receipt, "owner": 8},
            {**self.receipt, "actor_id": -9},
            {**self.receipt, "ref": 1},
            {**self.receipt, "extra": True},
        ):
            with self.subTest(payload=payload):
                self.db.execute.return_value.fetchone.return_value = {
                    "payload": payload
                }
                with self.assertRaisesRegex(ValueError, "exact native owner"):
                    contract.identify(self.db, self.character, [self.monster])

    def test_wrong_scene_roster_and_reconstructed_level_do_not_select_native_contract(
        self,
    ):
        self.assertIsNone(
            contract.identify(
                self.db, {**self.character, "map_id": 1385}, [self.monster]
            )
        )
        self.assertIsNone(
            contract.identify(self.db, self.character, [self.monster, self.monster])
        )
        with self.assertRaisesRegex(ValueError, "level 300"):
            contract.identify(self.db, self.character, [{**self.monster, "level": 6}])

    def test_bind_requires_captured_model_roles_level_and_positions_without_hp_writes(
        self,
    ):
        fight = SimpleNamespace(
            native_fight_model=contract.MODEL,
            actors={
                7: SimpleNamespace(
                    controlled=True,
                    team=1,
                    position=contract.PLAYER,
                    hp=45,
                    max_hp=120,
                ),
                -8: SimpleNamespace(
                    controlled=False,
                    team=0,
                    position=contract.TARGET,
                    effective_level=contract.LEVEL,
                    hp=1,
                    max_hp=120,
                ),
            },
        )
        found = contract.bind(
            fight, {"schema": contract.SCHEMA, "owner": 7, "target": -8}
        )
        self.assertEqual(found["target"], -8)
        self.assertTrue(contract.is_owned(fight, 7))
        self.assertFalse(contract.is_owned(fight, 8))
        self.assertEqual((fight.actors[7].hp, fight.actors[-8].hp), (45, 1))
        for ordinary_model in (2, 14):
            fight.native_fight_model = ordinary_model
            self.assertFalse(contract.is_owned(fight, 7))
        fight.native_fight_model = contract.MODEL

        corruptions = (
            ("native_fight_model", 2),
            ("native_fight_model", 14),
            ("player.team", 0),
            ("guardian.team", 1),
            ("player.controlled", False),
            ("guardian.effective_level", 6),
            ("player.position", (-12, 0, 1)),
            ("guardian.position", (-11, 0, 0)),
        )
        for field, value in corruptions:
            actors = {
                identity: SimpleNamespace(**vars(actor))
                for identity, actor in fight.actors.items()
            }
            bad = SimpleNamespace(
                native_fight_model=fight.native_fight_model, actors=actors
            )
            if field.startswith("player."):
                setattr(actors[7], field.split(".")[1], value)
            elif field.startswith("guardian."):
                setattr(actors[-8], field.split(".")[1], value)
            else:
                bad.native_fight_model = value
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "captured admission"):
                    contract.bind(
                        bad, {"schema": contract.SCHEMA, "owner": 7, "target": -8}
                    )

    def test_arena_uses_captured_cells_and_validates_the_owner_position(self):
        geometry = SimpleNamespace(cells={contract.PLAYER, contract.TARGET})
        layout = {
            "placement_cells": [{contract.PLAYER}, {contract.TARGET}],
            "validated_cells": {contract.PLAYER},
        }
        with patch(
            "wakfu_server.combat_terrain.published_geometry", return_value=geometry
        ), patch(
            "wakfu_server.combat_terrain.local_arena", return_value=layout
        ) as build:
            arena = contract.arena(
                self.character,
                [self.monster],
                {"schema": contract.SCHEMA, "owner": 7, "target": -8},
                cell_budget=20,
                size_range=(1, 8),
            )
        self.assertEqual(arena["native_fight_model"], contract.MODEL)
        self.assertEqual(
            arena["participant_player_position"], ((-12, 0, 2), contract.PLAYER)
        )
        self.assertEqual(
            arena["participant_positions"], [((-12, 1, 2), contract.TARGET)]
        )
        self.assertEqual(arena["terrain_effect_id"], contract.TERRAIN)
        build.assert_called_once()
        self.assertEqual(
            contract.validated_player_position(self.character, arena), contract.PLAYER
        )
        with self.assertRaisesRegex(ValueError, "authority"):
            contract.validated_player_position({**self.character, "x": -11}, arena)


if __name__ == "__main__":
    unittest.main()
