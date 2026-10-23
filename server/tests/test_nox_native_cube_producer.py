"""Original marker births, paid battery switches and the actual next Cube pulse."""
from collections import deque
from dataclasses import replace
from types import SimpleNamespace
import json
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase


class NoxNativeCubeProducerTests(PostgresCase):
    def test_paid_batteries_cube_damage_and_first_weapon_faille_share_one_encounter(
        self,
    ):
        from nox_native_offense_fixture import NativeNoxOffense
        from native_paid_party_fixture import native_endgame_iop_build
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_ordinary_authority import native_facing
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
        from wakfu_server.combat_obstacle_condition import footprint

        output = Path(
            ".runtime/parallel-readiness-20261021/nox-paid-cube-battery-producer.json"
        )
        receipt = dict(
            status="pending",
            scope="Cube two-table component then first real Faille; no3M or terminal victory claim",
            executions=[],
            movements=[],
            payments=[],
            mutations=[],
            boundaries=[],
        )
        self.addCleanup(
            lambda: output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        )
        execute, mutate = EffectDispatcher._execute, NativeRunnerAmount.mutate
        active = []
        observed = {
            401566,
            401568,
            401561,
            402117,
            401525,
            401528,
            401813,
            401548,
            401817,
            401821,
            401519,
            401584,
            402182,
            402197,
            402183,
            402215,
            402190,
            402204,
            402211,
        }

        def traced_execution(dispatcher, invocation, **kwargs):
            active.append(invocation.reference)
            try:
                result = execute(dispatcher, invocation, **kwargs)
                if invocation.reference in observed:
                    current = dispatcher.native_retention.fight
                    receipt["executions"].append(
                        dict(
                            reference=invocation.reference,
                            caster=invocation.caster_id,
                            target=invocation.target_id,
                            cell=invocation.cell,
                            result=bool(result),
                            table=current.native_table_turn,
                            turn=current.turn_id,
                        )
                    )
                return result
            finally:
                active.pop()

        def traced_mutation(runner, mode, value, replace):
            before = runner.value
            result = mutate(runner, mode, value, replace)
            if active and active[-1] in (401519, 401584):
                receipt["mutations"].append(
                    dict(
                        reference=active[-1],
                        uid=runner.uid,
                        family=runner.family,
                        mode=mode,
                        amount=value,
                        replace=replace,
                        before=before,
                        after=runner.value,
                    )
                )
            return result

        with patch.object(EffectDispatcher, "_execute", traced_execution), patch.object(
            NativeRunnerAmount, "mutate", traced_mutation
        ):
            baseline = native_endgame_iop_build()
            feca = replace(baseline, breed=1, active_spells=(6969,))
            case = NativeNoxOffense(
                self.store,
                name_prefix="nox-cube-native",
                owner_count=6,
                party_builds=(feca, *(baseline for _ in range(5))),
            )
            players = tuple(case.characters)
            hitter = players[0]

            def grade(actor, reference):
                entries = [
                    row.level
                    for row in actor.state_ledger.entries
                    if row.reference == reference
                ]
                self.assertLessEqual(len(entries), 1)
                return entries[0] if entries else None

            def natives(reference):
                return [
                    actor
                    for actor in case.fight.actors.values()
                    if (getattr(actor, "native_summon_source", None) or {}).get("ref")
                    == reference
                ]

            batteries, cubes = natives(5783), natives(5786)
            self.assertEqual((len(batteries), len(cubes)), (5, 1))
            cube_id, battery_ids = cubes[0].id, tuple(actor.id for actor in batteries)
            self.assertIsNotNone(grade(cubes[0], 8974))
            self.assertEqual(grade(cubes[0], 8970), 12)
            births = [row for row in receipt["executions"] if row["result"]]
            self.assertEqual(sum(row["reference"] == 401566 for row in births), 5)
            self.assertEqual(sum(row["reference"] == 401568 for row in births), 1)
            receipt["admission"] = dict(
                construction=case.construction,
                cube=dict(
                    id=cube_id,
                    source=cubes[0].native_summon_source,
                    position=cubes[0].position,
                    charge=grade(cubes[0], 8970),
                ),
                batteries=[
                    dict(
                        id=actor.id,
                        source=actor.native_summon_source,
                        position=actor.position,
                        recharge=grade(actor, 8972),
                        discharge=grade(actor, 8973),
                    )
                    for actor in batteries
                ],
            )

            def path_to(predicate):
                actor = case.fight.actors[case.identity]
                blocked = set().union(
                    *(
                        footprint(other.position, other.physical_radius)
                        for other in case.fight.actors.values()
                        if other.hp > 0 and other.id != actor.id
                    )
                )
                outgoing = {}
                for source, target in case.fight.edges:
                    outgoing.setdefault(tuple(source), []).append(tuple(target))
                pending, seen = deque([(actor.position, ())]), {actor.position}
                while pending:
                    cell, path = pending.popleft()
                    if predicate(cell):
                        return path
                    for target in sorted(outgoing.get(cell, ())):
                        if target not in seen and target[:2] not in blocked:
                            seen.add(target)
                            pending.append((target, (*path, target)))
                return None

            def move_to(predicate):
                for _ in range(6):
                    actor = case.fight.actors[case.identity]
                    if predicate(actor.position):
                        return True
                    path = path_to(predicate)
                    if not path or actor.mp <= 0:
                        return False
                    before, mp = actor.position, actor.mp
                    case.move(path[: actor.mp])
                    actor = case.fight.actors[case.identity]
                    receipt["movements"].append(
                        dict(
                            actor=actor.id,
                            before=before,
                            after=actor.position,
                            before_mp=mp,
                            after_mp=actor.mp,
                        )
                    )
                    self.assertNotEqual(actor.position, before)
                    self.assertLess(actor.mp, mp)
                return predicate(case.fight.actors[case.identity].position)

            switched, seen_turns, ready_hitter = set(), set(), False
            expected_charge, cube_verified = None, False
            planning_authority = server_runtime(
                case.characters[hitter],
                case.monsters,
                case.decks[hitter],
                action_id=1,
                critical=False,
                **case.common
            )[1].actor_authority

            def faille_condition(cell, weapon):
                actor, boss = case.fight.actors[hitter], case.fight.actors[-200]
                distance = sum(abs(a - b) for a, b in zip(cell, boss.position))
                if weapon == 8984:
                    if distance != 5:
                        return False
                elif not 1 <= distance <= 2:
                    return False
                if (
                    weapon == 8981
                    and native_facing(SimpleNamespace(position=cell), boss) != "FRONT"
                ):
                    return False
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

            for boundary in range(40):
                case.acknowledge()
                current = case.fight.current
                self.assertIsNotNone(current)
                self.assertEqual(case.fight.phase, "active")
                table = case.fight.native_table_turn
                if not cube_verified:
                    self.assertLessEqual(
                        table, 2, "Cube component exceeded two actual tables"
                    )
                receipt["boundaries"].append(
                    dict(actor=current.id, table=table, turn=case.fight.turn_id)
                )
                if current.id in players:
                    case.identity = current.id
                    turn = (case.fight.turn_id, current.id)
                    if table == 1 and turn not in seen_turns:
                        seen_turns.add(turn)
                        if current.id == hitter:
                            boss = case.fight.actors[-200]

                            def boss_range(cell):
                                return (
                                    cell[2] == boss.position[2]
                                    and (
                                        cell[0] == boss.position[0]
                                        or cell[1] == boss.position[1]
                                    )
                                    and 2
                                    <= abs(cell[0] - boss.position[0])
                                    + abs(cell[1] - boss.position[1])
                                    <= 5
                                )

                            ready_hitter = move_to(boss_range)
                        elif len(switched) < 3:
                            choices = []
                            for identity in battery_ids:
                                target = case.fight.actors[identity]
                                if identity in switched or grade(target, 8973) is None:
                                    continue

                                def adjacent(cell, target=target):
                                    return (
                                        sum(
                                            abs(a - b)
                                            for a, b in zip(cell, target.position)
                                        )
                                        == 1
                                    )

                                path = path_to(adjacent)
                                if (
                                    path is not None
                                    and len(path) <= case.fight.actors[current.id].mp
                                ):
                                    choices.append((len(path), identity, adjacent))
                            if choices:
                                # Spend the scarce long route first; another owner can still
                                # reach the nearby battery using its own genuine MP.
                                _, identity, predicate = max(
                                    choices, key=lambda row: row[:2]
                                )
                                self.assertTrue(move_to(predicate))
                                target = case.fight.actors[identity]
                                before_ap, before_hp = (
                                    case.fight.actors[current.id].ap,
                                    target.hp,
                                )
                                transaction = case.cast(4778, target.position)
                                target = case.fight.actors[identity]
                                self.assertEqual(transaction.plan["costs"]["ap"], 2)
                                self.assertEqual(
                                    case.fight.actors[current.id].ap, before_ap - 2
                                )
                                self.assertEqual(target.hp, before_hp)
                                self.assertEqual(grade(target, 8972), 1)
                                self.assertIsNone(grade(target, 8973))
                                switched.add(identity)
                                receipt["payments"].append(
                                    dict(
                                        actor=current.id,
                                        target=identity,
                                        spell=4778,
                                        costs=transaction.plan["costs"],
                                        recharge=grade(target, 8972),
                                        discharge=grade(target, 8973),
                                    )
                                )
                        if len(switched) >= 3:
                            recharge = sum(
                                grade(case.fight.actors[identity], 8972) is not None
                                for identity in battery_ids
                            )
                            discharge = sum(
                                grade(case.fight.actors[identity], 8973) is not None
                                for identity in battery_ids
                            )
                            self.assertEqual(recharge + discharge, 5)
                            count = grade(case.fight.actors[cube_id], 8995)
                            self.assertEqual(count, 6 + recharge - discharge)
                            expected_charge = max(1, min(24, 12 + recharge - discharge))
                            receipt["expected"] = dict(
                                recharge=recharge,
                                discharge=discharge,
                                native_counter=count,
                                delta=recharge - discharge,
                                charge=expected_charge,
                            )
                    elif table == 2 and current.id == hitter and not cube_verified:
                        self.assertTrue(
                            ready_hitter,
                            "Actual hitter never reached its native spell range",
                        )
                        self.assertGreaterEqual(len(switched), 3)
                        cube = case.fight.actors[cube_id]
                        self.assertEqual(grade(cube, 8970), expected_charge)
                        self.assertGreater(expected_charge, 12)
                        before_hp, before_ap = case.fight.actors[-200].hp, current.ap
                        receipt["mutations"].clear()
                        transaction = case.cast(6969, case.fight.actors[-200].position)
                        self.assertEqual(transaction.plan["costs"]["ap"], 3)
                        self.assertEqual(case.fight.actors[hitter].ap, before_ap - 3)
                        self.assertLess(case.fight.actors[-200].hp, before_hp)
                        modifiers = [
                            row
                            for row in receipt["mutations"]
                            if row["reference"] == 401519
                            and row["mode"] == 0
                            and row["amount"] == -360 + 30 * expected_charge
                        ]
                        self.assertTrue(
                            modifiers,
                            "Actual paid damage did not consume original Cube modifier",
                        )
                        self.assertTrue(
                            any(
                                row["before"] > 0 and row["after"] > row["before"]
                                for row in modifiers
                            )
                        )
                        pulses = [
                            row
                            for row in case.fight.native_npc_phase_deliveries.values()
                            if row["table_turn"] == 2
                        ]
                        self.assertEqual(len(pulses), 1)
                        self.assertEqual(
                            [row["owner_id"] for row in pulses[0]["owned_listeners"]],
                            [cube_id],
                        )
                        receipt["result"] = dict(
                            charge=grade(cube, 8970),
                            boss_damage=before_hp - case.fight.actors[-200].hp,
                            modifiers=modifiers,
                            pulse=pulses[0],
                            costs=transaction.plan["costs"],
                        )
                        cube_verified = True
                    elif cube_verified and current.id == hitter:
                        boss = case.fight.actors[-200]
                        weapons = sorted(
                            {
                                entry.reference
                                for entry in boss.state_ledger.entries
                                if entry.reference in (8981, 8982, 8983, 8984)
                            }
                        )
                        if weapons:
                            self.assertLessEqual(
                                table, 4, "First weapon component exceeded table4"
                            )
                            self.assertEqual(len(weapons), 1)
                            weapon = weapons[0]
                            self.assertIsNotNone(
                                grade(current, 9028),
                                "Original player Faille carrier missing",
                            )
                            self.assertTrue(
                                move_to(lambda cell: faille_condition(cell, weapon)),
                                "Feca cannot pay movement into the actual weapon condition",
                            )
                            boss = case.fight.actors[-200]
                            before = dict(
                                grade=grade(boss, 9027) or 0,
                                resistance=boss.effect_stats[27],
                                hp=boss.hp,
                                ap=case.fight.actors[hitter].ap,
                            )
                            self.assertEqual(before["grade"], 0)
                            transaction = case.cast(6969, boss.position)
                            self.assertEqual(transaction.plan["costs"]["ap"], 3)
                            self.assertEqual(
                                case.fight.actors[hitter].ap, before["ap"] - 3
                            )
                            self.assertLess(case.fight.actors[-200].hp, before["hp"])
                            if weapon == 8982:
                                case.advance()
                            boss = case.fight.actors[-200]
                            receipt["faille"] = dict(
                                weapon=weapon,
                                table=table,
                                before=before,
                                grade=grade(boss, 9027),
                                resistance=boss.effect_stats[27],
                                boss_hp=boss.hp,
                                costs=transaction.plan["costs"],
                                critical_decision=transaction.plan["critical_decision"],
                            )
                            self.assertEqual(grade(boss, 9027), 2)
                            self.assertEqual(
                                boss.effect_stats[27], before["resistance"] - 20
                            )
                            receipt["status"] = "passed"
                            break
                case.advance()
            else:
                self.fail(
                    "Combined Cube/Faille component exhausted40 actual boundaries"
                )
