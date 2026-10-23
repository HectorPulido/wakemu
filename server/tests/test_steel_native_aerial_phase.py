"""Actual paid damage reaches Steel's native second aerial phase.

This is a bounded phase witness, not a victory proof. The native maximum,
initial states, paid injury, clocks, platform areas and relocation are intact.
"""
import json
from pathlib import Path
import random
import struct
import sys
from dataclasses import replace
from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))


class SteelNativeAerialPhaseTests(PostgresCase):
    def test_paid_hit_enters_second_phase_and_native_start_switches_platform(self):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_paid_party_fixture import (
            native_paid_party_fixture,
            native_endgame_iop_build,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_crow_steel_scene_layout import (
            reconstructed_steel_scene,
            STEEL_BOSSES,
        )
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_casting_alignment import native_casting_alignment
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        geometry = json.loads(
            (ROOT / ".runtime/ultimate-scenes-20261021/map-959.json").read_text()
        )
        scene = reconstructed_steel_scene(geometry)
        scene.update(reference=3582, level=170)
        # Six original native main-board cells, all outside the declared
        # cliff perimeter. Builds are persisted and admitted before Actor.
        scene["party_placement_cells"] = (
            (-13, 1, 0),
            (-13, 2, 0),
            (-13, 3, 0),
            (-13, 4, 1),
            (-12, 2, 0),
            (-12, 3, 0),
        )
        scene["anchor"] = scene["party_placement_cells"][0]
        build = native_endgame_iop_build()
        build = replace(build, active_spells=(*build.active_spells, 4782))
        with original_bootstrap_publication():
            fight, characters, monsters, decks, _, _, _ = native_paid_party_fixture(
                self.store,
                scene,
                (build,) * 6,
                scene["party_placement_cells"],
                name_prefix="steel-paid-phase",
                encounter_layout=scene,
                production_scene=True,
            )
        levels = {fight.actors[identity].effective_level for identity in characters}
        casting_tables = {
            (level, reference): native_casting_table(reference, level)[0]
            for level in levels
            for reference in (4778, 4782)
        }
        self.assertEqual(
            (fight.actors[-200].hp, fight.actors[-200].max_hp), (80000, 80000)
        )
        first, rng = next(iter(characters)), random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)

        def serializer(actor, current):
            if getattr(actor, "native_summon_source", None) is not None:
                return registered_summon_stats(actor, current, 959)
            values = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=current,
            )
            if actor.id in characters:
                return actual_actor_stats(
                    characters[actor.id], actor, current.id, **values
                )
            return actual_monster_actor_stats(
                monsters[actor.id], actor, current.id, **values
            )

        runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=serializer,
            turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                characters[first],
                monsters,
                phase,
                decks[first],
                native_events=True,
                area_callbacks=True,
                **common,
                **kw,
            ),
            turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                characters[first], monsters, phase, decks[first], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[first],
                monsters,
                decks[first],
                action_id=action_id,
                critical=False,
                **common,
            )[0],
        )
        runtime.turn_started()

        def advance():
            # A native skipped turn may publish a subsequent ACK while handling
            # the preceding token. Consume every actual token before ending.
            def drain_acknowledgements():
                for _ in range(16):
                    token = runtime.awaiting_ack
                    if token is None:
                        return
                    runtime.acknowledge_turn(struct.pack(">i", token))
                self.fail("Native ACK chain exceeded the bounded fixture budget")

            drain_acknowledgements()
            advance_actual_turn(runtime)
            drain_acknowledgements()

        boss = runtime.fight.actors[-200]
        self.assertEqual(boss.position, STEEL_BOSSES["left"])
        self.assertIn(3497, {state.reference for state in boss.state_ledger.entries})
        paid_hits, boundaries, casts_per_turn = [], 0, {}
        hit_budget = 64
        while runtime.fight.actors[-200].hp > 68000:
            boss = runtime.fight.actors[-200]
            self.assertTrue(
                any(runtime.fight.actors[identity].hp > 0 for identity in characters),
                ("Party defeated", paid_hits),
            )
            self.assertLessEqual(
                getattr(runtime.fight, "native_table_turn", 1),
                3,
                ("Three-table damage budget exhausted", paid_hits),
            )
            current = runtime.fight.current
            key = (runtime.fight.turn_id, current.id)
            used = casts_per_turn.get(key, 0)
            reference = 4782 if used < 2 else 4778
            required_ap = 3 if reference == 4782 else 2
            if current.id not in characters or current.ap < required_ap or used >= 6:
                self.assertLess(
                    boundaries, 48, ("Native turn budget exhausted", paid_hits)
                )
                advance()
                boundaries += 1
                continue
            self.assertLess(
                len(paid_hits), hit_budget, ("Paid damage budget exhausted", paid_hits)
            )
            identity = current.id
            character, deck = characters[identity], decks[identity]
            hp, ap = boss.hp, current.ap
            # Original fcr excludes only the caster. Aim at a visible cell of
            # the boss's real QK footprint instead of through its front edge
            # towards its centre. The normal cast resolves that same actor.
            authority = server_runtime(
                character,
                monsters,
                deck,
                action_id=runtime.action_id + 1,
                critical=False,
                **common,
            )[1].actor_authority
            casting = casting_tables[current.effective_level, reference]
            candidates = []
            for x, y in footprint(boss.position, boss.physical_radius):
                cell = (x, y, boss.position[2])
                distance = abs(x - current.position[0]) + abs(y - current.position[1])
                aligned = native_casting_alignment(
                    current.position,
                    cell,
                    **{
                        key: casting[key]
                        for key in ("linear", "diagonal", "linear_path", "path_option")
                    },
                )
                if (
                    aligned
                    and 1 <= distance <= 4
                    and native_casting_ray(
                        runtime.fight,
                        authority,
                        959,
                        current.position,
                        cell,
                        source_height=current.native_los_height,
                        target_height=boss.native_los_height,
                        ignored_slots=(
                            *runtime.fight.native_qi_visibility_ignored_slots,
                            current.native_obstacle_id,
                        ),
                    )
                ):
                    candidates.append((distance, cell))
            if not candidates:
                # An ally or native summon may legitimately obstruct this
                # player. End its actual turn without paying a blocked cast.
                advance()
                boundaries += 1
                continue
            target_cell = min(candidates)[1]
            try:
                tx = prepare_server_spell(
                    struct.pack(
                        ">qqiih", identity, (identity << 32) | reference, *target_cell
                    ),
                    character,
                    monsters,
                    runtime.fight,
                    character["account_id"],
                    deck,
                    action_id=runtime.action_id + 1,
                    line_of_sight=lambda origin, target, current: authoritative_visible(
                        959,
                        origin,
                        target,
                        current,
                        blocking_footprints={
                            actor.id: footprint(actor.position, actor.physical_radius)
                            for actor in current.actors.values()
                            if actor.hp > 0
                        },
                    ),
                    critical=None,
                    **common,
                )
            except ValueError as error:
                diagnostic_path = (
                    ROOT
                    / ".runtime/parallel-readiness-20261021/steel-last-native-casting-diagnostic.json"
                )
                diagnostic_path.write_text(
                    json.dumps(
                        dict(
                            error=str(error),
                            caster=current.position,
                            target=target_cell,
                            diagnostic=getattr(
                                error, "native_casting_diagnostic", None
                            ),
                            cast_diagnostics=getattr(error, "cast_diagnostics", None),
                        ),
                        indent=2,
                        default=str,
                    )
                    + "\n"
                )
                raise
            self.assertGreater(tx.plan["costs"]["ap"], 0)
            self.assertEqual(tx.plan["target_id"], boss.id)
            damage = hp - tx.fight.actors[-200].hp
            self.assertGreater(
                damage, 0, ("Paid hit made no progress", reference, paid_hits)
            )
            self.assertEqual(tx.fight.actors[identity].ap, ap - tx.plan["costs"]["ap"])
            commit_spell_transaction(runtime, tx, stats_serializer=serializer)
            casts_per_turn[key] = casts_per_turn.get(key, 0) + 1
            paid_hits.append(
                (
                    identity,
                    reference,
                    hp,
                    runtime.fight.actors[-200].hp,
                    tx.plan["costs"]["ap"],
                )
            )
            if len(paid_hits) == 1:
                # Twice the observed first-hit requirement is a bounded allowance
                # for ordinary damage variation; no resets or free resources.
                hit_budget = min(64, 2 * ((12000 + damage - 1) // damage) + 2)
        observed = []
        # Phase3498 is installed by a real own-end, then152996/1001 flies
        # on the subsequent own-start. Allow both callbacks after threshold.
        for _ in range(min(64, 2 * (len(runtime.fight.actors) + 2))):
            boss = runtime.fight.actors[-200]
            states = {state.reference for state in boss.state_ledger.entries}
            observed.append((runtime.fight.turn_id, boss.position, sorted(states)))
            if 3498 in states and boss.position == STEEL_BOSSES["right"]:
                break
            advance()
        else:
            self.fail(
                (
                    "Native paid85-percent phase/platform switch missing",
                    paid_hits,
                    observed,
                )
            )
        self.assertNotIn(3497, states)
        self.assertEqual(boss.max_hp, 80000)
        self.assertEqual(runtime.fight.walkable, scene["cells"])
        self.assertEqual(runtime.fight.edges, scene["edges"])
        self.assertTrue(
            any(runtime.fight.actors[identity].hp > 0 for identity in characters)
        )
