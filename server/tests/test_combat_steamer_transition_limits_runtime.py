"""Remaining Steamer capacity and form transitions through real owned actions."""
import os
import struct
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerTransitionLimitsRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def targets(self, data, spell):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets

        character, monster, fight, deck, rng = data
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
        )
        grant = granted_spells(fight, 7).get(spell)
        return eligible_cast_targets(
            fight,
            character,
            deck,
            grant["uid"] if grant else (7 << 32) | spell,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            actor_id=7,
            limit=256,
            maximum_eligible=16,
        )

    def test_motor_capacity_accepts_six_or_eight_fresh_microbots_then_rejects_new_cell(
        self,
    ):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import candidate_cells

        for passive, cap in ((False, 6), (True, 8)):
            with self.subTest(passive=passive):
                data = self.fixture((6934,) if passive else ())
                occupied_at_start = {tuple(a.position) for a in data[2].actors.values()}
                reserved = next(
                    tuple(row["target"])
                    for row in self.targets(data, 7008)["eligible"]
                    if tuple(row["target"]) not in occupied_at_start
                )
                for index in range(cap):
                    if index:
                        data = self.next_owned_turn(data)
                    fight = data[2]
                    existing = {
                        tuple(row["cell"])
                        for row in fight.native_effect_areas.values()
                        if row["reference"] == 978
                    }
                    options = [
                        row["target"]
                        for row in self.targets(data, 7008)["eligible"]
                        if tuple(row["target"]) not in existing
                        and tuple(row["target"]) != reserved
                    ]
                    self.assertTrue(options, (index, cap, existing))
                    tx = self.cast(data, 7008, target=options[0])
                    data = self.adopt(data, tx.fight)
                    self.assertEqual(
                        len(data[2].native_microbot_networks[7]["microbot_ids"]),
                        index + 1,
                    )
                data = self.next_owned_turn(data)
                character, monster, fight, deck, rng = data
                existing = {
                    tuple(row["cell"])
                    for row in fight.native_effect_areas.values()
                    if row["reference"] == 978
                }
                occupied = {a.position for a in fight.actors.values()}
                cells, _ = candidate_cells(fight, 7, limit=256)
                fresh = reserved
                self.assertNotIn(fresh, existing | occupied)
                uid = granted_spells(fight, 7)[7008]["uid"]
                with self.assertRaisesRegex(ValueError, "twV"):
                    prepare_server_spell(
                        struct.pack(">qqiih", 7, uid, *fresh),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        deck,
                        action_id=4,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=rng,
                    )
                self.assertEqual(
                    len(fight.native_microbot_networks[7]["microbot_ids"]), cap
                )

    def test_cannoner_removes_reservoir_bonus_on_actual_form_entry(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6941,) if enabled else ())
                before = data[2].actors[7].effect_stats[87]
                # Cannoner requires the owner to stand on an actual Microbot.
                owner = data[2].actors[7].position
                options = [
                    row["target"]
                    for row in self.targets(data, 7008)["eligible"]
                    if sum(abs(row["target"][i] - owner[i]) for i in (0, 1)) == 1
                ]
                self.assertTrue(options)
                tx = self.cast(data, 7008, target=options[0])
                data = self.adopt(data, tx.fight)
                data[2].move(3, 7, [options[0]])
                entered = self.cast(data, 6924, target=data[2].actors[7].position)
                actor = entered.fight.actors[7]
                self.assertIn(7648, {s.reference for s in actor.state_ledger.entries})
                self.assertEqual(actor.effect_stats[87] - before, -50 if enabled else 0)
