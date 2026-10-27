"""Ordinary helper assembly, source scope and real native controller codec."""
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import struct
import unittest

from wakfu_server.combat_encounter_scene_helpers import (
    prepare_scene_roster,
    adapt_helper_placement,
    bind_scene_helper_controls,
    scene_helper_controller_records,
    reward_eligible_members,
)
from wakfu_server.combat_scene_controller_snapshot import (
    NativeControllerRecord,
    controller_snapshot,
)

MODULE = "wakfu_server.combat_encounter_scene_helpers"


class EncounterSceneHelperTests(unittest.TestCase):
    def character(self):
        from wakfu_server.progression import level_xp

        return dict(
            id=100,
            account_id=7,
            breed=8,
            level=200,
            xp=level_xp(200),
            hp=60,
            max_hp=60,
            map_id=1134,
            x=0,
            y=0,
            z=0,
            instance_id=0,
            active_build_index=0,
            inventory_items=[],
            builds={},
        )

    def roster(self, reference=5848):
        from wakfu_server.monsters import owned_instance, reference as native_reference

        char = self.character()
        boss = owned_instance(
            reference,
            native_reference(reference)["min_level"],
            -200,
            map_id=1134,
            x=6,
            y=0,
            z=0,
        )
        store = SimpleNamespace(connection=lambda: nullcontext(None))
        positions = (
            [(2, 0, 0), (2, 1, 0)]
            if reference == 5848
            else [(2, 0, 0), (2, 1, 0), (3, 1, 0)]
        )
        with patch(MODULE + "._cells", return_value=positions), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=1000000
        ), patch(
            "wakfu_server.combat_encounter_roles.role_assignment",
            return_value=SimpleNamespace(policy="wakemu-ordinary-player0-npc1-v1"),
        ), patch(
            "wakfu_server.combat_supreme_scene_policies.policy_for_reference",
            return_value=None,
        ), patch(
            "wakfu_server.builds.effective_sheet_level", return_value=200
        ), patch(
            "wakfu_server.combat_encounter_objective_spirit._published_book",
            return_value=True,
        ):
            members, manifest = prepare_scene_roster(store, char, (boss,))
        return char, members, manifest

    def fight(self):
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_wire import arena

        char, members, manifest = self.roster()
        cells = {(x, y, 0) for x in range(7) for y in range(4)}
        placement = {
            0: {(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0)},
            1: {(6, 0, 0), (5, 1, 0), (5, 2, 0)},
        }
        value = arena(1134, 0, sorted(cells), placement)
        value.update(
            validated_cells=cells,
            valid_edges=set(),
            placement_cells=placement,
            native_encounter_scene_helpers=manifest,
            participant_positions=[
                [[m[k] for k in ("x", "y", "z")], list(cell)]
                for m, cell in zip(members, ((6, 0, 0), (5, 1, 0), (5, 2, 0)))
            ],
        )
        catalog = dict(
            default_actor_radius=0,
            npc_profiles={str(m["ref"]): dict(physical_radius=0) for m in members},
        )
        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value=catalog,
        ):
            adapt_helper_placement(char, members, value)
        fight, _ = create_placement(
            char,
            members,
            value,
            fight_id=19,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=1,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )
        return fight, char, members, manifest

    def test_ordinary_rosters_and_authored_original_roles_keep_priority(self):
        char = self.character()
        self.assertEqual(
            prepare_scene_roster(None, char, (dict(ref=5525),)),
            ((dict(ref=5525),), None),
        )
        source = (dict(id=-200, ref=3518),)
        with patch(
            "wakfu_server.combat_encounter_roles.role_assignment",
            return_value=SimpleNamespace(policy="authored-scene"),
        ), patch(MODULE + "._cells") as geometry:
            self.assertEqual(prepare_scene_roster(None, char, source), (source, None))
            geometry.assert_not_called()

    def test_authored_spirit_roles_skip_optional_book_and_roster_reconstruction(self):
        char, source = self.character(), (dict(id=-200, ref=5848),)
        with patch(
            "wakfu_server.combat_encounter_roles.role_assignment",
            return_value=SimpleNamespace(policy="authored-spirit"),
        ), patch(
            MODULE + "._scene", side_effect=AssertionError("authored policy must win")
        ):
            self.assertEqual(prepare_scene_roster(None, char, source), (source, None))

    def test_security_initial_helpers_are_actual_native_ordinary_sources(self):
        _char, members, manifest = self.roster(3518)
        self.assertEqual([m["ref"] for m in members], [3518, 3516, 3516, 3516])
        self.assertEqual([m["level"] for m in members], [150] * 4)
        self.assertEqual([m["hp"] for m in members], [30000, 4250, 4250, 4250])
        self.assertEqual(len({m["id"] for m in members}), 4)
        self.assertTrue(
            all(
                row["controller_role"] == "self"
                for row in manifest["source"]["helpers"]
            )
        )
        self.assertFalse(any("summon" in key for member in members for key in member))

    def test_friendly_npc_constructor_control_and_12514_preserve_original_identity(
        self,
    ):
        from wakfu_server.combat_controller_registry import (
            current_native_controller,
            _row,
        )
        from wakfu_server.combat_effective_control import effective_input_owner
        from wakfu_server.combat_phase import action_transition

        fight, char, members, manifest = self.fight()
        helpers = manifest["source"]["helpers"]
        for row in helpers:
            actor = fight.actors[row["actor_id"]]
            self.assertFalse(actor.controlled)
            self.assertIsNone(actor.owner_id)
            self.assertEqual(actor.team, 0)
            self.assertEqual(current_native_controller(fight, actor.id), actor.id)
            self.assertIn(actor.position, fight.placement[0])
            self.assertFalse(hasattr(actor, "native_summon_source"))
            actor.native_controlled_by_ai = True
        # Component birth receipts: native state initialization is qualified by
        # its separate real suite; do not claim the full Spirit encounter here.
        fight.native_npc_initialization_receipts = {
            row["actor_id"]: dict(
                ref=row["reference"],
                initialized=True,
                descriptor_level=fight.actors[row["actor_id"]].effective_level,
            )
            for row in helpers
        }
        bind_scene_helper_controls(
            fight,
            source_policy=manifest["source"]["policy"],
            source_digest=manifest["source_digest"],
        )
        records = scene_helper_controller_records(fight)
        self.assertEqual(len(records), 2)
        for row in helpers:
            actor = fight.actors[row["actor_id"]]
            self.assertEqual(effective_input_owner(fight, actor), char["account_id"])
            self.assertEqual(_row(fight, actor.id)["original_controller"], actor.id)
            self.assertFalse(actor.native_controlled_by_ai)
            self.assertFalse(actor.controlled)
            self.assertIsNone(actor.owner_id)
        _op, ordinary = action_transition(fight.id, timestamp_ms=100)
        _op, controlled = action_transition(
            fight.id, timestamp_ms=100, controller_records=records
        )
        encoded = controller_snapshot(records)
        self.assertEqual(ordinary[-6:], struct.pack(">ih", 2, 0))
        self.assertEqual(controlled[-len(encoded) :], encoded)
        self.assertEqual(reward_eligible_members(fight, members), (members[0],))
        prior = controller_snapshot(records)
        bind_scene_helper_controls(
            fight,
            source_policy=manifest["source"]["policy"],
            source_digest=manifest["source_digest"],
        )
        self.assertEqual(
            controller_snapshot(scene_helper_controller_records(fight)), prior
        )

    def test_ordinary_scene_helper_action_uses_actual_native_book_and_owner(self):
        from wakfu_server.combat_cast import resolve_owned_spell_action
        from wakfu_server.monsters import native_abilities

        fight, char, members, manifest = self.fight()
        for actor in fight.actors.values():
            actor.native_controlled_by_ai = not actor.controlled
        fight.native_npc_initialization_receipts = {
            row["actor_id"]: dict(
                ref=row["reference"],
                initialized=True,
                descriptor_level=fight.actors[row["actor_id"]].effective_level,
            )
            for row in manifest["source"]["helpers"]
        }
        bind_scene_helper_controls(
            fight,
            source_policy=manifest["source"]["policy"],
            source_digest=manifest["source_digest"],
        )
        fight.ready(char["account_id"])
        row = manifest["source"]["helpers"][0]
        actor = fight.actors[row["actor_id"]]
        fight.turn_index = fight.order.index(actor.id)
        ability = native_abilities(row["reference"], actor.effective_level)[0]
        request = dict(actor_id=actor.id, spell_uid=ability["spell_id"])
        selected, reference, level = resolve_owned_spell_action(
            request, char, fight, 7, b""
        )
        self.assertIs(selected, actor)
        self.assertEqual(
            (reference, level), (ability["spell_id"], ability["spell_level"])
        )
        self.assertFalse(hasattr(actor, "native_summon_source"))
        self.assertFalse(hasattr(fight, "native_controller_action_books"))
        with self.assertRaises(ValueError):
            resolve_owned_spell_action(request, char, fight, 8, b"")
        with self.assertRaisesRegex(ValueError, "absent"):
            resolve_owned_spell_action(
                dict(actor_id=actor.id, spell_uid=1234567), char, fight, 7, b""
            )

    def controlled_fixture(self):
        fight, char, members, manifest = self.fight()
        for actor in fight.actors.values():
            actor.native_controlled_by_ai = not actor.controlled
        fight.native_npc_initialization_receipts = {
            row["actor_id"]: dict(
                ref=row["reference"],
                initialized=True,
                descriptor_level=fight.actors[row["actor_id"]].effective_level,
            )
            for row in manifest["source"]["helpers"]
        }
        bind_scene_helper_controls(
            fight,
            source_policy=manifest["source"]["policy"],
            source_digest=manifest["source_digest"],
        )
        return fight, char, members, manifest

    def test_connected_cast_selects_actual_helper_controller_after_main_changes(self):
        from wakfu_server.combat_cast_delivery_source import connected_action_source
        from wakfu_server.combat_cast import resolve_owned_spell_action
        from wakfu_server.monsters import native_abilities

        fight, char, _members, manifest = self.controlled_fixture()
        row = manifest["source"]["helpers"][0]
        actor = fight.actors[row["actor_id"]]
        fight.ready(7)
        fight.turn_index = fight.order.index(actor.id)
        new_main = dict(char, id=201)
        sources, decks = {100: char, 201: new_main}, {
            100: b"principal",
            201: b"new-main",
        }
        actual, deck = connected_action_source(fight, sources, decks, 201, 7, actor.id)
        self.assertIs(actual, char)
        self.assertEqual(deck, b"principal")
        ability = native_abilities(row["reference"], actor.effective_level)[0]
        selected = resolve_owned_spell_action(
            dict(actor_id=actor.id, spell_uid=ability["spell_id"]),
            actual,
            fight,
            7,
            deck,
        )
        self.assertEqual(selected, (actor, ability["spell_id"], ability["spell_level"]))
        with self.assertRaises(ValueError):
            connected_action_source(fight, sources, {201: b"main"}, 201, 7, actor.id)
        with self.assertRaises(ValueError):
            connected_action_source(fight, sources, decks, 201, 8, actor.id)

    def test_genuine_controller_book_precedes_original_scene_principal(self):
        from wakfu_server.combat_cast_delivery_source import connected_action_source
        from wakfu_server.combat_cast import resolve_owned_spell_action
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_global_pv_collections import register_global_fighter
        from wakfu_server.combat_controller_registry import transfer_native_controller
        from wakfu_server.combat_character_copy_book import CopyBookAction
        from wakfu_server.monsters import native_abilities

        fight, _char, _members, manifest = self.controlled_fixture()
        other = Actor(200, 0, (1, 1, 0), 60, 6, 3, 1, 1, 8, True)
        other.native_controlled_by_ai = False
        fight.actors[other.id] = other
        register_global_fighter(fight, other.id)
        from wakfu_server.combat_obstacle_ids import assign_obstacle_ids

        assign_obstacle_ids(fight.actors.values())
        fight.ready(7)
        if fight.phase == "placement":
            fight.ready(8)
        row = manifest["source"]["helpers"][0]
        actor = fight.actors[row["actor_id"]]
        fight.turn_index = fight.order.index(actor.id)
        ability = native_abilities(row["reference"], actor.effective_level)[0]
        transfer_native_controller(fight, actor.id, other.id)
        # Component record of the pre-existing genuine eWD-published book API;
        # original207 runner execution is verified in its dedicated suite.
        fight.native_controller_action_books = {
            actor.id: dict(
                producer="eWD207.eZd.fQM.actual",
                controller_id=other.id,
                running_uid=50,
                actions=(
                    CopyBookAction(
                        ability["spell_id"],
                        ability["spell_id"],
                        ability["spell_level"],
                        False,
                        False,
                        True,
                    ),
                ),
            )
        }
        source = dict(id=200, account_id=8)
        selected, deck = connected_action_source(
            fight, {200: source}, {200: b"other"}, 200, 8, actor.id
        )
        self.assertIs(selected, source)
        resolved = resolve_owned_spell_action(
            dict(actor_id=actor.id, spell_uid=ability["spell_id"]),
            source,
            fight,
            8,
            deck,
        )
        self.assertEqual(resolved, (actor, ability["spell_id"], ability["spell_level"]))
        self.assertEqual(fight.native_scene_helper_manifest["source"]["account_id"], 7)

    def test_helper_score_proof_uses_current_ready_human_and_native_birth(self):
        from wakfu_server.combat_encounter_scene_helpers import (
            helper_score_owner_receipt,
        )
        from wakfu_server.combat_quest_scene_authority import canonical_digest

        fight, char, _members, manifest = self.controlled_fixture()
        actor = fight.actors[manifest["source"]["helpers"][0]["actor_id"]]
        ready_source = dict(
            players=[dict(actor_id=char["id"], account_id=char["account_id"])]
        )
        admission = dict(
            status="granted",
            ready_participants=dict(
                source=ready_source, source_digest=canonical_digest(ready_source)
            ),
        )
        # The actual Spirit admission/Ready authority has its dedicated suite;
        # this component qualifies the additional ordinary-NPC score proof.
        with patch(
            "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
            return_value=admission,
        ):
            proof = helper_score_owner_receipt(fight, actor)
            self.assertEqual(proof["owner_actor_id"], char["id"])
            self.assertEqual(proof["source_digest"], manifest["source_digest"])
            self.assertEqual(proof["schema"], "wakemu.scene-helper-score-owner.v1")
            self.assertEqual(
                proof["native_birth_digest"],
                canonical_digest(fight.native_npc_initialization_receipts[actor.id]),
            )
            self.assertFalse(hasattr(actor, "native_summon_source"))
            self.assertIsNone(helper_score_owner_receipt(fight, fight.actors[-200]))
            ready_source["players"][0]["account_id"] = 8
            self.assertIsNone(helper_score_owner_receipt(fight, actor))
            ready_source["players"][0]["account_id"] = char["account_id"]
            fight.native_npc_initialization_receipts[actor.id]["ref"] = 3516
            with self.assertRaisesRegex(ValueError, "genuine native NPC birth"):
                helper_score_owner_receipt(fight, actor)

    def test_helper_score_proof_rejects_enemy_current_controller(self):
        from wakfu_server.combat_encounter_scene_helpers import (
            helper_score_owner_receipt,
        )
        from wakfu_server.combat_controller_registry import transfer_native_controller

        fight, char, _members, manifest = self.controlled_fixture()
        actor = fight.actors[manifest["source"]["helpers"][0]["actor_id"]]
        admission = dict(
            status="granted",
            ready_participants=dict(
                source=dict(players=[dict(actor_id=char["id"], account_id=7)]),
                source_digest="a" * 64,
            ),
        )
        transfer_native_controller(fight, actor.id, -200)
        with patch(
            "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
            return_value=admission,
        ):
            self.assertIsNone(helper_score_owner_receipt(fight, actor))
        self.assertFalse(actor.controlled)
        self.assertIsNone(actor.owner_id)

    def test_foreign_source_or_mutated_constructor_cannot_publish_control(self):
        fight, _, _, manifest = self.fight()
        with self.assertRaisesRegex(ValueError, "another"):
            bind_scene_helper_controls(
                fight,
                source_policy=manifest["source"]["policy"],
                source_digest="0" * 64,
            )
        changed = deepcopy(manifest)
        changed["source"]["helpers"][0]["reference"] = 3516
        fight.native_scene_helper_manifest = changed
        with self.assertRaisesRegex(ValueError, "changed"):
            reward_eligible_members(fight, ())

    def test_friendly_helper_reconnect_keeps_exact_ordinary_source_team(self):
        from wakfu_server.combat_reconnect_world_actors import ordinary_npc_appearances

        fight, _char, members, manifest = self.fight()
        for row in manifest["source"]["helpers"]:
            source = next(
                member for member in members if member["id"] == row["actor_id"]
            )
            self.assertEqual((source["team"], fight.actors[source["id"]].team), (0, 0))
        shared = SimpleNamespace(
            map_id=1134,
            instance_id=0,
            join_context=dict(
                monsters={m["id"]: m for m in members}, group_key=(1134, 0, 1)
            ),
        )
        packets = ordinary_npc_appearances(fight, shared)
        self.assertEqual([opcode for opcode, _ in packets], [12608])
        tampered = deepcopy(shared)
        tampered.join_context["monsters"][members[-1]["id"]]["team"] = 1
        with self.assertRaisesRegex(ValueError, "identity"):
            ordinary_npc_appearances(fight, tampered)

    def test_native_controller_codec_rejects_duplicates_and_unknown_status(self):
        from dataclasses import replace

        row = NativeControllerRecord(-10, "IN_PLAY", 0, 0, False, -10, False, 100)
        self.assertEqual(len(controller_snapshot((row,))), 35)
        self.assertEqual(controller_snapshot(()), b"\x00\x00")
        for rows in (
            (row, row),
            (replace(row, status="made-up"),),
            (replace(row, is_summon=1),),
        ):
            with self.assertRaises(ValueError):
                controller_snapshot(rows)


if __name__ == "__main__":
    unittest.main()
