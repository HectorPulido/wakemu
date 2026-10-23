"""Final publication must follow NPC19's real native1001 delivery."""
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class OgrestFinalPublicationOrderTests(unittest.TestCase):
    def test_sixth_completion_precedes_1001_and_original_final_follows_it(self):
        from wakfu_server import combat_ogrest_phase_controller as policy
        from wakfu_server.combat_server_spell import prepare_server_turn_start

        boss = SimpleNamespace(id=-200, team=2)
        context = dict(
            policy=policy.POLICY,
            boss_id=-200,
            delivered_tables=list(range(1, 19)),
            phase_order=list(policy.PHASE_STATES),
            current_phase=4985,
            transitions=[],
            final_entered=False,
        )
        fight = SimpleNamespace(
            phase="active",
            current=boss,
            actors={-200: boss},
            native_timeline_round=19,
            native_ogrest_phase_context=context,
            native_effect_areas={
                60: dict(
                    uid=60,
                    reference=1254,
                    owner_id=-200,
                    cell=(0, -30, 40),
                    native_area_contract="faY",
                    native_qq_guard_source="Qq.constructor",
                )
            },
            effect_resolution=nullcontext,
        )
        trace, levels = [], {4985: 1, 5008: 2}

        def source(dispatcher, selected, reference):
            trace.append(reference)
            if reference == 235865:
                levels.pop(4985)
                levels[5008] = 3
            elif reference == 235828:
                self.assertIn("owned1001", trace)
                levels[5020] = 1
                areas = dispatcher.native_retention.fight.native_effect_areas
                areas[90] = dict(
                    uid=90,
                    reference=1255,
                    owner_id=60,
                    effect_reference=238861,
                    cell=(-2, -27, 40),
                    native_area_contract="faY",
                    native_qq_guard_source="Qq.constructor",
                )
                del areas[60]  # Original parent may be removed by the sibling302.
            else:
                self.fail("Unexpected original producer")
            return True

        def factory(preview, unused):
            return SimpleNamespace(native_retention=SimpleNamespace(fight=preview)), []

        def turn_start(dispatcher, *, actor_id):
            self.assertEqual(actor_id, -200)
            self.assertNotIn(5020, levels)
            self.assertEqual(levels[5008], 3)
            self.assertFalse(
                dispatcher.native_retention.fight.native_ogrest_phase_context[
                    "final_entered"
                ]
            )
            trace.append("owned1001")

        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(factory, None),
        ), patch(
            "wakfu_server.combat_periodic_aptitude.renew_periodic_aptitudes"
        ), patch(
            "wakfu_server.combat_npc_phase_controller.deliver_npc_score_result"
        ), patch(
            "wakfu_server.combat_npc_phase_controller.deliver_npc_table_phase",
            side_effect=policy.deliver_ogrest_table_phase,
        ), patch(
            "wakfu_server.combat_turn_events.deliver_turn_start", side_effect=turn_start
        ), patch.object(
            policy, "_verify_active_phase", return_value=4985
        ), patch.object(
            policy, "_state_level", side_effect=lambda actor, ref: levels.get(ref)
        ), patch.object(
            policy, "_execute_original", side_effect=source
        ), patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=object(),
        ), patch.object(
            policy, "_publish_phase", return_value=()
        ):
            result, packets = prepare_server_turn_start(
                {}, {}, fight, b"", actor_id=-200, action_id=1
            )
            self.assertEqual(trace, [235865, "owned1001", 235828])
            final = result.native_ogrest_phase_context
            self.assertTrue(final["final_entered"])
            self.assertNotIn("pending_final", final)
            self.assertEqual(
                final["transitions"], [dict(table=19, completed=4985, entered=None)]
            )
            self.assertEqual(
                policy.deliver_ogrest_post_turn_start(
                    factory(result, None)[0], actor_id=-200
                ),
                (),
            )
            self.assertEqual(trace.count(235828), 1)
            self.assertNotIn(60, result.native_effect_areas)
            self.assertEqual(policy.ogrest_exit_areas(result)[0]["owner_id"], 60)
            actor = SimpleNamespace(
                id=1, owner_id=1, position=(-2, -27, 40), controlled=True, team=1
            )
            result.actors[1], result.current = actor, actor
            result.boss_score_profile = dict(
                encounter_controller=policy.POLICY, player_ids=(1,)
            )
            result._in_play = lambda selected: True
            result._event = lambda *args, **kwargs: None
            with patch(
                "wakfu_server.maps.boss_score_runtime.staged_score", return_value=0
            ):
                result.native_effect_areas[90]["owner_id"] = -200
                with self.assertRaisesRegex(ValueError, "creator lineage"):
                    policy.finish_ogrest_player_turn(
                        factory(result, None)[0], actor_id=1
                    )
                result.native_effect_areas[90]["owner_id"] = 60
                self.assertTrue(
                    policy.finish_ogrest_player_turn(
                        factory(result, None)[0], actor_id=1
                    )
                )
                self.assertEqual(
                    policy.ogrest_terminal_authority(result)["area_uid"], 90
                )
                result.native_effect_areas[90]["effect_reference"] = 1
                with self.assertRaisesRegex(ValueError, "creator lineage"):
                    policy.ogrest_terminal_authority(result)
