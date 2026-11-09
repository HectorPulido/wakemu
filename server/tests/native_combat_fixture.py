"""Owned synthetic placement producers for focused combat tests."""


class NativeOracleTests:
    """Shared minimal combat source for native bridge ownership regressions."""

    @classmethod
    def setUpClass(cls):
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
        from test_combat_npc_attack import NativeNpcAttackTests
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
            wp_resources={
                character["id"]: (6, 6),
                monster["id"]: (monster["wp"], monster["wp"]),
            },
            running_effects={character["id"]: (), monster["id"]: ()},
            initial_effect_uid=1,
        )
        fight.ready(character["account_id"])
        fixture.character, fixture.monster, fixture.fight = character, monster, fight
        fixture.pc, fixture.npc = (
            fight.actors[character["id"]],
            fight.actors[monster["id"]],
        )
        return fixture

    @staticmethod
    def oracle_for(runtime, character, monster, deck, *, flags=None):
        from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle

        return NativeOracle(
            runtime,
            characters={character["id"]: character},
            monsters={monster["id"]: monster},
            decks={character["id"]: deck},
            excluded_decks={character["id"]: frozenset()},
            viewer_id=character["id"],
            flags=flags or {},
        )


def initialize_fixture_qi(fight):
    """Own a flat synthetic arena and register actors before placement ends."""
    from wakfu_server.combat_qi_fight import (
        prepare_fresh_actor_slots,
        install_fresh_actor_slots,
    )
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )

    xs = [cell[0] for cell in fight.walkable]
    ys = [cell[1] for cell in fight.walkable]
    width, height = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    fight.native_qi_snapshot = dict(
        x=min(xs),
        y=min(ys),
        width=width,
        height=height,
        cell_masks=[0] * (width * height),
    )
    for slot, actor in enumerate(fight.actors.values()):
        actor.native_obstacle_id = slot
        actor.physical_radius = 0
    initialize_global_pv_collections(fight, tuple(fight.actors))
    install_fresh_actor_slots(
        fight,
        prepare_fresh_actor_slots(
            fight,
            physical_radii={
                identity: actor.physical_radius
                for identity, actor in fight.actors.items()
            },
        ),
    )
