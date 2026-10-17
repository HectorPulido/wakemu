"""Partial independent native byte decoder and recipient-state reconstruction.

No server serializers, catalogs, projection helpers or gameplay modules are
dependencies. Layouts follow original cvb/cvq/cvP/cvX/cvY/cvZ/ctA and iN/ij.
An execution fence is not completion. Only explicit independently observed
completion witnesses advance closed FIFO blocks. Native effect-definition
facts must be supplied separately; absence is unknown, never guessed.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import re
import struct
from itertools import islice


MAX_PACKETS = 4096
MAX_BODY = 1024 * 1024
MAX_ENTRIES = 4096
_HASH = re.compile(r"[0-9a-f]{64}\Z")
COMPONENTS = frozenset(("entities", "positions", "states", "areas", "queue"))


class MalformedPacket(ValueError):
    """Invalid bytes, distinct from unsupported native semantics."""


class _Reader:
    def __init__(self, body):
        if type(body) is not bytes or len(body) > MAX_BODY:
            raise MalformedPacket("Require bounded immutable packet bytes")
        self.body, self.offset = body, 0

    def take(self, size):
        if type(size) is not int or size < 0 or self.offset + size > len(self.body):
            raise MalformedPacket("Truncated or negative-sized native field")
        result = self.body[self.offset : self.offset + size]
        self.offset += size
        return result

    def read(self, fmt):
        values = struct.unpack(">" + fmt, self.take(struct.calcsize(">" + fmt)))
        return values[0] if len(values) == 1 else values

    def count(self, fmt):
        count = self.read(fmt)
        if not 0 <= count <= MAX_ENTRIES:
            raise MalformedPacket("Native collection count outside slice bounds")
        return count

    def blob(self, fmt):
        return self.take(self.read(fmt))

    def done(self):
        if self.offset != len(self.body):
            raise MalformedPacket("Trailing bytes outside supported native layout")


def _signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def _protobuf(body):
    """Bounded protobuf wire reader; preserve occurrences and unknown fields."""
    reader = _Reader(body)

    def varint():
        value = 0
        for shift in range(0, 70, 7):
            byte = reader.read("B")
            if shift == 63 and byte > 1:
                raise MalformedPacket("Overflowed protobuf varint")
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise MalformedPacket("Unterminated protobuf varint")

    fields = {}
    count = 0
    while reader.offset < len(body):
        count += 1
        if count > MAX_ENTRIES:
            raise MalformedPacket("Too many protobuf fields")
        tag = varint()
        number, wire = tag >> 3, tag & 7
        if not 1 <= number < (1 << 29):
            raise MalformedPacket("Invalid protobuf field number")
        if wire == 0:
            value = varint()
        elif wire == 2:
            value = reader.take(varint())
        elif wire in (1, 5):
            value = reader.take(8 if wire == 1 else 4)
        else:
            raise MalformedPacket("Unsupported protobuf wire group/type")
        fields.setdefault(number, []).append((wire, value))
    return fields


def _field(fields, number, wire, *, required=False, default=None):
    entries = fields.get(number)
    if not entries:
        if required:
            raise MalformedPacket("Missing required native field " + str(number))
        return default
    if any(kind != wire for kind, _ in entries):
        raise MalformedPacket("Wrong native field wire type " + str(number))
    # Original protobuf singular scalars use last occurrence wins.
    return entries[-1][1]


def _effect(body, family):
    fields = _protobuf(body)
    integer = lambda n, **kw: _field(fields, n, 0, **kw)
    value = _signed(integer(4, default=0), 32)
    result = dict(
        family=family,
        uid=_signed(integer(1, required=True), 64),
        base_uid=_signed(integer(2, default=0), 64),
        definition=_signed(integer(3, default=0), 32),
        value=value,
        caster=_signed(integer(6), 64) if 6 in fields else None,
        target=_signed(integer(7), 64) if 7 in fields else None,
        container_type=integer(9),
        container_id=_signed(integer(10), 64) if 10 in fields else None,
        additional=_protobuf(_field(fields, 8, 2, default=b"")),
        timing=_protobuf(_field(fields, 11, 2, default=b"")),
    )
    position = _field(fields, 5, 2)
    if position is not None:
        coordinates = _protobuf(position)
        result["cell"] = (
            _signed(_field(coordinates, 1, 0, default=0), 32),
            _signed(_field(coordinates, 2, 0, default=0), 32),
            _signed(_field(coordinates, 3, 0, default=0), 16),
        )
    if family == 310:
        # eZk.f(iN) reads ij.LV/getValue after the common Qe envelope,
        # overriding its UID/value. These are not interchangeable namespaces.
        result.update(wire_uid=result["uid"], wire_value=value)
        if 8 in fields:
            result["uid"] = _signed(_field(result["additional"], 13, 0, default=0), 64)
            value = _signed(_field(result["additional"], 10, 0, default=0), 32)
            result["value"] = value
        result.update(state_id=_signed(value >> 16, 16), level=_signed(value, 16))
    elif family in (308, 315):
        additional = result["additional"]
        result.update(
            prototype=value,
            area_uid=_signed(_field(additional, 21, 0, required=True), 64),
            level=_signed(_field(additional, 14, 0, default=0), 16),
            keep_after=_field(additional, 17, 0, default=0) != 0,
            direction=_signed(_field(additional, 16, 0, default=(1 << 64) - 1), 32),
        )
    return result


def decode_packet(opcode, body):
    """Decode supported native packets without applying any domain projection.

    Unknown opcodes return an explicit unknown record. A successfully parsed
    wrapper can still have unsupported family/execution semantics.
    """
    if type(opcode) is not int or not 0 < opcode < 65536:
        raise MalformedPacket("Invalid opcode")
    reader = _Reader(body)
    result = {"opcode": opcode}
    if opcode == 12847:
        result.update(fight=reader.read("i"), phase=reader.read("b"))
        result["metadata"] = reader.read("qqq")
        reader.blob("i")  # topology
        reader.blob("h")  # fight metadata
        reader.read("qq")
        compact = reader.read("B") == 1
        actors = []
        for _ in range(reader.count("b")):
            uid = reader.read("q")
            kind, team, extra = reader.read("bbb")
            descriptor = effects = None
            if not compact:
                descriptor, effects = reader.blob("h"), reader.blob("h")
            actors.append(
                dict(
                    id=uid,
                    kind=kind,
                    team=team,
                    extra=extra,
                    descriptor=descriptor,
                    effects=effects,
                )
            )
        result.update(kind="admission", actors=actors, compact=compact)
        reader.take(reader.count("b") * 9)  # cvc team identities
        reader.take(reader.count("b"))
        reader.take(reader.count("b"))
        for _ in range(reader.count("i")):
            reader.blob("i")
    elif opcode == 13652:
        result.update(kind="positions", fight=reader.read("i"))
        result["positions"] = [
            (reader.read("q"), reader.read("iih")) for _ in range(reader.count("h"))
        ]
        result["immediate"] = reader.read("B") == 1
    elif opcode == 12304:
        result.update(
            kind="despawn",
            flag=reader.read("B") == 1,
            second_flag=reader.read("B") == 1,
        )
        result["actors"] = [reader.read("bq") for _ in range(reader.count("B"))]
    elif opcode in (12613, 13497, 13560, 13624, 12727, 12238):
        result.update(zip(("fight", "action", "special"), reader.read("iii")))
        if opcode == 12238:
            result.update(kind="terminal", shortened=reader.read("B") == 1)
            if not result["shortened"]:
                result["winners"] = [reader.read("q") for _ in range(reader.count("b"))]
                result["losers"] = [reader.read("q") for _ in range(reader.count("b"))]
                result["others"] = [reader.read("q") for _ in range(reader.count("b"))]
        elif opcode == 13624:
            result.update(
                kind="movement",
                actor=reader.read("q"),
                direction=reader.read("b"),
                mode=reader.read("b"),
            )
            remaining = len(body) - reader.offset
            # amK ignores a partial trailing point; do not promote it to
            # supported convergence even though original construction accepts it.
            result["path"] = [reader.read("iih") for _ in range(remaining // 10)]
            result["partial_path_bytes"] = reader.take(remaining % 10)
            result["native_path_valid"] = 0 < remaining < 65536
        elif opcode == 12727:
            result.update(
                kind="fighter_status", actor=reader.read("q"), status=reader.read("b")
            )
        else:
            immediate = reader.read("B") == 1 if opcode == 12613 else None
            family = reader.read("i")
            result.update(
                kind="effect_remove" if opcode == 13560 else "effect",
                immediate=immediate,
                effect=_effect(reader.blob("h"), family),
            )
            if opcode == 13560:
                result.update(
                    removal_target=reader.read("q"), source_uid=reader.read("q")
                )
    elif opcode == 13420:
        result.update(kind="fence", fight=reader.read("i"))
    else:
        return dict(result, kind="unsupported")
    reader.done()
    return result


@dataclass(frozen=True)
class Recipient:
    role: str
    generation: str

    def __post_init__(self):
        if self.role not in ("participant", "spectator") or not self.generation:
            raise ValueError("Explicit recipient role and generation required")


@dataclass(frozen=True)
class EffectContract:
    """Independent native definition facts, never inferred from Python catalog.

    Key contracts by exact running definition and family. The evidence hash
    identifies the independent proof receipt supplied by the caller. This
    attestation is not generated or self-qualified by this decoder.
    """

    family: int
    retained: bool
    observation_registers: bool
    evidence_sha256: str

    def __post_init__(self):
        if (
            self.family not in (310, 308, 315)
            or type(self.retained) is not bool
            or type(self.observation_registers) is not bool
            or not _HASH.fullmatch(self.evidence_sha256)
        ):
            raise ValueError("Invalid independently attested effect contract")


@dataclass(frozen=True)
class BlockCompletion:
    """Actual original-consumer completion evidence for a closed FIFO block."""

    block_index: int
    action_ids: tuple
    evidence_sha256: str

    def __post_init__(self):
        if (
            type(self.block_index) is not int
            or self.block_index < 0
            or type(self.action_ids) is not tuple
            or not all(type(value) is int for value in self.action_ids)
            or not _HASH.fullmatch(self.evidence_sha256)
        ):
            raise ValueError("Invalid native completion witness")


@dataclass(frozen=True)
class TerminalCompletion:
    """Observed normal aUH/ciq/dLN cleanup, distinct from action FIFO/ACK.

    The original terminal consumer involves the renderer and aTT scheduling;
    decoding cvF or receiving 12925 alone cannot supply this witness.
    """

    action_id: int
    evidence_sha256: str

    def __post_init__(self):
        if type(self.action_id) is not int or not _HASH.fullmatch(self.evidence_sha256):
            raise ValueError("Invalid independent terminal cleanup witness")


@dataclass
class RecipientView:
    entities: dict = field(default_factory=dict)
    positions: dict = field(default_factory=dict)
    states: dict = field(default_factory=dict)
    areas: dict = field(default_factory=dict)
    runners: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    status: str
    component: str
    packet_index: int
    relationship: str


@dataclass
class Reconstruction:
    recipient: Recipient
    fight_id: int | None
    received: RecipientView
    executed: RecipientView
    decoded: tuple
    findings: tuple
    pending_blocks: tuple
    open_actions: tuple
    pending_terminal: int | None = None
    deferred_removals: tuple = ()

    @property
    def complete(self):
        return (
            not self.findings
            and not self.pending_blocks
            and not self.open_actions
            and self.pending_terminal is None
        )


class _Reconstructor:
    def __init__(self, recipient, contracts, completions):
        self.recipient = recipient
        self.contracts = dict(contracts)
        if any(
            not (
                type(k) is int
                or (
                    type(k) is tuple
                    and len(k) == 2
                    and all(type(part) is int for part in k)
                )
            )
            or not isinstance(v, EffectContract)
            for k, v in self.contracts.items()
        ):
            raise ValueError("Exact independent effect definition contracts required")
        self.witnesses = {}
        for completion in completions:
            if (
                not isinstance(completion, BlockCompletion)
                or completion.block_index in self.witnesses
            ):
                raise ValueError("Unique block completion witnesses required")
            self.witnesses[completion.block_index] = completion
        self.fight = None
        self.received, self.executed = RecipientView(), RecipientView()
        self.decoded, self.findings = [], []
        self.blocks, self.open = [], []
        self.actions = set()
        self.next_block, self.next_execution = 0, 0
        self.terminal = None
        self.deferred_removals = []

    def finding(self, status, component, index, relationship):
        self.findings.append(Finding(status, component, index, relationship))

    def known(self, view, actor, index, component):
        if actor is not None and actor not in view.entities:
            self.finding(
                "contradiction",
                component,
                index,
                "Unknown required entity " + str(actor),
            )
            return False
        return True

    def feed(self, opcode, body, index):
        try:
            packet = decode_packet(opcode, body)
        except MalformedPacket as error:
            self.finding("malformed", "queue", index, str(error))
            return
        self.decoded.append(packet)
        kind = packet["kind"]
        fight = packet.get("fight")
        if fight is not None:
            if self.fight is None and kind == "admission":
                self.fight = fight
            elif self.fight != fight:
                self.finding(
                    "contradiction",
                    "entities",
                    index,
                    "Unknown or different fight identity",
                )
                return
        if kind == "admission":
            for actor in packet["actors"]:
                uid = actor["id"]
                if uid in self.executed.entities:
                    self.finding(
                        "contradiction",
                        "entities",
                        index,
                        "Duplicate entity admission " + str(uid),
                    )
                    continue
                entry = {key: actor[key] for key in ("kind", "team", "extra")}
                self.received.entities[uid] = dict(entry)
                self.executed.entities[uid] = dict(entry)
                if actor["descriptor"] or actor["effects"]:
                    self.finding(
                        "unknown_coverage",
                        "states",
                        index,
                        "Nested admission actor/effect snapshot not reconstructed",
                    )
                    self.finding(
                        "unknown_coverage",
                        "positions",
                        index,
                        "Nested admission POSITION not reconstructed",
                    )
        elif kind == "positions":
            if not packet["immediate"]:
                self.finding(
                    "unknown_coverage",
                    "positions",
                    index,
                    "Non-immediate placement consumer",
                )
                return
            for actor, cell in packet["positions"]:
                if self.known(self.executed, actor, index, "positions"):
                    self.received.positions[actor] = tuple(cell)
                    self.executed.positions[actor] = dict(
                        cell=tuple(cell), direction=None
                    )
        elif kind == "despawn":
            for actor_kind, actor in packet["actors"]:
                if actor_kind not in (0, 1, 4):
                    self.finding(
                        "unknown_coverage",
                        "entities",
                        index,
                        "Unsupported ctA entity kind",
                    )
                    continue
                if self.known(self.executed, actor, index, "entities"):
                    # cgN -> buH.aY queues jqx for fight termination; it is
                    # NOT fdt.bx and cannot immediately unregister a fighter.
                    self.deferred_removals.append(actor)
        elif kind == "terminal":
            if self.terminal is not None:
                self.finding(
                    "contradiction", "queue", index, "Duplicate pending terminal action"
                )
            elif packet["shortened"]:
                self.finding(
                    "unknown_coverage",
                    "entities",
                    index,
                    "Shortened terminal lifecycle not modeled",
                )
            else:
                # ckc normal completion goes through aTT.f, not the ordinary
                # aER block path; do not fabricate a fence or automatic drain.
                self.terminal = packet["action"]
        elif kind == "fence":
            self.close(index)
        elif kind == "unsupported":
            self.finding(
                "unknown_coverage", "queue", index, "Unsupported opcode " + str(opcode)
            )
        else:
            action = packet["action"]
            if action in self.actions:
                self.finding(
                    "contradiction",
                    "queue",
                    index,
                    "Duplicate active native action identity " + str(action),
                )
            self.actions.add(action)
            self.open.append((index, packet))
            if kind == "movement":
                if (
                    self.known(self.received, packet["actor"], index, "positions")
                    and packet["path"]
                ):
                    self.received.positions[packet["actor"]] = tuple(packet["path"][-1])
            elif kind in ("effect", "effect_remove"):
                self.received.runners[packet["effect"]["uid"]] = deepcopy(
                    packet["effect"]
                )
            # cvK's dispatcher closes its accumulating block itself.
            if kind == "fighter_status":
                self.close(index)

    def close(self, index):
        # Original aER.cbu returns when no accumulating dIH group exists.
        # Consecutive native fences cannot fabricate empty pending blocks.
        if not self.open:
            return
        block = (self.next_block, tuple(self.open), index)
        self.next_block += 1
        self.open.clear()
        self.blocks.append(block)
        while self.blocks:
            number, actions, boundary = self.blocks[0]
            witness = self.witnesses.get(number)
            if witness is None:
                break
            actual = tuple(packet["action"] for _, packet in actions)
            if actual != witness.action_ids:
                self.finding(
                    "contradiction",
                    "queue",
                    boundary,
                    "Completion witness action identities differ",
                )
                break
            # Never drain a later completed block ahead of a pending predecessor.
            for packet_index, packet in actions:
                before = deepcopy(self.executed)
                try:
                    self.apply(packet, packet_index)
                except MalformedPacket as error:
                    self.executed = before
                    self.finding("malformed", "queue", packet_index, str(error))
                self.actions.discard(packet["action"])
            self.blocks.pop(0)
            self.next_execution = number + 1

    def apply(self, packet, index):
        kind = packet["kind"]
        if kind == "movement":
            path = packet["path"]
            if (
                packet["mode"] != 0
                or not packet["native_path_valid"]
                or packet["partial_path_bytes"]
                or not path
                or not 0 <= packet["direction"] < 8
            ):
                self.finding(
                    "unknown_coverage",
                    "positions",
                    index,
                    "Unsupported native movement variant/path",
                )
                return
            actor = packet["actor"]
            if self.known(self.executed, actor, index, "positions"):
                current = self.executed.positions.get(actor)
                if current is not None and current["cell"] != tuple(path[0]):
                    self.finding(
                        "contradiction",
                        "positions",
                        index,
                        "Movement origin differs from known position",
                    )
                self.executed.positions[actor] = dict(
                    cell=tuple(path[-1]), direction=packet["direction"]
                )
        elif kind == "fighter_status":
            self.finding(
                "unknown_coverage",
                "entities",
                index,
                "Fighter life status is not unconditional entity removal",
            )
        elif kind in ("effect", "effect_remove"):
            self.apply_effect(packet, index)

    def apply_effect(self, packet, index):
        effect = packet["effect"]
        family, uid = effect["family"], effect["uid"]
        if family not in (310, 308, 315):
            # An unmodeled effect can relocate/create/remove entities. Merely
            # labeling it an unknown area would wrongly qualify positions.
            self.finding(
                "unknown_coverage",
                "queue",
                index,
                "Unsupported native effect family " + str(family),
            )
            return
        component = "states" if family == 310 else "areas"
        contract = self.contracts.get(
            (effect["definition"], family), self.contracts.get(effect["definition"])
        )
        if contract is None or contract.family != family:
            self.finding(
                "unknown_coverage",
                component,
                index,
                "Missing independent native definition contract",
            )
            return
        if uid <= 0:
            self.finding("contradiction", component, index, "Invalid running identity")
            return
        if not all(
            self.known(self.executed, effect[key], index, component)
            for key in ("caster", "target")
        ):
            return
        if packet["kind"] == "effect_remove":
            existing = self.executed.runners.get(uid)
            if existing is None or existing["family"] != family:
                self.finding(
                    "contradiction",
                    component,
                    index,
                    "Unapplication references unknown owned runner",
                )
                return
            if any(
                existing[key] != effect[key]
                for key in (
                    "definition",
                    "base_uid",
                    "caster",
                    "target",
                    "container_type",
                    "container_id",
                )
            ):
                self.finding(
                    "contradiction",
                    component,
                    index,
                    "Unapplication runner identity relationship changed",
                )
                return
            if packet["removal_target"] != (
                existing["target"]
                if existing["target"] is not None
                else existing["caster"]
            ):
                self.finding(
                    "contradiction",
                    component,
                    index,
                    "Unapplication manager differs from owner",
                )
                return
            forced = _field(effect["timing"], 1, 0, default=0) != 0
            if not forced:
                self.finding(
                    "unknown_coverage",
                    component,
                    index,
                    "Unapplication lacks independently supported forced gate",
                )
                return
            self.executed.runners.pop(uid)
            if family == 310:
                self.executed.states.pop(uid, None)
            elif not existing["keep_after"]:
                self.executed.areas.pop(existing["area_uid"], None)
            return
        if family == 310:
            register = (
                contract.observation_registers
                if packet["opcode"] == 13497
                else contract.retained
            )
            if packet["immediate"] is True:
                self.finding(
                    "unknown_coverage",
                    "states",
                    index,
                    "Immediate state recalculation not modeled",
                )
                return
            if register:
                if uid in self.executed.runners:
                    self.finding(
                        "contradiction",
                        "states",
                        index,
                        "Duplicate retained state identity",
                    )
                    return
                self.executed.runners[uid] = deepcopy(effect)
                self.executed.states[uid] = {
                    key: effect[key]
                    for key in (
                        "state_id",
                        "level",
                        "caster",
                        "target",
                        "base_uid",
                        "container_type",
                        "container_id",
                    )
                }
        elif family in (308, 315):
            if packet["opcode"] != 12613 or packet["immediate"] is not False:
                self.finding(
                    "unknown_coverage",
                    "areas",
                    index,
                    "Area observation/recalculation route not modeled",
                )
                return
            area = effect["area_uid"]
            if area in self.executed.areas or uid in self.executed.runners:
                self.finding(
                    "contradiction",
                    "areas",
                    index,
                    "Duplicate area or creating runner identity",
                )
                return
            if "cell" not in effect:
                self.finding(
                    "unknown_coverage", "areas", index, "Missing original area origin"
                )
                return
            self.executed.areas[area] = {
                key: effect[key]
                for key in ("prototype", "level", "caster", "cell", "direction")
            }
            if contract.retained:
                self.executed.runners[uid] = deepcopy(effect)


def reconstruct_packets(
    bootstrap,
    packets,
    *,
    recipient,
    effect_contracts=None,
    completions=(),
    terminal_completion=None
):
    """Reconstruct one ordered recipient generation, preserving pending FIFO.

    Each stream element is ``(opcode, immutable_payload_bytes)``. Completion
    witnesses index fences/auto-closed native blocks from zero, across the
    whole stream. An empty/absent bootstrap never silently establishes a view.
    Unsupported inputs stay explicit findings; malformed bytes do not mutate
    the affected modeled component. Inputs and projection objects are not edited.
    """
    if not isinstance(recipient, Recipient):
        raise ValueError("Explicit Recipient required")
    initial = tuple(islice(iter(bootstrap), MAX_PACKETS + 1))
    updates = tuple(islice(iter(packets), MAX_PACKETS + 1))
    if len(initial) + len(updates) > MAX_PACKETS:
        raise ValueError("Packet stream exceeds reconstruction bounds")
    engine = _Reconstructor(recipient, effect_contracts or {}, tuple(completions))
    if not initial:
        engine.finding(
            "incomplete_evidence", "entities", -1, "Missing recipient bootstrap"
        )
    for index, entry in enumerate((*initial, *updates)):
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise ValueError("Require opcode/payload pairs")
        engine.feed(*entry, index)
    for number in engine.witnesses:
        if number >= engine.next_block:
            engine.finding(
                "incomplete_evidence",
                "queue",
                -1,
                "Completion witness has no observed closed block",
            )
    if terminal_completion is not None:
        if not isinstance(terminal_completion, TerminalCompletion):
            raise ValueError("Explicit TerminalCompletion required")
        if engine.terminal != terminal_completion.action_id:
            engine.finding(
                "contradiction",
                "entities",
                -1,
                "Terminal cleanup witness has no matching cvF action",
            )
        elif engine.blocks or engine.open:
            engine.finding(
                "incomplete_evidence",
                "queue",
                -1,
                "Terminal cleanup cannot bypass unresolved execution",
            )
        else:
            # Original fcb.ciq -> dLN -> fdt.clear retires combat membership.
            # This is combat-view cleanup, not deletion of world characters.
            engine.executed.entities.clear()
            engine.executed.positions.clear()
            engine.deferred_removals.clear()
            engine.terminal = None
            if engine.executed.states or engine.executed.areas:
                engine.finding(
                    "unknown_coverage",
                    "states",
                    -1,
                    "Terminal retained manager cleanup outside supported slice",
                )
                engine.finding(
                    "unknown_coverage",
                    "areas",
                    -1,
                    "Terminal area manager cleanup outside supported slice",
                )
    return Reconstruction(
        recipient,
        engine.fight,
        engine.received,
        engine.executed,
        tuple(engine.decoded),
        tuple(engine.findings),
        tuple(
            dict(index=n, action_ids=tuple(p["action"] for _, p in actions))
            for n, actions, _ in engine.blocks
        ),
        tuple(p["action"] for _, p in engine.open),
        engine.terminal,
        tuple(engine.deferred_removals),
    )


def compare_permitted_projection(reconstruction, *, recipient, projection):
    """Compare only caller-declared disclosed components at an executed boundary.

    The caller owns disclosure rules; this API cannot qualify arbitrary private
    facts as public. Role/generation must match exactly. No hidden full-Fight
    default projection is provided. Unknowns for a requested component (or queue)
    prevent convergence even if its current partial values happen to match.
    """
    if (
        not isinstance(reconstruction, Reconstruction)
        or recipient != reconstruction.recipient
        or not isinstance(projection, dict)
        or not projection
        or not set(projection) <= COMPONENTS - {"queue"}
    ):
        raise ValueError(
            "Explicit same-recipient permitted component projection required"
        )
    differences = []
    for component, expected in projection.items():
        if not isinstance(expected, dict):
            raise ValueError("Permitted component projection must be a mapping")
        actual = getattr(reconstruction.executed, component)
        if actual != expected:
            differences.append(component)
    unresolved = [
        finding
        for finding in reconstruction.findings
        if finding.component in set(projection) | {"queue"}
    ]
    pending = bool(
        reconstruction.pending_blocks
        or reconstruction.open_actions
        or reconstruction.pending_terminal is not None
    )
    return dict(
        matches=not differences and not unresolved and not pending,
        differences=tuple(differences),
        findings=tuple(unresolved),
        pending=pending,
    )
