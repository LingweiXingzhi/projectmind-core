#!/bin/bash
# Explicit host bootstrap. Does not start services or overwrite private configs.
set -euo pipefail
umask 077
if [[ $# != 3 || $EUID != 0 ]]; then
    echo '用法（root）：bash install.sh 完整源码副本 完整提交SHA 准备包目录' >&2; exit 2
fi
exec 9>/run/lock/projectmind-maintenance.lock
flock -n 9 || { echo "已有部署维护操作" >&2; exit 1; }
# Check host prerequisites before creating users or release directories.
[[ -d /run/systemd/system ]] || { echo '须在真实systemd Linux主机安装' >&2; exit 1; }
for command in git python3 runuser useradd install flock systemctl; do command -v "$command" >/dev/null; done
python3 -c 'import sys, venv, ensurepip; assert sys.version_info >= (3, 10), "需要Python3.10+"'
id caddy >/dev/null 2>&1 || { echo 'Caddy 系统账号未配置' >&2; exit 1; }
[[ $(id -u caddy) != 0 && $(id -g caddy) != 0 ]] || { echo 'caddy须为独立非root账号' >&2; exit 1; }
if id projectmind >/dev/null 2>&1; then
    [[ $(id -u projectmind) != 0 && $(id -g projectmind) != 0 ]] || { echo 'projectmind须为独立非root账号' >&2; exit 1; }
fi
source_dir=$(realpath "$1")
release_sha=$2
bundle_dir=$(realpath "$3")
[[ $release_sha =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ $(git -c "safe.directory=$source_dir" -C "$source_dir" rev-parse HEAD) == "$release_sha" ]] || { echo '源码HEAD与目标版本不同' >&2; exit 1; }
for file in runtime.json Caddyfile projectmind.service projectmind-proxy.service backup.sh activate.sh; do
    [[ -f "$bundle_dir/$file" && ! -L "$bundle_dir/$file" ]] || exit 1
done
[[ ! -e /opt/projectmind/releases/$release_sha ]] || { echo '发布目录已存在，不覆盖' >&2; exit 1; }
command -v git >/dev/null
command -v python3 >/dev/null
[[ -x /usr/bin/caddy ]] || { echo '先按官方方式安装 Caddy；本脚本不执行远程安装脚本' >&2; exit 1; }
id projectmind >/dev/null 2>&1 || useradd --system --user-group --home-dir /var/lib/projectmind/home --shell /usr/sbin/nologin projectmind
id caddy >/dev/null 2>&1 || { echo 'Caddy 系统账号未配置' >&2; exit 1; }
install -d -m 0755 /opt/projectmind /opt/projectmind/releases /srv/projectmind/code
install -d -m 0700 -o projectmind -g projectmind /var/lib/projectmind /var/lib/projectmind/home /var/lib/projectmind/state
install -d -m 0750 -o root -g projectmind /etc/projectmind
install -d -m 0700 -o projectmind -g projectmind /srv/projectmind-backups
install -d -m 0700 -o caddy -g caddy /var/lib/caddy
cd "$source_dir"
python3 -m deployment.host stage-release --source "$source_dir" --sha "$release_sha" --releases /opt/projectmind/releases
release_dir=/opt/projectmind/releases/$release_sha
python3 -m venv "$release_dir/venv"
"$release_dir/venv/bin/python" -m pip install -r "$release_dir/app/requirements-deploy.txt"
chown -R root:projectmind "$release_dir"
# umask077 made the clone/venv private to root. Explicitly grant the service
# group read/traverse/execute while keeping source and dependencies unwritable.
python3 -m deployment.host set-release-permissions --release "$release_dir"
if [[ ! -e /etc/projectmind/runtime.json ]]; then
    install -m 0600 -o projectmind -g projectmind "$bundle_dir/runtime.json" /etc/projectmind/runtime.json
fi
install -d -m 0755 /etc/caddy
if [[ ! -e /etc/caddy/projectmind.Caddyfile ]]; then
    install -m 0644 -o root -g root "$bundle_dir/Caddyfile" /etc/caddy/projectmind.Caddyfile
fi
# Git trust is exact-path, not a wildcard, for the read-only root-owned release.
git config --file /var/lib/projectmind/home/.gitconfig --add safe.directory "$release_dir/app"
chown projectmind:projectmind /var/lib/projectmind/home/.gitconfig
chmod 0600 /var/lib/projectmind/home/.gitconfig
install -m 0644 "$bundle_dir/projectmind.service" /etc/systemd/system/projectmind.service
install -m 0644 "$bundle_dir/projectmind-proxy.service" /etc/systemd/system/projectmind-proxy.service
install -m 0700 "$bundle_dir/backup.sh" /opt/projectmind/backup.sh
install -m 0700 "$bundle_dir/activate.sh" /opt/projectmind/activate.sh
systemctl daemon-reload
echo '安装完成，服务未启动。先准备架构Git/账号/登记代码，完成预检，再执行 activate.sh。'
