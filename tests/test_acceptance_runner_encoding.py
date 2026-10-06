# -*- coding: utf-8 -*-
"""R49-05: the D acceptance runner is encoding-independent.

Its manifest, owner marker, UI evidence and REPORT were read/written with the
locale default encoding, so a cp936 host (UTF-8 mode off) could not read the
report back and failed on non-ASCII input. Every text read/write is explicit
UTF-8 now; this test runs the runner with `-X utf8=0` on a fixture whose
directory name is Chinese and asserts the report round-trips as UTF-8 JSON.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "repo_explorer_acceptance"


def _fixture():
    if str(FIXTURE_DIR) not in sys.path:
        sys.path.insert(0, str(FIXTURE_DIR))
    import fixture  # noqa: PLC0415
    return fixture


@unittest.skipIf(shutil.which("git") is None, "git is required to build the fixture")
class AcceptanceRunnerEncodingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture()
        self._tmp = tempfile.TemporaryDirectory()
        # A non-ASCII parent directory: the manifest path itself then carries
        # characters a locale-default reader would mis-handle.
        parent = Path(self._tmp.name) / "夹具-parent"
        parent.mkdir()
        self.manifest = self.fixture.generate(parent)
        self.manifest_path = Path(self.manifest["root"]) / "manifest.json"
        self.report = Path(self._tmp.name) / "报告.json"

    def tearDown(self):
        try:
            self.fixture.cleanup(self.manifest)
        finally:
            self._tmp.cleanup()

    def _run(self, extra_args):
        # R50 (R49-05 residual): `encoding="utf-8"` in the PARENT only decodes
        # what the child wrote. A child started with `-X utf8=0` writes GBK to
        # its own stdout, so decoding the child's streams as UTF-8 in the parent
        # raises UnicodeDecodeError and (worse) hands back stdout=None. The
        # streams are therefore captured as BYTES and decoded leniently for
        # messages; the REPORT is what must be strictly valid UTF-8.
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        return subprocess.run(
            [sys.executable, "-B", *extra_args, "acceptance.py",
             "--fixture", str(self.manifest_path), "--report", str(self.report)],
            cwd=str(FIXTURE_DIR), capture_output=True, timeout=180, env=env)

    @staticmethod
    def _text(done):
        return (done.stdout + done.stderr).decode("utf-8", "replace")

    def test_report_round_trips_as_utf8_with_the_default_encoding_disabled(self):
        done = self._run(["-X", "utf8=0"])
        # exit 2 = NOT_RUN (no live origin supplied); the report must still be
        # written and readable as UTF-8.
        self.assertEqual(done.returncode, 2, self._text(done))
        raw = self.report.read_bytes()
        text = raw.decode("utf-8")
        report = json.loads(text)
        self.assertEqual(report["role"], "D")
        self.assertEqual(report["productAcceptance"], "NOT_RUN")
        self.assertIn("展开目录", text)          # the UI step names survived
        self.assertEqual(len(report["http"]), 9)

    def test_same_report_under_the_host_default_encoding(self):
        done = self._run([])
        self.assertEqual(done.returncode, 2, self._text(done))
        self.assertEqual(json.loads(self.report.read_text(encoding="utf-8"))["role"], "D")


if __name__ == "__main__":
    unittest.main()
