"""Ordered guide interactions through original paid actions and actual turn ACKs.

Safe ordered guide witnesses. No state, grant, resource, actor or effect injection.
The unresolved own-chain refund experiment is retained privately and excluded.
"""
from copy import deepcopy
import os
import random
import struct
import unittest

import xelor_multiowner_fixture as multi
import test_combat_spell_transaction as single
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_start,
    prepare_server_turn_end,
    server_runtime,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck, validate_deck
from wakfu_server.combat_cast import resolve_owned_spell_action
from tools.class_spell_eligible_targets import eligible_cast_targets
from tools.combat_audit_turns import advance_actual_turn


class PaidSequence:
    def __init__(self, case, breed, *, two_owners=False, active=()):
        self.case = case
        self.rng = random.Random(17)
        if two_owners:
            (
                fight,
                self.characters,
                self.monster,
                self.decks,
            ) = multi.TwoXelorFixture().fixture(
                caster_breed=breed,
                second_player_breed=breed,
                level=200,
                active_spells=active,
                second_player_spells=active,
                compact_arena=False,
                second_player_position=(-7, -7, -1),
                third_player_position=(-9, -6, -1),
                initialization_seed=17,
            )
        else:
            (
                character,
                self.monster,
                fight,
            ) = single.SpellTransactionTests().native_server_fixture(
                breed,
                200,
                native_qi=True,
                full_health=True,
                target_ref=4168,
                target_level=190,
                target_distance=3,
                variation_seed=17,
            )
            self.characters = {7: character}
            self.decks = {7: encode_deck(active, ())}
            fight, _ = prepare_server_initialization(
                character,
                {-7: self.monster},
                fight,
                character["account_id"],
                self.decks[7],
                action_id=1,
                rng=self.rng,
                fight_start=True,
            )
        self.common = dict(
            player_characters=self.characters, deck_blobs=self.decks, rng=self.rng
        )
        owner = fight.current.id
        fight, _ = prepare_server_turn_start(
            self.characters[7],
            {-7: self.monster},
            fight,
            self.decks[7],
            actor_id=owner,
            action_id=4,
            area_callbacks=True,
            **self.common,
        )
        self.runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                self.characters[7],
                {-7: self.monster},
                p,
                self.decks[7],
                **self.common,
                **kw,
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                self.characters[7],
                {-7: self.monster},
                p,
                self.decks[7],
                **self.common,
                **kw,
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                self.characters[7],
                {-7: self.monster},
                self.decks[7],
                action_id=action_id,
                critical=False,
                **self.common,
            )[0],
        )
        self.action = 10
        self.committed = []

    @property
    def fight(self):
        return self.runtime.fight

    def reach(self, actor_id, *, next_cycle=False):
        if next_cycle:
            advance_actual_turn(self.runtime)
        for _ in range(40):
            if self.fight.phase != "active":
                self.case.fail(
                    "Combat ended before the ordered native sequence completed"
                )
            if self.fight.current.id == actor_id:
                return
            advance_actual_turn(self.runtime)
        self.case.fail("Actual owner turn did not arrive")

    def uid(self, owner, reference):
        grant = granted_spells(self.fight, owner).get(reference)
        if grant is not None:
            uid = grant["uid"]
            self.case.assertEqual(
                uid, reference, "Real temporary book uses native raw UID"
            )
        else:
            character = self.characters[owner]
            deck = validate_deck(
                self.decks[owner], character["breed"], character["level"]
            )
            self.case.assertIn(
                reference, deck["active"], "Packed UID requires equipped owned active"
            )
            uid = (owner << 32) | reference
        actor, actual_reference, level = resolve_owned_spell_action(
            dict(actor_id=owner, spell_uid=uid),
            self.characters[owner],
            self.fight,
            self.characters[owner]["account_id"],
            self.decks[owner],
        )
        self.case.assertIs(actor, self.fight.actors[owner])
        self.case.assertEqual(actual_reference, reference)
        self.case.assertGreaterEqual(level, 0)
        return uid

    def los(self, origin, target, preview):
        from wakfu_server.combat_obstacle_condition import footprint

        return authoritative_visible(
            1134,
            origin,
            target,
            preview,
            blocking_footprints={
                actor.id: footprint(actor.position, actor.physical_radius)
                for actor in preview.actors.values()
                if actor.hp > 0
            },
        )

    def targets(self, owner, reference, prefer=None):
        _, adapter = server_runtime(
            self.characters[owner],
            {-7: self.monster},
            self.decks[owner],
            action_id=self.action,
            critical=False,
            **self.common,
        )
        from unittest.mock import patch
        import tools.class_spell_eligible_targets as selector

        cells, total = selector.candidate_cells(self.fight, owner, limit=512)
        if prefer is not None:
            cells = tuple(sorted(cells, key=lambda cell: not prefer(cell)))
        # Reorder genuine exported candidates only; every returned cell still
        # passes the unchanged production ownership/cost/criterion/LOS validator.
        with patch.object(selector, "candidate_cells", return_value=(cells, total)):
            selected = eligible_cast_targets(
                self.fight,
                self.characters[owner],
                self.decks[owner],
                self.uid(owner, reference),
                adapter=adapter,
                line_of_sight=self.los,
                actor_id=owner,
                limit=512,
                maximum_eligible=16,
            )
        return [tuple(row["target"]) for row in selected["eligible"]]

    def cast(self, owner, reference, target):
        self.case.assertEqual(self.fight.current.id, owner)
        before = snapshot(self.fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", owner, self.uid(owner, reference), *target),
            self.characters[owner],
            {-7: self.monster},
            self.fight,
            self.characters[owner]["account_id"],
            self.decks[owner],
            action_id=self.action,
            line_of_sight=self.los,
            critical=False,
            **self.common,
        )
        self.case.assertEqual(snapshot(self.fight), before)
        self.case.assertTrue(any(tx.outcomes))
        self.runtime.fight = tx.fight
        self.action += 1
        self.committed.append((owner, reference, dict(tx.plan["costs"])))
        return tx

    def reject(self, owner, reference, target):
        before, rng = snapshot(self.fight), self.rng.getstate()
        with self.case.assertRaises(ValueError) as rejected:
            self.cast(owner, reference, target)
        self.case.assertEqual(snapshot(self.fight), before)
        self.case.assertEqual(self.rng.getstate(), rng)
        return rejected.exception

    def summons(self, owner, profiles):
        return [
            a
            for a in self.fight.actors.values()
            if a.hp > 0
            and getattr(a, "native_summon_source", {}).get("ref") in profiles
            and a.native_summon_source["caster_id"] == owner
        ]

    def state(self, owner, reference):
        return sum(
            e.level
            for e in self.fight.actors[owner].state_ledger.entries
            if e.reference == reference
        )


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class FoggerGuideDepartureTests(unittest.TestCase):
    def test_paid_canonnier_ally_push_inverse_at_actual_boundary_then_owned_withdrawal(
        self,
    ):
        seq = PaidSequence(self, 16, two_owners=True, active=(6907, 6908))
        seq.reach(7)
        origin = seq.fight.actors[7].position
        from wakfu_server.combat_qi_movement import movement_blocked_cells

        future_los_witness = []

        def legal_adjacent_step(cell):
            blocked = movement_blocked_cells(seq.fight, seq.fight.actors[7], (cell,))
            other = seq.fight.actors[8].position
            if not (
                distance(cell, origin) == 1
                and cell in seq.fight.walkable
                and (cell[0] == other[0] or cell[1] == other[1])
                and 1 <= distance(other, cell) <= 4
                and not any(
                    a.hp > 0 and a.position == cell for a in seq.fight.actors.values()
                )
                and (blocked is None or cell not in blocked)
                and (seq.fight.edges is None or (origin, cell) in seq.fight.edges)
            ):
                return False
            before, rng_before = snapshot(seq.fight), seq.rng.getstate()
            future = deepcopy(seq.fight)
            future.move(seq.characters[7]["account_id"], 7, [cell])
            current_los = seq.los(other, cell, seq.fight)
            moved_los = seq.los(other, cell, future)
            self.assertEqual(snapshot(seq.fight), before)
            self.assertEqual(seq.rng.getstate(), rng_before)
            future_los_witness.append(
                dict(
                    source_position=list(other),
                    original_blocker=list(origin),
                    target=list(cell),
                    actual_future_position=list(future.actors[7].position),
                    original_los=current_los,
                    future_paid_move_los=moved_los,
                    original_mp=seq.fight.actors[7].mp,
                    future_mp=future.actors[7].mp,
                )
            )
            return moved_los

        adjacent = [
            c
            for c in seq.targets(7, 7008, legal_adjacent_step)
            if legal_adjacent_step(c)
        ]
        # Private first-smoke evidence captures actual native positions and both
        # original LOS queries. No actor/footprint is removed to clear the ray.
        import json

        print(
            "FOGGER_NATIVE_FUTURE_LOS " + json.dumps(future_los_witness, sort_keys=True)
        )
        self.assertTrue(
            adjacent,
            dict(
                reason="Need actual paid future movement and LOS",
                native_witness=future_los_witness,
            ),
        )
        seq.cast(7, 7008, adjacent[0])
        self.assertTrue(
            legal_adjacent_step(adjacent[0]),
            "Created floor must preserve actual QI walking",
        )
        from wakfu_server.combat_area_transaction import prepare_area_movement

        prior = snapshot(seq.fight)
        moved = deepcopy(seq.fight)
        before_mp = moved.actors[7].mp
        moved.move(seq.characters[7]["account_id"], 7, [adjacent[0]])
        self.assertEqual(moved.actors[7].mp, before_mp - 1)
        moved, _ = prepare_area_movement(
            seq.characters[7],
            {-7: seq.monster},
            moved,
            seq.decks[7],
            actor_id=7,
            action_id=seq.action,
            path=[adjacent[0]],
            origin=origin,
            **seq.common,
        )
        self.assertEqual(snapshot(seq.fight), prior)
        seq.runtime.fight = moved
        seq.action += 1
        seq.cast(7, 6924, adjacent[0])
        self.assertGreater(seq.state(7, 7648), 0)
        # Original6908 explicitly forbids native Canonnier7648. Its rejection
        # is a meaningful negative, not a reason to override eligibility.
        seq.reach(7, next_cycle=True)  # Real renewed budget: Evaporation costs4AP.
        current = seq.fight.actors[7].position
        rejected = None
        for cell in sorted(seq.fight.walkable):
            if (
                2 <= distance(current, cell) <= 3
                and (cell[0] == current[0] or cell[1] == current[1])
                and not any(
                    a.hp > 0 and a.position == cell for a in seq.fight.actors.values()
                )
            ):
                attempted = seq.reject(7, 6908, cell)
                if getattr(attempted, "native_casting_result", None) == "twV":
                    rejected = attempted
                    break
        self.assertIsNotNone(
            rejected,
            "Require actual criterion rejection after native geometry, not resource/range rejection",
        )
        self.assertIn(
            "not HasState(7648",
            rejected.cast_diagnostics["resolved_casting"]["cast_criterion_raw"],
        )
        seq.reach(8)
        foreign_cell = seq.targets(8, 7008)[0]
        seq.cast(8, 7008, foreign_cell)
        prior_position = seq.fight.actors[7].position
        own_cells = {
            tuple(row["cell"])
            for row in seq.fight.native_effect_areas.values()
            if row["reference"] in (385, 978) and row["owner_id"] == 7
        }
        targets = seq.targets(8, 6907, lambda c: c == prior_position)
        self.assertIn(
            prior_position,
            targets,
            "Actual equipped ally push must pass native targeting",
        )
        tx = seq.cast(8, 6907, prior_position)
        self.assertEqual(tx.plan["costs"]["ap"], 3)
        self.assertNotEqual(tx.fight.actors[7].position, prior_position)
        self.assertNotIn(tx.fight.actors[7].position, own_cells)
        # Native343097 listens to1001/1037 and real resource events. Do not
        # invent1036 or require an unproved immediate inverse on forced movement.
        seq.reach(7)
        self.assertEqual(seq.state(7, 7648), 0)
        seq.reject(7, 6924, seq.fight.actors[7].position)
        turret = seq.cast(7, 7700, seq.targets(7, 7700)[0])
        owned_turret = seq.summons(7, (2011,))[0]
        foreign = deepcopy(seq.fight.native_microbot_networks[8])
        from wakfu_server.combat_pve_withdraw import plan
        from wakfu_server.combat_pve_departure import retired_pve_actor_ids
        from wakfu_server.combat_shared import Session

        before = snapshot(seq.fight)
        withdrawal = plan(
            Session(3, 7, "guide-owner-a", 1134, 0), seq.fight, seq.runtime
        )
        self.assertEqual(snapshot(seq.fight), before)
        self.assertIn(owned_turret.id, withdrawal.removed_actor_ids)
        self.assertIn(owned_turret.id, retired_pve_actor_ids(withdrawal.fight))
        self.assertEqual(withdrawal.fight.native_microbot_networks[8], foreign)
        self.assertGreater(withdrawal.fight.actors[8].hp, 0)
        self.assertEqual(withdrawal.fight.phase, "active")


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class CraGuideEarnedPrecisionTests(unittest.TestCase):
    def test_earned_threshold_free_beacon_then_precision_consumption_and_bad_target_rollback(
        self,
    ):
        seq = PaidSequence(self, 9, active=(4816, 4820, 4810))
        seq.reach(7)
        self.assertEqual(seq.state(7, 7792), 0)
        self.assertEqual(seq.state(7, 8897), 0)
        # Actual normal arrows create persistent3430/7792 through their instant
        # native7758/7793 carriers. Continue only through real turn budgets.
        for index in range(8):
            reference = (4816, 4820)[index % 2]
            if seq.fight.actors[7].ap < 3:
                seq.reach(7, next_cycle=True)
            seq.cast(7, reference, seq.fight.actors[-7].position)
            if seq.state(7, 8897) > 0:
                break
        self.assertGreater(seq.state(7, 7792), 0)
        self.assertGreater(seq.state(7, 3431), 0)
        self.assertGreater(seq.state(7, 8897), 0)
        self.assertLess(seq.state(7, 3430), 100)
        if seq.fight.actors[7].ap < 1:
            seq.reach(7, next_cycle=True)
        beacon_cell = seq.targets(7, 4807)[0]
        before_ap = seq.fight.actors[7].ap
        beacon = seq.cast(7, 4807, beacon_cell)
        self.assertEqual(beacon.plan["costs"]["ap"], 0)
        self.assertEqual(beacon.fight.actors[7].ap, before_ap)
        self.assertEqual(seq.state(7, 8897), 0)
        seq.reach(7, next_cycle=True)
        precision_before = seq.state(7, 7792)
        self.assertGreaterEqual(precision_before, 30)
        toggle = seq.cast(7, 7752, seq.fight.actors[7].position)
        self.assertGreater(seq.state(7, 7757), 0)
        # A same-cell attempt fails actual arrow targeting; no synthetic states.
        seq.reject(7, 4816, seq.fight.actors[7].position)
        hp = seq.fight.actors[-7].hp
        enhanced = seq.cast(7, 4816, seq.fight.actors[-7].position)
        self.assertLess(enhanced.fight.actors[-7].hp, hp)
        self.assertLess(seq.state(7, 7792), precision_before)
        self.assertGreater(enhanced.plan["costs"]["ap"], 0)


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueForeignDetonationTests(unittest.TestCase):
    def test_paid_two_owner_bombs_reject_foreign_detonation_atomically(self):
        seq = PaidSequence(self, 13, two_owners=True, active=(6463, 6468, 6473))
        seq.reach(7)
        own_cell = seq.targets(7, 7906)[0]
        first_wp = seq.fight.actors[7].effect_stats[4]
        paid = seq.cast(7, 7906, own_cell)
        self.assertEqual(paid.plan["costs"]["wp"], 1)
        self.assertEqual(seq.fight.actors[7].effect_stats[4], first_wp - 1)
        own = seq.summons(7, (3795, 3796, 3797))
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0].native_summon_source["controller_id"], 7)
        self.assertEqual(seq.state(7, 7919), 2)

        seq.reach(8)

        def in_foreign_range(cell):
            return (
                distance(cell, own_cell) >= 5
                and 1 <= distance(seq.fight.actors[7].position, cell) <= 7
            )

        legal = [
            cell
            for cell in seq.targets(8, 7906, in_foreign_range)
            if in_foreign_range(cell)
        ]
        self.assertTrue(
            legal, "Need actual paid foreign bomb within detonation geometry"
        )
        other_wp = seq.fight.actors[8].effect_stats[4]
        foreign_paid = seq.cast(8, 7906, legal[0])
        self.assertEqual(foreign_paid.plan["costs"]["wp"], 1)
        self.assertEqual(seq.fight.actors[8].effect_stats[4], other_wp - 1)
        foreign = seq.summons(8, (3795, 3796, 3797))
        self.assertEqual(len(foreign), 1)
        self.assertEqual(foreign[0].native_summon_source["caster_id"], 8)
        self.assertEqual(foreign[0].native_summon_source["controller_id"], 8)
        self.assertEqual(seq.state(8, 7919), 2)

        seq.reach(7)
        self.assertNotIn(6495, validate_deck(seq.decks[7], 13, 200)["active"])
        grant = granted_spells(seq.fight, 7)[6495]
        self.assertEqual(seq.uid(7, 6495), grant["uid"])
        self.assertEqual(seq.fight.actors[7].team, foreign[0].team)
        self.assertTrue(
            1 <= distance(seq.fight.actors[7].position, foreign[0].position) <= 7
        )
        before, rng_before = snapshot(seq.fight), seq.rng.getstate()
        rejected = seq.reject(7, 6495, foreign[0].position)
        self.assertEqual(rejected.native_casting_result, "twV")
        selected = rejected.cast_diagnostics["resolved_casting"]
        self.assertEqual((selected["minimum"], selected["maximum"]), (1, 7))
        self.assertFalse(selected["line_of_sight"])
        self.assertIn("IsOwnSummon", selected["cast_criterion_raw"])
        self.assertEqual(snapshot(seq.fight), before)
        self.assertEqual(seq.rng.getstate(), rng_before)
        self.assertEqual(len(seq.summons(7, (3795, 3796, 3797))), 1)
        self.assertEqual(len(seq.summons(8, (3795, 3796, 3797))), 1)
        self.assertEqual((seq.state(7, 7919), seq.state(8, 7919)), (2, 2))
