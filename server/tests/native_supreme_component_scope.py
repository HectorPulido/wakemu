"""Explicit source-checked isolation for narrow encounter component witnesses."""
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def isolate_talkasha_pyramid_opening_damage(omissions):
    """Exclude only the diagnosed four-pyramid single-PC concentration.

    This is a test component boundary, never encounter setup or a production
    damage policy. Original turn events, WP producers, paid casts and ultimate
    damage remain real. A full fight needs a legitimate party to split attacks.
    """
    from wakfu_server.combat_effect_dispatch import EffectDispatcher

    original = EffectDispatcher.execute

    def execute(dispatcher, invocation, **kwargs):
        if invocation.reference != 380151:
            return original(dispatcher, invocation, **kwargs)
        effect = dispatcher.effects[str(invocation.reference)]
        if effect.get("effect_class") != 330 or tuple(effect.get("children", ())) != (
            380154,
            380152,
            380156,
            380160,
            380164,
        ):
            raise ValueError("Isolated native pyramid component source changed")
        omissions.append(
            dict(
                reference=invocation.reference,
                caster=invocation.caster_id,
                target=invocation.target_id,
                reason="single_pc_component_excludes_four_party_split_attacks",
            )
        )
        return False

    with patch.object(EffectDispatcher, "execute", execute):
        yield
