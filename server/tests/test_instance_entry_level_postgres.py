"""Bulk315–317 installation and real owned admission, in an isolated schema.

The dungeon callback adds a declared200-level fixture threshold to the exact
native criterion. It proves the shared admission policy without changing the
native route or claiming that Jalato itself originally required level200.
"""
from copy import deepcopy
import os
from pathlib import Path
import struct
import tempfile
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_dungeon_instances as dungeon_fixture
from wakfu_server import dungeon_transport, rift_entry_adapter
from wakfu_server.characters import heroes
from wakfu_server.maps import dungeon_entry_access


class InstanceEntryLevelAdmissionPostgresTests(PostgresCase):
    player = dungeon_fixture.DungeonInstanceTests.player
    install_context_policy = dungeon_fixture.DungeonInstanceTests.install_context_policy

    def setUp(self):
        # This explicitly qualifies the315–317 upgrade boundary. Later unrelated
        # migrations must not silently replace the pre-activation witness.
        directory = tempfile.TemporaryDirectory(prefix="wakemu-entry-policy-")
        self.addCleanup(directory.cleanup)
        root = Path(__file__).resolve().parents[1] / "migrations"
        for source in root.glob("*.sql"):
            if int(source.name.split("_", 1)[0]) <= 314:
                (Path(directory.name) / source.name).symlink_to(source)
        with patch.dict(os.environ, WAKFU_MIGRATIONS_TEST_DIR=directory.name):
            super().setUp()
        self.migrations = root
        self.install_context_policy(1)

    @staticmethod
    def setting(db, name):
        return db.execute(
            "SELECT value FROM settings WHERE name=%s", (name,)
        ).fetchone()["value"]

    def set_enforced(self, value):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='instance_entry_level_policy'",
                (Jsonb(dict(version=1, enforce_minimum_level=value)),),
            )

    def test_scoped_activation_low_owned_company_entry_late_join_and_reconnect(self):
        sql315 = (self.migrations / "315_rift_scoped_native_gameplay.sql").read_text()
        sql316 = (self.migrations / "316_rift_wave_actor_bindings.sql").read_text()
        sql317 = (self.migrations / "317_enable_scoped_ultimate_rifts.sql").read_text()
        with self.store.connection() as db:
            classic_before = deepcopy(self.setting(db, "rift_policy"))
            db.execute(sql315)
            db.execute(sql316)
            native315 = self.setting(db, "rift_native_gameplay_policy")
            self.assertFalse(native315["enabled"])
            self.assertFalse(native315["artifacts"]["enabled"])
            self.assertEqual(native315["enabled_types"], ["ULTIMATE_INFINITE_WAVE"])
            self.assertFalse(self.setting(db, "rift_policy")["ultimate_enabled"])
            self.assertEqual(
                self.setting(db, "instance_entry_level_policy"),
                dict(version=1, enforce_minimum_level=False),
            )
            for family in (
                "classic_grade_by_company_size",
                "ultimate_grade_by_company_size",
            ):
                self.assertEqual(set(native315["compensation"][family]), set("123456"))
                self.assertEqual(
                    [native315["compensation"][family][str(n)] for n in (5, 6)], [0, 0]
                )
            self.assertIsNotNone(
                db.execute(
                    "SELECT to_regclass('rift_wave_actor_bindings') AS relation"
                ).fetchone()["relation"]
            )

            class RollbackProbe(Exception):
                pass

            try:
                with db.transaction():
                    db.execute(sql317)
                    active = self.setting(db, "rift_native_gameplay_policy")
                    self.assertTrue(
                        active["enabled"] and active["artifacts"]["enabled"]
                    )
                    self.assertTrue(self.setting(db, "rift_policy")["ultimate_enabled"])
                    raise RollbackProbe()
            except RollbackProbe:
                pass
            self.assertEqual(self.setting(db, "rift_native_gameplay_policy"), native315)
            self.assertFalse(self.setting(db, "rift_policy")["ultimate_enabled"])
            db.execute(sql317)
            active = self.setting(db, "rift_native_gameplay_policy")
            expected = deepcopy(native315)
            expected["enabled"] = expected["artifacts"]["enabled"] = True
            self.assertEqual(active, expected)
            expected_classic = dict(classic_before, ultimate_enabled=True)
            self.assertEqual(self.setting(db, "rift_policy"), expected_classic)

        main = self.player("low-dungeon")
        account, generation, main_id = (
            main["account"],
            main["generation"],
            main["character"]["id"],
        )
        hero = self.store.create_character(account, "Lowdungeonhero")
        heroes.add(self.store, account, generation, main_id, hero["id"])
        ids = [main_id, hero["id"]]
        before = {identity: self.store.character(account, identity) for identity in ids}
        self.assertEqual([before[identity]["level"] for identity in ids], [1, 1])
        body = struct.pack(">qiBi", 26842, 2504, 0, 2)

        def criterion(character, native):
            return dungeon_entry_access.evaluate(
                self.store,
                "(" + native + ") and GetRealLevel() >= 200",
                character=character,
            )

        def enter(selected_generation=generation, source=True):
            return dungeon_transport.enter(
                self.store,
                account,
                selected_generation,
                main_id,
                527,
                body,
                criterion_allowed=criterion,
                source_allowed=lambda *_: source,
            )

        self.set_enforced(True)
        with self.assertRaises(ValueError):
            enter()
        with self.store.connection() as db:
            # 315 is conservative on operator choices when reapplied.
            db.execute(sql315)
            self.assertTrue(
                self.setting(db, "instance_entry_level_policy")["enforce_minimum_level"]
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )
        self.set_enforced(False)
        with self.store.connection() as db:
            mode_before = self.setting(db, "dungeon_server_mode")
            db.execute(
                "UPDATE settings SET value=%s WHERE name='dungeon_server_mode'",
                (Jsonb(dict(version=1, is_neo_server=True)),),
            )
        with self.assertRaises(ValueError):
            enter()
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='dungeon_server_mode'",
                (Jsonb(mode_before),),
            )
        with self.assertRaises(ValueError):
            enter(selected_generation="stale-lease")
        with self.assertRaises(ValueError):
            enter(source=False)
        entered = enter()
        self.assertEqual(set(entered["members"]), set(ids))
        for identity in ids:
            current = self.store.character(account, identity)
            self.assertEqual(current["instance_id"], entered["instance_id"])
            self.assertEqual(
                tuple(current[key] for key in ("level", "hp", "max_hp")),
                tuple(before[identity][key] for key in ("level", "hp", "max_hp")),
            )
        fresh_generation = self.store.begin_session(account, ttl=10000)
        restored = self.store.select_character(account, fresh_generation, main_id)
        self.assertEqual(restored["instance_id"], entered["instance_id"])
        self.assertEqual(restored["level"], 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members WHERE instance_id=%s AND status='active'",
                    (entered["instance_id"],),
                ).fetchone()["n"],
                2,
            )

        # A legitimately high real level still passes the enforced branch. The
        # source level is a declared fixture premise, not a claimed XP journey.
        high = self.player("high-dungeon")
        from wakfu_server import health_store

        high_id = high["character"]["id"]
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=245 WHERE id=%s", (high_id,))
        canonical = health_store.initialize(
            self.store, high["account"], high["generation"], high_id
        )
        maximum = canonical["max_hp"]
        health_store.sync(
            self.store,
            high["account"],
            high["generation"],
            high_id,
            canonical["hp"],
            maximum - 11,
        )
        self.set_enforced(True)
        high_result = dungeon_transport.enter(
            self.store,
            high["account"],
            high["generation"],
            high_id,
            527,
            body,
            criterion_allowed=criterion,
            source_allowed=lambda *_: True,
        )
        high_after = self.store.character(high["account"], high_id)
        self.assertEqual(high_after["level"], 245)
        self.assertEqual(high_after["instance_id"], high_result["instance_id"])
        self.assertEqual(
            (high_after["hp"], high_after["max_hp"]), (maximum - 11, maximum)
        )
        self.set_enforced(False)

        # The actual native Rift catalog has a positive minimum; low real levels
        # remain unchanged while the entrance-only policy admits the company.
        owner = self.player("low-rift")
        raccount, lease, owner_id = (
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
        )
        first_hero = self.store.create_character(raccount, "Lowrifthero")
        late_hero = self.store.create_character(raccount, "Laterifthero")
        heroes.add(self.store, raccount, lease, owner_id, first_hero["id"])
        with self.store.connection() as db:
            catalog = self.setting(db, "rift_catalog")
            native = next(
                row
                for _, row in sorted(catalog.items(), key=lambda item: int(item[0]))
                if row["type"] == "ULTIMATE_INFINITE_WAVE"
            )
            native_before = deepcopy(native)
            self.assertGreater(native["level"], 1)
            source = native["entrances"][0]
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=0,y=0,z=0 WHERE id=ANY(%s)",
                (source["map_id"], [owner_id, first_hero["id"]]),
            )
        action = struct.pack(">qHH", source["object_id"], 11, 0)

        def rift_enter(*, selected=owner_id, selected_lease=lease, near=True):
            return rift_entry_adapter.enter(
                self.store,
                raccount,
                selected_lease,
                selected,
                source["map_id"],
                action,
                source_allowed=lambda row, obj: near
                and row["map_id"] == source["map_id"]
                and obj["object_id"] == source["object_id"],
                resolve_destination=lambda *_: dict(
                    map_id=native["map_id"], x=0, y=1, z=0
                ),
                seed="entry-minimum-qualification",
            )

        self.set_enforced(True)
        with self.assertRaises(ValueError):
            rift_enter()
        self.set_enforced(False)
        with self.assertRaises(ValueError):
            rift_enter(selected_lease="stale-lease")
        with self.assertRaises(ValueError):
            rift_enter(near=False)
        admitted = rift_enter()
        run = admitted["run"]
        self.assertEqual(set(run["members"]), {owner_id, first_hero["id"]})
        self.assertEqual(run["catalog"], native_before)
        self.assertEqual(run["catalog"]["level"], native_before["level"])
        self.assertEqual(
            [
                self.store.character(raccount, identity)["level"]
                for identity in run["members"]
            ],
            [1, 1],
        )
        self.set_enforced(True)
        with self.assertRaisesRegex(ValueError, "entrance level"):
            heroes.add(self.store, raccount, lease, owner_id, late_hero["id"])
        self.set_enforced(False)
        heroes.add(self.store, raccount, lease, owner_id, late_hero["id"])
        with self.store.connection() as db:
            persisted = db.execute(
                "SELECT * FROM rift_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            self.assertEqual(
                set(persisted["members"]), {owner_id, first_hero["id"], late_hero["id"]}
            )
            self.assertEqual(
                (persisted["wave"], persisted["completed_waves"]),
                (run["wave"], run["completed_waves"]),
            )
        reconnect = self.store.begin_session(raccount, ttl=10000)
        current = self.store.select_character(raccount, reconnect, owner_id)
        self.assertEqual(
            (current["instance_id"], current["level"]), (run["instance_id"], 1)
        )
