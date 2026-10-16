"""Bounded server-to-server objectives requests; credentials never reach browsers."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def player_launch(store, character_id):
    """Issue a reusable player link without depending on native chat hyperlinks."""
    from urllib.parse import urlsplit
    from wakfu_server.objectives import player_auth

    if type(character_id) is not int or character_id < 1:
        raise ValueError("Invalid character identifier")
    address = os.environ.get(
        "WAKFU_OBJECTIVES_PUBLIC_URL", "http://127.0.0.1:18086/player/"
    )
    parsed = urlsplit(address)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Invalid objectives player URL")
    with store.connection() as db:
        row = db.execute(
            "SELECT id,account_id FROM characters WHERE id=%s AND deleted_at IS NULL",
            (character_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Character unavailable")
        token = player_auth.issue_embed(db, row["account_id"], row["id"])
    return {"url": address + "#token=" + token, "valid_days": 30}


def request(method, path, query="", payload=None):
    address = os.environ.get("WAKFU_OBJECTIVES_URL", "http://objectives:8094")
    try:
        token = (
            Path(
                os.environ.get("WAKFU_OBJECTIVES_TOKEN_FILE", "/data/objectives-token")
            )
            .read_text()
            .strip()
        )
        if not token:
            raise ValueError("Missing service token")
        headers = {"Accept": "application/json", "Authorization": "Bearer " + token}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        upstream = Request(
            address.rstrip("/") + path + ("?" + query if query else ""),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            response = urlopen(upstream, timeout=8)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Oversized service response")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("Invalid service response")
            return response.status, result
    except (OSError, URLError, ValueError):
        return 503, {"error": "Objectives service is unavailable. Try again later."}
