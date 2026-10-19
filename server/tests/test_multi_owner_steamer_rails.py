"""Actual allied Steamer rail construction and owner-local retirement."""
import copy
import json
import os
import random
import struct
import unittest
from unittest.mock import patch

import xelor_multiowner_fixture as fixtures
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot, _plain
from tools.combat_audit_turns import advance_actual_turn


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class MultiOwnerSteamerRailsTests(unittest.TestCase):
    def test_paid_two_owner_network_partial_retirement_preserves_foreign_checkpoint(
        self,
    ):
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum

        def steamer_character(row, *args, **kwargs):
            # Configure real character inputs before snapshots/Ready; never
            # rewrite actors, grants or native effects after initialization.
            row = dict(row)
            row["breed"] = 16
            row["hp"] = maximum(16, row["level"])
            return effective_character(row, *args, **kwargs)

        with patch(
            "wakfu_server.equipment_stats.effective_character", steamer_character
        ):
            fight, characters, monster, decks = fixtures.TwoXelorFixture().fixture(
                caster_breed=16,
                level=200,
                compact_arena=False,
                second_player_position=(-8, -4, -1),
                third_player_position=(-9, -7, -1),
            )
        self.assertEqual({characters[i]["breed"] for i in (7, 8)}, {16})
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
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

        def reach(owner, *, force_cycle=False):
            if force_cycle:
                advance_actual_turn(runtime)
            for _ in range(32):
                if runtime.fight.current.id == owner:
                    return
                advance_actual_turn(runtime)
            self.fail("Actual Steamer owner turn did not arrive")

        def cast(owner, cell, action_id):
            uid = granted_spells(runtime.fight, owner)[7008]["uid"]
            source = snapshot(runtime.fight)
            tx = prepare_server_spell(
                struct.pack(">qqiih", owner, uid, *cell),
                characters[owner],
                {-7: monster},
                runtime.fight,
                characters[owner]["account_id"],
                decks[owner],
                action_id=action_id,
                line_of_sight=lambda a, b, p: authoritative_visible(1134, a, b, p),
                critical=False,
                **common,
            )
            self.assertEqual(snapshot(runtime.fight), source)
            self.assertTrue(any(tx.outcomes))
            runtime.fight = tx.fight
            return tx

        endpoints = {}
        actual_cast_plans = {}
        for owner in (7, 8):
            reach(owner)
            origin = runtime.fight.actors[owner].position
            candidates = []
            occupied = {a.position for a in runtime.fight.actors.values() if a.hp > 0}
            # Enumerate actual exported surface geometry, not an assumed
            # four-cell corridor beside the requested placement preference.
            for start in sorted(runtime.fight.walkable):
                if (
                    start in occupied
                    or sum(abs(start[i] - origin[i]) for i in (0, 1)) > 4
                ):
                    continue
                for dx, dy in ((1, 0), (0, 1)):
                    cells = [
                        (start[0] + dx * n, start[1] + dy * n, start[2])
                        for n in range(3)
                    ]
                    if all(
                        cell in runtime.fight.walkable
                        and cell not in occupied
                        and sum(abs(cell[i] - origin[i]) for i in (0, 1)) <= 4
                        for cell in cells
                    ):
                        candidates.append(cells)
            if owner == 7:
                ally_origin = runtime.fight.actors[8].position
                candidates.sort(
                    key=lambda cells: min(
                        sum(abs(endpoint[i] - ally_origin[i]) for i in (0, 1))
                        for endpoint in (cells[0], cells[-1])
                    )
                )
            selected, rejections = None, []
            for cells in candidates:
                before = runtime.fight
                rng_before = rng.getstate()
                try:
                    cast(owner, cells[0], 10 + owner)
                    actual_cast_plans[owner] = cast(owner, cells[-1], 20 + owner).plan
                except ValueError as error:
                    runtime.fight = before
                    rng.setstate(rng_before)
                    rejections.append(str(error))
                    continue
                selected = cells
                break
            self.assertIsNotNone(
                selected,
                dict(
                    owner=owner,
                    origin=origin,
                    candidates=len(candidates),
                    rejections=rejections,
                ),
            )
            endpoints[owner] = selected
            network = runtime.fight.native_microbot_networks[owner]
            self.assertEqual(len(network["microbot_ids"]), 2)
            self.assertTrue(network["segments"])
            self.assertTrue(set(selected) <= {tuple(c) for c in network["cells"]})

        # Exercise the exact shared Qs cleanup suboperation used by forced
        # retirement on an isolated copy of the paid two-owner state. Put a
        # rail before its microbot in native global order so callback delivery
        # cannot depend on which owner row the native collection visits first.
        cleanup_fight = copy.deepcopy(runtime.fight)
        cleanup_factory, _ = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=500,
            critical=False,
            **common,
        )
        cleanup_dispatcher, cleanup_packets = cleanup_factory(
            cleanup_fight, actual_cast_plans[7]
        )
        from wakfu_server.combat_forced_retirement import NativeForcedRetirementCleanup

        cleanup = NativeForcedRetirementCleanup(cleanup_dispatcher.native_retention)
        cleanup_actor = cleanup_fight.actors[7]
        cleanup.preflight(cleanup_actor)
        cleanup_rails = {
            uid
            for uid in cleanup.areas
            if cleanup_fight.native_effect_areas[uid].get("native_microbot_rail_source")
        }
        self.assertTrue(cleanup_rails)
        cleanup.areas = tuple(
            sorted(cleanup.areas, key=lambda uid: (uid not in cleanup_rails, uid))
        )
        cleanup_foreign = copy.deepcopy(cleanup_fight.native_microbot_networks[8])
        cleanup_foreign_areas = {
            uid: _plain(cleanup_fight.native_effect_areas[uid])
            for uid, row in cleanup_fight.native_effect_areas.items()
            if row.get("owner_id") == 8
            and (
                uid in cleanup_foreign["microbot_ids"]
                or row.get("native_microbot_rail_source")
            )
        }
        self.assertTrue(
            any(
                row.get("native_microbot_rail_source")
                for uid, row in cleanup_fight.native_effect_areas.items()
                if row.get("owner_id") == 8
            )
        )
        cleanup.remove_areas(cleanup_actor)
        cleanup_removals = [
            struct.unpack(">iiiq", body)[3]
            for opcode, body in cleanup_packets
            if opcode == 13726 and len(body) == struct.calcsize(">iiiq")
        ]
        self.assertEqual(
            [uid for uid in cleanup_removals if uid in cleanup_rails],
            sorted(cleanup_rails),
        )
        self.assertTrue(cleanup_rails.isdisjoint(cleanup_fight.native_effect_areas))
        self.assertEqual(cleanup_fight.native_microbot_networks[8], cleanup_foreign)
        for uid, row in cleanup_foreign_areas.items():
            self.assertEqual(_plain(cleanup_fight.native_effect_areas[uid]), row)

        # Both allied networks contribute to travel. Use a real paid path
        # onto owner7's rail, then two rail steps for one MP with owner8.
        from collections import deque

        mover = runtime.fight.actors[8]
        self.assertEqual(runtime.fight.current.id, 8)
        blocked = {
            a.position for a in runtime.fight.actors.values() if a.hp > 0 and a.id != 8
        }
        travel = None
        for rail in (endpoints[7], list(reversed(endpoints[7]))):
            queue = deque([(mover.position, [])])
            seen = {mover.position}
            while queue:
                cell, path = queue.popleft()
                if cell == rail[0]:
                    travel = path, rail[1:]
                    break
                if len(path) >= mover.mp - 1:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    candidate = (cell[0] + dx, cell[1] + dy, cell[2])
                    if (
                        candidate in runtime.fight.walkable
                        and candidate not in blocked
                        and candidate not in seen
                    ):
                        seen.add(candidate)
                        queue.append((candidate, path + [candidate]))
            if travel:
                break
        self.assertIsNotNone(
            travel, dict(origin=mover.position, mp=mover.mp, foreign_rail=endpoints[7])
        )
        approach, rail_path = travel
        if approach:
            runtime.fight.move(characters[8]["account_id"], 8, approach)
        before_travel = mover.mp
        runtime.fight.move(characters[8]["account_id"], 8, rail_path)
        self.assertEqual(mover.mp, before_travel - 1)
        self.assertEqual(mover.position, rail_path[-1])

        reach(7, force_cycle=True)
        foreign = copy.deepcopy(runtime.fight.native_microbot_networks[8])
        foreign_areas = {
            uid: _plain(runtime.fight.native_effect_areas[uid])
            for uid in foreign["microbot_ids"]
        }
        removed_uid = next(
            uid
            for uid in runtime.fight.native_microbot_networks[7]["microbot_ids"]
            if tuple(runtime.fight.native_effect_areas[uid]["cell"]) == endpoints[7][0]
        )
        cast(7, endpoints[7][0], 40)
        current = runtime.fight
        self.assertNotIn(removed_uid, current.native_effect_areas)
        self.assertEqual(len(current.native_microbot_networks[7]["microbot_ids"]), 1)
        self.assertEqual(current.native_microbot_networks[7]["segments"], [])
        self.assertEqual(current.native_microbot_networks[8], foreign)
        for uid, row in foreign_areas.items():
            self.assertEqual(_plain(current.native_effect_areas[uid]), row)

        # Checkpoint container reconstruction is read-only. This does not claim
        # socket reconnect or process recovery coverage.
        saved = snapshot(current)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        restored_networks = restored["native_microbot_networks"]
        self.assertEqual(restored_networks["8"], json.loads(json.dumps(foreign)))
        self.assertEqual(len(restored_networks["7"]["microbot_ids"]), 1)
        self.assertNotIn(str(removed_uid), restored["native_effect_areas"])
        for uid, row in foreign_areas.items():
            self.assertEqual(_plain(restored["native_effect_areas"][str(uid)]), row)
        self.assertEqual(snapshot(current), saved)
