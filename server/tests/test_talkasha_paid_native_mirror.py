"""Real owned inline hit activates the original mirror's ray producers."""
import json
from pathlib import Path
from collections import deque
from random import Random
import struct
import unittest


class TalKashaPaidNativeMirrorTests(unittest.TestCase):
    def test_owned_iop_moves_and_pays_inline_fire_hit_to_real_mirror(self):
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from native_supreme_component_scope import (
            isolate_talkasha_pyramid_opening_damage,
        )
        from native_supreme_scene_turn_runtime import native_scene_turn_runtime
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.fight_checkpoint_store import snapshot

        helper = FulMoonTalKashaNativeBootstrapTests()
        fight, scene, children = helper._started(
            5500,
            155,
            1400,
            reconstructed_talkasha_scene,
            player_breed=8,
            player_deck=(4775,),
        )
        character, monsters, deck = helper.encounter_context
        rng = Random(0)
        runtime, stats = native_scene_turn_runtime(
            fight, character, monsters, deck, map_id=1400, rng=rng
        )
        omissions = []
        with isolate_talkasha_pyramid_opening_damage(omissions):
            runtime.turn_started()
            for _boundary in range(8):
                if runtime.fight.phase != "active" or runtime.fight.current.id == 7:
                    break
                advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.phase, "active")
        self.assertEqual(runtime.fight.current.id, 7)
        current = runtime.fight
        mirror = next(
            identity for identity, reference in children.items() if reference == 5579
        )
        source = current.actors[7]
        target = current.actors[mirror]
        _, adapter = server_runtime(
            character,
            monsters,
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        occupied = {
            tuple(actor.position)
            for actor in current.actors.values()
            if actor.hp > 0 and actor.id != 7
        }
        adjacent = {}
        for origin, end in current.edges:
            if tuple(end) not in occupied:
                adjacent.setdefault(tuple(origin), []).append(tuple(end))
        queue = deque([(tuple(source.position), ())])
        seen = {tuple(source.position)}
        probes = []
        selected = None
        while queue:
            cell, path = queue.popleft()
            distance = abs(cell[0] - target.position[0]) + abs(
                cell[1] - target.position[1]
            )
            if (
                path
                and 1 <= distance <= 3
                and (cell[0] == target.position[0] or cell[1] == target.position[1])
            ):
                diagnostic = {}
                visible = native_casting_ray(
                    current,
                    adapter.actor_authority,
                    1400,
                    cell,
                    target.position,
                    source_height=source.native_los_height,
                    target_height=target.native_los_height,
                    ignored_slots=(
                        *current.native_qi_visibility_ignored_slots,
                        source.native_obstacle_id,
                    ),
                    diagnostic=diagnostic,
                )
                probes.append(
                    dict(cell=cell, path=path, visible=visible, diagnostic=diagnostic)
                )
                if visible:
                    selected = (cell, path)
                    break
            if len(path) < 16:
                for end in sorted(adjacent.get(cell, ())):
                    if end not in seen:
                        seen.add(end)
                        queue.append((end, path + (end,)))
        probe_output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/ultimate-scenes-20261021/talkasha-mirror-native-route-planning.json"
        )
        probe_output.write_text(json.dumps(probes, indent=2, default=str) + "\n")
        self.assertIsNotNone(selected, probes)
        destination, path = selected
        movement_payments = []
        remaining = list(path)
        while remaining:
            current = runtime.fight
            if current.actors[7].mp <= 0:
                with isolate_talkasha_pyramid_opening_damage(omissions):
                    for _boundary in range(8):
                        advance_actual_turn(runtime)
                        if (
                            runtime.fight.phase != "active"
                            or runtime.fight.current.id == 7
                        ):
                            break
                self.assertEqual(runtime.fight.phase, "active")
                self.assertEqual(runtime.fight.current.id, 7)
                current = runtime.fight
            count = min(current.actors[7].mp, len(remaining))
            self.assertGreater(count, 0)
            steps, remaining = remaining[:count], remaining[count:]
            old_mp = current.actors[7].mp
            apply_client(
                runtime,
                3,
                struct.pack(">q", 7)
                + b"".join(struct.pack(">iih", *cell) for cell in steps),
                lambda actor: stats(actor, runtime.fight),
                runtime_stats_serializer=stats,
                area_provider=lambda candidate, **boundary: prepare_area_movement(
                    character, monsters, candidate, deck, rng=rng, **boundary
                ),
            )
            self.assertEqual(runtime.fight.actors[7].position, steps[-1])
            self.assertEqual(runtime.fight.actors[7].mp, old_mp - count)
            movement_payments.append(dict(path=steps, paid_mp=count))
        current = runtime.fight
        self.assertEqual(current.actors[7].position, destination)
        mirror = next(
            identity for identity, reference in children.items() if reference == 5579
        )
        before = snapshot(current)
        tx = prepare_server_spell(
            struct.pack(
                ">qqiih", 7, (7 << 32) | 4775, *current.actors[mirror].position
            ),
            character,
            monsters,
            current,
            3,
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
            line_of_sight=lambda origin, target, candidate: authoritative_visible(
                1400,
                origin,
                target,
                candidate,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in candidate.actors.values()
                    if actor.hp > 0
                },
            ),
            player_characters={7: character},
            deck_blobs={7: deck},
        )
        self.assertEqual(snapshot(current), before)
        self.assertEqual(tx.plan["costs"]["ap"], 3)
        self.assertEqual(tx.fight.actors[7].ap, current.actors[7].ap - 3)
        created = [
            dict(reference=row["reference"], cell=row["cell"])
            for row in tx.fight.native_effect_areas.values()
            if row["reference"] not in (1837, 1838)
        ]
        receipt = dict(
            scope="paid_inline_mirror_hit_component",
            full_encounter_victory=False,
            injected_states_or_resources=False,
            isolated_effects=omissions,
            spell=4775,
            target=mirror,
            origin=destination,
            target_cell=current.actors[mirror].position,
            paid_mp=len(path),
            movement_payments=movement_payments,
            costs=tx.plan["costs"],
            created_areas=created,
            mirror_direction=tx.fight.actors[mirror].direction,
        )
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/ultimate-scenes-20261021/talkasha-paid-native-mirror.json"
        )
        output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.assertTrue(created, receipt)
        self.assertTrue(
            any(row["reference"] in (1839, 1840, 1841, 1842, 1849) for row in created),
            receipt,
        )
