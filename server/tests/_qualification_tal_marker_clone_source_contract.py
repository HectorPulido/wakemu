"""Run the authorized isolated diagnostic against a clone of the retained fight."""
import runpy, unittest


def qualify():
    runpy.run_path(
        ".runtime/ultimate-scenes-20261021/trace_talkasha_actual_marker_contract.py"
    )
    return unittest.TestSuite()
