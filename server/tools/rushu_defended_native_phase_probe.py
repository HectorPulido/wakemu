"""Real Rushu phase boundaries with a legally constructed defensive owner."""
from pathlib import Path
from datetime import datetime, timezone
from random import Random
import json
import struct
import unittest
from unittest.mock import patch


class RushuDefendedNativePhaseTests(unittest.TestCase):
    def test_defended_owner_reaches_native_phase_and_actual_growl_producer(self):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from test_ultimate_encounter_scene_recipes import (
            UltimateEncounterSceneRecipeTests,
        )
        from ultimate_encounter_scene_recipes import encounter_fixture_factory
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_effective_control import effective_server_controlled
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.fight_checkpoint_store import snapshot

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/ultimate-scenes-20261021"
            / ("rushu-defended-owner-phase-" + stamp + ".json")
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        receipt = dict(
            status="pending",
            boundaries=[],
            callbacks=[],
            events=[],
            defense=[],
            acknowledgements=[],
        )
        selected = {324322, 324427, 324430, 319077, 319078, 319079, 319183, 323843}
        execute = EffectDispatcher.execute
        replay = NativeEventReplay.__call__

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in selected:
                receipt["callbacks"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        level=invocation.level,
                        result=result,
                        turn_id=dispatcher.native_retention.fight.turn_id,
                    )
                )
            return result

        def observe_event(dispatcher, event, **kwargs):
            result = replay(dispatcher, event, **kwargs)
            if 1037 in event.event_ids or 2243 in event.event_ids:
                receipt["events"].append(
                    dict(
                        manager=event.manager_actor_id,
                        event_ids=event.event_ids,
                        outcomes=list(result),
                        turn_id=dispatcher.retention.fight.turn_id,
                    )
                )
            return result

        try:
            scene = UltimateEncounterSceneRecipeTests().scene(5306)
            tank, facts = native_tank_fixture(validator, feca=True)
            fixture, preparation = encounter_fixture_factory(
                validator,
                scene,
                player_level=200,
                player_breed=1,
                player_deck=[6972],
                character_constructor=tank.__globals__["_healthy_owned_character"],
            )
            receipt.update(scene=preparation, player_fixture=facts)
            with original_bootstrap_publication():
                fight, character, monsters, deck = fixture(
                    5306,
                    scene["level"],
                    scene["anchor"],
                    native_lifecycle=True,
                )
            self.assertEqual((fight.actors[7].hp, fight.actors[7].max_hp), (6150, 6150))
            self.assertEqual(character["breed"], 1)
            self.assertEqual(character["map_id"], 1332)
            self.assertEqual(fight.actors[7].team, 0)
            self.assertEqual(fight.actors[-200].team, 1)
            self.assertIn(
                7000, {e.reference for e in fight.actors[-200].state_ledger.entries}
            )
            self.assertTrue(fight.walkable <= scene["cells"])
            rng = Random(0)

            def stats(actor, current):
                if getattr(actor, "native_summon_source", None) is not None:
                    return registered_summon_stats(actor, current, 1332)
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
                    character,
                    monsters,
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            with patch.object(EffectDispatcher, "execute", observe), patch.object(
                NativeEventReplay,
                "__call__",
                observe_event,
            ):
                runtime.turn_started()
                for _boundary in range(64):
                    for _ack in range(32):
                        if runtime.awaiting_ack is None:
                            break
                        barrier = runtime.awaiting_ack
                        runtime.acknowledge_turn(struct.pack(">i", barrier))
                        receipt["acknowledgements"].append(barrier)
                    else:
                        self.fail("Native Rushu ACK chain exceeded32 barriers")
                    current = runtime.fight
                    receipt["boundaries"].append(
                        dict(
                            turn_id=current.turn_id,
                            table_turn=getattr(current, "native_table_turn", None),
                            phase=current.phase,
                            current_id=None
                            if current.current is None
                            else current.current.id,
                            actors={
                                str(actor.id): dict(
                                    hp=actor.hp,
                                    max_hp=actor.max_hp,
                                    team=actor.team,
                                    position=actor.position,
                                    resources={
                                        str(key): actor.effect_stats[key]
                                        for key in (2, 3, 4)
                                    },
                                    states=[
                                        (entry.reference, entry.level)
                                        for entry in actor.state_ledger.entries
                                    ],
                                    grants=list(granted_spells(current, actor.id)),
                                )
                                for actor in current.actors.values()
                            },
                            areas=[
                                dict(reference=row["reference"], cell=row["cell"])
                                for row in current.native_effect_areas.values()
                            ],
                        )
                    )
                    positive = any(
                        row["reference"] == 323843
                        and row["caster"] == 7
                        and row["result"]
                        for row in receipt["callbacks"]
                    )
                    if positive:
                        break
                    if current.phase != "active" or current.current is None:
                        break
                    if getattr(current, "native_table_turn", 1) >= 11:
                        break
                    actor = current.current
                    if (
                        actor.id == 7
                        and not any(
                            entry.reference == 6364
                            for entry in actor.state_ledger.entries
                        )
                        and 7009 in granted_spells(current, actor.id)
                        and actor.ap >= 2
                        and actor.effect_stats[4] >= 1
                    ):
                        before = snapshot(current)
                        tx = prepare_server_spell(
                            struct.pack(">qqiih", actor.id, 7009, *actor.position),
                            character,
                            monsters,
                            current,
                            actor.owner_id,
                            deck,
                            action_id=runtime.action_id + 1,
                            line_of_sight=lambda origin, target, state: authoritative_visible(
                                1332,
                                origin,
                                target,
                                state,
                                blocking_footprints={
                                    a.id: footprint(a.position, a.physical_radius)
                                    for a in state.actors.values()
                                    if a.hp > 0
                                },
                            ),
                            critical=False,
                            rng=rng,
                        )
                        self.assertEqual(snapshot(current), before)
                        self.assertEqual(
                            (tx.plan["costs"]["ap"], tx.plan["costs"]["wp"]), (2, 1)
                        )
                        commit_spell_transaction(runtime, tx, stats_serializer=stats)
                        receipt["defense"].append(
                            dict(turn_id=runtime.fight.turn_id, costs=tx.plan["costs"])
                        )
                        current = runtime.fight
                        actor = current.current
                    if effective_server_controlled(current, actor):
                        runtime.end_server_turn(actor.id, current.turn_id)
                    else:
                        runtime.end_turn(
                            actor.owner_id, actor.id, current_wire_turn(current)
                        )
            self.assertTrue(receipt["defense"])
            self.assertTrue(any(1037 in row["event_ids"] for row in receipt["events"]))
            self.assertTrue(
                any(
                    row["reference"] == 319078 and row["caster"] == 7 and row["result"]
                    for row in receipt["callbacks"]
                ),
                receipt["boundaries"][-1],
            )
            self.assertTrue(
                any(
                    row["reference"] == 323843 and row["caster"] == 7 and row["result"]
                    for row in receipt["callbacks"]
                ),
                receipt["callbacks"],
            )
            receipt["status"] = "actual_owner_phase_growl_and_1688_observed"
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")


if __name__ == "__main__":
    unittest.main()
