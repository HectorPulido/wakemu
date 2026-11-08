"""Recipient verification does not request unused global summon-count metadata."""
from copy import copy
from dataclasses import asdict
import unittest
from unittest.mock import patch

from test_combat_summon_read_pass_reuse import SummonReadPassReuseTests
from wakfu_server.combat_summon import verify_event_recipient
from wakfu_server.combat_summon_count import registered_summon_counts
from wakfu_server.combat_runtime_adapter import NativeActorAuthority


class EventRecipientAuthorityLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SummonReadPassReuseTests.setUpClass()

    def setUp(self):
        SummonReadPassReuseTests.setUp(self)
        actor = self.case.fight.actors[-8]
        actor.native_summon_source = dict(
            native_relation_source="big.new_bje.fdt_initial_registration",
            caster_id=7,
            controller_id=7,
            ref=3251,
            level=actor.effective_level,
        )
        actor.native_controller_id = 7
        actor.native_master_id = 7
        actor.native_carrier_id = None
        actor.native_carried_actor_id = None
        actor.is_summon = True
        actor.spell_ap_cost_modifiers = {}
        actor.spell_range_modifiers = {}
        from wakfu_server.combat_summon_spellbook import fresh_action_book

        actor.native_summon_action_book = fresh_action_book(3251, actor.effective_level)
        authority = NativeActorAuthority(
            targeting={
                "is_eGj": True,
                "dTE": True,
                "dpr_id": 7,
                "dpu_id": 7,
                "buX": False,
            },
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=3251,
            summon_count=0,
            summon_counts_by_breed={5525: 1},
            occupant_blocks=True,
            is_summon=True,
            summon_root_id=7,
            is_carrying=False,
            native_real_level=actor.effective_level,
            native_instance_id=0,
            native_controller_id=7,
            native_in_play=True,
            native_summon_counts_complete=True,
        )
        self.case.fight.native_summon_registrations[-8] = dict(
            actor_id=-8,
            caster_id=7,
            controller_id=7,
            authority=asdict(authority),
        )

    def test_real_phase_skips_counts_but_keeps_identity_staleness_and_custom_fallback(
        self,
    ):
        fight, actor = self.case.fight, self.case.fight.actors[7]
        # Full authority remains the original count consumer.
        self.assertEqual(self.wrapper(fight, actor).summon_count, 1)
        seen = []
        self.case.events.replay = lambda source, **kwargs: seen.append(
            (source.channel, source.manager_actor_id)
        )
        with patch(
            "wakfu_server.combat_summon_count.registered_summon_counts",
            side_effect=AssertionError("Unused global summon count"),
        ):
            self.case.events.phase(
                self.case.effect,
                self.case.inv,
                uid=800,
                value=1,
                channel=3,
                _event_ids=(),
            )
            self.assertTrue(seen)
            with self.assertRaisesRegex(ValueError, "does not belong"):
                verify_event_recipient(self.wrapper, fight, copy(actor))
            fight.native_summon_registrations[-8]["actor_id"] = -99
            with self.assertRaisesRegex(ValueError, "Stale summon roster"):
                verify_event_recipient(self.wrapper, fight, actor)
            fight.native_summon_registrations[-8]["actor_id"] = -8
            actor.native_carrier_id = -7
            with self.assertRaises(ValueError):
                verify_event_recipient(self.wrapper, fight, actor)
            actor.native_carrier_id = None
        self.assertEqual(self.wrapper(fight, actor).summon_count, 1)

        ordinary = self.ordinary

        class Custom:
            catalog = ordinary.catalog

            def __call__(self, preview, current):
                return ordinary(preview, current)

        self.wrapper.ordinary = Custom()
        with patch(
            "wakfu_server.combat_summon_count.registered_summon_counts",
            wraps=registered_summon_counts,
        ) as counts:
            verify_event_recipient(self.wrapper, fight, actor)
            self.assertEqual(counts.call_count, 1)
