"""The native eZl post-factory callback is independent of cosmetic presence."""
from types import SimpleNamespace as NS
import unittest
from wakfu_server.combat_summon_visual_copy import install_summon_visual_copy


class NativeSummonFactoryControlOrderTests(unittest.TestCase):
    def test_factory_callback_runs_without_visual_or_equipment(self):
        actor = NS()
        calls = []
        self.assertFalse(
            install_summon_visual_copy(
                None,
                actor,
                None,
                None,
                after_common_factory=lambda: calls.append("lx_true"),
            )
        )
        self.assertEqual(calls, ["lx_true"])

    def test_existing_call_without_callback_preserves_visual_empty_return(self):
        self.assertFalse(install_summon_visual_copy(None, NS(), None, None))

    def test_callback_failure_propagates_to_transaction_rollback(self):
        def broken():
            raise ValueError("Missing native AI flag")

        with self.assertRaisesRegex(ValueError, "Missing native AI flag"):
            install_summon_visual_copy(
                None, NS(), None, None, after_common_factory=broken
            )

    def test_native_lx_true_occurs_after_common_visual_before_extra_3251_PJ(self):
        from unittest.mock import patch
        from test_combat_summon_visual_copy import NativeSummonVisualCopyTests
        from wakfu_server.combat_summon_visual_copy import plan_summon_visual_copy
        from wakfu_server.combat_character_copy_equipment import copied_equipment_source

        fixture = NativeSummonVisualCopyTests()
        fight, actor, caster, authority, appearance = fixture.fixture()
        events = []
        with patch(
            "wakfu_server.combat_character_copy_codec.connected_copy_appearance",
            return_value=appearance,
        ):
            actor.native_pending_summon_visual_copy = plan_summon_visual_copy(
                authority, fight, caster
            )
            actor.native_pending_summon_equipment_replication = copied_equipment_source(
                authority(fight, caster), caster.id
            )

            def after_factory():
                self.assertTrue(hasattr(actor, "native_summon_visual_copy"))
                self.assertFalse(
                    hasattr(actor, "native_summon_equipment_replication_source")
                )
                events.append("lx_true")

            install_summon_visual_copy(
                fight,
                actor,
                caster,
                authority,
                equipment_apply=lambda *_: events.append("PJ"),
                after_common_factory=after_factory,
            )
        self.assertEqual(events, ["PJ", "lx_true", "PJ"])
