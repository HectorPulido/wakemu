"""Rii lesson formations freeze and reload against native dojo geometry."""
from postgres_case import PostgresCase
from wakfu_server.achievements import rii_lesson_auto_start, rii_lesson_layout, storage
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_placement_policy import freeze
from wakfu_server.combat_terrain import published_geometry


class RiiLessonLayoutPostgresTests(PostgresCase):
    def test_owned_one_and_four_sack_layouts_freeze_and_reload_exact_markers(self):
        account = self.store.register("rii-layout-freeze", "test-password")["id"]
        character = self.store.create_character(account, "Layout Freeze")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        origin = (-1, -16, 0)
        destinations = {
            10574: ((0, -13, 0),),
            10575: ((0, -13, 0),),
            10576: ((0, -13, 0),),
            10608: ((0, -13, 0),),
            10610: ((0, -13, 0),),
            10611: ((0, -13, 0),),
            10609: ((1, -13, 0), (0, -14, 0), (0, -12, 0), (-1, -13, 0)),
        }
        geometry = published_geometry(1388)
        self.assertTrue(set(destinations[10609]) | {(0, -10, 0)} <= set(geometry.cells))
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1388,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (*origin, character["id"]),
            )
            state = storage.load_locked(db, character["id"])
            state["running"] = [5143]
            storage.store(db, character["id"], state)

        for case_index, objective in enumerate(
            (10574, 10575, 10576, 10608, 10610, 10611, 10609), start=1
        ):
            positions = geometry.outgoing[origin][: len(destinations[objective])]
            monsters = []
            prefix, kind = rii_lesson_auto_start.KEYS[objective]
            with self.store.connection() as db:
                for member_index, position in enumerate(positions):
                    actor_id = -(880000 + case_index * 10 + member_index)
                    monster = owned_instance(
                        5466,
                        1,
                        actor_id,
                        map_id=1388,
                        x=position[0],
                        y=position[1],
                        z=position[2],
                    )
                    monsters.append(monster)
                    self.assertTrue(
                        storage.record_event(
                            db,
                            character["id"],
                            prefix + str(-actor_id),
                            {
                                "kind": kind,
                                "owner": character["id"],
                                "actor_id": actor_id,
                                "ref": 5466,
                            },
                        )
                    )
                current = self.store.character(account, character["id"], db)
                self.assertEqual(
                    rii_lesson_layout.identify(db, current, monsters), objective
                )

            selected = rii_lesson_layout.arena(
                current,
                monsters,
                objective,
                cell_budget=2500,
                size_range=(7, 20),
            )
            fight_id = self._new_placement_fight(account, generation, character["id"])
            source_seeds = [
                tuple(member[key] for key in ("x", "y", "z")) for member in monsters
            ]
            first = freeze(
                self.store,
                account_id=account,
                generation=generation,
                character_id=character["id"],
                fight_id=fight_id,
                map_id=1388,
                instance_id=0,
                selected_arena=selected,
                seeds={0: [origin], 1: source_seeds},
            )
            expected_positions = list(zip(source_seeds, destinations[objective]))
            self.assertEqual(
                first["native_rii_lesson_layout"],
                {
                    "schema": rii_lesson_layout.SCHEMA,
                    "owner": character["id"],
                    "objective": objective,
                },
            )
            self.assertEqual(first["participant_positions"], expected_positions)
            self.assertEqual(
                first["participant_player_position"], (origin, rii_lesson_layout.PLAYER)
            )
            self.assertIn(rii_lesson_layout.PLAYER, first["placement_cells"][0])
            for cell in destinations[objective]:
                self.assertIn(cell, first["placement_cells"][1])

            reopened = self.reopen()
            current_after_reopen = reopened.character(account, character["id"])
            second = freeze(
                reopened,
                account_id=account,
                generation=generation,
                character_id=character["id"],
                fight_id=fight_id,
                map_id=1388,
                instance_id=0,
                selected_arena=selected,
                seeds={0: [origin], 1: source_seeds},
            )
            self.assertEqual(
                second["native_rii_lesson_layout"], first["native_rii_lesson_layout"]
            )
            self.assertEqual(
                [
                    tuple(tuple(cell) for cell in pair)
                    for pair in second["participant_positions"]
                ],
                [
                    tuple(tuple(cell) for cell in pair)
                    for pair in first["participant_positions"]
                ],
            )
            self.assertEqual(second["placement_cells"], first["placement_cells"])
            self.assertEqual(current_after_reopen["id"], character["id"])

    def _new_placement_fight(self, account, generation, character_id):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('placement') RETURNING id",
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (fight_id, character_id, account, generation),
            )
        return fight_id


if __name__ == "__main__":
    import unittest

    unittest.main()
