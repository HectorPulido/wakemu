"""Pure reachability/sweep proof; no gameplay or catalog construction."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server import combat_retained_source_provenance as provenance_module
import unittest

from wakfu_server.combat_retained_gc import plan_retired_effects, sweep_retired_effects
from wakfu_server.combat_retained_source_provenance import (
    POLICY,
    state_source_provenance,
)
from test_retained_gc_graph import wire


def row(uid, parent=None, target=-100):
    return dict(
        uid=uid,
        parent_state_uid=parent,
        parent_known=True,
        container_known=True,
        state_reference=1,
        state_level=1,
        caster_id=-100,
        target_id=target,
        retained=True,
        source="captured_application",
        container_present=parent is not None,
        container_type=1 if parent is not None else None,
        container_id=65537 if parent is not None else None,
        container_kind="state" if parent is not None else None,
        container_is_spell=False if parent is not None else None,
        spell_protected=False if parent is not None else None,
    )


def fixture():
    entries = {
        str(uid): row(uid) for uid in (500, 502, 510, 520, 530, 540, 550, 560, 580)
    }
    entries["501"] = row(501, 502)
    entries["503"] = row(503, 502)
    entries["10"] = row(10, 510, target=1)
    entries["580"] = row(580, target=1)
    snap = dict(
        actors={
            "1": dict(
                id=1,
                state_ledger={
                    "entries": [dict(uid=10, target_id=1, caster_id=1, timer=None)]
                },
            ),
            "-100": dict(
                id=-100,
                state_ledger={
                    "entries": [
                        dict(uid=550, target_id=-100, caster_id=-100, timer=None)
                    ]
                },
            ),
        },
        native_retained_records={
            "10": dict(
                uid=10, manager_id=1, target_id=1, effect_class=310, owner_uid=None
            )
        },
        state_wire_payloads={
            "10": wire(10, 1, 1, related=520),
            "560": wire(560, -100, -100),
        },
        native_owned_state_containers={},
        native_owned_group_effects={},
        owned_stat_effects={},
        native_owned_area_effects={},
        native_owned_spatial_effects={},
        native_state_source_provenance={"policy": POLICY, "entries": entries},
        native_retained_order=[10],
        native_effect_areas={"900": dict(uid=900, effect_uid=540)},
        events=[{"accounting": "unchanged"}],
    )
    snap["actors"]["-200"] = dict(id=-200, state_ledger=None)
    return snap


def materialize(snapshot):
    fields = deepcopy(snapshot)
    fields["actors"] = {
        int(key): SimpleNamespace(
            **{
                **actor,
                "state_ledger": (
                    None
                    if actor["state_ledger"] is None
                    else SimpleNamespace(
                        entries=tuple(
                            SimpleNamespace(**r)
                            for r in actor["state_ledger"]["entries"]
                        )
                    )
                ),
            }
        )
        for key, actor in fields["actors"].items()
    }
    for name in (
        "native_retained_records",
        "state_wire_payloads",
        "native_owned_state_containers",
        "native_owned_group_effects",
        "owned_stat_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
        "native_effect_areas",
    ):
        fields[name] = {int(key): value for key, value in fields[name].items()}
    return SimpleNamespace(**fields)


def snapshot_fixture(value):
    if type(value) is SimpleNamespace:
        return snapshot_fixture(vars(value))
    if type(value) is dict:
        return {str(key): snapshot_fixture(item) for key, item in value.items()}
    if type(value) in (tuple, list):
        return [snapshot_fixture(item) for item in value]
    return value


class ProvenanceLeafTests(unittest.TestCase):
    def test_only_unreachable_leaves_sweep_and_chain_retries_preserve_all_other_state(
        self,
    ):
        source = fixture()
        before = deepcopy(source)
        pending = {"source_parent_uid": 530}
        validated = []
        original_validator = provenance_module._validate_record

        def counted(row):
            validated.append(row["uid"])
            return original_validator(row)

        with patch.object(provenance_module, "_validate_record", new=counted):
            plan = plan_retired_effects(source, {-100}, pending_roots=pending)
        self.assertEqual(sorted(validated), [500, 501, 502, 503])
        self.assertFalse(plan.opaque_sources)
        self.assertEqual(plan.effect_uids, set())
        self.assertEqual(plan.orphan_provenance_uids, {500, 501, 503})
        self.assertEqual(source, before)
        fight = materialize(source)
        # No gameplay classes are fabricated; this is the same pure sweep API
        # supplied a typed-free container fixture, not a native boundary proof.
        validated.clear()
        with patch.object(provenance_module, "_validate_record", new=counted):
            sweep_retired_effects(fight, plan)
        self.assertEqual(sorted(validated), [500, 501, 502, 503])
        expected = deepcopy(before)
        for uid in (500, 501, 503):
            del expected["native_state_source_provenance"]["entries"][str(uid)]
        actual = snapshot_fixture(fight)
        self.assertEqual(actual, expected)
        self.assertEqual(fight.native_retained_order, before["native_retained_order"])
        self.assertEqual(fight.events, before["events"])
        self.assertEqual(fight.actors[-100].state_ledger.entries[0].uid, 550)
        # Keep the parent until its final historical child disappears. It can
        # become a leaf only in the following existing GC planning pass.
        second = plan_retired_effects(expected, {-100}, pending_roots=pending)
        self.assertEqual(second.orphan_provenance_uids, {502})
        sweep_retired_effects(fight, second)
        self.assertNotIn("502", fight.native_state_source_provenance["entries"])
        self.assertEqual(
            set(fight.native_state_source_provenance["entries"]),
            {"10", "510", "520", "530", "540", "550", "560", "580"},
        )
        # Authority still follows the real live carrier's retired ancestor.
        # This fixture's wire identity is a minimal graph wire, so validate the
        # provenance mapping without presenting it as a full state carrier.
        provenance_fight = SimpleNamespace(
            native_state_source_provenance=fight.native_state_source_provenance,
            state_wire_payloads={},
        )
        self.assertEqual(
            state_source_provenance(provenance_fight)[10]["parent_state_uid"], 510
        )
        opaque = deepcopy(before)
        opaque["unknown_callback"] = object()
        self.assertFalse(
            plan_retired_effects(
                opaque, {-100}, pending_roots=pending
            ).orphan_provenance_uids
        )
        malformed = deepcopy(before)
        malformed["native_state_source_provenance"]["entries"]["500"][
            "state_level"
        ] = "invalid"
        self.assertNotIn(
            500,
            plan_retired_effects(
                malformed, {-100}, pending_roots=pending
            ).orphan_provenance_uids,
        )
        # Adding a new child after planning must reject before any deletion.
        stale = materialize(before)
        stale.native_state_source_provenance["entries"]["599"] = row(599, 500)
        untouched = deepcopy(stale.native_state_source_provenance)
        with self.assertRaisesRegex(ValueError, "changed after GC planning"):
            sweep_retired_effects(stale, plan)
        self.assertEqual(stale.native_state_source_provenance, untouched)
