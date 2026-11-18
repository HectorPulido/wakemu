import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from wakfu_server import combat_native_dj_dance as dj


class NativeDjDanceTests(unittest.TestCase):
    def setUp(self):
        self.states = [
            dict(reference=1932, level=4, uid=11),
            dict(reference=1943, level=1, uid=12),
            dict(reference=1934, level=3, uid=13),
            dict(reference=1945, level=2, uid=14),
        ]
        self.state = dj.start(
            owner_id=101,
            owner_account_id=42,
            owner_level=85,
            setup_actor_id=202,
            setup_actor_reference=2502,
            setup_spell_id=3700,
            setup_root=95219,
            setup_state_effect=95845,
            applied_state_reference=1941,
            challenge_state_uid=20,
            area_subscription_event=1001,
            control_states=self.states,
        )

    def test_original_setup_witness_and_lowest_state_order_are_required(self):
        self.assertEqual(
            [row["reference"] for row in self.state["expected"]],
            [1943, 1945, 1934, 1932],
        )
        self.assertEqual([row["level"] for row in self.state["expected"]], [1, 2, 3, 4])
        for field, value in (
            ("setup_actor_reference", 2518),
            ("owner_level", 84),
            ("setup_spell_id", 3701),
            ("setup_root", 95121),
            ("setup_state_effect", 94812),
            ("applied_state_reference", 1932),
            ("area_subscription_event", 1003),
        ):
            args = dict(
                owner_id=101,
                owner_account_id=42,
                owner_level=85,
                setup_actor_id=202,
                setup_actor_reference=2502,
                setup_spell_id=3700,
                setup_root=95219,
                setup_state_effect=95845,
                applied_state_reference=1941,
                challenge_state_uid=20,
                area_subscription_event=1001,
                control_states=self.states,
            )
            args[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                dj.start(**args)

    def test_four_real_ordered_commands_complete_once(self):
        commands = ((3714, 528), (3716, 530), (3703, 529), (3701, 527))
        result = None
        for index, (spell, area) in enumerate(commands):
            self.state, result = dj.apply_input(
                self.state,
                actor_id=101,
                spell_id=spell,
                target_id=101,
                target_cell=(index, 0, 0),
                actual_color_area=area,
                cast_committed=True,
                cast_event_id=index + 1,
            )
        self.assertEqual(
            result,
            dict(
                kind="scenario_completed",
                quest_id=1264,
                objective_id=2393,
                evidence="four_native_ordered_dj_inputs",
            ),
        )
        self.assertEqual(self.state["stage"], "complete")
        replay, result = dj.apply_input(
            self.state,
            actor_id=101,
            spell_id=3701,
            target_id=101,
            target_cell=(0, 0, 0),
            actual_color_area=527,
            cast_committed=True,
            cast_event_id=5,
        )
        self.assertEqual(result, None)
        self.assertEqual(replay, self.state)

    def test_rejected_cast_does_not_progress_and_wrong_committed_input_fails(self):
        unchanged, result = dj.apply_input(
            self.state,
            actor_id=101,
            spell_id=3714,
            target_id=101,
            target_cell=(0, 0, 0),
            actual_color_area=528,
            cast_committed=False,
            cast_event_id=None,
        )
        self.assertEqual(result, None)
        self.assertEqual(unchanged, self.state)
        failed, result = dj.apply_input(
            self.state,
            actor_id=101,
            spell_id=3701,
            target_id=101,
            target_cell=(0, 0, 0),
            actual_color_area=527,
            cast_committed=True,
            cast_event_id=9,
        )
        self.assertEqual(failed["stage"], "failed")
        self.assertEqual(result["kind"], "failed")
        self.assertEqual(failed["index"], 0)

    def test_order_requires_four_distinct_states_and_unique_levels(self):
        with self.assertRaises(ValueError):
            dj.start(
                owner_id=101,
                owner_account_id=42,
                owner_level=85,
                setup_actor_id=202,
                setup_actor_reference=2502,
                setup_spell_id=3700,
                setup_root=95219,
                setup_state_effect=95845,
                applied_state_reference=1941,
                challenge_state_uid=20,
                area_subscription_event=1001,
                control_states=self.states[:3],
            )
        tied = [dict(row) for row in self.states]
        tied[0]["level"] = tied[1]["level"]
        with self.assertRaises(ValueError):
            dj.start(
                owner_id=101,
                owner_account_id=42,
                owner_level=85,
                setup_actor_id=202,
                setup_actor_reference=2502,
                setup_spell_id=3700,
                setup_root=95219,
                setup_state_effect=95845,
                applied_state_reference=1941,
                challenge_state_uid=20,
                area_subscription_event=1001,
                control_states=tied,
            )

    def test_actual_committed_cast_path_reads_registered_area_and_keeps_owner_receipts(
        self,
    ):
        owner = SimpleNamespace(
            id=101,
            owner_id=42,
            effective_level=85,
            controlled=True,
            team=0,
            position=(0, 0, 0),
            # 2502's native321 children clear the eight prior dance/beatbox
            # states after the1941 setup marker is committed.
            state_ledger=SimpleNamespace(
                entries=(SimpleNamespace(reference=1941, level=1, uid=20),)
            ),
        )

        class Fight:
            id = 88
            phase = "active"
            winner = None
            sequence = 0

            def __init__(self):
                self.actors = {101: owner}
                self.events = []
                self.native_dj_dance = dict(self.state)
                self.sequence = 0

            def _event(self, kind, **fields):
                self.sequence += 1
                event = dict(sequence=self.sequence, kind=kind, **fields)
                self.events.append(event)
                return event

        Fight.state = self.state
        fight = Fight()
        fight.native_dj_dance["control_book_spells"] = list(dj.CONTROL_BOOK_SPELLS)
        fight.native_dj_dance["grant_uids"] = list(range(31, 39))
        fight.native_dj_dance["source_sha256"] = dj.digest(
            {
                key: value
                for key, value in fight.native_dj_dance.items()
                if key != "source_sha256"
            }
        )
        commands = ((3714, 528), (3716, 530), (3703, 529), (3701, 527))
        with patch(
            "wakfu_server.combat_effect_area_queries.cell_contains_specific"
        ) as has_area:
            for action_id, (spell, area) in enumerate(commands, 1):
                has_area.side_effect = (
                    lambda _fight, *, cell, reference: reference == area
                )
                dj.record_committed_cast(
                    fight,
                    dict(
                        actor_id=101,
                        target_id=101,
                        target=owner.position,
                        spell_id=spell,
                    ),
                    action_id=action_id,
                )
        self.assertEqual(fight.native_dj_dance["stage"], "complete")
        self.assertEqual(len(fight.native_dj_dance["accepted"]), 4)
        self.assertIs(dj.validate_fight(fight), fight.native_dj_dance)

        class AdoptedFight:
            def _event(self, kind, **fields):
                self.sequence += 1
                event = dict(sequence=self.sequence, kind=kind, **fields)
                self.events.append(event)
                return event

        adopted = AdoptedFight()
        adopted.id = fight.id
        adopted.sequence = fight.sequence
        adopted.events = fight.events
        adopted.native_dj_dance = fight.native_dj_dance
        adopted.actors = fight.actors
        adopted.phase = "active"
        adopted.winner = None
        self.assertEqual(dj.adopt_witnesses(adopted, fight, previous_sequence=0), 4)
        self.assertIs(dj.validate_fight(adopted), adopted.native_dj_dance)
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        runtime = RuntimeMessages(adopted)
        self.assertTrue(dj.finish_challenge(adopted, runtime))
        self.assertEqual(adopted.phase, "finished")
        self.assertEqual(adopted.winner, owner.team)
        self.assertEqual(
            adopted.native_dj_dance["terminal"]["result"], "challenge_completed"
        )
        self.assertEqual(
            [event["kind"] for event in adopted.events[-2:]],
            ["challenge_terminal", "finished"],
        )
        self.assertIs(dj.validate_fight(adopted), adopted.native_dj_dance)
        self.assertFalse(dj.finish_challenge(adopted, runtime))

    def test_control_book_is_the_original_2518_order(self):
        fixture = json.loads(
            Path("server/tests/fixtures/native_dj_dance_quest1264.json").read_text()
        )
        self.assertEqual(
            dj.control_book_source(fixture["native_profiles"]["2518"]),
            (3713, 3714, 3715, 3716, 3701, 3702, 3703, 3704),
        )

    def test_wrong_committed_command_finishes_as_loss_without_quest_credit(self):
        from copy import deepcopy
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        class Fight:
            id = 88
            phase = "active"
            winner = None
            sequence = 0

            def _event(self, kind, **fields):
                self.sequence += 1
                event = dict(sequence=self.sequence, kind=kind, **fields)
                self.events.append(event)
                return event

        fight = Fight()
        fight.events = []
        fight.native_dj_dance = deepcopy(self.state)
        owner = SimpleNamespace(
            id=101,
            owner_id=42,
            controlled=True,
            team=0,
            position=(0, 0, 0),
            state_ledger=SimpleNamespace(
                entries=(
                    SimpleNamespace(
                        reference=1941, level=1, uid=self.state["challenge_state_uid"]
                    ),
                )
            ),
        )
        fight.actors = {101: owner, 202: SimpleNamespace(id=202, team=1)}
        fight.native_dj_dance.update(
            control_book_spells=list(dj.CONTROL_BOOK_SPELLS),
            grant_uids=list(range(31, 39)),
        )
        fight.native_dj_dance["source_sha256"] = dj.digest(
            {
                key: value
                for key, value in fight.native_dj_dance.items()
                if key != "source_sha256"
            }
        )
        with patch(
            "wakfu_server.combat_effect_area_queries.cell_contains_specific",
            return_value=False,
        ):
            dj.record_committed_cast(
                fight,
                dict(actor_id=101, target_id=101, target=owner.position, spell_id=3701),
                action_id=17,
            )
        self.assertEqual(fight.native_dj_dance["stage"], "failed")
        self.assertEqual(fight.native_dj_dance["failures"][0]["event_sequence"], 1)
        # A copied receipt cannot replace the actual accepted cast witness.
        witness = fight.events[0]
        fight.events[0] = dict(witness)
        with self.assertRaises(ValueError):
            dj.finish_challenge(fight, RuntimeMessages(fight))
        fight.events[0] = witness
        self.assertTrue(dj.finish_challenge(fight, RuntimeMessages(fight)))
        self.assertEqual((fight.phase, fight.winner), ("finished", 1))
        self.assertEqual(
            fight.native_dj_dance["terminal"]["result"], "challenge_failed"
        )
        self.assertEqual(fight.native_dj_dance["accepted"], [])
        self.assertIs(dj.validate_fight(fight), fight.native_dj_dance)
        self.assertIs(
            dj.validate_checkpoint({"native_dj_dance": fight.native_dj_dance}),
            fight.native_dj_dance,
        )
        self.assertEqual(dj.stage(None, None, fight), {})
        self.assertFalse(dj.finish_challenge(fight, RuntimeMessages(fight)))

    def test_setup_requires_the_actual_native_root_actor_and_owned_states(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_state_ledger import RunningState

        def state(uid, reference, level, caster, target):
            return RunningState(
                uid,
                reference,
                level,
                caster,
                target,
                0,
                "none",
                False,
                (),
                0,
                False,
                None,
            )

        controls = [
            state(10 + i, row["reference"], row["level"], 200, 101)
            for i, row in enumerate(self.state["expected"])
        ]
        challenge = state(20, 1941, 1, 200, 101)
        owner = SimpleNamespace(
            id=101,
            owner_id=42,
            effective_level=85,
            controlled=True,
            team=0,
            state_ledger=SimpleNamespace(entries=tuple((*controls, challenge))),
        )
        caster = SimpleNamespace(id=200, team=1)
        fight = SimpleNamespace(
            id=88,
            actors={101: owner, 200: caster},
            native_active_spell_id=3700,
            native_active_spell_roots=(95219,),
            native_dj_dance=None,
        )
        handler = SimpleNamespace(
            fight=fight,
            packets=[],
            action_id=1,
            allocate_uid=lambda: 30,
        )
        invocation = EffectInvocation(95845, 1, 200, 101, (0, 0, 0))
        with patch.object(
            dj, "install_control_book", return_value=(31, 32, 33, 34, 35, 36, 37, 38)
        ) as grant:
            contract = dj.start_from_native_state(
                handler,
                {"effect_class": 304},
                invocation,
                challenge,
                actor_reference=lambda actor: 2502 if actor.id == 200 else None,
                actor_real_level=lambda actor: 85 if actor.id == 101 else 100,
                active_roots=(95219,),
            )
        self.assertIsNotNone(contract)
        self.assertEqual(contract["owner_account_id"], 42)
        grant.assert_called_once()

        self.assertIsNone(
            dj.start_from_native_state(
                handler,
                {"effect_class": 304},
                invocation,
                challenge,
                actor_reference=lambda _actor: 2518,
                actor_real_level=lambda _actor: 85,
                active_roots=(95219,),
            )
        )
        self.assertIsNone(
            dj.start_from_native_state(
                handler,
                {"effect_class": 304},
                invocation,
                challenge,
                actor_reference=lambda _actor: 2502,
                actor_real_level=lambda _actor: 85,
                active_roots=(95220,),
            )
        )

    def test_native_setup_waits_for_four_later_order_states_then_accepts_after_reset(
        self,
    ):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_state_ledger import RunningState

        def state(uid, reference, level, caster, target):
            return RunningState(
                uid,
                reference,
                level,
                caster,
                target,
                0,
                "none",
                False,
                (),
                0,
                False,
                None,
            )

        challenge = state(20, 1941, 1, 202, 101)
        owner = SimpleNamespace(
            id=101,
            owner_id=42,
            controlled=True,
            team=0,
            position=(0, 0, 0),
            state_ledger=SimpleNamespace(entries=[challenge]),
        )
        caster = SimpleNamespace(id=202, team=1)
        fight = SimpleNamespace(
            actors={101: owner, 202: caster},
            native_active_spell_id=3700,
            native_active_spell_roots=(95219,),
            native_dj_dance=None,
        )
        handler = SimpleNamespace(
            fight=fight,
            packets=[],
            action_id=1,
            allocate_uid=lambda: 30,
        )
        actor_ref = lambda actor: 2502 if actor.id == 202 else None
        real_level = lambda actor: 85 if actor.id == 101 else 100
        self.assertIsNone(
            dj.observe_native_state(
                handler,
                {"effect_class": 304},
                EffectInvocation(95845, 1, 202, 101, owner.position),
                challenge,
                actor_reference=actor_ref,
                actor_real_level=real_level,
                active_roots=(95219,),
            )
        )
        self.assertIsNone(fight.native_dj_dance)
        fight.native_active_spell_id = 1895
        fight.native_active_spell_roots = ()
        with patch.object(
            dj, "install_control_book", return_value=tuple(range(31, 39))
        ) as grant:
            for index, row in enumerate(self.states, 1):
                current = state(30 + index, row["reference"], row["level"], 202, 101)
                owner.state_ledger.entries.append(current)
                result = dj.observe_native_state(
                    handler,
                    {"effect_class": 304},
                    EffectInvocation(99800 + index, 1, 202, 101, owner.position),
                    current,
                    actor_reference=actor_ref,
                    actor_real_level=real_level,
                    active_roots=(),
                )
            grant.assert_called_once()
        self.assertIsNotNone(result)
        self.assertEqual([row["level"] for row in result["expected"]], [1, 2, 3, 4])
        self.assertEqual(result["challenge_state_uid"], challenge.uid)
        result["control_book_spells"] = list(dj.CONTROL_BOOK_SPELLS)
        result["grant_uids"] = list(range(31, 39))
        result["source_sha256"] = dj.digest(
            {key: value for key, value in result.items() if key != "source_sha256"}
        )

        # The native setup spell subsequently decurses these order carriers.
        owner.state_ledger.entries = [challenge]

        class Fight:
            pass

        committed = Fight()
        committed.__dict__.update(fight.__dict__)
        fight = committed
        fight.events = []
        fight.sequence = 0
        fight.id = 88
        fight.phase = "active"
        fight.winner = None
        fight.native_spell_grants = {
            101: {spell: {} for spell in dj.CONTROL_BOOK_SPELLS}
        }

        def event(kind, **fields):
            fight.sequence += 1
            row = dict(sequence=fight.sequence, kind=kind, **fields)
            fight.events.append(row)
            return row

        fight._event = event
        with patch(
            "wakfu_server.combat_effect_area_queries.cell_contains_specific",
            side_effect=lambda _fight, *, cell, reference: reference == 528,
        ):
            dj.record_committed_cast(
                fight,
                dict(actor_id=101, target_id=101, target=owner.position, spell_id=3714),
                action_id=77,
            )
        self.assertEqual(fight.native_dj_dance["index"], 1)
        self.assertEqual(fight.native_dj_dance["accepted"][0]["expected_state"], 1943)


if __name__ == "__main__":
    unittest.main()
