"""Reconstruction contracts over selected committed Nox terminal evidence.

The captured KO/calendar is a component premise. These tests do not earn a new
score or replay an END; actual v5 evidence is recorded separately.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import psycopg
from postgres_case import PostgresCase


class NoxTerminalHelperCleanupTests(PostgresCase):
    def fixture(self):
        from wakfu_server import combat_encounter_terminal_cleanup as cleanup
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_state_ledger import RunningState

        for module in (cleanup, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        data = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "nox_terminal_cleanup_committed_evidence.json"
            ).read_text()
        )
        actors = []
        for raw in data["actors"].values():
            actor = Actor(
                raw["id"],
                raw["team"],
                tuple(raw["position"]),
                max(1, raw["hp"]),
                raw["ap"],
                raw["mp"],
                raw["initiative"],
                raw["effective_level"],
                raw["owner_id"],
                raw["controlled"],
                max_hp=raw["max_hp"],
            )
            for key, value in raw.items():
                if key == "state_ledger":
                    entries = []
                    for state in value["entries"]:
                        state = dict(state, effect_ids=tuple(state["effect_ids"]))
                        self.assertIsNone(state["timer"])
                        entries.append(RunningState(**state))
                    actor.state_ledger._entries = tuple(entries)
                elif (
                    key.startswith("effect_") or key.endswith("_property_counts")
                ) and isinstance(value, dict):
                    setattr(actor, key, {int(k): v for k, v in value.items()})
                elif key in (
                    "effect_frozen",
                    "native_fight_properties",
                    "native_world_properties",
                ):
                    setattr(actor, key, frozenset(value))
                elif key not in ("id", "position"):
                    setattr(actor, key, deepcopy(value))
            actors.append(actor)
        fight = Fight(
            78,
            actors,
            {a.position for a in actors},
            {team: {a.position for a in actors if a.team == team} for team in (0, 1)},
        )
        for key, value in data.items():
            if key.startswith("native_"):
                if key in (
                    "native_npc_initialization_receipts",
                    "native_summon_registrations",
                    "native_owned_group_effects",
                    "native_summon_creation_deliveries",
                ):
                    value = {int(k): v for k, v in value.items()}
                setattr(fight, key, deepcopy(value))
        fight.events = deepcopy(data["events"])
        # This compact restoration component initializes its own canonical PV/QI
        # collections; it does not impersonate the full original roster.
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )

        fight.actors[-200].hp = 1
        for actor in fight.actors.values():
            actor.physical_radius = 0
        fight.native_qi_snapshot = dict(
            x=-10, y=-22, width=12, height=10, cell_masks=[0] * 120
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight, physical_radii={identity: 0 for identity in fight.actors}
            ),
        )
        fight.actors[-200].hp = 0
        from wakfu_server.combat_ordinary_death import registered_ordinary_death
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        self.assertTrue(registered_ordinary_death(fight, fight.actors[-200]))
        set_global_fighter_status(fight, -200, "OFF_PLAY")
        fight.order = [4, 340, 380]
        fight.turn_index = 0
        from wakfu_server.combat_timeline_snapshot import (
            initialize as initialize_timeline,
        )

        initialize_timeline(fight, fight.order)
        fight.native_timeline_round = 12
        fight.sequence = max(event["sequence"] for event in fight.events)
        fight.turn_id = 126
        fight.native_table_turn = 12
        fight.phase = "placement"
        assignment = roles.frozen_roles(fight)
        frozen = cleanup.freeze_terminal_cleanup_policy(fight, roles=assignment)
        fight.phase = "active"
        return cleanup, assignment, fight, frozen

    def test_immutable_version_pinned_pointer_absence_scope_and_descriptor(self):
        cleanup, assignment, fight, frozen = self.fixture()
        self.assertEqual(frozen["helper_references"], [5783, 5786])
        with self.store.connection() as db:
            with self.assertRaises(psycopg.Error):
                with db.transaction():
                    db.execute(
                        "UPDATE encounter_terminal_cleanup_helpers SET constructor_state=1 WHERE policy=%s",
                        (frozen["policy"],),
                    )
            db.execute(
                "DELETE FROM encounter_terminal_cleanup_active WHERE map_id=1435"
            )
        self.assertEqual(
            cleanup.freeze_terminal_cleanup_policy(fight, roles=assignment), frozen
        )
        absent = SimpleNamespace(phase="placement")
        self.assertIsNone(
            cleanup.freeze_terminal_cleanup_policy(absent, roles=assignment)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_terminal_cleanup_active VALUES (1435,ARRAY[5664],%s)",
                (frozen["policy"],),
            )
        self.assertIsNone(
            cleanup.freeze_terminal_cleanup_policy(absent, roles=assignment)
        )
        with self.assertRaisesRegex(ValueError, "admission"):
            cleanup.freeze_terminal_cleanup_policy(
                SimpleNamespace(phase="active"), roles=assignment
            )
        altered = deepcopy(frozen)
        altered["cleanup_effect_reference"] = 402298
        with self.assertRaises(ValueError):
            cleanup.terminal_cleanup_from_record(altered)
        wrong = SimpleNamespace(map_id=1332, monster_references=(5306,))
        with self.assertRaises(ValueError):
            cleanup.freeze_terminal_cleanup_policy(fight, roles=wrong)

    def test_committed_ko_birth_and_calendar_authority_reject_forged_or_foreign_evidence(
        self,
    ):
        cleanup, _, fight, frozen = self.fixture()
        plan = cleanup.prepare_terminal_cleanup(fight, frozen)
        self.assertEqual(
            (
                plan["kill_uid"],
                plan["kill_sequence"],
                plan["caster_id"],
                plan["turn_id"],
                plan["table_turn"],
                plan["target_ids"],
            ),
            (18301, 4287, 4, 119, 11, [340, 380]),
        )
        mutations = (
            lambda f: f.native_turn_event_deliveries.clear(),
            lambda f: f.native_encounter_post_start_deliveries.clear(),
            lambda f: f.native_owned_group_effects[18311]["invocation"][
                "native_trigger_context"
            ].update(uid=1),
            lambda f: f.native_owned_group_effects[18311]["invocation"][
                "native_trigger_context"
            ].update(native_events_verified=False),
            lambda f: f.native_summon_registrations[340]["authority"].update(
                native_controller_id=-200
            ),
            lambda f: setattr(f.actors[340], "native_master_id", -200),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                candidate = deepcopy(fight)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    cleanup.prepare_terminal_cleanup(candidate, frozen)
        candidate = deepcopy(fight)
        candidate.actors[340].native_summon_source["caster_id"] = 7
        self.assertEqual(
            cleanup.prepare_terminal_cleanup(candidate, frozen)["target_ids"], [380]
        )
        live = deepcopy(fight)
        live.actors[-200].hp = 1
        self.assertIsNone(cleanup.prepare_terminal_cleanup(live, frozen))
        hostile = deepcopy(fight.actors[340])
        hostile.id = 999
        hostile.native_summon_source["caster_id"] = -999
        candidate = deepcopy(fight)
        candidate.actors[999] = hostile
        self.assertEqual(
            cleanup.prepare_terminal_cleanup(candidate, frozen)["target_ids"],
            [340, 380],
        )
        self.assertFalse(hasattr(fight, "native_encounter_terminal_cleanup_deliveries"))

    def dispatcher(self, fight, frozen):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_kill import NativeKillHandler
        from wakfu_server.combat_stat_handler import StatExecutionContext

        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 401564
        )
        sequence = iter(range(20000, 20100))
        handler = NativeKillHandler(
            fight,
            [],
            action_id=5,
            allocate_uid=lambda: next(sequence),
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            rng=lambda: 0,
            authority=SimpleNamespace(
                property_counts=lambda p, a: getattr(
                    a, "native_fight_property_counts", {}
                )
            ),
        )
        phase_uid = next(
            s.uid
            for s in fight.actors[-200].state_ledger.entries
            if s.reference == 8979
        )

        def original_kill(definition, values, invocation):
            self.assertEqual(invocation.state_uid, phase_uid)
            return handler(definition, values, invocation)

        dispatcher = EffectDispatcher(
            {"401564": effect},
            {28: original_kill},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda inv: ConditionContext(
                {
                    "target": ConditionActor(
                        breed_id=fight.actors[inv.target_id].native_summon_source["ref"]
                    )
                }
            ),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: fight.actors[identity].position,
            prepare_effect=handler.prepare,
        )
        dispatcher.native_retention = SimpleNamespace(fight=fight)
        dispatcher.original_native_kill_handler = handler
        return dispatcher

    def test_original_kill_dispatch_private_preview_and_terminal_journal_once(self):
        cleanup, _, fight, frozen = self.fixture()
        before = deepcopy(fight)
        candidate = deepcopy(fight)
        dispatcher = self.dispatcher(candidate, frozen)
        self.assertEqual(
            cleanup.deliver_terminal_helper_cleanup(dispatcher), (340, 380)
        )
        self.assertEqual([candidate.actors[i].hp for i in (340, 380)], [0, 0])
        self.assertEqual([fight.actors[i].hp for i in (340, 380)], [3600, 1200])
        self.assertEqual(fight.events, before.events)
        self.assertEqual(cleanup.deliver_terminal_helper_cleanup(dispatcher), ())
        kills = [
            e
            for e in candidate.events
            if e.get("kind") == "kill_hp_minimum_update"
            and e.get("target_id") in (340, 380)
        ]
        self.assertEqual(len(kills), 2)
        self.assertTrue(
            all(e["source_id"] == 4 and e["effect_class"] == 28 for e in kills)
        )
        self.assertEqual(candidate.actors[-200].hp, 0)
        self.assertGreater(candidate.actors[4].hp, 0)
        journal = candidate.native_encounter_terminal_cleanup_deliveries
        self.assertEqual(len(journal), 1)
        self.assertEqual(next(iter(journal.values()))["kill_uid"], 18301)
        invalid = deepcopy(fight)
        bad_dispatcher = self.dispatcher(invalid, frozen)
        bad_dispatcher.effects["401564"] = dict(
            bad_dispatcher.effects["401564"], criteria="True"
        )
        with self.assertRaises(ValueError):
            cleanup.deliver_terminal_helper_cleanup(bad_dispatcher)
        self.assertEqual(invalid.actors[340].hp, 3600)
        invalid = deepcopy(fight)
        invalid.native_summon_creation_deliveries[380]["opcode"] = 1
        with self.assertRaises(ValueError):
            cleanup.deliver_terminal_helper_cleanup(self.dispatcher(invalid, frozen))
        self.assertEqual([invalid.actors[i].hp for i in (340, 380)], [3600, 1200])
        self.assertFalse(
            hasattr(invalid, "native_encounter_terminal_cleanup_deliveries")
        )

        # Future native kills carry their own source/container provenance; no
        # unrelated passive subscription is required to authenticate cleanup.
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        future = deepcopy(fight)
        future.events = [deepcopy(fight.events[0])]
        future.native_owned_group_effects = {}
        boss = future.actors[-200]
        boss.hp = 1
        boss.effect_stats[1] = 1
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        set_global_fighter_status(future, -200, "IN_PLAY")
        native = self.dispatcher(future, frozen).original_native_kill_handler
        kill = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 402298
        )
        invocation = EffectInvocation(
            402298,
            1,
            4,
            -200,
            boss.position,
            native_explicit_target=True,
            state_uid=next(
                s.uid for s in boss.state_ledger.entries if s.reference == 8979
            ),
        )
        self.assertTrue(native(kill, {}, invocation))
        plan = cleanup.prepare_terminal_cleanup(future, frozen)
        self.assertEqual(plan["target_ids"], [340, 380])
        event = next(
            e for e in future.events if e.get("kind") == "kill_hp_minimum_update"
        )
        self.assertEqual(event["generic_effect"], 402298)
        self.assertEqual(event["native_container"]["state_id"], 8979)
        for changes in (
            {"generic_effect": 401564},
            {"native_container": dict(is_state=True, state_id=8969)},
        ):
            bad = deepcopy(future)
            next(
                e for e in bad.events if e.get("kind") == "kill_hp_minimum_update"
            ).update(changes)
            with self.assertRaises(ValueError):
                cleanup.prepare_terminal_cleanup(bad, frozen)
