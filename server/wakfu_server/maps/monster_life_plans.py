"""Durable seeded lifecycle decisions; active clocks remain time authority."""
import hashlib
import hmac
import secrets

BLOCK_SIZE = 32
MAX_FAILURES = 5
VERSION = 1


def event(seed, cycle):
    """Independent labels prevent adding a decision from perturbing old draws."""

    def digest(label):
        return hmac.new(
            bytes.fromhex(seed), f"{VERSION}:{cycle}:{label}".encode(), hashlib.sha256
        ).digest()

    def draw(label):
        return (int.from_bytes(digest(label)[:8], "big") >> 11) / (1 << 53)

    return dict(
        cycle=cycle,
        draw=draw("draw"),
        group_draw=draw("group"),
        destination_draw=draw("destination"),
        variant_seed=digest("variant").hex(),
        attempts=0,
    )


def choose(candidates, decision):
    """Pick first available candidate in a fixed seeded preference ordering."""

    def rank(candidate):
        identity = (
            candidate.get("reference")
            if isinstance(candidate, dict)
            else list(candidate)
        )
        return hmac.new(
            bytes.fromhex(decision["variant_seed"]),
            str(identity).encode(),
            hashlib.sha256,
        ).digest()

    return min(candidates, key=rank)


def choose_destination(candidates, decision):
    """Occupancy removes preferences without redrawing a destination."""
    key = str(decision["destination_draw"]).encode()
    return min(
        candidates,
        key=lambda cell: hmac.new(
            key, str(list(cell)).encode(), hashlib.sha256
        ).digest(),
    )


def load(db, map_id, instance_id, kind, timers, configuration):
    """Backfill and extend one complete scope using bounded statement counts."""
    from psycopg.types.json import Jsonb

    # Claim group liveness before locking plans. A concurrent defeat must wait
    # for this transaction and its death trigger then removes newly made plans.
    valid_ids = {
        r["monster_id"]
        for r in db.execute(
            "SELECT m.monster_id FROM combat_group_members m "
            "JOIN combat_groups g USING(map_id,instance_id,group_id) "
            "WHERE m.map_id=%s AND m.instance_id=%s AND g.status!='defeated' "
            "ORDER BY g.group_id,m.monster_id FOR SHARE OF g",
            (map_id, instance_id),
        )
    }
    timers = [timer for timer in timers if timer["monster_id"] in valid_ids]
    rows = {
        r["monster_id"]: dict(r)
        for r in db.execute(
            "SELECT monster_id,reference,seed,incarnation,policy,version,block_start FROM monster_life_plans WHERE map_id=%s AND instance_id=%s AND kind=%s AND monster_id=ANY(%s) FOR UPDATE",
            (map_id, instance_id, kind, sorted(valid_ids)),
        )
    }
    inserts, updates = [], []
    for timer in timers:
        identity, cycle = timer["monster_id"], max(1, timer["cycle"])
        row = rows.get(identity)
        if row is None:
            seed = secrets.token_hex(32)
            row = dict(
                monster_id=identity,
                reference=timer["reference"],
                seed=seed,
                incarnation=secrets.token_hex(16),
                policy=configuration,
                version=VERSION,
                block_start=cycle,
                events=[event(seed, c) for c in range(cycle, cycle + BLOCK_SIZE)],
            )
            rows[identity] = row
            inserts.append(row)
        elif cycle >= row["block_start"] + BLOCK_SIZE:
            row.update(
                block_start=cycle,
                events=[
                    event(row["seed"], c) for c in range(cycle, cycle + BLOCK_SIZE)
                ],
            )
            updates.append(row)
    if inserts:
        db.execute(
            "INSERT INTO monster_life_plans(map_id,instance_id,kind,monster_id,reference,seed,incarnation,policy,version,block_start,events) "
            "SELECT %s,%s,%s,x.monster_id,x.reference,x.seed,x.incarnation,x.policy,x.version,x.block_start,x.events "
            "FROM jsonb_to_recordset(%s) x(monster_id bigint,reference integer,seed text,incarnation text,policy jsonb,version integer,block_start bigint,events jsonb) ON CONFLICT DO NOTHING",
            (map_id, instance_id, kind, Jsonb(inserts)),
        )
    if updates:
        db.execute(
            "UPDATE monster_life_plans p SET block_start=x.block_start,events=x.events FROM jsonb_to_recordset(%s) "
            "x(monster_id bigint,block_start bigint,events jsonb) WHERE p.map_id=%s AND p.instance_id=%s AND p.kind=%s AND p.monster_id=x.monster_id",
            (Jsonb(updates), map_id, instance_id, kind),
        )
    return rows


def attach(store, scope, kind, tickets, configuration):
    from psycopg.types.json import Jsonb

    if not tickets:
        return []
    with store.connection() as db:
        live_plans = load(db, *scope, kind, tickets, configuration)
        tickets = [ticket for ticket in tickets if ticket["monster_id"] in live_plans]
        if not tickets:
            return []
        plans = {
            r["monster_id"]: r
            for r in db.execute(
                "SELECT p.monster_id,p.incarnation,p.policy,p.events->(x.cycle-p.block_start)::integer AS decision "
                "FROM monster_life_plans p JOIN jsonb_to_recordset(%s) x(monster_id bigint,cycle bigint) USING(monster_id) "
                "WHERE p.map_id=%s AND p.instance_id=%s AND p.kind=%s",
                (Jsonb(tickets), *scope, kind),
            )
        }
    result = []
    for ticket in tickets:
        plan = plans.get(ticket["monster_id"])
        if plan is None:
            continue
        decision = plan["decision"]
        if decision is not None and decision["attempts"] < MAX_FAILURES:
            result.append(
                dict(
                    ticket,
                    plan_incarnation=plan["incarnation"],
                    decision=decision,
                    plan_policy=plan["policy"],
                )
            )
    return result


def fence(db, ticket, kind, configuration=None, draw=None):
    """A defeated incarnation cannot consume a respawn's matching clock cycle."""
    if "plan_incarnation" not in ticket:
        return True
    row = db.execute(
        "SELECT incarnation,policy,events->(%s-block_start)::integer AS decision FROM monster_life_plans WHERE map_id=%s AND instance_id=%s AND monster_id=%s AND kind=%s FOR UPDATE",
        (
            ticket["cycle"],
            ticket["map_id"],
            ticket["instance_id"],
            ticket["monster_id"],
            kind,
        ),
    ).fetchone()
    return (
        row is not None
        and row["incarnation"] == ticket["plan_incarnation"]
        and row["decision"] is not None
        and {k: v for k, v in row["decision"].items() if k != "attempts"}
        == {k: v for k, v in ticket.get("decision", {}).items() if k != "attempts"}
        and row["decision"]["attempts"] < MAX_FAILURES
        and (configuration is None or row["policy"] == configuration)
        and (draw is None or row["decision"]["draw"] == draw)
    )


def failure(store, ticket, kind):
    """Only exceptional execution failures spend the persistent event budget."""
    with store.connection() as db:
        db.execute(
            "SELECT group_id FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
            (ticket["map_id"], ticket["instance_id"], ticket["group_id"]),
        ).fetchone()
        if not fence(db, ticket, kind):
            return
        db.execute(
            "UPDATE monster_life_plans SET events=jsonb_set(events,ARRAY[(%s-block_start)::text,'attempts'], "
            "to_jsonb(LEAST(5,COALESCE((events->(%s-block_start)::integer->>'attempts')::integer,0)+1))) "
            "WHERE map_id=%s AND instance_id=%s AND monster_id=%s AND kind=%s AND %s>=block_start AND %s<block_start+32",
            (
                ticket["cycle"],
                ticket["cycle"],
                ticket["map_id"],
                ticket["instance_id"],
                ticket["monster_id"],
                kind,
                ticket["cycle"],
                ticket["cycle"],
            ),
        )
        db.execute(
            "UPDATE monster_"
            + kind
            + "_timers t SET due=false,last_active_ms=NULL,remaining_ms=(p.policy->>'interval_ms')::bigint "
            "FROM monster_life_plans p WHERE t.map_id=p.map_id AND t.instance_id=p.instance_id AND t.monster_id=p.monster_id "
            "AND p.map_id=%s AND p.instance_id=%s AND p.monster_id=%s AND p.kind=%s AND t.cycle=%s "
            "AND (p.events->(%s-p.block_start)::integer->>'attempts')::integer=5",
            (
                ticket["map_id"],
                ticket["instance_id"],
                ticket["monster_id"],
                kind,
                ticket["cycle"],
                ticket["cycle"],
            ),
        )


def resolve_noops(store, proposals):
    """Advance failed probability draws in set-based guarded transactions.

    These operations never mutate actor/native state or publish. Current group
    composition, incarnation, reference and due cycle must still match.
    """
    from psycopg.types.json import Jsonb

    remaining = []
    by_kind = {"maturation": [], "reproduction": []}
    for p in proposals:
        kind = p["kind"]
        noop = kind == "maturation" and p.get("grown") is None
        if kind == "reproduction":
            # The commit path can only reduce this upper probability bound.
            from .monster_reproduction import birth_probability

            noop = p["draw"] >= birth_probability(
                p["ticket"]["reference"],
                p["configuration"],
                group_size=len(p["expected_members"]),
            )
        if not noop or "plan_incarnation" not in p.get("ticket", {}):
            remaining.append(p)
            continue
        t = p["ticket"]
        by_kind[kind].append(
            dict(
                t,
                members=p["expected_members"],
                policy=p["configuration"],
                draw=p["draw"],
                probability=(
                    birth_probability(
                        t["reference"],
                        p["configuration"],
                        group_size=len(p["expected_members"]),
                    )
                    if kind == "reproduction"
                    else 0
                ),
                interval_ms=p["configuration"]["interval_ms"],
            )
        )
    for kind, rows in by_kind.items():
        if not rows:
            continue
        with store.connection() as db:
            # Match the same population/group locking order as ordinary commits.
            scopes = sorted({(r["map_id"], r["instance_id"]) for r in rows})
            for scope in scopes:
                db.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    ("monster-population:" + ":".join(map(str, scope)),),
                )
            data = Jsonb(rows)
            definition = "map_id integer,instance_id bigint,monster_id bigint,group_id bigint,reference integer,cycle bigint,plan_incarnation text,members jsonb,policy jsonb,draw double precision,probability double precision,interval_ms bigint"
            # Lock all relevant groups once. No per-monster round trips.
            db.execute(
                "SELECT g.group_id FROM combat_groups g JOIN jsonb_to_recordset(%s) x("
                + definition
                + ") USING(map_id,instance_id,group_id) ORDER BY g.map_id,g.instance_id,g.group_id FOR UPDATE OF g",
                (data,),
            ).fetchall()
            if kind == "maturation":
                columns = "group_id,from_reference,to_reference,draw,policy"
                values = "x.group_id,x.reference,NULL,x.draw,x.policy || '{\"composition_model\":2}'::jsonb"
            else:
                columns = "parent_group_id,parent_reference,child_id,child_group_id,child,draw,probability,policy"
                values = "x.group_id,x.reference,NULL,NULL,NULL,x.draw,x.probability,x.policy"
            db.execute(
                "WITH x AS (SELECT * FROM jsonb_to_recordset(%s) x("
                + definition
                + ")), inserted AS ("
                "INSERT INTO monster_"
                + kind
                + "_receipts(map_id,instance_id,monster_id,cycle,"
                + columns
                + ") "
                "SELECT x.map_id,x.instance_id,x.monster_id,x.cycle,"
                + values
                + " FROM x "
                "JOIN combat_groups g USING(map_id,instance_id,group_id) "
                "JOIN monster_life_plans p USING(map_id,instance_id,monster_id) "
                "JOIN monster_"
                + kind
                + "_timers t USING(map_id,instance_id,monster_id) "
                "WHERE g.status='available' AND g.members=x.members AND p.kind=%s AND p.incarnation=x.plan_incarnation "
                "AND p.policy=x.policy AND (p.events->(x.cycle-p.block_start)::integer->>'draw')::double precision=x.draw AND t.due AND t.cycle=x.cycle AND t.reference=x.reference "
                "ON CONFLICT DO NOTHING RETURNING map_id,instance_id,monster_id,cycle) "
                "UPDATE monster_"
                + kind
                + "_timers t SET remaining_ms=x.interval_ms,last_active_ms=NULL,due=false "
                "FROM x JOIN inserted i USING(map_id,instance_id,monster_id,cycle) WHERE t.map_id=x.map_id AND t.instance_id=x.instance_id AND t.monster_id=x.monster_id",
                (data, kind),
            )
    return remaining
