"""ARCH12 G3.A 建 meta.lookup_value + meta.system_config（DM V1.1 §5.2 / §5.3）

Revision ID: 0030_meta_lookup_config
Revises: 0029_baseline_align_arp
Create Date: 2026-05-13 02:00:00.000000

ARCH-MDM-001 V1.1 / DM-MDM-001 V1.1 §6.1 行 727：meta schema 设计三张表
（code_sequence / lookup_value / system_config）；当前仅 code_sequence 落地
（0001_init_schemas）。本 migration 补齐另外两张表 + 按 DM V1.1 §5.2 / §5.3
seed 初始数据。

业务上：
- meta.lookup_value：所有 enum / status / type 的中英文展示字典（前端只读使用）
- meta.system_config：运行时配置项（密码策略 / token 期限 / 审计保留期 等）

应用层 Phase 5 Admin UI 接入后才会真正"动态生效"；目前先建表 + seed
保证 schema 与设计基准对齐。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_meta_lookup_config"
down_revision: str | None = "0029_baseline_align_arp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== meta.lookup_value ==============
    op.create_table(
        "lookup_value",
        sa.Column("lookup_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("lookup_type", sa.String(64), nullable=False),
        sa.Column("lookup_code", sa.String(64), nullable=False),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("lookup_name_en", sa.String(128)),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("description", sa.Text),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("lookup_type", "lookup_code", name="uq_lookup_type_code"),
        schema="meta",
    )
    op.execute(
        "CREATE INDEX ix_lookup_type ON meta.lookup_value(lookup_type, sort_order) "
        "WHERE is_active = TRUE"
    )

    # ============== meta.system_config ==============
    op.create_table(
        "system_config",
        sa.Column("config_key", sa.String(64), primary_key=True),
        sa.Column("config_value", sa.Text, nullable=False),
        sa.Column(
            "value_type", sa.String(16), nullable=False, server_default="string"
        ),
        sa.Column("description", sa.Text),
        sa.Column("is_sensitive", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger),
        sa.CheckConstraint(
            "value_type IN ('string','int','bool','json')",
            name="ck_config_type",
        ),
        schema="meta",
    )

    # ============== seed lookup_value（DM V1.1 §5.2 设计示例）==============
    op.execute(
        """
        INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order) VALUES
            -- substance 状态
            ('substance_status', 'draft',       '草稿',     'Draft',       10),
            ('substance_status', 'registered',  '已注册',   'Registered',  20),
            ('substance_status', 'active',      '活跃',     'Active',      30),
            ('substance_status', 'restricted',  '受限',     'Restricted',  40),
            ('substance_status', 'deprecated',  '已弃用',   'Deprecated',  50),
            ('substance_status', 'obsoleted',   '已废止',   'Obsoleted',   60),
            -- substance 类型
            ('substance_type', 'mab',            '单克隆抗体',  'Monoclonal Antibody', 10),
            ('substance_type', 'bispecific',     '双特异性抗体','Bispecific Antibody', 20),
            ('substance_type', 'adc',            'ADC',         'Antibody-Drug Conjugate', 30),
            ('substance_type', 'fusion',         '融合蛋白',    'Fusion Protein', 40),
            ('substance_type', 'small_molecule', '小分子',      'Small Molecule', 50),
            ('substance_type', 'oligonucleotide','寡核苷酸',    'Oligonucleotide', 60),
            ('substance_type', 'other',          '其他',        'Other',           99),
            -- 项目状态
            ('project_status', 'proposed',   '已提议', 'Proposed',   10),
            ('project_status', 'initiated',  '已启动', 'Initiated',  20),
            ('project_status', 'active',     '进行中', 'Active',     30),
            ('project_status', 'on_hold',    '暂停',   'On Hold',    40),
            ('project_status', 'completed',  '已完成', 'Completed',  50),
            ('project_status', 'terminated', '已终止', 'Terminated', 60),
            -- 项目类型
            ('project_type', 'cmc',         'CMC 项目',     'CMC Project',         10),
            ('project_type', 'preclinical', '临床前',       'Pre-Clinical',        20),
            ('project_type', 'clinical',    '临床',         'Clinical',            30),
            ('project_type', 'regulatory',  '注册',         'Regulatory',          40),
            ('project_type', 'commercial',  '商业化',       'Commercial',          50),
            -- 资产阶段
            ('asset_phase', 'discovery',   '发现',         'Discovery',     10),
            ('asset_phase', 'preclinical', '临床前',       'Pre-Clinical',  20),
            ('asset_phase', 'phase_1',     'I 期',         'Phase I',       30),
            ('asset_phase', 'phase_2',     'II 期',        'Phase II',      40),
            ('asset_phase', 'phase_3',     'III 期',       'Phase III',     50),
            ('asset_phase', 'submission',  '申报',         'Submission',    60),
            ('asset_phase', 'approved',    '已批准',       'Approved',      70),
            ('asset_phase', 'marketed',    '已上市',       'Marketed',      80),
            ('asset_phase', 'discontinued','已停止上市',   'Discontinued',  90)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING;
        """
    )

    # ============== seed system_config（DM V1.1 §5.3 设计示例）==============
    op.execute(
        """
        INSERT INTO meta.system_config (config_key, config_value, value_type, description) VALUES
            ('password.min_length',          '12',     'int',  '密码最小长度'),
            ('password.expire_days',         '90',     'int',  '密码有效期（天）'),
            ('password.history_count',       '5',      'int',  '不可重复使用最近 N 个密码'),
            ('login.max_failed_attempts',    '5',      'int',  '最大连续失败次数'),
            ('login.lock_duration_minutes',  '30',     'int',  '锁定时长'),
            ('session.access_token_minutes', '30',     'int',  'Access Token 有效期'),
            ('session.refresh_token_days',   '7',      'int',  'Refresh Token 有效期'),
            ('audit.retention_years',        '10',     'int',  '审计日志保留年限'),
            ('app.timezone_default',         'Asia/Shanghai', 'string', '默认显示时区'),
            ('app.locale_default',           'zh-CN',  'string', '默认语言')
        ON CONFLICT (config_key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("system_config", schema="meta")
    op.execute("DROP INDEX IF EXISTS meta.ix_lookup_type")
    op.drop_table("lookup_value", schema="meta")
