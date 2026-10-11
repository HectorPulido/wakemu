"""Finite authenticated requests issued only by the external ecology worker."""
import urllib.request
from urllib.parse import urlsplit

from .protocol import (
    MAX_RESPONSE_BYTES,
    SCHEMA_VERSION,
    bounded_json,
    json_bytes,
    validate_proposals,
    validate_snapshot,
    validate_query,
)


class EcologyClient:
    def __init__(self, base_url, token, *, timeout=2.0, opener=urllib.request.urlopen):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid ecology bridge URL")
        if not isinstance(token, str) or not token.strip() or len(token) > 4096:
            raise ValueError("Ecology credential is required")
        if not 0 < timeout <= 10:
            raise ValueError("Invalid ecology request timeout")
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.timeout = timeout
        self.opener = opener

    def request(self, path, payload=None):
        data = None if payload is None else json_bytes(payload)
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
            },
        )
        with self.opener(request, timeout=self.timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            result = bounded_json(raw, limit=MAX_RESPONSE_BYTES)
        if not isinstance(result, dict):
            raise ValueError("Ecology response must be an object")
        return result

    def snapshot(self):
        return validate_snapshot(self.request("/internal/ecology/snapshot"))

    def query(self, kind, map_id, instance_id, *, region_id=None):
        """Use an ecology-service base URL; callers must be outside gameplay locks."""
        value = {"kind": kind, "map_id": map_id, "instance_id": instance_id}
        if region_id is not None:
            value["region_id"] = region_id
        validate_query(value)
        return self.request("/query", value)

    def apply(self, proposals):
        payload = {"schema_version": SCHEMA_VERSION, "proposals": proposals}
        validate_proposals(payload)
        response = self.request("/internal/ecology/apply", payload)
        rows = response.get("results")
        expected = {row["id"] for row in proposals}
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise ValueError("Incomplete ecology acknowledgement")
        seen = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("id") not in expected
                or row["id"] in seen
                or row.get("status") not in ("applied", "duplicate", "stale", "retry")
            ):
                raise ValueError("Invalid ecology acknowledgement")
            seen.add(row["id"])
        return rows
