"""Shell failure injection with isolated paths and simulated service control.

This verifies ordering and cleanup, not a real systemd/Unix-user rehearsal.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from deployment.host import TEMPLATES
from deployment.machine import inventory


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'; self.bin.mkdir()
        self.log = self.root / 'events'
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'], EVENTS=str(self.log))
        self.sha = 'a' * 40
        self.opt = self.root / 'opt/projectmind'
        self.release = self.opt / 'releases' / self.sha
        (self.release / 'app/.git').mkdir(parents=True)
        (self.release / 'venv/bin').mkdir(parents=True)
        (self.root / 'run/lock').mkdir(parents=True)
        (self.root / 'etc/caddy').mkdir(parents=True)
        (self.root / 'srv/projectmind-backups').mkdir(parents=True)
        self.executable(self.release / 'venv/bin/python', '#!/bin/bash\ncat >/dev/null\necho "python $*" >> "$EVENTS"\nexit ${PYTHON_FAIL:-0}\n')
        self.executable(self.bin / 'runuser', '#!/bin/bash\nshift 3\nexec "$@"\n')
        self.executable(self.bin / 'systemctl', '#!/bin/bash\necho "systemctl $*" >> "$EVENTS"\nif [[ $1 == start && ${FAIL_START:-0} == 1 ]]; then exit 1; fi\nif [[ $1 == restart && ${FAIL_PROXY:-0} == 1 ]]; then exit 1; fi\nexit 0\n')
        self.executable(self.bin / 'caddy', '#!/bin/bash\nexit 0\n')
        self.executable(self.bin / 'chown', '#!/bin/bash\nexit 0\n')
        self.executable(self.opt / 'backup.sh', '#!/bin/bash\necho "backup $*" >> "$EVENTS"\nexit ${FAIL_BACKUP:-0}\n')

    def executable(self, path, text):
        path.write_text(text); path.chmod(0o700)

    def run_script(self, name, *args, **env):
        script = (TEMPLATES / name).read_text()
        for path in ('/opt/projectmind', '/run/lock', '/etc/caddy', '/srv/projectmind-backups'):
            script = script.replace(path, str(self.root)+path)
        script = script.replace('/usr/bin/caddy', str(self.bin / 'caddy'))
        # Tests require no root; all paths and service/user control are isolated.
        script = script.replace('$EUID == 0', '$EUID == $EUID')
        output = self.root / name; output.write_text(script)
        result = subprocess.run(['bash', str(output), *args], env=dict(self.env, **env),
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        events = self.log.read_text().splitlines() if self.log.exists() else []
        return result, events

    def old_release(self):
        old = self.opt / 'releases' / ('b' * 40); old.mkdir()
        (self.opt / 'current').symlink_to(old)
        return old

    def test_upgrade_backup_keeps_writes_stopped_until_switch(self):
        self.old_release()
        result, events = self.run_script('activate.sh', self.sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        backup = next(i for i, e in enumerate(events) if e.startswith('backup '))
        self.assertTrue(events[backup].endswith('--keep-stopped'))
        self.assertFalse(any(e == 'systemctl start projectmind.service' for e in events[:backup]))
        self.assertEqual((self.opt / 'current').resolve(), self.release)
        self.assertEqual(list(self.opt.glob('.activate.*')), [])

    def test_failed_start_is_explicitly_stopped(self):
        result, events = self.run_script('activate.sh', self.sha, FAIL_START='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1], 'systemctl stop projectmind.service')
        self.assertFalse(any('restart projectmind-proxy' in e for e in events))

    def test_failed_proxy_stops_application_and_preserves_release(self):
        result, events = self.run_script('activate.sh', self.sha, FAIL_PROXY='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1], 'systemctl stop projectmind.service')
        self.assertTrue(self.release.is_dir())

    def test_failed_backup_preserves_old_link_and_stops(self):
        old = self.old_release()
        result, events = self.run_script('activate.sh', self.sha, FAIL_BACKUP='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.opt / 'current').resolve(), old)
        self.assertEqual(events[-1], 'systemctl stop projectmind.service')

    def test_stale_temporary_link_does_not_block_activation(self):
        (self.opt / '.current-next').symlink_to(self.release)
        result, _ = self.run_script('activate.sh', self.sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.opt / '.current-next').is_symlink())

    def test_keep_stopped_backup_never_restarts(self):
        (self.opt / 'current').symlink_to(self.release)
        result, events = self.run_script('backup.sh', str(self.root / 'backup'), '--keep-stopped')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('systemctl start projectmind.service', events)

    def test_normal_backup_failed_restart_is_stopped(self):
        (self.opt / 'current').symlink_to(self.release)
        result, events = self.run_script('backup.sh', str(self.root / 'backup'), FAIL_START='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1], 'systemctl stop projectmind.service')

    def test_preflight_failure_does_not_stop_existing_service(self):
        old = self.old_release()
        result, events = self.run_script('activate.sh', self.sha, PYTHON_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(e.startswith('systemctl ') for e in events))
        self.assertEqual((self.opt / 'current').resolve(), old)


class MachineInventoryTests(unittest.TestCase):
    def test_unavailable_commands_report_blockers_without_public_pass(self):
        with patch('deployment.machine.probe', return_value=(None, '')):
            result = inventory()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertGreater(result['blocked'], 0)
        self.assertFalse(result['servicesChanged'])
        self.assertFalse(result['publicNetworkVerified'])
        self.assertTrue(result['remaining'])


if __name__ == '__main__':
    unittest.main()
