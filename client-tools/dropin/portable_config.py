"""Configuration for a drop-in launcher using an existing Wakfu install."""
import ipaddress, json, os, re, socket
from pathlib import Path
from urllib.parse import urlsplit


def package_root():
    return Path(__file__).resolve().parent


def _server_name(value):
    name = str(value).lower().rstrip(".")
    try:
        return str(ipaddress.IPv4Address(name))
    except ValueError:
        if (
            len(name) > 253
            or not name
            or re.fullmatch(r"[0-9.]+", name)
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in name.split(".")
            )
        ):
            raise ValueError(
                "server_host must be a numeric IPv4 address or DNS hostname"
            )
        return name


def _resolve_ipv4(name):
    pinned = os.environ.get("WAKFU_SERVER_IPV4")
    if pinned is not None:
        if os.environ.get("WAKFU_SERVER_NAME") != name:
            raise ValueError("Pinned server IPv4 does not match configured server name")
        host = str(ipaddress.IPv4Address(pinned))
        try:
            numeric = str(ipaddress.IPv4Address(name))
        except ValueError:
            return host
        if host != numeric:
            raise ValueError("Pinned server IPv4 does not match configured server host")
        return host
    try:
        return str(ipaddress.IPv4Address(name))
    except ValueError:
        pass
    try:
        addresses = socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)
        return str(ipaddress.IPv4Address(addresses[0][4][0]))
    except (OSError, IndexError, ValueError) as error:
        raise ValueError(
            "Could not resolve server hostname to IPv4: " + name
        ) from error


def pin_dns(cfg):
    """Keep the configured endpoint reachable after the launcher restricts networking."""
    names = {cfg["server_name"], urlsplit(cfg["api_url"]).hostname}
    original = socket.getaddrinfo

    def pinned_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        candidate = host.decode("ascii") if isinstance(host, bytes) else host
        if isinstance(candidate, str) and candidate.lower().rstrip(".") in names:
            host = cfg["server_host"]
        return original(host, port, family, type, proto, flags)

    socket.getaddrinfo = pinned_getaddrinfo


def settings():
    path = Path(
        os.environ.get("WAKFU_LAUNCHER_CONFIG", package_root() / "config.json")
    ).resolve()
    config = json.loads(path.read_text())
    base = path.parent
    name = _server_name(config.get("server_host", "127.0.0.1"))
    host = _resolve_ipv4(name)
    api = config.get("api_url", f"http://{name}:18081").rstrip("/")
    parsed = urlsplit(api)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in (name, host)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "api_url must use the configured server hostname or resolved IPv4 host"
        )

    def port(key, default):
        value = config.get(key, default)
        if type(value) is not int or not 1 <= value <= 65535:
            raise ValueError("Invalid " + key)
        return value

    def resolved(value):
        p = Path(value).expanduser()
        return p if p.is_absolute() else base / p

    open_planting = config.get("open_planting", True)
    if type(open_planting) is not bool:
        raise ValueError("open_planting must be boolean")
    return dict(
        open_planting=open_planting,
        server_host=host,
        server_name=name,
        api_url=api,
        api_port=parsed.port or (443 if parsed.scheme == "https" else 80),
        dispatch_port=port("dispatch_port", 15558),
        chat_port=port("chat_port", 16337),
        http_port=port("http_port", 18080),
        runtime_root=resolved(config.get("runtime_root", "profiles")),
        install_root=resolved(config.get("install_root", "..")),
        runner=resolved(config.get("runner", "run-client.sh")),
    )


def profile_root(name="main"):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        raise ValueError("Invalid profile name")
    root = settings()["runtime_root"]
    return root if name == "main" else root / "instances" / name


def client_root():
    base = settings()["install_root"].resolve()
    for candidate in (base, base / "client", base / "Contents/Resources"):
        if (
            (candidate / "lib/wakfu-client.jar").is_file()
            and (candidate / "config.properties").is_file()
            and (candidate / "classpath").is_file()
        ):
            return candidate
    raise ValueError(
        "Wakfu installation not found: put mini-launcher inside its folder (lib, contents, jre, classpath)"
    )
