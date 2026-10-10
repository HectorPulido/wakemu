"""Safe per-request correlation and bounded own-state summaries.

The context contains diagnostic IDs, never session authorization generations,
credentials or wire payloads. Engine diagnostics can use request_context().
"""
from contextvars import ContextVar
import re, time, traceback, uuid

ACTIONS = {
    13130: "start_fight",
    12523: "placement_ready",
    13260: "cast_spell",
    12161: "combat_move",
    12403: "end_turn",
    13510: "turn_ack",
    13332: "fight_recovery",
    13952: "abandon_fight",
    12772: "save_build",
    12490: "destroy_item",
    12659: "use_item",
    12804: "move_inventory_item",
    12656: "equip_bag",
    13673: "remove_bag",
    13686: "travel",
    12296: "travel_coordinates",
    13331: "world_move",
    12366: "chat",
    13220: "plant",
    13429: "plant_occupation",
    12767: "pet_feed",
    13826: "bag_furniture_place",
    13578: "bag_visit",
    12925: "fight_terminal_ack",
}


def safe_snapshot(callback):
    try:
        from wakfu_server.performance_profiler import PROFILER

        with PROFILER.span("diagnostics.state_snapshot"):
            return callback()
    except Exception as error:
        return {"diagnostic_snapshot_error": type(error).__name__}


_current = ContextVar("local_request_diagnostic", default=None)
_SECRET_KEYS = {
    "password",
    "password_hash",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "credentials",
    "secret",
    "generation",
    "body",
    "raw",
    "payload",
    "payload_hex",
    "payload_base64",
}
_LABELLED_SECRET = re.compile(
    r'(?i)(\b(?:password|passwd|token|access_token|refresh_token|authorization)\b\s*[:=]\s*)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+")


def redact(value, key=""):
    lowered = key.lower()
    if lowered in _SECRET_KEYS or lowered.endswith(
        (
            "_password",
            "_token",
            "_secret",
            "_payload",
            "_payload_hex",
            "_payload_base64",
        )
    ):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, bytes):
        return {"bytes": len(value), "content": "[redacted]"}
    if isinstance(value, str):
        return _LABELLED_SECRET.sub(
            r"\1[redacted]", _BEARER.sub("Bearer [redacted]", value)
        )[:4096]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return type(value).__name__


def request_context():
    active = _current.get()
    return (
        {}
        if active is None
        else dict(
            request_id=active.id,
            connection_id=active.connection_id,
            request_opcode=active.opcode,
            request_action=active.action,
        )
    )


def current_request():
    return _current.get()


def state_summary(character, fight, runtime=None):
    result = {}
    if character is not None:
        result["character"] = {
            key: character.get(key)
            for key in (
                "id",
                "breed",
                "level",
                "map_id",
                "instance_id",
                "x",
                "y",
                "z",
                "hp",
                "max_hp",
            )
        }
        result["build_indices"] = sorted(character.get("builds", {}))
        items = character.get("inventory_items", ())
        result["inventory_units"] = len(items)
        result["inventory"] = [
            {
                key: item.get(key)
                for key in ("uid", "reference", "quantity", "container", "slot")
            }
            for item in items[:128]
        ]
        result["inventory_omitted"] = max(0, len(items) - 128)
        result["equipment"] = []
        equipment_count = 0
        from wakfu_server.wire import proto_fields

        for index, build in sorted(character.get("builds", {}).items()):
            try:
                for tag, value in proto_fields(
                    bytes.fromhex(build.get("equipment", ""))
                ):
                    if tag == 10:
                        row = dict(proto_fields(value))
                        equipment_count += 1
                        if len(result["equipment"]) < 96:
                            result["equipment"].append(
                                {"build": index, "uid": row.get(8), "slot": row.get(16)}
                            )
            except (ValueError, TypeError):
                result["equipment_summary_error"] = "Invalid stored equipment encoding"
        result["equipment_omitted"] = max(0, equipment_count - 96)
    if fight is not None:
        result["fight"] = {
            "id": fight.id,
            "phase": fight.phase,
            "turn_id": fight.turn_id,
            "current_actor": None if fight.current is None else fight.current.id,
            "winner": getattr(fight, "winner", None),
            "actors": [],
        }
        actors = sorted(fight.actors.values(), key=lambda a: a.id)
        result["fight"]["actor_total"] = len(actors)
        result["fight"]["actors_omitted"] = max(0, len(actors) - 64)
        for actor in actors[:64]:
            result["fight"]["actors"].append(
                {
                    "id": actor.id,
                    "team": actor.team,
                    "controlled": actor.controlled,
                    "position": list(actor.position),
                    "hp": actor.hp,
                    "ap": actor.ap,
                    "mp": actor.mp,
                    "wp": None
                    if actor.effect_stats is None
                    else actor.effect_stats.get(4),
                    "states": [
                        {"uid": e.uid, "reference": e.reference, "level": e.level}
                        for e in actor.state_ledger.entries[:128]
                    ],
                    "state_total": len(actor.state_ledger.entries),
                    "states_omitted": max(0, len(actor.state_ledger.entries) - 128),
                }
            )
        if runtime is not None:
            result["fight"].update(
                awaiting_ack=runtime.awaiting_ack,
                action_id=runtime.action_id,
                pending_packets=len(runtime.pending),
            )
    return result


def exception_frames(error):
    # No exception text, source expressions or locals: those could contain data.
    return [
        {"file": frame.filename, "line": frame.lineno, "function": frame.name}
        for frame in traceback.extract_tb(error.__traceback__)[-32:]
    ]


class RequestTrace:
    def __init__(
        self,
        *,
        sink,
        opcode,
        service,
        connection_id,
        snapshot,
        action=None,
        clock=time.monotonic,
        effect_scope=None,
        flush=None
    ):
        self.id = uuid.uuid4().hex
        self.connection_id = connection_id
        self.opcode = opcode
        self.service = service
        self.action = action or ACTIONS.get(opcode, "opcode_" + str(opcode))
        self.sink = sink
        self.snapshot = snapshot
        self.clock = clock
        self.started = clock()
        self.cpu_started = time.thread_time()
        self.before = safe_snapshot(snapshot)
        self.rejections = []
        self.closed = False
        self.records = []
        self.flush_callback = flush
        self.scope = effect_scope
        self.token = _current.set(self)
        if self.scope is not None:
            self.scope.__enter__()
        sink(event="request_started", service=service, state_before=self.before)

    def append(self, record):
        self.records.append(record)
        if len(self.records) >= 1024:
            self.flush()

    def flush(self):
        if self.records and self.flush_callback is not None:
            rows, self.records = self.records, []
            self.flush_callback(rows)

    def rejection(self, event, reason):
        self.rejections.append({"event": event, "reason": redact(reason)})

    def finish(self, *, status=None):
        if self.closed:
            return
        try:
            if self.scope is not None:
                self.scope.__exit__(None, None, None)
            self.sink(
                event="request_finished",
                service=self.service,
                status=status or ("rejected" if self.rejections else "completed"),
                elapsed_ms=round((self.clock() - self.started) * 1000, 3),
                state_before=self.before,
                state_after=safe_snapshot(self.snapshot),
                rejections=self.rejections[:16],
            )
        finally:
            self.flush()
            self.closed = True
            try:
                from wakfu_server.performance_profiler import PROFILER

                PROFILER.observe(
                    "request." + ACTIONS.get(self.opcode, "other"),
                    max(0.0, self.clock() - self.started),
                    max(0.0, time.thread_time() - self.cpu_started),
                    error=bool(self.rejections) or status in ("failed", "exception"),
                )
            except Exception:
                pass  # Diagnostic aggregation cannot alter request completion.
            _current.reset(self.token)
