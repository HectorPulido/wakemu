"""Authenticated objective management API and independent durable event worker."""
import hmac
import json
import logging
import os
from pathlib import Path
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import psycopg
from psycopg.rows import dict_row
from wakfu_server.objectives import repository, reward_policies, rankings

LOG = logging.getLogger("objectives")
DATABASE_URL = os.environ.get("WAKFU_DATABASE_URL", "")


def connection_options():
    filename = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    return {"password": Path(filename).read_text().strip()} if filename else {}


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, **connection_options())


def status(db):
    row = db.execute(
        "SELECT count(*) FILTER(WHERE processed_at IS NULL AND attempts<5) AS pending,count(*) FILTER(WHERE processed_at IS NULL AND attempts>=5) AS quarantined FROM objectives_events"
    ).fetchone()
    diagnostics = db.execute(
        "SELECT key,value,updated_at FROM objectives_service_state ORDER BY key"
    ).fetchall()
    return {
        "status": "degraded" if diagnostics or row["quarantined"] else "ok",
        **row,
        "diagnostics": diagnostics,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        LOG.info(fmt, *args)

    def send_json(self, status_code, value):
        body = json.dumps(
            value,
            default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v),
        ).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        token = self.server.token
        return hmac.compare_digest(
            self.headers.get("Authorization", ""), "Bearer " + token
        )

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def do_PUT(self):
        self.handle_request(True)

    def do_OPTIONS(self):
        self.handle_request(False)

    def handle_request(self, mutation):
        path = urlsplit(self.path).path
        if path == "/player" or path.startswith(("/player/", "/player-api/")):
            from wakfu_server.objectives.player_http import dispatch

            return dispatch(self, connect, Path(__file__).resolve().parent / "static")
        if not self.authorized():
            return self.send_json(401, {"error": "Unauthorized"})
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        try:
            with connect() as db:
                if (
                    parsed.path == "/v1/player/gamedock-launch"
                    and self.command == "POST"
                ):
                    from wakfu_server.objectives import gamedock, player_auth
                    from wakfu_server.storage.store import Store

                    size = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= size <= 4096:
                        raise ValueError("Invalid request size")
                    credentials = json.loads(self.rfile.read(size))
                    store = Store(DATABASE_URL)
                    try:
                        result = gamedock.launch(store, credentials)
                    except player_auth.Unauthorized:
                        return self.send_json(
                            401, {"error": "Native account verification failed"}
                        )
                    finally:
                        store.close()
                    return self.send_json(200, result)
                if not mutation and parsed.path == "/health":
                    return self.send_json(200, status(db))
                if parsed.path == "/v1/challenge-profiles" and not mutation:
                    from wakfu_server.objectives.challenges_profiles import (
                        list_profiles,
                    )

                    return self.send_json(200, {"items": list_profiles(db)})
                if (
                    mutation
                    and self.command == "PUT"
                    and parsed.path.startswith("/v1/challenge-profiles/")
                ):
                    from wakfu_server.objectives.challenges_profiles import put_profile

                    size = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= size <= 131072:
                        raise ValueError("Invalid request size")
                    request = json.loads(self.rfile.read(size))
                    if type(request) is not dict or set(request) - {
                        "definition",
                        "expected_revision",
                        "operator",
                    }:
                        raise ValueError("Unexpected challenge profile fields")
                    definition = request["definition"]
                    if definition["key"] != unquote(
                        parsed.path[len("/v1/challenge-profiles/") :]
                    ):
                        raise ValueError("Challenge profile URL key mismatch")
                    result = put_profile(db, definition, request["expected_revision"])
                    db.commit()
                    return self.send_json(200, result)
                if (
                    mutation
                    and self.command == "PUT"
                    and parsed.path.startswith("/v1/reward-policies/")
                ):
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= size <= 131072:
                        raise ValueError("Invalid request size")
                    request = json.loads(self.rfile.read(size))
                    if type(request) is not dict or set(request) - {
                        "policy",
                        "expected_revision",
                        "operator",
                    }:
                        raise ValueError("Unexpected reward policy fields")
                    result = reward_policies.put_policy(
                        db,
                        unquote(parsed.path[len("/v1/reward-policies/") :]),
                        request["policy"],
                        request["expected_revision"],
                        request.get("operator", "api"),
                    )
                    db.commit()
                    return self.send_json(200, result)
                if not mutation and parsed.path == "/v1/reward-policies":
                    return self.send_json(
                        200, {"items": reward_policies.list_policies(db)}
                    )
                if not mutation and parsed.path == "/v1/rankings":
                    return self.send_json(
                        200,
                        {
                            "items": rankings.list_rankings(
                                db,
                                query.get("week", [None])[0],
                                query.get("bracket", [None])[0],
                                int(query.get("limit", ["100"])[0]),
                            )
                        },
                    )
                if (
                    mutation
                    and self.command == "POST"
                    and parsed.path.startswith("/v1/events/")
                    and parsed.path.endswith("/retry")
                ):
                    event_id = int(parsed.path.split("/")[3])
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 <= size <= 4096:
                        raise ValueError("Invalid request size")
                    request = json.loads(self.rfile.read(size)) if size else {}
                    if type(request) is not dict or set(request) - {"operator"}:
                        raise ValueError("Unexpected retry fields")
                    row = db.execute(
                        "SELECT id,character_id,attempts FROM objectives_events WHERE id=%s AND processed_at IS NULL FOR UPDATE",
                        (event_id,),
                    ).fetchone()
                    if row is None:
                        return self.send_json(404, {"error": "Pending event not found"})
                    db.execute(
                        "INSERT INTO objectives_event_retries(event_id,operator,previous_attempts) VALUES(%s,%s,%s)",
                        (
                            event_id,
                            str(request.get("operator", "api"))[:256],
                            row["attempts"],
                        ),
                    )
                    db.execute(
                        "UPDATE objectives_events SET attempts=0,error=NULL WHERE id=%s",
                        (event_id,),
                    )
                    db.execute(
                        "SELECT pg_notify('wakemu_objectives_events',%s)",
                        (str(row["character_id"]),),
                    )
                    db.commit()
                    return self.send_json(200, {"id": event_id, "status": "pending"})
                if (
                    mutation
                    and self.command == "PUT"
                    and parsed.path.startswith("/v1/definitions/")
                ):
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= size <= 131072:
                        raise ValueError("Invalid request size")
                    request = json.loads(self.rfile.read(size))
                    if set(request) - {"definition", "expected_revision", "operator"}:
                        raise ValueError("Unexpected request fields")
                    definition = request["definition"]
                    if definition["key"] != unquote(
                        parsed.path[len("/v1/definitions/") :]
                    ):
                        raise ValueError("Definition URL key mismatch")
                    result = repository.put_definition(
                        db, definition, request["expected_revision"]
                    )
                    db.execute(
                        "INSERT INTO objectives_definition_audit(definition_key,revision,operator,definition) VALUES(%s,%s,%s,%s)",
                        (
                            definition["key"],
                            result["revision"],
                            str(request.get("operator", "api"))[:256],
                            psycopg.types.json.Jsonb(result["definition"]),
                        ),
                    )
                    db.commit()
                    return self.send_json(200, result)
                if mutation:
                    return self.send_json(404, {"error": "Unknown route"})
                if parsed.path == "/v1/definitions":
                    return self.send_json(
                        200, {"items": repository.list_definitions(db)}
                    )
                if parsed.path == "/v1/progress":
                    return self.send_json(
                        200,
                        {
                            "items": repository.list_progress(
                                db, int(query["character_id"][0])
                            )
                        },
                    )
                if parsed.path in {"/v1/events", "/v1/rewards"}:
                    limit = int(query.get("limit", ["100"])[0])
                    if not 1 <= limit <= 1000:
                        raise ValueError("Limit must be 1 to 1000")
                    table = (
                        "objectives_events"
                        if parsed.path.endswith("events")
                        else "objectives_rewards"
                    )
                    clauses, values = [], []
                    if "character_id" in query:
                        clauses.append("character_id=%s")
                        values.append(int(query["character_id"][0]))
                    if "before_id" in query and table == "objectives_events":
                        clauses.append("id<%s")
                        values.append(int(query["before_id"][0]))
                    where = " WHERE " + " AND ".join(clauses) if clauses else ""
                    order = (
                        "id DESC"
                        if table == "objectives_events"
                        else "created_at DESC,character_id,definition_key,period_key,reward_index"
                    )
                    rows = db.execute(
                        "SELECT * FROM "
                        + table
                        + where
                        + " ORDER BY "
                        + order
                        + " LIMIT %s",
                        (*values, limit),
                    ).fetchall()
                    return self.send_json(200, {"items": rows})
                return self.send_json(404, {"error": "Unknown route"})
        except repository.ConflictError as exc:
            self.send_json(409, {"error": str(exc)})
        except (ValueError, KeyError, TypeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception:
            LOG.exception("Objective API request failed")
            self.send_json(503, {"error": "Objective service unavailable"})


def tick_coordinator(db, key, callback):
    """Keep one coordinator failure from rolling back accepted objective facts."""
    try:
        with db.transaction():
            callback(db)
        db.execute("DELETE FROM objectives_service_state WHERE key=%s", (key,))
    except Exception as exc:
        LOG.exception("Objective coordinator failed: %s", key)
        db.execute(
            "INSERT INTO objectives_service_state(key,value) VALUES(%s,%s) "
            "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,updated_at=CURRENT_TIMESTAMP",
            (key, psycopg.types.json.Jsonb({"error": str(exc)[:2048]})),
        )


def tick_pvp(db):
    from wakfu_server.objectives import pvp

    tick_coordinator(db, "pvp_scheduler_error", pvp.tick)


def worker():
    from wakfu_server.objectives import assignments, hunts

    while True:
        try:
            with psycopg.connect(
                DATABASE_URL, autocommit=True, **connection_options()
            ) as listener:
                listener.execute("LISTEN wakemu_objectives_events")
                while True:
                    with connect() as db:
                        result = repository.process_batch(db)
                        tick_coordinator(
                            db, "assignment_scheduler_error", assignments.ensure_online
                        )
                        tick_coordinator(db, "hunt_scheduler_error", hunts.tick)
                        tick_pvp(db)
                    if result["processed"] + result["failed"] >= 100:
                        continue
                    # Notifications wake immediately; bounded timeout covers restart/loss.
                    for _ in listener.notifies(timeout=0.5, stop_after=1):
                        break
        except Exception:
            LOG.exception("Objective worker reconnecting after failure")
            time.sleep(1)


def main():
    logging.basicConfig(level=logging.INFO)
    token = Path(os.environ["WAKFU_OBJECTIVES_TOKEN_FILE"]).read_text().strip()
    if len(token) < 32:
        raise ValueError("Objective service token must contain at least 32 characters")
    threading.Thread(target=worker, daemon=True, name="objective-evaluator").start()
    server = ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("WAKFU_OBJECTIVES_PORT", "8094"))), Handler
    )
    server.token = token
    server.serve_forever()


if __name__ == "__main__":
    main()
