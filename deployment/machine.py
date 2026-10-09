"""Read-only Linux host prerequisites. This is never a public acceptance result."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys

from .host import private_json


def probe(*args):
    try:
        result = subprocess.run(args, capture_output=True, stdin=subprocess.DEVNULL,
                                timeout=10, env=dict(os.environ, LC_ALL='C'))
        return result.returncode, result.stdout.decode(errors='replace').strip()
    except (OSError, subprocess.TimeoutExpired):
        return None, ''


def inventory(minimum_free_bytes=2 * 1024**3):
    """No raw command output, paths containing credentials, or environment saved."""
    checks = []

    def add(name, passed, instruction):
        checks.append({'name': name, 'status': 'PASS' if passed else 'BLOCKED',
                       'action': '' if passed else instruction})

    add('linux', os.name == 'posix' and Path('/proc/sys/kernel/ostype').exists()
        and Path('/proc/sys/kernel/ostype').read_text().strip() == 'Linux', '使用Linux服务器')
    add('systemd', Path('/run/systemd/system').is_dir()
        and probe('systemctl', 'is-system-running')[1] in ('running', 'degraded'),
        '使用实际systemd主机；degraded状态还须检查其他失败单元')
    for command in ('git', 'python3', 'runuser', 'flock', 'systemctl'):
        add('tool:' + command, shutil.which(command) is not None, '安装系统工具 ' + command)
    add('python-venv', importlib.util.find_spec('venv') is not None
        and importlib.util.find_spec('ensurepip') is not None and sys.version_info >= (3, 10),
        '安装Python3.10+及venv/ensurepip支持')
    add('caddy', Path('/usr/bin/caddy').is_file()
        and probe('/usr/bin/caddy', 'version')[0] == 0, '按官方方式安装Caddy及caddy系统账号')
    for user in ('projectmind', 'caddy'):
        try:
            account = pwd.getpwnam(user)
            passed = account.pw_uid != 0 and account.pw_gid != 0
        except KeyError:
            passed = False
        add('user:' + user, passed, '安装阶段准备独立的非root系统账号 ' + user)
    add('clock-synchronized', probe('timedatectl', 'show', '--property=NTPSynchronized', '--value')[1] == 'yes',
        '配置并验证系统时钟同步，保证TLS有效期和审计时间可信')
    # Evaluate actual mount destinations; /opt and /var may be separate volumes.
    for mount in ('/opt', '/var/lib', '/srv'):
        try:
            free = shutil.disk_usage(mount).free
        except OSError:
            free = 0
        add('free-space:' + mount, free >= minimum_free_bytes,
            '检查该卷容量；默认2GiB只是安装最低线，业务/备份容量须另行规划')
    for service in ('projectmind.service', 'projectmind-proxy.service'):
        checks.append({'name': 'runtime:' + service, 'status': 'OBSERVED',
                       'active': probe('systemctl', 'is-active', service)[1] == 'active',
                       'enabled': probe('systemctl', 'is-enabled', service)[1] == 'enabled'})
    blocked = sum(item['status'] == 'BLOCKED' for item in checks)
    return {'schemaVersion': 'projectmind_machine_inventory_v1',
            'status': 'BLOCKED' if blocked else 'HOST_PREREQUISITES_CHECKED',
            'blocked': blocked, 'checks': checks, 'servicesChanged': False,
            'publicNetworkVerified': False,
            'remaining': ['service-user preflight and runtime rehearsal',
                          'cloud firewall and host firewall (80/443; private 8765)',
                          'DNS A/AAAA matching actual server addresses',
                          'public CA issuance and renewal', 'public HTTPS authenticated smoke',
                          'different-network browser acceptance',
                          'private off-host backup and restore drill',
                          'real model and task verifier acceptance']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--minimum-free-gib', type=int, default=2)
    args = parser.parse_args()
    if args.minimum_free_gib < 1:
        parser.error('容量最低线须至少1GiB')
    report = inventory(args.minimum_free_gib * 1024**3)
    private_json(args.output, report)
    print(json.dumps({'status': report['status'], 'blocked': report['blocked'],
                      'publicNetworkVerified': False}))
    raise SystemExit(2 if report['blocked'] else 0)


if __name__ == '__main__':
    main()
