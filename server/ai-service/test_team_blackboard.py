from copy import deepcopy
from types import SimpleNamespace
import unittest

from team_blackboard import observe, confirm, team_context


def fixture(instance="encounter-one"):
    npc = SimpleNamespace(id=-1, team=1, hp=20, effect_stats={97: 0})
    pc = SimpleNamespace(id=7, team=0, hp=30, effect_stats={97: 4})
    fight = SimpleNamespace(
        id=99,
        current=npc,
        actors={-1: npc, 7: pc},
        turn_id=1,
        sequence=10,
        native_table_turn=1,
    )
    return SimpleNamespace(fight=fight, tactical_encounter_id=instance)


class TeamBlackboardTests(unittest.TestCase):
    def test_kill_is_recorded_without_reserving_dead_target_and_heal_is_net_only(self):
        runtime = fixture()
        before = observe(runtime.fight)
        runtime.fight.actors[7].hp = 0
        runtime.fight.actors[-1].hp += 2
        confirm(runtime, before, [dict(action={"type": "cast"})])
        context = team_context(runtime.fight, "encounter-one", -1)
        self.assertIsNone(context["focusId"])
        record = runtime.fight.native_ai_team_context["1"]["history"][-1]
        self.assertEqual(record["affectedEnemies"][0]["hpLoss"], 30)
        self.assertEqual(
            record["affectedAllies"], [dict(actorId=-1, hpGain=2, armorGain=0)]
        )
        self.assertEqual(record["attribution"], "published_transition_net_outcome")

    def test_local_delivery_failure_does_not_confirm_native_candidate(self):
        from world_host import execute

        runtime = fixture()
        runtime.awaiting_ack, runtime.pending = None, []
        runtime.fight.current.controlled = False
        runtime.fight.phase = "active"

        def runner(native, **kwargs):
            native.fight.actors[7].hp -= 5
            yield [(12588, b"cast"), (13420, b"fifo")], dict(action={"type": "cast"})

        sent = []

        def send(*args):
            sent.append(args[-2])
            if len(sent) == 2:
                raise OSError("client disconnected")

        world = dict(
            STORE=object(),
            character={"id": 7},
            TEST_MONSTERS_BY_ID={},
            send=send,
            connection=object(),
            service="world",
            record=lambda **kwargs: None,
        )
        with self.assertRaisesRegex(OSError, "client disconnected"):
            list(execute(runtime, dict(globals=world, scopes=[]), runner))
        self.assertEqual(sent, [12588, 13420])
        self.assertFalse(hasattr(runtime.fight, "native_ai_team_context"))

    def test_recent_coordination_history_is_bounded_without_changing_native_events(
        self,
    ):
        runtime = fixture()
        runtime.fight.native_events = [{"future": "complete-event-ledger"}]
        for turn in range(40):
            runtime.fight.turn_id = turn
            before = observe(runtime.fight)
            confirm(runtime, before, [dict(action={"type": "end_turn"})])
        history = runtime.fight.native_ai_team_context["1"]["history"]
        self.assertEqual(len(history), 32)
        self.assertEqual(history[0]["turnId"], 8)
        self.assertEqual(
            runtime.fight.native_events, [{"future": "complete-event-ledger"}]
        )

    def publish_attack(self, runtime):
        before = observe(runtime.fight)
        runtime.fight.actors[7].hp -= 5
        runtime.fight.sequence += 1
        confirm(runtime, before, [dict(action={"type": "cast", "spellId": 7962})])

    def test_observation_draft_and_native_damage_do_not_publish_coordination(self):
        runtime = fixture()
        before = observe(runtime.fight)
        runtime.fight.actors[7].hp -= 5
        self.assertFalse(hasattr(runtime.fight, "native_ai_team_context"))
        confirm(runtime, before, [dict(action={"type": "cast"})])
        self.assertEqual(team_context(runtime.fight, "encounter-one", -1)["focusId"], 7)
        self.assertEqual(
            runtime.fight.native_ai_team_context["1"]["history"][0]["affectedEnemies"],
            [dict(actorId=7, hpLoss=5, armorLoss=0)],
        )

    def test_uuid_team_revision_expiry_and_dead_focus_are_isolated(self):
        runtime = fixture()
        self.publish_attack(runtime)
        self.assertIsNone(
            team_context(runtime.fight, "another-instance", -1)["focusId"]
        )
        self.assertIsNone(team_context(runtime.fight, "encounter-one", 7)["focusId"])
        runtime.fight.sequence = 10
        self.assertIsNone(team_context(runtime.fight, "encounter-one", -1)["focusId"])
        runtime.fight.sequence = 12
        self.assertEqual(
            team_context(runtime.fight, "encounter-one", -1)["stateRevision"], 12
        )
        runtime.fight.native_table_turn = 3
        self.assertIsNone(team_context(runtime.fight, "encounter-one", -1)["focusId"])
        runtime.fight.native_table_turn = 1
        runtime.fight.actors[7].hp = 0
        self.assertIsNone(team_context(runtime.fight, "encounter-one", -1)["focusId"])

    def test_read_does_not_mutate_book_and_checkpoint_retains_published_fields(self):
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_state import Actor, Fight

        runtime = fixture()
        self.publish_attack(runtime)
        saved = deepcopy(runtime.fight.native_ai_team_context)
        team_context(runtime.fight, "encounter-one", -1)
        self.assertEqual(saved, runtime.fight.native_ai_team_context)
        native = Fight(
            99,
            [
                Actor(-1, 1, (1, 0, 0), 20, 6, 3, 1, 1),
                Actor(7, 0, (0, 0, 0), 30, 6, 3, 1, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        native.native_ai_team_context = saved
        native.native_ai_fight_uuid = "encounter-one"
        checkpoint = snapshot(native)
        self.assertEqual(checkpoint["native_ai_fight_uuid"], "encounter-one")
        self.assertEqual(checkpoint["native_ai_team_context"], saved)

    def test_same_numeric_fight_id_has_no_cross_instance_history(self):
        one, two = fixture(), fixture("encounter-two")
        self.publish_attack(one)
        self.assertIsNone(team_context(two.fight, "encounter-two", -1)["focusId"])
        self.publish_attack(two)
        self.assertEqual(
            two.fight.native_ai_team_context["1"]["instanceId"], "encounter-two"
        )
        self.assertEqual(len(two.fight.native_ai_team_context["1"]["history"]), 1)
