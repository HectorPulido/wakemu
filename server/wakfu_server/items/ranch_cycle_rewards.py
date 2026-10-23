"""Explicit Wakemu deployed-clock and independent native-row reward policy.

Native data supplies operands and criteria. This policy does not generate or
change lifespan, age, happiness, death, genetics or original lifecycle effects.
"""
import ast
from collections import Counter
from decimal import Decimal
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import random

POLICY = "wakemu_ranch_deployed_cycle_rewards_v1"
MAX_CYCLES_PER_SETTLEMENT = (
    3  # Processing budget; unprocessed elapsed time is retained.
)
CATALOG_SHA256 = "16e8220e099cc41063fa303fd5146851e009030a4afd9d8411ca4ea24b285415"


@lru_cache(maxsize=1)
def catalog():
    raw = Path(__file__).with_name("native_ranch_rewards.json").read_bytes()
    if sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("Conflicting original Ranch reward closure")
    data = json.loads(raw)
    species = {row["species_ref"]: row for row in data["species"]}
    tables = {row["p"]: row for row in data["tables"]}
    if len(species) != 125 or len(tables) != 114:
        raise ValueError("Incomplete original Ranch reward closure")
    for row in species.values():
        if (
            type(row["cycle_seconds"]) is not int
            or row["cycle_seconds"] <= 0
            or row["reward_table"] not in tables
        ):
            raise ValueError("Invalid native Ranch cycle definition")
    for table in tables.values():
        if table["eun"] != 1:
            raise ValueError("Unsupported native Ranch reward table mode")
        for entry in table["ugp"]:
            if (
                entry["bmW"] != 1
                or entry["enR"] != 1
                or entry["eus"] != 0
                or entry["ugq"]
                or not 0 <= entry["elS"] <= entry["elT"] <= 32767
                or entry["eiz"] != -1
                and not 0 <= entry["eiz"] <= 100
                or entry["elU"]
                and entry["atl"] not in tables
            ):
                raise ValueError("Unqualified native Ranch reward operand")
    return species, tables


def criterion(text, *, species, attributes, alive):
    """Typed native predicates with actual raw/default-zero attribute values."""
    if not text.strip():
        return True
    tree = ast.parse(text.replace("\r", " ").replace("\n", " ").strip(), mode="eval")

    def number(identity):
        value = attributes.get(identity, attributes.get(str(identity), 0))
        if type(value) is not int or not -(2**31) <= value < 2**31:
            raise ValueError("Malformed durable native Ranch attribute")
        return value

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, str):
            return node.value
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [evaluate(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not evaluate(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            left, right = evaluate(node.left), evaluate(node.right)
            if type(left) is not int or type(right) is not int:
                raise ValueError("Invalid Ranch criterion multiplication")
            return left * right
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == len(node.comparators) == 1
        ):
            left, right = evaluate(node.left), evaluate(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.GtE):
                return left >= right
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            name = node.func.id
            if name == "GetMonsterAttribute" and len(node.args) == 1:
                identity = evaluate(node.args[0])
                if type(identity) is not int:
                    raise ValueError("Invalid native Ranch attribute selector")
                return number(identity)
            if name == "GetRanchMonsterId" and not node.args:
                return species
            if name == "IsRanchMonsterDead" and (
                not node.args
                or len(node.args) == 1
                and evaluate(node.args[0]) == "target"
            ):
                return not alive
        raise ValueError("Unsupported native Ranch reward criterion")

    return bool(evaluate(tree.body))


def roll_cycle(definition, attributes, alive, rng):
    """Explicit independent-percent policy over the complete original table."""
    species, tables = catalog()
    if (
        definition not in species
        or type(alive) is not bool
        or not isinstance(attributes, dict)
    ):
        raise ValueError("Invalid native Ranch reward subject")
    # GetMonsterAttribute's original building modifiers apply by attribute ID.
    # All retained native construction modifiers are 33/87, disjoint from the
    # exact production selectors 0/1/2/34/55; no reward value is synthesized.
    result = Counter()

    def visit(identity, ancestors):
        if identity in ancestors:
            raise ValueError("Cyclic native Ranch reward table")
        for row in tables[identity]["ugp"]:
            if not criterion(
                row["eur"], species=definition, attributes=attributes, alive=alive
            ):
                continue
            rate = Decimal(str(row["eiz"]))
            if rate != -1 and rng.randrange(10000) >= int(rate * 100):
                continue
            amount = rng.randrange(row["elS"], row["elT"] + 1)
            if row["elU"]:
                for _ in range(amount):
                    visit(row["atl"], ancestors | {identity})
            elif row["atl"] != 0 and amount:
                result[row["atl"]] += amount

    visit(species[definition]["reward_table"], set())
    return [
        dict(reference=reference, quantity=quantity)
        for reference, quantity in sorted(result.items())
    ]


def consume_intervals(intervals, cycle_ms, max_cycles=MAX_CYCLES_PER_SETTLEMENT):
    """Consume chronological earned durations and retain exact completion dates."""
    if (
        not isinstance(intervals, (tuple, list))
        or type(cycle_ms) is not int
        or cycle_ms <= 0
        or type(max_cycles) is not int
        or not 0 <= max_cycles <= MAX_CYCLES_PER_SETTLEMENT
    ):
        raise ValueError("Invalid native Ranch earned interval queue")
    remaining = []
    previous = -1
    for interval in intervals:
        if (
            not isinstance(interval, (tuple, list))
            or len(interval) != 2
            or any(type(value) is not int for value in interval)
            or not 0 <= interval[0] < interval[1] < 2**63
            or interval[0] < previous
        ):
            raise ValueError("Malformed native Ranch earned interval")
        remaining.append(list(interval))
        previous = interval[1]
    available = sum(end - start for start, end in remaining)
    complete = min(available // cycle_ms, max_cycles)
    dates = []
    for _ in range(complete):
        needed = cycle_ms
        while needed:
            start, end = remaining[0]
            consumed = min(needed, end - start)
            needed -= consumed
            if start + consumed == end:
                remaining.pop(0)
            else:
                remaining[0][0] += consumed
            if not needed:
                dates.append(start + consumed)
    return dates, remaining


def settle_creature(db, store, row, *, now_ms):
    """Caller holds account and creature locks; all writes share its transaction."""
    from psycopg.types.json import Jsonb
    from wakfu_server.ranch_reward_retrieval import insert_pending

    released = row.get("released_at") is not None
    cycle_ms = catalog()[0][row["definition"]]["cycle_seconds"] * 1000
    if released and row["native_tjr"] < cycle_ms:
        return []
    if type(now_ms) is not int or not 0 <= row["native_tjr"] <= now_ms < 2**63:
        raise ValueError("Invalid durable Ranch cycle observation")
    initial = [[now_ms - row["native_tjr"], now_ms]] if row["native_tjr"] else []
    db.execute(
        "INSERT INTO account_ranch_cycle_progress(monster_uid,last_observed_ms,earned_intervals) "
        "VALUES(%s,%s,%s) ON CONFLICT(monster_uid) DO NOTHING",
        (row["uid"], now_ms, Jsonb(initial)),
    )
    clock = db.execute(
        "SELECT * FROM account_ranch_cycle_progress WHERE monster_uid=%s FOR UPDATE",
        (row["uid"],),
    ).fetchone()
    _, intervals = consume_intervals(clock["earned_intervals"], cycle_ms, max_cycles=0)
    if (
        now_ms < clock["last_observed_ms"]
        or any(end > clock["last_observed_ms"] for start, end in intervals)
        or sum(end - start for start, end in intervals) != row["native_tjr"]
    ):
        raise ValueError(
            "Native Ranch elapsed time differs from its durable earned intervals"
        )
    eligible = (
        not released
        and not row["inventory"]
        and row["native_tjv"]
        and clock["should_cycle"]
    )
    if eligible and now_ms > clock["last_observed_ms"]:
        start = clock["last_observed_ms"]
        if intervals and intervals[-1][1] == start:
            intervals[-1][1] = now_ms
        else:
            intervals.append([start, now_ms])
    dates, remaining = consume_intervals(intervals, cycle_ms)
    pending = []
    for index, drop_ms in enumerate(dates, 1):
        number = clock["cycle_number"] + index
        # Stable per-owned-cycle entropy is policy; replay cannot reroll a reward.
        seed = sha256(
            f"{POLICY}:{row['account_id']}:{row['uid']}:{number}".encode()
        ).digest()
        rng = random.Random(int.from_bytes(seed, "big"))
        items = roll_cycle(row["definition"], row["attributes"], row["native_tjv"], rng)
        pending.extend(
            insert_pending(
                db,
                account_id=row["account_id"],
                monster_uid=row["uid"],
                cycle_number=number,
                drop_date_ms=drop_ms,
                items=items,
                earned_carry=released,
            )
        )
    elapsed = sum(end - start for start, end in remaining)
    db.execute(
        "UPDATE account_ranch_cycle_progress SET last_observed_ms=%s,earned_intervals=%s,"
        "cycle_number=cycle_number+%s WHERE monster_uid=%s",
        (now_ms, Jsonb(remaining), len(dates), row["uid"]),
    )
    if elapsed != row["native_tjr"]:
        db.execute(
            "UPDATE account_ranch_creatures SET native_tjr=%s,revision=revision+1 WHERE uid=%s",
            (elapsed, row["uid"]),
        )
    return pending


def settle_account(db, store, account_id, *, now_ms):
    """Trusted periodic/interaction hook with the same account-first lock order."""
    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    pending = []
    minimum_cycle_ms = min(row["cycle_seconds"] for row in catalog()[0].values()) * 1000
    rows = db.execute(
        "SELECT * FROM account_ranch_creatures WHERE account_id=%s "
        "AND (released_at IS NULL OR native_tjr>=%s) ORDER BY uid FOR UPDATE",
        (account_id, minimum_cycle_ms),
    )
    for row in rows:
        pending.extend(settle_creature(db, store, row, now_ms=now_ms))
    return pending


def tick(store, account_id, generation, character, *, session):
    """Settle an idle owner's actual Ranch; visitors cannot drive another herd."""
    from wakfu_server.haven_ranch_herd import _authorize_scene
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.ranch_reward_retrieval import changed

    with store.connection() as db:
        _authorize_scene(store, db, account_id, generation, character, session)
        _idle(db, character["id"], store.now())
        pending = settle_account(
            db, store, account_id, now_ms=int(store.now().timestamp() * 1000)
        )
        return [
            changed(character["map_id"], pending[start : start + 32767])
            for start in range(0, len(pending), 32767)
        ]
