"""Actual eligible5347 source through the registered324 handler and checkpoint."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_captured_summon_handler import NativeCapturedSummonHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_summon_spellbook import actor_action_book


class CapturedRuntimeHandlerTests(unittest.TestCase):
    def test_source_intrinsic0_preserves_effect_events_without307_intrinsic2130(self):
        calls = []
        handler = NativeCapturedSummonHandler.__new__(NativeCapturedSummonHandler)
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *args, **kwargs: calls.append(kwargs)
        )
        handler._phase(
            {"target_masks": [[], [], [], [], [], [], [17]]},
            EffectInvocation(123, 1, 42, None, (0, 0, 0)),
            SimpleNamespace(uid=9, value=0),
            1,
        )
        self.assertEqual(calls[0]["_event_ids"], (0, 17))
        self.assertNotIn(2130, calls[0]["_event_ids"])

    def test_original_profile_book_fan_codec_owned_slot_and_plain_checkpoint(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/owned-captured-5347-native.json"
            ).read_text()
        )
        catalog = fixture["actor_catalog"]
        profile = fixture["native_profile_export"]["profiles"]["5347"]
        roster = OwnedCapturedRoster(
            42,
            (CapturedCreature(0, 5347, "owned Wonejo"),) + (None,) * 9,
            (True,) + (False,) * 9,
        )

        class Preview(SimpleNamespace):
            @property
            def current(self):
                return self.actors[self.order[self.turn_index]]

        class Authority:
            def __call__(self, fight, actor):
                return SimpleNamespace(
                    summon_root_id=42,
                    native_instance_id=1,
                    native_is_ehp=True,
                    native_captured_roster=roster,
                )

            def world_properties(self, fight, actor):
                return frozenset()

        class FixtureRegistration(RegisteredSummonAuthority):
            def __call__(self, fight, actor):
                return self.ordinary(fight, actor)

        caster = SimpleNamespace(
            id=42,
            owner_id=3,
            controlled=True,
            native_obstacle_id=0,
            hp=40,
            position=(0, 0, 0),
            effective_level=153,
            direction=3,
            team=0,
        )
        preview = Preview(
            id=1,
            actors={42: caster},
            phase="active",
            order=[42],
            turn_index=0,
            native_timeline_round=1,
            walkable={(3, 4, 0)},
        )
        # This fixture models an already-active fight; seed the exact native
        # Tc/SY progress snapshot required for a new fighter insertion.
        from wakfu_server.combat_timeline_snapshot import initialize

        initialize(preview, (42,))
        ids = iter((900, 901))
        packets = []
        with patch(
            "wakfu_server.combat_summon_creation.native_actor_catalog",
            return_value=catalog,
        ), patch(
            "wakfu_server.combat_summon_creation.native_property_catalog",
            return_value={"npc": {"5347": profile}},
        ), patch(
            "wakfu_server.combat_captured_scaling.native_actor_catalog",
            return_value=catalog,
        ), patch(
            "wakfu_server.combat_summon_creation.register_fresh_summon_obstacle",
            side_effect=lambda fight, actor: setattr(actor, "native_obstacle_id", 1),
        ):
            handler = NativeCapturedSummonHandler(
                preview,
                packets,
                action_id=2,
                allocate_uid=lambda: next(ids),
                context=lambda effect, invocation: StatExecutionContext(
                    True, True, None, False, b""
                ),
                actor_authority=FixtureRegistration(Authority()),
                container_level=lambda inv: (False, 0),
                container=lambda inv: ({"container_type": 1}, 42),
            )
            from wakfu_server.combat_effect_dispatch import EffectDispatcher
            from wakfu_server.combat_conditions import ConditionContext

            native = json.loads(
                (
                    Path(__file__).parent / "fixtures/captured324-native-effect.json"
                ).read_text()
            )["effects"]["326389"]
            invocation = EffectInvocation(326389, 153, 42, None, (3, 4, 0))
            dispatcher = EffectDispatcher(
                {"326389": native},
                {324: handler},
                resolve=lambda effect, inv: (inv,),
                condition_context=lambda inv: ConditionContext(
                    {},
                    space_in_symbiot_query=lambda: roster.free_slots,
                    state_range_query=lambda *args: 0,
                ),
                probability_accepts=lambda *args: True,
                group_cells=lambda *args: (),
                actor_position=lambda identity: preview.actors[identity].position,
            )
            self.assertTrue(dispatcher.execute(invocation))
        actor = preview.actors[901]
        self.assertTrue(actor.native_summoned_from_symbiot)
        self.assertEqual(actor.native_captured_name, "owned Wonejo")
        self.assertEqual(
            [a["reference"] for a in actor_action_book(actor)["actions"]],
            [7356, 7357, 7358],
        )
        self.assertFalse(preview.native_captured_rosters["42"]["available"][0])
        self.assertEqual(
            preview.native_captured_roster_updates, preview.native_captured_rosters
        )
        self.assertEqual(len(packets), 1)
        self.assertEqual(
            preview.native_summon_creation_deliveries[901]["payload_hex"],
            packets[0][1].hex(),
        )
        encoded = json.dumps(snapshot(preview), allow_nan=False)
        self.assertIn("native_captured_roster_updates", encoded)
        # Availability flips independently of entry ownership/free space.
        owned = OwnedCapturedRoster.from_record(
            preview.native_captured_rosters["42"], expected_owner_id=42
        )
        self.assertEqual(owned.free_slots, 9)
        self.assertEqual(owned.slots[0].profile_id, 5347)
