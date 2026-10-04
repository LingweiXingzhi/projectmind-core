import json
import subprocess
import sys
import unittest
from unittest.mock import patch
from extensions.context_authority.verifiers import _run
from extensions.context_authority.registry import load_registry
from extensions.context_authority.resolver import resolve
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class LiveBoundaryTests(unittest.TestCase):
    def test_utf8_subprocess_output_with_non_ascii_github_text(self):
        code,out,err=_run([sys.executable,'-c',"import sys;sys.stdout.buffer.write('中文 GitHub PR'.encode('utf-8'))"])
        self.assertEqual((code,out,err),(0,'中文 GitHub PR',''))
    def test_registered_snapshot_absence_is_explicitly_bounded(self):
        state=resolve(load_registry(ROOT/'extensions/context_authority/data/claims.jsonl'),run_verifiers=False)
        for key in ['implementation.map_proposal_snapshot','implementation.handoff_snapshot']:
            row=state['current'][key]
            self.assertEqual(row['value']['status'],'NOT_IMPLEMENTED')
            self.assertEqual(set(row['value']['checked_revisions']),{'main','PR21','PR22'})
            self.assertIn('future revisions are unknown',row['value']['limit'])
    def test_pr21_contents_have_exact_source_version(self):
        state=resolve(load_registry(ROOT/'extensions/context_authority/data/claims.jsonl'),run_verifiers=False)
        row=state['current']['implementation.pr_21_contents_snapshot']
        self.assertEqual(row['value']['head'],row['source']['revision'])
        self.assertIn('docs/standards/COLLABORATION_CONTRACT.md',row['value']['files'])
    def test_sha_units_corrected_with_explicit_supersession(self):
        state=resolve(load_registry(ROOT/'extensions/context_authority/data/claims.jsonl'),run_verifiers=False)
        self.assertIn('40/64-character',state['current']['contract.code_facts_input']['value']['revision'])
        old=next(row for row in state['stale'] if row['claim_id']=='claim-codefacts-input')
        self.assertEqual(old['state'],'SUPERSEDED')
