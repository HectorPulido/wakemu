"""Shared operation descriptions, without catalog imports or accreditation.

A description records the implementation boundary, not proof that every native
variant works. Bindings record the handlers actually constructed for one runtime;
their existing preparation methods remain the authority for dynamic eligibility.
"""
from dataclasses import dataclass
from types import MappingProxyType
from .combat_damage_contracts import DAMAGE_FAMILIES, HEAL_ELEMENTS
from .combat_subscription_contracts import GROUP_SUBSCRIPTION_FAMILIES


@dataclass(frozen=True)
class DependencySpec:
    kind: str
    parameter_index: int | None
    relation: str = "requires"
    transform: str = "identity"
    fixed_reference: int | None = None


@dataclass(frozen=True)
class OperationContract:
    operation_id: str
    families: tuple[int, ...]
    executor: str
    prerequisites: tuple[str, ...]
    mutations: tuple[str, ...]
    events: tuple[str, ...]
    presentation: tuple[str, ...]
    tests: tuple[str, ...]
    dependencies: tuple[DependencySpec, ...] = ()
    variants: tuple[str, ...] = ()
    variant_validation: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeOperationBinding:
    family: int
    contract: OperationContract | None
    handler: object

    @property
    def status(self):
        # Construction is not semantic, combination or recipient verification.
        return "conditional" if self.contract is not None else "unknown"


@dataclass(frozen=True)
class SupportAssessment:
    status: str
    reasons: tuple[str, ...]
    prerequisites: tuple[str, ...]


def _contract(
    identity,
    families,
    executor,
    prerequisites,
    mutations,
    events,
    presentation,
    tests,
    dependencies=(),
    variants=(),
    variant_validation=(),
):
    return OperationContract(
        identity,
        tuple(families),
        executor,
        tuple(prerequisites),
        tuple(mutations),
        tuple(events),
        tuple(presentation),
        tuple(tests),
        tuple(dependencies),
        tuple(variants),
        tuple(variant_validation),
    )


_CONTRACTS = (
    _contract(
        "cell.null",
        (402,),
        "combat_cell_null.NativeCellNullHandler",
        (
            "registered caster",
            "cell-target invocation without actor recipient",
            "source guards",
            "native timing",
            "owned UID allocation",
        ),
        ("optional caster-owned retained entry",),
        ("native cell application",),
        (
            "13497 cell birth",
            "absent payload actor target",
            "13560 retirement identifies caster owner",
            "stable effect UID",
        ),
        ("test_combat_cell_null", "test_feca_grant_pipeline"),
        variants=(
            "instantaneous",
            "retained",
            "native flags1/17",
            "subscribed clones remain unsupported",
        ),
        variant_validation=(
            "combat_cell_null.NativeCellNullHandler.__call__",
            "combat_stat_effects.null_execution_status",
        ),
    ),
    _contract(
        "spatial.displacement",
        (300, 301, 302, 305, 331, 340, 422),
        "combat_displacement.NativeDisplacementHandler",
        (
            "terrain transitions",
            "occupancy and footprint",
            "carry relationships",
            "transaction RNG for random direction variants",
        ),
        ("position", "orientation", "spatial registration", "passengers"),
        ("native movement boundary", "distinct area departure/arrival events"),
        ("registered recipients", "12613 endpoints", "action identity and queue order"),
        (
            "test_combat_spatial_pilot_displacement",
            "test_combat_displacement_geometry",
            "test_combat_pilot_displacement_reconstruction",
        ),
        variants=(
            "push",
            "pull",
            "caster teleport",
            "target teleport",
            "swap",
            "approach cell",
            "move away from cell",
        ),
    ),
    _contract(
        "resource.loss",
        (48, 55),
        "combat_resource_loss_handler.NativeResourceLossHandler",
        (
            "current/minimum/maximum characteristics",
            "mutability",
            "willpower",
            "rounding RNG",
            "secondary state executor",
        ),
        ("current resource", "secondary state5227"),
        ("resource reactions",),
        ("owned evaluated effect", "characteristic notification", "action identity"),
        (
            "test_combat_resource_loss_handler",
            "test_combat_resource_loss_payment_source",
        ),
        (
            DependencySpec(
                "state",
                None,
                relation="conditional-positive-loss",
                fixed_reference=5227,
            ),
        ),
        variants=(
            "MP48",
            "AP55",
            "willpower bypass flag30",
            "secondary suppression flag19",
            "triggering loss parameter-1",
        ),
    ),
    _contract(
        "resource.maximum",
        (20, 31, 41, 191, 991),
        "combat_maximum_resource.NativeMaximumResourceHandler",
        ("raw/effective bounds", "mutability", "native flags", "owned removal delta"),
        ("maximum characteristic", "optional current characteristic", "owned delta"),
        ("characteristic reactions",),
        ("evaluated effect", "actual clamped delta", "removal identity"),
        ("test_combat_maximum_resource", "test_combat_maximum_ko_resource"),
    ),
    _contract(
        "resource.consume",
        (923,),
        "combat_consume_resources.NativeConsumeResourcesHandler",
        ("native resource costs", "actual resource snapshot", "source guards"),
        ("current resource",),
        ("cost reactions",),
        ("actual paid costs", "resource notifications"),
        ("test_combat_consume_resources",),
    ),
    _contract(
        "state.apply",
        (304,),
        "combat_state_handler.NativeStateHandler",
        (
            "state definition",
            "owned container",
            "native UID allocation",
            "state level context",
            "child registration",
        ),
        ("state manager", "owned carrier310", "subscriptions", "timers"),
        ("state application", "eligible child execution"),
        (
            "state birth before child use",
            "carrier and container identities",
            "removal order",
        ),
        ("test_combat_state_handler", "test_combat_state_retained_migration"),
        (DependencySpec("state", 0, transform="signed-short"),),
        variants=(
            "fixed level",
            "owned spell level",
            "level multiplier",
            "signed level calculation",
            "native resistance chance",
        ),
        variant_validation=(
            "combat_state_mutation.publish_application",
            "combat_state_mutation.replace_carrier",
        ),
    ),
    _contract(
        "state.decurse",
        (321,),
        "combat_state_decurse.NativeStateDecurseHandler",
        ("state definition", "owned state population", "native removal eligibility"),
        ("state level", "owned effects", "subscriptions", "timers"),
        ("state removal and optional reapplication",),
        ("owned removal identities", "remaining state level", "ordered reapplication"),
        ("test_combat_state_decurse", "test_combat_state_decurse_runtime"),
        (DependencySpec("state", 0, relation="removes"),),
    ),
    _contract(
        "fight.property",
        (447,),
        "combat_fight_property.NativeFightPropertyHandler",
        (
            "registered native eGj actor",
            "published fight-property enum",
            "complete property counter authority",
            "property-specific native side effects when required",
            "owned retained-effect lifecycle",
        ),
        ("fight-property counter", "property-specific native side effect"),
        ("native property application and exact owned removal",),
        ("evaluated property enum", "property counter multiplicity", "retained UID"),
        ("test_combat_fight_property",),
        variants=(
            "counter",
            "AP/MP minimum",
            "timeline",
            "visibility",
            "WP notification",
        ),
        variant_validation=(
            "combat_fight_property.NativeFightPropertyHandler.__call__",
        ),
    ),
    _contract(
        "spellbook.morph",
        (933,),
        "combat_morph_handler.NativeMorphHandler",
        (
            "original native morph profile and complete casting dependencies",
            "registered actor and actual retained inverse ownership",
            "native context and phase-1/2 profile-value mutation authority",
        ),
        ("temporary native spellbook", "retained transformation UID"),
        ("native source runner phases",),
        ("original casting UIDs", "native transformation additional fields"),
        ("test_combat_morph_spellbook", "test_equipment_morph_characteristic_parsers"),
    ),
    _contract(
        "world.property",
        (449,),
        "combat_world_property_handler.NativeWorldPropertyHandler",
        (
            "registered native eGj actor",
            "published eHQ world-property enum and mapped fight property",
            "complete world/fight property counter authority",
            "native PN kind and owned retained lifecycle",
        ),
        (
            "world-property counter",
            "mapped fight-property counter",
            "native property presentation",
        ),
        ("owned application and native asymmetric removal",),
        ("world property enum", "retained UID", "evaluated amount"),
        ("test_combat_world_property_handler", "test_combat_world_property_runtime"),
        variants=(
            "eHQ counter",
            "mapped ffe application/removal",
        ),
        variant_validation=(
            "combat_world_property_handler.NativeWorldPropertyHandler.__call__",
        ),
    ),
    _contract(
        "effect.dispel",
        (421,),
        "combat_dispel.NativeDispelHandler",
        (
            "complete retained population",
            "container dispellability",
            "native removal view",
        ),
        ("owned effects", "subscriptions", "timers", "reversed deltas"),
        ("owned removal",),
        ("running effect removal", "container identity"),
        ("test_combat_dispel",),
    ),
    _contract(
        "effect.triggering_final_modifier",
        (1093,),
        "combat_final_modifier.NativeFinalModifierHandler",
        (
            "exact live triggering Qe identity",
            "native faq source and execution-local accumulator",
            "registered native recipient PVs",
            "source guards and native timing",
        ),
        ("triggering runner final modifier",),
        ("scoped native source reaction",),
        ("13497 modifier runner application",),
        ("test_combat_final_modifier", "test_equipment_parity_final_pipeline"),
        variants=("native signed amount parameter pair",),
        variant_validation=(
            "combat_final_modifier.NativeFinalModifierHandler.__call__",
            "combat_final_modifier.update_triggering_final",
        ),
    ),
    _contract(
        "effect.triggering_amount",
        (430,),
        "combat_trigger_value_handler.NativeTriggerValueHandler",
        (
            "exact live triggering Qe identity",
            "native source-owner mutation contract",
            "source guards and native timing",
            "owner-specific float32 arithmetic and rounding RNG",
        ),
        ("triggering runner amount",),
        ("scoped native runner reaction",),
        ("modifier runner suppresses its own PR notification",),
        ("test_combat_trigger_value_handler", "test_combat_trigger_value_modifier"),
        variants=("native mode/amount/replace parameter triple",),
        variant_validation=(
            "combat_trigger_value_handler.NativeTriggerValueHandler.__call__",
            "combat_trigger_value_modifier.mutate_triggering_runner",
        ),
    ),
    _contract(
        "state.cleanup",
        (982,),
        "combat_state_cleanup.NativeStateCleanupHandler",
        (
            "complete retained population",
            "native cleanup parameters",
            "PL.aZY/QF identity",
            "additional data18",
            "same-JVM identity hashes for multiple natural states",
        ),
        ("owned state effects", "subscriptions", "timers"),
        ("owned removal",),
        ("running effect removal", "state ownership"),
        ("test_combat_state_cleanup",),
    ),
    _contract(
        "area.create",
        (308, 314, 315, 339),
        "combat_effect_area.NativeEffectAreaHandler",
        ("area definition", "affiliation", "surface", "native obstacle authority"),
        ("area registration", "owned effects", "subscriptions"),
        ("native area lifecycle",),
        ("area birth before use", "owner and area identities", "expiry and retirement"),
        (
            "test_combat_retained_areas",
            "test_combat_spatial_pilot_area_integration",
            "test_combat_area_movement_plan",
        ),
        (DependencySpec("area", 0),),
    ),
    _contract(
        "spell.grant",
        (649,),
        "combat_spell_grant.NativeSpellGrantHandler",
        ("native spell definition", "owned spellbook", "level context"),
        ("owned spell grant",),
        ("spell grant lifecycle",),
        ("owned grant identity", "grant removal"),
        ("test_combat_spell_grant",),
        (DependencySpec("spell", 2),),
    ),
    _contract(
        "spell.callback",
        (426,),
        "combat_triggered_spell_handler.NativeTriggeredSpellHandler",
        ("native casting table", "callback context", "conditions", "native resources"),
        ("nested eligible spell effects",),
        ("native callback",),
        ("nested action ownership", "queue order"),
        ("test_combat_triggered_spell_runtime",),
        (DependencySpec("spell", 0),),
    ),
    _contract(
        "summon.create",
        (307,),
        "combat_summon_handler.NativeSummonHandler",
        (
            "native actor definition",
            "dummy or real owner",
            "spatial and timeline authority",
        ),
        ("actor registration", "spellbook", "controller", "timeline"),
        ("summon creation",),
        ("entity birth before use", "controller identity", "retirement"),
        ("test_combat_retained_summon307", "test_combat_summon_lifecycle"),
        (DependencySpec("summon", 0, transform="signed-short"),),
        variant_validation=(
            "combat_summon_lifecycle.prepare_registration",
            "combat_summon_lifecycle.register_summon",
            "combat_summon_lifecycle.settle_summons",
        ),
    ),
    _contract(
        "resource.maximum_reduction",
        (56, 57, 192),
        "combat_maximum_resource.NativeMaximumReductionHandler",
        ("raw/effective resource bounds", "mutability", "retention timing"),
        ("maximum resource", "owned reduction delta"),
        ("characteristic reactions",),
        ("actual clamped delta", "owned removal identity"),
        ("test_combat_maximum_resource",),
    ),
    _contract(
        "resource.minimum",
        (877, 1003),
        "combat_minimum_resource.NativeMinimumResourceHandler",
        ("raw/effective minimum and bounds", "mutability", "retention timing"),
        ("minimum characteristic", "optional current characteristic"),
        ("characteristic reactions",),
        ("owned evaluated effect", "removal delta"),
        ("test_combat_minimum_resource", "test_combat_minimum_resource_constructor"),
    ),
    _contract(
        "resource.spell_cost",
        (1065, 1066),
        "combat_spell_cost_effect.NativeSpellCostHandler",
        ("native cost modifier parameters", "owned spell-cost state", "source guards"),
        ("spell cost modifiers",),
        ("cost modifier lifecycle",),
        ("owned evaluated effect", "removal identity"),
        ("test_combat_spell_cost_effect",),
    ),
    _contract(
        "resource.ap_as_mp",
        (808,),
        "combat_ap_as_mp.NativeAPAsMPHandler",
        ("native PA setter notifications", "actual resource snapshot", "source guards"),
        ("AP-to-MP listener", "current MP"),
        ("native AP setter notifications",),
        ("owned evaluated effect", "resource notifications"),
        ("test_combat_resource_pa_notifications",),
    ),
    _contract(
        "spatial.carry",
        (333, 334),
        "combat_carry_handler.NativeCarryHandler",
        ("carry topology", "execution context", "position authority", "area events"),
        ("carrier/passenger relationships", "position", "spatial registration"),
        ("native carry and release lifecycle",),
        ("carry relationships", "registered actors", "release order"),
        ("test_combat_pilot_carry_reconstruction",),
    ),
)


# These families are supplied by the published native registry at the caller's
# boundary. Importing this module must not load catalogs or duplicate their IDs.
_CONTRACTS += (
    _contract(
        "resource.maximum_percentage",
        (986,),
        "combat_maximum_resource.NativePercentageHPHandler",
        ("native PA bounds/percentage/current", "owned timing and source guards"),
        ("additive maximum percentage", "optional protected current", "owned inverse"),
        ("native characteristic reactions",),
        ("owned running UID", "evaluated percentage and actual current"),
        ("test_combat_maximum_resource",),
    ),
    _contract(
        "resource.armor",
        (1013,),
        "combat_armor.NativeArmorHandler",
        (
            "native armor mode/element",
            "actual actor stats",
            "player cap authority",
            "transaction RNG",
        ),
        ("armor97", "owned running value"),
        ("native armor/healing reactions",),
        ("owned UID", "actual armor delta", "original removal"),
        ("test_combat_armor",),
    ),
    _contract(
        "spatial.orientation",
        (303,),
        "combat_orientation_effect.NativeOrientationHandler",
        (
            "native orientation mode",
            "actual directions/positions",
            "property authority",
            "transaction RNG",
        ),
        ("actual actor direction", "owned forced-characteristic lifetime"),
        ("native direction publication",),
        ("owned UID", "actual orientation"),
        ("test_combat_orientation_effect",),
    ),
)


CURRENT_RESOURCE = _contract(
    "resource.current",
    (),
    "combat_stat_handler.NativeStatHandler",
    (
        "native characteristic registry row",
        "current/minimum/maximum snapshot",
        "mutability",
        "native timing and source guards",
    ),
    ("current characteristic", "owned actual delta"),
    ("native characteristic reactions",),
    ("evaluated effect", "retained identity when applicable", "actual reversal delta"),
    ("test_combat_stat_handler", "test_combat_resource_pa_notifications"),
    variants=("eWQ", "eWR", "eXE null execution"),
    variant_validation=(
        "combat_stat_handler.NativeStatHandler.__call__",
        "native registry runner/stat/flags and actual context required",
    ),
)
FORCED_RESOURCE = _contract(
    "resource.forced",
    (),
    "combat_force_characteristic.NativeForcedCharacteristicHandler",
    ("native eYO registry row", "characteristic bounds", "native execution guards"),
    ("forced characteristic", "owned delta"),
    ("native characteristic reactions",),
    ("evaluated effect", "owned removal identity"),
    ("test_combat_forced_characteristic",),
    variant_validation=(
        "combat_force_characteristic.NativeForcedCharacteristicHandler.__call__",
        "native eYO registry row and actual context required",
    ),
)
SET_CURRENT_RESOURCE = _contract(
    "resource.set_current",
    (),
    "combat_set_current_characteristic.NativeSetCurrentCharacteristicHandler",
    (
        "native set-current registry row",
        "current/minimum/maximum snapshot",
        "mutability",
    ),
    ("fixed current characteristic", "measured setter delta"),
    ("native characteristic reactions",),
    ("evaluated effect", "measured reversal delta"),
    ("test_combat_set_current_characteristic",),
    variant_validation=(
        "combat_set_current_characteristic.NativeSetCurrentCharacteristicHandler._row",
        "combat_set_current_characteristic.NativeSetCurrentCharacteristicHandler._calculate",
    ),
)

DAMAGE_APPLICATION = _contract(
    "damage.apply",
    (),
    "combat_damage_handler.NativeDamageHandler",
    (
        "native selected actor or registered HP-owning area",
        "active fight and current actor",
        "complete native stat/bounds/frozen/footprint snapshots",
        "DamageExecutionContext",
        "native parameters and flags",
        "authoritative rounding and block RNG",
        "retained event/value context when applicable",
    ),
    (
        "target HP",
        "source barrier100",
        "target armor97",
        "target virtual HP92",
        "owned running effect when retained",
    ),
    ("native L1/L2/L3 runner phases", "damage reactions and death lifecycle"),
    (
        "registered source and target",
        "evaluated actual damage and absorption",
        "running UID/base/container identity",
        "native delivery order",
        "owned retirement",
    ),
    (
        "test_combat_damage_handler",
        "test_combat_damage_healing",
        "test_combat_retained_damage",
        "test_combat_vitality_migration",
    ),
    variants=(
        "ordinary elemental",
        "stasis917",
        "light1083",
        "partial area native no-op",
        "registered HP-owning area",
        "retained and triggered",
    ),
    variant_validation=(
        "combat_damage_handler.NativeDamageHandler._calculate",
        "combat_damage_handler.NativeDamageHandler._damage_parameters",
        "combat_damage_healing.damage_amount",
        "combat_vitality_execution.plan_damage_consumption",
        "combat_vitality_execution.apply_damage_consumption",
    ),
)

HEALING_APPLICATION = _contract(
    "healing.apply",
    (),
    "combat_healing_handler.NativeHealingHandler",
    (
        "native selected actor or verified partial area",
        "active fight and current actor",
        "complete native stat/bounds/frozen snapshots",
        "HealingExecutionContext",
        "verified native flags and target-life guard",
        "native healing resistance bounds",
        "authoritative rounding RNG",
        "event/value context when applicable",
    ),
    (
        "target HP",
        "target virtual HP",
        "healing resistance and native reactions",
        "owned running effect when retained",
    ),
    ("native runner phases", "healing reactions"),
    (
        "registered source and target",
        "actual HP plus virtual HP restored without overflow",
        "running UID/base/container identity",
        "native delivery order",
        "owned retirement",
    ),
    (
        "test_combat_healing_handler",
        "test_combat_healing_effect",
        "test_combat_damage_healing",
        "test_combat_vitality_migration",
    ),
    variants=(
        "eXv24 without elemental mastery",
        "elemental healing",
        "light1084",
        "undead context",
        "partial area native no-op",
        "retained and triggered",
    ),
    variant_validation=(
        "combat_healing_handler.NativeHealingHandler._calculate",
        "combat_damage_healing.healing_amount",
        "combat_vitality_execution.plan_healing_consumption",
        "combat_vitality_execution.apply_healing_consumption",
    ),
)

GROUP_EXECUTION = _contract(
    "effect.group",
    (),
    "combat_effect_dispatch.EffectDispatcher",
    (
        "native group mode",
        "ordered children",
        "variant-specific callback authority",
        "native eVt context for dynamic or retained variants",
    ),
    ("eligible nested effect mutations",),
    ("native child execution order",),
    ("parent/container identities", "ordered child effects", "queue order"),
    ("test_combat_effect_dispatch", "test_combat_retained_groups"),
    variants=(
        "ordered",
        "relative probability",
        "random",
        "multiple target",
        "cell",
        "symmetry",
        "team repeat",
        "value transfer",
        "dynamic level",
        "distance",
    ),
)


# Retention is a capability applied to leaf and group operations, not a family.
RETAINED_EXECUTION = _contract(
    "lifecycle.retained",
    (),
    "combat_retained_runtime.NativeRetainedRuntime",
    (
        "complete owned population",
        "subscription masks",
        "native trigger context",
        "PN/PL container",
        "timer and delay queue authority",
    ),
    ("running effects", "subscriptions", "timers", "delayed queue", "owned deltas"),
    ("eligible native events", "expiration", "owned removal"),
    (
        "birth before activation",
        "stable effect/container UID",
        "queue and removal ordering",
    ),
    (
        "test_combat_retained_handler_interface",
        "test_combat_retained_groups",
        "test_combat_retained_damage",
        "test_combat_retained_areas",
        "test_combat_state_retained_migration",
    ),
    variant_validation=(
        "combat_retained_mutation.plan_group_retirement",
        "combat_retained_mutation.retire_group",
        "combat_retained_mutation.retire_stat",
    ),
)

TURN_EXECUTION = _contract(
    "lifecycle.turn",
    (),
    "combat_turn_boundary.execute_turn_delivery",
    (
        "native recipient participation",
        "ordered event channels",
        "turn suppression policy",
        "current turn context",
    ),
    ("eligible reaction effects",),
    ("native start/end/regeneration channels",),
    ("source and recipient identities", "ordered reaction delivery"),
    ("test_combat_lifecycle_boundaries", "test_combat_turn_boundary_context"),
    variants=("start", "end", "regeneration"),
    variant_validation=("combat_turn_boundary.prepare_turn_delivery",),
)

EXPIRATION_EXECUTION = _contract(
    "lifecycle.expiration",
    (),
    "combat_expiration_boundary.prepare_expiration_order",
    (
        "native clock context",
        "complete owned timer population",
        "outer effect resolution boundary",
    ),
    ("due owned effect population",),
    ("ordered native expiration",),
    ("owned removal identity", "expiration packet order"),
    ("test_combat_lifecycle_boundaries", "test_combat_timed_expiration"),
    variant_validation=(
        "combat_expiration_boundary.collect_expiration_due",
        "combat_expiration_boundary.order_expiration_due",
    ),
)

DEATH_RECONCILIATION = _contract(
    "lifecycle.death",
    (),
    "combat_death_reconciliation.settle_deaths_shared",
    (
        "native in-play authority",
        "complete actor population",
        "timeline policy",
        "settled summon retirement",
        "wave victory policy",
    ),
    ("timeline", "turn successor", "fight phase and winner"),
    ("native death reconciliation", "conditional next turn", "conditional victory"),
    ("timeline removal identity", "turn and victory ordering"),
    ("test_combat_lifecycle_boundaries", "test_combat_qi_death_lifecycle"),
    variant_validation=("combat_death_reconciliation.prepare_death_reconciliation",),
)

DELIVERY_PUBLICATION = _contract(
    "delivery.publication",
    (),
    "combat_delivery_boundary.native_packets",
    (
        "accepted private preparation",
        "live session leases",
        "collective ACK fence",
        "complete settlement roster",
        "durable storage transaction boundary",
    ),
    ("prepared publication batch", "ACK preparation", "private recovery snapshot"),
    ("ordered recipient publication", "collective release", "recovery"),
    (
        "native packet shape and order",
        "recipient membership",
        "turn ACK identity",
        "reconnect snapshot",
        "idempotent owner settlement",
    ),
    ("test_combat_delivery_boundary", "test_combat_delivery_reproduction"),
    variant_validation=(
        "combat_delivery_boundary.accepted_ack",
        "combat_delivery_boundary.prepare_reconnect",
        "combat_delivery_boundary.settlement_batches",
    ),
)

ENTRY_EXECUTION = _contract(
    "execution.entry",
    (),
    "combat_entry_executor.execute_entry_roots",
    (
        "native adapter admission",
        "authoritative source snapshot",
        "private fight preview",
        "owned native costs and RNG",
        "explicit player/NPC/summon/weapon policy",
    ),
    ("ordered private root execution", "sealed transaction"),
    ("native root context", "player-only paid-cost events when applicable"),
    ("native action identity", "prepared packet order", "single later commit"),
    (
        "test_combat_entry_executor",
        "test_combat_entry_scope_failures",
        "test_combat_entry_summons",
        "test_combat_spell_transaction",
        "test_combat_ordinary_npc_spellbook",
        "test_combat_weapon",
    ),
    variants=("player", "npc", "summon.player", "summon.npc", "weapon"),
    variant_validation=(
        "combat_entry_executor.entry_route",
        "combat_entry_executor.private_entry_preview",
        "combat_entry_executor.seal_entry_transaction",
    ),
)

OPERATIONS = MappingProxyType(
    {
        entry.operation_id: entry
        for entry in (
            *_CONTRACTS,
            RETAINED_EXECUTION,
            CURRENT_RESOURCE,
            FORCED_RESOURCE,
            SET_CURRENT_RESOURCE,
            GROUP_EXECUTION,
            DAMAGE_APPLICATION,
            HEALING_APPLICATION,
            TURN_EXECUTION,
            EXPIRATION_EXECUTION,
            DEATH_RECONCILIATION,
            DELIVERY_PUBLICATION,
            ENTRY_EXECUTION,
        )
    }
)
_BY_FAMILY = {}
for _entry in _CONTRACTS:
    for _family in _entry.families:
        if _family in _BY_FAMILY:
            raise ValueError("Duplicate operation family")
        _BY_FAMILY[_family] = _entry
FAMILY_OPERATIONS = MappingProxyType(_BY_FAMILY)
del _BY_FAMILY


def operation_for_family(
    family, *, characteristic_registry=None, set_current_families=()
):
    if type(family) is not int:
        return None
    contract = FAMILY_OPERATIONS.get(family)
    if contract is not None:
        return contract
    if family in DAMAGE_FAMILIES:
        return DAMAGE_APPLICATION
    if family in HEAL_ELEMENTS:
        return HEALING_APPLICATION
    if characteristic_registry is not None:
        rows = characteristic_registry.get("effects", characteristic_registry)
        row = rows.get(str(family))
        if row is not None:
            runner = row.get("runner")
            if runner in ("eWQ", "eWR", "eXE"):
                return CURRENT_RESOURCE
            if runner == "eYO":
                return FORCED_RESOURCE
    if family in set_current_families:
        return SET_CURRENT_RESOURCE
    if family in GROUP_SUBSCRIPTION_FAMILIES:
        return GROUP_EXECUTION
    return None


def dependency_specs(family):
    contract = operation_for_family(family)
    if contract is not None:
        return contract.dependencies
    # Installed eZq/eZn constructs faB; eHI.cmY is fixed profile2349.
    # Structural references remain known even before an execution contract is
    # independently qualified for the operation.
    if family == 994:
        return (DependencySpec("summon", None, fixed_reference=2349),)
    return ()


def assess_operation(
    effect,
    *,
    characteristic_registry=None,
    set_current_registry=None,
    runtime_bindings=None,
):
    """Describe static support without executing or replacing native eligibility.

    Parameter counts below are raw coefficient-pair counts from the named
    executors. Published characteristic contracts instead count evaluated
    parameters, hence their explicit multiplication by two. A valid shape is
    only conditional: flags, criteria, targets and contexts remain authoritative
    at the existing eligible execution boundary.
    """
    if not isinstance(effect, dict) or type(effect.get("effect_class")) is not int:
        return SupportAssessment("unknown", ("Missing native effect family",), ())
    family = effect["effect_class"]
    set_rows = None
    if set_current_registry is not None:
        set_rows = set_current_registry.get("effects", set_current_registry)
    contract = operation_for_family(
        family,
        characteristic_registry=characteristic_registry,
        set_current_families=() if set_rows is None else tuple(map(int, set_rows)),
    )
    if contract is None:
        return SupportAssessment(
            "unknown", ("Native family has no shared operation description",), ()
        )
    prerequisites = contract.prerequisites
    if (
        runtime_bindings is not None
        and family not in runtime_bindings
        and contract is not GROUP_EXECUTION
    ):
        return SupportAssessment(
            "unsupported",
            ("Actual runtime did not construct this handler",),
            prerequisites,
        )
    parameters = effect.get("parameters")
    if not isinstance(parameters, (tuple, list)):
        return SupportAssessment(
            "unknown", ("Missing native raw parameter facts",), prerequisites
        )
    counts = None
    source = None
    if contract is DAMAGE_APPLICATION:
        counts, source = (
            2,
            4,
            6,
        ), "combat_damage_parameters.interpret_damage_parameters"
    elif contract is CURRENT_RESOURCE and characteristic_registry is not None:
        rows = characteristic_registry.get("effects", characteristic_registry)
        row = rows[str(family)]
        parameter_contract = row.get("parameter_contract", {})
        if not isinstance(parameter_contract, dict):
            return SupportAssessment(
                "unknown",
                ("Missing native characteristic parameter contract",),
                prerequisites,
            )
        supported = parameter_contract.get("supported_counts")
        if isinstance(supported, (tuple, list)) and all(
            type(n) is int for n in supported
        ):
            counts = tuple(n * 2 for n in supported)
            source = (
                "native characteristic registry parameter_contract.supported_counts"
            )
        if row.get("runner") in ("eWQ", "eWR") and row.get("fixed_stat_id") is None:
            if len(parameters) < 6:
                return SupportAssessment(
                    "unsupported",
                    ("Dynamic native characteristic requires third parameter",),
                    prerequisites,
                )
    elif contract is FORCED_RESOURCE:
        counts, source = (0, 2, 4, 6), "combat_force_characteristic.forced_parameters"
    elif contract is SET_CURRENT_RESOURCE:
        if set_rows is None:
            return SupportAssessment(
                "unknown", ("Missing native set-current registry facts",), prerequisites
            )
        row = set_rows[str(family)]
        if row.get("runner") != "eWX" or row.get("numeric_kind") != 0:
            return SupportAssessment(
                "unsupported", ("Unsupported native eWX registry row",), prerequisites
            )
        if len(parameters) % 2:
            return SupportAssessment(
                "unsupported", ("Malformed native eWX parameter pairs",), prerequisites
            )
    elif family == 402:
        masks = effect.get("target_masks")
        flags = effect.get("native_effect_flags")
        if (
            not isinstance(masks, (tuple, list))
            or len(masks) != 7
            or not all(
                value is None
                or (
                    isinstance(value, (tuple, list))
                    and all(type(member) is int for member in value)
                )
                for value in masks
            )
            or not isinstance(flags, (tuple, list))
            or not all(type(flag) is int for flag in flags)
        ):
            return SupportAssessment(
                "unknown", ("Missing native cell-null mask/flag facts",), prerequisites
            )
        if any(masks[:6]):
            return SupportAssessment(
                "unsupported",
                ("Native subscribed cell-null clones are unaudited",),
                prerequisites,
            )
        if set(flags) - {1, 17}:
            return SupportAssessment(
                "unsupported",
                ("Native cell-null flags outside audited1/17",),
                prerequisites,
            )
        if len(parameters) % 2:
            return SupportAssessment(
                "unsupported",
                ("Malformed native cell-null parameter pairs",),
                prerequisites,
            )
    elif family in (48, 55):
        if len(parameters) < 2 or len(parameters) % 2:
            return SupportAssessment(
                "unsupported",
                ("Native eVZ requires nonempty parameter pairs",),
                prerequisites,
            )
    elif family in (20, 31, 41, 191, 991):
        counts, source = (
            6,
        ), "combat_maximum_resource.NativeMaximumResourceHandler.__call__"
    elif family in (56, 57, 192):
        counts, source = (
            2,
            4,
            6,
            8,
        ), "combat_maximum_resource.NativeMaximumReductionHandler"
    elif family in (877, 1003):
        counts, source = (
            2,
            4,
        ), "combat_minimum_resource.NativeMinimumResourceHandler.__call__"
    elif family in (923, 1065, 1066):
        counts, source = (4,), contract.executor
    elif family == 430:
        if len(parameters) < 6 or len(parameters) % 2:
            return SupportAssessment(
                "unsupported",
                ("Native eZL requires at least three parameter pairs",),
                prerequisites,
            )
        counts, source = None, contract.executor
    elif family in (449, 1093):
        counts, source = (2,), contract.executor
    elif family == 321:
        counts, source = (
            2,
            4,
        ), "combat_state_decurse.NativeStateDecurseHandler._parameters"
    elif family == 447:
        if len(parameters) < 2 or len(parameters) % 2:
            return SupportAssessment(
                "unsupported",
                ("Native eWt property operation requires its first parameter pair",),
                prerequisites,
            )
    elif family == 304:
        if len(parameters) % 2 or len(parameters) < 6:
            return SupportAssessment(
                "unsupported",
                ("Native state applicator requires at least three parameter pairs",),
                prerequisites,
            )
    if counts is not None and len(parameters) not in counts:
        return SupportAssessment(
            "unsupported",
            (f"Raw parameter count {len(parameters)} outside {counts}: {source}",),
            prerequisites,
        )
    reason = "Native variant shape requires actual flags, guards, targeting and execution context"
    if contract is GROUP_EXECUTION:
        reason = "Internal dispatcher group path requires native group callback/context authority"
    return SupportAssessment("conditional", (reason,), prerequisites)


def bind_runtime_contracts(
    handlers, *, characteristic_registry=None, set_current_families=()
):
    """Freeze actual constructed routes, including unmodeled native families."""
    return MappingProxyType(
        {
            family: RuntimeOperationBinding(
                family,
                operation_for_family(
                    family,
                    characteristic_registry=characteristic_registry,
                    set_current_families=set_current_families,
                ),
                handler,
            )
            for family, handler in handlers.items()
        }
    )
