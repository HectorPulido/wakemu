"""Reattach the profiler after World replacement; never restart World."""
import argparse
import json
from pathlib import Path
import subprocess


def inspect(name):
    result = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def mount_source(container, destination):
    mounts = [
        row
        for row in (container or {}).get("Mounts", ())
        if row.get("Destination") == destination
    ]
    source = mounts[0].get("Source") if len(mounts) == 1 else None
    if not isinstance(source, str) or not Path(source).is_absolute():
        raise ValueError("Missing unique absolute container mount: " + destination)
    return source


def expected_metrics_source(world):
    """The running World's actual storage is authoritative, never a stage cwd."""
    return str(Path(mount_source(world, "/data")) / "logs" / "profiles")


def binding_errors(world, profiler):
    if not profiler:
        return ["profiler_missing"]
    errors = []
    if profiler.get("HostConfig", {}).get("PidMode") != "container:" + world["Id"]:
        errors.append("world_pid_namespace_mismatch")
    try:
        if mount_source(profiler, "/metrics") != expected_metrics_source(world):
            errors.append("world_metrics_storage_mismatch")
        elif any(
            row.get("RW") is not False
            for row in profiler.get("Mounts", ())
            if row.get("Destination") == "/metrics"
        ):
            errors.append("world_metrics_mount_not_read_only")
    except ValueError:
        errors.append("world_metrics_mount_unavailable")
    return errors


def recovery_overlay(root, world, profiler):
    """Pin storage and PID explicitly while preserving existing profiler artifacts."""
    volumes = [
        dict(
            type="bind",
            source=expected_metrics_source(world),
            target="/metrics",
            read_only=True,
        )
    ]
    output = (
        mount_source(profiler, "/profiles")
        if profiler
        else str(root / ".local-state" / "wakemu" / "profiler")
    )
    volumes.append(dict(type="bind", source=output, target="/profiles"))
    service = dict(pid="container:" + world["Id"], volumes=volumes)
    if profiler:
        image = profiler.get("Image") or profiler.get("Config", {}).get("Image")
        if image:
            service["image"] = image
    return dict(services=dict(profiler=service))


def validate_recovery(before, after, profiler, overlay):
    if not after or after["Id"] != before["Id"]:
        raise RuntimeError("World changed concurrently during profiler recovery")
    errors = binding_errors(after, profiler)
    output = next(
        row["source"]
        for row in overlay["services"]["profiler"]["volumes"]
        if row["target"] == "/profiles"
    )
    try:
        if mount_source(profiler, "/profiles") != output:
            errors.append("profiler_archive_storage_changed")
    except ValueError:
        errors.append("profiler_archive_storage_unavailable")
    if errors:
        raise RuntimeError(
            "Profiler recovery left invalid bindings: " + ", ".join(errors)
        )


def needs_recovery(world, profiler):
    if not world or not world["State"].get("Running"):
        return False
    if world["State"].get("Health", {}).get("Status") != "healthy":
        return False
    return (
        not profiler
        or not profiler["State"].get("Running")
        or bool(binding_errors(world, profiler))
        or profiler["State"].get("Health", {}).get("Status") == "unhealthy"
    )


def check_status(world, profiler):
    """Report bindings and service readiness without scheduling any recovery."""
    errors = binding_errors(world, profiler) if world else ["world_missing"]
    services = {}
    for name, container in (("world", world), ("profiler", profiler)):
        state = (container or {}).get("State", {})
        running = state.get("Running") is True
        health = state.get("Health", {}).get("Status")
        services[name] = dict(running=running, health=health)
        if not container:
            if name + "_missing" not in errors:
                errors.append(name + "_missing")
        elif not running:
            errors.append(name + "_not_running")
        elif health != "healthy":
            errors.append(name + "_not_healthy")
    return dict(
        errors=errors,
        services=services,
        recoveryNeeded=needs_recovery(world, profiler),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project", default="wakemu-linux")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Inspect bindings without changing services",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    world_name = args.project + "-world-1"
    profiler_name = args.project + "-profiler-1"
    world, profiler = inspect(world_name), inspect(profiler_name)
    if args.check:
        status = check_status(world, profiler)
        print(json.dumps(status, sort_keys=True))
        return 1 if status["errors"] else 0
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
        storage_overlay = root / ".runtime/profiler-storage-binding.json"
        binding_overlay = recovery_overlay(root, world, profiler)
        storage_overlay.write_text(json.dumps(binding_overlay))
        configs.append(str(storage_overlay))
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
        validate_recovery(world, after, inspect(profiler_name), binding_overlay)
        print("Profiler reattached to World " + world["Id"], flush=True)
    finally:
        (lock / "owner").unlink(missing_ok=True)
        lock.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
