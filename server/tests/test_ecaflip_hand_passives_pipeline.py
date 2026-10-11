"""Actual Ecaflip hand-dependent passives through casts, movement and turns."""
import math
import os
import struct
import unittest
from unittest.mock import patch

import test_ecaflip_tarot_pipeline as tarot
import test_aniripsa_grant_summon_pipeline as lifecycle


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipHandPassivesPipelineTests(unittest.TestCase):
    fixture = tarot.EcaflipTarotPipelineTests.fixture
    end_current_turn = lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn
    next_player_turn = lifecycle.AniripsaGrantSummonPipelineTests.next_player_turn

    @staticmethod
    def cards(fight):
        from wakfu_server.combat_spell_grant import granted_spells

        return set(granted_spells(fight, 7)) & set(range(7938, 7951))

    @staticmethod
    def level(fight, reference):
        return sum(
            entry.level
            for entry in fight.actors[7].state_ledger.entries
            if entry.reference == reference
        )

    def cast(self, data, reference, *, owned=False, allow_ineligible=False):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )

        character, monster, fight, deck, rng = data
        identity = (7 << 32) | reference if owned else reference
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=20, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            identity,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=1,
        )
        if not candidates["eligible"] and allow_ineligible:
            return None
        self.assertTrue(candidates["eligible"], candidates)
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        original_execute = EffectDispatcher.execute
        trace = []

        def observe(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            relevant = (
                invocation.reference
                in {
                    359256,
                    359762,
                    413265,
                    359285,
                    359284,
                    359078,
                    359079,
                    359822,
                    359372,
                    359373,
                }
                or 359542 <= invocation.reference <= 359554
                or 359657 <= invocation.reference <= 359668
            )
            if reference == 2060 and relevant and len(trace) < 80:
                trace.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        result,
                    )
                )
            return result

        before = dict(
            cards=sorted(self.cards(fight)),
            table=fight.native_table_turn,
            states=[
                (entry.reference, entry.level)
                for entry in fight.actors[7].state_ledger.entries
            ],
        )
        with patch.object(EffectDispatcher, "execute", observe):
            tx = prepare_server_spell(
                struct.pack(
                    ">qqiih", 7, identity, *candidates["eligible"][0]["target"]
                ),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=20,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        if reference == 2060:
            self.last_draw_evidence = dict(
                before=before,
                after=dict(
                    cards=sorted(self.cards(tx.fight)),
                    table=tx.fight.native_table_turn,
                    states=[
                        (entry.reference, entry.level)
                        for entry in tx.fight.actors[7].state_ledger.entries
                    ],
                ),
                target=candidates["eligible"][0]["target"],
                outcomes=tx.outcomes,
                trace=trace,
            )
        self.assertTrue(any(tx.outcomes))
        return character, monster, tx.fight, deck, rng

    def cast_held_card(self, data):
        # Held does not imply a legal target exists in this encounter (e.g.
        # a zero-range card can reject both self and occupied cells).
        for reference in sorted(self.cards(data[2])):
            result = self.cast(data, reference, allow_ineligible=True)
            if result is not None:
                return result, reference
        self.fail("No actual held card has a legal casting target")

    def move_one_step(self, data):
        from wakfu_server.combat_area_transaction import prepare_area_movement

        character, monster, fight, deck, rng = data
        actor = fight.actors[7]
        origin = actor.position
        occupied = {other.position for other in fight.actors.values()}
        border = getattr(fight, "native_border_constructor", {})
        boundary = set(
            map(tuple, border.get("arena", {}).get("native_border_cells", ()))
        )
        targets = sorted(
            end
            for start, end in fight.edges
            if start == origin and end not in occupied and end not in boundary
        )
        self.assertTrue(targets, "Fixture requires a native legal interior step")
        fight.move(3, 7, [targets[0]])
        preview, _ = prepare_area_movement(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=7,
            action_id=21,
            path=[targets[0]],
            origin=origin,
            rng=rng,
        )
        return preview

    def test_black_jack_armor_follows_real_weighted_hand_after_movement(self):
        # Native361071 weights grants359514..359527 by1..12; card7938 has
        # weight0. 359899 subscribes1005 (movement), not the turn boundary.
        selected = {}
        for seed in range(24):
            data = self.fixture(seed=seed, passives=(7960, 2068, 2080, 5250))
            total = sum(reference - 7938 for reference in self.cards(data[2]))
            selected.setdefault(total <= 20, (data, total))
            if len(selected) == 2:
                break
        self.assertEqual(set(selected), {False, True})
        for eligible, (data, total) in selected.items():
            with self.subTest(weighted_hand=total):
                actor = data[2].actors[7]
                armor_before = actor.effect_stats[97]
                maximum = actor.max_hp + actor.effect_maxima.get(92, 0)
                expected = math.floor(maximum * 0.1 + 0.5) if eligible else 0
                moved = self.move_one_step(data)
                self.assertEqual(
                    moved.actors[7].effect_stats[97] - armor_before, expected
                )
                self.assertEqual(self.level(moved, 6624), 0 if eligible else 5)
                if eligible:
                    self.assertGreater(expected, 0)

    def test_periodic_draw_uses_actual_table_parity_after_a_real_turn(self):
        data = self.fixture(seed=7, passives=(7961, 2068, 2080, 5250))
        initial = data[2].native_table_turn
        initial_cards = self.cards(data[2])
        self.assertEqual(len(initial_cards), 3)
        self.assertTrue(
            all((reference - 7938) % 2 == initial % 2 for reference in initial_cards)
        )
        # Ready initialization precedes RuntimeMessages adopting the actual
        # first round. Advance real complete cycles until parity changes; do
        # not pretend the pre-timeline Ready value is already round1.
        for _ in range(2):
            self.next_player_turn(data[2], data)
            if data[2].native_table_turn % 2 != initial % 2:
                break
        self.assertGreater(data[2].native_table_turn, initial)
        self.assertNotEqual(data[2].native_table_turn % 2, initial % 2)
        # Old-parity cards can become uncastable on the new actual round.
        # The real owned2060 draw has its own native cast criterion; do not
        # force an incompatible old card merely to manufacture a hand slot.
        before = self.cards(data[2])
        data = self.cast(data, 2060, owned=True)
        evidence = self.last_draw_evidence
        self.assertEqual(self.cards(data[2]), before, evidence)
        before_states = dict(evidence["before"]["states"])
        after_states = dict(evidence["after"]["states"])
        # Native2060 executes three draws (359256.limit3). Each35954x
        # applies its card carrier at level2; its426 (minimum level2) casts
        # the card while649 (minimum=maximum level1) never grants it to the
        # hand. 359372 suppresses hand-counter loss during these casts.
        new_carriers = {
            reference: level
            for reference, level in after_states.items()
            if 7961 <= reference <= 7973 and reference not in before_states
        }
        self.assertEqual(len(new_carriers), 3, evidence)
        self.assertEqual(set(new_carriers.values()), {2}, evidence)
        parity = data[2].native_table_turn % 2
        self.assertTrue(
            all((reference - 7961) % 2 == parity for reference in new_carriers),
            evidence,
        )
        self.assertNotEqual(parity, initial % 2)
        self.assertEqual(after_states[7940], before_states[7940] - 3, evidence)
        self.assertEqual(after_states[7941], before_states[7941], evidence)
        self.assertEqual(after_states[3683], before_states[3683] + 21, evidence)
        self.assertEqual(
            sum(
                reference == 359822 and result is True
                for reference, _, _, result in evidence["trace"]
            ),
            3,
            evidence,
        )

    def regeneration_observations(self, data):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        observations = []
        original = EffectDispatcher.execute_activation
        testcase = self

        def observe(dispatcher, invocation, **kwargs):
            if invocation.reference != 371345:
                return original(dispatcher, invocation, **kwargs)
            fight = dispatcher.native_retention.fight
            source = kwargs["source"]
            row = dict(
                hand=testcase.cards(fight),
                before=testcase.level(fight, 3683),
                table=fight.native_table_turn,
                events=source.event_ids,
                channel=source.channel,
                manager=source.manager_actor_id,
            )
            result = original(dispatcher, invocation, **kwargs)
            row["after"] = testcase.level(fight, 3683)
            row["result"] = result
            observations.append(row)
            return result

        # Observation only: preserve actual source, invocation, criteria,
        # execution result and production turn/end/ACK advancement unchanged.
        with patch.object(EffectDispatcher, "execute_activation", observe):
            self.end_current_turn(data[2], data)
        return observations

    def assert_hand_response(self, row):
        # Exact ordered371497..371509: six321 decurses and seven304 gains.
        removal_cards = {7939, 7941, 7944, 7946, 7948, 7949}
        self.assertEqual(row["events"], (1037,))
        self.assertEqual((row["manager"], row["channel"]), (7, 60))
        expected = row["before"]
        for reference in sorted(row["hand"]):
            expected = (
                max(0, expected - 15)
                if reference in removal_cards
                else min(100, expected + 15)
            )
        self.assertEqual(row["after"], expected, row)
        return row["after"] - row["before"]

    def test_retained_hand_rewards_only_unplayed_grants_at_real_regeneration(self):
        witnessed = set()
        for seed in range(8):
            data = self.fixture(seed=seed, passives=(8001,))
            rows = self.regeneration_observations(data)
            self.assertEqual(len(rows), 1, rows)
            delta = self.assert_hand_response(rows[0])
            if delta:
                witnessed.add("negative" if delta < 0 else "positive")
            if witnessed == {"positive", "negative"}:
                break
        self.assertEqual(witnessed, {"positive", "negative"})
        self.assertEqual(self.regeneration_observations(self.fixture(seed=7)), [])

        data = self.fixture(seed=7, passives=(8001,))
        data, played = self.cast_held_card(data)
        self.assertEqual(len(self.cards(data[2])), 2)
        self.assertNotIn(played, self.cards(data[2]))
        self.assertGreater(self.level(data[2], played + 23), 0)
        rows = self.regeneration_observations(data)
        self.assertEqual(len(rows), 1, rows)
        # End1002 can legitimately draw a replacement before1037. Inspect
        # actual surviving grants AT the subscribed group, not an earlier
        # two-card snapshot; the played carrier never counts as its grant.
        self.assertNotIn(played, rows[0]["hand"], rows)
        self.assert_hand_response(rows[0])
