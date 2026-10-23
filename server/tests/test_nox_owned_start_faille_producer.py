"""One freshly admitted Nox Faille component using only paid native actions."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase

# The centralized runner may retain this one isolated fixture for legitimate
# continuation. Its exact cleanup callbacks are retained for explicit release.
RETAIN_COMPONENT = False
retained_components = []


def release_retained_components():
    while retained_components:
        component = retained_components.pop()
        fixture = component["fixture"]
        fixture._cleanups = component["cleanups"]
        fixture.doCleanups()


class NoxOwnedStartFailleProducerTests(PostgresCase):
    def test_first_native_weapon_paid_condition_and_owned_end_earn_faille(self):
        from native_paid_party_fixture import native_endgame_iop_build
        from nox_native_offense_fixture import NativeNoxOffense
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_tactical_ai import _distances
        from wakfu_server.combat_ordinary_authority import native_facing
        from wakfu_server import combat_turn_events

        output = Path(
            ".runtime/parallel-readiness-20261021/nox259-fresh-earned-faille-component.json"
        )
        receipt = dict(
            status="pending",
            boundaries=[],
            movements=[],
            executions=[],
            phases=[],
            direct_state_or_stat_writes=False,
            scope="First native weapon; no3M or victory claim",
        )
        case = None
        execute, deliver = EffectDispatcher._execute, combat_turn_events._deliver
        watched = {
            402183,
            402194,
            402195,
            402211,
            402212,
            402213,
            402182,
            402215,
            402216,
            402190,
            402191,
            402204,
            402205,
        }

        def grade(actor, reference):
            return sum(
                row.level
                for row in actor.state_ledger.entries
                if row.reference == reference
            )

        def facts(fight):
            if case is None:
                return None
            player, boss = fight.actors[player_id], fight.actors[-200]
            return dict(
                turn=fight.turn_id,
                table=fight.native_table_turn,
                boss_grade=grade(boss, 9027),
                boss_resistance=boss.effect_stats[27],
                player_marker=grade(player, 9029),
                boss_marker=grade(boss, 9029),
                player_position=player.position,
                player_hp=player.hp,
            )

        def observed_execute(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in watched:
                receipt["executions"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        result=bool(result),
                        base_uid=invocation.base_uid,
                        state_uid=invocation.state_uid,
                        trigger=invocation.native_trigger_context,
                        facts=facts(dispatcher.native_retention.fight),
                    )
                )
            return result

        def observed_deliver(dispatcher, **kwargs):
            before = facts(dispatcher.native_retention.fight)
            result = deliver(dispatcher, **kwargs)
            if case is not None and kwargs["actor_id"] == player_id:
                receipt["phases"].append(
                    dict(
                        phase=kwargs["phase"],
                        event_id=kwargs["event_id"],
                        before=before,
                        after=facts(dispatcher.native_retention.fight),
                    )
                )
            return result

        try:
            baseline = native_endgame_iop_build()
            feca = replace(baseline, breed=1, active_spells=(6969,))
            with patch.object(
                EffectDispatcher, "_execute", observed_execute
            ), patch.object(combat_turn_events, "_deliver", observed_deliver):
                case = NativeNoxOffense(
                    self.store,
                    name_prefix="nox-faille-owned",
                    owner_count=6,
                    party_builds=(feca, *(baseline for _ in range(5))),
                )
                player_id = next(iter(case.characters))
                receipt["construction"] = case.construction
                receipt[
                    "frozen_binding"
                ] = case.fight.native_encounter_owned_start_binding
                self.assertIsNotNone(receipt["frozen_binding"])
                planning = server_runtime(
                    case.characters[player_id],
                    case.monsters,
                    case.decks[player_id],
                    action_id=1,
                    critical=False,
                    **case.common
                )[1].actor_authority

                def acceptable(cell, weapon):
                    actor, boss = case.fight.actors[player_id], case.fight.actors[-200]
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
                    return native_casting_ray(
                        case.fight,
                        planning,
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

                def route(weapon):
                    actor = case.fight.actors[player_id]
                    reached = _distances(case.fight, actor.position, player_id)
                    for cell, (_, path) in sorted(
                        reached.items(), key=lambda row: (row[1][0], row[0])
                    ):
                        if acceptable(cell, weapon):
                            return tuple(path)
                    self.fail("No native free-cell route satisfies the actual weapon")

                for boundary in range(40):
                    case.acknowledge()
                    current, boss = case.fight.current, case.fight.actors[-200]
                    self.assertIsNotNone(current)
                    self.assertLessEqual(case.fight.native_table_turn, 4)
                    weapons = sorted(
                        {
                            row.reference
                            for row in boss.state_ledger.entries
                            if row.reference in (8981, 8982, 8983, 8984)
                        }
                    )
                    receipt["boundaries"].append(
                        dict(actor=current.id, weapons=weapons, facts=facts(case.fight))
                    )
                    if current.id == player_id:
                        case.identity = player_id
                        weapon = weapons[0] if weapons else None
                        for _ in range(8):
                            actor = case.fight.actors[player_id]
                            path = route(weapon)
                            if not path or actor.mp <= 0:
                                break
                            position, mp = actor.position, actor.mp
                            requested = path[:mp]
                            case.move(requested)
                            actor = case.fight.actors[player_id]
                            receipt["movements"].append(
                                dict(
                                    before=position,
                                    after=actor.position,
                                    before_mp=mp,
                                    after_mp=actor.mp,
                                    requested=requested,
                                )
                            )
                            self.assertNotEqual(actor.position, position)
                            self.assertLess(actor.mp, mp)
                        if weapons:
                            self.assertEqual(len(weapons), 1)
                            self.assertFalse(
                                route(weapon),
                                "Actual MP cannot reach the weapon condition",
                            )
                            actor = case.fight.actors[player_id]
                            carriers = [
                                row
                                for row in actor.state_ledger.entries
                                if row.reference == 9028
                            ]
                            self.assertEqual(len(carriers), 1)
                            retained = [
                                row["invocation"]
                                for row in case.fight.native_owned_group_effects.values()
                                if row["invocation"]["reference"] == 402183
                                and row["invocation"].get("state_uid")
                                == carriers[0].uid
                            ]
                            receipt["retained_original"] = retained
                            self.assertEqual(
                                [
                                    (row["caster_id"], row["target_id"])
                                    for row in retained
                                ],
                                [(-200, player_id)],
                            )
                            before = facts(case.fight)
                            start_index = len(receipt["executions"])
                            before_hp, before_ap = boss.hp, actor.ap
                            transaction = case.cast(6969, boss.position)
                            receipt["payment"] = dict(
                                weapon=weapon,
                                before=before,
                                after_hit=facts(case.fight),
                                costs=transaction.plan["costs"],
                                critical_decision=transaction.plan["critical_decision"],
                                damage=before_hp - case.fight.actors[-200].hp,
                            )
                            self.assertEqual(transaction.plan["costs"]["ap"], 3)
                            self.assertEqual(
                                case.fight.actors[player_id].ap, before_ap - 3
                            )
                            self.assertLess(case.fight.actors[-200].hp, before_hp)
                            case.advance()  # Actual END1002 and regeneration1037, then next actual START.
                            after = facts(case.fight)
                            actions = receipt["executions"][start_index:]
                            applied = [
                                row
                                for row in actions
                                if row["reference"] in (402212, 402216, 402191, 402205)
                                and row["result"]
                            ]
                            removed = [
                                row
                                for row in actions
                                if row["reference"] == 402195 and row["result"]
                            ]
                            expected = max(
                                0,
                                min(
                                    40,
                                    before["boss_grade"]
                                    + 2 * len(applied)
                                    - len(removed),
                                ),
                            )
                            receipt["earned"] = dict(
                                after=after,
                                applied=applied,
                                removed=removed,
                                expected_grade=expected,
                                actual_actions=actions,
                            )
                            self.assertTrue(
                                applied, "Original weapon child did not apply Faille"
                            )
                            self.assertEqual(after["boss_grade"], expected)
                            self.assertGreater(
                                after["boss_grade"], before["boss_grade"]
                            )
                            self.assertEqual(
                                after["boss_resistance"],
                                before["boss_resistance"]
                                - 10 * (expected - before["boss_grade"]),
                            )
                            self.assertEqual(after["player_marker"], 1)
                            self.assertEqual(after["boss_marker"], 0)
                            self.assertTrue(
                                case.fight.native_owned_start_caster_deliveries
                            )
                            receipt["status"] = "passed"
                            if RETAIN_COMPONENT:
                                cleanups, self._cleanups = self._cleanups, []
                                retained_components.append(
                                    dict(
                                        case=case,
                                        store=self.store,
                                        fixture=self,
                                        cleanups=cleanups,
                                        receipt=receipt,
                                    )
                                )
                            break
                    case.advance()
                else:
                    self.fail("First actual weapon was not earned within40 boundaries")
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
