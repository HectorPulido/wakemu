import unittest
from wakfu_server.combat_group_level_transmission import transmitted_child_override
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effects import _integer
from wakfu_server.combat_effect_removal import _identity_fields
from dataclasses import replace


class GroupLevelTransmissionTests(unittest.TestCase):
    def resolve(self, **changes):
        values = dict(
            flags=[16],
            child_override=-1,
            parent_override=None,
            container_present=True,
            container_level=200,
        )
        values.update(changes)
        return transmitted_child_override(**values)

    def test_family_override_precedes_transmission(self):
        self.assertEqual(self.resolve(child_override=7), 7)
        self.assertEqual(self.resolve(flags=[]), -1)

    def test_parent_context_precedes_container_with_native_short_cast(self):
        self.assertEqual(self.resolve(parent_override=65538), 2)
        self.assertEqual(self.resolve(parent_override=-1), 200)

    def test_absent_container_is_zero_and_unknown_is_rejected(self):
        self.assertEqual(self.resolve(container_present=False, container_level=None), 0)
        with self.assertRaises(ValueError):
            self.resolve(container_present=None)
        with self.assertRaises(ValueError):
            self.resolve(container_level=None)

    def test_runtime_child_level_and_wire_context_share_authoritative_level(self):
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.plan = {
            "native_retained_container": {"present": True, "type": 11, "level": 23}
        }
        invocation = EffectInvocation(1, 200, 7, 7, (0, 0, 0))
        effect = {"effect_class": 330, "native_effect_flags": [16]}
        level, context = runtime.child_level_context(
            effect, {}, invocation, default_level=200
        )
        self.assertEqual(level, 23)
        self.assertEqual(_identity_fields(context, integer_fields=(4,))[4], 23)
        inherited = replace(invocation, native_context_hex=_integer(4, 65538).hex())
        level, context = runtime.child_level_context(
            effect, {}, inherited, default_level=200
        )
        self.assertEqual(level, 2)
        self.assertEqual(_identity_fields(context, integer_fields=(4,))[4], 2)
        runtime.plan = {"native_retained_container": {"present": False}}
        level, context = runtime.child_level_context(
            effect, {}, invocation, default_level=200
        )
        self.assertEqual(level, 0)

    def test_retained_999_null_level_source_preserves_container_not_fake_actor_level(
        self,
    ):
        from types import SimpleNamespace

        runtime = object.__new__(NativeRetainedRuntime)
        runtime.plan = {
            "native_retained_container": {"present": True, "type": 11, "level": 23}
        }
        runtime.fight = SimpleNamespace(
            actors={7: SimpleNamespace(effective_level=200)}
        )
        invocation = EffectInvocation(371570, 1, 7, None, (0, 0, 0))
        effect = {
            "effect_class": 999,
            "native_effect_flags": [],
            "parameters": [0, 0] * 8,
        }
        values = {"parameters": [0, 0, 0, 0, 0, 0, 0, 100]}
        level, context = runtime.child_level_context(
            effect, values, invocation, default_level=1
        )
        self.assertEqual(level, 23)
        self.assertEqual(
            _identity_fields(context, integer_fields=(4,))[4] & 0xFFFFFFFF, 0xFFFFFFFF
        )
        # eYg.fPP's null-target swap keeps the actual caster when requested.
        effect["parameters"][14] = 100
        values["parameters"][5:7] = [2, 1]
        self.assertEqual(
            runtime.child_level_context(effect, values, invocation, default_level=1)[0],
            200,
        )

    def test_runtime_does_not_guess_direct_spell_level_from_invocation(self):
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.plan = {"native_retained_container": {"present": True, "type": 11}}
        invocation = EffectInvocation(1, 200, 7, 7, (0, 0, 0))
        with self.assertRaisesRegex(ValueError, "eVo.cmZ"):
            runtime.child_context(
                {"effect_class": 330, "native_effect_flags": [16]}, {}, invocation
            )

    def test_new_context_without_transmission_resets_parent_override(self):
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.plan = {
            "native_retained_container": {"present": True, "type": 11, "level": 10}
        }
        invocation = EffectInvocation(
            1, 200, 7, 7, (0, 0, 0), native_context_hex=_integer(4, 200).hex()
        )
        effect = {"effect_class": 330, "native_effect_flags": []}
        level, context = runtime.child_level_context(
            effect, {}, invocation, default_level=200
        )
        self.assertEqual(level, 10)
        self.assertEqual(
            _identity_fields(context, integer_fields=(4,))[4] & 0xFFFFFFFF, 0xFFFFFFFF
        )
        runtime.plan = {"native_retained_container": {"present": False}}
        self.assertEqual(
            runtime.child_level_context(effect, {}, invocation, default_level=200)[0], 0
        )

    def test_explicit_child_override_applies_without_transmission_flag(self):
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.child_context = lambda *args, **kwargs: _integer(4, 65538)
        # An explicit SP takes precedence even when no PL is available.
        invocation = EffectInvocation(1, 200, 7, 7, (0, 0, 0))
        level, _ = runtime.child_level_context(
            {"native_effect_flags": []}, {}, invocation, default_level=200
        )
        self.assertEqual(level, 2)
