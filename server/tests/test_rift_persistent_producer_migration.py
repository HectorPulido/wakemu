"""Exact legacy producer correction preserves operator policy and transactions."""
from copy import deepcopy
from pathlib import Path
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase


class RiftPersistentProducerMigrationTests(PostgresCase):
    def test_known_legacy_only_fresh_noop_custom_preservation_and_rollback(self):
        sql = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "318_rift_persistent_artifact_producer.sql"
        ).read_text()
        with self.store.connection() as db:

            def load():
                return db.execute(
                    "SELECT value FROM settings WHERE name='rift_native_gameplay_policy'"
                ).fetchone()["value"]

            def save(value):
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='rift_native_gameplay_policy'",
                    (Jsonb(value),),
                )

            fresh = load()
            expected = fresh["artifacts"]["producer"]
            self.assertEqual(
                (expected["template_effect_reference"], expected["source_document"]),
                (147120, "combat-state-definitions.json"),
            )
            db.execute(sql)
            self.assertEqual(load(), fresh)
            counts_before = {
                name: db.execute("SELECT count(*) AS n FROM " + name).fetchone()["n"]
                for name in ("accounts", "characters", "sessions", "inventory_items")
            }
            for source in (None, "weapon-combat-effects.json"):
                legacy = deepcopy(fresh)
                legacy["enabled"] = True
                legacy["artifacts"]["enabled"] = True
                legacy["operator_marker"] = "preserve-all-sibling-values"
                legacy["artifacts"]["producer"] = dict(
                    expected, template_effect_reference=315925
                )
                if source is None:
                    legacy["artifacts"]["producer"].pop("source_document")
                else:
                    legacy["artifacts"]["producer"]["source_document"] = source
                save(legacy)

                class Discard(Exception):
                    pass

                try:
                    with db.transaction():
                        db.execute(sql)
                        corrected = deepcopy(legacy)
                        corrected["artifacts"]["producer"] = expected
                        self.assertEqual(load(), corrected)
                        raise Discard()
                except Discard:
                    pass
                self.assertEqual(load(), legacy)
                db.execute(sql)
                self.assertEqual(load(), corrected)
                db.execute(sql)
                self.assertEqual(load(), corrected)
                for mutation in (
                    dict(operator_key="custom"),
                    dict(template_effect_reference=999999),
                    dict(source_document="custom-original.json"),
                ):
                    custom = deepcopy(legacy)
                    custom["artifacts"]["producer"].update(mutation)
                    save(custom)
                    db.execute(sql)
                    self.assertEqual(load(), custom)
                custom = deepcopy(legacy)
                custom["policy"] = "operator.custom"
                save(custom)
                db.execute(sql)
                self.assertEqual(load(), custom)
            self.assertEqual(
                {
                    name: db.execute("SELECT count(*) AS n FROM " + name).fetchone()[
                        "n"
                    ]
                    for name in counts_before
                },
                counts_before,
            )
