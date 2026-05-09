-- =============================================================================
-- 文件: sql/init.sql
-- 用途: CMC 物料管理系统 MVP 数据库初始化脚本
--   1) 在 material_mgmt schema 中创建 7 张核心表
--      (material / batch / inventory_txn / location / unit_dict /
--       category_dict / import_log)
--   2) 预置单位字典初始值
--   3) 创建必要索引
--
-- 前置条件(由超级用户 postgres 一次性完成,不在本脚本内):
--   CREATE USER cmc_user WITH PASSWORD '<your-password>';
--   CREATE SCHEMA material_mgmt AUTHORIZATION cmc_user;
--   GRANT CONNECT ON DATABASE <db_name> TO cmc_user;
--
-- 执行身份: cmc_user(在自己 schema 内有完整 DDL 权限)
-- 执行命令:
--   PGPASSWORD='<password>' psql -h 127.0.0.1 -U cmc_user \
--                                 -d <db_name> -f sql/init.sql
--
-- 关键设计原则:
--   - material_code 用 VARCHAR(20),保留前导 0(如 04xxx 不会被截断)
--   - 库存数量不落表,实时由 inventory_txn 聚合,杜绝账实不符
--   - 所有数量字段用 NUMERIC(12,2) 避免浮点误差
--   - 不修改数据库级 search_path(共享库时绝不污染其他 schema)
--     backend/database.py 在每次连接建立时 SET search_path(会话级)
-- =============================================================================

-- 仅本脚本会话使用,影响范围 = 当前 psql 进程
SET search_path TO material_mgmt, public;

-- -----------------------------------------------------------------------------
-- 1. 单位字典(unit_dict)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS unit_dict (
    unit         VARCHAR(20) PRIMARY KEY,
    description  VARCHAR(100)
);

-- 预置常用单位(从导入样本提取)
INSERT INTO unit_dict (unit, description) VALUES
    ('张',  '张'),
    ('卷',  '卷'),
    ('个',  '个'),
    ('盒',  '盒'),
    ('包',  '包'),
    ('根',  '根'),
    ('袋',  '袋'),
    ('瓶',  '瓶'),
    ('把',  '把'),
    ('支',  '支'),
    ('kg',  '千克'),
    ('g',   '克'),
    ('mg',  '毫克'),
    ('mL',  '毫升'),
    ('L',   '升')
ON CONFLICT (unit) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. 分类字典(category_dict)
--    初始为空,导入时自动从文件提取唯一值入库
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS category_dict (
    category VARCHAR(50) PRIMARY KEY
);

-- -----------------------------------------------------------------------------
-- 3. 储存位置(location)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS location (
    location_id        SERIAL PRIMARY KEY,
    name               VARCHAR(100) NOT NULL UNIQUE,
    storage_condition  VARCHAR(50),  -- 常温 / 4℃ / -20℃ / -80℃ / 避光
    remark             TEXT
);

-- 预置几个常见位置(可在前端再增删)
INSERT INTO location (name, storage_condition) VALUES
    ('常温库房-A区',  '常温'),
    ('4℃冰箱A-2层',  '4℃'),
    ('-20℃冰箱',     '-20℃'),
    ('-80℃超低温冰箱','-80℃')
ON CONFLICT (name) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 4. 导入日志(import_log)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS import_log (
    import_id     SERIAL PRIMARY KEY,
    file_name     VARCHAR(200),
    imported_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operator      VARCHAR(50),
    total_rows    INT DEFAULT 0,
    inserted_rows INT DEFAULT 0,
    updated_rows  INT DEFAULT 0,
    failed_rows   INT DEFAULT 0,
    error_detail  JSONB
);

-- -----------------------------------------------------------------------------
-- 5. 物料主数据(material)
--    material_code 严格保留前导 0 → VARCHAR(20)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS material (
    material_code      VARCHAR(20) PRIMARY KEY,
    category           VARCHAR(50),
    name_cn            VARCHAR(200) NOT NULL,
    grade              VARCHAR(50),
    manufacturer       VARCHAR(100),
    spec_model         VARCHAR(200),
    catalog_no         VARCHAR(100),
    unit               VARCHAR(20)  NOT NULL,
    package_spec       VARCHAR(100),
    remark             TEXT,
    safety_stock       NUMERIC(12,2) DEFAULT 0,
    is_active          BOOLEAN      DEFAULT TRUE,
    deactivated_at     TIMESTAMP,
    deactivated_by     VARCHAR(50),
    deactivate_reason  VARCHAR(200),
    import_batch_id    INT REFERENCES import_log(import_id) ON DELETE SET NULL,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_material_unit
        FOREIGN KEY (unit) REFERENCES unit_dict(unit)
);

-- 物料常用查询索引
CREATE INDEX IF NOT EXISTS idx_material_category   ON material(category);
CREATE INDEX IF NOT EXISTS idx_material_is_active  ON material(is_active);
CREATE INDEX IF NOT EXISTS idx_material_name       ON material(name_cn);

-- updated_at 自动维护触发器
CREATE OR REPLACE FUNCTION trg_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS material_updated_at ON material;
CREATE TRIGGER material_updated_at
    BEFORE UPDATE ON material
    FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- -----------------------------------------------------------------------------
-- 6. 批次(batch)
--    (material_code, batch_no) 联合唯一
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch (
    batch_id       SERIAL PRIMARY KEY,
    material_code  VARCHAR(20) NOT NULL REFERENCES material(material_code),
    batch_no       VARCHAR(100) NOT NULL,
    expiry_date    DATE,                              -- 部分耗材可空
    location_id    INT REFERENCES location(location_id),
    received_date  DATE NOT NULL,
    initial_qty    NUMERIC(12,2) NOT NULL,
    remark         TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_batch_material_no UNIQUE (material_code, batch_no)
);

CREATE INDEX IF NOT EXISTS idx_batch_material   ON batch(material_code);
CREATE INDEX IF NOT EXISTS idx_batch_expiry     ON batch(expiry_date);
CREATE INDEX IF NOT EXISTS idx_batch_location   ON batch(location_id);

-- -----------------------------------------------------------------------------
-- 7. 出入库流水(inventory_txn) - 库存计算的唯一来源
--    qty: 入库为正,出库为负,调整可正可负
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory_txn (
    txn_id      SERIAL PRIMARY KEY,
    batch_id    INT NOT NULL REFERENCES batch(batch_id),
    txn_type    VARCHAR(10) NOT NULL CHECK (txn_type IN ('IN','OUT','ADJUST')),
    qty         NUMERIC(12,2) NOT NULL,
    txn_date    DATE NOT NULL,
    operator    VARCHAR(50) NOT NULL,
    purpose     VARCHAR(200),
    remark      TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_txn_batch  ON inventory_txn(batch_id);
CREATE INDEX IF NOT EXISTS idx_txn_date   ON inventory_txn(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_type   ON inventory_txn(txn_type);

-- =============================================================================
-- v1.1 — 用户系统 + 审计追踪(C 阶段)
-- 这部分在 v1.0 服务器上重跑 init.sql 即可获得(IF NOT EXISTS 保证幂等)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 8. 应用账号(app_user)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_user (
    id                    SERIAL PRIMARY KEY,
    username              VARCHAR(50)  NOT NULL UNIQUE,
    password_hash         VARCHAR(255) NOT NULL,            -- bcrypt
    role                  VARCHAR(20)  NOT NULL CHECK (role IN ('admin','user')),
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
    must_change_password  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at         TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_user_active ON app_user(is_active);

-- -----------------------------------------------------------------------------
-- 9. 会话/Token(auth_session)
--    随机 hex token,落库便于主动失效
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auth_session (
    token         VARCHAR(64) PRIMARY KEY,
    user_id       INT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP NOT NULL,
    last_seen_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_ip     VARCHAR(45)
);

CREATE INDEX IF NOT EXISTS idx_auth_session_user    ON auth_session(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_session_expires ON auth_session(expires_at);

-- -----------------------------------------------------------------------------
-- 10. 审计日志(audit_log)
--     before_json / after_json 用 JSONB 存任意结构;敏感字段(password_hash)
--     业务层在写入前抹掉
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INT REFERENCES app_user(id) ON DELETE SET NULL,
    username     VARCHAR(50),                                    -- 冗余,user 删除后仍可查
    action       VARCHAR(50) NOT NULL,                           -- 例: material.create / inventory.in
    entity_type  VARCHAR(50),                                    -- 例: material / batch / inventory_txn
    entity_id    VARCHAR(50),                                    -- 用 string,既能放 SERIAL 整数也能放 material_code
    before_json  JSONB,
    after_json   JSONB,
    source_ip    VARCHAR(45),
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_user_time   ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity_time ON audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action_time ON audit_log(action, created_at DESC);

-- -----------------------------------------------------------------------------
-- 完成
-- -----------------------------------------------------------------------------
