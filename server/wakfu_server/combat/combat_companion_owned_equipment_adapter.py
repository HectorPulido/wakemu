"""Adapt durable companion equipment to the shared owned-equipment motor.

Companions keep their native NPC actor identity and authority. This module
only builds the same pinned source format used by player equipment; it does
not create a player-shaped combat actor or a separate effect executor.
"""
from collections.abc import Mapping
from copy import deepcopy


def _npc_source(fight, actor_id, runtime_factory):
    from wakfu_server.combat_companions import registered_source
    from wakfu_server.combat_runtime_adapter import NativeActorAuthority

    actor = fight.actors.get(actor_id)
    rows = getattr(fight, "native_companion_sources", None)
    if actor is None or not isinstance(rows, Mapping):
        raise ValueError("Missing registered companion source snapshot")
    source = rows.get(str(actor_id))
    if (
        not isinstance(source, Mapping)
        or registered_source(fight, actor, source) is None
    ):
        raise ValueError("Companion is not registered from its durable NPC source")
    actor_source = getattr(actor, "native_companion_source", None)
    if not isinstance(actor_source, Mapping) or dict(actor_source) != dict(source):
        raise ValueError("Companion actor source differs from its placement snapshot")
    if (
        actor.controlled is not True
        or actor.owner_id != source.get("account_id")
        or type(source.get("owner_character_id")) is not int
        or source["owner_character_id"] not in fight.actors
    ):
        raise ValueError("Companion actor and selected owner lease do not match")
    authority_provider = getattr(runtime_factory, "summon_authority", None)
    if not callable(authority_provider):
        raise ValueError("Missing native NPC actor authority provider")
    authority = authority_provider(fight, actor)
    if (
        not isinstance(authority, NativeActorAuthority)
        or authority.is_player is not False
        or authority.is_summon is not False
        or authority.native_actor_type != 5
        or authority.native_is_ehp is not False
        or authority.native_account_id != source["account_id"]
        or authority.native_primary_character_id != source["owner_character_id"]
        or authority.native_npc_prototype_ref != source.get("ref")
        or authority.native_real_level != actor.effective_level
        or source.get("level") != actor.effective_level
    ):
        raise ValueError("Runtime did not attest the authentic companion NPC")
    owner = fight.actors[source["owner_character_id"]]
    if (
        not owner.controlled
        or owner.owner_id != source["account_id"]
        or owner.team != actor.team
    ):
        raise ValueError("Companion source has no selected owner lease on its team")
    return actor, dict(source), authority


def _planner_character(level, source, owner_character):
    """Build a temporary physical-item view for the shared EQUIP validator."""
    from wakfu_server.companion_equipment import pseudo_character, criterion_context
    from wakfu_server.combat_actor_snapshot import native_npc_creation_values
    from wakfu_server.equipment_resource_bonuses import from_native_values
    from wakfu_server.equipment import validate_sheet

    entries = source.get("equipment_entries")
    if not isinstance(entries, (tuple, list)):
        raise ValueError("Missing durable companion equipment entries")
    items, seen_uid, seen_slot = [], set(), set()
    for row in entries:
        if not isinstance(row, Mapping) or type(row.get("slot")) is not int:
            raise ValueError("Malformed companion equipment entry")
        entry = row.get("entry")
        item = entry.get("item") if isinstance(entry, Mapping) else None
        metadata = entry.get("metadata") if isinstance(entry, Mapping) else None
        if (
            not isinstance(item, Mapping)
            or not isinstance(metadata, Mapping)
            or type(item.get("uid")) is not int
            or item["uid"] <= 0
            or type(item.get("reference")) is not int
            or item.get("quantity") != 1
            or row["slot"] in seen_slot
            or item["uid"] in seen_uid
        ):
            raise ValueError("Invalid companion equipment UID or slot snapshot")
        gear = dict(item)
        gear["character_id"] = owner_character["id"]
        shards = metadata.get("inventory_item_shards")
        if shards is not None:
            if not isinstance(shards, Mapping) or not isinstance(
                shards.get("shard_state"), (bytes, bytearray)
            ):
                raise ValueError("Malformed companion shard-state snapshot")
            gear["shard_state"] = bytes(shards["shard_state"])
        pets = metadata.get("inventory_pets")
        if pets is not None:
            if not isinstance(pets, Mapping):
                raise ValueError("Malformed companion pet-state snapshot")
            gear["pet"] = dict(pets)
        items.append(gear)
        seen_uid.add(item["uid"])
        seen_slot.add(row["slot"])
    if (
        owner_character.get("id") != source["owner_character_id"]
        or owner_character.get("account_id") != source["account_id"]
    ):
        raise ValueError("Companion criteria require its selected owner lease")
    pseudo = pseudo_character(entries, owner_character, level)
    pseudo["inventory_items"] = items
    baseline = native_npc_creation_values(source["ref"], level)
    context = criterion_context(owner_character, level, from_native_values(baseline))
    selected = validate_sheet(
        pseudo,
        bytes.fromhex(pseudo["builds"][0]["equipment"]),
        criterion_context=context,
        native_baseline={
            identity: row["current"] for identity, row in baseline.items()
        },
        ignore_ineligible=True,
        strict=False,
    )
    return pseudo, tuple(selected)


def _prepare_sources(
    fight,
    actor,
    source,
    authority,
    owner_character,
    runtime_factory,
    compiled,
    registry,
):
    from wakfu_server.combat_equipment_initialization import plan
    from wakfu_server.combat_owned_equipment import (
        compiled_with_sources,
        ordinary_turn_state_contract,
    )
    from wakfu_server.combat_equipment_operation_capability import validate_graph
    from wakfu_server.combat_equipment_dynamic_levels import OwnerLevelFacts

    pseudo, selected = _planner_character(
        actor.effective_level, source, owner_character
    )
    sources = plan(pseudo, ordinary_only=True, _selected_entries=selected)
    extended = compiled_with_sources(compiled, sources)
    capability = getattr(runtime_factory, "equipment_operation_capability", None)
    if not callable(capability):
        raise ValueError("Missing live native equipment capability provider")
    routes, provider = capability()
    facts = OwnerLevelFacts.capture(fight, actor.id, source["account_id"])
    accepted, deferred = [], []
    for current in sources:
        result = validate_graph(
            current,
            extended,
            registry,
            runtime_bindings=routes,
            criteria_capability=provider,
            owner_level_facts=facts,
        )
        reason = None
        if result.status == "supported":
            current = dict(current, _generic_operation_admission=True)
            if "native_owned_actor_level" in result.requires_context:
                current["_generic_owner_level_facts"] = facts.plain()
        elif result.status == "unsupported":
            reason = "generic operation capability rejected: " + "; ".join(
                result.reasons
            )
        else:
            reason = ordinary_turn_state_contract(current, extended, registry)
        if reason is None:
            accepted.append(current)
        else:
            deferred.append(
                dict(
                    uid=current["uid"],
                    source_reference=current["source_reference"],
                    attachment_field=None,
                    reason=reason,
                )
            )
    return dict(
        compiled=extended,
        sources=tuple(accepted),
        deferred=tuple(deferred),
        _npc_authority=dict(
            actor_type=authority.native_actor_type,
            account_id=authority.native_account_id,
            owner_character_id=authority.native_primary_character_id,
            is_ehp=authority.native_is_ehp,
        ),
    )


def pin_companion(
    fight, actor_id, owner_character, runtime_factory, compiled, registry
):
    """Create the common immutable pin for one authentic active bHE NPC."""
    from wakfu_server.combat_owned_equipment_pin import (
        _digest,
        _plain,
        execution_contract_sha256,
        preparation_for_actor,
    )
    from wakfu_server.combat_static_catalogs import ImmutableCatalog

    actor, source, authority = _npc_source(fight, actor_id, runtime_factory)
    if (
        fight.phase != "active"
        or actor.hp <= 0
        or type(source.get("account_id")) is not int
        or source["account_id"] <= 0
    ):
        raise ValueError("Companion equipment pins require its active NPC battle actor")
    pins = getattr(fight, "native_owned_equipment_sources", {})
    if not isinstance(pins, Mapping) or str(actor_id) in pins:
        raise ValueError("Companion equipment source is already pinned or malformed")
    initial = _prepare_sources(
        fight,
        actor,
        source,
        authority,
        owner_character,
        runtime_factory,
        compiled,
        registry,
    )
    payload = dict(
        version=1,
        actor_id=actor_id,
        owner_id=source["account_id"],
        sources=_plain(initial["sources"]),
        deferred=_plain(initial["deferred"]),
    )
    payload["execution_sha256"] = execution_contract_sha256(
        initial["sources"], initial["compiled"], registry
    )
    record = dict(payload, sha256=_digest(payload))
    preview = deepcopy(fight)
    preview.native_owned_equipment_sources = dict(pins)
    preview.native_owned_equipment_sources[str(actor_id)] = ImmutableCatalog(record)
    # preparation_for_actor composes every pinned source itself. Pass the
    # pre-companion catalog here; passing initial["compiled"] would compose
    # this companion's definitions twice and can collide with existing rows.
    return preview, preparation_for_actor(preview, actor_id, compiled)


def initialize_companion(fight, actor_id, preparation, runtime_factory, *, account_id):
    """Apply already-qualified companion roots through the shared dispatcher."""
    from wakfu_server.combat_owned_equipment import initialize_transaction
    from wakfu_server.combat_companions import registered_source

    actor = fight.actors.get(actor_id)
    source = getattr(fight, "native_companion_sources", {}).get(str(actor_id))
    if (
        actor is None
        or source is None
        or registered_source(fight, actor, source) is None
    ):
        raise ValueError(
            "Missing registered NPC source before equipment initialization"
        )
    return initialize_transaction(
        fight, actor_id, preparation, runtime_factory, owner_id=account_id
    )


def preflight_custody(owner_character, companion_record, entries, level):
    """Validate the complete passive graph with a real factory manifest only.

    The store transaction supplies the owned DB row, selected owner snapshot,
    level cap and proposed durable entries. This method never fabricates a
    Fight/Actor or invokes handlers; it uses the production factory's
    side-effect-free operation manifest. Every graph must be completely
    supported here. The active Ready path repeats validation against the real
    companion actor, owner-level facts and live dispatcher before application.
    """
    from wakfu_server.combat_companions import companion_projection
    from wakfu_server.combat_server_spell import server_runtime
    from wakfu_server.combat_static_catalogs import characteristic_registry
    from wakfu_server.combat_equipment_initialization import plan
    from wakfu_server.combat_owned_equipment import compiled_with_sources
    from wakfu_server.combat_equipment_operation_capability import validate_graph
    from wakfu_server.combat_equipment_dynamic_levels import CompanionCustodyLevelFacts
    from wakfu_server.spells import default_deck

    if (
        not isinstance(owner_character, Mapping)
        or not isinstance(companion_record, Mapping)
        or not isinstance(entries, (tuple, list))
        or type(level) is not int
        or not 0 <= level <= 32767
    ):
        raise ValueError("Missing durable NPC companion custody facts")
    source_record = dict(
        companion_record, level=level, equipment_entries=tuple(entries)
    )
    custody_level_facts = CompanionCustodyLevelFacts.capture(
        companion_record, owner_character, level
    )
    source = companion_projection(source_record, dict(owner_character))
    pseudo, selected = _planner_character(level, source, owner_character)
    sources = plan(pseudo, ordinary_only=True, _selected_entries=tuple(selected))
    if not sources:
        return dict(status="supported", sources=(), reasons=())

    index = owner_character.get("active_build_index", 0)
    builds = owner_character.get("builds", {})
    build = (
        builds.get(index, builds.get(str(index), {}))
        if isinstance(builds, Mapping)
        else {}
    )
    raw_deck = build.get("deck") if isinstance(build, Mapping) else None
    deck_blob = (
        bytes.fromhex(raw_deck)
        if isinstance(raw_deck, str) and raw_deck
        else default_deck(owner_character)
    )
    # This factory is a manifest/context provider only. The controlled actor
    # passed to server_runtime remains the real selected owner; putting the
    # NPC projection in player_characters would forge a player deck/identity.
    factory, _ = server_runtime(
        owner_character,
        {},
        deck_blob,
        action_id=1,
        critical=False,
    )
    routes, provider = factory.equipment_operation_capability()
    base_compiled = getattr(factory, "_compiled", None)
    if base_compiled is None:
        raise ValueError("Production runtime factory lacks compiled native catalog")
    compiled = compiled_with_sources(base_compiled, sources)
    registry = characteristic_registry()
    for current in sources:
        result = validate_graph(
            current,
            compiled,
            registry,
            runtime_bindings=routes,
            criteria_capability=provider,
            owner_level_facts=custody_level_facts,
        )
        if result.status != "supported":
            reasons = tuple(result.reasons) or (
                "complete native graph is not supported",
            )
            return dict(status=result.status, sources=tuple(sources), reasons=reasons)
    return dict(status="supported", sources=tuple(sources), reasons=())
