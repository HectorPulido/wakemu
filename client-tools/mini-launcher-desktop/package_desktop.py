"""Package launcher-only Windows updates and a self-contained universal Mac launcher."""
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
FILES = (
    "launcher_backend.py",
    "local_launcher_auth.py",
    "portable_config.py",
    "run-client.py",
    "launcher-bridge.py",
)
README = """Wakfu Minilauncher - achievements and dungeon travel

This package does not include or modify the official game client.
Game release: 1.93.1+79.

Windows: extract the update into the EXISTING Windows Wakfu folder and replace
launcher files. Open Conectar.bat. If WebView2 Runtime is absent, use the official
Microsoft installation link shown in the achievements tab, then reopen.

Mac: open Wakfu Minilauncher.app or Conectar.command (macOS 12 or newer, Intel
or Apple Silicon). Python and WebKit are included/available with this package;
no Python installation is required. Open Configuración avanzada to select the folder of your EXISTING Mac
Wakfu 1.93.1+79 client in Carpeta del cliente. If updating the previous Mac
launcher folder, its existing client path is detected automatically.
The game itself may require Rosetta on Apple Silicon if its Java runtime is Intel.

Internet preset: wakemu.p.hectorpulido.net
The launcher detects ports and service URLs automatically from
https://wakemu.p.hectorpulido.net/launcher/config. No credentials are sent
when detecting configuration. All web services share that HTTPS origin.
If manual settings are needed, expand Configuración avanzada.
Certificate: empty for the public Internet server.

Use your NATIVE GAME account, not your GameDock portal nickname. Last server,
account and (when enabled) password save automatically. Windows uses DPAPI;
Mac uses the login Keychain, which may request access permission.

Registrarse opens a separate new-account form with password confirmation.
Only Crear cuenta submits registration to the selected server. On success,
the new account is selected and saved according to the remember preference;
the game is not launched automatically. Cancel or rejection preserves the
previous account. Usernames: 3-32 letters/numbers/underscore/hyphen; passwords:
8-256 characters. This creates a native game account, not a GameDock account.

The launcher stays open while playing. Open Logros y mazmorras to load the
existing page authenticated as the selected native account. This does not
start another game login. The displayed character is the current character
of that account. Dungeon travel and other actions obey the server's existing
connection, combat and instance rules. Changing accounts/servers clears the
embedded page before loading another account. Closing the launcher does not
close the game.

Acceptance test:
1. Configure the client folder on Mac, keep the Internet preset, enter your
   native account/password, enable saving, close and reopen. Expect the same
   server/account with a masked restored password.
2. Press Jugar and select a character. Keep the launcher open.
3. Open Logros y mazmorras. Expect the existing achievements page, your current
   character, progress and existing dungeon travel controls inside the launcher.
4. While connected, outside combat and outside a private instance, choose an
   available dungeon travel action. Confirm if requested. Expect the game to
   move to that dungeon entrance and the page to report the action result.
5. Reconnect/select a different character; expect the page to follow the
   account's current character. Switch launcher account: the previous page
   must disappear and the other account's page must authenticate independently.
6. Close the launcher while playing; expect the game to keep running. Reopen,
   choose Olvidar acceso and reopen again; expect the saved password removed.
"""


def copy_launcher(destination, work):
    target = destination / "mini-launcher"
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(SOURCE / name, target / name)
    shutil.copytree(
        work / "agent-assets/mini-launcher/agents",
        target / "agents",
        dirs_exist_ok=True,
    )
    return target


def receipt(path):
    return dict(
        path=str(path),
        bytes=path.stat().st_size,
        sha256=hashlib.file_digest(path.open("rb"), "sha256").hexdigest(),
    )


def build(work, output):
    output.mkdir(parents=True, exist_ok=True)
    windows = work / "windows-patch"
    target = copy_launcher(windows, work)
    shutil.copy2(SOURCE / "Launcher.ps1", target / "Launcher.ps1")
    shutil.copytree(
        work / "windows-deps/webview2", target / "webview2", dirs_exist_ok=True
    )
    (windows / "Conectar.bat").write_bytes(
        b'@echo off\r\npowershell.exe -STA -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0mini-launcher\\Launcher.ps1" %*\r\n'
    )
    (windows / "LEEME-LOGROS.txt").write_text(README, encoding="utf-8")
    winzip = output / "Wakfu-Minilauncher-Windows-Logros-PARCHE.zip"
    with zipfile.ZipFile(winzip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(windows.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(windows))
    mac = output / "Wakfu-Minilauncher-Mac"
    target = copy_launcher(mac, work)
    subprocess.run(["bash", str(SOURCE / "build-macos.sh"), str(mac)], check=True)
    shutil.copy2(SOURCE / "Conectar.command", mac / "Conectar.command")
    import certifi
    import importlib.metadata

    shutil.copy2(certifi.where(), target / "cacert.pem")
    distribution = importlib.metadata.distribution("certifi")
    license_file = next(
        item for item in distribution.files if str(item).endswith("/licenses/LICENSE")
    )
    shutil.copy2(distribution.locate_file(license_file), target / "certifi-LICENSE.txt")
    # Select the host architecture before invoking its bundled interpreter.
    runtimes = mac / "python-runtimes"
    for arch in ("arm64", "x86_64"):
        if (runtimes / arch).exists():
            shutil.rmtree(runtimes / arch)
        shutil.copytree(
            work / ("python-" + arch) / "python",
            runtimes / arch,
            symlinks=True,
            dirs_exist_ok=True,
        )
    wrapper = mac / "python/bin/python3"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        """#!/bin/sh
set -eu
base="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
case "$(uname -m)" in
  arm64) runtime=arm64 ;;
  x86_64) runtime=x86_64 ;;
  *) echo "Unsupported Mac architecture" >&2; exit 1 ;;
esac
exec "$base/python-runtimes/$runtime/bin/python3" "$@"
"""
    )
    wrapper.chmod(0o755)
    (mac / "README.txt").write_text(README, encoding="utf-8")
    (mac / "runtime-sources.json").write_text(
        json.dumps(json.loads((work / "python-assets.json").read_text()), indent=2)
        + "\n"
    )
    # Never ship saved accounts, absolute machine-specific paths, or linked game data.
    assert not (mac / "profile").exists()
    assert not (mac / "client").exists()
    maczip = output / "Wakfu-Minilauncher-Mac.zip"
    subprocess.run(
        [
            "/usr/bin/ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(mac),
            str(maczip),
        ],
        check=True,
    )
    result = [receipt(path) for path in (winzip, maczip)]
    (work / "package-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.work.resolve(), args.output.resolve())
