import { useState } from 'react'
import { Alert, Button, Form, InputNumber, Radio, Select, Space } from 'antd'
import DataSourceSelect from './DataSourceSelect'
import type { ProjectMeta, ReleaseOptions, ReleaseRequest } from '@/types'
import { attributeLabel } from '@/services/releasePresentation'

interface Props {
  value: ReleaseRequest
  projects: ProjectMeta[]
  options: ReleaseOptions | null
  optionsLoading: boolean
  projectError: string | null
  optionsError: string | null
  onChange: (value: ReleaseRequest) => void
  onReset: () => void
  onRetry: () => void
}

export default function FilterPanel({ value, projects, options, optionsLoading, projectError, optionsError, onChange, onReset, onRetry }: Props) {
  const [expanded, setExpanded] = useState(true)
  const change = (patch: Partial<ReleaseRequest>) => onChange({ ...value, ...patch })
  const disabled = !options || optionsLoading
  const multi = (field: 'production_line_ids' | 'group_ids' | 'batch_numbers' | 'test_types' | 'placement_statuses', label: string, choices: string[]) => (
    <Form.Item label={label} htmlFor={'filter-' + field}>
      <Select id={'filter-' + field} mode="multiple" allowClear showSearch maxTagCount="responsive" placeholder="全部"
        disabled={disabled} value={value[field] || []} options={choices.map((item) => ({ value: item, label: item }))}
        onChange={(items) => change({ [field]: items })} />
    </Form.Item>
  )
  return (
    <details className="qap-filter-section" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary>数据筛选<span>展开 / 收起</span></summary>
      <div className="qap-filter-content">
        <Form layout="vertical" requiredMark={false}>
          <DataSourceSelect value={value.data_source} onChange={(data_source) => change({ data_source })} />
          <Form.Item label="项目" htmlFor="filter-project" extra="逐项目分析，避免混用项目规格">
            <Select id="filter-project" showSearch allowClear placeholder="选择项目" value={value.project_id || undefined}
              options={projects.map((p) => ({ value: p.project_id, label: p.project_id + '（' + p.n + '条来源记录）' }))}
              onChange={(projectId) => change({ project_id: projectId || '' })} optionFilterProp="label" />
          </Form.Item>
          {projectError && <Alert type="error" message={projectError} action={<Button onClick={onRetry}>重试</Button>} />}
          {optionsError && <Alert type="error" message={optionsError} action={<Button onClick={onRetry}>重试</Button>} />}
          <Form.Item label="样品类型" htmlFor="filter-sample">
            <Select id="filter-sample" allowClear placeholder="全部" disabled={disabled} value={value.sample_type || undefined}
              options={options?.sample_types.map((type) => ({ value: type, label: type }))} onChange={(type) => change({ sample_type: type || null })} />
          </Form.Item>
          {multi('production_line_ids', '产线', options?.production_line_ids || [])}
          {multi('group_ids', '组别', options?.group_ids || [])}
          {multi('batch_numbers', '批号', options?.batch_numbers || [])}
          {multi('test_types', '检验类别', options?.test_types || [])}
          {value.data_source === 'EXCEL' && multi('placement_statuses', '放置状态', options?.placement_statuses || [])}
          <Form.Item label="批号年份（推算）" htmlFor="filter-year" extra="沿用旧版批号规则，不是检测日期">
            <Select id="filter-year" mode="multiple" allowClear placeholder="全部（包含未识别）" disabled={disabled}
              value={[...(value.batch_years || []), ...(value.include_unknown_batch_year ? ['unknown'] : [])]}
              options={[...(options?.batch_years || []).map((year) => ({ value: year as string | number, label: String(year) })),
                ...(options?.unknown_batch_year_count ? [{ value: 'unknown', label: '未识别（' + options.unknown_batch_year_count + '条）' }] : [])]}
              onChange={(years: (number | string)[]) => change({ batch_years: years.filter((year): year is number => typeof year === 'number'), include_unknown_batch_year: years.includes('unknown') })} />
          </Form.Item>
          <Form.Item label="质量属性" htmlFor="filter-attribute" extra="也可使用右侧常用指标组合；留空选择全部">
            <Select id="filter-attribute" mode="multiple" allowClear showSearch maxTagCount={3} placeholder="全部检测项" disabled={disabled}
              value={value.attribute_names || []} optionFilterProp="search"
              options={options?.attributes.map((attr) => ({ value: attr.attribute_name, label: attributeLabel(attr.attribute_name, options.attributes), search: attributeLabel(attr.attribute_name, options.attributes) + ' ' + attr.attribute_name + ' ' + attr.attribute_raws.join(' ') }))}
              onChange={(items) => change({ attribute_names: items })} />
          </Form.Item>
          {value.data_source === 'EXCEL' && <>
            <Form.Item label="SD参考数据" htmlFor="release-sd-reference">
              <Select id="release-sd-reference" value={value.sd_reference_mode || 'current'} options={[{value:'current',label:'当前筛选数据'}, {value:'history',label:'所选最新年份之前的历史数据'}]}
                onChange={(mode) => change({sd_reference_mode:mode})} />
            </Form.Item>
            {value.sd_reference_mode === 'history' && <Form.Item label="回顾历史年数" extra="依据批号推算年份；其他筛选条件保持一致，不足3条不画SD线。">
              <InputNumber min={1} max={10} precision={0} value={value.lookback_years || 3} onChange={(years) => change({lookback_years:years || 3})} />
            </Form.Item>}
          </>}
          <Form.Item label="能力指数计算方式">
            <Radio.Group disabled={value.data_source !== 'RD'} value={value.capability_mode} onChange={(event) => change({ capability_mode: event.target.value })}>
              <Space direction="vertical" size={4}><Radio value="population">总体标准差（Ppk / PPU / PPL）</Radio><Radio value="sample">样本标准差（Cpk / CPU / CPL）</Radio></Space>
            </Radio.Group>
          </Form.Item>
          {value.data_source !== 'RD' && <p className="qap-hint">QC 规格和单位尚未复核，暂不计算能力指数。</p>}
          <div className="qap-filter-actions">
            <Button onClick={onReset} aria-label="重置筛选">重置</Button>
          </div>
          <p className="qap-hint">修改条件后自动更新图表。清空某项表示不限制该项。</p>
        </Form>
      </div>
    </details>
  )
}
