"""Manifest-driven native constructor/Ready qualification; no battle winners.

One disposable schema and immutable catalog serve independent rollback cases.
The three ordinary owned builds are reused, never combat/QI/publication state.
"""
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import gzip
import json
import os
import time
import traceback
import unittest

from postgres_case import PostgresCase

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "dungeon_ready_batch"


def read_fixture(name):
    with gzip.open(FIXTURES / name, "rt") as source:
        return json.load(source)


@unittest.skipUnless(
    os.environ.get("WAKFU_NATIVE_READY_BATCH") == "1",
    "Explicit native Ready batch opt-in",
)
class NativeDungeonReadyBatch(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server import dungeon_runtime_config, native_scene_start
        from tools.export_native_scene_seed import scene_sql
        from psycopg.types.json import Jsonb

        self.manifest = read_fixture("manifest.json.gz")
        self.authority = read_fixture("authority.json.gz")
        self.results = []
        self.configurations = {}
        self.addCleanup(self.write_receipt)
        self.enterContext(
            patch.object(
                native_scene_start, "_policy_database", return_value=self.store
            )
        )
        native_scene_start._runtime_rules.cache_clear()
        native_scene_start._source_identities.cache_clear()
        self.addCleanup(native_scene_start._runtime_rules.cache_clear)
        self.addCleanup(native_scene_start._source_identities.cache_clear)
        with self.store.connection() as db:
            schema = db.execute("SELECT current_schema() AS name").fetchone()["name"]
            for statement in scene_sql(
                self.authority["normalized_scene_tables"], schema=schema
            ):
                db.execute(statement)
            for record in self.authority["configurations"]:
                config = deepcopy(record["configuration"])
                prior = db.execute(
                    "SELECT configuration FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s",
                    (record["route"], record["version"]),
                ).fetchone()
                if prior is not None and prior["configuration"] != config:
                    config["version"] += 900000
                    config["context_policy"]["policy_version"] = config["version"]
                dungeon_runtime_config.install_configuration(db, config)
                self.configurations[record["route"]] = config
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb(dict(schema_version=1, routes=self.authority["routes"])),),
            )
        self.owners, self.party_id = self.create_owners()
        self.owner_baseline = self.owner_state()

    def create_owners(self):
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            persisted_party_character,
        )
        from wakfu_server import player_parties, health_store, health

        owners = []
        original = self.store.save_build

        def save_and_rest(account, generation, identity, *args, **kwargs):
            original(account, generation, identity, *args, **kwargs)
            character = health_store.initialize(
                self.store, account, generation, identity, exploration=True
            )
            if character["hp"] != character["max_hp"]:
                coefficient = health.exploration_coefficient(
                    character["max_hp"], character["hp"]
                )
                wait = (
                    character["hp_damage"]
                    * health.REGEN_DENOMINATOR_MS
                    / coefficient
                    / 1000
                    + 0.02
                )
                self.assertLess(wait, 5, "Unexpected initial build damage")
                time.sleep(wait)
                health_store.tick(
                    self.store, account, generation, identity, character["hp"]
                )
            return self.store.character(account, identity)

        for index in range(3):
            with patch.object(self.store, "save_build", side_effect=save_and_rest):
                character, generation, _, _, gear = persisted_party_character(
                    self.store,
                    native_endgame_iop_build(),
                    name="ready-owner-" + chr(97 + index),
                    map_id=711,
                    position=(0, 0, 0),
                )
            owners.append(
                dict(
                    character=character,
                    account=character["account_id"],
                    generation=generation,
                    gear=gear,
                )
            )
        party_id = None
        for member in owners[1:]:
            leader = owners[0]
            token = player_parties.invite(
                self.store,
                leader["account"],
                leader["generation"],
                leader["character"]["id"],
                member["character"]["id"],
            )
            joined = player_parties.answer(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                token,
                True,
            )
            if party_id is not None:
                self.assertEqual(joined, party_id)
            party_id = joined
        return owners, party_id

    def owner_state(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT c.id,c.map_id,c.instance_id,c.hp_damage,c.health_dead,"
                "s.generation,s.character_id FROM characters c JOIN sessions s ON s.account_id=c.account_id "
                "WHERE c.id=ANY(%s) ORDER BY c.id",
                ([member["character"]["id"] for member in self.owners],),
            ).fetchall()

    def write_receipt(self):
        output = Path(
            os.environ.get("WAKFU_READY_RECEIPT", "/tmp/native-dungeon-ready.json")
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                dict(
                    schema="wakemu-native-ready-result-v1",
                    scope="Constructor+Ready only; prior room progress/position and paid item acquisition are fixture premises; no wins or Jondo",
                    source_snapshot=self.manifest["source_snapshot_sha256"],
                    manifest_cases=len(self.manifest["cases"]),
                    passed=sum(r["passed"] for r in self.results),
                    failed=sum(not r["passed"] for r in self.results),
                    cases=self.results,
                ),
                indent=2,
                default=str,
            )
            + "\n"
        )

    def test_manifest_native_constructors_and_ready(self):
        from native_dungeon_ready_fixture import construct_case

        requested = set(
            filter(None, os.environ.get("WAKFU_READY_CASES", "").split(","))
        )
        skipped = set(
            filter(None, os.environ.get("WAKFU_READY_SKIP_CASES", "").split(","))
        )
        cases = [
            case
            for case in self.manifest["cases"]
            if (
                not requested
                or case["case_id"] in requested
                or case["route"] in requested
            )
            and case["case_id"] not in skipped
        ]
        self.assertTrue(cases, "Requested manifest selection is empty")
        self.assertEqual(len({c["case_id"] for c in cases}), len(cases))
        for case in cases:
            # A leaked owner/lease would invalidate subsequent cases: stop the
            # batch rather than laundering that contamination into successes.
            self.assertEqual(self.owner_state(), self.owner_baseline)
            with self.subTest(case_id=case["case_id"]):
                started = time.monotonic()
                result = dict(
                    case_id=case["case_id"],
                    route=case["route"],
                    room=case["room"],
                    passed=False,
                )
                try:
                    for member in self.owners:
                        lease = self.store.session_health(
                            member["account"], member["generation"], renew=True
                        )
                        self.assertTrue(lease["valid"], lease)
                    # All Store consumers share this genuine transaction. Each
                    # case gets fresh Python groups/Fight/QI/13974 trackers.
                    # Force rollback discards even successful case writes;
                    # monotonic SQL sequence gaps are intentionally retained.
                    with self.store.connection() as db:
                        with db.transaction(force_rollback=True):
                            with patch.object(
                                self.store,
                                "connection",
                                side_effect=lambda: nullcontext(db),
                            ):
                                details = construct_case(
                                    self,
                                    self.store,
                                    db,
                                    case,
                                    self.configurations[case["route"]],
                                    self.owners,
                                    self.party_id,
                                )
                    self.assertEqual(self.owner_state(), self.owner_baseline)
                    result.update(passed=True, owner_baseline_preserved=True, **details)
                except Exception as error:
                    result.update(
                        error=type(error).__name__,
                        detail=str(error),
                        traceback=traceback.format_exc(),
                    )
                    raise
                finally:
                    result["seconds"] = time.monotonic() - started
                    self.results.append(result)
                    self.write_receipt()
        self.assertEqual(self.owner_state(), self.owner_baseline)
        self.assertEqual(len(self.results), len(cases))
