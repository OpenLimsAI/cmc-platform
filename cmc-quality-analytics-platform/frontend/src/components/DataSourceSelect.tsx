import { Alert, Form, Select } from 'antd'
import type { DataSource } from '@/types'

export const sourceLabel = (value: DataSource) => ({ RD: 'RD_LIMS（研发）', QC: 'QC_LIMS（LIMS 历史）', EXCEL: 'QC_LIMS（Excel 历史导入）' })[value]

export function DataSourceNotice({ value }: { value: DataSource }) {
  if (value === 'EXCEL') return <Alert type="info" showIcon message="原看板 Excel 历史数值记录" description="保留项目代码、产线、组别和批号原值。旧表未保存独立结果单位及全部文本结果，原值及描述统计不作单位换算，质量标准另行核对。" />
  return value === 'QC' ? <Alert type="info" showIcon message="当前查看 QC 历史来源记录"
    description="来自本机共享表，尚未核验为完整、最新或已批准数据。不含老看板的 Excel 导入记录；保留原始指标和单位，不套用研发规格。" /> : null
}

export default function DataSourceSelect({ value, onChange }: { value: DataSource; onChange: (value: DataSource) => void }) {
  return <Form.Item label="数据来源" htmlFor="quality-data-source" extra={value === 'EXCEL' ? '来自 quality.quality_data 原 Excel 导入记录' : value === 'QC' ? '历史共享表记录，不含旧 Excel 导入' : '研发 LIMS 数值记录'}>
    <Select id="quality-data-source" value={value} onChange={onChange}
      options={(['RD', 'QC', 'EXCEL'] as const).map((source) => ({ value: source, label: sourceLabel(source) }))} />
  </Form.Item>
}
