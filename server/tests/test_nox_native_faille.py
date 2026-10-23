"""Earn the real Nox weapon condition with a legally admitted ranged Feca."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase


class NoxNativeFailleTests(PostgresCase):
    def test_actual_weapon_paid_condition_grows_faille_and_lowers_boss_resistance(self):
        from native_paid_party_fixture import native_endgame_iop_build
        from nox_native_offense_fixture import NativeNoxOffense
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_tactical_ai import _distances
        from wakfu_server.combat_ordinary_authority import native_facing

        output = Path(
            ".runtime/parallel-readiness-20261021/nox-native-paid-faille.json"
        )
        receipt = dict(
            status="pending",
            boundaries=[],
            movements=[],
            hits=[],
            trace=[],
            direct_state_or_stat_writes=False,
        )
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (
                402182,
                402183,
                402190,
                402191,
                402204,
                402205,
                402211,
                402212,
                402215,
                402216,
            ):
                receipt["trace"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        result=bool(result),
                    )
                )
            return result

        def grade(boss):
            return sum(
                entry.level
                for entry in boss.state_ledger.entries
                if entry.reference == 9027
            )

        try:
            baseline = native_endgame_iop_build()
            feca = replace(baseline, breed=1, active_spells=(6969,))
            with patch.object(EffectDispatcher, "execute", observe):
                case = NativeNoxOffense(
                    self.store,
                    name_prefix="nox-native-faille",
                    owner_count=6,
                    party_builds=(feca, *(baseline for _ in range(5))),
                )
                receipt["construction"] = case.construction
                case.opening()
                planning_authority = server_runtime(
                    case.characters[case.identity],
                    case.monsters,
                    case.decks[case.identity],
                    action_id=1,
                    critical=False,
                    **case.common
                )[1].actor_authority

                def path_to_condition(weapon):
                    actor, boss = (
                        case.fight.actors[case.identity],
                        case.fight.actors[-200],
                    )

                    def acceptable(cell):
                        distance = sum(abs(a - b) for a, b in zip(cell, boss.position))
                        if weapon == 8984:
                            if distance != 5:
                                return False
                        elif not 1 <= distance <= 2:
                            return False
                        if (
                            weapon == 8981
                            and native_facing(SimpleNamespace(position=cell), boss)
                            != "FRONT"
                        ):
                            return False
                        # 6969 has its original LOS contract for every phase.
                        return native_casting_ray(
                            case.fight,
                            planning_authority,
                            case.scene["map_id"],
                            cell,
                            boss.position,
                            source_height=actor.native_los_height,
                            target_height=boss.native_los_height,
                            ignored_slots=(
                                *case.fight.native_qi_visibility_ignored_slots,
                                actor.native_obstacle_id,
                            ),
                        )

                    # Reuse production tactical reachability and the qualified
                    # coordinate fcr/QI LOS overload; no hypothetical Actor edit.
                    reached = _distances(case.fight, actor.position, actor.id)
                    for cell, (_distance, path) in sorted(
                        reached.items(), key=lambda item: (item[1][0], item[0])
                    ):
                        if acceptable(cell):
                            return tuple(path)
                    self.fail("No native Feca route satisfies the actual Nox weapon")

                for boundary in range(40):
                    boss = case.fight.actors[-200]
                    weapons = sorted(
                        {
                            entry.reference
                            for entry in boss.state_ledger.entries
                            if entry.reference in (8981, 8982, 8983, 8984)
                        }
                    )
                    receipt["boundaries"].append(
                        dict(
                            actor=case.fight.current.id,
                            round=case.fight.native_timeline_round,
                            weapons=weapons,
                            hp=case.fight.actors[case.identity].hp,
                        )
                    )
                    if case.fight.current.id == case.identity:
                        self.assertGreater(case.fight.actors[case.identity].hp, 0)
                        weapon = weapons[0] if weapons else None
                        for _ in range(12):
                            actor = case.fight.actors[case.identity]
                            path = path_to_condition(weapon)
                            if not path or actor.mp <= 0:
                                break
                            before, before_mp = actor.position, actor.mp
                            requested = path[: actor.mp]
                            case.move(requested)
                            actor = case.fight.actors[case.identity]
                            receipt["movements"].append(
                                dict(
                                    before=before,
                                    after=actor.position,
                                    before_mp=before_mp,
                                    after_mp=actor.mp,
                                    requested=requested,
                                )
                            )
                            self.assertNotEqual(actor.position, before)
                            self.assertLess(actor.mp, before_mp)
                        if weapons and not path_to_condition(weapon):
                            self.assertEqual(len(weapons), 1)
                            before = dict(
                                grade=grade(boss),
                                resistance=boss.effect_stats[27],
                                hp=boss.hp,
                                ap=case.fight.actors[case.identity].ap,
                            )
                            self.assertEqual(before["grade"], 0)
                            transaction = case.cast(6969, boss.position)
                            boss = case.fight.actors[-200]
                            receipt["hits"].append(
                                dict(
                                    spell=6969,
                                    before=before,
                                    after_hp=boss.hp,
                                    costs=transaction.plan["costs"],
                                    outcomes=transaction.outcomes,
                                    critical_decision=transaction.plan[
                                        "critical_decision"
                                    ],
                                )
                            )
                            self.assertLess(boss.hp, before["hp"])
                            self.assertEqual(
                                case.fight.actors[case.identity].ap, before["ap"] - 3
                            )
                            if weapon == 8982:
                                case.advance()  # This actual end, not the hit, is the authored producer.
                                boss = case.fight.actors[-200]
                            receipt["earned"] = dict(
                                weapon=weapon,
                                grade=grade(boss),
                                before_resistance=before["resistance"],
                                after_resistance=boss.effect_stats[27],
                            )
                            self.assertEqual(grade(boss), 2)
                            self.assertEqual(
                                boss.effect_stats[27], before["resistance"] - 20
                            )
                            self.assertTrue(
                                any(
                                    row["reference"] == 402182 and row["result"]
                                    for row in receipt["trace"]
                                )
                            )
                            if weapon != 8982:
                                before_second = dict(
                                    hp=boss.hp,
                                    ap=case.fight.actors[case.identity].ap,
                                    grade=grade(boss),
                                    resistance=boss.effect_stats[27],
                                )
                                second = case.cast(6969, boss.position)
                                boss = case.fight.actors[-200]
                                receipt["subsequent_paid_hit"] = dict(
                                    before=before_second,
                                    after_hp=boss.hp,
                                    costs=second.plan["costs"],
                                    critical_decision=second.plan["critical_decision"],
                                )
                                self.assertLess(boss.hp, before_second["hp"])
                                self.assertEqual(
                                    case.fight.actors[case.identity].ap,
                                    before_second["ap"] - 3,
                                )
                                self.assertEqual(grade(boss), 2)
                                self.assertEqual(
                                    boss.effect_stats[27], before_second["resistance"]
                                )
                            receipt["status"] = "passed"
                            break
                    if boundary == 39:
                        self.fail(
                            "No actual weapon condition earned within40nativeboundaries"
                        )
                    case.advance()
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
