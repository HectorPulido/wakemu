"""Durable, account-scoped friend, ignore, and DND state.

The session generation is checked and locked for every mutation. Contact IDs
are account IDs (the native request contract), never character IDs.
"""
import re


_CHARACTER_NAME = re.compile(r"[A-Za-z][A-Za-z -]{2,23}\Z")
_RELATIONS = {"friend", "ignore"}


def _identity(account_id, generation):
    if type(account_id) is not int or not 0 < account_id < (1 << 63):
        raise ValueError("Invalid social account")
    if not isinstance(generation, str) or not generation:
        raise ValueError("Invalid social session")


def _relation(relation):
    if relation not in _RELATIONS:
        raise ValueError("Unsupported social contact relation")


def _authorize(store, db, account_id, generation):
    """Fence mutations to the current unexpired account session."""
    lease = db.execute(
        "SELECT generation FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if lease is None:
        raise ValueError("Social session is stale or expired")


def _contact_row(row):
    contact = {
        "account_id": row["contact_account_id"],
        "account_name": row["username"],
        "is_online": row["session_account_id"] is not None,
    }
    if row["character_name"] is not None:
        contact.update(
            character_name=row["character_name"],
            breed_id=row["breed"],
            sex=int(row["sex"]),
        )
        if row["xp"] is not None:
            contact["xp"] = row["xp"]
    return contact


class SocialContacts:
    """PostgreSQL authority for native friends/ignored lists and DND."""

    def __init__(self, store):
        self.store = store

    def _add(self, account_id, generation, relation, character_name):
        _identity(account_id, generation)
        _relation(relation)
        if not isinstance(character_name, str):
            raise ValueError("Contact character name must be text")
        character_name = character_name.strip()
        if not _CHARACTER_NAME.fullmatch(character_name):
            raise ValueError("Invalid contact character name")
        with self.store.connection() as db:
            _authorize(self.store, db, account_id, generation)
            target = db.execute(
                "SELECT a.id AS account_id,a.username AS account_name,ch.id AS character_id,"
                "ch.name AS character_name,ch.breed,ch.sex,cp.xp "
                "FROM characters ch JOIN accounts a ON a.id=ch.account_id "
                "LEFT JOIN character_progression cp ON cp.character_id=ch.id "
                "WHERE ch.name_key=%s AND ch.deleted_at IS NULL",
                (character_name.casefold(),),
            ).fetchone()
            if target is None:
                raise ValueError("Contact character not found")
            if target["xp"] is None:
                raise ValueError("Contact character profile is incomplete")
            if target["account_id"] == account_id:
                raise ValueError("Cannot add your own account as a contact")
            previous = db.execute(
                "SELECT relation FROM account_social_contacts "
                "WHERE owner_account_id=%s AND contact_account_id=%s FOR UPDATE",
                (account_id, target["account_id"]),
            ).fetchone()
            if previous is not None:
                if previous["relation"] != relation:
                    raise ValueError("Account already has the other contact relation")
                changed = False
            else:
                db.execute(
                    "INSERT INTO account_social_contacts "
                    "(owner_account_id,contact_account_id,relation) VALUES(%s,%s,%s)",
                    (account_id, target["account_id"], relation),
                )
                changed = True
            return {
                "account_id": target["account_id"],
                "account_name": target["account_name"],
                "character_name": target["character_name"],
                "breed_id": target["breed"],
                "sex": int(target["sex"]),
                "xp": target["xp"],
                "changed": changed,
            }

    def add_friend(self, account_id, generation, character_name):
        return self._add(account_id, generation, "friend", character_name)

    def add_ignore(self, account_id, generation, character_name):
        return self._add(account_id, generation, "ignore", character_name)

    def _remove(self, account_id, generation, relation, contact_account_id):
        return (
            self._remove_contact(account_id, generation, relation, contact_account_id)
            is not None
        )

    def _remove_contact(self, account_id, generation, relation, contact_account_id):
        _identity(account_id, generation)
        _relation(relation)
        if type(contact_account_id) is not int or not 0 < contact_account_id < (
            1 << 63
        ):
            raise ValueError("Invalid contact account ID")
        with self.store.connection() as db:
            _authorize(self.store, db, account_id, generation)
            row = db.execute(
                "DELETE FROM account_social_contacts WHERE owner_account_id=%s "
                "AND contact_account_id=%s AND relation=%s RETURNING contact_account_id",
                (account_id, contact_account_id, relation),
            ).fetchone()
            if row is None:
                return None
            contact = db.execute(
                "SELECT id AS account_id,username AS account_name FROM accounts WHERE id=%s",
                (row["contact_account_id"],),
            ).fetchone()
            return dict(contact)

    def remove_friend(self, account_id, generation, contact_account_id):
        return self._remove(account_id, generation, "friend", contact_account_id)

    def remove_ignore(self, account_id, generation, contact_account_id):
        return self._remove(account_id, generation, "ignore", contact_account_id)

    def remove_friend_contact(self, account_id, generation, contact_account_id):
        """Remove and return the exact account identity for native ACK 719."""
        return self._remove_contact(
            account_id, generation, "friend", contact_account_id
        )

    def remove_ignore_contact(self, account_id, generation, contact_account_id):
        """Remove and return account identity for native ACK 765."""
        return self._remove_contact(
            account_id, generation, "ignore", contact_account_id
        )

    def toggle_do_not_disturb(self, account_id, generation):
        """Toggle the emulated account setting behind native empty-body 12449."""
        _identity(account_id, generation)
        with self.store.connection() as db:
            _authorize(self.store, db, account_id, generation)
            row = db.execute(
                "INSERT INTO account_social_preferences(account_id,do_not_disturb) "
                "VALUES(%s,true) ON CONFLICT(account_id) DO UPDATE SET "
                "do_not_disturb=NOT account_social_preferences.do_not_disturb "
                "RETURNING do_not_disturb",
                (account_id,),
            ).fetchone()
            return row["do_not_disturb"]

    def do_not_disturb(self, account_id):
        if type(account_id) is not int or not 0 < account_id < (1 << 63):
            raise ValueError("Invalid social account")
        with self.store.connection() as db:
            row = db.execute(
                "SELECT do_not_disturb FROM account_social_preferences WHERE account_id=%s",
                (account_id,),
            ).fetchone()
        return False if row is None else row["do_not_disturb"]

    def snapshot(self, account_id, generation):
        """Return a lease-fenced complete account friend/ignore bootstrap."""
        _identity(account_id, generation)
        with self.store.connection() as db:
            _authorize(self.store, db, account_id, generation)
            rows = db.execute(
                "SELECT c.relation,c.contact_account_id,a.username,s.account_id AS session_account_id,"
                "ch.name AS character_name,ch.breed,ch.sex,cp.xp "
                "FROM account_social_contacts c JOIN accounts a ON a.id=c.contact_account_id "
                "LEFT JOIN sessions s ON s.account_id=a.id AND s.expires_at>%s "
                "LEFT JOIN characters ch ON ch.id=s.character_id AND ch.account_id=a.id "
                "AND ch.deleted_at IS NULL "
                "LEFT JOIN character_progression cp ON cp.character_id=ch.id "
                "WHERE c.owner_account_id=%s ORDER BY c.relation,a.username_key",
                (self.store.now(), account_id),
            ).fetchall()
            preferences = db.execute(
                "SELECT do_not_disturb FROM account_social_preferences WHERE account_id=%s",
                (account_id,),
            ).fetchone()
        result = {"friends": [], "ignored": [], "do_not_disturb": False}
        if preferences is not None:
            result["do_not_disturb"] = preferences["do_not_disturb"]
        for row in rows:
            result["friends" if row["relation"] == "friend" else "ignored"].append(
                _contact_row(row)
            )
        return result

    def bootstrap_payload(self, account_id, generation):
        from wakfu_server.social_wire import encode_friend_lists

        snapshot = self.snapshot(account_id, generation)
        return encode_friend_lists(snapshot["friends"], snapshot["ignored"])

    def private_chat_block_reason(self, sender_account_id, recipient_account_id):
        """Return native private-chat denial 102 (DND) or 103 (ignored)."""
        for value in (sender_account_id, recipient_account_id):
            if type(value) is not int or not 0 < value < (1 << 63):
                raise ValueError("Invalid private-chat account")
        if sender_account_id == recipient_account_id:
            return None
        with self.store.connection() as db:
            preferences = db.execute(
                "SELECT do_not_disturb FROM account_social_preferences WHERE account_id=%s",
                (recipient_account_id,),
            ).fetchone()
            if preferences is not None and preferences["do_not_disturb"]:
                return 102
            ignored = db.execute(
                "SELECT 1 FROM account_social_contacts WHERE owner_account_id=%s "
                "AND contact_account_id=%s AND relation='ignore'",
                (recipient_account_id, sender_account_id),
            ).fetchone()
        return 103 if ignored is not None else None
