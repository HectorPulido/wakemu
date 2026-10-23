"""Qualify native paid journal and export current Polary authorities without actions."""
import importlib.util, json, sys, unittest
from pathlib import Path


class RetainedJournal(unittest.TestCase):
    def runTest(self):
        key = "_private_nox_paid_rotation_corrected_journal"
        spec = importlib.util.spec_from_file_location(
            key,
            ".runtime/staging/nox-cube24-fixed12-joint/qualify_retained_paid_rotation.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        result = module.qualify()
        recipe = sys.modules["test_nox_cube24_fixed12_joint"]
        record = recipe.retained_components[0]
        fight = record["case"].fight
        states = {
            str(identity): [
                dict(
                    uid=e.uid,
                    reference=e.reference,
                    level=e.level,
                    caster_id=getattr(e, "caster_id", None),
                )
                for e in actor.state_ledger.entries
                if e.reference in (9006, 9025)
            ]
            for identity, actor in fight.actors.items()
        }
        row = dict(
            qualified_rotation=result,
            states=states,
            native_spell_grants=getattr(fight, "native_spell_grants", None),
            verification_after=recipe.verify_retained_component(record),
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-fixed12-retained-polary-grants-readonly.json"
        ).write_text(json.dumps(row, indent=2, default=str))
        self.assertTrue(row["verification_after"]["loaded_implementation_unchanged"])


def qualify():
    return unittest.TestSuite([RetainedJournal()])
