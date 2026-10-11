"""Independent ecology planner with durable bounded delivery and no inline fallback."""
import hmac
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

MAX_PENDING = 256
OWNER_LOCK = 5790545566


class OwnershipLost(RuntimeError):
    """The advisory session must be reacquired before any further work."""


class Repository:
    def __init__(self, store, max_attempts=None):
        self.store = store
        self.owner = None
        self.max_attempts = (
            int(os.environ.get("WAKFU_ECOLOGY_MAX_ATTEMPTS", "5"))
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
            connect_timeout=2
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
        with self.connection() as db:
            for row in proposals:
                db.execute(
                    "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch) "
                    "VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET "
                    "world_epoch=EXCLUDED.world_epoch,delivered_at=NULL,attempts=0,last_error_code=NULL,next_attempt_at=CURRENT_TIMESTAMP "
                    "WHERE ecology_service_proposals.world_epoch<>EXCLUDED.world_epoch",
                    (
                        row["id"],
                        row["domain"],
                        Jsonb(row["payload"]),
                        row["world_epoch"],
                    ),
                )
            if dirty:
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

    def pending_count(self):
        with self.connection() as db:
            return db.execute(
                "SELECT count(*) AS count FROM ecology_service_proposals WHERE delivered_at IS NULL"
            ).fetchone()["count"]

    def pending(self):
        with self.connection() as db:
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT id,domain,payload,world_epoch FROM ecology_service_proposals "
                    "WHERE delivered_at IS NULL AND next_attempt_at<=CURRENT_TIMESTAMP "
                    "ORDER BY attempts,created_at,id LIMIT %s",
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
                terminal = row["status"] in TERMINAL_STATUSES
                db.execute(
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
            db.execute(
                "DELETE FROM ecology_service_proposals WHERE id IN (SELECT id FROM ("
                "(SELECT id FROM ecology_service_proposals WHERE delivered_at<CURRENT_TIMESTAMP-interval '7 days' "
                "ORDER BY delivered_at,id LIMIT 256) UNION "
                "(SELECT id FROM ecology_service_proposals WHERE delivered_at IS NOT NULL "
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
        wander_interval=None
    ):
        if (
            not domains
            or set(domains) - DOMAINS
            or any(not callable(fn) for fn in domains.values())
        ):
            raise ValueError("Invalid ecology domain registry")
        if not 0.1 <= interval <= 60:
            raise ValueError("Invalid ecology poll interval")
        self.repository, self.client, self.domains = repository, client, dict(domains)
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
        }
        self.pending = 0
        self.retry_totals = {"attempts": 0, "exhausted": 0}
        self.last_tick_seconds = 0
        self.last_locations = []
        self.last_wander = None
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
        self.repository.assert_owner()
        self.enabled = self.repository.enabled()
        if not self.enabled:
            self.domain_errors = {}
            return
        self.repository.expire_exhausted()
        self.retry_totals = self.repository.retry_stats()
        # Retry committed proposals before generating more work during an outage.
        pending = self.repository.pending()
        if pending:
            self.deliver(pending)
        self.pending = self.repository.pending_count()
        if self.pending >= MAX_PENDING:
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
        offset = self.counters["ticks"] % len(domains)
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
                    dict(snapshot, domain_planning_tick=domain_tick),
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
            ready = self.repository.pending()
            if ready:
                self.deliver(ready)
        self.pending = self.repository.pending_count()
        self.last_tick_seconds = self.clock() - started

    def deliver(self, rows):
        self.repository.assert_owner()
        batch = []
        for row in rows[:MAX_PROPOSALS]:
            try:
                json_bytes(
                    {"schema_version": SCHEMA_VERSION, "proposals": batch + [row]}
                )
            except ValueError:
                if not batch:
                    raise
                break
            batch.append(row)
        if not batch:
            return
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
                else "delivered"
            ] += 1

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
