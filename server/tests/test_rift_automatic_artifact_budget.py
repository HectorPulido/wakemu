"""Real native artifact assignment preserves the next wave's action budget.

Run explicitly against an installed immutable publication with
WAKFU_RIFT_ASSIGNMENT_COMPONENT=1. No player/database state is mutated.
"""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import os
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_RIFT_ASSIGNMENT_COMPONENT") == "1",
    "Installed native publication required",
)
class RiftAutomaticArtifactBudgetTests(unittest.TestCase):
    def test_four_species_births_keep_budget_and_grants_while_contact_spends_mp(self):
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.rift_artifact_generation import spawn_artifacts
        from wakfu_server.rift_native_gameplay import (
            install_wave_state,
            distribute_unclaimed_artifacts,
        )
        from wakfu_server.rift_npc_creation import install_native_wave
        from wakfu_server.rift_dispatch_lifecycle import next_roster
        from wakfu_server.rift_wave_initialization import initialize_registered_wave
        from wakfu_server.rift_policy import select_wave
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = NativeRiftCarrierComponentTests()
        fixture.compiled = npc_runtime_catalog()
        fixture.registry = characteristic_registry()
        component = fixture.fixture(
            1,
            rift_type="INFINITE_WAVE",
            native_map_id=1314,
            enabled_native_types=["INFINITE_WAVE"],
        )
        from wakfu_server.rift_company_compensation import install_company_compensation

        def verify_no_company_bonus(candidate):
            current = candidate.fight
            settings = current.rift_wave_state["policy"]["native_gameplay"][
                "compensation"
            ]
            for kind in ("classic", "ultimate"):
                settings[kind + "_grade_by_company_size"] = {
                    str(size): 0 for size in range(1, 7)
                }
            actor = current.actors[7]
            before = (
                actor.hp,
                actor.max_hp,
                actor.ap,
                actor.max_ap,
                actor.mp,
                actor.max_mp,
                deepcopy(actor.effect_stats),
                deepcopy(actor.effect_maxima),
                deepcopy(actor.effect_resource_raw_currents),
            )
            current_dispatcher, _ = candidate.factory(current)
            with current.effect_resolution():
                installed = install_company_compensation(
                    current_dispatcher, actor_ids=(7,)
                )
            self.assertFalse(installed)
            self.assertEqual(
                (
                    actor.hp,
                    actor.max_hp,
                    actor.ap,
                    actor.max_ap,
                    actor.mp,
                    actor.max_mp,
                    actor.effect_stats,
                    actor.effect_maxima,
                    actor.effect_resource_raw_currents,
                ),
                before,
            )
            self.assertFalse(
                any(state.reference == 6808 for state in actor.state_ledger.entries)
            )
            receipt = current.rift_wave_state["native_company_compensation"]
            self.assertEqual(receipt["level"], 0)
            self.assertEqual(
                receipt["rift_type"], current.rift_wave_state["catalog"]["type"]
            )
            self.assertEqual(receipt["company_ids"], [7])
            committed = snapshot(current)
            with current.effect_resolution():
                self.assertFalse(
                    install_company_compensation(current_dispatcher, actor_ids=(7,))
                )
            self.assertEqual(snapshot(current), committed)

        # The revised admission policy retains ordinary player statistics for
        # both Rift types; it still writes the idempotent zero-grade receipt.
        verify_no_company_bonus(component)
        verify_no_company_bonus(fixture.fixture(1))
        fight = component.fight
        policy = fight.rift_wave_state["policy"]
        policy["classic_wave_size"] = 4
        policy["native_gameplay"]["artifacts"] = dict(
            enabled=True,
            pools={"shushu": [1592, 1594], "legendary": [1613, 1614]},
            rarity_weights={"shushu": 1, "legendary": 0},
            selection="weighted_tier_uniform_reference_without_replacement",
            placement_policy="uniform_free_native_reachable_cells_without_replacement",
            classic_count=2,
            ultimate_count=4,
            legendary_cadence=5,
            legendary_anchor="displayed_wave_multiple",
            legendary_mode="whole_choice_group",
            producer=dict(
                policy="wakemu.rift.native-context-area-reference.v1",
                source_kind="native_context_area_ref",
                level_policy="owner_effective_level",
                context_policy="eVt_mb_false_SQ_area_reference",
                native_contract="faM",
                source_document="combat-state-definitions.json",
                template_effect_reference=147120,
            ),
        )
        dispatcher, _ = component.factory(fight)
        with fight.effect_resolution():
            install_wave_state(dispatcher, actor_ids=(-200, -201), wave=1)
            spawn_artifacts(dispatcher, wave=1)
        group = fight.rift_wave_state["native_artifact_groups"]["1"]
        self.assertEqual(set(group["original"].values()), {1592, 1594})
        # Scope is source-bound, fails closed for other losses, and unwinds
        # even when the underlying artifact callback rejects its transaction.
        from wakfu_server.combat_artifact_assignment import automatic_pickup_toll
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        candidate_uid = int(next(iter(group["original"])))
        toll = dict(
            effect_class=48, native_effect_flags=(19, 30), parameters=(100.0, 0.0)
        )
        invocation = EffectInvocation(
            315848,
            100,
            7,
            7,
            fight.actors[7].position,
            native_retained_container=dict(
                present=True, type=3, id=candidate_uid, native_kind="effect_area"
            ),
        )
        self.assertFalse(automatic_pickup_toll(toll, invocation))

        def rejected_assignment(*args, **kwargs):
            self.assertTrue(automatic_pickup_toll(toll, invocation))
            for fields in (
                dict(type=1, native_kind="state"),
                dict(id=candidate_uid + 100000),
                dict(present=False),
            ):
                foreign = replace(
                    invocation,
                    native_retained_container={
                        **invocation.native_retained_container,
                        **fields,
                    },
                )
                self.assertFalse(automatic_pickup_toll(toll, foreign))
            for fields in (
                dict(effect_class=55),
                dict(native_effect_flags=(30,)),
                dict(parameters=(99.0, 0.0)),
            ):
                self.assertFalse(automatic_pickup_toll({**toll, **fields}, invocation))
            raise ValueError("Reject private artifact callback")

        before_failure = snapshot(fight)
        with patch.object(
            dispatcher.native_area_events,
            "_deliver_event",
            side_effect=rejected_assignment,
        ), self.assertRaisesRegex(ValueError, "Reject private artifact callback"):
            dispatcher.native_area_events.assign_artifact(candidate_uid, 7)
        self.assertFalse(automatic_pickup_toll(toll, invocation))
        self.assertEqual(snapshot(fight), before_failure)
        fight.spend(3, 7, ap=1, mp=1)
        spent_budget = (fight.actors[7].ap, fight.actors[7].mp)

        # A genuine contact still runs the original 315848 100% MP loss.
        manual = deepcopy(fight)
        contact, _ = component.factory(manual)
        area_uid = next(
            int(uid) for uid, ref in group["original"].items() if ref == 1592
        )
        row = manual.native_effect_areas[area_uid]
        definition = native_effect_areas()[str(row["reference"])]
        with manual.effect_resolution():
            applied = contact.native_area_events._deliver_event(
                row, definition, manual.actors[7], 2243, artifact_origin="contact"
            )
        self.assertTrue(any(applied))
        self.assertEqual(manual.actors[7].mp, 0)
        self.assertEqual(manual.actors[7].effect_resource_raw_currents[3], 0)
        self.assertTrue(
            any(s.reference == 6786 for s in manual.actors[7].state_ledger.entries)
        )

        # Clear the actual old roster and admit four different native species.
        for identity in (-200, -201):
            fight.apply_damage(7, identity, fight.actors[identity].hp)
        fight.rift_wave_state["catalog"]["species_refs"] = [3, 3215, 4, 4079]
        for seed in map(str, range(10000)):
            if select_wave(fight.rift_wave_state["catalog"], policy, seed, 2) == (
                3,
                3215,
                4,
                4079,
            ):
                fight.rift_wave_state["seed"] = seed
                break
        else:
            self.fail("Native selector did not produce the requested compound roster")
        monsters = next_roster(fight, fight.rift_wave_state["pending_wave"])
        fight.rift_monsters.update({m["id"]: m for m in monsters})
        budgets = {}

        def initialize_wave(current, actors, sources):
            budgets.update({a.id: (a.ap, a.mp) for a in actors})
            current_dispatcher, packets = component.factory(current)
            with current.effect_resolution():
                initialize_registered_wave(
                    current_dispatcher, actors=actors, monsters=sources, player_ids=(7,)
                )
            return tuple(packets)

        packets = install_native_wave(
            fight,
            monsters,
            initialize_actor=lambda *args: (),
            initialize_wave=initialize_wave,
        )
        self.assertEqual(sum(opcode == 13091 for opcode, _ in packets), 4)
        self.assertEqual({m["ref"] for m in monsters}, {3, 3215, 4, 4079})
        self.assertEqual((fight.actors[7].ap, fight.actors[7].mp), spent_budget)
        for identity, budget in budgets.items():
            with self.subTest(species=fight.rift_monsters[identity]["ref"]):
                actor = fight.actors[identity]
                self.assertEqual((actor.ap, actor.mp), budget)
                source = fight.rift_monsters[identity]
                base = native_npc_creation_values(source["ref"], source["level"])
                self.assertGreater(actor.max_hp, base[1]["maximum"])
                self.assertEqual(
                    [
                        s.level
                        for s in actor.state_ledger.entries
                        if s.reference == 6807
                    ],
                    [2],
                )
                self.assertEqual(actor.effect_resource_raw_currents[3], actor.mp)
                self.assertTrue(
                    any(s.reference in (6786, 6794) for s in actor.state_ledger.entries)
                )
        self.assertEqual(group["remaining"], [])
        self.assertEqual(len(group["assignments"]), 1)

        # Replaying the same boundary cannot grant resources or consume RNG again.
        current_dispatcher, _ = component.factory(fight)
        before, rng_before = snapshot(fight), component.rng.getstate()
        with fight.effect_resolution():
            changed = distribute_unclaimed_artifacts(current_dispatcher, before_wave=2)
        self.assertFalse(changed)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(component.rng.getstate(), rng_before)

    def test_real_lav_hos_birth_preserves_realtime_innate_clock_and_wire_replay(self):
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.rift_dispatch_lifecycle import next_roster
        from wakfu_server.rift_npc_creation import install_native_wave, creation_packets
        from wakfu_server.combat_multiplayer_wire import decode_added
        from wakfu_server.combat_remote_effects import decode_remote_effects
        from wakfu_server.combat_effect_removal import _identity_fields
        from wakfu_server.combat_realtime_state_clock import expire_realtime_states
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = NativeRiftCarrierComponentTests()
        fixture.compiled = npc_runtime_catalog()
        fixture.registry = characteristic_registry()
        component = fixture.fixture(1)
        fight = component.fight
        state = fight.rift_wave_state
        state["catalog"]["species_refs"] = [4355]
        state["policy"]["ultimate_wave_size"] = 1
        for identity in (-200, -201):
            fight.apply_damage(7, identity, fight.actors[identity].hp)
        monsters = next_roster(fight, state["pending_wave"])
        self.assertEqual([monster["ref"] for monster in monsters], [4355])
        fight.rift_monsters.update({monster["id"]: monster for monster in monsters})
        now_ms = 1800000000000
        with patch("time.time_ns", return_value=now_ms * 1000000):
            packets = install_native_wave(
                fight, monsters, initialize_actor=lambda *args: ()
            )
        actor = fight.actors[monsters[0]["id"]]
        entries = [
            entry for entry in actor.state_ledger.entries if entry.reference == 4882
        ]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.realtime_duration, 600000)
        self.assertEqual(entry.realtime_deadline_ms, now_ms + 600000)
        self.assertTrue(entry.realtime_in_combat)
        self.assertIsNone(entry.timer)

        def remaining(admission):
            decoded = decode_added(admission)
            self.assertEqual(decoded["actor_id"], actor.id)
            records = [
                record
                for record in decode_remote_effects(decoded["effects"])
                if record.effect_class == 310
                and _identity_fields(record.payload, integer_fields=(1,)).get(1)
                == entry.uid
            ]
            self.assertEqual(len(records), 1)
            return records[0].remaining_milliseconds

        admission = next(payload for opcode, payload in packets if opcode == 13091)
        self.assertEqual(remaining(admission), 600000)
        before = snapshot(fight)

        def reproduce_at(clock_ms):
            with patch("time.time_ns", return_value=clock_ms * 1000000):
                return creation_packets(
                    monsters[0],
                    fight.id,
                    obstacle_id=actor.native_obstacle_id,
                    group_id=state["world_group_id"],
                    actor=actor,
                    fight=fight,
                )

        self.assertEqual(reproduce_at(now_ms), tuple(packets))
        later = reproduce_at(now_ms + 1000)
        self.assertEqual(remaining(later[-1][1]), 599000)
        self.assertEqual(snapshot(fight), before)
        clocks = {
            entry.uid: dict(deadline_ms=entry.realtime_deadline_ms, in_combat=True)
        }
        self.assertEqual(
            expire_realtime_states(
                clocks,
                now_ms=now_ms + 700000,
                remove=lambda uid: self.fail(
                    "Combat birth must not expire its realtime innate"
                ),
            ),
            (),
        )
        self.assertEqual(clocks[entry.uid]["deadline_ms"], now_ms + 600000)
        self.assertIn(entry, actor.state_ledger.entries)
