"""Opt-in native constructors and real table advancement for recurring roots."""
import os
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "tests"),
    str(ROOT / "tools"),
    str(ROOT / "ai-service" / "tests"),
]


@unittest.skipUnless(
    os.environ.get("WAKFU_NATIVE_TABLE_RUNTIME") == "1", "native catalog runtime"
)
class OrdinaryNpcTableStartRuntimeTests(unittest.TestCase):
    def test_real_constructor_receives_later_table_callbacks(self):
        from jondo_native_support_probe import build_fixture
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        # Three different source programs share one native table publisher.
        cases = (
            (4534, 157, 270370, True),
            (4886, 134, 270734, True),
            (4758, 53, 265136, False),
        )
        original = EffectDispatcher._execute_scoped
        selected = {
            int(value)
            for value in os.environ.get("WAKFU_NATIVE_TABLE_REFS", "").split(",")
            if value
        }
        for reference, level, child, expected in cases:
            if selected and reference not in selected:
                continue
            observed = []

            def observe(dispatcher, invocation, **kwargs):
                if invocation.reference == child:
                    fight = dispatcher.native_retention.fight
                    observed.append(getattr(fight, "native_table_turn", None))
                return original(dispatcher, invocation, **kwargs)

            with self.subTest(
                reference=reference
            ), original_bootstrap_publication(), patch.object(
                EffectDispatcher, "_execute_scoped", observe
            ):
                case = build_fixture(reference, level)
                receipt = case.fight.native_npc_initialization_receipts[-7]
                self.assertTrue(receipt["initialized"])
                for _ in range(16):
                    if case.fight.native_table_turn >= 5:
                        break
                    case.advance()
                self.assertGreaterEqual(case.fight.native_table_turn, 5)
                if not expected:
                    # The original herd mechanic needs more than one human.
                    self.assertEqual(observed, [])
                    continue
                self.assertTrue(
                    any(table is not None and table >= 2 for table in observed),
                    f"Native constructor {reference} never executed recurring child {child} after opening: {observed}",
                )
                self.assertIn(
                    5,
                    observed,
                    "A native state refresh must retain its later table producer",
                )

    def test_herd_repeats_with_two_real_human_owners_and_paid_ack_turns(self):
        from jondo_native_support_probe import build_fixture, _drain
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_server_spell import server_runtime, states_catalog

        events, boundaries = [], []
        original = EffectDispatcher._execute_scoped

        def markers(fight):
            return [
                actor.id
                for actor in fight.actors.values()
                if any(state.reference == 5605 for state in actor.state_ledger.entries)
            ]

        def observe(dispatcher, invocation, **kwargs):
            selected = invocation.reference in (265136, 265137, 265139)
            fight = dispatcher.native_retention.fight if selected else None
            before = markers(fight) if selected else None
            result = original(dispatcher, invocation, **kwargs)
            if selected:
                events.append(
                    dict(
                        effect=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        table=fight.native_table_turn,
                        markers_before=before,
                        markers_after=markers(fight),
                    )
                )
            return result

        with original_bootstrap_publication(), patch.object(
            EffectDispatcher, "_execute_scoped", observe
        ):
            case = build_fixture(4758, 53, additional_humans=1)
            self.assertEqual(len(case.characters), 2)
            owners = {character["account_id"] for character in case.characters.values()}
            self.assertEqual(
                len(owners), 2, "A hero cannot substitute for a second human owner"
            )
            first = case.characters[case.first]
            _, adapter = server_runtime(
                first,
                case.monsters,
                case.decks[case.first],
                action_id=case.runtime.action_id + 1,
                critical=False,
                player_characters=case.characters,
                deck_blobs=case.decks,
            )
            human_facts = []
            for identity, character in case.characters.items():
                actor = case.fight.actors[identity]
                authority = adapter._actor(case.fight, actor)
                self.assertEqual(actor.owner_id, character["account_id"])
                self.assertTrue(actor.controlled)
                self.assertEqual(authority.native_actor_type, 0)
                self.assertTrue(authority.native_in_play)
                self.assertIsNone(getattr(actor, "native_companion_source", None))
                human_facts.append(
                    dict(
                        identity=identity,
                        owner=actor.owner_id,
                        native_actor_type=authority.native_actor_type,
                    )
                )
            constructor = case.fight.native_npc_initialization_receipts[-7]
            self.assertTrue(constructor["initialized"])
            self.assertEqual(constructor["ref"], 4758)
            self.assertIn(
                5606, {row["state_id"] for row in constructor["resolved_states"]}
            )
            self.assertTrue(
                markers(case.fight), "The real native constructor must install5605"
            )
            self.assertTrue(set(markers(case.fight)) <= set(case.characters))
            # One ordinary owned move pays real MP; all later tables use the existing END/ACK path.
            for _ in range(12):
                if case.fight.current.id in case.characters:
                    break
                case.advance()
            identity = case.fight.current.id
            self.assertIn(identity, case.characters)
            origin = case.fight.current.position
            path = case.path_to(identity, lambda cell: cell != origin)
            self.assertTrue(path)
            self.assertTrue(case.player_move_prefix(identity, path[:1]))
            _drain(case)
            payment = case.payments[-1]
            self.assertEqual(payment["before"]["mp"] - payment["after"]["mp"], 1)
            for _ in range(32):
                boundaries.append(
                    dict(
                        table=case.fight.native_table_turn,
                        markers=markers(case.fight),
                        current=case.fight.current.id,
                        awaiting_ack=case.runtime.awaiting_ack,
                    )
                )
                if case.fight.native_table_turn >= 5:
                    break
                case.advance()
            self.assertGreaterEqual(case.fight.native_table_turn, 5)
            self.assertIsNone(case.runtime.awaiting_ack)
            applied = [event for event in events if event["effect"] == 265137]
            self.assertEqual([event["table"] for event in applied], [1, 3, 5])
            for event in applied:
                self.assertEqual(
                    event["markers_before"],
                    [],
                    "An existing5605 must suppress a fresh herd",
                )
                self.assertEqual(event["markers_after"], [event["target"]])
                self.assertIn(event["target"], case.characters)
            self.assertTrue(
                {2, 4}
                <= {event["table"] for event in events if event["effect"] == 265139}
            )
            self.assertTrue(
                markers(case.fight), "Table5 must reapply the actual native herd"
            )
            source = states_catalog()["effects"]
            evidence = dict(
                reference=4758,
                constructor_state=5606,
                root=265135,
                original_condition=source["265135"]["criteria"],
                humans=human_facts,
                events=events,
                boundaries=boundaries,
                payment=payment,
                final_table=case.fight.native_table_turn,
                final_markers=markers(case.fight),
                final_awaiting_ack=case.runtime.awaiting_ack,
                scope="Two native human owners; real constructor, paid movement and END/ACK clocks; generic fixture1134, not a complete dungeon fight",
                reused_negative="Existing solo4758 control through table5; not rerun",
                assigned_states=False,
                assigned_clocks=False,
                earned_victory=False,
            )
            output = os.environ.get("WAKFU_HERD_POSITIVE_RECEIPT")
            if output:
                Path(output).write_text(
                    json.dumps(evidence, indent=2, default=str) + "\n"
                )


if __name__ == "__main__":
    unittest.main()
