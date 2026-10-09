"""Published shared-server versions remain downloadable without an arch remote."""
import json
import os
import unittest
from urllib.parse import urlencode

from tests import test_public_deployment as fixtures
from tests import test_public_governed_tasks as governed_fixtures
from extensions.handoff.architecture import ArchitectureError, inspect_version_handoff, validate_handoff


@unittest.skipUnless(os.name == 'posix', 'Public deployment requires POSIX permissions')
class PublicHandoverExportTests(governed_fixtures.PublicGovernedTaskTests):
    def test_public_collaboration_assets_are_served_after_login(self):
        auth = self.login()
        status, _, page = self.request('GET', '/', auth=auth)
        self.assertEqual(status, 200)
        self.assertIn(b'/collaboration.js', page)
        self.assertIn(b'id="collab-shared"', page)
        status, headers, script = self.request('GET', '/collaboration.js', auth=auth)
        self.assertEqual(status, 200, script)
        self.assertIn('text/javascript', headers['Content-Type'])
        self.assertIn(b'collab-context-refresh', script)

    def version_envelope(self, path, publication):
        service = self.application.service
        record = service.store.load_workspace(path.rsplit('/', 1)[-1])
        return service.backend_b.export_version(record['backendB']['workspaceId'], publication['version']['mapRevision'])

    def test_planning_export_download_preserves_version_without_claiming_git_check(self):
        auth = self.login()
        path, _, publication = self.published(auth, planning=True)
        source = publication['provenance']['mapSourceRevision']
        before = fixtures.run_git(self.arch, 'rev-parse', 'HEAD')
        status, _, packet = self.request('GET', path+'/handover', auth=auth)
        self.assertEqual(status, 200, packet)
        self.assertEqual(packet['sources'], {'code': None, 'architecture': None})
        self.assertEqual(packet['versionEnvelope'], self.version_envelope(path, publication))
        self.assertEqual(packet['versionEnvelope']['provenance']['mapSourceRevision'], source)
        self.assertEqual(packet['trust'], 'untrusted_until_local_git_check')
        self.assertNotIn(str(self.arch), json.dumps(packet))
        validate_handoff(packet)
        with self.assertRaises(ArchitectureError) as caught:
            inspect_version_handoff(packet, architecture_repo=self.arch)
        self.assertEqual(caught.exception.code, 'SOURCE_REQUIRED')
        query = urlencode({'download': '1', 'mapRevision': publication['version']['mapRevision'],
                           'mapSourceRevision': source})
        status, headers, downloaded = self.request('GET', path+'/handover?'+query, auth=auth)
        self.assertEqual(status, 200, downloaded)
        self.assertIn('attachment;', headers['Content-Disposition'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(downloaded, packet)
        self.assertEqual(fixtures.run_git(self.arch, 'rev-parse', 'HEAD'), before)

    def test_existing_code_remote_and_identity_are_preserved(self):
        auth = self.login()
        path, _, publication = self.published(auth)
        status, _, packet = self.request('GET', path+'/handover', auth=auth)
        self.assertEqual(status, 200, packet)
        self.assertEqual(packet['sources']['code'], fixtures.run_git(self.code, 'remote', 'get-url', 'origin'))
        self.assertIsNone(packet['sources']['architecture'])
        self.assertEqual(packet['versionEnvelope'], self.version_envelope(path, publication))
        self.assertNotIn(str(self.arch), json.dumps(packet))
        validate_handoff(packet)

    def test_registered_architecture_remote_keeps_git_check_path(self):
        remote = 'https://example.invalid/architecture-versions.git'
        fixtures.run_git(self.arch, 'remote', 'add', 'origin', remote)
        self.addCleanup(lambda: fixtures.run_git(self.arch, 'remote', 'remove', 'origin'))
        auth = self.login()
        path, _, publication = self.published(auth, planning=True)
        status, _, packet = self.request('GET', path+'/handover', auth=auth)
        self.assertEqual(status, 200, packet)
        self.assertEqual(packet['sources']['architecture'], remote)
        checked = inspect_version_handoff(packet, architecture_repo=self.arch)
        self.assertEqual(checked['status'], 'same_version_git_checked')
        self.assertEqual(checked['mapSourceRevision'], publication['provenance']['mapSourceRevision'])


# Share production HTTP fixtures and publication helpers, without repeating old tests.
for base in (governed_fixtures.PublicGovernedTaskTests, fixtures.PublicHTTPTests):
    for name in base.__dict__:
        if name.startswith('test_'):
            setattr(PublicHandoverExportTests, name, None)
del base, name


if __name__ == '__main__':
    unittest.main()
