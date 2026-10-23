"""Native area-creation getters preserve Qq coordinates and subtype facing."""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_area_contracts import AREA_CONTRACTS
from wakfu_server.combat_area_orientation import creation_area_pv


class AreaCreationOrientationTests(unittest.TestCase):
    @staticmethod
    def verified_pvs(rows, actors):
        """Stand in for already verified active or retained native PV authority."""
        stack = ExitStack()
        pvs = {
            identity: SimpleNamespace(id=identity, position=row["cell"], direction=-1)
            for identity, row in rows.items()
        }
        stack.enter_context(
            patch(
                "wakfu_server.combat_state_managers.registered_area_pv",
                side_effect=lambda fight, identity: pvs.get(identity),
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_state_managers.retained_area_pv_row",
                side_effect=lambda fight, identity: rows[identity],
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_summon_initialization.registered_or_detached_actor",
                side_effect=lambda fight, identity: actors.get(identity),
            )
        )
        return stack, pvs

    def test_all_ten_getters_keep_own_xyz_and_native_facing_precedence(self):
        self.assertEqual(len(AREA_CONTRACTS), 10)
        owner = SimpleNamespace(id=7, position=(91, 92, 93), direction=5)
        fight = SimpleNamespace()
        for contract in AREA_CONTRACTS.values():
            for owner_id in (None, owner.id):
                with self.subTest(contract=contract, owner_id=owner_id):
                    row = dict(
                        native_area_contract=contract,
                        owner_id=owner_id,
                        cell=(-17, 23, -4),
                        direction=None,
                    )
                    rows = {100: row}
                    stack, pvs = self.verified_pvs(rows, {owner.id: owner})
                    with stack:
                        actual = creation_area_pv(fight, 100)
                        self.assertIs(actual, pvs[100])
                        self.assertEqual(actual.position, (-17, 23, -4))
                        self.assertEqual(
                            actual.direction,
                            7 if contract == "faY" or owner_id is None else 5,
                        )
                        self.assertIsNone(row["direction"])
                        if contract in ("faW", "fbb", "faY"):
                            row["direction"] = 3
                            self.assertEqual(
                                creation_area_pv(fight, 100).direction,
                                7 if contract == "faY" else 3,
                            )
                        owner.direction = 1
                        row["direction"] = None
                        self.assertEqual(
                            creation_area_pv(fight, 100).direction,
                            7 if contract == "faY" or owner_id is None else 1,
                        )
                        self.assertEqual(actual.position, (-17, 23, -4))
                        owner.direction = 5
        # A retained owner's own XYZ must never replace the created area's XYZ.
        rows = {
            100: dict(native_area_contract="faN", owner_id=101, cell=(1, 2, 3)),
            101: dict(
                native_area_contract="fbb",
                owner_id=7,
                cell=(30, 40, 50),
                direction=None,
            ),
        }
        stack, pvs = self.verified_pvs(rows, {7: owner})
        with stack:
            self.assertEqual(creation_area_pv(fight, 100).position, (1, 2, 3))
            self.assertEqual(pvs[100].direction, 5)
            owner.direction = 9
            self.assertEqual(creation_area_pv(fight, 100).direction, 9)
            self.assertEqual(pvs[101].position, (30, 40, 50))

    def test_missing_cyclic_and_invalid_owner_or_stored_facing_fail_closed(self):
        fight = SimpleNamespace()
        cases = [
            (
                {
                    100: dict(native_area_contract="faN", owner_id=101, cell=(1, 2, 3)),
                    101: dict(native_area_contract="faP", owner_id=100, cell=(4, 5, 6)),
                },
                "Cyclic native area orientation ownership",
            ),
            (
                {100: dict(native_area_contract="faN", owner_id=999, cell=(1, 2, 3))},
                "Missing native area orientation owner facing",
            ),
            (
                {100: dict(native_area_contract="faN", owner_id=True, cell=(1, 2, 3))},
                "Invalid native area orientation owner identity",
            ),
        ]
        for contract in ("faW", "fbb"):
            cases.extend(
                [
                    (
                        {
                            100: dict(
                                native_area_contract=contract,
                                owner_id=None,
                                cell=(1, 2, 3),
                                direction=True,
                            )
                        },
                        "Invalid native stored area orientation",
                    ),
                    (
                        {
                            100: dict(
                                native_area_contract=contract,
                                owner_id=None,
                                cell=(1, 2, 3),
                            )
                        },
                        "Missing native stored area orientation authority",
                    ),
                ]
            )
        for rows, message in cases:
            with self.subTest(rows=rows):
                stack, _ = self.verified_pvs(rows, {})
                with stack, self.assertRaisesRegex(ValueError, message):
                    creation_area_pv(fight, 100)
        stack, _ = self.verified_pvs({}, {})
        with stack:
            self.assertIsNone(creation_area_pv(fight, 999))
        # faY does not consume bkU, even when an irrelevant stored value is bool.
        rows = {100: dict(native_area_contract="faY", cell=(1, 2, 3), direction=True)}
        stack, _ = self.verified_pvs(rows, {})
        with stack:
            self.assertEqual(creation_area_pv(fight, 100).direction, 7)
