"""Persisted implementation-fix tasks (A-side seam that D's handoff will consume).

The previous round only produced a labeled sample task; this module stores real
tasks that carry the deviation, its evidence, the expected process, the code
revision the deviation was observed against, the acceptance conditions and the
take-over information for the next person or agent. Status transitions are
one-way unless the user rejects; "verified" requires a recorded commit, a
recorded verification result and an explicit human confirmation — a new commit
or a "done" claim never closes a deviation by itself.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from .contract import ContractError, ID_PATTERN, is_full_sha

STATUSES = ("queued", "received", "in_progress", "submitted", "verification_pending",
            "verified", "rejected")
TASK_DIR = "fix-tasks"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _task_dir(data_root: Path, workspace_id: str) -> Path:
    path = Path(data_root) / "workspaces" / workspace_id / TASK_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + f".{secrets.token_hex(4)}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=1)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def create_task(data_root: Path, record: dict, draft: dict, request: dict) -> dict:
    deviation = (request.get("deviation") or "").strip()
    if not deviation:
        raise ContractError("VALIDATION_FAILED", "请描述偏差内容（观察到的实现与期望过程的差异）")
    acceptance = (request.get("acceptance") or "").strip()
    if not acceptance:
        raise ContractError("VALIDATION_FAILED", "请写明验收条件；没有验收条件的任务不能派发")
    identity = record["identity"]
    task_id = "fix_" + secrets.token_hex(6)
    task = {
        "taskId": task_id,
        "taskType": "implementation_fix",
        "status": "queued",
        "workspaceId": record["workspaceId"],
        "mapId": identity.get("mapId"),
        "mapRevision": draft["graph"].get("mapRevision"),
        "publishedMapRevision": (record.get("lastPublish") or {}).get("mapRevision"),
        "expectedProcessRef": request.get("expectedProcessRef"),
        "expectedProcess": request.get("expectedProcess"),
        "observation": deviation,
        "evidence": request.get("evidence", []),
        "codeRepoId": identity.get("codeRepoId"),
        "targetCodeRevision": identity.get("codeRevision"),
        "verifiedCodeRevision": identity.get("verifiedCodeRevision"),
        "scope": request.get("scope", ""),
        "acceptance": acceptance,
        "takeover": {
            "repoPath": identity.get("repoPath"),
            "branchHint": request.get("branchHint", ""),
            "notes": request.get("notes", ""),
        },
        "history": [{"at": _now(), "status": "queued", "actor": request.get("actor", "local_user"),
                     "note": "任务创建；改图不会自动修改程序，需要实施者在独立分支提交代码"}],
        "source": request.get("source", "human"),
        "labeled": "A 工作台产生的实施任务；D 的同版交接模块接入后由其读取同一结构",
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if request.get("deviationId"):
        task["deviationId"] = request["deviationId"]
    if not isinstance(task["evidence"], list):
        raise ContractError("VALIDATION_FAILED", "evidence 必须是列表")
    _write(_task_dir(Path(data_root), record["workspaceId"]) / (task_id + ".json"), task)
    return task


def load_tasks(data_root: Path, workspace_id: str) -> list[dict]:
    folder = _task_dir(Path(data_root), workspace_id)
    tasks = []
    for path in sorted(folder.glob("fix_*.json")):
        try:
            tasks.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return tasks


def load_task(data_root: Path, workspace_id: str, task_id: str) -> dict:
    path = _task_dir(Path(data_root), workspace_id) / (task_id + ".json")
    if not path.exists():
        raise ContractError("NOT_FOUND", f"修正任务不存在: {task_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def update_task(data_root: Path, workspace_id: str, task_id: str, request: dict) -> dict:
    """Status transition with an explicit actor and reason; verified needs proof."""
    task = load_task(data_root, workspace_id, task_id)
    status = request.get("status")
    if status not in STATUSES:
        raise ContractError("VALIDATION_FAILED", f"status 必须是 {STATUSES}")
    actor = (request.get("actor") or "").strip()
    if not actor:
        raise ContractError("VALIDATION_FAILED", "状态变更需要 actor（本机操作者声明）")
    if status == "verified":
        commit = request.get("commitSha")
        if not is_full_sha(commit):
            raise ContractError("VALIDATION_FAILED", "verified 需要完整的实施提交 SHA")
        if not request.get("verificationEvidence"):
            raise ContractError("VALIDATION_FAILED", "verified 需要验证证据；提交存在不代表偏差消失")
        if request.get("confirmedBy") != actor:
            raise ContractError("VALIDATION_FAILED",
                                "verified 需要操作者本人确认（confirmedBy 必须等于 actor）")
        task["verification"] = {
            "commitSha": commit,
            "evidence": request["verificationEvidence"],
            "verifiedAt": _now(),
            "verifiedBy": actor,
            "scope": request.get("verificationScope", "仅限列明的核查范围"),
        }
    elif status == "submitted":
        commit = request.get("commitSha")
        if not is_full_sha(commit):
            raise ContractError("VALIDATION_FAILED", "submitted 需要完整的实施提交 SHA")
        task["submission"] = {
            "commitSha": commit,
            "branch": request.get("branch", ""),
            "summary": request.get("summary", ""),
            "evidence": request.get("evidence", []),
            "submittedAt": _now(),
            "submittedBy": actor,
            "note": "提交已回挂；偏差是否消失需要重新核查，未验证前不关闭",
        }
        task["status"] = "verification_pending"
        task["history"].append({"at": _now(), "status": "verification_pending", "actor": actor,
                                "note": f"实施提交 {commit[:12]} 已回挂，等待验证"})
        task["updatedAt"] = _now()
        _write(_task_dir(Path(data_root), workspace_id) / (task_id + ".json"), task)
        return task
    task["status"] = status
    task["history"].append({"at": _now(), "status": task["status"], "actor": actor,
                            "note": request.get("note", "")})
    task["updatedAt"] = _now()
    _write(_task_dir(Path(data_root), workspace_id) / (task_id + ".json"), task)
    return task


def task_markdown(task: dict) -> str:
    lines = [
        f"# 实施修正任务 {task['taskId']}",
        "",
        f"- 状态：{task['status']}",
        f"- 工作区：{task['workspaceId']}（mapId {task.get('mapId')}）",
        f"- 期望图版本：{task.get('mapRevision')}（已发布版本 {task.get('publishedMapRevision')}）",
        f"- 目标代码提交：{task.get('targetCodeRevision')}（核查过 {task.get('verifiedCodeRevision')}）",
        f"- 期望过程引用：{task.get('expectedProcessRef')}",
        "",
        "## 观察到的偏差",
        task.get("observation", ""),
        "",
        "## 依据",
    ]
    for item in task.get("evidence", []) or []:
        lines.append(f"- {item.get('path') or item}：{item.get('reason', '')}")
    lines += ["", "## 验收条件", task.get("acceptance", ""), "",
              "## 接手信息",
              f"- 仓库：{task.get('takeover', {}).get('repoPath')}",
              f"- 分支建议：{task.get('takeover', {}).get('branchHint')}",
              f"- 说明：{task.get('takeover', {}).get('notes')}", "",
              "改动架构图不会自动修改程序；实施者在独立分支交付后回挂提交，再由人确认核查结论。"]
    if task.get("submission"):
        lines += ["", "## 实施提交", json.dumps(task["submission"], ensure_ascii=False, indent=1)]
    if task.get("verification"):
        lines += ["", "## 验证结论", json.dumps(task["verification"], ensure_ascii=False, indent=1)]
    return "\n".join(lines)


__all__ = ["STATUSES", "create_task", "load_tasks", "load_task", "update_task", "task_markdown"]