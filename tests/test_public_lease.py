"""Single-process serving guard required by the existing A JSON store."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from deployment.access import AccessError


@unittest.skipUnless(os.name == "posix", "POSIX production serving lease")
class ServingLeaseTests(unittest.TestCase):
    def test_another_process_cannot_serve_same_root_and_release_allows_restart(self):
        from deployment.lease import ServingLease
        with tempfile.TemporaryDirectory() as root:
            command = [sys.executable, "-c",
                "from deployment.lease import ServingLease; import sys; "
                "lease=ServingLease(sys.argv[1]); lease.__enter__(); lease.__exit__()", root]
            with ServingLease(root):
                result = subprocess.run(command, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"AccessError", result.stderr)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual((Path(root) / ".serving.lock").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__": unittest.main()
