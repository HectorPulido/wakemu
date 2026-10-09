import struct
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

import audit_class_conditional_transitions as audit


class ConditionalTransitionOwnerTests(unittest.TestCase):
    def test_consumption_requires_complete_actual_owner_ledger_and_reference_absence(
        self,
    ):
        self.assertFalse(audit.committed_state_absent({}, 7, 7651))
        self.assertFalse(
            audit.committed_state_absent(
                {
                    "state_ledgers_after": {
                        "7": {"entries": [{"reference": 7651, "uid": 2}]}
                    }
                },
                7,
                7651,
            )
        )
        self.assertTrue(
            audit.committed_state_absent(
                {
                    "state_ledgers_after": {
                        "7": {"entries": [{"reference": 7745, "uid": 3}]}
                    }
                },
                7,
                7651,
            )
        )

    def test_expiry_control_is_independent_of_on_cast_cost_and_usage(self):
        precast = N(ap=4, usage={}, state_uids=[123])
        on, off = audit.independent_transition_branches(precast)
        on.ap -= 3
        on.usage[60] = 1
        on.state_uids.clear()
        self.assertEqual((off.ap, off.usage, off.state_uids), (4, {}, [123]))
        off.state_uids.clear()  # The actual expiry branch changes only itself.
        self.assertEqual(precast.state_uids, [123])
        self.assertEqual(precast.ap, 4)

    def test_owned_turn_advancement_uses_actual_end_and_ack_without_resource_writes(
        self,
    ):
        from unittest.mock import Mock

        player = N(id=7, owner_id=73, ap=0)
        monster = N(id=-7, controlled=False)
        fight = N(phase="active", current=monster, turn_id=11)
        runtime = N(fight=fight, awaiting_ack=None)

        def end(actor_id, turn_id):
            self.assertEqual((actor_id, turn_id), (-7, 11))
            runtime.awaiting_ack = 12
            fight.current = player
            return [b"end"]

        def acknowledge(body):
            self.assertEqual(struct.unpack(">i", body)[0], 12)
            runtime.awaiting_ack = None
            return [b"ack"]

        runtime.end_server_turn = Mock(side_effect=end)
        runtime.acknowledge_turn = Mock(side_effect=acknowledge)
        stages = audit.reach_owned_turn(runtime, 7, maximum_turns=4)
        self.assertEqual([stage["stage"] for stage in stages], ["end_turn", "ack"])
        self.assertEqual(player.ap, 0)
        runtime.end_server_turn.assert_called_once()
        runtime.acknowledge_turn.assert_called_once()

    def test_actual_ready_callback_cast_uses_account_owner_and_character_caster(self):
        actor = N(id=7, owner_id=73, state_ledger=N(entries=()))
        fight = N(phase="active", current=actor, actors={7: actor})
        runtime = N(fight=fight, awaiting_ack=None, action_id=1)
        character = dict(id=7, account_id=73, breed=9, level=20)
        case = dict(
            breed=9,
            level=20,
            state=7778,
            selector="caster",
            caller=50,
            spell=60,
            branch=0,
            native_state_applicator=500,
        )
        inspector = audit.TransitionAudit([case])
        inspector.current_case = case
        selected = dict(
            eligible=[dict(target=(1, 2, 3))], status="eligible_targets_found"
        )
        unavailable = dict(eligible=[], status="no_eligible_context")
        transaction = N(plan=dict(costs=dict(ap=1, mp=0, wp=0), target_id=7))
        with patch.object(
            audit, "snapshot", return_value={"actual_ready": True}
        ), patch.object(
            audit, "validate_deck", return_value=dict(active=[50, 60])
        ), patch.object(
            audit, "morph_record", return_value=None
        ), patch.object(
            audit, "granted_spells", return_value={}
        ), patch.object(
            audit, "server_runtime", return_value=(None, N())
        ), patch.object(
            audit, "eligible_cast_targets", side_effect=[selected, unavailable]
        ), patch.object(
            audit, "prepare_server_spell", return_value=transaction
        ) as prepare, patch.object(
            audit, "commit_spell_transaction", return_value=[]
        ) as commit:
            result = inspector(
                runtime, character, {"id": -7}, b"actual-deck", [], lambda *args: b""
            )
        self.assertEqual(result["attempts"][0]["status"], "actual_caller_committed")
        self.assertTrue(result["source_preserved"])
        qualification = result["attempts"][0]["actual_producer_qualification"]
        self.assertFalse(qualification["applicator_completed"])
        self.assertFalse(qualification["literal_required_level_met"])
        self.assertEqual(prepare.call_args.args[4], 73)
        self.assertEqual(struct.unpack(">qqiih", prepare.call_args.args[0])[0], 7)
        self.assertEqual(prepare.call_args.args[1], character)
        self.assertEqual(prepare.call_args.args[5], b"actual-deck")
        commit.assert_called_once()
