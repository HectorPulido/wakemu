"""Embeddable player UI and scoped bearer API, isolated from operator routes."""
import json
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit


def embed_origins():
    values = os.environ.get(
        "WAKFU_OBJECTIVES_EMBED_ORIGINS",
        "http://127.0.0.1:18083,http://127.0.0.1:18084,http://127.0.0.1:18086,http://localhost:18086",
    ).split(",")
    result = set()
    for value in values:
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Embed origins must be explicit HTTP or HTTPS origins")
        result.add(value)
    public = urlsplit(
        os.environ.get("WAKFU_OBJECTIVES_PUBLIC_URL", "http://127.0.0.1:18086/player/")
    )
    if public.scheme in ("http", "https") and public.netloc:
        result.add(public.scheme + "://" + public.netloc)
    return sorted(result)


def dispatch(handler, connect, static_root):
    from . import player_auth, player_actions, player_views
    from .repository import ConflictError

    origins = embed_origins()
    origin = handler.headers.get("Origin")
    allowed = origin is None or origin in origins
    path = urlsplit(handler.path).path.rstrip("/") or "/"

    def reply(
        code, value=None, *, raw=None, content_type="application/json; charset=utf-8"
    ):
        if raw is None:
            raw = json.dumps(
                value,
                default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v),
            ).encode()
        handler.send_response(code)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(raw)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'self' "
            + " ".join(origins),
        )
        if origin in origins:
            handler.send_header("Access-Control-Allow-Origin", origin)
            handler.send_header("Vary", "Origin")
            handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            handler.send_header(
                "Access-Control-Allow-Headers", "Authorization, Content-Type"
            )
        handler.end_headers()
        if raw:
            handler.wfile.write(raw)

    def body(maximum=8192):
        if (
            handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            raise ValueError("Requests must use application/json")
        size = int(handler.headers.get("Content-Length", "0"))
        if not 1 <= size <= maximum:
            raise ValueError("Invalid player request size")
        value = json.loads(handler.rfile.read(size))
        if type(value) is not dict:
            raise ValueError("Expected a JSON object")
        return value

    if not allowed:
        return reply(403, {"error": "Embedding origin is not allowed"})
    if handler.command == "OPTIONS":
        return reply(204, raw=b"")
    try:
        if path == "/player-api/config" and handler.command == "GET":
            return reply(200, {"embed_origins": origins})
        if path == "/player" or path.startswith("/player/"):
            if handler.command != "GET":
                return reply(405, {"error": "Method not allowed"})
            relative = unquote(path.removeprefix("/player").lstrip("/")) or "index.html"
            root = Path(static_root).resolve()
            asset = (root / relative).resolve()
            if root not in asset.parents or not asset.is_file():
                return reply(404, {"error": "Asset not found"})
            mime = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            return reply(200, raw=asset.read_bytes(), content_type=mime)
        if path == "/player-api/session" and handler.command == "POST":
            request = body()
            if set(request) != {"token"}:
                raise ValueError("Expected a launch token")
            with connect() as db:
                result = player_auth.exchange_launch(db, request["token"])
            return reply(200, result)
        authorization = handler.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise player_auth.Unauthorized("Open Adventures from the game to sign in")
        with connect() as db:
            identity = player_auth.authenticate(db, authorization[7:])
            if path == "/player-api/adventures" and handler.command == "GET":
                result = player_views.snapshot(db, identity)
                code = 200
            elif path == "/player-api/actions" and handler.command == "POST":
                request = body()
                if set(request) != {"action_key", "request_id"}:
                    raise ValueError("Expected an action key and request identity")
                result = player_actions.enqueue(
                    db, identity, request["action_key"], request["request_id"]
                )
                code = 202 if result["status"] in ("pending", "running") else 200
            elif path.startswith("/player-api/actions/") and handler.command == "GET":
                result = player_actions.receipt(
                    db, identity, path.removeprefix("/player-api/actions/")
                )
                if result is None:
                    return reply(404, {"error": "Action receipt not found"})
                code = 200
            else:
                return reply(404, {"error": "Player route not found"})
        # Commit action reservation or credential exchange before publication.
        return reply(code, result)
    except player_auth.Unauthorized as error:
        return reply(401, {"error": str(error)})
    except ConflictError as error:
        return reply(409, {"error": str(error)})
    except (ValueError, KeyError, TypeError) as error:
        return reply(400, {"error": str(error)})
    except Exception:
        return reply(
            503, {"error": "Adventures is unavailable. Refresh and try again."}
        )
