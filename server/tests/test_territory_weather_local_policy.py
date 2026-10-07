import struct
import unittest

from psycopg.errors import CheckViolation
from postgres_case import PostgresCase
from wakfu_server.territory_cells import territories
from wakfu_server.territory_weather import (
    context,
    decode,
    initialize_local_baselines,
    materialize_local_state,
)


class TerritoryWeatherLocalPolicyTests(PostgresCase):
    def test_all_catalog_territories_get_explicit_local_baseline_without_copying_capture(
        self,
    ):
        result = initialize_local_baselines(self.store)
        self.assertEqual(result["territories"], 274)
        self.assertEqual(result["policies_created"], 274)
        self.assertEqual(result["states_created"], 273)
        self.assertEqual(result["states_preserved"], 1)
        self.assertEqual(len(territories()), 274)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM territory_weather_local_policy"
                ).fetchone()["n"],
                274,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM territory_weather WHERE instance_id=0"
                ).fetchone()["n"],
                274,
            )
            local = db.execute(
                "SELECT source,weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6 "
                "FROM territory_weather_local_policy WHERE map_id=1134 AND region_id=79201"
            ).fetchone()
            captured = db.execute(
                "SELECT source,weather FROM territory_weather_local_policy "
                "WHERE map_id=1134 AND region_id=79301"
            ).fetchone()
        self.assertEqual(local["source"], "LOCAL_POLICY")
        self.assertEqual(local["weather"], "ABSENT")
        self.assertEqual(local["native_byte"], 0)
        self.assertEqual(tuple(local[f"value_{i}"] for i in range(1, 7)), (0,) * 6)
        self.assertEqual(captured["source"], "PRESERVED_STATE")
        self.assertEqual(captured["weather"], "LIGHT")

    def test_configured_policy_materializes_per_instance_and_preserves_float_fields(
        self,
    ):
        initialize_local_baselines(
            self.store,
            weather="HEAVY",
            native_byte=-7,
            native_values=(12.5, -2.0, 3.25, 4.0, 0.125, 0.75),
        )
        row = materialize_local_state(
            self.store, map_id=1134, instance_id=88, region_id=79201
        )
        decoded = decode(row["native_payload"])
        self.assertEqual(row["weather"], "HEAVY")
        self.assertEqual(decoded["native_identity"], 79201)
        self.assertEqual(decoded["native_byte"], -7)
        self.assertEqual(decoded["native_values"], (12.5, -2.0, 3.25, 4.0, 0.125, 0.75))
        self.assertEqual(decoded["weather"], "HEAVY")
        again = materialize_local_state(
            self.store, map_id=1134, instance_id=88, region_id=79201
        )
        self.assertEqual(again, row)

    def test_context_materializes_known_regions_but_does_not_invent_unknown_regions(
        self,
    ):
        character = {"map_id": 1134, "instance_id": 26}
        value = context(self.store, character, x=-23, y=-143, z=70)
        self.assertEqual(value["region_id"], 79201)
        self.assertEqual(value["weather"], "ABSENT")
        self.assertEqual(decode(value["native_payload"])["native_identity"], 79201)
        with self.assertRaisesRegex(ValueError, "Unknown native map region"):
            materialize_local_state(
                self.store, map_id=1134, instance_id=26, region_id=999999
            )
        with self.assertRaisesRegex(ValueError, "territory at position"):
            context(self.store, character, x=10000, y=10000, z=0)

    def test_baseline_policy_rejects_bad_fields_before_writing(self):
        for values, byte, weather in (
            ((0, 0, 0, 0, 0), 0, "ABSENT"),
            ((0, 0, 0, 0, 0, float("inf")), 0, "ABSENT"),
            ((0, 0, 0, 0, 0, 0), 128, "ABSENT"),
            ((0, 0, 0, 0, 0, 0), 0, "CLEAR"),
        ):
            with self.subTest(values=values, byte=byte, weather=weather):
                with self.assertRaises(ValueError):
                    initialize_local_baselines(
                        self.store,
                        weather=weather,
                        native_byte=byte,
                        native_values=values,
                    )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM territory_weather_local_policy"
                ).fetchone()["n"],
                0,
            )

    def test_initializer_materializes_missing_state_for_existing_policy(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO territory_weather_local_policy "
                "(map_id,region_id,source,policy_version,weather,native_byte,"
                "value_1,value_2,value_3,value_4,value_5,value_6) "
                "VALUES(1134,79201,'LOCAL_POLICY',4,'STORM',-2,1,2,3,4,5,6)"
            )
        result = initialize_local_baselines(self.store)
        self.assertEqual(result["policies_preserved"], 1)
        self.assertEqual(result["states_created"], 273)
        with self.store.connection() as db:
            state = db.execute(
                "SELECT native_payload FROM territory_weather "
                "WHERE map_id=1134 AND instance_id=0 AND region_id=79201"
            ).fetchone()
        decoded = decode(state["native_payload"])
        self.assertEqual(decoded["weather"], "STORM")
        self.assertEqual(decoded["native_byte"], -2)
        self.assertEqual(decoded["native_values"], (1, 2, 3, 4, 5, 6))

    def test_global_settings_override_is_used_for_new_local_policies(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s::jsonb WHERE name='weather_local_baseline'",
                (
                    '{"weather":"HEAVY","native_byte":3,"native_values":[1,2,3,4,5,6],"policy_version":9}',
                ),
            )
        initialize_local_baselines(self.store)
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT source,policy_version,weather,native_byte,value_1,value_2,value_3,"
                "value_4,value_5,value_6 FROM territory_weather_local_policy "
                "WHERE map_id=1134 AND region_id=79201"
            ).fetchone()
        self.assertEqual(policy["source"], "LOCAL_POLICY")
        self.assertEqual(policy["policy_version"], 9)
        self.assertEqual(policy["weather"], "HEAVY")
        self.assertEqual(policy["native_byte"], 3)
        self.assertEqual(
            tuple(policy[f"value_{i}"] for i in range(1, 7)), (1, 2, 3, 4, 5, 6)
        )

    def test_negative_instance_weather_rows_are_rejected_by_database(self):
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO territory_weather "
                    "(map_id,instance_id,region_id,weather,native_payload) "
                    "VALUES(1134,-1,79201,'ABSENT',%s)",
                    (struct.pack(">qb6fi", 79201, 0, 0, 0, 0, 0, 0, 0, 0),),
                )


if __name__ == "__main__":
    unittest.main()
