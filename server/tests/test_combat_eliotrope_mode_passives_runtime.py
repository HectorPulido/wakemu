"""Eliotrope mode/resource passives through owned native transactions."""
import os
import unittest

import test_combat_eliotrope_runtime as runtime
import eliotrope_allied_fixture as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeModePassiveRuntimeTests(
    allied.EliotropeAlliedFixture, unittest.TestCase
):
    fixture = runtime.EliotropeRuntimeTests.fixture
    cast = runtime.EliotropeRuntimeTests.cast
    place_portal = runtime.EliotropeRuntimeTests.place_portal
    next_owned_turn = runtime.EliotropeRuntimeTests.next_owned_turn

    @staticmethod
    def levels(fight, actor=7):
        values = {}
        for state in fight.actors[actor].state_ledger.entries:
            values[state.reference] = values.get(state.reference, 0) + state.level
        return values

    def test_efervescence_actual_toggle_installs_7750_only_when_equipped(self):
        observed = {}
        for enabled in (False, True):
            data = self.fixture(passives=(4688,) if enabled else ())
            tx = self.cast(data, 4682, target=data[2].actors[7].position)
            states = self.levels(tx.fight)
            self.assertEqual(states.get(3303), 1)
            observed[enabled] = states.get(7750, 0)
        self.assertEqual(observed, {False: 0, True: 1})

    def test_reminiscence_actual_toggle_changes_exaltation_carrier(self):
        observed = {}
        for enabled in (False, True):
            data = self.fixture(passives=(5132,) if enabled else ())
            tx = self.cast(data, 4682, target=data[2].actors[7].position)
            states = self.levels(tx.fight)
            self.assertEqual(states.get(3303), 1)
            observed[enabled] = states.get(7835, 0)
        self.assertEqual(observed, {False: 0, True: 30})

    def test_actual_gift_preserves_legacy_self_selector_and_medium_ap_cost(self):
        observations = {}
        for passives in ((), (4686,), (4686, 4689)):
            data = self.allied_fixture(passives=passives)
            before = data[2].actors[8]
            tx = self.allied_cast(data, 7813)
            recipient = tx.fight.actors[8]
            observations[passives] = (
                self.levels(tx.fight, 7).get(3671, 0),
                self.levels(tx.fight, 8).get(3671, 0),
                tx.plan["costs"]["ap"],
                tx.fight.actors[7].ap,
                recipient.mp - before.mp,
                recipient.ap - before.ap,
            )
            self.assertEqual(recipient.id, 8)
            self.assertEqual(tx.fight.actors[7].id, 7)
            self.assertIn(
                (7819, 1, 7),
                {
                    (state.reference, state.level, state.caster_id)
                    for state in recipient.state_ledger.entries
                },
            )
            gift_states = [
                state
                for state in recipient.state_ledger.entries
                if state.reference == 3671
            ]
            self.assertEqual(len(gift_states), 1 if 4686 in passives else 0)
            if gift_states:
                self.assertEqual(
                    (gift_states[0].level, gift_states[0].caster_id), (1, 7)
                )
        # Native397190 selects the actual allied PV. Rabia grants its recipient
        # AP through397192, or MP through397193 with Medium4689 equipped.
        # The separate7821 carrier still grants baseline2MP in every case.
        self.assertEqual(observations[()], (0, 0, 2, 4, 2, 0), observations)
        self.assertEqual(observations[(4686,)], (0, 1, 2, 4, 2, 2), observations)
        self.assertEqual(observations[(4686, 4689)], (0, 1, 0, 6, 4, 0), observations)
