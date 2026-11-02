#!/usr/bin/env python3
"""Fetch pinned official WebView2 SDK assets for the Windows launcher package."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

VERSION = "1.0.3650.58"
PACKAGE_SHA256 = "911a472128c82ac8baa0c486c23342cc9dd6e7dc50d754e676726642ca065c60"
URL = f"https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/{VERSION}/microsoft.web.webview2.{VERSION}.nupkg"


def prepare(cache, target):
    cache.mkdir(parents=True, exist_ok=True)
    package = cache / f"microsoft.web.webview2.{VERSION}.nupkg"
    if not package.exists():
        with urllib.request.urlopen(URL, timeout=90) as response:
            payload = response.read(16 * 1024 * 1024)
        package.write_bytes(payload)
    if hashlib.sha256(package.read_bytes()).hexdigest() != PACKAGE_SHA256:
        raise ValueError(
            "The WebView2 SDK package does not match the pinned official artifact"
        )
    entries = {
        "Microsoft.Web.WebView2.Core.dll": "lib/net462/Microsoft.Web.WebView2.Core.dll",
        "Microsoft.Web.WebView2.WinForms.dll": "lib/net462/Microsoft.Web.WebView2.WinForms.dll",
        "netcore/Microsoft.Web.WebView2.Core.dll": "lib_manual/netcoreapp3.0/Microsoft.Web.WebView2.Core.dll",
        "netcore/Microsoft.Web.WebView2.WinForms.dll": "lib_manual/netcoreapp3.0/Microsoft.Web.WebView2.WinForms.dll",
        "LICENSE.txt": "LICENSE.txt",
        **{
            f"{arch}/WebView2Loader.dll": f"runtimes/win-{arch}/native/WebView2Loader.dll"
            for arch in ("x64", "x86", "arm64")
        },
    }
    inventory = {}
    with zipfile.ZipFile(package) as archive:
        for name, source in entries.items():
            payload = archive.read(source)
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            inventory[name] = {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
    receipt = {
        "version": VERSION,
        "source": URL,
        "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "files": inventory,
        "runtime_download": "https://developer.microsoft.com/microsoft-edge/webview2/",
    }
    (target / "inventory.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.cache, args.output)
