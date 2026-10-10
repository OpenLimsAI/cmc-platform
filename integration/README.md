# 配套代码归属

已获授权并完成本地整合，旧Hub、迁移、培训与systemd审阅副本已移除，避免两份规则漂移。

| 项目 | 唯一代码入口 |
|---|---|
| Hub磁贴与路由 | [apps.ts](../../cmab-hub/frontend/src/config/apps.ts)、[hub-locations.conf](../../cmab-hub/nginx/hub-locations.conf) |
| 共享迁移 | [20261010_ops_monitor_v1.py](../../cmc-schema-migrations/alembic/versions/cmc_analytics/20261010_ops_monitor_v1.py) |
| 培训隔离/通知 | [training_db_reset.sh](../../rd-batch-registry/scripts/training_db_reset.sh) |
| cron整管道通知 | [Lucullus](../../rd-lucullus-etl/run_lucullus_pipeline.sh)、[RD LIMS](../../rd-lims-etl/scripts/run_etl.sh) |
| systemd观察服务 | [deploy/linux](../deploy/linux) 中7个ops-notify单元；各源仓受管service直接注册OnSuccess/OnFailure |
| 发送/接收 | [notify_completion.py](../scripts/notify_completion.py)、[receiver.py](../backend/app/receiver.py) |

permissions.sql.example仍是最低授权审阅材料，未执行。cron-exit-trap.sh.example保留为简单退出码测试示例，实际部署使用原仓顶层脚本。生产安装和实际验证状态以[DEPLOYMENT](../docs/DEPLOYMENT.md)、[TEST_ACCEPTANCE](../docs/TEST_ACCEPTANCE.md)为准。
