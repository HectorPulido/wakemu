import copy
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_runtime_config


class RecordingDatabase:
    def __init__(self, *, current=None, context=None):
        self.current = current
        self.context = context
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        return self

    def fetchone(self):
        sql = self.statements[-1][0]
        if "FROM dungeon_runtime_configurations" in sql:
            return self.current
        if "FROM dungeon_context_policy_versions" in sql:
            return self.context
        return None

    def writes(self):
        return [
            sql
            for sql, _ in self.statements
            if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]


def make_config(*, final_ref=4400):
    return {
        "route": {"key": "native_dungeon_test"},
        "version": 1,
        "provenance": "focused-admission-regression",
        "topology": {},
        "level_policy": {"mode": "native_minimum"},
        "compiled_plan": {
            "rooms": [
                {
                    "order": 1,
                    "monsters": [
                        {"ref_id": 1, "native_min_level": 10, "native_max_level": 20}
                    ],
                },
                {
                    "order": 2,
                    "monsters": [
                        {
                            "ref_id": final_ref,
                            "native_min_level": 203,
                            "native_max_level": 208,
                        }
                    ],
                },
            ]
        },
        "context_policy": {"route_key": "native_dungeon_test", "policy_version": 1},
    }


def enabled_policy(refs):
    return {
        "schema": "native-npc-activation-v1",
        "enabled_monsters": {
            str(ref): {"min_level": lo, "max_level": hi, "spell_ids": [100 + ref]}
            for ref, lo, hi in refs
        },
    }


class DungeonConfigurationAdmissionTests(unittest.TestCase):
    def install(self, config, db, policy, *, native_override=None):
        native_override = native_override or {}

        def reference(ref):
            lo, hi = {1: (10, 20), 4400: (203, 208), 5114: (203, 208)}[ref]
            return native_override.get(
                ref,
                {
                    "min_level": lo,
                    "max_level": hi,
                    "native_abilities": [{"spell_id": 100 + ref}],
                },
            )

        with (
            patch.object(
                dungeon_runtime_config, "prepare_configuration", return_value=config
            ),
            patch(
                "wakfu_server.dungeon_monster_admission.current_policy",
                return_value=policy,
            ),
            patch("wakfu_server.monsters.reference", side_effect=reference),
        ):
            dungeon_runtime_config.install_configuration(db, config)

    def test_final_actionless_species_is_rejected_before_any_configuration_write(self):
        for ref in (4400, 5114):
            with self.subTest(ref=ref):
                config = make_config(final_ref=ref)
                db = RecordingDatabase()
                with self.assertRaisesRegex(ValueError, "lacks ordinary NPC admission"):
                    self.install(config, db, enabled_policy([(1, 10, 20)]))
                self.assertEqual(db.writes(), [])

    def test_every_room_uses_selected_native_minimum_and_admission_passes(self):
        config = make_config()
        db = RecordingDatabase()
        # Only the selected native-minimum grade is admitted; this should pass
        # without treating every level in the frozen range as activated.
        policy = enabled_policy([(1, 10, 10), (4400, 203, 203)])
        from wakfu_server import dungeon_monster_admission

        with patch.object(
            dungeon_monster_admission,
            "require",
            wraps=dungeon_monster_admission.require,
        ) as require:
            self.install(config, db, policy)
        self.assertEqual(
            [
                (call.args[1], call.args[2], call.args[3])
                for call in require.call_args_list
            ],
            [(1, 10, 10), (4400, 203, 203)],
        )
        self.assertTrue(db.writes())

    def test_reactivation_is_rechecked_and_frozen_native_bounds_must_match(self):
        config = make_config()
        db = RecordingDatabase(current={"value": copy.deepcopy(config)})
        with self.assertRaisesRegex(ValueError, "lacks ordinary NPC admission"):
            self.install(config, db, enabled_policy([(1, 10, 20)]))
        self.assertEqual(db.writes(), [])

        db = RecordingDatabase()
        mismatched = {
            4400: {
                "min_level": 202,
                "max_level": 208,
                "native_abilities": [{"spell_id": 4500}],
            }
        }
        with self.assertRaisesRegex(ValueError, "grade bounds changed"):
            self.install(
                config,
                db,
                enabled_policy([(1, 10, 20), (4400, 203, 208)]),
                native_override=mismatched,
            )
        self.assertEqual(db.writes(), [])


if __name__ == "__main__":
    unittest.main()
