-- 只读源字段核对示例，未在 Oracle 执行。
-- 来源 owner MBTK 须在实际目标环境确认；不使用本脚本建立或修改任何数据。
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
