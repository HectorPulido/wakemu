import struct
import unittest
from copy import deepcopy

from wakfu_server.guild_haven_world import project_character
from wakfu_server.combat_actor import actual_monster_actor_stats
from wakfu_server.combat_haven_world_context import (
    bind_placement,
    placement_context,
    validate_placement,
)
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_wire import arena
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.monsters import owned_instance


class _BindingDB:
    def __init__(self, guild_id):
        self.guild_id = guild_id

    def execute(self, _query, _params):
        row = {"guild_id": self.guild_id, "native_world_id": -self.guild_id}
        return type("Result", (), {"fetchone": staticmethod(lambda: row)})()


class CombatHavenWorldContextTests(unittest.TestCase):
    def _placement(self, *, map_id=1134, instance_id=760008, guild_id=8):
        character = dict(
            id=100,
            account_id=1,
            breed=8,
            level=1,
            xp=0,
            hp=60,
            max_hp=60,
            map_id=map_id,
            x=0,
            y=0,
            z=0,
            instance_id=instance_id,
            builds={},
            inventory_items=[],
            active_build_index=0,
        )
        character = project_character(_BindingDB(guild_id), character)
        member = owned_instance(
            5525,
            1,
            -200,
            map_id=map_id,
            instance_id=instance_id,
            x=1,
            y=0,
            z=0,
        )
        cells = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
        terrain = arena(map_id, 1, cells, {0: cells[0], 1: cells[1]})
        terrain.update(
            validated_cells=cells,
            valid_edges={(cells[0], cells[1]), (cells[1], cells[0])},
        )
        fight, messages = create_placement(
            character,
            [member],
            terrain,
            fight_id=7,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )
        return character, member, fight, messages

    def test_private_world_identity_reaches_initial_and_live_npc_stats(self):
        character, member, fight, messages = self._placement()
        self.assertTrue(messages)
        self.assertEqual(member["map_id"], 1134)
        self.assertNotIn("native_world_id", member)
        actor = fight.actors[member["id"]]
        context = fight.native_haven_world_combat_context
        self.assertIs(actor.native_haven_world_combat_context, context)
        self.assertEqual(context.owner_character_id, character["id"])
        self.assertEqual(context.native_world_id, -8)

        # NPC eHj format2 has the POSITION world ID immediately after x/y/z.
        initial = next(payload for opcode, payload in messages if opcode == 12847)
        marker = struct.pack(">q", member["id"])
        self.assertIn(marker, initial)
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots

        initialize_fight_snapshots(
            fight,
            characters={character["id"]: character},
            monsters={member["id"]: member},
            wp_resources={
                character["id"]: (6, 6),
                member["id"]: (member["wp"], member.get("max_wp", member["wp"])),
            },
            running_effects={character["id"]: (), member["id"]: ()},
            initial_effect_uid=1,
        )
        self.assertIs(type(actor.native_controlled_by_ai), bool)
        live = actual_monster_actor_stats(
            member,
            actor,
            fight.id,
            wp_current=member["wp"],
            wp_maximum=member.get("max_wp", member["wp"]),
            fight=fight,
        )
        self.assertEqual(struct.unpack_from(">q", live, 11)[0], -8)

    def test_ordinary_actor_authority_uses_bound_private_world_arM(self):
        character, member, fight, _messages = self._placement()
        source = dict(member)
        authority = OrdinaryActorAuthority(
            characters={character["id"]: character},
            monsters={member["id"]: source},
            decks={character["id"]: []},
            excluded_decks={character["id"]: []},
        )
        npc = authority(fight, fight.actors[member["id"]])
        self.assertEqual(npc.native_instance_id, -8)

    def test_snapshot_boundary_rejects_scope_or_source_rebinding(self):
        character, member, fight, _messages = self._placement()
        validate_placement(fight, {character["id"]: character}, {member["id"]: member})
        wrong = dict(member, instance_id=member["instance_id"] + 1)
        with self.assertRaisesRegex(ValueError, "verified combat scope"):
            validate_placement(
                fight, {character["id"]: character}, {member["id"]: wrong}
            )

        detached = deepcopy(fight)
        detached.native_haven_world_combat_context = None
        with self.assertRaisesRegex(ValueError, "lacks combat NPC identity"):
            validate_placement(
                detached, {character["id"]: character}, {member["id"]: member}
            )

    def test_forged_or_cross_scope_private_identity_is_rejected(self):
        character, member, _fight, _messages = self._placement()
        forged = dict(character, native_world_id=-999)
        with self.assertRaisesRegex(ValueError, "Unverified private"):
            placement_context(forged, [member], fight_id=7)
        wrong_member = dict(member, instance_id=member["instance_id"] + 1)
        with self.assertRaisesRegex(ValueError, "roster differs"):
            placement_context(character, [wrong_member], fight_id=7)


if __name__ == "__main__":
    unittest.main()
