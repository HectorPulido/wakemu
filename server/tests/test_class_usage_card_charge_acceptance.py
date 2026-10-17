"""Native owned card recovery and earned mask-charge spending acceptance."""
import os
import json
import random
import struct
import unittest
from copy import deepcopy


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ClassUsageCardChargeAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.usage_trace = []
        self.addCleanup(self.persist_usage_trace)

    def persist_usage_trace(self):
        from pathlib import Path

        directory = Path(
            os.environ.get(
                "WAKFU_CLASS_USAGE_TRACE_DIR",
                ".runtime/combat-resilience-phase8.5/three-class-acceptance-v4/traces",
            )
        )
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self._testMethodName}-{os.getpid()}.json"
        path.write_text(json.dumps(self.usage_trace, indent=2, default=str) + "\n")
        print(f"Class usage trace: {path.resolve()}", flush=True)

    @staticmethod
    def cast_context(runtime, uid, target):
        return dict(
            uid=uid,
            target=target,
            turn=runtime.fight.turn_id,
            actors={
                str(a.id): dict(
                    hp=a.hp,
                    ap=a.ap,
                    mp=a.mp,
                    wp=a.effect_stats.get(4),
                    position=a.position,
                    slot=a.native_obstacle_id,
                    properties=getattr(a, "native_fight_properties", None),
                    states=[(e.reference, e.level) for e in a.state_ledger.entries],
                )
                for a in runtime.fight.actors.values()
            },
            qi_slots=getattr(runtime.fight, "native_qi_slots", None),
        )

    def assert_costs(self, plan, ap, mp, wp):
        costs = plan["costs"]
        self.assertEqual(
            {key: costs[key] for key in ("ap", "mp", "wp")}, dict(ap=ap, mp=mp, wp=wp)
        )
        self.assertEqual(costs["extra_resource_deltas"], {})
        self.assertEqual(costs["extra_resource_values"], {})

    @staticmethod
    def native_los(source, target, fight):
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_qi_fight import current_registry

        # Validate registered QK authority before using its native square radius.
        current_registry(fight)
        footprints = {}
        for actor in fight.actors.values():
            if actor.hp <= 0:
                continue
            radius = actor.physical_radius
            if type(radius) is not int or not 0 <= radius <= 127:
                raise ValueError("Missing native actor physical footprint")
            x, y = actor.position[:2]
            footprints[actor.id] = {
                (px, py)
                for px in range(x - radius, x + radius + 1)
                for py in range(y - radius, y + radius + 1)
            }
        return authoritative_visible(
            1134, source, target, fight, blocking_footprints=footprints
        )

    def runtime(self, fight, characters, monster, decks, rng):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )

        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        return RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7],
                {-7: monster},
                p,
                decks[7],
                area_callbacks=True,
                **common,
                **kw,
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

    def reach(self, runtime, identity, *, next_turn=False):
        from combat_audit_turns import advance_actual_turn

        if next_turn:
            advance_actual_turn(runtime)
        for _ in range(48):
            if runtime.fight.current.id == identity and runtime.awaiting_ack is None:
                return
            advance_actual_turn(runtime)
        self.fail("Actual native owned turn not reached")

    def eligible(self, runtime, characters, monster, decks, rng, uid):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import server_runtime

        _, adapter = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        search = eligible_cast_targets(
            runtime.fight,
            characters[7],
            decks[7],
            uid,
            adapter=adapter,
            line_of_sight=self.native_los,
            actor_id=7,
            limit=256,
            maximum_eligible=16,
        )
        self.usage_trace.append(
            dict(
                stage="target_search",
                uid=uid,
                search=search,
                context=self.cast_context(runtime, uid, None),
            )
        )
        return search["eligible"]

    def cast(self, runtime, characters, monster, decks, rng, uid, target):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        original = snapshot(runtime.fight)
        self.usage_trace.append(
            dict(stage="cast", context=self.cast_context(runtime, uid, target))
        )
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *target),
            characters[7],
            {-7: monster},
            runtime.fight,
            characters[7]["account_id"],
            decks[7],
            action_id=runtime.action_id + 1,
            line_of_sight=self.native_los,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(snapshot(runtime.fight), original)
        self.assertTrue(any(tx.outcomes))
        self.usage_trace.append(
            dict(
                stage="cast_succeeded",
                plan=tx.plan,
                packets=[opcode for opcode, _ in tx.packets],
            )
        )
        runtime.fight = tx.fight
        runtime.action_id = tx.action_id
        return tx

    def test_ecaflip_paid_recovery_preserves_foreign_hand_and_rejected_rng(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            level=200,
            caster_breed=6,
            second_player_breed=6,
            active_spells=(2079,),
            second_player_spells=(2079,),
            compact_arena=False,
            second_player_position=(-7, -7, -1),
            native_target_ref=4168,
            native_target_level=190,
        )
        rng = random.Random(7)
        runtime = self.runtime(fight, characters, monster, decks, rng)
        self.reach(runtime, 7)
        cards = set(range(7938, 7951))
        initial = set(granted_spells(runtime.fight, 7)) & cards
        self.assertEqual(len(initial), 3)
        foreign = deepcopy(granted_spells(runtime.fight, 8))
        before, before_rng = snapshot(runtime.fight), rng.getstate()
        with self.assertRaisesRegex(ValueError, "positive remaining probability total"):
            self.cast(
                runtime,
                characters,
                monster,
                decks,
                rng,
                (7 << 32) | 2079,
                runtime.fight.actors[7].position,
            )
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertEqual(rng.getstate(), before_rng)
        self.assertEqual(granted_spells(runtime.fight, 8), foreign)
        grants = granted_spells(runtime.fight, 7)
        source_before_trials = snapshot(runtime.fight)
        source_rng_before_trials = rng.getstate()
        chosen = None
        # Choose a normal recovery-compatible card from the real hand. Each
        # trial has its own identical fight/RNG; only one actual branch is kept.
        # Native card modes can legitimately change subsequent target rules.
        for card in sorted(initial):
            legal = self.eligible(
                runtime, characters, monster, decks, rng, grants[card]["uid"]
            )
            if not legal:
                continue
            owner_cell = runtime.fight.actors[7].position
            row = min(legal, key=lambda item: tuple(item["target"]) != owner_cell)
            trial_rng = deepcopy(rng)
            trial = self.runtime(
                deepcopy(runtime.fight), characters, monster, decks, trial_rng
            )
            trial.action_id = runtime.action_id
            paid_ap = trial.fight.actors[7].ap
            played = self.cast(
                trial,
                characters,
                monster,
                decks,
                trial_rng,
                grants[card]["uid"],
                tuple(row["target"]),
            )
            self.assertEqual(
                trial.fight.actors[7].ap,
                paid_ap - played.plan["costs"]["ap"] + (3 if card == 7947 else 0),
            )
            recovery = self.eligible(
                trial, characters, monster, decks, trial_rng, (7 << 32) | 2079
            )
            normal_self = [
                item
                for item in recovery
                if tuple(item["target"]) == trial.fight.actors[7].position
                and {key: item["plan"]["costs"][key] for key in ("ap", "mp", "wp")}
                == dict(ap=1, mp=0, wp=1)
            ]
            if normal_self and granted_spells(trial.fight, 8) == foreign:
                chosen = card, trial, trial_rng
                break
        self.assertEqual(snapshot(runtime.fight), source_before_trials)
        self.assertEqual(rng.getstate(), source_rng_before_trials)
        self.assertIsNotNone(chosen, json.dumps(self.usage_trace, default=str))
        card, runtime, rng = chosen
        self.assertNotIn(card, granted_spells(runtime.fight, 7))
        self.assertEqual(granted_spells(runtime.fight, 8), foreign)
        paid_ap = runtime.fight.actors[7].ap
        paid_wp = runtime.fight.actors[7].effect_stats[4]
        recovered = self.cast(
            runtime,
            characters,
            monster,
            decks,
            rng,
            (7 << 32) | 2079,
            runtime.fight.actors[7].position,
        )
        self.assert_costs(recovered.plan, 1, 0, 1)
        self.assertEqual(runtime.fight.actors[7].ap, paid_ap - 1)
        self.assertEqual(runtime.fight.actors[7].effect_stats[4], paid_wp - 1)
        self.assertEqual(set(granted_spells(runtime.fight, 7)) & cards, {card})
        self.assertEqual(granted_spells(runtime.fight, 8), foreign)
        self.reach(runtime, 7, next_turn=True)
        self.assertTrue(set(granted_spells(runtime.fight, 7)) & cards)

    def test_zobal_real_turn_charges_pay_native_cost_then_retreat_without_foreign_mutation(
        self,
    ):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_actor import actual_actor_stats
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            level=90,
            caster_breed=14,
            active_spells=(7075, 7066),
            compact_arena=False,
            enemy_position=(-5, -7, -1),
            second_player_position=(-7, -6, -1),
            third_player_position=(-9, -7, -1),
            native_target_ref=4168,
            native_target_level=190,
        )
        rng = random.Random(17)
        runtime = self.runtime(fight, characters, monster, decks, rng)
        self.reach(runtime, 7)
        charge_ids = {9247, 9248, 9249}
        refs = lambda branch: {
            s.reference for s in branch.actors[7].state_ledger.entries
        }
        self.assertTrue(charge_ids.isdisjoint(refs(runtime.fight)))
        # Control branch uses the same real learned spell before earning charges.
        control = self.runtime(
            deepcopy(runtime.fight), characters, monster, decks, random.Random(17)
        )
        before_wp = control.fight.actors[7].effect_stats[4]
        self.assertGreaterEqual(control.fight.actors[7].ap, 5)
        self.assertGreaterEqual(before_wp, 1)
        self.assertTrue(
            any(
                tuple(row["target"]) == control.fight.actors[-7].position
                for row in self.eligible(
                    control,
                    characters,
                    monster,
                    decks,
                    random.Random(17),
                    (7 << 32) | 7075,
                )
            )
        )
        normal = self.cast(
            control,
            characters,
            monster,
            decks,
            random.Random(17),
            (7 << 32) | 7075,
            control.fight.actors[-7].position,
        )
        self.assert_costs(normal.plan, 5, 0, 1)
        self.assertEqual(normal.plan["costs"]["conditional_rules"], 0)
        self.assertEqual(control.fight.actors[7].effect_stats[4], before_wp - 1)
        self.assertGreaterEqual(runtime.fight.actors[7].effect_stats[4], 3)
        for reference in (7081, 7082, 7083):
            grant = granted_spells(runtime.fight, 7)[reference]
            tx = self.cast(
                runtime,
                characters,
                monster,
                decks,
                rng,
                grant["uid"],
                runtime.fight.actors[7].position,
            )
            self.assertEqual(tx.plan["costs"]["wp"], 1)
        self.reach(runtime, 7, next_turn=True)
        self.assertTrue(charge_ids <= refs(runtime.fight))
        foreign = snapshot(runtime.fight)["actors"]["8"]
        enemy_hp = runtime.fight.actors[-7].hp
        actor = runtime.fight.actors[7]
        before_ap, before_wp = actor.ap, actor.effect_stats[4]
        self.assertGreaterEqual(before_ap, 5)
        self.assertGreaterEqual(actor.mp, 1)
        self.assertTrue(
            any(
                tuple(row["target"]) == runtime.fight.actors[-7].position
                for row in self.eligible(
                    runtime, characters, monster, decks, rng, (7 << 32) | 7075
                )
            )
        )
        charged = self.cast(
            runtime,
            characters,
            monster,
            decks,
            rng,
            (7 << 32) | 7075,
            runtime.fight.actors[-7].position,
        )
        self.assert_costs(charged.plan, 5, 0, 0)
        selection = charged.plan["native_casting_selection"]
        self.assertEqual(selection["selected_origin"], "conditional")
        self.assertEqual([rule["index"] for rule in selection["matched_rules"]], [1])
        self.usage_trace.append(
            dict(
                stage="after_charged_attack",
                context=self.cast_context(runtime, (7 << 32) | 7075, None),
            )
        )
        self.assertEqual(runtime.fight.actors[7].ap, before_ap - 5)
        self.assertTrue(charge_ids.isdisjoint(refs(runtime.fight)))
        self.assertLess(runtime.fight.actors[-7].hp, enemy_hp)
        # Native Psyko charge arms a one-shot damage producer193, capped by WP.
        self.assertEqual(
            runtime.fight.actors[7].effect_stats[4],
            min(runtime.fight.actors[7].effect_maxima[4], before_wp + 1),
        )
        self.assertEqual(snapshot(runtime.fight)["actors"]["8"], foreign)
        actor = runtime.fight.actors[7]
        origin, before_mp = actor.position, actor.mp
        enemy = runtime.fight.actors[-7].position
        distance = lambda cell: abs(cell[0] - enemy[0]) + abs(cell[1] - enemy[1])
        occupied = {a.position for a in runtime.fight.actors.values()}
        self.assertGreaterEqual(before_mp, 1)
        self.assertNotEqual(
            origin[:2],
            enemy[:2],
            "Living enemy and caster must retain distinct occupied cells",
        )
        border = {
            tuple(cell)
            for cell in getattr(runtime.fight, "native_border_constructor", {})
            .get("arena", {})
            .get("native_border_cells", ())
        }
        destinations = sorted(
            end
            for start, end in runtime.fight.edges
            if start == origin
            and end not in occupied
            and end not in border
            and distance(end) > distance(origin)
        )
        from wakfu_server.combat_rail_movement import movement_cost
        from wakfu_server.combat_tackle_movement import movement_tackle_cost

        affordable = []
        for destination in destinations:
            base, _ = movement_cost(runtime.fight, actor, [destination])
            tackle_ap, tackle_mp = movement_tackle_cost(
                runtime.fight, actor, [destination]
            )
            if actor.ap >= tackle_ap and before_mp >= base + tackle_mp:
                affordable.append((destination, base + tackle_mp, tackle_ap))
        self.usage_trace.append(
            dict(
                stage="retreat_budget",
                origin=origin,
                enemy=enemy,
                ap=actor.ap,
                mp=before_mp,
                affordable=affordable,
                context=self.cast_context(runtime, None, None),
            )
        )
        self.assertTrue(
            affordable, "Real post-attack resources must afford a native retreat"
        )
        destination, expected_mp, expected_ap = affordable[0]
        before_move_ap = actor.ap
        packets, event = apply_client(
            runtime,
            characters[7]["account_id"],
            struct.pack(">qiih", 7, *destination),
            lambda actor: actual_actor_stats(
                characters[7],
                actor,
                runtime.fight.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            ),
            area_provider=lambda candidate, **boundary: prepare_area_movement(
                characters[7],
                {-7: monster},
                candidate,
                decks[7],
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
                **boundary,
            ),
        )
        self.assertEqual(runtime.fight.actors[7].position, destination)
        self.assertGreater(distance(destination), distance(origin))
        self.assertEqual(event["cost"], expected_mp)
        self.assertEqual(runtime.fight.actors[7].mp, before_mp - expected_mp)
        self.assertEqual(runtime.fight.actors[7].ap, before_move_ap - expected_ap)
        self.assertIn(13624, {opcode for opcode, _ in packets})
        before, before_rng = snapshot(runtime.fight), rng.getstate()
        with self.assertRaises(ValueError):
            apply_client(
                runtime,
                characters[7]["account_id"],
                struct.pack(">qiih", 7, *runtime.fight.actors[8].position),
                lambda actor: actual_actor_stats(
                    characters[7],
                    actor,
                    runtime.fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                ),
            )
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertEqual(rng.getstate(), before_rng)
