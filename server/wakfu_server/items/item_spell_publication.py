"""Read-only common-spell publication for a loaded account company."""


def account_inventory_packets(store, account_id, generation, selected_character_id):
    """Publish only canonical owned item spells to the current main and heroes."""
    from wakfu_server.account_quest_inventory import load
    from wakfu_server.spells import common_spell_packet, item_spells

    if (
        type(account_id) is not int
        or account_id <= 0
        or type(selected_character_id) is not int
        or selected_character_id <= 0
        or not isinstance(generation, str)
        or not generation
    ):
        raise ValueError("Invalid common-spell publication identity")
    with store.connection() as db:
        # No character hydration: publication must not initialize or modify any
        # character, clock, roster, inventory or lease as a side effect.
        lease = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=%s "
            "AND generation=%s AND expires_at>%s",
            (account_id, generation, store.now()),
        ).fetchone()
        if lease is None or lease["character_id"] != selected_character_id:
            raise ValueError("Expired or changed common-spell publication lease")
        characters = db.execute(
            "SELECT c.id,c.account_id,c.breed,c.level FROM characters c "
            "JOIN sessions s ON s.account_id=c.account_id "
            "WHERE c.account_id=%s AND c.deleted_at IS NULL "
            "AND s.generation=%s AND s.character_id=%s AND s.expires_at>%s "
            "AND (c.id=s.character_id OR EXISTS ("
            "SELECT 1 FROM account_hero_slots h "
            "JOIN account_hero_rosters r USING(account_id) "
            "WHERE h.account_id=c.account_id AND h.character_id=c.id "
            "AND r.leader_id=s.character_id)) "
            "ORDER BY CASE WHEN c.id=s.character_id THEN 0 ELSE 1 END,c.id",
            (account_id, generation, selected_character_id, store.now()),
        ).fetchall()
        if not characters or characters[0]["id"] != selected_character_id:
            raise ValueError(
                "Selected common-spell publication character is unavailable"
            )
        if len(characters) > 3:
            raise ValueError("Invalid active company for common-spell publication")
        inventory = load(db, account_id)
        packets = []
        for row in characters:
            character = dict(row, account_quest_items=inventory)
            if item_spells(character, character["level"]):
                packets.append(common_spell_packet(character))
        return packets
