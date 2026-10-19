"""Bounded live-world validation for externally prepared ecology changes.

Snapshots and commits never call the worker. Explicit read queries are allowed
only outside gameplay locks; domain planners remain in the ecology process.
"""
import hmac
import threading
import time
import uuid
from datetime import datetime

from .protocol import SCHEMA_VERSION, MAX_SCOPES, validate_proposals, validate_query
from .priority import InteractivePriority, is_interactive

STALE_DOMAIN_STATUSES = frozenset(
    {
        "absent",
        "harvesting",
        "occupied",
        "stale_epoch",
        "stale_policy",
        "stale_group",
    }
)


class EcologyBusy(RuntimeError):
    pass


class EcologyWorldBridge:
    def __init__(
        self,
        *,
        store,
        world,
        groups,
        harvests,
        plantings,
        token,
        mode="external",
        record=lambda **fields: None,
        clock=time.time,
        combat_sessions=None,
        ecology_client=None,
        background_limit=16,
        background_budget_seconds=0.025,
        monotonic=time.monotonic,
    ):
        if mode not in ("inline", "external", "disabled"):
            raise ValueError("Invalid ecology execution mode")
        if mode == "external" and (not isinstance(token, str) or not token.strip()):
            raise ValueError("External ecology credential is required")
        self.store, self.world, self.groups = store, world, groups
        self.harvests, self.plantings = harvests, plantings
        self.combat_sessions = combat_sessions
        self.ecology_client = ecology_client
        self.token, self.mode, self.record, self.clock = token, mode, record, clock
        self.epoch = uuid.uuid4().hex
        self.plantings.ecology_world_epoch = self.epoch
        self.gate = threading.Lock()
        if type(background_limit) is not int or not 1 <= background_limit <= 16:
            raise ValueError("Invalid ecology background limit")
        if not 0 < background_budget_seconds <= 1:
            raise ValueError("Invalid ecology background budget")
        self.priority = InteractivePriority()
        self.background_limit = background_limit
        self.background_budget_seconds = background_budget_seconds
        self.monotonic = monotonic
        self.scope_offset = 0
        self.handlers = {}

    def interactive(self):
        """Mark a player request before it waits for gameplay locks."""
        return self.priority.interactive()

    def query(self, kind, map_id, instance_id, region=None):
        """Read current ecology on demand; never block a gameplay critical section."""
        request = {"kind": kind, "map_id": map_id, "instance_id": instance_id}
        if region is not None:
            request["region_id"] = region
        validate_query(request)
        for owner in (self.world, self.groups, self.harvests):
            lock = getattr(owner, "lock", None)
            if lock is None:
                continue
            owned = getattr(lock, "_is_owned", None)
            if callable(owned):
                held = owned()
            else:
                # Plain locks cannot identify their owner; conservatively refuse
                # any held lock instead of risking an HTTP call in a critical section.
                locked = getattr(lock, "locked", None)
                if not callable(locked):
                    raise RuntimeError("Cannot verify ecology query lock ownership")
                held = locked()
            if held:
                raise RuntimeError("Ecology queries are forbidden under gameplay locks")
        if self.mode != "external" or self.ecology_client is None:
            raise RuntimeError("External ecology queries are unavailable")
        result = self.ecology_client.query(kind, map_id, instance_id, region_id=region)
        if (
            not isinstance(result, dict)
            or result.get("authoritative") is not True
            or result.get("kind") != kind
            or result.get("map_id") != map_id
            or result.get("instance_id") != instance_id
            or type(result.get("revision")) is not int
            or result["revision"] < 0
            or not isinstance(result.get("data"), dict)
        ):
            raise ValueError("Ecology query returned invalid authority or scope")
        try:
            observed = datetime.fromisoformat(result["observed_at"])
            if observed.tzinfo is None:
                raise ValueError("Ecology observation lacks timezone")
            age = self.clock() - observed.timestamp()
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("Invalid ecology observation time") from None
        if not -2 <= age <= 5:
            raise ValueError("Ecology query returned a stale observation")
        return result

    def authorized(self, header):
        expected = "Bearer " + self.token
        return (
            bool(self.token)
            and isinstance(header, str)
            and hmac.compare_digest(header.encode(), expected.encode())
        )

    def snapshot(self):
        # Intents inserted during this snapshot belong to the next observation.
        started_at_ms = int(self.clock() * 1000)
        # Only current player coordinates and occupation identities cross this
        # boundary. Character inventories, secrets and credentials never do.
        players = self.world.ecology_snapshot()
        if len(players) > 2048:
            raise EcologyBusy("Ecology player snapshot exceeds configured capacity")
        positions = [
            {
                key: player[key]
                for key in (
                    "id",
                    "account_id",
                    "map_id",
                    "instance_id",
                    "x",
                    "y",
                    "z",
                    "presence_generation",
                )
                if key in player
            }
            for player in players
        ]
        scopes = sorted({(row["map_id"], row["instance_id"]) for row in positions})
        if len(scopes) > MAX_SCOPES:
            offset = self.scope_offset % len(scopes)
            scopes = (scopes + scopes)[offset : offset + MAX_SCOPES]
            self.scope_offset = offset + MAX_SCOPES
        with self.harvests.lock:
            excluded = sorted(self.harvests.targets)
        return {
            "schema_version": SCHEMA_VERSION,
            "epoch": self.epoch,
            "world_epoch": self.epoch,
            "mode": self.mode,
            "scopes": [list(scope) for scope in scopes],
            "locations": [list(scope) for scope in scopes],
            "players": positions,
            "excluded_ids": excluded,
            "started_at_ms": started_at_ms,
            "now_ms": int(self.clock() * 1000),
            "growth_seconds": self.plantings.growth_seconds,
            "open_test_policy": self.plantings.open_test_policy,
            "open_planting": self.plantings.open_test_policy,
        }

    def apply(self, envelope):
        proposals = validate_proposals(envelope)
        if not self.gate.acquire(blocking=False):
            self.record(event="ecology_admission_busy", proposals=len(proposals))
            raise EcologyBusy("Ecology commit worker is busy")
        try:
            results = {}
            diagnostics = []
            batch_started = time.monotonic()
            background_count = 0
            background_started = self.monotonic()
            ordered = sorted(proposals, key=lambda row: not is_interactive(row))
            for row in ordered:
                row_started = time.monotonic()
                admission_reason = None
                if self.mode != "external" or row["world_epoch"] != self.epoch:
                    result = {"status": "stale"}
                elif (
                    not is_interactive(row)
                    and row["payload"].get("world_epoch") == self.epoch
                    and (
                        self.priority.interactive_active
                        or background_count >= self.background_limit
                        or (
                            background_count
                            and self.monotonic() - background_started
                            >= self.background_budget_seconds
                        )
                    )
                ):
                    result = {"status": "deferred"}
                    admission_reason = (
                        "player_active"
                        if self.priority.interactive_active
                        else "background_count"
                        if background_count >= self.background_limit
                        else "background_time"
                    )
                else:
                    if not is_interactive(row):
                        if background_count == 0:
                            background_started = self.monotonic()
                        background_count += 1
                    try:
                        payload = row["payload"]
                        if payload.get("world_epoch") != self.epoch:
                            result = {"status": "stale"}
                        else:
                            handler = self.handlers.get(row["domain"])
                            if handler is None:
                                result = {"status": "retry"}
                            else:
                                self.record(
                                    event="ecology_handler_started",
                                    proposal_id=row["id"],
                                    domain=row["domain"],
                                    kind=payload.get("kind"),
                                    scope=payload.get("scope"),
                                    resource_uid=payload.get("resource_uid")
                                    or (
                                        payload["expected"].get("resource_uid")
                                        if isinstance(payload.get("expected"), dict)
                                        else None
                                    )
                                    or (
                                        payload["resource"].get("resource_uid")
                                        if isinstance(payload.get("resource"), dict)
                                        else None
                                    ),
                                )
                                result = handler(payload)
                        if not isinstance(result, dict):
                            raise ValueError("Invalid ecology domain result")
                        status = result.get("status")
                        if status is None:
                            status = "applied" if result.get("applied") else "stale"
                        if isinstance(status, str) and status in STALE_DOMAIN_STATUSES:
                            # These plans lost a live CAS fence. Replanning uses a
                            # fresh snapshot; retrying the same envelope cannot help.
                            self.record(
                                event="ecology_proposal_stale",
                                domain=row["domain"],
                                rejected_status=status,
                            )
                            status = "stale"
                        waiting = (
                            status == "deferred"
                            and row["domain"] == "plants"
                            and payload.get("kind")
                            in ("resource_growth", "resource_growth_bulk")
                            and result.get("reason")
                            in ("occupied", "not_due", "capacity")
                        )
                        if waiting:
                            admission_reason = result["reason"]
                        if (
                            status not in ("applied", "duplicate", "stale", "retry")
                            and not waiting
                        ):
                            self.record(
                                event="ecology_domain_status_rejected",
                                domain=row["domain"],
                                rejected_status=status[:64]
                                if isinstance(status, str)
                                else type(status).__name__,
                            )
                            raise ValueError("Invalid ecology domain status")
                        failures = result.get("resource_failures", [])
                        if (
                            not isinstance(failures, list)
                            or len(failures) > 64
                            or any(
                                type(uid) is not int or not 0 < uid < 2**63
                                for uid in failures
                            )
                            or len(set(failures)) != len(failures)
                        ):
                            raise ValueError("Invalid ecology resource failures")
                        result = {"status": status}
                        if failures:
                            result["resource_failures"] = failures
                    except Exception as error:
                        self.record(
                            event="ecology_apply_failed",
                            proposal_id=row["id"],
                            domain=row["domain"],
                            kind=row["payload"].get("kind"),
                            scope=row["payload"].get("scope"),
                            error_type=type(error).__name__,
                            reason=str(error)[:256]
                            if isinstance(error, ValueError)
                            else None,
                        )
                        result = {"status": "retry"}
                results[row["id"]] = {"id": row["id"], **result}
                diagnostics.append(
                    dict(
                        proposal_id=row["id"],
                        domain=row["domain"],
                        kind=row["payload"].get("kind"),
                        status=result["status"],
                        admission_reason=admission_reason,
                        elapsed_ms=round((time.monotonic() - row_started) * 1000, 3),
                    )
                )
            self.record(
                event="ecology_apply_batch",
                results=diagnostics,
                elapsed_ms=round((time.monotonic() - batch_started) * 1000, 3),
            )
            return {
                "schema_version": SCHEMA_VERSION,
                "results": [results[row["id"]] for row in proposals],
            }
        finally:
            self.gate.release()
