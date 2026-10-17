"""Pure, bounded diagnostics at completed combat action boundaries.

This module never calls gameplay validators, providers, clocks or catalogs.
It does not repair state or veto adoption. Missing native authority is reported
as unknown coverage, independently of contradictions in available facts.
"""
from dataclasses import dataclass
import sys


@dataclass(frozen=True)
class Boundary:
    operation: str
    stage: str
    runtime_binding: str = "candidate"

    def __post_init__(self):
        if (
            type(self.operation) is not str
            or not self.operation
            or self.stage not in ("prepared", "pre_adoption", "adopted")
            or self.runtime_binding not in ("candidate", "source")
        ):
            raise ValueError("Explicit completed operation boundary required")


@dataclass(frozen=True)
class Finding:
    invariant: str
    path: str
    status: str
    reason: str


@dataclass(frozen=True)
class BoundaryReport:
    boundary: Boundary
    findings: tuple
    checked: tuple
    actor_count: int
    resource_identity: tuple = ()

    @property
    def violations(self):
        return tuple(row for row in self.findings if row.status == "violation")

    @property
    def unknown(self):
        return tuple(row for row in self.findings if row.status == "unknown")

    def as_dict(self):
        return dict(
            operation=self.boundary.operation,
            boundary=self.boundary.stage,
            checked=list(self.checked),
            actor_count=self.actor_count,
            resource_authority=(
                dict(
                    zip(
                        ("revision", "actor_sha256", "copy_sha256"),
                        self.resource_identity,
                    )
                )
                if self.resource_identity
                else None
            ),
            findings=[
                dict(
                    invariant=f.invariant, path=f.path, status=f.status, reason=f.reason
                )
                for f in self.findings
            ],
        )

    def raise_if_violated(self):
        if self.violations:
            row = self.violations[0]
            raise CombatInvariantError(self, row)


class CombatInvariantError(AssertionError):
    def __init__(self, report, finding):
        self.report, self.finding = report, finding
        super().__init__(
            f"{report.boundary.operation} [{report.boundary.stage}] "
            f"{finding.invariant} at {finding.path}: {finding.reason}"
        )


def check_prepared_boundary(
    fight, runtime, boundary, *, resource_authority=None, ack=None
):
    """Inspect trusted owned objects without invoking properties or deepcopy.

    Findings contain relationship descriptions, not private values. This first
    slice checks available actor/state/resource/timeline/queue/listener facts.
    Canonical QI and retained population completeness have separate coverage
    findings until their dedicated adapters are installed.
    """
    from .combat_state import Fight, Actor
    from .combat_state_ledger import StateLedger, RunningState
    from .combat_invariant_resources import ResourceAuthority

    # An actual runtime/stats wrapper already loaded its defining module.
    # Importing RuntimeMessages here when runtime=None would load the native
    # action-packet catalog solely for diagnostics, violating read-only checks.
    runtime_module = sys.modules.get(__package__ + ".combat_runtime_messages")
    runtime_type = (
        vars(runtime_module).get("RuntimeMessages")
        if runtime_module is not None
        else None
    )
    stats_module = sys.modules.get(__package__ + ".combat_characteristic_link")
    stats_type = (
        vars(stats_module).get("ObservableCharacteristicStats")
        if stats_module is not None
        else None
    )

    if type(boundary) is not Boundary:
        raise ValueError("Typed boundary descriptor required")
    if (
        type(fight) is not Fight
        or runtime is not None
        and type(runtime) is not runtime_type
    ):
        raise ValueError("Trusted Fight and RuntimeMessages required")
    if (
        resource_authority is not None
        and type(resource_authority) is not ResourceAuthority
    ):
        raise ValueError("Typed hash-bound resource authority required")
    resource_identity = (
        ()
        if resource_authority is None
        else (
            resource_authority.revision,
            resource_authority.actor_sha256,
            resource_authority.copy_sha256,
        )
    )
    state, owned_runtime = vars(fight), vars(runtime) if runtime is not None else {}
    findings, checked = [], []

    def issue(name, path, reason, status="violation"):
        if len(findings) < 256:
            findings.append(Finding(name, path, status, reason))
        elif len(findings) == 256:
            findings.append(
                Finding(
                    "coverage.limit", "fight", "unknown", "Additional findings omitted"
                )
            )

    def unknown(name, path, reason):
        issue(name, path, reason, "unknown")

    if state.get("_resolution_depth") != 0:
        issue(
            "boundary.stable",
            "fight._resolution_depth",
            "Completed boundary still contains an outer effect resolution",
        )
    if runtime is None:
        unknown("runtime.authority", "runtime", "Placement has no runtime projection")
    elif boundary.runtime_binding == "candidate":
        if owned_runtime.get("fight") is not fight:
            issue(
                "runtime.fight_alias",
                "runtime.fight",
                "Runtime does not reference the prepared candidate",
            )
        checked.append("runtime.fight_alias")
    checked.append("boundary.stable")
    actors = state.get("actors")
    if type(actors) is not dict or len(actors) > 4096:
        issue("actor.population", "fight.actors", "Invalid or oversized roster")
        return BoundaryReport(
            boundary, tuple(findings), tuple(checked), 0, resource_identity
        )
    identities, state_uids, inspected_states = set(), set(), 0
    for key, actor in dict.items(actors):
        path = "fight.actors" if type(key) is not int else f"fight.actors[{key}]"
        if type(key) is not int or type(actor) is not Actor:
            issue(
                "actor.identity", path, "Roster needs integer keys and trusted actors"
            )
            continue
        row = vars(actor)
        identity = row.get("id")
        if type(identity) is not int or identity != key or identity in identities:
            issue(
                "actor.identity",
                path + ".id",
                "Roster key or unique actor identity disagrees",
            )
        if type(identity) is int:
            identities.add(identity)
        position = row.get("position")
        if (
            type(position) not in (tuple, list)
            or len(position) != 3
            or any(type(value) is not int for value in position)
        ):
            issue("actor.position", path + ".position", "Missing integer XYZ position")
        stats, minima, maxima = (
            row.get(name) for name in ("effect_stats", "effect_minima", "effect_maxima")
        )
        if not (
            type(stats) in (dict, stats_type)
            and type(minima) is dict
            and type(maxima) is dict
        ):
            unknown(
                "resource.authority",
                path,
                "Native characteristic projection unavailable",
            )
        else:
            for stat, scalar in ((1, "hp"), (2, "ap"), (3, "mp"), (4, None)):
                where = path + f".effect_stats[{stat}]"
                if any(
                    type(values.get(stat)) is not int
                    for values in (stats, minima, maxima)
                ):
                    unknown(
                        "resource.authority",
                        where,
                        "Incomplete native current/minimum/maximum",
                    )
                    continue
                if scalar is not None and (
                    row.get(scalar) != stats[stat]
                    or row.get("max_" + scalar) != maxima[stat]
                ):
                    issue(
                        "resource.scalar_projection",
                        where,
                        "Actor scalar or maximum disagrees with characteristic projection",
                    )
                raw = None
                if row.get("native_copy_pa_source") is not None:
                    source = row["native_copy_pa_source"]
                    if (
                        type(source) is dict
                        and source.get("producer") == "eHI.pRU.ffh.a"
                    ):
                        from .combat_copied_pa import _known_copied_profile

                        if (
                            source.get("actor_id") != identity
                            or not _known_copied_profile(source)
                            or type(source.get("effect_reference")) is not int
                            or type(source.get("source_actor_id")) is not int
                        ):
                            issue(
                                "resource.raw_source",
                                where,
                                "Copied raw operand disagrees with its owner or native profile",
                            )
                        else:
                            currents = row.get("effect_characteristic_raw_currents")
                            raw = currents.get(stat) if type(currents) is dict else None
                elif (
                    stat == 1
                    and row.get("native_hp_raw_current_source")
                    == "fresh_initial_tB_HP.on_resource_override"
                ):
                    raw = row.get("effect_hp_raw_current")
                elif (
                    stat in (2, 3)
                    and row.get("native_resource_raw_current_source")
                    == "fresh_ffh_AP_MP_mutable_on_within_bounds"
                ):
                    currents = row.get("effect_resource_raw_currents")
                    raw = currents.get(stat) if type(currents) is dict else None
                if raw is None:
                    unknown(
                        "resource.raw_authority",
                        where,
                        "No supported raw-current authority",
                    )
                elif type(raw) is not int or not -(1 << 31) <= raw < (1 << 31):
                    issue("resource.raw_width", where, "Raw current is not signed32")
                elif stats[stat] != max(minima[stat], min(maxima[stat], raw)):
                    issue(
                        "resource.raw_projection",
                        where,
                        "Effective current differs from native raw clamp",
                    )
            from .combat_invariant_resources import check_resource_definitions

            check_resource_definitions(
                row, path, resource_authority, issue, unknown, checked
            )
        ledger = row.get("state_ledger")
        if type(ledger) is not StateLedger:
            issue("state.owner", path + ".state_ledger", "Missing trusted state ledger")
            continue
        ledger_row = vars(ledger)
        if ledger_row.get("actor_id") != identity:
            issue(
                "state.owner",
                path + ".state_ledger.actor_id",
                "Ledger owner differs from actor",
            )
        entries = ledger_row.get("_entries")
        if type(entries) is not tuple or len(entries) > 4096:
            issue(
                "state.population",
                path + ".state_ledger",
                "Invalid or oversized ledger",
            )
            continue
        for index, entry in enumerate(entries):
            inspected_states += 1
            if inspected_states > 16384:
                issue(
                    "coverage.limit",
                    "fight.actors",
                    "Aggregate state inspection limit reached",
                    "unknown",
                )
                return BoundaryReport(
                    boundary,
                    tuple(findings),
                    tuple(checked),
                    len(actors),
                    resource_identity,
                )
            where = path + f".state_ledger.entries[{index}]"
            if type(entry) is not RunningState:
                issue("state.population", where, "Unknown running-state type")
                continue
            values = vars(entry)
            uid = values.get("uid")
            if type(uid) is not int or not 0 < uid < (1 << 63) or uid in state_uids:
                issue(
                    "state.identity",
                    where + ".uid",
                    "Invalid or duplicate running-state UID",
                )
            else:
                state_uids.add(uid)
            if values.get("target_id") != identity:
                issue(
                    "state.owner",
                    where + ".target_id",
                    "Running state targets another ledger owner",
                )
    checked.extend(
        (
            "actor.identity",
            "actor.position",
            "resource.scalar_projection",
            "resource.raw_projection",
            "state.identity",
            "state.owner",
        )
    )
    order = state.get("order")
    if type(order) is list and len(order) > 16384:
        unknown("coverage.limit", "fight.order", "Timeline inspection limit reached")
    elif type(order) is not list or any(
        type(uid) is not int or uid not in actors for uid in order
    ):
        issue(
            "timeline.references", "fight.order", "Timeline references an absent actor"
        )
    elif state.get("phase") == "active" and (
        not order
        or type(state.get("turn_index")) is not int
        or not 0 <= state["turn_index"] < len(order)
    ):
        issue(
            "timeline.current",
            "fight.turn_index",
            "Active timeline has no valid current slot",
        )
    checked.extend(("timeline.references", "timeline.current"))
    queue = state.get("native_delay_queue")
    from .combat_native_delay_queue import validate

    if type(queue) is not dict or type(queue.get("entries")) is not list:
        unknown(
            "timer.authority", "fight.native_delay_queue", "No supported native queue"
        )
    elif len(queue["entries"]) > 4096 or any(
        type(row) is not dict for row in queue["entries"]
    ):
        issue(
            "timer.population", "fight.native_delay_queue", "Invalid or oversized queue"
        )
    else:
        try:
            validate(queue)
        except (ValueError, TypeError, KeyError):
            issue(
                "timer.registration",
                "fight.native_delay_queue",
                "Malformed native queue registration",
            )
        else:
            uids = [row["uid"] for row in queue["entries"]]
            if len(uids) != len(set(uids)):
                issue(
                    "timer.identity",
                    "fight.native_delay_queue.entries",
                    "Duplicate delayed runner UID",
                )
        checked.extend(("timer.registration", "timer.identity"))
    _check_spatial(fight, state, actors, issue, unknown, checked)
    from .combat_invariant_ownership import check_ownership

    check_ownership(fight, state, actors, issue, unknown, checked)
    from .combat_invariant_sequences import check_runtime_sequences

    check_runtime_sequences(runtime, ack, issue, unknown, checked)
    return BoundaryReport(
        boundary, tuple(findings), tuple(checked), len(actors), resource_identity
    )


def _check_spatial(fight, state, actors, issue, unknown, checked):
    """Check existing registration relationships, without rebinding QI.

    Historical pointer aliases are allowed. This checks canonical ownership and
    slot references, not a guessed collision rule or regenerated cell topology.
    """
    from .combat_state import Actor

    checkpoint = state.get("native_pointer_checkpoint")
    if checkpoint is not None:
        # Canonical objects necessarily have their defining modules loaded;
        # a diagnostic must not initialize their constructors or catalogs.
        checkpoint_module = sys.modules.get(
            __package__ + ".combat_pointer_qi_checkpoint"
        )
        pointer_module = sys.modules.get(__package__ + ".combat_pointer_qi_actor")
        checkpoint_types = (
            vars(checkpoint_module) if checkpoint_module is not None else {}
        )
        pointer_types = vars(pointer_module) if pointer_module is not None else {}
        NativePointerCheckpoint = checkpoint_types.get("NativePointerCheckpoint")
        ActualActorQI = pointer_types.get("ActualActorQI")
        ActorQK, AreaQK = pointer_types.get("ActorQK"), pointer_types.get("AreaQK")
        if type(checkpoint) is not NativePointerCheckpoint:
            issue(
                "spatial.checkpoint",
                "fight.native_pointer_checkpoint",
                "Unknown canonical checkpoint type",
            )
            return
        if dict.get(
            checkpoint, "schema"
        ) != "native.QI.pointer_QL_history937.bound_plain.v1" or set(
            dict.keys(checkpoint)
        ) != {
            "schema",
            "canonical",
            "slots",
            "cells",
            "anchors",
        }:
            issue(
                "spatial.checkpoint",
                "fight.native_pointer_checkpoint",
                "Incomplete or unknown bound pointer schema",
            )
        qi = vars(checkpoint).get("_qi")
        if type(qi) is not ActualActorQI or vars(qi).get("fight") is not fight:
            issue(
                "spatial.owner",
                "fight.native_pointer_checkpoint._qi",
                "Canonical QI does not belong to candidate",
            )
            return
        facts = vars(qi)
        objects, areas = facts.get("objects"), facts.get("area_objects")
        pending = facts.get("pending_constructor_actors")
        slots = facts.get("slots")
        if (
            type(objects) is not dict
            or type(areas) is not dict
            or type(pending) is not dict
            or type(slots) is not list
            or len(slots) != 127
            or len(objects) + len(areas) > 8192
        ):
            issue(
                "spatial.population",
                "fight.native_pointer_checkpoint._qi",
                "Incomplete canonical pointer population",
            )
            return
        tokens, canonical, pointer_keys = set(), [], {}
        blocking = facts.get("movement_blocking")
        if type(blocking) is not dict:
            issue(
                "spatial.population",
                "fight.native_pointer_checkpoint._qi.movement_blocking",
                "Missing canonical blocking population",
            )
            return
        for population, kind, wrapper in (
            (objects, "actor", ActorQK),
            (areas, "effect_area", AreaQK),
        ):
            for identity, obj in dict.items(population):
                if type(identity) is not int or type(obj) is not wrapper:
                    issue(
                        "spatial.identity",
                        "fight.native_pointer_checkpoint._qi",
                        "Malformed canonical object namespace",
                    )
                    continue
                tokens.add(id(obj))
                pointer_keys[id(obj)] = [kind, identity]
                if kind == "actor":
                    actor = vars(obj).get("actor")
                    if type(actor) is not Actor:
                        issue(
                            "spatial.owner",
                            "fight.native_pointer_checkpoint._qi.objects",
                            "Canonical actor wrapper has no trusted actor",
                        )
                        continue
                    row = vars(actor)
                    if actors.get(identity) is not actor and not (
                        identity not in actors and pending.get(identity) is actor
                    ):
                        issue(
                            "spatial.owner",
                            "fight.native_pointer_checkpoint._qi.objects",
                            "Canonical actor object was replaced",
                        )
                    uid, position, radius, byte = (
                        row.get(name)
                        for name in (
                            "id",
                            "position",
                            "physical_radius",
                            "native_obstacle_id",
                        )
                    )
                else:
                    row = vars(obj).get("row")
                    if type(row) is not dict:
                        issue(
                            "spatial.owner",
                            "fight.native_pointer_checkpoint._qi.area_objects",
                            "Canonical area wrapper has no plain owner",
                        )
                        continue
                    uid, position, radius, byte = (
                        row.get("uid"),
                        row.get("cell"),
                        0,
                        row.get("native_obstacle_id"),
                    )
                    for name in ("native_effect_areas", "native_retired_area_managers"):
                        population_row = state.get(name)
                        if (
                            type(population_row) is dict
                            and identity in population_row
                            and population_row[identity] is not row
                        ):
                            issue(
                                "spatial.owner",
                                "fight." + name,
                                "Registered canonical area object was replaced",
                            )
                if (
                    uid != identity
                    or type(position) not in (tuple, list)
                    or len(position) < 2
                    or any(type(n) is not int for n in position[:2])
                    or type(radius) is not int
                    or type(byte) is not int
                    or type(blocking.get(id(obj))) is not bool
                ):
                    issue(
                        "spatial.registration",
                        "fight.native_pointer_checkpoint._qi",
                        "Canonical coordinates, identity, radius or byte unavailable",
                    )
                    continue
                canonical.append(
                    dict(
                        kind=kind,
                        identity=identity,
                        byte=byte,
                        position=list(position[:2]),
                        radius=radius,
                        movement_blocking=blocking[id(obj)],
                    )
                )
        if (
            type(dict.get(checkpoint, "canonical")) is not list
            or len(dict.get(checkpoint, "canonical")) > 8192
            or dict.get(checkpoint, "canonical") != canonical
        ):
            issue(
                "spatial.checkpoint",
                "fight.native_pointer_checkpoint.canonical",
                "Checkpoint facts disagree with existing canonical objects",
            )
        if any(obj is not None and id(obj) not in tokens for obj in slots):
            issue(
                "spatial.registration",
                "fight.native_pointer_checkpoint._qi.slots",
                "Slot refers to an unowned canonical pointer",
            )
        else:
            expected_slots = [
                None if obj is None else pointer_keys[id(obj)] for obj in slots
            ]
            if dict.get(checkpoint, "slots") != expected_slots:
                issue(
                    "spatial.checkpoint",
                    "fight.native_pointer_checkpoint.slots",
                    "Checkpoint slot aliases disagree with canonical pointer slots",
                )
        _check_pointer_cells(checkpoint, facts, issue, unknown, checked)
        checked.extend(("spatial.owner", "spatial.checkpoint", "spatial.registration"))
        return
    slots = state.get("native_qi_slots")
    if type(slots) is not list or len(slots) != 127:
        unknown(
            "spatial.authority", "fight.native_qi_slots", "No complete owned QI slots"
        )
        return
    for slot, row in enumerate(slots):
        if row is None:
            continue
        where = f"fight.native_qi_slots[{slot}]"
        identity = row.get("identity") if type(row) is dict else None
        if (
            type(identity) is not list
            or len(identity) != 2
            or type(identity[0]) is not str
            or type(identity[1]) is not int
        ):
            issue("spatial.registration", where, "Malformed native slot identity")
            continue
        if identity[0] == "effect_area":
            population = state.get("native_effect_areas")
            area = population.get(identity[1]) if type(population) is dict else None
            if type(area) is not dict or area.get("uid") != identity[1]:
                issue(
                    "spatial.owner",
                    where,
                    "Registered area obstacle has no active owner",
                )
                continue
            contract = area.get("native_area_contract")
            if type(contract) is not str:
                issue(
                    "spatial.area_obstacle",
                    where,
                    "Missing native area constructor kind",
                )
                continue
            constructor = area.get(
                {"faW": "native_faw_constructor", "fbd": "native_wall_constructor"}.get(
                    contract, ""
                )
            )
            if type(constructor) is not dict:
                unknown(
                    "spatial.area_obstacle",
                    where,
                    "Area obstacle needs its native constructor contract",
                )
            elif (
                constructor.get("obstacle") is not True
                or area.get("native_obstacle_id") != slot
                or type(area.get("cell")) not in (list, tuple)
                or row.get("position") != list(area["cell"][:2])
                or row.get("radius") != 0
            ):
                issue(
                    "spatial.registration",
                    where,
                    "Area obstacle disagrees with its native constructor or coordinates",
                )
            continue
        if identity[0] != "actor":
            issue("spatial.registration", where, "Unknown obstacle identity namespace")
            continue
        actor = actors.get(identity[1])
        if type(actor) is not Actor:
            issue("spatial.owner", where, "Registered slot has no roster actor")
            continue
        data = vars(actor)
        position = data.get("position")
        if (
            type(position) not in (tuple, list)
            or row.get("position") != list(position[:2])
            or data.get("native_obstacle_id") != slot
            or data.get("physical_radius") != row.get("radius")
        ):
            issue(
                "spatial.registration",
                where,
                "Slot and canonical actor coordinate/radius/byte disagree",
            )
    checked.extend(("spatial.owner", "spatial.registration"))
    from .combat_invariant_spatial import check_legacy_topology

    check_legacy_topology(state, slots, issue, unknown, checked)


def _check_pointer_cells(checkpoint, facts, issue, unknown, checked):
    """Compare sealed QL topology without repairing aliases or invoking order()."""
    from .combat_trove_byte_set import NativeTroveByteSet

    cells, anchors = facts.get("cells"), facts.get("anchors")
    origin, width, height = facts.get("origin"), facts.get("width"), facts.get("height")
    path = "fight.native_pointer_checkpoint"
    if (
        type(cells) is not dict
        or type(anchors) is not dict
        or type(origin) is not tuple
        or len(origin) != 2
        or any(type(n) is not int for n in origin)
        or type(width) is not int
        or type(height) is not int
        or width <= 0
        or height <= 0
    ):
        issue(
            "spatial.cell_topology", path, "Missing canonical terrain/topology fields"
        )
        return
    if len(cells) > 16384 or len(anchors) > 127:
        unknown("coverage.limit", path, "Spatial topology inspection limit reached")
        return

    def inside(cell):
        return (
            type(cell) is tuple
            and len(cell) == 2
            and all(type(n) is int for n in cell)
            and origin[0] <= cell[0] < origin[0] + width
            and origin[1] <= cell[1] < origin[1] + height
        )

    captured_cells, work = [], 0
    for cell, value in dict.items(cells):
        if not inside(cell) or type(value) is not NativeTroveByteSet:
            issue(
                "spatial.cell_topology",
                path + ".cells",
                "Invalid QL coordinate or set owner",
            )
            return
        row = vars(value).get("state")
        if type(row) is not dict or set(row) != {
            "keys",
            "states",
            "size",
            "free",
            "compact_removes",
        }:
            issue(
                "spatial.cell_topology",
                path + ".cells",
                "Incomplete native QL set topology",
            )
            return
        keys, statuses = row["keys"], row["states"]
        if (
            type(keys) is not list
            or type(statuses) is not list
            or len(keys) != len(statuses)
        ):
            issue("spatial.cell_topology", path + ".cells", "QL slot arrays disagree")
            return
        work += len(keys)
        if work > 131072:
            unknown(
                "coverage.limit",
                path + ".cells",
                "Aggregate QL slot inspection limit reached",
            )
            return
        if (
            any(type(n) is not int or not -128 <= n <= 127 for n in keys)
            or any(type(n) is not int or n not in (0, 1, 2) for n in statuses)
            or any(
                type(row[name]) is not int
                for name in ("size", "free", "compact_removes")
            )
        ):
            issue(
                "spatial.cell_topology",
                path + ".cells",
                "Malformed native QL slot fields",
            )
            return
        live = [key for key, status in zip(keys, statuses) if status == 1]
        if (
            row["size"] != len(live)
            or len(set(live)) != len(live)
            or any(not 0 <= key < 127 for key in live)
            or not 0 <= row["free"] <= len(keys)
        ):
            issue(
                "spatial.cell_topology",
                path + ".cells",
                "Invalid QL membership or accounting",
            )
            return
        captured_cells.append(
            dict(
                cell=list(cell),
                trove=dict(
                    keys=list(keys),
                    states=list(statuses),
                    size=row["size"],
                    free=row["free"],
                    compact_removes=row["compact_removes"],
                ),
            )
        )
    captured_cells.sort(key=lambda row: row["cell"])
    expected_cells = dict.get(checkpoint, "cells")
    if (
        type(expected_cells) is not list
        or len(expected_cells) > 16384
        or expected_cells != captured_cells
    ):
        issue(
            "spatial.checkpoint",
            path + ".cells",
            "Checkpoint QL cells differ from actual owned topology",
        )
    captured_anchors = []
    for byte, cell in dict.items(anchors):
        if type(byte) is not int or not 0 <= byte < 127 or not inside(cell):
            issue(
                "spatial.cell_topology",
                path + ".anchors",
                "Invalid native latest anchor",
            )
            return
        captured_anchors.append(dict(byte=byte, cell=list(cell)))
    captured_anchors.sort(key=lambda row: row["byte"])
    if dict.get(checkpoint, "anchors") != captured_anchors:
        issue(
            "spatial.checkpoint",
            path + ".anchors",
            "Checkpoint latest anchors differ from native owner",
        )
    checked.append("spatial.cell_topology")
