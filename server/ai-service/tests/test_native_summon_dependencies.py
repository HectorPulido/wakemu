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

    def test_authored_parent_and_source_registered_levels_preserve_actual_book(self):
        for level in (0, 9, 215, 32767):
            fight, actor, monsters, policy, book = self.fixture()
            fight.actors[-200].effective_level = 215
            actor.effective_level = level
            actor.native_summon_source["level"] = level
            fight.native_summon_registrations[901]["authority"][
                "native_real_level"
            ] = level
            book["actions"][0]["level"] = level
            with self.subTest(level=level):
                self.assertTrue(
                    self.check(fight, actor, monsters, policy, book, level=level)
                )
                self.assertFalse(
                    self.check(fight, actor, monsters, policy, book, level=level + 1)
                )

    def test_actual_native_profile_book_attests_overridden_descriptor_grade(self):
        from wakfu_server.combat_summon_spellbook import fresh_action_book

        fight, actor, monsters, policy, _ = self.fixture()
        fight.actors[-200].effective_level = 215
        actor.effective_level = 215
        actor.native_summon_source["level"] = 215
        fight.native_summon_registrations[901]["authority"]["native_real_level"] = 215
        profiles = {
            "735": {
                "abilities": [
                    dict(
                        reference=1948,
                        casting_uid=1948,
                        override_level=-1,
                        maximum_level=200,
                    )
                ]
            }
        }
        actor.native_summon_action_book = fresh_action_book(735, 215, profiles=profiles)
        with patch(
            "wakfu_server.combat_summon_spellbook.profile_abilities",
            return_value=profiles,
        ):
            self.assertTrue(
                registered_dependency_enabled(fight, actor, monsters, policy, 1948, 200)
            )
            self.assertFalse(
                registered_dependency_enabled(fight, actor, monsters, policy, 1948, 215)
            )
            actor.native_summon_action_book["actions"][0]["level"] = 215
            with self.assertRaisesRegex(
                ValueError, "changed fresh native summon action book"
            ):
                registered_dependency_enabled(fight, actor, monsters, policy, 1948, 215)

    def test_malformed_actor_levels_never_gain_dependency_imports(self):
        for kind in ("parent", "summon"):
            for level in (-1, 32768, True, 2.0):
                fight, actor, monsters, policy, book = self.fixture()
                if kind == "parent":
                    fight.actors[-200].effective_level = level
                else:
                    actor.effective_level = level
                    actor.native_summon_source["level"] = level
                    fight.native_summon_registrations[901]["authority"][
                        "native_real_level"
                    ] = level
                with self.subTest(kind=kind, level=level):
                    if kind == "summon" and type(level) is not int:
                        with self.assertRaisesRegex(
                            ValueError, "registered summon authority"
                        ):
                            self.check(fight, actor, monsters, policy, book)
                    else:
                        self.assertFalse(
                            self.check(fight, actor, monsters, policy, book)
                        )

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
