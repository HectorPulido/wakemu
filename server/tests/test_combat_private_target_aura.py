"""Actual detached constructor authority keeps eYJ faN outside global Qs."""
from dataclasses import replace
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch
import test_combat_maximum_detached_constructor as fixture
from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_target_aura import NativeTargetAuraConstruction
from wakfu_server.combat_private_target_aura import validate_private_target_aura
from wakfu_server.combat_retained_effects import (
    RetainedEffect,
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    register_owned_removals,
)


class PrivateTargetAuraTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DetachedMaximumConstructorTests()
        self.f.setUp()
        self.invocation = replace(
            self.f.f.invocation,
            reference=318679,
            level=1,
            native_running_uid=901,
            cell=(0, 0, 0),
        )
        self.registered = []
        self.handler = NativeEffectAreaHandler(
            self.f.f.fight,
            self.f.f.packets,
            action_id=1,
            allocate_uid=lambda: self.fail("Constructor identities must be reused"),
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            container=lambda _: (dict(container_type=None), None),
        )
        self.handler.target_aura_construction = lambda _: NativeTargetAuraConstruction(
            901, 902, self.f.actor.id, 1
        )
        self.handler.target_aura_applied = lambda *args: self.registered.append(
            args[-1]
        )
        self.handler.on_created = lambda _: self.fail(
            "Private aura must not run Qs callbacks"
        )
        self.definition = dict(
            type="AURA",
            raw_bde=-1,
            effect_ids=[],
            entry_masks=[],
            exit_masks=[],
            native_shape_class="anD",
        )

    def apply(self):
        with patch(
            "wakfu_server.combat_delivery_owners.owner_catalog",
            return_value={"effects": {"338": dict(runner="eYJ", bbA=True, bbB=True)}},
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1649": self.definition},
        ):
            return self.handler(
                dict(effect_class=338), dict(parameters=[1649]), self.invocation
            )

    def test_actual_constructor_creates_retained_private_aura_without_global_registration(
        self,
    ):
        with self.f.scope():
            self.assertTrue(self.apply())
        fight = self.f.f.fight
        self.assertEqual(fight.native_effect_areas, {})
        self.assertEqual(self.registered, [901])
        row = fight.native_owned_area_effects[901]
        self.assertEqual(validate_private_target_aura(fight, row)["reference"], 1649)
        self.assertEqual(row["area_uid"], 902)
        self.assertEqual(len(self.f.f.packets), 1)
        self.assertTrue(row["payload"])

    def test_unknown_provenance_or_global_membership_is_rejected(self):
        with self.f.scope():
            self.apply()
        fight = self.f.f.fight
        row = fight.native_owned_area_effects[901]
        row["native_private_area"]["source"] = "guessed"
        with self.assertRaises(ValueError):
            validate_private_target_aura(fight, row)

    def test_unscoped_constructor_remains_rejected(self):
        with self.assertRaises(ValueError):
            self.apply()

    def test_private_aura_removal_uses_owned_runner_without_global_area_callbacks(self):
        with self.f.scope():
            self.apply()
            fight = self.f.f.fight
            row = fight.native_owned_area_effects[901]
            row.update(
                native_manager_id=self.f.actor.id,
                native_manager_source="eYJ.PK.owner_on_caster",
            )
            entry = RetainedEffect(
                901,
                self.f.actor.id,
                338,
                318679,
                manager_id=self.f.actor.id,
                container_present=False,
            )
            view = NativeRetainedEffectView(
                fight, [entry], population_verified_complete=True
            )
            removal = NativeRetainedRemoval(view)
            packets = []
            register_owned_removals(
                removal,
                stat_handler=SimpleNamespace(fight=fight),
                packets=packets,
                action_id=1,
            )
            with patch(
                "wakfu_server.combat_effect_area.remove_owned_hour_area"
            ) as remove_area:
                removal.remove([901])
                remove_area.assert_not_called()
            self.assertEqual(fight.native_owned_area_effects, {})
            self.assertEqual(fight.native_effect_areas, {})
            self.assertEqual([opcode for opcode, _ in packets], [13560])

    def test_private_owned_record_roundtrip_preserves_identity_without_global_membership(
        self,
    ):
        with self.f.scope():
            self.apply()
        fight = self.f.f.fight
        row = fight.native_owned_area_effects[901]
        restored = json.loads(json.dumps(row))
        self.assertEqual(
            validate_private_target_aura(fight, restored), row["native_private_area"]
        )
        self.assertEqual(restored["payload"], row["payload"])
        self.assertEqual(fight.native_effect_areas, {})
        fight.native_effect_areas[902] = dict(uid=902)
        with self.assertRaises(ValueError):
            validate_private_target_aura(fight, restored)

    def test_actual_fight_checkpoint_snapshot_preserves_private_owned_row(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        with self.f.scope():
            self.apply()
        fight = self.f.f.fight
        saved = json.loads(json.dumps(snapshot(fight)))
        row = saved["native_owned_area_effects"]["901"]
        self.assertEqual(
            row["native_private_area"],
            fight.native_owned_area_effects[901]["native_private_area"],
        )
        self.assertEqual(
            row["payload"], fight.native_owned_area_effects[901]["payload"]
        )
        self.assertEqual(saved["native_effect_areas"], {})
