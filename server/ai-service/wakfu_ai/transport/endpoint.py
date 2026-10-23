"""Strict endpoint parsing for the separate AI TCP service."""
from urllib.parse import urlsplit

DEFAULT_ENDPOINT = "tcp://ai:8090"


def tcp_address(endpoint):
    """Read an address; legacy http URLs still use TCP framing exclusively."""
    if not isinstance(endpoint, str):
        raise ValueError("Invalid separate AI TCP endpoint")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
        if (
            parsed.scheme not in ("tcp", "http")
            or not parsed.hostname
            or port is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or not 1 <= port <= 65535
        ):
            raise ValueError("Invalid separate AI TCP endpoint")
    except ValueError as error:
        raise ValueError("Invalid separate AI TCP endpoint") from error
    return parsed.hostname, port
