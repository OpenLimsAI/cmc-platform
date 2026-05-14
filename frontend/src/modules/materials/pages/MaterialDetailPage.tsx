import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Result,
  Skeleton,
  Space,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  AuditOutlined,
  CopyOutlined,
  EditOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { materialsApi } from '@/api/materials';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { AuditLogPanel } from '@/shared/components/AuditLogPanel';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { BatchTable } from '../components/BatchTable';
import {
  MATERIAL_GRADE_OPTIONS,
  MATERIAL_TYPE_OPTIONS,
} from '../constants';

const { Title, Paragraph } = Typography;

export function MaterialDetailPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('basic');

  const { data: material, isLoading, isError } = useQuery({
    queryKey: ['material', code],
    queryFn: () => materialsApi.get(code!),
    enabled: !!code,
  });

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }
  if (isError || !material) {
    return (
      <Result
        status="404"
        title="物料不存在"
        subTitle={`未找到 ${code}`}
        extra={
          <Button type="primary" onClick={() => navigate('/materials')}>
            返回物料列表
          </Button>
        }
      />
    );
  }

  const typeDef = MATERIAL_TYPE_OPTIONS.find((o) => o.value === material.material_type);
  const gradeDef = material.grade
    ? MATERIAL_GRADE_OPTIONS.find((o) => o.value === material.grade)
    : undefined;

  const tabs = [
    {
      key: 'basic',
      label: '基本信息',
      children: (
        <Card title="详细信息">
          <Descriptions
            bordered
            column={2}
            size="middle"
            labelStyle={{ width: 140 }}
            items={[
              {
                key: 'material_code',
                label: '物料编码',
                children: <code>{material.material_code}</code>,
              },
              {
                key: 'status',
                label: '状态',
                children: <StatusBadge type="material" status={material.status} />,
              },
              { key: 'material_name', label: '名称', children: material.material_name },
              {
                key: 'material_name_en',
                label: '英文名',
                children: material.material_name_en ?? '—',
              },
              {
                key: 'material_type',
                label: '物料类型',
                children: (
                  <Tag color={typeDef?.color ?? 'default'}>
                    {typeDef?.label ?? material.material_type}
                  </Tag>
                ),
              },
              {
                key: 'grade',
                label: '等级',
                children: gradeDef ? (
                  <Tag color={gradeDef.color}>{gradeDef.label}</Tag>
                ) : (
                  '—'
                ),
              },
              {
                key: 'substance',
                label: '关联物质',
                children: material.substance_code ? (
                  <EntityCodeLink type="substance" code={material.substance_code} />
                ) : (
                  '—'
                ),
              },
              {
                key: 'physical_form',
                label: '物理形态',
                children: material.physical_form ?? '—',
              },
              {
                key: 'storage_condition',
                label: '存储条件',
                children: material.storage_condition ?? '—',
              },
              {
                key: 'source_type',
                label: '来源类型',
                children: material.source_type ?? '—',
              },
              {
                key: 'source_name',
                label: '来源名称',
                children: material.source_name ?? '—',
                span: 2,
              },
              {
                key: 'description',
                label: '描述',
                children: (
                  <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                    {material.description ?? '—'}
                  </Paragraph>
                ),
                span: 2,
              },
              {
                key: 'notes',
                label: '备注',
                children: (
                  <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                    {material.notes ?? '—'}
                  </Paragraph>
                ),
                span: 2,
              },
              {
                key: 'updated_at',
                label: '最近更新',
                children: <TimeDisplay value={material.updated_at} />,
              },
              {
                key: 'created_at',
                label: '创建时间',
                children: <TimeDisplay value={material.created_at} />,
              },
            ]}
          />
        </Card>
      ),
    },
    {
      key: 'batches',
      label: '批次列表',
      children: <BatchTable materialCode={material.material_code} />,
    },
    {
      key: 'audit',
      label: '审计',
      children: (
        <AuditLogPanel
          queryKey={['material-audit-logs', material.material_code]}
          loadFn={(page, page_size, include_children) =>
            materialsApi.auditLogs(material.material_code, {
              page,
              page_size,
              include_children,
            })
          }
          tableLabels={{
            material: '物料主表',
            material_batch: '物料批次',
          }}
        />
      ),
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/materials')}>物料</a> },
          { title: `${material.material_code} - ${material.material_name}` },
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space direction="vertical" size={4}>
            <Space>
              <Title level={3} style={{ margin: 0 }}>
                {material.material_name}
              </Title>
              <StatusBadge type="material" status={material.status} />
              {typeDef && <Tag color={typeDef.color}>{typeDef.label}</Tag>}
              {gradeDef && <Tag color={gradeDef.color}>{gradeDef.label}</Tag>}
            </Space>
            <Typography.Text type="secondary">
              <code>{material.material_code}</code>
              {material.source_name ? ` · 来源 ${material.source_name}` : ''}
              {material.substance_code ? ` · 物质 ${material.substance_code}` : ''}
            </Typography.Text>
          </Space>
          <Space wrap>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/materials')}>
              返回列表
            </Button>
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                void navigator.clipboard.writeText(material.material_code);
                message.success(`已复制编码: ${material.material_code}`);
              }}
            >
              复制编码
            </Button>
            <Button
              size="small"
              icon={<ShareAltOutlined />}
              onClick={() => {
                void navigator.clipboard.writeText(window.location.href);
                message.success('已复制详情页链接');
              }}
            >
              分享
            </Button>
            <Button size="small" icon={<AuditOutlined />} onClick={() => setActiveTab('audit')}>
              查看审计
            </Button>
            <PermissionGuard permission="material:update">
              <Button
                type="primary"
                icon={<EditOutlined />}
                onClick={() =>
                  navigate(`/materials/${encodeURIComponent(material.material_code)}/edit`)
                }
              >
                编辑
              </Button>
            </PermissionGuard>
          </Space>
        </div>
      </Card>

      <Tabs items={tabs} activeKey={activeTab} onChange={setActiveTab} />
    </div>
  );
}
