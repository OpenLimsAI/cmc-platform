-- =============================================================================
-- 文件: sql/init.sql
-- 用途: CMC 物料管理系统数据库初始化脚本
--   1) 在 material_mgmt schema 中创建当前版本所需的 9 张表
--      (material / batch / inventory_txn / location / unit_dict /
--       category_dict / audit_log)
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
--   - material_id 是 SERIAL 主键;material_code 是业务编码,允许 'TT内部物料'
--     这个保留值重复(部分唯一索引实现),其余 code 仍唯一
--   - material_code 用 VARCHAR(20),保留前导 0(如 04xxx 不会被截断)
--   - 库存数量不落表,实时由 inventory_txn 聚合,杜绝账实不符
--   - 所有数量字段用 NUMERIC(12,2) 避免浮点误差
--   - 不修改数据库级 search_path(共享库时绝不污染其他 schema)
--     backend/database.py 在每次连接建立时 SET search_path(会话级)
--   - location 用 (room_no, cabinet_no, layer_no) 三元组定位,name 为
--     计算列拼接展示,无需手填
--   - 同 (material, batch_no) 可分布在多个 location,(material_id, batch_no,
--     location_id) 才唯一,支持"同批次散落多柜"
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
--    用 (room_no, cabinet_no, layer_no) 三元组唯一定位。
--    name 为生成列,前端只展示不输入。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS location (
    location_id        SERIAL PRIMARY KEY,
    room_no            VARCHAR(20) NOT NULL,            -- 房间号,如 '2251'
    cabinet_no         VARCHAR(20) NOT NULL,            -- 柜号,如 'A01' / 'B06' / 'C07'
    layer_no           SMALLINT    NOT NULL,            -- 板层 1~N
    name               VARCHAR(80) GENERATED ALWAYS AS
                       (room_no || '-' || cabinet_no || '-L' || layer_no) STORED,
    storage_condition  VARCHAR(50),                     -- 常温 / 4℃ / -20℃ / -80℃ / 避光
    remark             TEXT,
    CONSTRAINT uq_location_triple UNIQUE (room_no, cabinet_no, layer_no),
    CONSTRAINT ck_location_layer_positive CHECK (layer_no >= 1)
);

CREATE INDEX IF NOT EXISTS idx_location_room ON location(room_no);

-- 预置房间 2251 的全部柜位(A01-A05 / B01-B06 / C01-C07,每柜 5 层)
-- 共 18 × 5 = 90 行;其他房间在前端手工新增。
INSERT INTO location (room_no, cabinet_no, layer_no)
SELECT '2251', cab, layer
FROM (VALUES
    ('A01'),('A02'),('A03'),('A04'),('A05'),
    ('B01'),('B02'),('B03'),('B04'),('B05'),('B06'),
    ('C01'),('C02'),('C03'),('C04'),('C05'),('C06'),('C07')
) AS cabs(cab)
CROSS JOIN generate_series(1, 5) AS layer
ON CONFLICT (room_no, cabinet_no, layer_no) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 5. 物料主数据(material)
--    material_id 是 SERIAL PK;material_code 是业务编码,允许保留值
--    'TT内部物料' 重复出现,其余编码保持唯一(部分唯一索引实现)。
--    hazard_class 为危化品分类多选,允许 NULL 或空数组,字面值在应用层校验
--    (危化品 / 易燃 / 易制毒 / 易制爆 / 剧毒品)。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS material (
    material_id        SERIAL PRIMARY KEY,
    material_code      VARCHAR(20) NOT NULL,
    category           VARCHAR(50),
    -- 入库表单"大类"; 决定入库页面的字段布局
    material_type      VARCHAR(20)  CHECK (material_type IS NULL OR material_type IN ('reagent','consumable','standard','column')),
    name_cn            VARCHAR(200) NOT NULL,
    name_en            VARCHAR(255),                    -- 英文名(MDM 快照)
    grade              VARCHAR(50),
    manufacturer       VARCHAR(100),
    spec_model         VARCHAR(200),
    catalog_no         VARCHAR(100),
    unit               VARCHAR(20)  NOT NULL,
    package_spec       VARCHAR(100),
    hazard_class       TEXT[],                          -- 多选:危化品/易燃/易制毒/易制爆/剧毒品
    remark             TEXT,
    safety_stock       NUMERIC(12,2) DEFAULT 0,
    data_source        VARCHAR(10)  DEFAULT 'local' CHECK (data_source IN ('mdm','local')),
    is_active          BOOLEAN      DEFAULT TRUE,
    deactivated_at     TIMESTAMP,
    deactivated_by     VARCHAR(50),
    deactivate_reason  VARCHAR(200),
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_material_unit
        FOREIGN KEY (unit) REFERENCES unit_dict(unit)
);

-- material_code 部分唯一:保留值 'TT内部物料' 例外,其余必须唯一
CREATE UNIQUE INDEX IF NOT EXISTS uq_material_code_non_tt
    ON material(material_code) WHERE material_code <> 'TT内部物料';

-- 物料常用查询索引
CREATE INDEX IF NOT EXISTS idx_material_code       ON material(material_code);
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
--    (material_id, batch_no, location_id) 联合唯一
--    —— 同一物料同一批号允许散落在多个 location 上独立计数
--       (例:NaCl 批号 A 在 2251-A01-L1 有 20 瓶,2251-C02-L4 还有 15 瓶)
--    location_id 现在是必填:批次必须有物理位置
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch (
    batch_id       SERIAL PRIMARY KEY,
    material_id    INT NOT NULL REFERENCES material(material_id),
    batch_no       VARCHAR(100) NOT NULL,
    expiry_date    DATE,                              -- 部分耗材可空
    location_id    INT NOT NULL REFERENCES location(location_id),
    received_date  DATE NOT NULL,
    initial_qty    NUMERIC(12,2) NOT NULL,
    remark         TEXT,
    -- 入库时所在 tab 的类型, 老批次留 NULL
    intake_type    VARCHAR(20) CHECK (intake_type IS NULL OR intake_type IN ('reagent','consumable','standard','column')),
    -- 入库表单"类型特定"字段, 都是 nullable; 哪类不用就留空
    concentration          VARCHAR(50),     -- 标准物质浓度(数值+单位, 例 "10 mg/mL")
    extinction_coefficient NUMERIC(12, 2),  -- 标准物质消光系数(2 位小数)
    serial_no              VARCHAR(100),    -- 色谱柱厂家序列号
    asset_no               VARCHAR(100),    -- 色谱柱内部编号/资产编号
    responsible_person     VARCHAR(50),     -- 色谱柱负责人
    project_no             VARCHAR(100),    -- 标准品项目编号
    originator_batch_no    VARCHAR(100),    -- 标准品原研药批号
    aliquot_date           DATE,            -- 标准品分装日期
    intake_operator_name   VARCHAR(128),    -- 入库登记操作人姓名(快照)
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_batch_material_no_loc UNIQUE (material_id, batch_no, location_id)
);

CREATE INDEX IF NOT EXISTS idx_batch_material   ON batch(material_id);
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
-- 用户系统 + 审计追踪
-- 这部分在旧服务器上重跑 init.sql 即可获得(IF NOT EXISTS 保证幂等)
-- =============================================================================

-- 注:认证自 v2.0 起统一走 MDM Portal 的 JWT,本系统无本地用户表,
--    原 app_user / auth_session 两表已废弃删除。

-- -----------------------------------------------------------------------------
-- 8. 审计日志(audit_log)
--     before_json / after_json 用 JSONB 存任意结构;敏感字段(password_hash)
--     业务层在写入前抹掉
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INT,                                            -- v2.0 起为 MDM user_id,不再外键 app_user
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
-- 11. 迁移段(对已存在的旧 DB 补齐后加的列/约束)
--     - CREATE TABLE IF NOT EXISTS 不会改老表,所以新增列必须显式 ALTER
--     - 全部使用 ADD COLUMN IF NOT EXISTS,可重复执行
--     - 以后新增字段时,模型/CREATE TABLE 和这里同步追加一行
-- -----------------------------------------------------------------------------

-- material: v1.3 加入 MDM 物料来源标记
ALTER TABLE material
    ADD COLUMN IF NOT EXISTS data_source VARCHAR(10) DEFAULT 'local';
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'material_data_source_check'
    ) THEN
        ALTER TABLE material
            ADD CONSTRAINT material_data_source_check
            CHECK (data_source IN ('mdm','local'));
    END IF;
END$$;

-- material: v1.2 加入 TT 分类
ALTER TABLE material
    ADD COLUMN IF NOT EXISTS material_type VARCHAR(20);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_material_type'
    ) THEN
        ALTER TABLE material
            ADD CONSTRAINT ck_material_type
            CHECK (material_type IS NULL OR material_type IN ('reagent','consumable','standard','column'));
    END IF;
END$$;

-- material: 危化品分类多选
ALTER TABLE material
    ADD COLUMN IF NOT EXISTS hazard_class TEXT[];

-- material: v1.6 英文名(MDM mm.material_name_en 快照)
ALTER TABLE material
    ADD COLUMN IF NOT EXISTS name_en VARCHAR(255);

-- batch: v1.2 加入入库类型及标准物质/色谱柱专属字段
ALTER TABLE batch ADD COLUMN IF NOT EXISTS intake_type             VARCHAR(20);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS concentration           VARCHAR(50);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS extinction_coefficient  NUMERIC(12,2);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS serial_no               VARCHAR(100);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS asset_no                VARCHAR(100);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS responsible_person      VARCHAR(50);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS project_no              VARCHAR(100);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS originator_batch_no     VARCHAR(100);
ALTER TABLE batch ADD COLUMN IF NOT EXISTS aliquot_date            DATE;
ALTER TABLE batch ADD COLUMN IF NOT EXISTS intake_operator_name    VARCHAR(128);

-- audit_log: v2.0 认证对接 MDM 后,user_id 为 MDM user_id,
-- 必须解除指向旧 app_user 的外键,否则 MDM 新用户的所有写操作都会失败
ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_user_id_fkey;

-- -----------------------------------------------------------------------------
-- storage_node: v1.5 存放位置层级树(覆盖层)
--   - 试剂柜:   ROOM → CABINET → CABINET_LAYER(bulk)
--   - 普通冰箱: ROOM → FRIDGE(2-8/-20) → FRIDGE_SHELF(bulk)
--   - -80冰箱:  ROOM → FRIDGE(-80) → RACK → RACK_LAYER → BOX → CELL(cell)  [期2]
--   bulk 叶子(CABINET_LAYER/FRIDGE_SHELF)通过 location_id 1:1 回链到 location,
--   批次仍挂 location_id,现有库存/出入库/移库逻辑零改动;CELL 叶子 location_id 为空。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS storage_node (
    node_id        SERIAL PRIMARY KEY,
    parent_id      INT REFERENCES storage_node(node_id) ON DELETE CASCADE,
    node_type      VARCHAR(20) NOT NULL,                 -- ROOM/CABINET/CABINET_LAYER/FRIDGE/FRIDGE_SHELF/RACK/RACK_LAYER/BOX/CELL
    code           VARCHAR(40) NOT NULL,                 -- 该级编号: '2251'/'A01'/'B'/'3'/'A'/'23'
    label          VARCHAR(80),                          -- 展示名(缺省=code), 冰箱可填别名如 'TT3'
    path           VARCHAR(255),                         -- 维护的全路径 '2251 / TT3 / B / 3 / A / 23'
    depth          SMALLINT NOT NULL DEFAULT 0,          -- 根=0
    sort_order     INT NOT NULL DEFAULT 0,               -- 同级稳定排序(字母 A=1,B=2…)
    capacity_kind  VARCHAR(10),                          -- 叶子: 'bulk'/'cell'; 非叶 NULL
    location_id    INT REFERENCES location(location_id), -- bulk 叶子回链 location; 否则 NULL
    temp_category  VARCHAR(20),                          -- 仅 FRIDGE: normal/2-8/-20/-80
    temp_text      VARCHAR(50),                          -- 温区可读文本 '-20~-40℃'
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    remark         TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_storage_node_type CHECK (node_type IN
        ('ROOM','CABINET','CABINET_LAYER','FRIDGE','FRIDGE_SHELF','RACK','RACK_LAYER','BOX','CELL')),
    CONSTRAINT ck_storage_capacity_kind CHECK (capacity_kind IS NULL OR capacity_kind IN ('bulk','cell'))
);
-- 同父下编号唯一(根节点 parent NULL 用 COALESCE 折叠成 0)
CREATE UNIQUE INDEX IF NOT EXISTS uq_storage_sibling
    ON storage_node (COALESCE(parent_id, 0), code);
CREATE INDEX IF NOT EXISTS ix_storage_parent ON storage_node (parent_id);
CREATE INDEX IF NOT EXISTS ix_storage_type   ON storage_node (node_type);
CREATE INDEX IF NOT EXISTS ix_storage_loc    ON storage_node (location_id);

-- 回填: 从现有 location 三元组生成 ROOM/CABINET/CABINET_LAYER 树(幂等: 已有数据则跳过)
DO $$
DECLARE
    loc   RECORD;
    v_room INT;
    v_cab  INT;
BEGIN
    IF EXISTS (SELECT 1 FROM storage_node) THEN
        RETURN;  -- 已迁移过, 不重复
    END IF;
    FOR loc IN SELECT * FROM location ORDER BY room_no, cabinet_no, layer_no LOOP
        -- 房间
        SELECT node_id INTO v_room FROM storage_node
            WHERE parent_id IS NULL AND node_type = 'ROOM' AND code = loc.room_no;
        IF v_room IS NULL THEN
            INSERT INTO storage_node (parent_id, node_type, code, label, path, depth, sort_order)
            VALUES (NULL, 'ROOM', loc.room_no, loc.room_no, loc.room_no, 0, 0)
            RETURNING node_id INTO v_room;
        END IF;
        -- 试剂柜
        SELECT node_id INTO v_cab FROM storage_node
            WHERE parent_id = v_room AND node_type = 'CABINET' AND code = loc.cabinet_no;
        IF v_cab IS NULL THEN
            INSERT INTO storage_node (parent_id, node_type, code, label, path, depth, sort_order)
            VALUES (v_room, 'CABINET', loc.cabinet_no, loc.cabinet_no,
                    loc.room_no || ' / ' || loc.cabinet_no, 1, 0)
            RETURNING node_id INTO v_cab;
        END IF;
        -- 板层(bulk 叶子, 回链 location)
        INSERT INTO storage_node
            (parent_id, node_type, code, label, path, depth, sort_order, capacity_kind, location_id)
        VALUES (v_cab, 'CABINET_LAYER', loc.layer_no::text, 'L' || loc.layer_no,
                loc.room_no || ' / ' || loc.cabinet_no || ' / L' || loc.layer_no,
                2, loc.layer_no, 'bulk', loc.location_id);
    END LOOP;
END$$;

-- -----------------------------------------------------------------------------
-- cell_occupancy: v1.5 期2 -80℃ 孔位单占用("一孔一管")
--   空孔 = 没有 status='stored' 的行;部分唯一索引保证一孔最多一管。
--   batch_id 复用现有批次(锚在 -80 冰箱的 location 上);占用数与 inventory_txn 对账:
--     SUM(inventory_txn.qty for batch) = 该批次当前占用孔数 = stored 行数。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cell_occupancy (
    occupancy_id  SERIAL PRIMARY KEY,
    cell_node_id  INT NOT NULL REFERENCES storage_node(node_id) ON DELETE CASCADE,
    batch_id      INT NOT NULL REFERENCES batch(batch_id),
    sample_label  VARCHAR(100),                          -- 管标签/样品号, 选填
    status        VARCHAR(10) NOT NULL DEFAULT 'stored', -- stored / removed(留痕软删)
    stored_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stored_by     VARCHAR(50),
    removed_at    TIMESTAMP,
    remark        TEXT,
    CONSTRAINT ck_cell_occ_status CHECK (status IN ('stored','removed'))
);
-- 一个孔最多一条在存记录
CREATE UNIQUE INDEX IF NOT EXISTS uq_cell_occupied
    ON cell_occupancy (cell_node_id) WHERE status = 'stored';
CREATE INDEX IF NOT EXISTS ix_cell_occ_batch ON cell_occupancy (batch_id);
CREATE INDEX IF NOT EXISTS ix_cell_occ_label ON cell_occupancy (sample_label);

-- -----------------------------------------------------------------------------
-- 完成
-- -----------------------------------------------------------------------------
