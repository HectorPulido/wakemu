"""Actual private839 handler and builder using sealed1549, no engine admission."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import wakfu_server

P = Path(__file__).parent / "fixtures/native_monster_recovery"
from test_combat_target_copy_creation import TargetCopyCreationTests
from wakfu_server.combat_three_spell_copy_handler import NativeThreeSpellCopyHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_character_copy_metadata import native_copy_characteristics


class Actual839Tests(unittest.TestCase):
    def fixture(self):
        helper = TargetCopyCreationTests()
        self.addCleanup(helper.doCleanups)
        supplied = (P / "native1549-builder-fixture.json").read_text()
        original = Path.read_text

        def read(path, *a, **kw):
            if path.name == "monster_target_copy2349_native.json":
                return supplied
            return original(path, *a, **kw)

        with patch.object(Path, "read_text", read):
            fight, old, packets, records = helper.fixture()
        cls = NativeThreeSpellCopyHandler
        handler = cls.__new__(cls)
        handler.__dict__.update(old.__dict__)
        metadata = dict(
            definitions=handler.casting_definitions,
            effects=handler.source_effects,
            flags=json.loads(supplied)["copy_book_flags"]["spells"],
        )
        patched = patch(
            "wakfu_server.combat_three_spell_copy_runtime_book._metadata",
            return_value=metadata,
        )
        patched.start()
        self.addCleanup(patched.stop)
        return fight, handler, packets, records

    def test_native1549_constructor_retains_borrowed_uid_capacity_and_self_controller(
        self,
    ):
        fight, handler, packets, records = self.fixture()
        self.assertTrue(
            handler(
                dict(effect_class=839, parameters=[], target_masks=(None,) * 7),
                {},
                EffectInvocation(388786, 1, -7, 7, (1, 1, 0)),
            )
        )
        created = fight.actors[902]
        self.assertEqual(created.native_summon_source["ref"], 1549)
        self.assertEqual(created.position, fight.actors[-7].position)
        self.assertEqual(created.native_controller_id, created.id)
        self.assertEqual(created.native_copy_pa_source["native_copy_family"], 839)
        book = created.native_summon_action_book["actions"]
        self.assertLessEqual(len(book), 3)
        self.assertTrue(book)
        self.assertTrue({r["uid"] for r in book} <= {r[0] for r in records})
        self.assertEqual([opcode for opcode, _ in packets], [12613])
        proof = created.native_character_copy_book_source
        from wakfu_server.combat_three_spell_copy_runtime_book import (
            validated_target_copied_action_book,
        )

        self.assertEqual(
            len(
                validated_target_copied_action_book(
                    created, created.native_summon_source
                )["actions"]
            ),
            len(book),
        )
        self.assertEqual(proof["source_actor_id"], 7)
        self.assertEqual(
            created.native_summon_source["native_copy_effect_reference"], 388786
        )
        self.assertEqual(created.native_copy_pa_source["source_actor_id"], 7)

    def test_npc_target_rejects_before_allocation_or_creation(self):
        fight, handler, packets, _ = self.fixture()
        before = set(fight.actors)
        with self.assertRaisesRegex(ValueError, "connected class target-copy source"):
            handler(
                dict(effect_class=839, parameters=[], target_masks=(None,) * 7),
                {},
                EffectInvocation(388786, 1, 7, -7, (1, 1, 0)),
            )
        self.assertEqual(set(fight.actors), before)
        self.assertEqual(packets, [])

    def test_actual_created_copy_death_retires_self_controller_and_releases_qi(self):
        old, handler, packets, _ = self.fixture()
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
            current_registry,
        )

        fight = Fight(
            839,
            list(old.actors.values()),
            old.walkable,
            {0: {(0, 0, 0)}, 1: {(3, 3, 0)}},
        )
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0] * 16
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0})
        )
        fight.ready(1)
        handler.fight = fight
        handler(
            dict(effect_class=839, parameters=[], target_masks=(None,) * 7),
            {},
            EffectInvocation(388786, 1, -7, 7, (1, 1, 0)),
        )
        created = fight.actors[902]
        slot = created.native_obstacle_id
        from wakfu_server.combat_summon_retirement import _registration

        self.assertEqual(_registration(fight, created.id)[-2:], (False, True))
        fight.apply_effect_damage(7, created.id, created.hp)
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(created.id)],
            "OUT_OF_PLAY",
        )
        self.assertTrue(fight.native_summon_retirements[created.id]["copied"])
        self.assertEqual(created.native_obstacle_id, -1)
        self.assertIn(7, fight.actors)
        self.assertIn(-7, fight.actors)
