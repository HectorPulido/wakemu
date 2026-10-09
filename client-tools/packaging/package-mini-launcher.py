#!/usr/bin/env python3
"""Build a deterministic drop-in ZIP: only explicitly selected own files."""
import argparse, hashlib, io, json, os, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DROPIN = ROOT / "client-tools/dropin"
CONFIG = dict(
    api_url="http://127.0.0.1:18081",
    server_host="127.0.0.1",
    dispatch_port=15558,
    game_ports=[15556],
    chat_port=16337,
    http_port=18080,
    runtime_root="profiles",
    runner="run-client.sh",
    install_root="..",
    open_planting=True,
)


def zip_bytes(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name, (contents, mode) in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, contents)
    return output.getvalue()


def build(output):
    jdk = os.environ.get("JAVA_HOME")
    if not jdk and sys.platform == "linux":
        javac = shutil.which("javac")
        if not javac:
            raise ValueError("Install a JDK 21 or newer, or set JAVA_HOME")
        jdk = str(Path(javac).resolve().parent.parent)
    if not jdk:
        jdk = subprocess.check_output(
            ["/usr/libexec/java_home", "-v", "21+"], text=True
        ).strip()
    java = Path(jdk) / "bin"
    entries = {}

    def add(name, content, mode=0o644):
        entries["mini-launcher/" + name] = (content, mode)

    for name in (
        "portable_config.py",
        "remote-login.py",
        "run-client.py",
        "launcher-bridge.py",
        "run-client.sh",
        "Launch.command",
        "README.txt",
    ):
        add(
            name,
            (DROPIN / name).read_bytes(),
            0o755 if name.endswith((".sh", ".command")) else 0o644,
        )
    add("local-launcher.py", (ROOT / "client-tools/local-launcher.py").read_bytes())
    add("config.json", (json.dumps(CONFIG, indent=2) + "\n").encode())
    sources = {
        name: (DROPIN / name)
        for name in ("DropinNetworkGuard.java", "DropinNetworkGuardTest.java")
    }
    sources["LocalDesktopFix.java"] = ROOT / "client-tools/java/LocalDesktopFix.java"
    sources["OpenPlantingAgent.java"] = (
        ROOT / "client-tools/java/OpenPlantingAgent.java"
    )
    for name, path in sources.items():
        add("sources/" + name, path.read_bytes())
    with tempfile.TemporaryDirectory() as temp:
        classes = Path(temp) / "classes"
        classes.mkdir()
        subprocess.run(
            [
                str(java / "javac"),
                "-proc:none",
                "-source",
                "21",
                "-target",
                "21",
                "--add-exports",
                "java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED",
                "-d",
                str(classes),
                *[str(p) for p in sources.values()],
            ],
            check=True,
        )
        for jar, premain, prefixes in [
            ("network-guard.jar", "DropinNetworkGuard", ("DropinNetworkGuard",)),
            ("desktop-fix.jar", "LocalDesktopFix", ("LocalDesktopFix",)),
            ("open-planting.jar", "OpenPlantingAgent", ("OpenPlantingAgent",)),
        ]:
            items = {
                "META-INF/MANIFEST.MF": (
                    f"Manifest-Version: 1.0\nPremain-Class: {premain}\n\n".encode(),
                    0o644,
                )
            }
            for item in sorted(classes.glob("*.class")):
                if any(item.stem.startswith(p) for p in prefixes):
                    items[item.name] = (item.read_bytes(), 0o644)
            add("agents/" + jar, zip_bytes(items))
    manifest = {
        "format": 1,
        "files": {
            n.removeprefix("mini-launcher/"): hashlib.sha256(c).hexdigest()
            for n, (c, _) in sorted(entries.items())
        },
    }
    add("manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(zip_bytes(entries))
    print(output, "bytes", output.stat().st_size, "files", len(entries))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/distribution/wakfu-mini-launcher.zip",
    )
    args = parser.parse_args()
    build(args.output.resolve())
