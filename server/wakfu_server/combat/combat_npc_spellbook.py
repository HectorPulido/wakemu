"""Actual ordinary bje/bPD ownership for shared spell-level consumers."""
from .combat_spell_level import NativeSpellBook


def ordinary_npc_spellbook(fight, actor, source):
    """Reuse native csd ownership and bPO clamping; never a player deck."""
    from wakfu_server.monsters import native_abilities

    if (
        fight.actors.get(actor.id) is not actor
        or actor.controlled is not False
        or not isinstance(source, dict)
        or source.get("id") != actor.id
        or type(source.get("ref")) is not int
        or source["ref"] <= 0
        or type(actor.effective_level) is not int
    ):
        raise ValueError("Missing actual ordinary NPC spellbook source")
    levels = {}
    for ability in native_abilities(source["ref"], actor.effective_level):
        reference, level = ability["spell_id"], ability["spell_level"]
        if (
            type(reference) is not int
            or not 0 < reference < (1 << 31)
            or type(level) is not int
            or not -32768 <= level <= 32767
            or reference in levels
        ):
            raise ValueError("Invalid complete ordinary NPC spellbook")
        levels[reference] = level
    return NativeSpellBook(levels, False)
