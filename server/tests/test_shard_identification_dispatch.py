from tests import test_element_selection_dispatch as elemental_dispatch


class ShardIdentificationDispatchTests(
    elemental_dispatch.ElementSelectionDispatchTests
):
    def run_branch(self, *, opcode=13787, **kwargs):
        return super().run_branch(opcode=opcode, **kwargs)
