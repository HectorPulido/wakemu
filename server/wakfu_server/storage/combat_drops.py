"""Wakfu-native loot rows with capped per-player prospection probability.

This module is deliberately an adapter/store API, not a combat callback. The
caller supplies a finished owned winner, the defeated native monster actor
identities, the winner's authoritative Wakfu prospection bonus, and the fight
condition snapshot. `resolve` writes one immutable, idempotent award batch in
the caller's transaction so it can share the victory reward/lifecycle commit.
"""
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.reward_rates import MAX_REWARD_RATE_BP
from wakfu_server.combat_drop_types import AwardBatch, DropDecision
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from hashlib import sha256
import json
import secrets

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from wakfu_server.paths import DATA_ROOT


ALGORITHM = "wakfu-capped-prospection-drop-formula-v2-native-catalog"
DRAW_DENOMINATOR = 1 << 53
PROSPECTION_STAT_ID = 33
_MAX_SAFE_ATTEMPTS = 1000


def _integer(value, name, minimum=0, maximum=(1 << 63) - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {name}")
    return value


def _decimal(value, name, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValueError(f"Invalid {name}")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Invalid {name}") from None
    if not result.is_finite():
        raise ValueError(f"Invalid {name}")
    if minimum is not None and result < minimum:
        raise ValueError(f"Invalid {name}")
    if maximum is not None and result > maximum:
        raise ValueError(f"Invalid {name}")
    return result


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@lru_cache(maxsize=1)
def native_drop_catalog():
    path = DATA_ROOT / "monster-encyclopedia.json"
    raw = protocol_catalog.read_bytes(path)
    catalog = protocol_catalog.load(path)
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 1:
        raise ValueError("Unsupported native monster loot catalog")
    monsters = catalog.get("monsters")
    if not isinstance(monsters, list):
        raise ValueError("Native monster loot catalog is malformed")
    indexed = {}
    for monster in monsters:
        if not isinstance(monster, dict):
            raise ValueError("Native monster loot catalog is malformed")
        reference = _integer(monster.get("ref"), "monster reference", 1, 2**31 - 1)
        if reference in indexed:
            raise ValueError("Duplicate native monster reference")
        drops = monster.get("combat_drops")
        if not isinstance(drops, list):
            raise ValueError("Native combat drop rows are malformed")
        indexed[reference] = drops
    return {
        "source_sha256": sha256(raw).hexdigest(),
        "monsters": indexed,
    }


def native_prospection_bonus(actor):
    """Read Wakfu stat33 from the already-frozen combat actor snapshot.

    Missing stat33 is an incomplete authoritative snapshot, not a zero bonus.
    """
    from wakfu_server.combat_actor_snapshot import native_actor_catalog

    catalog = native_actor_catalog().get("characteristics")
    row = catalog.get(str(PROSPECTION_STAT_ID)) if isinstance(catalog, dict) else None
    if (
        not isinstance(row, dict)
        or row.get("name") != "PROSPECTION"
        or row.get("native_default") != 0
    ):
        raise ValueError("Native Wakfu prospection characteristic is unavailable")
    stats = getattr(actor, "effect_stats", None)
    if not isinstance(stats, dict) or PROSPECTION_STAT_ID not in stats:
        raise ValueError("Player has no authoritative Wakfu prospection snapshot")
    return _integer(
        stats[PROSPECTION_STAT_ID],
        "Wakfu prospection bonus",
        row["hard_minimum"],
        row["hard_maximum"],
    )


def _condition_matches(condition, fight_context):
    if not isinstance(condition, dict):
        return False
    kind, value = condition.get("native_enum"), condition.get("value")
    if type(value) is not int:
        return False
    if kind == "NOT_IN_DUNGEON" and value == -1:
        return fight_context.get("in_dungeon") is False
    if kind == "ONLY_IN_DUNGEON" and value == -1:
        return fight_context.get("in_dungeon") is True
    if kind == "NOT_IN_INFINITE_WAVES" and value == -1:
        return fight_context.get("in_infinite_waves") is False
    if kind == "ONLY_WHEN_DOWNSCALED" and value == -1:
        return fight_context.get("downscaled") is True
    if kind == "CAN_BE_LOOTED_IN_STELE" and value == -1:
        return fight_context.get("stele_loot_enabled") is True
    if kind == "MIN_STASIS_LEVEL":
        stasis = fight_context.get("stasis_level")
        return type(stasis) is int and stasis >= value
    if kind == "MIN_SCORE":
        score = fight_context.get("score")
        return type(score) is int and score >= value
    return False


def _normalize_fight_context(context):
    if not isinstance(context, dict):
        raise ValueError("Invalid fight drop context")
    allowed = {
        "in_dungeon",
        "in_infinite_waves",
        "downscaled",
        "stele_loot_enabled",
        "stasis_level",
        "score",
        "dungeon_drop_rate_bp",
        "selected_stele_item_references",
    }
    if set(context) - allowed:
        raise ValueError("Fight drop context has unknown fields")
    normalized = {}
    for key in ("in_dungeon", "in_infinite_waves", "downscaled", "stele_loot_enabled"):
        if key in context:
            if type(context[key]) is not bool:
                raise ValueError("Invalid fight drop boolean context")
            normalized[key] = context[key]
    for key in ("stasis_level", "score"):
        if key in context:
            normalized[key] = _integer(
                context[key],
                f"fight drop {key}",
                0,
                (2**63 - 1 if key == "score" else 2**31 - 1),
            )
    if "selected_stele_item_references" in context:
        references = context["selected_stele_item_references"]
        if not isinstance(references, (list, tuple)) or len(references) > 10000:
            raise ValueError("Invalid selected Stele item references")
        selected = [
            _integer(ref, "selected Stele item", 1, 2**31 - 1) for ref in references
        ]
        if len(selected) != len(set(selected)):
            raise ValueError("Duplicate selected Stele item reference")
        normalized["selected_stele_item_references"] = sorted(selected)
    if "dungeon_drop_rate_bp" in context:
        normalized["dungeon_drop_rate_bp"] = _integer(
            context["dungeon_drop_rate_bp"], "dungeon drop rate", 1, 71000
        )
    return normalized


def _row_is_eligible(row, *, fight_context, effective_prospection):
    if not isinstance(row, dict):
        return False
    if row.get("is_loot_table") is not False:
        # External tables have no accredited combat link or server-side
        # expression resolver in this project; do not invent one.
        return False
    if row.get("complex_criteria") is not False:
        return False
    conditions = row.get("conditions")
    # A selected reward subset authorizes only its actual native item rows.
    # The legacy Boolean cannot unlock every Stele-capable monster row.
    row_context = dict(
        fight_context,
        stele_loot_enabled=row.get("reference_id")
        in fight_context.get("selected_stele_item_references", ()),
    )
    if not isinstance(conditions, list) or not all(
        _condition_matches(condition, row_context) for condition in conditions
    ):
        return False
    minimum_prospection = row.get("native_csF")
    if (
        type(minimum_prospection) is not int
        or effective_prospection < minimum_prospection
    ):
        return False
    return True


def _validate_monsters(monsters, catalog):
    if not isinstance(monsters, (list, tuple)):
        raise ValueError("Invalid defeated native monster roster")
    if not monsters:
        return []
    normalized = []
    seen = set()
    for raw in monsters:
        if not isinstance(raw, dict) or set(raw) != {"actor_id", "reference"}:
            raise ValueError("Invalid defeated monster identity")
        actor_id = _integer(
            raw["actor_id"], "defeated monster actor id", -(1 << 63) + 1, -1
        )
        reference = _integer(raw["reference"], "monster reference", 1, 2**31 - 1)
        if actor_id in seen:
            raise ValueError("Duplicate defeated monster actor id")
        if reference not in catalog["monsters"]:
            raise ValueError("Unknown native monster reference")
        seen.add(actor_id)
        normalized.append({"actor_id": actor_id, "reference": reference})
    return normalized


def _random_below(rng, upper):
    if rng is None:
        return secrets.randbelow(upper)
    value = rng(upper)
    return _integer(value, "random draw", 0, upper - 1)


def _factors(
    *,
    prospecting_bonus,
    challenge_drop_percent,
    star_bonus_percent,
    conquest_rate_bp,
    drop_rate_bp,
    breach_bonus_bp,
):
    # Wakfu PP is a bonus capped at 200, including in-fight sources.
    applied_prospection = min(200, max(0, prospecting_bonus))
    prospecting_factor = Decimal(1) + Decimal(applied_prospection) / Decimal(100)
    # Preserve the existing native criteria gate separately: its field
    # semantics are not established by the probability research.
    native_gate_prospection = 100 + prospecting_bonus
    challenge_factor = Decimal(1) + Decimal(max(0, challenge_drop_percent)) / Decimal(
        100
    )
    star_factor = max(
        Decimal(1), Decimal(1) + Decimal(star_bonus_percent) / Decimal(100)
    )
    conquest_factor = Decimal(conquest_rate_bp) / Decimal(10000)
    drop_rate_factor = Decimal(drop_rate_bp) / Decimal(10000)
    breach_factor = Decimal(breach_bonus_bp) / Decimal(10000)
    return native_gate_prospection, (
        prospecting_factor
        * challenge_factor
        * star_factor
        * conquest_factor
        * drop_rate_factor
        * breach_factor
    )


def plan_player_drops(
    *,
    monsters,
    character_id,
    prospecting_bonus,
    can_loot,
    fight_context,
    challenge_drop_percent=0,
    star_bonus_percent=0,
    conquest_rate_bp=10000,
    drop_rate_bp=10000,
    breach_bonus_bp=10000,
    rng=None,
    catalog=None,
):
    """Plan per-player outcomes from native Wakfu rows and exact decimal math.

    `roll_count <= 0` is the native each-player sentinel and yields one
    attempt. Positive values yield that many attempts, as displayed by the
    native loot UI. Each raw row keeps its source index; rows are never merged
    by item/probability. Unknown complex/table conditions are skipped.
    """
    _integer(character_id, "character id", 1)
    prospecting_bonus = _integer(
        prospecting_bonus, "Wakfu prospection bonus", -1000, 1000
    )
    if type(can_loot) is not bool:
        raise ValueError("Invalid loot eligibility")
    fight_context = _normalize_fight_context(fight_context)
    for name, value, minimum, maximum in (
        ("challenge drop percent", challenge_drop_percent, -1000000, 1000000),
        ("star bonus percent", star_bonus_percent, -1000000, 1000000),
        ("conquest rate", conquest_rate_bp, 0, 1000000),
        ("drop rate", drop_rate_bp, 0, MAX_REWARD_RATE_BP),
        ("breach bonus", breach_bonus_bp, 0, 1000000),
    ):
        _integer(value, name, minimum, maximum)
    catalog = native_drop_catalog() if catalog is None else catalog
    normalized_monsters = _validate_monsters(monsters, catalog)
    native_gate_pp, modifiers = _factors(
        prospecting_bonus=prospecting_bonus,
        challenge_drop_percent=challenge_drop_percent,
        star_bonus_percent=star_bonus_percent,
        conquest_rate_bp=conquest_rate_bp,
        drop_rate_bp=drop_rate_bp,
        breach_bonus_bp=breach_bonus_bp,
    )
    modifiers *= Decimal(fight_context.get("dungeon_drop_rate_bp", 10000)) / Decimal(
        10000
    )
    if not can_loot:
        return ()

    decisions = []
    for monster in normalized_monsters:
        rows = catalog["monsters"][monster["reference"]]
        for row_index, row in enumerate(rows):
            if not _row_is_eligible(
                row, fight_context=fight_context, effective_prospection=native_gate_pp
            ):
                continue
            probability = _decimal(
                row.get("probability"),
                "native drop probability",
                Decimal(0),
                Decimal(1),
            )
            roll_count = _integer(
                row.get("roll_count"), "native roll count", -32768, _MAX_SAFE_ATTEMPTS
            )
            attempt_count = roll_count if roll_count > 0 else 1
            quantity_min = _integer(
                row.get("quantity_min"), "minimum drop quantity", 1, 32767
            )
            quantity_max = _integer(
                row.get("quantity_max"), "maximum drop quantity", quantity_min, 32767
            )
            item_reference = _integer(
                row.get("reference_id"), "drop item reference", 1, 2**31 - 1
            )
            roll_max = _integer(
                row.get("native_csE"), "native roll maximum", -32768, 32767
            )
            minimum_prospection = _integer(
                row.get("native_csF"), "native minimum prospection", 0, 32767
            )
            # Preserve exact odds and cap only the comparison threshold;
            # modifiers never create extra attempts or alter quantities.
            raw_probability = probability * modifiers
            effective_probability = min(Decimal(1), raw_probability)
            for attempt_index in range(attempt_count):
                draw = _random_below(rng, DRAW_DENOMINATOR)
                success = Decimal(draw) / Decimal(DRAW_DENOMINATOR) < raw_probability
                quantity_draw = None
                quantity = None
                if success:
                    span = quantity_max - quantity_min + 1
                    quantity_draw = _random_below(rng, span)
                    quantity = quantity_min + quantity_draw
                decisions.append(
                    DropDecision(
                        defeated_actor_id=monster["actor_id"],
                        monster_reference=monster["reference"],
                        drop_row_index=row_index,
                        attempt_index=attempt_index,
                        item_reference=item_reference,
                        success=success,
                        quantity=quantity,
                        base_probability=probability,
                        raw_probability=raw_probability,
                        effective_probability=effective_probability,
                        draw_numerator=draw,
                        quantity_draw_numerator=quantity_draw,
                        quantity_min=quantity_min,
                        quantity_max=quantity_max,
                        roll_count=roll_count,
                        native_roll_max=roll_max,
                        native_min_prospection=minimum_prospection,
                    )
                )
    return tuple(decisions)


def _decision_from_row(row):
    return DropDecision(
        defeated_actor_id=row["defeated_actor_id"],
        monster_reference=row["monster_reference"],
        drop_row_index=row["drop_row_index"],
        attempt_index=row["attempt_index"],
        item_reference=row["item_reference"],
        success=row["success"],
        quantity=row["quantity"],
        base_probability=Decimal(row["base_probability"]),
        raw_probability=Decimal(row["raw_probability"]),
        effective_probability=Decimal(row["effective_probability"]),
        draw_numerator=row["draw_numerator"],
        quantity_draw_numerator=row["quantity_draw_numerator"],
        quantity_min=row["quantity_min"],
        quantity_max=row["quantity_max"],
        roll_count=row["roll_count"],
        native_roll_max=row["native_roll_max"],
        native_min_prospection=row["native_min_prospection"],
    )


def _stored_batch(db, fight_id, character_id):
    batch = db.execute(
        "SELECT * FROM fight_drop_awards WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight_id, character_id),
    ).fetchone()
    if batch is None:
        return None
    encoded = _canonical_json(batch["snapshot"]).encode("utf8")
    digest = sha256(encoded).hexdigest()
    if digest != batch["snapshot_sha256"]:
        raise ValueError("Stored drop award snapshot hash is invalid")
    attempts = db.execute(
        "SELECT * FROM fight_drop_attempt_receipts WHERE fight_id=%s AND character_id=%s "
        "ORDER BY defeated_actor_id,drop_row_index,attempt_index",
        (fight_id, character_id),
    ).fetchall()
    decisions = tuple(_decision_from_row(row) for row in attempts)
    return AwardBatch(
        fight_id=fight_id,
        character_id=character_id,
        policy_version=batch["policy_version"],
        snapshot=batch["snapshot"],
        snapshot_sha256=digest,
        decisions=decisions,
        replayed=True,
    )


def resolve(
    store,
    db,
    *,
    account_id,
    generation,
    character_id,
    fight_id,
    monsters,
    prospecting_bonus,
    can_loot,
    fight_context,
    challenge_drop_percent=0,
    star_bonus_percent=0,
    conquest_rate_bp=10000,
    breach_bonus_bp=10000,
    rng=None,
):
    """Persist one winner's drop outcomes inside an existing victory TX.

    The established `fight_rewards` row is the authorization proof; this
    function must run after the reward award, before the transaction commits.
    Inventory insertion and FightReport delivery remain the caller's work.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Drop award requires an active transaction")
    account_id = _integer(account_id, "account id", 1)
    character_id = _integer(character_id, "character id", 1)
    fight_id = _integer(fight_id, "fight id", 1, 2**31 - 1)
    if not isinstance(generation, str) or not generation:
        raise ValueError("Invalid session generation")
    from wakfu_server.combat_reward_ownership import lock_recipient

    lock_recipient(store, db, account_id, generation, character_id, fight_id)
    reward = db.execute(
        "SELECT r.generation,p.team,f.status,f.fight_kind FROM fight_rewards r "
        "JOIN combat_fight_participants p ON p.fight_id=r.fight_id AND p.character_id=r.character_id "
        "AND p.account_id=r.account_id JOIN combat_fights f ON f.id=r.fight_id "
        "WHERE r.fight_id=%s AND r.character_id=%s AND r.account_id=%s FOR UPDATE OF f",
        (fight_id, character_id, account_id),
    ).fetchone()
    if (
        reward is None
        or reward["status"] != "finished"
        or reward["fight_kind"] != "pve"
    ):
        raise ValueError("Drop award requires an own finished PvE victory receipt")

    current = _stored_batch(db, fight_id, character_id)
    if current is not None:
        if current.snapshot.get("account_id") != account_id:
            raise ValueError("Drop award belongs to another account")
        return current
    if reward["generation"] != generation:
        raise ValueError("New drop award must share the victory reward session")

    settings = db.execute(
        "SELECT v.version,v.drop_rate_bp FROM combat_drop_policy_active a "
        "JOIN combat_drop_policy_versions v ON v.version=a.version "
        "WHERE a.singleton=true FOR SHARE OF a,v"
    ).fetchone()
    if settings is None:
        raise ValueError("No active combat drop policy")

    catalog = native_drop_catalog()
    normalized_monsters = _validate_monsters(monsters, catalog)
    decisions = plan_player_drops(
        monsters=normalized_monsters,
        character_id=character_id,
        prospecting_bonus=prospecting_bonus,
        can_loot=can_loot,
        fight_context=fight_context,
        challenge_drop_percent=challenge_drop_percent,
        star_bonus_percent=star_bonus_percent,
        conquest_rate_bp=conquest_rate_bp,
        drop_rate_bp=settings["drop_rate_bp"],
        breach_bonus_bp=breach_bonus_bp,
        rng=rng,
        catalog=catalog,
    )
    from .drop_allocation import allocate

    decisions, allocation = allocate(db, fight_id, character_id, decisions)
    snapshot = {
        "algorithm": ALGORITHM,
        "allocation": allocation,
        "policy_version": settings["version"],
        "source_catalog_sha256": catalog["source_sha256"],
        "account_id": account_id,
        "generation": generation,
        "fight_id": fight_id,
        "character_id": character_id,
        "prospection_stat_id": PROSPECTION_STAT_ID,
        "prospection_bonus": prospecting_bonus,
        "applied_prospection_bonus": min(200, max(0, prospecting_bonus)),
        "effective_prospection": 100 + min(200, max(0, prospecting_bonus)),
        "native_gate_prospection": 100 + prospecting_bonus,
        "can_loot": can_loot,
        "fight_context": fight_context,
        "modifiers": {
            "challenge_drop_percent": challenge_drop_percent,
            "star_bonus_percent": star_bonus_percent,
            "conquest_rate_bp": conquest_rate_bp,
            "drop_rate_bp": settings["drop_rate_bp"],
            "breach_bonus_bp": breach_bonus_bp,
        },
        "monsters": normalized_monsters,
        "attempt_count": len(decisions),
        "success_count": sum(1 for decision in decisions if decision.success),
    }
    encoded = _canonical_json(snapshot).encode("utf8")
    digest = sha256(encoded).hexdigest()
    inserted = db.execute(
        "INSERT INTO fight_drop_awards "
        "(fight_id,character_id,account_id,generation,policy_version,snapshot,snapshot_sha256) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(fight_id,character_id) DO NOTHING",
        (
            fight_id,
            character_id,
            account_id,
            generation,
            settings["version"],
            Jsonb(snapshot),
            digest,
        ),
    )
    if inserted.rowcount != 1:
        current = _stored_batch(db, fight_id, character_id)
        if current is None:
            raise RuntimeError("Drop award receipt disappeared")
        return current
    for decision in decisions:
        db.execute(
            "INSERT INTO fight_drop_attempt_receipts "
            "(fight_id,character_id,defeated_actor_id,monster_reference,drop_row_index,attempt_index,"
            "item_reference,success,quantity,quantity_min,quantity_max,base_probability,raw_probability,effective_probability,"
            "draw_numerator,quantity_draw_numerator,roll_count,native_roll_max,native_min_prospection) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                fight_id,
                character_id,
                decision.defeated_actor_id,
                decision.monster_reference,
                decision.drop_row_index,
                decision.attempt_index,
                decision.item_reference,
                decision.success,
                decision.quantity,
                decision.quantity_min,
                decision.quantity_max,
                decision.base_probability,
                decision.raw_probability,
                decision.effective_probability,
                decision.draw_numerator,
                decision.quantity_draw_numerator,
                decision.roll_count,
                decision.native_roll_max,
                decision.native_min_prospection,
            ),
        )
    return AwardBatch(
        fight_id=fight_id,
        character_id=character_id,
        policy_version=settings["version"],
        snapshot=snapshot,
        snapshot_sha256=digest,
        decisions=tuple(decisions),
        replayed=False,
    )


def report_loots(batch):
    """Return committed successful decisions as the FightReport loots shape.

    Entries intentionally remain separate by native drop row/attempt. The
    client FightLoot quantity is a signed short, and every native quantity is
    validated to that range before it reaches this adapter.
    """
    if not isinstance(batch, AwardBatch):
        raise ValueError("Committed drop award batch is required")
    result = []
    for decision in batch.decisions:
        if not decision.success:
            continue
        if decision.quantity is None or not 1 <= decision.quantity <= 32767:
            raise ValueError("Invalid committed FightLoot quantity")
        result.append(
            {
                "reference": decision.item_reference,
                "quantity": decision.quantity,
                "is_purse_loot": False,
                "is_pvp_loot": False,
            }
        )
    return result


def delivery_items(batch):
    """Expose successful immutable receipt identities to the inventory layer."""
    if not isinstance(batch, AwardBatch):
        raise ValueError("Committed drop award batch is required")
    result = []
    for decision in batch.decisions:
        if not decision.success:
            continue
        if decision.quantity is None or not 1 <= decision.quantity <= 32767:
            raise ValueError("Invalid committed drop quantity")
        result.append(
            {
                "fight_id": batch.fight_id,
                "character_id": batch.character_id,
                "defeated_actor_id": decision.defeated_actor_id,
                "drop_row_index": decision.drop_row_index,
                "attempt_index": decision.attempt_index,
                "reference": decision.item_reference,
                "quantity": decision.quantity,
            }
        )
    return result
