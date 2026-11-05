"""Focused private candidate validation; no native Fight execution claim."""
import copy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import unittest
from wakfu_server.combat_encounter_scene_states import (
    prepare_scene_states,
    SceneStatePlan,
    install_scene_states,
    native_state_source_digest,
    validates_scene_receipt,
    deliver_scene_round_start,
    has_scene_round_interest,
)
from wakfu_server.combat_state import Actor
from wakfu_server.combat_summon_initial_states import NativeSummonInitialState
from unittest.mock import patch


class SceneStatesTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "states": {
                "7592": dict(
                    maximum_level=1,
                    duration_base=-1,
                    duration_per_level=0,
                    realtime_duration_base=0,
                    realtime_duration_per_level=0,
                    clock_actor=0,
                    tick_at_turn_end=False,
                    additive=False,
                    replace=False,
                    refresh=False,
                    protected=False,
                    skip_turn_timer=False,
                    effect_ids=[341747, 341758],
                )
            },
            "effects": {
                str(r): dict(minimum_level=0, maximum_level=32767, effect_class=345)
                for r in (341747, 341758)
            },
        }
        self.actor = SimpleNamespace(id=-1, effective_level=40, controlled=False)
        self.fight = SimpleNamespace(actors={-1: self.actor})
        self.monsters = {-1: {"ref": 5373}}
        self.row = dict(
            actor_id=-1,
            ref=5373,
            descriptor_level=40,
            policy_id="reviewed-pohl-room1",
            authority="Wakemu reviewed scene authoring",
            source_uri="native:state/7592",
            states=[
                dict(
                    state_id=7592,
                    level=1,
                    protected=False,
                    source_sha256=native_state_source_digest(self.catalog, 7592),
                )
            ],
        )

    def plans(self, rows=None):
        return prepare_scene_states(
            self.fight,
            self.monsters,
            [self.row] if rows is None else rows,
            catalog=self.catalog,
        )

    def test_empty_default_has_no_catalog_or_mutation(self):
        before = copy.deepcopy(self.fight.__dict__)
        self.assertEqual(prepare_scene_states(self.fight, self.monsters, ()), ())
        self.assertEqual(self.fight.__dict__.keys(), before.keys())

    def test_absent_scene_round_source_is_noop_without_catalog_or_clock(self):
        self.assertFalse(has_scene_round_interest(self.fight))
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=self.fight))
        self.assertEqual(deliver_scene_round_start(dispatcher, {}), ())

    def test_actual_identity_and_scene_lineage_without_innate_receipt(self):
        p = self.plans()[0]
        self.assertEqual((p.actor_id, p.reference, p.descriptor_level), (-1, 5373, 40))
        self.assertEqual(p.states[0].state_id, 7592)
        self.assertFalse(hasattr(self.fight, "native_npc_initialization_receipts"))
        self.assertEqual(tuple(self.fight.actors), (-1,))

    def test_scene_state_installation_preserves_prepared_native_bje_status(self):
        actor = Actor(-12, 1, (1, 2, 0), 100, 6, 3, 10, 40)
        actor.native_fight_properties = frozenset()
        status = {
            "source": "fresh.bjm.constructor",
            "actor_kind": "bje",
            "mwD": True,
            "dtM_status": "restored-status",
            "last_writer": "owned.state.transition",
        }
        actor.native_death_status = dict(status)
        fight = SimpleNamespace(actors={actor.id: actor})
        monsters = {actor.id: {"id": actor.id, "ref": 5373}}
        plan = SceneStatePlan(
            actor_id=actor.id,
            reference=5373,
            descriptor_level=40,
            policy_id="reviewed-scene",
            authority="test fixture",
            source_uri="native:state/7592",
            states=(NativeSummonInitialState(7592, 1, False),),
            source_digests=("fixture-digest",),
            repeat_roots=(),
        )

        def install_states(_fight, _actor, states, *, runtime_factory, application_results):
            application_results.extend(
                dict(state_id=state.state_id, level=state.level, applied=True)
                for state in states
            )

        with patch(
            "wakfu_server.combat_npc_initialization._runtime",
            return_value=(object(), object()),
        ), patch(
            "wakfu_server.combat_summon_initialization.install_initial_states",
            side_effect=install_states,
        ):
            install_scene_states(fight, monsters, (plan,))

        self.assertEqual(actor.native_death_status, status)
        self.assertEqual(
            fight.native_encounter_scene_state_receipts[actor.id]["applications"],
            [dict(state_id=7592, level=1, applied=True)],
        )

    def test_rejects_ghost_ref_level_or_duplicate_actor(self):
        for key, value in (("actor_id", -2), ("ref", 5374), ("descriptor_level", 41)):
            row = copy.deepcopy(self.row)
            row[key] = value
            with self.assertRaises(ValueError):
                self.plans([row])
        with self.assertRaises(ValueError):
            self.plans([self.row, self.row])

    def test_native_callback_changes_reject_before_mutation(self):
        self.catalog["effects"]["341747"]["effect_class"] = 304
        with self.assertRaisesRegex(ValueError, "program source changed"):
            self.plans()
        self.assertFalse(hasattr(self.fight, "native_encounter_scene_state_receipts"))

    def test_missing_provenance_or_untyped_state_rejected(self):
        for key, value in (("authority", ""), ("policy_id", None), ("source_uri", "")):
            row = copy.deepcopy(self.row)
            row[key] = value
            with self.assertRaises(ValueError):
                self.plans([row])
        self.row["states"][0]["protected"] = 1
        with self.assertRaises(ValueError):
            self.plans()

    def test_separate_receipt_needs_complete_native_applications(self):
        p = self.plans()[0]
        receipt = dict(
            kind="wakemu.reviewed_encounter_scene_states",
            actor_id=-1,
            ref=5373,
            descriptor_level=40,
            initialized=True,
            policy_id=p.policy_id,
            authority=p.authority,
            source_uri=p.source_uri,
            resolved_states=[asdict(s) for s in p.states],
            source_digests=list(p.source_digests),
            applications=[dict(state_id=7592, level=1, applied=True)],
        )
        self.fight.native_encounter_scene_state_receipts = {-1: receipt}
        self.assertTrue(validates_scene_receipt(self.fight, -1))
        receipt["applications"][0]["applied"] = False
        with self.assertRaises(ValueError):
            validates_scene_receipt(self.fight, -1)

    def test_snapshot_keyword_is_on_actual_initializer_only(self):
        import ast

        path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/combat/combat_actor_snapshot.py"
        )
        tree = ast.parse(path.read_text())
        functions = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }

        def kwargs(name):
            return [arg.arg for arg in functions[name].args.kwonlyargs]

        self.assertIn("scene_state_declarations", kwargs("initialize_fight_snapshots"))
        self.assertNotIn("scene_state_declarations", kwargs("build_player_snapshot"))

    def test_round_replay_selects_only_owned_declared_root_once(self):
        p = self.plans()[0]
        receipt = dict(
            kind="wakemu.reviewed_encounter_scene_states",
            actor_id=-1,
            ref=5373,
            descriptor_level=40,
            initialized=True,
            policy_id=p.policy_id,
            authority=p.authority,
            source_uri=p.source_uri,
            resolved_states=[asdict(state) for state in p.states],
            source_digests=list(p.source_digests),
            applications=[dict(state_id=7592, level=1, applied=True)],
            state_uids=[dict(state_id=7592, uid=100)],
            repeat_at_round_start=[dict(state_id=7592, root=341758)],
        )
        self.fight.native_encounter_scene_state_receipts = {-1: receipt}
        self.actor.hp = 100
        self.actor.state_ledger = SimpleNamespace(
            entries=[SimpleNamespace(uid=100, reference=7592, target_id=-1)]
        )
        self.fight.phase = "active"
        self.fight.native_timeline_round = 2
        self.fight.native_table_turn = 2
        self.fight.native_owned_group_effects = {
            101: dict(invocation=dict(state_uid=100))
        }
        entries = [
            SimpleNamespace(uid=101, manager_id=-1, generic_effect=341758),
            SimpleNamespace(uid=102, manager_id=-1, generic_effect=123),
        ]
        events = []
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(
                fight=self.fight, view=lambda: SimpleNamespace(entries=entries)
            ),
            native_clone_authority=object(),
            replay_event=lambda event, **kwargs: events.append((event, kwargs)) or (),
        )
        completed = dict(completed_round=1, delivered=True)
        self.assertEqual(deliver_scene_round_start(dispatcher, completed), ())
        self.assertEqual(events[0][1]["eligible_uids"], frozenset({101}))
        self.assertEqual(len(events), 1)
        deliver_scene_round_start(dispatcher, completed)
        self.assertEqual(len(events), 1)
        self.assertFalse(hasattr(self.fight, "native_npc_initialization_receipts"))
        del self.fight.native_encounter_scene_round_starts
        self.fight.native_owned_group_effects[101]["invocation"]["state_uid"] = 999
        with self.assertRaisesRegex(ValueError, "actual installed state UID"):
            deliver_scene_round_start(dispatcher, completed)


if __name__ == "__main__":
    unittest.main()
