#!/bin/bash
# Requires a clean checkout at the explicitly approved, already pushed SHA.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
expected_sha="${1:?必须指定已发布的完整提交 SHA}"
[[ "$expected_sha" =~ ^[a-f0-9]{40}$ ]] || exit 2
cd /opt/cmc-water-system-dashboard
[[ "$(git rev-parse HEAD)" == "$expected_sha" ]] || { echo '目标 SHA 不一致'; exit 2; }
[[ -z "$(git status --porcelain)" ]] || { echo '工作区不干净'; exit 2; }
[[ -f backend/.env ]] || { echo '缺少受保护环境配置'; exit 2; }
uv sync --directory backend --locked
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
echo '构建完成。尚未安装服务、重载 Hub 或发布业务。按 docs/08 的数据、快照、权限及中文字体前置条件验收后启用。'
