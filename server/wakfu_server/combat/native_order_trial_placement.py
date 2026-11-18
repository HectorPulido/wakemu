"""Checked placement SELF publisher for the finite native order constructor.

Only a source-qualified enabled mode may initialize its original native
programs. This scope preserves placement and does not relax ordinary states.
"""

from contextlib import contextmanager
from contextvars import ContextVar

_scope = ContextVar("native_order_trial_placement", default=None)
# Original bounded aNv/aZF state-and-root digests; no complete catalog hashing.
SOURCES = {
    3044: "86e7c4a321b7d5b281bf52cca76be253f5e3c591ed42a107b821e514e074aafa",
    3049: "204b20dd0827b6316191c543164118ddadea78a5e3439ac2c229fddbe9281685",
    3050: "1ed1d898a2e47a46c60465574fa0c2154d87936aea1cdfc26405b2c10b4d8e9f",
    3051: "7250901e10c964d6e63ac52918cb63e0e7917a8c6c707be4fecba7ca42b98eea",
    3052: "c91d3e7b3473cbc5e2fcd31183ec05bc9a787b556673c33dbc25f6fe8cde7e38",
    3053: "2783e0acfa624356259a5eb9b9836369c09480793460c664d8fafea4cd25fe9c",
    3054: "e35c3e5814fbf3086028a9f21003332156b0d94b3cb49889880e71fd05f1d315",
    3055: "8f06e0aa0a20082b19f12102236a7bd73088d46a77d09280f13baf5292a20caa",
    3056: "d110e2db05458dd914a9fa11ae8ed92355c089d50fe2ebaecc1eb60539a62c63",
    3057: "8e14b4dba0ab80b396215fef98611eb2026f641416610c61c63413e244651daa",
    3058: "337b943b3f3f76c8e59bd74a78bc6625d2b22167e1a05813e0edd936766e27d1",
    3059: "a26c5b7611292eebb3229c6593f385c930e571872a7d6a5bcfbe59ce79c3ee87",
    3060: "cd126e5c7d066a7c2c96decbafa9ed654902380ae3f86609c1839514ca18cfc0",
}


@contextmanager
def initialization_scope(fight, dispatcher, proof, character, *, capability):
    from wakfu_server import native_order_trial_admission as admission
    from .native_order_trial_encounter import policy_for
    from hashlib import sha256
    import json

    value = admission.validate(capability)
    policy = policy_for(fight)
    actor = fight.actors.get(getattr(proof, "owner_id", None))
    source = value["sources"].get(getattr(proof, "mode", None))
    if (
        policy is None
        or type(proof) is not admission.Admission
        or value["enabled"] is not True
        or proof.generation is None
        or fight.phase != "placement"
        or actor is None
        or actor.hp <= 0
        or actor.controlled is not True
        or actor.team != policy.player_team
        or (policy.player_team, policy.npc_team) != (1, 0)
        or dispatcher.native_state_handler.fight is not fight
        or dispatcher.native_retention.fight is not fight
        or source is None
        or proof.profile_sha256 != admission.digest(value)
        or proof.profile_id != value["id"]
        or proof.descriptor_sha256 != source["descriptor_sha256"]
        or proof.source_id != source["object_id"]
        or proof.source_map_id != source["map_id"]
        or proof.hard_mode is not (proof.mode == "hard")
        or (
            policy.owner_id,
            policy.account_id,
            policy.instance_id,
            policy.encounter_id,
            policy.mode,
            policy.source_sha256,
            policy.admission_sha256,
            policy.map_id,
        )
        != (
            proof.owner_id,
            proof.account_id,
            proof.instance_id,
            fight.id,
            proof.mode,
            proof.source_sha256,
            proof.profile_sha256,
            value["context"]["map_id"],
        )
        or (
            character.get("id"),
            character.get("account_id"),
            character.get("instance_id"),
            character.get("map_id"),
        )
        != (proof.owner_id, proof.account_id, proof.instance_id, policy.map_id)
        or actor.owner_id != proof.account_id
    ):
        raise ValueError("Order placement requires its enabled typed native source")
    catalog = dispatcher.native_state_handler.catalog
    for reference, expected in SOURCES.items():
        definition = catalog["states"][str(reference)]
        roots = {
            str(root): {
                key: value
                for key, value in catalog["effects"][str(root)].items()
                if key != "native_timing_checks"
            }
            for root in definition["effect_ids"]
        }
        # Release packaging adds original sampled timing checks. They attest
        # the retained timing definition and do not alter this native program.
        actual = sha256(
            json.dumps(
                {"state": definition, "roots": roots},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        if actual != expected:
            raise ValueError("Original order placement state source changed")
    descendants = {}
    for reference in SOURCES:
        pending = list(catalog["states"][str(reference)]["effect_ids"])
        seen = set()
        while pending:
            child = pending.pop()
            if child in seen:
                continue
            seen.add(child)
            pending.extend(catalog["effects"][str(child)]["children"])
        descendants[reference] = frozenset(seen)
    token = _scope.set((fight, actor.id, proof, policy, catalog, descendants))
    try:
        yield
    finally:
        _scope.reset(token)


def _current(fight, source_id, target_id):
    from .native_order_trial_encounter import policy_for

    scope = _scope.get()
    if (
        scope is None
        or scope[0] is not fight
        or fight.phase != "placement"
        or source_id != target_id
        or target_id != scope[1]
        or policy_for(fight) != scope[3]
    ):
        return None
    actor = fight.actors.get(target_id)
    if actor is None or not actor.controlled or actor.hp <= 0:
        return None
    return scope


def application_authorized(fight, source_id, target_id, reference, level):
    scope = _current(fight, source_id, target_id)
    if scope is None:
        return False
    if (reference, level) in ((3049, 1), (3044, 1)):
        return True
    if (reference, level) == (3052, 1):
        return scope[2].hard_mode
    if reference not in SOURCES or reference in (3044, 3049, 3052):
        return False
    from .native_order_trial_selection import placement_authorized

    if placement_authorized(fight, source_id, target_id, reference, level):
        return True
    from .native_order_trial_presentation import desired

    selected = desired(fight)
    from dataclasses import asdict

    document = getattr(fight, "native_order_trial", None)
    return (
        selected is not None
        and document["admission"] == asdict(scope[2])
        and not document["events"]
        and document["state"] == document["initial"]
        and selected[1].get(reference) == level
    )


def stat_context(fight, invocation):
    # Native global1001 listeners have null target during registration; this
    # admits only their exact retained player-state roots, never execution.
    if invocation.target_id is None and invocation.state_uid is not None:
        scope = _current(fight, invocation.caster_id, invocation.caster_id)
        if scope is not None and invocation.reference in (118951, 119030):
            from .combat_native_container import resolve_state_container

            parent = resolve_state_container(fight, invocation.state_uid)
            expected = 3044 if invocation.reference == 118951 else 3052
            row = scope[4]["effects"][str(invocation.reference)]
            return (
                parent.reference == expected
                and parent.level == 1
                and parent.caster_id == parent.target_id == scope[1]
                and (expected != 3052 or scope[2].hard_mode)
                and tuple(row["target_masks"][5] or ()) == (1001,)
            )
    scope = _current(fight, invocation.caster_id, invocation.target_id)
    if scope is None:
        return False
    from .native_order_trial_selection import placement_stat_context

    if placement_stat_context(fight, invocation):
        return True
    if invocation.state_uid is None:
        return False
    from .combat_native_container import resolve_state_container

    parent = resolve_state_container(fight, invocation.state_uid)
    return (
        application_authorized(
            fight, parent.caster_id, parent.target_id, parent.reference, parent.level
        )
        and invocation.reference in scope[5][parent.reference]
    )


def selection_context_authorized(fight, dispatcher, proof):
    scope = _current(fight, proof.owner_id, proof.owner_id)
    return (
        scope is not None
        and scope[2] == proof
        and dispatcher.native_state_handler.catalog is scope[4]
        and dispatcher.native_state_handler.fight is fight
        and dispatcher.native_retention.fight is fight
    )
