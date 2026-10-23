"""DB-frozen external owned NPC START reconstruction; no full-fight victory claim."""
from copy import deepcopy
from dataclasses import replace
import json
import psycopg
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from pathlib import Path

_NATIVE = sorted(
    json.loads(
        (
            Path(__file__).with_name("fixtures") / "rushu_npc_start_binding_native.json"
        ).read_text()
    )["descriptors"],
    key=lambda row: row["listener_reference"],
)


class RushuNpcStartBindingTests(PostgresCase):
    def fixture(self, descriptor_index=0):
        from wakfu_server import combat_encounter_npc_start_binding as binding
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_turn_events import TURN_BOUNDARY_POLICY as POLICY

        for module in (binding, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        native = _NATIVE[descriptor_index]
        reference, carrier, parent = (
            native[key]
            for key in ("listener_reference", "carrier_state", "parent_reference")
        )
        assignment = roles.role_assignment(1332, [5306])
        player = SimpleNamespace(
            id=3, owner_id=42, controlled=True, hp=100, team=assignment.player_team
        )
        boss = SimpleNamespace(
            id=-200,
            controlled=False,
            hp=100,
            team=assignment.npc_team,
            position=(0, 0, 0),
            state_ledger=SimpleNamespace(
                entries=(
                    SimpleNamespace(
                        uid=55,
                        reference=carrier,
                        caster_id=3,
                        target_id=-200,
                        effect_ids=(parent,),
                    ),
                )
            ),
        )
        invocation = EffectInvocation(reference, 1, 3, -200, (0, 0, 0), state_uid=55)
        fight = SimpleNamespace(
            phase="placement",
            current=boss,
            actors={3: player, -200: boss},
            turn_id=37,
            walkable={(0, 0, 0), (1, 0, 0)},
            edges=None,
            native_encounter_roles=assignment.record(),
            native_owned_group_effects={
                71: dict(
                    invocation=dict(
                        reference=reference, caster_id=3, target_id=-200, state_uid=55
                    )
                )
            },
            native_npc_initialization_receipts={
                -200: dict(
                    ref=5306, initialized=True, resolved_states=[dict(state_id=7000)]
                )
            },
        )
        binding.freeze_npc_start_binding(fight, roles=assignment)
        fight.phase = "active"
        context = dict(
            policy=POLICY, actor_id=-200, turn_id=37, phase="start", event_id=1001
        )
        source = NativeExternalEvent(-200, (1001,), 60, turn_boundary_context=context)
        entry = SimpleNamespace(uid=71, manager_id=-200, generic_effect=reference)
        args = dict(
            entry=entry,
            original=invocation,
            definition=native["native_metadata"],
            effect=native["native_effect"],
        )
        return binding, assignment, fight, source, args

    def test_four_descriptors_owned_uid_immutable_inventory_and_checkpoint(self):
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        binding, assignment, fight, source, args = self.fixture()
        self.assertIsNone(source.uid)
        self.assertEqual(len(fight.native_encounter_npc_start_binding["effects"]), 4)
        for index, native in enumerate(_NATIVE):
            with self.subTest(
                carrier=native["carrier_state"], listener=native["listener_reference"]
            ):
                _, _, current, event, actual = self.fixture(index)
                from wakfu_server.combat_static_catalogs import ImmutableCatalog

                with owned_turn_recipient_scope(current, event.turn_boundary_context):
                    self.assertEqual(
                        binding.npc_start_caster(
                            current,
                            event,
                            **dict(actual, effect=ImmutableCatalog(actual["effect"]))
                        ),
                        -200,
                    )
                self.assertEqual(
                    current.actors[-200].state_ledger.entries[0].caster_id, 3
                )
                self.assertEqual(
                    current.native_owned_group_effects[71]["invocation"]["caster_id"], 3
                )
                self.assertEqual(actual["original"].caster_id, 3)
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        # Exercise exactly the production lazy tuple projection, not a hand-
        # normalized fixture. Each preview is private and may be discarded.
        for effect in (args["effect"], ImmutableCatalog(args["effect"])):
            preview = deepcopy(fight)
            with owned_turn_recipient_scope(preview, source.turn_boundary_context):
                self.assertEqual(
                    binding.npc_start_caster(
                        preview, source, **dict(args, effect=effect)
                    ),
                    -200,
                )
            self.assertFalse(hasattr(fight, "native_npc_start_caster_deliveries"))
        with self.assertRaises(psycopg.Error):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE encounter_npc_start_binding_versions SET authority='tampered'"
                )
        with owned_turn_recipient_scope(fight, source.turn_boundary_context):
            self.assertEqual(binding.npc_start_caster(fight, source, **args), -200)
            with self.assertRaisesRegex(ValueError, "already consumed"):
                binding.npc_start_caster(fight, source, **args)
        self.assertEqual(
            (args["original"].caster_id, args["original"].target_id), (3, -200)
        )
        restored = json.loads(json.dumps(fight.native_npc_start_caster_deliveries))
        fight.native_npc_start_caster_deliveries = restored
        with owned_turn_recipient_scope(fight, source.turn_boundary_context):
            with self.assertRaisesRegex(ValueError, "already consumed"):
                binding.npc_start_caster(fight, source, **args)
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_npc_start_binding_active")
        fight.phase = "placement"
        pinned = deepcopy(fight.native_encounter_npc_start_binding)
        self.assertEqual(
            binding.freeze_npc_start_binding(fight, roles=assignment), pinned
        )
        del fight.native_encounter_npc_start_binding
        self.assertIsNone(binding.freeze_npc_start_binding(fight, roles=assignment))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_npc_start_binding_active VALUES "
                "(1332,ARRAY[5306],%s)",
                (pinned["policy"],),
            )
        self.assertIsNone(binding.freeze_npc_start_binding(fight, roles=assignment))

    def test_foreign_boundary_descriptor_carrier_and_tamper_fail_before_publication(
        self,
    ):
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        binding, assignment, fight, source, args = self.fixture()
        with self.assertRaisesRegex(ValueError, "Unattested"):
            binding.npc_start_caster(fight, source, **args)
        for changed in (replace(source, channel=6), replace(source, event_ids=(1002,))):
            self.assertIsNone(binding.npc_start_caster(fight, changed, **args))
        with owned_turn_recipient_scope(fight, source.turn_boundary_context):
            self.assertFalse(binding._same_sequence((True,), (1,)))
            self.assertFalse(binding._same_sequence((1,), (1.0,)))
            wrong = dict(args, effect=dict(args["effect"], criteria="tampered"))
            with self.assertRaisesRegex(ValueError, "descriptor changed"):
                binding.npc_start_caster(fight, source, **wrong)
            with self.assertRaisesRegex(ValueError, "actual native boss"):
                binding.npc_start_caster(
                    fight, replace(source, manager_actor_id=3), **args
                )
            original = args["original"]
            with self.assertRaisesRegex(ValueError, "carrier state UID"):
                binding.npc_start_caster(
                    fight,
                    source,
                    **dict(args, original=replace(original, state_uid=999))
                )
            carrier = fight.actors[-200].state_ledger.entries[0]
            parent = carrier.effect_ids
            carrier.effect_ids = (args["original"].reference,)
            with self.assertRaisesRegex(ValueError, "carrier state UID"):
                binding.npc_start_caster(fight, source, **args)
            carrier.effect_ids = parent
            fight.native_owned_group_effects[71]["invocation"]["caster_id"] = 999
            with self.assertRaisesRegex(ValueError, "retained listener UID"):
                binding.npc_start_caster(fight, source, **args)
            fight.native_owned_group_effects[71]["invocation"]["caster_id"] = 3
            fight.native_encounter_npc_start_binding["effects"][0][
                "selector_mask"
            ] = True
            with self.assertRaisesRegex(
                ValueError, "Frozen owned NPC START binding changed"
            ):
                binding.npc_start_caster(fight, source, **args)
            fight.native_encounter_npc_start_binding["effects"][0]["selector_mask"] = 1
            fight.native_encounter_npc_start_binding["effects"][0][
                "listener_reference"
            ] = 123
            with self.assertRaisesRegex(
                ValueError, "Frozen owned NPC START binding changed"
            ):
                binding.npc_start_caster(fight, source, **args)
        self.assertFalse(hasattr(fight, "native_npc_start_caster_deliveries"))


class RushuNpcStartReplayHookTests(unittest.TestCase):
    def test_four_original_subscriptions_replay_as_manager_without_rewriting_source(
        self,
    ):
        from test_combat_event_replay import NativeEventReplayTests
        from wakfu_server import combat_encounter_npc_start_binding as binding
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_turn_events import TURN_BOUNDARY_POLICY
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        for native in _NATIVE:
            with self.subTest(
                carrier=native["carrier_state"], listener=native["listener_reference"]
            ):
                case = NativeEventReplayTests()
                case.setUpClass()
                case.setUp()
                reference = native["listener_reference"]
                case.effects[str(reference)] = deepcopy(native["native_effect"])
                case.retention.metadata["effects"][str(reference)] = deepcopy(
                    native["native_metadata"]
                )
                case.dispatcher.execute(
                    EffectInvocation(reference, 1, -7, 7, (0, 0, 0))
                )
                retained = next(
                    row
                    for row in case.fight.native_owned_group_effects.values()
                    if row["invocation"]["reference"] == reference
                )
                before = deepcopy(retained["invocation"])
                children = []
                execute = case.dispatcher._execute

                def observe(invocation, **kwargs):
                    if invocation.reference in native["native_effect"]["children"]:
                        children.append(invocation)
                        return True  # Stop at the real child invocation boundary, not a fight claim.
                    return execute(invocation, **kwargs)

                def bridge(fight, source, **kwargs):
                    self.assertIsNone(source.uid)
                    self.assertEqual(
                        (kwargs["original"].caster_id, kwargs["original"].target_id),
                        (-7, 7),
                    )
                    self.assertEqual(kwargs["original"].reference, reference)
                    return 7  # The two PG methods qualify the actual scoped guard.

                context = dict(
                    policy=TURN_BOUNDARY_POLICY,
                    actor_id=7,
                    turn_id=case.fight.turn_id,
                    phase="start",
                    event_id=1001,
                )
                event = NativeExternalEvent(
                    7, (1001,), 60, turn_boundary_context=context
                )
                with owned_turn_recipient_scope(case.fight, context), patch.object(
                    binding, "npc_start_caster", side_effect=bridge
                ), patch.object(case.dispatcher, "_execute", side_effect=observe):
                    case.replay(event, authority=case.authority)
                self.assertEqual(
                    {child.reference for child in children},
                    set(native["native_effect"]["children"]),
                )
                self.assertTrue(
                    all(
                        (child.caster_id, child.target_id) == (7, 7)
                        and child.native_trigger_context is None
                        for child in children
                    )
                )
                self.assertEqual(retained["invocation"], before)
