from tests import test_element_selection_dispatch as elemental_dispatch


class ShardIdentificationDispatchTests(
    elemental_dispatch.ElementSelectionDispatchTests
):
    def run_branch(self, **kwargs):
        return super().run_branch(opcode=13787, **kwargs)
