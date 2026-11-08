"""Producer and direct shared consumers; no full-action performance claim."""
from copy import deepcopy
import unittest

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_runtime import _retained_definition_sequence
from wakfu_server.combat_native_events import subscription_selection
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_retained_gc import plan_retired_effects
import test_combat_retained_groups as native_fixture


class GroupDefinitionTupleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixture.NativeRetainedGroupTests.setUpClass()

    def test_native_producer_snapshot_removal_and_custom_sequence_contract(self):
        fixture = native_fixture.NativeRetainedGroupTests()
        fixture.setUp()
        # Match the explicit synthetic QI/Vy arena used by this native fixture.
        # Ordinary authority requires a real positive-map source for every PC/NPC.
        for source in (
            *fixture.authority.characters.values(),
            *fixture.authority.monsters.values(),
        ):
            source["map_id"] = 999999
            source["instance_id"] = 0
        dispatcher, packets = fixture.factory()
        self.assertTrue(
            dispatcher.execute(EffectInvocation(308265, 1, 7, 7, (0, 0, 0)))
        )
        uid = next(iter(fixture.preview.native_owned_group_effects))
        row = fixture.preview.native_owned_group_effects[uid]
        for field in ("native_effect_flags", "children"):
            self.assertIs(type(row[field]), tuple)
            self.assertIs(deepcopy(row[field]), row[field])
            self.assertEqual(row[field], tuple(fixture.effects["308265"][field]))
        control = deepcopy(fixture.preview)
        for field in ("native_effect_flags", "children"):
            control.native_owned_group_effects[uid][field] = list(row[field])
        # Real checkpoint serialization preserves the historical wire shape.
        self.assertEqual(snapshot(control), snapshot(fixture.preview))
        self.assertEqual(
            plan_retired_effects(snapshot(control), set(), pending_roots=()),
            plan_retired_effects(snapshot(fixture.preview), set(), pending_roots=()),
        )
        for channel in (4, 40, 41):
            kwargs = dict(
                masks=[(), (), (1001,), (), (), (), ()],
                event_ids=(1001,),
                channel=channel,
                global_subscription=channel == 41,
                reversed_subscription=channel == 40,
                source_present=False,
            )
            self.assertEqual(
                subscription_selection(flags=row["native_effect_flags"], **kwargs),
                subscription_selection(
                    flags=list(row["native_effect_flags"]), **kwargs
                ),
            )
        # Native family421 consumes and removes the actual newly stored listener.
        self.assertTrue(
            dispatcher.execute(EffectInvocation(308271, 1, 7, 7, (0, 0, 0)))
        )
        self.assertEqual(fixture.preview.native_owned_group_effects, {})
        self.assertEqual(fixture.preview.native_retained_records, {})
        self.assertEqual([op for op, _ in packets], [13497, 13560])
        from test_group_trigger_history import listener_fixture

        gc_control = listener_fixture()
        gc_candidate = deepcopy(gc_control)
        gc_control["native_owned_group_effects"]["11"]["native_effect_flags"] = [1, 5]
        gc_candidate["native_owned_group_effects"]["11"]["native_effect_flags"] = (1, 5)
        gc_candidate["native_owned_group_effects"]["11"]["children"] = ()
        self.assertEqual(
            plan_retired_effects(gc_control, {-100, -200}, pending_roots=()),
            plan_retired_effects(gc_candidate, {-100, -200}, pending_roots=()),
        )
        trace = []

        class Custom(list):
            def __iter__(self):
                trace.append("iter")
                return super().__iter__()

            def __len__(self):
                trace.append("len")
                return super().__len__()

        value = Custom([1, 2])
        expected = list(value)
        expected_trace = list(trace)
        trace.clear()
        actual = _retained_definition_sequence(value)
        self.assertIs(type(actual), list)
        self.assertEqual(actual, expected)
        self.assertEqual(trace, expected_trace)
        mutable = {}
        for values in ([True], [mutable], [1, None]):
            actual = _retained_definition_sequence(values)
            self.assertIs(type(actual), list)
            self.assertEqual(actual, values)
            self.assertIs(actual[0], values[0])
        self.assertEqual(_retained_definition_sequence([1, 2]), (1, 2))
