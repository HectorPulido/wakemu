"""Independent service endpoints for the portable private-server launcher."""
import ipaddress
import json
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit


def package_root():
    return Path(__file__).resolve().parent


def _server_name(value):
    name = str(value).strip().lower().rstrip(".")
    try:
        return str(ipaddress.IPv4Address(name))
    except ValueError:
        if (
            not name
            or len(name) > 253
            or re.fullmatch(r"[0-9.]+", name)
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in name.split(".")
            )
        ):
            raise ValueError("Use an IPv4 address or DNS hostname")
        return name


def validated_resolved_hosts(mappings):
    """Validate DNS pins before using them in subprocesses or Java hosts files."""
    if type(mappings) is not dict or len(mappings) > 64:
        raise ValueError("Invalid resolved service hosts")
    result = {}
    for name, address in mappings.items():
        if (
            type(name) is not str
            or _server_name(name) != name
            or type(address) is not str
        ):
            raise ValueError("Invalid resolved service host")
        value = str(ipaddress.IPv4Address(address))
        try:
            literal = str(ipaddress.IPv4Address(name))
        except ipaddress.AddressValueError:
            literal = None
        if literal is not None and literal != value:
            raise ValueError("Pinned IPv4 does not match its configured literal")
        result[name] = value
    return result


def _resolve_ipv4(name):
    inherited = os.environ.get("WAKFU_RESOLVED_HOSTS")
    if inherited is not None:
        if len(inherited) > 32768:
            raise ValueError("Resolved service hosts exceed their bound")
        try:
            mappings = validated_resolved_hosts(json.loads(inherited))
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid inherited resolved service hosts") from error
        if name in mappings:
            return mappings[name]
    pinned = os.environ.get("WAKFU_SERVER_IPV4")
    if pinned and os.environ.get("WAKFU_SERVER_NAME") == name:
        value = str(ipaddress.IPv4Address(pinned))
        try:
            if str(ipaddress.IPv4Address(name)) != value:
                raise ValueError("Pinned server IPv4 does not match configured server")
        except ipaddress.AddressValueError:
            pass
        return value
    try:
        return str(ipaddress.IPv4Address(name))
    except ValueError:
        pass
    try:
        return str(
            ipaddress.IPv4Address(
                socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)[0][
                    4
                ][0]
            )
        )
    except (OSError, IndexError, ValueError) as error:
        raise ValueError("Could not resolve hostname: " + name) from error


def pin_dns(cfg):
    """Pin each independent service to its own resolved IPv4 address."""
    mappings = validated_resolved_hosts(cfg["resolved_hosts"])
    os.environ["WAKFU_RESOLVED_HOSTS"] = json.dumps(
        mappings, sort_keys=True, separators=(",", ":")
    )
    original = socket.getaddrinfo

    def pinned_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        candidate = host.decode("ascii") if isinstance(host, bytes) else host
        if isinstance(candidate, str):
            host = mappings.get(candidate.lower().rstrip("."), host)
        return original(host, port, family, type, proto, flags)

    socket.getaddrinfo = pinned_getaddrinfo


def settings():
    path = Path(
        os.environ.get("WAKFU_LAUNCHER_CONFIG", package_root() / "config.json")
    ).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent

    def port(key, default):
        value = config.get(key, default)
        if type(value) is not int or not 1 <= value <= 65535:
            raise ValueError("Invalid " + key)
        return value

    def resolved(value):
        p = Path(value).expanduser()
        return p if p.is_absolute() else (base / p).resolve()

    def service_url(key, default):
        value = str(config.get(key, default)).strip().rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError(key + " must be an HTTP(S) service origin")
        host = _server_name(parsed.hostname)
        number = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not 1 <= number <= 65535:
            raise ValueError("Invalid " + key + " port")
        return value, host, number

    name = _server_name(config.get("server_host", "127.0.0.1"))
    host = _resolve_ipv4(name)
    chat_name = _server_name(config.get("chat_host", name))
    dispatch_port = port("dispatch_port", 15558)
    chat_port = port("chat_port", 16337)
    game_ports = config.get("game_ports", [15556])
    if (
        not isinstance(game_ports, list)
        or not game_ports
        or any(type(p) is not int or not 1 <= p <= 65535 for p in game_ports)
    ):
        raise ValueError("Invalid game_ports")
    api, api_name, api_port = service_url("api_url", f"http://{name}:18081")
    http, http_name, http_port = service_url(
        "http_url", f"http://{name}:{port('http_port', 18080)}"
    )
    shop, shop_name, shop_port = service_url("shop_url", http)
    names = {name, chat_name, api_name, http_name, shop_name}
    mappings = {n: host if n == name else _resolve_ipv4(n) for n in names}
    pairs = {
        (name, dispatch_port),
        *((name, p) for p in game_ports),
        (chat_name, chat_port),
        (api_name, api_port),
        (http_name, http_port),
        (shop_name, shop_port),
    }
    endpoints = sorted(
        {f"{n}:{p}" for n, p in pairs} | {f"{mappings[n]}:{p}" for n, p in pairs}
    )
    open_planting = config.get("open_planting", True)
    open_dungeon_missions = config.get("open_dungeon_missions", host == "127.0.0.1")
    if type(open_planting) is not bool or type(open_dungeon_missions) is not bool:
        raise ValueError("Gameplay flags must be boolean")
    certificate = config.get("certificate", "")
    return dict(
        open_planting=open_planting,
        open_dungeon_missions=open_dungeon_missions,
        server_host=host,
        server_name=name,
        dispatch_port=dispatch_port,
        game_ports=game_ports,
        chat_host=mappings[chat_name],
        chat_name=chat_name,
        chat_port=chat_port,
        api_url=api,
        api_port=api_port,
        http_url=http,
        http_port=http_port,
        shop_url=shop,
        shop_port=shop_port,
        certificate=resolved(certificate) if certificate else None,
        resolved_hosts=mappings,
        allowed_endpoints=endpoints,
        runtime_root=resolved(config.get("runtime_root", "profiles")),
        install_root=resolved(config.get("install_root", "..")),
        runner=resolved(config.get("runner", "run-client.py")),
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
    raise ValueError("Wakfu installation not found")
