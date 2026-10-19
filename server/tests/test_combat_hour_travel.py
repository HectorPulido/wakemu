"""Pure admission and descriptor guards; native behavior has separate paid tests."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_hour_travel import (
    POLICY,
    try_apply_hour_travel,
    validate_hour_boundary_facts,
)
from wakfu_server.combat_movement_payment_events import (
    WakemuMovementPolicy,
    valid_movement_descriptor,
)
from wakfu_server.combat_runtime_adapter import NativeActorAuthority


class HourTravelGuardTests(unittest.TestCase):
    def test_hour_appearance_excludes_marker_and_unproved_factories(self):
        from wakfu_server.combat_live_area_snapshot import _appearance

        definition = dict(
            type="HOUR",
            native_class="bcU",
            native_type_id=1,
            native_hour_contract=True,
            effect_ids=[],
            entry_masks=[],
            exit_masks=[],
        )
        row = dict(
            reference=1546,
            effect_class=315,
            native_area_contract="faZ",
            native_type_id=1,
            native_hour_contract=True,
            native_qq_guard_source="Qq.constructor",
            native_qq_bhi=False,
            effect_uid=12,
            effect_reference=313200,
        )
        self.assertEqual(_appearance(row, definition), b"\x00\x00")
        for excluded in (
            dict(row, reference=1558),
            dict(row, reference=9999),
            dict(row, effect_class=320),
            dict(row, effect_class=323),
        ):
            self.assertIsNone(_appearance(excluded, definition))
        for malformed in (
            dict(row, native_qq_guard_source=None),
            dict(row, effect_uid=0),
            dict(row, effect_reference=0),
        ):
            with self.assertRaisesRegex(ValueError, "native315 constructor"):
                _appearance(malformed, definition)

    def test_rejected_missing_callback_never_refreshes_unrelated_aura(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), effect_stats={4: 12})
        rows = {
            11: dict(
                uid=11,
                native_hour_contract=True,
                native_area_contract="faZ",
                native_type_id=1,
                owner_id=7,
                cell=(0, 0, 0),
            ),
            12: dict(
                uid=12,
                native_hour_contract=True,
                native_area_contract="faZ",
                native_type_id=1,
                owner_id=7,
                cell=(3, 0, 0),
            ),
            13: dict(
                uid=13,
                native_area_contract="faN",
                native_anchor_id=7,
                native_anchor_source="faN.bgZ",
                cell=(9, 9, 0),
                native_cells_xy=((9, 9),),
            ),
        }
        # This preflight fixture deliberately has no QI or callback authority:
        # rejection must happen before either could be consulted.
        authority = NativeActorAuthority(
            targeting={},
            is_player=True,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=5,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
        )
        fight = SimpleNamespace(
            actors={7: actor},
            native_effect_areas=rows,
            _current_owned=lambda owner, identity: actor,
            native_rail_movement_authority=lambda current, value: authority,
        )
        fight.native_rail_movement_authority.properties = lambda *_: frozenset()
        runtime = SimpleNamespace(fight=fight, action_id=3)
        before = deepcopy((rows, actor.__dict__, runtime.action_id))
        with patch(
            "wakfu_server.combat_effect_area_queries.refresh_area_geometry"
        ) as refresh:
            with self.assertRaisesRegex(ValueError, "payment and area callbacks"):
                try_apply_hour_travel(runtime, 3, 7, [(3, 0, 0)], lambda _: b"")
        refresh.assert_not_called()
        self.assertEqual((rows, actor.__dict__, runtime.action_id), before)

    def test_split_hour_wp_descriptor_does_not_specialize_tackle_costs(self):
        boundary = dict(
            policy=POLICY,
            actor_id=7,
            owner_id=3,
            turn_id=1,
            from_cell=(0, 0, 0),
            to_cell=(3, 0, 0),
            entry_uid=11,
            exit_uid=12,
            obstacle_id=0,
        )
        receipt = dict(
            fight_id=1,
            actor_id=7,
            turn_id=1,
            origin=(0, 0, 0),
            destination=(3, 0, 0),
            index=0,
            ap_before=6,
            ap_after=5,
            ap_paid=1,
            mp_before=3,
            mp_after=2,
            mp_paid=1,
            ap_effective_after=5,
            mp_effective_after=2,
            ap_raw_post=5,
            mp_raw_post=2,
            wp_before=12,
            wp_after=11,
            wp_paid=1,
            wp_effective_after=11,
            hour_boundary=boundary,
        )
        # A synthetic descriptor unit case, not an attested live payment.
        policy = WakemuMovementPolicy(receipt, object())
        wp = policy.descriptor(dict(ap=0, mp=0, wp=1))
        movement = policy.descriptor(dict(ap=1, mp=1, wp=0))
        self.assertTrue(valid_movement_descriptor(wp, caster_id=7, target_id=7))
        self.assertTrue(valid_movement_descriptor(movement, caster_id=7, target_id=7))
        self.assertEqual(
            (wp["movement_payment_policy"]["mi"], wp["movement_payment_policy"]["mh"]),
            (True, False),
        )
        self.assertEqual(
            (
                movement["movement_payment_policy"]["mi"],
                movement["movement_payment_policy"]["mh"],
            ),
            (False, True),
        )
        for altered in (
            dict(wp, action_costs=dict(ap=1, mp=0, wp=1)),
            dict(
                wp,
                movement_payment_policy=dict(
                    wp["movement_payment_policy"], wp_effective_after=12
                ),
            ),
            dict(
                wp,
                movement_payment_policy=dict(
                    wp["movement_payment_policy"], origin=None
                ),
            ),
        ):
            self.assertFalse(
                valid_movement_descriptor(altered, caster_id=7, target_id=7)
            )
        with self.assertRaisesRegex(ValueError, "Invalid native hour"):
            validate_hour_boundary_facts(dict(boundary, entry_uid=-1))
