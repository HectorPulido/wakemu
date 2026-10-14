"""Installed eWD207 controller transfer operands and source-qualified snapshots.

Fresh runner delivery and controller-facing action routing reuse the same
current-controller authority; original ownership is never rewritten.
"""
from dataclasses import dataclass

from .combat_parameters import parameter_value
from .combat_controller_registry import (
    apply_native_controller_transfer,
    remove_native_controller_transfer,
    current_native_controller,
    current_native_team,
)
from .combat_controller_spellbook import (
    target_controller_spellbook,
    controller_additional_payload,
)


def native_controller_selection(parameters, level):
    """eWD.C: first evaluated parameter equals1; absent parameter is false."""
    if (
        not isinstance(parameters, (list, tuple))
        or len(parameters) % 2
        or type(level) is not int
        or not 0 <= level <= 32767
    ):
        raise ValueError("Missing actual eWD parameter domain")
    return bool(parameters and parameter_value(parameters, 0, level) == 1)


@dataclass(frozen=True)
class ControllerTransferReceipt:
    target_id: int
    previous_ai: bool
    applied_controller: int
    applied_team: int
    use_current_controller: bool
    controller_book: tuple
    additional_payload: bytes


def prepare_controller_transfer(
    fight,
    caster,
    target,
    authority,
    *,
    parameters,
    level,
    definitions,
    effects,
    published,
):
    """Validate actual sources before eWD mutation; Qe.bbs controls UI book only.

    The selected book is serialization metadata, never new spell ownership.
    """
    if type(published) is not bool:
        raise ValueError("Missing actual Qe.bbs publication flag")
    if (
        fight.actors.get(caster.id) is not caster
        or fight.actors.get(target.id) is not target
        or authority(fight, caster).targeting.get("is_eGj") is not True
        or authority(fight, target).targeting.get("is_eGj") is not True
    ):
        raise ValueError("Missing actual registered eWD source and target eGj")
    for actor in (caster, target):
        if type(getattr(actor, "native_controlled_by_ai", None)) is not bool:
            raise ValueError("Missing actual eWD fqL field")
        current_native_controller(fight, actor.id)
        current_native_team(fight, actor.id)
    selection = native_controller_selection(parameters, level)
    if published:
        book, producer = target_controller_spellbook(
            fight,
            target,
            authority,
            definitions=definitions,
            effects=effects,
            effect_level=level,
        )
        if not producer:
            raise ValueError("Missing actual target controller book producer")
        additional = controller_additional_payload(
            book, use_current_controller=selection
        )
    else:
        book, additional = (), b""
    return selection, book, additional


def apply_controller_transfer(fight, caster_id, target_id, prepared):
    """eWD.c: transfer current relation then propagate true casterAI only."""
    selection, book, additional = prepared
    if (
        type(selection) is not bool
        or not isinstance(book, tuple)
        or not isinstance(additional, bytes)
    ):
        raise ValueError("Missing prepared native eWD operands")
    previous_ai = apply_native_controller_transfer(
        fight, caster_id, target_id, use_current_controller=selection
    )
    return ControllerTransferReceipt(
        target_id,
        previous_ai,
        current_native_controller(fight, target_id),
        current_native_team(fight, target_id),
        selection,
        book,
        additional,
    )


def remove_controller_transfer(fight, receipt):
    """eWD.bbR restores constructor controller/team and preceding AI flag."""
    if not isinstance(receipt, ControllerTransferReceipt):
        raise ValueError("Missing actual applied eWD receipt")
    remove_native_controller_transfer(
        fight, receipt.target_id, previous_ai=receipt.previous_ai
    )


class NativeControllerTransferHandler:
    """Fresh eWD runner; controller book publication never grants ownership."""

    def __init__(
        self,
        fight,
        packets,
        *,
        allocate_uid,
        action_id,
        context,
        authority,
        rng,
        definitions,
        effects,
    ):
        self.fight, self.packets = fight, packets
        self.allocate_uid, self.action_id = allocate_uid, action_id
        self.context, self.authority, self.rng = context, authority, rng
        self.definitions, self.effects = definitions, effects
        self.event_lifecycle = None
        self.runners = {}

    def _context(self, effect, invocation):
        from .combat_carry_handler import NativeCarryHandler
        from .combat_stat_handler import StatExecutionContext

        if effect.get("effect_class") != 207:
            raise ValueError("Wrong native eWD runner")
        NativeCarryHandler.require_execution_context(invocation)
        target = self.fight.actors.get(invocation.target_id)
        caster = self.fight.actors.get(invocation.caster_id)
        if target is not None and caster is not None:
            metadata = self.authority(self.fight, target)
            # Only the real class runtime's owned snapshots can enable this
            # branch. Missing producers still fail before UID/events/UI changes.
            if getattr(metadata, "is_player", None) is True and (
                getattr(caster, "native_controlled_by_ai", None) is True
                or getattr(target, "native_controlled_by_ai", None) is True
            ):
                from .combat_class_ai_spell import require_class_ai_producer

                require_class_ai_producer(self.fight, target, self.authority)
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing actual eWD execution authority")
        return context

    def _phase(self, effect, invocation, uid, channel):
        if self.event_lifecycle is None:
            return
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) != 7:
            raise ValueError("Missing native eWD event masks")
        runner = self.runners[uid][0]
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=runner.value,
            channel=channel,
            runner_modifier=runner,
            _event_ids=tuple(sorted({0, *(masks[6] or ())})),
            _execution_status=-1,
        )

    def cancel_prepared(self, invocation):
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        from dataclasses import replace
        from .combat_trigger_value_modifier import NativeRunnerAmount

        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        self.runners[uid] = (NativeRunnerAmount(uid, 207, rng=self.rng), None)
        try:
            self._phase(effect, invocation, uid, 1)
            selection = native_controller_selection(
                effect["parameters"], invocation.level
            )
            self.runners[uid] = (self.runners[uid][0], selection)
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        uid = invocation.native_running_uid
        if uid not in self.runners:
            raise ValueError("Missing prepared fresh eWD runner")
        try:
            context = self._context(effect, invocation)
            if not context.executable:
                return False
            self._phase(effect, invocation, uid, 2)
            caster = self.fight.actors.get(invocation.caster_id)
            target = self.fight.actors.get(invocation.target_id)
            if caster is None or target is None:
                raise ValueError("Missing actual eWD fighters")
            # Fresh Qe constructor bfD=true. Hydrated runners are not admitted
            # through this fresh-only entry point without their actual flag.
            selection = self.runners[uid][1]
            prepared = prepare_controller_transfer(
                self.fight,
                caster,
                target,
                self.authority,
                parameters=[int(selection), 0],
                level=invocation.level,
                definitions=self.definitions()
                if callable(self.definitions)
                else self.definitions,
                effects=self.effects,
                published=True,
            )
            receipt = apply_controller_transfer(
                self.fight, caster.id, target.id, prepared
            )
            self.fight.native_controller_action_books = getattr(
                self.fight, "native_controller_action_books", {}
            )
            self.fight.native_controller_action_books[target.id] = dict(
                producer="eWD207.eZd.fQM.actual",
                running_uid=uid,
                effect_reference=invocation.reference,
                caster_id=caster.id,
                applied_team=receipt.applied_team,
                controller_id=receipt.applied_controller,
                actions=receipt.controller_book,
            )
            from .combat_ai_control import ai_control_delivery
            from .combat_stat_effects import owned_effect_delivery
            from .combat_effects import _varint

            _, payload = ai_control_delivery(
                self.fight.id,
                self.action_id,
                effect,
                invocation,
                uid=uid,
                value=self.runners[uid][0].value,
                timing_payload=context.timing_payload,
            )
            extra = receipt.additional_payload
            payload += b"\x42" + _varint(len(extra)) + extra
            packet = owned_effect_delivery(
                self.fight.id,
                self.action_id,
                native_opcode=12613,
                effect_class=207,
                target_id=target.id,
                uid=uid,
                running_effect_payload=payload,
            )
            if context.retained:
                self.fight.owned_stat_effects[uid] = dict(
                    uid=uid,
                    effect_class=207,
                    family="eWD",
                    caster_id=caster.id,
                    target_id=target.id,
                    actual=0,
                    stat_id=None,
                    payload=payload.hex(),
                    state_uid=invocation.state_uid,
                    timer=None if context.timer is None else dict(vars(context.timer)),
                    native_controller_previous_ai=receipt.previous_ai,
                )
            self.packets.append(packet)
            if context.retained and self.event_lifecycle is not None:
                self.event_lifecycle.register_applied(effect, invocation, uid)
            self.runners[uid][0].finish_application()
            self._phase(effect, invocation, uid, 3)
            self._phase(effect, invocation, uid, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, self.runners[uid][0].value)
            return True
        finally:
            self.cancel_prepared(invocation)


def remove_controller_runner(handler, uid):
    from .combat_effect_removal import running_effect_removal

    row = handler.fight.owned_stat_effects[uid]
    if row.get("family") != "eWD" or row.get("effect_class") != 207:
        raise ValueError("Not actual retained eWD runner")
    previous = row.get("native_controller_previous_ai")
    if type(previous) is not bool:
        raise ValueError("Missing retained eWD AI snapshot")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=207,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    remove_native_controller_transfer(
        handler.fight, row["target_id"], previous_ai=previous
    )
    handler.fight.native_controller_action_books.pop(row["target_id"], None)
    handler.packets.append((13560, packet))
    del handler.fight.owned_stat_effects[uid]
    return True


def resolve_controller_action(fight, actor, owner_id, uid):
    """Resolve only the actual eZd-published target UID, with current control."""
    from .combat_effective_control import require_effective_owner
    from .combat_spell_grant_book import removed_raw_uids

    require_effective_owner(fight, actor, owner_id)
    row = getattr(fight, "native_controller_action_books", {}).get(actor.id)
    if (
        not isinstance(row, dict)
        or row.get("producer") != "eWD207.eZd.fQM.actual"
        or row.get("controller_id") != current_native_controller(fight, actor.id)
        or not isinstance(row.get("actions"), tuple)
        or type(row.get("running_uid")) is not int
    ):
        raise ValueError("Missing actual eWD published controller book")
    if type(uid) is not int or uid in removed_raw_uids(fight, actor.id):
        raise ValueError("Missing active native controller action UID")
    from .combat_character_copy_book import CopyBookAction

    for action in row["actions"]:
        if not isinstance(action, CopyBookAction):
            raise ValueError("Missing source-qualified controller action")
        action.validate()
        if action.uid == uid:
            return action.reference, action.level
    raise ValueError("Spell UID absent from actual eWD controller book")
