# 制药用水看板

纯化水、注射用水和纯蒸汽的 QC 检验结果、趋势、追溯与导出。只读消费 cmc_analytics.staging，最终结果筛选由 qc-lims-etl 维护；身份复用 MDM，唯一入口为 Hub /water/。

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

Linux 服务已首次部署，正式入口为 http://172.19.0.105:5100/water/；真实登录及两档权限验收仍待完成。参见 deploy/linux/README.md。流程为 Mac 提交推送→Linux拉取同一完整SHA→受保护环境配置→部署脚本→实际登录和导出验收。没有数据库结构变更；不从Mac拷贝业务数据或凭据到Linux。

## 文档与敏感材料

功能与接口契约见docs/01至docs/09。实际验收截图、真实导出、调查材料、备份和日志仅保留本地，不上传GitHub。私有仓库仍不得包含密码、令牌、私钥或真实连接凭据。环境模板仅含占位符。
