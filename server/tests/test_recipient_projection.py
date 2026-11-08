"""Compound regression for native-only lifecycle recipient projection."""
from copy import deepcopy
from dataclasses import asdict
import unittest

from test_combat_ordinary_population_read_pass import OrdinaryPopulationReadPassTests
from wakfu_server import combat_summon as summon_module
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_global_pv_collections import register_global_fighter
from wakfu_server.combat_native_death_status import initialize_fresh_bje_death_status
from wakfu_server.combat_controller_registry import (
    initialize_controller_registry,
    register_native_controller,
    transfer_native_controller,
)


class EventRecipientProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OrdinaryPopulationReadPassTests.setUpClass()

    def setUp(self):
        self.case = OrdinaryPopulationReadPassTests()
        self.case.setUp()
        self.fight = self.case.case.fight
        self.ordinary = self.case.ordinary
        self.authority = self.case.wrapper

    def _register_summon(self):
        actor = deepcopy(self.fight.actors[-7])
        actor.id = -8
        actor.controlled = True
        actor.native_controller_id = 7
        actor.native_master_id = 7
        actor.native_carrier_id = None
        actor.native_carried_actor_id = None
        actor.native_summon_source = dict(
            native_relation_source="big.new_bje.fdt_initial_registration",
            caster_id=7,
            controller_id=7,
            ref=5525,
            level=actor.effective_level,
        )
        actor.spell_ap_cost_modifiers = {}
        actor.spell_range_modifiers = {}
        if hasattr(actor, "native_death_status"):
            del actor.native_death_status
        initialize_fresh_bje_death_status(actor)
        self.fight.actors[-8] = actor
        register_global_fighter(self.fight, -8)
        transfer_native_controller(self.fight, -8, 7)
        metadata = NativeActorAuthority(
            targeting={"dpr_id": 7, "dpu_id": 7, "buX": False},
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=5525,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
            is_summon=True,
            summon_root_id=7,
            is_carrying=False,
            native_controller_id=7,
            native_real_level=actor.effective_level,
        )
        self.fight.native_summon_registrations = {
            actor.id: {
                "actor_id": actor.id,
                "caster_id": 7,
                "controller_id": 7,
                "authority": asdict(metadata),
            }
        }
        return actor

    def test_native_ordinary_and_summon_projection_preserve_guards_and_custom_fallback(
        self,
    ):
        npc = self.fight.actors[-7]
        source = self.ordinary.monsters[-7]
        # Full construction rejects this malformed unused book. Lifecycle
        # delivery only needs identity, relation, carry, life and controller.
        source["native_spellbook"] = object()
        with self.assertRaises(ValueError):
            summon_module._EVENT_RECIPIENT_CALL(
                self.authority, self.fight, npc, _include_summon_counts=False
            )
        self.assertIsNone(
            summon_module.verify_event_recipient(self.authority, self.fight, npc)
        )
        npc.native_carrier_id = 7
        with self.assertRaisesRegex(ValueError, "Unregistered native carrying"):
            summon_module.verify_event_recipient(self.authority, self.fight, npc)
        npc.native_carrier_id = None
        npc.native_master_id = 7
        with self.assertRaisesRegex(ValueError, "changed native relationships"):
            summon_module.verify_event_recipient(self.authority, self.fight, npc)
        npc.native_master_id = None

        fighter_status = self.fight.native_global_pv_collections["fighter_status"]
        fighter_status["-7"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "Missing actual native fighter status"):
            summon_module.verify_event_recipient(self.authority, self.fight, npc)
        fighter_status["-7"] = "IN_PLAY"

        initialize_controller_registry(self.fight)
        for identity, actor in self.fight.actors.items():
            register_native_controller(
                self.fight, identity, team=actor.team, controller_id=identity
            )
        controller_row = self.fight.native_controller_registry["fighters"]["-7"]
        controller_row["current_controller"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "Invalid native fdy controller"):
            summon_module.verify_event_recipient(self.authority, self.fight, npc)
        controller_row["current_controller"] = -7
        source.pop("native_spellbook")

        class CustomAuthority(summon_module.RegisteredSummonAuthority):
            def __init__(self, ordinary):
                super().__init__(ordinary)
                self.calls = 0

            def __call__(self, preview, actor, *, _include_summon_counts=True):
                self.calls += 1
                return super().__call__(
                    preview, actor, _include_summon_counts=_include_summon_counts
                )

        custom = CustomAuthority(self.ordinary)
        summon_module.verify_event_recipient(custom, self.fight, npc)
        self.assertEqual(custom.calls, 1)

        summon = self._register_summon()
        self.assertIsNone(
            summon_module.verify_event_recipient(self.authority, self.fight, summon)
        )
        summon.native_master_id = -7
        with self.assertRaisesRegex(ValueError, "Changed native summon master"):
            summon_module.verify_event_recipient(self.authority, self.fight, summon)


if __name__ == "__main__":
    unittest.main()
