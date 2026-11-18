"""Review-bound null-cell handling for an owned native self carrier."""

from contextlib import contextmanager
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from wakfu_server.combat.combat_casting_context import NativeOwnedCastingContext
from wakfu_server.combat.combat_casting_eligibility import (
    NativeCastingFlags,
    _native_casting_eligibility,
)
from wakfu_server.combat.combat_scene_cellless_casting import authorized, declarations


class CelllessCastingTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            spell_id=5620,
            level=0,
            state_id=4063,
            form_reference=3891,
            source_sha256="a" * 64,
            evidence="reviewed native zero-range self carrier",
        )
        self.descriptor = dict(full_room_scope=True, reviewed_cellless_casts=[self.row])
        self.actor = SimpleNamespace(
            id=71,
            owner_id=19,
            controlled=True,
            native_summon_source=None,
            position=(4, -2, 1),
            state_ledger=SimpleNamespace(
                entries=[
                    SimpleNamespace(reference=4063, uid=9801),
                ]
            ),
        )
        self.scene = dict(
            descriptor=self.descriptor,
            sha256="b" * 64,
        )
        self.fight = SimpleNamespace(
            native_encounter_scene=self.scene,
            native_controlled_scene_state_receipt=dict(
                actor_id=71,
                scene_sha256="b" * 64,
                programs=[dict(state_id=4063)],
                state_uids=[9801],
            ),
            actors={71: self.actor},
            phase="active",
            current=self.actor,
        )
        self.invocation = SimpleNamespace(caster_id=71, target_id=71, cell=(4, -2, 1))
        self.plan = dict(spell_id=5620, evaluation_level=0)
        self.rule = dict(
            minimum=0,
            maximum=0,
            line_of_sight=False,
            free_cell=False,
            forbid_QI_P=False,
            allow_self=False,
            cast_criterion_native_present=True,
            cast_criterion_raw="IsOnCell(self)",
        )

    @contextmanager
    def pinned_source(
        self, *, descriptor=None, morph=3891, digest="a" * 64, root_mask=64
    ):
        policy = ModuleType("wakfu_server.combat.combat_encounter_scene_policy")
        policy.frozen_scene = (
            lambda _fight: self.descriptor if descriptor is None else descriptor
        )
        morph_module = ModuleType("wakfu_server.combat.combat_morph_spellbook")
        morph_module.morph_record = lambda _fight, _actor: {"profile_id": morph}
        root = dict(
            native_casting_collision_area=None,
            native_selector_present=True,
            native_target_selector={"class": "fcE", "mask": root_mask},
        )
        record = dict(table={"level": [0, 0]}, roots={"1234": root})
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.combat.combat_encounter_scene_policy": policy,
                "wakfu_server.combat.combat_morph_spellbook": morph_module,
            },
        ), patch(
            "wakfu_server.combat.combat_scene_cellless_casting.source_digest",
            return_value=digest,
        ), patch(
            "wakfu_server.combat.combat_scene_cellless_casting.source_record",
            return_value=record,
        ):
            yield

    def context(self, *, cell=None, normal=True):
        context = NativeOwnedCastingContext(
            SimpleNamespace(),
            self.fight,
            self.plan,
            self.invocation,
            None,
            self.rule,
        )
        context.normal_mode = normal
        if cell is not None:
            context.cell = tuple(cell)
        return context

    def test_authority_requires_the_owned_self_state_matching_form_and_safe_native_roots(
        self,
    ):
        with self.pinned_source():
            self.assertTrue(authorized(self.context()))
            self.assertTrue(declarations(self.descriptor))
            self.assertFalse(authorized(self.context(cell=(5, -2, 1))))
            with self.assertRaisesRegex(ValueError, "original player/form/source"):
                with self.pinned_source(morph=3890):
                    authorized(self.context())
            with self.assertRaisesRegex(ValueError, "original player/form/source"):
                with self.pinned_source(digest="c" * 64):
                    authorized(self.context())
            with self.assertRaisesRegex(ValueError, "SELF actor root"):
                with self.pinned_source(root_mask=66):
                    authorized(self.context())

            self.actor.controlled = False
            with self.assertRaisesRegex(ValueError, "original player/form/source"):
                authorized(self.context())
            self.actor.controlled = True
            self.fight.native_controlled_scene_state_receipt["state_uids"] = []
            with self.assertRaisesRegex(ValueError, "original player/form/source"):
                authorized(self.context())

    def test_cellless_marker_is_temporary_and_does_not_skip_global_criterion(self):
        captured = []
        context = self.context()
        with self.pinned_source():
            with patch(
                "wakfu_server.combat.combat_casting_context.cast_cell_condition",
                side_effect=lambda _adapter, _fight, _plan, _actor, cell: captured.append(
                    cell
                )
                or SimpleNamespace(),
            ), patch(
                "wakfu_server.combat.combat_casting_context.evaluate_condition",
                return_value=False,
            ), patch(
                "wakfu_server.combat.combat_casting_context.native_casting_eligibility",
                side_effect=lambda hooks, _flags, trace=None: _native_casting_eligibility(
                    hooks, NativeCastingFlags()
                ),
            ):
                self.assertEqual(context.eligibility(), "twV")
            self.assertEqual(captured, [None])
            self.assertEqual(context.cell, self.actor.position)
            self.assertFalse(context._reviewed_cellless_validation)

            with patch(
                "wakfu_server.combat.combat_casting_context.cast_cell_condition",
                side_effect=lambda _adapter, _fight, _plan, _actor, cell: captured.append(
                    cell
                )
                or SimpleNamespace(),
            ), patch(
                "wakfu_server.combat.combat_casting_context.evaluate_condition",
                side_effect=RuntimeError("condition failure"),
            ), patch(
                "wakfu_server.combat.combat_casting_context.native_casting_eligibility",
                side_effect=lambda hooks, _flags, trace=None: _native_casting_eligibility(
                    hooks, NativeCastingFlags()
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "condition failure"):
                    context.eligibility()
            self.assertFalse(context._reviewed_cellless_validation)

    def test_unmarked_or_non_normal_context_keeps_ordinary_qi_requirement(self):
        context = self.context(normal=False)
        self.fight.native_qi_snapshot = None
        with self.pinned_source():
            self.assertFalse(authorized(context))
            with self.assertRaisesRegex(Exception, "Missing actual native casting QI"):
                context.eligibility()
            self.assertFalse(context._reviewed_cellless_validation)

        self.fight.native_encounter_scene["descriptor"] = dict(full_room_scope=True)
        context = self.context()
        with self.pinned_source(
            descriptor=self.fight.native_encounter_scene["descriptor"]
        ):
            self.assertFalse(authorized(context))
            with self.assertRaisesRegex(Exception, "Missing actual native casting QI"):
                context.eligibility()

    def test_declaration_rejects_duplicate_or_unpinned_spell_records(self):
        duplicate = dict(
            self.descriptor, reviewed_cellless_casts=[self.row, dict(self.row)]
        )
        with self.assertRaisesRegex(ValueError, "exact reviewed native source"):
            declarations(duplicate)
        unscoped = dict(self.descriptor, full_room_scope=False)
        with self.assertRaisesRegex(ValueError, "exact reviewed native source"):
            declarations(unscoped)


if __name__ == "__main__":
    unittest.main()
