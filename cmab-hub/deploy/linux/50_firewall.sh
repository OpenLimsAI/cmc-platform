#!/usr/bin/env bash
# 防火墙（ufw）：内网只放行 SSH(13568)和统一门户(5100)；其余入站一律拒绝。
# 各子系统前后端已改为只听 127.0.0.1，这里是第二道保险。
# 2026-08-17 批号系统已挂到门户 /batch/（25_batch.sh），5180 不再放行；若之前已放行过：sudo ufw delete allow 5180/tcp
# 用法（Linux 上以 prometheus 运行）：bash /opt/cmab-hub/deploy/linux/50_firewall.sh
source "$(dirname "$0")/00_common.sh"
log "ufw 规则"
sudo ufw default deny incoming  >/dev/null
sudo ufw default allow outgoing >/dev/null
sudo ufw allow 13568/tcp comment 'SSH'                              >/dev/null
sudo ufw allow 5100/tcp  comment 'cmab-hub 统一门户(唯一对外)'        >/dev/null
# 早期 quality-analysis-platform 已于 2026-09-24 退役，确保历史 3001 规则不会残留。
sudo ufw --force delete allow 3001/tcp >/dev/null 2>&1 || true
sudo ufw --force enable >/dev/null
sudo ufw status numbered
