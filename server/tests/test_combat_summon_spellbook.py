"""Fresh class summon bPD identity, level selection and connected ownership."""
import struct
import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_summon_spellbook import (
    fresh_action_book,
    actor_spellbook,
    resolve_controlled_action,
)


PROFILES = {
    "900": {
        "abilities": [
            dict(reference=77, casting_uid=77, override_level=-1, maximum_level=245),
            dict(reference=88, casting_uid=88, override_level=0, maximum_level=245),
            dict(reference=99, casting_uid=99, override_level=20, maximum_level=10),
        ]
    }
}


class SummonSpellBookTests(unittest.TestCase):
    def setUp(self):
        self.profiles = patch(
            "wakfu_server.combat_summon_spellbook.profile_abilities",
            return_value=PROFILES,
        )
        self.profiles.start()
        self.addCleanup(self.profiles.stop)
        # The cast target lookup includes all live actors before selecting the
        # controlled summon, so supply the player's actual target facts too.
        self.player = SimpleNamespace(
            id=1, owner_id=3, controlled=True, hp=10, position=(1, 0, 0)
        )
        self.actor = self.summon(2)
        self.fight = SimpleNamespace(
            id=9,
            actors={1: self.player, 2: self.actor},
            phase="active",
            current=self.actor,
            native_summon_registrations={2: self.registration(self.actor)},
            walkable={(0, 0, 0), (1, 0, 0)},
        )

    def summon(self, identity):
        return SimpleNamespace(
            id=identity,
            owner_id=3,
            controlled=True,
            native_controller_id=1,
            hp=10,
            ap=6,
            mp=3,
            effective_level=200,
            position=(0, 0, 0),
            spell_ap_cost_modifiers={},
            native_summon_source=dict(
                ref=900,
                level=200,
                caster_id=1,
                controller_id=1,
                native_relation_source="big.new_bje.fdt_initial_registration",
            ),
            native_summon_action_book=fresh_action_book(900, 200),
        )

    def registration(self, actor):
        return dict(
            actor_id=actor.id,
            controller_id=actor.native_controller_id,
            authority=dict(
                is_summon=True,
                is_player=False,
                breed_id=900,
                native_real_level=200,
                native_controller_id=actor.native_controller_id,
                summon_root_id=1,
                targeting=dict(dpr_id=actor.native_controller_id),
            ),
        )

    def test_descriptor_override_zero_and_maximum_are_distinct(self):
        self.assertEqual(actor_spellbook(self.actor).levels, {77: 200, 88: 0, 99: 10})
        self.assertEqual(actor_spellbook(self.actor).level(123), 0)

    def test_native_short_zero_and_definition_cap(self):
        self.assertEqual(fresh_action_book(900, 0)["actions"][0]["level"], 0)
        self.assertEqual(fresh_action_book(900, 300)["actions"][0]["level"], 245)

    def test_same_raw_uid_belongs_to_each_scoped_instance(self):
        other = self.summon(4)
        self.fight.actors[4] = other
        self.fight.native_summon_registrations[4] = self.registration(other)
        for actor in (self.actor, other):
            self.assertEqual(
                resolve_controlled_action(self.fight, actor, 1, 3, 77), (77, 200)
            )

    def test_forged_actor_packed_uid_and_foreign_ability_rejected(self):
        for uid in ((2 << 32) | 77, 100, (1 << 32) | 77):
            with self.assertRaisesRegex(ValueError, "summon-owned action book"):
                resolve_controlled_action(self.fight, self.actor, 1, 3, uid)

    def test_removed_or_foreign_controller_rejected(self):
        del self.fight.actors[1]
        with self.assertRaisesRegex(ValueError, "no longer registered"):
            resolve_controlled_action(self.fight, self.actor, 1, 3, 77)
        self.fight.actors[1] = self.player
        self.player.owner_id = 4
        with self.assertRaisesRegex(ValueError, "another owner"):
            resolve_controlled_action(self.fight, self.actor, 1, 3, 77)

    def test_controller_cycle_rejected(self):
        self.actor.native_controller_id = 2
        self.actor.native_summon_source["controller_id"] = 2
        self.fight.native_summon_registrations[2] = self.registration(self.actor)
        with self.assertRaisesRegex(ValueError, "controller authority"):
            resolve_controlled_action(self.fight, self.actor, 1, 3, 77)

    def test_unregistered_actor_and_stale_relation_rejected(self):
        self.fight.native_summon_registrations = {}
        with self.assertRaisesRegex(ValueError, "controller authority"):
            resolve_controlled_action(self.fight, self.actor, 1, 3, 77)

    def test_changed_book_and_changed_profile_level_rejected(self):
        self.actor.native_summon_action_book["actions"][0]["level"] = 100
        with self.assertRaisesRegex(ValueError, "changed fresh"):
            actor_spellbook(self.actor)
        self.actor.native_summon_action_book = fresh_action_book(900, 200)
        self.actor.native_summon_source["level"] = 100
        with self.assertRaisesRegex(ValueError, "changed fresh"):
            actor_spellbook(self.actor)

    def test_known_empty_book_is_not_missing_profile(self):
        self.assertEqual(
            fresh_action_book(901, 20, profiles={"901": {"abilities": []}})["actions"],
            [],
        )
        with self.assertRaisesRegex(ValueError, "Missing scoped"):
            fresh_action_book(901, 20, profiles={})

    def test_duplicate_native_uid_is_not_silently_overwritten(self):
        with self.assertRaisesRegex(ValueError, "Invalid complete"):
            fresh_action_book(
                900,
                20,
                profiles={"900": {"abilities": [PROFILES["900"]["abilities"][0]] * 2}},
            )

    def test_native_zero_book_level_and_actual_actor_are_encoded(self):
        from wakfu_server.combat_spells import cast_animation, cast_notification

        source = dict(id=2)
        animation = cast_animation(
            1, 4, source, 88, (1, 0, 0), native_uid=88, native_level=0
        )
        notification = cast_notification(
            1, 4, source, 88, (1, 0, 0), native_uid=88, native_level=0
        )
        self.assertEqual(struct.unpack_from(">q", animation, 12)[0], 2)
        self.assertEqual(struct.unpack_from(">qih", animation, 20), (88, 88, 0))
        self.assertEqual(struct.unpack_from(">q", notification, 12)[0], 2)
        self.assertEqual(struct.unpack_from(">qih", notification, 26), (88, 88, 0))

    def test_critical_availability_requires_explicit_evaluated_domain(self):
        from wakfu_server.combat_critical import spell_critical_available

        records = {
            77: dict(
                critical_levels=[0, 245],
                evaluated_minimum_level=0,
                evaluated_maximum_level=245,
            ),
            88: dict(critical_levels=[1]),
        }
        with patch(
            "wakfu_server.combat_critical._spell_availability",
            return_value={str(key): value for key, value in records.items()},
        ):
            self.assertTrue(spell_critical_available(77, 0))
            self.assertTrue(spell_critical_available(77, 245))
            self.assertFalse(spell_critical_available(77, 200))
            for reference, level in ((77, 246), (88, 0), (88, 201)):
                with self.assertRaisesRegex(ValueError, "audited native"):
                    spell_critical_available(reference, level)

    def test_scoped_dependencies_compile_independently_of_grant_permissions(self):
        from wakfu_server.combat_native_spell_casting import merged_spell_effects

        merged_spell_effects.cache_clear()
        self.addCleanup(merged_spell_effects.cache_clear)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "native-class-summon-effect-closure.json").write_text(
                json.dumps(
                    dict(added_effect_ids=[10], effect_reference_closure=[10, 20, 30])
                )
            )
            (path / "native-class-spell-grant-closure.json").write_text(
                json.dumps(
                    dict(
                        schema="native-class-spell-grant-closure-v1",
                        effect_reference_closure=[30],
                    )
                )
            )
            with patch(
                "wakfu_server.combat_native_spell_casting.DATA_ROOT", path
            ), patch(
                "wakfu_server.spell_audit.catalog", return_value={"effects": {"1": {}}}
            ), patch(
                "wakfu_server.combat_captured_dependencies.merge_captured_effects",
                side_effect=lambda effects: effects,
            ), patch(
                "wakfu_server.combat_triggered_dependencies.merge_effects",
                side_effect=lambda effects: effects,
            ), patch(
                "wakfu_server.combat_morph_dependencies.merge_effects",
                side_effect=lambda effects: effects,
            ), patch(
                "wakfu_server.combat_native_spell_casting.granted_effect_catalog",
                return_value={"effects": {"10": {}, "20": {}, "40": {}}},
            ), patch(
                "wakfu_server.combat_native_spell_casting.enabled", return_value=False
            ):
                self.assertEqual(set(merged_spell_effects()), {"1", "10", "20"})

    def test_shared_request_uses_book_level_and_player_deck_is_not_a_gate(self):
        from wakfu_server.combat_cast import prepare_spell_cast
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from unittest.mock import Mock

        rule = dict(
            costs=dict(ap=2, mp=0, wp=0),
            roots=(123,),
            minimum=0,
            maximum=2,
            linear=False,
            diagonal=False,
            linear_path=False,
            path_option=False,
            range_modifiable=False,
            line_of_sight=False,
            free_cell=False,
            allow_self=False,
            forbid_QI_P=False,
        )
        body = struct.pack(">qqiih", 2, 99, 1, 0, 0)
        eligibility = Mock(
            return_value=dict(result="twD", aligned=True, target_id=None)
        )
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    actor_id=self.actor.id,
                    fight_properties=frozenset(),
                )
            },
            native_casting_query=eligibility,
        )
        with patch(
            "wakfu_server.combat_cast.validate_deck",
            side_effect=ValueError("No applicable player deck"),
        ), patch(
            "wakfu_server.combat_native_spell_casting.definition", return_value=rule
        ) as definition, patch(
            "wakfu_server.combat_casting_range.resolve_range", return_value=rule
        ), patch(
            "wakfu_server.combat_spell_grant.granted_spells", return_value={}
        ), patch(
            "wakfu_server.combat_spell_usage.validate_usage", return_value={}
        ):
            result = prepare_spell_cast(
                body,
                dict(id=1, breed=15, level=1),
                self.fight,
                3,
                b"invalid player deck",
                wp=0,
                line_of_sight=lambda *args: True,
                conditional_context=lambda *args: context,
            )
            self.assertEqual(result["evaluation_level"], 10)
            self.assertEqual(result["actor_id"], 2)
            self.assertEqual(definition.call_args.args[:2], (99, 10))
            eligibility.assert_called_once_with(rule, 99, 10)
            self.fight.current = self.player
            with self.assertRaisesRegex(ValueError, "owned active actor"):
                prepare_spell_cast(
                    body,
                    dict(id=1),
                    self.fight,
                    3,
                    b"",
                    wp=0,
                    line_of_sight=lambda *args: True,
                )

    def test_server_critical_and_wp_use_actual_actor_and_selected_book_level(self):
        from wakfu_server.combat_server_spell import prepare_server_spell

        self.actor.effect_stats = {4: 0}
        self.player.effect_stats = {4: 6}
        result = SimpleNamespace(plan={})
        decision = SimpleNamespace(critical=False, diagnostic=lambda: {})
        body = struct.pack(">qqiih", 2, 99, 1, 0, 0)
        with patch(
            "wakfu_server.combat_spell_grant.granted_spells", return_value={}
        ), patch(
            "wakfu_server.combat_critical.spell_critical_available", return_value=False
        ) as availability, patch(
            "wakfu_server.combat_critical.choose_critical", return_value=decision
        ) as choose, patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(object(), object()),
        ), patch(
            "wakfu_server.combat_server_spell.prepare_spell_transaction",
            return_value=result,
        ) as prepare:
            self.assertIs(
                prepare_server_spell(
                    body,
                    dict(id=1),
                    {},
                    self.fight,
                    3,
                    b"",
                    action_id=4,
                    line_of_sight=lambda *args: True,
                    critical=None,
                ),
                result,
            )
            availability.assert_called_once_with(99, 10)
            self.assertIs(choose.call_args.args[0], self.actor)
            self.assertEqual(prepare.call_args.kwargs["wp_current"], 0)


if __name__ == "__main__":
    unittest.main()
