"""Native owned-consumable END1026 projection at terminal settlement."""
import json
import unittest
from pathlib import Path
from random import Random

from wakfu_server.combat_consumable_lifecycle import prepare_outcome
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    server_runtime,
)
from wakfu_server.paths import DATA_ROOT
from wakfu_server.spells import encode_deck


class CombatConsumableOutcomeTests(unittest.TestCase):
    def _fixture(
        self, item_ref, *, fight_start=False, wound_before_start=0, state_level=None
    ):
        from test_combat_spell_transaction import SpellTransactionTests

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            19,
            200,
            native_qi=True,
        )
        monsters = {monster["id"]: monster}
        deck = encode_deck([], [])
        catalog = json.loads((DATA_ROOT / "native-consumable-actions.json").read_text())
        plan = next(
            row["plan"] for row in catalog["items"] if row["item_ref"] == item_ref
        )
        rows = []
        for index, state in enumerate(plan["states"]):
            rows.append(
                dict(
                    uid=980 + index,
                    state_id=state["state_id"],
                    level=state["level"] if state_level is None else state_level,
                    clock=state["clock"],
                    duration_ms=state["duration_ms"],
                    remaining_ms=state["duration_ms"],
                    effect_ids=tuple(state["effect_ids"]),
                    metadata=state["metadata"],
                )
            )
        character = dict(character, consumable_states=rows)
        actor = fight.actors[character["id"]]
        if wound_before_start:
            actor.hp = max(1, actor.max_hp - wound_before_start)
            actor.effect_stats[1] = actor.hp
            from wakfu_server.combat_hp_raw import SOURCE, install_fresh_hp_operand

            install_fresh_hp_operand(
                actor, dict(producer=SOURCE, actor_id=actor.id, raw_current=actor.hp)
            )
        fight, _packets = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(1),
            fight_start=fight_start,
        )

        def runtime_factory(*, action_id):
            return server_runtime(
                character,
                monsters,
                deck,
                action_id=action_id,
                critical=False,
            )[0]

        return character, monsters, deck, fight, runtime_factory

    def test_fight_end_dispatches_owned_1026_once_through_original_listener(self):
        character, _monsters, _deck, fight, runtime_factory = self._fixture(18351)
        actor = fight.actors[character["id"]]
        before = actor.effect_stats.get(36, 0)
        self.assertEqual(
            1, len(fight.native_consumable_initializations[character["id"]])
        )
        fight.phase = "finished"
        fight.winner = 0

        ended, packets = prepare_outcome(fight, runtime_factory, action_id=2)
        self.assertIsNot(fight, ended)
        self.assertEqual("finished", ended.phase)
        self.assertEqual(
            40, ended.actors[character["id"]].effect_stats.get(36, 0) - before
        )
        self.assertTrue(ended.native_consumable_outcome_delivered)
        repeated, repeated_packets = prepare_outcome(
            ended, runtime_factory, action_id=3
        )
        self.assertIs(ended, repeated)
        self.assertEqual((), repeated_packets)
        self.assertEqual(
            ended.actors[character["id"]].effect_stats,
            repeated.actors[character["id"]].effect_stats,
        )

    def test_native_xp_food_start_handoff_installs_fresh_6874_carrier(self):
        from unittest.mock import patch

        from test_combat_spell_transaction import SpellTransactionTests

        (
            control_character,
            control_monster,
            control_fight,
        ) = SpellTransactionTests().native_server_fixture(19, 200, native_qi=True)
        control_monsters = {control_monster["id"]: control_monster}
        control_deck = encode_deck([], [])
        control_fight, _packets = prepare_server_initialization(
            control_character,
            control_monsters,
            control_fight,
            3,
            control_deck,
            action_id=1,
            rng=Random(1),
            fight_start=True,
        )
        control_wisdom = control_fight.actors[control_character["id"]].effect_stats.get(
            36, 0
        )
        with patch(
            "wakfu_server.combat.combat_consumable_handoff.time.time", return_value=1000
        ):
            character, _monsters, _deck, fight, _runtime_factory = self._fixture(
                22146,
                fight_start=True,
            )
        actor = fight.actors[character["id"]]
        self.assertEqual(control_wisdom + 100, actor.effect_stats.get(36, 0))
        entries = [
            entry
            for entry in actor.state_ledger.entries
            if entry.reference in (4872, 6874)
        ]
        self.assertEqual([6874], [entry.reference for entry in entries])
        replacement = entries[0]
        self.assertEqual(8_200_000, replacement.realtime_deadline_ms)
        self.assertEqual(7_200_000, replacement.realtime_duration)
        bindings = fight.native_consumable_initializations[character["id"]]
        self.assertEqual(1, len(bindings))
        self.assertEqual(6874, bindings[0]["state_id"])
        self.assertNotEqual(980, bindings[0]["combat_uid"])
        self.assertEqual(980, bindings[0]["world_uid"])
        from wakfu_server.combat_consumable_states import returning_states

        self.assertEqual(
            (
                {
                    "uid": 980,
                    "state_id": 6874,
                    "removed": False,
                    "level": 100,
                    "clock": "online",
                    "remaining_ms": 7_200_000,
                },
            ),
            returning_states(fight, character["id"], now_ms=1_000_000),
        )

    def test_vital_energy_end_heals_and_rebinds_decremented_carrier_once(self):
        character, _monsters, _deck, fight, runtime_factory = self._fixture(18422)
        actor = fight.actors[character["id"]]
        old = next(
            entry for entry in actor.state_ledger.entries if entry.reference == 2786
        )
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        set_hp_raw_current(actor, max(1, actor.max_hp - 50))
        before_hp = actor.hp
        fight.phase = "finished"
        fight.winner = 0

        ended, _packets = prepare_outcome(fight, runtime_factory, action_id=2)
        ended_actor = ended.actors[character["id"]]
        self.assertGreater(ended_actor.hp, before_hp)
        self.assertEqual(ended_actor.max_hp, ended_actor.hp)
        remaining = [
            entry
            for entry in ended_actor.state_ledger.entries
            if entry.reference == 2786
        ]
        self.assertEqual(
            [(old.uid != entry.uid, entry.level) for entry in remaining], [(True, 4)]
        )
        binding = ended.native_consumable_initializations[character["id"]][0]
        self.assertEqual((980, 2786), (binding["world_uid"], binding["state_id"]))
        self.assertEqual(remaining[0].uid, binding["combat_uid"])
        from wakfu_server.combat_consumable_states import returning_states

        self.assertEqual(
            (
                {
                    "uid": 980,
                    "state_id": 2786,
                    "removed": False,
                    "level": 4,
                    "clock": "event",
                    "remaining_ms": 0,
                },
            ),
            returning_states(ended, character["id"], now_ms=1_000_000),
        )
        after_stats = dict(ended_actor.effect_stats)
        after_carriers = [
            (entry.uid, entry.reference, entry.level)
            for entry in ended_actor.state_ledger.entries
        ]
        repeated, _packets = prepare_outcome(ended, runtime_factory, action_id=3)
        self.assertIs(ended, repeated)
        self.assertEqual(after_stats, repeated.actors[character["id"]].effect_stats)
        self.assertEqual(
            after_carriers,
            [
                (entry.uid, entry.reference, entry.level)
                for entry in repeated.actors[character["id"]].state_ledger.entries
            ],
        )

    def test_vital_energy_final_charge_is_removed_without_reapplication(self):
        character, _monsters, _deck, fight, runtime_factory = self._fixture(
            18422,
            state_level=1,
        )
        actor = fight.actors[character["id"]]
        self.assertEqual(
            1,
            next(
                entry for entry in actor.state_ledger.entries if entry.reference == 2786
            ).level,
        )
        fight.phase = "finished"
        fight.winner = 0
        ended, _packets = prepare_outcome(fight, runtime_factory, action_id=2)
        self.assertFalse(
            any(
                entry.reference == 2786
                for entry in ended.actors[character["id"]].state_ledger.entries
            )
        )
        self.assertEqual(
            ({"uid": 980, "state_id": 2786, "removed": True},),
            __import__(
                "wakfu_server.combat_consumable_states", fromlist=["returning_states"]
            ).returning_states(ended, character["id"], now_ms=1_000_000),
        )

    def test_vital_energy_charge_survives_return_and_decrements_next_fight_once(self):
        """The END counter is carried as level 4, then the next END makes 3."""
        from wakfu_server.combat_consumable_states import returning_states

        world_level = 5
        for expected_level in (4, 3):
            character, _monsters, _deck, fight, runtime_factory = self._fixture(
                18422,
                state_level=world_level,
            )
            actor = fight.actors[character["id"]]
            initial = [
                entry for entry in actor.state_ledger.entries if entry.reference == 2786
            ]
            self.assertEqual([world_level], [entry.level for entry in initial])
            self.assertEqual(
                1, len(fight.native_consumable_initializations[character["id"]])
            )
            fight.phase = "finished"
            fight.winner = 0

            ended, _ = prepare_outcome(fight, runtime_factory, action_id=2)
            ended_actor = ended.actors[character["id"]]
            remaining = [
                entry
                for entry in ended_actor.state_ledger.entries
                if entry.reference == 2786
            ]
            self.assertEqual(1, len(remaining))
            self.assertEqual(expected_level, remaining[0].level)
            binding = ended.native_consumable_initializations[character["id"]][0]
            self.assertEqual((980, 2786), (binding["world_uid"], binding["state_id"]))
            self.assertEqual(remaining[0].uid, binding["combat_uid"])
            self.assertEqual(
                (
                    {
                        "uid": 980,
                        "state_id": 2786,
                        "removed": False,
                        "level": expected_level,
                        "clock": "event",
                        "remaining_ms": 0,
                    },
                ),
                returning_states(ended, character["id"], now_ms=1_000_000),
            )
            state_snapshot = [(entry.uid, entry.level) for entry in remaining]
            repeated, packets = prepare_outcome(ended, runtime_factory, action_id=3)
            self.assertIs(ended, repeated)
            self.assertEqual((), packets)
            self.assertEqual(
                state_snapshot,
                [
                    (entry.uid, entry.level)
                    for entry in repeated.actors[character["id"]].state_ledger.entries
                    if entry.reference == 2786
                ],
            )
            # Returning to the world carries only the updated state level; the
            # next fight rebinds a fresh combat carrier to the same item UID.
            world_level = expected_level

    def test_actual_instant_987_source_allows_only_its_timed_981_child(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_native_timing_context import native_time_payload
        from wakfu_server.combat_state_handler import StateCarrierContext

        character, _monsters, _deck, fight, runtime_factory = self._fixture(10657)
        actor = fight.actors[character["id"]]
        dispatcher, _packets = runtime_factory(action_id=2)(
            fight, {"native_retained_container": {"present": False}}
        )
        invocation = EffectInvocation(
            2226,
            1,
            actor.id,
            actor.id,
            actor.position,
        )
        carrier = StateCarrierContext(
            0,
            0,
            False,
            None,
            None,
            False,
            False,
            False,
            0,
            native_time_payload(realtime_remaining=0),
        )
        with fight.effect_resolution():
            self.assertTrue(
                dispatcher.native_retention.apply_state_reference(
                    dispatcher.native_state_handler,
                    invocation,
                    987,
                    1,
                    carrier_context=carrier,
                )
            )
        states = [
            entry for entry in actor.state_ledger.entries if entry.reference == 981
        ]
        self.assertEqual(1, len(states))
        self.assertEqual(1, states[0].level)
        self.assertTrue(states[0].retained)
        origin = fight.native_external_state_origins[states[0].uid]
        self.assertEqual(
            (45980, 987, states[0].uid),
            (origin["effect_id"], origin["parent_state_id"], origin["combat_uid"]),
        )

    def test_regeneration_native_end_heals_wounded_actor(self):
        character, _monsters, _deck, fight, runtime_factory = self._fixture(22491)
        actor = fight.actors[character["id"]]
        actor.hp = max(1, actor.max_hp - 50)
        actor.effect_stats[1] = actor.hp
        from wakfu_server.combat_hp_raw import SOURCE, install_fresh_hp_operand

        install_fresh_hp_operand(
            actor, dict(producer=SOURCE, actor_id=actor.id, raw_current=actor.hp)
        )
        self.assertEqual(
            1, len(fight.native_consumable_initializations[character["id"]])
        )
        self.assertLess(actor.hp, actor.max_hp)
        fight.phase = "finished"
        fight.winner = 0

        ended, _packets = prepare_outcome(fight, runtime_factory, action_id=2)
        self.assertEqual(actor.max_hp, ended.actors[character["id"]].hp)
        self.assertEqual("finished", ended.phase)
        self.assertTrue(ended.native_consumable_outcome_delivered)

    def test_regeneration_native_start_and_end_events_heal_wounded_actor(self):
        character, _monsters, _deck, fight, runtime_factory = self._fixture(
            22491,
            fight_start=True,
            wound_before_start=50,
        )
        actor = fight.actors[character["id"]]
        self.assertTrue(fight.native_start_event_delivered)
        self.assertEqual(actor.max_hp, actor.hp)  # Native1028 start subscription.

        from wakfu_server.combat_hp_raw import set_hp_raw_current

        set_hp_raw_current(actor, max(1, actor.max_hp - 50))
        before_end = actor.hp
        self.assertLess(before_end, actor.max_hp)
        fight.phase = "finished"
        fight.winner = 0
        ended, _packets = prepare_outcome(fight, runtime_factory, action_id=2)
        self.assertEqual(actor.max_hp, ended.actors[character["id"]].hp)
        self.assertGreater(ended.actors[character["id"]].hp, before_end)
        self.assertEqual("finished", ended.phase)
        self.assertTrue(ended.native_consumable_outcome_delivered)

    def test_flasks_and_fortune_food_apply_original_end_effects(self):
        cases = (
            (18351, {36: 40}),
            (18355, {33: 40}),
            (18401, {36: 150}),
            (18406, {33: 150}),
            (18357, {33: 100, 36: 100}),
        )
        for item_ref, expected in cases:
            with self.subTest(item_ref=item_ref):
                character, _monsters, _deck, fight, runtime_factory = self._fixture(
                    item_ref
                )
                actor = fight.actors[character["id"]]
                before = {stat: actor.effect_stats.get(stat, 0) for stat in expected}
                fight.phase = "finished"
                fight.winner = 0

                ended, _packets = prepare_outcome(fight, runtime_factory, action_id=2)
                after = ended.actors[character["id"]].effect_stats
                self.assertEqual(
                    {stat: before[stat] + amount for stat, amount in expected.items()},
                    {stat: after.get(stat, 0) for stat in expected},
                )
                self.assertTrue(ended.native_consumable_outcome_delivered)

    def test_flask_end_event_does_not_apply_outside_native_fight_models(self):
        character, _monsters, _deck, fight, runtime_factory = self._fixture(18351)
        actor = fight.actors[character["id"]]
        before = actor.effect_stats.get(36, 0)
        fight.native_fight_model = 1
        fight.phase = "finished"
        fight.winner = 0

        ended, _packets = prepare_outcome(fight, runtime_factory, action_id=2)
        self.assertEqual(before, ended.actors[character["id"]].effect_stats.get(36, 0))
        self.assertTrue(ended.native_consumable_outcome_delivered)


if __name__ == "__main__":
    unittest.main()
