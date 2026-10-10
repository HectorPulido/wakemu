#!/usr/bin/env python3
"""Start an installed macOS or Linux Wakfu client with isolated private-server settings."""
import argparse, json, os, re, subprocess, sys
from pathlib import Path
from urllib.parse import urlsplit
from portable_config import settings, profile_root, client_root, package_root, pin_dns


def prepare(name):
    cfg = settings()
    source = client_root()
    runtime = profile_root(name)
    target = runtime / "client"
    for folder in (
        target,
        runtime / "preferences/preferences",
        runtime / "cache",
        runtime / "logs",
    ):
        folder.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.name in {
            "config.properties",
            "sentry.properties",
            "log4j.properties",
            "tools",
            package_root().name,
        }:
            continue
        link = target / item.name
        if not link.exists():
            link.symlink_to(item, target_is_directory=item.is_dir())
    config = (source / "config.properties").read_text()
    cfg_http = f"http://{cfg['server_host']}:{cfg['http_port']}"
    config = re.sub(r"https?://[^/\s]+", cfg_http, config)
    config = re.sub(
        r"^dispatchAddresses=.*$",
        f"dispatchAddresses={cfg['server_host']}:{cfg['dispatch_port']}",
        config,
        flags=re.M,
    )
    config = re.sub(
        r"^interChatUrl=.*$",
        f"interChatUrl={cfg['server_host']}:{cfg['chat_port']}",
        config,
        flags=re.M,
    )
    config = re.sub(
        r"^bugReport.enable=.*$", "bugReport.enable=false", config, flags=re.M
    )
    (target / "config.properties").write_text(config)
    (target / "sentry.properties").write_text("dsn=\n")
    logging = (
        (source / "log4j.properties")
        .read_text()
        .replace("INFO, stdout, mainLog, Sentry", "INFO, stdout, mainLog")
    )
    (target / "log4j.properties").write_text(logging)
    preferences = runtime / "preferences/preferences/userPreferences.properties"
    if not preferences.exists():
        preferences.write_text(
            "version=24\nresolution=1500x950x32x120x0x50x33xDisplay 1xfalse\nmusicMute=true\nambianceSoundsMute=true\nuiSoundsMute=true\n"
        )
    ports = {cfg["dispatch_port"], cfg["chat_port"], cfg["http_port"], cfg["api_port"]}
    # Game server ports must be explicit: dispatcher cannot redirect this client elsewhere.
    raw = json.loads(
        Path(
            os.environ.get("WAKFU_LAUNCHER_CONFIG", package_root() / "config.json")
        ).read_text()
    )
    for port in raw.get("game_ports", [15556]):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid game port")
        ports.add(port)
    sb = '(version 1)\n(allow default)\n(deny network*)\n(allow network-inbound (local ip "localhost:*"))\n(allow network-bind (local ip "localhost:*"))\n(allow network-outbound (remote ip "localhost:*"))\n'
    if cfg["server_host"] != "127.0.0.1":
        sb += "".join(
            f'(allow network-outbound (remote ip "{cfg["server_host"]}:{port}"))\n'
            for port in sorted(ports)
        )
    sb += '(deny mach-lookup (global-name "com.apple.mDNSResponder"))\n(deny mach-lookup (global-name "com.apple.dnssd.service"))\n'
    (runtime / "network.sb").write_text(sb)
    return source, runtime, ports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="main")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--use-local-auth", action="store_true")
    args = parser.parse_args()
    if sys.platform not in ("darwin", "linux"):
        raise ValueError("This package supports macOS and Linux")
    macos = sys.platform == "darwin"
    if macos and not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("macOS sandbox-exec is required")
    cfg = settings()
    os.environ["WAKFU_SERVER_NAME"] = cfg["server_name"]
    os.environ["WAKFU_SERVER_IPV4"] = cfg["server_host"]
    pin_dns(cfg)
    source, runtime, ports = prepare(args.profile)
    sandbox = (
        ["/usr/bin/sandbox-exec", "-f", str(runtime / "network.sb")] if macos else []
    )
    if not macos:
        print(
            "Linux isolation: Java network guard active; no OS network sandbox. "
            "The Python launcher bridge and native libraries are not sandboxed.",
            file=sys.stderr,
        )
    java = source / ("jre/Contents/Home/bin/java" if macos else "jre/bin/java")
    if not java.is_file():
        raise ValueError("Installed Wakfu Java runtime not found")
    agents = Path(os.environ.get("WAKFU_AGENT_ROOT", package_root() / "agents"))
    required_agents = ["network-guard.jar", "open-planting.jar", "desktop-fix.jar"]
    for name in required_agents:
        if not (agents / name).is_file():
            raise ValueError("Missing packaged agent " + name)
    env = dict(os.environ)
    for key in (
        "_JAVA_OPTIONS",
        "JAVA_TOOL_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        env.pop(key, None)
    env["WAKFU_LAUNCHER_CONFIG"] = str(
        Path(
            os.environ.get("WAKFU_LAUNCHER_CONFIG", package_root() / "config.json")
        ).resolve()
    )
    env["WAKFU_LOCAL_PROFILE"] = args.profile
    guard = f"-javaagent:{agents/'network-guard.jar'}={runtime/'logs/network-blocked.log'}|{settings()['server_host']}|{','.join(map(str,sorted(ports)))}"
    if args.check:
        result = subprocess.run(
            [
                *sandbox,
                str(java),
                "-Djava.security.manager=allow",
                guard,
                "-cp",
                str(agents / "network-guard.jar"),
                "DropinNetworkGuardTest",
            ],
            env=env,
        )
        if result.returncode:
            raise ValueError("Network isolation check failed")
        print("Existing Wakfu install and bundled agents verified; no client launched.")
        return 0
    if not args.use_local_auth:
        if args.token_file is None or not args.token_file.is_file():
            raise ValueError(
                "Launch from the launcher after signing into your private-server account"
            )
        env["WAKFU_GAME_LOGIN_FILE"] = str(args.token_file.resolve())
        return subprocess.call(
            [
                *sandbox,
                sys.executable,
                os.environ.get(
                    "WAKFU_REPOSITORY_BRIDGE",
                    str(package_root() / "launcher-bridge.py"),
                ),
            ],
            env=env,
        )
    if not macos and not env.get("DISPLAY"):
        raise ValueError("Linux GUI launch requires DISPLAY from the desktop session")
    if not env.get("ZAAP_PORT") or not env.get("ZAAP_HASH"):
        raise ValueError("Missing private launcher bridge")
    env.update(
        WAKFU_LANGUAGE="es",
        WAKFU_PREF_FILE_DIRECTORY=str(runtime / "preferences"),
        WAKFU_CACHE_FILE_DIRECTORY=str(runtime / "cache"),
    )
    command = [
        *sandbox,
        str(java),
        "-Djava.security.manager=allow",
        guard,
        "--add-exports=java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED",
        f'-javaagent:{agents/"desktop-fix.jar"}',
        "-Dwakfu.local.openPlanting=" + str(settings()["open_planting"]).lower(),
        "-Dwakfu.local.openDungeonMissions="
        + str(cfg["open_dungeon_missions"]).lower(),
        f'-javaagent:{agents/"open-planting.jar"}',
        "-Xms512m",
        "-Xmx2G",
        "-Djava.net.preferIPv4Stack=true",
        "-Dsun.awt.noerasebackground=true",
        "-Dsun.java2d.noddraw=true",
        "-Djogl.disable.openglarbcontext",
        "-Dsun.java2d.metal=false",
        "-Dsun.java2d.opengl=true",
        "--add-opens=java.desktop/sun.awt=ALL-UNNAMED",
        *(["--add-opens=java.desktop/com.apple.eawt=ALL-UNNAMED"] if macos else []),
        "-Dsun.java2d.uiScale.enabled=true",
        "-Djava.library.path=natives/",
        "@classpath",
        "com.ankamagames.wakfu.client.WakfuClient",
        "--partner=default",
        "--install-folder",
        ".",
        "-p",
        str(runtime / "preferences"),
        "-n",
        str(runtime / "cache"),
        "-L",
        "es",
    ]
    capture = env.get("WAKFU_CAPTURE_AGENT")
    if capture:
        (runtime / "captures").mkdir(exist_ok=True)
        command.insert(
            command.index("-Xms512m"), f"-javaagent:{capture}={runtime / 'captures'}"
        )
    log = runtime / "logs/client-console.log"
    with log.open("ab") as output:
        return subprocess.call(
            command,
            cwd=runtime / "client",
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
