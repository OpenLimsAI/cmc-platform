# CMC 质量分析看板

基于现有项目续建，使用 FastAPI、React/Vite 和 PostgreSQL `cmc_analytics`。当前在 Mac 开发验证，尚未部署至 Linux。

## 当前状态

- 放行：筛选后自动更新图表、指标组合、趋势连线、均值/SD参考线、描述统计；Excel历史原值可只读查看。
- 稳定性：筛选、趋势、组统计、拟合及来源明细；单位和业务统计口径仍待验收。
- Excel：结构校验与预览；正式确认导入、防重、更正和持久审计尚未完成。
- MDM：登录会话、验签和角色守卫已有代码；真实员工联调待完成。
- 相似性页面、正式质量事实层尚未完成。旧规格仅供核对，不代表批准标准。

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

访问 http://127.0.0.1:5140/release 。选择项目和筛选条件后自动生成图表。

数据库结构和权限迁移统一归属独立的 `cmc-schema-migrations` 仓库，不由本项目启动时创建。此仓库不包含数据库、Excel业务文件、密码、验签密钥或本地备份。新环境需另行配置数据库权限和MDM。

## 文档与验证

- [本地开发及认证配置](docs/QAP-LOCAL-DEV.md)
- [放行功能核对](docs/QAP-RELEASE-PARITY-20260916.md)
- [数据库设计与实施清单](docs/QAP-DB-IMPLEMENTATION-001.md)
- [Mac只读账号迁移说明](docs/QAP-MAC-READER-APPROVAL-20260916.md)

在 `backend` 目录运行 `uv run pytest -q`；在 `frontend` 目录运行 `pnpm test:auth`、`node --test tests/releaseDraft.test.mjs`、`pnpm build`。部分旧算法回归测试需要相邻旧项目 `quality_analysis_dashboard`，不能替代独立业务验收。
