import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Card, Descriptions, Empty, Select, Space, Spin, Table, Tag, Typography, Upload } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '@/auth/AuthProvider'
import { api } from '@/services/api'
import type { ImportCapabilities, PreviewCell, PreviewIssue, PreviewResponse, PreviewRow } from '@/types/imports'

const { Title, Paragraph, Text } = Typography

function rawText(value: unknown): string {
  if (value === null || value === undefined) return '（空值）'
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function CellValue({ cell }: { cell: PreviewCell | undefined }) {
  if (!cell) return <Text type="secondary">未提供</Text>
  return (
    <div>
      <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{rawText(cell.value)}</div>
      <Text type="secondary" style={{ fontSize: 12 }}>{cell.coordinate} · {cell.data_type} · {cell.number_format}</Text>
      {cell.data_type === 'f' && <div><Text type="secondary">公式缓存：{rawText(cell.cached_value)}（未执行公式）</Text></div>}
    </div>
  )
}

function PreviewResult({ result, headers }: { result: PreviewResponse; headers: string[] }) {
  const { preview } = result
  const cells = new Map(preview.rows.flatMap((row) => row.cells.map((cell) => [cell.coordinate, cell] as const)))
  const rowColumns: ColumnsType<PreviewRow> = [
    { title: 'Excel 行', dataIndex: 'row_number', width: 90, fixed: 'left' },
    ...(preview.columns?.length ? preview.columns.map((column) => ({
      title: <><div>{column.source_label || column.source_header || `第${column.column_index}列`}</div><Text type="secondary">{column.source_header}</Text></>,
      key: String(column.column_index), width: 190,
      render: (_: unknown, row: PreviewRow) => <CellValue cell={row.cells.find((cell) => {
        const letters = cell.coordinate.replace(/[0-9]/g, '')
        const index = [...letters].reduce((sum, char) => sum * 26 + char.charCodeAt(0) - 64, 0)
        return index === column.column_index
      })} />,
    })) : headers.map((field) => ({
      title: field, key: field, width: 190,
      render: (_: unknown, row: PreviewRow) => <CellValue cell={row.cells.find((cell) => cell.source_header === field)} />,
    }))),
  ]
  const issueColumns: ColumnsType<PreviewIssue> = [
    { title: '级别', dataIndex: 'severity', width: 85, render: (severity: string) => <Tag color={severity === 'error' ? 'error' : 'warning'}>{severity === 'error' ? '错误' : '警告'}</Tag> },
    { title: '位置', key: 'position', width: 160, render: (_, issue) => [issue.sheet_name, issue.coordinate || (issue.row_number ? `第 ${issue.row_number} 行` : issue.column_name)].filter(Boolean).join(' · ') || '文件/模板' },
    { title: '问题', dataIndex: 'message' },
    { title: '原值', key: 'raw', width: 200, render: (_, issue) => issue.coordinate && cells.has(issue.coordinate) ? <CellValue cell={cells.get(issue.coordinate)} /> : <Text type="secondary">请按位置核对原文件</Text> },
    { title: '问题代码', dataIndex: 'code', width: 160 },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Alert showIcon type={preview.structure_valid ? 'info' : 'warning'}
        message={preview.structure_valid ? '结构预览完成，尚未导入' : '发现结构问题，尚未导入'}
        description="结构检查仅确认文件可按模板解析。检测项、规格、单位换算和数据批准状态仍待业务校验，不能据此认定结果已通过质量审核。" />
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
        <Descriptions.Item label="文件">{preview.original_filename}</Descriptions.Item>
        <Descriptions.Item label="工作表">{preview.sheet_name}</Descriptions.Item>
        <Descriptions.Item label="操作人">{result.actor.full_name || result.actor.username}（{result.actor.username}）</Descriptions.Item>
        <Descriptions.Item label="记录行">{result.total_row_count}</Descriptions.Item>
        <Descriptions.Item label="问题总数">{result.total_issue_count}</Descriptions.Item>
        <Descriptions.Item label="空行">{preview.blank_row_count}</Descriptions.Item>
        <Descriptions.Item label="模板版本">{preview.template_code} / {preview.template_version}</Descriptions.Item>
        <Descriptions.Item label="解析版本">{preview.parser_version}</Descriptions.Item>
        <Descriptions.Item label="状态"><Tag>业务校验待实现</Tag><Tag>未写入数据库</Tag></Descriptions.Item>
        <Descriptions.Item label="文件 SHA256" span={3}><Text code style={{ overflowWrap: 'anywhere' }}>{preview.file_sha256}</Text></Descriptions.Item>
      </Descriptions>
      {(result.rows_truncated || result.issues_truncated) && <Alert type="warning" showIcon
        message="以下内容仅展示部分结果"
        description={`记录展示 ${preview.rows.length} / ${result.total_row_count} 行；问题展示 ${preview.issues.length} / ${result.total_issue_count} 条。服务端已完成全文件结构校验，未展示部分不代表没有错误；请按问题坐标核对原文件。`} />}
      <Card title={`结构问题（${result.total_issue_count} 条）`} size="small">
        {preview.issues.length ? <Table columns={issueColumns} dataSource={preview.issues} rowKey={(_, index) => String(index)} size="small" pagination={{ pageSize: 20, showSizeChanger: false }} scroll={{ x: 950 }} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="本次未发现结构问题；业务校验尚未执行" />}
      </Card>
      <Card title={`原始单元格预览（展示 ${preview.rows.length} 行）`} size="small">
        <Paragraph type="secondary">保留单元格原值、坐标和显示格式。批号未改写；单元格看起来相同不代表业务重复。</Paragraph>
        <Table columns={rowColumns} dataSource={preview.rows} rowKey="row_number" size="small" pagination={{ pageSize: 20, showSizeChanger: false }} scroll={{ x: 1040 }} />
      </Card>
    </Space>
  )
}

function AuthorizedPreview() {
  const [capabilities, setCapabilities] = useState<ImportCapabilities | null>(null)
  const [templateCode, setTemplateCode] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<PreviewResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [capabilityError, setCapabilityError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const requestGeneration = useRef(0)
  const request = useRef<AbortController | null>(null)
  const template = useMemo(() => capabilities?.templates.find((item) => item.template_code === templateCode), [capabilities, templateCode])

  useEffect(() => {
    let cancelled = false
    setCapabilityError(null)
    void api.importCapabilities().then(({ data }) => {
      if (cancelled) return
      setCapabilities(data)
      setTemplateCode(data.templates[0]?.template_code ?? '')
    }).catch((cause) => {
      if (!cancelled) setCapabilityError(cause instanceof Error ? cause.message : '无法读取模板信息')
    })
    return () => { cancelled = true }
  }, [reload])

  useEffect(() => () => {
    requestGeneration.current += 1
    request.current?.abort()
  }, [])

  const clearPreview = () => {
    requestGeneration.current += 1
    request.current?.abort()
    setResult(null)
    setError(null)
    setBusy(false)
  }

  const selectFile = (selected: File | null) => {
    clearPreview()
    setFile(selected)
    if (selected && !selected.name.toLowerCase().endsWith('.xlsx')) setError('请选择 .xlsx 文件')
    else if (selected && template && selected.size > template.max_file_bytes) setError(`文件超过模板允许的 ${template.max_file_bytes / 1024 / 1024} MB`)
  }

  const download = async () => {
    if (!template) return
    setDownloading(true)
    setError(null)
    try {
      const response = await api.downloadTemplate(template.template_code)
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${template.template_code}.xlsx`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '模板下载未完成')
    } finally {
      setDownloading(false)
    }
  }

  const preview = async () => {
    if (!file || !template) return
    const generation = ++requestGeneration.current
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const { data } = await api.previewImport(file, template.template_code, controller.signal)
      if (generation === requestGeneration.current) setResult(data)
    } catch (cause) {
      if (generation === requestGeneration.current && !axios.isCancel(cause)) setError(cause instanceof Error ? cause.message : '结构预览未完成')
    } finally {
      if (generation === requestGeneration.current) setBusy(false)
    }
  }

  if (capabilityError) return <Alert type="error" showIcon message={capabilityError} action={<Button onClick={() => setReload((value) => value + 1)}>重试</Button>} />
  if (!capabilities) return <Spin tip="正在读取可用模板…"><div style={{ minHeight: 100 }} /></Spin>
  const invalidFile = !file || !file.name.toLowerCase().endsWith('.xlsx') || !template || file.size > template.max_file_bytes

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card size="small" title="选择文件并检查结构">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap>
            <Text>模板</Text>
            <Select aria-label="结构预览模板" style={{ minWidth: 250 }} value={templateCode || undefined} options={capabilities.templates.map((item) => ({ value: item.template_code, label: item.label }))} onChange={(code) => { clearPreview(); setTemplateCode(code) }} />
            <Button onClick={download} loading={downloading} disabled={!template}>下载结构示例模板</Button>
          </Space>
          {template && <Text type="secondary">工作表：{template.sheet_name}；英文表头第 {template.header_row || 1} 行{template.label_row ? `，中文表头第 ${template.label_row} 行` : ''}；数据从第 {template.data_start_row || 2} 行开始。必需表头：{template.headers.join('、')}。单文件最大 {template.max_file_bytes / 1024 / 1024} MB。此模板尚未获得正式业务批准。</Text>}
          {templateCode === 'qap_first_table_v1' && <Alert type="info" showIcon message="直接使用现有项目第一表，不必改成五列长表"
            description="项目、组别、生产线、批号、放置状态及时间字段按原英文表头读取。后续检测项保留原名、原值和中文标题；未确认映射会列为待核对。当前只预览，不保存或改变看板数据。" />}
          <Space wrap>
            <Upload accept=".xlsx" beforeUpload={(selected) => { selectFile(selected); return false }} showUploadList={false} maxCount={1}>
              <Button disabled={!template}>选择 Excel 文件</Button>
            </Upload>
            {file && <><Text>{file.name}（{(file.size / 1024).toFixed(1)} KB）</Text><Button type="text" onClick={() => selectFile(null)}>移除</Button></>}
            <Button type="primary" aria-label="校验并预览结构" onClick={preview} loading={busy} disabled={invalidFile}>校验并预览结构</Button>
          </Space>
          <Text type="secondary">当前仅做结构预览，不保留原文件、不执行公式、不写入质量数据。更换文件或模板后须重新预览。</Text>
        </Space>
      </Card>
      {error && <Alert type="error" showIcon message={error} />}
      {busy && <Spin tip="正在读取并校验文件…"><div style={{ minHeight: 100 }} /></Spin>}
      {result && <PreviewResult result={result} headers={template?.headers ?? []} />}
    </Space>
  )
}

export default function ImportPreviewPage() {
  const { status, user, canPreview, loading, error, reload } = useAuth()
  return (
    <div>
      <Title level={3}>Excel 结构预览</Title>
      <Paragraph>上传前先检查模板、查看原始单元格和问题位置。本轮提供预览，正式导入与业务校验尚未开放。</Paragraph>
      {/* 续期核验期间隐藏内容但保留同一已验证身份的文件；换人或撤权则销毁。 */}
      <div hidden={!canPreview}>
        {user?.can_preview && <AuthorizedPreview key={user.subject} />}
      </div>
      {loading ? <Spin tip="正在核验预览权限…"><div style={{ minHeight: 100 }} /></Spin> : !canPreview && <Alert showIcon type="info"
        message={!status?.configured ? 'MDM 接入尚未就绪，结构预览未开放' : user ? '当前账号尚无结构预览权限' : '结构预览需要 MDM 员工身份'}
        description={error || '预览权限由后端验证。本地只读开发模式不会开放上传预览，也不能执行导入。'}
        action={<Space><Button onClick={reload}>重新检查</Button>{status?.configured && <Link to="/login">登录 MDM</Link>}</Space>} />}
    </div>
  )
}
