-- =============================================================================
-- 文件: sql/equipment_init.sql
-- 用途: CMC LabOps Portal 设备管理模块数据库初始化脚本 (Phase 3)
--   在 equipment_mgmt schema 中创建 7 张表:
--     equipment / equipment_calibration / equipment_maintenance /
--     equipment_repair / equipment_warranty / equipment_attachment /
--     equipment_reminder
--
-- 上位文档: DM-LABOPS-001 V1.1 §4
--
-- 前置条件(由超级用户 postgres 一次性完成,不在本脚本内):
--   CREATE SCHEMA equipment_mgmt AUTHORIZATION cmc_user;
--
-- 执行身份: cmc_user
-- 执行命令:
--   PGPASSWORD='<password>' psql -h 127.0.0.1 -U cmc_user \
--                                 -d <db_name> -f sql/equipment_init.sql
--
-- 关键设计原则(与 material_mgmt 一致):
--   - 软删除: equipment.is_active 标记,禁止物理删除
--   - 时间戳: TIMESTAMP 上海本地时间,应用层 datetime.now() 写入
--   - 金额: NUMERIC(12,2)
--   - created_by 等存 MDM 用户名快照,不对 MDM 库建外键
-- =============================================================================

-- 只设 equipment_mgmt:若 schema 不存在,后续建表会直接报错
-- "no schema has been selected to create in"(fail-fast),
-- 绝不允许静默回落到 search_path 里的其他 schema。
SET search_path TO equipment_mgmt;

-- -----------------------------------------------------------------------------
-- 1. 设备台账主表(equipment)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id      SERIAL PRIMARY KEY,
    -- —— MDM 快照字段(权威源 eqp.equipment,建档/sync-mdm 时整体覆盖) ——
    equipment_code    VARCHAR(32)  NOT NULL,
    equipment_no      VARCHAR(64),                -- V1.4: 业务编号(如 QC001)
    fixed_asset_no    VARCHAR(64),                -- V1.4: 固定资产号
    name              VARCHAR(200) NOT NULL,
    name_en           VARCHAR(255),               -- V1.4: 英文名称
    category          VARCHAR(50)  NOT NULL,
    model             VARCHAR(200),
    manufacturer      VARCHAR(100),
    serial_no         VARCHAR(100),
    rated_power       VARCHAR(64),                -- V1.4: 额定功率
    origin            VARCHAR(100),               -- V1.4: 产地
    supplier          VARCHAR(200),               -- V1.4: 供应商
    has_workstation   BOOLEAN      NOT NULL DEFAULT FALSE,  -- V1.4: 附带工作站
    workstation_info  JSONB,                      -- V1.4: 工作站配置
    purchase_date     DATE,                       -- V1.4: 归属改 MDM 快照
    asset_value       NUMERIC(12,2),              -- V1.4: 归属改 MDM 快照
    mdm_status        VARCHAR(32),                -- V1.4: MDM 主数据状态 active/retired
    mdm_synced_at     TIMESTAMP,                  -- V1.4: 快照同步时间
    -- —— 本地运营字段(LabOps 维护) ——
    location_room     VARCHAR(50),
    location_detail   VARCHAR(200),
    responsible_person VARCHAR(50),
    status            VARCHAR(20)  NOT NULL DEFAULT 'in_use',
    commission_date   DATE,
    remark            TEXT,
    -- MDM 引用: 主数据权威源在 MDM eqp 域
    mdm_equipment_id  BIGINT,
    data_source       VARCHAR(20)  NOT NULL DEFAULT 'local',
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    deactivated_at    TIMESTAMP,
    deactivated_by    VARCHAR(50),
    deactivate_reason VARCHAR(200),
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by        VARCHAR(50),
    updated_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by        VARCHAR(50),

    CONSTRAINT uq_equipment_code UNIQUE (equipment_code),
    CONSTRAINT ck_equipment_status CHECK (status IN ('in_use','out_of_service','scrapped','in_repair','in_calibration'))
);

CREATE INDEX IF NOT EXISTS ix_equipment_category ON equipment(category) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS ix_equipment_status   ON equipment(status) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS ix_equipment_room     ON equipment(location_room);
CREATE INDEX IF NOT EXISTS ix_equipment_responsible ON equipment(responsible_person);

-- updated_at 自动维护(复用 material_mgmt 的触发器函数)
DROP TRIGGER IF EXISTS equipment_updated_at ON equipment;
CREATE TRIGGER equipment_updated_at
    BEFORE UPDATE ON equipment
    FOR EACH ROW EXECUTE FUNCTION material_mgmt.trg_set_updated_at();

-- -----------------------------------------------------------------------------
-- 2. 计量校验记录(equipment_calibration)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_calibration (
    calibration_id      SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment(equipment_id),
    calibration_date    DATE        NOT NULL,
    calibration_agency  VARCHAR(200),
    result              VARCHAR(20) NOT NULL,
    certificate_no      VARCHAR(100),
    next_calibration_date DATE,
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by          VARCHAR(50),

    CONSTRAINT ck_calibration_result CHECK (result IN ('qualified','unqualified','limited_use'))
);

CREATE INDEX IF NOT EXISTS ix_calibration_equipment ON equipment_calibration(equipment_id, calibration_date DESC);
CREATE INDEX IF NOT EXISTS ix_calibration_next_date ON equipment_calibration(next_calibration_date);

-- -----------------------------------------------------------------------------
-- 3. 常规维护记录(equipment_maintenance)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_maintenance (
    maintenance_id      SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment(equipment_id),
    maintenance_date    DATE        NOT NULL,
    maintenance_type    VARCHAR(30) NOT NULL,
    content             TEXT,
    performed_by        VARCHAR(50) NOT NULL,
    next_maintenance_date DATE,
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by          VARCHAR(50),

    CONSTRAINT ck_maintenance_type CHECK (maintenance_type IN ('daily','periodic','special'))
);

CREATE INDEX IF NOT EXISTS ix_maintenance_equipment ON equipment_maintenance(equipment_id, maintenance_date DESC);
CREATE INDEX IF NOT EXISTS ix_maintenance_next_date ON equipment_maintenance(next_maintenance_date);

-- -----------------------------------------------------------------------------
-- 4. 维修记录(equipment_repair)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_repair (
    repair_id           SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment(equipment_id),
    report_date         DATE        NOT NULL,
    fault_description   TEXT        NOT NULL,
    repair_provider     VARCHAR(200),
    repair_type         VARCHAR(20) NOT NULL DEFAULT 'external',
    completion_date     DATE,
    repair_cost         NUMERIC(12,2),
    conclusion          TEXT,
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by          VARCHAR(50),

    CONSTRAINT ck_repair_type CHECK (repair_type IN ('internal','external'))
);

CREATE INDEX IF NOT EXISTS ix_repair_equipment ON equipment_repair(equipment_id, report_date DESC);

-- -----------------------------------------------------------------------------
-- 5. 保修信息(equipment_warranty) — 一台设备一条
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_warranty (
    warranty_id         SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment(equipment_id),
    warranty_start      DATE        NOT NULL,
    warranty_end        DATE        NOT NULL,
    warranty_scope      TEXT,
    provider_name       VARCHAR(200),
    provider_contact    VARCHAR(200),
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_warranty_equipment UNIQUE (equipment_id),
    CONSTRAINT ck_warranty_dates CHECK (warranty_end >= warranty_start)
);

CREATE INDEX IF NOT EXISTS ix_warranty_end ON equipment_warranty(warranty_end);

DROP TRIGGER IF EXISTS warranty_updated_at ON equipment_warranty;
CREATE TRIGGER warranty_updated_at
    BEFORE UPDATE ON equipment_warranty
    FOR EACH ROW EXECUTE FUNCTION material_mgmt.trg_set_updated_at();

-- -----------------------------------------------------------------------------
-- 6. 设备附件(equipment_attachment)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_attachment (
    attachment_id   SERIAL PRIMARY KEY,
    equipment_id    INT          NOT NULL REFERENCES equipment(equipment_id),
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    file_size       INT,
    file_type       VARCHAR(20),
    tag             VARCHAR(30),
    description     VARCHAR(200),
    uploaded_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uploaded_by     VARCHAR(50),

    CONSTRAINT ck_attachment_tag CHECK (tag IS NULL OR tag IN ('sop','certificate','contract','photo','other'))
);

CREATE INDEX IF NOT EXISTS ix_attachment_equipment ON equipment_attachment(equipment_id);

-- -----------------------------------------------------------------------------
-- 7. 到期提醒配置(equipment_reminder)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_reminder (
    reminder_id     SERIAL PRIMARY KEY,
    equipment_id    INT         NOT NULL REFERENCES equipment(equipment_id),
    reminder_type   VARCHAR(30) NOT NULL,
    due_date        DATE        NOT NULL,
    advance_days    INT         NOT NULL DEFAULT 30,
    is_resolved     BOOLEAN     NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMP,
    resolved_by     VARCHAR(50),
    remark          TEXT,
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_reminder_type CHECK (reminder_type IN ('calibration','maintenance','warranty'))
);

CREATE INDEX IF NOT EXISTS ix_reminder_due ON equipment_reminder(due_date) WHERE is_resolved = FALSE;
CREATE INDEX IF NOT EXISTS ix_reminder_equipment ON equipment_reminder(equipment_id);

-- -----------------------------------------------------------------------------
-- 迁移段(对已存在的旧 DB 补齐后加的列;与 init.sql 第 11 节同模式)
-- -----------------------------------------------------------------------------
-- equipment: MDM 引用列(主数据权威源在 MDM eqp 域)
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS mdm_equipment_id BIGINT;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS data_source VARCHAR(20) NOT NULL DEFAULT 'local';

-- equipment: V1.4 适配 MDM eqp 域 V1.2(迁移 0040~0044)新增的快照列
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS equipment_no     VARCHAR(64);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS fixed_asset_no   VARCHAR(64);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS name_en          VARCHAR(255);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS rated_power      VARCHAR(64);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS origin           VARCHAR(100);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS supplier         VARCHAR(200);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS has_workstation  BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS workstation_info JSONB;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS mdm_status       VARCHAR(32);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS mdm_synced_at    TIMESTAMP;
