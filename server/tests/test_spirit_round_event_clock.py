"""Spirit source-scoped publisher clock; native encounter outcome is separate QA."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_equipment_external_events as generic
from wakfu_server import combat_spirit_round_events as spirit
from wakfu_server.combat_conditions import ConditionContext, evaluate_condition


class SpiritRoundClockTests(unittest.TestCase):
    def fixture(self, completed=13):
        carrier = SimpleNamespace(uid=51, reference=9145, caster_id=7, target_id=7)
        player = SimpleNamespace(
            id=7,
            controlled=True,
            owner_id=3,
            in_play=True,
            state_ledger=SimpleNamespace(entries=[carrier]),
        )
        boss = SimpleNamespace(id=-7, controlled=False)
        source = dict(
            policy=spirit.SCENE,
            scenario_id=2710,
            guide_id=175,
            fight_id=1,
            map_id=1134,
            admission_digest="a" * 64,
            participant_id=7,
            player_ids=[7],
        )
        ready_source = dict(
            authority="existing_ready_refreshed_owned_participant_provider",
            fight_id=1,
            admission_digest="a" * 64,
            players=[dict(actor_id=7, account_id=3)],
        )
        scene = dict(
            source=source,
            source_digest=spirit._digest(source),
            ready_participants=dict(
                source=ready_source, source_digest=spirit._digest(ready_source)
            ),
            status="granted",
            carrier_uids={"7": 51},
        )
        fight = SimpleNamespace(
            id=1,
            actors={7: player, -7: boss},
            phase="active",
            current=player,
            native_timeline_round=completed + 1,
            native_table_turn=completed + 1,
            turn_id=28,
            native_encounter_objective_policy={"policy": spirit.OBJECTIVE},
            native_encounter_objective_player_id=7,
            native_spirit_scene_admission=scene,
            native_owned_group_effects={},
            native_owned_equipment_initializations={},
            order=[7, -7],
            _in_play=lambda actor: actor.in_play,
        )
        receipt = dict(
            policy=generic.ROUND_POLICY,
            completed_round=completed,
            ending_turn=27,
            ending_actor=-7,
            delivered=False,
        )
        fight.native_equipment_completed_rounds = {str(completed): receipt}
        entries = [
            SimpleNamespace(uid=61, generic_effect=410946, owner_uid=51, manager_id=7),
            SimpleNamespace(uid=62, generic_effect=410946, owner_uid=52, manager_id=7),
            SimpleNamespace(uid=63, generic_effect=2222, owner_uid=61, manager_id=7),
            SimpleNamespace(uid=81, generic_effect=3333, owner_uid=None, manager_id=7),
        ]
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(
                fight=fight, view=lambda: SimpleNamespace(entries=entries)
            ),
            native_clone_authority=object(),
            effects={"410946": dict(target_masks=[[], [], [], [], [], [1004], []])},
        )
        trace = []

        def replay(event, *, eligible_uids, authority):
            trace.append(
                (
                    event.manager_actor_id,
                    event.channel,
                    frozenset(eligible_uids),
                    fight.native_table_turn,
                )
            )
            if (
                61 in eligible_uids
                and event.manager_actor_id == 7
                and event.channel == 6
            ):
                context = ConditionContext(
                    {}, fight_current_table_turn=fight.native_table_turn
                )
                return (
                    ("native-clock-criterion-accepted",)
                    if evaluate_condition("GetFightCurrentTableTurn() == 13", context)
                    else ()
                )
            return ()

        dispatcher.replay_event = replay
        return fight, dispatcher, entries, trace

    @contextmanager
    def authority(self, fight):
        policy = SimpleNamespace(
            reference=5848,
            native_player_state=9145,
            scene_contract_policy=spirit.SCENE,
            observe_native_producer=True,
            boundary="completed_round",
            map_id=1134,
        )
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "wakfu_server.combat_encounter_objective_policy.require_admitted_policy",
                    return_value=policy,
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.combat_encounter_objective._score_scope",
                    side_effect=lambda current, policy: (
                        {
                            "player_ids": [
                                row["actor_id"]
                                for row in current.native_spirit_scene_admission[
                                    "ready_participants"
                                ]["source"]["players"]
                            ]
                        },
                        current.actors[-7],
                    ),
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.combat_encounter_objective._admission",
                    return_value=(spirit.SCENE, "a" * 64, "release"),
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.combat_encounter_objective.deliver_objective_score_marker",
                    return_value=False,
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
                    side_effect=lambda current: current.native_spirit_scene_admission,
                )
            )
            stack.enter_context(
                patch.object(
                    generic, "qualified_uids", return_value=frozenset({61, 81})
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.combat_npc_external_event_scope.qualified_npc_uids",
                    return_value=frozenset({61, 62, 63}),
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.combat_global_pv_collections.global_pv_iterator",
                    side_effect=lambda current, **kwargs: tuple(
                        identity
                        for identity in current.order
                        if not getattr(current.actors[identity], "pve_withdrawn", False)
                    ),
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.combat_external_event_removal.has_removal_subscription",
                    return_value=False,
                )
            )
            yield

    def test_completed_twelve_does_not_satisfy_thirteen_and_other_clocks_stay_thirteen(
        self,
    ):
        fight, dispatcher, _, trace = self.fixture(12)
        with self.authority(fight):
            self.assertEqual(generic.deliver_completed_round(dispatcher), ())
        own = [row for row in trace if 61 in row[2]]
        ordinary = [row for row in trace if 81 in row[2]]
        self.assertTrue(own and ordinary)
        self.assertEqual({row[3] for row in own}, {12})
        self.assertEqual({row[3] for row in ordinary}, {13})
        self.assertEqual(fight.native_table_turn, 13)

    def test_completed_thirteen_uses_native_guard_once_restores_clock_and_keeps_foreign_source(
        self,
    ):
        fight, dispatcher, _, trace = self.fixture(13)
        with self.authority(fight):
            self.assertEqual(
                generic.deliver_completed_round(dispatcher),
                ("native-clock-criterion-accepted",),
            )
            before = deepcopy(fight.native_spirit_completed_round_events), list(trace)
            self.assertEqual(generic.deliver_completed_round(dispatcher), ())
            self.assertEqual(
                (fight.native_spirit_completed_round_events, trace), before
            )
        self.assertEqual(fight.native_table_turn, 14)
        own = [row for row in trace if 61 in row[2]]
        ordinary = [row for row in trace if 81 in row[2]]
        self.assertEqual({row[3] for row in own}, {13})
        self.assertEqual({row[3] for row in ordinary}, {14})
        self.assertTrue(
            all(
                62 in row[2] and 61 not in row[2] and 63 not in row[2]
                for row in ordinary
            )
        )
        self.assertTrue(all(row[2] == frozenset({61, 63}) for row in own))

    def test_scoped_callback_failure_restores_actual_su_clock(self):
        fight, dispatcher, _, _ = self.fixture(13)
        with self.authority(fight):
            scope = spirit.prepare_scope(dispatcher)
            receipt = fight.native_equipment_completed_rounds["13"]
            receipt["delivered"] = True

            def reject(event, **kwargs):
                self.assertEqual(fight.native_table_turn, 13)
                raise ValueError("unpublished native callback rejected")

            dispatcher.replay_event = reject
            with self.assertRaisesRegex(ValueError, "unpublished native callback"):
                spirit.deliver_completed_round(dispatcher, receipt, ((7, 6),), scope)
        self.assertEqual(fight.native_table_turn, 14)

    def test_scene_digest_and_actual_carrier_owner_are_required(self):
        for mutation in ("digest", "owner", "carrier"):
            fight, dispatcher, entries, _ = self.fixture()
            if mutation == "digest":
                fight.native_spirit_scene_admission["source_digest"] = "f" * 64
            elif mutation == "owner":
                entries[0].owner_uid = 999
            else:
                fight.native_spirit_scene_admission["carrier_uids"]["7"] = 999
            with self.subTest(mutation=mutation), self.authority(
                fight
            ), self.assertRaises(ValueError):
                spirit.prepare_scope(dispatcher)
            self.assertEqual(fight.native_table_turn, 14)
            self.assertFalse(hasattr(fight, "native_spirit_completed_round_events"))

    def test_changed_completed_receipt_is_not_a_clock_authority(self):
        fight, dispatcher, _, _ = self.fixture()
        with self.authority(fight):
            scope = spirit.prepare_scope(dispatcher)
            receipt = dict(
                fight.native_equipment_completed_rounds["13"],
                delivered=True,
                ending_turn=99,
            )
            with self.assertRaisesRegex(ValueError, "actual completed SU receipt"):
                spirit.deliver_completed_round(dispatcher, receipt, ((7, 6),), scope)
        self.assertEqual(fight.native_table_turn, 14)

    def test_unrelated_fight_has_no_source_scope(self):
        fight, dispatcher, _, _ = self.fixture()
        del fight.native_encounter_objective_policy
        self.assertIsNone(spirit.prepare_scope(dispatcher))
        self.assertFalse(spirit.has_round_interest(fight))

    def test_actual_retired_root_does_not_receive_a_later_clock_replay(self):
        fight, dispatcher, entries, trace = self.fixture()
        with self.authority(fight):
            scope = spirit.prepare_scope(dispatcher)
            entries[:] = [entry for entry in entries if entry.uid not in (61, 63)]
            receipt = dict(
                fight.native_equipment_completed_rounds["13"], delivered=True
            )
            self.assertEqual(
                spirit.deliver_completed_round(dispatcher, receipt, ((7, 6),), scope),
                (),
            )
        self.assertEqual(fight.native_table_turn, 14)
        self.assertFalse(trace)

    def party_fixture(self, completed=13):
        fight, dispatcher, entries, trace = self.fixture(completed)
        carrier = SimpleNamespace(uid=52, reference=9145, caster_id=8, target_id=8)
        second = SimpleNamespace(
            id=8,
            controlled=True,
            owner_id=4,
            in_play=True,
            state_ledger=SimpleNamespace(entries=[carrier]),
        )
        fight.actors[8] = second
        fight.order = [7, 8, -7]
        scene = fight.native_spirit_scene_admission
        ready = scene["ready_participants"]
        ready["source"]["players"].append(dict(actor_id=8, account_id=4))
        ready["source_digest"] = spirit._digest(ready["source"])
        scene["carrier_uids"]["8"] = 52
        entries[1].owner_uid = 99  # Foreign source remains unrelated to either9145.
        entries.extend(
            [
                SimpleNamespace(
                    uid=71, generic_effect=410946, owner_uid=52, manager_id=8
                ),
                SimpleNamespace(
                    uid=72, generic_effect=2222, owner_uid=71, manager_id=8
                ),
            ]
        )
        original_replay = dispatcher.replay_event

        def replay(event, **kwargs):
            result = original_replay(event, **kwargs)
            if (
                71 in kwargs["eligible_uids"]
                and event.manager_actor_id == 8
                and event.channel == 6
            ):
                context = ConditionContext(
                    {}, fight_current_table_turn=fight.native_table_turn
                )
                return (
                    ("native-clock-criterion-accepted",)
                    if evaluate_condition("GetFightCurrentTableTurn() == 13", context)
                    else ()
                )
            return result

        dispatcher.replay_event = replay
        return fight, dispatcher, entries, trace

    def withdraw_first(self, fight, entries):
        first = fight.actors[7]
        first.pve_withdrawn, first.in_play = True, False
        first.state_ledger.entries.clear()
        fight.native_spirit_scene_admission["carrier_uids"].pop("7")
        entries[:] = [entry for entry in entries if entry.uid not in (61, 63)]
        fight.current = fight.actors[8]

    def test_clock_scope_includes_all_actual_ready_carriers_without_rewriting_initial_admission(
        self,
    ):
        fight, dispatcher, _, _ = self.party_fixture(12)
        original = deepcopy(fight.native_spirit_scene_admission["source"])
        with self.authority(fight):
            scope = spirit.prepare_scope(dispatcher)
        self.assertEqual(scope["player_id"], 7)
        self.assertEqual({binding["player_id"] for binding in scope["sources"]}, {7, 8})
        self.assertEqual(scope["eligible_uids"], frozenset({61, 63, 71, 72}))
        self.assertEqual(fight.native_spirit_scene_admission["source"], original)
        # Initial placement did not yet contain the second actual Ready human.
        self.assertEqual(original["player_ids"], [7])

    def test_partial_principal_withdrawal_hands_clock_to_remaining_ready_owner(self):
        fight, dispatcher, entries, trace = self.party_fixture()
        source = deepcopy(fight.native_spirit_scene_admission["source"])
        ready = deepcopy(fight.native_spirit_scene_admission["ready_participants"])
        with self.authority(fight):
            spirit.prepare_scope(dispatcher)
            self.withdraw_first(fight, entries)
            self.assertEqual(
                generic.deliver_completed_round(dispatcher),
                ("native-clock-criterion-accepted",),
            )
        self.assertEqual(fight.native_spirit_result_leadership["actor_id"], 8)
        self.assertEqual(
            fight.native_spirit_result_leadership["handoffs"][-1]["from_actor_id"], 7
        )
        self.assertEqual(fight.native_spirit_scene_admission["source"], source)
        self.assertEqual(
            fight.native_spirit_scene_admission["ready_participants"], ready
        )
        self.assertEqual(fight.native_encounter_objective_player_id, 7)
        self.assertEqual(fight.native_table_turn, 14)
        self.assertEqual(
            fight.native_spirit_completed_round_events["13"]["player_id"], 8
        )
        self.assertTrue(
            any(
                row[0] == 8 and row[3] == 13 and row[2] == frozenset({71, 72})
                for row in trace
            )
        )

    def test_ordinary_callbacks_can_retire_the_leader_without_cancelling_remaining_clock(
        self,
    ):
        fight, dispatcher, entries, _ = self.party_fixture()
        with self.authority(fight):
            scope = spirit.prepare_scope(dispatcher)
            self.withdraw_first(fight, entries)
            receipt = dict(
                fight.native_equipment_completed_rounds["13"], delivered=True
            )
            self.assertEqual(
                spirit.deliver_completed_round(dispatcher, receipt, ((8, 6),), scope),
                ("native-clock-criterion-accepted",),
            )
        self.assertEqual(fight.native_table_turn, 14)
        self.assertEqual(
            fight.native_spirit_completed_round_events["13"]["player_id"], 8
        )

    def test_unowned_remaining_actor_does_not_inherit_the_departed_leader_clock(self):
        fight, dispatcher, entries, _ = self.party_fixture()
        self.withdraw_first(fight, entries)
        fight.actors[8].owner_id = 99
        with self.authority(fight):
            self.assertIsNone(spirit.prepare_scope(dispatcher))
        self.assertFalse(hasattr(fight, "native_spirit_completed_round_events"))

    def test_non_ready_actor_with_same_state_cannot_join_the_clock_scope(self):
        fight, dispatcher, entries, _ = self.party_fixture()
        impostor = SimpleNamespace(
            id=9,
            controlled=True,
            owner_id=4,
            in_play=True,
            state_ledger=SimpleNamespace(
                entries=[
                    SimpleNamespace(uid=53, reference=9145, caster_id=9, target_id=9)
                ]
            ),
        )
        fight.actors[9] = impostor
        fight.native_spirit_scene_admission["carrier_uids"]["9"] = 53
        entries.append(
            SimpleNamespace(uid=91, generic_effect=410946, owner_uid=53, manager_id=9)
        )
        with self.authority(fight):
            scope = spirit.prepare_scope(dispatcher)
        self.assertNotIn(91, scope["eligible_uids"])
        self.assertEqual({binding["player_id"] for binding in scope["sources"]}, {7, 8})

    def test_post_generic_marker_recheck_uses_the_remaining_current_boundary(self):
        fight, dispatcher, entries, _ = self.party_fixture()
        with self.authority(fight):
            scope = spirit.prepare_scope(dispatcher)
            self.withdraw_first(fight, entries)
            receipt = dict(
                fight.native_equipment_completed_rounds["13"], delivered=True
            )
            with patch(
                "wakfu_server.combat_encounter_objective.deliver_objective_score_marker",
                return_value=False,
            ) as marker:
                spirit.deliver_completed_round(dispatcher, receipt, ((8, 6),), scope)
            marker.assert_called_once_with(
                dispatcher, actor_id=8, allow_delivered_round=True
            )
        self.assertEqual(fight.native_table_turn, 14)


if __name__ == "__main__":
    unittest.main()
