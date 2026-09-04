"""cmc_analytics: 工艺草稿——新建 batch.plan_draft（录入/复核分离 + 自动保存，2026-09-04）

背景：发放页画好的扩增计划在点「发放批号」前只在浏览器内存里；操作员没有发放
权限却常是实际录入的人，且 MDM 登录令牌 30 分钟过期、一被踢出全部白输。
设计见 rd-batch-registry docs/工艺草稿与自动保存设计_录入复核分离.md。

新表 batch.plan_draft（一行 = 一份尚未发放的扩增计划）：
  - 表头字段与发放请求一一对应（project_code / project_source / project_ref /
    campaign_type / start_date），容器树原样存 jsonb（plan），发放时仍走同一套
    校验与发号逻辑，草稿本身不占流水号、不占罐、不进看板。
  - status：editing 编辑中 → submitted 待复核 → issued 已发放；discarded 已作废。
  - version：乐观锁，两人同时改同一草稿时后保存者收到 409。
  - 录入人/修改人/提交人/发放人均存工号 + 姓名快照（不建人员外键，铁律）。
  - issued_batch_no：发放后回填批号，草稿不删、留审计。

Revision ID: cmc_analytics_batch_plan_draft
Revises: cmc_analytics_batch_key_by_no
Create Date: 2026-09-04
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_plan_draft"
down_revision = "cmc_analytics_batch_key_by_no"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE batch.plan_draft (
            draft_id          bigserial PRIMARY KEY,
            project_code      varchar(16)  NOT NULL,
            project_ref       varchar(64),
            project_source    varchar(8)   NOT NULL DEFAULT 'manual',
            campaign_type     varchar(16),
            start_date        date,
            note              text,
            plan              jsonb        NOT NULL DEFAULT '{}'::jsonb,
            vessel_count      integer      NOT NULL DEFAULT 0,
            status            varchar(16)  NOT NULL DEFAULT 'editing',
            version           integer      NOT NULL DEFAULT 1,
            created_by        varchar(64)  NOT NULL,
            created_by_name   varchar(128),
            updated_by        varchar(64)  NOT NULL,
            updated_by_name   varchar(128),
            submitted_by      varchar(64),
            submitted_by_name varchar(128),
            submitted_at      timestamptz,
            issued_batch_no   varchar(16),
            issued_by         varchar(64),
            issued_at         timestamptz,
            created_at        timestamptz  NOT NULL DEFAULT now(),
            updated_at        timestamptz  NOT NULL DEFAULT now(),
            CONSTRAINT ck_plan_draft_status
                CHECK (status IN ('editing','submitted','issued','discarded')),
            CONSTRAINT ck_plan_draft_project_source
                CHECK (project_source IN ('manual','mdm'))
        )
        """
    )
    # 草稿列表默认只看「编辑中 / 待复核」，按状态过滤加索引
    op.execute("CREATE INDEX ix_plan_draft_status ON batch.plan_draft (status, updated_at DESC)")
    op.execute("CREATE INDEX ix_plan_draft_created_by ON batch.plan_draft (created_by)")
    op.execute(
        "COMMENT ON TABLE batch.plan_draft IS "
        "'发放前的扩增计划草稿：操作员录入/自动保存，研究员复核后发放；plan 为容器树 jsonb'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch.plan_draft")
