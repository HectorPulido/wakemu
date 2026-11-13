"""Only the owned trace encounter receives the native allied Ruel actor."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from wakfu_server.combat_encounter_scene_helpers import (
    RUEL_POLICY,
    _ruel_scene,
    prepare_scene_roster,
    validated_manifest,
)


class RuelSceneTests(TestCase):
    def test_only_own_authenticated_trace_actor_spawns_ruel(self):
        character = dict(
            id=10, account_id=3, map_id=527, instance_id=0, x=-72, y=4, z=0
        )
        monster = dict(id=-321, ref=4689, level=15, x=-72, y=5, z=0)
        payload = dict(
            kind="reconstructed_ruel_phorreur_spawn_v1",
            actor_id=-321,
            reference=4689,
            owner=10,
        )

        class Database:
            def execute(self, sql, args):
                self.args = args
                return self

            def fetchone(self):
                return dict(payload=payload)

        db = Database()
        store = SimpleNamespace(connection=lambda: nullcontext(db))
        self.assertEqual(_ruel_scene(store, character, (monster,))[0], RUEL_POLICY)
        self.assertEqual(db.args, (10, "ruel-phorreur:321"))
        payload["owner"] = 11
        self.assertIsNone(_ruel_scene(store, character, (monster,)))
        payload["owner"] = 10
        with patch(
            "wakfu_server.combat_encounter_scene_helpers._cells",
            return_value=[(-72, 3, 0)],
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=1000
        ), patch(
            "wakfu_server.combat_encounter_roles.role_assignment",
            return_value=SimpleNamespace(policy="wakemu-ordinary-player0-npc1-v1"),
        ), patch(
            "wakfu_server.combat_supreme_scene_policies.policy_for_reference",
            return_value=None,
        ):
            members, manifest = prepare_scene_roster(store, character, (monster,))
        self.assertEqual([member["ref"] for member in members], [4689, 4690])
        self.assertEqual((members[1]["hp"], members[1]["sprite_id"]), (300, 192404573))
        helper = validated_manifest(manifest)["helpers"][0]
        self.assertEqual(
            (helper["team_role"], helper["controller_role"], helper["reward_eligible"]),
            ("player", "self", False),
        )

    def test_ruel_is_allied_npc_in_native_fight_constructor(self):
        from wakfu_server.combat_encounter_scene_helpers import (
            apply_helper_constructor_roles,
        )
        from wakfu_server.combat_quest_scene_authority import canonical_digest

        source = dict(
            schema="wakemu.initial-scene-npc-helpers.v1",
            policy=RUEL_POLICY,
            version=1,
            authority="explicit_source_backed_wakemu_reconstruction",
            principal_id=10,
            account_id=3,
            map_id=527,
            instance_id=0,
            originals=[dict(id=-321, reference=4689)],
            helpers=[
                dict(
                    actor_id=-322,
                    reference=4690,
                    level=15,
                    role="ruel",
                    team_role="player",
                    controller_role="self",
                    reward_eligible=False,
                )
            ],
        )
        manifest = dict(source=source, source_digest=canonical_digest(source))
        member = dict(id=-321, ref=4689, level=15)
        helper = dict(id=-322, ref=4690, level=15)
        actors = {
            -321: SimpleNamespace(),
            -322: SimpleNamespace(controlled=False, owner_id=None, team=1),
        }
        arena = dict(map_id=527, native_encounter_scene_helpers=manifest)
        result = apply_helper_constructor_roles(
            dict(id=10, account_id=3, map_id=527),
            (member, helper),
            actors,
            arena,
            fight_id=77,
            player_team=0,
            npc_team=1,
        )
        self.assertEqual(actors[-322].team, 0)
        self.assertEqual(result, manifest)

    def test_fight_bootstrap_with_actual_ruel_actor(self):
        from wakfu_server.combat_encounter_scene_helpers import prepare_scene_roster
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_wire import arena as native_arena
        from wakfu_server.progression import level_xp

        character = dict(
            id=100,
            account_id=7,
            breed=8,
            level=200,
            xp=level_xp(200),
            hp=60,
            map_id=527,
            x=0,
            y=0,
            z=0,
            instance_id=0,
            active_build_index=0,
            inventory_items=[],
            builds={},
        )
        from wakfu_server.health import maximum

        character["max_hp"] = maximum(character["breed"], character["level"])
        monster = owned_instance(4689, 15, -200, map_id=527, x=6, y=0, z=0)
        receipt = dict(
            kind="reconstructed_ruel_phorreur_spawn_v1",
            actor_id=-200,
            reference=4689,
            owner=character["id"],
        )
        db = SimpleNamespace(
            execute=lambda *args: SimpleNamespace(
                fetchone=lambda: dict(payload=receipt)
            )
        )
        store = SimpleNamespace(connection=lambda: nullcontext(db))
        with patch(
            "wakfu_server.combat_encounter_scene_helpers._cells",
            return_value=[(2, 0, 0)],
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=1000000
        ), patch(
            "wakfu_server.combat_encounter_roles.role_assignment",
            return_value=SimpleNamespace(policy="wakemu-ordinary-player0-npc1-v1"),
        ), patch(
            "wakfu_server.combat_supreme_scene_policies.policy_for_reference",
            return_value=None,
        ):
            members, manifest = prepare_scene_roster(store, character, (monster,))
        # Existing shared constructor test builds a third actor for its own case;
        # provide an equivalent two-actor validated arena directly here.
        from wakfu_server.combat_bootstrap import create_placement

        cells = {(x, y, 0) for x in range(7) for y in range(4)}
        placement = {
            0: {(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0)},
            1: {(6, 0, 0), (5, 1, 0)},
        }
        arena = native_arena(527, 0, sorted(cells), placement)
        arena.update(
            validated_cells=cells,
            valid_edges=set(),
            placement_cells=placement,
            native_encounter_scene_helpers=manifest,
            participant_positions=[
                [[m[k] for k in ("x", "y", "z")], list(cell)]
                for m, cell in zip(members, ((6, 0, 0), (1, 0, 0)))
            ],
        )
        fight, _ = create_placement(
            character,
            members,
            arena,
            fight_id=19,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=1,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )
        ruel = fight.actors[members[1]["id"]]
        self.assertEqual(ruel.team, 0)
        from wakfu_server.combat_effective_control import effective_server_controlled
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots

        initialize_fight_snapshots(
            fight,
            characters={character["id"]: character},
            monsters={m["id"]: m for m in members},
            wp_resources={
                character["id"]: (6, 6),
                **{m["id"]: (m["wp"], m["wp"]) for m in members},
            },
            running_effects={identity: () for identity in fight.actors},
            initial_effect_uid=1,
        )
        ruel = fight.actors[members[1]["id"]]
        fight.ready(character["account_id"])
        self.assertEqual(fight.current.id, members[0]["id"])
        fight.end_server_turn(fight.current.id, fight.turn_id)
        self.assertEqual(fight.current.id, ruel.id)
        from wakfu_server.combat_automatic_npc_turn import (
            requires_automatic_npc_turn_end,
        )

        self.assertFalse(effective_server_controlled(fight, ruel))
        self.assertTrue(requires_automatic_npc_turn_end(fight, ruel))
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        runtime = RuntimeMessages(fight)
        # A root without a tactical AI may have native SKIP_TURN.  It must
        # still finish through its attested end-only authority on turn start.
        ruel.native_fight_property_counts = {**ruel.native_fight_property_counts, 1: 1}
        packets = runtime.turn_started()
        self.assertTrue(packets)
        self.assertIsNotNone(runtime.awaiting_ack)
        import struct

        runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
        self.assertEqual(fight.current.id, character["id"])
