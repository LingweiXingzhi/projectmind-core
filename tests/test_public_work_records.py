"""Authenticated production HTTP work records, never formal cognition approval."""
import json
import unittest

import test_public_deployment as fixtures
from deployment.server import build_application


class SharedWorkRecordTests(fixtures.PublicHTTPTests):
    def body(self, envelope, **values):
        return {'category': 'daily', 'date': '2026-10-08', 'title': 'Synthetic participant record',
                'body': 'Fixture text only, no real team acceptance', 'origin': 'human',
                'author': 'FORGED_JSON_AUTHOR', 'expectedMapRevision': envelope['identity']['mapRevision'],
                'expectedDraftRevision': envelope['identity']['draftRevision'], **values}

    def save(self, path, envelope, auth, **values):
        return self.request('POST', path+'/records', self.body(envelope, **values), auth=auth)

    def test_shared_fixed_context_persistence_and_private_store(self):
        auth = self.login(); path, envelope = self.workspace(auth)
        before = (fixtures.run_git(self.code, 'rev-parse', 'HEAD'), fixtures.run_git(self.code, 'status', '--porcelain'))
        status, _, result = self.save(path, envelope, auth)
        self.assertEqual(status, 200, result); entry = result['entry']
        self.assertEqual(entry['author'], 'fixture'); self.assertEqual(entry['authorIdentity'], 'authenticated_account')
        self.assertEqual(entry['recordAuthority'], 'participant_claim'); self.assertEqual(entry['status'], 'contributor_record')
        self.assertEqual(entry['binding']['mapRevision'], envelope['identity']['mapRevision'])
        self.assertEqual(entry['binding']['draftRevision'], envelope['identity']['draftRevision'])
        self.assertEqual(entry['codeRevision'], envelope['identity']['codeRevision'])
        self.assertEqual(entry['workspaceId'], envelope['workspace']['workspaceId'])
        self.assertNotIn(str(self.root), json.dumps(result))
        other = self.login(); status, _, listing = self.request('GET', path+'/records', auth=other)
        self.assertEqual(status, 200); self.assertEqual(listing['entries'][0], entry)
        self.assertIn(entry, self.request('GET', '/api/archloop/records', auth=other)[2]['entries'])
        exported = self.request('GET', path+'/records/export', auth=other)[2]
        self.assertEqual(exported['schemaVersion'], 'workspace_records_v1'); self.assertEqual(exported['entries'], [entry])
        rebuilt = build_application(self.config)
        self.assertEqual(rebuilt.service.work_records.listing(entry['workspaceId'])['entries'], [entry])
        store = rebuilt.service.work_records.store
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(store.path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(before, (fixtures.run_git(self.code, 'rev-parse', 'HEAD'), fixtures.run_git(self.code, 'status', '--porcelain')))

    def test_edit_cas_history_and_ai_never_formal_authority(self):
        auth = self.login(); other = self.login(); path, envelope = self.workspace(auth)
        original = self.save(path, envelope, auth, category='decision')[2]['entry']
        status, _, result = self.save(path, envelope, other, id=original['id'], expectedVersion=1,
                                       title='Synthetic AI alternative', origin='ai', category='decision')
        self.assertEqual(status, 200, result); updated = result['entry']
        self.assertEqual(updated['version'], 2); self.assertEqual(updated['status'], 'ai_candidate')
        self.assertEqual(updated['recordAuthority'], 'ai_candidate'); self.assertEqual(updated['createdBy'], 'fixture')
        self.assertEqual(self.save(path, envelope, auth, id=original['id'], expectedVersion=1)[0], 409)
        self.assertEqual(self.save(path, envelope, auth, id=original['id'], expectedVersion=True)[0], 409)
        history = self.request('GET', path+'/records/'+original['id']+'/history', auth=auth)[2]['history']
        self.assertEqual([row['version'] for row in history], [2, 1]); self.assertEqual(history[1], original)

    def test_foreign_workspace_stale_context_and_json_boundaries(self):
        auth = self.login(); path, envelope = self.workspace(auth); other_path, other = self.workspace(auth)
        entry = self.save(path, envelope, auth)[2]['entry']
        self.assertEqual(self.request('GET', other_path+'/records/'+entry['id']+'/history', auth=auth)[0], 404)
        self.assertEqual(self.save(other_path, other, auth, id=entry['id'], expectedVersion=1)[0], 404)
        for extra in ({'server_fields': {}}, {'attachment': {}}, {'command': 'untrusted'}, {'id': []},
                      {'id': '', 'expectedVersion': 1}, {'category': []}, {'origin': []}):
            with self.subTest(extra=extra): self.assertEqual(self.save(path, envelope, auth, **extra)[0], 400)
        status, _, _ = self.request('POST', path+'/apply-ops', {
            'expectedDraftRevision': envelope['draft']['draftRevision'],
            'operations': [{'type': 'update_node', 'nodeId': envelope['draft']['graph']['nodes'][0]['id'],
                            'fields': {'title': 'Synthetic newer draft'}}]}, auth=auth)
        self.assertEqual(status, 200)
        self.assertEqual(self.save(path, envelope, auth)[0], 409)
        self.assertEqual(len(self.request('GET', path+'/records', auth=auth)[2]['entries']), 1)

    def test_planning_no_code_sha_and_request_protection(self):
        auth = self.login(); path, envelope = self.workspace(auth, planning=True)
        body = self.body(envelope)
        self.assertEqual(self.request('POST', path+'/records', body)[0], 401)
        self.assertEqual(self.request('POST', path+'/records', body, auth={'Cookie':auth['Cookie']})[0], 403)
        self.assertEqual(self.request('POST', path+'/records', body, auth=auth, origin='https://evil.invalid')[0], 403)
        status, _, result = self.request('POST', path+'/records', body, auth=auth)
        self.assertEqual(status, 200, result)
        self.assertIsNone(result['entry']['codeRevision']); self.assertIsNone(result['entry']['binding']['codeRepoId'])
        self.assertEqual(result['entry']['binding']['context'], 'planning')

    def test_capacity_rejected_before_new_write(self):
        auth = self.login(); path, envelope = self.workspace(auth)
        records = self.application.service.work_records; original = records.MAX_ENTRIES
        with records.store.connect() as db: before = db.execute('SELECT count(*) FROM entries').fetchone()[0]
        records.MAX_ENTRIES = before
        try:
            self.assertEqual(self.save(path, envelope, auth)[0], 503)
            with records.store.connect() as db: self.assertEqual(db.execute('SELECT count(*) FROM entries').fetchone()[0], before)
        finally: records.MAX_ENTRIES = original


for _name in fixtures.PublicHTTPTests.__dict__:
    if _name.startswith('test_'):
        setattr(SharedWorkRecordTests, _name, None)
