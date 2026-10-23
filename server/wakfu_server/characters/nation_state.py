"""Character citizenship shared by persistence, native identity and chat.

Government offices and battleground participation are separate authorities;
ordinary enrollment never grants either privilege.
"""
import struct


NATION_IDS = frozenset((0, 30, 31, 32, 33, 34))
ENROLLMENT_NATION_IDS = frozenset((30, 31, 32, 33))


def local_selection_request(text):
    if type(text) is not str:
        raise ValueError("Invalid nation selection command")
    parts = text.strip().split()
    if not parts or parts[0].lower() != "!nacion":
        return False
    if len(parts) != 1:
        raise ValueError("Uso: !nacion")
    return True


def selection_packet(populations):
    """cyB14006: native chooser data, without invented government state."""
    if any(
        type(key) is not int
        or key not in NATION_IDS - {0}
        or type(value) is not int
        or value < 0
        for key, value in populations.items()
    ):
        raise ValueError("Invalid nation populations")
    total = sum(populations.values())
    body = bytearray(struct.pack(">i", len(ENROLLMENT_NATION_IDS)))
    for identity in sorted(ENROLLMENT_NATION_IDS):
        fraction = populations.get(identity, 0) / total if total else 0.0
        # nation, treasury, population fraction, governor UTF8 length,
        # territory count, diplomacy count. No government/economy authority
        # currently exists; the public regional initialization is also empty.
        body.extend(struct.pack(">iifiii", identity, 0, fraction, 0, 0, 0))
    return 14006, bytes(body)


def open_selection(store, account_id, generation, character_id):
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        if nation_id(character) != 0:
            raise ValueError("El personaje ya pertenece a una nación.")
        if character["level"] < 1:
            raise ValueError("El personaje no puede elegir nación todavía.")
        rows = db.execute(
            "SELECT n.nation_id,COUNT(*) AS population "
            "FROM character_chat_nations n JOIN characters c ON c.id=n.character_id "
            "WHERE c.deleted_at IS NULL GROUP BY n.nation_id"
        ).fetchall()
        return selection_packet({row["nation_id"]: row["population"] for row in rows})


def nation_id(character):
    value = 0 if character is None else character.get("nation_id", 0)
    if type(value) is not int or value not in NATION_IDS:
        raise ValueError("Invalid character nation")
    return value


def synchro(character):
    nation_id(character)
    # rk: government office, jobs, vote date, opinion, candidacy, PvP rank.
    # Its final byte is the indexed rank identity, not a boolean PvP flag.
    from wakfu_server.national_progression import owned_snapshot

    snapshot = None if character is None else owned_snapshot(character)
    return bytes(26) + bytes((0 if snapshot is None else snapshot.rank_id,))


def load(db, character_id):
    row = db.execute(
        "SELECT nation_id FROM character_chat_nations WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    return nation_id(row)


def decode_enrollment(body):
    # Native crn.aWH writes an int into a six-byte zero-initialized buffer.
    if type(body) is not bytes or len(body) != 6 or body[4:] != bytes(2):
        raise ValueError("Invalid nation enrollment request")
    value = struct.unpack_from(">i", body)[0]
    if value not in ENROLLMENT_NATION_IDS:
        raise ValueError("Invalid nation enrollment choice")
    return value


def enroll(store, account_id, generation, character_id, body):
    chosen = decode_enrollment(body)
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        if nation_id(character) != 0:
            raise ValueError("El personaje ya pertenece a una nación.")
        if character["level"] < 1:
            raise ValueError("El personaje no puede elegir nación todavía.")
        db.execute(
            "INSERT INTO character_chat_nations(character_id,nation_id) VALUES(%s,%s)",
            (character_id, chosen),
        )
        return store.character(account_id, character_id, db)
