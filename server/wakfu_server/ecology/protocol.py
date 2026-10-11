"""JSON-only ecology bridge contract; never transports executable commands."""
import hashlib
import json

SCHEMA_VERSION = 1
MAX_BODY_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PROPOSALS = 16
MAX_SCOPES = 64
DOMAINS = frozenset(("plants", "mobs", "weather", "population"))
TERMINAL_STATUSES = frozenset(("applied", "duplicate", "stale"))


def json_bytes(value, *, limit=MAX_BODY_BYTES):
    encoded = json.dumps(
        value, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode()
    if len(encoded) > limit:
        raise ValueError("Ecology JSON exceeds byte limit")
    return encoded


def bounded_json(raw, *, limit=MAX_BODY_BYTES):
    if len(raw) > limit:
        raise ValueError("Ecology JSON exceeds byte limit")

    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")

    return json.loads(raw, parse_constant=invalid_constant)


def validate_snapshot(snapshot):
    if (
        not isinstance(snapshot, dict)
        or type(snapshot.get("schema_version")) is not int
        or snapshot.get("schema_version") != SCHEMA_VERSION
    ):
        raise ValueError("Unsupported ecology snapshot schema")
    epoch = snapshot.get("world_epoch", snapshot.get("epoch"))
    if not isinstance(epoch, str) or not 1 <= len(epoch) <= 128:
        raise ValueError("Invalid ecology snapshot epoch")
    scopes = snapshot.get("scopes")
    if not isinstance(scopes, list) or len(scopes) > MAX_SCOPES:
        raise ValueError("Invalid ecology scope count")
    json_bytes(snapshot, limit=MAX_RESPONSE_BYTES)
    return snapshot


def proposal(domain, payload, epoch):
    if domain not in DOMAINS or not isinstance(payload, dict):
        raise ValueError("Invalid ecology proposal")
    body = {"domain": domain, "payload": payload}
    identifier = hashlib.sha256(json_bytes(body)).hexdigest()
    return {"id": identifier, **body, "world_epoch": epoch}


def validate_proposals(value):
    if not isinstance(value, dict) or set(value) != {"schema_version", "proposals"}:
        raise ValueError("Invalid ecology proposal envelope")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError("Unsupported ecology proposal schema")
    rows = value["proposals"]
    if not isinstance(rows, list) or len(rows) > MAX_PROPOSALS:
        raise ValueError("Invalid ecology proposal count")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "id",
            "domain",
            "payload",
            "world_epoch",
        }:
            raise ValueError("Invalid ecology proposal fields")
        if (
            not isinstance(row["id"], str)
            or not 1 <= len(row["id"]) <= 128
            or row["id"] in ids
            or row["domain"] not in DOMAINS
            or not isinstance(row["payload"], dict)
            or not isinstance(row["world_epoch"], str)
            or not 1 <= len(row["world_epoch"]) <= 128
        ):
            raise ValueError("Invalid ecology proposal identity")
        ids.add(row["id"])
    json_bytes(value)
    return rows


def validate_query(value):
    if not isinstance(value, dict) or set(value) - {
        "kind",
        "map_id",
        "instance_id",
        "region_id",
    }:
        raise ValueError("Invalid ecology query fields")
    if value.get("kind") not in ("population", "weather"):
        raise ValueError("Invalid ecology query kind")
    if type(value.get("map_id")) is not int or not 0 < value["map_id"] < 2**31:
        raise ValueError("Invalid ecology query map")
    if (
        type(value.get("instance_id")) is not int
        or not 0 <= value["instance_id"] < 2**63
    ):
        raise ValueError("Invalid ecology query instance")
    if "region_id" in value and (
        type(value["region_id"]) is not int or not 0 < value["region_id"] < 2**31
    ):
        raise ValueError("Invalid ecology query region")
    return value
