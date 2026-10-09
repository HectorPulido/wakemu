"""Durable player membership, independent of fights and monster groups.

Invitations bind selected session generations. Disconnect does not dissolve
membership; an invitation must still have both live sessions when answered.
Native dispatch/delivery is kept separate from these transactions.
"""
import uuid


def _policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='player_party_policy'"
    ).fetchone()
    value = row["value"] if row else None
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] != 1
        or type(value.get("max_members")) is not int
        or not 2 <= value["max_members"] <= 6
        or type(value.get("invitation_seconds")) is not int
        or not 1 <= value["invitation_seconds"] <= 300
    ):
        raise ValueError("Invalid player party policy")
    return value


def _lock_members(db, identities):
    # Shared ascending order prevents opposing invitations from deadlocking.
    for identity in identities:
        if type(identity) is not int or not 0 < identity < 2**63:
            raise ValueError("Invalid player party member")
    for identity in sorted(set(identities)):
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"player-party-member:{identity}",),
        )


def _party(db, character_id):
    return db.execute(
        "SELECT p.* FROM player_parties p JOIN player_party_members m "
        "ON m.party_id=p.id WHERE m.character_id=%s FOR UPDATE OF p",
        (character_id,),
    ).fetchone()


def dissolve(db, party_id):
    """Remove live membership while retaining referenced dungeon ownership.

    The caller holds the party row lock. Referenced identities remain as
    leaderless historical parties; unreferenced parties retain normal deletion.
    """
    retained = db.execute(
        "SELECT 1 FROM dungeon_instances WHERE party_id=%s LIMIT 1", (party_id,)
    ).fetchone()
    if retained is None:
        db.execute("DELETE FROM player_parties WHERE id=%s", (party_id,))
    else:
        db.execute("DELETE FROM player_party_members WHERE party_id=%s", (party_id,))
        db.execute(
            "UPDATE player_parties SET leader_id=NULL,revision=revision+1 WHERE id=%s",
            (party_id,),
        )


def cleanup_dungeon_solo(db, party_id):
    """Remove an unchanged internally created singleton after its last return.

    Caller holds the party lock. Social expansion permanently clears the
    origin flag so shrinking later cannot erase a real group.
    """
    party = db.execute(
        "SELECT leader_id,dungeon_solo FROM player_parties WHERE id=%s", (party_id,)
    ).fetchone()
    if party is None or party["dungeon_solo"] is not True:
        return None
    members = db.execute(
        "SELECT character_id FROM player_party_members WHERE party_id=%s", (party_id,)
    ).fetchall()
    if len(members) != 1 or members[0]["character_id"] != party["leader_id"]:
        return None
    if (
        db.execute(
            "SELECT 1 FROM dungeon_instance_members WHERE party_id=%s AND status='active' LIMIT 1",
            (party_id,),
        ).fetchone()
        is not None
    ):
        return None
    identity = members[0]["character_id"]
    db.execute(
        "DELETE FROM player_party_invitations WHERE inviter_id=%s OR invitee_id=%s",
        (identity, identity),
    )
    dissolve(db, party_id)
    return {"party_id": party_id, "removed": [identity], "leader_id": None}


def invite(store, account_id, generation, character_id, target_id):
    if target_id == character_id:
        raise ValueError("Cannot invite yourself")
    with store.connection() as db:
        _lock_members(db, (character_id, target_id))
        store.lock_character(db, account_id, generation, character_id)
        policy = _policy(db)
        target = db.execute(
            "SELECT generation FROM sessions WHERE character_id=%s "
            "AND expires_at>%s",
            (target_id, store.now()),
        ).fetchone()
        if target is None:
            raise ValueError("Party target is offline")
        if _party(db, target_id) is not None:
            raise ValueError("Party target already belongs to a group")
        party = _party(db, character_id)
        if party is not None:
            if party["leader_id"] != character_id:
                raise ValueError("Only the party leader may invite")
            count = db.execute(
                "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                (party["id"],),
            ).fetchone()["n"]
            if count >= policy["max_members"]:
                raise ValueError("Player party is full")
        token = uuid.uuid4()
        db.execute(
            "INSERT INTO player_party_invitations VALUES(%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(inviter_id,invitee_id) DO UPDATE SET token=EXCLUDED.token,"
            "inviter_generation=EXCLUDED.inviter_generation,"
            "invitee_generation=EXCLUDED.invitee_generation,expires_at=EXCLUDED.expires_at",
            (
                token,
                character_id,
                target_id,
                generation,
                target["generation"],
                store.now(policy["invitation_seconds"]),
            ),
        )
    return str(token)


def answer(store, account_id, generation, character_id, token, accepted):
    if type(accepted) is not bool:
        raise ValueError("Invalid invitation answer")
    try:
        token = uuid.UUID(str(token))
    except (ValueError, AttributeError) as error:
        raise ValueError("Invalid invitation token") from error
    with store.connection() as db:
        initial = db.execute(
            "SELECT inviter_id,invitee_id FROM player_party_invitations "
            "WHERE token=%s",
            (token,),
        ).fetchone()
        if initial is None or initial["invitee_id"] != character_id:
            raise ValueError("Unknown owned party invitation")
        _lock_members(db, (initial["inviter_id"], character_id))
        store.lock_character(db, account_id, generation, character_id)
        invitation = db.execute(
            "SELECT * FROM player_party_invitations WHERE token=%s FOR UPDATE", (token,)
        ).fetchone()
        if (
            invitation is None
            or invitation["invitee_generation"] != generation
            or invitation["expires_at"] <= store.now()
        ):
            raise ValueError("Party invitation is expired or stale")
        if not accepted:
            db.execute("DELETE FROM player_party_invitations WHERE token=%s", (token,))
            return None
        inviter = invitation["inviter_id"]
        if (
            db.execute(
                "SELECT 1 FROM sessions WHERE character_id=%s AND generation=%s "
                "AND expires_at>%s",
                (inviter, invitation["inviter_generation"], store.now()),
            ).fetchone()
            is None
        ):
            raise ValueError("Party inviter is offline or stale")
        if _party(db, character_id) is not None:
            raise ValueError("Already belongs to a player party")
        policy = _policy(db)
        party = _party(db, inviter)
        if party is None:
            party = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING *",
                (inviter,),
            ).fetchone()
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (inviter, party["id"]),
            )
        if party["leader_id"] != inviter:
            raise ValueError("Inviter no longer leads the party")
        count = db.execute(
            "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
            (party["id"],),
        ).fetchone()["n"]
        if count >= policy["max_members"]:
            raise ValueError("Player party is full")
        db.execute(
            "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
            (character_id, party["id"]),
        )
        db.execute(
            "UPDATE player_parties SET revision=revision+1,dungeon_solo=false WHERE id=%s",
            (party["id"],),
        )
        db.execute(
            "DELETE FROM player_party_invitations WHERE invitee_id=%s", (character_id,)
        )
        return party["id"]


def change_member(
    store, account_id, generation, character_id, party_id, target_id, *, transfer=False
):
    """Removal includes self-leave; leadership passes to oldest remaining member."""
    if type(transfer) is not bool:
        raise ValueError("Invalid party membership action")
    with store.connection() as db:
        _lock_members(db, (character_id, target_id))
        store.lock_character(db, account_id, generation, character_id)
        party = _party(db, character_id)
        if party is None or type(party_id) is not int or party["id"] != party_id:
            raise ValueError("Not a member of the requested player party")
        if (transfer or target_id != character_id) and party[
            "leader_id"
        ] != character_id:
            raise ValueError("Only the party leader may change other members")
        target = db.execute(
            "SELECT character_id FROM player_party_members WHERE party_id=%s "
            "AND character_id=%s",
            (party_id, target_id),
        ).fetchone()
        if target is None:
            raise ValueError("Target is not in this player party")
        if transfer:
            db.execute(
                "UPDATE player_parties SET leader_id=%s,revision=revision+1 WHERE id=%s",
                (target_id, party_id),
            )
            db.execute(
                "DELETE FROM player_party_invitations WHERE inviter_id=%s",
                (character_id,),
            )
            return {"party_id": party_id, "leader_id": target_id, "removed": []}
        db.execute(
            "DELETE FROM player_party_members WHERE character_id=%s", (target_id,)
        )
        db.execute(
            "DELETE FROM player_party_invitations WHERE inviter_id=%s OR invitee_id=%s",
            (target_id, target_id),
        )
        remaining = db.execute(
            "SELECT character_id FROM player_party_members WHERE party_id=%s "
            "ORDER BY joined_order",
            (party_id,),
        ).fetchall()
        removed = [target_id]
        if len(remaining) < 2:
            removed.extend(row["character_id"] for row in remaining)
            if remaining:
                survivor = remaining[0]["character_id"]
                db.execute(
                    "DELETE FROM player_party_invitations WHERE inviter_id=%s OR invitee_id=%s",
                    (survivor, survivor),
                )
            dissolve(db, party_id)
            leader = None
        else:
            leader = (
                remaining[0]["character_id"]
                if party["leader_id"] == target_id
                else party["leader_id"]
            )
            db.execute(
                "UPDATE player_parties SET leader_id=%s,revision=revision+1 WHERE id=%s",
                (leader, party_id),
            )
        return {"party_id": party_id, "leader_id": leader, "removed": removed}


def snapshot(store, account_id, generation, character_id):
    """Consistent owned roster for reconnect; does not create membership."""
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        party = _party(db, character_id)
        if party is None:
            return None
        members = db.execute(
            "SELECT c.id,c.account_id,c.name,c.level,c.hp,c.max_hp,c.breed,c.sex,c.health_dead,m.joined_order "
            "FROM player_party_members m JOIN characters c ON c.id=m.character_id "
            "WHERE m.party_id=%s ORDER BY m.joined_order",
            (party["id"],),
        ).fetchall()
        if not any(row["id"] == character_id for row in members):
            return None
        return {
            "party_id": party["id"],
            "leader_id": party["leader_id"],
            "revision": party["revision"],
            "members": [dict(row) for row in members],
        }


def expire(store, *, limit=128):
    """Bounded cleanup, safe against invitations being answered/replaced."""
    if type(limit) is not int or not 1 <= limit <= 1024:
        raise ValueError("Invalid invitation cleanup limit")
    with store.connection() as db:
        return db.execute(
            "WITH expired AS (SELECT token FROM player_party_invitations "
            "WHERE expires_at<=%s ORDER BY expires_at LIMIT %s FOR UPDATE SKIP LOCKED) "
            "DELETE FROM player_party_invitations i USING expired e WHERE i.token=e.token",
            (store.now(), limit),
        ).rowcount


def answer_native(store, account_id, generation, character_id, request):
    """Resolve Ow1031 against a pending invitation owned by this session.

    The wire context is the inviter character ID, never a party ID. The native
    normal-player response has no second name; display strings cannot confer
    authority. answer() revalidates both generations and membership atomically.
    """
    inviter = request["inviter_id"]
    if type(inviter) is not int or not 0 < inviter < 2**63 or request["second_name"]:
        raise ValueError("Invalid native party invitation context")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        invitation = db.execute(
            "SELECT i.token,c.name FROM player_party_invitations i "
            "JOIN characters c ON c.id=i.inviter_id WHERE i.inviter_id=%s "
            "AND i.invitee_id=%s AND i.invitee_generation=%s AND i.expires_at>%s",
            (inviter, character_id, generation, store.now()),
        ).fetchone()
        if invitation is None or invitation["name"] != request["first_name"]:
            raise ValueError("Unknown owned native party invitation")
        token = invitation["token"]
    return answer(
        store, account_id, generation, character_id, token, request["accepted"]
    )
