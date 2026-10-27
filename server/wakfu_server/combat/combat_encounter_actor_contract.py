"""Frozen scene-role bindings over actual native actor creation receipts.

Contracts are explicit server content, never inferred from names, HP or native
properties. This sidecar does not create actors, grant books, or change control.
Unresolved declarations cannot be admitted. All records are checkpoint values.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json


SCHEMA = "wakemu-encounter-actor-contract-v1"


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _name(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 256


@dataclass(frozen=True)
class ActorRoleSpec:
    role: str
    reference: int
    constructor: str = "ordinary_npc"
    required_initial_states: tuple[int, ...] = ()
    minimum_hp: int | None = None
    native_owner_role: str | None = None
    scene_parent_role: str | None = None
    retire_on_success: bool = False
    retirement_effect_reference: int | None = None
    retirement_caster_role: str = "boundary_actor"

    def validate(self):
        if (
            not _name(self.role)
            or type(self.reference) is not int
            or self.reference <= 0
            or self.constructor not in ("ordinary_npc", "native_summon")
            or type(self.required_initial_states) is not tuple
            or any(type(x) is not int or x <= 0 for x in self.required_initial_states)
            or len(set(self.required_initial_states))
            != len(self.required_initial_states)
            or self.minimum_hp is not None
            and (type(self.minimum_hp) is not int or self.minimum_hp < 0)
            or type(self.retire_on_success) is not bool
            or self.native_owner_role is not None
            and (
                not _name(self.native_owner_role) or self.constructor != "native_summon"
            )
            or self.scene_parent_role is not None
            and not _name(self.scene_parent_role)
            or self.retire_on_success
            and (
                type(self.retirement_effect_reference) is not int
                or self.retirement_effect_reference <= 0
            )
            or not self.retire_on_success
            and self.retirement_effect_reference is not None
        ):
            raise ValueError("Incomplete encounter actor role")
        if self.retirement_caster_role not in ("boundary_actor", "boss") and not (
            isinstance(self.retirement_caster_role, str)
            and self.retirement_caster_role.startswith("role:")
            and _name(self.retirement_caster_role[5:])
        ):
            raise ValueError("Missing native scene retirement caster role")
        return self


@dataclass(frozen=True)
class EncounterActorContract:
    policy: str
    version: int
    authority: str
    map_id: int
    initial_references: tuple[int, ...]
    catalog_revision: str
    source_paths: tuple[str, ...]
    roles: tuple[ActorRoleSpec, ...]
    terminal_policies: tuple[str, ...]
    unresolved: tuple[str, ...] = ()

    def validate(self):
        if (
            self.unresolved
            or not _name(self.policy)
            or not _name(self.authority)
            or type(self.version) is not int
            or self.version < 1
            or type(self.map_id) is not int
            or type(self.initial_references) is not tuple
            or not self.initial_references
            or any(type(x) is not int or x <= 0 for x in self.initial_references)
            or tuple(sorted(self.initial_references)) != self.initial_references
            or not isinstance(self.catalog_revision, str)
            or len(self.catalog_revision) != 64
            or any(c not in "0123456789abcdef" for c in self.catalog_revision)
            or type(self.source_paths) is not tuple
            or not self.source_paths
            or any(
                not _name(x) or x.startswith("/") or ".." in x.split("/")
                for x in self.source_paths
            )
            or len(set(self.source_paths)) != len(self.source_paths)
            or type(self.roles) is not tuple
            or not self.roles
            or any(type(x) is not ActorRoleSpec for x in self.roles)
            or type(self.terminal_policies) is not tuple
            or not self.terminal_policies
            or any(not _name(x) for x in self.terminal_policies)
        ):
            raise ValueError("Encounter actor contract is incomplete or unresolved")
        names = {role.validate().role for role in self.roles}
        if len(names) != len(self.roles):
            raise ValueError("Duplicate encounter actor role")
        for role in self.roles:
            for parent in (role.native_owner_role, role.scene_parent_role):
                if parent is not None and (parent not in names or parent == role.role):
                    raise ValueError("Unknown or self-owned scene role")
            if (
                role.retirement_caster_role.startswith("role:")
                and role.retirement_caster_role[5:] not in names
            ):
                raise ValueError("Unknown native retirement caster binding")
        # Parent relationships must be finite, even when only scene metadata.
        edges = {
            r.role: tuple(
                x for x in (r.native_owner_role, r.scene_parent_role) if x is not None
            )
            for r in self.roles
        }

        def visit(name, path):
            if name in path:
                raise ValueError("Cyclic encounter actor role ownership")
            for parent in edges[name]:
                visit(parent, path | {name})

        for name in names:
            visit(name, set())
        return self

    def record(self):
        self.validate()
        return json.loads(json.dumps(asdict(self)))


def contract_from_record(record):
    if not isinstance(record, dict):
        raise ValueError("Missing immutable encounter actor declaration")
    try:
        values = dict(record)
        values["roles"] = tuple(
            ActorRoleSpec(
                **dict(
                    role, required_initial_states=tuple(role["required_initial_states"])
                )
            )
            for role in values["roles"]
        )
        for name in (
            "initial_references",
            "source_paths",
            "terminal_policies",
            "unresolved",
        ):
            values[name] = tuple(values[name])
        spec = EncounterActorContract(**values).validate()
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError("Malformed frozen encounter actor declaration") from error
    if spec.record() != record:
        raise ValueError("Encounter actor declaration changed")
    return spec


def freeze_actor_contract(fight, spec, *, map_id, initial_references):
    """Called only for an explicitly selected source-backed admission.

    No lookup by breed activates a contract. Existing fights cannot replace a
    frozen policy, and current active pointers are not consulted after admission.
    """
    if type(spec) is not EncounterActorContract:
        raise ValueError("Typed encounter actor declaration required")
    spec.validate()
    if (
        fight.phase != "placement"
        or type(fight.id) is not int
        or map_id != spec.map_id
        or tuple(sorted(initial_references)) != spec.initial_references
    ):
        raise ValueError("Encounter actor contract belongs to another admission")
    from .combat_encounter_source_revision import source_revision_matches

    if source_revision_matches(spec.catalog_revision, spec.source_paths) is not True:
        raise ValueError("Encounter actor native source pins do not match")
    declaration = spec.record()
    base = dict(
        schema=SCHEMA,
        policy=spec.policy,
        version=spec.version,
        authority=spec.authority,
        fight_id=fight.id,
        map_id=spec.map_id,
        initial_references=list(spec.initial_references),
        catalog_revision=spec.catalog_revision,
        roles=declaration["roles"],
        declaration=declaration,
    )
    digest = _digest(base)
    existing = getattr(fight, "native_encounter_actor_contract", None)
    if existing is not None:
        if actor_contract_admission_digest(fight) != digest:
            raise ValueError("Cannot replace an admitted encounter actor contract")
        return deepcopy(existing)
    fight.native_encounter_actor_contract = dict(
        base, admission_digest=digest, bindings={}, terminal_receipts={}
    )
    return deepcopy(fight.native_encounter_actor_contract)


def actor_contract_admission_digest(fight):
    record = getattr(fight, "native_encounter_actor_contract", None)
    expected_fields = {
        "schema",
        "policy",
        "version",
        "authority",
        "fight_id",
        "map_id",
        "initial_references",
        "catalog_revision",
        "roles",
        "declaration",
        "admission_digest",
        "bindings",
        "terminal_receipts",
    }
    if (
        not isinstance(record, dict)
        or set(record) != expected_fields
        or record.get("schema") != SCHEMA
        or record.get("fight_id") != fight.id
        or not isinstance(record.get("bindings"), dict)
        or not isinstance(record.get("terminal_receipts"), dict)
    ):
        raise ValueError("Missing frozen encounter actor contract")
    spec = contract_from_record(record["declaration"])
    if any(
        record[name] != getattr(spec, name)
        for name in ("policy", "version", "authority", "map_id", "catalog_revision")
    ):
        raise ValueError("Frozen actor contract scope drifted")
    if (
        record["initial_references"] != list(spec.initial_references)
        or record["roles"] != spec.record()["roles"]
    ):
        raise ValueError("Frozen actor contract role inventory drifted")
    base = {
        key: value
        for key, value in record.items()
        if key not in ("admission_digest", "bindings", "terminal_receipts")
    }
    if record["admission_digest"] != _digest(base):
        raise ValueError("Frozen actor admission digest changed")
    return record["admission_digest"]


def actor_role_spec(fight, role):
    actor_contract_admission_digest(fight)
    spec = contract_from_record(fight.native_encounter_actor_contract["declaration"])
    try:
        return next(item for item in spec.roles if item.role == role)
    except StopIteration as error:
        raise ValueError("Unknown admitted actor role") from error


def _birth(fight, actor, role):
    if role.constructor == "ordinary_npc":
        receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor.id)
        if (
            actor.controlled
            or getattr(actor, "native_summon_source", None) is not None
            or not isinstance(receipt, dict)
            or receipt.get("initialized") is not True
            or receipt.get("ref") != role.reference
            or receipt.get("descriptor_level") != actor.effective_level
        ):
            raise ValueError("Actor role lacks its actual native NPC constructor")
        initial = {row.get("state_id") for row in receipt.get("resolved_states", ())}
        if not set(role.required_initial_states) <= initial:
            raise ValueError("Actor constructor lacks declared native initial states")
        return dict(
            kind="ordinary_npc",
            reference=role.reference,
            receipt_digest=_digest(receipt),
        )
    from .combat_summon_retirement import _registration

    _, receipt, source, _, _ = _registration(fight, actor.id)
    if source["ref"] != role.reference:
        raise ValueError("Scene summon has the wrong native breed")
    return dict(
        kind="native_summon",
        reference=source["ref"],
        caster_id=receipt["caster_id"],
        controller_id=receipt["controller_id"],
        source_digest=_digest(source),
    )


def bind_actor_role(fight, role_name, actor_id):
    """Record an actual birth; never manufacture owner/control relationships."""
    role = actor_role_spec(fight, role_name)
    actor = fight.actors.get(actor_id)
    if actor is None:
        raise ValueError("Scene role requires an actual owned actor")
    record = fight.native_encounter_actor_contract
    if any(
        row["actor_id"] == actor_id
        for key, row in record["bindings"].items()
        if key != role_name
    ):
        raise ValueError("One actor cannot impersonate two scene roles")
    birth = _birth(fight, actor, role)
    from .combat_controller_registry import _row

    controller = _row(fight, actor_id)
    from .combat_global_pv_collections import global_fighter_guards

    if global_fighter_guards(fight, actor_id) != dict(baF=True, baG=False, baK=False):
        raise ValueError("Scene role birth must still be genuinely in play")
    if role.minimum_hp is not None and (
        not isinstance(actor.effect_minima, dict)
        or actor.effect_minima.get(1) != role.minimum_hp
    ):
        raise ValueError("Scene role native HP minimum differs from its source")
    if role.native_owner_role is not None:
        owner = record["bindings"].get(role.native_owner_role)
        if owner is None or birth.get("caster_id") != owner["actor_id"]:
            raise ValueError(
                "Scene summon does not belong to its declared native owner"
            )
    binding = dict(
        actor_id=actor_id,
        birth=birth,
        original_owner_id=actor.owner_id,
        original_controlled=actor.controlled,
        original_controller=controller["original_controller"],
        original_team=controller["original_team"],
    )
    existing = record["bindings"].get(role_name)
    if existing is not None and existing != binding:
        raise ValueError("Scene role cannot be rebound to another actor")
    record["bindings"] = dict(record["bindings"], **{role_name: binding})
    return deepcopy(binding)


def validate_actor_bindings(fight):
    """Current transfers may vary; original identity and birth provenance may not."""
    actor_contract_admission_digest(fight)
    from .combat_controller_registry import _row

    record = fight.native_encounter_actor_contract
    seen = set()
    for name, binding in record["bindings"].items():
        role = actor_role_spec(fight, name)
        identity = binding.get("actor_id")
        actor = fight.actors.get(identity)
        if actor is None or identity in seen:
            raise ValueError("Missing or duplicate bound scene actor")
        seen.add(identity)
        controller = _row(fight, identity)
        if (
            binding.get("birth") != _birth(fight, actor, role)
            or binding.get("original_owner_id") != actor.owner_id
            or binding.get("original_controlled") is not actor.controlled
            or binding.get("original_controller") != controller["original_controller"]
            or binding.get("original_team") != controller["original_team"]
        ):
            raise ValueError("Scene actor ownership or original controller changed")
        if role.native_owner_role is not None:
            owner = record["bindings"].get(role.native_owner_role)
            if owner is None or binding["birth"].get("caster_id") != owner["actor_id"]:
                raise ValueError("Scene actor native owner binding changed")
    return deepcopy(record["bindings"])
