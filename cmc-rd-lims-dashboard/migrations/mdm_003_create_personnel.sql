-- =========================================================================
-- migrations/mdm_003_create_personnel.sql
--
-- 目标:cmc_analytics.mdm.personnel
-- 作用:LIMS 检测员名册主数据,29 行数据由 Phase 3' 从
--       rd_pg.cmc_mdm.mdm_core.employee_master 迁入。
--
-- PK 设计 (P0-Q2 选 C):
--   employee_id 直接当 text PK。
--   理由:
--     1. raw LIMS 的 tester / authoriser 字段值就是 employee_id 字符串
--        ('060706' 等),mart.dim_employee.employee_id 也是 text
--     2. 与 cmab_mdm.auth.user 解耦:auth.user 是应用登录账号(5 行
--        英文 username),与 LIMS 检测员名册(29 行数字工号)语义不同
--
-- 与 cmab_mdm.auth.user 的可选关联:
--   personnel 不内联 auth_user_id FK —— 跨库 FK 实现复杂、维护成本高,
--   且当前 29 个检测员中没有人有 auth.user 账号。后续要做"检测员登录 +
--   电子签名"时再加。
-- =========================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mdm.personnel (
    -- 业务键 + PK
    employee_id    varchar(32)  PRIMARY KEY,

    -- 业务字段(对齐 mart.dim_employee 列签名)
    employee_name  varchar(128) NOT NULL,
    department     varchar(64)  NOT NULL DEFAULT '药学及技术转移部',
    group_id       varchar(32),

    -- 状态机
    status         varchar(16)  NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'inactive', 'left')),

    -- 审计 + 软删
    created_at     timestamptz  NOT NULL DEFAULT now(),
    created_by     varchar(64),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    updated_by     varchar(64),
    deleted_at     timestamptz,
    deleted_by     varchar(64)
);

-- 索引:group_id 是 sidebar "检验组多选" 的高频过滤列;status 高频过滤。
CREATE INDEX IF NOT EXISTS ix_personnel_group
  ON mdm.personnel (group_id)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_personnel_status
  ON mdm.personnel (status)
  WHERE deleted_at IS NULL;

-- 表/列注释
COMMENT ON TABLE  mdm.personnel
  IS 'LIMS 检测员名册主数据。迁自 rd_pg.cmc_mdm.mdm_core.employee_master '
     '(2026-05-18)。与 cmab_mdm.auth.user 正交 —— 后者是应用登录账号,'
     '本表是检测员人事名册(对应 raw LIMS 中的 tester/authoriser 字段值)。';
COMMENT ON COLUMN mdm.personnel.employee_id   IS '员工工号,业务主键,对应 raw LIMS tester/authoriser';
COMMENT ON COLUMN mdm.personnel.group_id      IS '所属检验组(TT1/TT5/PD/...),Dashboard sidebar 检验组多选用此列过滤';
COMMENT ON COLUMN mdm.personnel.status        IS 'active=在岗 / inactive=暂离 / left=离职';

COMMIT;

-- 校验:
--   \d mdm.personnel
--   SELECT count(*) FROM mdm.personnel;  -- 此时应为 0,Phase 3' 迁入 29 行

-- applied: 2026-05-18 00:30 by Claude (Phase 2' 自动执行)
