"""Shared native combat fixtures through the World SDK namespace."""
from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle


class NativeOracleTests:
    @classmethod
    def setUpClass(cls):
        # One warmup in this process; real cast cases share the immutable cache.
        from wakfu_server.combat_server_spell import prewarm_runtime_catalogs

        prewarm_runtime_catalogs()

    @staticmethod
    def wonejo_fixture(
        *,
        compact=False,
        terrain_effect_id=46,
        map_id=1134,
        player_position=(-8, -7, -1),
        monster_position=(-7, -7, -1),
        monster_ref=5525,
        monster_level=1,
    ):
        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.monsters import owned_instance

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        character = dict(fixture.character)
        character.update(
            map_id=map_id,
            instance_id=0,
            x=player_position[0],
            y=player_position[1],
            z=player_position[2],
            active_build_index=0,
        )
        monster = owned_instance(
            monster_ref,
            monster_level,
            fixture.npc.id,
            map_id=map_id,
            x=monster_position[0],
            y=monster_position[1],
            z=monster_position[2],
            instance_id=0,
        )
        # Preserve the adjacent casting fixture; the default live arena policy
        # may spread opponents to a different native cell.
        terrain = local_arena(
            map_id,
            77,
            player_position,
            monster_position,
            relocate_monsters=False,
            compact=compact,
        )
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=77,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=fixture.pc.initiative,
            terrain_effect_id=terrain_effect_id,
            terrain_instance_id=-300,
        )
        initialize_fight_snapshots(
            fight,
            characters={character["id"]: character},
            monsters={monster["id"]: monster},
            wp_resources={7: (6, 6), fixture.npc.id: (monster["wp"], monster["wp"])},
            running_effects={7: (), fixture.npc.id: ()},
            initial_effect_uid=1,
        )
        fight.ready(character["account_id"])
        fixture.character = character
        fixture.monster = monster
        fixture.fight = fight
        fixture.pc = fight.actors[character["id"]]
        fixture.npc = fight.actors[monster["id"]]
        return fixture

    @staticmethod
    def oracle_for(runtime, character, monster, deck, *, flags=None):
        return NativeOracle(
            runtime,
            characters={character["id"]: character},
            monsters={monster["id"]: monster},
            decks={character["id"]: deck},
            excluded_decks={character["id"]: frozenset()},
            viewer_id=character["id"],
            flags=flags or {},
        )
