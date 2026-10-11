"""Actual Eliotrope grants, portal ownership and Calm/Exalted transitions."""
import os
import random
import unittest
from unittest.mock import patch

import test_combat_spell_transaction as native_fixture
import test_sadida_grant_pipeline as casts
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeRuntimeTests(unittest.TestCase):
    cast = casts.SadidaGrantPipelineTests.cast

    def fixture(self, *, passives=(), target_distance=4):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            18,
            200,
            native_qi=True,
            target_hp=20000,
            target_distance=target_distance,
            variation_seed=17,
        )
        deck = encode_deck((4668, 4692, 4699), passives)
        rng = random.Random(17)
        fight, packets = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, fight, deck, rng, packets

    def next_owned_turn(self, data):
        helper = turns.AniripsaGrantSummonPipelineTests()
        for _ in range(16):
            helper.end_current_turn(data[2], data[:5])
            if data[2].current.id == 7:
                return
        self.fail("Actual owned turn not reached")

    def test_ready_installs_owned_grants_and_calm(self):
        from wakfu_server.combat_spell_grant import granted_spells

        data = self.fixture()
        self.assertTrue({4678, 4682, 7813} <= set(granted_spells(data[2], 7)))
        self.assertFalse(granted_spells(data[2], -7))
        self.assertIn(
            3386, {s.reference for s in data[2].actors[7].state_ledger.entries}
        )

    def test_actual_exaltation_toggle_restores_calm_without_duplicate_carrier(self):
        data = self.fixture()
        first = self.cast(data, 4682, target=data[2].actors[7].position)
        states = [s.reference for s in first.fight.actors[7].state_ledger.entries]
        self.assertIn(3303, states)
        self.assertNotIn(3386, states)
        data = (*data[:2], first.fight, *data[3:])
        self.next_owned_turn(data)
        second = self.cast(data, 4682, target=data[2].actors[7].position, action_id=20)
        states = [s.reference for s in second.fight.actors[7].state_ledger.entries]
        self.assertNotIn(3303, states)
        self.assertEqual(states.count(3386), 1)

    def test_calm_aegis_rejects_occupied_target_atomically(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        data = self.fixture()
        before = snapshot(data[2])
        rng_before = data[4].getstate()
        with self.assertRaisesRegex(ValueError, "twV"):
            self.cast(data, 4668, target=data[2].actors[-7].position)
        self.assertEqual(snapshot(data[2]), before)
        self.assertEqual(data[4].getstate(), rng_before)

    def place_portal(self, data, *, near, action_id):
        from class_spell_eligible_targets import eligible_cast_targets, candidate_cells
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_los import authoritative_visible

        character, monster, fight, deck, rng, _ = data
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=action_id, critical=False, rng=rng
        )
        cells, total = candidate_cells(fight, 7, limit=4096)
        occupied = {a.position for a in fight.actors.values() if a.hp > 0}
        used = {tuple(a["cell"]) for a in fight.native_effect_areas.values()}
        cells = tuple(
            sorted(
                (c for c in cells if c not in occupied | used),
                key=lambda c: (abs(c[0] - near[0]) + abs(c[1] - near[1]), c),
            )
        )

        def los(origin, destination, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in current.actors.values() if a.hp > 0
                },
            )

        # Change only bounded search order; every candidate uses production validation.
        with patch(
            "class_spell_eligible_targets.candidate_cells", return_value=(cells, total)
        ):
            selection = eligible_cast_targets(
                fight,
                character,
                deck,
                granted_spells(fight, 7)[4678]["uid"],
                adapter=adapter,
                line_of_sight=los,
                actor_id=7,
                limit=4096,
                maximum_eligible=16,
            )
        self.assertTrue(selection["eligible"], selection)
        rejected = []
        for row in selection["eligible"]:
            try:
                return self.cast(data, 4678, target=row["target"], action_id=action_id)
            except AssertionError as error:
                # An eligible cast can have no effect after native effect criteria.
                # Keep looking on independent immutable transaction branches.
                if str(error) != "False is not true":
                    raise
                rejected.append((row["target"], str(error)))
        self.fail(str(rejected))

    def test_owned_portal_pair_enables_attack_beyond_ordinary_range(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        data = self.fixture()
        fight = data[2]
        target = fight.actors[-7].position
        actor = fight.actors[7]
        paths = [(actor.position, ())]
        visited = {actor.position}
        selected = None
        while paths:
            cell, path = paths.pop(0)
            if abs(cell[0] - target[0]) + abs(cell[1] - target[1]) > 4:
                selected = path
                break
            if len(path) >= actor.mp:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cell[0] + dx, cell[1] + dy, cell[2])
                if nxt in fight.walkable and nxt not in visited and nxt != target:
                    visited.add(nxt)
                    paths.append((nxt, (*path, nxt)))
        self.assertIsNotNone(
            selected, "No legal native-arena path beyond ordinary range"
        )
        fight.move(3, 7, list(selected))
        self.assertGreater(
            abs(actor.position[0] - target[0]) + abs(actor.position[1] - target[1]), 4
        )
        before = snapshot(data[2])
        with self.assertRaisesRegex(ValueError, "twI"):
            self.cast(data, 4692, target=target)
        self.assertEqual(snapshot(data[2]), before)
        first = self.place_portal(data, near=data[2].actors[7].position, action_id=11)
        data = (*data[:2], first.fight, *data[3:])
        second = self.place_portal(data, near=target, action_id=12)
        data = (*data[:2], second.fight, *data[3:])
        gates = [
            a for a in data[2].native_effect_areas.values() if a.get("reference") == 823
        ]
        self.assertEqual(len(gates), 2)
        self.assertTrue(all(a["owner_id"] == 7 for a in gates))
        self.next_owned_turn(data)
        hp = data[2].actors[-7].hp
        attack = self.cast(data, 4692, target=target, action_id=20)
        self.assertLess(attack.fight.actors[-7].hp, hp)

    def test_recasting_owned_portal_cell_removes_it_without_mutating_source(self):
        data = self.fixture()
        first = self.place_portal(data, near=data[2].actors[7].position, action_id=11)
        data = (*data[:2], first.fight, *data[3:])
        gates = [
            a for a in data[2].native_effect_areas.values() if a.get("reference") == 823
        ]
        self.assertEqual(len(gates), 1)
        uid, cell = gates[0]["uid"], tuple(gates[0]["cell"])
        removed = self.cast(data, 4678, target=cell, action_id=12)
        self.assertNotIn(uid, removed.fight.native_effect_areas)
        self.assertIn(uid, data[2].native_effect_areas)
