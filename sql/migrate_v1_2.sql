-- =============================================================================
-- 文件: sql/migrate_v1_2.sql
-- 用途: v1.1 → v1.2 增量迁移
--   1) material: 加 material_id PK + hazard_class TEXT[];material_code 改为
--      可重复(部分唯一索引例外 'TT内部物料')
--   2) location: 拆为 (room_no, cabinet_no, layer_no) 三字段;name 变生成列;
--      预置 2251 房间 90 个柜位
--   3) batch: 改用 material_id FK;同 (material_id, batch_no, location_id)
--      唯一,允许同批次散落多位置;location_id 改为 NOT NULL
--
-- 设计原则:
--   - 幂等:可重复执行;条件块只在状态未达成时改一次
--   - 不丢数据:旧 location 用 '迁移占位' room 兜底保留;NULL location
--     的 batch 自动绑到一个 '未指定' 占位行,后续可在 UI 改
--
-- 执行(Linux 上以 cmc_user 身份):
--   PGPASSWORD='<password>' psql -h 127.0.0.1 -U cmc_user \
--       -d cmc_data_platform -v ON_ERROR_STOP=1 -f sql/migrate_v1_2.sql
--
-- 强烈建议执行前先备份:
--   pg_dump -h 127.0.0.1 -U postgres -n material_mgmt \
--           cmc_data_platform > backup_pre_v1_2.sql
-- =============================================================================

SET search_path TO material_mgmt, public;

-- 单事务,出错全部回滚
BEGIN;

-- ---------------------------------------------------------------------------
-- 1. material:加 material_id (SERIAL PK) + hazard_class
-- ---------------------------------------------------------------------------

-- 1.1 加 hazard_class(可空)
ALTER TABLE material ADD COLUMN IF NOT EXISTS hazard_class TEXT[];

-- 1.2 加 material_id 列 + 序列;先填值再加 NOT NULL
ALTER TABLE material ADD COLUMN IF NOT EXISTS material_id INT;

DO $$
BEGIN
    -- 序列必须在 material_id 列存在后才能 OWNED BY,故放在列添加之后
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relkind='S' AND n.nspname='material_mgmt'
          AND c.relname='material_material_id_seq'
    ) THEN
        CREATE SEQUENCE material_material_id_seq OWNED BY material.material_id;
    END IF;
END $$;

UPDATE material SET material_id = nextval('material_material_id_seq')
 WHERE material_id IS NULL;

ALTER TABLE material ALTER COLUMN material_id SET NOT NULL;
ALTER TABLE material ALTER COLUMN material_id
    SET DEFAULT nextval('material_material_id_seq');

-- 1.3 主键切换:material_code → material_id
--     (跑 init.sql 后已经是 material_id PK 的库会自动跳过)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema='material_mgmt' AND table_name='material'
          AND constraint_type='PRIMARY KEY' AND constraint_name='material_pkey'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE table_schema='material_mgmt' AND constraint_name='material_pkey'
          AND column_name='material_code'
    ) THEN
        -- 先把 batch 上引用 material_code 的 FK 拆掉(下面 #3 再重建到 material_id)
        ALTER TABLE batch DROP CONSTRAINT IF EXISTS batch_material_code_fkey;
        ALTER TABLE material DROP CONSTRAINT material_pkey;
        ALTER TABLE material ADD CONSTRAINT material_pkey PRIMARY KEY (material_id);
    END IF;
END $$;

-- 1.4 material_code 部分唯一索引:'TT内部物料' 例外
CREATE UNIQUE INDEX IF NOT EXISTS uq_material_code_non_tt
    ON material(material_code) WHERE material_code <> 'TT内部物料';

CREATE INDEX IF NOT EXISTS idx_material_code ON material(material_code);

-- ---------------------------------------------------------------------------
-- 2. location:拆三字段 + 生成列 name + 预置 2251 房间
-- ---------------------------------------------------------------------------

-- 2.1 加三字段(允许临时为空,backfill 后再设 NOT NULL)
ALTER TABLE location ADD COLUMN IF NOT EXISTS room_no    VARCHAR(20);
ALTER TABLE location ADD COLUMN IF NOT EXISTS cabinet_no VARCHAR(20);
ALTER TABLE location ADD COLUMN IF NOT EXISTS layer_no   SMALLINT;

-- 2.2 旧行回填:把 name 当 cabinet,room='迁移占位',layer=1
--     旧 4 个预置 location(常温库房-A区 等)不删,改为占位条目,前端可改名
UPDATE location
   SET room_no    = COALESCE(room_no, '迁移占位'),
       cabinet_no = COALESCE(cabinet_no, LEFT(name, 20)),
       layer_no   = COALESCE(layer_no, 1)
 WHERE room_no IS NULL OR cabinet_no IS NULL OR layer_no IS NULL;

-- 2.3 NOT NULL + CHECK
ALTER TABLE location ALTER COLUMN room_no    SET NOT NULL;
ALTER TABLE location ALTER COLUMN cabinet_no SET NOT NULL;
ALTER TABLE location ALTER COLUMN layer_no   SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_location_layer_positive') THEN
        ALTER TABLE location ADD CONSTRAINT ck_location_layer_positive CHECK (layer_no >= 1);
    END IF;
END $$;

-- 2.4 旧 UNIQUE(name) 拆掉,改 (room,cabinet,layer) 唯一
ALTER TABLE location DROP CONSTRAINT IF EXISTS location_name_key;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_location_triple') THEN
        ALTER TABLE location ADD CONSTRAINT uq_location_triple UNIQUE (room_no, cabinet_no, layer_no);
    END IF;
END $$;

-- 2.5 name 改成生成列(从原 VARCHAR(100) 转换)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='material_mgmt' AND table_name='location'
          AND column_name='name' AND is_generated='NEVER'
    ) THEN
        ALTER TABLE location DROP COLUMN name;
        ALTER TABLE location ADD COLUMN name VARCHAR(80) GENERATED ALWAYS AS
            (room_no || '-' || cabinet_no || '-L' || layer_no) STORED;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_location_room ON location(room_no);

-- 2.6 预置 2251 房间(18 柜 × 5 层)
INSERT INTO location (room_no, cabinet_no, layer_no)
SELECT '2251', cab, layer
FROM (VALUES
    ('A01'),('A02'),('A03'),('A04'),('A05'),
    ('B01'),('B02'),('B03'),('B04'),('B05'),('B06'),
    ('C01'),('C02'),('C03'),('C04'),('C05'),('C06'),('C07')
) AS cabs(cab)
CROSS JOIN generate_series(1, 5) AS layer
ON CONFLICT (room_no, cabinet_no, layer_no) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3. batch:material_code → material_id FK;(mat_id,batch_no,loc_id) 唯一
-- ---------------------------------------------------------------------------

-- 3.1 加 material_id 列
ALTER TABLE batch ADD COLUMN IF NOT EXISTS material_id INT;

-- 3.2 backfill material_id(若 batch 仍有 material_code 列)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='material_mgmt' AND table_name='batch'
          AND column_name='material_code'
    ) THEN
        UPDATE batch b
           SET material_id = m.material_id
          FROM material m
         WHERE b.material_id IS NULL AND b.material_code = m.material_code;
    END IF;
END $$;

-- 3.3 NULL location 兜底:迁前的批次若没指定位置,统一绑到占位行
INSERT INTO location (room_no, cabinet_no, layer_no)
VALUES ('迁移占位', '未指定', 1)
ON CONFLICT (room_no, cabinet_no, layer_no) DO NOTHING;

UPDATE batch
   SET location_id = (SELECT location_id FROM location
                       WHERE room_no='迁移占位' AND cabinet_no='未指定' AND layer_no=1)
 WHERE location_id IS NULL;

-- 3.4 NOT NULL + 新约束
ALTER TABLE batch ALTER COLUMN material_id SET NOT NULL;
ALTER TABLE batch ALTER COLUMN location_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='batch_material_id_fkey') THEN
        ALTER TABLE batch ADD CONSTRAINT batch_material_id_fkey
            FOREIGN KEY (material_id) REFERENCES material(material_id);
    END IF;
END $$;

-- 3.5 删旧唯一(material_code, batch_no);加新唯一三键
ALTER TABLE batch DROP CONSTRAINT IF EXISTS uq_batch_material_no;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_batch_material_no_loc') THEN
        ALTER TABLE batch ADD CONSTRAINT uq_batch_material_no_loc
            UNIQUE (material_id, batch_no, location_id);
    END IF;
END $$;

-- 3.6 删 material_code 列(已无人引用)
DROP INDEX IF EXISTS idx_batch_material;  -- 旧索引在 material_code 上
ALTER TABLE batch DROP COLUMN IF EXISTS material_code;
CREATE INDEX IF NOT EXISTS idx_batch_material ON batch(material_id);

COMMIT;

-- ---------------------------------------------------------------------------
-- 完成
-- ---------------------------------------------------------------------------
\echo '✅ v1.2 schema 迁移完成'
\echo '提醒:'
\echo '  - 旧预置 location 已变成 room=迁移占位 的条目,前端可重命名或删除'
\echo '  - 原本 location 为空的批次已绑到 (迁移占位, 未指定, 1),请在前端补正确位置'
