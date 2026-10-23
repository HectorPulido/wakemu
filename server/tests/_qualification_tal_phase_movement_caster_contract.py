"""Run the pure observed-receiver contract without scenes or event publication."""
import runpy, unittest


def qualify():
    runpy.run_path(
        ".runtime/ultimate-scenes-20261021/trace_talkasha_phase_movement_caster_contract.py"
    )
    return unittest.TestSuite()
