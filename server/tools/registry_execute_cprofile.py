"""One-shot thread-filtered cProfile wrapper for Registry.execute."""
import cProfile
import json
import os
from pathlib import Path
import sys
import time
import threading
from datetime import datetime, timezone


def _wave(fight):
    fields = object.__getattribute__(fight, "__dict__")
    state = fields.get("rift_wave_state")
    wave = state.get("wave") if type(state) is dict else None
    return wave if type(wave) in (str, int) else None


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _dump_profile(profile, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.chmod(temporary, 0o600)
        finally:
            os.close(descriptor)
        profile.dump_stats(str(temporary))
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _isolate_profile_callbacks(profiler, owner_thread):
    """Filter cProfile's monitoring callbacks before they are registered."""
    for name in (
        "_pystart_callback",
        "_pyreturn_callback",
        "_ccall_callback",
        "_creturn_callback",
    ):
        original = getattr(profiler, name)

        def filtered(*args, _original=original):
            if threading.get_ident() != owner_thread:
                return None
            return _original(*args)

        setattr(profiler, name, filtered)


def install(
    registry_type, fight_type, *, fight_id, wave, opcode, profile_path, metadata_path
):
    """Profile one matching call; all nonmatching calls pass straight through."""
    if type(fight_id) is not int or type(wave) not in (str, int):
        raise ValueError("Exact fight ID and wave selectors are required")
    if type(opcode) is not int or opcode <= 0:
        raise ValueError("Exact request opcode selector is required")
    original = registry_type.__dict__.get("execute")
    if type(original) is not type(lambda: None):
        raise ValueError("Registry.execute must be an exact Python method")
    state = dict(
        registry_type=registry_type,
        original=original,
        fight_type=fight_type,
        fight_id=fight_id,
        wave=wave,
        opcode=opcode,
        profile_path=profile_path,
        metadata_path=metadata_path,
        wrapper=None,
        fired=False,
    )

    def wrapped(
        self,
        fight_id_arg,
        session,
        actor_id,
        operation,
        *,
        expected_sequence=None,
        require_turn=True,
        incident_request=None,
    ):
        original_call = state["original"]
        if state["fired"]:
            return original_call(
                self,
                fight_id_arg,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        if (
            type(fight_id_arg) is not int
            or fight_id_arg != state["fight_id"]
            or type(incident_request) is not dict
            or type(incident_request.get("opcode")) is not int
            or incident_request.get("opcode") != state["opcode"]
        ):
            return original_call(
                self,
                fight_id_arg,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )

        shared = None
        lock_held = False
        fight = None
        matched = False
        try:
            shared = self.lookup(fight_id_arg)
            shared.lock.acquire()
            lock_held = True
            fight = shared.fight
            current_wave = _wave(fight)
            matched = (
                type(fight) is state["fight_type"]
                and object.__getattribute__(fight, "id") == state["fight_id"]
                and type(current_wave) is type(state["wave"])
                and current_wave == state["wave"]
            )
        except BaseException:
            if lock_held:
                shared.lock.release()
            return original_call(
                self,
                fight_id_arg,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        if not matched:
            shared.lock.release()
            return original_call(
                self,
                fight_id_arg,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        try:
            return _profile_one(
                state,
                original_call,
                self,
                fight,
                fight_id_arg,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        finally:
            shared.lock.release()

    state["wrapper"] = wrapped
    registry_type.execute = wrapped
    return original


def _profile_one(
    state,
    original,
    registry,
    fight,
    fight_id,
    session,
    actor_id,
    operation,
    *,
    expected_sequence,
    require_turn,
    incident_request,
):
    registry_type = state["registry_type"]
    if registry_type.__dict__.get("execute") is state["wrapper"]:
        registry_type.execute = original

    profile_path = state["profile_path"]
    metadata_path = state["metadata_path"]
    opcode = state["opcode"]
    wave = state["wave"]
    turn_id = object.__getattribute__(fight, "turn_id")
    started_utc = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    state.update(
        registry_type=None,
        fight_type=None,
        fight_id=None,
        wave=None,
        opcode=None,
        profile_path=None,
        metadata_path=None,
        wrapper=None,
        fired=True,
    )

    status = "returned"
    try:
        profiler = cProfile.Profile()
    except BaseException:
        return original(
            registry,
            fight_id,
            session,
            actor_id,
            operation,
            expected_sequence=expected_sequence,
            require_turn=require_turn,
            incident_request=incident_request,
        )
    profiled = False
    try:
        monitoring = getattr(sys, "monitoring", None)
        profiler_tool = (
            None if monitoring is None else monitoring.get_tool(monitoring.PROFILER_ID)
        )
        if sys.getprofile() is not None or profiler_tool is not None:
            status = "skipped_existing_profiler"
            return original(
                registry,
                fight_id,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        try:
            _isolate_profile_callbacks(profiler, threading.get_ident())
            profiler.enable()
            profiled = True
        except BaseException:
            status = "skipped_profiler_setup_failure"
            try:
                profiler.disable()
            except BaseException:
                pass
            return original(
                registry,
                fight_id,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        return original(
            registry,
            fight_id,
            session,
            actor_id,
            operation,
            expected_sequence=expected_sequence,
            require_turn=require_turn,
            incident_request=incident_request,
        )
    except BaseException:
        status = "raised"
        raise
    finally:
        if profiled:
            try:
                profiler.disable()
            except BaseException:
                pass
        ended_utc = datetime.now(timezone.utc).isoformat()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        try:
            if profiled:
                _dump_profile(profiler, profile_path)
            _write_json(
                metadata_path,
                dict(
                    status=status,
                    fight_id=fight_id,
                    turn_id=turn_id,
                    wave=wave,
                    opcode=opcode,
                    started_utc=started_utc,
                    ended_utc=ended_utc,
                    elapsed_ms=elapsed_ms,
                    profile_file=Path(profile_path).name if profiled else None,
                    profiler_backend="cProfile/sys.monitoring/thread-filtered"
                    if profiled
                    else None,
                    profiler_thread_id=threading.get_ident() if profiled else None,
                    thread_isolated=bool(profiled),
                ),
            )
        except BaseException:
            pass


def install_from_environment(*, runtime_root):
    if os.environ.get("WAKFU_REGISTRY_EXECUTE_CPROFILE") != "1":
        return False
    combat_shared = sys.modules.get("wakfu_server.combat_shared")
    state_module = sys.modules.get("wakfu_server.combat_state")
    if combat_shared is None or state_module is None:
        raise RuntimeError("Combat transaction modules are not loaded at startup")
    registry_type = combat_shared.__dict__.get("Registry")
    fight_type = state_module.__dict__.get("Fight")
    if not isinstance(registry_type, type) or not isinstance(fight_type, type):
        raise RuntimeError("Combat Registry/Fight classes are not loaded at startup")
    fight_id = int(os.environ["WAKFU_REGISTRY_EXECUTE_CPROFILE_FIGHT_ID"])
    wave_text = os.environ["WAKFU_REGISTRY_EXECUTE_CPROFILE_WAVE"]
    wave = int(wave_text) if wave_text.isdecimal() else wave_text
    opcode = int(os.environ.get("WAKFU_REGISTRY_EXECUTE_CPROFILE_OPCODE", "12403"))
    root = Path(
        os.environ.get(
            "WAKFU_REGISTRY_EXECUTE_CPROFILE_DIR",
            Path(runtime_root) / "logs" / "profiles",
        )
    )
    wave_label = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in str(wave)
    )[:32]
    stem = f"registry-execute-f{fight_id}-w{wave_label}-op{opcode}"
    install(
        registry_type,
        fight_type,
        fight_id=fight_id,
        wave=wave,
        opcode=opcode,
        profile_path=root / (stem + ".prof"),
        metadata_path=root / (stem + ".json"),
    )
    return True
