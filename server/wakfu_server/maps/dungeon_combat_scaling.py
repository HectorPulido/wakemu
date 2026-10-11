"""Explicit Wakemu dungeon scaling policy using native16/330/430 branches.

This selects original native effects by the frozen percentage profile. It does
not claim a native dungeon-kind to whole-state binding. Generic combat handlers
retain HP arithmetic and conditional triggering-value behavior.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
import json

POLICY = "wakemu-dungeon-native-curve-branches-v1"


@dataclass(frozen=True)
class InitializationPlan:
    snapshot_sha256: str
    profile: dict
    references: tuple
    actor_ids: tuple


def plan(fight, monsters, snapshot, catalog):
    if fight.phase != "placement" or type(fight.id) is not int or fight.id <= 0:
        raise ValueError("Dungeon scaling requires a durable unpublished placement")
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("Missing frozen dungeon scaling profile")
    if catalog.get("policy") != POLICY or catalog.get("schema_version") != 1:
        raise ValueError("Invalid dungeon scaling catalog")
    references = []
    for field, index in (("hp_percent", "hp"), ("damage_percent", "damage")):
        percent = snapshot.get(field)
        if type(percent) is not int or percent <= 0:
            raise ValueError("Invalid frozen dungeon scaling percentage")
        if percent == 100:
            continue
        selected = catalog[index].get(str(percent))
        if selected is None:
            raise ValueError("Native dungeon scaling percentage is unavailable")
        references.extend((selected,) if index == "hp" else selected)
    for reference in references:
        effect = catalog["effects"].get(str(reference))
        if effect is None or effect["effect_class"] not in (16, 330):
            raise ValueError("Dungeon scaling root is outside native policy")
    actor_ids = tuple(sorted(monsters))
    if not actor_ids:
        raise ValueError("Dungeon scaling requires authoritative monsters")
    for identity in actor_ids:
        actor = fight.actors.get(identity)
        if actor is None or identity >= 0 or actor.hp != actor.max_hp:
            raise ValueError("Dungeon scaling requires fresh owned NPC snapshots")
        if type(monsters[identity].get("ref")) is not int:
            raise ValueError("Dungeon scaling lacks native monster authority")
    digest = sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return InitializationPlan(digest, deepcopy(snapshot), tuple(references), actor_ids)


def _prepare_constructor(actor, reference):
    """Hydrate the same native property/death sources as ordinary NPC init."""
    from wakfu_server.combat_property_stack import add_property
    from wakfu_server.combat_native_death_status import (
        initialize_fresh_bje_death_status,
    )

    missing = [
        kind
        for kind in ("fight", "world")
        if getattr(actor, "native_" + kind + "_properties", None) is None
    ]
    if missing:
        from wakfu_server.combat_ordinary_authority import (
            native_property_catalog,
        )

        profile = native_property_catalog()["npc"][str(reference)]
        for kind in missing:
            counts = {}
            for prop in profile[kind + "_properties"]:
                add_property(counts, prop)
            setattr(actor, "native_" + kind + "_property_counts", counts)
            setattr(actor, "native_" + kind + "_properties", frozenset(counts))
    if not hasattr(actor, "native_death_status"):
        initialize_fresh_bje_death_status(actor)


def initialize(db, fight, monsters, *, catalog, runtime_factory):
    """Return an atomic private preview; root commits before publishing it.

    runtime_factory(preview, actor_id) returns a generic EffectDispatcher whose
    native effect/retention catalogs include this policy's exact native closure.
    No packets from detached construction are emitted: placement publishes the
    completed actor/effect snapshots. The durable encounter must already exist
    in the caller's transaction, with its selection revision verified at bind.
    """
    row = db.execute(
        "SELECT snapshot FROM dungeon_encounter_difficulties WHERE fight_id=%s",
        (fight.id,),
    ).fetchone()
    if row is None:
        return fight, None
    selected = plan(fight, monsters, row["snapshot"], catalog)
    previous = getattr(fight, "native_dungeon_scaling_receipt", None)
    receipt = dict(
        policy=POLICY,
        fight_id=fight.id,
        snapshot_sha256=selected.snapshot_sha256,
        profile=selected.profile,
        references=list(selected.references),
        actor_ids=list(selected.actor_ids),
        initialized=True,
    )
    if previous is not None:
        if previous != receipt:
            raise ValueError("Dungeon scaling replay changed its frozen authority")
        return fight, receipt
    if not callable(runtime_factory):
        raise ValueError("Dungeon scaling requires a generic native runtime")
    from wakfu_server.combat_effect_dispatch import EffectInvocation
    from wakfu_server.combat_summon_creation import native_fresh_summon_authority
    from wakfu_server.combat_summon_initialization import detached_summon_scope

    preview = deepcopy(fight)
    order = tuple(preview.actors)
    for identity in selected.actor_ids:
        actor = preview.actors[identity]
        team = actor.team
        _prepare_constructor(actor, monsters[identity]["ref"])
        authority = replace(
            native_fresh_summon_authority(actor, monsters[identity]["ref"]),
            is_summon=False,
            summon_root_id=actor.id,
            targeting=dict(
                native_fresh_summon_authority(
                    actor, monsters[identity]["ref"]
                ).targeting,
                bEe=42 not in actor.native_fight_properties,
                UNTARGETTABLE_BY_OTHER=21 in actor.native_fight_properties,
            ),
        )
        del preview.actors[identity]
        actor.team = -1
        try:
            with detached_summon_scope(preview, actor, authority):
                dispatcher = runtime_factory(preview, identity)
                with preview.effect_resolution():
                    for reference in selected.references:
                        if not dispatcher.execute(
                            EffectInvocation(
                                reference,
                                selected.profile["stasis_level"],
                                identity,
                                identity,
                                actor.position,
                                native_retained_container={"present": False},
                            )
                        ):
                            raise ValueError(
                                "Native dungeon scaling branch was not installed"
                            )
        finally:
            actor.team = team
            preview.actors[identity] = actor
            preview.actors = {key: preview.actors[key] for key in order}
    preview.native_dungeon_scaling_receipt = receipt
    return preview, receipt


def validates_constructor_receipt(fight, actor_id, *, catalog=None):
    """Prove scaling constructor ownership without requiring pre-effect HP.

    Catalog access uses the process-cached native supplement already consumed
    by runtime construction, never an actor-specific database lookup.
    """
    receipt = getattr(fight, "native_dungeon_scaling_receipt", None)
    if receipt is None:
        return False
    if not isinstance(receipt, dict) or not isinstance(receipt.get("actor_ids"), list):
        raise ValueError("Invalid native scaling constructor receipt")
    if actor_id not in receipt["actor_ids"]:
        return False
    if catalog is None:
        from .dungeon_scaling_catalog import current

        catalog = current()
    if (
        not isinstance(catalog, dict)
        or catalog.get("policy") != POLICY
        or catalog.get("schema_version") != 1
    ):
        raise ValueError("Missing native scaling constructor catalog")
    if (
        not isinstance(receipt, dict)
        or receipt.get("policy") != POLICY
        or type(receipt.get("fight_id")) is not int
        or receipt.get("fight_id") != fight.id
        or receipt.get("initialized") is not True
    ):
        raise ValueError("Invalid native scaling constructor receipt")
    profile = receipt.get("profile")
    identities = receipt.get("actor_ids")
    if (
        type(profile) is not dict
        or type(profile.get("stasis_level")) is not int
        or not 1 <= profile["stasis_level"] <= 10
    ):
        raise ValueError("Invalid native scaling constructor Stasis level")
    if (
        not isinstance(profile, dict)
        or profile.get("schema_version") != 1
        or not isinstance(identities, list)
        or not identities
        or any(
            type(identity) is not int
            or identity >= 0
            or identity not in fight.actors
            or fight.actors[identity].controlled
            for identity in identities
        )
        or identities != sorted(set(identities))
    ):
        raise ValueError("Invalid native scaling constructor ownership")
    digest = sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if receipt.get("snapshot_sha256") != digest:
        raise ValueError("Native scaling constructor profile changed")
    references = []
    for field, kind in (("hp_percent", "hp"), ("damage_percent", "damage")):
        percent = profile.get(field)
        if type(percent) is not int or percent <= 0:
            raise ValueError("Invalid native scaling constructor percentage")
        if percent == 100:
            continue
        selected = catalog.get(kind, {}).get(str(percent))
        if selected is None:
            raise ValueError("Unverified native scaling constructor curve")
        references.extend((selected,) if kind == "hp" else selected)
    if receipt.get("references") != references:
        raise ValueError("Native scaling constructor references changed")
    effects = catalog.get("effects", {})
    pending, visited = list(references), set()
    while pending:
        reference = pending.pop()
        if type(reference) is not int or reference <= 0:
            raise ValueError("Invalid native scaling constructor effect")
        if reference in visited:
            continue
        visited.add(reference)
        row = effects.get(str(reference))
        if not isinstance(row, dict) or row.get("effect_class") not in (16, 330, 430):
            raise ValueError("Unverified native scaling constructor closure")
        if reference in references and row["effect_class"] not in (16, 330):
            raise ValueError("Invalid native scaling constructor root")
        pending.extend(row.get("children", ()))
    return True
