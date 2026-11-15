"""World-owned lifecycle decision fences and exceptional failure accounting."""

MAX_FAILURES = 5


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
