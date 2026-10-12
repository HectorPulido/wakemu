"""Private retained eYa execution bridge using actual existing runtime codecs.

No shared registration is installed. The factory must supply its complete Qf
runtime and ordinary execution context; the sealed PK provider limits this
prototype to the two recovered indefinite native definitions.
"""
import json
from contextlib import contextmanager
from .combat_pointer_qi_lifecycle import NativePK937, NativeRunner937, _SOURCE
from .combat_pointer_qi_actor import ActualActorQI, ActualRetained937, RetainedContext
from .combat_pointer_qi_checkpoint import NativePointerCheckpoint
from .combat_pointer_qi_spatialowned import NativeSpatialRecord
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, evaluated_effect_delivery
from .combat_retained_effects import RetainedEffect
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value


class SpatialHooks:
    def __init__(
        self, handler, uid, invocation, target, context, collection, effect, amount
    ):
        self.operands = (
            handler,
            uid,
            invocation,
            target,
            context,
            collection,
            effect,
            amount,
        )

    def build_payload(self, runner):
        (
            handler,
            uid,
            invocation,
            target,
            context,
            collection,
            effect,
            amount,
        ) = self.operands
        from .combat_retained_runtime import group_payload
        from .combat_effects import _integer, _varint
        from wakfu_server.wire import proto_fields

        if not isinstance(context.timing_payload, bytes):
            raise ValueError("Actual native eYa TimeDatas required")
        clock = b"".join(
            _integer(tag >> 3, value)
            if tag & 7 == 0
            else _varint(tag) + _varint(len(value)) + value
            for tag, value in proto_fields(context.timing_payload)
            if tag >> 3 not in (2, 5)
        )
        clock += _integer(2, -1) + _integer(5, 1)
        owner, owner_id = handler.retention.container(invocation)
        self.payload = group_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=target.identity,
            cell=invocation.cell,
            container_type=owner["container_type"],
            container_id=owner_id,
            timing_payload=clock,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
            initial_value=amount.value,
        )

    def publish_execution(self, runner):
        (
            handler,
            uid,
            invocation,
            target,
            context,
            collection,
            effect,
            amount,
        ) = self.operands
        if not hasattr(self, "payload"):
            self.build_payload(runner)
        handler.packets.append(
            evaluated_effect_delivery(
                handler.fight.id,
                handler.action_id,
                retained=True,
                effect_class=937,
                target_id=target.identity,
                uid=uid,
                running_effect_payload=self.payload,
            )
        )

    def log_exception(self, stage, error):
        (
            handler,
            uid,
            invocation,
            target,
            context,
            collection,
            effect,
            amount,
        ) = self.operands
        # Preserve native catch-and-log; diagnostic events remain scoped.
        handler.fight._event(
            "native_runner_exception",
            family=937,
            stage=stage,
            error=type(error).__name__,
        )

    def after_application(self, runner):
        (
            handler,
            uid,
            invocation,
            target,
            context,
            collection,
            effect,
            amount,
        ) = self.operands
        if not hasattr(self, "payload"):
            raise ValueError("Missing actual eYa publication payload")
        if uid in collection:
            if collection[uid]._runner is not runner:
                raise ValueError("Spatial Qf registration changed before application")
            return
        row = NativeSpatialRecord(
            runner,
            caster_id=invocation.caster_id,
            state_uid=invocation.state_uid,
            payload=self.payload,
        )
        collection[uid] = row
        definition = handler.retention.definition(effect, invocation)
        container, _ = handler.retention.container(invocation)
        handler.retention.record(
            RetainedEffect(
                uid,
                target.identity,
                937,
                invocation.reference,
                owner_uid=invocation.state_uid,
                manager_id=target.identity,
                definition_type=definition["definition_type"],
                definition_dispellable=definition["definition_dispellable"],
                **container
            )
        )

    def before_dispose(self, runner):
        (
            handler,
            uid,
            invocation,
            target,
            context,
            collection,
            effect,
            amount,
        ) = self.operands
        handler.publish_registry(handler.fight, runner.spatial.context.qi)

    def release(self, runner):
        (
            handler,
            uid,
            invocation,
            target,
            context,
            collection,
            effect,
            amount,
        ) = self.operands
        if collection.get(uid) is None:
            raise ValueError("Missing owned spatial release")
        del collection[uid]


def publish_spatial_registry(fight, qi):
    from .combat_pointer_qi_registry import PointerRegistryCompatibility
    from .combat_carrying import _publish_registry

    _publish_registry(fight, PointerRegistryCompatibility(qi))


class NativeSpatialHandler:
    native_runner_value_verified = True

    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        context,
        retention,
        publish_registry,
        rng,
        allocate_uid=None
    ):
        if (
            retention.fight is not fight
            or not callable(context)
            or not callable(publish_registry)
        ):
            raise ValueError("Actual scoped spatial execution dependencies required")
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.context, self.retention, self.publish_registry = (
            context,
            retention,
            publish_registry,
        )
        self.rng = rng
        self.allocate_uid = allocate_uid or fight.allocate_effect_uid
        self.prepared = {}
        self.event_lifecycle = None
        self.collection_scopes = []

    def native_eligibility(self, effect, invocation):
        actor = self.fight.actors.get(invocation.target_id)
        if actor is None:
            return True
        from .combat_runner_target_life import runner_target_life_eligible

        return runner_target_life_eligible(
            self.fight, actor, effect, invocation=invocation
        )

    def _phase(self, effect, invocation, amount, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eYa event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=amount.uid,
                value=amount.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=amount,
                _execution_status=-1,
                _nullable_target=True,
            )

    def _prepare_amount(self, effect, invocation):
        amount = NativeRunnerAmount(invocation.native_running_uid, 937, rng=self.rng)
        self.prepared[amount.uid] = amount
        try:
            self._phase(effect, invocation, amount, 1)
            amount.set_calculated(
                apply_context_value(
                    0,
                    None
                    if invocation.native_context_hex is None
                    else bytes.fromhex(invocation.native_context_hex),
                )
            )
        except BaseException:
            self.prepared.pop(amount.uid, None)
            raise
        return amount

    def prepare(self, effect, values, invocation):
        from dataclasses import replace

        invocation = replace(invocation, native_running_uid=self.allocate_uid())
        self._prepare_amount(effect, invocation)
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    @contextmanager
    def native_collection_scope(self):
        """Qe.d constructs/registers all recipients before list4 execution."""
        plans = []
        self.collection_scopes.append(plans)
        try:
            yield
            self.collection_scopes.pop()
            for plan in plans:
                self._apply_plan(plan)
        finally:
            if self.collection_scopes and self.collection_scopes[-1] is plans:
                self.collection_scopes.pop()
            for _, _, invocation, _, _ in plans:
                self.cancel_prepared(invocation)

    def __call__(self, effect, values, invocation):
        plan = self._construct(effect, values, invocation)
        if plan is None:
            return False
        if self.collection_scopes:
            self.collection_scopes[-1].append(plan)
            # Qe.d marks success when n() preparation entered list4.
            return True
        return self._apply_plan(plan)

    def _construct(self, effect, values, invocation):
        definition = json.loads(_SOURCE.read_bytes()).get(str(invocation.reference))
        pk = NativePK937.from_sealed(invocation.reference, invocation.level, definition)
        identity = (
            "effect_class",
            "minimum_level",
            "maximum_level",
            "parameters",
            "variant",
            "native_effect_flags",
            "native_execution_mode",
            "native_timing_definition",
            "native_definition_class",
            "criteria",
            "children",
            "native_hmi_actions",
            "native_localization_enabled",
            "native_target_selector",
            "target_masks",
        )
        from .combat_definitions import effect_profile

        profile_valid = values == () or values == effect_profile(
            definition, invocation.level
        )
        if (
            any(
                json.dumps(effect.get(key), sort_keys=True)
                != json.dumps(definition.get(key), sort_keys=True)
                for key in identity
            )
            or not profile_valid
        ):
            raise ValueError("Execution differs from actual native eYa PK")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or context.retained is not True
        ):
            raise ValueError("Missing actual retained native execution authority")
        if not context.executable:
            self.cancel_prepared(invocation)
            return None
        actor = self.fight.actors.get(invocation.target_id)
        if actor is not None:
            from .combat_runner_target_life import verify_runner_target_life

            verify_runner_target_life(self.fight, actor, effect, invocation=invocation)
        if not hasattr(self.fight, "native_pointer_checkpoint"):
            self.fight.native_pointer_checkpoint = NativePointerCheckpoint(
                ActualActorQI(self.fight)
            )
        qi = self.fight.native_pointer_checkpoint.validate(self.fight)
        target = qi.objects.get(invocation.target_id) or qi.area_objects.get(
            invocation.target_id
        )
        if target is None:
            raise ValueError("Actual canonical eYa target required")
        if target.kind != "actor":
            raise ValueError("Native eYa Qq execution domain is not yet qualified")
        from .combat_state_managers import state_manager

        if state_manager(self.fight, target.identity) is None:
            raise ValueError(
                "Native eYa null-Qf pooling/publication is not yet qualified"
            )
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        uid = invocation.native_running_uid
        if type(uid) is not int or not 0 < uid < 1 << 63:
            raise ValueError("Actual native eYa execution UID required")
        collection = getattr(self.fight, "native_owned_spatial_effects", None)
        if collection is None:
            collection = self.fight.native_owned_spatial_effects = {}
        if uid in collection or uid in self.fight.native_retained_records:
            raise ValueError("Duplicate actual native spatial running UID")
        amount = self.prepared.get(uid)
        if amount is None:
            amount = self._prepare_amount(effect, invocation)
        runner = NativeRunner937(
            ActualRetained937(uid, target, RetainedContext(qi)),
            pk,
            SpatialHooks(
                self, uid, invocation, target, context, collection, effect, amount
            ),
        )
        # Native Qf.p/bbE precede the list4 bbJ execution pass. Build the
        # exact owned wire identity without publishing eZR.d prematurely.
        runner.hooks.build_payload(runner)
        runner.hooks.after_application(runner)
        return runner, effect, invocation, amount, qi

    def _apply_plan(self, plan):
        runner, effect, invocation, amount, qi = plan
        try:
            self._phase(effect, invocation, amount, 2)
            moved = runner.apply()
            self.publish_registry(self.fight, qi)
            amount.finish_application()
            self._phase(effect, invocation, amount, 3)
            self._phase(effect, invocation, amount, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, amount.value)
            return moved
        finally:
            self.cancel_prepared(invocation)
