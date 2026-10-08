"""Actual generated-proxy TLS and Waitress, with explicitly installed Caddy."""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest

from deployment.access import create_account_file
from deployment.host import TEMPLATES, private_json
from deployment.host_smoke import collect
from test_archloop_a_backend_b import tiny_code_repo, architecture_repo

SOURCE = Path(__file__).resolve().parents[1]
CADDY = shutil.which('caddy')


@unittest.skipUnless(CADDY, 'Requires explicit Caddy executable; not public TLS acceptance')
class HostHTTPSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name).resolve(); cls.root.chmod(0o700)
        cls.processes = []; cls.handles = []
        cls.addClassCleanup(cls.cleanup)
        def port():
            with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
        cls.backend_port, cls.proxy_port = port(), port()
        cls.origin = f'https://projectmind.example.invalid:{cls.proxy_port}'
        cls.password = secrets.token_urlsafe(24)
        accounts = cls.root/'accounts.json'; create_account_file(accounts, 'fixture', cls.password)
        code = tiny_code_repo(cls.root); arch = architecture_repo(cls.root)
        private_json(cls.root/'runtime.json', {'schemaVersion': 'projectmind_deploy_v1', 'publicOrigin': cls.origin,
                     'accountsFile': str(accounts), 'dataRoot': str(cls.root/'state'), 'codeRepositories': [str(code)],
                     'architectureRepo': str(arch), 'architectureBranch': 'architecture/candidates/archloop-test'})
        # Exercise the actual production proxy body. Only listen address,
        # local CA and admin config differ to keep this fixture off the public net.
        proxy = (TEMPLATES/'Caddyfile').read_text().replace('@DOMAIN@', cls.origin)
        proxy = proxy.replace('admin unix//var/lib/caddy/projectmind-admin.sock',
                              'admin off\n    skip_install_trust\n    auto_https disable_redirects')
        proxy = proxy.replace(cls.origin+' {', cls.origin+' {\n    bind 127.0.0.1\n    tls internal')
        proxy = proxy.replace('127.0.0.1:8765', f'127.0.0.1:{cls.backend_port}')
        (cls.root/'Caddyfile').write_text(proxy)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', XDG_DATA_HOME=str(cls.root/'caddy-data'),
                   XDG_CONFIG_HOME=str(cls.root/'caddy-config'))
        env.pop('OPENAI_API_KEY', None); env.pop('PROJECTMIND_AI_MODEL', None)
        for name, command in [
                ('application', [sys.executable, '-m', 'deployment.server', 'serve', '--config', str(cls.root/'runtime.json'), '--port', str(cls.backend_port)]),
                ('proxy', [CADDY, 'run', '--config', str(cls.root/'Caddyfile'), '--adapter', 'caddyfile'])]:
            handle = (cls.root/(name+'.log')).open('w'); cls.handles.append(handle)
            cls.processes.append(subprocess.Popen(command, cwd=SOURCE, env=env, stdout=handle, stderr=handle))
        cls.ca = cls.root/'caddy-data/caddy/pki/authorities/local/root.crt'
        for attempt in range(100):
            if any(p.poll() is not None for p in cls.processes): raise RuntimeError('TLS fixture failed to start')
            if cls.ca.exists():
                try:
                    collect(cls.origin, ca=cls.ca, connect_ip='127.0.0.1'); break
                except Exception:
                    # Startup may briefly return connection refused/handshake error.
                    if attempt == 99: raise
            time.sleep(.1)
        else: raise RuntimeError('TLS fixture startup timeout')

    @classmethod
    def cleanup(cls):
        for process in reversed(cls.processes):
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for handle in cls.handles: handle.close()
        cls.temp.cleanup()

    def test_actual_tls_login_logout_and_csrf_report_contains_no_secrets(self):
        report = collect(self.origin, ca=self.ca, connect_ip='127.0.0.1', username='fixture', password=self.password)
        self.assertEqual(report['status'], 'PASS'); self.assertTrue(report['certificateAndHostnameVerified'])
        self.assertTrue(report['authenticatedChecksRun']); self.assertFalse(report['productDataWritten'])
        self.assertEqual(len(report['observations']), 14)
        encoded = json.dumps(report); self.assertNotIn(self.password, encoded); self.assertNotIn('__Host-projectmind=', encoded)
        print(json.dumps({'hostIngress': report}))

    def test_untrusted_ca_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError): collect(self.origin, connect_ip='127.0.0.1')

    def test_wrong_sni_rejected_even_with_trusted_ca(self):
        # Caddy may reject unknown SNI before presenting a certificate. Both
        # that TLS alert and client hostname verification must reject the request.
        with self.assertRaises(ssl.SSLError):
            collect(f'https://wrong.example.invalid:{self.proxy_port}', ca=self.ca, connect_ip='127.0.0.1')


if __name__ == '__main__': unittest.main()
