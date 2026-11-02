"""Read-only qualification of a required prefix, independent of optional fights."""


def require_checkpoint(db, run, checkpoint, *, expected_hash):
    if (
        type(checkpoint) is not int
        or checkpoint <= 0
        or run["status"] not in ("active", "completed")
        or run.get("catalog_hash") != expected_hash
        or run["current_room"] < checkpoint + (run["status"] != "completed")
        or checkpoint > len(run["rooms"])
    ):
        raise ValueError("Optional gate lacks its required main checkpoint")
    rows = db.execute(
        "SELECT room_order,fight_id,result FROM dungeon_room_encounters "
        "WHERE instance_id=%s AND encounter_scope='main' AND status='victory' "
        "AND room_order<=%s ORDER BY room_order,fight_id",
        (run["instance_id"], checkpoint),
    ).fetchall()
    expected = list(range(1, checkpoint + 1))
    if (
        [row["room_order"] for row in rows] != expected
        or len({row["fight_id"] for row in rows}) != checkpoint
        or any(row["result"].get("victory") is not True for row in rows)
        or any(
            row["result"].get("current_room", 0) != row["room_order"] + 1
            for row in rows
            if row["room_order"] < len(run["rooms"])
        )
    ):
        raise ValueError("Optional gate requires distinct committed prefix victories")
    return tuple(row["fight_id"] for row in rows)


def require_access(db, run, receipt):
    if receipt.get("activation_method") != "native_vote":
        if run["status"] != "completed":
            raise ValueError("Optional encounter requires completed main progression")
        return
    if not {"instance_id", "catalog_hash", "rooms"} <= set(run):
        run = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
            (receipt["instance_id"],),
        ).fetchone()
        if run is None:
            raise ValueError("Optional vote main run is absent")
    gate = db.execute(
        "SELECT * FROM dungeon_optional_gate_choices WHERE instance_id=%s",
        (receipt["instance_id"],),
    ).fetchone()
    if (
        gate is None
        or gate["winner"] != "archimonster"
        or receipt.get("vote_gate_instance_id") != run["instance_id"]
        or gate["catalog_hash"] != receipt["catalog_hash"]
        or gate["rule_sha256"] != receipt["rule_sha256"]
    ):
        raise ValueError("Optional encounter lacks its winning native vote receipt")
    from wakfu_server.dungeon_optional_votes import rules, digest
    from wakfu_server import native_catalog

    contracts = [rule for rule in rules() if rule["key"] == gate["contract_key"]]
    if (
        len(contracts) != 1
        or digest(contracts[0]) != gate["rule_sha256"]
        or contracts[0]["native_revision"] != native_catalog.release()
    ):
        raise ValueError("Optional vote source is no longer qualified")
    require_checkpoint(
        db, run, gate["required_checkpoint"], expected_hash=gate["catalog_hash"]
    )
