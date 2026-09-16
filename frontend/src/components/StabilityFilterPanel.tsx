import { useState } from 'react'
import { Alert, Button, Form, Select } from 'antd'
import type { DataSource, ProjectMeta } from '@/types'
import DataSourceSelect from './DataSourceSelect'
import type { StabilityOptions, StabilityRequest } from '@/types/stability'
import { attributeLabel } from '@/services/releasePresentation'

export const emptyStability = (project_id = '', data_source: DataSource = 'RD'): StabilityRequest => ({ project_id, sample_types: [], test_types: [], production_line_ids: [], group_ids: [], batch_numbers: [], placement_statuses: [], attribute_names: [], data_source })

interface Props {
  value: StabilityRequest; projects: ProjectMeta[]; options: StabilityOptions | null
  optionsLoading: boolean; error: string | null
  onChange: (value: StabilityRequest) => void; onRetry: () => void
}
export default function StabilityFilterPanel({ value, projects, options, optionsLoading, error, onChange, onRetry }: Props) {
  const [expanded, setExpanded] = useState(true)
  const disabled = !options || optionsLoading
  const choose = (field: 'sample_types' | 'test_types' | 'production_line_ids' | 'group_ids' | 'batch_numbers' | 'placement_statuses', items: string[]) => {
    const next = { ...value, [field]: items, attribute_names: [] }
    if (field !== 'batch_numbers') next.batch_numbers = []
    if (field === 'sample_types') next.test_types = []
    if (field === 'sample_types' || field === 'test_types') { next.group_ids = []; next.production_line_ids = []; next.placement_statuses = [] }
    onChange(next)
  }
  const multi = (field: 'sample_types' | 'test_types' | 'production_line_ids' | 'group_ids' | 'batch_numbers' | 'placement_statuses', label: string) => (
    <Form.Item key={field} label={label} htmlFor={'stability-' + field}>
      <Select id={'stability-' + field} mode="multiple" allowClear showSearch maxTagCount="responsive" placeholder="全部"
        disabled={disabled} value={value[field]} options={(options?.[field] || []).map((item) => ({ value: item, label: item || '未填写（空文本）' }))}
        onChange={(items) => choose(field, items)} />
    </Form.Item>
  )
  return <details className="qap-filter-section" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary>稳定性筛选<span>展开 / 收起</span></summary>
    <div className="qap-filter-content">
      <Form layout="vertical" requiredMark={false}>
        <DataSourceSelect value={value.data_source} onChange={(source) => onChange(emptyStability('', source))} />
        <Form.Item label="项目" htmlFor="stability-project" extra="括号为项目全部数值来源记录数">
          <Select id="stability-project" showSearch allowClear placeholder="选择项目" value={value.project_id || undefined} optionFilterProp="label"
            options={projects.map((project) => ({ value: project.project_id, label: `${project.project_id}（${project.n}条来源记录）` }))}
            onChange={(project) => onChange(emptyStability(project || '', value.data_source))} />
        </Form.Item>
        {error && <Alert type="error" showIcon message={error} action={<Button onClick={onRetry}>重试筛选</Button>} />}
        {multi('sample_types', '样品类型')}{multi('test_types', '检验类别')}
        {value.data_source === 'EXCEL' && multi('placement_statuses', '放置状态')}
        {multi('production_line_ids', '产线')}{multi('group_ids', '组别')}{multi('batch_numbers', '批号')}
        <Form.Item label="质量属性" htmlFor="stability-attributes" extra="更改上游条件会清除批号和指标选择">
          <Select id="stability-attributes" mode="multiple" allowClear showSearch maxTagCount={3} placeholder="全部检测项" disabled={disabled}
            value={value.attribute_names} optionFilterProp="search"
            options={(options?.attributes || []).map((attr) => ({ value: attr.attribute_name, label: attributeLabel(attr.attribute_name, options?.attributes), search: attributeLabel(attr.attribute_name) + ' ' + attr.attribute_name + ' ' + attr.attribute_raws.join(' ') }))}
            onChange={(items) => onChange({ ...value, attribute_names: items })} />
        </Form.Item>
        <div className="qap-filter-actions">
          <Button aria-label="重置稳定性筛选" onClick={() => onChange(emptyStability(value.project_id, value.data_source))}>重置</Button>
        </div>
        <p className="qap-hint">修改条件后自动更新。清空某项表示不限该项。批号候选只来自所选稳定性类别，不混入仅做放行的批号。</p>
      </Form>
    </div>
  </details>
}
