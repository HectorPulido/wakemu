"""Static coverage follows executable dispatch branches, not metadata predicates."""
from pathlib import Path
import tempfile
import unittest

from audit_monster_family_coverage import COMBAT, dispatcher_families


class DispatcherFamilyCoverageTests(unittest.TestCase):
    def families(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dispatcher.py"
            path.write_text(source)
            return dispatcher_families(path)

    def test_current_team_repeat_branch_is_discovered(self):
        families = dispatcher_families(COMBAT / "combat_effect_dispatch.py")
        self.assertTrue({949, 1041}.issubset(families))

    def test_new_executable_branch_needs_no_parallel_whitelist(self):
        self.assertEqual(
            self.families(
                """
def execute(effect, values, selected, handler):
    if effect['effect_class'] == 8000:
        selected = None
    if effect['effect_class'] == 865:
        execute_transfer()
    elif effect['effect_class'] in (949, 1041, 8001):
        execute_group()
    else:
        result = handler(effect, values, selected)
"""
            ),
            {865, 949, 1041, 8001},
        )

    def test_unrecognized_executable_guard_rejects_instead_of_underreporting(self):
        with self.assertRaisesRegex(ValueError, "dispatcher family branch"):
            self.families(
                """
if effect['effect_class'] == 949:
    execute_group()
elif enabled:
    execute_other_group()
else:
    handler(effect, values, selected)
"""
            )

    def test_missing_fallback_cannot_be_mistaken_for_execution_coverage(self):
        with self.assertRaisesRegex(ValueError, "one executable dispatcher"):
            self.families("if effect['effect_class'] == 1041: metadata = True")
