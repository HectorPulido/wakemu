"""Exercise the shipped network guard as a real Java premain agent."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[2]
GUARD_SOURCE = ROOT / "client-tools/dropin/DropinNetworkGuard.java"
CLIENT_JAVA = ROOT / "client/jre/Contents/Home/bin/java"
JAVA_FIXTURE = r"""
public final class NetworkGuardFixture {
    public static void main(String[] args) throws Exception {
        SecurityManager guard = System.getSecurityManager();
        if (guard == null) throw new AssertionError("Guard missing");
        for (String item : args) {
            String[] fields = item.split("\\|", 3);
            String host = fields[0];
            int port = Integer.parseInt(fields[1]);
            boolean expected = Boolean.parseBoolean(fields[2]);
            boolean allowed = true;
            try {
                guard.checkConnect(host, port);
            } catch (SecurityException denied) {
                allowed = false;
            }
            if (allowed != expected) {
                throw new AssertionError("Unexpected result for " + host + ":" + port
                        + " expected=" + expected + " allowed=" + allowed);
            }
        }
        System.out.println("Guard fixture passed");
    }
}
"""


class NetworkGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        javac = shutil.which("javac")
        java = shutil.which("java")
        if not javac or not java or not CLIENT_JAVA.is_file():
            raise unittest.SkipTest("JDK 21+ and the bundled client Java runtime are required")
        version = subprocess.run(
            [javac, "-version"], capture_output=True, text=True, check=True
        )
        match = re.search(r"javac\s+(\d+)", version.stderr + version.stdout)
        if not match or int(match.group(1)) < 21:
            raise unittest.SkipTest("Compiling the network guard requires JDK 21 or newer")

        cls.temp = tempfile.TemporaryDirectory(prefix="wakemu-network-guard-")
        cls.root = Path(cls.temp.name)
        classes = cls.root / "classes"
        classes.mkdir()
        fixture = cls.root / "NetworkGuardFixture.java"
        fixture.write_text(JAVA_FIXTURE, encoding="utf-8")
        subprocess.run(
            [javac, "-proc:none", "-source", "21", "-target", "21", "-d", str(classes),
             str(GUARD_SOURCE), str(fixture)],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.agent = cls.root / "network-guard.jar"
        with zipfile.ZipFile(cls.agent, "w") as archive:
            archive.writestr(
                "META-INF/MANIFEST.MF",
                "Manifest-Version: 1.0\nPremain-Class: DropinNetworkGuard\n\n",
            )
            archive.write(classes / "DropinNetworkGuard.class", "DropinNetworkGuard.class")
            archive.write(classes / "NetworkGuardFixture.class", "NetworkGuardFixture.class")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def run_agent(self, config, checks=(), *, expect_success=True):
        audit = self.root / "network-blocked.log"
        audit.unlink(missing_ok=True)
        options = f"{audit}|{config}"
        result = subprocess.run(
            [
                str(CLIENT_JAVA),
                "-Djava.security.manager=allow",
                f"-javaagent:{self.agent}={options}",
                "-cp", str(self.agent), "NetworkGuardFixture", *checks,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if expect_success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Guard fixture passed", result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Invalid guard port", result.stderr)
            self.assertFalse(audit.exists(), "Invalid config must fail before guard setup")
        return result

    @staticmethod
    def check(host, port, allowed):
        return f"{host}|{port}|{str(allowed).lower()}"

    def test_legacy_single_host_and_loopback_rules(self):
        self.run_agent(
            "127.0.0.1|15556,15558",
            [
                self.check("127.0.0.1", 15556, True),
                self.check("127.0.0.1", -1, True),
                self.check("localhost", 443, True),
                self.check("::1", 1, True),
                self.check("127.0.0.2", 15556, False),
                self.check("127.0.0.1", 443, True),
            ],
        )

    def test_v2_exact_host_port_pairs_and_dns_rules(self):
        self.run_agent(
            "v2|203.0.113.10:15556,198.51.100.20:16337,game.example.test:18081",
            [
                self.check("203.0.113.10", 15556, True),
                self.check("203.0.113.10", -1, True),
                self.check("198.51.100.20", 16337, True),
                self.check("198.51.100.20", -1, True),
                self.check("game.example.test", 18081, True),
                self.check("game.example.test", -1, True),
                self.check("203.0.113.10", 16337, False),
                self.check("198.51.100.20", 15556, False),
                self.check("203.0.113.11", -1, False),
                self.check("unknown.example.test", -1, False),
                self.check("203.0.113.10", 443, False),
                self.check("localhost", 443, True),
            ],
        )

    def test_invalid_v2_fails_during_agent_premain(self):
        self.run_agent(
            "v2|203.0.113.10:not-a-port",
            expect_success=False,
        )


if __name__ == "__main__":
    unittest.main()
