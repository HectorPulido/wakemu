import unittest

from wakfu_server.achievements.intro_profession_bootstrap import packets


class IntroProfessionBootstrapTests(unittest.TestCase):
    def test_intro_keeps_account_snapshot_without_learning_notifications(self):
        source = [(12675, b"job"), (13873, b"snapshot")]
        self.assertEqual(packets(1465, source), [(13873, b"snapshot")])
        self.assertEqual(packets(1385, source), source)


if __name__ == "__main__":
    unittest.main()
