"""Owned class withdrawals earn Ful Moon's5227 through actual AP/MP deltas."""
from collections import deque
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import struct

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]


class FulMoonPaidNativeResourceLossTests(PostgresCase):
    def test_five_owned_cras_and_xelor_earn_fifty_after_native_boss_refill(self):
        from unittest.mock import patch
        from native_paid_party_fixture import (
            NativePartyBuild,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_movement_runtime import (
            apply_ai,
            apply_client,
            _with_areas,
        )
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_ai import (
            snapshot as ai_snapshot,
            validate as ai_validate,
        )
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_obstacle_condition import footprint

        scene = reconstructed_fulmoon_scene(
            json.loads(
                (
                    ROOT / ".runtime/parallel-readiness-20261021/"
                    "supreme-entry-staging/map-1056.json"
                ).read_text()
            )
        )
        scene.update(reference=3870, level=185)
        aptitudes = ((1, 50), (23, 50), (37, 20), (2, 1), (3, 1), (4, 1), (8, 1))
        builds = (NativePartyBuild(9, 200, (4816,), aptitudes),) * 5 + (
            NativePartyBuild(5, 200, (775,), aptitudes),
        )
        receipt = dict(
            scope="actual_paid_fulmoon_resource_loss_component",
            casts=[],
            boundaries=[],
            movements=[],
            phase_or_resource_grants=False,
            rng_search=False,
            full_first_phase_or_victory=False,
        )
        output = (
            ROOT
            / ".runtime/ultimate-scenes-20261021/fulmoon-paid-native-resource-loss.json"
        )
        try:
            with original_bootstrap_publication() as publication:
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    resources,
                    generations,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    builds,
                    tuple(scene["party_placement_cells"][:6]),
                    name_prefix="fulmoon-withdrawals",
                    encounter_layout=scene,
                )
            receipt.update(premise=premise, publication=publication)
            self.assertEqual(len({row["account_id"] for row in characters.values()}), 6)
            self.assertEqual(
                [row["breed"] for row in characters.values()], [9] * 5 + [5]
            )
            self.assertTrue(
                all(fight.actors[i].effect_stats[86] >= 20 for i in characters)
            )
            first = next(iter(characters))
            rng = Random(
                0
            )  # One ordinary chronological stream, never searched or rewound.
            common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
            authority = server_runtime(
                characters[first],
                monsters,
                decks[first],
                action_id=1,
                critical=False,
                **common
            )[1].actor_authority

            def stats(actor, current):
                if getattr(actor, "native_summon_source", None) is not None:
                    return registered_summon_stats(actor, current, 1056)
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
                runtime_stats_serializer=stats,
                turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                    characters[first],
                    monsters,
                    phase,
                    decks[first],
                    native_events=True,
                    area_callbacks=True,
                    **common,
                    **kw
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
                    **common
                )[0],
            )

            def drain_ack():
                for _ in range(32):
                    if runtime.awaiting_ack is None:
                        return
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                self.fail("Actual ACK chain exceeded component bound")

            def advance():
                drain_ack()
                advance_actual_turn(runtime)
                drain_ack()
                self.assertEqual(runtime.fight.phase, "active")

            def level():
                return sum(
                    e.level
                    for e in runtime.fight.actors[-200].state_ledger.entries
                    if e.reference == 5227
                )

            runtime.turn_started(arm_deadline=False)
            drain_ack()
            self.assertEqual(runtime.fight.current.id, -200)
            boss = runtime.fight.actors[-200]
            self.assertEqual((boss.team, runtime.fight.actors[first].team), (0, 1))
            # Spend a real native movement point, then observe the next real refill.
            occupied = {a.position for a in runtime.fight.actors.values() if a.hp > 0}
            step = next(
                end
                for start, end in sorted(runtime.fight.edges)
                if start == boss.position
                and end not in occupied
                and end not in scene["native_border_cells"]
            )
            before_mp, origin = boss.mp, boss.position

            def decide(candidate, actor_id):
                request = ai_snapshot(candidate, actor_id)
                return ai_validate(
                    candidate,
                    actor_id,
                    request,
                    dict(
                        protocol=1,
                        requestId=request["requestId"],
                        stateKey=request["stateKey"],
                        decision=dict(
                            actor_id=actor_id,
                            target_id=first,
                            path=[list(step)],
                            attack=None,
                        ),
                    ),
                )

            with patch("wakfu_server.combat_ai.plan", decide):
                _with_areas(
                    runtime,
                    lambda candidate, **kw: prepare_area_movement(
                        characters[first],
                        monsters,
                        candidate,
                        decks[first],
                        **common,
                        **kw
                    ),
                    lambda candidate, callback: apply_ai(
                        candidate,
                        lambda actor: stats(actor, candidate.fight),
                        direction=boss.direction,
                        _step_callback=callback,
                    ),
                )
            self.assertEqual(runtime.fight.actors[-200].mp, before_mp - 1)
            receipt["boss_paid_movement"] = dict(
                origin=origin,
                destination=step,
                mp_before=before_mp,
                mp_after=before_mp - 1,
            )
            spent_turn = runtime.fight.turn_id
            for _ in range(32):
                advance()
                if (
                    runtime.fight.current.id == -200
                    and runtime.fight.turn_id != spent_turn
                ):
                    break
            else:
                self.fail("No actual boss refill within bounded turn sequence")
            boss = runtime.fight.actors[-200]
            self.assertEqual(boss.mp, boss.max_mp)
            self.assertGreaterEqual(boss.mp, 5)
            receipt["native_refill"] = dict(
                turn=runtime.fight.turn_id,
                mp=boss.mp,
                maximum=boss.max_mp,
                ap=boss.ap,
                willpower=boss.effect_stats[86],
            )
            # End this boss turn without spending the freshly restored MP.
            advance()

            def firing_path(identity, minimum, maximum):
                phase = runtime.fight
                actor, target = phase.actors[identity], phase.actors[-200]
                blocked = set().union(
                    *(
                        footprint(a.position, a.physical_radius)
                        for a in phase.actors.values()
                        if a.hp > 0 and a.id != identity
                    )
                )
                outgoing = {}
                for start, end in phase.edges:
                    outgoing.setdefault(start, []).append(end)
                pending, seen = deque([(actor.position, ())]), {actor.position}
                while pending:
                    cell, path = pending.popleft()
                    distance = sum(abs(a - b) for a, b in zip(cell, target.position))
                    if minimum <= distance <= maximum and native_casting_ray(
                        phase,
                        authority,
                        1056,
                        cell,
                        target.position,
                        source_height=actor.native_los_height,
                        target_height=target.native_los_height,
                        ignored_slots=(
                            *phase.native_qi_visibility_ignored_slots,
                            actor.native_obstacle_id,
                        ),
                    ):
                        try:
                            if path:
                                deepcopy(phase).move(actor.owner_id, identity, path)
                        except ValueError:
                            pass
                        else:
                            return path
                    if len(path) >= actor.mp:
                        continue
                    for end in sorted(outgoing.get(cell, ())):
                        if end not in seen and end[:2] not in blocked:
                            seen.add(end)
                            pending.append((end, (*path, end)))
                return None

            cra_ids = set(list(characters)[:5])
            xelor_id = list(characters)[5]
            used = set()
            for _ in range(24):
                drain_ack()
                phase = runtime.fight
                identity = phase.current.id
                if identity == -200:
                    break  # Never bridge another boss end to extend5227 artificially.
                if identity in characters and identity not in used and level() < 50:
                    if identity == xelor_id and not cra_ids <= used:
                        # Native initiative ties may place Xelor before some Cra.
                        # Preserve that order and wait; never pay an early AP
                        # fallback that increases the remaining Cra resistance.
                        receipt[
                            "xelor_fallback_skipped"
                        ] = "native_turn_precedes_remaining_cra"
                        advance()
                        continue
                    used.add(identity)
                    reference, attempts = (4816, 1) if identity in cra_ids else (775, 2)
                    # Use the native +15 target-Willpower fallback only if its
                    # genuine turn naturally follows the complete Cra cohort.
                    minimum, maximum = (2, 4) if reference == 4816 else (1, 3)
                    path = firing_path(identity, minimum, maximum)
                    self.assertIsNotNone(
                        path, (identity, reference, phase.actors[identity].position)
                    )
                    if path:
                        actor = phase.actors[identity]
                        old_mp = actor.mp
                        apply_client(
                            runtime,
                            actor.owner_id,
                            struct.pack(">q", identity)
                            + b"".join(struct.pack(">iih", *cell) for cell in path),
                            lambda actor: stats(actor, runtime.fight),
                            runtime_stats_serializer=stats,
                            area_provider=lambda candidate, **kw: prepare_area_movement(
                                characters[first],
                                monsters,
                                candidate,
                                decks[first],
                                **common,
                                **kw
                            ),
                        )
                        receipt["movements"].append(
                            dict(
                                actor=identity,
                                path=path,
                                mp_before=old_mp,
                                mp_after=runtime.fight.actors[identity].mp,
                            )
                        )
                    for _cast in range(attempts):
                        if level() >= 50:
                            break
                        phase = runtime.fight
                        actor, target = phase.actors[identity], phase.actors[-200]
                        stat = "mp" if reference == 4816 else "ap"
                        before, previous_level = getattr(target, stat), level()
                        if before == 0:
                            break
                        ap, wp = actor.ap, actor.effect_stats[4]
                        tx = prepare_server_spell(
                            struct.pack(
                                ">qqiih",
                                identity,
                                (identity << 32) | reference,
                                *target.position
                            ),
                            characters[identity],
                            monsters,
                            phase,
                            actor.owner_id,
                            decks[identity],
                            action_id=runtime.action_id + 1,
                            critical=None,
                            **common,
                            line_of_sight=lambda origin, target, current: authoritative_visible(
                                1056,
                                origin,
                                target,
                                current,
                                blocking_footprints={
                                    a.id: footprint(a.position, a.physical_radius)
                                    for a in current.actors.values()
                                    if a.hp > 0
                                },
                            )
                        )
                        commit_spell_transaction(runtime, tx, stats_serializer=stats)
                        after_actor, after_target = (
                            runtime.fight.actors[identity],
                            runtime.fight.actors[-200],
                        )
                        delta = before - getattr(after_target, stat)
                        self.assertGreaterEqual(delta, 0)
                        self.assertEqual(level() - previous_level, delta * 10)
                        self.assertEqual(
                            ap - after_actor.ap, 3 if reference == 4816 else 1
                        )
                        self.assertEqual(
                            wp - after_actor.effect_stats[4],
                            0 if reference == 4816 else 1,
                        )
                        receipt["casts"].append(
                            dict(
                                actor=identity,
                                spell=reference,
                                resource=stat,
                                before=before,
                                after=getattr(after_target, stat),
                                actual_loss=delta,
                                level_before=previous_level,
                                level_after=level(),
                                costs=tx.plan["costs"],
                            )
                        )
                if level() >= 50:
                    break
                advance()
            self.assertGreaterEqual(level(), 50, receipt)
            self.assertGreaterEqual(
                sum(row["actual_loss"] for row in receipt["casts"]), 5
            )
            self.assertLessEqual(
                sum(row["spell"] == 775 for row in receipt["casts"]), 2
            )
            receipt.update(
                status="original_boss_5227_earned_by_paid_owned_withdrawals",
                level=level(),
            )
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
