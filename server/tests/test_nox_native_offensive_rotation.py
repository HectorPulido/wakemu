"""Earned Ebony active, ordinary paid boss hit and actual Polarynox birth."""
import json
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase


class NoxNativeOffensiveRotationTests(PostgresCase):
    def test_earned_ebony_active_and_paid_hit_produce_original_polarynox(self):
        self._exercise_earned_opening()

    def test_three_owned_turns_kill_earned_polarynox_and_grant_global_paid_ap(self):
        self._exercise_earned_opening(
            owner_count=2,
            after_birth=self._paid_polarynox_kill,
            output_name="nox-earned-polarynox-paid-kill.json",
        )

    def test_six_owned_party_paid_wrath_hits_earned_polarynox_and_scores_boss_together(
        self,
    ):
        self._exercise_earned_opening(
            owner_count=6,
            additional_actives=(4779,),
            after_birth=self._paid_wrath,
            output_name="nox-earned-six-owner-wrath.json",
        )

    def test_six_owned_party_gathers_two_earned_polarynox_for_paid_wrath(self):
        self._exercise_earned_opening(
            owner_count=6,
            additional_actives=(4779,),
            after_birth=self._paid_grouped_wrath,
            output_name="nox-earned-six-owner-grouped-wrath.json",
        )

    def _exercise_earned_opening(
        self,
        *,
        owner_count=1,
        after_birth=None,
        additional_actives=(),
        output_name="nox-earned-offensive-opening.json"
    ):
        from nox_native_offense_fixture import NativeNoxOffense
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_spell_grant import granted_spells

        receipt = dict(
            status="pending",
            scope="Opening active and one earned native add, not3M victory",
            direct_state_grants=False,
            direct_score_or_resource_writes=False,
            trace=[],
        )
        output = Path(".runtime/parallel-readiness-20261021") / output_name
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (
                401983,
                401997,
                402175,
                402176,
                402177,
                407359,
                407360,
                407361,
                407307,
                407356,
                407357,
                407370,
                407769,
                407770,
            ):
                receipt["trace"].append(
                    dict(
                        reference=invocation.reference,
                        result=bool(result),
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                    )
                )
            return result

        try:
            with patch.object(EffectDispatcher, "execute", observe):
                case = NativeNoxOffense(
                    self.store,
                    name_prefix="nox-earned-offense",
                    owner_count=owner_count,
                    additional_actives=additional_actives,
                )
                receipt["construction"] = case.construction
                receipt["opening_boundaries"] = case.opening()
                identity = case.identity
                self.assertNotIn(8460, granted_spells(case.fight, identity))
                case.move(((-1, -8, 0), (-1, -9, 0), (-1, -10, 0)))
                self.assertIn(8460, granted_spells(case.fight, identity))
                actor = case.fight.actors[identity]
                before = (actor.ap, actor.mp, actor.effect_stats[48])
                case.cast(8460, actor.position, granted=True)
                actor = case.fight.actors[identity]
                self.assertEqual(
                    (actor.ap, actor.mp, actor.effect_stats[48]),
                    (before[0] + 1, before[1] + 1, before[2] + 25),
                )
                self.assertTrue(
                    any(entry.reference == 9025 for entry in actor.state_ledger.entries)
                )
                receipt["ebony"] = dict(
                    before=before, after=(actor.ap, actor.mp, actor.effect_stats[48])
                )
                # The intervening original Shushu area interrupts actual movement.
                # Use two genuine requests; the existing carrier cannot collect it.
                case.move(((-1, -11, 0), (-1, -12, 0)))
                case.move(((-1, -13, 0),))
                self.assertEqual(case.fight.actors[identity].position, (-1, -13, 0))
                self.assertGreaterEqual(case.fight.actors[identity].mp, 1)
                boss = case.fight.actors[-200]
                before_hp, before_ap = boss.hp, case.fight.actors[identity].ap
                transaction = case.cast(4778, boss.position)
                self.assertLess(case.fight.actors[-200].hp, before_hp)
                self.assertEqual(case.fight.actors[identity].ap, before_ap - 2)
                glyphs = [
                    dict(row)
                    for row in case.fight.native_effect_areas.values()
                    if row["reference"] == 2110
                ]
                self.assertTrue(
                    glyphs,
                    "Paid direct boss hit did not create original Polarynox glyph",
                )
                receipt["paid_hit"] = dict(
                    spell=4778,
                    before_hp=before_hp,
                    after_hp=case.fight.actors[-200].hp,
                    before_ap=before_ap,
                    after_ap=case.fight.actors[identity].ap,
                    outcomes=transaction.outcomes,
                    glyphs=glyphs,
                )
                case.move(((0, -13, 0),))
                self.assertNotIn(
                    case.fight.actors[identity].position,
                    {tuple(row["cell"]) for row in glyphs},
                )
                births = []
                for boundary in range(4):
                    births = [
                        actor
                        for actor in case.fight.actors.values()
                        if (getattr(actor, "native_summon_source", None) or {}).get(
                            "ref"
                        )
                        == 5775
                    ]
                    if births:
                        break
                    if boundary == 3:
                        self.fail(
                            "No original Polarynox birth within three real boundaries"
                        )
                    case.advance()
                receipt["births"] = [
                    dict(
                        id=actor.id,
                        hp=actor.hp,
                        max_hp=actor.max_hp,
                        team=actor.team,
                        source=actor.native_summon_source,
                    )
                    for actor in births
                ]
                self.assertTrue(
                    any(
                        row["reference"] == 407357 and row["result"]
                        for row in receipt["trace"]
                    )
                )
                if after_birth is not None:
                    after_birth(case, births[0].id, receipt)
                receipt["status"] = "passed"
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")

    def _paid_polarynox_kill(self, case, polarynox_id, receipt):
        from collections import deque
        from copy import deepcopy
        from types import SimpleNamespace
        from wakfu_server.combat_ordinary_authority import native_facing
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_spell_grant import granted_spells

        evidence = dict(
            scope="At most three owned turns, not terminal victory",
            attacks=[],
            movements=[],
            boundaries=0,
            rejections=[],
            initial_hp=case.fight.actors[polarynox_id].hp,
        )
        receipt["paid_kill"] = evidence
        identity = case.identity
        allowed_usage_errors = {
            "Native spell cast interval has not elapsed",
            "Native spell maximum casts per turn reached",
            "Native spell maximum casts per target reached",
        }
        lethal_before, lethal_cost = None, None

        def resources():
            return {
                actor_id: dict(
                    ap=case.fight.actors[actor_id].ap,
                    max_ap=case.fight.actors[actor_id].effect_maxima[2],
                )
                for actor_id in case.characters
            }

        def adjacent_path():
            actor, target = case.fight.actors[identity], case.fight.actors[polarynox_id]

            def acceptable(cell):
                return (
                    sum(abs(a - b) for a, b in zip(cell, target.position)) == 1
                    and native_facing(SimpleNamespace(position=cell), target) == "BACK"
                )

            if acceptable(actor.position):
                return ()
            blocked = set().union(
                *(
                    footprint(other.position, other.physical_radius)
                    for other in case.fight.actors.values()
                    if other.hp > 0 and other.id != identity
                )
            )
            outgoing = {}
            for source, destination in case.fight.edges:
                outgoing.setdefault(source, []).append(destination)
            pending, seen = deque([(actor.position, ())]), {actor.position}
            while pending:
                cell, path = pending.popleft()
                if path and acceptable(cell):
                    try:
                        deepcopy(case.fight).move(actor.owner_id, identity, path)
                    except ValueError:
                        pass
                    else:
                        return path
                if len(path) >= actor.mp:
                    continue
                for destination in sorted(outgoing.get(cell, ())):
                    if destination not in seen and destination[:2] not in blocked:
                        seen.add(destination)
                        pending.append((destination, (*path, destination)))
            self.fail("No paid BACK-adjacent Polarynox route within actual MP")

        for owned_turn in range(1, 4):
            for _ in range(12):
                if case.fight.phase == "active" and case.fight.current.id == identity:
                    break
                case.advance()
                evidence["boundaries"] += 1
            else:
                self.fail(
                    "Owned Polarynox turn not reached within twelve actual boundaries"
                )
            self.assertGreater(case.fight.actors[identity].hp, 0)
            # Original artifact callbacks may interrupt a genuine movement request.
            # Replan from its committed destination, paying every additional step.
            for _ in range(4):
                path = adjacent_path()
                if not path:
                    break
                actor = case.fight.actors[identity]
                before_position, before_mp = actor.position, actor.mp
                case.move(path)
                actor = case.fight.actors[identity]
                evidence["movements"].append(
                    dict(
                        turn=owned_turn,
                        requested=path,
                        before=before_position,
                        after=actor.position,
                        before_mp=before_mp,
                        after_mp=actor.mp,
                    )
                )
                self.assertNotEqual(actor.position, before_position)
                self.assertLess(actor.mp, before_mp)
                if (
                    native_facing(actor, case.fight.actors[polarynox_id]) == "BACK"
                    and sum(
                        abs(a - b)
                        for a, b in zip(
                            actor.position, case.fight.actors[polarynox_id].position
                        )
                    )
                    == 1
                ):
                    break
            self.assertEqual(
                sum(
                    abs(a - b)
                    for a, b in zip(
                        case.fight.actors[identity].position,
                        case.fight.actors[polarynox_id].position,
                    )
                ),
                1,
            )
            self.assertEqual(
                native_facing(
                    case.fight.actors[identity], case.fight.actors[polarynox_id]
                ),
                "BACK",
            )
            for _ in range(16):
                target = case.fight.actors[polarynox_id]
                if target.hp <= 0:
                    break
                admitted = False
                grants = granted_spells(case.fight, identity)
                for reference in (8403, 4778, 4780, 8402, 4777, 4781, 4789):
                    if reference in (8402, 8403) and reference not in grants:
                        continue
                    before_hp, before_resources = target.hp, resources()
                    facing = native_facing(case.fight.actors[identity], target)
                    self.assertEqual(facing, "BACK")
                    try:
                        transaction = case.cast(
                            reference, target.position, granted=reference in grants
                        )
                    except ValueError as error:
                        if (
                            getattr(error, "cast_validation_code", None)
                            != "insufficient_resources"
                            and str(error) not in allowed_usage_errors
                        ):
                            raise
                        evidence["rejections"].append(
                            dict(turn=owned_turn, spell=reference, reason=str(error))
                        )
                        continue
                    costs = transaction.plan["costs"]
                    self.assertGreater(
                        sum(costs.get(resource, 0) for resource in ("ap", "mp", "wp")),
                        0,
                    )
                    after_hp = case.fight.actors[polarynox_id].hp
                    evidence["attacks"].append(
                        dict(
                            turn=owned_turn,
                            spell=reference,
                            costs=costs,
                            before_hp=before_hp,
                            after_hp=after_hp,
                            facing=facing,
                            position=case.fight.actors[identity].position,
                            target_direction=target.direction,
                        )
                    )
                    self.assertLess(after_hp, before_hp)
                    if after_hp == 0:
                        lethal_before, lethal_cost = before_resources, costs
                    admitted = True
                    break
                if not admitted:
                    break
            if case.fight.actors[polarynox_id].hp == 0:
                break
            if owned_turn < 3:
                case.advance()
                evidence["boundaries"] += 1

        self.assertEqual(
            case.fight.actors[polarynox_id].hp,
            0,
            "Three paid owned turns did not kill the actual native50000HP add",
        )
        self.assertIsNotNone(
            lethal_before, "The native add did not die from an admitted owned paid hit"
        )
        ap_entries = [
            dict(entry)
            for entry in case.fight.owned_stat_effects.values()
            if entry.get("caster_id") == polarynox_id
            and entry.get("family") == "eWN"
            and entry.get("stat_id") == 2
        ]
        self.assertEqual(
            {entry["target_id"] for entry in ap_entries}, set(case.characters)
        )
        self.assertEqual(
            len({entry["uid"] for entry in ap_entries}), len(case.characters)
        )
        for entry in ap_entries:
            target = entry["target_id"]
            self.assertEqual(
                (entry["actual"], entry["effective_delta"], entry["remove_current"]),
                (2, 2, False),
            )
            self.assertEqual(entry["timer"]["actor_id"], target)
            self.assertEqual(entry["timer"]["phase"], "end")
            self.assertGreaterEqual(
                entry["timer"]["expiration_round"], case.fight.native_table_turn
            )
            self.assertEqual(
                case.fight.actors[target].effect_maxima[2],
                lethal_before[target]["max_ap"] + 2,
            )
            expected_ap = (
                lethal_before[target]["ap"]
                + 2
                - (lethal_cost["ap"] if target == identity else 0)
            )
            self.assertEqual(case.fight.actors[target].ap, expected_ap)
        # execute observes the original invocation; _execute resolves the native
        # population internally. The UID ledgers above prove actual delivery.
        invocations = [
            row
            for row in receipt["trace"]
            if row["reference"] == 407770
            and row["caster"] == polarynox_id
            and row["result"]
        ]
        evidence.update(
            status="paid_kill_and_global_ap_qualified",
            entries=ap_entries,
            invocations=invocations,
            before_lethal=lethal_before,
            after=resources(),
        )
        self.assertTrue(invocations)
        self.assertEqual({row["target"] for row in invocations}, {identity})
        evidence["status"] = "passed"

    def _paid_wrath(self, case, polarynox_id, receipt):
        from wakfu_server.combat_ordinary_authority import native_facing

        evidence = dict(
            scope="One paid native ring attack against actual add and boss",
            boundaries=0,
        )
        receipt["paid_wrath"] = evidence
        for _ in range(12):
            if case.fight.current.id == case.identity:
                break
            case.advance()
            evidence["boundaries"] += 1
        else:
            self.fail("Six-owner caster did not receive its actual next turn")
        # Original2066 at(0,-14) interrupts this first request. Resume by
        # another paid request, preserving its committed cell and resource loss.
        case.move(((0, -14, 0),))
        case.move(((-1, -14, 0), (-1, -15, 0)))
        actor = case.fight.actors[case.identity]
        boss, add = case.fight.actors[-200], case.fight.actors[polarynox_id]
        self.assertEqual(actor.position, (-1, -15, 0))
        self.assertEqual(native_facing(actor, add), "BACK")
        self.assertEqual(native_facing(actor, boss), "FRONT")
        self.assertEqual(len(case.characters), 6)
        actual_adds = {
            identity: target.hp
            for identity, target in case.fight.actors.items()
            if (getattr(target, "native_summon_source", None) or {}).get("ref") == 5775
            and target.hp > 0
        }
        before = dict(
            boss_hp=boss.hp, add_hp=add.hp, ap=actor.ap, wp=actor.effect_stats[4]
        )
        previous_score_ids = set(case.fight.boss_score_events)
        transaction = case.cast(4779, actor.position)
        actor = case.fight.actors[case.identity]
        after = dict(
            boss_hp=case.fight.actors[-200].hp,
            add_hp=case.fight.actors[polarynox_id].hp,
            ap=actor.ap,
            wp=actor.effect_stats[4],
        )
        evidence.update(
            before=before,
            after=after,
            costs=transaction.plan["costs"],
            outcomes=transaction.outcomes,
            boss_damage=before["boss_hp"] - after["boss_hp"],
            add_damage=before["add_hp"] - after["add_hp"],
        )
        self.assertEqual(
            (before["ap"] - after["ap"], before["wp"] - after["wp"]), (6, 1)
        )
        self.assertGreater(evidence["boss_damage"], 0)
        self.assertGreater(evidence["add_damage"], 0)
        evidence["all_adds"] = [
            dict(
                identity=identity,
                before_hp=hp,
                after_hp=case.fight.actors[identity].hp,
                cell=case.fight.actors[identity].position,
            )
            for identity, hp in actual_adds.items()
        ]
        for row in evidence["all_adds"]:
            self.assertLess(row["after_hp"], row["before_hp"])
        score_events = [
            dict(event)
            for key, event in case.fight.boss_score_events.items()
            if key not in previous_score_ids
        ]
        evidence["score_events"] = score_events
        self.assertTrue(score_events)
        self.assertEqual({event["target_id"] for event in score_events}, {-200})
        self.assertEqual(
            {event["owner_actor_id"] for event in score_events}, {case.identity}
        )
        self.assertGreaterEqual(
            sum(
                event["post_mitigation_damage"] + event["armor_absorbed"]
                for event in score_events
            ),
            evidence["boss_damage"],
        )
        evidence["status"] = "passed"

    def _paid_grouped_wrath(self, case, polarynox_id, receipt):
        from collections import deque
        from wakfu_server.combat_obstacle_condition import footprint

        original_identity = case.identity
        builder = tuple(case.characters)[2]
        goal, retreat = (-2, -15, 0), (-3, -15, 0)
        evidence = dict(
            scope="Two real births without transporting or assigning an add",
            builder=builder,
            movements=[],
            boundaries=[],
            paid_hit=None,
        )
        receipt["grouping"] = evidence

        def approach(destination):
            # Plan only. Every selected prefix is submitted through actual12161.
            for _ in range(12):
                actor = case.fight.actors[case.identity]
                if actor.position == destination:
                    return True
                if actor.mp <= 0:
                    return False
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
                path = None
                while pending:
                    cell, steps = pending.popleft()
                    if cell == destination:
                        path = steps
                        break
                    for target in sorted(outgoing.get(cell, ())):
                        if target not in seen and target[:2] not in blocked:
                            seen.add(target)
                            pending.append((target, (*steps, target)))
                self.assertIsNotNone(path, "No native free-cell grouping route")
                # Keep one genuine MP for vacating the birth cell after the hit.
                reserve = destination == goal and len(path) == actor.mp
                if reserve and actor.mp == 1:
                    return False
                requested = path[: actor.mp - int(reserve)]
                before, before_mp = actor.position, actor.mp
                case.move(requested)
                actor = case.fight.actors[case.identity]
                evidence["movements"].append(
                    dict(
                        actor=actor.id,
                        before=before,
                        requested=requested,
                        after=actor.position,
                        before_mp=before_mp,
                        after_mp=actor.mp,
                    )
                )
                self.assertNotEqual(actor.position, before)
                self.assertLess(actor.mp, before_mp)
                if reserve:
                    return False
            self.fail("Grouping exceeded twelve genuine movement requests in one turn")

        initial_adds = {
            identity
            for identity, actor in case.fight.actors.items()
            if (getattr(actor, "native_summon_source", None) or {}).get("ref") == 5775
        }
        builder_turns, produced = 0, False
        for _ in range(32):
            actor = case.fight.current
            if actor.id == builder and not produced:
                case.identity = (
                    builder  # Select the real currently controlled party actor.
                )
                builder_turns += 1
                self.assertLessEqual(builder_turns, 3)
                if approach(goal):
                    self.assertGreaterEqual(case.fight.actors[builder].mp, 1)
                    before_hp, before_ap = (
                        case.fight.actors[-200].hp,
                        case.fight.actors[builder].ap,
                    )
                    # The glyph cell is diagonal to Nox: use the already owned
                    # non-linear4781, rather than relaxing4778's line guard.
                    case.cast(4781, case.fight.actors[-200].position)
                    evidence["paid_hit"] = dict(
                        spell=4781,
                        before_hp=before_hp,
                        after_hp=case.fight.actors[-200].hp,
                        before_ap=before_ap,
                        after_ap=case.fight.actors[builder].ap,
                    )
                    self.assertLess(evidence["paid_hit"]["after_hp"], before_hp)
                    self.assertEqual(evidence["paid_hit"]["after_ap"], before_ap - 4)
                    self.assertTrue(
                        any(
                            row["reference"] == 2110 and tuple(row["cell"]) == goal
                            for row in case.fight.native_effect_areas.values()
                        )
                    )
                    self.assertTrue(approach(retreat))
                    produced = True
            born = [
                identity
                for identity, target in case.fight.actors.items()
                if identity not in initial_adds
                and (getattr(target, "native_summon_source", None) or {}).get("ref")
                == 5775
            ]
            if produced and born and case.fight.current.id == original_identity:
                evidence["new_births"] = [
                    dict(
                        identity=identity,
                        cell=case.fight.actors[identity].position,
                        hp=case.fight.actors[identity].hp,
                        source=case.fight.actors[identity].native_summon_source,
                    )
                    for identity in born
                ]
                self.assertTrue(
                    any(tuple(row["cell"]) == goal for row in evidence["new_births"])
                )
                break
            evidence["boundaries"].append(
                dict(
                    actor=case.fight.current.id, round=case.fight.native_timeline_round
                )
            )
            case.advance()
        else:
            self.fail(
                "Second earned birth and real first-owner turn not reached within32boundaries"
            )
        case.identity = original_identity
        self._paid_wrath(case, polarynox_id, receipt)
        self.assertGreaterEqual(len(receipt["paid_wrath"]["all_adds"]), 2)
        evidence["status"] = "passed"
