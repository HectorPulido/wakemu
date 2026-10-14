"""GC suppression is restricted to static prewarm, including its failure path."""
import unittest
from test_catalog_gc_bootstrap import CatalogGCBootstrapTests


class CatalogPrewarmGCOnlyTests(unittest.TestCase):
    run_case = CatalogGCBootstrapTests.run_case

    def test_only_prewarm_disables_gc_cleanup_and_failure_restore_it(self):
        self.run_case(
            """
import gc
from wakfu_server.catalog_gc_bootstrap import freeze_startup_heap
seen = []
def fail():
    assert not gc.isenabled()
    seen.append('prewarm')
    raise ValueError('source preload failed')
def cleanup():
    assert gc.isenabled()
    seen.append('cleanup')
try:
    freeze_startup_heap(fail, cleanup)
except ValueError as error:
    assert str(error) == 'source preload failed'
else:
    raise AssertionError('prewarm failure swallowed')
assert seen == ['prewarm', 'cleanup']
assert gc.isenabled() and gc.get_freeze_count() == initial_frozen
"""
        )
