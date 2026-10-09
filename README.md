# 制药用水看板

纯化水、注射用水和纯蒸汽的 QC 检验结果、趋势、追溯与导出。只读消费 cmc_analytics.staging，最终结果筛选由 qc-lims-etl 维护；身份复用 MDM，唯一入口为 Hub /water/。

用户2026-10-09要求仅保留总览与取样点趋势：总览无统一筛选，趋势保留图表、原文核对与导出。[两页整理方案](docs/changes/20261009-two-page-dashboard.md)已按用户本轮指令更新并获授权实施：总览仅WFI/PW/PS三卡片，每项显示点位数和当前自然年样品总数。位置与系统分类暂停，等待用户对照表。

## 本地运行

```bash
cd backend && uv sync --locked
cd ../frontend && pnpm install --frozen-lockfile
cd .. && bash deploy/mac/start.sh
```

受保护 backend/.env 参照占位符模板配置，不能提交。固定本机端口8015/5115；入口 http://localhost:5100/water/。

## 验证

```bash
cd backend && uv run pytest -q
cd ../frontend && pnpm test && pnpm build
```

日期按 Asia/Shanghai 当前日回溯3/6/12日历月。水点号来自LIMS当前主表映射，同号内部点位、方法、版本和单位保持分组隔离。图表和导出沿用一致筛选；未确认限度、系统归属和历史映射有效期明确显示。各类导出均执行后端角色校验。

## Linux 发布

2026-10-09两页及三卡片已部署Linux，随后业务提交f712b0ba42728b04d5ac784fd4fabe0a3ba81cc3移除顶部黄色提示，入口为 http://172.19.0.105:5100/water/；本轮Mac/Linux前端各9项测试、构建和Hub资源核验通过，后端未变。见[本轮提示移除记录](docs/changes/20261009-remove-context-notice.md)和[此前两页发布记录](docs/releases/20261009-two-page-linux.md)。真实登录后的页面交互、两档身份及下载落盘仍待验收。流程和边界见[状态登记](docs/STATUS.md)及[Linux操作说明](deploy/linux/README.md)。没有数据库结构变更，不切换mart或加载预览数据。

## 文档与敏感材料

文档职责和阅读顺序见 [文档索引](docs/README.md)，当前实现/验收见 [STATUS](docs/STATUS.md)，待确认事项与代码差距见 [docs/10](docs/10-decisions-open-items.md)。功能、规则、接口和操作分别由docs/01–09维护；历史执行记录与当前说明分开。实际验收截图、真实导出、调查材料、备份和日志仅保留本地，不上传GitHub。私有仓库仍不得包含密码、令牌、私钥或真实连接凭据。环境模板仅含占位符。
