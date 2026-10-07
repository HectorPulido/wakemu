"""Load every ordinary participant's complete native authority in one snapshot.

The stable world shim passes its Store and encounter, never a projected DTO.
No candidate policy or spell formulas live in this database adapter.
"""
from copy import deepcopy


def load_authorities(runtime, store, monsters, *, viewer_id):
    from wakfu_server.spells import default_deck
    from wakfu_server.builds import catalog_indices

    fight = runtime.fight
    registrations = getattr(fight, "native_summon_registrations", {})
    characters, descriptors, decks, excluded = {}, {}, {}, {}
    with store.connection() as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for identity, actor in sorted(fight.actors.items()):
            if identity in registrations:
                continue
            if actor.controlled:
                if type(actor.owner_id) is not int or actor.owner_id <= 0:
                    raise ValueError("Missing authoritative participant account")
                character = store.character(actor.owner_id, identity, db)
                if (
                    character["id"] != identity
                    or character["account_id"] != actor.owner_id
                ):
                    raise ValueError("Native participant ownership mismatch")
                index = character.get("active_build_index")
                if type(index) is not int:
                    raise ValueError("Missing selected native build identity")
                if index not in catalog_indices(character):
                    raise ValueError("Selected native build is absent")
                build = character.get("builds", {}).get(index)
                # The native catalog always owns permanent build zero, even
                # before its first saved row exists. Keep the complete SQL
                # character unchanged and use its native default deck.
                if build is None and index == 0:
                    stored = ""
                elif isinstance(build, dict):
                    stored = build.get("deck")
                else:
                    raise ValueError("Selected native build is absent")
                if character.get("effective_level") != actor.effective_level:
                    raise ValueError("Selected build level differs from native actor")
                if not isinstance(stored, str):
                    raise ValueError("Missing selected native deck data")
                characters[identity] = deepcopy(character)
                decks[identity] = (
                    bytes.fromhex(stored) if stored else default_deck(character)
                )
                # Current ordinary engine has no excluded-deck source in Store.
                # An explicit empty set matches its server_runtime authority;
                # future sources can be loaded here without altering the shim.
                excluded[identity] = frozenset()
            else:
                descriptor = monsters.get(identity)
                if not isinstance(descriptor, dict) or descriptor.get("id") != identity:
                    raise ValueError("Missing complete native monster descriptor")
                descriptors[identity] = deepcopy(descriptor)
    if viewer_id not in characters:
        raise ValueError("Viewer is not an ordinary participant in this encounter")
    return dict(
        characters=characters,
        monsters=descriptors,
        decks=decks,
        excluded_decks=excluded,
        viewer_id=viewer_id,
        registrations=deepcopy(registrations),
    )
