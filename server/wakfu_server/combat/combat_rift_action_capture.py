"""One opt-in private end-turn diagnostic, before Registry publication.

No source service is replaced. Capture failures never retry or reject gameplay.
The existing private incident writer owns persistence/quota; no private payload
is logged. Enable only for one explicit local fight and a minimum wave.
"""
from datetime import datetime, timezone
import logging
import os
import sys
import threading
import time

LOGGER = logging.getLogger(__name__)
_LOCK = threading.Lock()
_CLAIMED = False


def _configuration():
    root = os.environ.get("WAKFU_RIFT_ACTION_CAPTURE_DIR")
    if not root:
        return None
    try:
        fight = int(os.environ["WAKFU_RIFT_ACTION_CAPTURE_FIGHT"])
        wave = int(os.environ["WAKFU_RIFT_ACTION_CAPTURE_MIN_WAVE"])
        if fight <= 0 or wave < 1:
            raise ValueError("positive selectors required")
        return root, fight, wave
    except (KeyError, ValueError):
        LOGGER.warning("rift_action_capture_disabled reason=invalid_selectors")
        return None


_CONFIG = _configuration()


def _claim(runtime):
    global _CLAIMED
    if _CONFIG is None or _CLAIMED:
        return False
    from .combat_runtime_messages import RuntimeMessages
    from .combat_state import Fight

    if type(runtime) is not RuntimeMessages or type(runtime.fight) is not Fight:
        return False
    fields = vars(runtime.fight)
    wave = fields.get("rift_wave_state")
    if (
        fields.get("id") != _CONFIG[1]
        or type(wave) is not dict
        or type(wave.get("wave")) is not int
        or wave["wave"] < _CONFIG[2]
    ):
        return False
    with _LOCK:
        if _CLAIMED:
            return False
        _CLAIMED = True  # One attempt, even when unsupported or persistence fails.
    return True


def _save(receipt):
    try:
        from .combat_incident_capture import _enqueue

        _enqueue(_CONFIG[0], receipt)
    except Exception as error:
        LOGGER.warning(
            "rift_action_capture_failed stage=persist type=%s", type(error).__name__
        )


def _failure(receipt, stage, error):
    entry = {"stage": stage, "type": type(error).__name__}
    try:
        message = " ".join(str(error).split())
        entry["message"] = message[:768]
        entry["message_truncated"] = len(message) > 768
    except BaseException:
        entry["message"] = "<exception message unavailable>"
        entry["message_truncated"] = False
    frames = []
    truncated = False
    try:
        tb = error.__traceback__
        while tb is not None:
            frames.append(
                {
                    "file": os.path.basename(tb.tb_frame.f_code.co_filename),
                    "line": tb.tb_lineno,
                    "function": tb.tb_frame.f_code.co_name,
                }
            )
            tb = tb.tb_next
        truncated = len(frames) > 12
        frames = frames[-12:]
    except BaseException:
        frames = []
        truncated = True
    entry["traceback"] = frames
    entry["traceback_truncated"] = truncated
    receipt["incomplete"] = [entry]
    _save(receipt)


def capture_end_turn(runtime, owner_id, actor_id, turn_id, *, boundary):
    """Called inside the caller's owned scope; invoke original boundary once."""
    if not _claim(runtime):
        return boundary(owner_id, actor_id, turn_id)
    receipt = {
        "incident_id": "rift-private-end-turn-f%s-t%s" % (_CONFIG[1], turn_id),
        "scope": "private-end-turn-before-publication",
        "publication_observed": False,
        "wave_at_capture": vars(runtime.fight)["rift_wave_state"]["wave"],
        "incomplete": [],
        "action": {
            "type": "end_turn",
            "owner_id": owner_id,
            "actor_id": actor_id,
            "turn_id": turn_id,
        },
    }
    try:
        from .combat_input_observation import _active, InputReplayMismatch

        if _active.get() is not None:
            raise InputReplayMismatch("Existing incident observer owns this operation")
        from .combat_rift_action_reproduction import (
            capture_before,
            observe_operation,
            finish_capture,
        )

        captured = capture_before(runtime, receipt["action"])
        receipt.update(captured)
        observation = observe_operation(runtime)
        tape = observation.__enter__()
    except Exception as error:
        _failure(receipt, "before", error)
        return boundary(owner_id, actor_id, turn_id)
    started = time.perf_counter_ns()
    receipt["operation_started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        packets = boundary(owner_id, actor_id, turn_id)
    except BaseException as error:
        ended = time.perf_counter_ns()
        try:
            observation.__exit__(*sys.exc_info())
        except Exception:
            pass
        receipt["operation_duration_ns"] = ended - started
        _failure(receipt, "operation", error)
        raise
    ended = time.perf_counter_ns()
    receipt["operation_finished_at"] = datetime.now(timezone.utc).isoformat()
    receipt["operation_duration_ns"] = ended - started
    wave_after = vars(runtime.fight).get("rift_wave_state")
    receipt["wave_after_operation"] = (
        wave_after.get("wave") if type(wave_after) is dict else None
    )
    receipt["timing_scope"] = "boundary_with_input_observer_excluding_snapshot_encoding"
    try:
        observation.__exit__(None, None, None)
        receipt = finish_capture(
            receipt, runtime, packets, tape, action=receipt["action"]
        )
    except Exception as error:
        try:
            from .combat_reproduction_state import encode_state

            receipt["unsupported_after_runtime"] = encode_state(
                runtime, preserve_scalars=True
            )
            receipt["unsupported_observations"] = encode_state(
                tape.snapshot(), preserve_scalars=True
            )
        except Exception as evidence_error:
            receipt["after_evidence_error"] = type(evidence_error).__name__
        _failure(receipt, "after", error)
    else:
        _save(receipt)
    return packets
