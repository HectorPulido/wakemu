"""One real fight earns Moon's composite inputs; no outer-HP guard bypass."""
import json
from pathlib import Path

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]


class FulMoonNativeCompositePhaseGateTests(PostgresCase):
    def fixture(self):
        from native_paid_party_fixture import (
            NativePartyBuild,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )

        scene = reconstructed_fulmoon_scene(
            json.loads(
                (
                    ROOT / ".runtime/parallel-readiness-20261021/"
                    "supreme-entry-staging/map-1056.json"
                ).read_text()
            )
        )
        scene.update(reference=3870, level=185)
        positions = (
            (-2, 3, 0),
            (5, 1, 0),
            (-1, 6, 0),
            (6, 5, 0),
            (4, 3, 0),
            (-3, 2, 0),
        )
        scene["party_placement_cells"], scene["anchor"] = positions, positions[0]
        common = ((1, 50), (23, 50), (37, 20), (2, 1), (3, 1), (4, 1), (8, 1))
        # Ordinary agility budget50:20 Willpower +20 initiative +10 dodge.
        cra = NativePartyBuild(9, 200, (4769, 4816), common + ((20, 20), (19, 10)))
        xelor = NativePartyBuild(5, 200, (775,), common)
        with original_bootstrap_publication():
            (
                fight,
                chars,
                monsters,
                decks,
                resources,
                generations,
                premise,
            ) = native_paid_party_fixture(
                self.store,
                scene,
                (cra,) * 5 + (xelor,),
                positions,
                name_prefix="moon-composite",
                encounter_layout=scene,
            )
        case = PaidComponentRuntime(fight, chars, monsters, decks, map_id=1056, seed=0)
        children = {
            identity: row["authority"]["breed_id"]
            for identity, row in fight.native_summon_registrations.items()
            if identity in fight.actors
            and row["authority"]["breed_id"] in (3993, 3995, 3996, 3997)
        }
        self.assertCountEqual(children.values(), (3993, 3995, 3996, 3997))
        self.assertEqual(fight.actors[-200].team, 0)
        self.assertTrue(all(fight.actors[i].team == 1 for i in chars))
        self.assertTrue(all(fight.actors[i].effect_stats[86] >= 20 for i in chars))
        return case, scene, tuple(sorted(children)), premise

    @staticmethod
    def level(case, identity, reference):
        return sum(
            entry.level
            for entry in case.fight.actors[identity].state_ledger.entries
            if entry.reference == reference
        )

    def approach_and_cast(self, case, identity, spell, target, minimum, maximum):
        path = case.cast_path(identity, target, minimum, maximum)
        self.assertIsNotNone(path, (identity, spell, target))
        if path:
            case.player_move_prefix(identity, path)
            path = case.cast_path(identity, target, minimum, maximum)
        if path != ():
            return None
        return case.cast(identity, spell, target)

    def test_composite_party_one_paid_action_preflight(self):
        """One actual paid native attack calibrates the shared party before a loop."""
        case, scene, targets, premise = self.fixture()
        receipt = dict(
            scope="one_actual_paid_composite_party_preflight",
            premise=premise,
            injected_states_or_resources=False,
            rng_search=False,
        )
        output = (
            ROOT
            / ".runtime/ultimate-scenes-20261021/fulmoon-composite-one-action-preflight.json"
        )
        try:
            case.runtime.turn_started(arm_deadline=False)
            for _ in range(12):
                identity = case.fight.current.id
                if (
                    identity in case.characters
                    and case.characters[identity]["breed"] == 9
                ):
                    before = case.fight.actors[-200].hp
                    row = self.approach_and_cast(case, identity, 4769, -200, 2, 5)
                    if row is None:
                        case.advance()
                        continue
                    self.assertEqual(row["costs"]["ap"], 2)
                    order = case.fight.order
                    xelor = tuple(case.characters)[-1]
                    self.assertTrue(
                        all(
                            order.index(i) < order.index(xelor)
                            for i in tuple(case.characters)[:5]
                        )
                    )
                    self.assertLess(case.fight.actors[-200].hp, before)
                    self.assertGreater(case.fight.actors[-200].hp, 1)
                    self.assertTrue(
                        all(case.fight.actors[target].hp == 5000 for target in targets)
                    )
                    receipt.update(
                        status="one_native_owned_small_attack_applied",
                        attack=row,
                        boss_hp=case.fight.actors[-200].hp,
                        boss_max_hp=case.fight.actors[-200].max_hp,
                        boss_mp=case.fight.actors[-200].mp,
                        initiative={
                            i: case.fight.actors[i].initiative for i in case.characters
                        },
                        turn_order=case.fight.order,
                    )
                    return
                case.advance()
            self.fail("No owned preflight attack within bounded opening")
        except Exception as error:
            receipt.update(
                status="failed", error=str(error), error_type=type(error).__name__
            )
            raise
        finally:
            receipt["payments"] = case.payments
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")

    def test_all_original_177773_inputs_are_earned_in_one_fight_without_dispatching_outside_hp_guard(
        self,
    ):
        from wakfu_server.combat_conditions import evaluate_condition
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.fight_checkpoint_store import snapshot

        case, scene, targets, premise = self.fixture()
        players = tuple(case.characters)
        cra_ids, xelor = players[:5], players[5]
        holder = cra_ids[-1]
        glyph, edge, inner = (2, 4, 0), (3, 8, 0), (3, 7, 0)
        firing = dict(
            zip(
                players,
                ((4, 3, 0), (5, 4, 0), (1, 3, 0), (2, 2, 0), (1, 7, 0), (4, 5, 0)),
            )
        )
        self.assertTrue(set(firing.values()) <= set(scene["cells"]))
        self.assertIn(firing[holder], scene["native_border_cells"])
        self.assertIn(edge, scene["native_border_cells"])
        self.assertNotIn(inner, scene["native_border_cells"])
        receipt = dict(
            scope="all_original_177773_inputs_same_native_fight",
            premise=premise,
            phase_dispatched=False,
            hp_guard_bypassed=False,
            injected_states_or_resources=False,
            rng_search=False,
            boundaries=[],
            hits=[],
            withdrawals=[],
            evaluations=[],
        )
        output = (
            ROOT
            / ".runtime/ultimate-scenes-20261021/fulmoon-native-composite-inputs.json"
        )
        hammered, used_withdrawal = set(), set()
        boss_stage, player_stage = "hammers", "totems"
        returning = False
        try:
            case.runtime.turn_started(arm_deadline=False)
            for _boundary in range(112):
                phase, boss = case.fight, case.fight.actors[-200]
                self.assertEqual(phase.phase, "active")
                self.assertGreater(
                    boss.hp,
                    1,
                    "Composite-only witness must not bypass or trigger outerHP guard",
                )
                for target in targets:
                    self.assertGreater(phase.actors[target].hp, 0)
                marked = {
                    target for target in targets if self.level(case, target, 4227)
                }
                if len(marked) == 4 and player_stage == "totems":
                    player_stage = "position"
                ready_players = (
                    all(phase.actors[i].position == firing[i] for i in players)
                    and self.level(case, holder, 4211) == 5
                )
                receipt["boundaries"].append(
                    dict(
                        turn=phase.turn_id,
                        actor=phase.current.id,
                        boss_stage=boss_stage,
                        player_stage=player_stage,
                        marked=sorted(marked),
                        holder=self.level(case, holder, 4211),
                        boss_moons=self.level(case, -200, 4212),
                        will=self.level(case, -200, 5227),
                        boss_position=boss.position,
                        boss_mp=boss.mp,
                    )
                )
                if self.level(case, -200, 5227) >= 50:
                    self.assertEqual(len(marked), 4)
                    self.assertEqual(self.level(case, holder, 4211), 5)
                    self.assertEqual(self.level(case, -200, 4212), 5)
                    self.assertEqual(boss.position, glyph)
                    source_state = next(
                        entry
                        for entry in boss.state_ledger.entries
                        if entry.reference == 4214
                    )
                    factory, adapter = server_runtime(
                        case.characters[case.first],
                        case.monsters,
                        case.decks[case.first],
                        action_id=case.runtime.action_id + 1,
                        critical=False,
                        **case.common
                    )
                    before = snapshot(phase)
                    answers = {}
                    for reference in (177673, 177773):
                        effect = factory.effects[str(reference)]
                        invocation = EffectInvocation(
                            reference,
                            185,
                            -200,
                            -200,
                            boss.position,
                            state_uid=source_state.uid,
                        )
                        context = adapter.condition(phase, {}, effect, invocation)
                        answers[str(reference)] = evaluate_condition(
                            effect["criteria"], context
                        )
                    self.assertEqual(snapshot(phase), before)
                    self.assertFalse(answers["177673"])
                    self.assertTrue(answers["177773"])
                    receipt.update(
                        status="all_177773_inputs_earned_and_readonly_condition_true",
                        evaluations=answers,
                        boss_hp=boss.hp,
                        outer_hp_guard=False,
                        final_totems={
                            target: dict(
                                hp=phase.actors[target].hp,
                                marker=self.level(case, target, 4227),
                            )
                            for target in targets
                        },
                    )
                    return
                identity = phase.current.id
                if identity == -200:
                    if boss_stage == "hammers":
                        if boss.position == tuple(scene["source"]):
                            case.npc_move(((0, 1, 0), (1, 1, 0)))
                        for target in [
                            target for target in targets if target not in hammered
                        ][:2]:
                            row = case.npc_cast(5693, target)
                            self.assertEqual(row["costs"]["ap"], 2)
                            self.assertGreater(case.fight.actors[target].hp, 0)
                            hammered.add(target)
                        if len(hammered) == 4:
                            boss_stage = "wait_players"
                    elif (
                        boss_stage == "wait_players"
                        and ready_players
                        and len(marked) == 4
                    ):
                        boss_stage = "border"
                    if boss_stage == "border":
                        boss = case.fight.actors[-200]
                        if boss.position != edge:
                            path = case.path_to(-200, lambda cell: cell == edge)
                            self.assertIsNotNone(path)
                            prefix = path[: boss.mp]
                            self.assertTrue(prefix)
                            case.npc_move(prefix)
                        if case.fight.actors[-200].position == edge:
                            while (
                                self.level(case, -200, 4212) < 5
                                and case.fight.actors[-200].mp >= 2
                            ):
                                case.npc_move((inner, edge))
                            if self.level(case, -200, 4212) == 5:
                                boss_stage = "return"
                    if boss_stage == "return":
                        boss = case.fight.actors[-200]
                        path = case.path_to(-200, lambda cell: cell == glyph)
                        self.assertIsNotNone(path)
                        if not returning:
                            # Split the five-step return: preserve>=5MP for real withdrawals.
                            prefix = path[: min(2, boss.mp)]
                            if prefix:
                                case.npc_move(prefix)
                                returning = True
                        else:
                            self.assertLessEqual(len(path), 3)
                            self.assertGreaterEqual(boss.mp - len(path), 5)
                            if path:
                                case.npc_move(path)
                            self.assertEqual(case.fight.actors[-200].position, glyph)
                            boss_stage = "withdrawals"
                elif identity in case.characters:
                    if player_stage == "totems" and len(hammered) == 4:
                        if identity in cra_ids:
                            turn_target_hits = {}
                            for _cast in range(3):
                                if case.fight.actors[identity].ap < 2:
                                    break
                                options = [
                                    target
                                    for target in targets
                                    if not self.level(case, target, 4227)
                                    and turn_target_hits.get(target, 0) < 2
                                ]
                                if not options:
                                    break
                                actor = case.fight.actors[identity]
                                options.sort(
                                    key=lambda target: (
                                        sum(
                                            abs(a - b)
                                            for a, b in zip(
                                                actor.position,
                                                case.fight.actors[target].position,
                                            )
                                        ),
                                        target,
                                    )
                                )
                                row = None
                                for target in options:
                                    row = self.approach_and_cast(
                                        case, identity, 4769, target, 2, 5
                                    )
                                    if row is not None:
                                        break
                                if row is None:
                                    break
                                self.assertLess(row["after"]["hp"], row["before"]["hp"])
                                self.assertGreater(row["after"]["hp"], 0)
                                self.assertEqual(row["costs"]["ap"], 2)
                                turn_target_hits[target] = (
                                    turn_target_hits.get(target, 0) + 1
                                )
                                receipt["hits"].append(row)
                                self.assertLessEqual(len(receipt["hits"]), 64)
                    elif player_stage == "position":
                        if case.fight.actors[identity].position != firing[identity]:
                            path = case.path_to(
                                identity, lambda cell: cell == firing[identity]
                            )
                            self.assertIsNotNone(path)
                            case.player_move_prefix(identity, path)
                        if (
                            identity == holder
                            and case.fight.actors[identity].position == firing[holder]
                        ):
                            while (
                                self.level(case, holder, 4211) < 5
                                and case.fight.actors[holder].mp >= 2
                            ):
                                case.player_move_prefix(
                                    holder, ((1, 6, 0), firing[holder])
                                )
                    if boss_stage == "withdrawals" and identity not in used_withdrawal:
                        if identity == xelor:
                            self.assertTrue(
                                set(cra_ids) <= used_withdrawal,
                                "Native initiative must put fallback after all five Cra",
                            )
                        used_withdrawal.add(identity)
                        reference, attempts = (
                            (4816, 1) if identity in cra_ids else (775, 2)
                        )
                        for _attempt in range(attempts):
                            if self.level(case, -200, 5227) >= 50:
                                break
                            stat = "mp" if reference == 4816 else "ap"
                            before_resource = getattr(case.fight.actors[-200], stat)
                            before_level = self.level(case, -200, 5227)
                            if before_resource == 0:
                                break
                            row = self.approach_and_cast(
                                case,
                                identity,
                                reference,
                                -200,
                                2 if reference == 4816 else 1,
                                4 if reference == 4816 else 3,
                            )
                            self.assertIsNotNone(row)
                            loss = before_resource - getattr(
                                case.fight.actors[-200], stat
                            )
                            self.assertGreaterEqual(loss, 0)
                            self.assertEqual(
                                self.level(case, -200, 5227) - before_level, loss * 10
                            )
                            self.assertEqual(
                                row["costs"]["ap"], 3 if reference == 4816 else 1
                            )
                            receipt["withdrawals"].append(
                                dict(
                                    row,
                                    actual_loss=loss,
                                    level_before=before_level,
                                    level_after=self.level(case, -200, 5227),
                                )
                            )
                if self.level(case, -200, 5227) >= 50:
                    continue  # Evaluate the real conjunction before another end/ACK.
                case.advance()
                if boss_stage == "withdrawals" and case.fight.current.id == -200:
                    self.fail(
                        "One genuine withdrawal cohort ended below50; no RNG search or extra expiry bridge"
                    )
            self.fail("Integrated native prerequisite bound exceeded")
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            receipt["payments"] = case.payments
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
