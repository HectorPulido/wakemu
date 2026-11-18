"""Narrow authority tests for controlled actors' source-bound scene states."""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from types import ModuleType
from unittest.mock import patch

from wakfu_server.combat.combat_scene_controlled_states import (
    _application_scope,
    declarations,
    placement_application_authorized,
    placement_stat_context,
    prepare,
    install,
)


class ControlledSceneStateAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.program = dict(
            state_id=4063,
            level=1,
            protected=True,
            source_sha256="a" * 64,
            evidence="reviewed controlled scene carrier",
        )
        self.descriptor = dict(
            full_room_scope=True, controlled_state_programs=[self.program]
        )
        self.actor = SimpleNamespace(
            id=71, owner_id=19, team=0, controlled=True, position=(0, 0, 0)
        )
        self.fight = SimpleNamespace(
            phase="placement",
            actors={71: self.actor},
            native_encounter_scene=dict(
                descriptor=self.descriptor,
                sha256="b" * 64,
                scope=dict(instance_id=9001),
            ),
        )
        self.characters = {
            71: dict(id=71, account_id=19, map_id=1018, instance_id=9001)
        }
        self.plans = (self.program,)
        self.roles = SimpleNamespace(player_team=0, map_id=1018)

    @contextmanager
    def source(
        self, descriptor=None, *, source_digest="a" * 64, duration=-1, realtime=0
    ):
        catalog_module = ModuleType("wakfu_server.combat.combat_server_spell")
        catalog_module.states_catalog = lambda: {
            "states": {"4063": {"maximum_level": 1}},
            "effects": {},
        }
        with patch.dict(
            "sys.modules", {"wakfu_server.combat.combat_server_spell": catalog_module}
        ), patch(
            "wakfu_server.combat.combat_encounter_scene_policy.frozen_scene",
            return_value=self.descriptor if descriptor is None else descriptor,
        ), patch(
            "wakfu_server.combat.combat_encounter_roles.assigned_roles",
            return_value=self.roles,
        ), patch(
            "wakfu_server.combat.combat_encounter_scene_states.native_state_source_digest",
            return_value=source_digest,
        ), patch(
            "wakfu_server.combat.combat_definitions.state_profile",
            return_value=dict(duration=duration, realtime_duration=realtime),
        ):
            yield

    def test_contextvar_limits_exact_fight_actor_state_and_cleans_after_exception(self):
        self.assertFalse(placement_application_authorized(self.fight, 71, 71, 4063, 1))
        self.assertFalse(
            placement_stat_context(
                self.fight, SimpleNamespace(caster_id=71, target_id=71)
            )
        )
        with self.source():
            with self.assertRaisesRegex(RuntimeError, "forced failure"):
                with _application_scope(
                    self.fight, self.characters, self.plans, self.program
                ):
                    self.assertTrue(
                        placement_application_authorized(self.fight, 71, 71, 4063, 1)
                    )
                    self.assertTrue(
                        placement_stat_context(
                            self.fight, SimpleNamespace(caster_id=71, target_id=71)
                        )
                    )
                    self.assertFalse(
                        placement_application_authorized(self.fight, 71, 72, 4063, 1)
                    )
                    self.assertFalse(
                        placement_application_authorized(self.fight, 71, 71, 4062, 1)
                    )
                    self.assertFalse(
                        placement_application_authorized(self.fight, 71, 71, 4063, 2)
                    )
                    other_fight = deepcopy(self.fight)
                    self.assertFalse(
                        placement_application_authorized(other_fight, 71, 71, 4063, 1)
                    )
                    self.fight.phase = "active"
                    self.assertFalse(
                        placement_application_authorized(self.fight, 71, 71, 4063, 1)
                    )
                    self.fight.phase = "placement"
                    raise RuntimeError("forced failure")
            self.assertFalse(
                placement_application_authorized(self.fight, 71, 71, 4063, 1)
            )
        self.assertFalse(
            placement_stat_context(
                self.fight, SimpleNamespace(caster_id=71, target_id=71)
            )
        )

    def test_prepare_requires_owned_positive_instance_and_exact_native_source(self):
        with self.source():
            self.assertEqual(prepare(self.fight, self.characters), self.plans)

            for field, value in (
                ("instance_id", 0),
                ("account_id", 20),
                ("map_id", 1001),
            ):
                with self.subTest(field=field):
                    changed = deepcopy(self.characters)
                    changed[71][field] = value
                    with self.assertRaisesRegex(ValueError, "original player scope"):
                        prepare(self.fight, changed)

            self.fight.phase = "active"
            with self.assertRaisesRegex(ValueError, "original player scope"):
                prepare(self.fight, self.characters)
            self.fight.phase = "placement"

        with self.source(source_digest="c" * 64):
            with self.assertRaisesRegex(ValueError, "source changed"):
                prepare(self.fight, self.characters)
        with self.source(duration=10):
            with self.assertRaisesRegex(ValueError, "indefinite native carrier"):
                prepare(self.fight, self.characters)

    def test_malformed_or_non_full_room_declaration_fails_closed(self):
        bad = deepcopy(self.descriptor)
        bad["controlled_state_programs"][0]["level"] = True
        with self.assertRaisesRegex(ValueError, "exact reviewed source"):
            declarations(bad)

    def test_actual_bworkball_2338_native_negative_realtime_state_is_installed(self):
        root = Path(__file__).resolve().parents[2]
        state_rows = json.loads(
            (
                root / ".runtime/quest-archetypes/bworkball/morph-state-source.json"
            ).read_text()
        )
        effect_rows = json.loads(
            (root / ".runtime/quest-archetypes/bworkball/morph-source.json").read_text()
        )
        state = next(
            row["payload"]
            for row in state_rows
            if row["collection"] == "states" and row["record_key"] == "2338"
        )
        effect = next(
            row["payload"] for row in effect_rows if row["record_key"] == "105570"
        )
        catalog = {"states": {"2338": state}, "effects": {"105570": effect}}
        profile = json.loads(
            (
                root
                / "server/wakfu_server/maps/owned_story_profiles/wild-estate-bworkball-719-encounters.json"
            ).read_text()
        )
        descriptor = next(
            room["encounter_scene"]
            for room in profile["rooms"]
            if room.get("encounter_scene", {}).get("controlled_state_programs")
        )
        program = descriptor["controlled_state_programs"][0]
        self.program = program
        self.plans = (program,)
        self.descriptor = descriptor
        self.actor.id = 2338
        self.fight.actors = {2338: self.actor}
        self.fight.native_encounter_scene = dict(
            descriptor=descriptor,
            sha256="b" * 64,
            scope=dict(instance_id=9001),
        )
        self.characters = {
            2338: dict(id=2338, account_id=19, map_id=719, instance_id=9001)
        }
        self.roles = SimpleNamespace(player_team=0, map_id=719)
        with patch(
            "wakfu_server.combat.combat_encounter_scene_policy.frozen_scene",
            return_value=descriptor,
        ), patch(
            "wakfu_server.combat.combat_encounter_roles.assigned_roles",
            return_value=self.roles,
        ):
            self.assertEqual(
                prepare(self.fight, self.characters, catalog=catalog), (program,)
            )

            bad_descriptor = deepcopy(descriptor)
            bad_descriptor["controlled_state_programs"][0]["source_sha256"] = "0" * 64
            with patch(
                "wakfu_server.combat.combat_encounter_scene_policy.frozen_scene",
                return_value=bad_descriptor,
            ):
                with self.assertRaisesRegex(ValueError, "source changed"):
                    prepare(self.fight, self.characters, catalog=catalog)
            with patch(
                "wakfu_server.combat.combat_definitions.state_profile",
                return_value={"duration": -1, "realtime_duration": 1},
            ):
                with self.assertRaisesRegex(ValueError, "indefinite native carrier"):
                    prepare(self.fight, self.characters, catalog=catalog)
            with patch(
                "wakfu_server.combat.combat_definitions.state_profile",
                return_value={"duration": 0, "realtime_duration": -1000},
            ):
                with self.assertRaisesRegex(ValueError, "indefinite native carrier"):
                    prepare(self.fight, self.characters, catalog=catalog)

        # Keep the real state profile and native time payload; stub only the
        # retention boundary so the exact values passed to it are observable.
        from types import ModuleType
        from wakfu_server.combat.combat_native_timing_context import native_time_payload

        spell_module = ModuleType("wakfu_server.combat.combat_server_spell")
        spell_module.states_catalog = lambda: catalog
        context_seen = []
        self.actor.state_ledger = SimpleNamespace(entries=[])

        class Retention:
            def apply_state_reference(
                inner,
                handler,
                invocation,
                reference,
                level,
                *,
                carrier_context,
                protected
            ):
                context_seen.append(carrier_context)
                self.actor.state_ledger.entries.append(
                    SimpleNamespace(uid=9901, reference=reference)
                )
                return True

        dispatcher = SimpleNamespace(
            native_state_handler=SimpleNamespace(catalog=catalog),
            native_retention=Retention(),
        )
        factory = lambda fight, options: (dispatcher, None)
        with patch.dict(
            "sys.modules", {"wakfu_server.combat.combat_server_spell": spell_module}
        ), patch(
            "wakfu_server.combat.combat_encounter_scene_policy.frozen_scene",
            return_value=descriptor,
        ), patch(
            "wakfu_server.combat.combat_encounter_roles.assigned_roles",
            return_value=self.roles,
        ), patch(
            "wakfu_server.combat.combat_npc_initialization._runtime",
            return_value=(factory, None),
        ), patch(
            "wakfu_server.combat.combat_qi_fight.current_registry"
        ):
            install(self.fight, self.characters, {}, (program,))
        self.assertEqual(context_seen[0].native_turn_clock, -1)
        self.assertEqual(context_seen[0].native_realtime_remaining, -1000)
        self.assertEqual(
            context_seen[0].timing_payload,
            native_time_payload(realtime_remaining=-1000),
        )
        self.assertEqual(
            self.fight.native_controlled_scene_state_receipt["state_uids"], [9901]
        )
        bad = deepcopy(self.descriptor)
        bad["full_room_scope"] = False
        with self.assertRaisesRegex(ValueError, "exact reviewed source"):
            declarations(bad)


class MorphExtensionScopeTests(unittest.TestCase):
    def test_explicit_native_profile_ids_are_finite_unique_and_not_mixed_with_legacy_scope(
        self,
    ):
        from tools.stage_encounter_morph_catalog import extension_scope

        additions, tag = extension_scope(None, [3907, 3891])
        self.assertEqual(additions, {"3891", "3907"})
        self.assertEqual(tag, "encounter-morphs-3891-3907")
        with self.assertRaises(ValueError):
            extension_scope(None, [3907, 3907])
        with self.assertRaises(ValueError):
            extension_scope(3907, [3907])
        with self.assertRaises(ValueError):
            extension_scope(None, [True])


if __name__ == "__main__":
    unittest.main()
