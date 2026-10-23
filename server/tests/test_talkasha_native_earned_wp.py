"""Paid native boss movement earns Tal Kasha's guarded internal ultimate component."""
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch


class TalKashaEarnedWpTests(unittest.TestCase):
    def test_paid_native_movement_earns_twenty_wp_and_triggers_original_8147(self):
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from native_supreme_component_scope import (
            isolate_talkasha_pyramid_opening_damage,
        )
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_movement_runtime import apply_ai, _with_areas
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_ai import (
            snapshot as ai_snapshot,
            validate as ai_validate,
        )
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_triggered_spell_handler import (
            NativeTriggeredSpellHandler,
        )

        helper = FulMoonTalKashaNativeBootstrapTests()
        fight, scene, children = helper._started(
            5500, 155, 1400, reconstructed_talkasha_scene
        )
        character, monsters, deck = helper.encounter_context
        rng = Random(0)
        receipt = dict(
            scope="paid_native_movement_component_with_validated_ai_decision_input",
            original_1005_publisher="unrecovered",
            movement_payments=[],
            full_encounter_victory=False,
            injected_states_or_resources=False,
            source=scene["source"],
            samples=[],
            ultimate=[],
            isolated_effects=[],
        )

        def stats(actor, current):
            if getattr(actor, "native_summon_source", None) is not None:
                return registered_summon_stats(actor, current, 1400)
            values = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=current,
            )
            if actor.controlled:
                return actual_actor_stats(character, actor, current.id, **values)
            return actual_monster_actor_stats(
                monsters[actor.id], actor, current.id, **values
            )

        runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=stats,
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                character,
                monsters,
                p,
                deck,
                rng=rng,
                native_events=True,
                area_callbacks=True,
                **kw
            ),
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                character, monsters, p, deck, rng=rng, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character, monsters, deck, action_id=action_id, critical=False, rng=rng
            )[0],
        )
        original = NativeTriggeredSpellHandler.__call__

        def observe(handler, effect, values, invocation):
            if invocation.reference != 379831:
                return original(handler, effect, values, invocation)
            caster = handler.fight.actors[invocation.caster_id]
            row = dict(
                reference=invocation.reference,
                spell=int(effect["parameters"][0]),
                caster=invocation.caster_id,
                wp_before=caster.effect_stats[4],
            )
            result = original(handler, effect, values, invocation)
            row.update(result=bool(result), wp_after=caster.effect_stats[4])
            receipt["ultimate"].append(row)
            return result

        try:
            with isolate_talkasha_pyramid_opening_damage(
                receipt["isolated_effects"]
            ), patch.object(NativeTriggeredSpellHandler, "__call__", observe):
                runtime.turn_started()
                for boundary in range(32):
                    current = runtime.fight
                    boss = current.actors[-200]
                    receipt["samples"].append(
                        dict(
                            boundary=boundary,
                            table=getattr(current, "native_table_turn", None),
                            current=current.current.id if current.current else None,
                            wp=boss.effect_stats[4],
                            maximum=boss.effect_maxima[4],
                            player_hp=current.actors[7].hp,
                            phase=current.phase,
                        )
                    )
                    if (
                        receipt["ultimate"]
                        or current.phase != "active"
                        or current.current is None
                    ):
                        break
                    if current.current.id == -200 and boss.mp > 0:
                        origin = tuple(boss.position)
                        occupied = {
                            tuple(actor.position)
                            for actor in current.actors.values()
                            if actor.hp > 0 and actor.id != boss.id
                        }
                        steps = sorted(
                            tuple(end)
                            for start, end in current.edges
                            if tuple(start) == origin and tuple(end) not in occupied
                        )
                        self.assertTrue(steps, receipt)
                        destination = steps[0]

                        # This is an ordinary validated planner response input,
                        # not a Qe/event/resource injection or a model-service test.
                        def decide(candidate, actor_id):
                            request = ai_snapshot(candidate, actor_id)
                            response = dict(
                                protocol=1,
                                requestId=request["requestId"],
                                stateKey=request["stateKey"],
                                decision=dict(
                                    actor_id=actor_id,
                                    target_id=7,
                                    path=[list(destination)],
                                    attack=None,
                                ),
                            )
                            return ai_validate(candidate, actor_id, request, response)

                        old_mp, old_wp = boss.mp, boss.effect_stats[4]
                        with patch("wakfu_server.combat_ai.plan", decide):
                            _, decision = _with_areas(
                                runtime,
                                lambda candidate, **kw: prepare_area_movement(
                                    character, monsters, candidate, deck, rng=rng, **kw
                                ),
                                lambda candidate, callback: apply_ai(
                                    candidate,
                                    lambda actor: stats(actor, candidate.fight),
                                    direction=boss.direction,
                                    _step_callback=callback,
                                ),
                            )
                        moved = runtime.fight.actors[-200]
                        receipt["movement_payments"].append(
                            dict(
                                origin=origin,
                                requested_destination=destination,
                                actual_position=moved.position,
                                mp_before=old_mp,
                                mp_after=moved.mp,
                                wp_before=old_wp,
                                wp_after=moved.effect_stats[4],
                                decision=decision,
                            )
                        )
                        self.assertEqual(moved.mp, old_mp - 1)
                        if receipt["ultimate"]:
                            break
                    advance_actual_turn(runtime)
            self.assertTrue(receipt["ultimate"], receipt)
            self.assertTrue(
                any(
                    row["result"] and row["spell"] == 8147 and row["wp_before"] >= 20
                    for row in receipt["ultimate"]
                ),
                receipt,
            )
            self.assertEqual(receipt["samples"][0]["wp"], 0)
            self.assertLess(receipt["ultimate"][0]["wp_after"], 20)
            self.assertTrue(receipt["isolated_effects"], receipt)
            receipt["status"] = "native_earned_ultimate_observed"
        finally:
            output = (
                Path(__file__).resolve().parents[2]
                / ".runtime/ultimate-scenes-20261021/talkasha-earned-native-wp.json"
            )
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
