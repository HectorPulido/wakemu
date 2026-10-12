"""Select immutable definitions for the actual participant source domain."""


def fight_runtime_catalog(monsters, compiled, *, class_catalog, npc_catalog):
    if compiled is not None:
        return compiled
    # The existing NPC catalog includes class definitions; it grants no books.
    return npc_catalog() if monsters else class_catalog()
