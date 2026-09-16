# Mac QAP 最小只读账号实施包（已授权并在 Mac 执行）

## 已核对

2026-09-16 当前 QAP 使用 lims_admin 连接 Mac cmc_analytics，会话只读。数据库目录确认其 quality schema USAGE=false、quality_data SELECT=false。qad_reader 已存在，供旧看板使用；qap_reader 不存在。本包不更改旧看板账号、密码或权限，不向 lims_admin 扩权。

## 请求确认的完整范围

仅本机 rd_pg / cmc_analytics：通过中央 cmc-schema-migrations 新增迁移，创建独立登录角色 qap_reader（无超级用户、建库、建角色、继承其他角色能力）。只授予连接 cmc_analytics、使用 staging/quality schema、读取下列四张表。QAP 本机配置切换到该账号；密码环境内生成及保存，不出现在代码、文档、日志或 Git。

| 对象 | 权限 | 用途 |
|---|---|---|
| staging.stg_sample | SELECT | 现有 RD/QC 样品与筛选 |
| staging.stg_test | SELECT | 现有 RD/QC 检测关联 |
| staging.stg_result | SELECT | 现有 RD/QC 结果 |
| quality.quality_data | SELECT | 旧 Excel 历史数值与业务维度 |

不授予 import_history、序列、其他表、未来表默认权限、DML/DDL。既有 PUBLIC 权限仍须在执行前列出并核对；若有非预期写入/其他库权限，先暂停处理，不能用会话只读冒充最小权限。

## 待中央迁移收录的精确 SQL 草案

```sql
CREATE ROLE qap_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE qap_reader SET default_transaction_read_only = on;
GRANT CONNECT ON DATABASE cmc_analytics TO qap_reader;
GRANT USAGE ON SCHEMA staging, quality TO qap_reader;
GRANT SELECT ON TABLE staging.stg_sample, staging.stg_test,
    staging.stg_result, quality.quality_data TO qap_reader;
```

此段为评审草案，不能直接代替迁移执行。密码设置独立于迁移，不提供默认密码。迁移须检查 current_database() 和前置 revision；若账号已被其他变更创建，停止并审查，不以 IF NOT EXISTS 静默复用。

Mac 当前前置 revision 为 cmc_analytics_qad_phase1；批准后先核对中央仓库实际单一 head、父级迁移规范与已应用一期文件，作为新 revision 接续，不修改已应用迁移。本轮没有提前写入/提交中央仓库文件，不触及 Linux/培训库。

## 执行前保存与回退

执行前保存相关角色/成员关系/对象ACL和 QAP 配置的本机受限备份（配置含敏感信息，不进 Git）；记录数据库迁移版本及本机表结构。操作仅增加角色权限、不改业务表结构或行，不需要导出业务数据。逐步执行并记录无密码结果。

完成后用新账号核对四表 SELECT=true，四表 INSERT/UPDATE/DELETE/TRUNCATE=false，两个schema CREATE=false，以及角色无超级/建库/建角色能力；确认无非预期继承或 PUBLIC 写权限。检查 RD/QC 原页面，Excel 项目/产线/组别/放置状态筛选，选定单项目单批单检测项核对来源结果；不向真实业务表执行试写。

若失败，恢复原 QAP 配置并重启（Excel 来源恢复权限未就绪提示），撤销本次四表 SELECT、两schema USAGE、数据库 CONNECT，禁用 qap_reader 登录。确认没有被其他应用使用、没有其他依赖后才由迁移回退处理角色；禁止 DROP OWNED 或 CASCADE，禁止删除表/数据。配置备份仅恢复，不输出内容。

## 当前代码交付与限制

EXCEL 来源已接 ORM 适配器，固定读取 QC_LIMS 历史数值记录；项目代码等原字段保留，不把项目代码当主键。继承历史 data_type，不重新猜分类。结果单位未知，显示原值而不推断百分比、规格或统计；放置状态/子批号分面以防混合。正式导入和历史数据逐条对账尚未执行。


## 执行与验收记录（2026-09-16）

负责人回复“确认授权”后，仅在Mac执行。中央新增20260916_cmc_analytics_qap_reader.py，从cmc_analytics_qad_phase1精确升级到cmc_analytics_qap_reader并核对head。未修改一期迁移、未提交或推送、未操作Linux。培训库不继承正式账号授权，本轮未执行培训迁移。

执行前角色/成员关系、数据库/schema/table ACL、四表列结构和QAP配置保存于本项目.local-backups/reader-*，目录0700/文件0600；备份和.env均已验证Git忽略。随机口令经SCRAM设置，只保存本机0600配置，不输出；旧看板账户及配置未改。

实际登录qap_reader验证：默认只读、无超级/建库/建角色/继承/复制/绕过RLS权限，无角色成员关系；分析库业务对象中能SELECT的恰为四张约定表，无业务DML权限，public/staging/quality均无CREATE，无可调用的业务SECURITY DEFINER函数。未做真实试写。

实例既有PUBLIC CONNECT/TEMP权限保留；属于数据库默认权限，不代表本次获得其他业务表读写，不宣称跨数据库硬隔离。未修改其他库或共享PUBLIC设置。

本机后端已重启：RD项目197、QC项目21保持可读；Excel项目19，逐项目API汇总放行22067、稳定性62690（均可入原始时间数值图），合计84757，与旧表相符。CMAB007单批SEC单体正置样例20条的来源结果ID、数值、时间点、批号逐条对账一致。

实际浏览器验证：CMAB007放行分子大小组合781条/24分面，稳定性正置分子大小组合2774条/69分面，图形生成正常。放行产线DS1/DS4/FF1/FF3、组别IH、放置状态正置，来自原字段。单位尚待核对，规格/能力及缺单位统计仍关闭。正式导入及MDM员工联调不在本次完成范围。
