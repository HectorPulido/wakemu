#!/usr/bin/env python3
"""Compile structural attack dependencies using the shared operation registry.

This offline compiler never admits actors, changes native definitions, grants
resources, or treats handler registration as behavioral/client proof.
"""
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import asdict, dataclass
import hashlib
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wakfu_server.combat_operation_registry import (
    dependency_specs,
    operation_for_family,
    RETAINED_EXECUTION,
    assess_operation,
)
from wakfu_server import combat_operation_registry as operation_registry
from wakfu_server import combat_subscription_contracts as subscription_contracts
from wakfu_server import combat_damage_contracts as damage_contracts
from wakfu_server.combat_local_criteria import (
    parse_local_criterion,
    LocalCriterionSyntax,
)
from wakfu_server import combat_local_criteria as local_criteria


SCHEMA = "wakemu-operation-catalog-v1"
KINDS = {"spell", "state", "area", "summon", "morph", "effect"}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _source_identity(module):
    path = Path(module.__file__).resolve()
    return {
        "path": str(path.relative_to(Path(__file__).resolve().parents[2])),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _retained_capability(effect, reference, metadata):
    """Conservative applicability from exported masks and native timing fields.

    Mode0 is retained by native_definition_timing. A nonzero curve identifies
    a potentially retained variant, not retention at every level. Missing
    metadata/queue/container facts remain explicit. No runtime object is built.
    """
    reasons = []
    required = False
    family = effect.get("effect_class", effect.get("family"))
    masks = effect.get("target_masks")
    subscription = None
    if family in subscription_contracts.SUBSCRIPTION_FAMILIES:
        if (
            isinstance(masks, (list, tuple))
            and len(masks) == 7
            and all(
                value is None
                or (
                    isinstance(value, (list, tuple))
                    and all(type(member) is int for member in value)
                )
                for value in masks
            )
        ):
            subscription = any(masks[index] for index in (0, 1, 3, 4, 5))
            required |= subscription
        else:
            reasons.append("unknown-subscription-masks")
    else:
        subscription = False
    mode = effect.get("native_execution_mode")
    fields = effect.get("native_timing_definition")
    if mode == 0:
        required = True
    elif mode in (1, 2) and isinstance(fields, Mapping):
        names = ("ryE", "ryF") if mode == 2 else ("rzv", "rzw")
        if all(
            isinstance(fields.get(name), (int, float))
            and not isinstance(fields[name], bool)
            for name in names
        ):
            if any(fields[name] != 0 for name in names):
                required = True
                reasons.append("duration-requires-actual-level-and-timer-context")
        else:
            reasons.append("unknown-duration-fields")
        if mode == 2 and (fields.get("ryH") != 0 or fields.get("ryI") != 0):
            reasons.append("delayed-queue-registration-scope-unresolved")
    else:
        reasons.append("unknown-native-duration-mode")
    row = (metadata or {}).get("effects", {}).get(str(reference))
    if required:
        if row is None:
            reasons.append("missing-published-retained-definition-metadata")
        else:
            for name in (
                "effect_class",
                "variant",
                "minimum_level",
                "maximum_level",
                "parameters",
            ):
                if name not in effect or name not in row or row[name] != effect[name]:
                    reasons.append("retained-metadata-identity-mismatch:" + name)
            if row.get("definition_type") != mode:
                reasons.append("retained-metadata-mode-mismatch")
            if subscription is not None and row.get("subscription") is not subscription:
                reasons.append("retained-metadata-subscription-mismatch")
    if any("mismatch" in reason for reason in reasons):
        status = "unsupported"
    elif any(reason.startswith(("unknown-", "missing-")) for reason in reasons):
        status = "unknown"
    else:
        status = "conditional" if required else "unknown" if reasons else "not-required"
    return {
        "status": status,
        "required": required,
        "subscription": subscription,
        "reasons": sorted(set(reasons)),
    }


def _identity(value):
    if isinstance(value, str) and value.isdecimal():
        value = int(value)
    if type(value) is not int or value <= 0:
        raise ValueError("Positive native reference required")
    return value


def _roots(row):
    """Read exported roots without inventing unevaluated native levels."""
    if isinstance(row, (list, tuple)):
        return tuple(_identity(value) for value in row)
    if not isinstance(row, Mapping):
        raise ValueError("Malformed native definition")
    result = list(row.get("effect_ids", ()))
    result.extend(row.get("level_zero_roots", ()))
    for level in row.get("levels", ()):
        if isinstance(level, Mapping):
            result.extend(level.get("effects", ()))
        elif isinstance(level, (list, tuple)) and len(level) == 3:
            result.extend(level[2])
        else:
            raise ValueError("Malformed native level roots")
    return tuple(sorted({_identity(value) for value in result}))


def reference_values(effect, spec, *, extra=None):
    """Return evaluated references and unresolved-reference diagnostics.

    Raw parameter pairs are curves, not evaluated values. They are accepted
    only when their slope is explicitly zero. Dynamic references stay unknown.
    """
    fixed = getattr(spec, "fixed_reference", None)
    if fixed is not None:
        return (fixed,), ()
    index = spec.parameter_index
    samples = list(effect.get("parameters_by_level", ()))
    samples.extend(effect.get("parameter_samples", ()))
    samples.extend(effect.get("parameter_samples_by_level", {}).values())
    if extra is not None:
        samples.append(extra.get("parameters", ()))
    values = []
    unknown = []
    if samples:
        for sample in samples:
            if not isinstance(sample, (list, tuple)) or len(sample) <= index:
                unknown.append("missing-evaluated-reference-slot")
            elif type(sample[index]) is not int:
                unknown.append("noninteger-evaluated-reference")
            else:
                values.append(sample[index])
    elif "references" in effect:
        values.extend(effect["references"])
    elif index == 0 and effect.get("parameter0_by_level") is not None:
        values.extend(effect["parameter0_by_level"])
    else:
        raw = effect.get("parameters")
        offset = 2 * index
        if isinstance(raw, (list, tuple)) and len(raw) > offset + 1:
            base, slope = raw[offset : offset + 2]
            if slope != 0:
                unknown.append("dynamic-reference-needs-evaluated-levels")
            elif (
                isinstance(base, (int, float))
                and not isinstance(base, bool)
                and int(base) == base
            ):
                values.append(int(base))
            else:
                unknown.append("noninteger-constant-reference")
        else:
            unknown.append("missing-reference-parameters")
    transform = getattr(spec, "transform", "identity")
    result = []
    for value in values:
        if type(value) is not int:
            unknown.append("noninteger-evaluated-reference")
            continue
        if (
            transform in ("signed-short", "signed_short")
            or effect.get("effect_class", effect.get("family")) == 307
        ):
            value = ((value + 32768) % 65536) - 32768
        if value <= 0:
            unknown.append("nonpositive-reference:" + str(value))
        else:
            result.append(value)
    return tuple(sorted(set(result))), tuple(sorted(set(unknown)))


def normalize_tables(tables):
    """Normalize collection names only; preserve all original definition rows."""
    if not isinstance(tables, Mapping):
        raise ValueError("Catalog tables required")
    aliases = {
        "summon": ("summons", "profiles", "monsters"),
        "morph": ("morphs", "morph_profiles"),
    }
    result = {}
    for kind in KINDS:
        names = aliases.get(kind, (kind + "s",))
        collection = next((tables[name] for name in names if name in tables), {})
        if not isinstance(collection, Mapping):
            raise ValueError("Catalog collection must be a mapping: " + kind)
        result[kind] = {str(_identity(key)): value for key, value in collection.items()}
    return result


@dataclass(frozen=True)
class CompiledAttackPlan:
    """Immutable serialized plan; decoded reports are independent copies."""

    serialized: str

    def report(self):
        return json.loads(self.serialized)


def compile_catalog(
    tables,
    seeds,
    *,
    zero_effects=None,
    characteristic_registry=None,
    set_current_families=(),
    set_current_registry=None,
    runtime_bindings=None,
    retained_metadata=None
):
    """Compile reference paths and honest support axes for supplied actions.

    All branches are structural dependencies. A conditional/unsupported child
    is reported without rejecting a runtime-ineligible branch or changing its
    guard. State removal references are validated but not executed recursively.
    """
    tables = normalize_tables(tables)
    seeds = tuple(sorted({(kind, _identity(identity)) for kind, identity in seeds}))
    if any(kind not in KINDS for kind, _ in seeds):
        raise ValueError("Unknown catalog seed kind")
    pending = deque(
        (kind, identity, (kind + ":" + str(identity),), "requires")
        for kind, identity in seeds
    )
    seen = set()
    nodes, edges, issues = {}, {}, {}
    families = defaultdict(set)
    while pending:
        kind, identity, path, relation = pending.popleft()
        key = kind + ":" + str(identity)
        row = tables[kind].get(str(identity))
        if row is None:
            issue = {
                "status": "unsupported",
                "reason": "missing-native-definition",
                "path": list(path),
            }
            issues[(key, tuple(path), issue["reason"])] = issue
            continue
        nodes.setdefault(key, {"kind": kind, "reference": identity})
        # A removed state is a reference obligation, not an execution producer.
        if relation == "removes":
            continue
        if key in seen:
            continue
        seen.add(key)

        def link(target_kind, target, reason="requires"):
            target = _identity(target)
            destination = target_kind + ":" + str(target)
            edge = {
                "source": key,
                "target": destination,
                "relation": reason,
                "path": list((*path, destination)),
            }
            edges[(key, destination, reason)] = edge
            pending.append((target_kind, target, (*path, destination), reason))

        if kind in ("summon", "morph"):
            abilities = row.get("native_abilities", row.get("abilities", ()))
            for ability in abilities:
                link("spell", ability.get("spell_id", ability.get("reference")))
            # Morph933 switches the book; it does not initialize NPC states.
            triples = row.get("initial_state_triples", ()) if kind == "summon" else ()
            if len(triples) % 3:
                raise ValueError("Malformed native summon initial states")
            for state in triples[::3]:
                link("state", state)
            continue
        if kind != "effect":
            for child in _roots(row):
                link("effect", child)
            continue
        if not isinstance(row, Mapping):
            raise ValueError("Expanded native effect rows required")
        family = row.get("effect_class", row.get("family"))
        if type(family) is not int:
            raise ValueError("Native effect family required")
        families[family].add(identity)
        operation = operation_for_family(
            family,
            characteristic_registry=characteristic_registry,
            set_current_families=set_current_families,
        )
        node = nodes[key]
        node["family"] = family
        node["operation_id"] = getattr(
            operation, "id", getattr(operation, "operation_id", None)
        )
        # An executor descriptor alone proves availability, not combinations or
        # client lifecycle. Qualification receipts must be joined separately.
        assessment = assess_operation(
            row,
            characteristic_registry=characteristic_registry,
            set_current_registry=set_current_registry,
            runtime_bindings=runtime_bindings,
        )
        node["operation_support"] = assessment.status
        node["operation_support_reasons"] = list(assessment.reasons)
        node["combination_verification"] = "unknown"
        node["modeled_client_compatibility"] = "unknown"
        node["prerequisites"] = (
            list(getattr(operation, "prerequisites", ())) if operation else []
        )
        node["execution_requirements"] = {
            "prerequisites": list(assessment.prerequisites),
            "mutations": list(operation.mutations) if operation else [],
            "events": list(operation.events) if operation else [],
            "variants": list(operation.variants) if operation else [],
            "variant_validation": list(getattr(operation, "variant_validation", ()))
            if operation
            else [],
        }
        node["presentation_requirements"] = (
            list(getattr(operation, "presentation", ())) if operation else []
        )
        node["contract_tests"] = (
            list(getattr(operation, "tests", ())) if operation else []
        )
        lifecycle = _retained_capability(row, identity, retained_metadata)
        node["retained_execution"] = lifecycle
        capabilities = [operation] if operation is not None else []
        if lifecycle["required"]:
            capabilities.append(RETAINED_EXECUTION)
        node["operation_ids"] = [contract.operation_id for contract in capabilities]
        node["operation_contracts"] = {
            contract.operation_id: {
                "contract_sha256": _digest(asdict(contract)),
                **asdict(contract),
            }
            for contract in capabilities
        }
        node["contract_sha256"] = _digest(asdict(operation)) if operation else None
        criterion = row.get("criteria")
        if criterion is None:
            node["criterion_syntax"] = {
                "status": "unknown",
                "reason": "criterion-source-unavailable",
            }
        elif not isinstance(criterion, str):
            node["criterion_syntax"] = {
                "status": "unsupported",
                "reason": "criterion-must-be-text",
            }
        elif not criterion.strip():
            node["criterion_syntax"] = {
                "status": "supported",
                "reason": "explicit-empty-criterion",
            }
        else:
            try:
                parse_local_criterion(criterion)
            except (LocalCriterionSyntax, SyntaxError, ValueError) as error:
                node["criterion_syntax"] = {
                    "status": "unsupported",
                    "reason": "malformed-native-criterion",
                    "detail": str(error),
                }
            else:
                node["criterion_syntax"] = {
                    "status": "supported",
                    "reason": "parsed-by-runtime-native-syntax-parser",
                }
        node["criterion_evaluation"] = {
            "status": "unknown",
            "reason": "predicate-support-and-dynamic-context-not-proven-by-parsing",
        }
        for reason in assessment.reasons:
            if assessment.status in ("unknown", "unsupported"):
                issues[(key, tuple(path), reason)] = {
                    "status": assessment.status,
                    "reason": reason,
                    "family": family,
                    "path": list(path),
                }
        if node["criterion_syntax"]["status"] != "supported":
            reason = node["criterion_syntax"]["reason"]
            issues[(key, tuple(path), reason)] = {
                "status": node["criterion_syntax"]["status"],
                "reason": reason,
                "path": list(path),
            }
        for reason in lifecycle["reasons"]:
            status = "unsupported" if "mismatch" in reason else "unknown"
            issues[(key, tuple(path), reason)] = {
                "status": status,
                "reason": reason,
                "path": list(path),
            }
        if operation is None:
            issues[(key, tuple(path), "missing-shared-operation")] = {
                "status": "unknown",
                "reason": "missing-shared-operation",
                "family": family,
                "path": list(path),
            }
        for child in row.get("children", ()):
            link("effect", child)
        for spec in dependency_specs(family):
            references, unknowns = reference_values(
                row, spec, extra=(zero_effects or {}).get(str(identity))
            )
            for reference in references:
                link(spec.kind, reference, getattr(spec, "relation", "requires"))
            for reason in unknowns:
                issues[(key, tuple(path), reason)] = {
                    "status": "unknown",
                    "reason": reason,
                    "dependency_kind": spec.kind,
                    "path": list(path),
                }
    reverse = defaultdict(set)
    for edge in edges.values():
        reverse[edge["target"]].add(edge["source"])
    seed_keys = {kind + ":" + str(identity) for kind, identity in seeds}

    def consumers(keys):
        reached, queue = set(keys), deque(keys)
        while queue:
            for owner in reverse[queue.popleft()]:
                if owner not in reached:
                    reached.add(owner)
                    queue.append(owner)
        return sorted(reached & seed_keys)

    for issue in issues.values():
        issue["affected_consumers"] = consumers((issue["path"][-1],))
    source_identities = [
        _source_identity(module)
        for module in (
            operation_registry,
            subscription_contracts,
            damage_contracts,
            local_criteria,
        )
    ]
    source_identities.append(
        {
            "path": str(
                Path(__file__)
                .resolve()
                .relative_to(Path(__file__).resolve().parents[2])
            ),
            "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    )
    report = {
        "schema": SCHEMA,
        "registry_source": _source_identity(operation_registry),
        "registry_sources": {
            entry["path"]: entry["sha256"] for entry in source_identities
        },
        "seeds": [{"kind": kind, "reference": identity} for kind, identity in seeds],
        "nodes": dict(sorted(nodes.items())),
        "edges": sorted(
            edges.values(),
            key=lambda row: (row["source"], row["target"], row["relation"]),
        ),
        "issues": sorted(issues.values(), key=lambda row: (row["path"], row["reason"])),
        "family_dependents": {
            str(family): sorted(refs) for family, refs in sorted(families.items())
        },
        "family_consumers": {
            str(family): consumers(tuple("effect:" + str(ref) for ref in refs))
            for family, refs in sorted(families.items())
        },
        "combination_verification": "unknown",
        "modeled_client_compatibility": "unknown",
        "limitations": [
            "Structural closure includes guarded branches; runtime eligibility is authoritative.",
            "Registry availability is not behavioral or presentation accreditation.",
            "No native resources, ownership, conditions or activation policy are changed.",
        ],
    }
    return CompiledAttackPlan(json.dumps(report, sort_keys=True, separators=(",", ":")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables", required=True)
    parser.add_argument("--seed", action="append", required=True, help="kind:reference")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    seeds = [
        (kind, int(identity))
        for kind, identity in (value.split(":", 1) for value in args.seed)
    ]
    with open(args.tables, encoding="utf-8") as stream:
        plan = compile_catalog(json.load(stream), seeds)
    with open(args.output, "x", encoding="utf-8") as stream:
        json.dump(plan.report(), stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
