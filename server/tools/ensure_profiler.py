"""Reattach the profiler after World replacement; never restart World."""
import argparse
import json
from pathlib import Path
import subprocess


def inspect(name):
    result = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def needs_recovery(world, profiler):
    if not world or not world["State"].get("Running"):
        return False
    if world["State"].get("Health", {}).get("Status") != "healthy":
        return False
    return (
        not profiler
        or not profiler["State"].get("Running")
        or profiler["HostConfig"].get("PidMode") != "container:" + world["Id"]
        or profiler["State"].get("Health", {}).get("Status") == "unhealthy"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project", default="wakemu-linux")
    args = parser.parse_args()
    root = args.root.resolve()
    world_name = args.project + "-world-1"
    profiler_name = args.project + "-profiler-1"
    world, profiler = inspect(world_name), inspect(profiler_name)
    if not needs_recovery(world, profiler):
        return
    lock = root / ".runtime/world-deploy.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        return
    try:
        (lock / "owner").write_text("profiler-supervisor")
        world, profiler = inspect(world_name), inspect(profiler_name)
        if not needs_recovery(world, profiler):
            return
        configs = world["Config"]["Labels"][
            "com.docker.compose.project.config_files"
        ].split(",")
        overlay = root / ".runtime/profiler-window-20261013/compose.json"
        configs += [str(root / "compose.profiler.yaml")]
        if overlay.is_file():
            configs.append(str(overlay))
        command = ["docker", "compose", "-p", args.project]
        for config in dict.fromkeys(configs):
            command += ["-f", config]
        subprocess.run(
            command
            + ["up", "-d", "--no-deps", "--no-build", "--force-recreate", "profiler"],
            cwd=root,
            check=True,
            timeout=90,
        )
        after = inspect(world_name)
        if not after or after["Id"] != world["Id"]:
            raise RuntimeError("World changed concurrently during profiler recovery")
        print("Profiler reattached to World " + world["Id"], flush=True)
    finally:
        (lock / "owner").unlink(missing_ok=True)
        lock.rmdir()


if __name__ == "__main__":
    main()
