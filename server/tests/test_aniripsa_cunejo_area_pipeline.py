"""Naturaleza Muerta death glyph through actual area-enabled turn providers."""
import os
import struct
import unittest

import test_aniripsa_grant_summon_pipeline as grant_fixture
from wakfu_server.combat_server_spell import prepare_server_spell


class AreaEnabledFixture:
    fixture = grant_fixture.AniripsaGrantSummonPipelineTests.fixture
    cast = grant_fixture.AniripsaGrantSummonPipelineTests.cast
    adopt = grant_fixture.AniripsaGrantSummonPipelineTests.adopt
    next_player_turn = grant_fixture.AniripsaGrantSummonPipelineTests.next_player_turn
    assertEqual = staticmethod(unittest.TestCase().assertEqual)
    assertTrue = staticmethod(unittest.TestCase().assertTrue)
    fail = staticmethod(unittest.TestCase().fail)

    def end_current_turn(self, fight, fixture):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from combat_audit_turns import advance_actual_turn

        character, monster, _, deck, rng = fixture
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                character, {-7: monster}, p, deck, rng=rng, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                character, {-7: monster}, p, deck, rng=rng, area_callbacks=True, **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )[0],
        )
        advance_actual_turn(runtime)


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaCunejoAreaPipelineTests(unittest.TestCase):
    def kill_summon(self, helper, fixture):
        summon = next(
            a
            for a in fixture[2].actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        )
        for _ in range(40):
            character, monster, fight, deck, rng = fixture
            try:
                transaction = prepare_server_spell(
                    struct.pack(">qqiih", 7, (7 << 32) | 630, *summon.position),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=50 + fight.turn_id,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=rng,
                )
            except ValueError as exc:
                if "resources" not in str(exc) and "maximum casts" not in str(exc):
                    raise
                helper.next_player_turn(fight, fixture)
                continue
            fixture = helper.adopt(fixture, transaction.fight)
            if transaction.fight.actors[summon.id].hp == 0:
                return fixture
        self.fail("Actual summon death exceeded legal turn budget")

    def test_actual_turn_heals_applies_guard_and_next_death_replaces_old_area(self):
        helper = AreaEnabledFixture()
        fixture = helper.fixture(passives=(5455,))
        # Injured fixture: the glyph must produce observable healing.
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        set_hp_raw_current(fixture[2].actors[7], 100)
        fixture = helper.adopt(fixture, helper.cast(fixture, 7978, (-8, -6, -1)).fight)
        fixture = self.kill_summon(helper, fixture)
        fight = fixture[2]
        first_uid = next(iter(fight.native_effect_areas))
        from wakfu_server.combat_effect_area_queries import own_specific_area

        self.assertTrue(
            own_specific_area(
                fight,
                reference=1814,
                selector="target",
                caster_id=7,
                target_id=first_uid,
                cell=None,
            )
        )
        self.assertFalse(
            own_specific_area(
                fight,
                reference=1814,
                selector="target",
                caster_id=-7,
                target_id=first_uid,
                cell=None,
            )
        )
        self.assertEqual(fight.actors[7].hp, 100)
        helper.next_player_turn(fight, fixture)
        # Native1084 light healing: p0=4+0.1*200=24, mastery yields31.
        self.assertEqual(fight.actors[7].hp, 131)
        self.assertIn(3918, {s.reference for s in fight.actors[7].state_ledger.entries})
        # Native area1814 has unlimited charges; replacing it is explicit843.
        self.assertIn(first_uid, fight.native_effect_areas)
        guard_uid = next(
            s.uid for s in fight.actors[7].state_ledger.entries if s.reference == 3918
        )
        helper.next_player_turn(fight, fixture)
        self.assertNotIn(
            guard_uid, {s.uid for s in fight.actors[7].state_ledger.entries}
        )
        self.assertIn(3918, {s.reference for s in fight.actors[7].state_ledger.entries})
        self.assertLessEqual(
            max(
                s.level
                for s in fight.actors[7].state_ledger.entries
                if s.reference == 3869
            ),
            fight.actors[7].effective_level,
        )
        for _ in range(5):
            helper.next_player_turn(fight, fixture)
        fixture = helper.adopt(fixture, helper.cast(fixture, 7978, (-8, -6, -1)).fight)
        fixture = self.kill_summon(helper, fixture)
        areas = fixture[2].native_effect_areas
        self.assertNotIn(first_uid, areas)
        self.assertEqual(len(areas), 1)
        self.assertEqual(next(iter(areas.values()))["reference"], 1814)
        self.assertIn(first_uid, fixture[2].native_retired_area_managers)
