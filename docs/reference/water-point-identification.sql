-- 2026-10-02调查时的只读字段核对示例；本文件未作为已执行SQL证据。
-- 后续已确认编号来自S_SAMPLEPOINT.LOCATIONLABEL、描述来自SAMPLEPOINTDESC。
-- S_LOCATION关联及本脚本所选字段须另外核实；看板当前仅消费staging，不执行此SQL。
-- 后续源调查已核实MBTK；执行前仍核对实际目标环境/字段，不使用本脚本修改任何数据。
SELECT sp.s_samplepointid AS lims_samplepoint_id,
       sp.samplepointdesc AS source_point_description,
       sp.locationlabel AS source_point_location_label,
       sp.u_locationid AS source_point_custom_location_id,
       sp.locationid AS source_location_id,
       sp.u_samplepointtype AS source_point_type,
       sp.activeflag,
       sp.moddt,
       l.locationdesc AS source_location_description,
       l.locationlabel AS source_location_label
FROM MBTK.S_SAMPLEPOINT sp
LEFT JOIN MBTK.S_LOCATION l ON l.s_locationid = sp.locationid
WHERE sp.s_samplepointid IN (
    'SP-00000282', 'SP-00000230', 'SP-00000449', 'SP-00000136'
)
ORDER BY sp.s_samplepointid;
