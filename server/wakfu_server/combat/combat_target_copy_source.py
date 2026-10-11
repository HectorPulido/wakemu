"""Server-owned raw target records for the otherwise null native frL hook.

UIDs and encounter order come from existing published inventory/bPD producers,
never from a reconstructed or sorted spell-level map.
"""


def target_copy_raw_records(fight, target, authority):
    from .combat_native_actor_lookup import native_actor
    from .combat_morph_spellbook import morph_record
    from .combat_spell_grant import granted_spells
    from .combat_spell_grant_book import removed_raw_uids
    from .combat_spell_level import NativeSpellBook
    from .combat_runtime_adapter import NativeActorAuthority

    if native_actor(fight, target.id) is not target:
        raise ValueError("Missing actual target-copy actor identity")
    metadata = authority(fight, target)
    if not isinstance(metadata, NativeActorAuthority):
        raise ValueError("Missing native target-copy actor authority")
    ordinary = getattr(authority, "ordinary", authority)
    book = metadata.native_spellbook
    if not isinstance(book, NativeSpellBook) or not isinstance(book.levels, dict):
        raise ValueError("Missing actual target-copy current book")
    morph = morph_record(fight, target.id)
    if morph is not None:
        records = [(ref, ref, level) for ref, level in morph["levels"].items()]
        producer = "big.bPu.current_raw_book"
    elif target.id in getattr(ordinary, "characters", {}):
        from wakfu_server.spells import owned_spell_records

        source = ordinary.characters[target.id]
        if (
            source.get("id") != target.id
            or metadata.is_player is not True
            or source.get("native_spellbook") is not None
        ):
            raise ValueError("Missing actual target-copy character inventory")
        records = list(owned_spell_records(source))
        producer = "owned.character.sy"
    elif target.id in getattr(ordinary, "monsters", {}):
        from wakfu_server.monsters import native_abilities

        source = ordinary.monsters[target.id]
        if (
            source.get("id") != target.id
            or metadata.is_player is not False
            or source.get("native_spellbook") is not None
        ):
            raise ValueError("Missing actual target-copy ordinary bPD source")
        records = [
            (row["spell_id"], row["spell_id"], row["spell_level"])
            for row in native_abilities(source["ref"], target.effective_level)
        ]
        producer = "owned.ordinary.bPD"
    else:
        from .combat_summon_spellbook import actor_action_book

        source = actor_action_book(target)
        records = [
            (row["uid"], row["reference"], row["level"]) for row in source["actions"]
        ]
        producer = "owned.registered.bPD"
    removed = removed_raw_uids(fight, target.id)
    records = [row for row in records if row[0] not in removed]
    seen = set()
    for uid, ref, level in records:
        if (
            type(uid) is not int
            or not -(1 << 63) <= uid < (1 << 63)
            or type(ref) is not int
            or not 0 < ref < (1 << 31)
            or type(level) is not int
            or not -32768 <= level <= 32767
            or uid in seen
        ):
            raise ValueError("Invalid actual target-copy raw book record")
        seen.add(uid)
    for row in granted_spells(fight, target.id).values():
        if row["uid"] not in seen:
            records.append((row["uid"], row["reference"], row["level"]))
            seen.add(row["uid"])
    # Progression may be clamped by native definitions; take levels only from
    # the separately proved current book while retaining actual raw UID order.
    if {ref for _, ref, _ in records} != set(book.levels):
        raise ValueError("Target-copy raw inventory disagrees with current book")
    return tuple((uid, ref, book.levels[ref]) for uid, ref, _ in records), producer
