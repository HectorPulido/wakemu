"""Private versioned QI/QL checkpoint and atomic937 transaction boundary.

Only owned spatial state is snapshotted here. The caller's whole-fight
transaction still owns resources, global collections, packets and other effects.
"""
from contextlib import contextmanager
from copy import deepcopy
from .combat_trove_byte_set import NativeTroveByteSet
from .combat_pointer_qi_actor import ActualRetained937, RetainedContext
from .combat_pointer_qi_hashset import qf_clear_order

SCHEMA = "native.QI.pointer_QL_history937.private.v1"


def checkpoint(qi, runners):
    if len({runner.uid for runner in runners}) != len(runners):
        raise ValueError("Duplicate retained UID")
    objects = tuple(qi.objects.values()) + tuple(qi.area_objects.values())
    keys = {id(obj): index for index, obj in enumerate(objects)}
    for runner in runners:
        if (
            not isinstance(runner, ActualRetained937)
            or runner.target is not None
            and id(runner.target) not in keys
        ):
            raise ValueError("Missing canonical actual retained QK")
        if runner.context is not None and runner.context.qi not in (None, qi):
            raise ValueError("Mismatched retained PN/QI context")
    return dict(
        schema=SCHEMA,
        objects=objects,
        actors=[
            dict(
                position=obj.actor.position,
                byte=obj.byte,
                physical_position=obj.actor.native_physical_position,
            )
            if obj.kind == "actor"
            else dict(cell=deepcopy(obj.row["cell"]), byte=obj.byte)
            for obj in objects
        ],
        slots=[None if obj is None else keys[id(obj)] for obj in qi.slots],
        cells={cell: deepcopy(value.state) for cell, value in qi.cells.items()},
        anchors=deepcopy(qi.anchors),
        runners=tuple(runners),
        runner_states=[
            (
                runner.target,
                runner.context,
                runner.executed,
                None if runner.context is None else runner.context.qi,
            )
            for runner in runners
        ],
    )


def restore(qi, runners, state):
    if (
        state.get("schema") != SCHEMA
        or tuple(qi.objects.values()) + tuple(qi.area_objects.values())
        != state["objects"]
    ):
        raise ValueError("Mismatched actual QI checkpoint owner")
    # Restore actual pointers/coordinates in place, preserving all Actor identities.
    for obj, row in zip(state["objects"], state["actors"]):
        if obj.kind == "actor":
            obj.actor.position = row["position"]
            obj.actor.native_physical_position = row["physical_position"]
        else:
            obj.row["cell"] = deepcopy(row["cell"])
        obj.byte = row["byte"]
    qi.slots = [
        None if key is None else state["objects"][key] for key in state["slots"]
    ]
    qi.cells = {
        cell: NativeTroveByteSet(deepcopy(value))
        for cell, value in state["cells"].items()
    }
    qi.anchors = deepcopy(state["anchors"])
    runners[:] = state["runners"]
    for runner, (target, context, executed, context_qi) in zip(
        runners, state["runner_states"]
    ):
        runner.target, runner.context, runner.executed = target, context, executed
        if context is not None:
            context.qi = context_qi


@contextmanager
def spatial_transaction(qi, runners, *, forecast=False):
    before = checkpoint(qi, runners)
    try:
        yield
    except BaseException:
        restore(qi, runners, before)
        raise
    else:
        if forecast:
            restore(qi, runners, before)


def clear_manager_native_order(runners, events):
    indexed = {runner.uid: runner for runner in runners}
    order = qf_clear_order(tuple(runner.uid for runner in runners))
    for uid in order:
        runner = indexed[uid]
        events.append(("bbR", uid))
        runner.remove_runner()
        events.append(("dispose", uid))
    runners.clear()
