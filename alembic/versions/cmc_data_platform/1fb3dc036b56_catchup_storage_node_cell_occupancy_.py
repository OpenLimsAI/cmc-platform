"""catchup storage_node cell_occupancy equipment_mdm_cols

追认 2026-06-04 baseline 之后、未走 alembic 直接落到真实库的 cmc_data_platform 结构变更：
  - material_mgmt.storage_node   （存储节点树）
  - material_mgmt.cell_occupancy （库位占用）
  - equipment_mgmt.equipment     （新增 10 个设备/MDM 字段）

DDL 直接取自真实库（Mac/Linux 两端一致），与现状一字不差。
真实库已存在这些对象，请用 `stamp`（见 SOP）记账，勿对真实库重跑 upgrade；
此迁移仅用于从空库重建时一并建出。

Revision ID: 1fb3dc036b56
Revises: cmc_data_platform_baseline
Create Date: 2026-06-09 10:30:20.592592
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '1fb3dc036b56'
down_revision = 'cmc_data_platform_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- material_mgmt.storage_node（先建，被 cell_occupancy 外键引用）-----------
    op.execute("""
        CREATE TABLE material_mgmt.storage_node (
            node_id integer NOT NULL,
            parent_id integer,
            node_type character varying(20) NOT NULL,
            code character varying(40) NOT NULL,
            label character varying(80),
            path character varying(255),
            depth smallint DEFAULT 0 NOT NULL,
            sort_order integer DEFAULT 0 NOT NULL,
            capacity_kind character varying(10),
            location_id integer,
            temp_category character varying(20),
            temp_text character varying(50),
            is_active boolean DEFAULT true NOT NULL,
            remark text,
            created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
            CONSTRAINT ck_storage_capacity_kind CHECK (capacity_kind IS NULL OR capacity_kind IN ('bulk', 'cell')),
            CONSTRAINT ck_storage_node_type CHECK (node_type IN ('ROOM', 'CABINET', 'CABINET_LAYER', 'FRIDGE', 'FRIDGE_SHELF', 'RACK', 'RACK_LAYER', 'BOX', 'CELL'))
        );
    """)
    op.execute("""
        CREATE SEQUENCE material_mgmt.storage_node_node_id_seq
            AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
    """)
    op.execute("ALTER SEQUENCE material_mgmt.storage_node_node_id_seq OWNED BY material_mgmt.storage_node.node_id;")
    op.execute("ALTER TABLE ONLY material_mgmt.storage_node ALTER COLUMN node_id SET DEFAULT nextval('material_mgmt.storage_node_node_id_seq'::regclass);")
    op.execute("ALTER TABLE ONLY material_mgmt.storage_node ADD CONSTRAINT storage_node_pkey PRIMARY KEY (node_id);")
    op.execute("CREATE INDEX ix_storage_loc ON material_mgmt.storage_node USING btree (location_id);")
    op.execute("CREATE INDEX ix_storage_parent ON material_mgmt.storage_node USING btree (parent_id);")
    op.execute("CREATE INDEX ix_storage_type ON material_mgmt.storage_node USING btree (node_type);")
    op.execute("CREATE UNIQUE INDEX uq_storage_sibling ON material_mgmt.storage_node USING btree (COALESCE(parent_id, 0), code);")
    op.execute("ALTER TABLE ONLY material_mgmt.storage_node ADD CONSTRAINT storage_node_location_id_fkey FOREIGN KEY (location_id) REFERENCES material_mgmt.location(location_id);")
    op.execute("ALTER TABLE ONLY material_mgmt.storage_node ADD CONSTRAINT storage_node_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES material_mgmt.storage_node(node_id) ON DELETE CASCADE;")

    # ---- material_mgmt.cell_occupancy ------------------------------------------
    op.execute("""
        CREATE TABLE material_mgmt.cell_occupancy (
            occupancy_id integer NOT NULL,
            cell_node_id integer NOT NULL,
            batch_id integer NOT NULL,
            sample_label character varying(100),
            status character varying(10) DEFAULT 'stored'::character varying NOT NULL,
            stored_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
            stored_by character varying(50),
            removed_at timestamp without time zone,
            remark text,
            CONSTRAINT ck_cell_occ_status CHECK (status IN ('stored', 'removed'))
        );
    """)
    op.execute("""
        CREATE SEQUENCE material_mgmt.cell_occupancy_occupancy_id_seq
            AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
    """)
    op.execute("ALTER SEQUENCE material_mgmt.cell_occupancy_occupancy_id_seq OWNED BY material_mgmt.cell_occupancy.occupancy_id;")
    op.execute("ALTER TABLE ONLY material_mgmt.cell_occupancy ALTER COLUMN occupancy_id SET DEFAULT nextval('material_mgmt.cell_occupancy_occupancy_id_seq'::regclass);")
    op.execute("ALTER TABLE ONLY material_mgmt.cell_occupancy ADD CONSTRAINT cell_occupancy_pkey PRIMARY KEY (occupancy_id);")
    op.execute("CREATE INDEX ix_cell_occ_batch ON material_mgmt.cell_occupancy USING btree (batch_id);")
    op.execute("CREATE INDEX ix_cell_occ_label ON material_mgmt.cell_occupancy USING btree (sample_label);")
    op.execute("CREATE UNIQUE INDEX uq_cell_occupied ON material_mgmt.cell_occupancy USING btree (cell_node_id) WHERE ((status)::text = 'stored'::text);")
    op.execute("ALTER TABLE ONLY material_mgmt.cell_occupancy ADD CONSTRAINT cell_occupancy_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES material_mgmt.batch(batch_id);")
    op.execute("ALTER TABLE ONLY material_mgmt.cell_occupancy ADD CONSTRAINT cell_occupancy_cell_node_id_fkey FOREIGN KEY (cell_node_id) REFERENCES material_mgmt.storage_node(node_id) ON DELETE CASCADE;")

    # ---- equipment_mgmt.equipment：新增 10 列（按真实库 ordinal 顺序）-----------
    op.execute("""
        ALTER TABLE equipment_mgmt.equipment
            ADD COLUMN equipment_no     character varying(64),
            ADD COLUMN fixed_asset_no   character varying(64),
            ADD COLUMN name_en          character varying(255),
            ADD COLUMN rated_power      character varying(64),
            ADD COLUMN origin           character varying(100),
            ADD COLUMN supplier         character varying(200),
            ADD COLUMN has_workstation  boolean DEFAULT false NOT NULL,
            ADD COLUMN workstation_info jsonb,
            ADD COLUMN mdm_status       character varying(32),
            ADD COLUMN mdm_synced_at    timestamp without time zone;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE equipment_mgmt.equipment
            DROP COLUMN mdm_synced_at,
            DROP COLUMN mdm_status,
            DROP COLUMN workstation_info,
            DROP COLUMN has_workstation,
            DROP COLUMN supplier,
            DROP COLUMN origin,
            DROP COLUMN rated_power,
            DROP COLUMN name_en,
            DROP COLUMN fixed_asset_no,
            DROP COLUMN equipment_no;
    """)
    # cell_occupancy 先删（外键依赖 storage_node）；序列随表 DROP 一并消失
    op.execute("DROP TABLE material_mgmt.cell_occupancy;")
    op.execute("DROP TABLE material_mgmt.storage_node;")
