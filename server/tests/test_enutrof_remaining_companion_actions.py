"""Real two-owner Drheller actions preserve unrelated actors and owned areas."""
import math
import os
import random
import struct
import unittest
from unittest.mock import patch

import test_combat_aptitude_healing_runtime as allied
from tools.combat_audit_turns import advance_actual_turn
from wakfu_server import equipment_stats
from wakfu_server.combat_hp_raw import set_hp_raw_current
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EnutrofRemainingCompanionActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allied.AptitudeHealingRuntimeTests.setUpClass()

    def fixture(self):
        original = equipment_stats.effective_character

        def source(character, *args, **kwargs):
            if character["id"] == 8:
                from wakfu_server.health import maximum

                character = dict(character, breed=3, hp=maximum(3, character["level"]))
            return original(character, *args, **kwargs)

        with patch.object(equipment_stats, "effective_character", source):
            (
                fight,
                characters,
                monster,
                decks,
            ) = allied.AptitudeHealingRuntimeTests().fixture(
                active_spells=(),
                caster_breed=3,
                caster_aptitudes=(),
                injury=0,
                level=200,
                compact_arena=False,
                enemy_position=(-10, -8, -1),
            )
        # The allied helper supplies Ready initialization but not the opening
        # owner's1001 boundary. Real mines are1001 subscribers; execute it
        # before ending that owner's first turn, as World does.
        fight, _ = prepare_server_turn_start(
            characters[7],
            {-7: monster},
            fight,
            decks[7],
            actor_id=fight.current.id,
            action_id=10,
            rng=random.Random(17),
            area_callbacks=True,
            player_characters=characters,
            deck_blobs=decks,
        )
        return fight, characters, monster, decks

    def reach(self, fight, characters, monster, decks, identity, rng):
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                characters[7], {-7: monster}, preview, decks[7], **common, **boundary
            ),
            turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                characters[7],
                {-7: monster},
                preview,
                decks[7],
                area_callbacks=True,
                **common,
                **boundary
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )
        for _ in range(40):
            if fight.current.id == identity:
                return
            advance_actual_turn(runtime)
        self.fail("Actual companion turn did not arrive")

    def test_remaining_three_actions_have_actual_consequences_and_owner_isolation(self):
        from tools.class_spell_eligible_targets import eligible_cast_targets

        for reference in (2058, 2077, 3542):
            with self.subTest(action=reference):
                fight, characters, monster, decks = self.fixture()
                companions = {
                    actor.native_summon_source["controller_id"]: actor
                    for actor in fight.actors.values()
                    if getattr(actor, "native_summon_source", None)
                }
                self.assertTrue({7, 8} <= set(companions), companions)
                companion = companions[7]
                rng = random.Random(17)
                self.reach(fight, characters, monster, decks, companion.id, rng)
                if reference == 2077:
                    set_hp_raw_current(companion, companion.max_hp // 2)
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)

                def los(origin, target, current):
                    return authoritative_visible(
                        characters[7]["map_id"],
                        origin,
                        target,
                        current,
                        blocking_footprints={
                            a.id: {a.position[:2]}
                            for a in current.actors.values()
                            if a.hp > 0
                        },
                    )

                _, adapter = server_runtime(
                    characters[7],
                    {-7: monster},
                    decks[7],
                    action_id=40,
                    critical=False,
                    **common
                )
                if reference == 2077:
                    # Opening1001 may already leave a bag on every initial
                    # mine. Create a real fresh ore through3541 so2077's
                    # positive bag branch is not excluded by an existing bag.
                    ore_targets = eligible_cast_targets(
                        fight,
                        characters[7],
                        decks[7],
                        3541,
                        actor_id=companion.id,
                        adapter=adapter,
                        line_of_sight=los,
                        maximum_eligible=16,
                        limit=256,
                    )
                    occupied = {a.position for a in fight.actors.values() if a.hp > 0}
                    area_cells = {
                        tuple(row["cell"]) for row in fight.native_effect_areas.values()
                    }
                    fresh_cells = [
                        row["target"]
                        for row in ore_targets["eligible"]
                        if tuple(row["target"]) not in occupied | area_cells
                    ]
                    self.assertTrue(fresh_cells, ore_targets)
                    fresh_cell = tuple(fresh_cells[0])
                    prepared = prepare_server_spell(
                        struct.pack(">qqiih", companion.id, 3541, *fresh_cell),
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=30,
                        line_of_sight=los,
                        critical=False,
                        **common
                    )
                    fight = prepared.fight
                    companion = fight.actors[companion.id]
                    self.assertTrue(
                        any(
                            row["reference"] == 203
                            and row.get("owner_id") == 7
                            and tuple(row["cell"]) == fresh_cell
                            for row in fight.native_effect_areas.values()
                        )
                    )
                    self.assertFalse(
                        any(
                            row["reference"] in (207, 209)
                            and tuple(row["cell"]) == fresh_cell
                            for row in fight.native_effect_areas.values()
                        )
                    )
                selection = eligible_cast_targets(
                    fight,
                    characters[7],
                    decks[7],
                    reference,
                    actor_id=companion.id,
                    adapter=adapter,
                    line_of_sight=los,
                    maximum_eligible=16,
                    limit=256,
                )
                target_id = -7 if reference == 2058 else companion.id
                target = fight.actors[target_id]
                if reference == 2077:
                    choices = [
                        row
                        for row in selection["eligible"]
                        if tuple(row["target"]) == fresh_cell
                    ]
                else:
                    choices = [
                        row
                        for row in selection["eligible"]
                        if tuple(row["target"]) == target.position
                    ]
                self.assertTrue(
                    choices, dict(selection=selection, target=target.position)
                )
                before = snapshot(fight)
                foreign = {
                    uid: dict(row)
                    for uid, row in fight.native_effect_areas.items()
                    if row.get("owner_id") == 8
                }
                self.assertTrue(foreign, "Second real Enutrof must own actual deposits")
                resources = (companion.ap, companion.mp, companion.effect_stats[4])
                hp, armor, position = (
                    target.hp,
                    target.effect_stats[97],
                    target.position,
                )
                from wakfu_server.combat_effect_dispatch import EffectDispatcher

                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, *args, **kwargs):
                    value = execute(dispatcher, invocation, *args, **kwargs)
                    if reference == 2077:
                        trace.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                invocation.cell,
                                value,
                            )
                        )
                    return value

                with patch.object(EffectDispatcher, "execute", observe):
                    tx = prepare_server_spell(
                        struct.pack(
                            ">qqiih", companion.id, reference, *choices[0]["target"]
                        ),
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=40,
                        line_of_sight=los,
                        critical=False,
                        **common
                    )
                self.assertEqual(snapshot(fight), before)
                actor, result = (
                    tx.fight.actors[companion.id],
                    tx.fight.actors[target_id],
                )
                for value, actual, key in zip(
                    resources,
                    (actor.ap, actor.mp, actor.effect_stats[4]),
                    ("ap", "mp", "wp"),
                ):
                    self.assertEqual(value - actual, tx.plan["costs"][key])
                for uid, row in foreign.items():
                    self.assertEqual(tx.fight.native_effect_areas.get(uid), row)
                for identity in (7, 8, companions[8].id, 9):
                    self.assertEqual(
                        tx.fight.actors[identity].hp, fight.actors[identity].hp
                    )
                    self.assertEqual(
                        tx.fight.actors[identity].position,
                        fight.actors[identity].position,
                    )
                    self.assertEqual(
                        tx.fight.actors[identity].effect_stats[97],
                        fight.actors[identity].effect_stats[97],
                    )
                if reference == 2058:
                    self.assertEqual(
                        sum(abs(result.position[i] - position[i]) for i in (0, 1)), 2
                    )
                    self.assertEqual(result.hp, hp)
                elif reference == 2077:
                    # Native385425 uses25% of the source maximum HP (far1),
                    # with stochastic rounding and receiver coefficients.
                    self.assertEqual(target.effect_stats[32], 0)
                    self.assertIn(
                        result.hp - hp,
                        {
                            math.floor(companion.max_hp / 4),
                            math.ceil(companion.max_hp / 4),
                        },
                    )
                    clicked_cell = tuple(choices[0]["target"])
                    selected_mines = {
                        uid
                        for uid, row in fight.native_effect_areas.items()
                        if row.get("owner_id") == 7
                        and row["reference"] in (202, 203, 204, 205)
                        and tuple(row["cell"]) == clicked_cell
                    }
                    self.assertTrue(selected_mines)
                    self.assertTrue(
                        selected_mines.isdisjoint(tx.fight.native_effect_areas)
                    )
                    new_bags = [
                        row
                        for uid, row in tx.fight.native_effect_areas.items()
                        if uid not in fight.native_effect_areas
                        and row["reference"] == 207
                        and row.get("owner_id") == 7
                        and tuple(row["cell"]) == clicked_cell
                    ]
                    self.assertEqual(
                        len(new_bags),
                        1,
                        dict(
                            clicked_cell=clicked_cell,
                            trace=trace,
                            before_areas=fight.native_effect_areas,
                            after_areas=tx.fight.native_effect_areas,
                        ),
                    )
                else:
                    # Native386172 maximum HP+virtual ×0.25, nearest integer;
                    # child386173 armor base equals that derived level.
                    self.assertEqual(companion.effect_stats.get(120, 0), 0)
                    self.assertEqual(target.effect_stats.get(121, 0), 0)
                    expected = math.floor(
                        (target.max_hp + target.effect_maxima[92]) / 4 + 0.5
                    )
                    self.assertEqual(result.effect_stats[97] - armor, expected)
                    self.assertEqual(result.hp, hp)
