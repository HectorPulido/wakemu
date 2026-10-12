"""Audited, idempotent corrections of historical ecology-bound mistakes.

The World owner chooses original operations and publishes the committed result.
This module never starts a transaction, changes historical receipts, or forces
an absolute character value. Frozen historical policy magnitudes are preserved.
"""
import hashlib
import json
from .ecology_equilibrium import limits
from .ecology_progression import LIMIT

OLD_SOURCES = ("local_fallback", "native", "local")


def evaluate(receipt):
    evidence = receipt["evidence"]
    policy = evidence.get("policy", {})
    if (
        evidence.get("limit_source") not in OLD_SOURCES
        or policy.get("version") != 2
        or policy.get("unit") != "basis_points"
    ):
        raise ValueError("Unsupported historical ecology receipt")
    native = limits(
        evidence["map_id"],
        evidence["region_id"],
        evidence["kind"],
        evidence["family_id"],
    )
    low, high = native["minimum"], native["maximum"]
    before, after = evidence["before_population"], evidence["after_population"]
    if any(type(value) is not int or value < 0 for value in (before, after)):
        raise ValueError("Invalid historical population evidence")
    for key, lower, upper in (
        ("balance_delta", 1, LIMIT),
        ("imbalance_delta", -LIMIT, -1),
    ):
        if type(policy.get(key)) is not int or not lower <= policy[key] <= upper:
            raise ValueError("Invalid historical ecology policy")
    old_distance = max(low - before, before - high, 0) if low is not None else 0
    new_distance = max(low - after, after - high, 0) if low is not None else 0
    expected = (
        policy["balance_delta"]
        if new_distance < old_distance
        else policy["imbalance_delta"]
        if new_distance > old_distance
        else 0
    )
    expected_applied = (
        max(-LIMIT, min(LIMIT, receipt["before_value"] + expected))
        - receipt["before_value"]
    )
    actual_applied = receipt["after_value"] - receipt["before_value"]
    canonical = json.dumps(dict(receipt), sort_keys=True, separators=(",", ":"))
    return dict(
        original_operation=receipt["operation"],
        original_revision=receipt["revision"],
        original_receipt_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        original_requested_delta=receipt["requested_delta"],
        original_applied_delta=actual_applied,
        expected_requested_delta=expected,
        expected_applied_delta=expected_applied,
        correction_delta=expected_applied - actual_applied,
        native_limits=native,
    )


def plan(db, character_id):
    """Read a reviewable plan; unsupported old policy units are explicit skips."""
    rows = db.execute(
        "SELECT * FROM personal_ecology_receipts WHERE character_id=%s "
        "AND evidence->>'limit_source'=ANY(%s) ORDER BY revision",
        (character_id, list(OLD_SOURCES)),
    ).fetchall()
    corrections, skipped = [], []
    for row in rows:
        try:
            result = evaluate(row)
        except (ValueError, KeyError) as error:
            skipped.append(dict(operation=row["operation"], reason=str(error)))
            continue
        if result["correction_delta"] > 0:
            corrections.append(result)
        elif result["correction_delta"] < 0:
            skipped.append(
                dict(operation=row["operation"], reason="historical_clawback_excluded")
            )
    completed = {
        row["original_operation"]
        for row in db.execute(
            "SELECT evidence->'original'->>'original_operation' AS original_operation "
            "FROM personal_ecology_receipts WHERE character_id=%s "
            "AND operation LIKE 'native-chief-correction:%%'",
            (character_id,),
        )
    }
    corrections = [
        row for row in corrections if row["original_operation"] not in completed
    ]
    return dict(
        character_id=character_id,
        corrections=corrections,
        skipped=skipped,
        total_delta=sum(row["correction_delta"] for row in corrections),
    )


def apply_selected(db, character_id, *, operations):
    """Recompute selected immutable originals under the caller's World lease.

    Each correction uses the ordinary personal-ecology ledger. Repeating a
    selection replays the same correction operations and cannot credit twice.
    Return the final absolute packet and state for publication after commit.
    """
    from .personal_ecology import apply

    if (
        not isinstance(operations, (tuple, list))
        or not operations
        or any(
            not isinstance(operation, str) or not operation for operation in operations
        )
        or len(set(operations)) != len(operations)
    ):
        raise ValueError("Explicit unique ecology operations are required")
    actor = db.execute(
        "SELECT id FROM characters WHERE id=%s FOR UPDATE", (character_id,)
    ).fetchone()
    if actor is None:
        raise ValueError("Unknown ecology character")
    originals = db.execute(
        "SELECT * FROM personal_ecology_receipts WHERE character_id=%s "
        "AND operation=ANY(%s) ORDER BY revision",
        (character_id, list(operations)),
    ).fetchall()
    if len(originals) != len(operations):
        raise ValueError("Missing original ecology operation")
    # Validate the entire selection before writing any correction.
    evaluations = [evaluate(receipt) for receipt in originals]
    if any(row["correction_delta"] <= 0 for row in evaluations):
        raise ValueError("Only harmful historical charges may be corrected")
    results = []
    for original, evaluation in zip(originals, evaluations):
        remainder = evaluation["correction_delta"]
        digest = hashlib.sha256(
            (str(character_id) + ":" + original["operation"]).encode()
        ).hexdigest()
        part = 0
        while remainder:
            delta = max(-LIMIT, min(LIMIT, remainder))
            proof = dict(
                correction_schema_version=1,
                correction_reason="native_chief_equilibrium",
                original=evaluation,
                correction_part=part,
                correction_part_delta=delta,
            )
            results.append(
                apply(
                    db,
                    character_id,
                    operation=f"native-chief-correction:{digest}:{part}",
                    delta=delta,
                    evidence=proof,
                )
            )
            remainder -= delta
            part += 1
    actor = db.execute(
        "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
        (character_id,),
    ).fetchone()
    from .personal_ecology import packet

    return dict(
        results=results,
        ecology_value=actor["ecology_value"],
        ecology_revision=actor["ecology_revision"],
        packet=packet(character_id, actor["ecology_value"]),
    )


def prepare(store, snapshot, *, limit=1):
    """Plan at most sixteen positive corrections for active owned characters."""
    epoch = snapshot.get("world_epoch")
    if (
        not isinstance(epoch, str)
        or not epoch
        or type(limit) is not int
        or not 1 <= limit <= 16
    ):
        raise ValueError("Invalid affinity reconciliation snapshot")
    proposals = []
    for player in snapshot.get("players", ()):
        character_id, account_id = player.get("id"), player.get("account_id")
        if any(
            type(value) is not int or not 0 < value < 2**63
            for value in (character_id, account_id)
        ):
            continue
        with store.connection() as db:
            owner = db.execute(
                "SELECT account_id FROM characters WHERE id=%s AND deleted_at IS NULL",
                (character_id,),
            ).fetchone()
            if owner is None or owner["account_id"] != account_id:
                continue
            candidates = plan(db, character_id)["corrections"][:16]
        if not candidates:
            continue
        proposals.append(
            dict(
                kind="affinity_reconcile",
                world_epoch=epoch,
                character_id=character_id,
                account_id=account_id,
                original_operations=[
                    dict(
                        operation=row["original_operation"],
                        receipt_sha256=row["original_receipt_sha256"],
                    )
                    for row in candidates
                ],
            )
        )
        if len(proposals) >= limit:
            break
    return proposals


def apply(store, world, proposal):
    """Apply a World-authorized plan and publish its committed current state.

    Runtime must fence this handler with its current epoch. No group, garden,
    or harvesting locks are needed: only the character ledger row is changed.
    """
    if proposal.get("kind") != "affinity_reconcile":
        raise ValueError("Invalid affinity reconciliation proposal")
    identity = world.live_identity(character_id=proposal["character_id"])
    if identity is None or identity[1]["account_id"] != proposal["account_id"]:
        return dict(applied=False, reason="inactive_character")
    selected = proposal.get("original_operations")
    if not isinstance(selected, list) or not 1 <= len(selected) <= 16:
        raise ValueError("Invalid affinity reconciliation selection")
    operations = [row["operation"] for row in selected]
    with store.connection() as db:
        owner = db.execute(
            "SELECT account_id FROM characters WHERE id=%s AND deleted_at IS NULL FOR UPDATE",
            (proposal["character_id"],),
        ).fetchone()
        if owner is None or owner["account_id"] != proposal["account_id"]:
            return dict(applied=False, reason="foreign_character")
        originals = db.execute(
            "SELECT * FROM personal_ecology_receipts WHERE character_id=%s AND operation=ANY(%s)",
            (proposal["character_id"], operations),
        ).fetchall()
        fingerprints = {
            row["operation"]: evaluate(row)["original_receipt_sha256"]
            for row in originals
        }
        if len(fingerprints) != len(selected) or any(
            fingerprints.get(row["operation"]) != row["receipt_sha256"]
            for row in selected
        ):
            raise ValueError("Stale affinity reconciliation receipt fingerprint")
        result = apply_selected(db, proposal["character_id"], operations=operations)
        committed = store.character(
            proposal["account_id"], proposal["character_id"], db
        )
    result["published"] = world.publish_ecology(committed)
    result["applied"] = any(not row["duplicate"] for row in result["results"])
    corrected = [row["receipt"] for row in result["results"] if not row["duplicate"]]
    restored = sum(row["after_value"] - row["before_value"] for row in corrected)
    if result["published"] and corrected:
        world.information(
            proposal["character_id"],
            "Ecosistema: restitución de afinidad por errores anteriores de equilibrio "
            f"({restored / 100:.2f} puntos hacia Wakfu). No es una recompensa por reproducción natural.",
        )
    return result
