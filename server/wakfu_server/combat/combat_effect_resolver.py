"""Common dispatcher resolver: native branch, trigger guards, fcE and XY area.

Callbacks read the current transaction preview on every invocation. Actor kinds
and properties come from authoritative snapshots; cell eligibility needs its
own native policy callback and is never inferred from an empty actor selection.
"""
from .combat_subscription_runners import SUBSCRIPTION_FAMILIES
from dataclasses import dataclass, replace
from .combat_effect_dispatch import EffectInvocation
from .combat_effect_targets import select_native_effect_targets
from .combat_trigger_masks import match_trigger_masks


class UnknownEffectResolution(ValueError):
    pass


@dataclass(frozen=True)
class TriggerEligibility:
    event_bits: tuple[int, ...]
    channel: int
    routing: str
    guards_verified: bool


@dataclass(frozen=True)
class EffectResolutionContext:
    variant_mode: str  # eTG EFFECTS_ONLY / CRITICALS_ONLY / ALL
    delivery: str  # immediate / event
    selection: str  # actors / cell
    eligible: bool  # remaining native application/source guards
    trigger: TriggerEligibility | None = None


def variant_accepts(effect, mode):
    """eTM.h partitions by dd(1), rather than treating variant as an enum.

    Bits beyond1 have unaudited meanings and remain explicit blockers even
    though native dd(1) can partition them. ALL includes both branches.
    """
    variant = effect.get("variant")
    if type(variant) is not int or variant not in (0, 1):
        raise UnknownEffectResolution("Unaudited native variant bits")
    if mode not in ("EFFECTS_ONLY", "CRITICALS_ONLY", "ALL"):
        raise UnknownEffectResolution("Unknown native variant mode")
    return mode == "ALL" or bool(variant & 1) == (mode == "CRITICALS_ONLY")


def application_eligible(effect, context):
    if (
        not isinstance(context, EffectResolutionContext)
        or type(context.eligible) is not bool
    ):
        raise UnknownEffectResolution("Missing authoritative resolution context")
    if context.delivery not in (
        "immediate",
        "event",
        "registration",
    ) or context.selection not in ("actors", "cell"):
        raise UnknownEffectResolution("Unknown native delivery/selection path")
    if not variant_accepts(effect, context.variant_mode) or not context.eligible:
        return False
    masks = effect.get("target_masks")
    if not isinstance(masks, (list, tuple)) or len(masks) != 7:
        raise UnknownEffectResolution("Missing seven native trigger masks")
    if any(
        mask is not None
        and (
            not isinstance(mask, (list, tuple, set, frozenset))
            or any(type(bit) is not int or bit < 0 for bit in mask)
        )
        for mask in masks
    ):
        raise UnknownEffectResolution("Invalid native trigger mask bits")
    if context.delivery == "registration":
        if (
            context.trigger is not None
            or effect.get("_native_group_registration_verified") is not True
            or effect["effect_class"] not in SUBSCRIPTION_FAMILIES
        ):
            raise UnknownEffectResolution(
                "Unverified native retained group registration"
            )
        if not any(masks[index] for index in (0, 1, 3, 4, 5)):
            raise UnknownEffectResolution(
                "Registration requires native Qa.aZN subscription masks"
            )
        return True
    if context.delivery == "immediate":
        if context.trigger is not None:
            raise UnknownEffectResolution("Event context on immediate delivery")
        # Qa.aZN excludes index2: removal events do not defer initial
        # calculation. Index6 emits events rather than subscribing.
        if any(masks[index] for index in (0, 1, 3, 4, 5)):
            raise UnknownEffectResolution(
                "Subscribed effect requires native event delivery"
            )
        return True
    trigger = context.trigger
    if (
        not isinstance(trigger, TriggerEligibility)
        or trigger.guards_verified is not True
    ):
        raise UnknownEffectResolution(
            "Unverified native trigger source/recursion guards"
        )
    action = match_trigger_masks(
        masks,
        event_bits=trigger.event_bits,
        channel=trigger.channel,
        routing=trigger.routing,
    )
    if action == "remove":
        raise UnknownEffectResolution(
            "Removal event must use the owned-effect removal path"
        )
    return action == "apply"


class NativeEffectResolver:
    """Callable contract for EffectDispatcher.resolve(effect, invocation).

    actors(effect,invocation) supplies the complete intended candidate scope
    and caster; native_context(effect,invocation) supplies per-ID fcE metadata.
    context chooses native branch/delivery explicitly. A cell callback must
    validate the native cell selection path; no actor-selection fallback.
    """

    def __init__(
        self,
        *,
        actors,
        native_context,
        context,
        cell_eligible=None,
        caster=None,
        direct_target_policies=None
    ):
        self.actors = actors
        self.native_context = native_context
        self.context = context
        self.cell_eligible = cell_eligible
        self.caster = caster
        self.direct_target_policies = direct_target_policies

    def __call__(self, effect, invocation):
        if not isinstance(invocation, EffectInvocation):
            raise UnknownEffectResolution("Invalid dispatcher invocation")
        context = self.context(effect, invocation)
        if not application_eligible(effect, context):
            return ()
        if context.selection == "cell":
            if self.cell_eligible is None:
                raise UnknownEffectResolution("Missing native cell eligibility policy")
            accepted = self.cell_eligible(effect, invocation)
            if type(accepted) is not bool:
                raise UnknownEffectResolution("Unknown native cell eligibility")
            return (replace(invocation, target_id=None),) if accepted else ()
        return self.candidate_invocations(effect, invocation, direct=True)

    def candidate_invocations(self, effect, invocation, *, direct=False):
        """eZR.a actor selection used by eYE.e, independent of parent bbB."""
        actors = tuple(self.actors(effect, invocation))
        identities = [actor.id for actor in actors]
        if len(set(identities)) != len(identities):
            raise UnknownEffectResolution("Duplicate runtime actor identities")
        caster = (
            self.caster(effect, invocation)
            if self.caster is not None
            else next(
                (actor for actor in actors if actor.id == invocation.caster_id), None
            )
        )
        if caster is None:
            raise UnknownEffectResolution("Missing caster in authoritative actor scope")
        if caster.id != invocation.caster_id:
            raise UnknownEffectResolution(
                "Caster callback changed authoritative source identity"
            )
        if type(invocation.native_explicit_target) is not bool:
            raise UnknownEffectResolution(
                "Explicit native PV argument presence required"
            )
        policy = (
            None
            if self.direct_target_policies is None
            else self.direct_target_policies.get(str(invocation.reference))
        )
        if type(invocation.wakemu_fresh_child_selection) is not bool:
            raise UnknownEffectResolution("Invalid server fresh-child selection policy")
        # Client aZX defaults false and describes replay of an already chosen
        # PV. Server-created children with an explicit relationship selector
        # select that relationship first. Non-point areas also enumerate their
        # occupants before passing a chosen PV to point children. A null/zero/
        # point selector retains the group's intentional transmitted PV.
        selector = effect.get("native_target_selector")
        server_fresh_selection = (
            invocation.wakemu_fresh_child_selection
            and isinstance(selector, dict)
            and selector.get("class") == "fcE"
            and type(selector.get("mask")) is int
            and (
                bool(selector["mask"] & (2 | 4 | 8 | 64 | 128 | 256))
                or (
                    bool(selector["mask"] & 1)
                    and effect.get("area_class") not in (None, "anA", "anD")
                )
            )
        )
        # A transmitted point PV with fcE(self + area) belongs to the
        # triggering recipient. Re-selecting self here loses allied received-
        # healing modifiers: the caster is outside the recipient's point.
        # Keep Qe.g(PV)'s explicit-target contract for this combined selector;
        # a pure self selector still requests the server relationship policy.
        if (
            invocation.native_explicit_target
            and isinstance(selector, dict)
            and selector.get("class") == "fcE"
            and selector.get("mask") == 3
            and effect.get("area_class") == "anD"
        ):
            server_fresh_selection = False
        if (
            direct
            and not server_fresh_selection
            and (
                invocation.native_explicit_target
                or (policy is not None and policy[2] is True)
            )
        ):
            from .combat_direct_target import explicit_native_target

            target_id = explicit_native_target(
                effect, invocation, metadata=self.direct_target_policies
            )
            if target_id is not None:
                # Qe.g(PV) skips amQ/fcE entirely. Criteria, probability and
                # handler fMy guards still execute in the common dispatcher.
                target = next(
                    (actor for actor in actors if actor.id == target_id), None
                )
                return (
                    ()
                    if target is None
                    else (replace(invocation, target_id=target.id),)
                )
        targets = select_native_effect_targets(
            effect,
            caster,
            invocation.cell,
            actors,
            native_context=self.native_context(effect, invocation),
        )
        from .combat_target_ordering import order_native_targets

        targets = order_native_targets(effect, invocation, targets)
        return tuple(replace(invocation, target_id=target.id) for target in targets)
