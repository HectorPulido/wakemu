"""Trusted offline movement comparisons; never executes a live commit/delivery.

Recipes rebuild providers explicitly. This runner is not a sandbox: recipes must
not reference live stores, sockets or global mutable combat authorities.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from random import Random

from wakfu_server.combat_reproduction_state import encode_state


class DifferentialSetupError(ValueError):
    """A fixture cannot support an independent old/new observation."""


def _capture(value):
    captured = encode_state(value)
    if captured["services"]:
        raise DifferentialSetupError("Projection contains omitted runtime services")
    return captured


def _mutable_owners(value, seen=None):
    """Inspect instance data, without executing properties or provider callbacks."""
    seen = set() if seen is None else seen
    identity = id(value)
    if identity in seen:
        return set()
    seen.add(identity)
    if value is None or type(value) in (bool, int, float, str, bytes, range, type):
        return set()
    if type(value) in (tuple, frozenset):
        result = set()
        for item in value:
            result.update(_mutable_owners(item, seen))
        return result
    result = {identity}
    if isinstance(value, dict):
        children = [*value.keys(), *value.values()]
    elif isinstance(value, (list, set)):
        children = list(value)
    else:
        children = []
    # Native mapping subclasses keep their live owners in instance attributes.
    # Inspect both representations; treating mapping contents as the complete
    # object misses ObservableCharacteristicStats._fight and checkpoint._qi.
    if hasattr(value, "__dict__"):
        children.extend(vars(value).values())
    for item in children:
        result.update(_mutable_owners(item, seen))
    return result


@dataclass
class OfflineContext:
    """Explicit deterministic providers and operation-local observation sinks."""

    rng: Random
    fixed_clock_ns: int
    events: list = field(default_factory=list)
    packets: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    clock_reads: int = 0
    _closed: bool = False

    def _open(self):
        if self._closed:
            raise DifferentialSetupError("Observation context is already closed")

    def clock_ns(self):
        self._open()
        self.clock_reads += 1
        return self.fixed_clock_ns

    def event(self, value):
        self._open()
        observation = _capture(value)
        self.events.append(observation)
        self.observations.append({"kind": "event", "value": deepcopy(observation)})

    def packet(self, recipient, opcode, payload):
        self._open()
        if type(opcode) is not int or not 0 <= opcode <= 65535:
            raise DifferentialSetupError(
                "Packet opcode must be an unsigned 16-bit integer"
            )
        if type(payload) is not bytes:
            raise DifferentialSetupError("Packet payload must be immutable bytes")
        observation = {
            "recipient": _capture(recipient),
            "opcode": opcode,
            "payload": payload.hex(),
        }
        self.packets.append(observation)
        self.observations.append({"kind": "packet", "value": deepcopy(observation)})


def _differences(old, new, path, output):
    if type(old) is not type(new):
        output.append({"path": path, "old": old, "new": new})
    elif type(old) is dict:
        for key in dict.fromkeys([*old, *new]):
            child = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in old or key not in new:
                output.append(
                    {
                        "path": child,
                        "old_present": key in old,
                        "new_present": key in new,
                        "old": old.get(key),
                        "new": new.get(key),
                    }
                )
            else:
                _differences(old[key], new[key], child, output)
    elif type(old) is list:
        for index in range(max(len(old), len(new))):
            child = path + "/" + str(index)
            if index >= len(old) or index >= len(new):
                output.append(
                    {
                        "path": child,
                        "old_present": index < len(old),
                        "new_present": index < len(new),
                        "old": old[index] if index < len(old) else None,
                        "new": new[index] if index < len(new) else None,
                    }
                )
            else:
                _differences(old[index], new[index], child, output)
    elif old != new:
        output.append({"path": path, "old": old, "new": new})


def compare_movement(
    *,
    case_id,
    make_world,
    legacy,
    candidate,
    project_state,
    inputs=None,
    rng_state=None,
    clock_ns=1700000000000000000,
    classify_difference=None
):
    """Run both trusted recipes independently and retain exact observations.

    Factory signature: ``make_world(context)``. Execution signature:
    ``operation(world, inputs, context)``. Projection must include resources,
    ownership, registration and pending queues relevant to the scenario.
    Exceptions are observations, never successful actions. A classification
    callback may label each difference expected/erroneous/unresolved; it cannot
    erase a difference or convert byte equality into native-client proof.
    """
    if not isinstance(case_id, str) or not case_id:
        raise DifferentialSetupError("A stable case identity is required")
    if type(clock_ns) is not int:
        raise DifferentialSetupError("Clock must be an integer nanosecond observation")
    initial_rng = Random(0).getstate() if rng_state is None else deepcopy(rng_state)
    contexts = [OfflineContext(Random(), clock_ns), OfflineContext(Random(), clock_ns)]
    for context in contexts:
        context.rng.setstate(initial_rng)
    worlds = [make_world(context) for context in contexts]
    if _mutable_owners(worlds[0]) & _mutable_owners(worlds[1]):
        raise DifferentialSetupError(
            "Legacy and candidate worlds share mutable instance data"
        )
    before = [_capture(project_state(world)) for world in worlds]
    if before[0] != before[1]:
        raise DifferentialSetupError("Legacy and candidate initial projections differ")
    if contexts[0].rng.getstate() != contexts[1].rng.getstate():
        raise DifferentialSetupError("Factories consumed different RNG observations")
    if (
        contexts[0].events,
        contexts[0].packets,
        contexts[0].observations,
        contexts[0].clock_reads,
    ) != (
        contexts[1].events,
        contexts[1].packets,
        contexts[1].observations,
        contexts[1].clock_reads,
    ):
        raise DifferentialSetupError(
            "Factories produced different initial observations"
        )
    observations = []
    for world, context, operation in zip(worlds, contexts, (legacy, candidate)):
        result, error = None, None
        try:
            result = operation(world, deepcopy(inputs), context)
        except DifferentialSetupError:
            raise
        except Exception as raised:
            error = {
                "type": type(raised).__module__ + "." + type(raised).__qualname__,
                "message": str(raised),
            }
        finally:
            context._closed = True
        observations.append(
            {
                "state": _capture(project_state(world)),
                "result": _capture(result),
                "error": error,
                "events": deepcopy(context.events),
                "packets": deepcopy(context.packets),
                "observations": deepcopy(context.observations),
                "rng_state": _capture(context.rng.getstate()),
                "clock_reads": context.clock_reads,
            }
        )
    # An operation must not mutate the other branch through an undeclared alias.
    if _capture(project_state(worlds[0])) != observations[0]["state"]:
        raise DifferentialSetupError("Candidate changed the completed legacy world")
    differences = []
    _differences(*observations, "", differences)
    for difference in differences:
        classification = (
            "unresolved"
            if classify_difference is None
            else classify_difference(deepcopy(difference))
        )
        if classification not in ("expected", "erroneous", "unresolved"):
            raise DifferentialSetupError("Invalid difference classification")
        difference["classification"] = classification
    return {
        "schema": "wakemu-movement-differential-v2",
        "case_id": case_id,
        "equivalent": not differences,
        "actions_succeeded": all(item["error"] is None for item in observations),
        "before": before[0],
        "legacy": observations[0],
        "candidate": observations[1],
        "differences": differences,
        "live_delivery": False,
        "native_client_qualified": False,
        "limitations": [
            "Trusted offline recipes only; no process sandbox or live commit.",
            "Equality covers the explicitly supplied full-state projection and provider observations.",
            "Packet equality does not certify native execution, animation or ACK completion.",
        ],
    }


def observe_movement(
    *,
    case_id,
    make_world,
    operation,
    project_state,
    inputs=None,
    rng_state=None,
    clock_ns=1700000000000000000
):
    """Record one actual current execution; this is not a differential witness."""
    if not isinstance(case_id, str) or not case_id:
        raise DifferentialSetupError("A stable case identity is required")
    if type(clock_ns) is not int:
        raise DifferentialSetupError("Clock must be an integer nanosecond observation")
    context = OfflineContext(Random(), clock_ns)
    context.rng.setstate(
        Random(0).getstate() if rng_state is None else deepcopy(rng_state)
    )
    world = make_world(context)
    before = _capture(project_state(world))
    result, error = None, None
    try:
        result = operation(world, deepcopy(inputs), context)
    except DifferentialSetupError:
        raise
    except Exception as raised:
        error = {
            "type": type(raised).__module__ + "." + type(raised).__qualname__,
            "message": str(raised),
        }
    finally:
        context._closed = True
    observation = {
        "state": _capture(project_state(world)),
        "result": _capture(result),
        "error": error,
        "events": deepcopy(context.events),
        "packets": deepcopy(context.packets),
        "observations": deepcopy(context.observations),
        "rng_state": _capture(context.rng.getstate()),
        "clock_reads": context.clock_reads,
    }
    return {
        "schema": "wakemu-current-movement-observation-v1",
        "case_id": case_id,
        "action_succeeded": error is None,
        "before": before,
        "current": observation,
        "live_delivery": False,
        "native_client_qualified": False,
        "limitations": [
            "One trusted current offline execution; no historical equivalence claim.",
            "Native/behavior assertions remain the consumer's responsibility.",
        ],
    }
