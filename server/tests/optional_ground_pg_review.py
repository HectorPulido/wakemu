"""Opt-in disposable-schema integration; native catalogs are read-only."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import struct
import time
import uuid
from threading import RLock
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

if os.environ.get("WAKFU_OPTIONAL_REVIEW_PG") != "1":
    raise SystemExit("Explicit isolated PG opt-in required")

from wakfu_server import dungeon_optional_ground_items as ground
from wakfu_server import dungeon_runtime_config as configuration
from wakfu_server import (
    dungeon_progression,
    dungeon_fight_binding,
    dungeon_optional_encounters,
    fight_store,
)
from wakfu_server.combat_group_store import PersistentGroups

from wakfu_server import native_compiled_catalog as compiled
import wakfu_server

fixture = None
compiler_fixture = None
if os.environ.get("WAKFU_OPTIONAL_REVIEW_COMPILER_FIXTURE") == "1":
    frozen = Path("/authority/server")
    inventory = {
        "wakfu_server/"
        + p.relative_to(frozen / "wakfu_server")
        .as_posix(): hashlib.sha256(p.read_bytes())
        .hexdigest()
        for p in sorted((frozen / "wakfu_server").rglob("*.py"))
        if "__pycache__" not in p.parts
    }
    for name in (
        "tools/publish_compiled_combat_catalog.py",
        "migrations/320_native_compiled_catalogs.sql",
    ):
        inventory[name] = hashlib.sha256((frozen / name).read_bytes()).hexdigest()
    compiler_fixture = compiled.canonical_bytes(inventory)
    fixture = patch.object(
        compiled, "_compiler_source_bytes", return_value=compiler_fixture
    )
    fixture.start()

schema = "wakemu_optional_review_" + uuid.uuid4().hex[:12]
kw = dict(row_factory=dict_row)
if os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"):
    kw["password"] = (
        Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"]).read_text().strip()
    )
url = os.environ["WAKFU_DATABASE_URL"]


def raw():
    return psycopg.connect(url, **kw)


class Store:
    def __init__(self):
        self.trace = []
        self.late_failure = False

    @contextmanager
    def connection(self):
        with raw() as db:
            db.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))

            class Guard:
                info = db.info

                def execute(inner, query, args=()):
                    text = query if isinstance(query, str) else str(query)
                    self.trace.append(text)
                    if self.late_failure and text.startswith(
                        "INSERT INTO dungeon_optional_publication_outbox"
                    ):
                        raise RuntimeError("Injected late outbox failure")
                    return db.execute(query, args)

            yield Guard()

    def now(self):
        return datetime.now(timezone.utc)

    def character(self, account_id, character_id, db):
        row = db.execute(
            "SELECT * FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        row["inventory_items"] = db.execute(
            "SELECT * FROM inventory_items WHERE character_id=%s", (character_id,)
        ).fetchall()
        row["builds"] = {}
        row["level"] = 60
        return row


class Positions:
    def __init__(self):
        self.calls = []

    @contextmanager
    def account_barrier(self, account_id, blocking=False):
        assert blocking is False
        self.calls.append(("barrier", account_id))
        yield

    def flush(self, account_id):
        self.calls.append(("flush", account_id))


store = Store()
positions = Positions()
groups = PersistentGroups(store)
body = struct.pack(">iqii", 7952, 700001, 21, 51)
checks = []
metrics = {}
started = time.monotonic()


def check(name, predicate):
    assert predicate, name
    checks.append(name)


def snapshot():
    with store.connection() as db:
        return dict(
            run=db.execute(
                "SELECT * FROM dungeon_room_runs ORDER BY instance_id"
            ).fetchone(),
            items=db.execute(
                "SELECT uid,quantity FROM inventory_items ORDER BY uid"
            ).fetchall(),
            access=db.execute("SELECT * FROM dungeon_optional_access").fetchall(),
            groups=db.execute(
                "SELECT group_id,status FROM combat_groups ORDER BY group_id"
            ).fetchall(),
            outbox=db.execute(
                "SELECT * FROM dungeon_optional_publication_outbox"
            ).fetchall(),
        )


def expect_failure(label, call, exception=ValueError):
    before = snapshot()
    first_query = len(store.trace)
    start = time.perf_counter_ns()
    try:
        call()
    except exception:
        pass
    else:
        raise AssertionError(label + " did not reject")
    queries = store.trace[first_query:]
    metrics[label] = dict(
        elapsed_ms=round((time.perf_counter_ns() - start) / 1e6, 3),
        queries=len(queries),
        inventory_writes=sum(
            q.startswith(("UPDATE inventory_items", "DELETE FROM inventory_items"))
            for q in queries
        ),
    )
    check(label, snapshot() == before)


def use(lease="lease", actor=76, payload=body):
    return ground.use(store, groups, 54, lease, actor, payload, positions=positions)


try:
    with raw() as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        db.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        db.execute(
            """
CREATE TABLE accounts(id bigint PRIMARY KEY,is_admin boolean DEFAULT false);
CREATE TABLE characters(id bigint PRIMARY KEY,account_id bigint,map_id integer,instance_id bigint,x integer,y integer,z integer,deleted_at timestamptz);
CREATE TABLE sessions(account_id bigint PRIMARY KEY,character_id bigint,generation text,expires_at timestamptz);
CREATE TABLE dungeon_instances(instance_id bigint PRIMARY KEY,party_id bigint,status text,context_route_key text,context_policy_version integer,definition_id integer,UNIQUE(instance_id,party_id));
CREATE TABLE dungeon_instance_members(instance_id bigint,party_id bigint,character_id bigint,status text,session_generation text);
CREATE TABLE inventory_items(uid bigint PRIMARY KEY,character_id bigint,reference integer,quantity integer,container bigint,slot integer);
CREATE TABLE account_professions(account_id bigint,profession_id integer,xp bigint);
CREATE TABLE combat_fights(id integer PRIMARY KEY,status text);
CREATE TABLE combat_fight_participants(fight_id integer,character_id bigint,account_id bigint,team integer,session_generation text);
CREATE TABLE developer_item_test_groups(map_id integer,instance_id bigint,group_id bigint);
CREATE TABLE combat_groups(map_id integer,instance_id bigint,group_id bigint,members jsonb,status text,revision bigint DEFAULT 0,fight_id integer,generation text,defeated_at timestamptz,PRIMARY KEY(map_id,instance_id,group_id));
CREATE TABLE combat_group_members(map_id integer,instance_id bigint,monster_id bigint,group_id bigint,PRIMARY KEY(map_id,instance_id,monster_id));
CREATE TABLE npc_actor_identity_aliases(map_id integer,instance_id bigint,group_id bigint,old_actor_id bigint,new_actor_id bigint);
CREATE TABLE dungeon_room_spawn_receipts(instance_id bigint,room_order integer,asset_map_id integer,group_id bigint);
CREATE TABLE objectives_challenge_runs(instance_id bigint,map_id integer,group_id bigint,status text,returned_at timestamptz);
CREATE TABLE dungeon_runtime_configurations(route_key text,policy_version integer,configuration jsonb,PRIMARY KEY(route_key,policy_version));
CREATE TABLE player_exchange_members(character_id bigint,exchange_id bigint);
CREATE TABLE player_exchanges(id bigint,state text,expires_at timestamptz);
CREATE TABLE resource_harvest_occupations(character_id bigint,expires_at timestamptz);
CREATE TABLE craft_occupations(character_id bigint,state text);
CREATE SEQUENCE dungeon_room_group_ids AS bigint START WITH 288230376151711744 INCREMENT BY 8;
CREATE SEQUENCE lua_exact_npc_actor_ids AS bigint START WITH 1125899906842624 INCREMENT BY 128;
CREATE TABLE settings(name text PRIMARY KEY,value jsonb);
CREATE TABLE dungeon_stele_encounters(fight_id integer PRIMARY KEY,instance_id bigint,snapshot jsonb);
CREATE TABLE fight_reward_awards(fight_id integer,character_id bigint,marker text);
"""
        )
        migration = Path(wakfu_server.__file__).resolve().parent.parent / "migrations"
        db.execute((migration / "071_dungeon_room_progression.sql").read_text())
        db.execute((migration / "074_dungeon_aborted_encounters.sql").read_text())
        difficulty = (migration / "125_dungeon_difficulty_authority.sql").read_text()
        db.execute(difficulty[: difficulty.index("CREATE FUNCTION")])
        db.execute((migration / "334_dungeon_optional_ground_access.sql").read_text())
        # Native difficulty source copied read-only; no public writes/sequences.
        db.execute(
            "INSERT INTO settings SELECT name,value FROM public.settings WHERE name='dungeon_difficulty_catalog'"
        )
        config_path = Path(
            os.environ.get(
                "WAKFU_OPTIONAL_REVIEW_CONFIGURATION", "/qa_configuration.json"
            )
        )
        cfg = json.loads(config_path.read_text())
        expected = configuration.prepare_configuration(
            cfg["compiled_plan"],
            cfg["topology"],
            cfg["route"],
            version=cfg["version"],
            provenance=cfg["provenance"],
            level_policy=cfg["level_policy"],
        )
        check(
            "exact balanced configuration retains reviewed level policy",
            expected == cfg and cfg["level_policy"]["mode"] != "native_minimum",
        )
        configuration.require_monster_admission(cfg)
        check("all4 source rosters pass actual native admission", True)
        # Every retained roster has a real native six-player formation, including
        # the optional room sharing native first-floor terrain.
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.dungeon_encounters import roster_members

        geometry = map_geometry(910)
        formations = []
        for room in cfg["topology"]["rooms"]:
            frozen = next(
                r for r in cfg["compiled_plan"]["rooms"] if r["order"] == room["order"]
            )
            roster = [
                dict(
                    ref_id=r["ref_id"],
                    count=r["count"],
                    min_level=r["native_min_level"],
                    max_level=r["native_max_level"],
                    role=r["role"],
                )
                for r in frozen["monsters"]
            ]
            cells = set(map(tuple, room["cells"]))
            section = dict(
                geometry,
                cells=tuple(cells),
                edges=tuple(
                    (a, b)
                    for a, b in geometry["edges"]
                    if tuple(a) in cells and tuple(b) in cells
                ),
            )
            members = roster_members(
                10,
                roster,
                asset_map_id=910,
                anchor=room["anchor"],
                geometry=section,
                group_id=288230376151711744,
                select_level=configuration.level_selector(
                    cfg, room_order=room["order"]
                ),
                actor_id_base=1125899906842624 + room["order"] * 128,
                player_slots=6,
            )
            formations.append(
                dict(
                    order=room["order"],
                    count=len(members),
                    all_native_cells=all(
                        (m["x"], m["y"], m["z"]) in cells for m in members
                    ),
                )
            )
        check(
            "all4 retained rooms support six-player native formations",
            all(r["all_native_cells"] for r in formations),
        )
        Path("/work/candidate25-v5-qualification.json").write_text(
            json.dumps(
                dict(
                    prepare_equality=configuration.prepare_configuration(
                        cfg["compiled_plan"],
                        cfg["topology"],
                        cfg["route"],
                        version=cfg["version"],
                        provenance=cfg["provenance"],
                        level_policy=cfg["level_policy"],
                    )
                    == cfg,
                    admission=True,
                    formations=formations,
                    main_rooms=[
                        r.order
                        for r in configuration.plan_from_configuration(cfg).rooms
                    ],
                    future_admissions_only=True,
                    active_instances_repinned=False,
                ),
                indent=2,
            )
            + "\n"
        )
        check(
            "qualified optional config prepares",
            configuration.prepare_configuration(
                cfg["compiled_plan"],
                cfg["topology"],
                cfg["route"],
                version=cfg["version"],
                provenance=cfg["provenance"],
                level_policy=cfg["level_policy"],
            )
            == cfg,
        )
        db.execute("INSERT INTO accounts(id) VALUES(54)")
        db.execute(
            "INSERT INTO characters(id,account_id,map_id,instance_id,x,y,z) VALUES(76,54,910,10,20,51,0)"
        )
        db.execute(
            "INSERT INTO sessions VALUES(54,76,'lease',%s)",
            (store.now() + timedelta(hours=1),),
        )
        db.execute(
            "INSERT INTO dungeon_instances VALUES(10,20,'active','native_dungeon_25',5,25)"
        )
        db.execute(
            "INSERT INTO dungeon_instance_members VALUES(10,20,76,'active','lease')"
        )
        rooms = [
            dict(order=r["order"], monsters=r["monsters"])
            for r in cfg["compiled_plan"]["rooms"][:3]
        ]
        db.execute(
            "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,current_room,status,revision) VALUES(10,20,%s,%s,3,'completed',4)",
            (cfg["compiled_plan"]["document_sha256"], Jsonb(rooms)),
        )
        db.execute("INSERT INTO inventory_items VALUES(700001,76,11387,1,500,1)")
        db.execute("INSERT INTO account_professions VALUES(54,64,0)")
        db.execute(
            "INSERT INTO dungeon_runtime_configurations VALUES('native_dungeon_25',5,%s)",
            (Jsonb(cfg),),
        )
        db.execute(
            "INSERT INTO dungeon_difficulty_selections(instance_id,stasis_level,competitive,competitive_max_level) VALUES(10,2,false,0)"
        )
        db.execute(
            "INSERT INTO fight_reward_awards VALUES(507,76,'earned-main-boss-reward-unchanged')"
        )
    expect_failure("wrong lease cannot consume/spawn", lambda: use(lease="stale"))
    with store.connection() as db:
        db.execute("UPDATE dungeon_instance_members SET status='returned'")
    expect_failure("inactive membership cannot consume/spawn", use)
    with store.connection() as db:
        db.execute("UPDATE dungeon_instance_members SET status='active'")
    expect_failure(
        "wrong soil cannot consume/spawn",
        lambda: use(payload=struct.pack(">iqii", 7952, 700001, 22, 51)),
    )
    store.late_failure = True
    expect_failure(
        "late outbox failure rolls back seed/group/receipt", use, RuntimeError
    )
    store.late_failure = False
    before = snapshot()
    store.trace.clear()
    result = use()
    after = snapshot()
    with store.connection() as db:
        check(
            "Farmer XP remains zero",
            db.execute("SELECT xp FROM account_professions").fetchone()["xp"] == 0,
        )
    check(
        "Farmer0 consumes exactly one seed without XP grant",
        result["consumed"] == 1 and after["items"] == [],
    )
    check(
        "one registered group/access/outbox atomically",
        len(after["groups"]) == len(after["access"]) == len(after["outbox"]) == 1,
    )
    check("main3 frontier/revision preserved on access", before["run"] == after["run"])
    run_lock = next(
        i
        for i, s in enumerate(store.trace)
        if s.startswith("SELECT * FROM dungeon_room_runs") and "FOR UPDATE" in s
    )
    account_lock = next(
        i
        for i, s in enumerate(store.trace)
        if s.startswith("SELECT id FROM accounts") and "FOR UPDATE" in s
    )
    pop_lock = next(
        i for i, s in enumerate(store.trace) if "pg_advisory_xact_lock" in s
    )
    check(
        "actual SQL lock order run before account before population",
        run_lock < account_lock < pop_lock,
    )
    check(
        "canonical nonblocking position fence used",
        positions.calls[-2:] == [("barrier", 54), ("flush", 54)],
    )
    replay = use()
    check(
        "paid request replay no second consume/group",
        replay["replay"] and replay["consumed"] == 0 and snapshot() == after,
    )
    with store.connection() as db:
        receipt = db.execute("SELECT * FROM dungeon_optional_access").fetchone()
        group_key = (receipt["asset_map_id"], 10, receipt["group_id"])
        check(
            "ordinary group visibility includes paid optional",
            len(groups.available(910, 10)) == 1,
        )

    # A post-commit delivery failure does not lose the outbox or the paid group.
    def broken_delivery(*packet):
        raise OSError("Injected socket failure")

    try:
        dungeon_optional_encounters.publish_pending(
            store, groups, instance_id=10, publish=broken_delivery
        )
    except OSError:
        pass
    else:
        raise AssertionError("delivery failure not observed")
    check(
        "failed socket retains pending outbox",
        snapshot()["outbox"][0]["published"] is False,
    )
    recovered_groups = PersistentGroups(store)
    check(
        "restart object recovers same paid group without seed",
        recovered_groups.available(910, 10)[0]["key"] == group_key
        and snapshot()["items"] == [],
    )
    sends = []
    world = SimpleNamespace(
        lock=RLock(),
        players={"lease": ("lease", "peer", dict(map_id=910, instance_id=10))},
        location=lambda actor: (actor["map_id"], actor["instance_id"]),
        _send=lambda *packet: False,
    )
    confirmed = lambda *packet: dungeon_optional_encounters.publish_native_scene(
        world, *packet
    )
    check(
        "false native socket result retains pending outbox",
        dungeon_optional_encounters.publish_pending(
            store, recovered_groups, instance_id=10, publish=confirmed
        )
        is False
        and snapshot()["outbox"][0]["published"] is False,
    )
    world._send = lambda *packet: sends.append(packet) or True
    check(
        "reconnect poll publishes committed group",
        dungeon_optional_encounters.publish_pending(
            store, recovered_groups, instance_id=10, publish=confirmed
        )
        is True,
    )
    check(
        "successful delivery acknowledged once",
        snapshot()["outbox"][0]["published"] is True and len(sends) == 1,
    )
    check(
        "acknowledged outbox does not republish",
        dungeon_optional_encounters.publish_pending(
            store, recovered_groups, instance_id=10, publish=confirmed
        )
        is False
        and len(sends) == 1,
    )
    # NOWAIT owner acquisition must release the earlier run lock without writes.
    stable = snapshot()
    with raw() as blocker:
        blocker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        blocker.execute("SELECT id FROM accounts WHERE id=54 FOR UPDATE")
        contention_started = time.monotonic()
        expect_failure("real owner contention returns retry without writes", use)
        check(
            "owner contention bounded under one second",
            time.monotonic() - contention_started < 1.0,
        )
        blocker.execute(
            "SELECT instance_id FROM dungeon_room_runs WHERE instance_id=10 FOR UPDATE NOWAIT"
        )
    check("contention preserved all paid state", snapshot() == stable)
    for fight_id, outcome in ((100, "defeat"), (101, "abort"), (102, "victory")):
        lease, _ = groups.claim(group_key, "lease", fight_id)
        with store.connection() as db:
            dungeon_optional_encounters.lock_group_run(db, group_key)
            db.execute("INSERT INTO combat_fights VALUES(%s,'active')", (fight_id,))
            db.execute(
                "INSERT INTO combat_fight_participants VALUES(%s,76,54,0,'lease')",
                (fight_id,),
            )
            bound = dungeon_fight_binding.bind_room_group(
                db,
                group_key,
                76,
                fight_id,
                player_team=0,
                expected_selection_revision=1,
            )
            check(
                "optional scope binds " + outcome,
                bound["encounter_scope"] == "optional",
            )
            if outcome == "abort":
                check(
                    "public fight abort applied",
                    fight_store.abort(
                        store,
                        54,
                        76,
                        fight_id,
                        expected_generation="lease",
                        db=db,
                        on_aborted=dungeon_fight_binding.abort_room_encounter,
                    ),
                )
                groups.finish(lease, defeated=False, db=db)
                settled = db.execute(
                    "SELECT result FROM dungeon_room_encounters WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["result"]
            else:
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s",
                    (fight_id,),
                )
                dungeon_progression.lock_encounter_run(db, fight_id)
                check(
                    "actual group finalizer " + outcome,
                    groups.finish(lease, defeated=outcome == "victory", db=db),
                )
                settled = dungeon_progression.settle_encounter(
                    db,
                    SimpleNamespace(
                        id=fight_id,
                        phase="finished",
                        winner=0 if outcome == "victory" else 1,
                    ),
                )
                replayed = dungeon_progression.settle_encounter(
                    db,
                    SimpleNamespace(
                        id=fight_id,
                        phase="finished",
                        winner=0 if outcome == "victory" else 1,
                    ),
                )
                check("optional settlement replay " + outcome, replayed["replay"])
            check(
                "optional result retains main3 " + outcome,
                settled["current_room"] == 3
                and settled["revision"] == 4
                and settled["completed"],
            )
        check(
            "main run remains identical " + outcome, snapshot()["run"] == after["run"]
        )
        visible = groups.available(910, 10)
        check(
            "actual group availability " + outcome,
            (len(visible) == 1 and visible[0]["key"] == group_key)
            if outcome != "victory"
            else visible == [],
        )
    with store.connection() as db:
        check(
            "optional victory terminal; same group identity",
            db.execute("SELECT status,group_id FROM dungeon_optional_access").fetchone()
            == dict(status="victory", group_id=group_key[2]),
        )
        check(
            "no main boss stele granted",
            db.execute("SELECT count(*) n FROM dungeon_stele_encounters").fetchone()[
                "n"
            ]
            == 0,
        )
        check(
            "old main rewards retained",
            db.execute("SELECT * FROM fight_reward_awards").fetchall()
            == [
                dict(
                    fight_id=507,
                    character_id=76,
                    marker="earned-main-boss-reward-unchanged",
                )
            ],
        )
        # FK really points at shared encounter authority, including optional rows.
        db.execute(
            "INSERT INTO dungeon_encounter_difficulties(fight_id,instance_id,selection_revision,snapshot) VALUES(102,10,1,'{}') ON CONFLICT DO NOTHING"
        )
        check(
            "shared difficulty FK admits optional encounter",
            db.execute(
                "SELECT count(*) n FROM dungeon_encounter_difficulties WHERE fight_id=102"
            ).fetchone()["n"]
            == 1,
        )
    # Actual movement endpoint activation, without fabricating cqd13220.
    wrong_position = dict(map_id=910, x=20, y=51, z=0)
    store.trace.clear()
    no_target_start = time.perf_counter_ns()
    for _ in range(1000):
        ground.step_on_target(
            store, groups, 54, "lease", 76, wrong_position, positions=positions
        )
    metrics["non_target_step"] = dict(
        iterations=1000,
        mean_ms=round((time.perf_counter_ns() - no_target_start) / 1e9, 6),
        queries=len(store.trace),
    )
    check(
        "non-target step is a zero-DB no-op",
        ground.step_on_target(
            store, groups, 54, "lease", 76, wrong_position, positions=positions
        )
        is None
        and not store.trace,
    )
    actual_position = dict(map_id=910, x=21, y=51, z=0)
    expect_failure(
        "claimed step cannot forge actual owned location",
        lambda: ground.step_on_target(
            store, groups, 54, "lease", 76, actual_position, positions=positions
        ),
    )
    with store.connection() as db:
        db.execute(
            "INSERT INTO dungeon_instances VALUES(11,20,'active','native_dungeon_25',5,25)"
        )
        db.execute(
            "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,current_room,status,revision) SELECT 11,party_id,catalog_hash,rooms,3,'active',4 FROM dungeon_room_runs WHERE instance_id=10"
        )
        db.execute(
            "INSERT INTO dungeon_instance_members VALUES(11,20,76,'active','lease')"
        )
        db.execute("UPDATE characters SET instance_id=11,x=21,y=51,z=0 WHERE id=76")
        db.execute("INSERT INTO inventory_items VALUES(700002,76,11387,1,500,1)")
    expect_failure(
        "step before mandatory completion cannot consume",
        lambda: ground.step_on_target(
            store, groups, 54, "lease", 76, actual_position, positions=positions
        ),
    )
    with store.connection() as db:
        db.execute(
            "UPDATE dungeon_room_runs SET status='completed' WHERE instance_id=11"
        )
        db.execute("DELETE FROM inventory_items WHERE uid=700002")
    expect_failure(
        "step without owned seed cannot spawn",
        lambda: ground.step_on_target(
            store, groups, 54, "lease", 76, actual_position, positions=positions
        ),
    )
    with store.connection() as db:
        db.execute("INSERT INTO inventory_items VALUES(700002,76,11387,1,500,1)")
    before_step = snapshot()
    step_result = ground.step_on_target(
        store, groups, 54, "lease", 76, actual_position, positions=positions
    )
    check(
        "Farmer0 actual endpoint consumes one seed",
        step_result["consumed"] == 1 and step_result["instance_id"] == 11,
    )
    with store.connection() as db:
        step_receipt = db.execute(
            "SELECT * FROM dungeon_optional_access WHERE instance_id=11"
        ).fetchone()
        check(
            "step receipt records actual event not forged packet",
            step_receipt["activation_method"] == "step_on_target"
            and step_receipt["source_uid"] == 700002,
        )
        check(
            "step no profession XP grant",
            db.execute("SELECT xp FROM account_professions").fetchone()["xp"] == 0,
        )
        check(
            "step mandatory frontier/revision retained",
            db.execute(
                "SELECT current_room,status,revision FROM dungeon_room_runs WHERE instance_id=11"
            ).fetchone()
            == dict(current_room=3, status="completed", revision=4),
        )
    step_replay = ground.step_on_target(
        store, groups, 54, "lease", 76, actual_position, positions=positions
    )
    check(
        "same step replays paid receipt without seed",
        step_replay["replay"] and step_replay["consumed"] == 0,
    )
    extension = os.environ.get("WAKFU_OPTIONAL_REVIEW_EXTENSION")
    if extension:
        import runpy

        exercise = runpy.run_path(extension)["exercise"]
        exercise(
            dict(
                store=store,
                groups=groups,
                schema=schema,
                cfg=cfg,
                raw=raw,
                checks=checks,
                check=check,
                instance_id=11,
                character_id=76,
                account_id=54,
                generation="lease",
                positions=positions,
            )
        )
    print(
        json.dumps(
            dict(
                status="PASS",
                checks=checks,
                count=len(checks),
                seconds=round(time.monotonic() - started, 3),
                schema=schema,
                source="isolated-review",
                configuration_sha256=hashlib.sha256(
                    config_path.read_bytes()
                ).hexdigest(),
                configuration_file=str(config_path),
                level_policy_mode=cfg["level_policy"]["mode"],
                metrics=metrics,
                overlay_qualification=fixture is not None,
                frozen_compiler_fixture_sha256=hashlib.sha256(
                    compiler_fixture
                ).hexdigest()
                if compiler_fixture is not None
                else None,
                limits=[
                    "Native catalogs and real formation/group validation used read-only.",
                    "Real PostgreSQL seed/access/group/outbox transaction; all mutable rows/sequences in disposable schema.",
                    "Fight outcomes invoke actual bind/settle/abort dispatch; no native fight engine or live player delivery claimed.",
                ],
            )
        )
    )
finally:
    with raw() as db:
        db.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
        )
    if fixture is not None:
        fixture.stop()
