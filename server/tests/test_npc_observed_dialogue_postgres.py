"""Actual SQL scene/facts gate for captured read-only continuation paths."""
import struct
from postgres_case import PostgresCase
from wakfu_server.maps import npc_objective_facts, npc_world


class ObservedDialoguePostgresTests(PostgresCase):
    def test_current_sql_scenes_follow_captured_edges_without_mutating_owned_domains(
        self,
    ):
        account = self.store.register("observed-dialogue-owner", "test-password")["id"]
        character = self.store.create_character(account, "Observed Dialogue")

        def snapshot():
            with self.store.connection() as db:
                return {
                    "character": db.execute(
                        "SELECT row_to_json(c) AS row FROM characters c WHERE id=%s",
                        (character["id"],),
                    ).fetchone(),
                    "progression": db.execute(
                        "SELECT * FROM character_progression WHERE character_id=%s",
                        (character["id"],),
                    ).fetchall(),
                    "wallet": db.execute(
                        "SELECT * FROM account_wallets WHERE account_id=%s", (account,)
                    ).fetchall(),
                    "facts": npc_objective_facts.load(db, account, character["id"]),
                    "items": db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    ).fetchall(),
                }

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=6 WHERE id=%s", (character["id"],))
        character["level"] = 6
        before = snapshot()
        specs = [
            (
                1385,
                5461,
                [
                    (5765, 13275, 5766),
                    (5766, 13278, 5767),
                    (5767, 13280, 5768),
                    (5768, 13281, 5769),
                    (5769, 13282, 5783),
                    (5783, 13306, 5770),
                    (5770, 13283, 0),
                ],
            ),
            (1385, 5459, [(5772, 13288, 5773), (5773, 13289, 5774), (5774, 13290, 0)]),
            (1385, 5467, [(5782, 13305, 5786), (5786, 13318, 0)]),
            (1388, 5460, [(5755, 13258, 5756), (5756, 13260, 0)]),
            (1387, 5458, [(5764, 13343, 5790), (5790, 13345, 5791), (5791, 13347, 0)]),
        ]
        for world, reference, edges in specs:
            with self.store.connection() as db:
                row = next(
                    row
                    for row in npc_world.load_scene(db, world, 0)
                    if row["reference_id"] == reference
                )
            current = dict(
                character,
                **{key: row[key] for key in ("map_id", "instance_id", "x", "y", "z")}
            )

            def scene():
                with self.store.connection() as db:
                    return npc_world.load_scene(db, world, 0)

            def facts():
                with self.store.connection() as db:
                    return npc_objective_facts.load(db, account, character["id"])

            session, _ = npc_world.begin(
                lambda: current,
                scene,
                row["actor_id"],
                row["action_ids"][0],
                facts_provider=facts,
            )
            for node, choice, target in edges:
                self.assertEqual(
                    session.choose(node, choice), (12218, struct.pack(">i", target))
                )
            self.assertIsNone(session.node_id)
        self.assertEqual(snapshot(), before)
