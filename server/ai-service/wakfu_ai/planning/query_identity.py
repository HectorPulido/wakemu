"""Runtime identity for search; receipt hashes remain retrieval references."""
import re


def identity(state):
    if "runtimeIdentity" not in state:
        return state["key"]
    value = state["runtimeIdentity"]
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid complete native runtime identity")
    return value
