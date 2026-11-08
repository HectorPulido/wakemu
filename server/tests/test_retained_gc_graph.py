"""Pure graph tests; native lifecycle attestation belongs to boundary tests."""
import unittest
from copy import deepcopy
from wakfu_server.combat_retained_gc import plan_retired_effects


def varint(value):
    value &= (1 << 64) - 1
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def scalar(number, value):
    return varint(number << 3) + varint(value)


def wire(uid, caster, target, related=0):
    data = scalar(1, uid) + scalar(2, uid) + scalar(6, caster) + scalar(7, target)
    if related:
        nested = scalar(50, related)
        data += varint(8 << 3 | 2) + varint(len(nested)) + nested
    return data.hex()


def fixture():
    snapshot = dict(
        actors={},
        native_retained_records={},
        state_wire_payloads={},
        native_owned_state_containers={},
        native_owned_group_effects={},
        owned_stat_effects={},
        native_owned_area_effects={},
        native_owned_spatial_effects={},
        native_state_source_provenance={"entries": {}},
        native_retained_order=[],
    )
    for identity in (1, -100, -200):
        snapshot["actors"][str(identity)] = {
            "id": identity,
            "state_ledger": {"entries": []},
        }

    def add(uid, owner, caster=None):
        caster = owner if caster is None else caster
        snapshot["native_retained_records"][str(uid)] = dict(
            uid=uid, manager_id=owner, target_id=owner, effect_class=310, owner_uid=None
        )
        snapshot["state_wire_payloads"][str(uid)] = wire(uid, caster, owner)
        entry = dict(uid=uid, target_id=owner, caster_id=caster, timer=None)
        snapshot["actors"][str(owner)]["state_ledger"]["entries"].append(entry)
        snapshot["native_owned_state_containers"][str(uid)] = dict(entry)
        snapshot["native_retained_order"].append(uid)

    add(10, 1)
    add(20, -100)
    add(30, -200)
    for uid, owner, state_uid in ((21, -100, 20), (22, -100, 20), (31, -200, 30)):
        snapshot["native_retained_records"][str(uid)] = dict(
            uid=uid,
            manager_id=owner,
            target_id=owner,
            effect_class=949,
            owner_uid=state_uid,
        )
        snapshot["native_owned_group_effects"][str(uid)] = dict(
            uid=uid,
            target_id=owner,
            state_uid=state_uid,
            payload=wire(uid, owner, owner),
            timer=None,
        )
        snapshot["native_retained_order"].append(uid)
    return snapshot


class RetainedGCGraphTests(unittest.TestCase):
    def plan(self, snapshot, pending=()):
        return plan_retired_effects(snapshot, {-100, -200}, pending_roots=pending)

    def test_unreachable_terminal_islands_and_live_source_alias(self):
        snapshot = fixture()
        self.assertEqual(self.plan(snapshot).effect_uids, {21, 22, 31})
        snapshot["state_wire_payloads"]["10"] = wire(10, -100, 1)
        self.assertEqual(self.plan(snapshot).effect_uids, {31})

    def test_parent_source_uid_keeps_parent_not_unrelated_sibling(self):
        snapshot = fixture()
        snapshot["native_state_source_provenance"]["entries"] = {
            "10": dict(uid=10, caster_id=1, target_id=1, parent_state_uid=19),
            "19": dict(uid=19, caster_id=-100, target_id=-100, parent_state_uid=20),
            "20": dict(uid=20, caster_id=-100, target_id=-100, parent_state_uid=None),
        }
        self.assertEqual(self.plan(snapshot).effect_uids, {21, 22, 31})

    def test_live_area_effect_uid_and_pending_unknown_uid_are_operative(self):
        snapshot = fixture()
        snapshot["native_effect_areas"] = {"900": dict(uid=900, effect_uid=20)}
        self.assertEqual(self.plan(snapshot).effect_uids, {31})
        snapshot.pop("native_effect_areas")
        self.assertEqual(self.plan(snapshot, {"future_runner": 20}).effect_uids, {31})
        self.assertEqual(self.plan(snapshot, {20: {}}).effect_uids, {31})

    def test_retired_area_is_not_automatic_root_and_related_uid_survives(self):
        snapshot = fixture()
        snapshot["native_retired_area_managers"] = {"900": dict(uid=900, effect_uid=20)}
        self.assertEqual(self.plan(snapshot).effect_uids, {21, 22, 31})
        snapshot["state_wire_payloads"]["10"] = wire(10, 1, 1, related=21)
        self.assertEqual(self.plan(snapshot).effect_uids, {22, 31})

    def test_retired_null_manager_area_source_does_not_execute_old_children(self):
        snapshot = fixture()
        row = dict(
            uid=900,
            effect_uid=10,
            native_area_contract="faM",
            native_running_effect_manager=False,
            executing=False,
            removing=False,
            child_effect_uids={"-100": [21]},
        )
        snapshot["actors"]["1"]["area_uid"] = 900
        snapshot["native_effect_areas"] = {"900": row}
        self.assertEqual(self.plan(snapshot).effect_uids, {31})
        snapshot["native_retired_area_managers"] = snapshot.pop("native_effect_areas")
        before = deepcopy(snapshot)
        self.assertEqual(self.plan(snapshot).effect_uids, {21, 22, 31})
        self.assertEqual(snapshot, before)
        snapshot["actors"]["1"]["target_id"] = 900
        self.assertEqual(self.plan(snapshot).effect_uids, {31})
        del snapshot["actors"]["1"]["target_id"]
        # Pending source execution upgrades the same identity to operational.
        self.assertEqual(self.plan(snapshot, {"area": 900}).effect_uids, {31})

    def test_retired_area_with_manager_or_active_callback_remains_operational(self):
        for field, value in (
            ("native_area_contract", "faZ"),
            ("native_running_effect_manager", True),
            ("executing", True),
            ("removing", True),
            ("state_ledger", {"entries": [{"uid": 21}]}),
        ):
            with self.subTest(field=field):
                snapshot = fixture()
                row = dict(
                    uid=900,
                    effect_uid=10,
                    native_area_contract="faM",
                    native_running_effect_manager=False,
                    executing=False,
                    removing=False,
                    child_effect_uids={"-100": [21]},
                )
                row[field] = value
                snapshot["actors"]["1"]["area_uid"] = 900
                snapshot["native_retired_area_managers"] = {"900": row}
                self.assertEqual(self.plan(snapshot).effect_uids, {31})

    def test_attested_pl3_metadata_matches_wire_but_target_stays_operational(self):
        snapshot = fixture()
        snapshot["native_retired_area_managers"] = {
            "900": dict(
                uid=900,
                effect_uid=10,
                native_area_contract="faM",
                native_running_effect_manager=False,
                executing=False,
                removing=False,
                child_effect_uids={"-100": [21]},
            )
        }
        wire_only = deepcopy(snapshot)
        wire_only["state_wire_payloads"]["10"] += (scalar(9, 3) + scalar(10, 900)).hex()
        snapshot["native_retained_records"]["10"].update(
            container_present=True,
            container_type=3,
            container_kind="effect_area",
            container_id=900,
        )
        self.assertEqual(self.plan(snapshot).effect_uids, {21, 22, 31})
        self.assertEqual(self.plan(snapshot), self.plan(wire_only))
        snapshot["actors"]["1"]["target_id"] = 900
        self.assertEqual(self.plan(snapshot).effect_uids, {31})
        del snapshot["actors"]["1"]["target_id"]
        snapshot["native_retained_records"]["10"]["container_kind"] = "unknown"
        self.assertEqual(self.plan(snapshot).effect_uids, {31})

    def test_new_orphan_descriptor_is_typed_and_matches_native_synchronize(self):
        from types import SimpleNamespace
        from wakfu_server.combat_retained_gc import sweep_retired_effects
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_state_ledger import StateLedger

        snapshot = fixture()
        # Keep the unrelated live descriptor genuinely owned. The comparison
        # isolates newly orphaned terminal descriptors, not pre-existing junk.
        snapshot["owned_stat_effects"]["99"] = {"uid": 99, "state_uid": 10}
        plan = self.plan(snapshot)
        self.assertEqual(plan.orphan_container_uids, {20, 30})
        self.assertTrue(plan.orphan_container_uids.isdisjoint(plan.effect_uids))

        def build():
            actors = {}
            for key, row in snapshot["actors"].items():
                ledger = StateLedger(int(key))
                ledger._entries = tuple(
                    SimpleNamespace(**entry) for entry in row["state_ledger"]["entries"]
                )
                actors[int(key)] = SimpleNamespace(state_ledger=ledger)
            maps = {
                name: {int(key): deepcopy(row) for key, row in snapshot[name].items()}
                for name in (
                    "native_retained_records",
                    "native_owned_state_containers",
                    "native_owned_group_effects",
                    "owned_stat_effects",
                    "native_owned_area_effects",
                    "native_owned_spatial_effects",
                    "state_wire_payloads",
                )
            }
            return SimpleNamespace(
                actors=actors,
                native_retained_order=list(snapshot["native_retained_order"]),
                **maps
            )

        candidate, baseline = build(), build()
        sweep_retired_effects(candidate, plan)
        for uid in plan.effect_uids:
            baseline.native_owned_group_effects.pop(uid)
        live = set(baseline.native_retained_records) - plan.effect_uids
        runtime = SimpleNamespace(fight=baseline, _live=lambda **kwargs: live)
        NativeRetainedRuntime.synchronize(runtime)
        self.assertEqual(
            candidate.native_owned_state_containers,
            baseline.native_owned_state_containers,
        )
        self.assertEqual(set(candidate.native_owned_state_containers), {10})
        self.assertEqual(
            candidate.native_retained_records, baseline.native_retained_records
        )
        self.assertEqual(candidate.state_wire_payloads, baseline.state_wire_payloads)
        self.assertEqual(
            [entry.uid for entry in candidate.actors[-100].state_ledger.entries], [20]
        )
        self.assertEqual(snapshot["native_state_source_provenance"], {"entries": {}})
        # A newly surviving child revokes the stale descriptor deletion plan,
        # before either the effect maps or the ledger can be changed.
        stale = build()
        stale.owned_stat_effects[100] = {"state_uid": 20}
        before = deepcopy(stale.native_owned_group_effects)
        with self.assertRaisesRegex(ValueError, "users changed"):
            sweep_retired_effects(stale, plan)
        self.assertEqual(stale.native_owned_group_effects, before)
        self.assertIn(20, stale.native_owned_state_containers)

    def test_timers_and_unknown_wire_fail_conservatively(self):
        snapshot = fixture()
        snapshot["actors"]["-100"]["state_ledger"]["entries"][0]["timer"] = {
            "actor_id": 1
        }
        self.assertEqual(self.plan(snapshot).effect_uids, {31})
        snapshot = fixture()
        snapshot["state_wire_payloads"]["20"] += scalar(99, 30).hex()
        self.assertFalse(self.plan(snapshot).effect_uids)
        self.assertTrue(self.plan(snapshot).opaque_sources)

    def test_global_false_state_criterion_survives_actual_storage_sweep(self):
        from types import SimpleNamespace
        from wakfu_server.combat_conditions import ConditionContext, evaluate_condition
        from wakfu_server.combat_range_conditions import (
            RangeFighter,
            range_count,
            registered_state_carriers,
        )
        from wakfu_server.combat_state_ledger import StateLedger, RunningState
        from wakfu_server.combat_retained_gc import sweep_retired_effects

        snapshot = fixture()
        actors = {}
        for key, row in snapshot["actors"].items():
            identity = int(key)
            ledger = StateLedger(identity)
            ledger._entries = tuple(
                RunningState(
                    uid=entry["uid"],
                    reference=3442,
                    level=1,
                    caster_id=entry["caster_id"],
                    target_id=identity,
                    duration=-1,
                    clock_actor="target",
                    tick_at_turn_end=False,
                    effect_ids=(),
                    realtime_duration=0,
                    retained=True,
                    timer=None,
                )
                for entry in row["state_ledger"]["entries"]
            )
            actors[identity] = SimpleNamespace(id=identity, state_ledger=ledger)
        maps = {
            name: {int(key): deepcopy(row) for key, row in snapshot[name].items()}
            for name in (
                "native_retained_records",
                "native_owned_state_containers",
                "native_owned_group_effects",
                "owned_stat_effects",
                "native_owned_area_effects",
                "native_owned_spatial_effects",
                "state_wire_payloads",
            )
        }
        fight = SimpleNamespace(
            actors=actors,
            native_retained_order=list(snapshot["native_retained_order"]),
            **maps
        )

        def registered(identity):
            return tuple(
                (-1, record["effect_class"], uid)
                for uid, record in fight.native_retained_records.items()
                if record["manager_id"] == identity
            )

        def query(maximum, alias, reference, level, in_play, caster):
            rows = tuple(
                RangeFighter(
                    (0, 0, 0),
                    0,
                    1,
                    actor.id == 1,
                    False,
                    False,
                    states=registered_state_carriers(
                        fight, actor, retained_reader=registered
                    ),
                )
                for actor in fight.actors.values()
            )
            return range_count(
                rows,
                relation="state",
                affiliation=1,
                center=(0, 0, 0),
                minimum=0,
                maximum=maximum,
                state_reference=reference,
                state_level=level,
                in_play=in_play,
            )

        context = ConditionContext({}, state_range_query=query)
        expression = 'GetStateCountInRange(5,"caster",3442,False)==3'
        self.assertTrue(evaluate_condition(expression, context))
        plan = self.plan(snapshot)
        self.assertTrue(plan.effect_uids)
        sweep_retired_effects(fight, plan)
        self.assertTrue(evaluate_condition(expression, context))
        self.assertTrue(
            evaluate_condition('GetStateCountInRange(5,"caster",3442,True)==1', context)
        )
        self.assertEqual(set(fight.native_retained_records), {10, 20, 30})

    def test_durable_history_does_not_become_execution_root(self):
        snapshot = fixture()
        snapshot["events"] = [{"actor_id": -100}]
        snapshot["native_artifact_activation_receipts"] = {
            "50": {"actor_id": -200, "uid": 30}
        }
        snapshot["native_spell_usage"] = {"-100": {"casts": {"20": 1}}}
        before = deepcopy(snapshot)
        self.assertEqual(self.plan(snapshot).effect_uids, {21, 22, 31})
        self.assertEqual(snapshot, before)


if __name__ == "__main__":
    unittest.main()
