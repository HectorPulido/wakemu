from copy import deepcopy
import unittest
from monster_actual_ai_gameplay import committed_gameplay_delta, execute_replanned


class ActualAiGameplayTests(unittest.TestCase):
    def snapshot(self):
        return dict(
            actors={
                7: dict(
                    position=(0, 0, 0),
                    statistics={1: 50, 2: 6, 3: 3, 4: 2},
                    copied_actions=None,
                )
            },
            areas={},
            granted={7: []},
            hp_states={7: dict(hp=50, states=[])},
        )

    def delta(self, before, after, kind="cast"):
        return committed_gameplay_delta(
            before, after, caster_id=7, action=dict(type=kind)
        )

    def test_caster_ap_mp_wp_payment_alone_is_not_effectful_cast(self):
        before = self.snapshot()
        after = deepcopy(before)
        after["actors"][7]["statistics"].update({2: 3, 3: 2, 4: 1})
        delta = self.delta(before, after)
        self.assertFalse(delta["effectful_committed_cast"])
        self.assertEqual(len(delta["excluded_possible_caster_resource_payments"]), 3)

    def test_real_healing_or_state_buff_qualifies_cast(self):
        before = self.snapshot()
        for change in (dict(hp=60, states=[]), dict(hp=50, states=[(913, 2)])):
            after = deepcopy(before)
            after["hp_states"][7] = change
            self.assertTrue(self.delta(before, after)["effectful_committed_cast"])

    def test_actual_roster_or_native_area_delta_qualifies_cast(self):
        before = self.snapshot()
        after = deepcopy(before)
        after["actors"][8] = dict(
            position=(1, 0, 0), statistics={}, copied_actions=None
        )
        self.assertTrue(self.delta(before, after)["effectful_committed_cast"])
        after = deepcopy(before)
        after["areas"][900] = dict(reference=669, level=1, cell=(1, 0, 0))
        self.assertTrue(self.delta(before, after)["effectful_committed_cast"])

    def test_movement_only_action_does_not_qualify(self):
        before = self.snapshot()
        after = deepcopy(before)
        after["actors"][7]["position"] = (1, 0, 0)
        delta = self.delta(before, after, "move")
        self.assertTrue(delta["effectful_gameplay"])
        self.assertFalse(delta["effectful_committed_cast"])

    def test_replans_after_move_accepts_fresh_cast_and_enforces_end_or_bound(self):
        actions = [dict(type="move", to=1), dict(type="cast", spellId=7)]
        state = []

        def choose():
            self.assertEqual(len(state), 2 - len(actions))
            return actions.pop(0), dict(fresh=len(state))

        def commit(action):
            state.append(action)
            return dict(
                gameplay=dict(effectful_committed_cast=action["type"] == "cast")
            )

        result = execute_replanned(choose=choose, commit=commit)
        self.assertEqual(result["status"], "validated_ordinary_ai")
        self.assertEqual([s["decision"]["fresh"] for s in result["steps"]], [0, 1])
        self.assertEqual(
            execute_replanned(
                choose=lambda: (dict(type="end_turn"), {}),
                commit=lambda _: self.fail("end turn committed"),
            )["steps"],
            [],
        )
        commits = []
        result = execute_replanned(
            choose=lambda: (dict(type="move"), {}),
            commit=lambda a: commits.append(a)
            or dict(gameplay=dict(effectful_committed_cast=False)),
        )
        self.assertEqual(len(commits), 3)
        self.assertEqual(result["status"], "pending")
