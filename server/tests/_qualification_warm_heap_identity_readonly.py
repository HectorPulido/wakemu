"""Report existing process and cache identities without loading catalog data."""
import json
import os
from pathlib import Path
import resource
import sys
import unittest


class ReadWarmHeapIdentity(unittest.TestCase):
    def runTest(self):
        names = (
            "wakfu_server.native_catalog",
            "wakfu_server.combat_actor_snapshot",
            "wakfu_server.spell_audit",
            "test_combat_effect_runtime",
        )
        modules = {}
        for name in names:
            module = sys.modules.get(name)
            if module is None:
                modules[name] = None
                continue
            rows = {}
            for key, value in vars(module).items():
                if isinstance(value, (dict, list, tuple)) and len(value) > 1000:
                    rows[key] = dict(
                        identity=id(value), kind=type(value).__name__, count=len(value)
                    )
                elif callable(getattr(value, "cache_info", None)):
                    rows[key] = dict(
                        identity=id(value), cache_info=str(value.cache_info())
                    )
            modules[name] = dict(identity=id(module), existing_values=rows)
        facts = dict(
            pid=os.getpid(),
            ppid=os.getppid(),
            rss_peak_bytes_macos=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            existing_modules=modules,
            no_catalog_call_or_reload=True,
            nox_empty=not sys.modules[
                "test_nox_full_party_victory_v5"
            ].retained_components,
            rushu_released=sys.modules[
                "test_rushu_dd230_eleven_slot_opening"
            ].RUSHU_ACTUAL_CHECKPOINT
            is None,
        )
        Path(
            ".runtime/parallel-readiness-20261021/warm-native-catalog-heap-owner-readonly.json"
        ).write_text(json.dumps(facts, indent=2) + "\n")
        print(json.dumps(facts), flush=True)


def qualify():
    return unittest.TestSuite([ReadWarmHeapIdentity()])
