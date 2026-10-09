import unittest
from itertools import count
from types import SimpleNamespace as N
from wakfu_server.combat_morph_spellbook import (
    build_morph_book,
    install_morph_book,
    remove_morph_book,
    active_morph_book,
    resolve_morph_action,
)
from wakfu_server.combat_morph_handler import NativeMorphHandler, remove_morph_effect
from wakfu_server.combat_spell_level import NativeSpellBook
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_removal import _identity_fields


class MorphSpellbookTests(unittest.TestCase):
    def profile(self, identity=5900):
        return dict(
            profile_id=identity,
            minimum_level=12,
            abilities=[
                dict(
                    reference=91, casting_uid=91, override_level=999, maximum_level=20
                ),
                dict(
                    reference=92, casting_uid=92, override_level=999, maximum_level=200
                ),
            ],
        )

    def test_direct_bpo_clamp_order_duplicates_and_capacity(self):
        profile = self.profile()
        self.assertEqual(build_morph_book(profile, 50), {91: 20, 92: 50})
        profile["abilities"] = [profile["abilities"][0]] * 2 + [
            dict(reference=i, casting_uid=i, maximum_level=200) for i in range(100, 190)
        ]
        book = build_morph_book(profile, 50)
        self.assertEqual(len(book), 80)
        self.assertEqual(tuple(book)[:2], (91, 100))
        self.assertNotIn(179, book)

    def test_temporary_pointer_preserves_player_progression_and_base(self):
        actor = N(id=7, effective_level=50)
        fight = N(actors={7: actor})
        base = NativeSpellBook({12: 50}, True, {12: 50, 91: 17}, 15)
        install_morph_book(fight, actor, self.profile(), own_level=True, uid=501)
        switched = active_morph_book(fight, 7, base)
        self.assertEqual(switched.level(91), 15)
        self.assertEqual(switched.level(92), -1)
        self.assertEqual(resolve_morph_action(fight, 7, 91), (91, 20))
        with self.assertRaises(ValueError):
            resolve_morph_action(fight, 7, (7 << 32) | 12)
        remove_morph_book(fight, 7)
        self.assertIs(active_morph_book(fight, 7, base), base)
        self.assertEqual(base.levels, {12: 50})

    def test_grants_and_raw_removal_follow_current_book_without_base_leak(self):
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_spell_grant_book import (
            merged_grant_book,
            register_raw_removal,
        )

        actor = N(id=7, effective_level=50)
        base_grant = dict(uid=12, reference=12, level=40)
        fight = N(
            actors={7: actor},
            native_spell_grants={7: {12: base_grant}},
            native_removed_spell_uids={7: {92}},
        )
        base = NativeSpellBook({10: 50}, True, {10: 50}, -1)
        install_morph_book(fight, actor, self.profile(), own_level=True, uid=501)
        self.assertEqual(granted_spells(fight, 7), {})
        self.assertEqual(active_morph_book(fight, 7, base).levels, {91: 20, 92: 50})
        granted_spells(fight, 7)[93] = dict(uid=93, reference=93, level=15)
        register_raw_removal(fight, 7, 91)
        current = merged_grant_book(fight, 7, active_morph_book(fight, 7, base))
        self.assertEqual(current.levels, {92: 50, 93: 15})
        with self.assertRaises(ValueError):
            resolve_morph_action(fight, 7, 91)
        self.assertEqual(resolve_morph_action(fight, 7, 93), (93, 15))
        install_morph_book(fight, actor, self.profile(), own_level=False, uid=502)
        self.assertEqual(granted_spells(fight, 7), {})
        self.assertEqual(resolve_morph_action(fight, 7, 91), (91, 12))
        remove_morph_book(fight, 7)
        self.assertEqual(granted_spells(fight, 7), {12: base_grant})
        self.assertEqual(fight.native_removed_spell_uids, {7: {92}})

    def test_actual_cast_resolver_uses_raw_form_uid_and_owner_account(self):
        from wakfu_server.combat_cast import resolve_owned_spell_action

        actor = N(id=7, effective_level=50, controlled=True, owner_id=3, hp=100)
        fight = N(actors={7: actor}, phase="active", current=actor)
        character = dict(id=7, breed=11, level=50)
        install_morph_book(fight, actor, self.profile(), own_level=True, uid=501)
        request = dict(actor_id=7, spell_uid=91)
        self.assertEqual(
            resolve_owned_spell_action(request, character, fight, 3, b""),
            (actor, 91, 20),
        )
        with self.assertRaisesRegex(ValueError, "owned active actor"):
            resolve_owned_spell_action(request, character, fight, 4, b"")
        with self.assertRaisesRegex(ValueError, "temporary transformation book"):
            resolve_owned_spell_action(
                dict(actor_id=7, spell_uid=(7 << 32) | 91), character, fight, 3, b""
            )

    def test_full_form_grant_native_null_object_does_not_remove_later_book(self):
        import test_combat_spell_grant as grant_fixture
        from wakfu_server.combat_spell_grant import granted_spells, remove_spell_grant

        fixture = grant_fixture.SpellGrantTests()
        fixture.setUp()
        actor = fixture.fight.actors[7]
        profile = self.profile()
        profile["abilities"] = [
            dict(reference=i, casting_uid=i, maximum_level=200) for i in range(100, 180)
        ]
        install_morph_book(fixture.fight, actor, profile, own_level=True, uid=501)
        self.assertTrue(fixture.apply(5345))
        self.assertNotIn(5345, granted_spells(fixture.fight, 7))
        self.assertFalse(
            fixture.fight.owned_stat_effects[101]["native_spell_object_present"]
        )
        remove_spell_grant(fixture.handler, 101)
        self.assertEqual(
            fixture.fight.native_morph_spellbooks[7]["removed_raw_uids"], set()
        )

    def test_application_wire_mode_and_old_carrier_removes_current_book(self):
        actor = N(id=7, effective_level=50)
        fight = N(id=77, actors={7: actor}, owned_stat_effects={})
        packets, ids = [], count(501)
        handler = NativeMorphHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(ids),
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0.5,
            profiles={"5900": self.profile()},
        )
        definition = dict(
            effect_class=933,
            parameter_count=2,
            parameters=[5900, 0, 1, 0],
            target_masks=[[], [], [], [], [], [], []],
        )
        invocation = EffectInvocation(416860, 20, 7, 7, (0, 0, 0))
        self.assertTrue(handler(definition, {}, invocation))
        self.assertEqual(fight.native_morph_spellbooks[7]["levels"], {91: 20, 92: 50})
        payload = bytes.fromhex(fight.owned_stat_effects[501]["payload"])
        messages = {}
        _identity_fields(payload, messages=messages)
        self.assertEqual(_identity_fields(messages[8], integer_fields=(14,)), {14: 1})
        definition["parameters"][2] = 0
        self.assertTrue(handler(definition, {}, invocation))
        self.assertEqual(fight.native_morph_spellbooks[7]["levels"], {91: 12, 92: 12})
        remove_morph_effect(handler, 501)
        self.assertEqual(fight.native_morph_spellbooks, {})
        self.assertIn(502, fight.owned_stat_effects)
        self.assertEqual([kind for kind, _ in packets], [12613, 12613, 13560])
        self.assertEqual(handler.prepared, {})
        self.assertEqual(packets[0][1][12], 0)
        self.assertEqual(packets[0][1][19:], payload)
