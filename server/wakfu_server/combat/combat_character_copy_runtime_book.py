"""Actual server-owned class inventory supplied to eZw's faC/faE hook.

The installed client frL hook is null. The server supplies its current published
inventory encounter order; this does not assert an unavailable client producer.
"""
from dataclasses import asdict
from .combat_character_copy_book import CopyBookAction, copy_character_book
from .combat_character_copy_metadata import native_copy_book_flags


def copied_class_source_deck(ordinary, actor_id):
    from wakfu_server.spells import validate_deck

    blobs = getattr(ordinary, "deck_blobs", None)
    character = ordinary.characters.get(actor_id)
    if (
        not isinstance(blobs, dict)
        or not isinstance(blobs.get(actor_id), bytes)
        or not isinstance(character, dict)
        or character.get("id") != actor_id
    ):
        raise ValueError("Missing actual source-copy raw fzf deck")
    parsed = validate_deck(blobs[actor_id], character["breed"], character["level"])
    if ordinary.decks.get(actor_id) != frozenset(
        parsed["active"] + parsed["passive"]
    ) or ordinary.deck_caps.get(actor_id) != (
        parsed["level_cap"] if parsed["level_cap"] >= 0 else None
    ):
        raise ValueError("Changed source-copy raw fzf deck authority")
    return parsed


def copied_class_book(fight, caster, authority, *, allocate_uid, definitions):
    from .combat_runtime_adapter import NativeActorAuthority
    from wakfu_server.spells import owned_spell_records
    from .combat_morph_spellbook import morph_record
    from .combat_spell_grant import granted_spells
    from .combat_spell_grant_book import removed_raw_uids

    ordinary = getattr(authority, "ordinary", authority)
    characters, decks = getattr(ordinary, "characters", None), getattr(
        ordinary, "decks", None
    )
    metadata = authority(fight, caster)
    character = None if not isinstance(characters, dict) else characters.get(caster.id)
    if (
        fight.actors.get(caster.id) is not caster
        or not isinstance(character, dict)
        or character.get("id") != caster.id
        or not isinstance(decks, dict)
        or caster.id not in decks
        or not isinstance(metadata, NativeActorAuthority)
        or metadata.native_actor_type != 0
        or metadata.native_is_ehp is not True
    ):
        raise ValueError("Missing actual owned class source-copy inventory")
    deck = copied_class_source_deck(ordinary, caster.id)
    morph = morph_record(fight, caster.id)
    records = (
        list(owned_spell_records(character))
        if morph is None
        else [
            (ref, ref, level)
            for ref, level in morph["levels"].items()
            if ref not in removed_raw_uids(fight, caster.id)
        ]
    )
    known = {uid for uid, _, _ in records}
    for row in granted_spells(fight, caster.id).values():
        if row["uid"] not in known:
            records.append((row["uid"], row["reference"], row["level"]))
            known.add(row["uid"])
    flags = native_copy_book_flags()
    actions = []
    for uid, ref, level in records:
        row, definition = flags.get(str(ref)), definitions.get(str(ref))
        if (
            row is None
            or not isinstance(definition, dict)
            or type(definition.get("maximum_level")) is not int
        ):
            raise ValueError("Missing scoped native copied-class action metadata")
        actions.append(
            CopyBookAction(
                uid,
                ref,
                min(level, definition["maximum_level"]),
                row["native_elO"],
                row["native_elemental_copy"],
                row["native_neutral_copy"],
            )
        )
    from .combat_character_copy_metadata import native_copy_book_document

    limits = native_copy_book_document()
    if (
        type(limits.get("copy_level_minimum")) is not int
        or type(limits.get("copy_level_maximum")) is not int
        or not -32768
        <= limits["copy_level_minimum"]
        <= limits["copy_level_maximum"]
        <= 32767
    ):
        raise ValueError("Missing original MX copied-book level domain")
    cap = deck["level_cap"]
    allocated = []

    def allocate_clone():
        uid = allocate_uid()
        allocated.append(uid)
        return uid

    copied = copy_character_book(
        tuple(actions),
        availability_present=True,
        available_references=tuple(deck["active"]) + tuple(deck["passive"]),
        selector_present=True,
        selector_cap=cap,
        actor_cap=metadata.native_real_level,
        minimum=limits["copy_level_minimum"],
        maximum=limits["copy_level_maximum"],
        allocate_uid=allocate_clone,
    )
    proof = dict(
        producer="server.current_owned_inventory.faC.eZx",
        source_actor_id=caster.id,
        source_actions=[asdict(a) for a in actions],
        copied_actions=[asdict(a) for a in copied],
        allocated_clone_uids=allocated,
        available_references=list(deck["active"]) + list(deck["passive"]),
        selector_cap=cap,
        actor_cap=metadata.native_real_level,
        minimum=limits["copy_level_minimum"],
        maximum=limits["copy_level_maximum"],
    )
    return copied, proof


def install_copied_action_book(actor, copied, proof, *, effect_reference):
    from .combat_summon_spellbook import fresh_action_book

    base = fresh_action_book(2382, actor.effective_level)
    if (
        not isinstance(proof, dict)
        or proof.get("producer") != "server.current_owned_inventory.faC.eZx"
        or not isinstance(copied, tuple)
        or proof.get("copied_actions") != [asdict(a) for a in copied]
        or type(effect_reference) is not int
        or effect_reference <= 0
    ):
        raise ValueError("Missing exact copied action-book constructor proof")
    actions = list(base["actions"])
    used = {row["uid"] for row in actions}
    for action in copied:
        action.validate()
        if action.uid not in used and len(actions) < 80:
            actions.append(
                dict(uid=action.uid, reference=action.reference, level=action.level)
            )
            used.add(action.uid)
    actor.native_character_copy_book_source = dict(
        proof,
        producer="eZw1002.eHI.R.bPl.R",
        profile=2382,
        actor_id=actor.id,
        effect_reference=effect_reference,
        descriptor_level=actor.effective_level,
        base_actions=base["actions"],
        installed_actions=actions,
    )
    actor.native_summon_action_book = dict(
        producer="eZw1002.eHI.R.bPl.R",
        profile=2382,
        descriptor_level=actor.effective_level,
        actions=actions,
    )


def validated_copied_action_book(actor, source):
    from .combat_summon_spellbook import fresh_action_book

    if source.get("native_character_copy_source") == "eZq994.faB.eHI.bPl":
        from .combat_target_copy_runtime_book import validated_target_copied_action_book

        return validated_target_copied_action_book(actor, source)

    proof = getattr(actor, "native_character_copy_book_source", None)
    expected_base = fresh_action_book(source.get("ref"), source.get("level"))
    if (
        not isinstance(proof, dict)
        or proof.get("producer") != "eZw1002.eHI.R.bPl.R"
        or proof.get("actor_id") != actor.id
        or source.get("native_character_copy_source") != "eZw1002.faB.eHI.bPl"
        or source.get("native_copy_source_actor_id") != proof.get("source_actor_id")
        or source.get("native_copy_effect_reference") != proof.get("effect_reference")
        or proof.get("profile") != source.get("ref")
        or proof.get("descriptor_level") != source.get("level")
        or proof.get("base_actions") != expected_base["actions"]
        or type(proof.get("effect_reference")) is not int
        or proof["effect_reference"] <= 0
        or type(proof.get("source_actor_id")) is not int
        or proof["source_actor_id"] <= 0
        or not isinstance(proof.get("copied_actions"), list)
    ):
        raise ValueError("Missing native copied-book source identity")
    copied = tuple(CopyBookAction(**row) for row in proof["copied_actions"])
    for action in copied:
        action.validate()
    originals = tuple(CopyBookAction(**row) for row in proof["source_actions"])
    flags = native_copy_book_flags()
    for original in originals:
        original.validate()
        native = flags.get(str(original.reference))
        if native is None or (
            original.special,
            original.elemental,
            original.neutral,
        ) != (
            native["native_elO"],
            native["native_elemental_copy"],
            native["native_neutral_copy"],
        ):
            raise ValueError("Changed copied source action metadata")
    allocated = iter(proof["allocated_clone_uids"])
    try:
        regenerated = copy_character_book(
            originals,
            availability_present=True,
            available_references=tuple(proof["available_references"]),
            selector_present=True,
            selector_cap=proof["selector_cap"],
            actor_cap=proof["actor_cap"],
            minimum=proof["minimum"],
            maximum=proof["maximum"],
            allocate_uid=lambda: next(allocated),
        )
        exhausted = next(allocated, None) is None
    except (KeyError, TypeError, StopIteration) as error:
        raise ValueError("Incomplete native copied source-book proof") from error
    if regenerated != copied or not exhausted:
        raise ValueError("Changed native copied-book selection or clone identity")
    expected = list(expected_base["actions"])
    used = {row["uid"] for row in expected}
    for action in copied:
        if action.uid not in used and len(expected) < 80:
            expected.append(
                dict(uid=action.uid, reference=action.reference, level=action.level)
            )
            used.add(action.uid)
    book = dict(
        producer="eZw1002.eHI.R.bPl.R",
        profile=source["ref"],
        descriptor_level=source["level"],
        actions=expected,
    )
    if (
        proof.get("installed_actions") != expected
        or actor.native_summon_action_book != book
    ):
        raise ValueError("Changed native copied action-book population")
    return book
