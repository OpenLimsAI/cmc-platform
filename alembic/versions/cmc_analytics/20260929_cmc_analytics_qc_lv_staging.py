"""Create five QC LabVantage staging tables in cmc_analytics.

The first four tables hold the traceable source chain. The fifth table's
columns and grain are prepared, but final-result selection requires
method-level validation against CoA. This migration does not backfill data.
"""
from alembic import op

revision = "cmc_analytics_qc_lv_staging"
down_revision = "cmc_analytics_qap_reader"
branch_labels = None
depends_on = None

DDL = [
    """
CREATE TABLE staging.stg_lv_sample (
    source_system        text NOT NULL DEFAULT 'gmp_labvantage',
    s_sampleid           text NOT NULL,         -- 样品主键（= 下游 keyid1，当 sdcid='Sample'）
    sampledesc           text,
    sampletypeid         text,                  -- Finished / Stability / ...
    samplesubtypeid      text,                  -- ConcentrateSubtype / FinishedProduct / DrugProduct ...
    samplestatus         text,
    batchid              text,                  -- → s_batch.s_batchid
    u_batchno            text,                  -- 业务批号
    productid            text,
    projectid            text,
    studyid              text,
    materialid           text,
    collectiondt         timestamptz,           -- 采样时间
    receiveddt           timestamptz,
    submitteddt          timestamptz,
    starttestingdt       timestamptz,           -- 开始检测
    completedt           timestamptz,           -- 检测完成
    duedt                timestamptz,
    revieweddt           timestamptz,
    reviewedby           text,
    reviewdisposition    text,
    u_releasedt          timestamptz,           -- 放行时间
    u_releaseby          text,
    u_finalresultflag    text,
    u_testresult         text,
    assignedanalystid    text,
    testingdepartmentid  text,
    workareadepartmentid text,
    assigneddepartmentid text,
    sitedepartmentid     text,
    templateflag         text,
    basedonsampleid      text,                  -- 重测/派生来源样品
    createdt             timestamptz,
    createby             text,
    moddt                timestamptz,
    modby                text,
    _etl_loaded_at       timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_system, s_sampleid)
);
    """,
    """
CREATE INDEX ix_stg_lv_sample_batch    ON staging.stg_lv_sample (u_batchno);
    """,
    """
CREATE INDEX ix_stg_lv_sample_batchid  ON staging.stg_lv_sample (batchid);
    """,
    """
CREATE INDEX ix_stg_lv_sample_complete ON staging.stg_lv_sample (completedt);
    """,
    """
CREATE TABLE staging.stg_lv_workitem (
    source_system             text NOT NULL DEFAULT 'gmp_labvantage',
    sdcid                     text NOT NULL,    -- 'Sample'（少量 LV_ReagentLot）
    keyid1                    text NOT NULL,    -- = s_sampleid（当 sdcid='Sample'）
    keyid2                    text NOT NULL,
    keyid3                    text NOT NULL,
    workitemid                text NOT NULL,    -- 检测项目（含中文，已排除 '_Reflex'）
    workiteminstance          numeric NOT NULL,
    workitemversionid         text,
    workitemstatus            text,             -- Completed / Cancelled / InProgress ...
    appliedflag               text,
    completeflag              text,
    s_assignedanalyst         text,
    s_assigneddepartment      text,
    workitemdesc              text,             -- workitem 维度：项目中文描述
    workitem_testingdepartment text,            -- workitem 维度：执行部门
    createdt                  timestamptz,
    moddt                     timestamptz,
    _etl_loaded_at            timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_system, sdcid, keyid1, keyid2, keyid3, workitemid, workiteminstance)
);
    """,
    """
CREATE INDEX ix_stg_lv_workitem_sample ON staging.stg_lv_workitem (source_system, keyid1);
    """,
    """
CREATE INDEX ix_stg_lv_workitem_wid    ON staging.stg_lv_workitem (workitemid);
    """,
    """
CREATE TABLE staging.stg_lv_dataset (
    source_system          text NOT NULL DEFAULT 'gmp_labvantage',
    sdcid                  text NOT NULL,
    keyid1                 text NOT NULL,       -- = s_sampleid
    keyid2                 text NOT NULL,
    keyid3                 text NOT NULL,
    paramlistid            text NOT NULL,
    paramlistversionid     text NOT NULL,
    variantid              text NOT NULL,       -- 原始阶段标签；本实例多为中文，不以 '1' 判最终值
    dataset                numeric NOT NULL,
    workitemid             text,                -- 链路回指 workitem（来自桥接 sdiworkitemitem）
    workiteminstance       numeric,
    s_datasetstatus        text,
    s_notebookreference    text,
    s_assignedanalyst      text,
    s_instrumentid         text,
    s_qcbatchid            text,                -- CPK 关键
    s_qcbatchitemid        text,
    accreditedflag         text,               -- CNAS 认可
    limitruleid            text,
    limitruleversionid     text,
    paramlistdesc          text,               -- paramlist 维度
    versionstatus          text,
    s_paramlisttype        text,
    s_instrumenttype       text,
    composite_test_method_id text,             -- 派生：V_SAMPLETEST 的检测方法显示名（见 §15.2）
    createdt               timestamptz,
    moddt                  timestamptz,
    _etl_loaded_at         timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_system, sdcid, keyid1, keyid2, keyid3, paramlistid, paramlistversionid, variantid, dataset)
);
    """,
    """
CREATE INDEX ix_stg_lv_dataset_sample  ON staging.stg_lv_dataset (source_system, keyid1);
    """,
    """
CREATE INDEX ix_stg_lv_dataset_qcbatch ON staging.stg_lv_dataset (s_qcbatchid);
    """,
    """
CREATE TABLE staging.stg_lv_dataitem (
    source_system        text NOT NULL DEFAULT 'gmp_labvantage',
    sdcid                text NOT NULL,
    keyid1               text NOT NULL,        -- = s_sampleid
    keyid2               text NOT NULL,
    keyid3               text NOT NULL,
    paramlistid          text NOT NULL,
    paramlistversionid   text NOT NULL,
    variantid            text NOT NULL,
    dataset              numeric NOT NULL,
    paramid              text NOT NULL,        -- 参数（含中文，如 'pH值'）
    paramtype            text NOT NULL,        -- Standard / Average / Calculation
    replicateid          numeric NOT NULL,     -- 第几次重复
    sdidataitemid        text,                 -- LIMS 逻辑 ID（VARCHAR2，可能非唯一，仅参考）
    mandatoryflag        text,
    datatypes            text,
    enteredvalue         numeric,              -- 录入数值（部分行 NULL，用 enteredtext）
    enteredtext          text,
    enteredunits         text,
    transformvalue       numeric,              -- 变换/计算后数值
    transformtext        text,
    transformdt          timestamptz,
    displayvalue         text,                 -- 报告显示值（可能含格式，留 text）
    displayunits         text,
    releasedflag         text,                 -- 发布标志；Y 也可能是中间过程，不能单独判最终值
    valuestatus          text,                 -- NULL 正常；CALC_ERROR/TRANSFORM_FAILURE 等异常
    calcexcludeflag      text,
    reportflag           text,
    s_analystid          text,
    s_qcevalstatus       text,
    paramdesc            text,                 -- param 维度：参数中文描述
    composite_param_id   text,                 -- 派生：V_SAMPLETESTRESULT 的参数显示名（见 §15.2）
    uncertaintyvalue     numeric,
    uncertaintydisplayvalue text,
    createdt             timestamptz,          -- 结果录入时间
    moddt                timestamptz,
    _etl_loaded_at       timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_system, sdcid, keyid1, keyid2, keyid3, paramlistid, paramlistversionid, variantid, dataset, paramid, paramtype, replicateid)
);
    """,
    """
CREATE INDEX ix_stg_lv_dataitem_sample ON staging.stg_lv_dataitem (source_system, keyid1);
    """,
    """
CREATE INDEX ix_stg_lv_dataitem_param  ON staging.stg_lv_dataitem (paramid);
    """,
    """
CREATE TABLE staging.stg_lv_test_result_wide (
    source_system        text NOT NULL DEFAULT 'gmp_labvantage',
    -- 复合 PK（同 dataitem 粒度，是其过滤子集）
    sdcid                text NOT NULL,
    keyid1               text NOT NULL,
    keyid2               text NOT NULL,
    keyid3               text NOT NULL,
    paramlistid          text NOT NULL,
    paramlistversionid   text NOT NULL,
    variantid            text NOT NULL,
    dataset              numeric NOT NULL,
    paramid              text NOT NULL,
    paramtype            text NOT NULL,
    replicateid          numeric NOT NULL,
    -- 样品/批次（denormalize 自 s_sample + s_batch）
    s_sampleid           text,
    sample_name          text,                 -- ← sampledesc
    sampletypeid         text,
    samplesubtypeid      text,
    batchid              text,
    u_batchno            text,                 -- 业务批号
    batchtype            text,                 -- ← s_batch.batchtype
    disposition          text,                 -- ← s_batch.disposition（放行）
    releaseddt           timestamptz,          -- ← s_batch.releaseddt
    -- 检测方法（denormalize 自 sdiworkitem/workitem/sdidata）
    workitemid           text,
    workitemdesc         text,
    composite_test_method_id text,
    paramlistdesc        text,
    -- 参数与值（自 sdidataitem/param）
    paramdesc            text,
    composite_param_id   text,
    enteredvalue         numeric,
    transformvalue       numeric,
    displayvalue         text,
    unit                 text,                 -- ← COALESCE(displayunits, enteredunits)
    releasedflag         text,
    valuestatus          text,
    -- 执行上下文
    s_analystid          text,
    s_instrumentid       text,
    s_qcbatchid          text,
    -- 时间
    collectiondt         timestamptz,
    starttestingdt       timestamptz,
    completedt           timestamptz,
    result_createdt      timestamptz,          -- ← sdidataitem.createdt（结果录入）
    transformdt          timestamptz,
    sdidataitemid        text,
    _etl_loaded_at       timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_system, sdcid, keyid1, keyid2, keyid3, paramlistid, paramlistversionid, variantid, dataset, paramid, paramtype, replicateid)
);
    """,
    """
CREATE INDEX ix_stg_lv_trw_batch  ON staging.stg_lv_test_result_wide (u_batchno);
    """,
    """
CREATE INDEX ix_stg_lv_trw_param  ON staging.stg_lv_test_result_wide (paramid);
    """,
    """
CREATE INDEX ix_stg_lv_trw_sample ON staging.stg_lv_test_result_wide (s_sampleid);
    """,
    """
CREATE INDEX ix_stg_lv_trw_complete ON staging.stg_lv_test_result_wide (completedt);
    """,
]


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)
    for table in ('stg_lv_sample', 'stg_lv_workitem', 'stg_lv_dataset', 'stg_lv_dataitem', 'stg_lv_test_result_wide',):
        op.execute(f"GRANT SELECT, INSERT, DELETE ON staging.{table} TO lims_admin")
        op.execute(f"GRANT SELECT ON staging.{table} TO lims_reader")
    op.execute("COMMENT ON TABLE staging.stg_lv_test_result_wide IS 'QC 最终报告值宽表：结构已建，筛选规则待 CoA 逐方法验证，暂不装载'")


def downgrade() -> None:
    raise RuntimeError("QC staging tables may contain data; review backup and dependent consumers before dropping them")
