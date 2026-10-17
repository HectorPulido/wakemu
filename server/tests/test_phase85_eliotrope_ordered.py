"""Two actual owned Eliotropes share their native two-portal passive network."""
import json
import random
import struct
import unittest
from unittest.mock import patch

import xelor_multiowner_fixture as fixtures
from durable_native_fixture import assert_native_enemy
from tools.combat_audit_turns import advance_actual_turn
from tools import class_spell_eligible_targets as targets
from wakfu_server import native_catalog
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.fight_checkpoint_store import snapshot, Checkpoints

REVISION = "08523b7b8f2dd2e7c5fcac816bfcc7e31f777beb61acb0d76913bfcd568007f8"


class EliotropeOrderedUsageTests(unittest.TestCase):
    def test_two_owned_players_share_portals_cap_replace_remove_and_restore(self):
        self.assertEqual(native_catalog.release(), REVISION)
        fight, characters, monster, decks = fixtures.TwoXelorFixture().fixture(
            caster_breed=18,
            second_player_breed=18,
            level=200,
            native_target_ref=4168,
            native_target_level=190,
            active_spells=(4692,),
            second_player_spells=(4692,),
            passive_spells=(7206,),
            second_player_passives=(7206,),
            second_player_position=(-5, -6, -1),
            third_player_position=(-9, -7, -1),
            enemy_position=(-3, -7, -1),
            compact_arena=False,
            initialization_seed=17,
        )
        assert_native_enemy(self, fight, monster)
        rng = random.Random(17)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common,
            )[0],
        )

        def advance(owner):
            for _ in range(24):
                if runtime.fight.current.id == owner:
                    return
                advance_actual_turn(runtime)
            self.fail("Owned Eliotrope did not receive a real turn")

        def los(a, b, state):
            return authoritative_visible(
                1134,
                a,
                b,
                state,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in state.actors.values()
                    if actor.hp > 0
                },
            )

        def portals():
            return {
                uid: row
                for uid, row in runtime.fight.native_effect_areas.items()
                if row["reference"] == 823
            }

        def cast(owner, reference, cell):
            self.assertEqual(runtime.fight.current.id, owner)
            grant = granted_spells(runtime.fight, owner).get(reference)
            uid = grant["uid"] if grant else (owner << 32) | reference
            before, before_rng = snapshot(runtime.fight), rng.getstate()
            try:
                tx = prepare_server_spell(
                    struct.pack(">qqiih", owner, uid, *cell),
                    characters[owner],
                    {-7: monster},
                    runtime.fight,
                    characters[owner]["account_id"],
                    decks[owner],
                    action_id=runtime.action_id + 1,
                    line_of_sight=los,
                    critical=False,
                    **common,
                )
            except Exception:
                self.assertEqual(snapshot(runtime.fight), before)
                self.assertEqual(rng.getstate(), before_rng)
                raise
            self.assertEqual(snapshot(runtime.fight), before)
            self.assertTrue(any(tx.outcomes))
            runtime.fight = tx.fight
            runtime.action_id += 1
            return tx

        def place(owner, near):
            _, adapter = server_runtime(
                characters[owner],
                {-7: monster},
                decks[owner],
                action_id=runtime.action_id + 1,
                critical=False,
                **common,
            )
            occupied = {a.position for a in runtime.fight.actors.values() if a.hp > 0}
            existing = {tuple(row["cell"]) for row in portals().values()}
            candidates, total = targets.candidate_cells(
                runtime.fight, owner, limit=4096
            )
            candidates = tuple(
                sorted(
                    (cell for cell in candidates if cell not in occupied | existing),
                    key=lambda cell: (
                        abs(cell[0] - near[0]) + abs(cell[1] - near[1]),
                        cell,
                    ),
                )
            )
            # Only order the real bounded terrain candidates. Every target still
            # passes the production validator, costs, ownership and native LOS.
            with patch.object(
                targets, "candidate_cells", return_value=(candidates, total)
            ):
                result = targets.eligible_cast_targets(
                    runtime.fight,
                    characters[owner],
                    decks[owner],
                    granted_spells(runtime.fight, owner)[4678]["uid"],
                    adapter=adapter,
                    actor_id=owner,
                    line_of_sight=los,
                    limit=4096,
                    maximum_eligible=1,
                )
            cells = [tuple(row["target"]) for row in result["eligible"]]
            self.assertTrue(cells, result)
            return cast(owner, 4678, cells[0])

        advance(7)
        self.assertEqual(characters[7]["breed"], 18)
        self.assertEqual(characters[8]["breed"], 18)
        target = runtime.fight.actors[-7].position
        self.assertGreater(
            sum(abs(runtime.fight.actors[7].position[i] - target[i]) for i in (0, 1)), 4
        )
        with self.assertRaisesRegex(ValueError, "twI"):
            cast(7, 4692, target)
        place(7, runtime.fight.actors[7].position)
        advance(8)
        place(8, target)
        pair = dict(portals())
        self.assertEqual(len(pair), 2)
        self.assertEqual({row["owner_id"] for row in pair.values()}, {7, 8})

        advance(7)
        before_hp = runtime.fight.actors[-7].hp
        attack = cast(7, 4692, target)
        self.assertEqual(attack.plan["costs"]["ap"], 2)
        self.assertLess(runtime.fight.actors[-7].hp, before_hp)
        self.assertEqual(set(portals()), set(pair))
        # Actual7206 criterion counts the TEAM's native type19 areas. A third
        # placement must replace one even when the existing pair has two owners.
        place(7, target)
        replaced = dict(portals())
        self.assertEqual(len(replaced), 2)
        self.assertEqual(len(set(replaced) - set(pair)), 1)
        self.assertEqual(len(set(pair) - set(replaced)), 1)
        saved = snapshot(runtime.fight)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        for uid, row in replaced.items():
            self.assertEqual(
                restored["native_effect_areas"][str(uid)], json.loads(json.dumps(row))
            )
        # Recast the live portal nearest the current caster; its removal uses
        # the actual shared-area target, not an invented own-only UID.
        removed_uid, removed = min(
            replaced.items(),
            key=lambda item: sum(
                abs(item[1]["cell"][i] - runtime.fight.actors[7].position[i])
                for i in (0, 1)
            ),
        )
        cast(7, 4678, tuple(removed["cell"]))
        self.assertEqual(set(portals()), set(replaced) - {removed_uid})
        before = snapshot(runtime.fight)
        before_rng = rng.getstate()
        with self.assertRaisesRegex(ValueError, "maximum casts per turn"):
            cast(7, 4678, tuple(removed["cell"]))
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertEqual(rng.getstate(), before_rng)
        self.assertEqual(native_catalog.release(), REVISION)
