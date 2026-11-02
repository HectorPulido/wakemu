"""Entry can resolve its native destination before optional run state exists."""
from contextlib import ExitStack
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import dungeon_runtime


class DungeonEntryInitializationTests(unittest.TestCase):
    def test_special_admission_honors_minimum_policy_without_waiving_seat_limit(self):
        from wakfu_server import special_instance_admission

        policy = dict(
            policy_id="isolated-native-133-admission",
            authority="reconstructed_wakemu_native_scene_v1",
            route=dict(
                template_id=136,
                definition_id=133,
                entry_map_id=1202,
                entry_object_id=29076,
                destination_id=3117,
                start_map_id=1159,
            ),
            minimum_configuration_version=5,
            maximum_members=3,
            competitive_ceiling=50,
        )
        route = SimpleNamespace(
            key="native_dungeon_133",
            context_route_key=None,
            criterion="GetRealLevel() >= 36",
            **policy["route"]
        )
        for enforce_minimum, controlled, allowed in (
            (False, 1, True),
            (True, 1, False),
            (False, 4, False),
        ):
            with self.subTest(
                enforce_minimum=enforce_minimum, controlled=controlled
            ), ExitStack() as stack:
                db = Mock()

                def execute(query, parameters):
                    if "FROM settings" in query:
                        value = {"version": 1, "enforce_minimum_level": enforce_minimum}
                        return Mock(fetchone=Mock(return_value={"value": value}))
                    return Mock(
                        fetchall=Mock(
                            return_value=[
                                dict(
                                    id=1,
                                    level=1,
                                    snapshot=dict(
                                        running=[], completed=[], objectives=[]
                                    ),
                                )
                            ]
                        )
                    )

                db.execute.side_effect = execute
                stack.enter_context(
                    patch(
                        "wakfu_server.native_scene_policy_authority.admission_policy",
                        return_value=policy,
                    )
                )
                stack.enter_context(
                    patch(
                        "wakfu_server.companions.controlled_count",
                        return_value=controlled - 1,
                    )
                )
                stack.enter_context(
                    patch(
                        "wakfu_server.dungeon_difficulty.definition",
                        return_value=dict(
                            forced_competitive=True,
                            native_level=36,
                        ),
                    )
                )
                stack.enter_context(
                    patch(
                        "wakfu_server.dungeon_difficulty.selection",
                        return_value=dict(
                            competitive=True,
                            competitive_max_level=50,
                        ),
                    )
                )
                session = dict(
                    context_policy_version=5, members=[1], instance_id=81, reused=False
                )
                resolved = dict(route=route, native_destination={})
                if allowed:
                    special_instance_admission.initialize(db, session, resolved)
                    self.assertIn("special_instance_admission", session)
                else:
                    with self.assertRaises(ValueError):
                        special_instance_admission.initialize(db, session, resolved)

    def test_native_entry_precedes_ballot_initialization_without_losing_policy(self):
        run = dict(
            instance_id=81, context_route_key="fixture", context_policy_version=1
        )
        config = dict(
            compiled_plan=dict(document_sha256="a" * 64),
            topology=dict(
                asset_map_id=123, optional_vote_access=dict(rule_key="fixture")
            ),
        )
        destination = dict(map_id=123, x=4, y=8, z=0)
        for initialized in (False, True):
            with self.subTest(initialized=initialized), ExitStack() as stack:
                progress = (
                    dict(instance_id=81, catalog_hash="a" * 64) if initialized else None
                )
                db = Mock()
                db.execute.side_effect = [
                    Mock(fetchone=Mock(return_value=run)),
                    Mock(fetchone=Mock(return_value=progress)),
                ] + (
                    [Mock(fetchone=Mock(return_value=progress))] if initialized else []
                )
                stack.enter_context(
                    patch.object(
                        dungeon_runtime.dungeon_runtime_config,
                        "pinned_configuration",
                        return_value=config,
                    )
                )
                stack.enter_context(
                    patch(
                        "wakfu_server.dungeon_optional_continuations.scene_enabled",
                        return_value=False,
                    )
                )
                project = stack.enter_context(
                    patch(
                        "wakfu_server.dungeon_optional_votes.project_configuration",
                        return_value=config,
                    )
                )
                self.assertEqual(
                    destination, dungeon_runtime.entry_destination(db, run, destination)
                )
                if initialized:
                    project.assert_called_once_with(db, progress, config)
                else:
                    project.assert_not_called()
                self.assertIn("optional_vote_access", config["topology"])


if __name__ == "__main__":
    unittest.main()
