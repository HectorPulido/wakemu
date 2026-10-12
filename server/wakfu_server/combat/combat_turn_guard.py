"""Isolate shared NPC preparation failures from the owner's transport."""
from .combat_effective_control import effective_server_controlled
import time
import uuid


def run_shared_npc_attempt(shared, operation, failed, *, clock=time.monotonic):
    with shared.lock:
        actor = shared.fight.current
        runtime = shared.runtime
        if (
            shared.fight.phase != "active"
            or actor is None
            or not effective_server_controlled(shared.fight, actor)
            or runtime is None
            or runtime.awaiting_ack is not None
            or runtime.pending
        ):
            return False
        identity = (actor.id, shared.fight.turn_id)
        previous = getattr(shared, "native_npc_retry", None)
        if previous is not None and previous[0] == identity and clock() < previous[1]:
            return False
        if getattr(shared, "native_npc_retry_claim", None) is not None:
            return False
        # The AI bridge freezes SharedFight metadata with its lossless graph
        # codec. A primitive token preserves identity without an opaque object.
        claim = uuid.uuid4().hex
        shared.native_npc_retry_claim = claim
    try:
        operation()
    except (EOFError, OSError, MemoryError):
        raise  # Transport/resource failures keep their existing cleanup path.
    except Exception as error:
        with shared.lock:
            shared.native_npc_retry = (identity, clock() + 2.0)
        try:
            failed(identity, error)
        except (EOFError, OSError, MemoryError):
            raise
        except Exception as diagnostic_error:
            # Do not let diagnostic formatting undo the gameplay boundary.
            # Keep bounded type-only evidence: messages can contain secrets.
            with shared.lock:
                shared.native_npc_retry_diagnostic_failure = {
                    "actor_id": identity[0],
                    "turn_id": identity[1],
                    "original_error_type": type(error).__name__[:128],
                    "diagnostic_error_type": type(diagnostic_error).__name__[:128],
                }
        return False
    finally:
        with shared.lock:
            if getattr(shared, "native_npc_retry_claim", None) == claim:
                shared.native_npc_retry_claim = None
    with shared.lock:
        shared.native_npc_retry = None
    return True
