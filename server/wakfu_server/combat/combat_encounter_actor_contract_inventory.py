"""Source-known actor facts, explicitly separate from scene admission.

These declarations are a recovery inventory, not active encounter contracts.
Maps, owners, terminal predicates and their native operation producers have not
been recovered for these exact breed references. A shared name is not a join.
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ActorIntegrationDeclaration:
    reference: int
    initial_states: tuple[int, ...]
    protection_effects: tuple[int, ...]
    selected_producer_spell: int | None = None
    immutable_hp_floor: int | None = None
    map_id: int | None = None
    native_owner_reference: int | None = None
    terminal_effect_reference: int | None = None
    terminal_policy: str | None = None
    unresolved: tuple[str, ...] = (
        "exact scene admission and actor identity binding",
        "authored owner/controller and participation roles",
        "authenticated scene terminal predicate and native retirement source",
    )

    @property
    def admitted(self):
        return (
            not self.unresolved
            and type(self.map_id) is int
            and type(self.terminal_effect_reference) is int
            and bool(self.terminal_policy)
        )

    def record(self):
        return dict(asdict(self), admitted=self.admitted)


DECLARATIONS = {
    1723: ActorIntegrationDeclaration(1723, (1128, 1137, 7998), (57571,)),
    1860: ActorIntegrationDeclaration(
        1860,
        (731,),
        (283135,),
        selected_producer_spell=2859,
        unresolved=(
            "exact wave-controller scene binding; Cucupidon1855/1860/5614 differ",
            "wave cadence, area and opponent birth ownership",
            "authenticated score/exit and native terminal retirement source",
        ),
    ),
    **{
        reference: ActorIntegrationDeclaration(
            reference, (2958,), (116520, 116522), immutable_hp_floor=1
        )
        for reference in (3143, 3144, 3145, 3146, 3147)
    },
    3510: ActorIntegrationDeclaration(
        3510,
        (3339,),
        (146400, 146401),
        selected_producer_spell=4738,
        immutable_hp_floor=1,
    ),
    **{
        reference: ActorIntegrationDeclaration(reference, (3523,), (153124,))
        for reference in (3595, 3596, 3597)
    },
}


def actor_integration_declaration(reference):
    return DECLARATIONS.get(reference)


def require_actor_integration_admitted(reference):
    declaration = actor_integration_declaration(reference)
    if declaration is None or not declaration.admitted:
        raise ValueError("Original actor scene contract remains unresolved")
    return declaration
