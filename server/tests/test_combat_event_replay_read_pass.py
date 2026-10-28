"""Callback-free retained scans reuse views without hiding later mutations."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_combat_event_replay as replay_fixture
import test_combat_ordinary_events as ordinary_fixture
from wakfu_server import combat_event_replay as replay_module
from wakfu_server import combat_ordinary_events as ordinary_module
from wakfu_server import combat_ordinary_authority as authority_module
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    register_global_area,
)
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_trove_long_map import NativeTroveLongMap


class EventReplayReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        replay_fixture.NativeEventReplayTests.setUpClass()
        ordinary_fixture.OrdinaryHealingEventTests.setUpClass()

    def fixture(self):
        result = replay_fixture.NativeEventReplayTests()
        result.setUp()
        return result

    def test_empty_complete_scans_share_once_only_inside_one_global_phase(self):
        f = self.fixture()
        empty = replace(f.source(), channel=31)
        with patch.object(f.retention, "view", wraps=f.retention.view) as view:
            with f.replay.read_pass():
                for identity in (7, -7, 7, -7, 7, -7):
                    self.assertEqual(
                        f.replay(
                            replace(empty, manager_actor_id=identity),
                            authority=f.authority,
                        ),
                        (),
                    )
            self.assertEqual(view.call_count, 1)
            f.replay(empty, authority=f.authority)
            self.assertEqual(view.call_count, 2)
        self.assertIsNone(f.replay._read_pass)
        case = ordinary_fixture.OrdinaryHealingEventTests()
        case.setUp()
        case.adapter.actor_authority.characters[7].update(
            map_id=527, instance_id=0, account_id=3, selected_character_id=7
        )
        case.adapter.actor_authority.monsters[-7].update(map_id=527, instance_id=0)
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        initialize_global_pv_collections(case.fight, tuple(case.fight.actors))
        with patch.object(
            case.f.retention, "view", wraps=case.f.retention.view
        ) as view:
            self.assertEqual(
                case.events.phase(case.effect, case.inv, uid=800, value=1, channel=3),
                ((), (), (), ()),
            )
            # Two independent local deliveries plus one complete global scan.
            self.assertEqual(view.call_count, 3)
        self.assertIsNone(case.events.replay._read_pass)

    def test_late_real_registration_denied_callback_and_removal_invalidate_first(self):
        for mode in ("registration", "denied", "removal"):
            with self.subTest(mode=mode):
                f = self.fixture()
                source = replace(f.source(), channel=31)
                definition = f.retention.metadata["effects"]["308265"]
                definition["event_global_subscription"] = True
                row = f.fight.native_owned_group_effects[900]
                row["native_subscription_masks"] = [None] * 7
                row["native_subscription_masks"][3 if mode != "removal" else 2] = list(
                    source.event_ids
                )
                callbacks = []

                def activation(invocation, **kwargs):
                    self.assertIsNone(f.replay._read_pass["view"])
                    callbacks.append(invocation.target_id)
                    if invocation.target_id == 7:
                        # Register a real retained group through its normal
                        # dispatcher while the preceding manager reacts.
                        f.dispatcher.execute(
                            EffectInvocation(308265, 1, -7, -7, (1, 0, 0))
                        )
                        added = max(f.fight.native_owned_group_effects)
                        f.fight.native_owned_group_effects[added][
                            "native_subscription_masks"
                        ] = [None] * 7
                        f.fight.native_owned_group_effects[added][
                            "native_subscription_masks"
                        ][3] = list(source.event_ids)
                    return False

                if mode == "registration":
                    f.dispatcher.execute_activation = activation
                if mode == "denied":
                    original = f.authority

                    def denied(*args):
                        self.assertIsNone(f.replay._read_pass["view"])
                        callbacks.append("denied")
                        return False

                    f.authority = replay_module.NativeCloneAuthority(
                        denied, original.condition_context
                    )
                with patch.object(f.retention, "view", wraps=f.retention.view) as view:
                    with f.replay.read_pass():
                        f.replay(
                            replace(source, manager_actor_id=-7), authority=f.authority
                        )
                        self.assertEqual(view.call_count, 1)
                        current = replace(
                            source, channel=41 if mode == "removal" else 31
                        )
                        f.replay(current, authority=f.authority)
                        self.assertIsNone(f.replay._read_pass["view"])
                        built = view.call_count
                        f.replay(
                            replace(source, manager_actor_id=-7), authority=f.authority
                        )
                        self.assertEqual(view.call_count, built + 1)
                if mode == "registration":
                    self.assertEqual(callbacks, [7, -7])
                elif mode == "denied":
                    self.assertEqual(callbacks, ["denied"])
                    self.assertIn(900, f.fight.native_owned_group_effects)
                    self.assertEqual(
                        f.fight.native_owned_group_effects[900]["execution_count"], 1
                    )
                else:
                    self.assertNotIn(900, f.fight.native_owned_group_effects)

    def test_nested_exceptions_preview_service_changes_and_fresh_graph_errors(self):
        f = self.fixture()
        source = replace(f.source(), channel=31)
        with patch.object(f.retention, "view", wraps=f.retention.view) as view:
            with f.replay.read_pass():
                f.replay(source, authority=f.authority)
                with self.assertRaisesRegex(RuntimeError, "nested failure"):
                    with f.replay.read_pass():
                        f.replay(source, authority=f.authority)
                        raise RuntimeError("nested failure")
                self.assertIsNone(f.replay._read_pass["view"])
                f.replay(source, authority=f.authority)
                self.assertEqual(view.call_count, 3)
                original = f.retention.fight
                f.retention.fight = deepcopy(original)
                f.replay(source, authority=f.authority)
                self.assertEqual(view.call_count, 4)
                f.retention.fight = original
                f.replay(source, authority=f.authority)
                self.assertEqual(view.call_count, 5)
                old = f.replay.retention
                proxy = SimpleNamespace(
                    fight=original, metadata=f.retention.metadata, view=f.retention.view
                )
                f.replay.retention = proxy
                f.replay(source, authority=f.authority)
                self.assertEqual(view.call_count, 6)
                f.replay.retention = old
        self.assertIsNone(f.replay._read_pass)
        # A new query must fail closed on an incomplete central population.
        del f.fight.native_retained_records[900]
        with f.replay.read_pass(), self.assertRaisesRegex(
            ValueError, "Unregistered native retained"
        ):
            f.replay(source, authority=f.authority)

    def test_area_and_unknown_authority_or_retention_never_carry_a_view(self):
        for mode in (
            "area",
            "registered",
            "custom-replay",
            "custom-authority",
            "custom-catalog",
            "custom-spellbook",
            "custom-retention",
        ):
            with self.subTest(mode=mode):
                f = self.fixture()
                f.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
                    None
                ] * 7
                initialize_global_pv_collections(f.fight, tuple(f.fight.actors))
                if mode == "area":
                    f.fight.native_effect_areas = {99: dict(uid=99)}
                    register_global_area(f.fight, 99)
                # Duplicate PVs in the real native extra segment remain valid
                # deliveries and must not be deduplicated by the optimization.
                extras = NativeTroveLongMap(
                    f.fight.native_global_pv_collections["extras"]
                )
                extras.put(7)
                extras.put(-7)
                authority = object.__new__(OrdinaryActorAuthority)
                authority.npc_spellbook = None
                property_catalog = {"player": {}, "npc": {}}
                authority.catalog = property_catalog
                if mode == "registered":
                    authority = RegisteredSummonAuthority(authority)
                elif mode == "custom-authority":
                    authority = SimpleNamespace(npc_spellbook=None)
                elif mode == "custom-spellbook":
                    authority.npc_spellbook = lambda *args: None
                elif mode == "custom-catalog":
                    authority.catalog = {"player": {}, "npc": {}}
                replay = f.replay
                if mode == "custom-replay":

                    class CustomReplay(replay_module.NativeEventReplay):
                        pass

                    replay = CustomReplay(f.dispatcher, f.retention)
                elif mode == "custom-retention":
                    replay.retention = SimpleNamespace(
                        fight=f.fight,
                        metadata=f.retention.metadata,
                        view=f.retention.view,
                    )
                instance = SimpleNamespace(
                    preview=f.fight,
                    adapter=SimpleNamespace(actor_authority=authority),
                    replay=replay,
                    authority=f.authority,
                )
                # Execute the production global iterator branch. Recipient
                # construction is a declared boundary here; the preceding
                # test executes the full real ordinary phase separately.
                module = ordinary_module
                path = Path(module.__file__)
                tree = ast.parse(path.read_text())
                branch = next(
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.If)
                    and ast.unparse(node.test)
                    == "hasattr(self.preview, 'native_global_pv_collections')"
                )
                returned = []

                def verify(identity):
                    returned.append(identity)
                    if identity == 99:
                        self.assertIsNone(replay._read_pass["view"])
                        return SimpleNamespace(
                            native_is_area=True, native_running_effect_manager=False
                        )
                    if mode not in ("area", "registered"):
                        self.assertIsNone(replay._read_pass)
                    return f.fight.actors[identity]

                namespace = dict(
                    vars(module),
                    self=instance,
                    global_channel=31,
                    invocation=EffectInvocation(308265, 1, 7, 7, (0, 0, 0)),
                    base=replace(f.source(), channel=3),
                    outcomes=[],
                    channel=1,
                    verify_recipient=verify,
                )
                function = ast.FunctionDef(
                    name="run_global",
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[],
                        kwonlyargs=[],
                        kw_defaults=[],
                        defaults=[],
                    ),
                    body=[branch],
                    decorator_list=[],
                )
                code = ast.fix_missing_locations(
                    ast.Module(body=[function], type_ignores=[])
                )
                exec(compile(code, str(path), "exec"), namespace)
                with patch.object(
                    f.retention, "view", wraps=f.retention.view
                ) as view, patch.object(
                    authority_module,
                    "_immutable_property_catalog",
                    return_value=property_catalog,
                ):
                    if mode == "custom-retention":
                        replay.retention.view = f.retention.view
                    result = namespace["run_global"]()
                    self.assertEqual(result, ((), (), (), ()))
                    expected = 1 if mode == "registered" else 2 if mode == "area" else 4
                    self.assertEqual(view.call_count, expected)
                self.assertEqual(returned.count(7), 2)
                self.assertEqual(returned.count(-7), 2)
                self.assertIsNone(replay._read_pass)

        # A supported custom catalog can execute its own reads. If that code
        # changes ownership between global recipients, the next complete view
        # must still reject the resulting incomplete graph.
        case = ordinary_fixture.OrdinaryHealingEventTests()
        case.setUp()
        ordinary = case.adapter.actor_authority
        ordinary.characters[7].update(
            map_id=527, instance_id=0, account_id=3, selected_character_id=7
        )
        ordinary.monsters[-7].update(map_id=527, instance_id=0)
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        initialize_global_pv_collections(case.fight, tuple(case.fight.actors))
        original_catalog = ordinary.catalog
        mutated = []

        class MutatingCatalog:
            def __getitem__(self, key):
                if view.call_count >= 3 and not mutated:
                    case.fight.native_retained_records.pop(900)
                    mutated.append(True)
                return original_catalog[key]

        ordinary.catalog = MutatingCatalog()
        with patch.object(
            case.f.retention, "view", wraps=case.f.retention.view
        ) as view:
            with self.assertRaisesRegex(ValueError, "Unregistered native retained"):
                case.events.phase(case.effect, case.inv, uid=800, value=1, channel=3)
        self.assertEqual(mutated, [True])
        self.assertIsNone(case.events.replay._read_pass)


if __name__ == "__main__":
    unittest.main()
