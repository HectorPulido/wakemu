"""Immediate eZl307 creation on the transaction-owned preview.

Actor/controller registration is separate from effect retention. eZl.bbF does
not unsummon; retained/subscribed creation stays guarded until its lifecycle
is represented by the central effect manager.
"""
from .combat_summon import (
    summon_specification,
    fresh_summon_insertion,
    RegisteredSummonAuthority,
)
from .combat_summon_creation import NativeSummonBuilder
from .combat_summon_codec import summon_application
from .combat_stat_handler import StatExecutionContext
from .combat_actor_snapshot import native_actor_catalog


class NativeSummonHandler:
    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        actor_authority,
        container_level,
        container
    ):
        if not isinstance(actor_authority, RegisteredSummonAuthority):
            raise ValueError("Summoning requires the registered-roster authority")
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.authority, self.container_level = (
            context,
            actor_authority,
            container_level,
        )
        self.container = container
        self.builder = NativeSummonBuilder(actor_authority)

    def __call__(self, effect, values, invocation):
        caster = self.fight.actors.get(invocation.caster_id)
        if (
            effect["effect_class"] != 307
            or caster is None
            or self.fight.phase != "active"
            or invocation.target_id is not None
        ):
            raise ValueError("Native eZl requires a caster-owned cell application")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native summon execution/timing authority")
        if not ctx.executable:
            return False
        if ctx.retained or invocation.native_running_uid is not None:
            raise ValueError("Native retained/subscribed summon lifecycle is unaudited")
        self.authority(self.fight, caster)
        direction = getattr(caster, "direction", None)
        if type(direction) is not int or not 0 <= direction < 8:
            raise ValueError("Missing native summoner orientation")
        parameters = values["parameters"]
        if not parameters:
            raise ValueError("Missing native summoned breed")
        reference = ((parameters[0] + 32768) % 65536) - 32768
        profile = native_actor_catalog()["npc_profiles"].get(str(reference))
        if profile is None:
            raise ValueError("Missing native summoned breed characteristics")
        present, _ = self.container_level(invocation)
        from .monsters import reference as native_reference

        spec = summon_specification(
            effect,
            values,
            evaluation_level=invocation.level,
            container_present=present,
            caster_level=caster.effective_level,
            caster_team=caster.team,
            caster_direction=direction,
            native_minimum_level=native_reference(reference)["min_level"],
        )
        # Separate effect and creature identities; both reservations belong to
        # this preview and disappear when its transaction is rejected.
        actor_uid = self.allocate_uid()
        while actor_uid in self.fight.actors:
            actor_uid = self.allocate_uid()
        effect_uid = self.allocate_uid()
        actor, registration = self.builder(
            self.fight, spec, caster.id, actor_uid, invocation.cell
        )
        actor.direction = spec.direction
        if 114 in registration.fight_properties:
            order, index = list(self.fight.order), self.fight.turn_index
        else:
            order, index = fresh_summon_insertion(
                self.fight, spec, caster_id=caster.id, actor_id=actor_uid
            )
        owner, owner_id = self.container(invocation)
        properties = self.builder.properties["npc"][str(reference)]["fight_properties"]
        packet = summon_application(
            self.fight.id,
            self.action_id,
            uid=effect_uid,
            base_uid=invocation.base_uid,
            effect_reference=invocation.reference,
            caster_id=caster.id,
            cell=invocation.cell,
            specification=spec,
            actor_id=actor_uid,
            obstacle_index=actor.native_obstacle_id,
            properties=properties,
            timing_payload=ctx.timing_payload,
            container_type=owner["container_type"],
            container_id=owner_id,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        self.authority.register(
            self.fight, actor, registration, new_order=order, new_turn_index=index
        )
        self.packets.append(packet)
        return True
