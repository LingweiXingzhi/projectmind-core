import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.architecture_loop_acceptance.run import load_ui_evidence


class AcceptanceHonestyTests(unittest.TestCase):
    def test_actual_fixture_success_does_not_mean_product_pass(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'evidence'
            p=subprocess.run([sys.executable,'-m','tests.architecture_loop_acceptance.run',
                '--run-d-fixture','--output',str(output)],capture_output=True,timeout=30)
            self.assertEqual(p.returncode,2,p.stderr.decode())
            report=json.loads((output/'report.json').read_text())
            self.assertEqual(report['dFixture']['status'],'PASS')
            self.assertEqual(report['productAcceptance'],'INCOMPLETE')
            self.assertEqual(len(report['checks']),28)
            self.assertFalse(any(c['status']=='PASS' for c in report['checks']))
            raw=(output/'d-http.json').read_text()
            for token in ['confirmationToken','csrfToken','sessionId','confirmation_token']:
                self.assertNotIn('"'+token+'"',raw)

    def test_wrong_ui_version_or_missing_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'ui.json'
            value={'targetHead':'a'*40,'baseUrl':'http://127.0.0.1:18872',
                'observer':'TEST_ONLY','observedAt':'2026-10-07T00:00:00Z',
                'checks':[{'id':'T03','status':'PASS','evidence':[]}]}
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):load_ui_evidence(path,'a'*40,value['baseUrl'])
            value['checks'][0]['evidence']=['real-screenshot-reference'];path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):load_ui_evidence(path,'b'*40,value['baseUrl'])
            checked=load_ui_evidence(path,'a'*40,value['baseUrl'])
            self.assertEqual(checked['trust'],'participant_observation_not_independent_audit')

    def test_fixture_generator_refuses_existing_checkout_and_ignores_git_env(self):
        from unittest.mock import patch
        from tests.architecture_loop_acceptance.fixture import create
        with tempfile.TemporaryDirectory() as root:
            f=create(Path(root)/'fixture')
            with self.assertRaises(ValueError):create(Path(f['code'])/'nested-fixture')
            with patch.dict('os.environ',{'GIT_DIR':str(Path(f['code'])/'.git')}):
                isolated=create(Path(root)/'other-fixture')
            self.assertNotEqual(isolated['code'],f['code'])


if __name__=='__main__':unittest.main()
