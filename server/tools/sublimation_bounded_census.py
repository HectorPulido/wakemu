"""Bounded attachment graph census through the real configured native factory.

This qualification tool uses a source-pinned complete attachment closure and
small published metadata projections. It never imports the whole game catalog,
opens a database, changes an eligibility policy, or claims semantic execution.
The native capability provider and its production callbacks are not replaced.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


class BoundedDataset:
    def __init__(self, path):
        self.manifest_path = Path(path).resolve()
        self.manifest = json.loads(self.manifest_path.read_bytes())
        self.loaded_documents = {}
        self.published_metadata = None
        self.published_metadata_bytes = 0
        self.closure = self.read(self.manifest["closure"])
        self.states = self.read(self.manifest["state_catalog"])
        self.parent = self.read(self.manifest["parent_definition"])
        revision = self.manifest.get("revision")
        if (
            not isinstance(revision, str)
            or len(revision) != 64
            or any(c not in "0123456789abcdef" for c in revision)
            or self.closure.get("revision") != revision
        ):
            raise ValueError("Bounded closure release identity differs from manifest")
        actual = dict(
            scrolls=len(self.closure["source_definitions"]),
            effects=len(self.closure["effects"]),
            states=len(self.closure["states"]),
            registry=len(self.closure["registry"]),
        )
        expected = {key: self.manifest["counts"][key] for key in actual}
        if actual != expected or self.states["states"] != self.closure["states"]:
            raise ValueError("Bounded dataset counts or state projection differ")
        if self.states["effects"] != self.closure["effects"]:
            raise ValueError("Bounded state effect projection is incomplete")
        if (
            self.closure.get("missing_effects")
            or self.closure.get("missing_states")
            or self.closure.get("unresolved_dynamic_state_references")
        ):
            raise ValueError("Unresolved attachment closure cannot qualify")
        pack = self.manifest.get("published_metadata_pack")
        if pack is not None:
            from tools.sublimation_published_metadata import PublishedMetadataPack

            path = Path(pack["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.published_metadata = PublishedMetadataPack(
                path,
                revision=revision,
                manifest_sha256=pack["sha256"],
            )

    def read(self, entry):
        path = Path(entry["path"])
        if not path.is_absolute():
            path = ROOT / path
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Bounded input checksum mismatch: " + str(path))
        return json.loads(raw)

    def install_catalog_backend(self):
        from wakfu_server import native_catalog

        # Preserve native_catalog's public parser and path semantics. Only its
        # byte backend is replaced by verified projections and, optionally,
        # original small documents from one hash-pinned published inventory.
        # There is no live database or arbitrary workstation file source.
        def read_published(name):
            entry = self.manifest["documents"].get(name)
            if entry is None:
                if self.published_metadata is None:
                    raise ValueError("Unlisted bounded catalog dependency: " + name)
                raw = self.published_metadata.read(name)
                if name not in self.loaded_documents:
                    self.published_metadata_bytes += len(raw)
                    if self.published_metadata_bytes > 16 * 1024 * 1024:
                        raise ValueError(
                            "Published metadata exceeds cumulative bounded budget"
                        )
                self.loaded_documents[name] = self.published_metadata.read_documents[
                    name
                ]["sha256"]
                return raw
            path = Path(entry["path"])
            if not path.is_absolute():
                path = ROOT / path
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ValueError("Bounded document checksum mismatch: " + name)
            self.loaded_documents[name] = entry["sha256"]
            return raw

        # The published revision is itself pinned by the read-only dataset
        # receipt. Resolving that fixture identity must not query a live DB.
        native_catalog.release = lambda: self.manifest["revision"]
        native_catalog._read_published = read_published
        indexed_entry = self.manifest.get("indexed_records")
        if indexed_entry is not None:
            from copy import deepcopy

            indexed = self.read(indexed_entry)
            inventory_entry = self.manifest.get("semantic", {}).get(
                "published_document_inventory"
            )
            if not isinstance(inventory_entry, dict):
                raise ValueError("Indexed projection requires its published inventory")
            inventory = self.read(inventory_entry)
            if (
                indexed.get("revision") != self.manifest["revision"]
                or not isinstance(indexed.get("records"), dict)
                or not isinstance(indexed.get("source_document_sha256"), dict)
            ):
                raise ValueError("Invalid original indexed source projection")
            hashes = {name: row["sha256"] for name, row in inventory.items()}
            for name, digest in indexed["source_document_sha256"].items():
                if hashes.get(name) != digest or name not in indexed["records"]:
                    raise ValueError(
                        "Indexed record differs from published source inventory"
                    )

            def record(path, collection, record_key):
                name = native_catalog._key(path)
                rows = indexed["records"].get(name, {}).get(collection)
                if not isinstance(rows, dict) or str(record_key) not in rows:
                    raise ValueError(
                        "Unlisted bounded indexed dependency: "
                        + str((name, collection, record_key))
                    )
                return deepcopy(rows[str(record_key)])

            native_catalog.record = record
            native_catalog.document_hashes = lambda: dict(hashes)
            native_catalog._exists = lambda revision, name: (
                revision == self.manifest["revision"] and name in inventory
            )


def construct_factory(dataset, *, actor_level=100):
    """Use production classes/callbacks over the exact bounded source closure.

    This creates a declared graph-assessment fixture, not a paid battle or a
    Store ownership receipt. Dynamic runtime values remain guarded by the real
    providers; none is sampled while validating the source graph.
    """
    dataset.install_catalog_backend()
    from wakfu_server.combat_static_catalogs import CompiledEffects
    from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
    from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
    from wakfu_server.combat_ordinary_authority import (
        OrdinaryActorAuthority,
        ordinary_cast_authority,
    )
    from wakfu_server.combat_summon import RegisteredSummonAuthority
    from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
    from wakfu_server.combat_relative_probability import RelativeGroupAuthority
    from wakfu_server.combat_random_group import RandomGroupAuthority
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_equipment_dynamic_levels import OwnerLevelFacts

    effects, states = dataset.closure["effects"], dataset.states
    if dataset.manifest.get("producer_effects") is not None:
        from wakfu_server.combat_effect_runtime import _merge_effects

        supplemental = dataset.read(dataset.manifest["producer_effects"])
        effects = _merge_effects(effects, supplemental)
        states = dict(states, effects=_merge_effects(states["effects"], supplemental))
    compiled = CompiledEffects(effects, states)
    registry = dict(effects=dataset.closure["registry"])
    character = dict(
        id=7,
        account_id=3,
        breed=1,
        level=actor_level,
        real_level=actor_level,
        sex=False,
        inventory_items=[],
        builds={},
    )
    actors = RegisteredSummonAuthority(
        OrdinaryActorAuthority(
            characters={7: character},
            monsters={},
            decks={7: frozenset()},
            excluded_decks={7: frozenset()},
            deck_caps={7: None},
        )
    )
    rng = random.Random(700031)
    cast = ordinary_cast_authority(
        actors=actors,
        timing=NativeEffectTimingProvider(dataset.states),
        rng=rng,
        critical=False,
    )
    adapter = NativeServerRuntimeAdapter(actor_authority=actors, cast=cast, viewer_id=7)
    factory = NativeEffectRuntimeFactory(
        effects=compiled.source_effects,
        state_catalog=compiled.source_states,
        compiled_effects=compiled,
        characteristic_registry=registry,
        action_id=1,
        contexts=adapter.contexts(),
        displacement_authority=actors,
        summon_authority=actors,
        transaction_rng=rng,
    )
    factory.native_rail_movement_authority = actors
    factory.relative_group_children = RelativeGroupAuthority(
        effects=factory.effects,
        actor_authority=actors,
        condition_context=adapter.condition,
        draw_integer=lambda total: rng.randint(1, total),
        draw_fraction=lambda fraction: rng.random() < fraction,
    )
    factory.random_group_children = RandomGroupAuthority(
        effects=factory.effects,
        condition_context=adapter.condition,
        draw_integer=lambda total: rng.randrange(total),
    )
    from wakfu_server.combat_equipment_external_contracts import (
        bind_owned_equipment_producers,
    )

    bind_owned_equipment_producers(factory)
    player = Actor(
        7, 0, (0, 0, 0), 100, 6, 3, 20, actor_level, owner_id=3, controlled=True
    )
    enemy = Actor(-200, 1, (1, 0, 0), 100, 6, 3, 10, actor_level)
    fight = Fight(
        1, (player, enemy), {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
    )
    fight.phase = "active"
    facts = OwnerLevelFacts.capture(fight, 7, 3)
    return factory, compiled, registry, facts, fight, character


def census(dataset, factory, compiled, registry, facts):
    from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan, SOURCE
    from wakfu_server.combat_equipment_operation_capability import validate_graph
    from wakfu_server.combat_owned_equipment import immediate_scalar_contract

    definitions = dict(dataset.closure["source_definitions"])
    parent_reference = dataset.parent["reference"]
    definitions[str(parent_reference)] = dataset.parent
    native = dict(
        producer=SOURCE,
        complete=True,
        definition_count=len(definitions),
        definitions=definitions,
    )
    parent = copied_equipment_plan(parent_reference, native)[
        "native_retained_container"
    ]
    routes, provider = factory.equipment_operation_capability()
    rows = []
    for item in dataset.manifest["scrolls"]:
        definition = definitions[str(item["reference"])]
        roots = tuple(
            row["reference"]
            for row in definition["ordered_effects"]
            if row["variant"] == 0 and row["metadata"]["native_active_effect"] is False
        )
        if not roots:
            raise ValueError(
                "Native scroll lacks a complete passive root: " + str(item["reference"])
            )
        source = dict(
            uid=500,
            reference=parent_reference,
            source_reference=item["reference"],
            attachment_field=24 if item["kind"] == "BASIC" else 32,
            roots=roots,
            unplanned_passive_effect_ids=(),
            native_retained_container=parent,
            effects={str(ref): dataset.closure["effects"][str(ref)] for ref in roots},
        )
        observations = []

        def observe(**arguments):
            value = provider(**arguments)
            if value is not True:
                effect = arguments.get("effect", {})
                observations.append(
                    dict(
                        kind=arguments.get("kind"),
                        family=effect.get("effect_class"),
                        level=arguments.get("level"),
                        context=list(arguments.get("requires_context", ())),
                        masks=[list(m or ()) for m in effect.get("target_masks", ())],
                        criterion=effect.get("criteria"),
                        verdict=value,
                    )
                )
            return value

        decision = validate_graph(
            source,
            compiled,
            registry,
            runtime_bindings=routes,
            criteria_capability=observe,
            owner_level_facts=facts,
        )
        scalar_reason = immediate_scalar_contract(source, compiled, registry)
        accepted = (
            decision.status == "supported"
            or decision.status == "unknown"
            and scalar_reason is None
        )
        rows.append(
            dict(
                item,
                status="admitted" if accepted else "deferred",
                generic_status=decision.status,
                reasons=list(decision.reasons),
                boundary_family=decision.family,
                boundary_level=decision.level,
                boundary_operation=decision.operation_id,
                legacy_scalar_reason=scalar_reason,
                capability_observations=observations,
                required_context=list(decision.requires_context),
                roots=list(roots),
            )
        )
    return dict(
        schema=1,
        scope="Complete source graph admission at one declared parent/actor level; not semantic execution or installation authority",
        parent_container=parent,
        actor_level=facts.effective_level,
        total=len(rows),
        counts=dict(Counter(r["status"] for r in rows)),
        generic_counts=dict(Counter(r["generic_status"] for r in rows)),
        deferred_reasons=dict(
            Counter(
                reason
                for r in rows
                if r["status"] == "deferred"
                for reason in r["reasons"]
            )
        ),
        loaded_documents=dataset.loaded_documents,
        rows=rows,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-limit-mib", type=int, default=1280)
    args = parser.parse_args()
    if not 256 <= args.memory_limit_mib <= 1536:
        parser.error("Qualification address-space limit must be256..1536MiB")
    limit_kind = (
        resource.RLIMIT_DATA if sys.platform == "darwin" else resource.RLIMIT_AS
    )
    resource.setrlimit(limit_kind, (args.memory_limit_mib * 1024 * 1024,) * 2)
    sys.path.insert(0, str(ROOT / "server"))
    started = time.monotonic()
    dataset = BoundedDataset(args.manifest)
    factory, compiled, registry, facts, _fight, _character = construct_factory(dataset)
    result = census(dataset, factory, compiled, registry, facts)
    result.update(
        manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        seconds=time.monotonic() - started,
        maximum_rss_kib=(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            // (1024 if sys.platform == "darwin" else 1)
        ),
        memory_limit_kind="DATA" if sys.platform == "darwin" else "AS",
        memory_limit_mib=args.memory_limit_mib,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "total",
                    "counts",
                    "generic_counts",
                    "deferred_reasons",
                    "seconds",
                    "maximum_rss_kib",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
