"""Scaling-only placement uses the complete retained effect snapshot."""
import copy
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server import dungeon_combat_scaling as scaling
from wakfu_server.combat import combat_bootstrap, combat_remote_effects


class ScalingConstructorPublicationTests(unittest.TestCase):
    def setUp(self):
        profile = dict(
            schema_version=1, hp_percent=150, damage_percent=120, stasis_level=3
        )
        self.catalog = dict(
            schema_version=1,
            policy=scaling.POLICY,
            hp={"150": 10},
            damage={"120": [11]},
            effects={
                "10": dict(effect_class=16),
                "11": dict(effect_class=330, children=[12]),
                "12": dict(effect_class=430),
            },
        )
        self.fight = SimpleNamespace(
            id=7,
            phase="placement",
            actors={-2: SimpleNamespace(controlled=False)},
            native_dungeon_scaling_receipt=dict(
                policy=scaling.POLICY,
                fight_id=7,
                initialized=True,
                actor_ids=[-2],
                profile=profile,
                references=[10, 11],
                snapshot_sha256=hashlib.sha256(
                    json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            ),
        )

    def test_scaling_only_npc_publishes_retained_snapshot_without_ordinary_receipt(
        self,
    ):
        with patch(
            "wakfu_server.maps.dungeon_scaling_catalog.current",
            return_value=self.catalog,
        ), patch.object(
            combat_remote_effects, "_live_actor_effects", return_value=b"retained"
        ) as live:
            self.assertEqual(
                combat_remote_effects.initial_npc_actor_effects(self.fight, -2),
                b"retained",
            )
            live.assert_called_once_with(self.fight, -2)
        self.assertTrue(combat_bootstrap.should_rebuild_placement(self.fight, ()))

    def test_tampered_receipt_and_incomplete_closure_rejected(self):
        for field, value in (
            ("fight_id", 8),
            ("policy", "invented"),
            ("initialized", False),
            ("references", [10]),
            ("snapshot_sha256", "changed"),
            ("actor_ids", [-2, -2]),
        ):
            with self.subTest(field=field):
                fight = copy.deepcopy(self.fight)
                fight.native_dungeon_scaling_receipt[field] = value
                with self.assertRaises(ValueError):
                    scaling.validates_constructor_receipt(
                        fight, -2, catalog=self.catalog
                    )
        catalog = copy.deepcopy(self.catalog)
        del catalog["effects"]["12"]
        with self.assertRaises(ValueError):
            scaling.validates_constructor_receipt(self.fight, -2, catalog=catalog)

    def test_ordinary_monster_without_scaling_keeps_empty_constructor(self):
        del self.fight.native_dungeon_scaling_receipt
        with patch(
            "wakfu_server.combat.combat_actor.actor_effects", return_value=b"empty"
        ):
            self.assertEqual(
                combat_remote_effects.initial_npc_actor_effects(self.fight, -2),
                b"empty",
            )
        self.assertFalse(combat_bootstrap.should_rebuild_placement(self.fight, ()))

    def test_scaling_does_not_bypass_existing_ordinary_constructor_proof(self):
        self.fight.native_npc_initialization_receipts = {-2: dict(initialized=False)}
        with patch(
            "wakfu_server.maps.dungeon_scaling_catalog.current",
            return_value=self.catalog,
        ):
            with self.assertRaisesRegex(ValueError, "constructor proof"):
                combat_remote_effects.initial_npc_actor_effects(self.fight, -2)
