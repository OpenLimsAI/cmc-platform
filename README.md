# CMC 质量分析看板

基于现有项目续建，使用 FastAPI、React/Vite 和 PostgreSQL `cmc_analytics`。当前在 Mac 开发验证，尚未部署至 Linux。

## 当前状态

- 放行：筛选后自动更新图表、指标组合、趋势连线、均值/SD参考线、描述统计；Excel历史原值可只读查看。
- 稳定性：筛选、趋势、组统计、拟合及来源明细；单位和业务统计口径仍待验收。
- Excel：结构校验与预览；正式确认导入、防重、更正和持久审计尚未完成。
- MDM：统一使用 cmab-hub 登录和会话，后端独立验签并按 `QAP_QC_GENERAL`、`QAP_QA_RELEASE` 授权；真实员工联调待完成。
- 相似性：已接入原值比较六图、显式参比/比较选择、探索性 TOST/Tier 汇总和 Excel 报告。正式质量事实层尚未完成，旧规格仅供核对，不代表批准标准。

## 本地开发

后端在 `backend` 目录执行 `uv sync`，复制 `.env.example` 为 `.env` 并配置独立只读账号，再执行：

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8040
```

前端在 `frontend` 目录执行：

```sh
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1
```

访问 http://127.0.0.1:5140/qap/release 。选择项目和筛选条件后自动生成图表。

## cmab-hub 接入

QAP 固定挂载在统一门户 `/qap/`。前端构建、React Router、API 和健康检查均使用该前缀；未登录时跳转到 Hub `/login?redirect=/qap/`，QAP 不再显示独立账号密码表单。Linux 的 5140/8040 只监听 `127.0.0.1`，外部只能通过 Hub 5100 进入；后端仍独立验签和检查 QAP 角色。

部署文件位于 `deploy/linux/`，完整边界及验收见 [Hub 接入说明](docs/QAP-HUB-INTEGRATION.md)。

数据库结构和权限迁移统一归属独立的 `cmc-schema-migrations` 仓库，不由本项目启动时创建。此仓库不包含数据库、Excel业务文件、密码、验签密钥或本地备份。新环境需另行配置数据库权限和MDM。

## 文档与验证

- [本地开发及认证配置](docs/QAP-LOCAL-DEV.md)
- [cmab-hub 接入与部署](docs/QAP-HUB-INTEGRATION.md)
- [放行功能核对](docs/QAP-RELEASE-PARITY-20260916.md)
- [相似性现状与待确认规则](docs/QAP-SIMILARITY-001.md)
- [相似性新旧逐项核对](docs/QAP-SIMILARITY-PARITY-AUDIT-20260916.md)
- [数据库设计与实施清单](docs/QAP-DB-IMPLEMENTATION-001.md)
- [Mac只读账号迁移说明](docs/QAP-MAC-READER-APPROVAL-20260916.md)

在 `backend` 目录运行 `uv run pytest -q`；在 `frontend` 目录运行 `pnpm test:auth`、`node --test tests/releaseDraft.test.mjs`、`pnpm build`。部分旧算法回归测试需要相邻旧项目 `quality_analysis_dashboard`，不能替代独立业务验收。
