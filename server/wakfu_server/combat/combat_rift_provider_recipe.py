"""Fixed constructors for captured native Rift operation callback owners.

Return source references to the enclosing graph encoder; never encode owners in
an independent graph, which would lose aliases with Fight and source snapshots.
"""
from types import MethodType

from .combat_input_observation import InputReplayMismatch
from .combat_expiration_provider import OwnedExpirationFactory

FIELDS = ("turn_start_provider", "turn_end_provider", "expiration_runtime_factory")
_EXPIRATION_FIELDS = frozenset(
    ("characters", "monsters", "decks", "actor_id", "fight_start", "area_callbacks")
)
_ORACLE_FIELDS = frozenset(
    (
        "runtime",
        "characters",
        "monsters",
        "companions",
        "decks",
        "excluded_decks",
        "viewer_id",
        "flags",
        "outcome_features_provider",
    )
)
_EXPIRATION_METHODS = {
    "turn_start_provider": OwnedExpirationFactory.turn_start,
    "turn_end_provider": OwnedExpirationFactory.turn_end,
}


class ProviderRecipeError(InputReplayMismatch):
    """Unsupported diagnostic authority, never a rejected gameplay action."""


def capture_providers(runtime):
    """Capture only exact native callback owners and actual provider aliases."""
    from .combat_npc_reproduction import _sdk_modules

    oracle_module, _, _ = _sdk_modules()
    oracle_type = oracle_module.NativeOracle
    owners, providers, owner_ids, provider_ids = [], {}, {}, {}
    for field in FIELDS:
        provider = getattr(runtime, field)
        if provider is None:
            providers[field] = None
            continue
        if id(provider) in provider_ids:
            providers[field] = dict(alias=provider_ids[id(provider)])
            continue
        provider_ids[id(provider)] = field
        if type(provider) is OwnedExpirationFactory:
            if field != "expiration_runtime_factory":
                raise ProviderRecipeError("Expiration callable in incompatible field")
            owner, method, kind = provider, "__call__", "expiration"
        elif type(provider) is MethodType:
            owner = provider.__self__
            if type(
                owner
            ) is OwnedExpirationFactory and provider.__func__ is _EXPIRATION_METHODS.get(
                field
            ):
                kind, method = "expiration", provider.__func__.__name__
            elif (
                type(owner) is oracle_type
                and field in FIELDS[:2]
                and provider.__func__
                is getattr(
                    oracle_module,
                    {
                        "turn_start_provider": "_GC_ORACLE_START",
                        "turn_end_provider": "_GC_ORACLE_END",
                    }[field],
                )
            ):
                kind, method = "oracle", provider.__func__.__name__
            else:
                raise ProviderRecipeError("Unsupported native boundary method")
        else:
            raise ProviderRecipeError("Unsupported native boundary provider")
        if id(owner) not in owner_ids:
            fields = vars(owner)
            if kind == "expiration":
                if (
                    set(fields) != _EXPIRATION_FIELDS
                    or type(fields["fight_start"]) is not bool
                    or type(fields["area_callbacks"]) is not bool
                ):
                    raise ProviderRecipeError("Unsupported expiration owner state")
                row = dict(kind=kind, fields=dict(fields))
            else:
                free = fields.get("runtime") is None
                expected = _ORACLE_FIELDS | (
                    {"_native_boundary_fight_id"} if free else set()
                )
                if (
                    set(fields) != expected
                    or fields["outcome_features_provider"] is not None
                    or (not free and fields["runtime"] is not runtime)
                    or oracle_module.native_boundary_fight_id(owner) != runtime.fight.id
                ):
                    raise ProviderRecipeError("Unsupported oracle owner state")
                for name, constant in (
                    ("live_start_boundary", "_GC_ORACLE_START"),
                    ("live_end_boundary", "_GC_ORACLE_END"),
                    ("start_boundary", "_GC_ORACLE_START_IMPL"),
                    ("end_boundary", "_GC_ORACLE_END_IMPL"),
                    ("factory", "_GC_ORACLE_FACTORY"),
                ):
                    if getattr(oracle_type, name) is not getattr(
                        oracle_module, constant
                    ):
                        raise ProviderRecipeError(
                            "Oracle lifecycle implementation differs"
                        )
                row = dict(kind=kind, fields=dict(fields), runtime_free=free)
            owner_ids[id(owner)] = len(owners)
            owners.append(row)
        providers[field] = dict(owner=owner_ids[id(owner)], method=method)
    return dict(schema=1, owners=owners, providers=providers)


def restore_providers(runtime, payload):
    """Rebuild validated native owners without payload-selected imports/code."""
    from .combat_npc_reproduction import _sdk_modules

    oracle_module, _, _ = _sdk_modules()
    try:
        if payload["schema"] != 1 or set(payload["providers"]) != set(FIELDS):
            raise ProviderRecipeError("Unsupported native provider recipe")
        owners = []
        for row in payload["owners"]:
            fields = row["fields"]
            if row["kind"] == "expiration":
                if set(fields) != _EXPIRATION_FIELDS:
                    raise ProviderRecipeError("Unknown expiration owner fields")
                owner = OwnedExpirationFactory(**fields)
                owner.__dict__.update(fields)
            elif row["kind"] == "oracle":
                free = row["runtime_free"]
                if (
                    type(free) is not bool
                    or set(fields)
                    != _ORACLE_FIELDS
                    | ({"_native_boundary_fight_id"} if free else set())
                    or fields["outcome_features_provider"] is not None
                    or (
                        free and fields["_native_boundary_fight_id"] != runtime.fight.id
                    )
                    or (not free and fields["runtime"] is not runtime)
                ):
                    raise ProviderRecipeError("Invalid captured oracle owner")
                from .combat_ordinary_reinforcement_sources import (
                    current_monster_sources,
                )

                # The native factory itself expands old sources from committed
                # wave births. Validate construction against that same genuine
                # complete roster, then restore the captured source aliases below.
                # No Fight actor, ledger or wave field is altered for admission.
                current_sources = current_monster_sources(
                    runtime.fight,
                    fields["monsters"],
                    map_id=fields["characters"][fields["viewer_id"]].get("map_id"),
                )
                owner = oracle_module.NativeOracle(
                    runtime,
                    characters=fields["characters"],
                    monsters=current_sources,
                    decks=fields["decks"],
                    excluded_decks=fields["excluded_decks"],
                    viewer_id=fields["viewer_id"],
                    flags=fields["flags"],
                )
                if owner.companions != fields["companions"]:
                    raise ProviderRecipeError("Captured companion authority differs")
                if free:
                    owner = oracle_module.native_boundary_owner(owner, runtime)
                    if owner.runtime is not None:
                        raise ProviderRecipeError(
                            "Runtime-free oracle reconstruction failed"
                        )
                owner.__dict__.update(fields)
            else:
                raise ProviderRecipeError("Unknown native provider owner kind")
            owners.append(owner)
        for field in FIELDS:
            binding = payload["providers"][field]
            if binding is None:
                provider = None
            elif set(binding) == {"alias"}:
                if binding["alias"] not in FIELDS[: FIELDS.index(field)]:
                    raise ProviderRecipeError("Invalid native provider alias")
                provider = getattr(runtime, binding["alias"])
            else:
                owner = owners[binding["owner"]]
                method = binding["method"]
                allowed = (
                    {
                        "expiration_runtime_factory": "__call__",
                        "turn_start_provider": "turn_start",
                        "turn_end_provider": "turn_end",
                    }
                    if type(owner) is OwnedExpirationFactory
                    else {
                        "turn_start_provider": "live_start_boundary",
                        "turn_end_provider": "live_end_boundary",
                    }
                )
                if allowed.get(field) != method:
                    raise ProviderRecipeError(
                        "Provider method differs from fixed recipe"
                    )
                provider = owner if method == "__call__" else getattr(owner, method)
            setattr(runtime, field, provider)
        capture_providers(runtime)
    except ProviderRecipeError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as error:
        raise ProviderRecipeError(
            "Incomplete native provider authority: " + str(error)
        ) from error
    return runtime
