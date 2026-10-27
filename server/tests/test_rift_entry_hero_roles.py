"""Durable World entry roles and public placement/owned-hero admission."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest

from postgres_case import PostgresCase
from wakfu_server import fight_store
from wakfu_server.characters import heroes
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_heroes import admit_owned_heroes
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_encounter_roles import assigned_roles
from wakfu_server.rift_encounter_roles import roles_for_catalog
from wakfu_server.rift_native_gameplay_policy import load as native_policy
from wakfu_server.combat_terrain import local_arena
from wakfu_server.monsters import owned_instance
from wakfu_server.equipment_stats import combat_resources


def world_create_entry(*, legacy=False):
    """Compile the actual World call and its role validation, not a copied fix."""
    path = Path("server/local_game_server.py")
    tree = ast.parse(path.read_text())
    body = None
    for parent in ast.walk(tree):
        candidate = getattr(parent, "body", None)
        if not isinstance(candidate, list):
            continue
        for index, node in enumerate(candidate):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "create_fight_identity"
            ):
                body = deepcopy(candidate[index - 3 : index + 1])
                break
        if body is not None:
            break
    if body is None or not isinstance(body[0], ast.ImportFrom):
        raise AssertionError("World entry role validation/call boundary changed")
    call = body[-1].value
    if legacy:
        call.keywords = [item for item in call.keywords if item.arg != "team"]
    elif not any(item.arg == "team" for item in call.keywords):
        raise AssertionError("World does not pass the authenticated player team")
    arguments = [
        "STORE",
        "account_id",
        "generation",
        "character",
        "arena",
        "TEST_MONSTERS",
        "capture_entry_boundary",
    ]
    function = ast.FunctionDef(
        name="entry",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=name) for name in arguments],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=body + [ast.Return(ast.Name("durable_fight_id", ast.Load()))],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {"create_fight_identity": fight_store.create}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace["entry"]


class RiftEntryHeroRoleTests(PostgresCase):
    def test_world_durable_roles_public_placement_and_owned_hero_admission(self):
        fixed, previous = world_create_entry(), world_create_entry(legacy=True)
        for label, kind, with_hero in (
            ("classic", "INFINITE_WAVE", True),
            ("ultimate", "ULTIMATE_INFINITE_WAVE", True),
            ("ordinary", None, False),
        ):
            with self.subTest(kind=label):
                account = self.store.register("entry-" + label, "entry-password")["id"]
                main = self.store.create_character(account, "Entry" + label + "main")
                hero = self.store.create_character(account, "Entry" + label + "hero")
                generation = self.store.begin_session(account)
                self.store.select_character(account, generation, main["id"])
                if with_hero:
                    heroes.add(self.store, account, generation, main["id"], hero["id"])
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET map_id=1314,instance_id=0,x=0,y=0,z=0 WHERE id=ANY(%s)",
                        ([main["id"], hero["id"]],),
                    )
                    policy = db.execute(
                        "SELECT value FROM settings WHERE name='rift_policy'"
                    ).fetchone()["value"]
                    policy["native_gameplay"] = native_policy(db)
                main = self.store.character(account, main["id"])
                monster = owned_instance(
                    3, 14, -200, map_id=1314, instance_id=0, x=3, y=0, z=0, team=1
                )
                arena = local_arena(
                    1314,
                    0,
                    (0, 0, 0),
                    [(3, 0, 0)],
                    compact=False,
                    relocate_monsters=False,
                )
                if kind:
                    roles = roles_for_catalog(
                        dict(type=kind, map_id=1314, wave_id=3, species_refs=[3]),
                        policy,
                        monster_references=(3,),
                    )
                    arena["native_encounter_roles"] = roles.record()
                else:
                    roles = assigned_roles(None)
                player_team = 1 if kind else 0
                self.assertEqual(roles.player_team, player_team)
                placements = roles.placement_cells(
                    set(arena["validated_cells"]) - {(3, 0, 0)}, {(3, 0, 0)}
                )
                session = Session(account, main["id"], generation, 1314, 0)
                resources = combat_resources(main)

                def placement(identity):
                    candidate = create_placement(
                        main,
                        [monster],
                        arena,
                        fight_id=identity,
                        player_ap=resources["ap"],
                        player_mp=resources["mp"],
                        player_wp=resources["wp"],
                        player_initiative=resources["initiative"],
                        terrain_effect_id=46,
                        terrain_instance_id=999,
                        placement_cells=placements,
                    )[0]

                    from wakfu_server.combat_actor_snapshot import (
                        initialize_fight_snapshots,
                    )

                    initialize_fight_snapshots(
                        candidate,
                        characters={main["id"]: main},
                        monsters={-200: monster},
                        wp_resources={
                            main["id"]: (resources["wp"], resources["wp"]),
                            -200: (monster["wp"], monster.get("max_wp", monster["wp"])),
                        },
                        running_effects={uid: () for uid in candidate.actors},
                        initial_effect_uid=1,
                    )
                    return candidate

                if kind == "INFINITE_WAVE":
                    old_id = previous(
                        self.store, account, generation, main, arena, [monster], None
                    )
                    old_fight = placement(old_id)
                    self.assertEqual(old_fight.actors[main["id"]].team, 1)
                    with self.store.connection() as db:
                        with self.assertRaisesRegex(ValueError, "actual owning main"):
                            admit_owned_heroes(db, self.store, session, old_fight)
                        count = db.execute(
                            "SELECT count(*) AS n FROM combat_fight_participants WHERE fight_id=%s",
                            (old_id,),
                        ).fetchone()["n"]
                        self.assertEqual(count, 1)
                        # Close only the declared historical failed placement in
                        # this disposable schema; no live fight is touched.
                        db.execute(
                            "UPDATE combat_fights SET status='aborted' WHERE id=%s",
                            (old_id,),
                        )

                identity = fixed(
                    self.store, account, generation, main, arena, [monster], None
                )
                fight = placement(identity)
                with self.store.connection() as db:
                    durable = db.execute(
                        "SELECT team FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
                        (identity, main["id"]),
                    ).fetchone()
                    self.assertEqual(durable["team"], fight.actors[main["id"]].team)
                    self.assertEqual(durable["team"], player_team)
                    wrong = deepcopy(fight)
                    wrong.actors[main["id"]].team = 1 - player_team
                    with self.assertRaisesRegex(ValueError, "actual owning main"):
                        admit_owned_heroes(db, self.store, session, wrong)
                    wrong = deepcopy(fight)
                    wrong.actors[main["id"]].owner_id = account + 10000
                    with self.assertRaisesRegex(ValueError, "actual owning main"):
                        admit_owned_heroes(db, self.store, session, wrong)
                    result = admit_owned_heroes(db, self.store, session, fight)
                    expected = {hero["id"]} if with_hero else set()
                    self.assertEqual(set(result["characters"]), expected)
                    rows = db.execute(
                        "SELECT character_id,team,session_generation FROM combat_fight_participants WHERE fight_id=%s",
                        (identity,),
                    ).fetchall()
                    self.assertEqual(
                        {row["character_id"] for row in rows}, {main["id"]} | expected
                    )
                    self.assertTrue(
                        all(
                            row["team"] == player_team
                            and row["session_generation"] == generation
                            for row in rows
                        )
                    )
                current = result["fight"]
                registry = Registry(
                    lambda supplied: self.store.current_character_session(
                        supplied.account_id, supplied.generation, supplied.character_id
                    )
                )
                shared = registry.register(
                    current, session, runtime=RuntimeMessages(current)
                )
                self.assertIs(shared.fight, current)
                self.assertTrue(
                    all(
                        current.actors[uid].team == player_team
                        for uid in {main["id"]} | expected
                    )
                )
                self.assertTrue({main["id"]} | expected <= set(registry.by_character))
                with self.assertRaisesRegex(ValueError, "already registered"):
                    registry.register(current, session)
