"""Private diagnostic copy shim preserves exact native deepcopy semantics."""
import copy
import unittest

from jondo_spirit_initial_turn_spans import _provider_top_copy


class InitialTurnCopyProbeTests(unittest.TestCase):
    def provider(self):
        namespace = {}
        exec(
            compile(
                "def prepare_server_turn_start(value):\n from copy import deepcopy\n return deepcopy(value)\n",
                "/private/test/combat_server_spell.py",
                "exec",
            ),
            namespace,
        )
        return namespace["prepare_server_turn_start"]

    def test_only_provider_top_copy_is_measured_and_recursion_sees_original(self):
        original = copy.deepcopy
        observed = []

        class NativeCopy:
            def __deepcopy__(self, memo):
                self.assert_original()
                return {"nested": copy.deepcopy([1, {"a": 2}], memo)}

            def assert_original(self):
                if copy.deepcopy is not original:
                    raise AssertionError("Recursive/native copy still instrumented")

        def span(label, operation):
            observed.append(label)
            return operation()

        with _provider_top_copy(span):
            self.assertEqual(self.provider()(NativeCopy()), {"nested": [1, {"a": 2}]})
            self.assertEqual(copy.deepcopy([3]), [3])
            self.assertIsNot(copy.deepcopy, original)
        self.assertIs(copy.deepcopy, original)
        self.assertEqual(observed, ["actual_provider_local_fight_deepcopy"])

    def test_original_exception_and_module_binding_restore(self):
        original = copy.deepcopy
        failure = ValueError("Actual native copy failure")

        class Broken:
            def __deepcopy__(self, memo):
                raise failure

        with self.assertRaises(ValueError) as caught:
            with _provider_top_copy(lambda label, operation: operation()):
                self.provider()(Broken())
        self.assertIs(caught.exception, failure)
        self.assertIs(copy.deepcopy, original)
