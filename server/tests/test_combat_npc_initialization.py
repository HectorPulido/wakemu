"""Constructor authority and atomic orchestration, independent of live catalogs."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat.combat_state import Actor, Fight
from wakfu_server.combat.combat_npc_initialization import (
    constructor_stat_context,
    initial_plans,
)
from wakfu_server.combat.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat.combat_summon_creation import native_fresh_summon_authority
from wakfu_server.combat.combat_actor_snapshot import initialize_fight_snapshots


class NpcInitializationTests(unittest.TestCase):
    def actor(self):
        return Actor(-3, 1, (0, 0, 0), 10, 6, 3, 1, 5)

    def test_constructor_guard_requires_actual_detached_self(self):
        actor = self.actor()
        fight = SimpleNamespace(actors={}, phase="placement", current=None)
        invocation = SimpleNamespace(caster_id=actor.id, target_id=actor.id)
        self.assertFalse(constructor_stat_context(fight, invocation))
        authority = native_fresh_summon_authority(actor, 6)
        actor.team = -1
        with detached_summon_scope(fight, actor, authority):
            self.assertTrue(constructor_stat_context(fight, invocation))
            self.assertFalse(
                constructor_stat_context(
                    fight,
                    SimpleNamespace(caster_id=actor.id, target_id=9),
                )
            )
            with self.assertRaises(ValueError):
                with detached_summon_scope(fight, actor, authority):
                    pass
            self.assertEqual(fight.phase, "placement")
            self.assertIsNone(fight.current)
        self.assertFalse(constructor_stat_context(fight, invocation))

    def test_normal_npc_initialization_rebuilds_placement_without_heroes(self):
        from wakfu_server.combat.combat_bootstrap import should_rebuild_placement

        fight = SimpleNamespace()
        self.assertFalse(should_rebuild_placement(fight, []))
        self.assertTrue(should_rebuild_placement(fight, [-4]))
        fight.native_npc_initialization_receipts = {}
        self.assertFalse(should_rebuild_placement(fight, []))
        fight.native_npc_initialization_receipts[-3] = {"initialized": True}
        self.assertTrue(should_rebuild_placement(fight, []))

    def test_placement_serializer_requires_complete_constructor_receipt(self):
        from dataclasses import asdict
        from wakfu_server.combat.combat_remote_effects import (
            active_actor_effects,
            initial_npc_actor_effects,
        )
        from wakfu_server.combat.combat_summon_initial_states import initial_state_plan

        actor = self.actor()
        fight = SimpleNamespace(phase="placement", actors={actor.id: actor})
        self.assertEqual(initial_npc_actor_effects(fight, actor.id), bytes(2))
        with self.assertRaises(ValueError):
            active_actor_effects(fight, actor.id)
        receipt = dict(
            initialized=True,
            descriptor_level=5,
            raw_triples=[123, -1, 0],
            resolved_states=[asdict(p) for p in initial_state_plan([123, -1, 0], 5)],
            applications=[dict(state_id=123, level=5, applied=True)],
        )
        fight.native_npc_initialization_receipts = {actor.id: receipt}
        with patch(
            "wakfu_server.combat.combat_remote_effects._live_actor_effects",
            return_value=b"native-retained",
        ) as serializer:
            self.assertEqual(
                initial_npc_actor_effects(fight, actor.id), b"native-retained"
            )
            serializer.assert_called_once_with(fight, actor.id)
            self.assertEqual(fight.phase, "placement")
            receipt["applications"][0]["applied"] = False
            with self.assertRaises(ValueError):
                initial_npc_actor_effects(fight, actor.id)
            receipt["applications"][0]["applied"] = True
            actor.controlled = True
            with self.assertRaises(ValueError):
                initial_npc_actor_effects(fight, actor.id)

    def test_group_constructor_ignores_unread_flag17_and_preserves_normal_guards(self):
        from wakfu_server.combat.combat_native_events import (
            validate_group_registration_flags,
        )

        validate_group_registration_flags([1, 16], active=False, constructor=True)
        validate_group_registration_flags([17], active=False, constructor=True)
        for flags, constructor in (([999], True), ([1], False), ([17], False)):
            with self.assertRaises(ValueError):
                validate_group_registration_flags(
                    flags,
                    active=False,
                    constructor=constructor,
                )
        validate_group_registration_flags([17], active=True)

    def test_shared_state_installer_records_actual_rejected_application(self):
        from wakfu_server.combat.combat_summon_initialization import (
            install_initial_states,
        )
        from wakfu_server.combat.combat_summon_initial_states import initial_state_plan

        actor = self.actor()
        actor.team = -1
        fight = SimpleNamespace(actors={})
        authority = native_fresh_summon_authority(actor, 6)
        retention = SimpleNamespace(apply_state_reference=lambda *args, **kwargs: False)
        dispatcher = SimpleNamespace(
            native_state_handler=SimpleNamespace(fight=fight, catalog={}),
            native_retention=retention,
        )
        results = []
        with detached_summon_scope(fight, actor, authority), patch(
            "wakfu_server.combat.combat_definitions.state_profile",
            return_value={"duration": -1, "realtime_duration": 0},
        ):
            install_initial_states(
                fight,
                actor,
                initial_state_plan([123, -1, 0], 5),
                runtime_factory=lambda *args: (dispatcher, []),
                application_results=results,
            )
        self.assertEqual(results, [{"state_id": 123, "level": 5, "applied": False}])

    def test_state_application_requires_active_or_detached_self(self):
        actor = self.actor()
        fight = SimpleNamespace(actors={actor.id: actor}, phase="placement")
        apply = lambda target: Fight.apply_state(
            fight,
            actor.id,
            target,
            123,
            5,
            uid=1,
            catalog={},
        )
        with self.assertRaises(ValueError):
            apply(actor.id)
        fight.actors.clear()
        actor.team = -1
        authority = native_fresh_summon_authority(actor, 6)
        result = SimpleNamespace(removed=[], applied=None)
        with detached_summon_scope(fight, actor, authority), patch.object(
            type(actor.state_ledger), "apply", return_value=result
        ) as ledger:
            self.assertIs(apply(actor.id), result)
            ledger.assert_called_once()
            with self.assertRaises(ValueError):
                apply(9)
        self.assertEqual(fight.phase, "placement")

    def test_registered_actor_cannot_claim_constructor_authority(self):
        actor = self.actor()
        fight = SimpleNamespace(actors={actor.id: actor})
        authority = native_fresh_summon_authority(actor, 6)
        actor.team = -1
        with self.assertRaises(ValueError):
            with detached_summon_scope(fight, actor, authority):
                pass

    def test_empty_plan_preserves_original_snapshot_path(self):
        actor = self.actor()
        fight = SimpleNamespace(
            actors={actor.id: actor},
            phase="placement",
            native_effect_uid_next=None,
            owned_stat_effects={},
            state_wire_payloads={},
        )
        snapshot = SimpleNamespace(
            physical_radius=0, install=lambda target: setattr(target, "hp", 7)
        )
        with patch(
            "wakfu_server.combat.combat_actor_snapshot.build_npc_snapshot",
            return_value=snapshot,
        ), patch(
            "wakfu_server.combat.combat_qi_fight.prepare_fresh_actor_slots",
            return_value=object(),
        ), patch(
            "wakfu_server.combat.combat_qi_fight.install_fresh_actor_slots"
        ), patch(
            "wakfu_server.combat.combat_npc_initialization.initial_plans",
            return_value={},
        ), patch(
            "wakfu_server.combat.combat_npc_initialization.initialize_ordinary_npcs"
        ) as constructor:
            initialize_fight_snapshots(
                fight,
                characters={},
                monsters={actor.id: {"ref": 6}},
                wp_resources={actor.id: (0, 0)},
                running_effects={actor.id: ()},
                initial_effect_uid=1,
            )
        constructor.assert_not_called()
        self.assertIs(fight.actors[actor.id], actor)
        self.assertEqual(actor.hp, 7)
        self.assertEqual(fight.native_effect_uid_next, 1)
        self.assertFalse(hasattr(fight, "native_npc_initialization_receipts"))

    def test_native_triples_inherit_descriptor_level_and_respect_activation(self):
        actor = self.actor()
        fight = SimpleNamespace(actors={actor.id: actor})
        monsters = {actor.id: dict(id=actor.id, ref=6)}
        policy = dict(
            schema="native-npc-activation-v1",
            enabled_monsters={
                "6": dict(
                    min_level=1,
                    max_level=9,
                    initial_state_triples=[123, -1, 0, 456, 2, 1],
                ),
            },
        )
        with patch(
            "wakfu_server.combat.combat_npc_attack.npc_spell_catalog",
            return_value={"activation_policy": policy},
        ):
            reference, raw, plan = initial_plans(fight, monsters)[actor.id]
            self.assertEqual(reference, 6)
            self.assertEqual(raw, (123, -1, 0, 456, 2, 1))
            self.assertEqual(
                [(p.level, p.native_rBq, p.native_rBr) for p in plan],
                [(5, True, True), (2, False, True)],
            )
            actor.effective_level = 10
            self.assertEqual(initial_plans(fight, monsters), {})
            actor.effective_level = 5
            policy["enabled_monsters"]["6"]["initial_state_triples"] = None
            with self.assertRaises(ValueError):
                initial_plans(fight, monsters)

    def test_rejecting_constructor_does_not_mutate_live_fight(self):
        actor = self.actor()
        fight = SimpleNamespace(
            actors={actor.id: actor},
            phase="placement",
            native_effect_uid_next=None,
            owned_stat_effects={},
            state_wire_payloads={},
        )
        before_actor = deepcopy(
            {k: v for k, v in actor.__dict__.items() if k != "state_ledger"}
        )
        before_ledger = deepcopy(actor.state_ledger.entries)
        snapshot = SimpleNamespace(
            physical_radius=0, install=lambda target: setattr(target, "hp", 7)
        )

        def reject(preview, monsters, plans):
            preview.actors[actor.id].hp = 1
            preview.native_effect_uid_next += 1
            preview.owned_stat_effects[1] = {"partial": True}
            raise ValueError("Unsupported constructor child")

        with patch(
            "wakfu_server.combat.combat_actor_snapshot.build_npc_snapshot",
            return_value=snapshot,
        ), patch(
            "wakfu_server.combat.combat_qi_fight.prepare_fresh_actor_slots",
            return_value=object(),
        ), patch(
            "wakfu_server.combat.combat_npc_initialization.initial_plans",
            return_value={actor.id: object()},
        ), patch(
            "wakfu_server.combat.combat_npc_initialization.initialize_ordinary_npcs",
            side_effect=reject,
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported constructor child"):
                initialize_fight_snapshots(
                    fight,
                    characters={},
                    monsters={actor.id: {"ref": 6}},
                    wp_resources={actor.id: (0, 0)},
                    running_effects={actor.id: ()},
                    initial_effect_uid=1,
                )
        self.assertIs(fight.actors[actor.id], actor)
        self.assertEqual(
            {k: v for k, v in actor.__dict__.items() if k != "state_ledger"},
            before_actor,
        )
        self.assertEqual(actor.state_ledger.entries, before_ledger)
        self.assertIsNone(fight.native_effect_uid_next)
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(fight.state_wire_payloads, {})
        self.assertEqual(fight.phase, "placement")


if __name__ == "__main__":
    unittest.main()
