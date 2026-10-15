"""Private company publication keeps host isolation and exterior return custody."""
import ast
import copy
import unittest
from pathlib import Path

from wakfu_server.characters import hero_private_scene
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession, destination


def actor(identity=41, account=7, owner=41):
    return dict(
        id=identity,
        account_id=account,
        map_id=527,
        instance_id=0,
        x=12,
        y=15,
        z=0,
        haven_bag={"owner_id": owner, "rooms": []},
        inventory_items=[{"uid": identity * 10}],
        builds={"active": 0},
    )


class HeroPrivateSceneTests(unittest.TestCase):
    def scene(self, *, ranch=False, visitor=False):
        main = actor()
        host = actor(92, 9, 92) if visitor else None
        bag = HavenBagSession(main, owner=host)
        scene = bag
        if ranch:
            scene = RanchSession(
                bag, bag.inside, destination(35), lease="lease", now_ms=1
            )
        live = scene.move(scene.inside, dict(x=8, y=9, z=4 if ranch else 0))
        return main, bag, scene, live

    def test_add_remove_projection_in_owned_and_visited_bag_and_ranch(self):
        for ranch in (False, True):
            for visitor in (False, True):
                with self.subTest(ranch=ranch, visitor=visitor):
                    main, bag, session, live = self.scene(ranch=ranch, visitor=visitor)
                    hero = actor(42)
                    roster = dict(leader=main, heroes=(hero,), revision=2)
                    before = copy.deepcopy(roster)
                    result = hero_private_scene.project(roster, session, live, "lease")
                    for projected in (result["leader"], *result["heroes"]):
                        self.assertEqual(
                            tuple(
                                live[key] for key in hero_private_scene.LOCATION_KEYS
                            ),
                            tuple(
                                projected[key]
                                for key in hero_private_scene.LOCATION_KEYS
                            ),
                        )
                        self.assertEqual(visitor, projected["haven_bag_visitor"])
                        self.assertEqual(
                            92 if visitor else 41, projected["instance_id"]
                        )
                    self.assertEqual(
                        hero["inventory_items"], result["heroes"][0]["inventory_items"]
                    )
                    self.assertEqual(before, roster)
                    self.assertEqual(main, bag.outside)
                    removed = hero_private_scene.project(
                        dict(roster, heroes=()), session, live, "lease"
                    )
                    self.assertEqual((), removed["heroes"])
                    self.assertTrue(session.owns(live))
                    self.assertEqual(not visitor, bag.is_owner)

    def test_switch_then_add_keeps_same_host_and_original_exterior(self):
        for visitor in (False, True):
            with self.subTest(visitor=visitor):
                main, bag, session, live = self.scene(ranch=True, visitor=visitor)
                selected = actor(42)
                selected_live = session.rebind(live, selected)
                result = hero_private_scene.project(
                    dict(leader=selected, heroes=(main, actor(43))),
                    session,
                    selected_live,
                    "lease",
                )
                self.assertTrue(session.owns(selected_live))
                self.assertEqual(
                    {live["instance_id"]}, {h["instance_id"] for h in result["heroes"]}
                )
                self.assertEqual(selected["map_id"], bag.outside["map_id"])
                self.assertEqual(527, bag.outside["map_id"])
                self.assertEqual(not visitor, bag.is_owner)

    def test_other_account_cannot_be_projected_into_company(self):
        main, _, session, live = self.scene(ranch=True, visitor=True)
        with self.assertRaisesRegex(ValueError, "another account"):
            hero_private_scene.project(
                dict(leader=main, heroes=(actor(92, 9, 92),)), session, live, "lease"
            )
        with self.assertRaisesRegex(ValueError, "current private scene"):
            hero_private_scene.authorize(session, dict(live, instance_id=41), "lease")
        with self.assertRaisesRegex(ValueError, "Expired"):
            hero_private_scene.authorize(session, live, "old-lease")

    def test_public_roster_is_not_relocated(self):
        roster = dict(leader=actor(), heroes=(actor(42),))
        self.assertIs(
            roster, hero_private_scene.project(roster, None, actor(), "lease")
        )

    def test_production_publication_activates_private_positions(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "publish_heroes"
        )
        module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        main, _, session, live = self.scene(ranch=True, visitor=True)
        from unittest.mock import patch
        from wakfu_server.characters import hero_wire

        activated = []
        namespace = dict(
            active_private_session=lambda: session,
            character=live,
            generation="lease",
            account_id=7,
            connection=None,
            service="world",
            OWNED_HERO_TEMPLATE=b"",
            send=lambda *args: None,
            refresh_party=lambda *args: None,
        )
        with patch.object(
            hero_wire,
            "activate",
            side_effect=lambda template, char: activated.append(char) or (1, b""),
        ), patch.object(hero_wire, "statistics", return_value=(2, b"")), patch.object(
            hero_wire, "company", return_value=(3, b"")
        ):
            exec(compile(module, "production-publish", "exec"), namespace)
            namespace["publish_heroes"](dict(leader=main, heroes=(actor(42),)))
        self.assertEqual(
            (1440, 92, 8, 9, 4),
            tuple(activated[0][k] for k in hero_private_scene.LOCATION_KEYS),
        )
        self.assertEqual(7, activated[0]["account_id"])


if __name__ == "__main__":
    unittest.main()
