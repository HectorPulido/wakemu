"""Reconcile live company membership without rewriting completed encounters."""
import struct

from psycopg.types.json import Jsonb


def rift_company(db, account_id, selected_id, instance_id):
    """Resolve a live company through its selected account lease and location."""
    rows = db.execute(
        "SELECT c.id,c.account_id FROM characters c JOIN sessions s ON s.account_id=c.account_id "
        "JOIN account_hero_rosters r ON r.account_id=c.account_id "
        "WHERE c.account_id=%s AND s.character_id=%s AND r.leader_id=%s "
        "AND c.instance_id=%s AND (c.id=%s OR EXISTS(SELECT 1 FROM account_hero_slots h "
        "WHERE h.account_id=c.account_id AND h.character_id=c.id))",
        (account_id, selected_id, selected_id, instance_id, selected_id),
    ).fetchall()
    return {row["id"] for row in rows}


def _rift_destination(character, run):
    from wakfu_server import generic_transports

    candidates = []
    for obj in run["catalog"]["objects"]:
        if obj["type"] != "Teleporter" or obj["map_id"] != character["map_id"]:
            continue
        source = generic_transports.source(character["map_id"], obj["id"])
        if source is None:
            continue
        for destination in source["destinations"]:
            if destination["map_id"] == character["map_id"]:
                continue
            result = generic_transports.resolve(
                dict(character, instance_id=0),
                struct.pack(">qiBi", source["id"], destination["destination_id"], 0, 2),
                source_allowed=lambda actor, candidate: True,
            )
            candidates.append(result["destination"])
    unique = {
        tuple(row[key] for key in ("map_id", "x", "y", "z")) for row in candidates
    }
    if len(unique) != 1:
        raise ValueError("Rift companion has no unique authorized exterior destination")
    return dict(zip(("map_id", "x", "y", "z"), unique.pop()))


def reconcile(db, store, account_id, generation, leader, hero, *, joining):
    """Called inside the roster transaction, before slot mutation is committed."""
    from wakfu_server.characters.heroes import _outside_combat
    from wakfu_server.objectives.challenges import is_challenge_instance

    if any(is_challenge_instance(member["instance_id"]) for member in (leader, hero)):
        # The attempt captures its competitors and each return position before
        # entry. A roster mutation would admit an unranked helper or strand a
        # newly activated hero without a return receipt.
        raise ValueError("Leave the weekly challenge before changing active heroes")

    if joining:
        foreign = db.execute(
            "SELECT 1 FROM dungeon_instance_members m JOIN characters c ON c.id=m.character_id "
            "WHERE m.character_id=%s AND m.status='active' AND m.instance_id<>%s AND c.instance_id=m.instance_id "
            "UNION ALL SELECT 1 FROM rift_instances r JOIN characters c ON c.instance_id=r.instance_id "
            "WHERE r.status IN ('entered','running') AND c.id=%s "
            "AND r.members @> %s AND r.instance_id<>%s LIMIT 1",
            (
                hero["id"],
                leader["instance_id"],
                hero["id"],
                Jsonb([hero["id"]]),
                leader["instance_id"],
            ),
        ).fetchone()
        if foreign:
            raise ValueError("Hero belongs to another active instance")

    dungeon = db.execute(
        "SELECT i.* FROM dungeon_instances i JOIN dungeon_instance_members m "
        "ON m.instance_id=i.instance_id WHERE m.character_id=%s AND m.status='active' "
        "AND i.instance_id=%s AND i.status IN ('active','completed') FOR UPDATE OF i",
        (leader["id"], leader["instance_id"]),
    ).fetchone()
    rift = db.execute(
        "SELECT * FROM rift_instances WHERE instance_id=%s FOR UPDATE",
        (leader["instance_id"],),
    ).fetchone()
    destination = None
    if dungeon is not None:
        # Encounter participants are frozen separately. A different account's
        # battle must not prevent this idle company preparing its next fight.
        _outside_combat(db, [leader["id"], hero["id"]])
        if joining:
            # A prior membership whose character has already left its instance
            # cannot remain the unique active admission for this owned hero.
            db.execute(
                "UPDATE dungeon_instance_members SET status='removed',ended_at=%s "
                "WHERE character_id=%s AND status='active' AND instance_id<>%s",
                (store.now(), hero["id"], dungeon["instance_id"]),
            )
            db.execute(
                "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
                "WHERE character_id=%s AND status='pending' AND instance_id<>%s",
                (store.now(), hero["id"], dungeon["instance_id"]),
            )
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) "
                "VALUES(%s,%s,%s,%s,%s,'member') ON CONFLICT(instance_id,character_id) DO UPDATE "
                "SET status='active',ended_at=NULL,session_generation=EXCLUDED.session_generation",
                (
                    dungeon["instance_id"],
                    dungeon["party_id"],
                    hero["id"],
                    generation,
                    dungeon["party_revision"],
                ),
            )
        else:
            from wakfu_server import dungeon_runtime, dungeon_exit

            _, config = dungeon_runtime.configuration_for_instance(
                db, dungeon["instance_id"]
            )
            destination = dungeon_exit.automatic_destination(leader, dungeon, config)
            db.execute(
                "UPDATE dungeon_instance_members SET status='removed',ended_at=%s "
                "WHERE instance_id=%s AND character_id=%s AND status='active'",
                (store.now(), dungeon["instance_id"], hero["id"]),
            )
            db.execute(
                "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
                "WHERE character_id=%s AND status='pending'",
                (store.now(), hero["id"]),
            )
    if rift is not None:
        # Historical reward participants may now be fighting elsewhere.
        _outside_combat(db, [leader["id"], hero["id"]])
        if rift["status"] == "running":
            raise ValueError("Rift combat settlement is still pending")
        if rift["status"] == "entered":
            members = set(rift["members"])
            if joining:
                if hero["level"] < rift["catalog"]["level"]:
                    raise ValueError("Rift companion does not meet its entrance level")
                members.add(hero["id"])
                if len(members) > rift["policy"]["max_members"]:
                    raise ValueError("Rift company exceeds the configured member limit")
            else:
                members.discard(hero["id"])
            db.execute(
                "UPDATE rift_instances SET members=%s,revision=revision+1 WHERE instance_id=%s",
                (Jsonb(sorted(members)), rift["instance_id"]),
            )
        # Terminal members remain the immutable reward roster. Current company
        # membership authorizes only travel, never retrospective rewards.
        if not joining:
            destination = _rift_destination(leader, rift)
    if destination is not None:
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
            tuple(destination[key] for key in ("map_id", "x", "y", "z"))
            + (hero["id"],),
        )
