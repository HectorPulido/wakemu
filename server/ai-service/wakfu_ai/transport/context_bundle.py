"""Verify complete context attachments before resuming a native query session."""
import base64
import hashlib
import json
import re

from ..native.native_deadline import check

BUNDLE_LIMIT = 3 * 1024 * 1024
MAX_ATTACHMENTS = 16


def bundle_size(request, blocks):
    """Exact compact JSON size without copying validated base64 bodies."""
    check()
    size = len(
        json.dumps(
            dict(request=request, blocks=[]), separators=(",", ":"), allow_nan=False
        ).encode()
    )
    for block in blocks:
        check()
        header = dict(block, data="")
        size += len(
            json.dumps(header, separators=(",", ":"), allow_nan=False).encode()
        ) + len(block["data"])
    check()
    return size + max(0, len(blocks) - 1)


def continue_request(payload, store, sessions):
    if (
        not isinstance(payload, dict)
        or set(payload) != {"request", "blocks"}
        or not isinstance(payload["request"], dict)
        or set(payload["request"]) != {"requestId", "sourceKey", "response"}
        or not isinstance(payload["blocks"], list)
        or not 1 <= len(payload["blocks"]) <= MAX_ATTACHMENTS
    ):
        raise ValueError("Invalid native context continuation bundle")
    sessions._validate_identity(payload["request"])
    response = payload["request"]["response"]
    if not isinstance(response, dict) or type(response.get("id")) is not str:
        raise ValueError("Invalid native context continuation response")
    decoded = []
    seen = set()
    encoded_bytes = 0
    for block in payload["blocks"]:
        check()
        if (
            not isinstance(block, dict)
            or set(block) != {"sha256", "size", "offset", "data"}
            or type(block["sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", block["sha256"]) is None
            or type(block["size"]) is not int
            or block["size"] < 0
            or type(block["offset"]) is not int
            or not 0 <= block["offset"] <= block["size"]
            or type(block["data"]) is not str
            or block["sha256"] in seen
        ):
            raise ValueError("Invalid native context continuation attachment")
        seen.add(block["sha256"])
        encoded_bytes += len(block["data"])
        if encoded_bytes > BUNDLE_LIMIT:
            raise ValueError("Native context continuation bundle is too large")
        try:
            data = base64.b64decode(block["data"], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid native context attachment encoding") from error
        if len(data) > 2 * 1024 * 1024 or block["offset"] + len(data) != block["size"]:
            raise ValueError(
                "Native context attachment must finish its complete object"
            )
        if block["offset"] == 0 and hashlib.sha256(data).hexdigest() != block["sha256"]:
            raise ValueError("Native context attachment checksum mismatch")
        # The ordinary block endpoint can acknowledge an existing object
        # without reading the retransmitted bytes. A bundle certifies every
        # attachment, even on a lost-reply retry, before advancing any search.
        if store.has(block["sha256"], block["size"]):
            existing = store.read(block["sha256"])
            if existing[block["offset"] :] != data:
                raise ValueError("Conflicting native context attachment")
        decoded.append((block, data))
    # Base64 has now been strictly validated: every body character is ASCII
    # and needs no JSON escaping. Count those bytes without reserializing them.
    if bundle_size(payload["request"], payload["blocks"]) > BUNDLE_LIMIT:
        raise ValueError("Native context continuation bundle is too large")
    for block, data in decoded:
        check()
        receipt = store.put(block["sha256"], block["size"], block["offset"], data)
        if receipt != dict(complete=True, offset=block["size"]):
            raise ValueError("Incomplete native context continuation attachment")
    check()
    # QuerySessions validates exact response IDs and caches its reply. Repeating
    # the identical bundle after a lost socket reply cannot advance it twice.
    return sessions.decide(payload["request"], store)
