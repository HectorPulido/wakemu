"""Serve pre-exported native item icons without exposing arbitrary files."""
import hashlib
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

_ICON_PATH = re.compile(r"/item-icons/([1-9][0-9]{0,9})\.(jpg|png)\Z")


def item_icon_url(reference: int) -> str:
    origin = os.environ.get("SHOP_PUBLIC_URL", "http://127.0.0.1:18083").rstrip("/")
    return f"{origin}/item-icons/{int(reference)}.jpg"


def serve_item_icon(handler, assets_root=None) -> bool:
    """Handle an icon GET/HEAD, returning False for unrelated HTTP paths."""
    path = urlsplit(handler.path).path
    if not path.startswith("/item-icons/"):
        return False
    match = _ICON_PATH.fullmatch(path)
    if match is None:
        handler.send_error(404)
        return True
    root = (
        Path(assets_root or os.environ.get("SHOP_ASSETS_DIR", "/shop-assets")) / "icons"
    )
    extension = match.group(2)
    icon = root / f"{match.group(1)}.{extension}"
    # Reject symlinks as well as traversal; deployment only mounts exported images.
    if icon.is_symlink() or not icon.is_file():
        handler.send_error(404)
        return True
    data = icon.read_bytes()
    etag = '"' + hashlib.sha256(data).hexdigest() + '"'
    if handler.headers.get("If-None-Match") == etag:
        handler.send_response(304)
        handler.send_header("ETag", etag)
        handler.send_header("Cache-Control", "public, max-age=86400")
        handler.end_headers()
        return True
    handler.send_response(200)
    handler.send_header(
        "Content-Type", "image/jpeg" if extension == "jpg" else "image/png"
    )
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.send_header("ETag", etag)
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    if getattr(handler, "command", "GET") != "HEAD":
        handler.wfile.write(data)
    return True
