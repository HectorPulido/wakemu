"""Independent ecology planner with durable bounded delivery and no inline fallback."""
import hmac
import hashlib
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import signal
import resource
import sys
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from psycopg import connect
from psycopg.types.json import Jsonb
from wakfu_server.ecology.client import EcologyClient
from wakfu_server.ecology.protocol import (
    DOMAINS,
    MAX_BODY_BYTES,
    MAX_PROPOSALS,
    MAX_SCOPES,
    SCHEMA_VERSION,
    TERMINAL_STATUSES,
    bounded_json,
    json_bytes,
    proposal,
    validate_query,
)

from wakfu_server.ecology.proposal_identity import identity as _proposal_identity

MAX_PENDING = 4096
RESERVED_INTERACTIVE = 32
RESERVED_GROWTH = 16
SOFT_PENDING = 512
DRAIN_BUDGET_SECONDS = 0.2
MAX_DRAIN_BATCHES = 16


BULK_FIELDS = {
    "resource_growth_bulk": ("resources", 64),
    "lifecycle_bulk": ("operations", 16),
}


def bulk_entry_key(entry):
    if entry.get("kind") == "resource_growth":
        return [
            entry["expected"]["resource_uid"],
            entry["expected"]["stage"],
            entry["expected"].get("resource_reference"),
        ]
    ticket = entry.get("ticket")
    if ticket is not None:
        return [
            entry["kind"],
            {
                key: ticket.get(key)
                for key in (
                    "map_id",
                    "instance_id",
                    "group_id",
                    "monster_id",
                    "reference",
                    "cycle",
                    "plan_incarnation",
                )
            },
        ]
    return entry


def bulk_failure_identity(domain, epoch, entry):
    identity = [epoch, domain, bulk_entry_key(entry)]
    if entry.get("kind") == "resource_growth":
        expected = entry["expected"]
        # A resource incarnation survives World restarts and batch reshuffling.
        identity = [
            domain,
            "resource_growth",
            {
                key: expected.get(key)
                for key in (
                    "resource_uid",
                    "map_id",
                    "instance_id",
                    "resource_reference",
                    "creation_time",
                    "stage",
                )
            },
        ]
    return hashlib.sha256(b"bulk_failure_guard:" + json_bytes(identity)).hexdigest()


def filter_failed_bulk(row, exhausted):
    specification = BULK_FIELDS.get(row["payload"].get("kind"))
    if specification is None:
        if (
            row["payload"].get("kind") == "resource_growth"
            and bulk_failure_identity(row["domain"], row["world_epoch"], row["payload"])
            in exhausted
        ):
            return None
        return row
    field, _ = specification
    entries = [
        entry
        for entry in row["payload"][field]
        if bulk_failure_identity(row["domain"], row["world_epoch"], entry)
        not in exhausted
    ]
    if not entries:
        return None
    if len(entries) == len(row["payload"][field]):
        return row
    return proposal(
        row["domain"], dict(row["payload"], **{field: entries}), row["world_epoch"]
    )


def split_bulk_proposals(rows):
    result = []
    for row in rows:
        payload = row["payload"]
        specification = BULK_FIELDS.get(payload.get("kind"))
        if specification is None:
            result.append(row)
            continue
        field, _ = specification
        scopes = {}
        for entry in payload[field]:
            source = entry.get("expected", entry.get("ticket", {}))
            scope = entry.get(
                "scope", [source.get("map_id"), source.get("instance_id")]
            )
            scopes.setdefault(tuple(scope), []).append(entry)
        for scope, entries in scopes.items():
            result.append(
                proposal(
                    row["domain"],
                    dict(payload, **{field: entries, "scope": list(scope)}),
                    row["world_epoch"],
                )
            )
    return result


def merge_bulk_payload(original, fresh):
    field, limit = BULK_FIELDS[fresh["kind"]]
    merged = dict(fresh)
    entries = {}
    for entry in original[field] + fresh[field]:
        key = json_bytes(bulk_entry_key(entry))
        if key in entries:
            original_entry = entries[key]
            if fresh["kind"] == "lifecycle_bulk":
                # A retained draw must be reconstructed against the fresh
                # roster; copying its old actor snapshot retains stale cells.
                updated = refresh_stale_decision(original_entry, entry)
            else:
                updated = deepcopy(entry)
                for outcome in ("draw", "group_draw", "child", "member", "grown"):
                    if outcome in original_entry:
                        updated[outcome] = deepcopy(original_entry[outcome])
            if isinstance(updated.get("plan"), dict) and isinstance(
                original_entry.get("plan"), dict
            ):
                for outcome in (
                    "draw",
                    "group_draw",
                    "destination_draw",
                    "variant_order",
                ):
                    if outcome in original_entry["plan"]:
                        updated["plan"][outcome] = deepcopy(
                            original_entry["plan"][outcome]
                        )
            entries[key] = updated
        else:
            candidate = dict(merged, **{field: list(entries.values()) + [entry]})
            if len(entries) >= limit or len(json_bytes(candidate)) > 224 * 1024:
                continue
            entries[key] = entry
    merged[field] = list(entries.values())
    return merged


def proposal_identity(row):
    # Legacy or malformed rows must still reach domain validation instead of
    # preventing unrelated valid work from draining after an upgrade.
    try:
        payload = row["payload"]
        specification = BULK_FIELDS.get(payload.get("kind"))
        if specification is not None:
            field, _ = specification
            scope = payload.get("scope")
            if scope is None:
                entry = payload[field][0]
                source = entry.get("expected", entry.get("ticket", {}))
                scope = entry.get(
                    "scope", [source.get("map_id"), source.get("instance_id")]
                )
            slot = json_bytes(
                [row["world_epoch"], row["domain"], payload["kind"], scope]
            ).decode()
            version = json_bytes(
                [
                    [
                        bulk_entry_key(entry),
                        entry.get("expected_members"),
                        entry.get("configuration"),
                        entry.get("expected"),
                    ]
                    for entry in payload[field]
                ]
            ).decode()
            durable_id = hashlib.sha256((slot + version).encode()).hexdigest()
            return slot, version, durable_id
        if (
            row["domain"] == "population"
            and payload.get("kind") == "initial_population"
        ):
            plan = payload["plan"]
            slot = json_bytes(
                [
                    row["world_epoch"],
                    "initial_population",
                    plan["map_id"],
                    plan["instance_id"],
                    plan["region_id"],
                ]
            ).decode()
            version = json_bytes(
                [
                    payload["scope_digest"],
                    payload["policy"],
                    payload["catalog_revision"],
                ]
            ).decode()
            return slot, version, None
        if row["domain"] == "population" and payload.get("kind") == "corpse_expiry":
            slot = json_bytes(
                [row["world_epoch"], "corpse_expiry", payload["actor_id"]]
            ).decode()
            return slot, row["id"], None
        return _proposal_identity(row)
    except (KeyError, TypeError, ValueError):
        return row["id"], row["id"], None


OWNER_LOCK = 5790545566


def refresh_stale_decision(original, fresh):
    """Refresh live CAS inputs while retaining the first cycle's random draws."""
    refreshed = deepcopy(fresh)
    for key in ("draw", "group_draw", "child", "member"):
        if key in original:
            refreshed[key] = deepcopy(original[key])
    if fresh.get("kind") == "maturation" and "configuration" in fresh:
        from wakfu_server import monster_maturation as maturation
        from wakfu_server import monster_life_plans as life_plans
        from wakfu_server.monsters import owned_instance

        parent = next(
            member
            for member in fresh["expected_members"]
            if member["id"] == fresh["ticket"]["monster_id"]
        )
        decision = fresh.get("ticket", {}).get("decision", {})
        choice = (
            dict(choose=lambda candidates: life_plans.choose(candidates, decision))
            if isinstance(decision, dict) and "variant_seed" in decision
            else {}
        )
        candidate = maturation.choose_next(
            parent["ref"],
            fresh["configuration"],
            draw=refreshed["draw"],
            members=fresh["expected_members"],
            source_level=parent["level"],
            **choice,
        )
        refreshed["grown"] = (
            None
            if candidate is None
            else owned_instance(
                candidate["reference"],
                candidate["min_level"],
                parent["id"],
                map_id=fresh["scope"][0],
                instance_id=fresh["scope"][1],
                team=parent["team"],
                **{key: parent[key] for key in ("x", "y", "z")},
            )
        )
    elif "grown" in original:
        refreshed["grown"] = deepcopy(original["grown"])
    if refreshed.get("child") is not None and "destination" in fresh:
        refreshed["child"].update(zip(("x", "y", "z"), fresh["destination"]))
    if refreshed.get("member") is not None and "expected" in fresh:
        refreshed["member"].update(
            {key: fresh["expected"][key] for key in ("x", "y", "z")}
        )
    return refreshed


class OwnershipLost(RuntimeError):
    """The advisory session must be reacquired before any further work."""


class Repository:
    def __init__(self, store, max_attempts=None):
        self.store = store
        self.owner = None
        self.max_attempts = (
            int(os.environ.get("WAKFU_ECOLOGY_MAX_ATTEMPTS", "3"))
            if max_attempts is None
            else max_attempts
        )
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 100:
            raise ValueError("Invalid ecology maximum attempts")

    def expire_exhausted(self):
        with self.connection() as db:
            return db.execute(
                "UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP, "
                "last_error_code='retry_exhausted' WHERE id IN (SELECT id FROM ecology_service_proposals "
                "WHERE delivered_at IS NULL AND attempts>=%s ORDER BY created_at,id LIMIT 256)",
                (self.max_attempts,),
            ).rowcount

    def retry_stats(self):
        with self.connection() as db:
            return dict(
                db.execute(
                    "SELECT COALESCE(sum(attempts),0)::bigint AS attempts, "
                    "count(*) FILTER (WHERE last_error_code='retry_exhausted') AS exhausted "
                    "FROM ecology_service_proposals"
                ).fetchone()
            )

    def acquire(self):
        database = self.store.database
        connection = connect(
            database.conninfo,
            **database.connection_kwargs,
            autocommit=True,
            connect_timeout=2,
        )
        try:
            connection.execute("SET statement_timeout='1s'")
            owned = connection.execute(
                "SELECT pg_try_advisory_lock(%s) AS owned", (OWNER_LOCK,)
            ).fetchone()["owned"]
        except BaseException:
            connection.close()
            raise
        if not owned:
            connection.close()
            raise RuntimeError("Another ecology worker owns the database")
        self.owner = connection

    def assert_owner(self):
        if self.owner is None:
            raise OwnershipLost("Ecology worker does not own the database")
        # A dead session invalidates ownership. Never reconnect without reacquiring.
        try:
            self.owner.execute("SELECT 1")
        except Exception:
            self.close()
            raise OwnershipLost("Ecology ownership session was lost") from None

    def close(self):
        if self.owner is not None:
            self.owner.close()
            self.owner = None

    @contextmanager
    def connection(self):
        with self.store.connection(timeout=0.5) as db:
            db.execute("SET LOCAL statement_timeout='1s'")
            db.execute("SET LOCAL lock_timeout='250ms'")
            yield db

    def enabled(self):
        with self.connection() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE name='ecology_service_enabled'"
            ).fetchone()
            return row is None or row["value"] is True

    def set_enabled(self, enabled):
        with self.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('ecology_service_enabled',%s) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb(enabled),),
            )

    def dirty(self):
        with self.connection() as db:
            return list(
                db.execute(
                    "SELECT map_id,instance_id,revision FROM ecology_dirty_scopes "
                    "WHERE revision>processed_revision ORDER BY updated_at,map_id,instance_id LIMIT %s",
                    (MAX_SCOPES,),
                ).fetchall()
            )

    def save(self, proposals, dirty):
        proposals = split_bulk_proposals(proposals)
        statistics = dict(
            incoming=len(proposals),
            inserted=0,
            deduplicated=0,
            superseded=0,
            capacity_deferred=0,
            refreshed=0,
        )
        with self.connection() as db:
            pending = db.execute(
                "SELECT id,domain,payload,world_epoch,attempts FROM ecology_service_proposals "
                "WHERE delivered_at IS NULL ORDER BY created_at,id FOR UPDATE"
            ).fetchall()
            guard_ids = [
                bulk_failure_identity(row["domain"], row["world_epoch"], entry)
                for row in list(pending) + proposals
                for entry in (
                    row["payload"][BULK_FIELDS[row["payload"]["kind"]][0]]
                    if row["payload"].get("kind") in BULK_FIELDS
                    else [row["payload"]]
                    if row["payload"].get("kind") == "resource_growth"
                    else []
                )
            ]
            exhausted = set()
            if guard_ids:
                exhausted = {
                    row["id"]
                    for row in db.execute(
                        "SELECT id FROM ecology_service_proposals WHERE id=ANY(%s) AND attempts>=%s",
                        (list(set(guard_ids)), self.max_attempts),
                    ).fetchall()
                }
            slots = {}
            superseded = []
            retained = []
            for existing in pending:
                filtered = filter_failed_bulk(existing, exhausted)
                if filtered is None or filtered["id"] != existing["id"]:
                    superseded.append(existing["id"])
                    if filtered is not None:
                        filtered["attempts"] = existing.get("attempts", 0)
                        proposals.insert(0, filtered)
                else:
                    retained.append(existing)
            pending = retained
            proposals = [
                filtered
                for row in proposals
                if (filtered := filter_failed_bulk(row, exhausted)) is not None
            ]
            proposals = [
                dict(row)
                for row in pending
                if row["payload"].get("kind") in BULK_FIELDS
            ] + proposals
            for existing in pending:
                slot, version, _ = proposal_identity(existing)
                previous = slots.get(slot)
                if previous is not None:
                    if previous[1] == version:
                        superseded.append(existing["id"])
                        statistics["deduplicated"] += 1
                        continue
                    superseded.append(previous[0]["id"])
                slots[slot] = (existing, version)
            for supplied in proposals:
                row = dict(supplied)
                slot, version, decision_id = proposal_identity(row)
                previous = slots.get(slot)
                inherited_attempts = row.get("attempts", 0)
                if previous is not None and row["payload"].get("kind") in BULK_FIELDS:
                    merged = merge_bulk_payload(previous[0]["payload"], row["payload"])
                    row = proposal(row["domain"], merged, row["world_epoch"])
                    slot, version, decision_id = proposal_identity(row)
                    inherited_attempts = previous[0].get("attempts", 0)
                if previous is not None:
                    if previous[1] == version:
                        statistics["deduplicated"] += 1
                        continue
                    # Out-of-order observations cannot replace a newer regional revision.
                    if row["domain"] == "bonuses" and row["payload"].get(
                        "revision", 0
                    ) < previous[0]["payload"].get("revision", 0):
                        statistics["deduplicated"] += 1
                        continue
                    superseded.append(previous[0]["id"])
                else:
                    kind = row["payload"].get("kind")
                    capacity = (
                        MAX_PENDING
                        if kind in ("planting_begin", "planting_rejected")
                        else MAX_PENDING - RESERVED_INTERACTIVE
                        if kind == "resource_growth_bulk"
                        or (kind == "resource_growth" and row["payload"].get("member"))
                        else MAX_PENDING - RESERVED_INTERACTIVE - RESERVED_GROWTH
                    )
                    if len(slots) >= capacity:
                        statistics["capacity_deferred"] += 1
                        continue
                if decision_id is not None:
                    row["id"] = decision_id
                    history = db.execute(
                        "SELECT payload,attempts,last_error_code,delivered_at, "
                        "next_attempt_at<=CURRENT_TIMESTAMP AS due FROM ecology_service_proposals "
                        "WHERE id=%s AND world_epoch=%s FOR UPDATE",
                        (row["id"], row["world_epoch"]),
                    ).fetchone()
                    if history is not None:
                        bulk_kind = row["payload"].get("kind") in BULK_FIELDS
                        pass_complete = history["last_error_code"] in (
                            None,
                            "bulk_pass_complete",
                        )
                        normal_wait_due = (
                            history["last_error_code"] == "normal_wait"
                            and history["due"]
                        )
                        if (
                            bulk_kind
                            and history["delivered_at"] is not None
                            and history["attempts"] < self.max_attempts
                            and (pass_complete or normal_wait_due)
                        ):
                            row["payload"] = merge_bulk_payload(
                                history["payload"], row["payload"]
                            )
                            db.execute(
                                "UPDATE ecology_service_proposals SET payload=%s,delivered_at=NULL, "
                                "last_error_code=NULL,next_attempt_at=CURRENT_TIMESTAMP,created_at=CURRENT_TIMESTAMP WHERE id=%s",
                                (Jsonb(row["payload"]), row["id"]),
                            )
                            row["attempts"] = history["attempts"]
                            slots[slot] = (row, version)
                            statistics["refreshed"] += 1
                            continue
                        changed = history["payload"].get("expected_members") != row[
                            "payload"
                        ].get("expected_members")
                        if (
                            history["last_error_code"] == "stale"
                            and history["attempts"] < self.max_attempts
                            and (changed or history["due"])
                        ):
                            row["payload"] = refresh_stale_decision(
                                history["payload"], row["payload"]
                            )
                            db.execute(
                                "UPDATE ecology_service_proposals SET payload=%s,delivered_at=NULL, "
                                "last_error_code=NULL,next_attempt_at=CURRENT_TIMESTAMP WHERE id=%s",
                                (Jsonb(row["payload"]), row["id"]),
                            )
                            slots[slot] = (row, version)
                            statistics["refreshed"] += 1
                        else:
                            statistics["deduplicated"] += 1
                        continue
                inserted = db.execute(
                    "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,attempts) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET "
                    "world_epoch=EXCLUDED.world_epoch,delivered_at=NULL,attempts=0,last_error_code=NULL,next_attempt_at=CURRENT_TIMESTAMP "
                    "WHERE ecology_service_proposals.world_epoch<>EXCLUDED.world_epoch",
                    (
                        row["id"],
                        row["domain"],
                        Jsonb(row["payload"]),
                        row["world_epoch"],
                        inherited_attempts,
                    ),
                )
                row["attempts"] = inherited_attempts
                statistics["inserted"] += inserted.rowcount
                slots[slot] = (row, version)
            active_ids = {value[0]["id"] for value in slots.values()}
            superseded = [
                identifier for identifier in superseded if identifier not in active_ids
            ]
            if superseded:
                statistics["superseded"] = len(set(superseded))
                db.execute(
                    "UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP, "
                    "last_error_code='superseded' WHERE id=ANY(%s) AND delivered_at IS NULL",
                    (list(dict.fromkeys(superseded)),),
                )
            if dirty and not statistics["capacity_deferred"]:
                db.execute(
                    "UPDATE ecology_dirty_scopes d SET processed_revision=GREATEST(d.processed_revision,x.revision) "
                    "FROM unnest(%s::bigint[],%s::bigint[],%s::bigint[]) AS x(map_id,instance_id,revision) "
                    "WHERE d.map_id=x.map_id AND d.instance_id=x.instance_id",
                    (
                        [row["map_id"] for row in dirty],
                        [row["instance_id"] for row in dirty],
                        [row["revision"] for row in dirty],
                    ),
                )

        if any(
            statistics[key] for key in ("incoming", "superseded", "capacity_deferred")
        ):
            print(
                json.dumps(dict(event="ecology_queue_admission", **statistics)),
                flush=True,
            )
        return statistics

    def pending_count(self):
        with self.connection() as db:
            return db.execute(
                "SELECT count(*) AS count FROM ecology_service_proposals WHERE delivered_at IS NULL"
            ).fetchone()["count"]

    def growth_pending_count(self):
        with self.connection() as db:
            return db.execute(
                "SELECT count(*) AS count FROM ecology_service_proposals WHERE delivered_at IS NULL "
                "AND domain='plants' AND ((payload->>'kind'='resource_growth' "
                "AND jsonb_typeof(payload->'member')='object') OR payload->>'kind'='resource_growth_bulk')"
            ).fetchone()["count"]

    def queue_summary(self):
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT domain,COALESCE(payload->>'kind','context') AS kind,count(*) AS pending, "
                    "round(extract(epoch FROM CURRENT_TIMESTAMP-min(created_at)))::bigint AS oldest_age_seconds, "
                    "min(attempts) AS min_attempts,max(attempts) AS max_attempts "
                    "FROM ecology_service_proposals WHERE delivered_at IS NULL "
                    "GROUP BY domain,payload->>'kind' ORDER BY min(created_at)"
                )
            ]

    def pending(self):
        with self.connection() as db:
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT id,domain,payload,world_epoch FROM ecology_service_proposals "
                    "WHERE delivered_at IS NULL AND next_attempt_at<=CURRENT_TIMESTAMP "
                    "ORDER BY CASE WHEN domain='plants' AND payload->>'kind' IN "
                    "('planting_begin','planting_rejected') THEN 0 "
                    "WHEN domain='plants' AND ((payload->>'kind'='resource_growth' "
                    "AND jsonb_typeof(payload->'member')='object') OR payload->>'kind'='resource_growth_bulk') THEN 1 ELSE 2 END, "
                    "attempts,created_at,id LIMIT %s",
                    (MAX_PROPOSALS,),
                ).fetchall()
            ]
        batch = []
        for row in rows:
            try:
                json_bytes(
                    {"schema_version": SCHEMA_VERSION, "proposals": batch + [row]}
                )
            except ValueError:
                break
            batch.append(row)
        return batch

    def acknowledge(self, results):
        with self.connection() as db:
            for row in results:
                failures = row.get("resource_failures", [])
                if failures:
                    source = db.execute(
                        "SELECT domain,payload,world_epoch FROM ecology_service_proposals "
                        "WHERE id=%s AND delivered_at IS NULL FOR UPDATE",
                        (row["id"],),
                    ).fetchone()
                    if source is not None:
                        entries = source["payload"].get(
                            "resources", [source["payload"]]
                        )
                        by_uid = {
                            entry["expected"]["resource_uid"]: entry
                            for entry in entries
                            if entry.get("kind") == "resource_growth"
                        }
                        for uid in set(failures):
                            entry = by_uid.get(uid)
                            if entry is None:
                                raise ValueError("Unknown failed ecology resource")
                            guard_id = bulk_failure_identity(
                                source["domain"], source["world_epoch"], entry
                            )
                            db.execute(
                                "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,attempts,"
                                "delivered_at,last_error_code) VALUES(%s,%s,%s,%s,1,CURRENT_TIMESTAMP,'bulk_entry_retry') "
                                "ON CONFLICT(id) DO UPDATE SET attempts=LEAST(%s,ecology_service_proposals.attempts+1),"
                                "delivered_at=CURRENT_TIMESTAMP,last_error_code='bulk_entry_retry'",
                                (
                                    guard_id,
                                    source["domain"],
                                    Jsonb(
                                        dict(
                                            kind="bulk_failure_guard",
                                            entry_key=bulk_entry_key(entry),
                                        )
                                    ),
                                    source["world_epoch"],
                                    self.max_attempts,
                                ),
                            )
                # A normal bulk pass is not a failed delivery. Native timers,
                # life plans and seed rows decide whether any operation remains due.
                if row["status"] in ("deferred", "applied", "duplicate", "stale"):
                    outcome = db.execute(
                        "SELECT payload->>'kind' AS kind FROM ecology_service_proposals "
                        "WHERE id=%s AND delivered_at IS NULL FOR UPDATE",
                        (row["id"],),
                    ).fetchone()
                    kind = None if outcome is None else outcome["kind"]
                    if kind in BULK_FIELDS and (
                        row["status"] != "deferred" or kind == "resource_growth_bulk"
                    ):
                        normal_wait = (
                            kind == "resource_growth_bulk"
                            and row["status"] == "deferred"
                        )
                        db.execute(
                            "UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP, "
                            "last_error_code=%s,next_attempt_at=CURRENT_TIMESTAMP+%s*interval '1 second' "
                            "WHERE id=%s AND delivered_at IS NULL",
                            (
                                "normal_wait" if normal_wait else "bulk_pass_complete",
                                5 if normal_wait else 0,
                                row["id"],
                            ),
                        )
                        continue
                if row["status"] == "deferred":
                    # Admission delay is not a failed delivery attempt.
                    db.execute(
                        "UPDATE ecology_service_proposals SET next_attempt_at="
                        "CURRENT_TIMESTAMP+interval '1 second' "
                        "WHERE id=%s AND delivered_at IS NULL",
                        (row["id"],),
                    )
                    continue
                failed_bulk = None
                if row["status"] == "retry":
                    failed_bulk = db.execute(
                        "SELECT domain,payload,world_epoch FROM ecology_service_proposals "
                        "WHERE id=%s AND delivered_at IS NULL FOR UPDATE",
                        (row["id"],),
                    ).fetchone()
                terminal = row["status"] in TERMINAL_STATUSES
                acknowledged = db.execute(
                    "UPDATE ecology_service_proposals SET attempts=attempts+1,last_error_code="
                    "CASE WHEN %s THEN NULL WHEN attempts+1>=%s THEN 'retry_exhausted' ELSE 'retry' END, "
                    "delivered_at=CASE WHEN %s OR attempts+1>=%s THEN CURRENT_TIMESTAMP ELSE delivered_at END, "
                    "next_attempt_at=CASE WHEN %s THEN next_attempt_at ELSE CURRENT_TIMESTAMP+ "
                    "LEAST(30,power(2,LEAST(attempts,5))::integer)*interval '1 second' END "
                    "WHERE id=%s AND delivered_at IS NULL",
                    (
                        terminal,
                        self.max_attempts,
                        terminal,
                        self.max_attempts,
                        terminal,
                        row["id"],
                    ),
                )
                if acknowledged.rowcount and failed_bulk is not None:
                    specification = BULK_FIELDS.get(failed_bulk["payload"].get("kind"))
                    if specification is not None:
                        field, _ = specification
                        for entry in failed_bulk["payload"][field]:
                            guard_id = bulk_failure_identity(
                                failed_bulk["domain"], failed_bulk["world_epoch"], entry
                            )
                            db.execute(
                                "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,attempts,"
                                "delivered_at,last_error_code) VALUES(%s,%s,%s,%s,1,CURRENT_TIMESTAMP,'bulk_entry_retry') "
                                "ON CONFLICT(id) DO UPDATE SET attempts=LEAST(%s,ecology_service_proposals.attempts+1),"
                                "delivered_at=CURRENT_TIMESTAMP,last_error_code='bulk_entry_retry'",
                                (
                                    guard_id,
                                    failed_bulk["domain"],
                                    Jsonb(
                                        dict(
                                            kind="bulk_failure_guard",
                                            entry_key=bulk_entry_key(entry),
                                        )
                                    ),
                                    failed_bulk["world_epoch"],
                                    self.max_attempts,
                                ),
                            )
                if row["status"] == "stale" and acknowledged.rowcount:
                    db.execute(
                        "UPDATE ecology_service_proposals SET last_error_code="
                        "CASE WHEN attempts>=%s THEN 'retry_exhausted' ELSE 'stale' END, "
                        "next_attempt_at=CURRENT_TIMESTAMP+interval '1 second' WHERE id=%s "
                        "AND delivered_at IS NOT NULL",
                        (self.max_attempts, row["id"]),
                    )
            db.execute(
                "DELETE FROM ecology_service_proposals WHERE id IN (SELECT id FROM ("
                "(SELECT id FROM ecology_service_proposals WHERE delivered_at<CURRENT_TIMESTAMP-interval '7 days' "
                "AND COALESCE(payload->>'kind','') NOT IN ('maturation','reproduction','resource_growth','planting_begin','planting_rejected','mineral_refill','fishing_refill','bulk_failure_guard') "
                "ORDER BY delivered_at,id LIMIT 256) UNION "
                "(SELECT id FROM ecology_service_proposals WHERE delivered_at IS NOT NULL "
                "AND COALESCE(payload->>'kind','') NOT IN ('maturation','reproduction','resource_growth','planting_begin','planting_rejected','mineral_refill','fishing_refill','bulk_failure_guard') "
                "ORDER BY delivered_at DESC,id OFFSET 4096 LIMIT 256)) obsolete LIMIT 256)"
            )

    def query(self, request):
        validate_query(request)
        map_id, instance_id = request["map_id"], request["instance_id"]
        region = request.get("region_id")
        with self.connection() as db:
            db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            metadata = db.execute(
                "SELECT clock_timestamp() AS observed_at, "
                "COALESCE((SELECT revision FROM ecology_dirty_scopes WHERE map_id=%s AND instance_id=%s),0) AS revision",
                (map_id, instance_id),
            ).fetchone()
            if request["kind"] == "weather":
                rows = db.execute(
                    "SELECT region_id,weather,revision,updated_at FROM territory_weather "
                    "WHERE map_id=%s AND instance_id=%s "
                    + ("AND region_id=%s " if region else "")
                    + "ORDER BY region_id LIMIT 65",
                    (map_id, instance_id, region) if region else (map_id, instance_id),
                ).fetchall()
                if len(rows) > 64:
                    raise ValueError("Ecology weather query exceeds region budget")
                result = {
                    "regions": [
                        dict(row, updated_at=row["updated_at"].isoformat())
                        for row in rows
                    ]
                }
            else:
                count = db.execute(
                    "SELECT (SELECT count(*) FROM planted_resources WHERE map_id=%s AND instance_id=%s) + "
                    "COALESCE((SELECT sum(jsonb_array_length(members)) FROM combat_groups WHERE map_id=%s AND instance_id=%s "
                    "AND status<>'defeated'),0) AS count",
                    (map_id, instance_id, map_id, instance_id),
                ).fetchone()["count"]
                if count > 4096:
                    raise ValueError("Ecology population query exceeds entity budget")
                from wakfu_server.ecology_population import snapshot

                result = snapshot(db, map_id, instance_id)
                if region is not None:
                    result["regions"] = {region: result["regions"].get(region, {})}
        response = {
            "authoritative": True,
            "kind": request["kind"],
            "map_id": map_id,
            "instance_id": instance_id,
            "revision": metadata["revision"],
            "observed_at": metadata["observed_at"].isoformat(),
            "data": result,
        }
        json_bytes(response)
        return response


class Worker:
    def __init__(
        self,
        repository,
        client,
        domains,
        *,
        interval=1.0,
        clock=time.monotonic,
        wander_interval=None,
        interactive_prepare=None,
        growth_prepare=None,
        proposal_validator=None,
    ):
        if (
            not domains
            or set(domains) - DOMAINS
            or any(not callable(fn) for fn in domains.values())
        ):
            raise ValueError("Invalid ecology domain registry")
        if not 0.1 <= interval <= 60:
            raise ValueError("Invalid ecology poll interval")
        if interactive_prepare is not None and not callable(interactive_prepare):
            raise ValueError("Invalid interactive ecology planner")
        if growth_prepare is not None and not callable(growth_prepare):
            raise ValueError("Invalid reserved growth planner")
        if proposal_validator is not None and not callable(proposal_validator):
            raise ValueError("Invalid ecology proposal validator")
        self.repository, self.client, self.domains = repository, client, dict(domains)
        self.growth_prepare = growth_prepare
        self.interactive_prepare = interactive_prepare
        self.proposal_validator = proposal_validator
        self.interval, self.clock = interval, clock
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.last_progress = clock()
        self.last_success = None
        self.last_error = None
        self.domain_errors = {}
        self.domain_planning_ticks = {}
        self.last_snapshot = None
        self.snapshot_at = None
        self.enabled = True
        self.counters = {
            "ticks": 0,
            "planned": 0,
            "delivered": 0,
            "stale": 0,
            "retries": 0,
            "deferred": 0,
        }
        self.pending = 0
        self.retry_totals = {"attempts": 0, "exhausted": 0}
        self.last_tick_seconds = 0
        self.last_queue_log = float("-inf")
        self.last_locations = []
        self.last_wander = None
        self.last_reserved_growth = float("-inf")
        self.last_mobs_now_ms = None
        self.last_epoch = None
        self.wander_interval = wander_interval or self._configured_wander_interval
        self.query_gate = threading.Semaphore(1)
        self.query_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="ecology-query"
        )

    def _configured_wander_interval(self):
        from wakfu_server.monster_wander import policy

        return policy(self.repository.store)["interval_seconds"]

    def query(self, value):
        validate_query(value)
        if not self.query_gate.acquire(blocking=False):
            raise TimeoutError("Ecology query already running")
        try:
            future = self.query_executor.submit(self.repository.query, value)
        except BaseException:
            self.query_gate.release()
            raise
        future.add_done_callback(lambda _future: self.query_gate.release())
        return future.result(timeout=2)

    def tick(self):
        started = self.clock()
        self.delivery_deadline = time.monotonic() + DRAIN_BUDGET_SECONDS
        self.repository.assert_owner()
        if self.clock() - self.last_queue_log >= 30 and hasattr(
            self.repository, "queue_summary"
        ):
            summary = self.repository.queue_summary()
            if isinstance(summary, list):
                print(
                    json.dumps(
                        dict(
                            event="ecology_queue_summary",
                            queues=summary,
                            counters=dict(self.counters),
                        )
                    ),
                    flush=True,
                )
            self.last_queue_log = self.clock()
        self.enabled = self.repository.enabled()
        if not self.enabled:
            self.domain_errors = {}
            return
        self.repository.expire_exhausted()
        self.retry_totals = self.repository.retry_stats()
        # Retry committed proposals before generating more work during an outage.
        self.repository.save([], [])
        self.drain()
        self.pending = self.repository.pending_count()
        if (
            self.pending >= MAX_PENDING
            and self.interactive_prepare is None
            and self.growth_prepare is None
        ):
            return
        snapshot = self.client.snapshot()
        if snapshot.get("mode", "external") != "external":
            raise RuntimeError("World does not authorize external ecology ownership")
        dirty = self.repository.dirty()
        snapshot = dict(
            snapshot,
            dirty_scopes=[dict(row) for row in dirty],
            planning_tick=self.counters["ticks"],
        )
        epoch = snapshot.get("world_epoch", snapshot.get("epoch"))
        if self.interactive_prepare is not None:
            # Player planting has reserved admission independent of background
            # backlog. The authoritative intent table bounds active requests.
            interactive = self.interactive_prepare(
                self.repository.store, snapshot, limit=4
            )
            if not isinstance(interactive, list) or len(interactive) > 4:
                raise ValueError("Interactive ecology planner exceeded budget")
            interactive_rows = [
                proposal("plants", payload, epoch) for payload in interactive
            ]
            if interactive_rows:
                self.repository.save(interactive_rows, [])
                ready = self.repository.pending()
                if ready:
                    self.deliver(ready)
                self.counters["planned"] += len(interactive_rows)
            snapshot["skip_interactive"] = True
            self.pending = self.repository.pending_count()
        if (
            self.growth_prepare is not None
            and self.clock() - self.last_reserved_growth >= 5
        ):
            self.last_reserved_growth = self.clock()
            # Seed growth must remain plannable when ambient proposals fill their
            # own backlog. A separate bounded lane reserves sixteen monster births.
            growth_pending = (
                self.repository.growth_pending_count()
                if hasattr(self.repository, "growth_pending_count")
                else 0
            )
            capacity = min(4, max(0, 16 - growth_pending))
            if capacity:
                growth = self.growth_prepare(
                    self.repository.store,
                    dict(snapshot, skip_interactive=True, reserve_monster_births=True),
                    limit=capacity,
                )
                if not isinstance(growth, list) or len(growth) > capacity:
                    raise ValueError("Reserved ecology growth planner exceeded budget")
                growth_rows = [proposal("plants", payload, epoch) for payload in growth]
                if growth_rows:
                    self.repository.save(growth_rows, [])
                    self.counters["planned"] += len(growth_rows)
                    ready = self.repository.pending()
                    if ready:
                        self.deliver(ready)
            self.pending = self.repository.pending_count()
        if self.pending >= SOFT_PENDING:
            return
        if epoch != self.last_epoch:
            self.last_locations, self.last_wander, self.last_mobs_now_ms = (
                [],
                None,
                None,
            )
            self.last_epoch = epoch
        now_ms = snapshot.get("now_ms")
        if self.last_mobs_now_ms is not None and (
            not isinstance(now_ms, int) or now_ms < self.last_mobs_now_ms
        ):
            raise ValueError("Ecology snapshot clock moved backwards")
        snapshot["previous_locations"] = self.last_locations
        if "mobs" in self.domains:
            if type(now_ms) is not int or now_ms < 0:
                raise ValueError("Invalid ecology snapshot clock")
            cadence = float(self.wander_interval()) * 1000
            if not cadence > 0:
                raise ValueError("Invalid monster wander cadence")
            snapshot["allow_wander"] = self.last_wander is None or (
                isinstance(now_ms, int) and now_ms - self.last_wander >= cadence
            )
        available = min(MAX_PROPOSALS, MAX_PENDING - self.pending)
        rows = []
        failures = {}
        mobs_prepared = False
        domains = list(self.domains.items())
        offset = self.counters["ticks"] % len(domains) if domains else 0
        domains = domains[offset:] + domains[:offset]
        visited = 0
        for name, prepare in domains:
            if len(rows) >= available:
                break
            visited += 1
            try:
                domain_tick = self.domain_planning_ticks.get(name, 0)
                self.domain_planning_ticks[name] = domain_tick + 1
                prepared = prepare(
                    self.repository.store,
                    dict(
                        snapshot,
                        domain_planning_tick=domain_tick,
                        skip_monster_births=(
                            name == "plants" and self.growth_prepare is not None
                        ),
                    ),
                    limit=available - len(rows),
                )
                if not isinstance(prepared, list) or len(prepared) > available - len(
                    rows
                ):
                    raise ValueError("Ecology domain exceeded proposal budget")
                candidates = [proposal(name, payload, epoch) for payload in prepared]
                # Ensure each pending row can be sent alone within the wire limit.
                for candidate in candidates:
                    json_bytes(
                        {"schema_version": SCHEMA_VERSION, "proposals": [candidate]}
                    )
                rows.extend(candidates)
                if name == "mobs":
                    mobs_prepared = True
            except Exception as error:
                failures[name] = type(error).__name__
        self.repository.assert_owner()
        self.repository.save(rows, [] if failures or visited < len(domains) else dirty)
        if mobs_prepared:
            self.last_locations = snapshot.get("locations", [])
            self.last_mobs_now_ms = now_ms
            if snapshot.get("allow_wander"):
                self.last_wander = now_ms
        self.counters["planned"] += len(rows)
        self.domain_errors = failures
        self.last_snapshot, self.snapshot_at = snapshot, self.clock()
        if rows:
            self.repository.assert_owner()
            self.drain()
        self.pending = self.repository.pending_count()
        self.last_tick_seconds = self.clock() - started

    def drain(self):
        """Drain bounded batches while World admits them, without busy spinning."""
        deadline = getattr(self, "delivery_deadline", None)
        if deadline is None:
            deadline = time.monotonic() + DRAIN_BUDGET_SECONDS
        seen = set()
        for _ in range(MAX_DRAIN_BATCHES):
            if time.monotonic() >= deadline:
                break
            ready = self.repository.pending()
            if not ready:
                break
            identities = frozenset(row["id"] for row in ready)
            if identities & seen:
                break
            seen.update(identities)
            results = self.deliver(ready)
            if not results or any(
                row["status"] in ("deferred", "retry") for row in results
            ):
                break

    def deliver(self, rows):
        self.repository.assert_owner()
        batch = []
        rejected = []
        for row in rows[:MAX_PROPOSALS]:
            if self.proposal_validator is not None and not self.proposal_validator(
                self.repository.store, row
            ):
                rejected.append({"id": row["id"], "status": "stale"})
                continue
            try:
                json_bytes(
                    {"schema_version": SCHEMA_VERSION, "proposals": batch + [row]}
                )
            except ValueError:
                if not batch:
                    raise
                break
            batch.append(row)
        if rejected:
            self.repository.acknowledge(rejected)
            self.counters["stale"] += len(rejected)
        if not batch:
            return rejected or None
        try:
            results = self.client.apply(batch)
        except Exception:
            # An unknown HTTP outcome is still a delivery attempt. Durable CAS
            # receipts protect duplicate application; exhausted rows are archived.
            self.repository.acknowledge(
                [{"id": row["id"], "status": "retry"} for row in batch]
            )
            self.counters["retries"] += len(batch)
            raise
        self.repository.acknowledge(results)
        for row in results:
            self.counters[
                "stale"
                if row["status"] == "stale"
                else "retries"
                if row["status"] == "retry"
                else "deferred"
                if row["status"] == "deferred"
                else "delivered"
            ] += 1
        return rejected + results

    def run(self):
        while not self.stop.is_set():
            try:
                with self.lock:
                    if self.repository.owner is None:
                        self.repository.acquire()
                    self.tick()
                    self.last_success = self.clock()
                    self.last_error = None
            except Exception as error:
                with self.lock:
                    self.last_error = type(error).__name__
            finally:
                with self.lock:
                    self.counters["ticks"] += 1
                    self.last_progress = self.clock()
            self.stop.wait(self.interval)

    def status(self):
        # Nonblocking reads keep health available while a bounded external call runs.
        age = max(0, self.clock() - self.last_progress)
        return {
            "healthy": age <= max(15, self.interval * 3)
            and not self.last_error
            and not self.domain_errors
            and self.pending < MAX_PENDING,
            "enabled": self.enabled,
            "progress_age_seconds": age,
            "last_error": self.last_error,
            "domain_errors": dict(self.domain_errors),
            "pending": self.pending,
            "last_tick_seconds": self.last_tick_seconds,
            "delivery_attempts": self.retry_totals["attempts"],
            "retry_exhausted": self.retry_totals["exhausted"],
            "max_attempts": self.repository.max_attempts,
            "counters": dict(self.counters),
            "domains": sorted(self.domains),
            "cpu_cumulative_seconds": time.process_time(),
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            * (1 if sys.platform == "darwin" else 1024),
        }


class Handler(BaseHTTPRequestHandler):
    worker = None
    token = None

    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, *args):
        pass

    def reply(self, code, value):
        body = json_bytes(value, limit=1024 * 1024)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            self.close_connection = True

    def authorized(self):
        received = self.headers.get("Authorization", "")
        if not hmac.compare_digest(
            received.encode(), ("Bearer " + self.token).encode()
        ):
            self.reply(401, {"error": "Unauthorized"})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        if self.path in ("/health", "/status", "/metrics"):
            status = self.worker.status()
            return self.reply(
                503 if self.path == "/health" and not status["healthy"] else 200, status
            )
        if self.path == "/query":
            return self.reply(
                200,
                {
                    "authoritative": False,
                    "snapshot": self.worker.last_snapshot,
                    "age_seconds": None
                    if self.worker.snapshot_at is None
                    else self.worker.clock() - self.worker.snapshot_at,
                },
            )
        self.reply(404, {"error": "Unknown endpoint"})

    def do_POST(self):
        if not self.authorized():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_BODY_BYTES:
                raise ValueError("Invalid request size")
            value = bounded_json(self.rfile.read(length) or b"{}")
            if self.path == "/query":
                return self.reply(200, self.worker.query(value))
            if value != {}:
                raise ValueError("No request fields accepted")
            if self.path not in ("/pause", "/resume"):
                return self.reply(404, {"error": "Unknown endpoint"})
            enabled = self.path == "/resume"
            self.worker.repository.set_enabled(enabled)
            self.reply(200, {"enabled": enabled})
        except (ValueError, TypeError):
            self.reply(400, {"error": "Invalid request"})
        except Exception:
            self.reply(503, {"error": "Ecology control unavailable"})


def main():
    from wakfu_server.store import Store
    from wakfu_server.native_catalog import release

    os.umask(0o077)
    token = Path(os.environ["WAKFU_ECOLOGY_TOKEN_FILE"]).read_text().strip()
    if not token:
        raise ValueError("Ecology credential is required")
    if not os.environ.get("WAKFU_CATALOG_REVISION"):
        raise ValueError("Pinned ecology catalog revision is required")
    release()
    store = Store(os.environ["WAKFU_DATABASE_URL"])
    repository = Repository(store)
    repository.acquire()
    modules = {
        "plants": "wakfu_server.ecology_plants",
        "mobs": "wakfu_server.ecology_mobs",
        "weather": "wakfu_server.ecology_weather",
        "population": "wakfu_server.ecology_population",
        "bonuses": "wakfu_server.territory_bonus_updates",
    }
    modules.update(json.loads(os.environ.get("WAKFU_ECOLOGY_DOMAIN_MODULES", "{}")))
    domains = {
        name: importlib.import_module(module).prepare
        for name, module in modules.items()
    }
    worker = Worker(
        repository,
        EcologyClient(os.environ.get("WAKFU_WORLD_URL", "http://world:18081"), token),
        domains,
        interval=float(os.environ.get("WAKFU_ECOLOGY_POLL_SECONDS", "1")),
        growth_prepare=domains["plants"],
        interactive_prepare=importlib.import_module(
            "wakfu_server.ecology_planting_intents"
        ).prepare_intents,
        proposal_validator=importlib.import_module(
            "wakfu_server.monster_home_delivery"
        ).validate_proposal,
    )
    Handler.worker, Handler.token = worker, token
    server = ThreadingHTTPServer(
        (os.environ.get("WAKFU_ECOLOGY_BIND", "0.0.0.0"), 8093), Handler
    )
    server.daemon_threads = True
    thread = threading.Thread(target=worker.run, name="ecology-worker", daemon=True)
    thread.start()

    def terminate(_signal, _frame):
        worker.stop.set()
        thread.join(timeout=8)
        repository.close()
        store.close()
        server.server_close()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        server.serve_forever()
    finally:
        worker.stop.set()
        repository.close()
        store.close()


if __name__ == "__main__":
    main()
