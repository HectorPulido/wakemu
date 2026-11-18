"""Typed noncombat ownership for native order-trial mode selection.

Physical arrival and return never assign a mission, grant a score or invent a
fight. The separately qualified native mode producer owns those mechanics.
"""

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "owned-native-order-context-v1"


@lru_cache(maxsize=8)
def _document(name, digest):
    if Path(name).name != name or not name.endswith(".json"):
        raise ValueError("Order context source escapes its reviewed directory")
    path = Path(__file__).parents[1] / "achievements/order_trial_profiles" / name
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError("Order context source attestation changed")
    return json.loads(raw)


def policy(configuration):
    """Qualify the existing zero-room story scope, with no mission effects."""
    topology = configuration.get("topology", {})
    controller = topology.get("owned_story_controller")
    value = (
        controller.get("native_order_trial_context")
        if isinstance(controller, dict)
        else None
    )
    if value is None:
        return None
    if (
        type(value) is not dict
        or set(value)
        != {
            "schema",
            "id",
            "quest_id",
            "scenario_id",
            "ready_step",
            "admission_source",
            "geometry_source",
        }
        or value["schema"] != SCHEMA
        or any(
            type(value[key]) is not int or value[key] <= 0
            for key in ("quest_id", "scenario_id")
        )
        or any(
            type(value[key]) is not str or not value[key]
            for key in ("id", "ready_step")
        )
    ):
        raise ValueError("Invalid native order context declaration")
    from wakfu_server import owned_noncombat_context

    selected = owned_noncombat_context.selected(topology)
    if selected is None or topology.get("policy") != owned_noncombat_context.NARRATIVE:
        raise ValueError("Native order context requires its typed noncombat ownership")
    if (
        selected["admission"]
        != dict(
            quest_id=value["quest_id"],
            objective_id=None,
            continuation_quest_id=value["quest_id"],
        )
        or len(selected["steps"]) != 1
        or selected["steps"][0]["id"] != value["ready_step"]
        or selected["steps"][0]["kind"] != "world_ready"
        or selected["steps"][0]["reference"] != selected["map_id"]
        or selected["steps"][0]["requires"]
        or selected["steps"][0]["effects"]
        or not topology.get("native_story_exits")
    ):
        raise ValueError(
            "Order context arrival cannot assign progress, rewards or scenes"
        )
    documents = []
    for key in ("admission_source", "geometry_source"):
        pin = value[key]
        if (
            type(pin) is not dict
            or set(pin) != {"path", "sha256"}
            or type(pin["path"]) is not str
            or type(pin["sha256"]) is not str
            or len(pin["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in pin["sha256"])
        ):
            raise ValueError("Native order context lacks an immutable source")
        documents.append(_document(pin["path"], pin["sha256"]))
    admission, geometry = documents
    from wakfu_server.native_order_trial_admission import validate as validate_admission

    validate_admission(admission)
    if (
        admission["context"]["map_id"] != selected["map_id"]
        or geometry["map_id"] != selected["map_id"]
        or geometry.get("schema") != "reviewed-native-order-trial-layout-v1"
    ):
        raise ValueError("Order context differs from its native map")
    from wakfu_server import owned_story_mechanics

    native = owned_story_mechanics.sources(selected)
    if (
        native["scenario_id"] != value["scenario_id"]
        or native["scenario_events"]
        or native["scenes"]
    ):
        raise ValueError("Order context cannot replay native gameplay presentation")
    return value


def scope(db, store, character):
    """Return the authenticated context independently of quest assignment."""
    from wakfu_server import dungeon_runtime, owned_story_controller

    _, configuration = dungeon_runtime.configuration_for_instance(
        db, character["instance_id"]
    )
    selected = policy(configuration)
    if selected is None:
        raise ValueError("Owned map is not a declared native order context")
    controller, completed = owned_story_controller._scope(db, store, character)
    if controller["native_order_trial_context"] != selected:
        raise ValueError("Order context membership changed its pinned policy")
    return dict(
        configuration=configuration,
        policy=selected,
        controller=controller,
        completed_steps=completed,
    )


def geometry(configuration):
    """Return the immutable geometry already qualified by this context policy."""
    selected = policy(configuration)
    if selected is None:
        raise ValueError("Owned map is not a declared native order context")
    pin = selected["geometry_source"]
    return deepcopy(_document(pin["path"], pin["sha256"]))


def admission(configuration):
    """Return the immutable native mode declaration qualified by this context."""
    selected = policy(configuration)
    if selected is None:
        raise ValueError("Owned map is not a declared native order context")
    pin = selected["admission_source"]
    return deepcopy(_document(pin["path"], pin["sha256"]))
