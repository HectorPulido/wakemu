"""Canonical core-family metadata after retirement of migration selectors.

Backend attribute names describe historical evidence only. Components identify
actual shared source boundaries; they do not select implementations or accredit
native compatibility. Historical engines are reproduced outside this runtime.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class MigrationFamily:
    name: str
    backend_attribute: str
    operation_ids: tuple[str, ...]
    invariants: tuple[str, ...]
    components: tuple[str, ...] = ()


_FAMILIES = (
    MigrationFamily(
        "vitality",
        "native_vitality_backend",
        ("damage.apply", "healing.apply"),
        (
            "native formulas and rounding",
            "absorption order",
            "characteristic bounds",
            "reaction and packet order",
        ),
        components=(
            "combat_vitality_execution",
            "combat_damage_handler",
            "combat_healing_handler",
            "combat_damage_healing",
        ),
    ),
    MigrationFamily(
        "states",
        "native_state_backend",
        ("state.apply", "state.decurse", "state.cleanup"),
        ("owned identity", "replacement order", "native state timing"),
        components=(
            "combat_state_ledger",
            "combat_state_mutation",
            "combat_state_handler",
            "combat_state_decurse",
            "combat_state_cleanup",
        ),
    ),
    MigrationFamily(
        "retained",
        "native_retained_backend",
        ("lifecycle.retained", "effect.dispel"),
        ("subscription masks", "owned removal", "timer cancellation"),
        components=(
            "combat_retained_runtime",
            "combat_retained_mutation",
            "combat_dispel",
        ),
    ),
    MigrationFamily(
        "summons",
        "native_summon_lifecycle_backend",
        ("summon.create",),
        (
            "identity allocation",
            "controller and spellbook",
            "spatial registration",
            "timeline publication",
        ),
        components=(
            "combat_summon_lifecycle",
            "combat_summon_handler",
            "combat_summon_retirement",
        ),
    ),
    MigrationFamily(
        "lifecycle",
        "native_lifecycle_backend",
        ("lifecycle.turn", "lifecycle.expiration", "lifecycle.death"),
        (
            "turn reaction order",
            "expiration order",
            "death reconciliation",
            "victory boundary",
        ),
        components=(
            "combat_turn_events",
            "combat_turn_boundary",
            "combat_timed_expiration",
            "combat_expiration_boundary",
            "combat_state",
            "combat_death_reconciliation",
        ),
    ),
    MigrationFamily(
        "entry",
        "native_entry_backend",
        ("execution.entry",),
        (
            "native eligibility and cost ownership",
            "root order",
            "source identity",
            "single commit and delivery",
        ),
        components=(
            "combat_spell_transaction",
            "combat_npc_spell",
            "combat_weapon",
            "combat_entry_executor",
        ),
    ),
    MigrationFamily(
        "delivery",
        "native_delivery_backend",
        ("delivery.publication",),
        (
            "packet order",
            "collective acknowledgements",
            "reconnect snapshot",
            "reward settlement",
        ),
        components=(
            "combat_delivery_boundary",
            "combat_shared",
            "combat_spectator_snapshot",
        ),
    ),
)

MIGRATION_FAMILIES = MappingProxyType({family.name: family for family in _FAMILIES})


def _family(name):
    try:
        return MIGRATION_FAMILIES[name]
    except (KeyError, TypeError):
        raise ValueError(f"Unknown combat migration family: {name!r}") from None


def operation_contracts(family):
    """Resolve canonical boundary metadata without accrediting native variants.

    Runtime contracts and tooling share these exact descriptors. A dangling
    declaration is a programming error, not an unsupported native spell gate.
    Native eligibility remains with each adapter and effect implementation.
    """
    from .combat_operation_registry import OPERATIONS

    declaration = _family(family)
    try:
        return tuple(OPERATIONS[identity] for identity in declaration.operation_ids)
    except KeyError as error:
        raise ValueError(
            f"Missing canonical combat operation for migration family {family!r}: {error.args[0]!r}"
        ) from None
