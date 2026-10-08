"""Authenticated single-process deployment behind a same-host HTTPS proxy."""
import argparse
import getpass
import json
from pathlib import Path

from .access import AccessError, PublicAccess, _outside_git, add_account, check, create_account_file
from .wsgi import Application, MAX_BODY
from extensions.architecture_workspace.errors import WorkspaceError
from archloop.contract import ContractError


def build_application(config_path):
    path = _outside_git(config_path)
    check(path.is_file() and path.stat().st_size <= 65536, message="需要源代码外的部署配置")
    with path.open(encoding="utf-8") as file:
        config = json.load(file)
    keys = {"schemaVersion", "publicOrigin", "accountsFile", "dataRoot",
            "codeRepositories", "architectureRepo", "architectureBranch"}
    check(isinstance(config, dict) and set(config) == keys
          and config["schemaVersion"] == "projectmind_deploy_v1")
    access = PublicAccess(config["publicOrigin"], config["accountsFile"])
    paths = config["codeRepositories"]
    check(isinstance(paths, list) and len(paths) <= 16 and all(isinstance(p, str) for p in paths))
    repos = [Path(p).resolve() for p in paths]
    check(all(Path(p).is_absolute() and repo.is_dir() for p, repo in zip(paths, repos)))
    check(len(set(repos)) == len(repos), message="仓库不得重复登记")
    data = _outside_git(config["dataRoot"])
    data.mkdir(mode=0o700, parents=True, exist_ok=True)
    check(data.is_dir() and data.stat().st_mode & 0o077 == 0,
          message="数据根权限必须为 0700")
    architecture = Path(config["architectureRepo"])
    check(architecture.is_absolute() and architecture.is_dir() and architecture.resolve() not in repos)
    branch = config["architectureBranch"]
    check(isinstance(branch, str) and branch.startswith("architecture/candidates/"))
    from app import ROOT, make_handler
    from archloop.adapters import AdapterRegistry
    from archloop.backend_b import BackendB
    from archloop.service import WorkbenchService
    from repo_index.explorer import ExplorerRegistry
    backend = BackendB(data / "b", code_repositories=repos, architecture_repo=architecture,
                       architecture_branch=branch, allowed_origin=access.origin, trusted_https_proxy=True)
    check(backend.available, message="B 版本后端配置无效；检查专用数据根和独立架构候选分支")
    service = WorkbenchService(data / "a", AdapterRegistry(), allowed_repositories=repos)
    service.bind_backend_b(backend)
    from archloop.backend_d import GovernedTasks
    service.bind_backend_d(GovernedTasks(service, backend, data, access.origin))
    from archloop.work_records import WorkspaceRecords
    service.bind_work_records(WorkspaceRecords(service, data, access.origin))
    handler = make_handler(repos[0] if repos else ROOT, None, explorer_registry=ExplorerRegistry(),
                           archloop_service=service, public_origin=access.origin)
    application = Application(handler, access, repos)
    application.service = service
    application.data_root = data
    return application


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    provision = commands.add_parser("create-account", help="交互式创建新账号文件，不覆盖旧文件")
    provision.add_argument("--file", required=True, type=Path)
    provision.add_argument("--username", required=True)
    add = commands.add_parser("add-account", help="原子新增团队账号，不覆盖既有账号")
    add.add_argument("--file", required=True, type=Path)
    add.add_argument("--username", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--config", required=True, type=Path)
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command in ("create-account", "add-account"):
            password = getpass.getpass("设置密码（至少16字符）: ")
            check(password == getpass.getpass("再次输入密码: "), message="两次密码不同")
            function = create_account_file if args.command == "create-account" else add_account
            function(args.file, args.username, password)
            print("账号文件已保存，权限为0600；新增账号在服务重启后生效。")
        else:
            check(0 < args.port <= 65535)
            application = build_application(args.config)
            from waitress import serve as run
            from .lease import ServingLease
            with ServingLease(application.data_root):
                print(f"ProjectMind authenticated backend: 127.0.0.1:{args.port}", flush=True)
                run(application, host="127.0.0.1", port=args.port, threads=8, connection_limit=64,
                    channel_timeout=30, max_request_header_size=16384,
                    max_request_body_size=MAX_BODY, clear_untrusted_proxy_headers=True,
                    expose_tracebacks=False, ident="ProjectMind")
    except (AccessError, WorkspaceError, ContractError, OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"部署配置未通过：{type(exc).__name__}。请检查私有配置与目录。\n")


if __name__ == "__main__":
    main()
