"""Dispatcher-level coverage for the explicit compact-arena range glyph."""
import json
import unittest
from dataclasses import replace

from wakfu_server.combat_battleground_border import POLICY as BORDER_POLICY
from wakfu_server.combat_effect_area_catalog import area_effect_catalog
from wakfu_server.combat_environment_glyphs import (
    environment_sections,
    prepare_environment_glyphs,
)
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_retained_runtime import native_retained_condition_effects
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.fight_checkpoint_store import (
    _plain as checkpoint_plain,
    snapshot as checkpoint_snapshot,
)


class EnvironmentGlyphRuntimeTests(unittest.TestCase):
    def test_range_glyph_entry_repeat_exit_and_checkpoint_myK(self):
        # Import locally so unittest does not also collect the large runtime
        # fixture's unrelated catalog tests as members of this module.
        from test_combat_effect_runtime import NativeRuntimeFactoryTests

        NativeRuntimeFactoryTests.setUpClass()
        fixture = NativeRuntimeFactoryTests()
        fixture.setUp()
        fight = fixture.fight
        actor = fight.actors[7]
        fight.actors = {actor.id: actor}
        fight.order = [actor.id]
        fight.walkable = {(x, y, 0) for x in range(5) for y in range(5)}
        actor.position = (1, 1, 0)
        actor.effect_stats[11] = 0
        actor.effect_minima[11] = -100
        actor.effect_maxima[11] = 100
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=5, height=5, cell_masks=[0] * 25
        )
        initialize_global_pv_collections(fight, (actor.id,))

        border_cells = {
            cell for cell in fight.walkable if cell[0] in (0, 4) or cell[1] in (0, 4)
        }
        arena = dict(
            native_border_policy=BORDER_POLICY,
            native_border_cells=border_cells,
        )
        prepare_environment_glyphs(fight, arena, -100)
        (before_entry_myK,) = environment_sections(fight)
        glyph = fight.native_environment_glyph_constructors[0]
        glyph_cell = tuple(glyph["cell"])

        effects = dict(fixture.effects)
        effects.update(area_effect_catalog()["effects"])

        def condition(preview, plan, effect, invocation):
            target = preview.actors[invocation.target_id]
            retained = native_retained_condition_effects(preview, invocation.target_id)
            return ConditionContext(
                {
                    "caster": ConditionActor(
                        actor_id=invocation.caster_id,
                        is_native_fighter=False,
                        is_character=False,
                    ),
                    "target": ConditionActor(
                        actor_id=target.id,
                        is_player=True,
                        is_character=True,
                        characteristics={"RANGE": target.effect_stats[11]},
                        retained_effect_ids=frozenset(row[0] for row in retained),
                    ),
                }
            )

        contexts = replace(fixture.contexts, condition=condition)
        factory = NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog=fixture.states,
            characteristic_registry=fixture.registry,
            action_id=1,
            contexts=contexts,
        )
        dispatcher, packets = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        events = dispatcher.native_area_events
        row = fight.native_effect_areas[glyph["uid"]]
        self.assertEqual(row["reference"], 910)
        self.assertEqual(row["cell"], glyph_cell)
        self.assertEqual(actor.effect_stats[11], 0)

        actor.position = glyph_cell
        with fight.effect_resolution():
            self.assertEqual(
                events.event(10001, actor.id, from_cell=(1, 1, 0), to_cell=glyph_cell),
                (True,),
            )
        self.assertEqual(actor.effect_stats[11], 4)
        applied = native_retained_condition_effects(fight, actor.id)
        self.assertIn(152453, {record[0] for record in applied})
        self.assertTrue(row["child_effect_uids"]["7"])
        child_uids = tuple(row["child_effect_uids"]["7"])
        self.assertEqual(len(child_uids), len(set(child_uids)))

        try:
            checkpoint = checkpoint_snapshot(fight)
        except ValueError:
            nonportable = []
            for name, value in actor.__dict__.items():
                try:
                    checkpoint_plain(value)
                except ValueError:
                    nonportable.append((name, type(value).__qualname__))
            self.fail(f"fixture actor has non-checkpoint fields: {nonportable}")
        roundtripped = json.loads(json.dumps(checkpoint))
        self.assertEqual(
            roundtripped["native_environment_glyph_constructors"],
            checkpoint["native_environment_glyph_constructors"],
        )
        self.assertEqual(
            environment_sections(fight),
            [before_entry_myK],
            "the existing faY snapshot remains the same myK section after activation",
        )
        restored = type("RestoredFightView", (), {})()
        restored.native_environment_glyph_constructors = roundtripped[
            "native_environment_glyph_constructors"
        ]
        restored.native_environment_glyphs_installed = roundtripped[
            "native_environment_glyphs_installed"
        ]
        restored.native_effect_areas = {
            int(identity): row
            for identity, row in roundtripped["native_effect_areas"].items()
        }
        restored.walkable = {tuple(cell) for cell in roundtripped["walkable"]}
        restored.native_border_cells = border_cells
        self.assertEqual(environment_sections(restored), [before_entry_myK])

        entry_packet_count = len(packets)
        with fight.effect_resolution():
            events.event(10000, actor.id)
        self.assertEqual(actor.effect_stats[11], 4)
        self.assertEqual(tuple(row["child_effect_uids"]["7"]), child_uids)
        self.assertEqual(len(packets), entry_packet_count)

        with fight.effect_resolution():
            self.assertEqual(
                events.event(10002, actor.id, from_cell=glyph_cell, to_cell=(3, 3, 0)),
                (True,),
            )
        self.assertEqual(actor.effect_stats[11], 0)
        self.assertNotIn(
            152453,
            {
                record[0]
                for record in native_retained_condition_effects(fight, actor.id)
            },
        )
        self.assertEqual(row["child_effect_uids"].get("7", []), [])
        self.assertEqual(environment_sections(fight), [before_entry_myK])


if __name__ == "__main__":
    unittest.main()
