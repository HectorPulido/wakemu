"""Real same-account hero characters, without synthetic accounts or sessions."""
NATIVE_HERO_CAP = 2


def session_authorized(db, row):
    """An inactive owned hero uses its selected main's real account lease."""
    if row["selected_character_id"] == row["id"]:
        return True
    return (
        db.execute(
            "SELECT 1 FROM account_hero_slots h JOIN account_hero_rosters r USING(account_id) "
            "WHERE h.account_id=%s AND h.character_id=%s AND r.leader_id=%s",
            (row["account_id"], row["id"], row["selected_character_id"]),
        ).fetchone()
        is not None
    )


def expand_session_rows(db, store, rows):
    """Freeze owned heroes beside their fenced mains without extra sessions."""
    result = []
    for main in rows:
        result.append(dict(main))
        roster = load_roster(db, store, main["account_id"], main["id"])
        for hero in roster["heroes"]:
            store.lock_character(
                db, main["account_id"], main["generation"], hero["id"], selected=False
            )
            row = dict(
                hero,
                generation=main["generation"],
                expires_at=main["expires_at"],
                selected_character_id=main["id"],
                hero_main_id=main["id"],
            )
            for key in ("map_id", "instance_id", "x", "y", "z"):
                row[key] = main[key]
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                tuple(row[key] for key in ("map_id", "instance_id", "x", "y", "z"))
                + (row["id"],),
            )
            result.append(row)
    if len(result) > 6 or len({row["id"] for row in result}) != len(result):
        raise ValueError("Native party including heroes exceeds six unique characters")
    return sorted(result, key=lambda row: row["id"])


def _idle(db, identities):
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=ANY(%s) AND f.status IN ('placement','active') LIMIT 1",
        (list(identities),),
    ).fetchone():
        raise ValueError("Hero roster cannot change during combat")
    if db.execute(
        "SELECT 1 FROM rift_instances WHERE status IN ('entered','running') "
        "AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(members) m WHERE m::bigint=ANY(%s)) LIMIT 1",
        (list(identities),),
    ).fetchone():
        raise ValueError("Hero roster is frozen by an active rift")
    if db.execute(
        "SELECT 1 FROM dungeon_instance_members WHERE character_id=ANY(%s) "
        "AND status='active' LIMIT 1",
        (list(identities),),
    ).fetchone():
        raise ValueError("Hero roster is frozen by an active dungeon")


def _fence(db, store, account_id, generation, main_character_id):
    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    store.lock_character(db, account_id, generation, main_character_id)
    row = db.execute(
        "SELECT * FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
        (account_id,),
    ).fetchone()
    if row is None:
        row = db.execute(
            "INSERT INTO account_hero_rosters(account_id,leader_id) VALUES(%s,%s) RETURNING *",
            (account_id, main_character_id),
        ).fetchone()
    if row["leader_id"] != main_character_id:
        raise ValueError("Selected character does not own the active hero roster")
    return row


def load_roster(db, store, account_id, main_character_id):
    """Load owned character snapshots; caller fences the main selected session."""
    row = db.execute(
        "SELECT * FROM account_hero_rosters WHERE account_id=%s", (account_id,)
    ).fetchone()
    if row is None:
        return {
            "leader": store.character(account_id, main_character_id, db),
            "heroes": (),
            "revision": 0,
        }
    if row["leader_id"] != main_character_id:
        raise ValueError("Hero roster leader differs from selected character")
    slots = db.execute(
        "SELECT slot,character_id FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
        (account_id,),
    ).fetchall()
    ids = [r["character_id"] for r in slots]
    if (
        len(ids) > NATIVE_HERO_CAP
        or len(set(ids)) != len(ids)
        or main_character_id in ids
    ):
        raise ValueError("Invalid native hero roster")
    return {
        "leader": store.character(account_id, main_character_id, db),
        "heroes": tuple(store.character(account_id, i, db) for i in ids),
        "slots": tuple(r["slot"] for r in slots),
        "revision": row["revision"],
    }


def add(store, account_id, generation, main_character_id, hero_id):
    if type(hero_id) is not int or hero_id <= 0 or hero_id == main_character_id:
        raise ValueError("Invalid hero identity")
    with store.connection() as db:
        _fence(db, store, account_id, generation, main_character_id)
        hero = db.execute(
            "SELECT * FROM characters WHERE account_id=%s AND id=%s "
            "AND deleted_at IS NULL FOR UPDATE",
            (account_id, hero_id),
        ).fetchone()
        if hero is None:
            raise ValueError("Hero character unavailable or foreign")
        if hero["hp"] <= 0:
            raise ValueError("Dead characters cannot join as heroes")
        roster = load_roster(db, store, account_id, main_character_id)
        identities = [main_character_id, hero_id] + [r["id"] for r in roster["heroes"]]
        _idle(db, identities)
        if any(r["id"] == hero_id for r in roster["heroes"]):
            return dict(roster, applied=False)
        if len(roster["heroes"]) >= NATIVE_HERO_CAP:
            raise ValueError("Native hero slots are full")
        if db.execute(
            "SELECT 1 FROM player_party_members WHERE character_id=%s", (hero_id,)
        ).fetchone():
            raise ValueError("Hero already belongs to an ordinary player party")
        slot = next(
            i for i in range(NATIVE_HERO_CAP) if i not in roster.get("slots", ())
        )
        db.execute(
            "INSERT INTO account_hero_slots(account_id,slot,character_id) VALUES(%s,%s,%s)",
            (account_id, slot, hero_id),
        )
        leader = roster["leader"]
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
            tuple(leader[k] for k in ("map_id", "instance_id", "x", "y", "z"))
            + (hero_id,),
        )
        db.execute(
            "UPDATE account_hero_rosters SET revision=revision+1 WHERE account_id=%s",
            (account_id,),
        )
        party = _ensure_party(db, main_character_id)
        party_rows = db.execute(
            "SELECT c.* FROM player_party_members m JOIN characters c ON c.id=m.character_id "
            "WHERE m.party_id=%s",
            (party["id"],),
        ).fetchall()
        augment_party(db, store, party_rows)
        return dict(load_roster(db, store, account_id, main_character_id), applied=True)


def remove(store, account_id, generation, main_character_id, hero_id):
    if type(hero_id) is not int or hero_id <= 0 or hero_id == main_character_id:
        raise ValueError("Invalid hero removal identity")
    with store.connection() as db:
        _fence(db, store, account_id, generation, main_character_id)
        if (
            db.execute(
                "SELECT 1 FROM characters WHERE account_id=%s AND id=%s AND deleted_at IS NULL",
                (account_id, hero_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Hero removal character unavailable or foreign")
        roster = load_roster(db, store, account_id, main_character_id)
        _idle(db, [main_character_id] + [r["id"] for r in roster["heroes"]])
        removed = db.execute(
            "DELETE FROM account_hero_slots WHERE account_id=%s AND character_id=%s RETURNING slot",
            (account_id, hero_id),
        ).fetchone()
        if removed:
            db.execute(
                "UPDATE account_hero_rosters SET revision=revision+1 WHERE account_id=%s",
                (account_id,),
            )
        return dict(
            load_roster(db, store, account_id, main_character_id),
            applied=removed is not None,
        )


def select_main(store, account_id, generation, main_character_id):
    """Align a newly selected real main with the saved roster, preserving hero slots."""
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, main_character_id)
        row = db.execute(
            "SELECT * FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        if row is None:
            _fence(db, store, account_id, generation, main_character_id)
        elif row["leader_id"] != main_character_id:
            slots = db.execute(
                "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                (account_id,),
            ).fetchall()
            _idle(
                db,
                [row["leader_id"], main_character_id]
                + [r["character_id"] for r in slots],
            )
            selected = next(
                (r for r in slots if r["character_id"] == main_character_id), None
            )
            if selected:
                db.execute(
                    "UPDATE account_hero_slots SET character_id=%s WHERE account_id=%s AND slot=%s",
                    (row["leader_id"], account_id, selected["slot"]),
                )
            db.execute(
                "UPDATE account_hero_rosters SET leader_id=%s,revision=revision+1 WHERE account_id=%s",
                (main_character_id, account_id),
            )
            membership = db.execute(
                "SELECT party_id FROM player_party_members WHERE character_id=%s FOR UPDATE",
                (row["leader_id"],),
            ).fetchone()
            if membership is not None:
                db.execute(
                    "UPDATE player_party_members SET character_id=%s WHERE character_id=%s",
                    (main_character_id, row["leader_id"]),
                )
                db.execute(
                    "UPDATE player_parties SET leader_id=CASE WHEN leader_id=%s THEN %s ELSE leader_id END,"
                    "revision=revision+1 WHERE id=%s",
                    (row["leader_id"], main_character_id, membership["party_id"]),
                )
        return load_roster(db, store, account_id, main_character_id)


def switch_main(store, account_id, generation, main_character_id, hero_id):
    """Atomically change the selected main and swap its real hero slot."""
    if type(hero_id) is not int or hero_id <= 0:
        raise ValueError("Invalid hero switch identity")
    with store.connection() as db:
        _fence(db, store, account_id, generation, main_character_id)
        roster = load_roster(db, store, account_id, main_character_id)
        if hero_id == main_character_id:
            return dict(roster, applied=False)
        slot = next(
            (
                slot
                for slot, hero in zip(roster["slots"], roster["heroes"])
                if hero["id"] == hero_id
            ),
            None,
        )
        if slot is None:
            raise ValueError("Only an active owned hero can become main")
        _idle(db, [main_character_id] + [hero["id"] for hero in roster["heroes"]])
        leader = roster["leader"]
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
            tuple(leader[k] for k in ("map_id", "instance_id", "x", "y", "z"))
            + (hero_id,),
        )
        db.execute(
            "UPDATE account_hero_slots SET character_id=%s WHERE account_id=%s AND slot=%s",
            (main_character_id, account_id, slot),
        )
        db.execute(
            "UPDATE account_hero_rosters SET leader_id=%s,revision=revision+1 WHERE account_id=%s",
            (hero_id, account_id),
        )
        membership = db.execute(
            "SELECT party_id FROM player_party_members WHERE character_id=%s FOR UPDATE",
            (main_character_id,),
        ).fetchone()
        if membership is not None:
            db.execute(
                "UPDATE player_party_members SET character_id=%s WHERE character_id=%s",
                (hero_id, main_character_id),
            )
            db.execute(
                "UPDATE player_parties SET leader_id=CASE WHEN leader_id=%s THEN %s ELSE leader_id END,"
                "revision=revision+1 WHERE id=%s",
                (main_character_id, hero_id, membership["party_id"]),
            )
        from wakfu_server.characters.guild_character import record_presence

        record_presence(db, account_id, generation)
        db.execute(
            "UPDATE sessions SET character_id=%s WHERE account_id=%s AND generation=%s",
            (hero_id, account_id, generation),
        )
        return dict(load_roster(db, store, account_id, hero_id), applied=True)


def augment_party(db, store, members):
    """Virtual native hero rows share their main's account association."""
    result = []
    for member in members:
        result.append(dict(member))
        roster = db.execute(
            "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
            (member["account_id"],),
        ).fetchone()
        if roster is not None and roster["leader_id"] == member["id"]:
            for row in db.execute(
                "SELECT character_id FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                (member["account_id"],),
            ).fetchall():
                hero = store.character(member["account_id"], row["character_id"], db)
                hero["hero_main_id"] = member["id"]
                result.append(hero)
    if len(result) > 6 or len({member["id"] for member in result}) != len(result):
        raise ValueError("Native party including heroes exceeds six unique characters")
    return result


def _ensure_party(db, main_character_id):
    from wakfu_server import player_parties

    party = player_parties._party(db, main_character_id)
    if party is None:
        party = db.execute(
            "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING *",
            (main_character_id,),
        ).fetchone()
        db.execute(
            "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
            (main_character_id, party["id"]),
        )
    return party


def ensure_company_party(store, account_id, generation, main_character_id):
    """Restore a real private party for a saved company under its main lease."""
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, main_character_id)
        db.execute(
            "SELECT account_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        roster = load_roster(db, store, account_id, main_character_id)
        if roster["heroes"]:
            _ensure_party(db, main_character_id)
        return roster
