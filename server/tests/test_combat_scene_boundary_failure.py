"""Focused opt-in checks for native faP boundary-loss handling."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_scene_boundary_failure import (
    declaration,
    prepare_contact,
    settle_contact,
)
from wakfu_server.combat_encounter_scene_policy import prepare_scene
from wakfu_server.combat_encounter_roles import ORDINARY_POLICY


class NativeBoundaryFailureTests(unittest.TestCase):
    def descriptor(self):
        return {
            "schema_version": 1,
            "policy_id": "test-reviewed-school-border",
            "authority": "synthetic focused fixture; actual faP 909 prototype",
            "source_uri": "test-only://native-faP-909",
            "full_room_scope": True,
            "native_border_reference": 909,
            "native_boundary_failure": {
                "schema": "owned-boundary-failure-v1",
                "border_reference": 909,
                "losing_role": "original_controlled",
                "outcome": "opposing_team_wins",
                "evidence": "test fixture for the reviewed boundary rule",
            },
        }

    def make_fight(self, *, opted_in=True, null_rule=False):
        cells = {(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)}
        actor = SimpleNamespace(
            id=7,
            position=(0, 0, 0),
            team=0,
            controlled=True,
            owner_id=3,
            native_summon_source=None,
            is_summon=False,
            hp=91,
        )
        fight = SimpleNamespace(
            id=77,
            phase="active",
            winner=None,
            actors={7: actor},
            walkable=cells,
            order=[7],
            current=actor,
            native_effect_areas={},
            native_retained_records={},
            native_encounter_roles={
                "schema": "wakemu-encounter-roles-v1",
                "policy": ORDINARY_POLICY,
                "authority": "ordinary-existing-constructor-role-policy",
                "map_id": 1030,
                "monster_references": [3927],
                "player_team": 0,
                "npc_team": 1,
            },
            native_qi_snapshot={
                "x": 0,
                "y": 0,
                "width": 2,
                "height": 2,
                "cell_masks": [132, 4, 4, 4],
            },
            _in_play=lambda target: target.hp > 0,
            _event=lambda kind, **payload: events.append({"kind": kind, **payload}),
        )
        events = []
        descriptor = self.descriptor()
        if not opted_in:
            descriptor.pop("native_boundary_failure")
            descriptor.pop("native_border_reference")
        elif null_rule:
            descriptor["native_boundary_failure"] = None
        scope = {
            "map_id": 1030,
            "instance_id": 0,
            "group_id": 1,
            "room_order": 1,
            "policy_version": 1,
            "route_key": "fixture",
            "evidence_hashes": {},
        }
        fight.native_encounter_scene = prepare_scene(
            descriptor, scope=scope, room_cells=cells
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(fight, (7,))
        return fight, actor, events

    def row(self, fight):
        from wakfu_server.combat_battleground_border import install_battleground_border

        return install_battleground_border(
            fight,
            {
                "native_border_policy": "wakemu.compact-cardinal-perimeter-v1",
                "native_border_cells": {(0, 0, 0)},
                "min_z": 0,
            },
            reference=909,
            identity=-100,
        )

    def test_declaration_is_exact_and_bad_or_partial_opt_in_is_rejected(self):
        good = self.descriptor()
        self.assertEqual(declaration(good)["border_reference"], 909)
        for mutate in (
            lambda value: value["native_boundary_failure"].update(
                outcome="player_wins"
            ),
            lambda value: value["native_boundary_failure"].update(border_reference=910),
            lambda value: value.update(full_room_scope=False),
            lambda value: value["native_boundary_failure"].update(extra=True),
        ):
            invalid = deepcopy(good)
            mutate(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                declaration(invalid)

    def test_actual_909_fap_contact_settles_once_without_damage_or_death(self):
        fight, actor, events = self.make_fight()
        row = self.row(fight)
        contact = prepare_contact(fight, row, actor, 10000)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["event_id"], 10000)
        self.assertEqual(actor.hp, 91)
        self.assertTrue(settle_contact(fight, contact))
        self.assertFalse(settle_contact(fight, contact))
        self.assertEqual((fight.phase, fight.winner), ("finished", 1))
        self.assertEqual(actor.hp, 91)
        self.assertEqual([event["kind"] for event in events], ["finished"])
        self.assertEqual(events[0]["reason"], "owned_scene_boundary_failure")

    def test_native_area_event_delivery_settles_after_the_original_909_callback(self):
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime

        fight, actor, events = self.make_fight()
        row = self.row(fight)
        executions = []
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(synchronize=lambda: None),
            effects={},
            execute=executions.append,
        )
        runtime = NativeAreaEventRuntime(
            fight, dispatcher, definitions=native_effect_areas()
        )
        runtime.event(10000, actor.id, area_uid=row["uid"])
        self.assertEqual(len(executions), 2)  # Original 909 roots 152446/152447.
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(fight.winner, 1)
        self.assertEqual(actor.hp, 91)
        self.assertEqual(events[-1]["reason"], "owned_scene_boundary_failure")

    def test_original_909_delivery_without_opt_in_keeps_the_normal_fight_active(self):
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime

        fight, actor, _events = self.make_fight(opted_in=False)
        row = self.row(fight)
        executions = []
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(synchronize=lambda: None),
            effects={},
            execute=executions.append,
        )
        runtime = NativeAreaEventRuntime(
            fight, dispatcher, definitions=native_effect_areas()
        )
        runtime.event(10000, actor.id, area_uid=row["uid"])
        self.assertEqual(len(executions), 2)
        self.assertEqual((fight.phase, fight.winner, actor.hp), ("active", None, 91))

    def test_source_backed_native_floor_runs_enemy_callback_then_player_loss(self):
        """A real terrain/QI constructor and native runtime, in an offline fixture."""
        from native_recorded_instance_fixture import original_bootstrap_publication
        from jondo_native_support_probe import build_fixture
        from wakfu_server.combat_encounter_roles import (
            EncounterRoles,
            ORDINARY_POLICY,
        )
        from wakfu_server.combat_encounter_scene_policy import (
            arena_scene,
            bind_scene,
        )
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat.combat_qi_fight import move_registered_actor
        import wakfu_server.combat_bootstrap as combat_bootstrap
        import wakfu_server.combat.combat_encounter_roles as combat_encounter_roles

        original_create = combat_bootstrap.create_placement

        def create_with_native_border(character, monsters, arena, **kwargs):
            members = list(monsters)
            refs = tuple(sorted(member["ref"] for member in members))
            roles = EncounterRoles(
                ORDINARY_POLICY,
                "ordinary-existing-constructor-role-policy",
                character["map_id"],
                refs,
                0,
                1,
            )
            arena = dict(arena, native_encounter_roles=roles.record())
            descriptor = self.descriptor()
            scope = {
                "map_id": character["map_id"],
                "instance_id": character["instance_id"],
                "group_id": 1,
                "room_order": 1,
                "policy_version": 1,
                "route_key": "offline-native-faP-909",
                "evidence_hashes": {},
            }
            record = prepare_scene(
                descriptor, scope=scope, room_cells=arena["validated_cells"]
            )
            arena = arena_scene(record, arena, character, members)
            kwargs["terrain_effect_id"] = 909

            def bind_role_record(fight, assigned, **bind_kwargs):
                # Preserve actual team/placement validation's ordinary0/1 role
                # assignment without initializing unrelated encounter policies.
                for actor_id in bind_kwargs["player_ids"]:
                    self.assertEqual(fight.actors[actor_id].team, assigned.player_team)
                for actor_id in bind_kwargs["npc_ids"]:
                    self.assertEqual(fight.actors[actor_id].team, assigned.npc_team)
                fight.native_encounter_roles = assigned.record()

            with patch.object(
                combat_encounter_roles, "bind_roles", side_effect=bind_role_record
            ):
                fight, packets = original_create(character, monsters, arena, **kwargs)
            bind_scene(fight, arena, {member["id"]: member for member in members})
            return fight, packets

        with original_bootstrap_publication(), patch.object(
            combat_bootstrap, "create_placement", side_effect=create_with_native_border
        ):
            case = build_fixture(3927, 15, allies=((3928, 15, (-5, -7, -1)),))
        fight = case.fight
        self.assertEqual(fight.native_border_constructor["reference"], 909)
        player = fight.actors[7]
        enemies = [actor for actor in fight.actors.values() if not actor.controlled]
        self.assertEqual(len(enemies), 2)
        factory, _ = server_runtime(
            case.characters[7],
            case.monsters,
            case.decks[7],
            action_id=909,
            critical=False,
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        events = dispatcher.native_area_events
        border = {tuple(cell) for cell in fight.native_border_cells}
        adjacency = {}
        for left, right in fight.edges:
            adjacency.setdefault(tuple(left), set()).add(tuple(right))
            adjacency.setdefault(tuple(right), set()).add(tuple(left))

        def enter_border(actor):
            start = tuple(actor.position)
            queue, previous = [start], {start: None}
            destination = None
            for cell in queue:
                if cell in border:
                    destination = cell
                    break
                for nxt in sorted(adjacency.get(cell, ())):
                    if nxt not in previous:
                        previous[nxt] = cell
                        queue.append(nxt)
            self.assertIsNotNone(destination, "native path must reach QI.P perimeter")
            path, cursor = [], destination
            while cursor != start:
                path.append(cursor)
                cursor = previous[cursor]
            for nxt in reversed(path):
                prior = tuple(actor.position)
                move_registered_actor(fight, actor, nxt)
                try:
                    events.movement(actor.id, from_cell=prior, to_cell=nxt)
                except Exception as error:
                    self.fail(
                        f"native boundary callback failed: {error}; events={fight.events[-8:]!r}"
                    )

        # The original 909 effect roots execute against an NPC that crosses the
        # real generated QI.P shape; the optional loss rule is player-only.
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        enemy = enemies[0]
        enter_border(enemy)
        self.assertEqual(enemy.hp, 0)
        self.assertTrue(registered_ordinary_death(fight, enemy))
        self.assertEqual(fight.phase, "active")
        self.assertIsNone(getattr(fight, "native_boundary_failure_receipt", None))
        from wakfu_server.combat_battleground_border import (
            registered_border_kill_source,
        )

        causal_kill = next(
            event
            for event in reversed(fight.events)
            if event.get("kind") == "kill_hp_minimum_update"
            and event.get("target_id") == enemy.id
        )
        self.assertTrue(registered_border_kill_source(fight, causal_kill))
        forged_root = dict(
            causal_kill, generic_effect=causal_kill["generic_effect"] + 1
        )
        self.assertFalse(registered_border_kill_source(fight, forged_root))
        forged_uid = dict(causal_kill, source_id=causal_kill["source_id"] - 1)
        self.assertFalse(registered_border_kill_source(fight, forged_uid))
        actual_constructor = fight.native_border_constructor
        fight.native_border_constructor = dict(actual_constructor, reference=910)
        self.assertFalse(registered_border_kill_source(fight, causal_kill))
        fight.native_border_constructor = actual_constructor

        before_hp = player.hp
        enter_border(player)
        self.assertNotIn(tuple(player.position), border)
        self.assertEqual(player.hp, before_hp)
        self.assertEqual(fight.phase, "finished")
        self.assertNotEqual(fight.winner, 0)
        self.assertEqual(fight.native_boundary_failure_receipt["actor_id"], player.id)

    def test_no_opt_in_or_unqualified_contact_preserves_normal_fight(self):
        fight, actor, _events = self.make_fight(opted_in=False)
        row = self.row(fight)
        self.assertIsNone(prepare_contact(fight, row, actor, 10000))
        self.assertFalse(settle_contact(fight, None))
        self.assertEqual((fight.phase, fight.winner, actor.hp), ("active", None, 91))

        opted, target, _ = self.make_fight()
        area = self.row(opted)
        self.assertIsNone(prepare_contact(opted, area, target, 10002))
        self.assertIsNone(prepare_contact(opted, area, None, 10000))
        target.controlled = False
        self.assertIsNone(prepare_contact(opted, area, target, 10000))

        null_opt_in, null_target, _ = self.make_fight(null_rule=True)
        null_area = self.row(null_opt_in)
        self.assertIsNone(prepare_contact(null_opt_in, null_area, null_target, 10000))

    def test_contact_receipt_rejects_wrong_owner_and_scene_drift(self):
        fight, actor, _events = self.make_fight()
        row = self.row(fight)
        contact = prepare_contact(fight, row, actor, 10001)
        self.assertIsNotNone(contact)
        actor.owner_id = 4
        with self.assertRaisesRegex(ValueError, "authentic contact"):
            settle_contact(fight, contact)
        actor.owner_id = 3
        fight.native_encounter_scene["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source changed"):
            settle_contact(fight, contact)


if __name__ == "__main__":
    unittest.main()
