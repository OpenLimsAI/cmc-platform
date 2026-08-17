#!/usr/bin/env bash
# 防火墙（ufw）：内网只放行 SSH(13568) 与 统一门户(5100)；其余入站一律拒绝。
# 各子系统前后端已改为只听 127.0.0.1（10~40 脚本），这里是第二道保险。
# ⚠️ 5180（rd-batch-registry 前端）临时放行：批号系统尚未挂到门户 /batch/ 下，关了就没入口；
#    批号窗口按 /batch/ 改完并部署后，执行：sudo ufw delete allow 5180/tcp
# 用法（Linux 上以 prometheus 运行）：bash /opt/cmab-hub/deploy/linux/50_firewall.sh
source "$(dirname "$0")/00_common.sh"
log "ufw 规则"
sudo ufw default deny incoming  >/dev/null
sudo ufw default allow outgoing >/dev/null
sudo ufw allow 13568/tcp comment 'SSH'                              >/dev/null
sudo ufw allow 5100/tcp  comment 'cmab-hub 统一门户(唯一对外)'        >/dev/null
sudo ufw allow 5180/tcp  comment 'rd-batch-registry 临时,上门户后删'  >/dev/null
sudo ufw --force enable >/dev/null
sudo ufw status numbered
