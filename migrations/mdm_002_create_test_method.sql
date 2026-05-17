-- =========================================================================
-- migrations/mdm_002_create_test_method.sql
--
-- 目标:cmc_analytics.mdm.test_method
-- 作用:LIMS 检验方法主数据,79 行数据由 003 后的 Phase 3' 从
--       rd_pg.cmc_mdm.mdm_quality.method_master 迁入。
--
-- PK 设计 (P0-Q1 选 A):
--   method_code 直接当 PK,不引入 surrogate bigint。
--   理由:
--     1. stats_service.py 全部 JOIN 都是 ON v.method_code = m.method_code
--     2. 79 行的小表,surrogate 无价值
--     3. method_code 业务上稳定(由 QA 命名,无意义重命名)
--
-- 命名 (cmab_mdm 风格 vs 简洁):
--   选择 test_method 不选 method,因为 "method" 太泛 (analytical method?
--   process method?);test_method 明示是检验方法。
-- =========================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mdm.test_method (
    -- 业务键 + PK
    method_code   varchar(32)   PRIMARY KEY,

    -- 业务字段(对齐 mart.dim_method 列签名,迁移期间字段集要 1:1 可投影)
    method_name   varchar(255)  NOT NULL,
    std_minutes   numeric(6, 2),
    target_days   integer,

    -- 扩展字段
    description   text,

    -- 状态机
    status        varchar(16)   NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'inactive', 'retired')),

    -- 审计 + 软删
    created_at    timestamptz   NOT NULL DEFAULT now(),
    created_by    varchar(64),
    updated_at    timestamptz   NOT NULL DEFAULT now(),
    updated_by    varchar(64),
    deleted_at    timestamptz,
    deleted_by    varchar(64)
);

-- 索引:看板取数靠 mart.dim_method 视图,无需额外列索引。
-- 软删过滤的部分覆盖索引,供 mart.dim_method 加 WHERE deleted_at IS NULL 时走索引。
CREATE INDEX IF NOT EXISTS ix_test_method_active
  ON mdm.test_method (method_code)
  WHERE deleted_at IS NULL;

-- 表/列注释
COMMENT ON TABLE  mdm.test_method
  IS 'LIMS 检验方法主数据。迁自 rd_pg.cmc_mdm.mdm_quality.method_master '
     '(2026-05-18)。由 Dashboard /api/v1/admin/methods 端点写,'
     'mart.dim_method 视图消费。';
COMMENT ON COLUMN mdm.test_method.method_code  IS '方法编码,业务主键(QA 命名,稳定)';
COMMENT ON COLUMN mdm.test_method.std_minutes  IS '标准检测工时(分钟),供工时统计';
COMMENT ON COLUMN mdm.test_method.target_days  IS '目标周转天数,供超期判定';
COMMENT ON COLUMN mdm.test_method.status       IS 'active=在用 / inactive=暂停 / retired=已废止';
COMMENT ON COLUMN mdm.test_method.created_by   IS 'admin 面板操作者名,允许空(过渡期 admin 端点暂未携带身份)';

COMMIT;

-- 校验:
--   \d mdm.test_method
--   SELECT count(*) FROM mdm.test_method;  -- 此时应为 0,003 跑完后仍 0,Phase 3' 迁入 79 行

-- applied: 2026-05-18 00:30 by Claude (Phase 2' 自动执行)
