"""CONTRACT_V1 tests for the architecture-loop workbench (A role)."""
from __future__ import annotations

import unittest

from archloop.contract import (ContractError, semantic_revision, validate_graph,
                               validate_workspace_identity)


def sample_graph() -> dict:
    return {
        "nodes": [
            {"id": "n_one", "title": "入口", "summary": "负责启动", "status": "candidate",
             "provenance": "ai_candidate", "entryPoints": ["main"], "interfaces": [],
             "evidence": [{"path": "app.py", "reason": "入口", "kind": "code_fact"}],
             "process": [
                 {"stepId": "s1", "title": "解析", "detail": "", "inputs": ["args"],
                  "outputs": ["config"], "branches": [], "next": ["s2"]},
                 {"stepId": "s2", "title": "启动", "detail": "", "inputs": ["config"],
                  "outputs": ["server"], "branches": [], "next": []},
             ]},
            {"id": "n_two", "title": "存储", "summary": "负责持久化", "status": "candidate",
             "provenance": "human_input", "entryPoints": [], "interfaces": [], "evidence": [], "process": []},
        ],
        "edges": [{"from": "n_one", "to": "n_two", "type": "functional_collaboration", "label": "调用"}],
    }


class RevisionIdentityTests(unittest.TestCase):
    def test_layout_only_change_keeps_revision(self) -> None:
        graph = sample_graph()
        base = semantic_revision(graph)
        moved = sample_graph()
        moved["nodes"][0]["position"] = {"x": 500, "y": 500}
        self.assertEqual(base, semantic_revision(moved))

    def test_semantic_change_mints_new_revision(self) -> None:
        graph = sample_graph()
        base = semantic_revision(graph)
        changed = sample_graph()
        changed["nodes"][0]["summary"] = "职责变了"
        self.assertNotEqual(base, semantic_revision(changed))

    def test_process_reorder_changes_revision(self) -> None:
        graph = sample_graph()
        base = semantic_revision(graph)
        changed = sample_graph()
        changed["nodes"][0]["process"] = list(reversed(changed["nodes"][0]["process"]))
        self.assertNotEqual(base, semantic_revision(changed))


class GraphValidationTests(unittest.TestCase):
    def test_valid_graph_passes(self) -> None:
        self.assertEqual(validate_graph(sample_graph()), sample_graph())

    def test_duplicate_node_id_rejected(self) -> None:
        graph = sample_graph()
        graph["nodes"][1]["id"] = "n_one"
        with self.assertRaises(ContractError) as caught:
            validate_graph(graph)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_edge_type_restricted(self) -> None:
        graph = sample_graph()
        graph["edges"][0]["type"] = "runtime_magic"
        with self.assertRaises(ContractError):
            validate_graph(graph)

    def test_process_step_needs_stable_id(self) -> None:
        graph = sample_graph()
        del graph["nodes"][0]["process"][1]["stepId"]
        with self.assertRaises(ContractError):
            validate_graph(graph)

    def test_provenance_is_mandatory(self) -> None:
        graph = sample_graph()
        del graph["nodes"][0]["provenance"]
        with self.assertRaises(ContractError):
            validate_graph(graph)


class IdentityTests(unittest.TestCase):
    def test_planning_rejects_code_fields(self) -> None:
        with self.assertRaises(ContractError) as caught:
            validate_workspace_identity({
                "workspaceId": "ws_x", "codeRepoId": "repo-abc",
                "codeRevision": "a" * 40, "verifiedCodeRevision": None,
            }, "planning")
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_existing_project_needs_stable_repo_id(self) -> None:
        with self.assertRaises(ContractError):
            validate_workspace_identity({"workspaceId": "ws_x", "codeRepoId": None,
                                         "codeRevision": None, "verifiedCodeRevision": None},
                                        "existing_project")

    def test_existing_project_accepts_null_revisions(self) -> None:
        identity = validate_workspace_identity({
            "workspaceId": "ws_x", "codeRepoId": "repo-abc", "mapId": "map-abc",
            "codeRevision": None, "mapSourceRevision": None, "verifiedCodeRevision": None,
        }, "existing_project")
        self.assertEqual(identity["workspaceId"], "ws_x")


if __name__ == "__main__":
    unittest.main()
