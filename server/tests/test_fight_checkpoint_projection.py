"""Focused regression for the isolated versioned checkpoint projection."""
import json
import sys
from threading import RLock
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server import fight_checkpoint_store as checkpoints
from wakfu_server import combat_state_ledger

RunningState, StateLedger = (
    combat_state_ledger.RunningState,
    combat_state_ledger.StateLedger,
)


class Fight(SimpleNamespace):
    pass


def actor(identity, *, controlled=True, full=True):
    fields = dict(
        id=identity,
        controlled=controlled,
        owner_id=77 if controlled else None,
        team=0 if controlled else 1,
        hp=75,
        max_hp=100,
        effective_level=230,
        position=(4, 5, 0),
        is_summon=False,
        native_summon_source=None,
        native_companion_source=None,
        pve_withdrawn=False,
        ap=6,
        mp=3,
        turn_count=8,
        effect_stats={33: 12, 36: 42, 118: 100, 119: 115, 1: 900, 9001: 10},
    )
    if full:
        fields.update(
            effect_maxima={i: i * 10 for i in range(40)},
            native_effect_runtime={"deep": ["large", "discard"]},
            debug_blob="x" * 8192,
        )
    result = SimpleNamespace(**fields)
    result.state_ledger = StateLedger(identity)
    result.state_ledger._entries = (
        RunningState(
            501,
            987,
            1,
            identity,
            identity,
            0,
            "turn",
            False,
            (45980,),
            240000,
            True,
            None,
        ),
        RunningState(
            502, 1001, 1, identity, identity, 0, "turn", False, (123,), 0, False, None
        ),
        RunningState(
            503,
            981,
            1,
            identity,
            identity,
            0,
            "turn",
            False,
            (45980,),
            240000,
            True,
            None,
        ),
    )
    return result


def make_fight(phase="active"):
    controlled = actor(42)
    fight = Fight(
        id=902,
        phase=phase,
        winner=None,
        turn_id=12,
        turn_index=1,
        order=[42, -5],
        native_timeline_round=7,
        native_fight_model={"kind": "fight", "version": 1},
        native_encounter_roles={"player_team": 0, "npc_team": 1},
        actors={42: controlled, -5: actor(-5, controlled=False)},
        native_summon_registrations={},
        native_companion_sources={},
        native_consumable_initializations={
            42: (
                {
                    "combat_uid": 501,
                    "state_id": 987,
                    "world_uid": 7001,
                    "handoff_target": {"state_id": 981},
                },
            )
        },
        native_external_state_origins={
            503: {
                "kind": "native-state",
                "combat_uid": 503,
                "character_id": 42,
                "fight_id": 902,
                "effect_id": 45980,
                "parent_state_id": 987,
                "parent_uid": 90,
                "source_uid": 91,
            }
        },
        state_wire_payloads={
            "503": {"payload": "required"},
            "502": {"payload": "unrelated"},
        },
        rift_monsters={-5: {"id": -5, "ref": 501, "level": 230, "instance_id": 600}},
        rift_wave_state={
            "instance_id": 600,
            "wave": 4,
            "outcome": "active",
            "persisted_wave": 3,
            "staged_receipts": [],
            "last_cleared_wave": 3,
            "pending_wave": 4,
            "wave_actor_ids": [-5],
            "wave_species_refs": [501],
            "native_artifact_groups": {"large": "drop"},
        },
        large_transient_graph={"effect": ["x"] * 1000},
    )
    return fight


class CheckpointProjectionTests(unittest.TestCase):
    def test_full_api_and_active_projection_preserve_recovery_evidence(self):
        fight = make_fight()
        full = checkpoints.snapshot(fight)
        projected = checkpoints.recovery_snapshot(fight)
        self.assertNotIn("checkpoint_schema", full)
        self.assertIn("large_transient_graph", full)
        self.assertEqual(projected["checkpoint_schema"], checkpoints.RECOVERY_SCHEMA)
        self.assertNotIn("large_transient_graph", projected)
        self.assertNotIn("effect_maxima", projected["actors"]["42"])
        self.assertEqual(
            projected["actors"]["42"]["effect_stats"],
            {"33": 12, "36": 42, "118": 100, "119": 115},
        )
        self.assertEqual(projected["actors"]["42"]["state_ledger"]["actor_id"], 42)
        entries = projected["actors"]["42"]["state_ledger"]["entries"]
        self.assertEqual([row["uid"] for row in entries], [501, 503])
        self.assertEqual(
            projected["native_external_state_origins"]["503"]["source_uid"], 91
        )
        self.assertEqual(
            projected["state_wire_payloads"], {"503": {"payload": "required"}}
        )
        self.assertNotIn("native_artifact_groups", projected["rift_wave_state"])
        self.assertEqual(projected["rift_monsters"]["-5"]["ref"], 501)
        self.assertEqual(projected["native_encounter_roles"]["player_team"], 0)

    def test_active_save_uses_v2_but_terminal_save_keeps_full_snapshot(self):
        class Capture(checkpoints.Checkpoints):
            def __init__(self):
                self.state = None

            def save_prepared(self, account_id, generation, fight, state, **kwargs):
                self.state = state
                return 19

        for phase, schema in (
            ("active", checkpoints.RECOVERY_SCHEMA),
            ("finished", None),
        ):
            writer = Capture()
            result = writer.save(77, "g", make_fight(phase), expected_revision=18)
            self.assertEqual(result, 19)
            self.assertEqual(writer.state.get("checkpoint_schema"), schema)
            self.assertEqual("large_transient_graph" in writer.state, schema is None)

        from wakfu_server import checkpoint_worker

        serialize_detached = checkpoint_worker.serialize_detached
        for phase, schema in (
            ("active", checkpoints.RECOVERY_SCHEMA),
            ("finished", None),
        ):
            fight = make_fight(phase)
            runtime = SimpleNamespace(
                fight=fight,
                action_id=1,
                native_action_id=2,
                awaiting_ack=False,
                round=3,
                duration=4,
            )
            serialized = serialize_detached(fight, runtime=runtime)
            self.assertEqual(serialized.get("checkpoint_schema"), schema)
            self.assertEqual("large_transient_graph" in serialized, schema is None)

    def test_consumable_projection_restores_only_bound_carrier_and_external_payload(
        self,
    ):
        fight = make_fight()
        projected = checkpoints.recovery_snapshot(fight)
        restored = make_fight()
        restored.actors[42].state_ledger = StateLedger(42)
        from wakfu_server import combat_consumable_states

        restore_checkpoint_projection = (
            combat_consumable_states.restore_checkpoint_projection
        )
        restore_checkpoint_projection(restored, projected)
        self.assertEqual(
            [entry.uid for entry in restored.actors[42].state_ledger.entries],
            [501, 503],
        )
        self.assertEqual(
            restored.native_consumable_initializations[42][0]["combat_uid"], 501
        )
        self.assertEqual(restored.native_external_state_origins[503]["source_uid"], 91)
        self.assertEqual(restored.state_wire_payloads[503], {"payload": "required"})

    def test_expired_bound_carrier_keeps_binding_without_unrelated_ledger_rows(self):
        fight = make_fight()
        fight.native_consumable_initializations = {
            42: ({"combat_uid": 999, "state_id": 987, "world_uid": 7001},)
        }
        fight.native_external_state_origins = {}
        fight.actors[42].state_ledger = StateLedger(42)
        projected = checkpoints.recovery_snapshot(fight)
        self.assertEqual(
            projected["native_consumable_initializations"]["42"][0]["combat_uid"], 999
        )
        self.assertEqual(projected["actors"]["42"]["state_ledger"]["entries"], [])
        restored = make_fight()
        from wakfu_server import combat_consumable_states

        restore_checkpoint_projection = (
            combat_consumable_states.restore_checkpoint_projection
        )
        restore_checkpoint_projection(restored, projected)
        self.assertEqual(
            restored.native_consumable_initializations[42][0]["combat_uid"], 999
        )
        self.assertEqual(restored.actors[42].state_ledger.entries, ())

    def test_runtime_identity_is_checked_and_fields_are_retained(self):
        fight = make_fight()
        runtime = SimpleNamespace(
            fight=fight,
            action_id=4,
            native_action_id=5,
            awaiting_ack=False,
            round=7,
            duration=8,
        )
        result = checkpoints.recovery_snapshot(fight, runtime=runtime)
        self.assertEqual(
            result["runtime"],
            {
                "action_id": 4,
                "native_action_id": 5,
                "awaiting_ack": False,
                "round": 7,
                "duration": 8,
            },
        )
        with self.assertRaisesRegex(ValueError, "another fight"):
            checkpoints.recovery_snapshot(
                fight, runtime=SimpleNamespace(fight=make_fight())
            )

    def test_versioned_read_skips_container_reconstruction_and_digest_is_versioned(
        self,
    ):
        versioned = checkpoints.recovery_snapshot(make_fight())
        import types

        module_name = "wakfu_server.combat_checkpoint_containers"
        fake_module = types.ModuleType(module_name)
        fake_module.reconstruct_state_containers = lambda _raw: (_ for _ in ()).throw(
            AssertionError("must not reconstruct v2")
        )
        with patch.dict(sys.modules, {module_name: fake_module}):
            self.assertIs(checkpoints.Checkpoints._read_snapshot(versioned), versioned)
        legacy = {"id": 2, "phase": "active", "actors": {}}
        sentinel = {"legacy": True}
        calls = []
        fake_module.reconstruct_state_containers = (
            lambda raw: calls.append(raw) or sentinel
        )
        with patch.dict(sys.modules, {module_name: fake_module}):
            self.assertIs(checkpoints.Checkpoints._read_snapshot(legacy), sentinel)
        self.assertEqual(calls, [legacy])
        changed = dict(versioned, checkpoint_schema="wakemu.fight-checkpoint.v3")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            checkpoints.Checkpoints._read_snapshot(changed)
        self.assertNotEqual(
            checkpoints.checkpoint_digest(versioned),
            checkpoints.checkpoint_digest(
                dict(versioned, checkpoint_schema="different")
            ),
        )

    def test_worker_active_detach_skips_irrelevant_graph_and_freezes_source(self):
        from wakfu_server import checkpoint_worker, combat_retained_collections

        source = make_fight()
        owned_actors = combat_retained_collections.OwnedMap(None, "actors")
        for identity, value in source.actors.items():
            owned_actors[identity] = value
        source.actors = owned_actors

        class Poison:
            def __deepcopy__(self, memo):
                raise AssertionError("irrelevant graph must not be visited")

        source.poisoned_runtime_graph = Poison()
        source.native_rift_creation_deliveries = Poison()
        source.native_rift_birth_locations = Poison()
        source.rift_wave_state["native_wave_entries"] = {
            "current": {"wave": 4, "actor_ids": [-5]},
            "old": {"wave": 3, "actor_ids": [-9]},
        }
        runtime = SimpleNamespace(
            fight=source,
            action_id=7,
            native_action_id=8,
            awaiting_ack=False,
            round=9,
            duration=10,
        )
        shared = SimpleNamespace(
            lock=RLock(), fight=source, runtime=runtime, checkpoint_revision=22
        )
        (
            frozen,
            detached_runtime,
            revision,
        ) = checkpoint_worker._detach_active_projection(shared)
        self.assertEqual(revision, 22)
        self.assertIsNot(frozen.actors, source.actors)
        self.assertEqual(type(frozen.actors), dict)
        source.actors[42].hp = 1
        source.native_encounter_roles["player_team"] = 9
        serialized = checkpoint_worker.serialize_detached(
            frozen, runtime=detached_runtime
        )
        self.assertEqual(serialized["actors"]["42"]["hp"], 75)
        self.assertEqual(serialized["native_encounter_roles"]["player_team"], 0)
        self.assertEqual(serialized["checkpoint_schema"], checkpoints.RECOVERY_SCHEMA)
        self.assertNotIn("poisoned_runtime_graph", serialized)
        self.assertNotIn("native_rift_creation_deliveries", frozen.__dict__)
        self.assertNotIn("native_rift_birth_locations", frozen.__dict__)
        self.assertEqual(
            set(frozen.rift_wave_state),
            {
                "instance_id",
                "wave",
                "outcome",
                "persisted_wave",
                "staged_receipts",
                "last_cleared_wave",
                "pending_wave",
                "wave_actor_ids",
                "wave_species_refs",
            },
        )
        self.assertEqual(
            serialized["rift_wave_state"]["native_wave_entries"],
            {"current": {"wave": 4, "actor_ids": [-5]}},
        )

    def test_custom_and_terminal_detach_keep_full_snapshot_path(self):
        from wakfu_server import checkpoint_worker

        fight = make_fight()
        shared = SimpleNamespace(
            lock=RLock(), fight=fight, runtime=None, checkpoint_revision=3
        )
        full, runtime, revision = checkpoint_worker.detach(shared)
        self.assertEqual(revision, 3)
        custom_snapshot = checkpoints.snapshot(full, runtime=runtime)
        self.assertNotIn("checkpoint_schema", custom_snapshot)
        self.assertIn("large_transient_graph", custom_snapshot)
        terminal = make_fight("finished")
        terminal_shared = SimpleNamespace(
            lock=RLock(), fight=terminal, runtime=None, checkpoint_revision=4
        )
        full_terminal, runtime, _ = checkpoint_worker.detach(terminal_shared)
        terminal_snapshot = checkpoint_worker.serialize_detached(
            full_terminal, runtime=runtime
        )
        self.assertEqual(terminal_snapshot["phase"], "finished")
        self.assertNotIn("checkpoint_schema", terminal_snapshot)
        self.assertIn("large_transient_graph", terminal_snapshot)

        # A job queued while active can be captured after settlement. The active
        # fast path must recheck phase under the lock and switch to full evidence.
        queued = make_fight("active")
        queued.phase = "finished"
        queued_shared = SimpleNamespace(
            lock=RLock(), fight=queued, runtime=None, checkpoint_revision=5
        )
        captured, runtime, _ = checkpoint_worker._detach_active_projection(
            queued_shared
        )
        queued_snapshot = checkpoint_worker.serialize_detached(
            captured, runtime=runtime
        )
        self.assertEqual(queued_snapshot["phase"], "finished")
        self.assertNotIn("checkpoint_schema", queued_snapshot)
        self.assertIn("large_transient_graph", queued_snapshot)

    def test_bounded_qa_fields_keep_only_current_authoritative_roots(self):
        fight = make_fight()
        fight.walkable = [[1, 2, 0]]
        fight.edges = [[[1, 2, 0], [2, 2, 0]]]
        fight.native_qi_slots = [4, 7]
        fight.native_qi_snapshot = {"slots": [4, 7]}
        fight.native_qi_touched_cells = [[4, 0, 0]]
        fight.native_qi_byte_topology = {"1:2:0": 7}
        fight.native_qi_ignored_slots = [7]
        fight.native_qi_movement_override = {"actor_id": 42, "cell": [4, 5, 0]}
        fight.native_los_ignored_affiliations = [42]
        fight.native_ordinary_qi_retirements = {42: {"reason": "complete"}}
        fight.native_timeline_removed = {42, 99}
        fight.native_global_pv_collections = {
            "fighter_status": {"uid": 99, "source": "native"},
            "unrelated": {"large": True},
        }
        fight.native_effect_areas = {
            800: {
                "uid": 800,
                "reference": 1574,
                "cell": [1, 2, 0],
                "native_area_contract": "faY",
                "native_qq_bhi": False,
                "native_qq_guard_source": "frozen",
                "executing": False,
                "remaining_activations": 2,
                "large_graph": "drop",
            },
            801: {
                "uid": 801,
                "reference": 1574,
                "cell": [1, 3, 0],
                "native_area_contract": "faY",
                "native_qq_bhi": False,
                "native_qq_guard_source": "frozen",
                "executing": True,
                "remaining_activations": 2,
            },
            802: {
                "uid": 802,
                "reference": 999,
                "cell": [1, 4, 0],
                "native_area_contract": "other",
                "native_qq_bhi": False,
                "executing": False,
                "remaining_activations": 2,
            },
        }
        fight.rift_wave_state["native_wave_entries"] = {
            "a": {"wave": 4, "actor_ids": [-5]},
            "b": {"wave": 3, "actor_ids": [-9]},
        }
        fight.actors[42].physical_radius = 0.7
        fight.actors[42].native_obstacle_id = 21
        fight.actors[42].native_los_height = 1
        fight.actors[42].native_ordinary_qi_retirement = {"reason": "complete"}
        projected = checkpoints.recovery_snapshot(fight)
        self.assertEqual(projected["native_timeline_removed_count"], 2)
        self.assertEqual(
            projected["native_effect_areas"],
            {
                "800": {
                    "uid": 800,
                    "reference": 1574,
                    "cell": [1, 2, 0],
                    "native_area_contract": "faY",
                    "native_qq_bhi": False,
                    "native_qq_guard_source": "frozen",
                    "executing": False,
                    "remaining_activations": 2,
                }
            },
        )
        self.assertEqual(
            projected["native_global_pv_collections"],
            {"fighter_status": {"uid": 99, "source": "native"}},
        )
        self.assertEqual(
            projected["rift_wave_state"]["native_wave_entries"],
            {"a": {"wave": 4, "actor_ids": [-5]}},
        )
        self.assertEqual(projected["actors"]["42"]["physical_radius"], 0.7)
        self.assertEqual(projected["actors"]["42"]["native_obstacle_id"], 21)
        self.assertEqual(projected["actors"]["42"]["native_los_height"], 1)
        self.assertIn("native_qi_slots", projected)
        self.assertIn("native_qi_byte_topology", projected)
        fresh = checkpoints.recovery_snapshot(make_fight())
        self.assertEqual(fresh["native_ordinary_qi_retirements"], {})
        self.assertIsNone(fresh["native_rift_birth_fence"])

    def test_invalid_source_binding_fails_closed(self):
        fight = make_fight()
        fight.native_consumable_initializations = {42: ({"world_uid": 7001},)}
        with self.assertRaises((ValueError, KeyError)):
            checkpoints.recovery_snapshot(fight)


if __name__ == "__main__":
    unittest.main()
