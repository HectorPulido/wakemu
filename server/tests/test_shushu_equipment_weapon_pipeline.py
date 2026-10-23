"""Native Shushu gear exists before actual snapshot/Ready and weapon use."""
import struct
from random import Random
import unittest

import test_combat_aptitude_healing_runtime as healing_fixture
import test_combat_weapon as weapon_fixture
from wakfu_server import equipment_stats
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_weapon import prepare_server_weapon
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.health import maximum


SHUSHU_REFERENCES = (
    14667,
    18445,
    18446,
    18447,
    18448,
    18449,
    18450,
    18451,
    18452,
    18453,
    18454,
    18456,
    24063,
    29473,
    29474,
    29479,
    29480,
    29487,
    29488,
    29821,
    29822,
    29823,
    29824,
    29825,
    29826,
    29827,
    29828,
    29829,
    29830,
    31395,
)


def owned_weapon_character(reference, level=245):
    character = weapon_fixture.equipped(
        dict(
            id=7,
            account_id=3,
            map_id=1134,
            breed=11,
            level=level,
            hp=maximum(11, level),
            active_build_index=0,
        ),
        reference,
    )
    item = character["inventory_items"][0]
    from wakfu_server.element_selection import _required_counts

    counts = _required_counts(reference)
    for field in ("damage_elements", "resistance_elements"):
        item[field] = sum(1 << (i + 1) for i in range(counts[field]))
    return character


class ShushuEquipmentWeaponPipelineTests(unittest.TestCase):
    def test_all_thirty_owned_passive_projections_have_no_missing_effects(self):
        for reference in SHUSHU_REFERENCES:
            with self.subTest(reference=reference):
                character = owned_weapon_character(reference)
                projected = equipment_stats.bonuses(character)
                self.assertEqual(projected["unsupported"], [])
                self.assertEqual(projected["equipped_uids"], [1000])
                self.assertTrue(projected["stats"])
                self.assertTrue(projected["active_effects"])
                self.assertGreater(
                    equipment_stats.effective_character(character)["max_hp"],
                    maximum(11, 245),
                )

    def test_native_pinchu_passives_ready_and_normal_critical_weapon_commit_together(
        self,
    ):
        healing_fixture.AptitudeHealingRuntimeTests.setUpClass()
        helper = healing_fixture.AptitudeHealingRuntimeTests()
        # Native breed initialization can add innate HP after snapshot import.
        # Compare gear against the same complete Ready pipeline, not bare HP.
        control, _, _, _ = helper.fixture(
            active_spells=(),
            caster_aptitudes=(),
            injury=300,
            level=155,
            caster_breed=11,
            enemy_position=(-4, -7, -1),
            second_player_position=(-7, -7, -1),
            third_player_position=(-6, -7, -1),
            compact_arena=True,
        )
        bare_maximum = control.actors[7].max_hp
        heals = []
        for critical in (False, True):
            with self.subTest(critical=critical):
                character = owned_weapon_character(18445, 155)
                fight, characters, monster, decks = helper.fixture(
                    active_spells=(),
                    caster_aptitudes=(),
                    injury=300,
                    level=155,
                    caster_breed=11,
                    enemy_position=(-4, -7, -1),
                    second_player_position=(-7, -7, -1),
                    third_player_position=(-6, -7, -1),
                    compact_arena=True,
                    caster_character=character,
                )
                actor = fight.actors[7]
                self.assertEqual(actor.max_ap, 7)
                self.assertEqual(actor.effect_stats[27], 14)
                self.assertEqual(actor.effect_stats[21], 88)
                self.assertEqual(actor.effect_stats[22], 88)
                self.assertEqual(actor.effect_stats[23], 88)
                self.assertEqual(actor.max_hp, bare_maximum + 110)
                before = snapshot(fight)
                ally_hp, ap = fight.actors[9].hp, actor.ap
                transaction = prepare_server_weapon(
                    struct.pack(">qqbiih", 7, 1000, 15, *fight.actors[9].position),
                    characters[7],
                    {-7: monster},
                    fight,
                    3,
                    decks[7],
                    action_id=1,
                    line_of_sight=lambda *args: True,
                    critical=critical,
                    rng=Random(1),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                self.assertEqual(snapshot(fight), before)
                healed = transaction.fight.actors[9].hp - ally_hp
                self.assertGreater(healed, 55 if critical else 44)
                self.assertEqual(transaction.fight.actors[7].ap, ap - 5)
                runtime = RuntimeMessages(fight)
                packets = commit_spell_transaction(
                    runtime,
                    transaction,
                    stats_serializer=lambda *_args: b"native-weapon-stats",
                )
                self.assertEqual(runtime.fight.actors[9].hp, ally_hp + healed)
                self.assertTrue(any(opcode == 13509 for opcode, _ in packets))
                heals.append(healed)
        self.assertEqual(len(heals), 2)
        self.assertGreater(heals[1], heals[0])

    def test_native_shushu_damage_variants_keep_paid_normal_and_critical_paths(self):
        healing_fixture.AptitudeHealingRuntimeTests.setUpClass()
        helper = healing_fixture.AptitudeHealingRuntimeTests()
        for reference, level in ((14667, 109), (29474, 230)):
            hits = []
            for critical in (False, True):
                with self.subTest(reference=reference, critical=critical):
                    character = owned_weapon_character(reference, level)
                    fight, characters, monster, decks = helper.fixture(
                        active_spells=(),
                        caster_aptitudes=(),
                        level=level,
                        caster_breed=11,
                        enemy_position=(-8, -6, -1),
                        second_player_position=(-7, -7, -1),
                        third_player_position=(-6, -7, -1),
                        compact_arena=True,
                        caster_character=character,
                    )
                    before = snapshot(fight)
                    hp, ap = fight.actors[-7].hp, fight.actors[7].ap
                    transaction = prepare_server_weapon(
                        struct.pack(">qqbiih", 7, 1000, 15, *fight.actors[-7].position),
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=1,
                        line_of_sight=lambda *args: True,
                        critical=critical,
                        rng=Random(1),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                    self.assertEqual(snapshot(fight), before)
                    hit = hp - transaction.fight.actors[-7].hp
                    self.assertGreater(hit, 0)
                    self.assertEqual(transaction.fight.actors[7].ap, ap - 6)
                    runtime = RuntimeMessages(fight)
                    packets = commit_spell_transaction(
                        runtime,
                        transaction,
                        stats_serializer=lambda *_args: b"native-weapon-stats",
                    )
                    self.assertEqual(runtime.fight.actors[-7].hp, hp - hit)
                    self.assertTrue(any(opcode == 13509 for opcode, _ in packets))
                    hits.append(hit)
            self.assertEqual(len(hits), 2)
            self.assertGreater(hits[1], hits[0])
