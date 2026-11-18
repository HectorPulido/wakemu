"""Focused native type-1 adapter proof for the four Whisper rescue targets."""
from contextlib import contextmanager
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server import (
    npc_world,
    owned_story_controller as controller,
    owned_story_mechanics,
    owned_story_npc_sources,
    owned_story_npc_targets,
    owned_story_npcs,
)
from wakfu_server.dungeon_achievement_authority import queries_from_state

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server"


class _DB:
    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return {"id": 7}


class _Store:
    def __init__(self, character):
        self.current = dict(character)
        self.db = _DB()

    @contextmanager
    def connection(self):
        yield self.db

    def lock_character(self, *_args, **_kwargs):
        return None

    def character(self, *_args, **_kwargs):
        return dict(self.current)


class WhisperPrisonNpcTargetsTests(unittest.TestCase):
    def test_four_native_type1_targets_complete_once_in_any_order(self):
        config = json.loads(
            (
                ROOT
                / "maps/owned_story_profiles/whisper-prison-1299.configuration.json"
            ).read_text()
        )
        profile = json.loads(
            (
                ROOT / "maps/owned_story_npc_profiles/whisper-prison-1299.json"
            ).read_text()
        )
        selected = controller.policy(config)
        groups = owned_story_npc_targets.validate(selected, profile)
        self.assertEqual(groups[0]["targets"], [1, 2, 3, 4])

        # Read actual action 252 from the hash-pinned native type-1 overlay.
        native = owned_story_npc_sources.catalog(profile)
        speaker = next(row for row in native["speakers"] if row["ref"] == 2099)
        action = next(row for row in speaker["actions"] if row["id"] == 252)
        self.assertEqual(
            (action["type"], action["criteria"]), (1, "IsAchievementActive(4872)")
        )

        instance_id = (1 << 57) + 9001
        state = dict(
            running=[],
            completed=[4872],
            active=[4872],
            active_periods={},
            active_unknown=[],
            objectives=[],
            variables={},
            tracking=[],
            recent=[],
            completion_dates={"4872": 1000},
        )
        native_authority = queries_from_state(state)
        self.assertTrue(native_authority["IsAchievementActive"](4872))
        self.assertTrue(native_authority["IsAchievementComplete"](4872))
        character = dict(
            id=41,
            account_id=7,
            map_id=1299,
            instance_id=instance_id,
            x=-21,
            y=-1,
            z=0,
            level=45,
        )
        store = _Store(character)
        completed = {"prison-door-open"}
        accepted = []
        final_evidence = []
        effect_batches = []

        for template in profile["npcs"]:
            actor = dict(
                template,
                actor_id=owned_story_npcs.actor_id(
                    instance_id, template["template_id"]
                ),
                map_id=1299,
                instance_id=instance_id,
                enabled=True,
            )
            opcode, packet = npc_world.spawn(
                actor, native, enabled_actions=actor["action_ids"]
            )
            self.assertEqual(opcode, 12608)
            self.assertIn(struct.pack(">q", actor["actor_id"]), packet)

        def apply_effects(_db, _store, _character, effects):
            effect_batches.append(effects)
            return [
                (13411, b"native scoped mechanic")
                for effect in effects
                if effect["kind"] == "scenario_event"
            ]

        def settle_stub(
            _db,
            _store,
            current,
            selected_profile,
            completed_steps,
            *,
            kind,
            reference,
            evidence,
            apply_effects,
        ):
            step = controller.plan(
                selected_profile, completed_steps, kind=kind, reference=reference
            )
            if step is None:
                return dict(applied=False, packets=[], step=None)
            if step["kind"] == "npc_targets_completed":
                final_evidence.append(evidence)
                self.assertEqual(
                    set(completed_steps),
                    {
                        "prison-door-open",
                        "prison-rescue-1",
                        "prison-rescue-2",
                        "prison-rescue-3",
                        "prison-rescue-4",
                    },
                )
            packets = apply_effects(_db, _store, current, step["effects"])
            accepted.append(step["id"])
            return dict(applied=True, packets=packets, step=step["id"])

        # Exercise the public NPC action adapter and actual source criterion,
        # while controller._settle is a receipt harness rather than a database
        # persistence claim. The target-group planner and aggregation remain real.
        with (
            patch.object(owned_story_npcs, "profiles", return_value=(profile,)),
            patch.object(owned_story_npcs, "_rows") as rows,
            patch.object(
                controller,
                "_scope",
                side_effect=lambda *_args, **_kwargs: (
                    selected,
                    set(completed) | set(accepted),
                ),
            ),
            patch.object(controller, "pending_scene", return_value=None),
            patch.object(controller, "_settle", side_effect=settle_stub),
            patch.object(owned_story_mechanics, "executor", return_value=apply_effects),
            patch("wakfu_server.environment_interactions._guard"),
        ):
            for identity in (3, 3, 1, 4, 2):
                template = next(
                    row
                    for row in profile["npcs"]
                    if row["controller_target_id"] == identity
                )
                actor_id = owned_story_npcs.actor_id(instance_id, identity)
                row = dict(
                    template,
                    actor_id=actor_id,
                    map_id=1299,
                    instance_id=instance_id,
                    enabled=True,
                )
                store.current.update(
                    x=template["interaction_anchor"]["x"],
                    y=template["interaction_anchor"]["y"],
                    z=template["interaction_anchor"]["z"],
                )
                rows.return_value = [(profile, row, state)]
                self.assertTrue(npc_world.nearby(store.current, row))
                session, packets = owned_story_npcs.begin(
                    store, 7, "generation", store.current, actor_id, 252
                )
                self.assertIsNone(session)
                if identity != 2:
                    self.assertEqual(packets, [])
                    self.assertNotIn("prison-release-complete", accepted)
                    if identity == 3 and accepted.count("prison-rescue-3") == 1:
                        self.assertEqual(len(accepted), 1)
                else:
                    self.assertEqual(packets, [(13411, b"native scoped mechanic")])

            self.assertEqual(
                [step for step in accepted if step.startswith("prison-rescue-")],
                [
                    "prison-rescue-3",
                    "prison-rescue-1",
                    "prison-rescue-4",
                    "prison-rescue-2",
                ],
            )
            self.assertEqual(accepted.count("prison-release-complete"), 1)
            self.assertEqual(
                final_evidence,
                [
                    dict(
                        target_ids=[1, 2, 3, 4],
                        source_actor_id=owned_story_npcs.actor_id(instance_id, 2),
                    )
                ],
            )
            self.assertEqual(effect_batches[-1][0]["event"], 11215)
            self.assertEqual(
                effect_batches[-1][0]["arguments"],
                [
                    "story_target:1",
                    "story_target:2",
                    "story_target:3",
                    "story_target:4",
                ],
            )
            self.assertIn(
                dict(kind="quest_objective", quest_id=4873, objective_id=10055),
                effect_batches[-1],
            )
            rows.return_value = [
                (
                    profile,
                    dict(
                        template,
                        actor_id=owned_story_npcs.actor_id(
                            instance_id, template["controller_target_id"]
                        ),
                        map_id=1299,
                        instance_id=instance_id,
                        enabled=True,
                    ),
                    state,
                )
                for template in profile["npcs"]
            ]
            from wakfu_server.owned_story_mechanics import _arguments

            self.assertEqual(
                _arguments(
                    store.db,
                    character,
                    effect_batches[-1][0],
                    selected,
                    store=store,
                ),
                [
                    owned_story_npcs.actor_id(instance_id, identity)
                    for identity in (1, 2, 3, 4)
                ],
            )

            # Repeating one real actor is inert; it cannot stand in for a
            # distinct target or emit the aggregate callback twice.
            repeated = profile["npcs"][0]
            actor_id = owned_story_npcs.actor_id(instance_id, 1)
            row = dict(
                repeated,
                actor_id=actor_id,
                map_id=1299,
                instance_id=instance_id,
                enabled=True,
            )
            store.current.update(x=-21, y=-1, z=0)
            rows.return_value = [(profile, row, state)]
            before = list(accepted)
            owned_story_npcs.begin(store, 7, "generation", store.current, actor_id, 252)
            self.assertEqual(accepted, before)
            self.assertEqual(accepted.count("prison-release-complete"), 1)

            # Actual scoped actor/range and native Active4872 criteria reject
            # foreign context, moved actors, and a completed-but-inactive quest.
            with self.assertRaisesRegex(ValueError, "unavailable or outside"):
                owned_story_npcs.begin(
                    store,
                    7,
                    "generation",
                    store.current,
                    owned_story_npcs.actor_id(instance_id + 1, 1),
                    252,
                )
            store.current.update(x=100, y=100, z=0)
            with self.assertRaisesRegex(ValueError, "unavailable or outside"):
                owned_story_npcs.begin(
                    store, 7, "generation", store.current, actor_id, 252
                )
            store.current.update(x=-21, y=-1, z=0)
            state["active"] = []
            with self.assertRaisesRegex(ValueError, "original native producer"):
                owned_story_npcs.begin(
                    store, 7, "generation", store.current, actor_id, 252
                )


if __name__ == "__main__":
    unittest.main()
