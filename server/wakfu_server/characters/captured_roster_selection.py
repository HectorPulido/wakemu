"""Owned cnw/13571 selection: ddO -> eHU.eH(byte), persisted server policy."""
from dataclasses import replace
import struct
from .captured_roster import OwnedCapturedRoster
from .captured_roster_store import load, save


def request_owner(body):
    if not isinstance(body, bytes) or len(body) != 9:
        raise ValueError("Invalid native Symbiot selection payload")
    owner_id, slot = struct.unpack(">qb", body)
    if owner_id <= 0 or not 0 <= slot < 10:
        raise ValueError("Invalid owned Symbiot selection")
    return owner_id


def owned_request_character(
    store, account_id, generation, selected, owner_id, *, fight=None
):
    """Resolve a controlled hero only inside the live shared action boundary."""
    if selected.get("account_id") != account_id:
        raise ValueError("Foreign selected Symbiot account")
    if owner_id == selected.get("id"):
        return selected
    actor = fight.actors.get(owner_id) if fight is not None else None
    if (
        fight is None
        or fight.phase != "active"
        or fight.current is not actor
        or actor is None
        or actor.controlled is not True
        or actor.owner_id != account_id
        or actor.hp <= 0
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("Symbiot hero is not the current owned combat actor")
    if not store.current_character_session(account_id, generation, selected["id"]):
        raise ValueError("Stale selected Symbiot session")
    owner = store.character(account_id, owner_id)
    if (
        owner.get("id") != owner_id
        or owner.get("account_id") != account_id
        or owner.get("breed") != 2
        or owner.get("deleted_at") is not None
    ):
        raise ValueError("Missing owned Osamodas combat character")
    return owner


def select(store, account_id, character, body, *, fight=None):
    request_owner(body)
    owner_id, slot = struct.unpack(">qb", body)
    if (
        owner_id != character["id"]
        or account_id != character["account_id"]
        or character["breed"] != 2
        or not 0 <= slot < 10
    ):
        raise ValueError("Invalid owned Symbiot selection")
    overlays = (
        getattr(fight, "native_captured_rosters", {}) if fight is not None else {}
    )
    updates = (
        getattr(fight, "native_captured_roster_updates", {})
        if fight is not None
        else {}
    )
    if not isinstance(overlays, dict) or not isinstance(updates, dict):
        raise ValueError("Invalid captured component overlay")
    key = str(owner_id)
    if fight is not None:
        actor = fight.actors.get(owner_id)
        if (
            actor is None
            or actor.controlled is not True
            or actor.owner_id != account_id
        ):
            raise ValueError("Missing owned Symbiot combat actor")
    if fight is not None:
        source = overlays.get(key, updates.get(key, character.get("captured_roster")))
        roster = OwnedCapturedRoster.from_record(source, expected_owner_id=owner_id)
        record = replace(roster, selected_slot=slot).to_record()
        # The existing fight checkpoint transaction persists this mutation queue.
        # Never commit the component independently of its combat checkpoint.
        fight.native_captured_rosters = {**overlays, key: record}
        fight.native_captured_roster_updates = {**updates, key: record}
        return record
    with store.connection() as db:
        with db.transaction():
            owner = db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s "
                "AND breed=2 AND deleted_at IS NULL FOR UPDATE",
                (owner_id, account_id),
            ).fetchone()
            if owner is None:
                raise ValueError("Missing Symbiot character ownership")
            source = overlays.get(key, updates.get(key))
            if source is None:
                source = load(db, character)
            roster = OwnedCapturedRoster.from_record(source, expected_owner_id=owner_id)
            selected = replace(roster, selected_slot=slot)
            save(db, character, selected)
    record = selected.to_record()
    return record
