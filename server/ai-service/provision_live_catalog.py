"""Provision ALL files from the running world before the first measured turn.

The image bootstrap remains useful, but runtime-generated files and the
mounted SDK also belong to the complete catalogue. Copy them without changing
world, import their full bytes, and seal through the running AI's own store.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def command(*args, **kwargs):
    return subprocess.run(
        args, check=True, text=True, capture_output=True, **kwargs
    ).stdout


def identity(world):
    return command(
        "docker", "inspect", "--format", "{{.Image}} {{.State.StartedAt}}", world
    ).strip()


def provision(world="wakfu-local-world-1", ai="wakfu-local-ai-1"):
    before = identity(world)
    command(
        "docker", "exec", world, "python3", "/app/ai-service/prepare_catalog_cache.py"
    )
    with tempfile.TemporaryDirectory(prefix="wakfu-ai-live-catalog-") as directory:
        root = Path(directory) / "server"
        root.mkdir()
        command("docker", "cp", world + ":/app/.", str(root))
        if identity(world) != before:
            raise RuntimeError(
                "World changed during complete catalogue capture; rerun AI rebuild"
            )
        command(
            "docker",
            "exec",
            ai,
            "python3",
            "-c",
            "import pathlib,shutil; p=pathlib.Path('/native/live-world'); "
            "shutil.rmtree(p,ignore_errors=True); p.mkdir(parents=True)",
        )
        command("docker", "cp", str(root) + "/.", ai + ":/native/live-world")
    result = json.loads(
        command(
            "docker",
            "exec",
            ai,
            "python3",
            "catalog_bootstrap.py",
            "--root",
            "/native/live-world",
            "--store",
            "/var/lib/wakfu-ai-context",
        )
    )
    seal_code = """
import json, sys, urllib.request
payload=json.dumps({'sha256':sys.argv[1]}).encode()
request=urllib.request.Request('http://127.0.0.1:8090/v3/context/seal',data=payload,
                              headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=120) as response:
    result=json.load(response)
if result.get('complete') is not True:
    raise RuntimeError('Live world catalogue is incomplete')
print(json.dumps(result))
"""
    sealed = json.loads(
        command(
            "docker",
            "exec",
            "-i",
            ai,
            "python3",
            "-",
            result["sha256"],
            input=seal_code,
        )
    )
    if sealed.get("complete") is not True or sealed.get("entries") != result["entries"]:
        raise RuntimeError("Running AI did not seal the complete live catalogue")
    if identity(world) != before:
        raise RuntimeError(
            "World changed during complete catalogue provisioning; rerun AI rebuild"
        )
    print(
        json.dumps(
            dict(worldIdentity=before, catalogue=result, sealed=sealed), sort_keys=True
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", default="wakfu-local-world-1")
    parser.add_argument("--ai", default="wakfu-local-ai-1")
    args = parser.parse_args()
    provision(args.world, args.ai)
