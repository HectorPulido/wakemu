"""Actual eZp839 borrowed target actions installed through common eHI.R."""
from dataclasses import asdict
from .combat_character_copy_book import CopyBookAction
from .combat_three_spell_copy_book import TargetCopyBookAction, copy_target_book

SOURCE = "eZp839.faB.eHI.bPl"
PRODUCER = "eZp839.eHI.R.bPl.R"


def validated_target_selection(proof, *, definitions, effects, flags):
    if (
        not isinstance(proof, dict)
        or proof.get("producer") not in ("eZp839.faD.actual_target_book", PRODUCER)
        or not isinstance(proof.get("source_actions"), list)
    ):
        raise ValueError("Missing exact native839 borrowed-book source")
    rows = []
    for raw in proof["source_actions"]:
        try:
            action = CopyBookAction(**raw)
            action.validate()
            flag = flags[str(action.reference)]
            definition = definitions[str(action.reference)]
            roots = (
                definition["level_zero_roots"]
                if action.level == 0
                else definition["levels"][action.level - 1][2]
            )
            if action.level < 0:
                raise ValueError("Unsupported negative target-copy level")
            kinds = tuple(effects[str(ref)]["effect_class"] for ref in roots)
            if (action.special, action.elemental, action.neutral) != (
                flag["native_elO"],
                flag["native_elemental_copy"],
                flag["native_neutral_copy"],
            ):
                raise ValueError("Changed native839 action selection flags")
            rows.append(TargetCopyBookAction(action, kinds, action.elemental))
        except (KeyError, TypeError, IndexError) as error:
            raise ValueError(
                "Missing complete native839 action source metadata"
            ) from error
    selected = copy_target_book(rows)
    if proof.get("copied_actions") != [asdict(row) for row in selected]:
        raise ValueError("Changed native839 borrowed UID selection")
    return selected


def _metadata():
    from .combat_native_spell_casting import catalog
    from .combat_npc_attack import npc_runtime_catalog
    from .combat_character_copy_metadata import native_copy_book_flags

    return dict(
        definitions=catalog(),
        effects=npc_runtime_catalog(imported=True).source_effects,
        flags=native_copy_book_flags(),
    )


def install_target_copied_action_book(actor, copied, proof, *, effect_reference):
    from .combat_summon_spellbook import fresh_action_book

    expected = validated_target_selection(proof, **_metadata())
    if copied != expected or type(effect_reference) is not int or effect_reference <= 0:
        raise ValueError("Missing actual839 constructor book identity")
    base = fresh_action_book(1549, actor.effective_level)
    if base["actions"]:
        raise ValueError("Unexpected native1549 intrinsic action population")
    actions = [
        dict(uid=row.uid, reference=row.reference, level=row.level) for row in copied
    ]
    actor.native_character_copy_book_source = dict(
        proof,
        producer=PRODUCER,
        profile=1549,
        actor_id=actor.id,
        effect_reference=effect_reference,
        descriptor_level=actor.effective_level,
        base_actions=[],
        installed_actions=actions,
    )
    actor.native_summon_action_book = dict(
        producer=PRODUCER,
        profile=1549,
        descriptor_level=actor.effective_level,
        actions=actions,
    )


def validated_target_copied_action_book(actor, source):
    proof = getattr(actor, "native_character_copy_book_source", None)
    if (
        not isinstance(proof, dict)
        or proof.get("producer") != PRODUCER
        or source.get("native_character_copy_source") != SOURCE
        or source.get("ref") != 1549
        or proof.get("profile") != 1549
        or proof.get("actor_id") != actor.id
        or proof.get("source_actor_id") != source.get("native_copy_source_actor_id")
        or type(source.get("native_copy_source_actor_id")) is not int
        or proof.get("effect_reference") != source.get("native_copy_effect_reference")
        or type(proof.get("effect_reference")) is not int
        or proof["effect_reference"] <= 0
        or type(source.get("native_copy_effect_reference")) is not int
        or proof.get("descriptor_level") != source.get("level")
        or type(proof.get("source_actor_id")) is not int
        or proof["source_actor_id"] <= 0
    ):
        raise ValueError("Missing exact native839 copied-book provenance")
    selected = validated_target_selection(proof, **_metadata())
    expected = dict(
        producer=PRODUCER,
        profile=1549,
        descriptor_level=source["level"],
        actions=[
            dict(uid=row.uid, reference=row.reference, level=row.level)
            for row in selected
        ],
    )
    if (
        proof.get("base_actions") != []
        or proof.get("installed_actions") != expected["actions"]
        or getattr(actor, "native_summon_action_book", None) != expected
    ):
        raise ValueError("Changed native839 installed borrowed-book population")
    return expected
