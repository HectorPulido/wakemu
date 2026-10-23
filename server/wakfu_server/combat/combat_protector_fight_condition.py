"""Native eOK predicate backed by the exact published protector registry.

This bridge uses the existing world publisher's complete records and the
actual constructor class of every fighter. It does not infer protector status
from species, nation, team, HP, profession, equipment or an arbitrary flag.
"""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class PublishedProtectorRegistry:
    map_id: int
    instance_id: int
    associations: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if (
            type(self.map_id) is not int
            or self.map_id <= 0
            or type(self.instance_id) is not int
            or self.instance_id < 0
            or not isinstance(self.associations, tuple)
        ):
            raise ValueError("Missing complete world protector publication")
        actors, protectors = set(), set()
        for row in self.associations:
            if (
                not isinstance(row, tuple)
                or len(row) != 2
                or type(row[0]) is not int
                or row[0] == 0
                or not -(2**63) <= row[0] < 2**63
                or type(row[1]) is not int
                or not 0 < row[1] < 2**31
                or row[0] in actors
                or row[1] in protectors
            ):
                raise ValueError("Invalid published protector association")
            actors.add(row[0])
            protectors.add(row[1])

    def association(self, actor_id, constructor):
        if type(actor_id) is not int:
            raise ValueError("Missing actual fighter identity")
        if constructor == "biB":
            # biB/bjo inherits eGj.dsH's actual null implementation.
            return None
        if constructor != "bje":
            raise ValueError("Unqualified native protector constructor")
        # bje.dso searches bLU for bLO.cXS()==this.Sn(), not breed identity.
        return dict(self.associations).get(actor_id)


def capture_published_registry(records, map_id, instance_id):
    """Read the exact complete wW records produced by npc_protectors.records."""
    if not isinstance(records, (tuple, list)):
        raise ValueError("Missing complete protector publication records")
    associations = []
    protectors = set()
    for record in records:
        if not isinstance(record, bytes) or len(record) < 5:
            raise ValueError("Unqualified protector publication record")
        protector = struct.unpack_from(">i", record)[0]
        if not 0 < protector < 2**31 or protector in protectors:
            raise ValueError("Invalid published protector identity")
        protectors.add(protector)
        offset = 4
        nation_flag = record[offset]
        offset += 1
        if nation_flag not in (0, 1):
            raise ValueError("Unknown native protector nation flag")
        if nation_flag:
            if len(record) < offset + 12:
                raise ValueError("Truncated protector territory publication")
            original, current, territory = struct.unpack_from(">iii", record, offset)
            offset += 12
            if (
                not 0 <= original < 2**31
                or not 0 <= current < 2**31
                or not 0 < territory < 2**31
            ):
                raise ValueError("Unqualified protector nation/territory")
        if len(record) < offset + 1:
            raise ValueError("Truncated protector actor flag")
        actor_flag = record[offset]
        offset += 1
        if actor_flag not in (0, 1):
            raise ValueError("Unknown native protector actor flag")
        if actor_flag:
            if len(record) < offset + 12 + 11:
                raise ValueError("Truncated protector actor publication")
            appearance, actor = struct.unpack_from(">iq", record, offset)
            offset += 12
            if not 0 < appearance < 2**31:
                raise ValueError("Unqualified protector appearance")
            associations.append((actor, protector))
        if len(record) < offset + 11:
            raise ValueError("Truncated protector optional sections")
        # Tax/wish/ecology sections do not bind an actor. They remain owned and
        # validated by the existing producer; this is not a network decoder.
    return PublishedProtectorRegistry(map_id, instance_id, tuple(associations))


def capture_world_registry(db, character):
    """Reuse the actual published world contract inside fight construction.

    The publisher authenticates captured SQL identity, map, instance and
    publication authorization. An empty result is its explicit published empty
    registry for that scene, not an unknown protector lookup default.
    """
    from wakfu_server import npc_protectors, protector_ecosystem

    records = npc_protectors.bootstrap_records(db, character)
    records = protector_ecosystem.bootstrap_records(
        db,
        character["map_id"],
        records,
        instance_id=character["instance_id"],
    )
    return capture_published_registry(
        records,
        character["map_id"],
        character["instance_id"],
    )


def selector(arguments):
    """eOK accepts no argument or one string; only target selects the target."""
    if not isinstance(arguments, (tuple, list)) or len(arguments) > 1:
        raise ValueError("Unsupported IsProtectorInFight arguments")
    if arguments and type(arguments[0]) is not str:
        raise ValueError("Unsupported IsProtectorInFight selector")
    return "target" if arguments and arguments[0].lower() == "target" else "caster"


def protector_in_fight(selected_actor, fighters, registry, constructor_for_actor):
    """eOK scans every fighter in the selected actor's actual fcb.dLy roster.

    The runtime supplies None for native eII.a null/no fight, otherwise its
    complete owned roster. Constructor provenance comes from the existing
    ordinary actor authority (biB or bje), including later registered summons.
    No life, team or in-play filter is applied by the original predicate.
    """
    if selected_actor is None or fighters is None:
        return False
    if type(registry) is not PublishedProtectorRegistry or not callable(
        constructor_for_actor
    ):
        raise ValueError("Missing authoritative protector registry/actor producer")
    if not isinstance(fighters, dict):
        raise ValueError("Missing complete native fighter roster")
    if (
        type(getattr(selected_actor, "id", None)) is not int
        or fighters.get(selected_actor.id) is not selected_actor
    ):
        raise ValueError("Selected fighter differs from its actual fight roster")
    found = False
    for identity, actor in fighters.items():
        if type(identity) is not int or getattr(actor, "id", None) != identity:
            raise ValueError("Native fighter roster identity mismatch")
        if registry.association(identity, constructor_for_actor(actor)) is not None:
            found = True
    return found


def capture_fight_condition(db, character, fight, ordinary_actor_authority):
    """Capture published registry and real PC/NPC constructor facts at admission.

    Invoke after ordinary actors/properties exist and before their equipment
    Ready roots. The existing ordinary authority authenticates exact actor and
    source membership; this bridge does not accept caller-supplied class flags.
    The returned primitive record is suitable for the fight checkpoint codec.
    """
    from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority

    if type(ordinary_actor_authority) is not OrdinaryActorAuthority:
        raise ValueError("Protector admission requires the actual ordinary authority")
    if type(getattr(fight, "id", None)) is not int or fight.id <= 0:
        raise ValueError("Missing durable fight identity")
    if (
        not isinstance(character, dict)
        or character.get("id") not in ordinary_actor_authority.characters
    ):
        raise ValueError(
            "Protector admission requires an owned participating character"
        )
    selected_source = ordinary_actor_authority.characters[character["id"]]
    if (
        type(character.get("account_id")) is not int
        or character["account_id"] <= 0
        or selected_source.get("account_id") != character["account_id"]
        or any(
            selected_source.get(key) != character.get(key)
            for key in ("map_id", "instance_id")
        )
    ):
        raise ValueError("Protector publication differs from the owned world source")
    registry = capture_world_registry(db, character)
    constructors = []
    for identity, actor in fight.actors.items():
        player, source, *_ = ordinary_actor_authority._creation_facts(fight, actor)
        if source.get("id") != identity:
            raise ValueError("Protector constructor differs from owned source")
        constructors.append([identity, "biB" if player else "bje"])
    return {
        "schema_version": 1,
        "fight_id": fight.id,
        "map_id": registry.map_id,
        "instance_id": registry.instance_id,
        "associations": [list(pair) for pair in registry.associations],
        "constructors": constructors,
    }


def query_fight_condition(fight, selected_actor):
    """Read the checkpointed producer receipt without SQL or live mutation."""
    if selected_actor is None or fight is None:
        return False
    value = getattr(fight, "native_protector_condition", None)
    keys = {
        "schema_version",
        "fight_id",
        "map_id",
        "instance_id",
        "associations",
        "constructors",
    }
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or value["schema_version"] != 1
        or value["fight_id"] != fight.id
    ):
        raise ValueError("Missing exact admitted protector condition receipt")
    if not isinstance(value["associations"], list) or not isinstance(
        value["constructors"], list
    ):
        raise ValueError("Malformed protector condition receipt")
    registry = PublishedProtectorRegistry(
        value["map_id"],
        value["instance_id"],
        tuple(tuple(row) for row in value["associations"]),
    )
    constructors = {}
    for row in value["constructors"]:
        if (
            not isinstance(row, list)
            or len(row) != 2
            or type(row[0]) is not int
            or row[0] in constructors
            or row[1] not in ("biB", "bje")
        ):
            raise ValueError("Malformed admitted native constructor")
        constructors[row[0]] = row[1]

    def constructor(actor):
        if actor.id not in constructors:
            raise ValueError("New fighter lacks actual constructor provenance")
        return constructors[actor.id]

    return protector_in_fight(selected_actor, fight.actors, registry, constructor)


def capture_world_registry_record(db, character, fight_id):
    """Primitive fight-bound publication receipt, captured before equipment Ready."""
    if type(fight_id) is not int or fight_id <= 0:
        raise ValueError("Missing durable protector fight identity")
    registry = capture_world_registry(db, character)
    return dict(
        schema_version=1,
        fight_id=fight_id,
        map_id=registry.map_id,
        instance_id=registry.instance_id,
        associations=[list(pair) for pair in registry.associations],
    )


def constructor_from_authority(authority):
    """Use actual ordinary constructor facts, never a raw actor-kind guess."""
    from .combat_runtime_adapter import NativeActorAuthority

    if (
        type(authority) is not NativeActorAuthority
        or authority.targeting.get("is_eGj") is not True
    ):
        raise ValueError("Missing actual native fighter constructor authority")
    # OrdinaryActorAuthority documents the original dpR constructor baseline:
    # biB/bjo false, bje true. The actor type and NPC prototype independently
    # bind that provenance to the actual registered creation route.
    if (
        authority.is_player is True
        and authority.native_actor_type == 0
        and authority.native_ai_control_baseline is False
    ):
        return "biB"
    if (
        authority.is_player is False
        and authority.native_actor_type in (1, 2, 5)
        and authority.native_ai_control_baseline is True
        and type(authority.native_npc_prototype_ref) is int
        and authority.native_npc_prototype_ref > 0
    ):
        return "bje"
    raise ValueError("Unqualified protector actor constructor provenance")


def query_owned_fight(fight, selected_actor, actor_authority):
    """Resolve current complete roster against checkpointed world publication."""
    if selected_actor is None or fight is None:
        return False
    value = getattr(fight, "native_protector_registry", None)
    keys = {"schema_version", "fight_id", "map_id", "instance_id", "associations"}
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or value["schema_version"] != 1
        or value["fight_id"] != fight.id
        or not isinstance(value["associations"], list)
        or not callable(actor_authority)
    ):
        raise ValueError("Missing exact admitted world protector registry")
    registry = PublishedProtectorRegistry(
        value["map_id"],
        value["instance_id"],
        tuple(tuple(row) for row in value["associations"]),
    )
    return protector_in_fight(
        selected_actor,
        fight.actors,
        registry,
        lambda actor: constructor_from_authority(actor_authority(actor)),
    )


@dataclass(frozen=True)
class ProtectorConditionCapability:
    """Constructor-complete evidence for static admission, never branch truth."""

    factory: object
    adapter: object
    condition: object
    fight_id: int
    registry: PublishedProtectorRegistry
    constructors: tuple


def bind_condition_capability(factory, fight):
    """Bind only the actual adapter and current complete construction receipt.

    Missing authority defers this predicate alone. This does not run eOK,
    allocate effects, query SQL, or decide whether the condition is true.
    """
    from .combat_runtime_adapter import NativeServerRuntimeAdapter

    # The production wrapper delegates attributes to this exact native factory.
    from .combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory

    if type(factory) is OwnedEquipmentRuntimeFactory:
        factory = factory._factory
    from .combat_effect_runtime import NativeEffectRuntimeFactory

    if type(factory) is not NativeEffectRuntimeFactory:
        return None
    condition = getattr(getattr(factory, "contexts", None), "condition", None)
    adapter = getattr(condition, "__self__", None)
    factory.native_protector_condition_capability = None
    if (
        type(adapter) is not NativeServerRuntimeAdapter
        or getattr(condition, "__func__", None)
        is not NativeServerRuntimeAdapter.condition
    ):
        return None
    try:
        value = getattr(fight, "native_protector_registry", None)
        keys = {"schema_version", "fight_id", "map_id", "instance_id", "associations"}
        if (
            not isinstance(value, dict)
            or set(value) != keys
            or value["schema_version"] != 1
            or value["fight_id"] != fight.id
            or type(fight.id) is not int
            or fight.id <= 0
            or not isinstance(value["associations"], list)
            or not isinstance(fight.actors, dict)
        ):
            return None
        registry = PublishedProtectorRegistry(
            value["map_id"],
            value["instance_id"],
            tuple(tuple(row) for row in value["associations"]),
        )
        constructors = []
        for identity, actor in fight.actors.items():
            if type(identity) is not int or getattr(actor, "id", None) != identity:
                return None
            constructors.append(
                (identity, constructor_from_authority(adapter._actor(fight, actor)))
            )
        proof = ProtectorConditionCapability(
            factory, adapter, condition, fight.id, registry, tuple(constructors)
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    factory.native_protector_condition_capability = proof
    return proof


def protector_condition_capability(factory):
    """Attest receipt presence without executing any dynamic criterion query."""
    proof = getattr(factory, "native_protector_condition_capability", None)
    if (
        type(proof) is not ProtectorConditionCapability
        or proof.factory is not factory
        or getattr(getattr(factory, "contexts", None), "condition", None)
        != proof.condition
    ):
        return None
    return True
