#!/bin/bash
# A failed backup leaves the application stopped; never silently resume writes.
set -euo pipefail
umask 077
[[ $EUID == 0 && $# == 1 ]] || { echo '用法（root）：backup.sh 新备份目录' >&2; exit 2; }
if [[ ${PROJECTMIND_MAINTENANCE_LOCKED:-0} != 1 ]]; then
    exec 9>/run/lock/projectmind-maintenance.lock
    flock -n 9 || { echo "已有部署维护操作" >&2; exit 1; }
fi
backup_dir=$(realpath -m "$1")
[[ ! -e "$backup_dir" && ! -e "$backup_dir.binding.json" ]] || exit 1
was_active=0
systemctl is-active --quiet projectmind.service && was_active=1
systemctl stop projectmind.service
cd /opt/projectmind/current/app
runuser -u projectmind -- /opt/projectmind/current/venv/bin/python -m deployment.host backup --config /etc/projectmind/runtime.json --output "$backup_dir"
chown -R root:root "$backup_dir" "$backup_dir.binding.json"
if [[ $was_active == 1 ]]; then systemctl start projectmind.service; fi
echo '私有冷备和来源绑定完成。账号/API配置须另作私有备份。'
