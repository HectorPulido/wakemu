"""Exact native fbX.aE selection and Qs retirement for every carry consumer."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_carry_glyph_cleanup import (
    carried_glyphs,
    cleanup_carried_glyphs,
)


class CarryGlyphCleanupTests(unittest.TestCase):
    def test_only_owner_linked_displaced_glyph_is_retired(self):
        actor = SimpleNamespace(id=7, position=(3, 4, 0))
        rows = {
            uid: dict(
                uid=uid,
                reference=ref,
                owner_id=owner,
                native_area_contract=contract,
                native_geometry_reference=cell,
            )
            for uid, ref, owner, contract, cell in (
                (1, 101, 7, "faY", (1, 2, 0)),
                (2, 101, 7, "faY", (3, 4, 0)),
                (3, 101, 8, "faY", (1, 2, 0)),
                (4, 102, 7, "faY", (1, 2, 0)),
                (5, 101, None, "faY", (1, 2, 0)),
                (6, 101, 7, "faN", (1, 2, 0)),
            )
        }
        fight = SimpleNamespace(native_effect_areas=rows)
        catalog = {"101": {"raw_bdh": [1]}, "102": {"raw_bdh": []}}
        removed = []
        callbacks = SimpleNamespace(removed=lambda row: removed.append(row["uid"]))
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas", return_value=catalog
        ):
            self.assertEqual([row["uid"] for row in carried_glyphs(fight, actor)], [1])
            cleanup_carried_glyphs(fight, actor, callbacks=callbacks)
            self.assertEqual(removed, [1])
            self.assertEqual(set(rows), {2, 3, 4, 5, 6})
            self.assertEqual(
                cleanup_carried_glyphs(fight, actor, callbacks=callbacks), ()
            )

    def test_environment_and_unrelated_glyph_need_no_cleanup_authority(self):
        actor = SimpleNamespace(id=7, position=(3, 4, 0))
        fight = SimpleNamespace(
            native_effect_areas={
                1: dict(uid=1, reference=910, owner_id=None, native_area_contract="faY")
            }
        )
        self.assertEqual(cleanup_carried_glyphs(fight, actor, callbacks=None), ())
