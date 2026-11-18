"""Source and terminal-event fences for the native 4850 escape callback."""

from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server import (
    combat_encounter_roles,
    combat_encounter_scene_policy,
    combat_scene_triggered_failure as failure,
)


class NativeTriggeredSceneFailureTests(unittest.TestCase):
    def setUp(self):
        self.actor_id = -3589001
        self.descriptor = {
            "schema_version": 1,
            "policy_id": "native-escape-failure-test",
            "authority": "Original source spell callback fixture.",
            "source_uri": "fixture://native-4850-escape",
            "full_room_scope": True,
            "native_escape_failure": {
                "schema": failure.SCHEMA,
                "actor_reference": 3589,
                "trigger_effect": 254694,
                "spell_reference": 4850,
                "state_reference": 3478,
                "losing_role": "original_controlled",
                "evidence": "The original 4850 escape trigger occurs on the owned state carrier.",
            },
        }
        self.scope = {
            "map_id": 777,
            "instance_id": 0,
            "group_id": 91,
            "room_order": 1,
            "policy_version": 1,
            "route_key": "native-escape-test-room",
            "evidence_hashes": {},
            "actor_bindings": [{"actor_id": self.actor_id, "ref": 3589}],
        }
        self.actor = SimpleNamespace(
            id=self.actor_id,
            controlled=False,
            team=1,
            hp=100,
            state_ledger=SimpleNamespace(
                entries=[
                    SimpleNamespace(
                        uid=90001,
                        reference=3478,
                        caster_id=self.actor_id,
                        target_id=self.actor_id,
                        effect_ids=(254692,),
                    )
                ]
            ),
        )
        self.fight = SimpleNamespace(
            id=501,
            phase="active",
            winner=None,
            sequence=12,
            events=[],
            actors={self.actor_id: self.actor},
            native_encounter_roles=combat_encounter_roles._ordinary(
                777, (3589,)
            ).record(),
            native_npc_initialization_receipts={
                self.actor_id: {
                    "initialized": True,
                    "ref": 3589,
                    "resolved_states": [{"state_id": 3478}],
                }
            },
            _in_play=lambda actor: actor.hp > 0,
        )

        def append_event(kind, **fields):
            self.fight.sequence += 1
            self.fight.events.append(
                dict(kind=kind, sequence=self.fight.sequence, **fields)
            )

        self.fight._event = append_event
        self.fight.native_encounter_scene = combat_encounter_scene_policy.prepare_scene(
            self.descriptor, scope=self.scope, room_cells=[(0, 0, 0)]
        )
        self.effect = {"effect_class": 426, "reference": 254694}
        self.effects = {
            "254692": {"effect_class": 330, "children": [254693]},
            "254693": {"effect_class": 330, "children": [254694]},
            "254694": self.effect,
        }
        self.request = SimpleNamespace(spell_id=4850, caster_id=self.actor_id)
        self.invocation = SimpleNamespace(
            reference=254694,
            caster_id=self.actor_id,
            target_id=self.actor_id,
            state_uid=90001,
            native_trigger_context={
                "native_events_verified": True,
                "manager_actor_id": self.actor_id,
                "generic_effect": 254692,
            },
        )

    def test_authentic_4850_callback_rewrites_its_new_terminal_event_once(self):
        captured = failure.prepare_triggered(
            self.fight,
            self.request,
            self.effect,
            self.invocation,
            effects=self.effects,
        )
        self.assertEqual(captured["event_sequence"], 12)
        self.assertEqual(captured["state_reference"], 3478)
        self.assertEqual(captured["trigger_effect"], 254694)

        # The nested native effect has already killed its owner and appended a
        # normal player-win event. Resolve that uncommitted event in place.
        self.actor.hp = 0
        self.fight.phase = "finished"
        self.fight.winner = 0
        self.fight.sequence = 13
        terminal = {"kind": "finished", "sequence": 13, "winner": 0}
        self.fight.events.append(terminal)

        self.assertTrue(failure.settle_triggered(self.fight, captured))
        self.assertEqual(self.fight.winner, 1)
        self.assertEqual(self.fight.phase, "finished")
        self.assertEqual(self.actor.hp, 0)
        self.assertIs(self.fight.events[0], terminal)
        self.assertEqual(terminal["winner"], 1)
        self.assertEqual(terminal["reason"], "owned_scene_native_escape_failure")
        self.assertEqual(terminal["native_original_winner"], 0)
        self.assertFalse(failure.settle_triggered(self.fight, captured))
        self.assertEqual(len(self.fight.events), 1)

    def test_actual_4850_nested_trigger_without_prior_terminal_appends_one_loss(self):
        captured = failure.prepare_triggered(
            self.fight,
            self.request,
            self.effect,
            self.invocation,
            effects=self.effects,
        )
        self.assertTrue(failure.settle_triggered(self.fight, captured))
        self.assertEqual(self.fight.winner, 1)
        self.assertEqual(len(self.fight.events), 1)
        self.assertEqual(self.fight.events[0]["kind"], "finished")
        self.assertEqual(
            self.fight.events[0]["reason"], "owned_scene_native_escape_failure"
        )
        self.assertEqual(self.fight.events[0]["spell_id"], 4850)
        self.assertEqual(self.fight.events[0]["actor_id"], self.actor_id)

    def test_native_4850_leaf_kill_is_adjudicated_before_terminal_consumers(self):
        # Execute the real class-28 handler used by the nested 4850 spell,
        # then settle its callback before a victory consumer can observe it.
        from test_combat_kill import NativeKillTests
        from wakfu_server import combat_effect_dispatch
        from wakfu_server.combat_state_ledger import RunningState

        fight, _, _, _, kill, _, _ = NativeKillTests().fixture()
        actor = fight.actors[-7]
        actor.hp = 80
        actor.effect_stats[1] = 80
        actor.effect_minima[1] = actor.effect_base_minima[1] = 0
        actor.effect_maxima[1] = actor.effect_base_maxima[1] = 100
        actor.effect_percentages[1] = 0
        actor.effect_frozen = frozenset()
        actor.team = 1
        actor.state_ledger._entries = (
            RunningState(
                90001,
                3478,
                1,
                actor.id,
                actor.id,
                0,
                "target",
                False,
                (254692,),
                0,
                False,
                None,
                None,
                None,
                None,
            ),
        )
        self.actor_id = actor.id
        scope = dict(self.scope, actor_bindings=[{"actor_id": actor.id, "ref": 3589}])
        fight.native_encounter_roles = combat_encounter_roles._ordinary(
            777, (3589,)
        ).record()
        fight.native_npc_initialization_receipts = {
            actor.id: {
                "initialized": True,
                "ref": 3589,
                "resolved_states": [{"state_id": 3478}],
            }
        }
        fight.native_encounter_scene = combat_encounter_scene_policy.prepare_scene(
            self.descriptor, scope=scope, room_cells=[(0, 0, 0)]
        )
        # Model the real null-Qe 1001 callback produced for the state carrier.
        # The owned turn scope supplies the authenticated recipient; it does
        # not fabricate a native triggering effect.
        fight.order = [
            actor.id,
            *[identity for identity in fight.order if identity != actor.id],
        ]
        fight.turn_index = 0
        fight.turn_id = 1
        boundary = {
            "policy": "wakemu.owned-turn-boundary-facts-v1",
            "actor_id": actor.id,
            "turn_id": 1,
            "phase": "start",
            "event_id": 1001,
        }
        self.effects["254692"]["target_masks"] = [
            None,
            None,
            None,
            None,
            None,
            [1001],
            None,
        ]
        request = SimpleNamespace(spell_id=4850, caster_id=actor.id)
        outer_invocation = SimpleNamespace(
            reference=254694,
            caster_id=actor.id,
            target_id=actor.id,
            state_uid=90001,
            native_trigger_context=None,
            native_turn_boundary_context=boundary,
        )
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        with owned_turn_recipient_scope(fight, boundary):
            captured = failure.prepare_triggered(
                fight, request, self.effect, outer_invocation, effects=self.effects
            )

        effect = dict(
            effect_class=28,
            parameter_count=0,
            parameters=[],
            target_masks=[[] for _ in range(7)],
        )
        native_invocation = combat_effect_dispatch.EffectInvocation(
            153978, 20, actor.id, actor.id, actor.position, state_uid=90001
        )
        kill(effect, {}, native_invocation)
        self.assertTrue(any(event["kind"] == "death" for event in fight.events))
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        self.assertTrue(registered_ordinary_death(fight, actor))
        self.assertEqual(actor.hp, 0)
        self.assertTrue(failure.settle_triggered(fight, captured))
        terminal = [event for event in fight.events if event["kind"] == "finished"]
        self.assertEqual(len(terminal), 1)
        self.assertEqual((fight.winner, terminal[0]["winner"]), (1, 1))
        self.assertNotIn("native_original_winner", terminal[0])
        self.assertTrue(failure.settle_triggered(fight, captured) is False)

        # The ordinary achievement consumer rejects the losing controlled
        # participant after this same terminal event has been adjudicated.
        from wakfu_server.achievements import service

        class ParticipantDB:
            def execute(self, query, params):
                class Result:
                    def fetchone(self):
                        return {"team": 0, "status": "finished", "fight_kind": "pve"}

                return Result()

        with self.assertRaisesRegex(ValueError, "durable winning participant"):
            service._event(
                ParticipantDB(),
                {"id": 7, "account_id": 10, "map_id": 777},
                fight,
                [],
            )

    def test_unrelated_self_kill_spell_and_ordinary_fight_keep_normal_winner(self):
        unrelated = SimpleNamespace(spell_id=1041, caster_id=self.actor_id)
        self.assertIsNone(
            failure.prepare_triggered(
                self.fight,
                unrelated,
                self.effect,
                self.invocation,
                effects=self.effects,
            )
        )
        self.fight.phase = "finished"
        self.fight.winner = 0
        self.fight.sequence += 1
        self.fight.events.append(
            {"kind": "finished", "sequence": self.fight.sequence, "winner": 0}
        )
        self.assertFalse(failure.settle_triggered(self.fight, None))
        self.assertEqual(self.fight.winner, 0)
        self.assertNotIn("native_triggered_failure_receipt", vars(self.fight))

        ordinary = SimpleNamespace(
            phase="active", actors={}, native_encounter_scene=None
        )
        self.assertIsNone(
            failure.prepare_triggered(
                ordinary,
                self.request,
                self.effect,
                self.invocation,
                effects=self.effects,
            )
        )

    def test_wrong_actor_state_or_source_lineage_fails_closed(self):
        bad = deepcopy(self.fight)
        bad.native_npc_initialization_receipts = {}
        with self.assertRaisesRegex(ValueError, "original callback actor"):
            failure.prepare_triggered(
                bad, self.request, self.effect, self.invocation, effects=self.effects
            )

        self.actor.state_ledger.entries[0] = SimpleNamespace(
            uid=90001,
            reference=9999,
            caster_id=self.actor_id,
            target_id=self.actor_id,
            effect_ids=(153978,),
        )
        with self.assertRaisesRegex(ValueError, "owned state lineage"):
            failure.prepare_triggered(
                self.fight,
                self.request,
                self.effect,
                self.invocation,
                effects=self.effects,
            )

        self.actor.state_ledger.entries[0] = SimpleNamespace(
            uid=90001,
            reference=3478,
            caster_id=self.actor_id,
            target_id=self.actor_id,
            effect_ids=(153978,),
        )
        wrong_owner = deepcopy(self.invocation)
        wrong_owner.native_trigger_context = dict(
            self.invocation.native_trigger_context, manager_actor_id=123
        )
        with self.assertRaisesRegex(ValueError, "original callback actor"):
            failure.prepare_triggered(
                self.fight,
                self.request,
                self.effect,
                wrong_owner,
                effects=self.effects,
            )

    def test_nested_execution_failure_cannot_commit_a_terminal_outcome(self):
        captured = failure.prepare_triggered(
            self.fight,
            self.request,
            self.effect,
            self.invocation,
            effects=self.effects,
        )

        # The runtime calls settle_triggered only after nested execution and
        # its buffered packets return. A thrown nested error leaves the source
        # fight and its event journal untouched.
        def nested_execution_then_settlement():
            try:
                raise RuntimeError("native nested failure")
            except RuntimeError:
                raise
            else:
                failure.settle_triggered(self.fight, captured)

        with self.assertRaisesRegex(RuntimeError, "native nested failure"):
            nested_execution_then_settlement()
        self.assertEqual(self.fight.phase, "active")
        self.assertIsNone(self.fight.winner)
        self.assertEqual(self.fight.events, [])
        self.assertNotIn("native_triggered_failure_receipt", vars(self.fight))


if __name__ == "__main__":
    unittest.main()
