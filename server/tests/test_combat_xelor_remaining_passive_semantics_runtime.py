"""Actual native Xelor passive receipts; no state or resource injection."""
import random
import unittest
import json
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers
import test_combat_xelor_own_hour_runtime as native_paths
from wakfu_server.combat_effect_dispatch import EffectDispatcher

WATCH_SIX = {
    758: {349619, 349616, 349618},
    761: {20962, 314337, 351796, 351797, 352198, 352200, 352201, 352206},
    785: {
        314473,
        314476,
        314478,
        314479,
        316255,
        316380,
        316384,
        316385,
        316403,
        349655,
        349656,
        349657,
    },
    5352: {164680},
    7186: {393456, 413760, 413761, 413762, 413763, 413764, 413765, 413766, 413767},
    7188: {312887, 349683, 164347, 164755, 314222, 314227},
}


def facts(fight):
    return {
        str(key): dict(
            position=actor.position,
            hp=actor.hp,
            max_hp=actor.max_hp,
            ap=actor.ap,
            mp=actor.mp,
            wp=actor.effect_stats.get(4),
            selected_stats={str(k): actor.effect_stats.get(k) for k in (48, 86, 120)},
            states=helpers.XelorRuntimePipelineTests.states(actor),
        )
        for key, actor in fight.actors.items()
    }


def _scenario(passive, enabled):
    helper = helpers.XelorRuntimePipelineTests()
    data = helper.fixture(
        passives=(passive,) if enabled else (), actives=(751, 754, 775, 752, 5344)
    )
    trace = []
    report = dict(
        passive=passive, enabled=enabled, initial=facts(data[2]), trace=trace, stages=[]
    )
    original = EffectDispatcher.execute

    def observe(dispatcher, invocation, **kwargs):
        fight = dispatcher.native_retention.fight
        watched = invocation.reference in WATCH_SIX[passive]
        row = dict(
            reference=invocation.reference,
            caster=invocation.caster_id,
            target=invocation.target_id,
            cell=invocation.cell,
        )
        if watched:
            row["before"] = facts(fight)
        try:
            result = original(dispatcher, invocation, **kwargs)
        except Exception as error:
            if watched:
                row.update(error=type(error).__name__, message=str(error))
                trace.append(row)
            raise
        if watched:
            row.update(result=result, after=facts(fight))
            trace.append(row)
        return result

    def cast(ref, cell):
        nonlocal data
        tx = helper.cast(data, ref, cell, action_id=30 + len(report["stages"]))
        data = helper.adopt(data, tx.fight)
        report["stages"].append(
            dict(
                spell=ref,
                cell=cell,
                outcomes=list(tx.outcomes),
                costs=dict(tx.plan["costs"]),
                casting_selection=tx.plan.get("native_casting_selection"),
                facts=facts(data[2]),
            )
        )

    try:
        with patch.object(EffectDispatcher, "execute", observe):
            cast(5345, (-11, -7, -1))
            if passive == 5352:
                # Native751 rule requires actual even6759, supplied by birth12.
                cast(751, data[2].actors[-7].position)
            else:
                cast(775, data[2].actors[-7].position)
            if passive in (758, 761, 7188):
                # Traverse attested native edges with real MP and ordinary
                # end/ACK/start. The destination is reread from actual1558.
                for _ in range(8):
                    fight = data[2]
                    hours = [
                        tuple(r["cell"])
                        for r in fight.native_effect_areas.values()
                        if r.get("owner_id") == 7 and r["reference"] == 1558
                    ]
                    if len(hours) != 1:
                        raise ValueError(("Current-hour authority", hours))
                    if fight.actors[7].position == hours[0]:
                        break
                    if fight.actors[7].mp <= 0:
                        data = helper.next_owned_turn(data)
                        continue
                    path = native_paths.XelorOwnHourRuntimeTests.path(fight, hours[0])
                    from wakfu_server.combat_area_transaction import (
                        prepare_area_movement,
                    )

                    origin = fight.actors[7].position
                    steps = path[: fight.actors[7].mp]
                    fight.move(3, 7, steps)
                    preview, _ = prepare_area_movement(
                        data[0],
                        {-7: data[1]},
                        fight,
                        data[3],
                        actor_id=7,
                        action_id=60,
                        path=steps,
                        origin=origin,
                        rng=data[4],
                    )
                    data = helper.adopt(data, preview)
                    fight = preview
                    if fight.actors[7].position != hours[0]:
                        data = helper.next_owned_turn(data)
                data = helper.next_owned_turn(data)
            elif passive == 785:
                owner = data[2].actors[7].position
                occupied = {a.position for a in data[2].actors.values() if a.hp > 0}
                cells = sorted(
                    {
                        tuple(r["cell"])
                        for r in data[2].native_effect_areas.values()
                        if r.get("owner_id") == 7
                        and 1546 <= r["reference"] <= 1557
                        and tuple(r["cell"]) not in occupied
                        and 1
                        <= abs(r["cell"][0] - owner[0]) + abs(r["cell"][1] - owner[1])
                        <= 2
                    }
                )
                if not cells:
                    raise ValueError("No real owned hour in native5344range")
                cast(5344, cells[0])
            elif passive != 5352:
                data = helper.next_owned_turn(data)
                cast(754, data[2].actors[-7].position)
        report.update(status="actual_sequence_completed", final=facts(data[2]))
    except Exception as error:
        report.update(
            status="blocked",
            error=type(error).__name__,
            message=str(error),
            final=facts(data[2]),
        )
    return report


def _boundary(passive, enabled):
    helper = helpers.XelorRuntimePipelineTests()
    if passive == 785:
        # Actual native5574 level133/HP4500 survives repeated full-level casts;
        # no HP override or fabricated resource snapshot.
        origin, target = (-8, -7, -1), (-6, -7, -1)
        terrain = helpers.bounded_arena(
            helpers.map_geometry(1134), origin, [target], radius=12
        )
        character, monster, fight = helpers.native_fixture.fixture(
            5, 200, target, terrain, origin, monster_reference=5574, monster_level=133
        )
        deck = helpers.encode_deck((775, 2839, 1418), (passive,) if enabled else ())
        rng = random.Random(17)
        fight, _ = helpers.prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        fight, _ = helpers.prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        data = character, monster, fight, deck, rng
        if fight.current.id != 7:
            data = helper.next_owned_turn(data)
    else:
        data = helper.fixture(
            passives=(passive,) if enabled else (), actives=(775, 2839, 1418)
        )
    records, stages = [], []
    report = dict(passive=passive, enabled=enabled, records=records, stages=stages)
    original = EffectDispatcher.execute
    watched = {
        312729,
        312731,
        312747,
        312748,
        349616,
        349618,
        349619,
        349663,
        349664,
        349665,
        314473,
        314476,
        314478,
        314479,
        316255,
        349655,
        316380,
        316403,
        349656,
        349657,
        316384,
        316385,
    }

    def facts(fight):
        return {
            str(k): dict(
                position=list(a.position),
                hp=a.hp,
                ap=a.ap,
                mp=a.mp,
                wp=a.effect_stats.get(4),
                states=helper.states(a),
            )
            for k, a in fight.actors.items()
        }

    def observe(dispatcher, invocation, **kwargs):
        fight = dispatcher.native_retention.fight
        before = facts(fight)
        result = original(dispatcher, invocation, **kwargs)
        if invocation.reference in watched:
            records.append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    result=result,
                    before=before,
                    after=facts(fight),
                )
            )
        return result

    def cast(ref, cell):
        nonlocal data
        tx = helper.cast(data, ref, cell, action_id=30 + len(stages))
        data = helper.adopt(data, tx.fight)
        stages.append(
            dict(
                spell=ref, cell=cell, costs=dict(tx.plan["costs"]), facts=facts(data[2])
            )
        )

    try:
        with patch.object(EffectDispatcher, "execute", observe):
            if passive == 758:
                cast(5345, (-11, -7, -1))
                # First wrap may consume actual birth marker7788; repeat real
                # four-WP Devotion through ordinary replenishment until next wrap.
                for _ in range(8):
                    if data[2].actors[7].effect_stats[4] < 4:
                        data = helper.next_owned_turn(data)
                        if data[2].actors[7].effect_stats[4] < 4:
                            raise ValueError(
                                "Actual WP replenishment cannot fund another Devotion"
                            )
                    cast(2839, data[2].actors[-7].position)
                    data = helper.next_owned_turn(data)
                    if any(x["reference"] == 349619 and x["result"] for x in records):
                        break
            else:
                # Actual occupied enemy requests expose native fighter/state
                # portal branches; owned reference stats supply survivable HP.
                cast(2839, data[2].actors[-7].position)
                cast(5345, (-7, -7, -1))
                # Actual clock birth moves owner to its outer hour (-10,-7).
                # Spend real MP to occupy the native minus-one portal point.
                from wakfu_server.combat_area_transaction import prepare_area_movement

                fight = data[2]
                origin = fight.actors[7].position
                steps = [(-9, -7, -1), (-8, -7, -1)]
                fight.move(3, 7, steps)
                preview, _ = prepare_area_movement(
                    data[0],
                    {-7: data[1]},
                    fight,
                    data[3],
                    actor_id=7,
                    action_id=40,
                    path=steps,
                    origin=origin,
                    rng=data[4],
                )
                data = helper.adopt(data, preview)
                stages.append(
                    dict(
                        action="actual_paid_movement", path=steps, facts=facts(preview)
                    )
                )
                cast(1418, (-7, -7, -1))
        report.update(status="actual_sequences_completed", final=facts(data[2]))
    except Exception as error:
        report.update(
            status="blocked",
            error=type(error).__name__,
            message=str(error),
            final=facts(data[2]),
        )
    return report


class XelorRemainingPassiveSemanticsTests(unittest.TestCase):
    def pair(self, passive):
        rows = [_scenario(passive, enabled) for enabled in (False, True)]
        for row in rows:
            self.assertEqual(row["status"], "actual_sequence_completed", row)
        return rows

    def test_knowledge_changes_actual_clock_hp_with_baseline_control(self):
        baseline, selected = self.pair(7186)
        clocks = []
        for row in (baseline, selected):
            actors = [
                v for k, v in row["stages"][0]["facts"].items() if k not in ("7", "-7")
            ]
            self.assertEqual(len(actors), 1)
            clocks.append(actors[0]["hp"])
        self.assertEqual(clocks, [820, 1230])
        self.assertTrue(
            any(x["reference"] == 413767 and x["result"] for x in selected["trace"])
        )
        self.assertFalse(
            any(x["reference"] == 413767 and x["result"] for x in baseline["trace"])
        )

    def test_dimension_applies_actual_current_hour_willpower_only_with_passive(self):
        baseline, selected = self.pair(7188)
        self.assertEqual(baseline["final"]["7"]["selected_stats"]["86"], 0)
        self.assertEqual(selected["final"]["7"]["selected_stats"]["86"], 30)
        receipts = [
            x for x in selected["trace"] if x["reference"] == 349683 and x["result"]
        ]
        self.assertTrue(receipts)
        self.assertTrue(
            any(
                x["before"]["7"]["selected_stats"]["86"] == 0
                and x["after"]["7"]["selected_stats"]["86"] == 30
                for x in receipts
            )
        )

    def test_promptness_even_clock_selects_native_los_and_linear_contract(self):
        baseline, selected = self.pair(5352)
        before = baseline["stages"][1]["casting_selection"]
        after = selected["stages"][1]["casting_selection"]
        self.assertEqual(before["selected_origin"], "baseline")
        self.assertEqual(after["selected_origin"], "conditional")
        self.assertEqual(tuple(before["selected_values"][5:7]), (True, False))
        self.assertEqual(tuple(after["selected_values"][5:7]), (False, True))
        self.assertEqual(before["selected_values"][:5], after["selected_values"][:5])
        self.assertEqual(selected["stages"][0]["facts"]["7"]["states"][6759], 12)

    def test_clockmaking_turn_branch_moves_actual_owner_and_applies_final_damage(self):
        baseline, selected = self.pair(761)
        receipts = [
            x for x in selected["trace"] if x["reference"] == 20962 and x["result"]
        ]
        self.assertTrue(receipts)
        self.assertTrue(
            any(
                x["before"]["7"]["position"] != x["after"]["7"]["position"]
                and x["before"]["7"]["selected_stats"]["48"] == 0
                and x["after"]["7"]["selected_stats"]["48"] == 50
                for x in receipts
            )
        )
        self.assertFalse(
            any(x["reference"] == 20962 and x["result"] for x in baseline["trace"])
        )

    def test_master_clock_emits_native_marker_with_real_clock_wp_receipt(self):
        baseline, selected = [_marker_lifecycle(enabled) for enabled in (False, True)]
        for row in (baseline, selected):
            self.assertEqual(row["status"], "actual_sequences_completed", row)
        controls = [
            x for x in baseline["marker_lifecycle_records"] if x["reference"] == 349619
        ]
        markers = [
            x for x in selected["marker_lifecycle_records"] if x["reference"] == 349619
        ]
        refunds = [
            x for x in selected["marker_lifecycle_records"] if x["reference"] == 413415
        ]
        self.assertTrue(controls)
        self.assertTrue(markers)
        self.assertTrue(
            all(
                x["result"] is False and x["wp_after"] == x["wp_before"]
                for x in controls
            )
        )
        self.assertTrue(
            any(
                x["result"] is True and x["wp_after"] == x["wp_before"] + 1
                for x in refunds
            )
        )
        self.assertTrue(
            any(
                x["result"] is True and x["wp_after"] == x["wp_before"] + 1
                for x in markers
            )
        )
        # Native eVy duration0: emitted marker is instant, no Qf retained row.
        self.assertTrue(all(x["new_owned_rows"] == [] for x in markers))

    def test_course_portal_callback_refunds_actual_paid_wp_with_control(self):
        baseline, selected = [_boundary(785, enabled) for enabled in (False, True)]
        for row in (baseline, selected):
            self.assertEqual(row["status"], "actual_sequences_completed", row)
            stages = row["stages"]
            self.assertEqual(
                [x.get("spell", x.get("action")) for x in stages],
                [2839, 5345, "actual_paid_movement", 1418],
            )
            self.assertEqual(
                [(x["costs"]["ap"], x["costs"]["wp"]) for x in stages if "costs" in x],
                [(0, 4), (2, 0), (4, 0)],
            )
            self.assertEqual(stages[0]["facts"]["7"]["wp"], 8)
            self.assertEqual(stages[1]["facts"]["7"]["position"], [-10, -7, -1])
            self.assertEqual(stages[2]["facts"]["7"]["position"], [-8, -7, -1])
            self.assertEqual(
                stages[1]["facts"]["7"]["mp"] - stages[2]["facts"]["7"]["mp"], 2
            )
            self.assertEqual(stages[3]["facts"]["7"]["ap"], 0)
            self.assertEqual(stages[3]["facts"]["7"]["position"], [-6, -7, -1])
            self.assertEqual(stages[3]["facts"]["-7"]["position"], [-8, -7, -1])
            self.assertEqual(stages[3]["facts"]["-7"]["wp"], 0)
        self.assertFalse(
            any(
                x["reference"] in (349656, 349657) and x["result"]
                for x in baseline["records"]
            )
        )
        receipts = [
            x for x in selected["records"] if x["reference"] == 349656 and x["result"]
        ]
        self.assertEqual(len(receipts), 1, selected)
        # Resource restoration targets native caster even when PK is the enemy.
        self.assertEqual((receipts[0]["caster"], receipts[0]["target"]), (7, -7))
        self.assertEqual(
            (receipts[0]["before"]["7"]["wp"], receipts[0]["after"]["7"]["wp"]), (8, 9)
        )
        self.assertEqual(
            (baseline["final"]["7"]["wp"], selected["final"]["7"]["wp"]), (8, 9)
        )


def _marker_lifecycle(enabled):
    records = []
    last_fight = None
    original = EffectDispatcher.execute

    def observe(dispatcher, invocation, **kwargs):
        nonlocal last_fight
        fight = dispatcher.native_retention.fight
        last_fight = fight
        previous = set(fight.owned_stat_effects)
        wp = fight.actors[7].effect_stats[4]
        result = original(dispatcher, invocation, **kwargs)
        if invocation.reference in (349619, 413414, 413415):
            records.append(
                dict(
                    reference=invocation.reference,
                    result=result,
                    wp_before=wp,
                    wp_after=fight.actors[7].effect_stats[4],
                    source_base_uid=invocation.base_uid,
                    new_owned_rows=[
                        dict(
                            uid=uid,
                            family=row["family"],
                            effect_class=row["effect_class"],
                            timer=row.get("timer"),
                        )
                        for uid, row in fight.owned_stat_effects.items()
                        if uid not in previous
                    ],
                )
            )
        return result

    with patch.object(EffectDispatcher, "execute", observe):
        report = _boundary(758, enabled)
    report["marker_lifecycle_records"] = records
    report["final_owned_stat_uids"] = (
        sorted(last_fight.owned_stat_effects) if last_fight is not None else []
    )
    return report
