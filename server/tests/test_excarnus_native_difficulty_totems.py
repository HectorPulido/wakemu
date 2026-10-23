"""Own selected Stasis publication drives Excarnus' actual totem producers."""
from io import BytesIO
import json
import random
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class ExcarnusNativeDifficultyTotemTests(PostgresCase):
    def test_owned_selected_five_and_eight_publish_and_produce_both_native_totems(self):
        from wakfu_server import (
            native_catalog,
            dungeon_instances,
            dungeon_difficulty,
            dungeon_context,
            dungeon_runtime_config,
            dungeon_transport,
            generic_transports,
            player_parties,
            health_store,
            fight_store,
        )
        from wakfu_server.combat_geometry import prepare_geometry
        from wakfu_server.paths import DATA_ROOT
        from native_paid_party_fixture import (
            NativePartyBuild,
            persisted_party_character,
        )
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_environment_glyphs import prepare_environment_glyphs
        from wakfu_server.combat_instance_publication import (
            InstancePublicationTracker,
            bind_party_encounter,
        )
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_qi_fight import current_registry

        # Copy the real published route/policy into only this disposable schema.
        with native_catalog._database().connection() as source:
            config = source.execute(
                "SELECT c.configuration FROM dungeon_runtime_configurations c "
                "JOIN dungeon_runtime_active_configurations a USING(route_key,policy_version) "
                "WHERE c.route_key='native_dungeon_4'"
            ).fetchone()["configuration"]
            native = source.execute(
                "SELECT value->'definitions'->'4' AS definition FROM settings "
                "WHERE name='dungeon_difficulty_catalog'"
            ).fetchone()["definition"]
        self.assertTrue(native["difficulty_available"])
        self.assertEqual(config["route"]["definition_id"], 4)
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, config)
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_difficulty_catalog',%s::jsonb) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(definitions={"4": native})),),
            )
        routes = dungeon_instances._load_routes([config["route"]])
        source = generic_transports.source(711, 20704)
        approach = source["approach_positions"][0]
        initial_position = tuple(approach[k] for k in ("x", "y", "z"))
        board = frozenset(map(tuple, config["topology"]["rooms"][0]["cells"]))
        geometry = prepare_geometry(
            native_catalog.load(DATA_ROOT / "combat-maps/360.json")
        )
        self.assertLessEqual(board, geometry.cells)
        bosses = [
            cell
            for cell in board
            if all(
                (cell[0] + dx, cell[1] + dy, cell[2]) in board
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
            )
        ]
        boss_cell = min(bosses, key=lambda c: (abs(c[0]) + abs(c[1]) + abs(c[2]), c))
        candidates = sorted(
            (
                cell
                for cell in board
                if cell[2] == boss_cell[2]
                and 6 <= abs(cell[0] - boss_cell[0]) + abs(cell[1] - boss_cell[1]) <= 8
            ),
            key=lambda c: (abs(c[0] - boss_cell[0]) + abs(c[1] - boss_cell[1]), c),
        )
        first = candidates[0]
        second = min(
            (c for c in candidates if c != first),
            key=lambda c: (abs(c[0] - first[0]) + abs(c[1] - first[1]), c),
        )
        positions = (first, second)

        with patch.object(
            dungeon_instances, "_ROUTES", {**dungeon_instances._ROUTES, **routes}
        ):
            for difficulty in (5, 8):
                with self.subTest(difficulty=difficulty):
                    owners = []
                    for index in range(2):
                        build = NativePartyBuild(8, 80, (4780,), ())
                        (
                            char,
                            generation,
                            deck,
                            resources,
                            gear,
                        ) = persisted_party_character(
                            self.store,
                            build,
                            name="excarnus-"
                            + ("five" if difficulty == 5 else "eight")
                            + "-"
                            + chr(97 + index),
                            map_id=711,
                            position=initial_position,
                        )
                        owners.append((char, generation, deck))
                    leader, generation, _ = owners[0]
                    partner = owners[1][0]
                    invitation = player_parties.invite(
                        self.store,
                        leader["account_id"],
                        generation,
                        leader["id"],
                        partner["id"],
                    )
                    player_parties.answer(
                        self.store,
                        partner["account_id"],
                        owners[1][1],
                        partner["id"],
                        invitation,
                        True,
                    )
                    entered = dungeon_transport.enter(
                        self.store,
                        leader["account_id"],
                        generation,
                        leader["id"],
                        711,
                        struct.pack(">qiBi", 20704, 878, 0, 2),
                        criterion_allowed=lambda character, criterion: criterion == "",
                        source_allowed=lambda character, selected: character["map_id"]
                        == selected["map_id"]
                        and any(
                            tuple(character[k] for k in ("x", "y", "z"))
                            == tuple(position[k] for k in ("x", "y", "z"))
                            for position in selected["approach_positions"]
                        ),
                    )
                    instance = entered["instance_id"]
                    selected = dungeon_difficulty.select(
                        self.store,
                        leader["account_id"],
                        generation,
                        leader["id"],
                        stasis_level=difficulty,
                        competitive=True,
                        expected_instance_id=instance,
                    )
                    self.assertEqual(selected["stasis_level"], difficulty)
                    self.assertEqual(selected["competitive_max_level"], 80)
                    characters, decks, generations, resources = {}, {}, {}, {}
                    for (char, gen, deck), position in zip(owners, positions):
                        with self.store.connection() as db:
                            db.execute(
                                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                                (*position, char["id"]),
                            )
                        char = health_store.initialize(
                            self.store, char["account_id"], gen, char["id"]
                        )
                        self.assertEqual(
                            (char["map_id"], char["instance_id"]), (360, instance)
                        )
                        characters[char["id"]], decks[char["id"]] = char, deck
                        generations[char["id"]] = gen
                        resources[char["id"]] = combat_resources(char)
                    leader = characters[leader["id"]]
                    fight_id = fight_store.create(
                        self.store, leader["account_id"], generation, leader["id"]
                    )
                    monster = owned_instance(
                        1986,
                        80,
                        -200,
                        map_id=360,
                        instance_id=instance,
                        x=boss_cell[0],
                        y=boss_cell[1],
                        z=boss_cell[2],
                    )
                    arena = local_arena(
                        360,
                        instance,
                        positions[0],
                        boss_cell,
                        compact=False,
                        relocate_monsters=False,
                        allowed_cells=board,
                    )
                    actors = [
                        Actor(
                            identity,
                            0,
                            tuple(char[k] for k in ("x", "y", "z")),
                            char["hp"],
                            resources[identity]["ap"],
                            resources[identity]["mp"],
                            resources[identity]["initiative"],
                            char["level"],
                            char["account_id"],
                            True,
                            max_hp=char["max_hp"],
                        )
                        for identity, char in characters.items()
                    ]
                    actors.append(
                        Actor(
                            -200,
                            1,
                            boss_cell,
                            monster["hp"],
                            monster["ap"],
                            monster["mp"],
                            monster["initiative"],
                            80,
                            max_hp=monster["max_hp"],
                        )
                    )
                    fight = Fight(
                        fight_id,
                        actors,
                        arena["validated_cells"],
                        {0: set(positions), 1: {boss_cell}},
                        arena["valid_edges"],
                    )
                    initialize_global_pv_collections(
                        fight, tuple(fight.actors), controller_registration=True
                    )
                    fight.native_qi_snapshot = {
                        k: arena[k] for k in ("x", "y", "width", "height", "cell_masks")
                    }
                    fight.native_qi_surface_provenance = dict(
                        arena["native_qi_surface_provenance"]
                    )
                    freeze_terrain(fight)
                    if arena.get("native_border_policy") is not None:
                        fight.native_border_constructor = dict(
                            reference=46,
                            identity=9001,
                            arena={
                                k: arena[k]
                                for k in (
                                    "native_border_policy",
                                    "native_border_cells",
                                    "min_z",
                                )
                            },
                        )
                    prepare_environment_glyphs(fight, arena, 9001)
                    opcode, body = dungeon_context.update_packet(
                        self.store, instance, fight_in_progress=False
                    )
                    trackers = []
                    for identity, char in characters.items():
                        tracker = InstancePublicationTracker()
                        scope = (
                            char["account_id"],
                            generations[identity],
                            identity,
                            char["map_id"],
                            instance,
                        )
                        frame = struct.pack(">IH", 6 + len(body), opcode) + body
                        transport = BytesIO()
                        self.assertEqual(transport.write(frame), len(frame))
                        tracker.after_write(transport.getvalue(), scope)
                        trackers.append((tracker, scope))
                    self.assertTrue(
                        bind_party_encounter(
                            fight, publications=tuple(trackers), npc_ids=(-200,)
                        )
                    )
                    initialize_fight_snapshots(
                        fight,
                        characters=characters,
                        monsters={-200: monster},
                        wp_resources={
                            **{i: (v["wp"], v["wp"]) for i, v in resources.items()},
                            -200: (monster["wp"], monster["wp"]),
                        },
                        running_effects={i: () for i in fight.actors},
                        initial_effect_uid=1,
                    )
                    for char in characters.values():
                        fight.ready(char["account_id"])
                    rng = random.Random(7)
                    for number, char in enumerate(characters.values(), 1):
                        fight, _ = prepare_server_initialization(
                            char,
                            {-200: monster},
                            fight,
                            char["account_id"],
                            decks[char["id"]],
                            action_id=number,
                            rng=rng,
                            fight_start=number == len(characters),
                            player_characters=characters,
                            deck_blobs=decks,
                        )
                    self.assertEqual(
                        fight.native_instance_difficulty_snapshots[-200].difficulty,
                        difficulty,
                    )
                    calls = []
                    execute = EffectDispatcher.execute

                    def observe(dispatcher, invocation, *args, **kwargs):
                        if invocation.reference in (333623, 333625, 333694, 333696):
                            calls.append(invocation.reference)
                        return execute(dispatcher, invocation, *args, **kwargs)

                    common = dict(
                        player_characters=characters, deck_blobs=decks, rng=rng
                    )
                    runtime = RuntimeMessages(
                        fight,
                        turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                            leader,
                            {-200: monster},
                            p,
                            decks[leader["id"]],
                            **common,
                            **kw
                        ),
                        turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                            leader,
                            {-200: monster},
                            p,
                            decks[leader["id"]],
                            **common,
                            **kw
                        ),
                        expiration_runtime_factory=lambda *, action_id: server_runtime(
                            leader,
                            {-200: monster},
                            decks[leader["id"]],
                            action_id=action_id,
                            critical=False,
                            **common
                        )[0],
                    )
                    self.assertEqual(runtime.fight.current.id, -200)
                    with patch.object(EffectDispatcher, "execute", observe):
                        runtime.turn_started(arm_deadline=False)
                    summons = [
                        a
                        for a in runtime.fight.actors.values()
                        if (getattr(a, "native_summon_source", None) or {}).get(
                            "caster_id"
                        )
                        == -200
                    ]
                    self.assertEqual(
                        {a.native_summon_source["ref"] for a in summons} & {5359, 5360},
                        {5359, 5360},
                    )
                    self.assertLessEqual(
                        {333694, 333696} if difficulty == 5 else {333623, 333625},
                        set(calls),
                    )
                    for summoned in summons:
                        self.assertIn(
                            summoned.id, runtime.fight.native_summon_registrations
                        )
                        self.assertIn(summoned.position, board)
                    current_registry(runtime.fight)
