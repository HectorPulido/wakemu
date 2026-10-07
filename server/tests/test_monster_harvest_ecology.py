from postgres_case import PostgresCase
from wakfu_server.ecology_feedback import information
from wakfu_server.monster_harvest_ecology import change


class MonsterHarvestEcologyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("monster-harvest-ecology", "test-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Harvest Ecology")
        self.monster = {
            "id": -7001,
            "ref": 1,
            "map_id": 1134,
            "instance_id": 23,
            "x": 10,
            "y": 20,
            "z": 3,
        }

    def locate(self, map_id, x, y, z):
        self.assertEqual((map_id, x, y, z), (1134, 10, 20, 3))
        return {"region_id": 79001}

    def test_extraction_is_neutral_receipted_and_replay_is_silent(self):
        expected = information(
            "Ecosistema: población 0 → 0; rango de equilibrio 1–128. "
            "Tu acción no reduce el desequilibrio: sin cambio de afinidad. "
            "Afinidad: Neutral → Neutral."
        )
        with self.store.connection() as db:
            first = change(
                db,
                self.character["id"],
                self.monster,
                operation="monster-harvest:direct-test",
                locate=self.locate,
            )
        self.assertEqual(first, [expected])
        with self.store.connection() as db:
            replay = change(
                db,
                self.character["id"],
                self.monster,
                operation="monster-harvest:direct-test",
                locate=self.locate,
            )
        self.assertEqual(replay, [])
        with self.store.connection() as db:
            state = db.execute(
                "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                (self.character["id"],),
            ).fetchone()
            receipt = db.execute(
                "SELECT requested_delta,evidence FROM personal_ecology_receipts "
                "WHERE character_id=%s AND operation='monster-harvest:direct-test'",
                (self.character["id"],),
            ).fetchone()
        self.assertEqual((state["ecology_value"], state["ecology_revision"]), (0, 1))
        self.assertEqual(receipt["requested_delta"], 0)
        self.assertEqual(receipt["evidence"]["action"], "harvest")

    def test_unknown_surface_explains_without_inventing_a_population_receipt(self):
        def unknown(*_):
            raise ValueError("unknown native surface")

        with self.store.connection() as db:
            packets = change(
                db,
                self.character["id"],
                self.monster,
                operation="monster-harvest:unknown-surface",
                locate=unknown,
            )
            receipts = db.execute(
                "SELECT count(*) AS n FROM personal_ecology_receipts WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["n"]
        self.assertEqual(
            packets,
            [
                information(
                    "Ecosistema: extraer este producto no elimina al monstruo "
                    "ni cambia tu afinidad. Población regional no disponible."
                )
            ],
        )
        self.assertEqual(receipts, 0)
