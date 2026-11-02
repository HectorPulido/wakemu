#!/usr/bin/env python3
"""Start the portable Windows, macOS or Linux Wakfu client."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import urlsplit
from portable_config import (
    settings,
    profile_root,
    client_root,
    package_root,
    pin_dns,
    validated_resolved_hosts,
)


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
    mutable = {"config.properties", "sentry.properties", "log4j.properties"}
    for item in source.iterdir():
        if item.name in mutable | {"tools", package_root().name, ".DS_Store"}:
            continue
        destination = target / item.name
        if sys.platform == "win32":
            if item.is_dir():
                for parent, directories, files in os.walk(item):
                    relative = Path(parent).relative_to(source)
                    (target / relative).mkdir(parents=True, exist_ok=True)
                    for filename in files:
                        if filename == ".DS_Store":
                            continue
                        origin = Path(parent) / filename
                        copied = target / relative / filename
                        if not copied.exists():
                            try:
                                os.link(origin, copied)
                            except OSError:
                                shutil.copy2(origin, copied)
            elif not destination.exists():
                try:
                    os.link(item, destination)
                except OSError:
                    shutil.copy2(item, destination)
        elif not destination.exists():
            destination.symlink_to(item, target_is_directory=item.is_dir())
    config = (source / "config.properties").read_text(encoding="utf-8")
    cfg_http = cfg["http_url"]
    config = re.sub(r"https?://[^/\s]+", cfg_http, config)
    config = re.sub(
        r"^dispatchAddresses=.*$",
        f"dispatchAddresses={cfg['server_host']}:{cfg['dispatch_port']}",
        config,
        flags=re.M,
    )
    config = re.sub(
        r"^interChatUrl=.*$",
        f"interChatUrl={cfg['chat_host']}:{cfg['chat_port']}",
        config,
        flags=re.M,
    )
    # Native Shopi and its authenticated HAAPI calls use the selected shop origin.
    # Browser links retain their path/query placeholders for the configured shop.
    for key in (
        "shopiUrl",
        "haapiAnkamaUrl",
        "haapiWakfuUrl",
        "shopServices",
        "shopBuyOgrinesUrl",
        "payementHandleUrl",
        "payementOgrinesHandleUrl",
    ):
        config = re.sub(
            rf"^({key}=)https?://[^/\s]+",
            lambda match: match.group(1) + cfg["shop_url"],
            config,
            flags=re.M,
        )
    config = re.sub(
        r"^bugReport.enable=.*$", "bugReport.enable=false", config, flags=re.M
    )
    (target / "config.properties").write_text(config, encoding="utf-8")
    (target / "sentry.properties").write_text(
        "dsn=\nrelease=1.93.1+79\nenvironment=private\n", encoding="utf-8"
    )
    logging = (
        (source / "log4j.properties")
        .read_text(encoding="utf-8")
        .replace("INFO, stdout, mainLog, Sentry", "INFO, stdout, mainLog")
    )
    (target / "log4j.properties").write_text(logging, encoding="utf-8")
    preferences = runtime / "preferences/preferences/userPreferences.properties"
    if not preferences.exists():
        preferences.write_text(
            "version=24\nresolution=1500x950x32x120x0x50x33xDisplay 1xfalse\nmusicMute=true\nambianceSoundsMute=true\nuiSoundsMute=true\n",
            encoding="utf-8",
        )
    ports = {int(endpoint.rsplit(":", 1)[1]) for endpoint in cfg["allowed_endpoints"]}
    sb = '(version 1)\n(allow default)\n(deny network*)\n(allow network-inbound (local ip "localhost:*"))\n(allow network-bind (local ip "localhost:*"))\n(allow network-outbound (remote ip "localhost:*"))\n'
    if cfg["server_host"] != "127.0.0.1":
        sb += "".join(
            f'(allow network-outbound (remote ip "*:{port}"))\n'
            for port in sorted(ports)
        )
    sb += '(deny mach-lookup (global-name "com.apple.mDNSResponder"))\n(deny mach-lookup (global-name "com.apple.dnssd.service"))\n'
    (runtime / "network.sb").write_text(sb, encoding="utf-8")
    return source, runtime, ports


def java_hosts_options(runtime, cfg):
    """Keep URL hostnames and TLS SNI while resolving without sandboxed DNS."""
    mappings = validated_resolved_hosts(cfg["resolved_hosts"])
    hosts = runtime / "resolved-hosts.txt"
    rows = ["127.0.0.1 localhost", "::1 localhost"]
    rows.extend(address + " " + name for name, address in sorted(mappings.items()))
    hosts.write_text("\n".join(rows) + "\n", encoding="ascii")
    return ["-Djdk.net.hosts.file=" + str(hosts.resolve())]


def java_trust_options(source, runtime, cfg, environment):
    """Add a selected CA to a private copy of the bundled platform trust roots."""
    certificate = cfg.get("certificate")
    if not certificate or not any(
        urlsplit(cfg[key]).scheme == "https" for key in ("http_url", "shop_url")
    ):
        return []
    certificate = Path(certificate)
    if not certificate.is_file():
        raise ValueError("El certificado configurado no existe.")
    java_home = source / ("jre/Contents/Home" if sys.platform == "darwin" else "jre")
    original = java_home / "lib/security/cacerts"
    keytool = java_home / (
        "bin/keytool.exe" if sys.platform == "win32" else "bin/keytool"
    )
    if not original.is_file() or not keytool.is_file():
        raise ValueError(
            "El Java incluido no contiene las herramientas de certificados."
        )
    cert_bytes = certificate.read_bytes()
    roots_bytes = original.read_bytes()
    cert_hash = hashlib.sha256(cert_bytes).hexdigest()
    cache_key = hashlib.sha256(roots_bytes + b"\x00" + cert_bytes).hexdigest()
    cache = runtime / "cache/java-trust"
    cache.mkdir(parents=True, exist_ok=True)
    truststore = cache / (cache_key + ".store")
    if not truststore.is_file():
        fd, temporary = tempfile.mkstemp(prefix="trust-", suffix=".store", dir=cache)
        os.close(fd)
        staged = Path(temporary)
        try:
            shutil.copyfile(original, staged)
            result = subprocess.run(
                [
                    str(keytool),
                    "-importcert",
                    "-noprompt",
                    "-alias",
                    "wakemu-configured-" + cert_hash,
                    "-file",
                    str(certificate),
                    "-keystore",
                    str(staged),
                    "-storepass",
                    "changeit",
                ],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if result.returncode:
                raise ValueError(
                    "No se pudo importar el certificado HTTPS configurado."
                )
            staged.replace(truststore)
        finally:
            staged.unlink(missing_ok=True)
    store_type = "JKS" if roots_bytes.startswith(b"\xfe\xed\xfe\xed") else "PKCS12"
    return [
        "-Djavax.net.ssl.trustStore=" + str(truststore),
        "-Djavax.net.ssl.trustStorePassword=changeit",
        "-Djavax.net.ssl.trustStoreType=" + store_type,
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="main")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--use-local-auth", action="store_true")
    args = parser.parse_args()
    if sys.platform not in ("darwin", "linux", "win32"):
        raise ValueError("Unsupported operating system")
    macos = sys.platform == "darwin"
    if macos and not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("macOS sandbox-exec is required")
    cfg = settings()
    os.environ["WAKFU_SERVER_NAME"] = cfg["server_name"]
    os.environ["WAKFU_SERVER_IPV4"] = cfg["server_host"]
    pin_dns(cfg)
    source, runtime, ports = prepare(args.profile)
    hosts_options = java_hosts_options(runtime, cfg)
    sandbox = (
        ["/usr/bin/sandbox-exec", "-f", str(runtime / "network.sb")] if macos else []
    )
    if sys.platform in ("linux", "win32"):
        print(
            "Java network guard active; no OS network sandbox. "
            "The Python launcher bridge and native libraries are not sandboxed.",
            file=sys.stderr,
        )
    java = source / (
        "jre/Contents/Home/bin/java"
        if macos
        else "jre/bin/java.exe"
        if sys.platform == "win32"
        else "jre/bin/java"
    )
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
    guard = f"-javaagent:{agents/'network-guard.jar'}={runtime/'logs/network-blocked.log'}|v2|{','.join(cfg['allowed_endpoints'])}"
    if args.check:
        result = subprocess.run(
            [
                *sandbox,
                str(java),
                *hosts_options,
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
    if sys.platform == "linux" and not env.get("DISPLAY"):
        raise ValueError("Linux GUI launch requires DISPLAY from the desktop session")
    if not env.get("ZAAP_PORT") or not env.get("ZAAP_HASH"):
        raise ValueError("Missing private launcher bridge")
    env.update(
        WAKFU_LANGUAGE="es",
        WAKFU_PREF_FILE_DIRECTORY=str(runtime / "preferences"),
        WAKFU_CACHE_FILE_DIRECTORY=str(runtime / "cache"),
    )
    trust_options = java_trust_options(source, runtime, cfg, env)
    command = [
        *sandbox,
        str(java),
        *hosts_options,
        *trust_options,
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
