"""Three real companions share a single lawful six-AP owner turn."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerCompanionCapacityRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt

    def test_three_spatially_separated_companions_use_actual_two_ap_casts(self):
        from wakfu_server.combat_server_spell import server_runtime
        from tools.class_spell_eligible_targets import eligible_cast_targets
        import tools.class_spell_eligible_targets as selector

        data = self.fixture((6931,), actives=(6914,))
        turn = data[2].turn_id
        initial_ap = data[2].actors[7].ap
        for count in range(3):
            character, monster, fight, deck, rng = data
            companions = [
                a
                for a in fight.actors.values()
                if a.hp > 0 and any(s.reference == 6288 for s in a.state_ledger.entries)
            ]
            cells, total = selector.candidate_cells(fight, 7, limit=256)
            occupied = {a.position for a in fight.actors.values() if a.hp > 0}
            distance = lambda a, b: sum(abs(a[i] - b[i]) for i in (0, 1))
            ranked = sorted(
                cells,
                key=lambda c: (
                    tuple(c) in occupied,
                    -min((distance(c, a.position) for a in companions), default=99),
                    -distance(c, fight.actors[7].position),
                ),
            )
            _, adapter = server_runtime(
                character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
            )
            with patch.object(
                selector, "candidate_cells", return_value=(ranked, total)
            ):
                targets = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    (7 << 32) | 6914,
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    actor_id=7,
                    limit=256,
                    maximum_eligible=16,
                )
            choices = [
                row["target"]
                for row in targets["eligible"]
                if tuple(row["target"]) not in occupied
                and all(distance(row["target"], a.position) > 4 for a in companions)
            ]
            self.assertTrue(
                choices,
                dict(
                    count=count,
                    targets=targets,
                    companions=[(a.id, a.position) for a in companions],
                ),
            )
            result = self.cast(data, 6914, target=choices[0])
            data = self.adopt(data, result.fight)
            actual = [
                a
                for a in data[2].actors.values()
                if a.hp > 0 and any(s.reference == 6288 for s in a.state_ledger.entries)
            ]
            self.assertEqual(len(actual), count + 1)
            self.assertEqual(data[2].turn_id, turn)
            self.assertEqual(data[2].actors[7].ap, initial_ap - 2 * (count + 1))

    def test_real_equipment_allows_fourth_paid_cast_without_fourth_companion(self):
        from wakfu_server import equipment_stats
        from wakfu_server.wire import proto_field
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        # The same source-validated owned equipment used by the critical
        # excess test; effective_character validates every real effect/slot.
        equipment = (
            (23924, 4),
            (31319, 13),
            (19146, 15),
            (20151, 16),
            (19746, 10),
            (20278, 3),
            (18005, 5),
            (23975, 0),
            (30353, 12),
            (22126, 17),
        )
        effective = equipment_stats.effective_character

        def equipped(character, *args, **kwargs):
            if character.get("id") == 7:
                character = dict(character)
                character["inventory_items"] = [
                    dict(uid=90000 + i, character_id=7, reference=ref, quantity=1)
                    for i, (ref, _) in enumerate(equipment)
                ]
                builds = {
                    key: dict(value) for key, value in character["builds"].items()
                }
                builds.setdefault(0, {"sheet": proto_field(24, 0xFFFFFFFF).hex()})
                builds[0]["equipment"] = b"".join(
                    proto_field(10, proto_field(8, 90000 + i) + proto_field(16, slot))
                    for i, (_, slot) in enumerate(equipment)
                ).hex()
                character["builds"] = builds
            return effective(character, *args, **kwargs)

        captured = []
        fixture = self.fixture

        def with_variant(passives=(), *, actives=()):
            return fixture(passives, actives=tuple(actives) + (6913,))

        adopt = self.adopt

        def capture(data, fight):
            result = adopt(data, fight)
            captured.append(result)
            return result

        with patch.object(
            equipment_stats, "effective_character", equipped
        ), patch.object(self, "adopt", capture), patch.object(
            self, "fixture", with_variant
        ):
            self.test_three_spatially_separated_companions_use_actual_two_ap_casts()
        data = captured[-1]
        self.assertGreaterEqual(data[2].actors[7].ap, 3)
        before_ap = data[2].actors[7].ap
        before_turn = data[2].turn_id
        before_roster = tuple(data[2].actors)
        with self.assertRaisesRegex(ValueError, "maximum casts per turn"):
            self.cast(data, 6914, target=data[2].actors[-7].position)
        self.assertEqual(data[2].actors[7].ap, before_ap)
        self.assertEqual(data[2].turn_id, before_turn)
        self.assertEqual(tuple(data[2].actors), before_roster)
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference == 344157:
                trace.append(result)
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            # Three6914 casts exhaust its native per-turn usage. A distinct
            # actual owned6913 (3AP) shares the companion capacity predicate.
            fourth = self.cast(data, 6913, target=data[2].actors[-7].position)
        companions = [
            a
            for a in fourth.fight.actors.values()
            if a.hp > 0 and any(s.reference == 6288 for s in a.state_ledger.entries)
        ]
        self.assertEqual(len(companions), 3)
        self.assertEqual(fourth.fight.actors[7].ap, before_ap - 3)
        self.assertIn(False, trace)
        self.assertNotIn(True, trace)
