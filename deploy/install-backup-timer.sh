#!/usr/bin/env bash
# Run once on the VPS as root: sudo deploy/install-backup-timer.sh [user]
set -euo pipefail
dir="$(cd "$(dirname "$0")/.." && pwd)"
user="${1:-${SUDO_USER:-root}}"
sed -e "s|__DIR__|$dir|g" -e "s|__USER__|$user|g" "$dir/deploy/coffeepos-backup.service" > /etc/systemd/system/coffeepos-backup.service
cp "$dir/deploy/coffeepos-backup.timer" /etc/systemd/system/coffeepos-backup.timer
systemctl daemon-reload
systemctl enable --now coffeepos-backup.timer
systemctl start coffeepos-backup.service
systemctl --no-pager status coffeepos-backup.service | tail -5
systemctl list-timers coffeepos-backup.timer --no-pager
