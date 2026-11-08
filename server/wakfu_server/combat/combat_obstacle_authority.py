"""Native-only obstacle authority qualification; loaded only for owned QI."""
# This branch changes native population semantics only. Arbitrary authority
# callbacks retain the historical full-population invocation order below.
from .combat_ordinary_authority import OrdinaryActorAuthority
from .combat_summon import RegisteredSummonAuthority

_AUTHORITY_READERS = {
    OrdinaryActorAuthority: {
        name: getattr(OrdinaryActorAuthority, name)
        for name in (
            "__call__",
            "properties",
            "_condition_fight_properties",
            "_creation_population",
            "_creation_identity",
            "_creation_facts",
            "_monster_sources",
        )
    },
    RegisteredSummonAuthority: {
        name: getattr(RegisteredSummonAuthority, name)
        for name in (
            "__call__",
            "properties",
            "_condition_fight_properties",
            "_ordinary_view",
            "_fresh_relationships",
        )
    },
}


def _native_authority(authority):
    kind = type(authority)
    if kind is not OrdinaryActorAuthority and kind is not RegisteredSummonAuthority:
        return False
    if kind.__getattribute__ is not object.__getattribute__:
        return False
    fields = vars(authority)
    if any(
        name in fields or getattr(kind, name) is not method
        for name, method in _AUTHORITY_READERS[kind].items()
    ):
        return False
    if kind is RegisteredSummonAuthority:
        return type(
            fields.get("ordinary")
        ) is OrdinaryActorAuthority and _native_authority(fields["ordinary"])
    return True
