"""Exact eWn raw-UID overlay, independent of player progression and deck slots."""
from dataclasses import replace

from .combat_spell_level import NativeSpellBook


def grant_record(fight, actor_id, reference):
    from .combat_spell_grant import granted_spells

    record = granted_spells(fight, actor_id).get(reference)
    if record is None:
        return None
    if (
        not isinstance(record, dict)
        or type(reference) is not int
        or reference <= 0
        or type(record.get("uid")) is not int
        or type(record.get("reference")) is not int
        or record.get("uid") != reference
        or record.get("reference") != reference
        or type(record.get("level")) is not int
        or not 0 <= record["level"] <= 32767
    ):
        raise ValueError("Invalid owned native temporary spell record")
    return record


def removed_raw_uids(fight, actor_id):
    from .combat_morph_spellbook import morph_record

    morph = morph_record(fight, actor_id)
    values = (
        morph["removed_raw_uids"]
        if morph is not None
        else getattr(fight, "native_removed_spell_uids", {}).get(actor_id, set())
    )
    if not isinstance(values, (set, frozenset)) or any(
        type(value) is not int or value <= 0 for value in values
    ):
        raise ValueError("Invalid native removed raw spell UID registry")
    return values


def merged_grant_book(fight, actor_id, book):
    from .combat_spell_grant import granted_spells

    if not isinstance(book, NativeSpellBook):
        raise ValueError("Exact native base spellbook required for temporary grants")
    if book.levels is None:
        if granted_spells(fight, actor_id):
            raise ValueError("Native temporary grant has no owning spellbook")
        return book
    levels = {} if book.levels is None else dict(book.levels)
    # Ordinary player spell UIDs are packed owner/ref; controlled fresh books
    # use raw refs. Native eWn.bbR removes its raw object UID even if it already
    # existed before the grant. It does not remove a player's packed object.
    if not book.player_character:
        for uid in removed_raw_uids(fight, actor_id):
            levels.pop(uid, None)
    for reference in granted_spells(fight, actor_id):
        record = grant_record(fight, actor_id, reference)
        levels.setdefault(reference, record["level"])
    # bjo.dsx points at its separate progression book. Temporary objects do
    # not become progression entries or bypass the actual fzf execution cap.
    return replace(book, levels=levels)


def register_raw_removal(fight, actor_id, reference):
    from .combat_morph_spellbook import morph_record

    morph = morph_record(fight, actor_id)
    if morph is not None:
        morph["removed_raw_uids"].add(reference)
        return
    if not hasattr(fight, "native_removed_spell_uids"):
        fight.native_removed_spell_uids = {}
    fight.native_removed_spell_uids.setdefault(actor_id, set()).add(reference)
