#!/bin/bash
# Explicit activation or code rollback. Data is never reset or restored here.
set -euo pipefail
umask 077
[[ $EUID == 0 && $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]] || { echo '用法（root）：activate.sh 完整提交SHA' >&2; exit 2; }
exec 9>/run/lock/projectmind-maintenance.lock
flock -n 9 || { echo "已有部署维护操作" >&2; exit 1; }
activation_started=0
next_link=''
# After any failed activation, stop restart-policy retries and retain all data.
cleanup() {
    status=$?
    trap - EXIT
    if [[ $status != 0 && $activation_started == 1 ]]; then
        systemctl stop projectmind.service || true
        echo '激活未完成，应用保持停止；保留发布目录、当前链接及冷备，核对后显式回退。' >&2
    fi
    if [[ -n $next_link ]]; then
        rm -f -- "$next_link" || true
        rmdir "${next_link%/*}" || true
    fi
    exit "$status"
}
trap cleanup EXIT
release_sha=$1
release_dir=/opt/projectmind/releases/$release_sha
[[ -d "$release_dir/app/.git" && -x "$release_dir/venv/bin/python" ]] || exit 1
[[ ! -e /opt/projectmind/current || -L /opt/projectmind/current ]] || { echo 'current须为发布链接' >&2; exit 1; }
cd "$release_dir/app"
runuser -u projectmind -- "$release_dir/venv/bin/python" -m deployment.host preflight --config /etc/projectmind/runtime.json --source "$release_dir/app" --expected-sha "$release_sha" --public
runuser -u caddy -- /usr/bin/caddy validate --config /etc/caddy/projectmind.Caddyfile --adapter caddyfile
# Reject mismatched runtime/Caddy domains before touching the active service.
"$release_dir/venv/bin/python" - <<'PY'
import json,pathlib
from urllib.parse import urlsplit
c=json.loads(pathlib.Path('/etc/projectmind/runtime.json').read_text())
domain=urlsplit(c['publicOrigin']).hostname
lines=pathlib.Path('/etc/caddy/projectmind.Caddyfile').read_text().splitlines()
assert domain+' {' in [s.strip() for s in lines], 'Caddy 与 publicOrigin 不一致'
PY
previous=''
if [[ -L /opt/projectmind/current ]]; then
    previous=$(readlink -f /opt/projectmind/current)
    activation_started=1
    PROJECTMIND_MAINTENANCE_LOCKED=1 /opt/projectmind/backup.sh "/srv/projectmind-backups/before-$release_sha-$(date -u +%Y%m%dT%H%M%SZ)" --keep-stopped
fi
activation_started=1
systemctl stop projectmind.service
# Own a unique temporary directory; an interrupted older run cannot block this run.
next_dir=$(mktemp -d /opt/projectmind/.activate.XXXXXXXX)
next_link=$next_dir/current
ln -s "$release_dir" "$next_link"
mv -Tf "$next_link" /opt/projectmind/current
rmdir "$next_dir"
next_link=''
if ! systemctl start projectmind.service; then
    echo '启动失败，保留数据和备份。服务保持停止；核对兼容性后显式回退。' >&2; exit 1
fi
# Poll the actual backend (expected anonymous API response is 401).
if ! "$release_dir/venv/bin/python" - <<'PY'
import json,pathlib,time
from http.client import HTTPConnection
from urllib.parse import urlsplit
host=urlsplit(json.loads(pathlib.Path('/etc/projectmind/runtime.json').read_text())['publicOrigin']).netloc
for attempt in range(30):
    con=HTTPConnection('127.0.0.1',8765,timeout=2)
    try:
        con.request('GET','/api/archloop',headers={'Host':host})
        response=con.getresponse();response.read()
        if response.status==401:break
    except OSError:pass
    finally:con.close()
    time.sleep(1)
else:raise SystemExit('后端未通过登录边界检查')
PY
then
    systemctl stop projectmind.service
    echo '后端验收失败，服务已停止；未自动恢复旧数据库。' >&2; exit 1
fi
systemctl enable projectmind.service projectmind-proxy.service
systemctl restart projectmind-proxy.service
echo "已激活代码 $release_sha。上一目录：${previous:-无}。继续执行真实公网HTTPS/第二设备验收。"
