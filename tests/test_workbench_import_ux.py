"""User-correctable import failures stay safe, actionable, and non-INTERNAL."""
import tempfile
import unittest
from pathlib import Path
from archloop.contract import ContractError
from tests.test_archloop_a_service import service_with_git, tiny_repo, run_git


class ImportExperienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service = service_with_git(self.root)

    def rejected(self, path, text, code='VALIDATION_FAILED'):
        with self.assertRaises(ContractError) as caught:
            self.service.create_workspace({'context':'existing_project', 'title':'体验', 'repoPath':str(path)})
        self.assertEqual(caught.exception.code, code)
        self.assertIn(text, str(caught.exception))
        self.assertNotIn('fatal:', str(caught.exception))
        self.assertEqual(self.service.list_workspaces()['workspaces'], [])

    def test_missing_directory_gives_recovery_without_partial_workspace(self):
        self.rejected(self.root/'missing', '检查路径')

    def test_file_is_not_a_project_directory(self):
        path=self.root/'a.txt';path.write_text('x')
        self.rejected(path, '项目目录')

    def test_plain_folder_requires_git(self):
        path=self.root/'plain';path.mkdir()
        self.rejected(path, 'Git 仓库目录')

    def test_empty_git_requires_first_commit(self):
        path=self.root/'empty';path.mkdir();run_git(path, 'init')
        self.rejected(path, '首次 Git 提交')

    def test_url_requires_clone(self):
        self.rejected('https://github.com/team/project.git', '先克隆')

    def test_registered_boundary_still_precedes_path_disclosure(self):
        self.service.allowed_repositories=frozenset({self.root/'allowed'})
        self.rejected(self.root/'missing', '未在服务器登记', 'REQUEST_FORBIDDEN')

    def test_valid_import_still_binds_real_commit(self):
        repo=tiny_repo(self.root)
        value=self.service.create_workspace({'context':'existing_project','title':'体验','repoPath':str(repo)})
        self.assertEqual(value['identity']['codeRevision'],run_git(repo,'rev-parse','HEAD'))
        self.assertIsNone(value['identity']['verifiedCodeRevision'])
