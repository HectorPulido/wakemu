"""Source-qualified pizza form and the unchanged native command-book lifecycle."""

from dataclasses import replace
from itertools import count
import json
from pathlib import Path
import struct
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from wakfu_server import native_order_trial_admission as admission
from wakfu_server import native_order_trial_form as form
from wakfu_server.combat_morph_handler import NativeMorphHandler, remove_morph_effect
from wakfu_server.combat_morph_spellbook import active_morph_book
from wakfu_server.combat_cast import resolve_owned_spell_action
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_spell_level import NativeSpellBook


class NativeOrderTrialFormTests(unittest.TestCase):
    def setUp(self):
        self.native = json.loads(
            Path(__file__)
            .with_name("fixtures")
            .joinpath("pizzlarva-native-form.json")
            .read_text()
        )
        self.value = admission.document()
        self.value["enabled"] = True
        self.profiles = self.native["morph_document"]["profiles"]

    def test_admission_document_mutations_do_not_change_sealed_default(self):
        changed = admission.document()
        self.assertFalse(changed["enabled"])
        changed["enabled"] = True
        changed["sources"]["hard"]["approaches"][0][0] += 100

        fresh = admission.document()
        self.assertFalse(fresh["enabled"])
        self.assertNotEqual(
            fresh["sources"]["hard"]["approaches"][0][0],
            changed["sources"]["hard"]["approaches"][0][0],
        )

    def proof(self, mode="hard"):
        source = self.value["sources"][mode]
        character = dict(
            id=7,
            account_id=3,
            instance_id=99,
            map_id=885,
            **dict(zip(("x", "y", "z"), source["approaches"][0]))
        )
        proof = admission.plan(
            self.value,
            character,
            struct.pack(">qHH", source["object_id"], 0, 0),
            native_source=self.native["mode_objects"][str(source["object_id"])],
        )
        return replace(proof, generation="selected-qa"), character

    def prepare(self, proof, character, **changes):
        return form.prepare_form(
            proof,
            encounter_id=77,
            character=character,
            value=self.value,
            profiles=self.profiles,
            **changes
        )

    def test_disabled_default_precedes_catalog_or_combat_mutation(self):
        proof, character = self.proof()
        with patch(
            "wakfu_server.combat_morph_spellbook.native_morph_profiles",
            side_effect=AssertionError("disabled content read"),
        ):
            with self.assertRaisesRegex(ValueError, "enabled selected"):
                form.prepare_form(proof, encounter_id=77, character=character)
        plan = self.prepare(proof, character)
        with self.assertRaisesRegex(ValueError, "owned instance"):
            form.apply_form(object(), plan, instance_id=99)

    def test_native_mode_owner_and_descriptor_level_are_immutable(self):
        for mode in ("normal", "hard"):
            proof, character = self.proof(mode)
            plan = self.prepare(proof, character)
            self.assertEqual(plan.mode, mode)
            self.assertEqual(plan.book, ((4535, 1), (4538, 1), (4537, 1), (4536, 1)))
            for changed in (
                replace(proof, generation=None),
                replace(proof, owner_id=8),
                replace(proof, instance_id=0),
                replace(proof, source_id=23626),
                replace(proof, effect_reference=1457),
                replace(proof, hard_mode=mode != "hard"),
                replace(proof, profile_sha256="0" * 64),
            ):
                with self.subTest(mode=mode, proof=changed), self.assertRaises(
                    ValueError
                ):
                    self.prepare(changed, character)

    def test_actual_native933_switch_blocks_class_book_then_removal_restores_it(self):
        proof, character = self.proof()
        plan = self.prepare(proof, character)
        actor = N(id=7, owner_id=3, effective_level=230, controlled=True, hp=2350)
        fight = N(
            id=77,
            actors={7: actor},
            owned_stat_effects={},
            phase="active",
            current=actor,
        )
        packets, ids = [], count(501)
        base = NativeSpellBook({12: 230}, True, {12: 230}, -1)
        handler = NativeMorphHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(ids),
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0.5,
            profiles=self.profiles,
        )
        original = self.native["morph_effect"]
        self.assertEqual(original["effect_class"], 933)
        self.assertTrue(
            handler(original, {}, EffectInvocation(118992, 1, 7, 7, (0, 0, 0)))
        )
        self.assertEqual(
            tuple(fight.native_morph_spellbooks[7]["levels"].items()), plan.book
        )
        self.assertEqual(base.levels, {12: 230})
        with self.assertRaisesRegex(ValueError, "not been removed"):
            form.restored_book(fight, plan, base)
        for ref in form.SPELLS:
            self.assertEqual(
                resolve_owned_spell_action(
                    dict(actor_id=7, spell_uid=ref), character, fight, 3, b""
                ),
                (actor, ref, 1),
            )
        with self.assertRaises(ValueError):
            resolve_owned_spell_action(
                dict(actor_id=7, spell_uid=(7 << 32) | 12), character, fight, 3, b""
            )
        remove_morph_effect(handler, 501)
        self.assertIs(form.restored_book(fight, plan, base), base)
        self.assertIs(active_morph_book(fight, 7, base), base)
        self.assertEqual([op for op, _ in packets], [12613, 13560])
