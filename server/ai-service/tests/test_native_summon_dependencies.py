"""Registered NPC dependencies never grant wild or player class imports."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.native.native_summon_dependencies import registered_dependency_enabled


class NativeSummonDependencyTests(unittest.TestCase):
    def fixture(self):
        root = SimpleNamespace(id=-200, controlled=False, effective_level=1)
        summon = SimpleNamespace(
            id=901,
            controlled=False,
            effective_level=8,
            team=1,
            position=(0, 1, 0),
            native_summon_source=dict(
                ref=735,
                level=8,
                direction=1,
                caster_id=-200,
                controller_id=-200,
                native_relation_source="big.new_bje.fdt_initial_registration",
            ),
        )
        registration = dict(
            actor_id=901,
            caster_id=-200,
            controller_id=-200,
            authority=dict(
                is_summon=True,
                is_player=False,
                breed_id=735,
                native_real_level=8,
                native_instance_id=1134,
            ),
        )
        fight = SimpleNamespace(
            actors={-200: root, 901: summon},
            native_summon_registrations={901: registration},
        )
        monsters = {-200: dict(id=-200, ref=2819)}
        policy = dict(
            schema="native-npc-activation-v1",
            enabled_monsters={
                "2819": dict(
                    min_level=1,
                    max_level=1,
                    spell_ids=[4627],
                    registered_summon_profiles={
                        "735": dict(
                            min_level=8,
                            max_level=8,
                            descriptor_levels=[8],
                            spell_ids=[1948],
                        )
                    },
                )
            },
        )
        book = dict(actions=[dict(reference=1948, level=8)])
        return fight, summon, monsters, policy, book

    def check(self, fight, actor, monsters, policy, book, spell=1948, level=8):
        with patch(
            "wakfu_server.combat_summon_spellbook.actor_action_book", return_value=book
        ):
            return registered_dependency_enabled(
                fight, actor, monsters, policy, spell, level
            )

    def test_actual_registration_parent_scope_and_book_authorize_dependency(self):
        self.assertTrue(self.check(*self.fixture()))

    def test_player_class_root_never_gains_dependency_imports(self):
        args = self.fixture()
        args[0].actors[-200].controlled = True
        self.assertFalse(self.check(*args))

    def test_unrelated_root_or_profile_is_rejected(self):
        for change in ("root", "profile", "wild", "controlled"):
            fight, actor, monsters, policy, book = self.fixture()
            if change == "root":
                monsters[-200]["ref"] = 6
            elif change == "profile":
                actor.native_summon_source["ref"] = 736
                fight.native_summon_registrations[901]["authority"]["breed_id"] = 736
            elif change == "wild":
                fight.native_summon_registrations.clear()
            else:
                actor.controlled = True
            with self.subTest(change=change):
                self.assertFalse(self.check(fight, actor, monsters, policy, book))

    def test_unowned_spell_or_level_cannot_be_imported(self):
        args = self.fixture()
        self.assertFalse(self.check(*args, spell=9999))
        self.assertFalse(self.check(*args, level=9))

    def test_out_of_scope_descriptor_and_parent_levels_are_rejected(self):
        for change in ("parent", "summon"):
            fight, actor, monsters, policy, book = self.fixture()
            if change == "parent":
                fight.actors[-200].effective_level = 2
            else:
                actor.effective_level = 9
                actor.native_summon_source["level"] = 9
                fight.native_summon_registrations[901]["authority"][
                    "native_real_level"
                ] = 9
            with self.subTest(change=change):
                self.assertFalse(self.check(fight, actor, monsters, policy, book))

    def test_missing_caster_and_cyclic_chains_are_rejected(self):
        for caster in (999, 901):
            fight, actor, monsters, policy, book = self.fixture()
            actor.native_summon_source["caster_id"] = caster
            fight.native_summon_registrations[901]["caster_id"] = caster
            with self.subTest(caster=caster):
                self.assertFalse(self.check(fight, actor, monsters, policy, book))

    def test_changed_actual_registration_fails_closed(self):
        fight, actor, monsters, policy, book = self.fixture()
        fight.native_summon_registrations[901]["authority"]["breed_id"] = 736
        with self.assertRaisesRegex(ValueError, "registered summon authority"):
            self.check(fight, actor, monsters, policy, book)

    def test_scope_must_cover_complete_native_book(self):
        fight, actor, monsters, policy, book = self.fixture()
        book["actions"].append(dict(reference=1999, level=8))
        self.assertFalse(self.check(fight, actor, monsters, policy, book))


if __name__ == "__main__":
    unittest.main()
