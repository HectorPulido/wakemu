"""Read-only attribution of bounded scene prerequisites; no bypasses."""
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class FulMoonTalKashaComponentDiagnostics(unittest.TestCase):
    def test_record_original_fulmoon_initial_selector_ownership(self):
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )
        from wakfu_server import combat_effect_resolver

        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_summon_initialization import detached_actor

        rows, invocations = [], []
        execute = EffectDispatcher.execute

        def observe_invocation(dispatcher, invocation, **kwargs):
            if invocation.reference in (178024, 178404, 178405, 178026, 178036):
                current = dispatcher.native_retention.fight
                caster = current.actors.get(invocation.caster_id) or detached_actor(
                    current, invocation.caster_id
                )
                invocations.append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        caster_team=None if caster is None else caster.team,
                        cell=invocation.cell,
                        boss_states=[
                            (entry.reference, entry.level)
                            for entry in current.actors[-200].state_ledger.entries
                        ],
                    )
                )
            return execute(dispatcher, invocation, **kwargs)

        original = combat_effect_resolver.select_native_effect_targets

        def observe(effect, caster, center, actors, **kwargs):
            actors = tuple(actors)
            result = original(effect, caster, center, actors, **kwargs)
            mask = (effect.get("native_target_selector") or {}).get("mask")
            if mask == 140737488355332:
                rows.append(
                    dict(
                        mask=mask,
                        criterion=effect.get("criteria"),
                        caster=dict(
                            id=caster.id, team=caster.team, position=caster.position
                        ),
                        candidates=[
                            dict(id=actor.id, team=actor.team) for actor in actors
                        ],
                        selected=[actor.id for actor in result],
                    )
                )
            return result

        helper = FulMoonTalKashaNativeBootstrapTests()
        with patch.object(
            combat_effect_resolver, "select_native_effect_targets", observe
        ), patch.object(EffectDispatcher, "execute", observe_invocation):
            fight, scene, children = helper._started(
                3870, 185, 1056, reconstructed_fulmoon_scene
            )
        receipt = dict(
            scope="readonly_original_constructor_target_selection",
            state_or_resource_grants=False,
            selectors=rows,
            invocations=invocations,
            actors={
                str(actor.id): dict(
                    team=actor.team,
                    states=[
                        (entry.reference, entry.level)
                        for entry in actor.state_ledger.entries
                    ],
                )
                for actor in fight.actors.values()
            },
            children=children,
        )
        (
            ROOT
            / ".runtime/ultimate-scenes-20261021/fulmoon-constructor-selector-diagnostic.json"
        ).write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.assertTrue(rows, receipt)

    def test_record_original_talkasha_first_end_damage_attribution(self):
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from native_supreme_scene_turn_runtime import native_scene_turn_runtime
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        helper = FulMoonTalKashaNativeBootstrapTests()
        fight, scene, children = helper._started(
            5500, 155, 1400, reconstructed_talkasha_scene
        )
        character, monsters, deck = helper.encounter_context
        runtime, stats = native_scene_turn_runtime(
            fight, character, monsters, deck, map_id=1400, rng=Random(0)
        )
        rows = []
        original = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            current = dispatcher.native_retention.fight
            player = current.actors.get(7)
            hp = None if player is None else player.hp
            ancestors = list(
                kwargs.get("ancestors") or getattr(dispatcher, "_active_ancestors", ())
            )
            result = original(dispatcher, invocation, **kwargs)
            player = current.actors.get(7)
            after = None if player is None else player.hp
            if hp is not None and after is not None and after < hp:
                effect = dispatcher.effects[str(invocation.reference)]
                rows.append(
                    dict(
                        reference=invocation.reference,
                        family=effect["effect_class"],
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        hp_before=hp,
                        hp_after=after,
                        ancestors=ancestors,
                    )
                )
            return result

        before = dict(wp=fight.actors[-200].effect_stats[4], hp=fight.actors[7].hp)
        with patch.object(EffectDispatcher, "execute", observe):
            runtime.turn_started()
            advance_actual_turn(runtime)
        current = runtime.fight
        receipt = dict(
            scope="readonly_original_first_end_attribution",
            isolated_effects=[],
            state_or_resource_grants=False,
            before=before,
            after=dict(
                wp=current.actors[-200].effect_stats[4],
                hp=current.actors[7].hp,
                phase=current.phase,
            ),
            damage=rows,
        )
        (
            ROOT
            / ".runtime/ultimate-scenes-20261021/talkasha-first-end-damage-diagnostic.json"
        ).write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.assertTrue(rows, receipt)
