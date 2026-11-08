"""Compound regression for native-only lifecycle recipient projection."""
from copy import deepcopy
from dataclasses import asdict
import sys
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

    def test_four_phase_native_event_uses_local_recipient_facts(self):
        def execute(use_local_projection):
            case = OrdinaryPopulationReadPassTests()
            case.setUp()
            event_case = case.case
            target = event_case.fight.actors[7]
            target.hp = 50
            target.effect_stats[1] = 50
            phases = []
            original_phase = event_case.events.phase

            def capture_phase(*args, **kwargs):
                phases.append(kwargs.get("channel"))
                return original_phase(*args, **kwargs)

            event_case.events.phase = capture_phase
            population_scans = []

            def profile(frame, event, arg):
                if event != "call" or frame.f_code.co_name != "_creation_population":
                    return
                caller = frame.f_back
                while caller is not None:
                    if caller.f_code.co_name == "verify_event_recipient":
                        population_scans.append(caller.f_code.co_name)
                        break
                    caller = caller.f_back

            original_local_facts = summon_module._EVENT_RECIPIENT_LOCAL_FACTS
            previous_profile = sys.getprofile()
            try:
                if not use_local_projection:
                    summon_module._EVENT_RECIPIENT_LOCAL_FACTS = object()
                sys.setprofile(profile)
                event_case.f.dispatcher.execute(event_case.inv)
            finally:
                sys.setprofile(previous_profile)
                summon_module._EVENT_RECIPIENT_LOCAL_FACTS = original_local_facts

            state = (
                target.hp,
                dict(target.effect_stats),
                tuple(event_case.fight.order),
                event_case.fight.turn_index,
                event_case.fight.native_effect_uid_next,
                deepcopy(event_case.fight.owned_stat_effects),
            )
            return phases, list(event_case.f.packets), state, population_scans

        candidate = execute(True)
        baseline = execute(False)
        self.assertEqual(candidate[0], [1, 2, 3, 4])
        self.assertEqual(candidate[1], baseline[1])
        self.assertEqual(candidate[2], baseline[2])
        self.assertEqual(candidate[3], [])
        self.assertTrue(baseline[3])
        self.assertEqual(
            [opcode for opcode, _ in candidate[1]], [13497, 12613, 12613, 13560]
        )

    def test_unsupported_local_sources_and_instance_overrides_fall_back(self):
        npc = self.fight.actors[-7]
        source = self.ordinary.monsters.pop(-7)
        try:
            with self.assertRaisesRegex(ValueError, "roster changed"):
                summon_module.verify_event_recipient(self.authority, self.fight, npc)
        finally:
            self.ordinary.monsters[-7] = source

        self.ordinary._recipient_creation_facts = lambda preview, actor: None
        try:
            self.assertIsNone(
                summon_module.verify_event_recipient(self.authority, self.fight, npc)
            )
        finally:
            del self.ordinary._recipient_creation_facts

    def test_companion_source_only_matches_full_authority_and_rejects_conflict(self):
        companion = self.fight.actors[-7]
        owner = self.fight.actors[7]
        companion.controlled = True
        companion.owner_id = owner.owner_id
        companion.native_master_id = None
        companion.native_carrier_id = None
        companion.native_carried_actor_id = None
        original_monster = self.ordinary.monsters.pop(companion.id)
        companion_source = {
            "id": companion.id,
            "ref": 2828,
            "native_actor_type": 5,
            "account_id": owner.owner_id,
            "owner_character_id": owner.id,
        }
        self.fight.native_companion_sources = {str(companion.id): companion_source}
        try:
            local_facts = self.ordinary._recipient_creation_facts(self.fight, companion)
            self.assertIsNotNone(local_facts)
            self.assertIs(local_facts[1], companion_source)
            # The previous projected recipient path passed the filtered view
            # directly to _creation_facts; compare that exact contract without
            # invoking unused world/spellbook metadata construction.
            full_projected_facts = self.ordinary._creation_facts(
                self.authority._ordinary_view(self.fight, _pure_callback=self.ordinary),
                companion,
            )
            self.assertEqual(local_facts, full_projected_facts)
            self.assertIsNone(
                summon_module.verify_event_recipient(
                    self.authority, self.fight, companion
                )
            )

            self.ordinary.monsters[companion.id] = original_monster
            with self.assertRaisesRegex(
                ValueError, "Conflicting companion and NPC source"
            ):
                summon_module.verify_event_recipient(
                    self.authority, self.fight, companion
                )
        finally:
            self.ordinary.monsters.pop(companion.id, None)
            self.ordinary.monsters[companion.id] = original_monster
            del self.fight.native_companion_sources


if __name__ == "__main__":
    unittest.main()
