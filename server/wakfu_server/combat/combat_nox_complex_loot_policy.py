"""Database-owned reconstructed eligibility over exact native Nox loot rows.

Original complex expressions are unrecovered. The immutable policy version in
PostgreSQL declares the reviewed guide/package mismatch and exact whitelist.
No runtime file supplies rules; native rows still supply chances and quantities.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from .combat_boss_score_policy import NOX_SCORE


@dataclass(frozen=True)
class NoxComplexLootPolicy:
    version: str
    monster_reference: int
    encounter_controller: str
    minimum_score: int
    catalog_revision: str
    native_rows_sha256: str
    expected_item_count: int
    item_references: tuple[int, ...]


def load_policy(db, *, version=None):
    """Read either the active reviewed policy or an immutable receipt version."""
    if version is None:
        row = db.execute(
            "SELECT v.* FROM combat_complex_loot_policy_active a "
            "JOIN combat_complex_loot_policy_versions v ON v.version=a.version "
            "AND v.monster_reference=a.monster_reference WHERE a.monster_reference=%s "
            "FOR SHARE OF a,v",
            (NOX_SCORE.reference,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT * FROM combat_complex_loot_policy_versions WHERE version=%s FOR SHARE",
            (version,),
        ).fetchone()
    if row is None:
        return None
    references = tuple(
        r["item_reference"]
        for r in db.execute(
            "SELECT item_reference FROM combat_complex_loot_policy_items WHERE version=%s ORDER BY item_reference",
            (row["version"],),
        ).fetchall()
    )
    if (
        row["monster_reference"] != NOX_SCORE.reference
        or row["encounter_controller"] != NOX_SCORE.name
        or type(row["minimum_score"]) is not int
        or row["minimum_score"] < NOX_SCORE.minimum_score
        or len(references) != row["expected_item_count"]
    ):
        raise ValueError("Complex loot database policy lost its reviewed scope")
    return NoxComplexLootPolicy(
        row["version"],
        row["monster_reference"],
        row["encounter_controller"],
        row["minimum_score"],
        row["catalog_revision"],
        row["native_rows_sha256"],
        row["expected_item_count"],
        references,
    )


def permission(policy):
    return dict(
        policy=policy.version,
        monster_reference=policy.monster_reference,
        encounter_controller=policy.encounter_controller,
        minimum_score=policy.minimum_score,
        catalog_revision=policy.catalog_revision,
        native_rows_sha256=policy.native_rows_sha256,
        expected_item_count=policy.expected_item_count,
        item_references=list(policy.item_references),
    )


def validate_native_rows(policy, catalog_revision, native_rows):
    observed_revision = None
    if catalog_revision != policy.catalog_revision:
        if (
            type(catalog_revision) is not str
            or len(catalog_revision) != 64
            or any(value not in "0123456789abcdef" for value in catalog_revision)
        ):
            raise ValueError("Invalid Nox loot source revision")
        from wakfu_server import native_catalog
        from wakfu_server.native_catalog_compatibility import require_source_revision

        observed_revision = native_catalog.release()
        if catalog_revision != observed_revision:
            raise ValueError("Nox loot rows do not belong to the current native source")
        require_source_revision(policy.catalog_revision, ("monster-encyclopedia.json",))
    selected = sorted(
        (
            row
            for row in native_rows
            if row.get("reference_id") in policy.item_references
            and row.get("complex_criteria") is True
        ),
        key=lambda row: row["reference_id"],
    )
    if tuple(row["reference_id"] for row in selected) != policy.item_references or any(
        row.get("complex_criteria") is not True
        or row.get("is_loot_table") is not False
        or row.get("conditions") != []
        for row in selected
    ):
        raise ValueError(
            "Nox complex loot rows differ from the bounded database policy"
        )
    digest = sha256(
        json.dumps(
            selected, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    if digest != policy.native_rows_sha256:
        raise ValueError("Nox loot cannot replace native probabilities or quantities")
    if observed_revision is not None and native_catalog.release() != observed_revision:
        raise ValueError("Native publication changed during Nox loot validation")


def validate_context(context, score):
    """Validate a frozen authorization's shape before pure drop arithmetic."""
    keys = {
        "policy",
        "monster_reference",
        "encounter_controller",
        "minimum_score",
        "catalog_revision",
        "native_rows_sha256",
        "expected_item_count",
        "item_references",
    }
    if not isinstance(context, dict) or set(context) != keys:
        raise ValueError("Malformed Nox complex-loot permission")
    references = context["item_references"]
    if (
        context["monster_reference"] != NOX_SCORE.reference
        or context["encounter_controller"] != NOX_SCORE.name
        or not isinstance(context["policy"], str)
        or not context["policy"]
        or type(context["minimum_score"]) is not int
        or context["minimum_score"] < NOX_SCORE.minimum_score
        or type(score) is not int
        or score < context["minimum_score"]
        or type(references) is not list
        or not references
        or any(type(i) is not int or i <= 0 for i in references)
        or references != sorted(set(references))
        or type(context["expected_item_count"]) is not int
        or len(references) != context["expected_item_count"]
        or any(
            not isinstance(context[k], str)
            or len(context[k]) != 64
            or any(c not in "0123456789abcdef" for c in context[k])
            for k in ("catalog_revision", "native_rows_sha256")
        )
    ):
        raise ValueError("Nox complex loot lacks its scored, bounded permission")
    return dict(context, item_references=list(references))


def policy_from_context(context, score):
    c = validate_context(context, score)
    return NoxComplexLootPolicy(
        c["policy"],
        c["monster_reference"],
        c["encounter_controller"],
        c["minimum_score"],
        c["catalog_revision"],
        c["native_rows_sha256"],
        c["expected_item_count"],
        tuple(c["item_references"]),
    )


def earned(policy, terminal):
    score = terminal.get("score")
    return (
        terminal.get("eligible") is True
        and terminal.get("boss_defeated") is True
        and terminal.get("survived") is True
        and terminal.get("encounter_controller") == policy.encounter_controller
        and type(score) is int
        and score >= policy.minimum_score
    )


def terminal_drop_context(db, terminal):
    policy = load_policy(db)
    if policy is None or not earned(policy, terminal):
        return None
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    monster = native_catalog.record(
        DATA_ROOT / "monster-encyclopedia.json", "monsters", policy.monster_reference
    )
    if not isinstance(monster, dict) or not isinstance(
        monster.get("combat_drops"), list
    ):
        raise ValueError("Nox terminal loot lacks its indexed native rows")
    validate_native_rows(policy, native_catalog.release(), monster["combat_drops"])
    return permission(policy)


def validate_durable_permission(db, fight_id, fight_context):
    c = validate_context(fight_context["nox_complex_loot"], fight_context.get("score"))
    policy = load_policy(db, version=c["policy"])
    row = db.execute(
        "SELECT snapshot,score FROM boss_score_terminal_receipts WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if (
        policy is None
        or c != permission(policy)
        or row is None
        or row["score"] != fight_context["score"]
        or row["snapshot"].get("score") != row["score"]
        or not earned(policy, row["snapshot"])
    ):
        raise ValueError(
            "Nox complex loot requires this fight's actual durable terminal"
        )
