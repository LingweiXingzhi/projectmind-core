import unittest
from tests import test_archloop_d_fix_tasks as fixture_tests
from extensions.handoff.archloop_backend import create_archloop_backend


class AdapterTests(fixture_tests.FixTasksTests):
    def test_configured_A_D_factory_requires_real_B_version_binding(self):
        provider=lambda wid:{'versionHandoff':self.packet,'actor':self.args['actor'],
            'scope':self.args['scope'],'deviationId':self.args['deviation_id']}
        backend=create_archloop_backend(self.service,provider)
        p={'workspaceId':self.packet['workspaceId'],'mapRevision':self.task['mapRevision'],
            'expectedProcessRef':self.args['expected_process_ref'],'deviation':self.args['deviation'],
            'evidence':self.args['evidence'],'acceptance':self.args['acceptance']}
        try:
            from archloop.adapters import call_backend
        except ImportError:
            result=backend['call']('create_fix_task',p)
        else:
            result=call_backend(backend,'create_fix_task',p)
        self.assertEqual(result['id'],self.task['id']);self.assertIn('允许改动',result['markdown'])
        p['mapRevision']='maprev-another-A-draft'
        with self.assertRaises(Exception) as err:backend['call']('create_fix_task',p)
        self.assertEqual(err.exception.code,'STALE_CONTEXT')

    def test_missing_provider_bindings_are_not_faked(self):
        backend=create_archloop_backend(self.service,lambda wid:{})
        with self.assertRaises(Exception) as err:backend['call']('create_fix_task',{'workspaceId':'workspace-fixture'})
        self.assertEqual(err.exception.code,'BACKEND_UNAVAILABLE')


for name in list(fixture_tests.FixTasksTests.__dict__):
    if name.startswith('test_'):setattr(AdapterTests,name,None)

if __name__=='__main__':unittest.main()
