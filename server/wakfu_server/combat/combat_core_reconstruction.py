"""Independent bounded recipient model for native core snapshot lifecycles.

Only standard library and the existing independent protobuf decoder are used.
Server serializers, authority projections and combat execution are not oracles.
A fence is not a completion witness; opaque actor stats/spellbooks, rendering
and unmodeled typed phase events never acquire support through this model.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import re

from .combat_protocol_reconstruction import (
    BlockCompletion,
    MalformedPacket,
    Recipient,
    _Reader,
    _field,
    _protobuf,
    _signed,
    decode_packet as decode_slice,
)


class UnknownCoreLayout(ValueError):
    """Valid-looking native variant outside this independently modeled slice."""


def _boolean(reader):
    value = reader.read("B")
    if value not in (0, 1):
        raise MalformedPacket("Invalid native boolean")
    return bool(value)


def _unique(values, label):
    if len(values) != len(set(values)):
        raise MalformedPacket("Duplicate native " + label)
    return values


def decode_timeline(body):
    """SU prefix, Tc/SX/SY membership and removed statuses, then feN bonuses."""
    reader = _Reader(body)
    value = dict(zip(("round", "turn", "phase", "deadline"), reader.read("hibq")))
    if value["phase"] not in (0, 1):
        raise UnknownCoreLayout("Unmodeled native SU phase")
    for name in ("available", "next_order"):
        value[name] = [reader.read("q") for _ in range(reader.count("b"))]
    progress = {}
    for _ in range(reader.count("b")):
        identity, counter = reader.read("qh")
        if identity in progress:
            raise MalformedPacket("Duplicate native progress member")
        progress[identity] = counter
    value["progress"] = progress
    value["index"] = reader.read("b")
    removed = {}
    for _ in range(reader.count("b")):
        identity, counter, position, modifications = reader.read("qhih")
        if identity in removed:
            raise MalformedPacket("Duplicate native removed member")
        if modifications != 0:
            raise UnknownCoreLayout("Native pending removed-turn modifications")
        removed[identity] = dict(progress=counter, position=position)
    value["removed"] = removed
    bonuses = {}
    for _ in range(reader.count("b")):
        identity, bonus = reader.read("qi")
        if identity in bonuses:
            raise MalformedPacket("Duplicate native bonus member")
        bonuses[identity] = bonus
    value["bonuses"] = bonuses
    reader.done()
    members = set(value["available"])
    if not members or members != set(value["next_order"]) or members != set(progress):
        raise MalformedPacket("Inconsistent native timeline membership")
    if members & set(removed):
        raise MalformedPacket("Removed member remains in native timeline")
    index = value["index"]
    if value["phase"] == 0:
        if index != -1:
            raise MalformedPacket("INITIAL native timeline has a current member")
        value["current"] = None
    else:
        if not 0 <= index < len(value["available"]):
            raise MalformedPacket("Invalid native current member index")
        value["current"] = value["available"][index]
    return value


def decode_bonus_snapshot(body):
    reader = _Reader(body)
    period = reader.read("i")
    if period <= 0:
        raise MalformedPacket("Invalid native bonus period")
    actors = {}
    for _ in range(reader.count("b")):
        identity, counter = reader.read("qi")
        flag = _boolean(reader)
        if identity in actors:
            raise MalformedPacket("Duplicate native feN actor")
        actors[identity] = dict(counter=counter, flag=flag)
    maps = []
    for _ in range(2):
        entries = {}
        for _ in range(reader.count("b")):
            key = reader.read("i")
            if key in entries:
                raise MalformedPacket("Duplicate native feN event key")
            entries[key] = [reader.read("i") for _ in range(reader.count("b"))]
        maps.append(entries)
    reader.done()
    return dict(period=period, actors=actors, events=maps[0], deferred=maps[1])


def _bootstrap(reader):
    fight, kind = reader.read("ib")
    metadata = reader.read("qqq")
    topology = reader.blob("i")
    timeline = decode_timeline(reader.blob("h"))
    leaders = reader.read("qq")
    compact = _boolean(reader)
    entities = {}
    for _ in range(reader.count("b")):
        identity, actor_kind, team, extra = reader.read("qbbb")
        if identity == 0 or identity in entities:
            raise MalformedPacket("Invalid or duplicate native roster identity")
        actor = dict(kind=actor_kind, team=team, extra=extra)
        if not compact:
            actor.update(descriptor=reader.blob("h"), effects=reader.blob("h"))
        entities[identity] = actor
    teams = [reader.read("bq") for _ in range(reader.count("b"))]
    rows = [[reader.read("b") for _ in range(reader.count("b"))] for _ in range(2)]
    sections = [reader.blob("i") for _ in range(reader.count("i"))]
    return dict(
        kind="bootstrap",
        fight=fight,
        model=kind,
        metadata=metadata,
        topology=topology,
        timeline=timeline,
        leaders=leaders,
        compact=compact,
        entities=entities,
        teams=teams,
        lists=rows,
        sections=sections,
    )


def decode_summon(body):
    """eZl null-vK/vM descriptor, eHN property counts and SQ insertion data."""
    fields = _protobuf(body)
    additional = _protobuf(_field(fields, 8, 2, required=True))
    reader = _Reader(_field(additional, 1, 2, required=True))
    self_controlled = _boolean(reader)
    reference = reader.read("h")
    name_bytes = reader.blob("H")
    try:
        name = name_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise MalformedPacket("Malformed native descriptor name") from error
    health_override, actor_id, level, obstacle = reader.read("iqhb")
    if _boolean(reader) or _boolean(reader):
        raise UnknownCoreLayout("Non-null native vK/vM summon descriptor")
    direction, original_controller = reader.read("iq")
    flag = _boolean(reader)
    properties = {}
    for _ in range(reader.count("H")):
        identity, count = reader.read("BB")
        if identity in properties or count == 0:
            raise MalformedPacket("Invalid native summon property counts")
        properties[identity] = count
    anchor, caster, offset, team = reader.read("bqib")
    reader.done()
    generated = _protobuf(_field(fields, 12, 2, required=True))
    owned_id = _signed(_field(generated, 4, 0, required=True), 64)
    if actor_id != owned_id or actor_id <= 0 or caster == 0:
        raise MalformedPacket("Summon descriptor and additional UID disagree")
    if anchor not in (0, 1, 2) or direction not in range(4):
        raise UnknownCoreLayout("Unmodeled native summon anchor or facing")
    outer_caster = _signed(_field(fields, 6, 0, required=True), 64)
    if caster != outer_caster:
        raise MalformedPacket("Summon SQ caster differs from running source")
    return dict(
        actor=actor_id,
        reference=reference,
        level=level,
        name=name,
        self_controlled=self_controlled,
        controller=actor_id if self_controlled else caster,
        caster=caster,
        anchor=anchor,
        offset=offset,
        team=team,
        obstacle=obstacle,
        direction=direction,
        original_controller=original_controller,
        flag=flag,
        health_override=health_override,
        properties=properties,
        timeline_member=114 not in properties,
        effect_uid=_signed(_field(fields, 1, 0, required=True), 64),
    )


def decode_core_packet(opcode, body):
    reader = _Reader(body)
    if opcode in (12847, 12044):
        result = _bootstrap(reader)
        result["opcode"] = opcode
        if opcode == 12044:
            result["role"] = "spectator"
            result["phase"] = reader.read("b")
            if result["phase"] not in range(6):
                raise UnknownCoreLayout("Unmodeled native spectator phase")
            result["bonus_snapshot"] = decode_bonus_snapshot(reader.blob("i"))
        else:
            result["role"] = "participant"
    elif opcode == 12053:
        fight = reader.read("i")
        envelope = _Reader(reader.blob("h"))
        if envelope.read("BBiB") != (1, 0, 6, 0):
            raise UnknownCoreLayout("Unmodeled native fg recovery field envelope")
        timeline = decode_timeline(envelope.blob("h"))
        envelope.done()
        result = dict(kind="recovery", fight=fight, timeline=timeline, opcode=opcode)
    elif opcode in (13912, 12873):
        result = dict(
            kind="opaque_actor_snapshot",
            fight=reader.read("i"),
            actor=reader.read("q"),
            payload=reader.blob("i" if opcode == 13912 else "h"),
            opcode=opcode,
        )
    elif opcode == 12233:
        result = dict(kind="placement_end", fight=reader.read("i"), opcode=opcode)
    elif opcode == 12514:
        fight, phase, duration, timestamp = reader.read("ibiq")
        bonus_snapshot = decode_bonus_snapshot(reader.blob("i"))
        if reader.count("b"):
            raise UnknownCoreLayout(
                "Native feb phase effects require separate decoding"
            )
        timed, zones = reader.blob("i"), reader.blob("i")
        if timed != b"\x00" * 10 or zones != b"\x00\x00":
            raise UnknownCoreLayout("Nonempty native timed events or permanent zones")
        if phase not in range(6) or duration < 0:
            raise MalformedPacket("Invalid native action phase")
        result = dict(
            kind="phase",
            fight=fight,
            phase=phase,
            duration=duration,
            timestamp=timestamp,
            bonus_snapshot=bonus_snapshot,
            opcode=opcode,
        )
    else:
        result = decode_slice(opcode, body)
        if opcode in (12613, 13497) and result.get("effect", {}).get("family") == 307:
            # Parse the exact raw iN again; the shared decoder intentionally does
            # not yet interpret307 additional descriptor or generated UID.
            reader.read("iii")
            if opcode == 12613:
                _boolean(reader)
            if reader.read("i") != 307:
                raise MalformedPacket("Inconsistent summon family")
            result.update(kind="summon_birth", summon=decode_summon(reader.blob("h")))
        else:
            return result
    reader.done()
    return result


@dataclass(frozen=True)
class NativeRetirementContext:
    """Separately established attached OFF_PLAY/QI context, not HP inference."""

    fight_id: int
    actor_id: int
    off_play: bool
    physical_registered: bool
    prior_timeline_removed: bool
    saved_removed_record: bool
    evidence_sha256: str

    def __post_init__(self):
        if (
            type(self.fight_id) is not int
            or self.fight_id <= 0
            or type(self.actor_id) is not int
            or self.actor_id == 0
            or self.off_play is not True
            or self.physical_registered is not True
            or self.prior_timeline_removed is not True
            or self.saved_removed_record is not True
            or not re.fullmatch(r"[0-9a-f]{64}", self.evidence_sha256)
        ):
            raise ValueError(
                "Explicit native OFF_PLAY/QI and prior removed-clock evidence required"
            )


@dataclass
class CoreView:
    roster: dict = field(default_factory=dict)
    summons: dict = field(default_factory=dict)
    known_world_instances: set = field(default_factory=set)
    timeline: dict | None = None
    phase: int | None = None
    fighter_status_messages: dict = field(default_factory=dict)
    retirements: dict = field(default_factory=dict)


@dataclass
class CoreReconstruction:
    recipient: Recipient
    received: CoreView = field(default_factory=CoreView)
    executed: CoreView = field(default_factory=CoreView)
    findings: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    fight: int | None = None
    unknown_components: set = field(default_factory=set)


def reconstruct_core(packets, *, recipient, completions=(), retirement_contexts=()):
    """Model explicit role/generation, queued births and recovered live timeline.

    Completions must come from an independently verified native receipt. This
    pure function validates identity/order only; callers validate receipt hashes.
    """
    if not isinstance(recipient, Recipient):
        raise ValueError("Explicit recipient identity required")
    retirement_contexts = tuple(retirement_contexts)
    if any(not isinstance(x, NativeRetirementContext) for x in retirement_contexts):
        raise ValueError("Typed native retirement contexts required")
    retirement_by_actor = {x.actor_id: x for x in retirement_contexts}
    if len(retirement_by_actor) != len(retirement_contexts):
        raise ValueError("Duplicate native retirement context")
    result = CoreReconstruction(recipient)
    completions = tuple(completions)
    if any(not isinstance(x, BlockCompletion) for x in completions):
        raise ValueError("Typed explicit block completions required")
    witnesses = {entry.block_index: entry for entry in completions}
    if len(witnesses) != len(completions) or any(
        len(x.action_ids) != len(set(x.action_ids)) for x in completions
    ):
        raise ValueError("Unique block and native action identities required")
    open_births, block = [], 0
    consumed_witnesses = set()
    contradicted_retirement_actors = set()

    def finding(code, packet):
        result.findings.append(dict(code=code, packet=packet))

    def install_birth(view, value, index):
        summon = value["summon"]
        actor = summon["actor"]
        if actor in view.known_world_instances:
            finding("summon_reuses_known_world_identity", index)
            return
        if actor in view.summons:
            finding("duplicate_summon_birth", index)
            return
        if actor == summon["caster"]:
            finding("summon_reuses_source_identity", index)
            return
        if summon["caster"] not in view.roster:
            finding("unregistered_summon_source", index)
            return
        # A cvb/cva roster reference does not construct the summon. Native
        # buK resolves roster IDs through bio.jv; later eZl creates the actual
        # instance. Keep roster authority and constructed instances distinct.
        if actor in view.roster and view.roster[actor]["team"] != summon["team"]:
            finding("summon_roster_team_mismatch", index)
            return
        view.roster.setdefault(actor, dict(kind="summon", team=summon["team"]))
        view.summons[actor] = deepcopy(summon)
        if view.timeline is not None and actor in view.timeline["available"]:
            finding("timeline_enrolled_before_birth", index)

    def close_actions(index):
        nonlocal open_births, block
        if not open_births:
            return
        actions = tuple(action["action"] for _, action in open_births)
        witness = witnesses.get(block)
        if witness is not None and witness.action_ids == actions:
            consumed_witnesses.add(block)
            for action_index, action in open_births:
                if action["kind"] == "summon_birth":
                    install_birth(result.executed, action, action_index)
                elif action["kind"] == "fighter_status":
                    actor = action["actor"]
                    context = retirement_by_actor.get(actor)
                    result.executed.fighter_status_messages[actor] = action["status"]
                    if (
                        action["status"] == 2
                        and context is not None
                        and context.fight_id == result.fight
                        and actor not in contradicted_retirement_actors
                    ):
                        result.executed.retirements[actor] = dict(
                            state="OUT_OF_PLAY",
                            physical_registered=False,
                            roster_retained=True,
                            timeline_member=False,
                            saved_removed_record=False,
                        )
                        # Native proof excludes timeline removal timing. Do not
                        # pretend the pre-retirement timeline remained current.
                        result.unknown_components.add("timeline")
                    else:
                        finding("fighter_retirement_semantics_not_proven", action_index)
        else:
            result.pending.append(dict(block=block, action_ids=actions))
            finding("action_completion_not_proven", index)
        open_births = []
        block += 1

    for index, packet in enumerate(packets):
        if index >= 4096:
            raise MalformedPacket("Too many core packets")
        opcode, body = packet
        try:
            value = decode_core_packet(opcode, body)
        except UnknownCoreLayout:
            finding("unknown_native_layout", index)
            continue
        kind = value["kind"]
        if kind == "bootstrap":
            if result.fight is not None:
                finding("duplicate_bootstrap_in_generation", index)
                continue
            if recipient.role != value["role"]:
                finding("recipient_role_mismatch", index)
                continue
            result.fight = value["fight"]
            result.received.roster = deepcopy(value["entities"])
            result.received.known_world_instances = {
                identity
                for identity in value["leaders"]
                if identity in value["entities"]
            }
            result.received.timeline = deepcopy(value["timeline"])
            result.received.phase = value.get("phase")
            result.executed = deepcopy(result.received)
            if set(value["timeline"]["available"]) - set(value["entities"]):
                finding("timeline_references_unregistered_actor", index)
            continue
        if result.fight is None:
            finding("missing_bootstrap", index)
            continue
        if value.get("fight", result.fight) != result.fight:
            finding("foreign_fight_packet", index)
            continue
        if kind == "summon_birth":
            if not value.get("immediate"):
                finding("unmodeled_observation_only_summon", index)
                continue
            if value["action"] in {birth["action"] for _, birth in open_births}:
                finding("duplicate_native_action_in_block", index)
                continue
            install_birth(result.received, value, index)
            open_births.append((index, value))
        elif kind == "fighter_status":
            actor = value["actor"]
            if actor not in result.executed.roster:
                finding("fighter_status_references_unregistered_actor", index)
                continue
            result.received.fighter_status_messages[actor] = value["status"]
            context = retirement_by_actor.get(actor)
            if context is not None and context.fight_id == result.fight:
                known_timeline = result.executed.timeline
                if (
                    known_timeline is not None
                    and known_timeline["phase"] == 1
                    and actor in known_timeline["available"]
                ):
                    finding("native_retirement_context_contradicts_timeline", index)
                    contradicted_retirement_actors.add(actor)
                else:
                    result.executed.retirements.setdefault(
                        actor,
                        dict(
                            state="OFF_PLAY",
                            physical_registered=True,
                            roster_retained=True,
                            timeline_member=False,
                            saved_removed_record=True,
                        ),
                    )
                    result.unknown_components.add("timeline")
            if value["action"] in {action["action"] for _, action in open_births}:
                finding("duplicate_native_action_in_block", index)
                continue
            open_births.append((index, value))
            # Original cvK dispatch closes the accumulating native block itself.
            close_actions(index)
        elif kind == "fence":
            close_actions(index)
        elif kind == "recovery":
            timeline = value["timeline"]
            if open_births or result.pending:
                finding("recovery_before_birth_completion", index)
            for view in (result.received, result.executed):
                if set(timeline["available"]) - set(view.roster):
                    finding("recovery_references_unregistered_actor", index)
                if any(
                    s["timeline_member"] is False and actor in timeline["available"]
                    for actor, s in view.summons.items()
                ):
                    finding("property114_actor_enrolled_in_timeline", index)
                view.timeline = deepcopy(timeline)
        elif kind == "opaque_actor_snapshot":
            if value["actor"] not in result.executed.roster:
                finding("snapshot_references_unregistered_actor", index)
            # Only envelope ownership is modeled. Stats/effects bytes are opaque
            # and cannot be requested as a supported projection component.
        elif kind == "placement_end":
            pass
        elif kind == "phase":
            result.received.phase = value["phase"]
            result.executed.phase = value["phase"]
        elif kind == "despawn":
            finding("world_despawn_not_combat_retirement", index)
        else:
            finding("unknown_core_coverage", index)
    if open_births:
        finding("unclosed_birth_group", len(result.findings))
    if result.fight is None:
        finding("missing_bootstrap", 0)
    for unused in set(witnesses) - consumed_witnesses:
        finding("completion_without_matching_closed_block", unused)
    return result


def compare_core_view(result, *, recipient, expected):
    """Compare only supplied modeled components; unknown/pending blocks acceptance."""
    if recipient != result.recipient or not expected:
        raise ValueError(
            "Comparison requires exact recipient generation and components"
        )
    allowed = {
        "roster",
        "summons",
        "timeline",
        "phase",
        "fighter_status_messages",
        "retirements",
    }
    if set(expected) - allowed:
        raise ValueError("Unmodeled core projection component")
    different = [
        name
        for name, value in expected.items()
        if getattr(result.executed, name) != value
    ]
    unknown = sorted(set(expected) & result.unknown_components)
    return dict(
        matches=not different
        and not unknown
        and not result.findings
        and not result.pending,
        unknown_components=unknown,
        differences=different,
        findings=deepcopy(result.findings),
        pending=deepcopy(result.pending),
    )
