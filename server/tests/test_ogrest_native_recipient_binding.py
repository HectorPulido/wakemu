"""Scoped original Ivory chosen-PV contract; no earned phase/paid-fight claim."""
from copy import deepcopy
from dataclasses import replace
from itertools import count
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase
import test_combat_effect_resolver as resolver_fixture


class OgrestNativeRecipientBindingTests(PostgresCase):
    def scene(self):
        from wakfu_server import combat_encounter_recipient_binding as policy
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_state_ledger import RunningState

        for module in (policy, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        f = resolver_fixture.NativeResolverTests()
        f.setUp()
        pc = Actor(1, 1, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        boss = Actor(-200, 0, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            77,
            [pc, boss],
            {pc.position, boss.position},
            {1: {pc.position}, 0: {boss.position}},
        )
        # This is a source-binding unit premise, not an earned Ivory witness.
        boss.state_ledger._entries = (
            RunningState(
                687,
                4984,
                1,
                boss.id,
                boss.id,
                -1,
                "target",
                False,
                (237875, 237996, 237999, 238002),
                -1,
                True,
                None,
            ),
        )
        fight.native_npc_initialization_receipts = {
            -200: {"ref": 4378, "initialized": True}
        }
        assigned = roles.role_assignment(1156, [4378])
        roles.bind_roles(fight, assigned, player_ids=[1], npc_ids=[-200])
        fight.ready(3)
        f.actors = [pc, boss]
        f.native = {
            actor.id: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for actor in f.actors
        }
        f.resolver.preserve_explicit_recipient = (
            lambda effect, invocation: policy.permits_native_recipient_binding(
                fight, effect, invocation
            )
        )
        native = json.loads(
            (
                Path(__file__).parent
                / "fixtures/ogrest_ivory_recipient_binding_native.json"
            ).read_text()
        )
        f.resolver.direct_target_policies = {
            ref: [row["effect_class"], False, False]
            for ref, row in native["effects"].items()
        }
        source = dict(
            uid=301,
            generic_effect=151640,
            caster_id=pc.id,
            target_id=boss.id,
            manager_actor_id=boss.id,
            channel=2,
            event_ids=(8,),
            native_events_verified=True,
        )
        invocation = replace(
            f.invocation,
            reference=240713,
            level=2,
            caster_id=pc.id,
            target_id=boss.id,
            cell=boss.position,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
            native_trigger_context=source,
            state_uid=687,
        )
        return policy, roles, f, fight, pc, boss, native, invocation

    def test_four_native_elements_keep_boss_marker_and_actual_resistance(self):
        from wakfu_server.combat_state_handler import (
            NativeStateHandler,
            StateCarrierContext,
        )
        from wakfu_server.combat_stat_handler import (
            NativeStatHandler,
            StatExecutionContext,
        )
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        for marker, gain, event in (
            (238154, 238155, 5),
            (240706, 240707, 6),
            (240709, 240710, 7),
            (240712, 240713, 8),
        ):
            with self.subTest(gain=gain):
                policy, roles, f, fight, pc, boss, native, invocation = self.scene()
                self.assertEqual(
                    len(fight.native_encounter_recipient_binding["effects"]), 8
                )
                for actor, initial in ((pc, 100), (boss, 400)):
                    actor.effect_stats = {key: initial for key in (28, 29, 30, 31)}
                    actor.effect_maxima = {
                        key: 2147483647 for key in actor.effect_stats
                    }
                    actor.effect_minima = {
                        key: -2147483648 for key in actor.effect_stats
                    }
                    actor.effect_frozen = frozenset()
                packets, children = [], []
                uids = count(1000)
                state_handler = NativeStateHandler(
                    fight,
                    packets,
                    native,
                    action_id=1,
                    allocate_uid=lambda: next(uids),
                    execute_child=lambda inv: children.append(inv),
                    context=lambda *args: StateCarrierContext(
                        -1, 0, False, None, 100, False, False, False, 0, None
                    ),
                )
                stat_handler = NativeStatHandler(
                    fight,
                    packets,
                    native["registry"],
                    action_id=1,
                    allocate_uid=lambda: next(uids),
                    context=lambda *args: StatExecutionContext(
                        True, True, None, True, None
                    ),
                )
                source = dict(invocation.native_trigger_context, event_ids=(event,))
                current = replace(invocation, native_trigger_context=source)
                effect = ImmutableCatalog(native["effects"][str(marker)])
                self.assertIsInstance(effect["parameters"], tuple)
                selected = f.resolver(effect, replace(current, reference=marker))
                self.assertEqual([row.target_id for row in selected], [boss.id])
                self.assertTrue(
                    state_handler(effect, {"parameters": [5072, 1, -1]}, selected[0])
                )
                self.assertTrue(
                    any(row.reference == 5072 for row in boss.state_ledger.entries)
                )
                self.assertFalse(
                    any(row.reference == 5072 for row in pc.state_ledger.entries)
                )
                effect = ImmutableCatalog(native["effects"][str(gain)])
                selected = f.resolver(effect, replace(current, reference=gain))
                self.assertEqual([row.target_id for row in selected], [boss.id])
                self.assertTrue(stat_handler(effect, {}, selected[0]))
                stat = native["registry"]["effects"][str(effect["effect_class"])][
                    "fixed_stat_id"
                ]
                self.assertEqual(
                    (boss.effect_stats[stat], pc.effect_stats[stat]), (410, 100)
                )
                owned = list(fight.owned_stat_effects.values())[-1]
                self.assertEqual(
                    (owned["target_id"], owned["caster_id"], owned["actual"]),
                    (-200, 1, 10),
                )

    def test_scope_source_descriptor_and_immutable_admission_boundaries(self):
        policy, roles, f, fight, pc, boss, native, invocation = self.scene()
        effect = native["effects"]["240713"]
        self.assertTrue(
            policy.permits_native_recipient_binding(fight, effect, invocation)
        )
        for changes in (
            dict(wakemu_fresh_child_selection=False),
            dict(native_explicit_target=False),
            dict(native_preselected_target=True),
            dict(wakemu_rebound_child_selection=True),
            dict(native_trigger_context=None),
            dict(state_uid=123),
            dict(target_id=pc.id),
        ):
            with self.subTest(invocation=changes):
                self.assertFalse(
                    policy.permits_native_recipient_binding(
                        fight, effect, replace(invocation, **changes)
                    )
                )
        for changes in (
            dict(caster_id=-200),
            dict(target_id=1),
            dict(manager_actor_id=1),
            dict(channel=3),
            dict(event_ids=(5,)),
            dict(native_events_verified=False),
        ):
            with self.subTest(source=changes):
                current = replace(
                    invocation,
                    native_trigger_context=dict(
                        invocation.native_trigger_context, **changes
                    ),
                )
                self.assertFalse(
                    policy.permits_native_recipient_binding(fight, effect, current)
                )
        for changes in (
            dict(criteria="True"),
            dict(parameters=[0, 6]),
            dict(parameters="0,5"),
            dict(parameters={0: 0, 1: 5}),
            dict(parameters=[False, 5]),
            dict(area_class="anD"),
            dict(native_target_selector={"class": "fcE", "mask": 2}),
        ):
            with self.subTest(descriptor=changes), self.assertRaisesRegex(
                ValueError, "descriptor changed"
            ):
                policy.permits_native_recipient_binding(
                    fight, dict(effect, **changes), invocation
                )
        frozen = deepcopy(fight.native_encounter_recipient_binding)
        fight.native_encounter_recipient_binding["authority"] = "forged"
        with self.assertRaisesRegex(ValueError, "policy changed"):
            policy.permits_native_recipient_binding(fight, effect, invocation)
        fight.native_encounter_recipient_binding = frozen
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM encounter_recipient_binding_active WHERE map_id=1156"
            )
        # Frozen existing policy remains valid; an absent decision also stays pinned.
        self.assertTrue(
            policy.permits_native_recipient_binding(fight, effect, invocation)
        )
        assigned = roles.role_assignment(1156, [4378])
        absent = SimpleNamespace(phase="placement")
        self.assertIsNone(
            policy.freeze_encounter_recipient_binding_policy(absent, roles=assigned)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_recipient_binding_active VALUES "
                "(1156,ARRAY[4378],'wakemu-ogrest-ivory-native-recipient-v1')"
            )
        self.assertIsNone(
            policy.freeze_encounter_recipient_binding_policy(absent, roles=assigned)
        )
        self.assertFalse(
            policy.permits_native_recipient_binding(absent, effect, invocation)
        )
        for table in (
            "encounter_recipient_binding_versions",
            "encounter_recipient_binding_effects",
        ):
            with self.subTest(table=table), self.assertRaisesRegex(
                psycopg.Error, "immutable"
            ), self.store.connection() as db:
                db.execute("DELETE FROM " + table)
        # Without admission, keep existing fresh SELF behavior; do not globally fix it.
        fight.native_encounter_recipient_binding = None
        marker = native["effects"]["240712"]
        self.assertEqual(
            [
                row.target_id
                for row in f.resolver(marker, replace(invocation, reference=240712))
            ],
            [pc.id],
        )
